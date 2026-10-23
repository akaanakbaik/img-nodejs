#!/usr/bin/env python3
"""Fail-closed verification of an exported release evidence bundle."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from audit_scan import audit
from verify_oci_layout import verify_oci_layout

PRIORITY_CVE = "CVE-2026-111497"
SEVERITIES = {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}
REPO_CATEGORIES = ("Vulnerabilities", "Misconfigurations", "Secrets")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _list_or_empty(value: Any, label: str) -> list[Any]:
    if value is None or value is _MISSING:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list or null")
    return value


class _Missing:
    pass


_MISSING = _Missing()


def _validate_results(report: dict[str, Any], label: str, *, require_image_vulnerability_id: bool = False) -> list[dict[str, Any]]:
    results = report.get("Results", _MISSING)
    if not isinstance(results, list):
        raise ValueError(f"{label} Results must be a list")
    if any(not isinstance(result, dict) for result in results):
        raise ValueError(f"{label} contains an invalid result")
    findings: list[dict[str, Any]] = []
    for index, result in enumerate(results):
        for category in REPO_CATEGORIES:
            entries = _list_or_empty(result.get(category, _MISSING), f"{label} result {index} {category}")
            for finding in entries:
                if not isinstance(finding, dict):
                    raise ValueError(f"{label} result {index} {category} contains a non-object finding")
                severity = finding.get("Severity")
                if not isinstance(severity, str) or severity not in SEVERITIES:
                    raise ValueError(f"{label} result {index} {category} has invalid severity")
                if category == "Vulnerabilities":
                    cve = finding.get("VulnerabilityID")
                    if not isinstance(cve, str) or not cve:
                        raise ValueError(f"{label} vulnerability is missing VulnerabilityID")
                findings.append(finding)
    return findings


def _verify_gates(metadata: dict[str, Any], scan: dict[str, Any], sbom: dict[str, Any], repo: dict[str, Any], expected_arch: str) -> str:
    if expected_arch not in ("amd64", "arm64"):
        raise ValueError("expected architecture must be amd64 or arm64")
    if metadata.get("arch") != expected_arch:
        raise ValueError("metadata architecture does not match expected architecture")

    _validate_results(scan, "image scan", require_image_vulnerability_id=True)
    repo_findings = _validate_results(repo, "repository scan")
    try:
        audited = audit(metadata, scan, sbom)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"scan/SBOM audit failed: {exc}") from exc

    # The image scan is unfiltered: target CVE blocks at every severity, and
    # HIGH/CRITICAL findings remain a release blocker.
    for finding in audited["findings"]:
        if finding["cve"] == PRIORITY_CVE or finding["severity"] in ("HIGH", "CRITICAL"):
            raise ValueError("image vulnerability gate failed")
    for finding in repo_findings:
        if finding.get("VulnerabilityID") == PRIORITY_CVE or finding.get("Severity") in ("HIGH", "CRITICAL"):
            raise ValueError("repository vulnerability gate failed")
    return audited["candidate"]["manifest_digest"]


def verify_release_bundle(metadata: dict[str, Any], oci: Path, scan: dict[str, Any], sbom: dict[str, Any], repo: dict[str, Any], expected_arch: str) -> str:
    """Verify all bundle evidence and return the single runtime manifest digest."""
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    evidence = verify_oci_layout(metadata, oci)
    verified = evidence.get("verified")
    if not isinstance(verified, dict):
        raise ValueError("OCI verifier returned invalid evidence")
    runtime_digest = verified.get("runtime_manifest_digest")
    if not isinstance(runtime_digest, str) or metadata.get("manifest_digest") != runtime_digest:
        raise ValueError("metadata manifest_digest does not equal verified runtime manifest digest")
    if verified.get("architecture") != expected_arch or metadata.get("arch") != expected_arch:
        raise ValueError("verified architecture does not match expected architecture")
    _verify_gates(metadata, scan, sbom, repo, expected_arch)
    return runtime_digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--oci", type=Path, required=True)
    parser.add_argument("--scanner-report", type=Path, required=True)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--repo-report", type=Path, required=True)
    parser.add_argument("--expected-arch", choices=("amd64", "arm64"), required=True)
    args = parser.parse_args(argv)
    digest = verify_release_bundle(
        _load(args.metadata), args.oci, _load(args.scanner_report), _load(args.sbom), _load(args.repo_report), args.expected_arch
    )
    print(digest)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"release bundle verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
