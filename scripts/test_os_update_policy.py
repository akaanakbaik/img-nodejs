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
        dockerfile = (ROOT / 'Dockerfile').read_text().split('AS supported', 1)[1]
        self.assertIn('ARG APPLY_OS_UPDATES=true', dockerfile)
        self.assertIn('false) ;;', dockerfile)
        self.assertIn('APPLY_OS_UPDATES must be true or false', dockerfile)
        self.assertLess(dockerfile.index('USER root'), dockerfile.index('apt-get update'))
        self.assertLess(dockerfile.index('apt-get update'), dockerfile.index('USER container'))
        self.assertTrue(dockerfile.rstrip().endswith('node /usr/local/share/image-security/verify_runtime.js'))

    def test_eol_target_does_not_build_supported_packages(self):
        dockerfile = (ROOT / 'Dockerfile').read_text()
        eol = dockerfile.split('AS eol-audit', 1)[1].split('FROM ${BASE_IMAGE} AS brotli-build', 1)[0]
        self.assertNotIn('apt-get', eol)
        self.assertNotIn('brotli-build', eol)
        workflow = (ROOT / '.github/workflows/publish.yml').read_text()
        self.assertIn("target: ${{ matrix.publish && 'supported' || 'eol-audit' }}", workflow)
        self.assertIn('continue-on-error: ${{ !matrix.publish }}', workflow)


if __name__ == '__main__':
    unittest.main()
