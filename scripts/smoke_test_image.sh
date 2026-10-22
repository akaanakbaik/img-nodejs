#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 <node-major> <amd64|arm64> <image> [expected-full-version]" >&2
  exit 2
fi

expected_major="$1"
arch="$2"
image="$3"
expected_version="${4:-}"
platform="linux/${arch}"

engine="${CONTAINER_ENGINE:-docker}"
command -v "$engine" >/dev/null || { echo "Container engine not found: $engine" >&2; exit 2; }
run_args=()
if [[ -n "${RUN_ARGS:-}" ]]; then read -r -a run_args <<<"$RUN_ARGS"; fi
network_args=()
if [[ -n "${CONTAINER_NETWORK:-}" ]]; then
  network_args+=(--network "$CONTAINER_NETWORK")
elif [[ "$engine" == "podman" ]]; then
  # Podman in the CI sandbox needs host networking to reach the registry/runtime.
  network_args+=(--network host)
fi

case "$arch" in
  amd64|arm64) ;;
  *) echo "Unsupported architecture: $arch" >&2; exit 2 ;;
esac

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# These are the Pterodactyl Yolks runtime defaults that the Egg relies on.
image_user="$("$engine" inspect --format '{{.Config.User}}' "$image")"
workdir="$("$engine" inspect --format '{{.Config.WorkingDir}}' "$image")"
entrypoint="$("$engine" inspect --format '{{json .Config.Entrypoint}}' "$image")"
cmd="$("$engine" inspect --format '{{json .Config.Cmd}}' "$image")"
[[ "$image_user" == "container" ]] || fail "expected Config.User=container, got '$image_user'"
[[ "$workdir" == "/home/container" ]] || fail "expected Config.WorkingDir=/home/container, got '$workdir'"
[[ "$entrypoint" == '["/usr/bin/tini","-g","--"]' ]] || fail "unexpected entrypoint: $entrypoint"
[[ "$cmd" == '["/entrypoint.sh"]' ]] || fail "unexpected default command: $cmd"
printf 'PASS: %s user=%s workdir=%s entrypoint=%s cmd=%s\n' "$platform" "$image_user" "$workdir" "$entrypoint" "$cmd"

# Exercise the Egg's startup shape after substituting AUTO_UPDATE=0 and a harmless CMD_RUN.
# This does not pull application code or access credentials.
startup_fixture="$(cat <<'STARTUP'
set -euo pipefail
if [[ -d .git ]] && [[ 0 == "1" ]]; then git pull; fi; if [[ ! -z ${NODE_PACKAGES} ]]; then /usr/local/bin/npm install ${NODE_PACKAGES}; fi; if [[ ! -z ${UNNODE_PACKAGES} ]]; then /usr/local/bin/npm uninstall ${UNNODE_PACKAGES}; fi; if [ -f /home/container/package.json ]; then /usr/local/bin/npm install; fi; if [[ ! -z ${CUSTOM_ENVIRONMENT_VARIABLES} ]]; then vars=$(echo ${CUSTOM_ENVIRONMENT_VARIABLES} | tr ";" "\n"); for line in $vars; do export $line; done; fi; /usr/local/bin/${CMD_RUN};
STARTUP
)"

bash -n <<<"$startup_fixture" || fail "Egg startup fixture does not parse as Bash"
"$engine" run --rm "${run_args[@]}" "${network_args[@]}" --platform "$platform" \
  --env AUTO_UPDATE=0 \
  --env NODE_PACKAGES= \
  --env UNNODE_PACKAGES= \
  --env CUSTOM_ENVIRONMENT_VARIABLES= \
  --env CMD_RUN='node --version' \
  --env EXPECTED_NODE_MAJOR="$expected_major" \
  ${expected_version:+--env EXPECTED_NODE_VERSION="$expected_version"} \
  "$image" /bin/bash -lc "$startup_fixture" > /tmp/img-nodejs-smoke.log

# The container command above keeps the inherited Tini entrypoint and configured user/workdir.
grep -Eq "^v${expected_major}\\." /tmp/img-nodejs-smoke.log || fail "Egg startup did not run the expected Node.js major"
actual_version="$("$engine" run --rm "${run_args[@]}" "${network_args[@]}" --platform "$platform" --env EXPECTED_NODE_MAJOR="$expected_major" "$image" /bin/bash -lc 'test "$(id -un)" = container && test "$HOME" = /home/container && test "$PWD" = /home/container && node -e '\''const m=process.versions.node.split(".")[0]; if(m!==process.env.EXPECTED_NODE_MAJOR) process.exit(1); if(!["x64","arm64"].includes(process.arch)) process.exit(1)'\'' && npm --version >/dev/null && node --version')"
if [[ -n "$expected_version" ]]; then
  [[ "$actual_version" == "v${expected_version}" ]] || fail "runtime Node.js exact version mismatch: $actual_version (expected v$expected_version)"
else
  [[ "$actual_version" == v"${expected_major}".* ]] || fail "runtime Node.js version mismatch: $actual_version"
fi
printf 'PASS: %s Node.js %s, npm, HOME, PWD, USER, inherited Tini entrypoint, and Egg startup fixture.\n' "$platform" "$expected_major"
