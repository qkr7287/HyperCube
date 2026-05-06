#!/usr/bin/env bash
# Build the air-gapped installer (.run) for Ubuntu 24.04 LTS.
# Output: dist/hypercube-<VERSION>-ubuntu2404.run
#
# Requires on the build host:
#   - docker (any version)
#   - makeself (apt-get install makeself)
#
# The build pulls Docker .debs inside an ubuntu:24.04 container, so the
# build host distro/version does not matter — only docker + makeself do.

set -euo pipefail

VERSION="${VERSION:-1.0}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
UBUNTU_VERSION="${UBUNTU_VERSION:-24.04}"

case "${UBUNTU_VERSION}" in
    22.04) UBUNTU_CODENAME=jammy ;;
    24.04) UBUNTU_CODENAME=noble ;;
    *) echo "Unsupported UBUNTU_VERSION: ${UBUNTU_VERSION} (supported: 22.04, 24.04)" >&2; exit 1 ;;
esac

TARGET="ubuntu${UBUNTU_VERSION//./}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PKG_DIR="${REPO_ROOT}/packaging"
WORK_DIR="${REPO_ROOT}/build/installer-${VERSION}-${TARGET}"
DIST_DIR="${REPO_ROOT}/dist"
RUN_FILE="${DIST_DIR}/hypercube-${VERSION}-${TARGET}.run"

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
mkdir -p "${WORK_DIR}/docker-debs" "${WORK_DIR}/images" "${WORK_DIR}/app"

log "downloading Docker .debs for ${UBUNTU_CODENAME} inside ubuntu:${UBUNTU_VERSION} container"
docker run --rm \
    -v "${WORK_DIR}/docker-debs:/out" \
    -v "${PKG_DIR}/download-docker-debs.sh:/download.sh:ro" \
    -e "UBUNTU_CODENAME=${UBUNTU_CODENAME}" \
    "ubuntu:${UBUNTU_VERSION}" bash /download.sh

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

log "staging installer scripts (substituting target codename)"
sed -e "s/__CODENAME__/${UBUNTU_CODENAME}/g" \
    -e "s/__VERSION__/${UBUNTU_VERSION} LTS/g" \
    "${PKG_DIR}/install.sh" > "${WORK_DIR}/install.sh"
cp "${PKG_DIR}/uninstall.sh" "${WORK_DIR}/uninstall.sh"
cp "${PKG_DIR}/env-generate.sh" "${WORK_DIR}/env-generate.sh"
chmod +x "${WORK_DIR}"/*.sh

log "writing version manifest"
cat > "${WORK_DIR}/VERSION" <<EOF
hypercube_version=${VERSION}
image_tag=${IMAGE_TAG}
target=${TARGET}
ubuntu_codename=${UBUNTU_CODENAME}
built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
built_from=$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)
EOF

log "creating self-extracting archive"
mkdir -p "${DIST_DIR}"
makeself --gzip --notemp \
    "${WORK_DIR}" \
    "${RUN_FILE}" \
    "HyperCube ${VERSION} (Ubuntu ${UBUNTU_VERSION})" \
    ./install.sh

size=$(du -h "${RUN_FILE}" | cut -f1)
log "done: ${RUN_FILE} (${size})"
