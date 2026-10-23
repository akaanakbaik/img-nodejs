#!/usr/bin/env bash
set -euo pipefail
# Builder-only toolchain; never copied into the runtime image.
arch="$(dpkg --print-architecture)"
case "$arch" in
  amd64) checksum=ccfe7ae822d2c2f41f4fe7c956199967a4dac22d0ee0d2b2bfdb440aab3b20c5 ;;
  arm64) checksum=3f4227ce7b206a513e794f1393adb473a07b46e94d18bd15d1c684bbb7319797 ;;
  *) echo "Unsupported native Go architecture: $arch" >&2; exit 2 ;;
esac
archive="$(mktemp)"
trap 'rm -f "$archive"' EXIT
curl --fail --show-error --location --proto '=https' --tlsv1.2 --retry 3 --max-time 180 \
  "https://go.dev/dl/go1.26.10.linux-${arch}.tar.gz" -o "$archive"
printf '%s  %s\n' "$checksum" "$archive" | sha256sum -c -
# Refuse to merge a toolchain into an existing installation.
test ! -e /opt/go
tar -xzf "$archive" -C /opt
test "$(/opt/go/bin/go env GOVERSION)" = go1.26.10
test "$(/opt/go/bin/go env GOARCH)" = "$arch"
