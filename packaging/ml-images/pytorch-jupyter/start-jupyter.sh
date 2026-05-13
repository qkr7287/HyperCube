#!/usr/bin/env bash
set -euo pipefail

PORT="${JUPYTER_PORT:-8888}"
BASE_URL="${JUPYTER_BASE_URL:-/}"
WORKDIR="${JUPYTER_WORKDIR:-/workspace}"
TOKEN="${JUPYTER_TOKEN:-}"

mkdir -p "${WORKDIR}"
cd "${WORKDIR}"

exec jupyter lab \
  --ip=0.0.0.0 \
  --port="${PORT}" \
  --ServerApp.base_url="${BASE_URL}" \
  --ServerApp.root_dir="${WORKDIR}" \
  --ServerApp.token="${TOKEN}" \
  --ServerApp.allow_remote_access=True \
  --ServerApp.allow_origin="*" \
  --no-browser \
  --allow-root
