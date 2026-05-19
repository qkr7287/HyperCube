# HyperCube-agent Handoff: GPU create_container

Date: 2026-05-12
Scope: `qkr7287/HyperCube-agent`
Core counterpart: HyperCube Track 2 / PR 2 Full GPU Allocation

This is the agent-side work required by HyperCube core. Do not implement it in
the HyperCube core repo.

## Goal

Extend `create_container` so HyperCube core can pass reserved GPU device ids to
the agent. Existing `create_container` calls without `gpus` must continue to
behave exactly as before.

## Request Extension

```json
{
  "type": "command",
  "requestId": "<ContainerRequest.id>",
  "command": "create_container",
  "params": {
    "image": "hypercube/ml-pytorch-jupyter:cuda12.4-airgap",
    "name": "hc-abc12345",
    "env": {},
    "ports": [],
    "volumes": [],
    "gpus": [
      { "deviceId": "GPU-...", "kind": "full" }
    ]
  }
}
```

## Required Behavior

- Treat missing or empty `gpus` as a non-GPU container.
- Before container creation, verify each `gpus[].deviceId` is present on the
  host and accepted by NVIDIA container runtime.
- Add Docker NVIDIA `DeviceRequests` for the requested device ids.
- Return `success:false` with a clear error if the requested device is missing,
  `nvidia-smi` is unavailable, or NVIDIA container runtime is not configured.
- Do not pull public images. The image must already exist locally or be
  available from an operator-approved internal offline registry.
- Do not change existing metrics, control, logs, exec, or non-GPU
  `create_container` behavior.

## Core Lifecycle Expectation

HyperCube core creates `GpuAllocation(status="reserved")` before dispatch.
The core marks the allocation `active` only after `create_container` succeeds.
If this command fails, the core marks reserved allocations failed.

## Validation

- non-GPU `create_container` regression
- one full GPU by UUID
- missing GPU UUID fails clearly
- host without NVIDIA runtime fails clearly
- requested image missing fails fast without public pull
