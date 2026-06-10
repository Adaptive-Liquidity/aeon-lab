#!/usr/bin/env node
// Installs the lab cron schedule on the host machine.
//
// - On Linux/macOS it writes user crontab entries (idempotent — keyed by
//   a marker comment).
// - On Windows it generates `schtasks` invocations under
//   `lab/scripts/install-cron.bat` for the user to run elevated.
//
// Each platform path forwards to `node lab/scripts/run-cron.js <job>`
// so the schedule and the job catalogue stay defined in cron.yaml.

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const MARKER = '# ECC-LAB-CRON';
const CRON_RUNNER = path.resolve(__dirname, 'run-cron.js');

function listJobs() {
  const text = fs.readFileSync(path.join(__dirname, 'cron.yaml'), 'utf8');
  const lines = text.split(/\r?\n/);
  const jobs = [];
  let cur = null;
  for (const raw of lines) {
    const line = raw.replace(/\t/g, '  ');
    if (line.startsWith('  - ')) {
      if (cur) jobs.push(cur);
      cur = {};
      const after = line.replace('  - ', '').trim();
      if (after.includes(':')) {
        const [k, ...rest] = after.split(':');
        cur[k.trim()] = rest.join(':').trim();
      }
    } else if (cur && line.startsWith('    ') && line.includes(':')) {
      const [k, ...rest] = line.trim().split(':');
      cur[k.trim()] = rest.join(':').trim();
    }
  }
  if (cur) jobs.push(cur);
  return jobs.filter((j) => j.name && j.schedule);
}

function installUnix(jobs) {
  const list = spawnSync('crontab', ['-l'], { encoding: 'utf8' });
  const existing = (list.stdout || '').split('\n').filter((l) => !l.includes(MARKER));
  const repoRoot = path.resolve(__dirname, '..', '..');
  const newLines = jobs.map(
    (j) => `${j.schedule} cd ${repoRoot} && node ${CRON_RUNNER} ${j.name} ${MARKER} ${j.name}`,
  );
  const merged = [...existing.filter((l) => l.trim()), ...newLines, ''].join('\n');
  const write = spawnSync('crontab', ['-'], { input: merged, encoding: 'utf8' });
  if (write.status !== 0) {
    console.error('crontab install failed:', write.stderr);
    process.exit(write.status || 1);
  }
  console.log(`Installed ${jobs.length} lab cron jobs.`);
}

function installWindows(jobs) {
  const lines = ['@echo off'];
  const repoRoot = path.resolve(__dirname, '..', '..');
  for (const j of jobs) {
    // Translate `m h dom mon dow` to schtasks. For the simple schedules
    // we ship (daily / weekly) we map the common cases.
    const [minute, hour, , , dow] = j.schedule.split(/\s+/);
    const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
    let schedule;
    if (dow !== '*') {
      const days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'];
      const day = days[Number(dow)] || 'MON';
      schedule = `/SC WEEKLY /D ${day} /ST ${time}`;
    } else {
      schedule = `/SC DAILY /ST ${time}`;
    }
    lines.push(
      `schtasks /Create /F /TN "ECC-Lab\\${j.name}" ${schedule} ` +
        `/TR "cmd /c cd /d ${repoRoot} && node ${CRON_RUNNER} ${j.name}"`,
    );
  }
  const batPath = path.join(__dirname, 'install-cron.bat');
  fs.writeFileSync(batPath, lines.join('\r\n') + '\r\n', 'utf8');
  console.log(`Wrote ${batPath}. Run it from an elevated Command Prompt to install scheduled tasks.`);
}

function main() {
  const jobs = listJobs();
  if (os.platform() === 'win32') {
    installWindows(jobs);
  } else {
    installUnix(jobs);
  }
}

main();
