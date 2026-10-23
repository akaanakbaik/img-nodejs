# Reviewed multi-platform Node.js 24 default; CI passes an immutable digest per major.
ARG BASE_IMAGE=ghcr.io/parkervcp/yolks@sha256:9e84c334572bf9c0310fbc4d0b0a789a909957d30bd7f2454a7af758ee842919

# EOL is an unmodified-base compatibility/security report, never a release.
# BuildKit skips the supported-only package builder for this explicit target.
FROM ${BASE_IMAGE} AS eol-audit
ARG NODE_MAJOR
ARG NODE_PATCH
COPY --chown=container:container scripts/verify_runtime.js /usr/local/share/image-security/verify_runtime.js
COPY --chown=container:container versions.json /usr/local/share/versions.json
USER container
RUN EXPECTED_NODE_VERSION="${NODE_PATCH}" EXPECTED_NODE_MAJOR="${NODE_MAJOR}" node /usr/local/share/image-security/verify_runtime.js

FROM ${BASE_IMAGE} AS brotli-build

USER root
COPY vendor/brotli-source/brotli-1.1.1.tar.gz /work/brotli-1.1.1.tar.gz
COPY vendor/brotli-debian/debian /work/debian
COPY scripts/build_brotli_packages.sh scripts/verify_brotli_package.sh /work/scripts/
COPY security/brotli-debian-packaging.sha256 /work/packaging.sha256
RUN chmod 0755 /work/scripts/*.sh \
 && cd /work \
 && sed 's|  vendor/brotli-debian/debian/|  debian/|' packaging.sha256 | sha256sum -c - \
 && apt-get update --error-on=any \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      build-essential cmake debhelper debhelper-compat dh-python \
      dpkg-dev libpython3-all-dev python3-all-dev python3-setuptools \
      python3 \
 && /work/scripts/build_brotli_packages.sh \
 && rm -rf /var/lib/apt/lists/*

FROM ${BASE_IMAGE} AS typescript-build
USER root
COPY scripts/install_go_toolchain.sh scripts/build_typescript.sh scripts/test_typescript_source.py /work/scripts/
COPY security/typescript-source.json /work/security/typescript-source.json
ENV PATH="/opt/go/bin:${PATH}" \
    GOTOOLCHAIN=local \
    GOFLAGS=-p=2 \
    GOCACHE=/tmp/typescript-go-cache \
    GOMODCACHE=/tmp/typescript-go-modules
RUN bash /work/scripts/install_go_toolchain.sh \
 && OUT_DIR=/work/typescript-packages bash /work/scripts/build_typescript.sh \
 && TYPESCRIPT_REBUILD_OUTPUT=/work/typescript-packages python3 /work/scripts/test_typescript_source.py \
 && rm -rf /tmp/typescript-go-cache /tmp/typescript-go-modules

FROM ${BASE_IMAGE} AS supported
USER root
COPY --from=brotli-build /work/packages /tmp/brotli-packages
COPY scripts/verify_brotli_package.sh /usr/local/sbin/verify_brotli_package
RUN chmod 0755 /usr/local/sbin/verify_brotli_package \
 && cd /tmp/brotli-packages && sha256sum -c SHA256SUMS \
 && apt-get update --error-on=any \
 && packages="$(find /tmp/brotli-packages -name 'libbrotli1_*.deb')" \
 && for name in libbrotli-dev python3-brotli brotli; do \
      if [ "$(dpkg-query -W -f='${db:Status-Status}' "$name" 2>/dev/null)" = installed ]; then \
        packages="$packages $(find /tmp/brotli-packages -name "${name}_*.deb")"; \
      fi; \
    done \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $packages \
 && /usr/local/sbin/verify_brotli_package /tmp/brotli-packages \
 && test "$(dpkg-query -W -f='${Version}' libbrotli1)" = '1.1.1-0img1~deb13u1' \
 && install -d /usr/local/share/image-security/brotli-provenance \
 && cp /tmp/brotli-packages/provenance.json /tmp/brotli-packages/SHA256SUMS /tmp/brotli-packages/*.dsc /tmp/brotli-packages/*.changes /tmp/brotli-packages/*.buildinfo /usr/local/share/image-security/brotli-provenance/ \
 && install -Dm0644 /tmp/brotli-packages/provenance.json /usr/share/doc/libbrotli1/brotli-build-provenance.json \
 && install -Dm0644 /tmp/brotli-packages/SHA256SUMS /usr/share/doc/libbrotli1/brotli-package-sha256sums \
 && rm -rf /tmp/brotli-packages /var/lib/apt/lists/*

COPY --from=typescript-build /work/typescript-packages /tmp/typescript-packages
COPY scripts/install_typescript_rebuild.py /usr/local/share/image-security/install_typescript_rebuild.py
RUN python3 /usr/local/share/image-security/install_typescript_rebuild.py \
 && rm -rf /tmp/typescript-packages

ARG NODE_MAJOR=24
ARG NODE_PATCH=24.22.1
ARG APPLY_OS_UPDATES=true
LABEL org.opencontainers.image.title="Pterodactyl Node.js ${NODE_MAJOR}" \
      org.opencontainers.image.description="Version-verified Node.js based on Parkervcp Yolks; review security scans before deployment" \
      org.opencontainers.image.source="https://github.com/akaanakbaik/img-nodejs" \
      org.opencontainers.image.version="${NODE_PATCH}"

# Keep the inherited Yolks tools. Never remove packages to make a scan pass.
# Failed repository refreshes must stop the build rather than use stale indexes.
USER root
COPY scripts/update_supported_npm.js /usr/local/share/image-security/update_supported_npm.js
RUN case "${APPLY_OS_UPDATES}" in \
      true) apt-get update --error-on=any \
         && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-remove \
         && apt-get clean \
         && rm -rf /var/lib/apt/lists/* \
         && node /usr/local/share/image-security/update_supported_npm.js ;; \
      false) ;; \
      *) echo "APPLY_OS_UPDATES must be true or false" >&2; exit 1 ;; \
    esac

COPY --chown=container:container scripts/verify_runtime.js /usr/local/share/image-security/verify_runtime.js
COPY --chown=container:container versions.json /usr/local/share/versions.json
USER container
RUN EXPECTED_NODE_VERSION="${NODE_PATCH}" EXPECTED_NODE_MAJOR="${NODE_MAJOR}" node /usr/local/share/image-security/verify_runtime.js
