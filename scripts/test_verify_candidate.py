#!/usr/bin/env python3
import hashlib
import tempfile
import unittest
from pathlib import Path

from verify_candidate import verify_candidate, verify_sha256

ID = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64


def candidate():
    return {"manifest_digest": "sha256:" + "c" * 64, "image_id": ID, "arch": "amd64"}


class VerifyCandidateTests(unittest.TestCase):
    def test_matching_candidate_scanner_and_inspect_pass(self):
        verify_candidate(candidate(), {"Metadata": {"ImageID": ID}}, {"image_id": ID, "architecture": "amd64"}, "amd64")

    def test_malformed_manifest_rejected(self):
        value = candidate()
        value['manifest_digest'] = 'not-a-manifest'
        with self.assertRaises(ValueError):
            verify_candidate(value, {"Metadata": {"ImageID": ID}}, {"image_id": ID, "architecture": "amd64"})

    def test_empty_manifest_or_image_id_rejected(self):
        for key in ("manifest_digest", "image_id", "arch"):
            value = candidate()
            value[key] = ""
            with self.subTest(key=key), self.assertRaises(ValueError):
                verify_candidate(value, {"Metadata": {"ImageID": ID}}, {"image_id": ID, "architecture": "amd64"})

    def test_scanner_id_must_match_loaded_id(self):
        with self.assertRaises(ValueError):
            verify_candidate(candidate(), {"Metadata": {"ImageID": OTHER}}, {"image_id": ID, "architecture": "amd64"})

    def test_architecture_must_match(self):
        with self.assertRaises(ValueError):
            verify_candidate(candidate(), {"Metadata": {"ImageID": ID}}, {"image_id": ID, "architecture": "arm64"})

    def test_sha256_record_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "image.tar.gz"
            checksum = Path(directory) / "image.tar.gz.sha256"
            artifact.write_bytes(b"tested image")
            digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
            checksum.write_text(f"{digest}  {artifact.name}\n")
            self.assertEqual(verify_sha256(artifact, checksum), digest)

    def test_sha256_mismatch_and_malformed_records_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "image.tar.gz"
            checksum = Path(directory) / "image.tar.gz.sha256"
            artifact.write_bytes(b"tested image")
            for record in ("0" * 64 + "  image.tar.gz\n", "not-a-checksum\n", "\n", ("0" * 64 + "  image.tar.gz\n") * 2):
                checksum.write_text(record)
                with self.subTest(record=record), self.assertRaises(ValueError):
                    verify_sha256(artifact, checksum)


if __name__ == "__main__":
    unittest.main()
