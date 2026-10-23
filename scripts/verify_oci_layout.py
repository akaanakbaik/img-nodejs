#!/usr/bin/env python3
"""Verify a Buildx OCI archive contains exactly the tested runtime image."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
from pathlib import Path
from typing import Any, BinaryIO

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ARCH_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
INDEX_MT = {"application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json"}
MANIFEST_MT = {"application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"}
CONFIG_MT = {"application/vnd.oci.image.config.v1+json", "application/vnd.docker.container.image.v1+json"}
LAYER_MT = {"application/vnd.oci.image.layer.v1.tar", "application/vnd.oci.image.layer.v1.tar+gzip", "application/vnd.oci.image.layer.nondistributable.v1.tar", "application/vnd.oci.image.layer.nondistributable.v1.tar+gzip", "application/vnd.docker.image.rootfs.diff.tar", "application/vnd.docker.image.rootfs.diff.tar.gzip"}
ATTEST_LAYER_MT = {"application/vnd.in-toto+json", "application/vnd.in-toto+json+gzip", "application/vnd.dsse.envelope.v1+json"}
MAX_JSON = 16 * 1024 * 1024


def _digest(value: str, label: str = "digest") -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise ValueError(f"invalid {label}")
    return value


def _json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _descriptor(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} is not a descriptor")
    _digest(value.get("digest"), f"{label} digest")
    if not isinstance(value.get("mediaType"), str) or not value["mediaType"]:
        raise ValueError(f"{label} has no mediaType")
    size = value.get("size")
    if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 0):
        raise ValueError(f"{label} has invalid size")
    return value


def _safe_name(name: str) -> bool:
    # A trailing slash is the only empty component permitted (directory member).
    if not name or name.startswith("/") or "\\" in name:
        return False
    parts = name.split("/")
    if name.endswith("/"):
        parts.pop()
    return bool(parts) and all(part not in ("", ".", "..") for part in parts)


def _read_small(archive: tarfile.TarFile, member: tarfile.TarInfo, label: str) -> bytes:
    if member.size > MAX_JSON:
        raise ValueError(f"{label} exceeds {MAX_JSON} bytes")
    stream = archive.extractfile(member)
    if stream is None:
        raise ValueError(f"cannot read archive member: {member.name}")
    data = stream.read(MAX_JSON + 1)
    if len(data) > MAX_JSON:
        raise ValueError(f"{label} exceeds {MAX_JSON} bytes")
    return data


def _read_archive(path: Path) -> tuple[dict[str, tarfile.TarInfo], bytes, bytes]:
    members: dict[str, tarfile.TarInfo] = {}
    archive_hash = hashlib.sha256()
    try:
        with tarfile.open(path, mode="r:*") as archive:
            for member in archive:
                name = member.name
                if not _safe_name(name):
                    raise ValueError(f"unsafe archive path: {name!r}")
                if name in members:
                    raise ValueError(f"duplicate archive member: {name}")
                if member.isdir():
                    continue
                if not member.isfile():
                    raise ValueError(f"archive member is not a regular file: {name}")
                members[name] = member
            if "oci-layout" not in members or "index.json" not in members:
                raise ValueError("OCI archive must contain oci-layout and index.json")
            layout = _json_bytes(_read_small(archive, members["oci-layout"], "oci-layout"), "oci-layout")
            if layout.get("imageLayoutVersion") != "1.0.0":
                raise ValueError("unsupported OCI layout version")
            index_bytes = _read_small(archive, members["index.json"], "index.json")
        with path.open("rb") as raw:
            for chunk in iter(lambda: raw.read(1024 * 1024), b""):
                archive_hash.update(chunk)
    except (tarfile.TarError, OSError) as exc:
        raise ValueError(f"cannot read OCI archive: {exc}") from exc
    return members, index_bytes, archive_hash.digest()


def verify_oci_layout(metadata: dict[str, Any], archive: Path) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    manifest_digest = _digest(metadata.get("manifest_digest"), "candidate manifest_digest")
    image_id = _digest(metadata.get("image_id"), "candidate image_id")
    arch = metadata.get("arch")
    if not isinstance(arch, str) or not ARCH_RE.fullmatch(arch):
        raise ValueError("candidate arch is invalid")
    members, index_bytes, archive_sha256 = _read_archive(archive)
    root_index = _json_bytes(index_bytes, "index.json")
    if root_index.get("schemaVersion") != 2 or not isinstance(root_index.get("manifests"), list) or not root_index["manifests"]:
        raise ValueError("index.json must contain schemaVersion 2 and manifests")
    roots: dict[str, dict[str, Any]] = {}
    for i, value in enumerate(root_index["manifests"]):
        d = _descriptor(value, f"index manifest {i}")
        if d["digest"] in roots:
            raise ValueError("duplicate root descriptor")
        roots[d["digest"]] = d
    index_file_digest = "sha256:" + hashlib.sha256(index_bytes).hexdigest()
    if manifest_digest == index_file_digest:
        root_digests = list(roots)
    elif manifest_digest in roots:
        root_digests = [manifest_digest]
    else:
        raise ValueError("candidate manifest_digest is neither a root descriptor nor index.json digest")

    blob_members: dict[str, tarfile.TarInfo] = {}
    for name, member in members.items():
        if name.startswith("blobs/"):
            bits = name.split("/")
            if len(bits) != 3 or bits[1] != "sha256" or not re.fullmatch(r"[0-9a-f]{64}", bits[2]):
                raise ValueError(f"invalid OCI blob path: {name}")
            blob_members["sha256:" + bits[2]] = member

    checked: dict[str, int] = {}
    parsed: dict[str, dict[str, Any]] = {}
    visiting: set[str] = set()
    traversed: set[str] = set()
    runtime: list[dict[str, str]] = []
    attest_bindings: list[str] = []

    def check_blob(desc: dict[str, Any], label: str, want_json: bool = False) -> Any:
        d = _descriptor(desc, label)
        digest = d["digest"]
        member = blob_members.get(digest)
        if member is None:
            raise ValueError(f"missing blob for {label}: {digest}")
        if digest not in checked:
            h = hashlib.sha256(); total = 0
            stream = None
            try:
                with tarfile.open(archive, mode="r:*") as ar:
                    stream = ar.extractfile(member)
                    if stream is None:
                        raise ValueError(f"cannot read archive member: {member.name}")
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        total += len(chunk); h.update(chunk)
            except (tarfile.TarError, OSError) as exc:
                raise ValueError(f"cannot read blob {digest}: {exc}") from exc
            if "size" in d and d["size"] != total:
                raise ValueError(f"size mismatch for {label}: {digest}")
            if "sha256:" + h.hexdigest() != digest:
                raise ValueError(f"digest mismatch for {label}: {digest}")
            checked[digest] = total
        elif "size" in d and d["size"] != checked[digest]:
            raise ValueError(f"size mismatch for {label}: {digest}")
        if want_json:
            if member.size > MAX_JSON:
                raise ValueError(f"{label} exceeds {MAX_JSON} bytes")
            with tarfile.open(archive, mode="r:*") as ar:
                return _json_bytes(_read_small(ar, member, label), label)
        return None

    def walk(desc: dict[str, Any], label: str, bound_attest: bool = False) -> None:
        d = _descriptor(desc, label); digest = d["digest"]
        if digest in visiting:
            raise ValueError("descriptor graph contains a cycle")
        if digest in parsed:
            return
        visiting.add(digest)
        try:
            obj = check_blob(d, label, want_json=True)
            traversed.add(digest)
            media = d["mediaType"]
            if media in INDEX_MT:
                children = obj.get("manifests")
                if not isinstance(children, list) or not children:
                    raise ValueError(f"{label} index has no manifests")
                for i, child in enumerate(children):
                    walk(_descriptor(child, f"{label} child {i}"), f"{label} child {i}", False)
            elif media in MANIFEST_MT:
                config = _descriptor(obj.get("config"), f"{label} config")
                cfg = check_blob(config, f"{label} config", want_json=config["mediaType"] in CONFIG_MT)
                traversed.add(config["digest"])
                layers = obj.get("layers")
                if not isinstance(layers, list):
                    raise ValueError(f"{label} has invalid layers")
                for i, layer in enumerate(layers):
                    ld = _descriptor(layer, f"{label} layer {i}")
                    if ld["mediaType"] not in LAYER_MT and ld["mediaType"] not in ATTEST_LAYER_MT:
                        raise ValueError(f"unsupported layer media type: {ld['mediaType']}")
                    check_blob(ld, f"{label} layer {i}")
                    traversed.add(ld["digest"])
                if config["mediaType"] in CONFIG_MT:
                    if not isinstance(cfg, dict):
                        raise ValueError(f"{label} config is invalid")
                    architecture, operating_system = cfg.get("architecture"), cfg.get("os")
                    if bound_attest:
                        if architecture != "unknown" or operating_system != "unknown":
                            raise ValueError(f"attestation config is not unknown/unknown: {label}")
                    else:
                        if not isinstance(architecture, str) or not ARCH_RE.fullmatch(architecture) or operating_system != "linux":
                            raise ValueError(f"runtime config has invalid architecture or os: {label}")
                        runtime.append({"manifest_digest": digest, "config_digest": config["digest"], "architecture": architecture, "os": operating_system})
                elif bound_attest and config["mediaType"] in {"application/vnd.in-toto+json", "application/vnd.in-toto+json+gzip"}:
                    pass
                else:
                    raise ValueError(f"unsupported config media type: {config['mediaType']}")
            else:
                raise ValueError(f"unsupported descriptor media type: {media}")
            parsed[digest] = obj
        finally:
            visiting.remove(digest)

    # Validate every archived blob, including unreferenced blobs, rather than silently accepting garbage.
    for digest, member in blob_members.items():
        check_blob({"digest": digest, "mediaType": "application/octet-stream", "size": member.size}, f"archive blob {digest}")
    for digest in root_digests:
        root = roots[digest]
        ann = root.get("annotations") if isinstance(root.get("annotations"), dict) else {}
        is_attest = ann.get("vnd.docker.reference.type") == "attestation-manifest"
        platform = root.get("platform")
        if is_attest:
            if not isinstance(platform, dict) or platform.get("os") != "unknown" or platform.get("architecture") != "unknown":
                raise ValueError("attestation root must have unknown/unknown platform")
            attest_bindings.append(_digest(ann.get("vnd.docker.reference.digest"), "attestation reference digest"))
        elif isinstance(platform, dict) and (platform.get("os") == "unknown" or platform.get("architecture") == "unknown"):
            raise ValueError("unknown platform root is not an attestation")
        walk(root, f"root {digest}", is_attest)
    if len(runtime) != 1:
        raise ValueError(f"expected exactly one runtime image, found {len(runtime)}")
    found = runtime[0]
    for binding in attest_bindings:
        if binding != found["manifest_digest"]:
            raise ValueError("attestation is not bound to the verified runtime manifest")
    if found["config_digest"] != image_id or found["architecture"] != arch:
        raise ValueError("OCI runtime config does not match candidate image_id and arch")
    return {"candidate": {"manifest_digest": manifest_digest, "image_id": image_id, "arch": arch}, "verified": {"runtime_manifest_digest": found["manifest_digest"], "config_digest": found["config_digest"], "architecture": found["architecture"], "os": found["os"], "traversed_digests": sorted(traversed)}, "archive": {"path": str(archive), "sha256": archive_sha256.hex()}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--metadata", type=Path, required=True); parser.add_argument("--oci", type=Path, required=True)
    args = parser.parse_args(); print(json.dumps(verify_oci_layout(json.loads(args.metadata.read_text(encoding="utf-8")), args.oci), sort_keys=True)); return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, tarfile.TarError) as exc:
        print(f"OCI candidate verification failed: {exc}", file=sys.stderr); raise SystemExit(1)
