#!/usr/bin/env python3
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from verify_oci_layout import verify_oci_layout


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def blob(value):
    data = value if isinstance(value, bytes) else json.dumps(value, separators=(",", ":")).encode()
    return digest(data), data


def descriptor(media, dg, data):
    return {"mediaType": media, "digest": dg, "size": len(data)}


def make_archive(directory, arch="amd64", image_id=None, root_mode="index", tamper=None):
    config_d, config_b = blob({"architecture": arch, "os": "linux", "rootfs": {"type": "layers", "diff_ids": []}})
    if image_id is None:
        image_id = config_d
    layer_d, layer_b = blob(b"runtime layer")
    manifest = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json", "config": descriptor("application/vnd.oci.image.config.v1+json", config_d, config_b), "layers": [descriptor("application/vnd.oci.image.layer.v1.tar", layer_d, layer_b)]}
    manifest_d, manifest_b = blob(manifest)
    att_cfg_d, att_cfg_b = blob({"architecture": "unknown", "os": "unknown"})
    att_layer_d, att_layer_b = blob(b"attestation")
    att = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json", "config": descriptor("application/vnd.oci.image.config.v1+json", att_cfg_d, att_cfg_b), "layers": [descriptor("application/vnd.in-toto+json", att_layer_d, att_layer_b)]}
    att_d, att_b = blob(att)
    index = {"schemaVersion": 2, "manifests": [descriptor("application/vnd.oci.image.manifest.v1+json", manifest_d, manifest_b), {**descriptor("application/vnd.oci.image.manifest.v1+json", att_d, att_b), "platform": {"os": "unknown", "architecture": "unknown"}, "annotations": {"vnd.docker.reference.type": "attestation-manifest", "vnd.docker.reference.digest": manifest_d}}]}
    index_b = json.dumps(index, separators=(",", ":")).encode()
    metadata_digest = manifest_d
    if root_mode == "index-digest":
        metadata_digest = digest(index_b)
    members = {"oci-layout": b'{"imageLayoutVersion":"1.0.0"}\n', "index.json": index_b,
               f"blobs/sha256/{manifest_d[7:]}": manifest_b, f"blobs/sha256/{config_d[7:]}": config_b,
               f"blobs/sha256/{layer_d[7:]}": layer_b, f"blobs/sha256/{att_d[7:]}": att_b,
               f"blobs/sha256/{att_cfg_d[7:]}": att_cfg_b, f"blobs/sha256/{att_layer_d[7:]}": att_layer_b}
    if tamper == "blob":
        members[f"blobs/sha256/{config_d[7:]}"] = b"tampered"
    if tamper == "missing-root":
        del members[f"blobs/sha256/{manifest_d[7:]}"]
    if tamper == "path":
        members["../escape"] = b"no"
    if tamper == "wrong-config":
        image_id = digest(b"different config")
    path = directory / "candidate.oci.tar"
    with tarfile.open(path, "w") as tar:
        for name in ("blobs/", "blobs/sha256/"):
            directory_info = tarfile.TarInfo(name)
            directory_info.type = tarfile.DIRTYPE
            tar.addfile(directory_info)
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path, {"manifest_digest": metadata_digest, "image_id": image_id, "arch": arch}


class VerifyOciLayoutTests(unittest.TestCase):
    def test_index_with_runtime_and_attestation_passes(self):
        with tempfile.TemporaryDirectory() as d:
            archive, metadata = make_archive(Path(d), root_mode="index-digest")
            evidence = verify_oci_layout(metadata, archive)
            self.assertEqual(evidence["candidate"]["manifest_digest"], metadata["manifest_digest"])
            self.assertEqual(evidence["verified"]["config_digest"], metadata["image_id"])
            self.assertEqual(evidence["verified"]["architecture"], "amd64")
            self.assertEqual(len(evidence["verified"]["traversed_digests"]), 6)
            self.assertEqual(len(evidence["archive"]["sha256"]), 64)

    def test_direct_manifest_root_digest_passes(self):
        with tempfile.TemporaryDirectory() as d:
            archive, metadata = make_archive(Path(d), root_mode="direct")
            evidence = verify_oci_layout(metadata, archive)
            self.assertEqual(evidence["verified"]["runtime_manifest_digest"], metadata["manifest_digest"])

    def test_tampered_blob_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive, metadata = make_archive(Path(d), tamper="blob")
            with self.assertRaisesRegex(ValueError, "size mismatch|digest mismatch|mismatched"):
                verify_oci_layout(metadata, archive)

    def test_wrong_architecture_and_config_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive, metadata = make_archive(Path(d), arch="arm64")
            metadata["arch"] = "amd64"
            with self.assertRaises(ValueError):
                verify_oci_layout(metadata, archive)
            archive, metadata = make_archive(Path(d), tamper="wrong-config")
            with self.assertRaises(ValueError):
                verify_oci_layout(metadata, archive)

    def test_missing_root_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive, metadata = make_archive(Path(d), tamper="missing-root")
            with self.assertRaisesRegex(ValueError, "missing blob"):
                verify_oci_layout(metadata, archive)

    def test_path_traversal_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            archive, metadata = make_archive(Path(d), tamper="path")
            with self.assertRaisesRegex(ValueError, "unsafe archive path"):
                verify_oci_layout(metadata, archive)
            self.assertFalse((Path(d).parent / "escape").exists())


if __name__ == "__main__":
    unittest.main()
