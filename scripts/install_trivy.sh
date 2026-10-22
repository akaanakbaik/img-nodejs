#!/usr/bin/env bash
set -euo pipefail

# Install a pinned Trivy release and verify its publisher-provided checksum.
TRIVY_VERSION="${TRIVY_VERSION:-0.76.1}"
TRIVY_ROOT="${TRIVY_ROOT:-${RUNNER_TEMP:-/tmp}/trivy-${TRIVY_VERSION}}"
mkdir -p "$TRIVY_ROOT"

case "$(uname -m)" in
  x86_64) trivy_arch=64bit ;;
  aarch64|arm64) trivy_arch=ARM64 ;;
  *) echo "unsupported host architecture: $(uname -m)" >&2; exit 2 ;;
esac
archive="trivy_${TRIVY_VERSION}_Linux-${trivy_arch}.tar.gz"
base="https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}"
curl --fail --location --retry 5 --proto '=https' --tlsv1.2 \
  "${base}/${archive}" -o "${TRIVY_ROOT}/${archive}"
curl --fail --location --retry 5 --proto '=https' --tlsv1.2 \
  "${base}/trivy_${TRIVY_VERSION}_checksums.txt" -o "${TRIVY_ROOT}/checksums.txt"

expected="$(awk -v f="$archive" '$2 == f || $2 == "*" f {print $1; exit}' "${TRIVY_ROOT}/checksums.txt")"
[[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || { echo "missing checksum for $archive" >&2; exit 1; }
actual="$(sha256sum "${TRIVY_ROOT}/${archive}" | awk '{print $1}')"
[[ "$actual" == "$expected" ]] || { echo "Trivy checksum mismatch" >&2; exit 1; }
tar -xzf "${TRIVY_ROOT}/${archive}" -C "$TRIVY_ROOT" trivy
install -m 0755 "${TRIVY_ROOT}/trivy" "${TRIVY_BIN:-/usr/local/bin/trivy}"
"${TRIVY_BIN:-/usr/local/bin/trivy}" --version
