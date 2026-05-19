#!/usr/bin/env bash
# HyperCube air-gapped installer.
#
# Docker is a PRE-REQUISITE — the operator (or infra team) installs it via
# whatever channel suits their distro (apt/dnf/etc). This script is OS-
# agnostic and only handles HyperCube itself: image load, /opt/hypercube
# layout, .env, compose up, systemd registration.

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { printf "${GREEN}[+]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
err()  { printf "${RED}[x]${NC} %s\n" "$*" >&2; exit 1; }

INSTALL_DIR="/opt/hypercube"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ---------------------------------------------------------------- preflight
[[ $EUID -eq 0 ]] || err "Run with sudo or as root."

[[ -f "${SCRIPT_DIR}/images/hypercube-images.tar" ]] \
    || err "Image tarball missing — installer is corrupted."

# ---------------------------------------------------------------- docker check
if ! command -v docker >/dev/null 2>&1; then
    err "Docker is not installed. Please install Docker first.

  Ubuntu/Debian:  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  RHEL/Rocky:     sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  After install:  sudo systemctl enable --now docker"
fi

if ! docker info >/dev/null 2>&1; then
    err "Docker is installed but daemon is not running.

  Start it with:  sudo systemctl start docker
  Enable on boot: sudo systemctl enable docker"
fi

if ! docker compose version >/dev/null 2>&1; then
    err "docker compose plugin missing.

  Ubuntu/Debian:  sudo apt-get install -y docker-compose-plugin
  RHEL/Rocky:     sudo dnf install -y docker-compose-plugin"
fi

log "Docker detected: $(docker --version)"
log "Compose detected: $(docker compose version --short 2>/dev/null || docker compose version)"

# ---------------------------------------------------------------- images
log "Loading HyperCube images (this can take a minute)..."
docker load -i "${SCRIPT_DIR}/images/hypercube-images.tar"

# ---------------------------------------------------------------- install dir
mkdir -p "${INSTALL_DIR}"
cp "${SCRIPT_DIR}/app/docker-compose.yml" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/app/.env.example"       "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/env-generate.sh"        "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/uninstall.sh"           "${INSTALL_DIR}/"
[[ -f "${SCRIPT_DIR}/VERSION" ]] && cp "${SCRIPT_DIR}/VERSION" "${INSTALL_DIR}/"
chmod +x "${INSTALL_DIR}/env-generate.sh" "${INSTALL_DIR}/uninstall.sh"

# ---------------------------------------------------------------- .env
if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    log "Generating .env (interactive)..."
    bash "${INSTALL_DIR}/env-generate.sh" "${INSTALL_DIR}/.env"
    chmod 600 "${INSTALL_DIR}/.env"
else
    warn ".env already exists — keeping current configuration."
fi

# ---------------------------------------------------------------- compose up
log "Starting HyperCube stack..."
cd "${INSTALL_DIR}"
docker compose up -d

# ---------------------------------------------------------------- systemd
cp "${SCRIPT_DIR}/app/hypercube.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable hypercube >/dev/null 2>&1

# ---------------------------------------------------------------- healthcheck
log "Waiting for backend (up to 60s)..."
healthy=false
for _ in $(seq 1 30); do
    if curl -fsS --max-time 2 "http://127.0.0.1:$(grep -E '^HC_PORT=' "${INSTALL_DIR}/.env" | cut -d= -f2)/api/health/" \
        >/dev/null 2>&1; then
        healthy=true
        break
    fi
    sleep 2
done

# ---------------------------------------------------------------- summary
host=$(grep -E '^HC_HOST='   "${INSTALL_DIR}/.env" | cut -d= -f2 | tr -d '\r')
port=$(grep -E '^HC_PORT='   "${INSTALL_DIR}/.env" | cut -d= -f2 | tr -d '\r')

echo
if [[ "${healthy}" == "true" ]]; then
    log "HyperCube installed successfully."
else
    warn "Installed, but health check did not respond yet."
    warn "Check 'docker compose logs -f' under ${INSTALL_DIR}."
fi
cat <<EOF

  URL        http://${host}:${port}
  Config     ${INSTALL_DIR}/.env
  Logs       cd ${INSTALL_DIR} && docker compose logs -f
  Stop       systemctl stop hypercube
  Start      systemctl start hypercube
  Uninstall  ${INSTALL_DIR}/uninstall.sh

EOF
