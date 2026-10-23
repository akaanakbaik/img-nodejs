#!/usr/bin/env python3
"""Regression invariants for the actual workflow, without registry access."""
import json
import gzip
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import textwrap
import unittest

from test_verify_oci_layout import make_archive

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
        self.assertEqual(freeze.count('--download-db-only'), 1)
        self.assertIn('trivy image --download-db-only', freeze)
        self.assertIn('trivy --version --format json > scanner-db-snapshot/scanner-metadata.json', freeze)
        self.assertIn('db/trivy.db db/metadata.json > scanner-db.sha256', freeze)
        self.assertIn('scanner-db-metadata.json', freeze)
        scan = section('Scan image and repository')
        self.assertEqual(scan.count('--skip-db-update'), 3)
        self.assertEqual(scan.count('--image-src docker'), 2)
        self.assertIn('(cd "$TRIVY_CACHE_DIR" && sha256sum --check scanner-db.sha256)', scan)
        self.assertIn('scanner-metadata-after.json', scan)
        self.assertIn('sha256sum trivy-*.json scanner-*.json > scan-evidence.sha256', scan)
        gates = section('Block CVE-2026-111497 at every severity') + section('Enforce vulnerability and repository security gates')
        self.assertNotRegex(gates, r'33[34]|340')
        for name in ('Upload scan reports', 'Upload exact tested image'):
            upload = section(name)
            for evidence in ('trivy-*.json', 'scanner-*.json', 'scanner-db.sha256', 'scan-evidence.sha256'):
                self.assertIn(evidence, upload)

    def test_shared_database_is_produced_once_consumed_immutably_and_checked_before_scans(self):
        metadata = WORKFLOW.split('\n  validate-metadata:', 1)[1].split('\n  verify:', 1)[0]
        verify = WORKFLOW.split('\n  verify:', 1)[1].split('\n  publish-arch:', 1)[0]
        freeze = section('Freeze and record vulnerability database snapshot')
        upload_db = section('Upload immutable shared vulnerability database')
        upload_db = upload_db.split('\n\n  verify:', 1)[0]
        self.assertEqual(WORKFLOW.count('trivy image --download-db-only'), 1)
        self.assertIn('db_artifact_name:', metadata)
        self.assertIn("printf 'db_artifact_name=", freeze)
        self.assertIn('if-no-files-found: error', upload_db)
        self.assertNotIn('continue-on-error:', upload_db)
        self.assertIn('name: ${{ needs.validate-metadata.outputs.db_artifact_name }}', verify)
        self.assertNotIn('--download-db-only', verify)
        download = section('Download immutable shared vulnerability database')
        self.assertIn('name: ${{ needs.validate-metadata.outputs.db_artifact_name }}', download)
        snapshot = section('Verify shared vulnerability database snapshot')
        scan = section('Scan image and repository')
        self.assertIn('EXPECTED_DB_SHA256: ${{ needs.validate-metadata.outputs.db_sha256 }}', snapshot)
        self.assertIn('EXPECTED_SNAPSHOT_SHA256: ${{ needs.validate-metadata.outputs.db_snapshot_sha256 }}', snapshot)
        for check in ('sha256sum --check scanner-db.sha256', 'sha256sum "$TRIVY_CACHE_DIR/db/trivy.db"'):
            self.assertIn(check, snapshot)
        self.assertLess(verify.index('Verify shared vulnerability database snapshot'),
                        verify.index('Scan image and repository'))
        self.assertLess(scan.index('sha256sum --check scanner-db.sha256'),
                        scan.index('trivy --version --format json > scanner-metadata-after.json'))
        push = section('Verify and push immutable OCI architecture candidate')
        self.assertIn('test "$(jq -er .db_sha256 scanner-db-identity.json)" = "$EXPECTED_DB_SHA256"', push)
        self.assertIn('test "$(sha256sum scanner-db.sha256 | cut -d\' \' -f1)" = "$EXPECTED_SNAPSHOT_SHA256"', push)
        self.assertLess(push.index('test "$(jq -er .db_sha256 scanner-db-identity.json)"'),
                        push.index('skopeo login'))

    def test_actual_arch_publish_body_gates_bundle_before_fake_registry(self):
        """Execute the workflow's publish shell, with only skopeo replaced."""
        push = section('Verify and push immutable OCI architecture candidate')
        body = textwrap.dedent(push.split('run: |', 1)[1])
        body = (body.replace('${{ matrix.major }}', '22')
                    .replace('${{ matrix.arch }}', 'amd64')
                    .replace('${{ github.actor }}', 'test-user'))

        def run_case(change=None):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                scripts = root / 'scripts'
                scripts.symlink_to(ROOT / 'scripts', target_is_directory=True)
                archive, metadata = make_archive(root, arch='amd64', root_mode='direct')
                (root / 'candidate-metadata.json').write_text(json.dumps(metadata))
                scan = {'Metadata': {'ImageID': metadata['image_id']}, 'Results': []}
                sbom = {'bomFormat': 'CycloneDX', 'metadata': {'component': {'properties': [
                    {'name': 'aquasecurity:trivy:ImageID', 'value': metadata['image_id']}]}},
                    'components': [{'bom-ref': 'pkg-ref', 'purl': 'pkg:npm/example@1.0.0', 'properties': []}]}
                repo = {'Results': [{'Target': 'repo', 'Vulnerabilities': [], 'Misconfigurations': [], 'Secrets': []}]}
                values = {'trivy-image-22-amd64.json': scan, 'trivy-sbom-22-amd64.json': sbom,
                          'trivy-repo-22-amd64.json': repo}
                for name, value in values.items():
                    (root / name).write_text(json.dumps(value))
                def refresh_evidence():
                    paths = sorted(root.glob('trivy-*.json'))
                    (root / 'scan-evidence.sha256').write_text(''.join(
                        hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n' for path in paths))
                refresh_evidence()
                with tarfile.open(archive) as tar:
                    index = json.loads(tar.extractfile('index.json').read())
                    manifest_name = 'blobs/sha256/' + index['manifests'][0]['digest'][7:]
                    manifest_bytes = tar.extractfile(manifest_name).read()
                image = root / 'image-22-amd64.tar.gz'
                with image.open('wb') as output, archive.open('rb') as source:
                    with gzip.GzipFile(fileobj=output, mode='wb', compresslevel=1) as zipped:
                        zipped.write(source.read())
                (root / 'image-22-amd64.tar.gz.sha256').write_text(
                    hashlib.sha256(image.read_bytes()).hexdigest() + '  ' + image.name + '\n')
                db_sha256 = 'a' * 64
                (root / 'scanner-db.sha256').write_text(db_sha256 + '  db/trivy.db\n')
                snapshot_sha256 = hashlib.sha256((root / 'scanner-db.sha256').read_bytes()).hexdigest()
                (root / 'scanner-db-identity.json').write_text(json.dumps({
                    'db_sha256': db_sha256, 'snapshot_sha256': snapshot_sha256}))
                if change:
                    change(metadata, values, root)
                    (root / 'candidate-metadata.json').write_text(json.dumps(metadata))
                    for name, value in values.items():
                        (root / name).write_text(json.dumps(value))
                    refresh_evidence()

                fake = root / 'fake-bin'
                fake.mkdir()
                log = root / 'skopeo.log'
                manifest = root / 'manifest.json'
                manifest.write_bytes(manifest_bytes)
                (fake / 'skopeo').write_text(textwrap.dedent('''\
                    #!/bin/sh
                    set -eu
                    printf '%s\n' "$*" >> "$FAKE_SKOPEO_LOG"
                    case "$1" in
                      login|copy) exit 0 ;;
                      inspect) cat "$FAKE_SKOPEO_MANIFEST" ;;
                      *) exit 2 ;;
                    esac
                '''))
                (fake / 'skopeo').chmod(0o755)
                env = os.environ.copy()
                env.update({'IMAGE': 'ghcr.io/example/test', 'STAGE': 'stage', 'REGISTRY': 'ghcr.io',
                            'REGISTRY_TOKEN': 'dummy', 'PATH': str(fake) + os.pathsep + env['PATH'],
                            'FAKE_SKOPEO_LOG': str(log), 'FAKE_SKOPEO_MANIFEST': str(manifest),
                            'EXPECTED_DB_SHA256': db_sha256,
                            'EXPECTED_SNAPSHOT_SHA256': snapshot_sha256})
                result = subprocess.run(['bash', '-c', body], cwd=root, env=env, text=True, capture_output=True)
                return result, (log.read_text() if log.exists() else ''), (root / 'digest-22-amd64.txt').read_text() if (root / 'digest-22-amd64.txt').exists() else '', metadata

        result, commands_text, digest_record, metadata = run_case()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = commands_text.splitlines()
        self.assertTrue(any(command.startswith('login ') for command in commands))
        self.assertTrue(any(command.startswith('copy --preserve-digests ') for command in commands))
        self.assertEqual(digest_record,
                         f"digest=ghcr.io/example/test@{metadata['manifest_digest']}\n")

        def assert_rejected(change):
            result, commands_text, _digest_record, _metadata = run_case(change)
            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertFalse(commands_text.strip(), result.stderr)

        def priority(_metadata, values, _root):
            values['trivy-image-22-amd64.json']['Results'] = [{'Target': 'node', 'Type': 'node-pkg',
                'Vulnerabilities': [{'VulnerabilityID': 'CVE-2026-111497', 'Severity': 'UNKNOWN',
                'PkgName': 'example', 'InstalledVersion': '1.0.0',
                'PkgIdentifier': {'PURL': 'pkg:npm/example@1.0.0'}}]}]

        def repo_finding(_metadata, values, _root):
            values['trivy-repo-22-amd64.json']['Results'][0]['Misconfigurations'] = [{'Severity': 'HIGH'}]

        def image_identity(metadata, values, _root):
            values['trivy-image-22-amd64.json']['Metadata']['ImageID'] = 'sha256:' + 'c' * 64

        def sbom_identity(metadata, values, _root):
            values['trivy-sbom-22-amd64.json']['metadata']['component']['properties'][0]['value'] = 'sha256:' + 'd' * 64

        def bad_checksum(_metadata, _values, root):
            (root / 'image-22-amd64.tar.gz.sha256').write_text('0' * 64 + '  image-22-amd64.tar.gz\n')

        def bad_db_snapshot(_metadata, _values, root):
            (root / 'scanner-db.sha256').write_text('b' * 64 + '  db/trivy.db\n')

        def wrong_db_identity(_metadata, _values, root):
            (root / 'scanner-db-identity.json').write_text(json.dumps({
                'db_sha256': 'c' * 64, 'snapshot_sha256': '0' * 64}))

        def wrong_arch(metadata, _values, _root):
            metadata['arch'] = 'arm64'

        for change in (priority, repo_finding, image_identity, sbom_identity, bad_checksum,
                       bad_db_snapshot, wrong_db_identity, wrong_arch):
            with self.subTest(change=change.__name__):
                assert_rejected(change)


if __name__ == '__main__':
    unittest.main()
