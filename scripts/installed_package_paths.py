#!/usr/bin/env python3
"""Read-only dpkg path/ELF inventory for scanner-selected blocking OS packages.

Package names arrive on stdin. Run inside the exact scanned final image.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    packages = sorted(set(line.strip() for line in sys.stdin if line.strip()))
    out = []
    for package in packages:
        if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?', package):
            raise ValueError('invalid Debian package name')
        record = subprocess.check_output(
            ['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Status}', package],
            text=True).split('\t')
        if len(record) != 4 or record[3] != 'installed':
            raise ValueError('scanner package is not installed: ' + package)
        paths = subprocess.check_output(['dpkg-query', '-L', package], text=True).splitlines()
        files = []
        for name in paths:
            p = Path(name)
            if not name.startswith('/') or p.is_dir():
                continue
            f = {'path': name}
            if p.is_symlink():
                f['symlink'] = os.readlink(p)
            if p.is_file():
                with p.open('rb') as stream:
                    elf = stream.read(4) == b'\x7fELF'
                    if elf:
                        stream.seek(0)
                        h = hashlib.sha256()
                        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                            h.update(chunk)
                        f['elf_sha256'] = h.hexdigest()
            elif not p.exists():
                f['missing'] = True
            files.append(f)
        out.append({'package': record[0], 'version': record[1], 'architecture': record[2], 'files': files})
    print(json.dumps({'scope': 'dpkg-owned files of blocking scanner OS packages; not proof of exploitability', 'packages': out}, indent=2))


if __name__ == '__main__':
    main()
