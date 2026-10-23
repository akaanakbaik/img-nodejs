#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

function fail(message) { throw new Error(message); }
function parseVersion(value) {
  const match = /^v?(\d+)\.(\d+)\.(\d+)$/.exec(String(value || ''));
  if (!match) fail(`invalid Node.js version: ${value}`);
  return match.slice(1).map(Number);
}
function compare(a, b) {
  for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] - b[i];
  return 0;
}
function randomBuffer(size) {
  return require('crypto').randomBytes(size);
}
async function streamRoundTrip(input) {
  const compressor = zlib.createBrotliCompress();
  const chunks = [];
  compressor.on('data', chunk => chunks.push(chunk));
  const done = new Promise((resolve, reject) => { compressor.on('end', resolve); compressor.on('error', reject); });
  for (let offset = 0; offset < input.length; offset += 97) compressor.write(input.subarray(offset, Math.min(offset + 97, input.length)));
  compressor.end();
  await done;
  return new Promise((resolve, reject) => {
    const decompressor = zlib.createBrotliDecompress(); const out = [];
    decompressor.on('data', chunk => out.push(chunk));
    decompressor.on('end', () => resolve(Buffer.concat(out)));
    decompressor.on('error', reject);
    for (const chunk of chunks) decompressor.write(chunk);
    decompressor.end();
  });
}
async function main() {
  const expectedText = process.argv[2] || process.env.EXPECTED_NODE_VERSION || process.env.EXPECTED_NODE_PATCH;
  if (!expectedText) fail('expected version argument or EXPECTED_NODE_VERSION/EXPECTED_NODE_PATCH');
  const expected = parseVersion(expectedText);
  const actual = parseVersion(process.versions.node);
  if (compare(actual, expected) !== 0) fail(`Node.js version mismatch: expected ${expected.join('.')}, got ${actual.join('.')}`);
  if (process.env.EXPECTED_NODE_MAJOR && String(expected[0]) !== process.env.EXPECTED_NODE_MAJOR) fail('expected major and patch disagree');
  if (process.env.EXPECTED_NODE_ARCH && process.arch !== process.env.EXPECTED_NODE_ARCH) fail('runtime architecture mismatch');
  if (!['x64', 'arm64'].includes(process.arch)) fail(`unsupported process architecture: ${process.arch}`);
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'versions.json'), 'utf8'));
  const entry = manifest.versions.find(item => item.major === expected[0]);
  if (!entry) fail(`unconfigured Node.js major: ${expected[0]}`);
  if (entry && entry.supported && compare(expected, parseVersion(entry.minimum_patch || entry.version)) < 0) {
    fail(`Node.js ${expected.join('.')} is below supported minimum ${entry.minimum_patch || entry.version}`);
  }
  const samples = [Buffer.alloc(0), Buffer.from('Node.js Brotli round-trip'), randomBuffer(1), randomBuffer(4096), randomBuffer(65537)];
  for (const sample of samples) {
    if (!zlib.brotliDecompressSync(zlib.brotliCompressSync(sample)).equals(sample)) fail('Brotli synchronous round-trip failed');
    if (!(await streamRoundTrip(sample)).equals(sample)) fail('Brotli streaming round-trip failed');
  }
  // Fixed invalid fixtures: random bytes can occasionally form valid Brotli.
  for (const malformed of [Buffer.from([0]), Buffer.from('not Brotli')]) {
    try { zlib.brotliDecompressSync(malformed); fail('malformed Brotli input unexpectedly succeeded'); } catch (error) {
      if (error.message === 'malformed Brotli input unexpectedly succeeded') throw error;
    }
  }
  console.log(`PASS: Node.js ${process.versions.node}, arch ${process.arch}, Brotli round-trips and malformed-input checks`);
}
main().catch(error => { console.error(`FAIL: ${error.message}`); process.exitCode = 1; });
