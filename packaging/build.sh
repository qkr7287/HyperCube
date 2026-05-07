#!/usr/bin/env bash
# Build the air-gapped HyperCube installer (.sh).
#
# Output: dist/hypercube-<VERSION>.sh
#
# Docker engine is NOT bundled — the target host must have docker + compose
# plugin installed first (apt/dnf/whatever the distro provides). This makes
# the installer fully OS-agnostic: works on Ubuntu, RHEL, Rocky, AlmaLinux,
# Debian, SUSE, etc., as long as docker is present.
#
# Build host requires:
#   - docker (to pull/save HyperCube images)
#   - makeself (to build the self-extractor)

set -euo pipefail

VERSION="${VERSION:-1.0}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG_DIR="${REPO_ROOT}/packaging"
WORK_DIR="${REPO_ROOT}/build/installer-${VERSION}"
DIST_DIR="${REPO_ROOT}/dist"
RUN_FILE="${DIST_DIR}/hypercube-${VERSION}.sh"

IMAGES=(
    "ghcr.io/qkr7287/hypercube-backend:${IMAGE_TAG}"
    "ghcr.io/qkr7287/hypercube-nginx:${IMAGE_TAG}"
    "pgvector/pgvector:pg16"
    "redis:7-alpine"
)

log() { echo "[build] $*"; }

require() {
    command -v "$1" >/dev/null 2>&1 || { echo "missing tool: $1" >&2; exit 1; }
}

require docker
require makeself

log "cleaning ${WORK_DIR}"
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}/images" "${WORK_DIR}/app"

log "ensuring HyperCube images are present (pull only if missing)"
for img in "${IMAGES[@]}"; do
    if docker image inspect "${img}" >/dev/null 2>&1; then
        log "  cached: ${img}"
    else
        log "  pulling: ${img}"
        docker pull "${img}"
    fi
done

log "saving images to tarball (this may take a few minutes)"
docker save "${IMAGES[@]}" -o "${WORK_DIR}/images/hypercube-images.tar"

log "staging app files"
cp "${REPO_ROOT}/deploy/docker-compose.yml" "${WORK_DIR}/app/"
cp "${REPO_ROOT}/deploy/.env.example" "${WORK_DIR}/app/"
cp "${PKG_DIR}/systemd/hypercube.service" "${WORK_DIR}/app/"

log "staging installer scripts"
cp "${PKG_DIR}/install.sh" "${WORK_DIR}/install.sh"
cp "${PKG_DIR}/uninstall.sh" "${WORK_DIR}/uninstall.sh"
cp "${PKG_DIR}/env-generate.sh" "${WORK_DIR}/env-generate.sh"
chmod +x "${WORK_DIR}"/*.sh

log "writing version manifest"
cat > "${WORK_DIR}/VERSION" <<EOF
hypercube_version=${VERSION}
image_tag=${IMAGE_TAG}
docker_engine=external (operator-installed)
built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
built_from=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)
EOF

log "creating self-extracting archive"
mkdir -p "${DIST_DIR}"
makeself --gzip --notemp \
    "${WORK_DIR}" \
    "${RUN_FILE}" \
    "HyperCube ${VERSION}" \
    ./install.sh

size=$(du -h "${RUN_FILE}" | cut -f1)
log "done: ${RUN_FILE} (${size})"
