#!/usr/bin/env python3
"""Offline checks for the exact source and Debian packaging used by the build."""
import hashlib
import json
from pathlib import Path
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class BrotliSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.metadata = json.loads((ROOT / 'security/brotli-source.json').read_text())

    def test_archive_matches_reviewed_pin(self):
        source = self.metadata['upstream']
        self.assertEqual(source['version'], '1.1.1')
        self.assertEqual(source['commit'], 'db0631dfea829194206d269bc7b25d0908cdb97d')
        archive = ROOT / source['archive']
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), source['archive_sha256'])
        with tarfile.open(archive) as tar:
            root = 'brotli-' + source['commit']
            decoder = tar.extractfile(root + '/c/dec/decode.c').read().decode()
            header = tar.extractfile(root + '/c/include/brotli/decode.h').read().decode()
            self.assertIn('BROTLI_SAFE_WITH_STATUS', decoder)
            self.assertIn('BROTLI_DECODER_ERROR_FORMAT_BLOCK_SWITCH', decoder)
            self.assertIn('BLOCK_SWITCH, -17', header)

    def test_every_packaging_input_matches_checksum(self):
        checksum_file = ROOT / self.metadata['debian_packaging']['checksums']
        covered = set()
        for line in checksum_file.read_text().splitlines():
            expected, name = line.split(maxsplit=1)
            name = name.strip()
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)
            covered.add(name)
        actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'vendor/brotli-debian/debian').rglob('*') if p.is_file()}
        self.assertEqual(covered, actual)

    def test_changelog_matches_real_source_version(self):
        packaging = self.metadata['debian_packaging']
        changelog = (ROOT / packaging['files']['changelog']).read_text()
        self.assertTrue(changelog.startswith('brotli (' + packaging['rebuild_version'] + ')'))
        self.assertTrue(packaging['rebuild_version'].startswith(self.metadata['upstream']['version'] + '-'))

    def test_strict_abi_and_real_tests_remain_enabled(self):
        build = (ROOT / 'scripts/build_brotli_packages.sh').read_text()
        self.assertIn('DPKG_GENSYMBOLS_CHECK_LEVEL=4', build)
        self.assertIn('dpkg-buildpackage --build=full', build)
        self.assertIn('python3 -m unittest discover', build)
        self.assertNotIn('nocheck', build)
        verifier = (ROOT / 'scripts/verify_brotli_package.sh').read_text()
        self.assertIn('comm -23', verifier)
        self.assertIn('Library soname:', verifier)


if __name__ == '__main__':
    unittest.main()
