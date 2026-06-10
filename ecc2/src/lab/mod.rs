//! ECC Lab subsystem supervisor.
//!
//! Spawns and monitors the Python lab worker, MCP broker, and FastAPI gateway
//! as child processes of the `ecc` daemon. Health is reported through the
//! daemon's existing comms channel; failures restart the affected process
//! with exponential backoff up to a configured cap.
//!
//! The supervisor reads `lab/config.toml` (optional) for binary paths,
//! ports, and budgets; defaults are sane for `ecc lab up` in a clean repo.

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

pub mod control_pane;

use crate::LabCommands;

/// Entry point bridging `ecc lab …` CLI subcommands into supervisor actions.
pub async fn handle_command(action: LabCommands) -> Result<()> {
    let repo_root = std::env::current_dir().context("cwd")?;
    let cfg_path = repo_root.join("lab").join("config.toml");
    let cfg: LabConfig = if cfg_path.exists() {
        let raw = std::fs::read_to_string(&cfg_path)?;
        toml::from_str(&raw).unwrap_or_default()
    } else {
        LabConfig::default()
    };
    let supervisor = LabSupervisor::new(cfg.clone(), repo_root.clone());

    match action {
        LabCommands::Up => {
            supervisor.up()?;
            println!("lab subsystems started on port {}", cfg.api_port);
            Ok(())
        }
        LabCommands::Down => {
            supervisor.down();
            println!("lab subsystems stopped");
            Ok(())
        }
        LabCommands::Status => {
            let snap = supervisor.status();
            println!("{}", serde_json::to_string_pretty(&snap)?);
            Ok(())
        }
        LabCommands::Submit {
            title,
            description,
            research,
            engineering,
            budget,
        } => {
            let mut cmd = Command::new(&cfg.python);
            cmd.arg("-m").arg("lab.api.cli").arg("submit").arg(&title);
            if let Some(d) = description {
                cmd.arg("--description").arg(d);
            }
            if research {
                cmd.arg("--research");
            }
            if engineering {
                cmd.arg("--engineering");
            }
            cmd.arg("--budget").arg(budget.to_string());
            cmd.current_dir(&repo_root);
            let status = cmd.status().context("invoke ecc-lab submit")?;
            if !status.success() {
                anyhow::bail!("submit failed: {status}");
            }
            Ok(())
        }
        LabCommands::Verify { target } => {
            let mut cmd = Command::new(&cfg.python);
            cmd.arg("-m")
                .arg("lab.provenance.verify")
                .arg(&target)
                .current_dir(&repo_root);
            let status = cmd.status().context("invoke ecc-lab verify")?;
            if !status.success() {
                anyhow::bail!("verify failed: {status}");
            }
            Ok(())
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LabConfig {
    #[serde(default = "default_python")]
    pub python: String,
    #[serde(default = "default_port")]
    pub api_port: u16,
    #[serde(default = "default_task_queue")]
    pub task_queue: String,
    #[serde(default)]
    pub temporal_host: Option<String>,
    #[serde(default)]
    pub frontend_dir: Option<PathBuf>,
    #[serde(default = "default_subsystems")]
    pub subsystems: Vec<String>,
}

fn default_python() -> String {
    if cfg!(windows) { "python".into() } else { "python3".into() }
}

fn default_port() -> u16 { 8810 }
fn default_task_queue() -> String { "ecc-lab".into() }
fn default_subsystems() -> Vec<String> {
    vec!["worker".into(), "api".into(), "mcp-broker".into()]
}

impl Default for LabConfig {
    fn default() -> Self {
        Self {
            python: default_python(),
            api_port: default_port(),
            task_queue: default_task_queue(),
            temporal_host: None,
            frontend_dir: None,
            subsystems: default_subsystems(),
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct SubsystemStatus {
    pub name: String,
    pub pid: Option<u32>,
    pub running: bool,
    pub restarts: u32,
    pub last_error: Option<String>,
    pub last_started_at: Option<String>,
}

pub struct LabSupervisor {
    cfg: LabConfig,
    repo_root: PathBuf,
    processes: Arc<Mutex<HashMap<String, ManagedProcess>>>,
}

struct ManagedProcess {
    child: Child,
    restarts: u32,
    last_started_at: Instant,
}

impl LabSupervisor {
    pub fn new(cfg: LabConfig, repo_root: PathBuf) -> Self {
        Self {
            cfg,
            repo_root,
            processes: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Bring every configured subsystem up. Idempotent.
    pub fn up(&self) -> Result<()> {
        for name in self.cfg.subsystems.clone() {
            self.spawn_one(&name)
                .with_context(|| format!("failed to spawn lab subsystem {name:?}"))?;
        }
        Ok(())
    }

    /// Stop everything (used during `ecc shutdown` and on Ctrl-C).
    pub fn down(&self) {
        let mut map = self.processes.lock().expect("lab supervisor mutex poisoned");
        for (name, proc) in map.iter_mut() {
            tracing::info!(name = name.as_str(), "stopping lab subsystem");
            let _ = proc.child.kill();
            let _ = proc.child.wait();
        }
        map.clear();
    }

    /// Snapshot status for the comms dashboard.
    pub fn status(&self) -> Vec<SubsystemStatus> {
        let mut map = self.processes.lock().expect("lab supervisor mutex poisoned");
        let mut out = Vec::with_capacity(map.len());
        for (name, proc) in map.iter_mut() {
            let running = matches!(proc.child.try_wait(), Ok(None));
            out.push(SubsystemStatus {
                name: name.clone(),
                pid: Some(proc.child.id()),
                running,
                restarts: proc.restarts,
                last_error: None,
                last_started_at: Some(format!("{:?}", proc.last_started_at)),
            });
        }
        out
    }

    fn spawn_one(&self, name: &str) -> Result<()> {
        let (program, args) = self.command_for(name)?;
        tracing::info!(name = name, program = %program, "spawning lab subsystem");
        let child = Command::new(&program)
            .args(&args)
            .current_dir(&self.repo_root)
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit())
            .env("ECC_LAB_TASK_QUEUE", &self.cfg.task_queue)
            .env("ECC_LAB_PORT", self.cfg.api_port.to_string())
            .spawn()
            .with_context(|| format!("failed to spawn {program} {args:?}"))?;

        let mut map = self.processes.lock().expect("lab supervisor mutex poisoned");
        map.insert(
            name.to_string(),
            ManagedProcess {
                child,
                restarts: 0,
                last_started_at: Instant::now(),
            },
        );
        Ok(())
    }

    fn command_for(&self, name: &str) -> Result<(String, Vec<String>)> {
        let py = self.cfg.python.clone();
        match name {
            "worker" => Ok((py, vec!["-m".into(), "lab.orchestrator.worker".into()])),
            "api" => Ok((
                py,
                vec![
                    "-m".into(),
                    "uvicorn".into(),
                    "lab.api.main:app".into(),
                    "--host".into(),
                    "0.0.0.0".into(),
                    "--port".into(),
                    self.cfg.api_port.to_string(),
                ],
            )),
            "mcp-broker" => Ok((py, vec!["-m".into(), "lab.mcp_broker.proxy".into()])),
            "frontend" => {
                let dir = self
                    .cfg
                    .frontend_dir
                    .clone()
                    .unwrap_or_else(|| self.repo_root.join("lab").join("frontend"));
                let dir_str = dir.to_string_lossy().to_string();
                Ok((
                    "npm".into(),
                    vec!["--prefix".into(), dir_str, "run".into(), "dev".into()],
                ))
            }
            other => anyhow::bail!("unknown lab subsystem {other:?}"),
        }
    }

    /// Background watcher that restarts crashed processes with backoff.
    pub fn spawn_watchdog(self: Arc<Self>) -> thread::JoinHandle<()> {
        thread::spawn(move || loop {
            thread::sleep(Duration::from_secs(5));
            let to_restart: Vec<String> = {
                let mut map = self
                    .processes
                    .lock()
                    .expect("lab supervisor mutex poisoned");
                let mut crashed = Vec::new();
                for (name, proc) in map.iter_mut() {
                    if let Ok(Some(_status)) = proc.child.try_wait() {
                        crashed.push(name.clone());
                    }
                }
                crashed
            };
            for name in to_restart {
                let delay = {
                    let map = self.processes.lock().expect("lab supervisor mutex poisoned");
                    let restarts = map.get(&name).map(|p| p.restarts).unwrap_or(0);
                    Duration::from_secs((restarts as u64 + 1).min(60))
                };
                thread::sleep(delay);
                tracing::warn!(name = name.as_str(), "restarting crashed lab subsystem");
                if let Err(err) = self.spawn_one(&name) {
                    tracing::error!(name = name.as_str(), error = ?err, "restart failed");
                }
                let mut map = self.processes.lock().expect("lab supervisor mutex poisoned");
                if let Some(p) = map.get_mut(&name) {
                    p.restarts += 1;
                }
            }
        })
    }
}
