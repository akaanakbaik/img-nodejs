# Reviewed multi-platform Node.js 24 default; CI passes an immutable digest per major.
ARG BASE_IMAGE=ghcr.io/parkervcp/yolks@sha256:9e84c334572bf9c0310fbc4d0b0a789a909957d30bd7f2454a7af758ee842919
FROM ${BASE_IMAGE}

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
RUN case "${APPLY_OS_UPDATES}" in \
      true) apt-get update --error-on=any \
         && DEBIAN_FRONTEND=noninteractive apt-get upgrade -y --no-remove \
         && apt-get clean \
         && rm -rf /var/lib/apt/lists/* ;; \
      false) ;; \
      *) echo "APPLY_OS_UPDATES must be true or false" >&2; exit 1 ;; \
    esac

COPY --chown=container:container scripts/verify_runtime.js /usr/local/share/image-security/verify_runtime.js
COPY --chown=container:container versions.json /usr/local/share/versions.json
USER container
RUN EXPECTED_NODE_VERSION="${NODE_PATCH}" EXPECTED_NODE_MAJOR="${NODE_MAJOR}" node /usr/local/share/image-security/verify_runtime.js
