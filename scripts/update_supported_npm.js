'use strict';
// Upgrade npm as an upstream release unit; never mutate nested dependencies.
const https = require('node:https');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const version = '12.2.1';
const url = `https://registry.npmjs.org/npm/-/npm-${version}.tgz`;
const integrity = 'bKCmFRVT/BB+YPEYbZwQ1XUI3N5t4xKSpU1MxOjo7z3iWzKBJ0ZXRC1xFdEN+TC7N5TdywaBzf2dMXGJq/e2PQ==';

async function main() {
  const data = await new Promise((resolve, reject) => {
    const request = https.get(url, response => {
      if (response.statusCode !== 200) {
        response.resume();
        reject(new Error(`npm download HTTP ${response.statusCode}`));
        return;
      }
      const chunks = [];
      let size = 0;
      response.on('data', chunk => {
        size += chunk.length;
        if (size > 32 * 1024 * 1024) response.destroy(new Error('npm archive exceeds size limit'));
        else chunks.push(chunk);
      });
      response.on('end', () => resolve(Buffer.concat(chunks)));
      response.on('error', reject);
    });
    request.setTimeout(60000, () => request.destroy(new Error('npm download timeout')));
    request.on('error', reject);
  });
  if (crypto.createHash('sha512').update(data).digest('base64') !== integrity) {
    throw new Error('npm archive SHA-512 mismatch');
  }
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'verified-npm-'));
  try {
    const archive = path.join(dir, 'npm.tgz');
    fs.writeFileSync(archive, data);
    execFileSync('/usr/local/bin/npm', ['install', '--global', '--ignore-scripts', '--no-audit', '--no-fund', archive], { stdio: 'inherit' });
    const actual = execFileSync('/usr/local/bin/npm', ['--version'], { encoding: 'utf8' }).trim();
    if (actual !== version) throw new Error(`npm version mismatch: ${actual}`);
    const root = '/usr/local/lib/node_modules/npm/node_modules';
    for (const [name, expected] of Object.entries({ 'brace-expansion': '5.0.12', 'undici': '6.29.0', 'http-cache-semantics': '4.3.0' })) {
      const actualDependency = JSON.parse(fs.readFileSync(path.join(root, name, 'package.json'), 'utf8')).version;
      if (actualDependency !== expected) throw new Error(`${name} mismatch: ${actualDependency}`);
      console.log(`Verified npm bundle: ${name}@${actualDependency}`);
    }
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
