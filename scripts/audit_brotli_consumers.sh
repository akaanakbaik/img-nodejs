#!/usr/bin/env bash
set -euo pipefail

# Bounded, evidence-only audit. It does not attempt to trigger a vulnerability.
TMPDIR_AUDIT="$(mktemp -d /tmp/audit-brotli.XXXXXX)"
cleanup() { jobs -p 2>/dev/null | xargs -r kill 2>/dev/null || true; rm -rf "$TMPDIR_AUDIT"; }
trap cleanup EXIT INT TERM

say() { printf '%s\n' "$*"; }
fail() { say "FAIL: $*" >&2; exit 1; }

say "Brotli consumer audit (evidence-only; no exploit, no exemption, no publish)"
say "timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ) host=$(uname -m)"
say "image=$(cat /etc/os-release 2>/dev/null | tr '\n' ';' || true)"
say "-- installed Brotli packages and dpkg reverse dependency evidence --"
if command -v dpkg-query >/dev/null 2>&1; then
  dpkg-query -W -f='${binary:Package}\t${Version}\t${Status}\n' 'libbrotli*' 2>/dev/null || say "No libbrotli package matched dpkg-query"
  say "Installed packages declaring a dependency on libbrotli packages:"
  dpkg-query -W -f='${binary:Package}\t${Depends}\t${Pre-Depends}\t${Recommends}\n' 2>/dev/null | awk -F '\t' '$0 ~ /(^|[ ,|])libbrotli[^ ,|]*/ {print}' || true
else
  say "dpkg-query unavailable"
fi
if command -v apt-cache >/dev/null 2>&1; then
  apt-cache rdepends --installed libbrotli1 2>/dev/null || true
  apt-cache rdepends --installed libbrotli-dev 2>/dev/null || true
fi
say "-- curl version --"
if command -v curl >/dev/null 2>&1; then curl --version; else say "curl unavailable"; fi

say "-- ELF DT_NEEDED and undefined Brotli decoder symbols --"
elf_report() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  say "TARGET $f"
  if command -v readelf >/dev/null 2>&1 && readelf -h "$f" >/dev/null 2>&1; then
    say "DT_NEEDED:"
    readelf -d "$f" 2>/dev/null | sed -n 's/.*Shared library: \[\([^]]*\)\].*/  \1/p' || true
    say "UNDEFINED_BROTLI_DECODER_SYMBOLS:"
    readelf --dyn-syms --wide "$f" 2>/dev/null | awk '$7 == "UND" && $8 ~ /^BrotliDecoder/ {print "  "$8}' | sort -u || true
  else
    say "not an ELF or readelf unavailable"
  fi
}
elf_report /usr/bin/curl
GIT_HTTP="$(command -v git-remote-http 2>/dev/null || true)"
[[ -n "$GIT_HTTP" ]] || for p in /usr/lib/git-core/git-remote-http /usr/libexec/git-core/git-remote-http; do [[ -x "$p" ]] && GIT_HTTP="$p" && break; done
elf_report "$GIT_HTTP"
for tool in /usr/bin/ffmpeg /usr/bin/ffprobe; do
  [[ -e "$tool" ]] && elf_report "$tool"
done
while IFS= read -r f; do elf_report "$f"; done < <(ldconfig -p 2>/dev/null | awk '$1 ~ /^lib(curl|jxl|freetype)/ {print $NF}' | sort -u | while read -r p; do readlink -f "$p" 2>/dev/null || printf '%s\n' "$p"; done | sort -u)
say "TARGET node (expected no direct Brotli linkage in the Node executable):"
if command -v node >/dev/null 2>&1; then elf_report "$(command -v node)"; else say "node unavailable"; fi

say "-- safe dynamic decoder proof (valid benign Brotli payload only) --"
command -v gcc >/dev/null 2>&1 || fail "gcc is required for the dynamic probe"
command -v python3 >/dev/null 2>&1 || fail "python3 is required for the local HTTP proof"
command -v curl >/dev/null 2>&1 || fail "curl is required for the dynamic proof"
SRC="/audit/brotli_decoder_probe.c"
[[ -r "$SRC" ]] || SRC="$(dirname "$0")/brotli_decoder_probe.c"
[[ -r "$SRC" ]] || fail "probe source not found"
gcc -shared -fPIC -O2 -Wall -Wextra -o "$TMPDIR_AUDIT/brotli_decoder_probe.so" "$SRC" -ldl
[[ -s "$TMPDIR_AUDIT/brotli_decoder_probe.so" ]] || fail "probe compilation failed"
if ! command -v node >/dev/null 2>&1; then fail "node is required to generate the valid .br fixture"; fi
node - "$TMPDIR_AUDIT/fixture.br" <<'NODE'
const fs = require('fs'), zlib = require('zlib');
const out = process.argv[2];
fs.writeFileSync(out, zlib.brotliCompressSync(Buffer.from('brotli-audit-benign-proof\n')));
NODE
[[ -s "$TMPDIR_AUDIT/fixture.br" ]] || fail "Node did not create a Brotli fixture"
cat >"$TMPDIR_AUDIT/server.py" <<'PY'
import http.server, os, sys
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            data = open(os.environ['BROTLIFIX'], 'rb').read()
            self.send_response(200); self.send_header('Content-Type','text/plain')
            self.send_header('Content-Encoding','br'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        except Exception:
            self.send_error(500)
    def log_message(self, fmt, *args): pass
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
PY
portfile="$TMPDIR_AUDIT/port"
BROTLIFIX="$TMPDIR_AUDIT/fixture.br" python3 "$TMPDIR_AUDIT/server.py" >"$portfile" 2>"$TMPDIR_AUDIT/server.err" &
server_pid=$!
port=""
for _ in $(seq 1 50); do [[ -s "$portfile" ]] && { read -r port <"$portfile"; [[ "$port" =~ ^[0-9]+$ ]] && break; }; sleep 0.1; done
[[ "$port" =~ ^[0-9]+$ ]] || fail "local HTTP server readiness timed out"
printf 'probe_url=http://127.0.0.1:%s/fixture.br\n' "$port"
probe_output="$TMPDIR_AUDIT/output"
probe_log="$TMPDIR_AUDIT/probe.log"
set +e
BROTLI_PROBE_LOG="$probe_log" LD_PRELOAD="$TMPDIR_AUDIT/brotli_decoder_probe.so" curl --noproxy '*' --connect-timeout 5 --max-time 15 --silent --show-error --fail --compressed "http://127.0.0.1:$port/fixture.br" >"$probe_output"
curl_rc=$?
set -e
[[ "$curl_rc" -eq 0 ]] || fail "curl Brotli proof failed (rc=$curl_rc)"
grep -Fqx 'brotli-audit-benign-proof' "$probe_output" || fail "curl output was not decoded expected benign text"
if ! grep -Eq '^BROTLI_PROBE_CALLED BrotliDecoder(DecompressStream|Decompress) ' "$probe_log" 2>/dev/null; then
  fail "LD_PRELOAD did not observe a Brotli decoder call"
fi
say "PASS: curl --compressed decoded benign HTTP Content-Encoding: br payload"
say "PASS: LD_PRELOAD observed system Brotli decoder invocation:"
cat "$probe_log"
say "INTERPRETATION: This proves network-controlled content routed through curl reaches the system Brotli decoder. It does NOT prove that a vulnerable branch or exact CVE trigger was exercised. libbrotli vulnerability status must come from vendor/advisory evidence; static libjxl/libfreetype symbol matches are inference only, not dynamic consumption proof."
