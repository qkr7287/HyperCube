#!/usr/bin/env bash
# Local validation harness for the .run installer.
# Run inside WSL Ubuntu 24.04 as root.
#
# Usage (from PowerShell):
#   wsl -d Ubuntu -u root -- bash "/mnt/c/Users/agics/Desktop/workspace/01. git/HyperCube/packaging/test-install.sh"
#
# Or paste this in a Claude prompt:
#   ! wsl -d Ubuntu -u root -- bash "/mnt/c/Users/agics/Desktop/workspace/01. git/HyperCube/packaging/test-install.sh"

set -e

REPO_ROOT="/mnt/c/Users/agics/Desktop/workspace/01. git/HyperCube"
RUN_FILE="${REPO_ROOT}/dist/hypercube-1.0-ubuntu2404.run"

if [[ ! -f "${RUN_FILE}" ]]; then
    echo "ERROR: ${RUN_FILE} not found. Build first: bash packaging/build.sh"
    exit 1
fi

echo "==> 1. Pre-seed /opt/hypercube/.env (skip interactive prompt)"
mkdir -p /opt/hypercube
cat > /opt/hypercube/.env <<'EOF'
IMAGE_TAG=latest
HC_HOST=127.0.0.1
HC_PORT=7003
DJANGO_SECRET_KEY=test-validation-key-not-for-production-use-50chars
DJANGO_ALLOWED_HOSTS=*
CORS_ALLOWED_ORIGINS=
CORS_ALLOW_ALL_ORIGINS=true
CSRF_TRUSTED_ORIGINS=http://127.0.0.1:7003
DB_NAME=hypercube
DB_USER=hypercube
DB_PASSWORD=test-password-validation
EOF
chmod 600 /opt/hypercube/.env

echo "==> 2. Copy installer to /tmp (avoid Windows path quirks)"
cp "${RUN_FILE}" /tmp/
cd /tmp
chmod +x hypercube-1.0-ubuntu2404.run

echo "==> 3. Run installer"
./hypercube-1.0-ubuntu2404.run

echo
echo "==> 4. Health check via curl (after a small grace period)"
sleep 5
if curl -fsS --max-time 5 http://127.0.0.1:7003/api/health/ ; then
    echo
    echo "==> SUCCESS: backend responded healthy"
else
    echo
    echo "==> WARN: health check failed; inspecting containers"
    docker ps --filter name=hc- --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    echo
    echo "Backend logs (last 30 lines):"
    docker logs hc-backend --tail 30 2>&1 || true
fi

echo
echo "==> Done. To clean up:"
echo "    wsl -d Ubuntu -u root -- bash /opt/hypercube/uninstall.sh"
