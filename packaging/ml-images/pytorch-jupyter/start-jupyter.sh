#!/usr/bin/env bash
set -euo pipefail

PORT="${JUPYTER_PORT:-8888}"
BASE_URL="${JUPYTER_BASE_URL:-/}"
WORKDIR="${JUPYTER_WORKDIR:-/workspace}"
TOKEN="${JUPYTER_TOKEN:-}"

mkdir -p "${WORKDIR}"
cd "${WORKDIR}"

# -----------------------------------------------------------------------------
# Auto-extract mounted model archives.
#
# HyperCube mounts model files into /workspace/models/<asset-slug>@<version>/.
# Most multimodal models we ship are HuggingFace directories packed as
# .tar.gz / .tgz, so extract them to /workspace/<asset-slug>/ on first run.
# Skipped if the destination already exists (idempotent across restarts).
# -----------------------------------------------------------------------------
if [[ -d "${WORKDIR}/models" ]]; then
  for model_dir in "${WORKDIR}/models/"*/; do
    [[ -d "${model_dir}" ]] || continue
    asset_at_version="$(basename "${model_dir}")"
    asset_slug="${asset_at_version%@*}"
    dest="${WORKDIR}/${asset_slug}"
    if [[ -d "${dest}" ]] && [[ -n "$(ls -A "${dest}" 2>/dev/null)" ]]; then
      echo "[hc-entrypoint] model already extracted: ${dest}"
      continue
    fi
    archive=""
    for cand in "${model_dir}"*.tar.gz "${model_dir}"*.tgz "${model_dir}"*.tar; do
      [[ -f "${cand}" ]] && { archive="${cand}"; break; }
    done
    if [[ -z "${archive}" ]]; then
      echo "[hc-entrypoint] no archive in ${model_dir}, skipping"
      continue
    fi
    echo "[hc-entrypoint] extracting ${archive} -> ${dest}"
    mkdir -p "${dest}"
    # The archive's top-level directory often equals the asset name; if so,
    # strip it so files land directly in ${dest} (parents=1 mimics --strip 1).
    tar -xf "${archive}" -C "${dest}" --strip-components=1 2>/dev/null || \
      tar -xf "${archive}" -C "${dest}"
    echo "[hc-entrypoint] extracted: $(ls "${dest}" | head -5 | tr '\n' ' ')"
  done
fi

# -----------------------------------------------------------------------------
# Seed quickstart notebook.
# -----------------------------------------------------------------------------
NOTEBOOK_SRC="/opt/hc/00-quickstart.ipynb"
NOTEBOOK_DST="${WORKDIR}/00-quickstart.ipynb"
if [[ -f "${NOTEBOOK_SRC}" ]] && [[ ! -f "${NOTEBOOK_DST}" ]]; then
  cp "${NOTEBOOK_SRC}" "${NOTEBOOK_DST}"
  echo "[hc-entrypoint] seeded quickstart notebook"
fi

# -----------------------------------------------------------------------------
# Auto-launch the inference recipe selected at container create.
#
# HC_LAUNCHER_RECIPE + HC_MODEL_DIR are injected by the backend whenever the
# template has a non-"none" launcher_recipe_id. /opt/hc/launch.py reads the
# recipe id from launcher_recipes.json and loads the right transformers
# class + gradio app, listening on 127.0.0.1:7860 (root_path=/proxy/7860 so
# jupyter-server-proxy forwards <workspace>/proxy/7860/ correctly).
# -----------------------------------------------------------------------------
LAUNCHER="/opt/hc/launch.py"
LAUNCHER_RECIPE="${HC_LAUNCHER_RECIPE:-none}"
if [[ "${LAUNCHER_RECIPE}" != "none" ]] && [[ -f "${LAUNCHER}" ]]; then
  echo "[hc-entrypoint] launching recipe=${LAUNCHER_RECIPE} model_dir=${HC_MODEL_DIR:-?} (background)"
  nohup python "${LAUNCHER}" \
    >"${WORKDIR}/.hc-launch.log" 2>&1 &
fi

# -----------------------------------------------------------------------------
# Foreground: JupyterLab.
# -----------------------------------------------------------------------------
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
