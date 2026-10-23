#!/usr/bin/env bash
set -euo pipefail

# Native-only rebuild of the exact TypeScript 7.0.2 source tag.  The version,
# toolchain and x/text pins are deliberately constants: this is not a generic
# or overrideable feasibility builder.
readonly VERSION='7.0.2'
readonly SOURCE_URL='https://github.com/microsoft/typescript-go/archive/refs/tags/typescript/v7.0.2.tar.gz'
readonly SOURCE_SHA256='25cca8ec9d89e4ceec5181a677ded2c6d690fa18b81e1277846303973eb71fcf'
readonly SOURCE_COMMIT='2bd066d87f5bafd315be9f40889d0a60b9e58e0b'
readonly XTEXT_VERSION='v0.41.0'
readonly GO_VERSION='1.26.10'
readonly OUT_DIR="${OUT_DIR:-$PWD/typescript-rebuild-output}"
readonly WORK_DIR="${WORK_DIR:-$(mktemp -d)}"
readonly KEEP_WORK="${KEEP_WORK:-0}"
cleanup() { [[ "$KEEP_WORK" == 1 ]] || rm -rf "$WORK_DIR"; }
trap cleanup EXIT
export GOTOOLCHAIN=local GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org

command -v go >/dev/null || { echo 'go is required' >&2; exit 2; }
command -v curl >/dev/null || { echo 'curl is required' >&2; exit 2; }
actual_go="$(go env GOVERSION | sed 's/^go//')"
[[ "$actual_go" == "$GO_VERSION" ]] || { echo "requires Go $GO_VERSION, found $actual_go" >&2; exit 2; }
[[ "$(go env GOOS)" == linux ]] || { echo "requires native Linux builder, found GOOS=$(go env GOOS)" >&2; exit 2; }
actual_arch="$(go env GOARCH)"
case "$actual_arch" in amd64|arm64) ;; *) echo "unsupported native GOARCH=$actual_arch" >&2; exit 2;; esac
case "$(uname -m)" in x86_64) host_arch=amd64;; aarch64) host_arch=arm64;; *) exit 2;; esac
[[ "$actual_arch" == "$host_arch" ]] || { echo 'GOARCH does not match native kernel architecture' >&2; exit 2; }
if [[ -n "${TARGET_ARCH:-}" && "$TARGET_ARCH" != "$actual_arch" ]]; then
  echo "cross-compilation is forbidden: TARGET_ARCH=$TARGET_ARCH, native GOARCH=$actual_arch" >&2; exit 2
fi
mkdir -p "$WORK_DIR/src" "$OUT_DIR"
archive="$WORK_DIR/source.tar.gz"
curl -fsSL --proto '=https' --tlsv1.2 --retry 3 -o "$archive" "$SOURCE_URL"
printf '%s  %s\n' "$SOURCE_SHA256" "$archive" | sha256sum -c -
tar -xzf "$archive" -C "$WORK_DIR/src"
root="$(find "$WORK_DIR/src" -mindepth 1 -maxdepth 1 -type d -print -quit)"
[[ -n "$root" && -f "$root/go.mod" ]] || { echo 'source archive has no go.mod' >&2; exit 1; }
printf 'source=%s\ncommit=%s\ntar_sha256=%s\n' "$SOURCE_URL" "$SOURCE_COMMIT" "$SOURCE_SHA256" > "$WORK_DIR/source-pin.txt"

cd "$root"
# Record every Go source hash before tooling; only go.mod/go.sum may change.
find . -type f -name '*.go' -print0 | sort -z | xargs -0 sha256sum > "$WORK_DIR/go-sources.before"
cp go.mod "$WORK_DIR/go.mod.original"
cp go.sum "$WORK_DIR/go.sum.original"
go mod edit -require="golang.org/x/text@$XTEXT_VERSION"
GOTOOLCHAIN=local GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org go mod download all
find . -type f -name '*.go' -print0 | sort -z | xargs -0 sha256sum > "$WORK_DIR/go-sources.after"
cmp "$WORK_DIR/go-sources.before" "$WORK_DIR/go-sources.after"
GOTOOLCHAIN=local GOPROXY=https://proxy.golang.org GOSUMDB=sum.golang.org go mod verify
# The release tag changes core.version to 7.0.2, but its help baseline was
# formatted with the nine-character development version before sanitization.
# Set that version ONLY in test executables; never accept/skip a baseline.
if ! go test -p 2 -ldflags='-X github.com/microsoft/typescript-go/internal/core.version=7.0.0-dev' ./...; then
  find testdata/baselines/local -type f -name '*.js' -print | sed -n '1,20p'
  reference=testdata/baselines/reference/tsc/commandLine/show-help-with-ExitStatus.DiagnosticsPresent_OutputsSkipped.js
  local=testdata/baselines/local/tsc/commandLine/show-help-with-ExitStatus.DiagnosticsPresent_OutputsSkipped.js
  if test -f "$local"; then diff -u "$reference" "$local" || true; fi
  exit 1
fi
find . -type f -name '*.go' -print0 | sort -z | xargs -0 sha256sum > "$WORK_DIR/go-sources.after-tests"
cmp "$WORK_DIR/go-sources.before" "$WORK_DIR/go-sources.after-tests"

# Do not guess a main package: cmd/tsgo is the authenticated upstream entrypoint.
[[ -d ./cmd/tsgo ]] || { echo 'authenticated cmd/tsgo package missing' >&2; exit 1; }
npm_arch=x64; [[ "$actual_arch" == arm64 ]] && npm_arch=arm64
case "$npm_arch" in
  x64) platform_url='https://registry.npmjs.org/@typescript/typescript-linux-x64/-/typescript-linux-x64-7.0.2.tgz'; platform_sha512='EYdf2cNg7rgCWJnxCdJ+F3V39O8ihb37eHAu1LK8oAFizgTQbPOK7zHHXbPt8rX24COqODXeI3sIf0fCXG7H/A==' ;;
  arm64) platform_url='https://registry.npmjs.org/@typescript/typescript-linux-arm64/-/typescript-linux-arm64-7.0.2.tgz'; platform_sha512='Qh4eU4/y3yDjnfjjyPYihMj5/ODIlmt+Bzu17OI+fiSRDW57QmU5SiN63exPRNJPKUzcc1INa1NXdrJ+MqHjUQ==' ;;
esac
platform_tgz="$WORK_DIR/platform.tgz"
curl -fsSL --proto '=https' --tlsv1.2 --retry 3 -o "$platform_tgz" "$platform_url"
python3 - "$platform_tgz" "$platform_sha512" <<'PY'
import base64, hashlib, pathlib, sys
actual = base64.b64encode(hashlib.sha512(pathlib.Path(sys.argv[1]).read_bytes()).digest()).decode()
if actual != sys.argv[2]:
    raise SystemExit('TypeScript platform package SHA-512 mismatch')
PY
pkg="$OUT_DIR/typescript-linux-$npm_arch"
rm -rf "$pkg"; mkdir -p "$pkg"
# Start from the complete authentic package (wrappers, declarations, license,
# README and metadata), then replace only its compiler executable.
tar -xzf "$platform_tgz" -C "$pkg" --strip-components=1
rm -f "$pkg/lib/tsc.sig" # signature belongs to the upstream binary we replace
GOTOOLCHAIN=local CGO_ENABLED=0 go build -trimpath -o "$pkg/lib/tsc" ./cmd/tsgo
chmod 0755 "$pkg/lib/tsc"
python3 - "$pkg/package.json" "$pkg" "$actual_arch" "$platform_sha512" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text()); d['x-image-build']={'kind':'custom-native-rebuild','official_upstream_binary':False,'compiler_sources_modified':False,'source_commit':'2bd066d87f5bafd315be9f40889d0a60b9e58e0b','source_tar_sha256':'25cca8ec9d89e4ceec5181a677ded2c6d690fa18b81e1277846303973eb71fcf','go_version':'1.26.10','x_text':'v0.41.0','platform_package_sha512':sys.argv[4]}; p.write_text(json.dumps(d,indent=2)+'\n')
PY
cat > "$pkg/BUILD-PROVENANCE.json" <<EOF
{"kind":"custom-native-rebuild","upstream_version":"$VERSION","source_url":"$SOURCE_URL","source_commit":"$SOURCE_COMMIT","source_tar_sha256":"$SOURCE_SHA256","go_version":"$GO_VERSION","x_text":"$XTEXT_VERSION","main_package":"./cmd/tsgo","target":"linux/$actual_arch","tests":"go test -p 2 -ldflags=-X=github.com/microsoft/typescript-go/internal/core.version=7.0.0-dev ./...","test_only_version":"7.0.0-dev","runtime_version":"7.0.2","baseline_modified":false,"tests_skipped":false,"official_upstream_binary":false,"compiler_sources_modified":false,"platform_package_url":"$platform_url","platform_package_sha512":"$platform_sha512","stale_upstream_signature_removed":true}
EOF
go version -m "$pkg/lib/tsc" > "$pkg/go-build-info.txt"
grep -F 'go1.26.10' "$pkg/go-build-info.txt"
grep -E 'dep[[:space:]]+golang.org/x/text[[:space:]]+v0\.41\.0[[:space:]]' "$pkg/go-build-info.txt"
cp go.mod "$pkg/build.go.mod"
cp go.sum "$pkg/build.go.sum"
cp "$WORK_DIR/go-sources.before" "$pkg/compiler-source-sha256sums.txt"
for file in go.mod go.sum; do
  diff -u --label "upstream/$file" --label "rebuilt/$file" "$WORK_DIR/$file.original" "$file" >> "$pkg/dependency-diff.txt" || test "$?" = 1
done
( cd "$OUT_DIR" && find "typescript-linux-$npm_arch" -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
printf 'Built complete custom package %s (native linux/%s, Go %s, x/text %s)\n' "$pkg" "$actual_arch" "$actual_go" "$XTEXT_VERSION"
