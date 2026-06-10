#!/usr/bin/env node
// Records scheduled lab audit events. Reads a JSON event from stdin and
// appends a one-line summary to `~/.ecc/lab/audit-events.jsonl` so the
// dashboard and `ecc lab status` can surface "last audit" information.

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');

function dataHome() {
  return process.env.ECC_LAB_DATA_HOME || path.join(os.homedir(), '.ecc', 'lab');
}

function readStdin() {
  return new Promise((resolve) => {
    let buf = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => (buf += chunk));
    process.stdin.on('end', () => resolve(buf));
  });
}

async function main() {
  const raw = await readStdin();
  let event;
  try {
    event = JSON.parse(raw);
  } catch (err) {
    process.stderr.write(`lab-audit-record: invalid JSON: ${err.message}\n`);
    process.exit(0);
  }
  if (!event || event.type !== 'lab.audit_event') return;
  const home = dataHome();
  fs.mkdirSync(home, { recursive: true });
  const line = JSON.stringify({
    recorded_at: new Date().toISOString(),
    job: event.job,
    exit_code: event.exit_code,
    started_at: event.started_at,
    finished_at: event.finished_at,
  });
  fs.appendFileSync(path.join(home, 'audit-events.jsonl'), line + '\n');
}

main();
