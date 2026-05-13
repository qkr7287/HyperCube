# Model Prepare API

Track 4b adds the agent-cache and model-prepare part of GPU ML Workspace v1.

## User/API Surface

- `GET /api/model-versions/cache-status/?agent=<uuid>&versions=<csv>`
  returns cache status for the selected target agent.
- `GET /api/model-version-caches/` returns read-only per-agent cache rows.
- `GET /api/model-prepare-jobs/` returns read-only prepare job rows.
- `POST /api/requests/` accepts `model_version_ids` in create requests.

Example request payload:

```json
{
  "action": "create",
  "template": "<template-id>",
  "target_agent": "<agent-id>",
  "gpu_slice_ids": [1],
  "model_version_ids": ["<model-version-id>"],
  "requested_max_runtime_hours": 24
}
```

## Agent Internal Content Endpoint

```text
GET /api/model-versions/<model-version-id>/content/
Authorization: Bearer agent_...
```

The endpoint streams the server-local model file only when the approved agent
has an active `ModelPrepareJob` for the same model version. It also returns:

- `X-HyperCube-Model-Version`
- `X-HyperCube-Model-SHA256`
- `Content-Length`

## Approval Flow

1. Admin approves a `ContainerRequest`.
2. Backend reserves GPU slices.
3. Backend creates or attaches `ModelPrepareJob` rows for missing agent caches.
4. Backend dispatches `prepare_model_assets` with `ModelPrepareJob.id` as
   `requestId`.
5. Agent streams from HyperCube, verifies SHA256, atomically moves into its
   local cache, and returns `cachePath`.
6. Backend marks `ModelVersionCache.ready`.
7. When all selected models are ready, backend dispatches `create_container`
   with read-only `modelMounts`.

No external model URL, Hugging Face, Git, S3, package install, or public
registry path is valid in this flow.
