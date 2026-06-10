#!/usr/bin/env node
'use strict';

/**
 * Record rollback events to ~/.ecc/lab/rollback-audit.jsonl for the dashboard.
 */

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const AUDIT = path.join(os.homedir(), '.ecc', 'lab', 'rollback-audit.jsonl');

function read() {
  return new Promise(resolve => {
    let s = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', c => (s += c));
    process.stdin.on('end', () => resolve(s));
    process.stdin.on('error', () => resolve(''));
  });
}

async function main() {
  const raw = await read();
  if (!raw.trim()) return;
  let evt;
  try { evt = JSON.parse(raw); } catch { return; }
  if (!evt || evt.event !== 'rollback') return;
  try {
    fs.mkdirSync(path.dirname(AUDIT), { recursive: true });
    fs.appendFileSync(AUDIT, JSON.stringify(evt) + '\n', 'utf8');
  } catch { /* fail-open */ }
}

main();
