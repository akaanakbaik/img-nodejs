#!/usr/bin/env node
'use strict';
const assert = require('assert');
const cp = require('child_process');
const path = require('path');
const script = path.join(__dirname, 'verify_runtime.js');
const current = process.versions.node;
function run(version) { return cp.spawnSync(process.execPath, [script, version], {encoding: 'utf8'}); }
const [major, minor, patch] = current.split('.').map(Number);
const supportedMinimum = {22: [22, 23, 4], 24: [24, 22, 1], 26: [26, 12, 1]}[major];
const hostResult = run(current);
if (supportedMinimum && (minor < supportedMinimum[1] || (minor === supportedMinimum[1] && patch < supportedMinimum[2]))) {
  assert.notStrictEqual(hostResult.status, 0, 'below supported CVE minimum must fail');
} else {
  assert.strictEqual(hostResult.status, 0, hostResult.stderr);
}
assert.notStrictEqual(run('0.0.0').status, 0, 'wrong version must fail');
assert.notStrictEqual(run(`v${current.split('.').map((n, i) => i === 0 ? Number(n) + 1 : n).join('.')}`).status, 0, 'wrong major must fail');
assert.notStrictEqual(run('22.0.0').status, 0, 'supported branch below CVE minimum must fail');
const envRun = cp.spawnSync(process.execPath, [script], {env: {...process.env, EXPECTED_NODE_VERSION: current}, encoding: 'utf8'});
assert.strictEqual(envRun.status, hostResult.status, 'env and argument validation should agree');
console.log('PASS: verify_runtime offline tests');
