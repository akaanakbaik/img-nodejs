#!/usr/bin/env python3
"""Install a whole verified native TypeScript package, never an opaque .so/binary patch."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path('/tmp/typescript-packages')
DEST_ROOT = Path('/usr/local/lib/node_modules/typescript')


def main():
    arch = {'x86_64': ('x64', 'amd64'), 'aarch64': ('arm64', 'arm64')}.get(platform.machine())
    if not arch:
        raise ValueError('unsupported native platform')
    npm_arch, go_arch = arch
    package_name = 'typescript-linux-' + npm_arch
    package = ROOT / package_name
    # Verify the complete build output before replacing the installed package.
    checked = set()
    for line in (ROOT / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        relative = Path(name.lstrip('* '))
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != package_name:
            raise ValueError('unsafe checksum path')
        target = ROOT / relative
        if target.is_symlink() or not target.is_file():
            raise ValueError('invalid checksummed package file')
        h = hashlib.sha256()
        with target.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(block)
        if h.hexdigest() != expected or name in checked:
            raise ValueError('package checksum mismatch/duplicate')
        checked.add(name)
    actual = {str(p.relative_to(ROOT)) for p in package.rglob('*') if p.is_file()}
    if not actual or actual != checked or any(p.is_symlink() for p in package.rglob('*')):
        raise ValueError('package file inventory mismatch')
    metadata = json.loads((package / 'package.json').read_text())
    provenance = json.loads((package / 'BUILD-PROVENANCE.json').read_text())
    inherited = json.loads((DEST_ROOT / 'package.json').read_text())
    if inherited.get('version') != '7.0.2' or metadata.get('version') != inherited['version']:
        raise ValueError('upstream/compiler release mismatch')
    if metadata.get('name') != '@typescript/' + package_name or metadata.get('cpu') != [npm_arch] or metadata.get('os') != ['linux']:
        raise ValueError('native package identity mismatch')
    if metadata.get('x-image-build', {}).get('official_upstream_binary') is not False:
        raise ValueError('missing explicit custom-build package identity')
    expected = {'kind': 'custom-native-rebuild', 'go_version': '1.26.10', 'x_text': 'v0.41.0', 'target': 'linux/' + go_arch, 'official_upstream_binary': False, 'compiler_sources_modified': False, 'source_commit': '2bd066d87f5bafd315be9f40889d0a60b9e58e0b'}
    if any(provenance.get(k) != v for k, v in expected.items()):
        raise ValueError('unapproved TypeScript build provenance')
    installed = DEST_ROOT / 'node_modules/@typescript' / package_name
    if not installed.is_dir():
        raise ValueError('inherited native package not found')
    # Whole-package replacement is an actual source rebuild, not package deletion
    # to reduce scan counts. Root wrappers, compiler version and functionality remain.
    shutil.rmtree(installed)
    shutil.copytree(package, installed)
    evidence_dir = Path('/usr/local/share/image-security/typescript')
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name in ('BUILD-PROVENANCE.json', 'go-build-info.txt', 'build.go.mod', 'build.go.sum', 'compiler-source-sha256sums.txt', 'dependency-diff.txt'):
        shutil.copyfile(package / name, evidence_dir / name)
    shutil.copyfile(ROOT / 'SHA256SUMS', evidence_dir / 'SHA256SUMS')
    shutil.copyfile(package / 'BUILD-PROVENANCE.json', evidence_dir.parent / 'typescript-provenance.json')
    actual_version = subprocess.check_output(['/usr/local/bin/tsc', '--version'], text=True).strip()
    if actual_version != 'Version 7.0.2':
        raise ValueError('rebuilt compiler exact version failed: ' + actual_version)
    native_packages = list((DEST_ROOT / 'node_modules/@typescript').glob('typescript-linux-*/lib/tsc'))
    if native_packages != [installed / 'lib/tsc']:
        raise ValueError('unexpected extra native TypeScript binary remains installed')
    print('Verified full native TypeScript 7.0.2 custom rebuild, Go 1.26.10, x/text v0.41.0')


if __name__ == '__main__':
    main()
