#!/usr/bin/env python3
"""Validate this repository's Pterodactyl image map and optionally audit an Egg export."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "egg" / "docker_images.json"
OWNER = "akaanakbaik"
REPO = "img-nodejs"
MAJORS = range(18, 27)
PANEL_BUILTINS = {
    "SERVER_MEMORY", "SERVER_IP", "SERVER_PORT", "SERVER_UUID", "SERVER_NAME",
    "SERVER_USER", "SERVER_LOCATION", "STARTUP", "TZ",
}
SHELL_BUILTINS = {
    "HOME", "PATH", "PWD", "SHELL", "USER", "TERM", "LANG", "LC_ALL",
    "HOSTNAME", "TMPDIR", "IFS", "UID", "EUID", "BASH_VERSION",
    "SERVER_MEMORY", "SERVER_IP", "SERVER_PORT", "SERVER_UUID", "SERVER_NAME",
    "SERVER_USER", "SERVER_LOCATION", "SERVER_EGG", "PTERODACTYL_CONTAINER",
}
SENSITIVE_NAME = re.compile(r"(?:TOKEN|PASSWORD|SECRET|PRIVATE_KEY|API_KEY)", re.I)
CREDENTIAL_IN_URL = re.compile(
    r"\$\{?([A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET)[A-Z0-9_]*)\}?@", re.I
)
PLACEHOLDER = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")
SHELL_VARIABLE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")
ASSIGNMENT = re.compile(r"(?m)^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)=")


def expected_mapping() -> dict[str, str]:
    return {
        f"Node.js {major}": f"ghcr.io/{OWNER}/{REPO}:nodejs_{major}"
        for major in MAJORS
    }


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"tidak dapat membaca JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"akar JSON harus berupa objek: {path}")
    return value


def bash_syntax(script: str) -> tuple[bool, str]:
    result = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
    return result.returncode == 0, result.stderr.strip()


def validate_mapping(path: Path) -> tuple[bool, dict[str, str]]:
    try:
        data = read_json(path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return False, {}

    expected = expected_mapping()
    ok = True
    if data != expected:
        missing = sorted(set(expected) - set(data))
        extra = sorted(set(data) - set(expected))
        wrong = sorted(k for k in set(data) & set(expected) if data[k] != expected[k])
        if missing:
            print("ERROR: pilihan Egg yang hilang: " + ", ".join(missing))
            ok = False
        if extra:
            print("ERROR: pilihan Egg tak dikenal: " + ", ".join(extra))
            ok = False
        for key in wrong:
            print(f"ERROR: {key} harus menunjuk ke {expected[key]}")
            ok = False
    if ok:
        print(f"PASS: peta JSON valid; {len(expected)} label Node.js 18–26 menunjuk ke GHCR yang benar.")
    return ok, data


def audit_egg(path: Path, expected: dict[str, str]) -> bool:
    try:
        egg = read_json(path)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return False

    ok = True
    if egg.get("meta", {}).get("version") != "PTDL_v2":
        print("ERROR: meta.version bukan PTDL_v2.")
        ok = False
    images = egg.get("docker_images")
    if not isinstance(images, dict):
        print("ERROR: docker_images harus berupa objek.")
        ok = False
    elif images != expected:
        print("ERROR: docker_images Egg belum sama dengan snippet repo; ganti field itu saja, bukan seluruh Egg.")
        ok = False

    variables = egg.get("variables", [])
    if not isinstance(variables, list):
        variables = []
    declared = {
        item.get("env_variable")
        for item in variables
        if isinstance(item, dict) and isinstance(item.get("env_variable"), str)
    }
    defaults = {
        item.get("env_variable"): str(item.get("default_value", ""))
        for item in variables
        if isinstance(item, dict) and isinstance(item.get("env_variable"), str)
    }

    startup = egg.get("startup", "")
    if not isinstance(startup, str):
        print("ERROR: startup harus berupa string.")
        ok = False
        startup = ""
    refs = set(PLACEHOLDER.findall(startup))
    missing = sorted(ref for ref in refs if ref not in declared and ref not in PANEL_BUILTINS)
    if missing:
        print("ERROR: placeholder startup belum dideklarasikan: " + ", ".join(missing))
        ok = False

    rendered = startup
    for name in refs:
        replacement = defaults.get(name, "0" if name == "AUTO_UPDATE" else "")
        rendered = rendered.replace("{{" + name + "}}", replacement)
    if rendered.strip():
        passed, detail = bash_syntax(rendered)
        if not passed:
            print("ERROR: sintaks startup gagal bash -n setelah substitusi placeholder: " + detail)
            ok = False
        else:
            print("PASS: sintaks startup lolos bash -n setelah substitusi placeholder.")

    installation = egg.get("scripts", {}).get("installation", {})
    if not isinstance(installation, dict):
        installation = {}
    install_script = installation.get("script", "")
    if not isinstance(install_script, str):
        install_script = ""

    shell_refs = set(SHELL_VARIABLE.findall(startup + "\n" + install_script))
    local_names = set(ASSIGNMENT.findall(startup + "\n" + install_script))
    missing_shell_vars = sorted(shell_refs - declared - SHELL_BUILTINS - local_names)
    if missing_shell_vars:
        print("ERROR: environment Egg yang dirujuk tetapi belum dideklarasikan: " + ", ".join(missing_shell_vars))
        ok = False

    for var in variables:
        if not isinstance(var, dict):
            continue
        name = var.get("env_variable", "")
        if SENSITIVE_NAME.search(name) and var.get("user_viewable") is True:
            print(f"ERROR: variable sensitif {name} masih user_viewable=true.")
            ok = False
    leaked_name = CREDENTIAL_IN_URL.search(install_script)
    if leaked_name:
        print(f"ERROR: skrip installer menyisipkan {leaked_name.group(1)} ke URL; token berisiko tersimpan di remote/log.")
        ok = False

    normalized_script = install_script.replace("\r\n", "\n").replace("\r", "\n")
    if normalized_script != install_script:
        print("WARNING: skrip installer berisi CRLF; normalisasi ke LF atau pastikan importer Panel melakukannya.")
    if normalized_script.strip():
        passed, detail = bash_syntax(normalized_script)
        if not passed:
            print("ERROR: sintaks installer gagal bash -n setelah normalisasi line ending: " + detail)
            ok = False
        else:
            print("PASS: sintaks installer lolos bash -n setelah normalisasi line ending.")

    container = installation.get("container", "")
    base_match = re.search(r"(?:^|/)node:(\d+)", container)
    if base_match and int(base_match.group(1)) not in set(MAJORS):
        print(
            f"WARNING: installer memakai Node {base_match.group(1)}, sedangkan runtime Egg mencakup 18–26; "
            "native module dapat berbeda ABI. Gunakan installer per-major atau bangun native dependency pada runtime yang cocok."
        )

    if ok:
        print("PASS: struktur Egg dan pemeriksaan keamanan dasar lolos.")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=MAP_PATH, help="file snippet docker_images.json")
    parser.add_argument("--egg", type=Path, help="opsional: ekspor Egg PTDL_v2 untuk diaudit")
    args = parser.parse_args()

    ok, _ = validate_mapping(args.map)
    if args.egg:
        ok = audit_egg(args.egg, expected_mapping()) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
