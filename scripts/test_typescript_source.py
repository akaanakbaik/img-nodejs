#!/usr/bin/env python3
"""Validate the safe TypeScript source-rebuild contract without trusting binaries."""
import hashlib, json, os, pathlib, subprocess, sys, tempfile, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
META = json.loads((ROOT / "security/typescript-source.json").read_text())
REQUIRED = {"go": "1.26.10", "x_text": "v0.41.0"}

def fail(message):
    raise SystemExit(f"FAIL: {message}")

def test_metadata():
    rebuild = META.get("custom_rebuild") or fail("custom_rebuild metadata missing")
    if rebuild["source_commit"] != "2bd066d87f5bafd315be9f40889d0a60b9e58e0b":
        fail("source commit is not the authenticated TypeScript 7.0.2 tag commit")
    if rebuild["source_tar_sha256"] != "25cca8ec9d89e4ceec5181a677ded2c6d690fa18b81e1277846303973eb71fcf":
        fail("source tarball pin changed")
    if rebuild["go"] != REQUIRED["go"] or rebuild["x_text"] != REQUIRED["x_text"]:
        fail("required dependency floors are not recorded")
    if rebuild["compiler_sources_modified"] or rebuild["official_upstream_binary"]:
        fail("metadata permits opaque or source-modified artifact")
    if "typescript-go/archive/refs/tags/typescript/v7.0.2.tar.gz" not in rebuild["source_url"]:
        fail("source URL is not the stable upstream tag archive")

def test_builder_contract():
    text = (ROOT / "scripts/build_typescript.sh").read_text()
    for needle in ("sha256sum -c", "base64.b64encode(hashlib.sha512", "go mod edit", "go test -p 2 ./...", "go mod verify", "compiler_sources_modified", "official_upstream_binary", "dependency-diff.txt", "go-sources.after-tests"):
        if needle not in text:
            fail(f"builder lacks {needle}")
    if "go mod tidy" in text:
        fail("builder must not perform unreviewed dependency churn")
    for forbidden in ("ALLOW_UNVERIFIED_GO", "TYPESCRIPT_VERSION", "XTEXT_VERSION:-", "REQUIRE_GO_VERSION"):
        if forbidden in text:
            fail(f"builder permits forbidden override {forbidden}")
    if "GOOS=linux GOARCH=\"$arch\"" in text or "main_pkg=\"$(go list" in text:
        fail("builder permits cross compilation or guessed main package")

def test_output(out):
    packages = list(out.glob("typescript-linux-*/package.json"))
    if not packages:
        fail("no rebuilt package found; set TYPESCRIPT_REBUILD_OUTPUT for integration test")
    for package in packages:
        data = json.loads(package.read_text())
        prov = json.loads((package.parent / "BUILD-PROVENANCE.json").read_text())
        if data["x-image-build"]["official_upstream_binary"] or prov["official_upstream_binary"]:
            fail("rebuilt package falsely claims upstream provenance")
        if data.get("version") != "7.0.2" or data.get("os") != ["linux"]:
            fail("platform metadata was not preserved")
        if data.get("cpu") not in (["x64"], ["arm64"]):
            fail("platform cpu metadata was not preserved")
        binary = package.parent / "lib/tsc"
        if not binary.is_file() or not os.access(binary, os.X_OK):
            fail(f"missing executable {binary}")
        result = subprocess.run([str(binary), "--version"], text=True, capture_output=True)
        if result.returncode != 0 or result.stdout.strip() != "Version 7.0.2":
            fail(f"compiler regression/version check failed: {result.stdout}{result.stderr}")
        if (package.parent / "lib/tsc.sig").exists():
            fail("stale upstream signature shipped beside replaced binary")
        if not (package.parent / "go-build-info.txt").is_file():
            fail("Go build information missing")
        info = (package.parent / 'go-build-info.txt').read_text()
        if 'go1.26.10' not in info or 'golang.org/x/text\tv0.41.0\t' not in info:
            fail('embedded Go/x-text differs from reviewed versions')
        if prov.get('go_version') != REQUIRED['go'] or prov.get('x_text') != REQUIRED['x_text']:
            fail('output provenance toolchain mismatch')
        expected = json.loads((package.parent / "BUILD-PROVENANCE.json").read_text())["source_tar_sha256"]
        if expected != META["custom_rebuild"]["source_tar_sha256"]:
            fail("output provenance source hash differs from reviewed pin")

def main():
    test_metadata(); test_builder_contract()
    output = os.environ.get("TYPESCRIPT_REBUILD_OUTPUT")
    if output:
        out = pathlib.Path(output)
        test_output(out)
    print("PASS: TypeScript stable-source provenance, dependency floors, and builder contract")

if __name__ == "__main__":
    main()
