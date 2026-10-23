#!/usr/bin/env python3
import copy
import unittest
from audit_scan import audit


class AuditScanTests(unittest.TestCase):
    def setUp(self):
        self.image_id = 'sha256:' + 'a' * 64
        self.purl = 'pkg:npm/example@1.0.0'
        self.candidate = {'image_id': self.image_id, 'manifest_digest': 'sha256:' + 'b' * 64, 'arch': 'arm64'}
        self.scan = {'Metadata': {'ImageID': self.image_id}, 'Results': [
            {'Target': 'Node.js', 'Type': 'node-pkg', 'Vulnerabilities': [
                {'VulnerabilityID': 'CVE-2026-111497', 'Severity': 'UNKNOWN',
                 'PkgName': 'example', 'InstalledVersion': '1.0.0',
                 'PkgPath': 'usr/lib/example/package.json',
                 'PkgIdentifier': {'PURL': self.purl}}
            ]}
        ]}
        self.sbom = {'bomFormat': 'CycloneDX', 'metadata': {'component': {'properties': [
            {'name': 'aquasecurity:trivy:ImageID', 'value': self.image_id}
        ]}}, 'components': [{'bom-ref': 'example-ref', 'purl': self.purl, 'properties': [
            {'name': 'aquasecurity:trivy:FilePath', 'value': 'usr/lib/example/package.json'}
        ]}]}

    def run_audit(self):
        return audit(self.candidate, self.scan, self.sbom)

    def test_priority_unknown_retained(self):
        out = self.run_audit()
        self.assertEqual(out['blocking_package_cve_pairs'], 1)
        self.assertEqual(out['priority_findings'][0]['severity'], 'UNKNOWN')
        self.assertEqual(out['findings'][0]['sbom_refs'], ['example-ref'])

    def test_scanner_image_mismatch(self):
        self.scan['Metadata']['ImageID'] = 'sha256:' + 'c' * 64
        with self.assertRaises(ValueError): self.run_audit()

    def test_sbom_image_mismatch(self):
        self.sbom['metadata']['component']['properties'][0]['value'] = 'other'
        with self.assertRaises(ValueError): self.run_audit()

    def test_sbom_package_missing(self):
        self.sbom['components'][0]['purl'] = 'pkg:npm/other@1.0.0'
        with self.assertRaises(ValueError): self.run_audit()

    def test_sbom_path_mismatch(self):
        self.sbom['components'][0]['properties'][0]['value'] = 'other/package.json'
        with self.assertRaises(ValueError): self.run_audit()

    def test_invalid_manifest(self):
        self.candidate['manifest_digest'] = ''
        with self.assertRaises(ValueError): self.run_audit()

    def test_malformed_scan(self):
        self.scan['Results'] = None
        with self.assertRaises(ValueError): self.run_audit()

    def test_all_findings_retained_without_reclassifying(self):
        v = self.scan['Results'][0]['Vulnerabilities'][0]
        for severity in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL'):
            other = copy.deepcopy(v)
            other.update(VulnerabilityID='CVE-OTHER-' + severity, Severity=severity)
            self.scan['Results'][0]['Vulnerabilities'].append(other)
        out = self.run_audit()
        self.assertEqual(len(out['findings']), 5)
        self.assertEqual(out['blocking_package_cve_pairs'], 3)


if __name__ == '__main__':
    unittest.main()
