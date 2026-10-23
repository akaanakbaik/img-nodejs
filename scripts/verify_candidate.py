#!/usr/bin/env python3
"""Fail-closed checks for the image candidate handed between workflow jobs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ARCH_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def inspect_image(image: str) -> dict[str, str]:
    result = subprocess.run(["docker", "inspect", "--format", "{{json .}}", image], check=True, text=True, capture_output=True)
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("docker inspect returned no image object")
    image_id, architecture = value.get("Id"), value.get("Architecture")
    if not isinstance(image_id, str) or not isinstance(architecture, str):
        raise ValueError("docker inspect omitted Id or Architecture")
    return {"image_id": image_id, "architecture": architecture}


def verify_candidate(metadata: dict[str, Any], scanner: dict[str, Any], inspected: dict[str, str], expected_arch: str | None = None) -> None:
    """Validate candidate metadata, scanner identity, and the loaded image identity."""
    for key in ("manifest_digest", "image_id", "arch"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f"candidate metadata {key} is empty")
    if not ID_RE.fullmatch(metadata["image_id"]):
        raise ValueError("candidate image_id is not a sha256 image ID")
    if not ID_RE.fullmatch(metadata["manifest_digest"]):
        raise ValueError("candidate manifest_digest is not a sha256 digest")
    if not isinstance(inspected.get("image_id"), str) or not ID_RE.fullmatch(inspected["image_id"]):
        raise ValueError("docker inspect returned an invalid image ID")
    if metadata["image_id"] != inspected["image_id"]:
        raise ValueError("candidate image_id does not match loaded image ID")
    architecture = inspected.get("architecture")
    if not isinstance(architecture, str) or not ARCH_RE.fullmatch(architecture):
        raise ValueError("docker inspect returned an invalid architecture")
    if metadata["arch"] != architecture or (expected_arch and expected_arch != architecture):
        raise ValueError("candidate architecture does not match loaded image architecture")
    scan_metadata = scanner.get("Metadata")
    if not isinstance(scan_metadata, dict) or not isinstance(scan_metadata.get("ImageID"), str) or not scan_metadata["ImageID"].strip():
        raise ValueError("scanner Metadata.ImageID is empty or missing")
    if scan_metadata["ImageID"] != inspected["image_id"]:
        raise ValueError("scanner Metadata.ImageID does not match loaded image ID")


def verify_sha256(artifact: Path, checksum_file: Path) -> str:
    """Verify a sha256sum-compatible record, rejecting malformed or extra records."""
    lines = [line.strip() for line in checksum_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("checksum file must contain exactly one record")
    parts = lines[0].split(maxsplit=1)
    if len(parts) != 2 or not re.fullmatch(r"[0-9a-f]{64}", parts[0]):
        raise ValueError("invalid SHA256 record")
    expected, name = parts
    if Path(name.lstrip("* ")).name != artifact.name:
        raise ValueError("checksum filename does not match artifact")
    with artifact.open("rb") as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    actual = h.hexdigest()
    if actual != expected:
        raise ValueError("artifact SHA256 mismatch")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--scanner-report", type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-arch")
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--sha256", dest="checksum", type=Path)
    args = parser.parse_args()
    if (args.artifact is None) != (args.checksum is None):
        parser.error("--artifact and --sha256 must be supplied together")
    inspected = inspect_image(args.image)
    scanner = _json(args.scanner_report) if args.scanner_report else {"Metadata": {"ImageID": inspected["image_id"]}}
    verify_candidate(_json(args.metadata), scanner, inspected, args.expected_arch)
    if args.artifact:
        verify_sha256(args.artifact, args.checksum)
    print(f"candidate verified: {inspected['image_id']} ({inspected['architecture']})")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"candidate verification failed: {exc}", flush=True)
        raise SystemExit(1)
