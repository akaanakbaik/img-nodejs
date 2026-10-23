#!/usr/bin/env python3
"""Verify release-vs-golden help mismatch without editing or accepting a golden."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re

PREFIX = 'tsc: The TypeScript Compiler - Version FakeTSVersion'
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')


def verify(reference, actual):
    before, after = reference.splitlines(keepends=True), actual.splitlines(keepends=True)
    if len(before) != len(after):
        raise ValueError('help diff changes line structure, not only header padding')
    differences = [(i, a, b) for i, (a, b) in enumerate(zip(before, after), 1) if a != b]
    if len(differences) != 1:
        raise ValueError('expected exactly one version-dependent help header line')
    line, old, new = differences[0]
    if not old.startswith(PREFIX) or not new.startswith(PREFIX):
        raise ValueError('changed text is outside the version-dependent help header')
    # Keep all text and escape codes identical; only the padding before the icon
    # may change. No option body, default, diagnostic, or output line is waived.
    pattern = re.compile('^' + re.escape(PREFIX) + r'( +)(\x1b\[44m     \x1b\[39;49m\r?\n?)$')
    left, right = pattern.fullmatch(old), pattern.fullmatch(new)
    if not left or not right or left[2] != right[2]:
        raise ValueError('header content/colour/icon changed, not only padding')
    expected_delta = len('7.0.0-dev') - len('7.0.2')
    if len(right[1]) - len(left[1]) != expected_delta:
        raise ValueError('padding difference does not match release/dev version length')
    return {'status': 'verified_version_header_padding_only', 'changed_line': line, 'padding_delta': expected_delta, 'reference_sha256': hashlib.sha256(reference.encode()).hexdigest(), 'actual_sha256': hashlib.sha256(actual.encode()).hexdigest(), 'reference_modified': False, 'tests_skipped': False, 'runtime_version': '7.0.2', 'test_only_version': '7.0.0-dev', 'diff': ''.join(difflib.unified_diff(before, after, fromfile='upstream-reference', tofile='stable-release-test-actual'))}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference', type=Path)
    p.add_argument('actual', type=Path)
    args = p.parse_args()
    print(json.dumps(verify(args.reference.read_text(), args.actual.read_text()), indent=2))
