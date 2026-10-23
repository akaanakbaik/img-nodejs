import unittest
from triage_groups import group, normalize_package

class TriageGroupsTest(unittest.TestCase):
    def test_keeps_every_high_critical_and_joins_paths(self):
        audit = {"candidate": {"name": "x"}, "findings": [
            {"type":"debian","severity":"CRITICAL","package":"p","cve":"CVE-1","installed":"1","fixed_version":None,"status":"affected","sbom_refs":["r"]},
            {"type":"debian","severity":"HIGH","package":"p","cve":"CVE-2","installed":"1","fixed_version":"2","status":"fix_deferred"},
            {"type":"debian","severity":"LOW","package":"p","cve":"CVE-3"},
        ]}
        out = group(audit, {"packages":[{"package":"p","version":"1","files":[{"path":"/x"}]}]})
        self.assertEqual(out["counts"]["records"], 2)
        self.assertEqual(out["counts"]["critical"], 1)
        self.assertEqual(out["counts"]["fixed_version"], 1)
        ref = out['groups'][0]['path_inventory_ref']
        self.assertEqual(out['path_inventory'][ref]['files'], [{'path': '/x'}])

    def test_normalizes_multiarch_path_package_and_uses_raw_source(self):
        audit = {"findings": [{"type": "debian", "severity": "HIGH", "package": "libx", "installed": "1", "cve": "CVE-X", "status": "affected"}]}
        paths = {"packages": [{"package": "libx:arm64", "version": "1", "architecture": "arm64", "files": [{"path": "/usr/lib/a"}]}]}
        scan = {"Metadata": {"ImageID": "sha256:" + "a" * 64}, "Results": [{"Packages": [{"Name": "libx", "SrcName": "real-source", "SrcVersion": "2.0"}]}]}
        out = group(audit, paths, scan=scan)
        self.assertEqual(normalize_package("libx:arm64"), "libx")
        self.assertEqual(out["groups"][0]["source_package"], "real-source")
        self.assertEqual(out["groups"][0]["source_version"], "2.0")
        self.assertEqual(out["counts"]["path_mapped_packages"], 1)

    def test_rejects_path_version_mismatch(self):
        audit = {"findings": [{"type": "debian", "severity": "HIGH", "package": "libx", "installed": "2", "cve": "CVE-X"}]}
        paths = {"packages": [{"package": "libx:amd64", "version": "1", "files": []}]}
        with self.assertRaises(ValueError):
            group(audit, paths)

    def test_preserves_digest_and_rejects_unbound_vendor_evidence(self):
        candidate = {'image_id': 'sha256:' + 'a' * 64, 'manifest_digest': 'sha256:' + 'b' * 64, 'arch': 'arm64'}
        audit = {'candidate': candidate, 'findings': []}
        out = group(audit, candidate='nodejs_24-arm64')
        self.assertEqual(out['candidate'], candidate)
        self.assertEqual(out['candidate_name'], 'nodejs_24-arm64')
        for key, value in (('image_id', 'sha256:' + 'c' * 64), ('arch', 'amd64'), ('manifest_digest', 'sha256:' + 'd' * 64)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                group(audit, apt={'candidate': dict(candidate, **{key: value}), 'packages': []})
        with self.assertRaises(ValueError):
            group(audit, sbom={'bomFormat': 'CycloneDX', 'components': []})

if __name__ == "__main__": unittest.main()
