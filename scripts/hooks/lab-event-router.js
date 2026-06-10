#!/usr/bin/env node
'use strict';

/**
 * Route a lab stage event through the existing ECC hooks pipeline.
 *
 * Input (stdin, JSON):
 *   { type: "lab.stage_event", project_id, track, stage, event, payload, timestamp }
 *
 * This script normalizes the event and dispatches matching hook handlers
 * defined in hooks/hooks.json. It does not throw — hooks are fail-open so a
 * mis-configured automation never blocks the lab.
 */

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

const HOOKS_JSON = path.join(__dirname, '..', '..', 'hooks', 'lab-hooks.json');
const SESSION_LOG = path.join(__dirname, '..', '..', 'manifests', 'lab-session.log');

function readStdin() {
  return new Promise(resolve => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => (data += chunk));
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', () => resolve(''));
  });
}

function loadHooks() {
  try {
    const raw = fs.readFileSync(HOOKS_JSON, 'utf8');
    return JSON.parse(raw);
  } catch {
    return { hooks: [] };
  }
}

function matchesMatcher(matcher, event) {
  if (!matcher) return true;
  if (typeof matcher === 'string') {
    return matcher === '*' || matcher === event.event || matcher === `lab:${event.event}`;
  }
  if (typeof matcher === 'object') {
    if (matcher.type && matcher.type !== 'lab.stage_event') return false;
    if (matcher.track && matcher.track !== event.track) return false;
    if (matcher.stage && matcher.stage !== event.stage) return false;
    if (matcher.event && matcher.event !== event.event) return false;
    return true;
  }
  return false;
}

function appendSessionLog(event) {
  try {
    fs.mkdirSync(path.dirname(SESSION_LOG), { recursive: true });
    fs.appendFileSync(
      SESSION_LOG,
      JSON.stringify({ ...event, recordedAt: new Date().toISOString() }) + '\n',
      'utf8'
    );
  } catch {
    // intentionally swallow — session log is best-effort
  }
}

function spawnHandler(command, args, eventJSON) {
  return new Promise(resolve => {
    let child;
    try {
      child = spawn(command, args, { stdio: ['pipe', 'pipe', 'pipe'] });
    } catch {
      return resolve({ ok: false });
    }
    child.stdin.write(eventJSON);
    child.stdin.end();
    let stdout = '';
    let stderr = '';
    child.stdout?.on('data', d => (stdout += d.toString()));
    child.stderr?.on('data', d => (stderr += d.toString()));
    child.on('error', () => resolve({ ok: false, stdout, stderr }));
    child.on('exit', code => resolve({ ok: code === 0, stdout, stderr, code }));
  });
}

async function main() {
  const raw = await readStdin();
  if (!raw.trim()) return;
  let event;
  try {
    event = JSON.parse(raw);
  } catch {
    return;
  }
  if (!event || event.type !== 'lab.stage_event') return;

  appendSessionLog(event);

  const def = loadHooks();
  const handlers = (def.hooks || []).filter(h => matchesMatcher(h.matcher, event));
  const eventJSON = JSON.stringify(event);

  await Promise.all(
    handlers.map(async handler => {
      const cmd = handler.command || handler.handler || null;
      if (!cmd) return;
      const parts = Array.isArray(cmd) ? cmd : cmd.split(' ');
      const [command, ...args] = parts;
      try {
        await spawnHandler(command, args, eventJSON);
      } catch {
        // fail-open
      }
    })
  );
}

main();
