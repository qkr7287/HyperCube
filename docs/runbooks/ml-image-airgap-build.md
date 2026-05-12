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

## Import

On each GPU agent host:

```bash
docker load -i hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar
docker image inspect hypercube/ml-pytorch-jupyter:cuda12.4-airgap
```

If an internal offline registry exists, push the loaded image there and pin templates to the internal registry tag.

## Smoke Test

Run a GPU smoke test on the target agent host:

```bash
docker run --rm --gpus all hypercube/ml-pytorch-jupyter:cuda12.4-airgap nvidia-smi
```

Run a Jupyter startup smoke test:

```bash
docker run --rm -p 8888:8888 \
  -e JUPYTER_TOKEN=test-token \
  -e JUPYTER_BASE_URL=/workspace/test/ \
  hypercube/ml-pytorch-jupyter:cuda12.4-airgap
```

Then verify that the backend or operator machine can reach the mapped port inside the airgapped network.

## Validation Gate

PR 3 is not complete until:

- At least one Jupyter image is present on the selected GPU agent.
- `image_inspect` or `docker image inspect` confirms the image.
- The image starts Jupyter with the configured base URL and token.
- External egress from the workspace is blocked or explicitly marked `not_enforced`.
