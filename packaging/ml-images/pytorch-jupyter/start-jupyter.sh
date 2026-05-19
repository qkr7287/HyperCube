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
#
# Copy the shipped quickstart notebook into /workspace if the user hasn't
# replaced it yet. Lets the user open Jupyter → double-click 00-quickstart.ipynb
# → Run All to see the gradio UI embedded via jupyter-server-proxy.
# -----------------------------------------------------------------------------
NOTEBOOK_SRC="/opt/hc/00-quickstart.ipynb"
NOTEBOOK_DST="${WORKDIR}/00-quickstart.ipynb"
if [[ -f "${NOTEBOOK_SRC}" ]] && [[ ! -f "${NOTEBOOK_DST}" ]]; then
  cp "${NOTEBOOK_SRC}" "${NOTEBOOK_DST}"
  echo "[hc-entrypoint] seeded quickstart notebook"
fi

# -----------------------------------------------------------------------------
# Auto-launch Qwen2-VL gradio app in the background if we see its model.
#
# Detected by directory name (qwen2-vl-2b-instruct). When matched, run the
# launcher which loads transformers + serves a gradio UI on 127.0.0.1:7860.
# jupyter-server-proxy makes it reachable at <jupyter base>/proxy/7860/.
# -----------------------------------------------------------------------------
QWEN_DIR="${WORKDIR}/qwen2-vl-2b-instruct"
LAUNCHER="/opt/hc/launch_qwen2vl.py"
if [[ -d "${QWEN_DIR}" ]] && [[ -f "${LAUNCHER}" ]]; then
  echo "[hc-entrypoint] launching Qwen2-VL gradio app on :7860 (background)"
  HC_QWEN2VL_MODEL="${QWEN_DIR}" \
    nohup python "${LAUNCHER}" \
      >"${WORKDIR}/.hc-qwen2vl.log" 2>&1 &
fi

# -----------------------------------------------------------------------------
# Foreground: JupyterLab. ServerApp.allow_remote_access lets the HyperCube
# workspace proxy talk to us across the bridge network.
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
