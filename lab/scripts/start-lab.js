#!/usr/bin/env node
'use strict';

/**
 * Start every lab subsystem locally:
 *   - Temporal dev server (via docker compose if available, otherwise hint)
 *   - MCP broker (stdio)
 *   - lab worker (temporalio)
 *   - FastAPI gateway (uvicorn)
 *   - Optional: frontend dev server
 *
 * Each subsystem runs in a child process and is supervised; Ctrl-C tears
 * everything down. Status is also exposed via the ecc-control-pane URL.
 */

const { spawn, spawnSync } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');

const ROOT = path.resolve(__dirname, '..', '..');
const LAB = path.join(ROOT, 'lab');

const PY = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');

const SERVICES = [];

function start(name, command, args, opts = {}) {
  const proc = spawn(command, args, {
    stdio: ['ignore', 'inherit', 'inherit'],
    env: { ...process.env, ...(opts.env || {}) },
    cwd: opts.cwd || ROOT,
    shell: process.platform === 'win32'
  });
  SERVICES.push({ name, proc });
  proc.on('exit', code => {
    console.error(`[start-lab] ${name} exited with code ${code}`);
  });
  console.log(`[start-lab] started ${name} (pid ${proc.pid}): ${command} ${args.join(' ')}`);
  return proc;
}

function pythonAvailable() {
  const r = spawnSync(PY, ['--version'], { stdio: 'ignore' });
  return r.status === 0;
}

function temporalAvailable() {
  const r = spawnSync('docker', ['ps'], { stdio: 'ignore' });
  return r.status === 0;
}

function startTemporal() {
  if (!temporalAvailable()) {
    console.log('[start-lab] Docker not available — assuming Temporal already runs at localhost:7233.');
    return;
  }
  const compose = path.join(LAB, 'scripts', 'docker-compose.temporal.yml');
  if (!fs.existsSync(compose)) {
    console.log('[start-lab] docker-compose.temporal.yml missing; skipping Temporal launch.');
    return;
  }
  start('temporal', 'docker', ['compose', '-f', compose, 'up', '-d']);
}

function shutdown() {
  console.log('\n[start-lab] shutting down...');
  for (const s of SERVICES) {
    try { s.proc.kill(); } catch { /* ignore */ }
  }
  setTimeout(() => process.exit(0), 800);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

(async function main() {
  if (!pythonAvailable()) {
    console.error(`[start-lab] ${PY} not found on PATH; install Python 3.11+ first.`);
    process.exit(2);
  }
  startTemporal();
  start('mcp-broker', PY, ['-m', 'lab.mcp_broker.proxy']);
  start('worker', PY, ['-m', 'lab.orchestrator.worker']);
  start('api', PY, ['-m', 'uvicorn', 'lab.api.main:app', '--host', '0.0.0.0', '--port', String(process.env.ECC_LAB_PORT || 8810)]);
  if (process.env.ECC_LAB_FRONTEND === '1') {
    start('frontend', 'npm', ['run', 'dev'], { cwd: path.join(LAB, 'frontend') });
  }
})();
