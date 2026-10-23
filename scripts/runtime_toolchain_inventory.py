#!/usr/bin/env python3
"""Record installed TypeScript release/native compiler without executing untrusted input."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def inventory(candidate, package_root=Path('/usr/local/lib/node_modules/typescript')):
    arch = {'x86_64': 'amd64', 'aarch64': 'arm64'}.get(platform.machine())
    if candidate.get('arch') != arch:
        raise ValueError('runtime tooling candidate architecture mismatch')
    for key in ('image_id', 'manifest_digest'):
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', candidate.get(key, '')):
            raise ValueError('invalid candidate identity')
    package = json.loads((package_root / 'package.json').read_text())
    executable = shutil.which('tsc')
    if not executable:
        raise ValueError('missing TypeScript compiler entrypoint')
    entrypoint = Path(executable).resolve(strict=True)
    binaries = sorted(package_root.glob('node_modules/@typescript/typescript-linux-*/lib/tsc'))
    if len(binaries) != 1:
        raise ValueError('expected exactly one native TypeScript compiler')
    native = binaries[0]
    with native.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            raise ValueError('native TypeScript compiler is not ELF')
    native_package = json.loads((native.parent.parent / 'package.json').read_text())
    expected_cpu = {'amd64': 'x64', 'arm64': 'arm64'}[arch]
    if native_package.get('cpu') != [expected_cpu] or native_package.get('os') != ['linux']:
        raise ValueError('native TypeScript package platform mismatch')
    if package.get('version') != native_package.get('version'):
        raise ValueError('TypeScript root/native package version mismatch')
    provenance_path = Path('/usr/local/share/image-security/typescript-provenance.json')
    return {'candidate': candidate, 'observed_arch': arch, 'package': {'name': package['name'], 'version': package['version'], 'package_json_sha256': sha256(package_root / 'package.json')}, 'entrypoint': {'path': executable, 'resolved': str(entrypoint), 'sha256': sha256(entrypoint)}, 'native_compilers': [{'path': str(native), 'sha256': sha256(native), 'package': native_package['name'], 'version': native_package['version']}], 'custom_build_provenance': json.loads(provenance_path.read_text()) if provenance_path.exists() else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inventory(json.loads(args.metadata.read_text())), indent=2))
