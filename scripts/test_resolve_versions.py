#!/usr/bin/env python3
import json, tempfile, unittest
from pathlib import Path
import resolve_versions as rv

class ResolveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.index = Path(self.tmp.name) / 'index.json'
        self.manifest = Path(self.tmp.name) / 'versions.json'
        entries = [{"major": m, "version": v, "supported": m in (22,24,26)} for m,v in [(18,'18.20.8'),(19,'19.9.0'),(20,'20.20.2'),(21,'21.7.3'),(22,'22.23.4'),(23,'23.11.1'),(24,'24.22.1'),(25,'25.9.0'),(26,'26.12.1')]]
        self.manifest.write_text(json.dumps({"versions": entries}))
        self.index.write_text(json.dumps([{"version": e['version']} for e in entries] + [{"version":"22.99.0-rc.1"}]))
        self.url = 'file://' + str(self.index)
    def tearDown(self): self.tmp.cleanup()
    def test_latest_and_matrix(self):
        self.assertTrue(rv.check_manifest(self.manifest, self.url))
        self.assertEqual(rv.matrix(self.manifest)[4], {"node":"22","version":"22.23.4","supported":True})
    def test_stale_version_rejected(self):
        data = json.loads(self.manifest.read_text()); data['versions'][4]['version'] = '22.0.0'; self.manifest.write_text(json.dumps(data))
        with self.assertRaises(RuntimeError): rv.check_manifest(self.manifest, self.url)
    def test_wrong_major_rejected(self):
        data = json.loads(self.manifest.read_text()); data['versions'][0]['version'] = '17.9.0'; self.manifest.write_text(json.dumps(data))
        with self.assertRaises(ValueError): rv.load_manifest(self.manifest)
    def test_prerelease_ignored(self):
        self.assertEqual(rv.latest_stable([{"version":"24.99.0-rc.1"},{"version":"24.22.1"}])[24], '24.22.1')

if __name__ == '__main__': unittest.main()
