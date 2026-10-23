#!/usr/bin/env python3
"""Read-only vendor candidate evidence after refreshing indexes in an ephemeral container.

This does not install packages, decide CVE status, or change any security gate.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


def command(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def inventory(packages):
    records = []
    for package in sorted(set(packages)):
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?', package):
            raise ValueError('invalid Debian package name')
        values = command(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${Architecture}\t${source:Package}\t${source:Version}\t${db:Status-Status}', package]).split('\t')
        if len(values) != 6 or values[5] != 'installed':
            raise ValueError('not an installed package: ' + package)
        policy = command(['apt-cache', 'policy', package])
        match = re.search(r'^\s*Candidate:\s*(\S+)', policy, re.M)
        if not match or match[1] == '(none)':
            raise ValueError('missing APT candidate for ' + package)
        records.append(dict(zip(('package', 'installed', 'arch', 'source_package', 'source_version'), values[:5]), candidate=match[1], policy=policy))
    sources = []
    for path in sorted(Path('/etc/apt').rglob('*')):
        if path.is_file() and (path.name == 'sources.list' or path.suffix in ('.sources', '.list')):
            data = path.read_bytes()
            sources.append({'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'content': data.decode()})
    return {'scope': 'Refreshed vendor candidates, not CVE fixed-status decisions; no package installation', 'packages': records, 'sources': sources}


def bind_candidate(evidence, candidate):
    if not isinstance(evidence, dict) or not isinstance(evidence.get('packages'), list):
        raise ValueError('invalid inventory schema')
    # The candidate metadata is deliberately top-level; per-package candidate
    # strings are APT availability evidence, not proof that a CVE is fixed.
    if not isinstance(candidate, dict):
        raise ValueError('invalid candidate metadata')
    for key in ('image_id', 'manifest_digest'):
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', candidate.get(key, '')):
            raise ValueError('invalid candidate ' + key)
    arch = command(['dpkg', '--print-architecture']).strip()
    if arch not in ('amd64', 'arm64') or candidate.get('arch') != arch:
        raise ValueError('candidate architecture mismatch')
    for package in evidence['packages']:
        if not isinstance(package, dict) or package.get('arch') not in (arch, 'all'):
            raise ValueError('package architecture mismatch')
    return dict(evidence, candidate=candidate, observed_arch=arch,
                candidate_semantics='APT candidate availability; not proof of fixed version')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', required=True, type=Path)
    args = parser.parse_args()
    evidence = inventory([line.strip() for line in sys.stdin if line.strip()])
    print(json.dumps(bind_candidate(evidence, json.loads(args.metadata.read_text())), indent=2))
