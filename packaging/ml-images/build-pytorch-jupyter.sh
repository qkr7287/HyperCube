#!/usr/bin/env bash
set -euo pipefail

TAG="${TAG:-hypercube/ml-pytorch-jupyter:cuda12.4-airgap}"
BASE_IMAGE="${BASE_IMAGE:-pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime}"
OUT="${OUT:-hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar}"
CONTEXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

docker build \
  --build-arg BASE_IMAGE="${BASE_IMAGE}" \
  -t "${TAG}" \
  -f "${CONTEXT_DIR}/packaging/ml-images/pytorch-jupyter/Dockerfile" \
  "${CONTEXT_DIR}/packaging/ml-images/pytorch-jupyter"

docker run --rm --entrypoint python "${TAG}" -c \
  "import torch, jupyterlab; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available()); print('jupyterlab', jupyterlab.__version__)"

docker save "${TAG}" -o "${OUT}"
docker image inspect "${TAG}" --format 'image={{.RepoTags}} id={{.Id}} size={{.Size}}'
printf 'saved=%s\n' "${OUT}"
