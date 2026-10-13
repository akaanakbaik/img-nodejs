ARG NODE_VERSION=24
FROM ghcr.io/parkervcp/yolks:nodejs_${NODE_VERSION}

ARG NODE_VERSION
LABEL org.opencontainers.image.title="Pterodactyl Node.js ${NODE_VERSION}" \
      org.opencontainers.image.description="Node.js ${NODE_VERSION} runtime based on Parkervcp Yolks for Pterodactyl" \
      org.opencontainers.image.source="https://github.com/akaanakbaik/img-nodejs" \
      org.opencontainers.image.version="${NODE_VERSION}"
