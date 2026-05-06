#!/usr/bin/env bash
# End-to-end install rehearsal inside the air-gap container.
# Pre-seeds /opt/hypercube/.env (skip interactive prompt) and runs the .run.
#
# Usage (from a shell that can reach the docker socket — PowerShell or WSL):
#   bash packaging/test-airgap/run-validation.sh
#
# Pipes everything to /tmp/airgap-install.log inside the container so a
# truncated terminal can't lose the trace.

set +e

CONTAINER=hc-airgap-test

if ! docker inspect "${CONTAINER}" >/dev/null 2>&1; then
    echo "Container ${CONTAINER} not found. Start it first:"
    echo "  docker compose -f packaging/test-airgap/docker-compose.yml up -d --build"
    exit 1
fi

echo "==> Pre-seeding /opt/hypercube/.env in container"
docker exec "${CONTAINER}" bash -c '
set -e
mkdir -p /opt/hypercube
cat > /opt/hypercube/.env <<EOF
IMAGE_TAG=latest
HC_HOST=127.0.0.1
HC_PORT=7003
DJANGO_SECRET_KEY=airgap-validation-key-50chars-not-secure-test
DJANGO_ALLOWED_HOSTS=*
CORS_ALLOWED_ORIGINS=
CORS_ALLOW_ALL_ORIGINS=true
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:7003
DB_NAME=hypercube
DB_USER=hypercube
DB_PASSWORD=airgap-test-password
EOF
chmod 600 /opt/hypercube/.env
'

echo "==> Running installer (logs -> /tmp/airgap-install.log inside container)"
docker exec "${CONTAINER}" bash -c '
/root/hypercube-1.0-ubuntu2404.run 2>&1 | tee /tmp/airgap-install.log
'
INSTALL_EXIT=$?

echo
echo "==> Installer exit code: ${INSTALL_EXIT}"
echo "==> Container post-state:"
docker exec "${CONTAINER}" bash -c '
echo "--- docker version ---"
docker --version 2>&1 || echo "docker not installed"
echo "--- systemctl status docker ---"
systemctl is-active docker 2>&1 || true
echo "--- docker ps -a ---"
docker ps -a --format "table {{.Names}}\t{{.Status}}" 2>&1 || true
echo "--- healthcheck ---"
curl -fsS --max-time 5 http://127.0.0.1:7003/api/health/ 2>&1 || echo "HEALTHCHECK_FAIL"
echo "--- last 20 lines of install log ---"
tail -20 /tmp/airgap-install.log 2>&1 || true
'
