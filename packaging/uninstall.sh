#!/usr/bin/env bash
# Remove HyperCube. Optionally remove Docker images and the Docker engine itself.

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log()  { printf "${GREEN}[+]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[!]${NC} %s\n" "$*"; }

[[ $EUID -eq 0 ]] || { echo "Run with sudo or as root."; exit 1; }

INSTALL_DIR="/opt/hypercube"

read -r -p "Stop HyperCube and remove ${INSTALL_DIR}? [y/N] " confirm
[[ "${confirm}" =~ ^[Yy]$ ]] || { echo "aborted"; exit 0; }

systemctl stop hypercube     2>/dev/null || true
systemctl disable hypercube  2>/dev/null || true
rm -f /etc/systemd/system/hypercube.service
systemctl daemon-reload

if [[ -f "${INSTALL_DIR}/docker-compose.yml" ]]; then
    cd "${INSTALL_DIR}"
    docker compose down -v 2>/dev/null || true
fi

rm -rf "${INSTALL_DIR}"
log "Removed ${INSTALL_DIR}"

read -r -p "Also remove HyperCube Docker images? [y/N] " rmimg
if [[ "${rmimg}" =~ ^[Yy]$ ]]; then
    docker rmi $(docker images 'ghcr.io/qkr7287/hypercube-*' -q) 2>/dev/null || true
    docker rmi pgvector/pgvector:pg16 redis:7-alpine 2>/dev/null || true
    log "Removed HyperCube images"
fi

read -r -p "Also remove Docker engine itself? [y/N] " rmdocker
if [[ "${rmdocker}" =~ ^[Yy]$ ]]; then
    apt-get purge -y docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin 2>/dev/null || true
    rm -rf /var/lib/docker /var/lib/containerd
    log "Removed Docker engine"
else
    warn "Docker engine kept."
fi
