# HyperCube-agent Handoff: GPU Inventory

Date: 2026-05-12
Scope: `qkr7287/HyperCube-agent`
Core counterpart: HyperCube Track 1 / PR 1 GPU Inventory

This is the agent-side work required by HyperCube core. Do not implement it in
the HyperCube core repo.

## Issue Command

Create the tracking issue from a network-enabled environment:

```bash
gh issue create -R qkr7287/HyperCube-agent \
  -t "GPU inventory system_info subCommand for ML Workspace" \
  -b "$(cat docs/agent-gpu-inventory-handoff.md)"
```

## Goal

Implement `system_info` subCommand `gpu_inventory` so HyperCube core can
periodically upsert GPU devices and allocatable slices through
`/api/agents/{id}/gpus/`.

## Request

```json
{
  "type": "command",
  "requestId": "gpu-inventory:<agent_id>:<uuid>",
  "command": "system_info",
  "params": { "subCommand": "gpu_inventory" }
}
```

## Success Response

```json
{
  "type": "command_response",
  "requestId": "gpu-inventory:<agent_id>:<uuid>",
  "success": true,
  "data": {
    "gpus": [
      {
        "index": 0,
        "vendor": "NVIDIA",
        "name": "NVIDIA GeForce RTX 4090",
        "uuid": "GPU-...",
        "pciBusId": "00000000:82:00.0",
        "totalMemoryMb": 24564,
        "driverVersion": "550.54.15",
        "cudaVersion": "12.4",
        "migCapable": false,
        "migEnabled": false,
        "slices": [
          {
            "kind": "full",
            "deviceId": "GPU-...",
            "profile": "",
            "memoryMb": 24564
          }
        ]
      }
    ]
  }
}
```

## Required Behavior

- Echo the incoming `requestId`.
- If `nvidia-smi` is absent, return `success:false` with a clear error such as
  `nvidia-smi not available`.
- If the host has no GPU, return `success:true` with `data.gpus=[]`.
- For MIG-enabled GPUs, return MIG slices and do not return an allocatable full
  GPU slice for the same physical device.
- For MIG-disabled NVIDIA GPUs, return one `full` slice with `deviceId` equal to
  the GPU UUID accepted by NVIDIA container runtime.
- Non-NVIDIA/iGPU devices may be reported as devices, but should not expose an
  allocatable slice unless the agent can actually bind it into containers.
- Do not add external downloads or package installs at runtime.

## Validation Matrix

- no `nvidia-smi`
- no GPU
- one RTX 4090
- RTX 4090 plus non-NVIDIA/iGPU
- A100/H100 with MIG enabled
- H200
- Blackwell/B200 if available
- 8-GPU host
- offline/error/ECC state where `nvidia-smi` exposes it

## Regression Rules

- Existing `system_info` subCommands must keep their response shape.
- Existing `create_container`, metrics, control, logs, and exec commands must
  behave the same when GPU inventory is not requested.
- Requests without `subCommand: "gpu_inventory"` must not invoke GPU discovery.
