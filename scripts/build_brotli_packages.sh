#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
: "${BUILD_ROOT:=/work}"
: "${SOURCE_ARCHIVE:=$BUILD_ROOT/brotli-1.1.1.tar.gz}"
: "${PACKAGING_DIR:=$BUILD_ROOT/debian}"
: "${OUTPUT_DIR:=$BUILD_ROOT/packages}"
EXPECTED_SHA256=38f9c17ee36c2e930ce00975b50fcd246a8e5594c1bcf43cd56b14118786b82a
EXPECTED_VERSION='1.1.1-0img1~deb13u1'
export SOURCE_DATE_EPOCH=1792713600
export DPKG_GENSYMBOLS_CHECK_LEVEL=4
rm -rf "$BUILD_ROOT/build" "$OUTPUT_DIR"
mkdir -p "$BUILD_ROOT/build" "$OUTPUT_DIR"
echo "$EXPECTED_SHA256  $SOURCE_ARCHIVE" | sha256sum -c -
root=$(tar -tzf "$SOURCE_ARCHIVE" | sed -n '1p' | cut -d/ -f1)
tar -xzf "$SOURCE_ARCHIVE" -C "$BUILD_ROOT/build"
cp -a "$PACKAGING_DIR" "$BUILD_ROOT/build/$root/debian"
cp "$SOURCE_ARCHIVE" "$BUILD_ROOT/build/brotli_1.1.1.orig.tar.gz"
chmod 0755 "$BUILD_ROOT/build/$root/debian/rules" "$BUILD_ROOT/build/$root/debian/rename-static-libs.sh"
cd "$BUILD_ROOT/build/$root"
test "$(dpkg-parsechangelog -S Version)" = "$EXPECTED_VERSION"
# Full source + binary build; normal CMake tests and strict Debian symbols check.
dpkg-buildpackage --build=full --no-sign --jobs=auto
# Upstream removed distutils' test command: explicitly run its Python suite
# against the extension produced by this build, including subprocess fixtures.
PYTHONPATH="$PWD/debian/python3-brotli/usr/lib/python3/dist-packages:$PWD/python" \
  python3 -m unittest discover -s python/tests -t python -p '*_test.py'
find "$BUILD_ROOT/build" -maxdepth 1 -type f \( -name '*.deb' -o -name '*.dsc' -o -name '*.changes' -o -name '*.buildinfo' -o -name '*.debian.tar.*' -o -name '*.orig.tar.*' \) -exec cp -t "$OUTPUT_DIR" {} +
"$SCRIPT_DIR/verify_brotli_package.sh" "$OUTPUT_DIR" "$EXPECTED_VERSION"
(cd "$OUTPUT_DIR" && sha256sum -- *.deb *.dsc *.changes *.buildinfo *.debian.tar.* *.orig.tar.*) > "$OUTPUT_DIR/SHA256SUMS"
cat > "$OUTPUT_DIR/provenance.json" <<EOF
{
  "package_version": "$EXPECTED_VERSION",
  "upstream_commit": "db0631dfea829194206d269bc7b25d0908cdb97d",
  "upstream_archive_sha256": "$EXPECTED_SHA256",
  "debian_packaging_source_version": "1.1.0-2",
  "debian_packaging_path": "vendor/brotli-debian/debian",
  "package_sha256_file": "SHA256SUMS",
  "tests": "Debian full source/binary build, CMake tests, explicit upstream Python unittest suite, strict dpkg symbols, SONAME and baseline exported-symbol comparison",
  "abi": ["libbrotlicommon.so.1", "libbrotlidec.so.1", "libbrotlienc.so.1"],
  "security_status": "Custom rebuild, not a Debian security release. No scanner exception; vendor-unfixed findings still block publication."
}
EOF
