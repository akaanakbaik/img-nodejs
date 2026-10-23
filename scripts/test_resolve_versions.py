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

    def test_supported_only_allows_missing_and_stale_eol(self):
        self.index.write_text(json.dumps([{'version': '22.23.4'}, {'version': '24.22.1'}, {'version': '26.12.1'}, {'version': '18.99.0'}]))
        self.assertTrue(rv.check_manifest(self.manifest, self.url, supported_only=True))
        with self.assertRaises(RuntimeError): rv.check_manifest(self.manifest, self.url)

    def test_supported_only_still_rejects_stale_or_missing_supported(self):
        for versions in (['22.99.0', '24.22.1', '26.12.1'], ['24.22.1', '26.12.1']):
            self.index.write_text(json.dumps([{'version': v} for v in versions]))
            with self.subTest(versions=versions), self.assertRaises(RuntimeError):
                rv.check_manifest(self.manifest, self.url, supported_only=True)

    def test_ci_publication_is_supported_only_both_architectures(self):
        matrices = rv.ci_matrices(self.manifest)
        self.assertEqual(len(matrices['verify']['include']), 18)
        self.assertEqual({(x['major'], x['arch']) for x in matrices['publish']['include']}, {(m,a) for m in ('22','24','26') for a in ('amd64','arm64')})
        self.assertEqual({x['major'] for x in matrices['manifests']['include']}, {'22','24','26'})
        self.assertTrue(all(not x['publish'] for x in matrices['verify']['include'] if x['major'] not in ('22','24','26')))
    def test_eol_cannot_be_published_even_if_manifest_marks_supported(self):
        data = json.loads(self.manifest.read_text())
        for item in data['versions']: item['supported'] = True
        self.manifest.write_text(json.dumps(data))
        self.assertEqual({x['major'] for x in rv.ci_matrices(self.manifest)['publish']['include']}, {'22','24','26'})
    def test_workflow_eol_failures_nonblocking_and_cve_gate_supported_only(self):
        workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/publish.yml').read_text()
        self.assertIn('continue-on-error: ${{ !matrix.publish }}', workflow)
        self.assertIn('name: Block CVE-2026-111497 at every severity\n        if: matrix.publish', workflow)
        self.assertIn('matrix: ${{ fromJSON(needs.validate-metadata.outputs.publish_matrix) }}', workflow)
        self.assertNotIn('inputs.include_eol', workflow)
        self.assertIn("github.ref == 'refs/heads/main' && needs.verify.result == 'success'", workflow)

if __name__ == '__main__': unittest.main()
