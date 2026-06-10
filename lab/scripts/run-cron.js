#!/usr/bin/env node
// Entry point invoked by host cron / GitHub Actions / Windows Task
// Scheduler. Reads `lab/scripts/cron.yaml`, runs the job whose name was
// passed on the command line, captures stdout/stderr, and posts a
// `lab.audit_event` to the local lab-event-router so the dashboard
// reflects the audit run.

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function parseSimpleYaml(text) {
  // Very small YAML reader scoped to the shapes this file uses: a
  // top-level `defaults` map and a list of `jobs` objects. Supports
  // string values and `${VAR}` substitution. Avoids pulling in a full
  // YAML dependency for one config file.
  const lines = text.split(/\r?\n/);
  const defaults = {};
  const jobs = [];
  let mode = null;
  let currentJob = null;
  for (const raw of lines) {
    const line = raw.replace(/\t/g, '  ');
    if (!line.trim() || line.trim().startsWith('#')) continue;
    if (line.startsWith('defaults:')) { mode = 'defaults'; continue; }
    if (line.startsWith('jobs:')) { mode = 'jobs'; continue; }
    if (mode === 'defaults' && line.startsWith('  ') && line.includes(':')) {
      const [k, ...rest] = line.trim().split(':');
      defaults[k.trim()] = rest.join(':').trim();
    } else if (mode === 'jobs') {
      if (line.startsWith('  - ')) {
        if (currentJob) jobs.push(currentJob);
        currentJob = {};
        const after = line.replace('  - ', '').trim();
        if (after.includes(':')) {
          const [k, ...rest] = after.split(':');
          currentJob[k.trim()] = rest.join(':').trim();
        }
      } else if (line.startsWith('    ') && line.includes(':')) {
        const [k, ...rest] = line.trim().split(':');
        currentJob[k.trim()] = rest.join(':').trim();
      }
    }
  }
  if (currentJob) jobs.push(currentJob);
  return { defaults, jobs };
}

function substitute(value, env) {
  if (typeof value !== 'string') return value;
  return value.replace(/\$\{([A-Z_][A-Z0-9_]*)\}/g, (_, name) => env[name] || '');
}

function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('usage: run-cron.js <job-name>');
    process.exit(2);
  }
  const jobName = args[0];
  const cronPath = path.join(__dirname, 'cron.yaml');
  const text = fs.readFileSync(cronPath, 'utf8');
  const { defaults, jobs } = parseSimpleYaml(text);
  const job = jobs.find((j) => j.name === jobName);
  if (!job) {
    console.error(`unknown job: ${jobName}`);
    process.exit(2);
  }
  const cwd = substitute(job.cwd || defaults.cwd || process.cwd(), process.env);
  const shell = job.shell || defaults.shell || 'bash';
  const command = job.command;
  const started = new Date().toISOString();
  const result = spawnSync(shell, ['-c', command], { cwd, env: process.env, encoding: 'utf8' });
  const finished = new Date().toISOString();
  const event = {
    type: 'lab.audit_event',
    job: jobName,
    started_at: started,
    finished_at: finished,
    exit_code: result.status,
    stdout_tail: (result.stdout || '').slice(-2000),
    stderr_tail: (result.stderr || '').slice(-2000),
  };
  const router = path.join(__dirname, '..', '..', 'scripts', 'hooks', 'lab-event-router.js');
  if (fs.existsSync(router)) {
    const dispatch = spawnSync('node', [router], {
      input: JSON.stringify(event),
      encoding: 'utf8',
    });
    if (dispatch.status !== 0 && process.env.ECC_LAB_DEBUG) {
      console.error('lab-event-router exit', dispatch.status, dispatch.stderr);
    }
  }
  if (result.status !== 0) {
    process.stderr.write(result.stderr || '');
    process.exit(result.status || 1);
  }
  process.stdout.write(result.stdout || '');
}

main();
