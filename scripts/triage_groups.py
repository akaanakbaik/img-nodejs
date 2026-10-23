#!/usr/bin/env python3
"""Fail-closed grouping of Debian HIGH/CRITICAL findings with package evidence."""
from __future__ import annotations
import argparse, hashlib, json, re
from collections import Counter
from pathlib import Path

ARCH_RE = re.compile(r"^(?P<name>[^:]+):(?P<arch>amd64|arm64|all)$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

def load(path):
    return json.loads(Path(path).read_text()) if path else {}

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def normalize_package(name):
    """Return Debian binary name without dpkg's :arch suffix."""
    if not isinstance(name, str) or not name:
        return name
    m = ARCH_RE.match(name)
    return m.group("name") if m else name

def _validate_inventory(apt):
    """Accept vendor_package_inventory JSON and return normalized package map."""
    if not apt:
        return {}, None
    if isinstance(apt, dict) and isinstance(apt.get("packages"), list):
        rows = apt["packages"]
        out = {}
        for row in rows:
            if not isinstance(row, dict) or not row.get("package"):
                raise ValueError("invalid vendor inventory package record")
            key = normalize_package(row["package"])
            if key in out and out[key].get("arch") != row.get("arch"):
                raise ValueError("ambiguous multiarch vendor inventory: " + key)
            out[key] = row
        return out, apt.get("candidate")
    if isinstance(apt, dict):
        return {normalize_package(k): dict(v, package=k) for k, v in apt.items() if isinstance(v, dict)}, None
    raise ValueError("invalid apt evidence schema")

def source_map(apt):
    rows, _ = _validate_inventory(apt)
    return {k: (v.get("source_package") or v.get("source") or v.get("sourcePackage"))
            for k, v in rows.items()}

def scan_source_map(scan):
    """Map binary package -> actual SrcName/SrcVersion from raw Trivy Packages[]."""
    if not scan:
        return {}, None
    if not isinstance(scan, dict) or not isinstance(scan.get("Results"), list):
        raise ValueError("invalid raw scan: missing Results")
    out = {}
    image_id = scan.get("Metadata", {}).get("ImageID")
    for result in scan["Results"]:
        for row in result.get("Packages", []) if isinstance(result, dict) else []:
            name = row.get("Name")
            if not name or row.get("SrcName") is None:
                continue
            key = normalize_package(name)
            value = {"source_package": row.get("SrcName"), "source_version": row.get("SrcVersion"), "scan_package": name}
            old = out.get(key)
            if old and (old["source_package"], old.get("source_version")) != (value["source_package"], value.get("source_version")):
                raise ValueError("conflicting raw scan source metadata: " + key)
            out[key] = value
    return out, image_id

def _validate_sbom(audit, sbom):
    if not sbom:
        return
    if sbom.get("bomFormat") != "CycloneDX" or not isinstance(sbom.get("components"), list):
        raise ValueError("invalid CycloneDX SBOM")
    expected_image = audit.get("candidate", {}).get("image_id") if isinstance(audit.get("candidate"), dict) else None
    observed_image = sbom.get("metadata", {}).get("component", {}).get("properties", [])
    observed_ids = {p.get("value") for p in observed_image if p.get("name") == "aquasecurity:trivy:ImageID"}
    if expected_image and observed_ids != {expected_image}:
        raise ValueError("SBOM does not match audit candidate image")
    refs = set()
    for c in sbom["components"]:
        if isinstance(c, dict):
            refs.update(x for x in (c.get("bom-ref"), c.get("purl")) if x)
    for f in audit.get("findings", []):
        if f.get("type") == "debian" and f.get("severity") in {"HIGH", "CRITICAL"}:
            given = f.get("sbom_refs", [])
            if not given or not all(x in refs for x in given):
                raise ValueError("audit finding has no matching SBOM component: " + str(f.get("package")))

def group(audit, paths=None, sbom=None, apt=None, candidate=None, scan=None, evidence_sha256=None):
    if not isinstance(audit, dict) or not isinstance(audit.get("findings"), list):
        raise ValueError("invalid audit evidence")
    _validate_sbom(audit, sbom or {})
    inv, inv_candidate = _validate_inventory(apt or {})
    smap = source_map(apt or {})
    scanmap, scan_image = scan_source_map(scan or {})
    if scan and not scanmap:
        raise ValueError("raw scan contains no Debian package source metadata")
    expected = audit.get('candidate', {})
    if isinstance(expected, dict) and expected.get('image_id'):
        if scan and scan_image != expected['image_id']:
            raise ValueError('raw scan candidate mismatch')
        if apt and (not isinstance(inv_candidate, dict) or any(inv_candidate.get(k) != expected.get(k) for k in ('image_id', 'manifest_digest', 'arch'))):
            raise ValueError('vendor inventory candidate mismatch')
    pmap = {}
    for p in (paths or {}).get("packages", []):
        if not isinstance(p, dict) or not p.get("package"):
            raise ValueError("invalid package paths record")
        key = normalize_package(p["package"])
        if key in pmap:
            raise ValueError("duplicate normalized package path record: " + key)
        pmap[key] = p
    findings = [f for f in audit["findings"] if f.get("type") == "debian" and f.get("severity") in {"HIGH", "CRITICAL"}]
    groups = []
    for f in findings:
        pkg = f.get("package"); key = normalize_package(pkg); pe = pmap.get(key, {})
        if paths and not pe:
            raise ValueError('missing dpkg paths package: ' + str(pkg))
        if pe and pe.get("version") != f.get("installed"):
            raise ValueError("audit/path version mismatch for " + str(pkg))
        if isinstance(expected, dict) and expected.get('arch') and pe and pe.get('architecture') not in (expected['arch'], 'all'):
            raise ValueError('audit/path architecture mismatch for ' + str(pkg))
        if scan and key not in scanmap:
            raise ValueError("audit package absent from raw scan: " + str(pkg))
        source = (scanmap.get(key, {}).get("source_package") if scan else None) or smap.get(key) or key
        available = None; av = inv.get(key)
        if apt and not av:
            raise ValueError('missing vendor inventory package: ' + str(pkg))
        if av:
            if av.get('installed') != f.get('installed'):
                raise ValueError('vendor inventory version mismatch for ' + str(pkg))
            if av.get('source_package') and av['source_package'] != source:
                raise ValueError('vendor/source mapping mismatch for ' + str(pkg))
            available = av.get("available_version") or av.get("candidate")
        fixed = f.get("fixed_version")
        groups.append({"source_package": source, "source_version": (scanmap.get(key, {}).get("source_version") if scan else None) or (av or {}).get("source_version"),
            "binary_package": pkg, "cve": f.get("cve"), "severity": f.get("severity"), "installed_version": f.get("installed"), "fixed_version": fixed, "status": f.get("status"),
            "fixed_availability": "scanner_fixed_version" if fixed else ("apt_candidate" if available else "not_evidenced"),
            "apt_available_version": available, "path_inventory_ref": key if pe else None, "path_count": sum(bool(x.get('path')) for x in pe.get('files', [])),
            "sbom_refs": f.get("sbom_refs", []), "sbom_paths": f.get("sbom_paths", []), "purl": f.get("purl"), "layer": f.get("layer"), "advisory": f.get("advisory"),
            "evidence": {"path_package": pe.get("package"), "path_package_version": pe.get("version"), "path_architecture": pe.get("architecture"), "sbom_present": bool(sbom), "source_from_scan": bool(scan and key in scanmap)}})
    groups.sort(key=lambda x: (x["source_package"], x["binary_package"], x["cve"] or ""))
    inv_count = len(inv)
    return {"schema":"debian-triage/v3", "candidate":audit.get("candidate"), "candidate_name":candidate, "scope":"every Debian HIGH/CRITICAL finding; one record per package/CVE pair; path_inventory_ref resolves to path_inventory including file/ELF hashes", "path_inventory":pmap, "counts":{
        "records":len(groups), "unique_pairs":len({(x['binary_package'],x['cve']) for x in groups}), "critical":sum(x['severity']=='CRITICAL' for x in groups), "high":sum(x['severity']=='HIGH' for x in groups), "fixed_version":sum(bool(x['fixed_version']) for x in groups), "status":dict(Counter(x.get('status') for x in groups)), "packages":len({normalize_package(x['binary_package']) for x in groups}), "inventory_packages":inv_count, "path_inventory_packages":len(pmap), "path_mapped_packages":len({normalize_package(x['binary_package']) for x in groups if x['path_count']}), "apt_candidate_is_not_fix_proof":True},
        "groups":groups, "source":{"audit":audit.get("evidence_sha256", {}), "interpretation":audit.get("interpretation"), "evidence_sha256":evidence_sha256 or {}, "candidate_metadata":inv_candidate, "raw_scan_image_id":scan_image}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--audit',required=True); ap.add_argument('--paths'); ap.add_argument('--sbom'); ap.add_argument('--apt-evidence'); ap.add_argument('--scan'); ap.add_argument('--candidate'); ap.add_argument('--output',required=True); args=ap.parse_args()
    files=[x for x in (args.audit,args.paths,args.sbom,args.apt_evidence,args.scan) if x]
    data={x:load(x) for x in files}
    audit=data[args.audit]; sbom=data.get(args.sbom,{}); paths=data.get(args.paths,{}); apt=data.get(args.apt_evidence,{}); scan=data.get(args.scan,{})
    cand=audit.get('candidate',{})
    if isinstance(cand,dict) and (not DIGEST_RE.fullmatch(cand.get('image_id','')) or not DIGEST_RE.fullmatch(cand.get('manifest_digest',''))): raise ValueError('invalid audit candidate metadata')
    if scan and scan.get('Metadata',{}).get('ImageID') != cand.get('image_id'): raise ValueError('raw scan does not match audit candidate image')
    out=group(audit,paths,sbom,apt,args.candidate,scan,{Path(x).name:sha256_file(x) for x in files})
    Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps(out['counts'],sort_keys=True))
if __name__=='__main__': main()
