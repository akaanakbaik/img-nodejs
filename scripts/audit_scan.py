#!/usr/bin/env python3
"""Correlate an unfiltered Trivy report with its final-image CycloneDX SBOM.

Evidence only: never removes, suppresses, reclassifies, or accepts a finding.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

PRIORITY = 'CVE-2026-111497'
DIGEST = re.compile(r'^sha256:[0-9a-f]{64}$')


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def properties(component, suffix):
    return [p['value'] for p in component.get('properties', [])
            if p.get('name') == 'aquasecurity:trivy:' + suffix]


def audit(candidate, report, sbom):
    image_id = candidate.get('image_id', '')
    if not DIGEST.fullmatch(image_id):
        raise ValueError('missing/invalid candidate image ID')
    if not DIGEST.fullmatch(candidate.get('manifest_digest', '')):
        raise ValueError('missing/invalid candidate manifest digest')
    if candidate.get('arch') not in ('amd64', 'arm64'):
        raise ValueError('unsupported candidate architecture')
    if report.get('Metadata', {}).get('ImageID') != image_id:
        raise ValueError('scan does not belong to candidate image ID')
    if not isinstance(report.get('Results'), list):
        raise ValueError('invalid/missing scan results')
    if sbom.get('bomFormat') != 'CycloneDX':
        raise ValueError('expected CycloneDX SBOM')
    sbom_image = sbom.get('metadata', {}).get('component', {})
    if properties(sbom_image, 'ImageID') != [image_id]:
        raise ValueError('SBOM does not belong to candidate image ID')
    components = sbom.get('components')
    if not isinstance(components, list) or not components:
        raise ValueError('empty/invalid SBOM components')
    by_purl = defaultdict(list)
    for c in components:
        if c.get('purl'):
            by_purl[c['purl']].append(c)
    findings = []
    for result in report['Results']:
        for v in result.get('Vulnerabilities', []):
            purl = v.get('PkgIdentifier', {}).get('PURL')
            matches = by_purl.get(purl, [])
            path = v.get('PkgPath')
            if path:
                matches = [c for c in matches if path in properties(c, 'FilePath')]
            if not matches:
                raise ValueError('finding has no matching SBOM package/path: ' + str((v.get('PkgID'), path, purl)))
            findings.append({
                'cve': v['VulnerabilityID'], 'severity': v['Severity'],
                'package': v['PkgName'], 'installed': v['InstalledVersion'],
                'fixed_version': v.get('FixedVersion'), 'status': v.get('Status'),
                'target': result['Target'], 'type': result.get('Type'),
                'path': path or (result['Target'] if result.get('Type') != 'debian' else None),
                'path_note': 'OS package; binary paths require dpkg/ELF evidence' if result.get('Type') == 'debian' else None,
                'purl': purl, 'sbom_refs': sorted(c['bom-ref'] for c in matches),
                'sbom_paths': sorted(set(p for c in matches for p in properties(c, 'FilePath'))),
                'layer': v.get('Layer', {}).get('DiffID'),
                'source': v.get('DataSource'), 'advisory': v.get('PrimaryURL'),
            })
    counts = Counter(f['severity'] for f in findings)
    blocking = [f for f in findings if f['severity'] in ('HIGH', 'CRITICAL') or f['cve'] == PRIORITY]
    return {
        'candidate': candidate,
        'interpretation': 'Unmodified scanner findings, not exploitability claims or exceptions. Custom packages may remain unfixed in vendor database; gates remain closed.',
        'sbom_components': len(components), 'counts': dict(sorted(counts.items())),
        'unique_cves': len(set(f['cve'] for f in findings)),
        'blocking_package_cve_pairs': len(blocking),
        'blocking_without_vendor_fixed_version': sum(not f['fixed_version'] for f in blocking),
        'priority_findings': [f for f in findings if f['cve'] == PRIORITY],
        'findings': findings,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('candidate'); p.add_argument('scan'); p.add_argument('sbom'); p.add_argument('output')
    a = p.parse_args()
    output = audit(*(json.loads(Path(path).read_text()) for path in (a.candidate, a.scan, a.sbom)))
    output['evidence_sha256'] = {Path(path).name: digest_file(path) for path in (a.candidate, a.scan, a.sbom)}
    Path(a.output).write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({k: output[k] for k in ('counts', 'blocking_package_cve_pairs', 'blocking_without_vendor_fixed_version', 'sbom_components')}))


if __name__ == '__main__':
    main()
