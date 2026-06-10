#!/usr/bin/env node
'use strict';

/**
 * Emit a lab stage event as an OpenTelemetry span via the OTLP HTTP exporter.
 *
 * Reads stdin (one JSON event per invocation) and posts a minimal Resource +
 * Span payload to the OTLP endpoint specified by OTEL_EXPORTER_OTLP_ENDPOINT.
 * Falls back silently when the endpoint is unreachable.
 */

const http = require('node:http');
const https = require('node:https');
const { URL } = require('node:url');

const ENDPOINT =
  process.env.OTEL_EXPORTER_OTLP_HTTP_ENDPOINT ||
  process.env.OTEL_EXPORTER_OTLP_ENDPOINT ||
  'http://localhost:4318';
const SERVICE_NAME = process.env.OTEL_SERVICE_NAME || 'ecc-lab';

function read() {
  return new Promise(resolve => {
    let s = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', c => (s += c));
    process.stdin.on('end', () => resolve(s));
    process.stdin.on('error', () => resolve(''));
  });
}

function id(bytes) {
  const out = Buffer.alloc(bytes);
  for (let i = 0; i < bytes; i++) out[i] = Math.floor(Math.random() * 256);
  return out.toString('hex');
}

async function main() {
  const raw = await read();
  if (!raw.trim()) return;
  let evt;
  try {
    evt = JSON.parse(raw);
  } catch {
    return;
  }
  if (!evt || evt.type !== 'lab.stage_event') return;

  const start = (evt.timestamp || Date.now() / 1000) * 1e9;
  const end = start + 1e6;
  const traceId = id(16);
  const spanId = id(8);

  const payload = {
    resourceSpans: [
      {
        resource: {
          attributes: [
            { key: 'service.name', value: { stringValue: SERVICE_NAME } },
            { key: 'service.namespace', value: { stringValue: 'lab' } }
          ]
        },
        scopeSpans: [
          {
            scope: { name: 'ecc-lab.hooks' },
            spans: [
              {
                traceId,
                spanId,
                name: `${evt.track}.${evt.stage}.${evt.event}`,
                kind: 1,
                startTimeUnixNano: String(BigInt(Math.floor(start))),
                endTimeUnixNano: String(BigInt(Math.floor(end))),
                attributes: [
                  { key: 'lab.project_id', value: { stringValue: evt.project_id || '' } },
                  { key: 'lab.track', value: { stringValue: evt.track || '' } },
                  { key: 'lab.stage', value: { stringValue: evt.stage || '' } },
                  { key: 'lab.event', value: { stringValue: evt.event || '' } }
                ]
              }
            ]
          }
        ]
      }
    ]
  };

  const url = new URL(ENDPOINT.replace(/\/$/, '') + '/v1/traces');
  const data = Buffer.from(JSON.stringify(payload), 'utf8');
  const opts = {
    method: 'POST',
    hostname: url.hostname,
    port: url.port || (url.protocol === 'https:' ? 443 : 80),
    path: url.pathname,
    headers: { 'content-type': 'application/json', 'content-length': data.length },
    timeout: 1500
  };
  const lib = url.protocol === 'https:' ? https : http;
  try {
    await new Promise(resolve => {
      const req = lib.request(opts, res => {
        res.on('data', () => {});
        res.on('end', resolve);
      });
      req.on('error', resolve);
      req.on('timeout', () => { req.destroy(); resolve(); });
      req.write(data);
      req.end();
    });
  } catch {
    // swallow
  }
}

main();
