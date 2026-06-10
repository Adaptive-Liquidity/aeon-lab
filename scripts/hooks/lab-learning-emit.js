#!/usr/bin/env node
'use strict';

/**
 * On gate_passed events, queue a "skill candidate" job for continuous-
 * learning-v2. The skill extractor reads ~/.ecc/lab/learning-queue.jsonl
 * and decides whether the stage produced a reusable pattern.
 */

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const QUEUE = path.join(os.homedir(), '.ecc', 'lab', 'learning-queue.jsonl');

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
  if (!evt || evt.event !== 'gate_passed') return;
  try {
    fs.mkdirSync(path.dirname(QUEUE), { recursive: true });
    fs.appendFileSync(
      QUEUE,
      JSON.stringify({
        project_id: evt.project_id,
        track: evt.track,
        stage: evt.stage,
        timestamp: evt.timestamp,
        payload: evt.payload || {}
      }) + '\n',
      'utf8'
    );
  } catch { /* fail-open */ }
}

main();
