# Agent Message Schema v2 — networks & mounts on container list

Status: **proposed, Agent-side not yet implemented.** Backend + Frontend
keep working without it (new fields are optional).

## Motivation

The new topology needs to draw **Network hubs** and **Volume hubs** in
addition to the existing stack (compose project) hubs. That data is
already in `docker inspect`, but the per-tick `containers` WS message
only carries `id / name / image / state / status / ports / created /
labels`. Frontend has no way to build the hubs without fetching every
container individually, which does not scale.

## Change

On every `containers` message each container object gains two optional
fields:

```jsonc
{
  "id": "b9e8962d9acd",
  "name": "hypercube-agent-agent-1",
  "image": "hypercube-agent-agent",
  "state": "running",
  "status": "Up About an hour",
  "ports": [],
  "created": 1776397672,
  "labels": { "...": "..." },

  // NEW
  "networks": ["hypercube-agent_default"],
  "mounts": [
    { "name": "hypercube-agent_data", "type": "volume" }
  ]
}
```

### networks

- Array of strings — the keys of `NetworkSettings.Networks` from
  `docker inspect`.
- Exclude built-in `bridge`, `host`, `none` at the Agent side. They
  are noise and every container is attached to at least one of them.

### mounts

- Array of `{ name, type }`.
- `type === "volume"` only. Bind mounts are skipped — host paths are
  too noisy, and compose bind directories already group containers
  by stack.
- `name` = the Docker named volume (the value the daemon exposes as
  `Mounts[i].Name`).

## Non-requirements

- No change to message type, envelope, or delta-sync semantics.
- No new REST endpoint.
- No change to on-demand `inspect` command — it keeps returning the
  full Docker inspect payload.

## Compatibility

- Fields are **optional**. Absent / `undefined` / `[]` means "Agent
  still on v1" and the topology simply skips network + volume hubs.
  No visual regression; the stack hub keeps working.

## Verification plan

1. After Agent patch, inspect a cached payload:
   `docker exec hc-redis redis-cli -n 1 GET "server:<id>:containers"`
   — each container should include `networks` and `mounts`.
2. Frontend topology Phase 3 enables Network / Volume hubs the moment
   the data arrives.
