#!/usr/bin/env node
'use strict';

/**
 * Vendor Claw-AI-Lab into lab/researchclaw and lab/frontend.
 *
 * Phase 0 supports two modes:
 *   - bridge (default) — leave Claw-AI-Lab as a sibling and rely on
 *     lab/__init__.py's sys.path bridge so `from lab.researchclaw.*` works.
 *   - physical — copy files into lab/researchclaw and rewrite imports.
 *
 * Usage:
 *   node lab/scripts/vendor-claw.js            # bridge mode, no copy
 *   node lab/scripts/vendor-claw.js --physical # full copy + import rewrite
 *   node lab/scripts/vendor-claw.js --check    # report status only
 */

const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..', '..');
const CLAW_SRC = path.join(ROOT, 'Claw-AI-Lab', 'backend', 'agent', 'researchclaw');
const CLAW_FRONTEND_SRC = path.join(ROOT, 'Claw-AI-Lab', 'frontend');
const LAB_DST = path.join(ROOT, 'lab', 'researchclaw');
const LAB_FRONTEND_DST = path.join(ROOT, 'lab', 'frontend');

const args = process.argv.slice(2);
const flag = name => args.includes(name);

function status() {
  const clawExists = fs.existsSync(path.join(CLAW_SRC, '__init__.py'));
  const labExists = fs.existsSync(path.join(LAB_DST, '__init__.py'));
  const frontendExists = fs.existsSync(path.join(LAB_FRONTEND_DST, 'package.json'));
  return { clawExists, labExists, frontendExists };
}

async function copyDir(src, dst) {
  await fsp.mkdir(dst, { recursive: true });
  const entries = await fsp.readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name === '__pycache__' || entry.name === 'node_modules') continue;
    const s = path.join(src, entry.name);
    const d = path.join(dst, entry.name);
    if (entry.isDirectory()) {
      await copyDir(s, d);
    } else if (entry.isFile()) {
      await fsp.copyFile(s, d);
    }
  }
}

async function rewritePythonImports(dir) {
  const entries = await fsp.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === '__pycache__') continue;
      await rewritePythonImports(p);
      continue;
    }
    if (!entry.isFile() || !entry.name.endsWith('.py')) continue;
    const text = await fsp.readFile(p, 'utf8');
    const rewritten = text
      .replace(/(^|\n)from researchclaw(\.|\s)/g, '$1from lab.researchclaw$2')
      .replace(/(^|\n)import researchclaw(\.|\s|$)/g, '$1import lab.researchclaw$2');
    if (rewritten !== text) await fsp.writeFile(p, rewritten, 'utf8');
  }
}

async function physicalVendor() {
  if (!fs.existsSync(path.join(CLAW_SRC, '__init__.py'))) {
    console.error('[vendor-claw] Claw-AI-Lab source not found at', CLAW_SRC);
    process.exit(2);
  }
  console.log('[vendor-claw] copying researchclaw ->', LAB_DST);
  await copyDir(CLAW_SRC, LAB_DST);
  console.log('[vendor-claw] rewriting researchclaw imports');
  await rewritePythonImports(LAB_DST);

  if (fs.existsSync(path.join(CLAW_FRONTEND_SRC, 'package.json'))) {
    console.log('[vendor-claw] copying frontend ->', LAB_FRONTEND_DST);
    await copyDir(CLAW_FRONTEND_SRC, LAB_FRONTEND_DST);
  }

  console.log('[vendor-claw] done. Run: pip install -e lab[research]');
}

(async function main() {
  if (flag('--check')) {
    console.log(JSON.stringify(status(), null, 2));
    return;
  }
  if (flag('--physical')) {
    await physicalVendor();
    return;
  }
  const st = status();
  if (!st.clawExists) {
    console.error('[vendor-claw] Claw-AI-Lab/backend/agent/researchclaw missing.');
    console.error('Clone Claw-AI-Lab into the ECC repo root first, then re-run.');
    process.exit(2);
  }
  console.log('[vendor-claw] bridge mode active — lab/__init__.py adds Claw-AI-Lab to sys.path.');
  console.log('[vendor-claw] For physical vendoring, re-run with --physical.');
  console.log('[vendor-claw] Status:', JSON.stringify(st));
})();
