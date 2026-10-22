# Reviewed multi-platform Node.js 24 default; CI passes an immutable digest per major.
ARG BASE_IMAGE=ghcr.io/parkervcp/yolks@sha256:9e84c334572bf9c0310fbc4d0b0a789a909957d30bd7f2454a7af758ee842919
FROM ${BASE_IMAGE}

ARG NODE_MAJOR=24
ARG NODE_PATCH=24.22.1
LABEL org.opencontainers.image.title="Pterodactyl Node.js ${NODE_MAJOR}" \
      org.opencontainers.image.description="Version-verified Node.js based on Parkervcp Yolks; review security scans before deployment" \
      org.opencontainers.image.source="https://github.com/akaanakbaik/img-nodejs" \
      org.opencontainers.image.version="${NODE_PATCH}"

COPY --chown=container:container scripts/verify_runtime.js /usr/local/share/image-security/verify_runtime.js
COPY --chown=container:container versions.json /usr/local/share/versions.json
USER container
RUN EXPECTED_NODE_VERSION="${NODE_PATCH}" EXPECTED_NODE_MAJOR="${NODE_MAJOR}" node /usr/local/share/image-security/verify_runtime.js
