#!/usr/bin/env python3
"""Resolve exact Node.js versions from nodejs.org/dist/index.json.

Examples:
  python3 scripts/resolve_versions.py --matrix
  python3 scripts/resolve_versions.py --check
  python3 scripts/resolve_versions.py --url file:///tmp/index.json --matrix
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from urllib.request import Request, urlopen

INDEX_URL = "https://nodejs.org/dist/index.json"
MANIFEST = Path(__file__).resolve().parents[1] / "versions.json"
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

def version_tuple(value: str):
    m = VERSION_RE.fullmatch(value)
    if not m: raise ValueError(f"invalid version: {value}")
    return tuple(map(int, m.groups()))

def load_manifest(path=MANIFEST):
    data = json.loads(Path(path).read_text())
    entries = data.get("versions")
    if not isinstance(entries, list): raise ValueError("manifest versions must be a list")
    result = {}
    for item in entries:
        major = int(item["major"]); version = str(item["version"])
        parsed = version_tuple(version)
        if parsed[0] != major: raise ValueError(f"manifest major/version mismatch: {major}/{version}")
        if major in result: raise ValueError(f"duplicate manifest major: {major}")
        result[major] = item
    return data, result

def read_index(url=INDEX_URL, timeout=15):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "node-version-resolver/1"})
    if url.startswith("file://"):
        from urllib.parse import urlparse, unquote
        return json.loads(Path(unquote(urlparse(url).path)).read_text())
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)

def latest_stable(index):
    latest = {}
    for item in index:
        version = str(item.get("version", ""))
        if "-" in version: continue
        try: parsed = version_tuple(version)
        except ValueError: continue
        major = parsed[0]
        if major not in latest or parsed > latest[major][0]: latest[major] = (parsed, version.lstrip("v"))
    return {major: value[1] for major, value in latest.items()}

def check_manifest(manifest_path=MANIFEST, index_url=INDEX_URL, include_eol=False):
    data, entries = load_manifest(manifest_path)
    latest = latest_stable(read_index(index_url))
    wanted = sorted(entries)
    missing = [m for m in wanted if m not in latest]
    if missing and not include_eol: raise RuntimeError("official index has no stable release for majors: " + ", ".join(map(str, missing)))
    stale = [(m, entries[m]["version"], latest[m]) for m in wanted if m in latest and entries[m]["version"] != latest[m]]
    if stale:
        raise RuntimeError("manifest is stale: " + "; ".join(f"{m}: {old} != official latest {new}" for m, old, new in stale))
    return True

def matrix(manifest_path=MANIFEST):
    _, entries = load_manifest(manifest_path)
    return [{"node": str(m), "version": entries[m]["version"], "supported": bool(entries[m].get("supported", False))} for m in sorted(entries)]

def main(argv=None):
    parser = argparse.ArgumentParser(description="Resolve exact stable Node.js versions from the official index.")
    parser.add_argument("--url", default=INDEX_URL, help="official index JSON URL (or file:// URL for offline tests)")
    parser.add_argument("--manifest", default=str(MANIFEST))
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--check", action="store_true", help="fail if manifest is not latest per major")
    parser.add_argument("--matrix", action="store_true", help="print JSON build matrix")
    parser.add_argument("--include-eol", action="store_true", help="allow majors absent from the current official index")
    args = parser.parse_args(argv)
    try:
        if args.check:
            check_manifest(args.manifest, args.url, args.include_eol)
            print("OK: manifest matches official latest stable versions")
        if args.matrix: print(json.dumps(matrix(args.manifest), separators=(",", ":")))
        if not args.check and not args.matrix: parser.error("choose --check or --matrix")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); return 1
    return 0

if __name__ == "__main__": sys.exit(main())
