#!/usr/bin/env node
'use strict';

/**
 * Append a cost ledger row when a stage succeeds. Reads stage payload from
 * stdin; writes to ~/.ecc/lab/cost_ledger.jsonl. Best-effort, fail-open.
 */

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

const LEDGER = path.join(os.homedir(), '.ecc', 'lab', 'cost_ledger.jsonl');

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
  if (!evt || evt.type !== 'lab.stage_event' || evt.event !== 'succeeded') return;
  const cost = evt.payload && Number(evt.payload.cost_usd || 0);
  if (!cost) return;
  const row = {
    project_id: evt.project_id,
    track: evt.track,
    stage: evt.stage,
    agent_role: (evt.payload && evt.payload.agent) || '',
    model: (evt.payload && evt.payload.model_used) || '',
    cost_usd: cost,
    timestamp: evt.timestamp
  };
  try {
    fs.mkdirSync(path.dirname(LEDGER), { recursive: true });
    fs.appendFileSync(LEDGER, JSON.stringify(row) + '\n', 'utf8');
  } catch { /* fail-open */ }
}

main();
