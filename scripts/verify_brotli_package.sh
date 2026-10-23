#!/usr/bin/env bash
set -euo pipefail
PKG_DIR=${1:?package directory required}
EXPECTED_VERSION=${2:-1.1.1-0img1~deb13u1}
required=(libbrotli1 libbrotli-dev python3-brotli brotli)
for name in "${required[@]}"; do
  mapfile -t matches < <(find "$PKG_DIR" -maxdepth 1 -type f -name "${name}_*.deb" -print)
  [[ ${#matches[@]} == 1 ]] || { echo "expected one $name package" >&2; exit 1; }
  deb="${matches[0]}"
  test "$(dpkg-deb -f "$deb" Package)" = "$name"
  test "$(dpkg-deb -f "$deb" Version)" = "$EXPECTED_VERSION"
  test "$(dpkg-deb -f "$deb" Architecture)" = "$(dpkg --print-architecture)"
  # Debian omits the source version when it equals the binary version.
  source_field="$(dpkg-deb -f "$deb" Source)"
  [[ "$source_field" == brotli || "$source_field" == "brotli ($EXPECTED_VERSION)" ]]
done
lib="$(find "$PKG_DIR" -maxdepth 1 -type f -name 'libbrotli1_*.deb' -print)"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
dpkg-deb -x "$lib" "$tmp"
for soname in libbrotlicommon.so.1 libbrotlidec.so.1 libbrotlienc.so.1; do
  mapfile -t matches < <(find "$tmp/usr/lib" -name "$soname" -print)
  [[ ${#matches[@]} == 1 ]] || { echo "missing/duplicate $soname" >&2; exit 1; }
  so="${matches[0]}"
  readelf -d "$so" | grep -F "Library soname: [$soname]" >/dev/null
  readelf --dyn-syms --wide "$so" | grep -E 'Brotli(Decoder|Encoder|GetDictionary|DefaultAlloc)' >/dev/null
  # Compare all exported Brotli public symbols against the baseline SONAME.
  baseline="$(ldconfig -p | awk -v n="$soname" '$1 == n {print $NF}')"
  [[ -n "$baseline" && -f "$baseline" ]]
  readelf --dyn-syms --wide "$baseline" | awk '$7 != "UND" && $8 ~ /^(Brotli|_kBrotli)/ {print $8}' | sort -u > "$tmp/old-symbols"
  readelf --dyn-syms --wide "$so" | awk '$7 != "UND" && $8 ~ /^(Brotli|_kBrotli)/ {print $8}' | sort -u > "$tmp/new-symbols"
  comm -23 "$tmp/old-symbols" "$tmp/new-symbols" > "$tmp/missing-symbols"
  [[ ! -s "$tmp/missing-symbols" ]] || { cat "$tmp/missing-symbols" >&2; exit 1; }
done
printf 'Brotli Debian packages verified: version=%s architecture=%s ABI=libbrotli*.so.1 no baseline public symbols lost\n' "$EXPECTED_VERSION" "$(dpkg --print-architecture)"
