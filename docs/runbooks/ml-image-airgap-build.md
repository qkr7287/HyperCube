# ML Image Airgap Build Runbook

This runbook defines the offline image track for GPU ML Workspace.

## Scope

Build and import the platform ML images required by templates:

- `hypercube/ml-pytorch-jupyter:<pinned>-airgap`
- `hypercube/ml-tensorflow-jupyter:<pinned>-airgap`
- `hypercube/ml-vllm-openai:<pinned>-airgap`
- `hypercube/ml-code-server-cuda:<pinned>-airgap`

At least one Jupyter image must be imported before PR 3 workspace validation.

## Responsibilities

- Platform/operator builds images in a networked build environment.
- Platform/operator records image digest, CUDA version, Python version, included packages, and base image provenance.
- Platform/operator moves tar archives into the airgapped site through the approved offline media process.
- GPU host operator loads images on each target agent host.

## Build Output

Each image build must produce:

- Image tag.
- Image digest.
- `docker save` tar archive.
- Package manifest.
- CUDA/runtime notes.
- Smoke-test command.

## PyTorch Jupyter Image Build

HyperCube provides the image wrapper under
`packaging/ml-images/pytorch-jupyter/`. The wrapper expects an operator-approved
PyTorch CUDA 12.4 runtime base image and adds JupyterLab plus the HyperCube
workspace entrypoint.

On a networked build machine:

```bash
cd /path/to/HyperCube

TAG=hypercube/ml-pytorch-jupyter:cuda12.4-airgap \
OUT=hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar \
  bash packaging/ml-images/build-pytorch-jupyter.sh
```

By default the build script uses
`pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`. Override it with
`BASE_IMAGE=<approved-pytorch-cuda12.4-runtime-image>` if the deployment has a
separately approved base. The base image must already include Python, PyTorch,
CUDA runtime, and cuDNN compatible with the target host driver. Do not use
`nvidia/cuda:*base*` alone: that image family does not include PyTorch or
Jupyter.

Record the selected base image tag/digest and the generated image id in the
deployment report.

## Import

On each GPU agent host:

```bash
docker load -i /path/to/hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar
docker image inspect hypercube/ml-pytorch-jupyter:cuda12.4-airgap
```

If an internal offline registry exists, push the loaded image there and pin templates to the internal registry tag.

## Smoke Test

Run GPU smoke tests on the target agent host. The image entrypoint starts
Jupyter, so diagnostics must override the entrypoint:

```bash
docker run --rm --gpus all \
  --entrypoint nvidia-smi \
  hypercube/ml-pytorch-jupyter:cuda12.4-airgap

docker run --rm --gpus all \
  --entrypoint python \
  hypercube/ml-pytorch-jupyter:cuda12.4-airgap \
  -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

Run a Jupyter startup smoke test:

```bash
docker run --rm -p 8888:8888 \
  -e JUPYTER_TOKEN=test-token \
  -e JUPYTER_BASE_URL=/workspace/test/ \
  -e JUPYTER_WORKDIR=/workspace \
  hypercube/ml-pytorch-jupyter:cuda12.4-airgap
```

Then verify that the backend or operator machine can reach the mapped port inside the airgapped network.

## Validation Gate

PR 3 is not complete until:

- At least one Jupyter image is present on the selected GPU agent.
- `image_inspect` or `docker image inspect` confirms the image.
- The image starts Jupyter with the configured base URL and token.
- The mounted model directory rejects writes, for example
  `touch /workspace/models/<model-dir>/write-test` fails with a read-only file
  system error. Do not use `/workspace/models/write-test` for this check; the
  parent directory can be writable while the model bind mount is read-only.
- External egress from the workspace is blocked or explicitly marked `not_enforced`.
