//! Embed the lab dashboard route into the existing ecc-control-pane.
//!
//! The control pane already serves a small status site on its configured
//! port. This module renders an extra page that iframes the lab dashboard
//! (or, when the frontend is not running, embeds a minimal status table
//! served by the lab API gateway).

use crate::lab::{LabConfig, SubsystemStatus};

/// Render an HTML fragment for the lab section of the control pane.
pub fn render_lab_section(cfg: &LabConfig, status: &[SubsystemStatus]) -> String {
    let api_url = format!("http://localhost:{}", cfg.api_port);
    let dashboard_url = cfg
        .frontend_dir
        .as_ref()
        .map(|_| "http://localhost:3000/lab".to_string())
        .unwrap_or_else(|| format!("{api_url}/api/lab/health"));
    let mut rows = String::new();
    for s in status {
        rows.push_str(&format!(
            "<tr><td><code>{}</code></td><td>{}</td><td>{}</td><td>{}</td></tr>",
            html_escape(&s.name),
            s.pid.map(|p| p.to_string()).unwrap_or_else(|| "—".into()),
            if s.running { "running" } else { "stopped" },
            s.restarts
        ));
    }
    format!(
        r#"
<section id="ecc-lab">
  <h2>ECC Lab</h2>
  <p>API: <a href="{api_url}/api/lab/health" target="_blank">{api_url}</a> · Dashboard: <a href="{dashboard_url}" target="_blank">{dashboard_url}</a></p>
  <table class="lab-status">
    <thead><tr><th>subsystem</th><th>pid</th><th>state</th><th>restarts</th></tr></thead>
    <tbody>
      {rows}
    </tbody>
  </table>
  <iframe src="{dashboard_url}" style="width:100%;min-height:480px;border:1px solid #d4d8de;border-radius:8px;margin-top:12px;"></iframe>
</section>
"#
    )
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;").replace('<', "&lt;").replace('>', "&gt;")
}
