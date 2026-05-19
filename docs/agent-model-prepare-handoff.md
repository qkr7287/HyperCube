# HyperCube-agent Handoff: Model Prepare and Cache

Status as of 2026-05-13: operator reported issue #14 implemented, deployed,
and loopback-tested on `hypercube-agent-dev-63` and
`hypercube-agent-dev-16`. Keep this document as the protocol checklist and use
`docs/gpu-ml-workspace-validation.md` for the remaining server 63 end-to-end
core validation.

Do not implement this in the HyperCube core repo. This is the required
HyperCube-agent follow-up for GPU ML Workspace Track 4b.

## Required Agent Command

Implement `prepare_model_assets`.

- Echo `ModelPrepareJob.id` as `requestId` in all progress and response
  messages.
- Support `transferMode=backend_stream` first.
- Pull model bytes from HyperCube only:
  `GET /api/model-versions/<version-id>/content/`.
- Send the existing approved agent token as
  `Authorization: Bearer agent_...`.
- Never put the token in a query string.
- Reject `http://`, `https://`, `s3://`, `git://`, Hugging Face, public
  registries, package installs, and arbitrary user URLs as model sources.
- Write to a temp path, verify SHA256, then atomically move to an agent-local
  cache path.
- Read the checksum from `params.assets[].sha256`. The core also sends
  `params.assets[].checksum`, `params.assets[].source.sha256`, and
  `params.assets[].source.checksum` as compatibility aliases.
- Emit byte-based `command_progress` when possible.

## Required Create Container Extension

Honor `create_container.params.modelMounts[]`:

```json
{
  "versionId": "<model-version-id>",
  "assetSlug": "tiny-local-model",
  "sourcePath": "/var/lib/hypercube-agent/model-cache/tiny-local-model/v1",
  "mountPath": "/workspace/models/tiny-local-model@v1",
  "readOnly": true,
  "sha256": "<sha256>",
  "sizeBytes": 1234
}
```

Before container creation, verify every `sourcePath` exists in the verified
agent cache. Bind-mount it read-only. `create_container` must not copy large
models; it only mounts ready cache paths.

## Validation

- Prepare a tiny local file through HyperCube model upload.
- Approve a request selecting that model.
- Confirm the agent receives `prepare_model_assets` before `create_container`.
- Confirm checksum verification succeeds.
- Confirm `create_container` receives `modelMounts`.
- Confirm the running workspace sees the file under `/workspace/models/...`.
- Confirm requests without `modelMounts`, `workspace`, or `gpus` behave exactly
  as before.
