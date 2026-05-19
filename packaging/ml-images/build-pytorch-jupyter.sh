#!/usr/bin/env bash
set -euo pipefail

TAG="${TAG:-hypercube/ml-pytorch-jupyter:cuda12.4-airgap}"
BASE_IMAGE="${BASE_IMAGE:-pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime}"
OUT="${OUT:-hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar}"
CONTEXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMG_DIR="${CONTEXT_DIR}/packaging/ml-images/pytorch-jupyter"

# Strip CRLF that mutagen / Windows clones sometimes leave on bash + py + ipynb
# files. set -o pipefail / json parsers blow up on them and the failure mode
# is hard to spot inside the running container.
for f in \
    "${IMG_DIR}/start-jupyter.sh" \
    "${IMG_DIR}/Dockerfile" \
    "${IMG_DIR}/launch.py" \
    "${IMG_DIR}/launcher_recipes.json" \
    "${IMG_DIR}/00-quickstart.ipynb"; do
  [[ -f "${f}" ]] || continue
  sed -i 's/\r$//' "${f}"
done

# Regenerate launcher_recipes.json from the backend source-of-truth so the
# image never drifts from the wizard / serializer view of the catalogue.
if command -v python3 >/dev/null 2>&1; then
  HC_REPO_ROOT="${CONTEXT_DIR}" python3 - <<'PY'
import os, sys
from pathlib import Path
ROOT = Path(os.environ["HC_REPO_ROOT"])
sys.path.insert(0, str(ROOT / "backend"))
from apps.containers.launcher_recipes import export_catalogue_json
out = ROOT / "packaging" / "ml-images" / "pytorch-jupyter" / "launcher_recipes.json"
out.write_text(export_catalogue_json(), encoding="utf-8")
print(f"[build] regenerated {out}")
PY
fi

docker build \
  --build-arg BASE_IMAGE="${BASE_IMAGE}" \
  -t "${TAG}" \
  -f "${IMG_DIR}/Dockerfile" \
  "${IMG_DIR}"

docker run --rm --entrypoint python "${TAG}" -c \
  "import torch, jupyterlab; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('jupyterlab', jupyterlab.__version__)"

docker save "${TAG}" -o "${OUT}"
docker image inspect "${TAG}" --format 'image={{.RepoTags}} id={{.Id}} size={{.Size}}'
printf 'saved=%s\n' "${OUT}"
