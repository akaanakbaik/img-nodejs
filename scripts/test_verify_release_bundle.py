#!/usr/bin/env python3
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verify_release_bundle import main, verify_release_bundle
from test_verify_oci_layout import make_archive


class VerifyReleaseBundleTests(unittest.TestCase):
    def setUp(self):
        self.image_id = "sha256:" + "a" * 64
        self.manifest = "sha256:" + "b" * 64
        self.purl = "pkg:npm/example@1.0.0"
        self.metadata = {"image_id": self.image_id, "manifest_digest": self.manifest, "arch": "amd64"}
        self.scan = {"Metadata": {"ImageID": self.image_id}, "Results": [{
            "Target": "node", "Type": "node-pkg", "Vulnerabilities": [{
                "VulnerabilityID": "CVE-OTHER", "Severity": "LOW", "PkgName": "example",
                "InstalledVersion": "1.0.0", "PkgIdentifier": {"PURL": self.purl},
            }]
        }]}
        self.sbom = {"bomFormat": "CycloneDX", "metadata": {"component": {"properties": [
            {"name": "aquasecurity:trivy:ImageID", "value": self.image_id}
        ]}}, "components": [{"bom-ref": "ref", "purl": self.purl, "properties": []}]}
        self.repo = {"Results": [{"Target": "repo", "Vulnerabilities": [], "Misconfigurations": [], "Secrets": []}]}
        self.oci = Path("candidate.oci.tar")
        self.oci_evidence = {"verified": {"runtime_manifest_digest": self.manifest, "architecture": "amd64"}}

    def verify(self, **changes):
        values = {"metadata": self.metadata, "scan": self.scan, "sbom": self.sbom, "repo": self.repo}
        values.update(changes)
        expected_arch = values.pop("expected_arch", "amd64")
        with patch("verify_release_bundle.verify_oci_layout", return_value=self.oci_evidence):
            return verify_release_bundle(values["metadata"], self.oci, values["scan"], values["sbom"], values["repo"], expected_arch)

    def test_passes_and_returns_runtime_root(self):
        self.assertEqual(self.verify(), self.manifest)

    def test_architecture_is_strict(self):
        with self.assertRaises(ValueError): self.verify(expected_arch="arm64")
        self.metadata["arch"] = "arm64"
        with self.assertRaises(ValueError): self.verify()

    def test_wrong_root_digest_rejected(self):
        self.metadata["manifest_digest"] = "sha256:" + "c" * 64
        with self.assertRaisesRegex(ValueError, "runtime manifest"):
            self.verify()

    def test_image_scan_and_sbom_identity_rejected(self):
        bad_scan = copy.deepcopy(self.scan)
        bad_scan["Metadata"]["ImageID"] = "sha256:" + "c" * 64
        with self.assertRaises(ValueError): self.verify(scan=bad_scan)
        bad_sbom = copy.deepcopy(self.sbom)
        bad_sbom["metadata"]["component"]["properties"][0]["value"] = "sha256:" + "c" * 64
        with self.assertRaises(ValueError): self.verify(sbom=bad_sbom)

    def test_priority_cve_blocks_at_every_severity(self):
        for severity in ("UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
            scan = copy.deepcopy(self.scan)
            scan["Results"][0]["Vulnerabilities"][0].update(VulnerabilityID="CVE-2026-111497", Severity=severity)
            with self.assertRaises(ValueError, msg=severity): self.verify(scan=scan)

    def test_high_critical_image_findings_block(self):
        for severity in ("HIGH", "CRITICAL"):
            scan = copy.deepcopy(self.scan)
            scan["Results"][0]["Vulnerabilities"][0]["Severity"] = severity
            with self.assertRaises(ValueError): self.verify(scan=scan)

    def test_repository_categories_block_high_critical_and_priority(self):
        for category in ("Vulnerabilities", "Misconfigurations", "Secrets"):
            for finding in ({"Severity": "HIGH", "VulnerabilityID": "CVE-OTHER"}, {"Severity": "CRITICAL", "VulnerabilityID": "CVE-OTHER"}, {"Severity": "LOW", "VulnerabilityID": "CVE-2026-111497"}):
                repo = {"Results": [{"Target": "repo", "Vulnerabilities": [], "Misconfigurations": [], "Secrets": []}]}
                repo["Results"][0][category] = [finding]
                with self.assertRaises(ValueError, msg=(category, finding)):
                    self.verify(repo=repo)

    def test_malformed_results_and_findings_fail_closed(self):
        for field, value in (("Results", None), ("Results", {})):
            scan = copy.deepcopy(self.scan); scan[field] = value
            with self.assertRaises(ValueError): self.verify(scan=scan)
        for value in (None, {}, ["not an object"]):
            scan = copy.deepcopy(self.scan); scan["Results"][0]["Vulnerabilities"] = value
            with self.assertRaises(ValueError): self.verify(scan=scan)
        for severity in (None, "bogus"):
            scan = copy.deepcopy(self.scan); scan["Results"][0]["Vulnerabilities"][0]["Severity"] = severity
            with self.assertRaises(ValueError): self.verify(scan=scan)
        scan = copy.deepcopy(self.scan); del scan["Results"][0]["Vulnerabilities"][0]["VulnerabilityID"]
        with self.assertRaises(ValueError): self.verify(scan=scan)

    def test_missing_and_null_category_lists_are_clean(self):
        repo = {"Results": [{"Target": "repo"}, {"Target": "repo", "Vulnerabilities": None, "Misconfigurations": None, "Secrets": None}]}
        self.assertEqual(self.verify(repo=repo), self.manifest)

    def test_cli_prints_only_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for name, value in (("metadata", self.metadata), ("scanner-report", self.scan), ("sbom", self.sbom), ("repo-report", self.repo)):
                path = Path(directory) / (name + ".json"); path.write_text(json.dumps(value)); paths[name] = path
            with patch("verify_release_bundle.verify_oci_layout", return_value=self.oci_evidence), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                self.assertEqual(main(["--metadata", str(paths["metadata"]), "--oci", str(self.oci), "--scanner-report", str(paths["scanner-report"]), "--sbom", str(paths["sbom"]), "--repo-report", str(paths["repo-report"]), "--expected-arch", "amd64"]), 0)
                self.assertEqual(stdout.getvalue(), self.manifest + "\n")

    def test_real_oci_cli_passes_clean_and_rejects_cve_or_tampering(self):
        for arch in ('amd64', 'arm64'):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive, metadata = make_archive(root, arch=arch, root_mode='direct')
                scan = copy.deepcopy(self.scan)
                sbom = copy.deepcopy(self.sbom)
                scan['Metadata']['ImageID'] = metadata['image_id']
                sbom['metadata']['component']['properties'][0]['value'] = metadata['image_id']
                arguments = [sys.executable, str(Path(__file__).with_name('verify_release_bundle.py')), '--oci', str(archive), '--expected-arch', arch]
                for name, value in (('metadata', metadata), ('scanner-report', scan), ('sbom', sbom), ('repo-report', self.repo)):
                    path = root / (name + '.json')
                    path.write_text(json.dumps(value))
                    arguments.extend(['--' + name, str(path)])
                clean = subprocess.run(arguments, text=True, capture_output=True)
                self.assertEqual(clean.returncode, 0, clean.stderr)
                self.assertEqual(clean.stdout, metadata['manifest_digest'] + '\n')
                scan['Results'][0]['Vulnerabilities'][0].update(VulnerabilityID='CVE-2026-111497', Severity='UNKNOWN')
                (root / 'scanner-report.json').write_text(json.dumps(scan))
                blocked = subprocess.run(arguments, text=True, capture_output=True)
                self.assertNotEqual(blocked.returncode, 0)
                self.assertEqual(blocked.stdout, '')
                self.assertIn('gate failed', blocked.stderr)
                make_archive(root, arch=arch, root_mode='direct', tamper='blob')
                corrupt = subprocess.run(arguments, text=True, capture_output=True)
                self.assertNotEqual(corrupt.returncode, 0)
                self.assertEqual(corrupt.stdout, '')


if __name__ == "__main__":
    unittest.main()
