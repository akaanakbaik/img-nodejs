#!/usr/bin/env python3
"""Regression checks for non-destructive supported-image OS updates."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OsUpdatePolicyTests(unittest.TestCase):
    def test_repository_refresh_fails_closed(self):
        dockerfile = (ROOT / 'Dockerfile').read_text()
        self.assertIn('apt-get update --error-on=any', dockerfile)
        self.assertIn('apt-get upgrade -y --no-remove', dockerfile)
        self.assertNotIn('apt-get autoremove', dockerfile)
        self.assertNotIn('apt-get remove', dockerfile)
        self.assertNotIn('dist-upgrade', dockerfile)

    def test_only_supported_ci_candidates_are_updated(self):
        workflow = (ROOT / '.github/workflows/publish.yml').read_text()
        self.assertIn('APPLY_OS_UPDATES=${{ matrix.publish }}', workflow)
        self.assertIn('python3 scripts/test_os_update_policy.py', workflow)

    def test_non_root_runtime_is_restored(self):
        dockerfile = (ROOT / 'Dockerfile').read_text()
        self.assertIn('ARG APPLY_OS_UPDATES=true', dockerfile)
        self.assertIn('false) ;;', dockerfile)
        self.assertIn('APPLY_OS_UPDATES must be true or false', dockerfile)
        self.assertLess(dockerfile.index('USER root'), dockerfile.index('apt-get update'))
        self.assertLess(dockerfile.index('apt-get update'), dockerfile.index('USER container'))
        self.assertTrue(dockerfile.rstrip().endswith('node /usr/local/share/image-security/verify_runtime.js'))


if __name__ == '__main__':
    unittest.main()
