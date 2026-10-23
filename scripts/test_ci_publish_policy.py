#!/usr/bin/env python3
"""Regression invariants for the actual workflow, without registry access."""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / '.github/workflows/publish.yml').read_text()


def section(name):
    return WORKFLOW.split('name: ' + name, 1)[1].split('\n      - name:', 1)[0]


class PublishPolicyTests(unittest.TestCase):
    def test_publication_requires_all_supported_jobs_and_explicit_main_dispatch(self):
        arch = WORKFLOW.split('\n  publish-arch:', 1)[1].split('\n  publish-manifest:', 1)[0]
        manifest = WORKFLOW.split('\n  publish-manifest:', 1)[1]
        self.assertIn('needs: [validate-metadata, verify]', arch)
        self.assertIn("if: github.ref == 'refs/heads/main' && needs.verify.result == 'success' && github.event_name == 'workflow_dispatch' && inputs.publish == true", arch)
        self.assertIn('needs: [validate-metadata, publish-arch]', manifest)
        self.assertIn("inputs.publish == true && needs.publish-arch.result == 'success'", manifest)
        self.assertNotIn('continue-on-error:', arch + manifest)
        self.assertNotIn('always()', arch + manifest)
        self.assertEqual(WORKFLOW.count('packages: write'), 2)
        self.assertNotIn('pull_request_target:', WORKFLOW)

    def test_eol_report_only_but_all_supported_pairs_required(self):
        self.assertIn('continue-on-error: ${{ !matrix.publish }}', WORKFLOW)
        self.assertIn('resolve_versions.py --check --supported-only', WORKFLOW)
        matrix = section('Resolve exact patch matrix')
        expressions = re.findall(r"jq -e '([^']+)'", matrix)
        required = next(e for e in expressions if '.publish.include' in e)
        pairs = [(m, a) for m in ('22', '24', '26') for a in ('amd64', 'arm64')]
        for excluded in [None] + pairs:
            report = {'publish': {'include': [{'major': m, 'arch': a} for m, a in pairs if (m, a) != excluded]}}
            result = subprocess.run(['jq', '-e', required], input=json.dumps(report), text=True, capture_output=True)
            self.assertEqual(result.returncode == 0, excluded is None)

    def test_export_requires_success_of_gates_and_release_bundle(self):
        self.assertIn("if: success() && matrix.publish && steps.gate.outcome == 'success'", section('Verify complete release bundle before export'))
        self.assertIn("if: success() && steps.gate.outcome == 'success' && steps.bundle.outcome == 'success'", section('Save exact tested image'))
        self.assertIn("if: steps.save.outcome == 'success'", section('Upload exact tested image'))
        self.assertEqual(WORKFLOW.count('continue-on-error:'), 1)
        self.assertNotIn('docker save', WORKFLOW)
        self.assertNotIn('docker load', WORKFLOW)

    def test_exact_oci_and_evidence_rechecked_before_registry_login(self):
        push = section('Verify and push immutable OCI architecture candidate')
        for check in ('verify_sha256', 'sha256sum --check scan-evidence.sha256', 'scripts/verify_release_bundle.py'):
            self.assertLess(push.index(check), push.index('skopeo login'))
        self.assertIn('skopeo copy --preserve-digests', push)
        self.assertIn('test "$remote" = "$digest"', push)
        for flag in ('--metadata', '--oci', '--scanner-report', '--sbom', '--repo-report', '--expected-arch'):
            self.assertIn(flag, push)
        self.assertIn('gzip -1 -c candidate.oci.tar', section('Save exact tested image'))
        self.assertIn('provenance: false', WORKFLOW)
        self.assertIn('sbom: false', WORKFLOW)

    def test_db_snapshot_and_raw_evidence_not_fixed_finding_counts(self):
        freeze = section('Freeze and record vulnerability database snapshot')
        self.assertIn('trivy image --download-db-only', freeze)
        self.assertIn('trivy --version --format json > scanner-metadata.json', freeze)
        self.assertIn('$TRIVY_CACHE_DIR/db/trivy.db', freeze)
        self.assertIn('scanner-db-metadata.json', freeze)
        scan = section('Scan image and repository')
        self.assertEqual(scan.count('--skip-db-update'), 3)
        self.assertEqual(scan.count('--image-src docker'), 2)
        self.assertIn('sha256sum --check scanner-db.sha256', scan)
        self.assertIn('scanner-metadata-after.json', scan)
        self.assertIn('sha256sum trivy-*.json scanner-*.json > scan-evidence.sha256', scan)
        gates = section('Block CVE-2026-111497 at every severity') + section('Enforce vulnerability and repository security gates')
        self.assertNotRegex(gates, r'33[34]|340')
        for name in ('Upload scan reports', 'Upload exact tested image'):
            upload = section(name)
            for evidence in ('trivy-*.json', 'scanner-*.json', 'scanner-db.sha256', 'scan-evidence.sha256'):
                self.assertIn(evidence, upload)


if __name__ == '__main__':
    unittest.main()
