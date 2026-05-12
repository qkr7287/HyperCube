# GPU Workspace Reconcile Runbook

Use this when a GPU workspace request is `needs_reconcile` or `ambiguous`.

## When This Happens

- Backend timed out waiting for `create_container`.
- Agent disconnected after receiving a command.
- Backend cannot prove whether the container was created.
- GPU allocation, Redis token, and container row may disagree.

## Operator Steps

1. Identify the `ContainerRequest.id`, target agent, requested container name, GPU slice ids, and `workspace_token_ref`.
2. Check whether the agent is online in HyperCube.
3. On the agent host, list containers and search for the expected name or labels.
4. If the container exists and is healthy:
   - Attach or repair the `Container` row.
   - Move matching `GpuAllocation` rows to `active`.
   - Preserve the Redis workspace token if it still exists.
   - If the token is missing, restart the workspace with a rotated token.
5. If the container exists but should not:
   - Stop/delete the container through the agent or manually on the host.
   - Mark `GpuAllocation` rows `released` or `failed`.
   - Delete the Redis workspace token.
   - Append the action to `ContainerRequest.deployment_log`.
6. If the container does not exist:
   - Mark the request `failed`.
   - Mark reserved allocations `failed`.
   - Delete the Redis workspace token.
   - Append the reason to `deployment_log`.

## Do Not

- Do not blindly release a GPU allocation until the agent host has been checked.
- Do not expose the plaintext Jupyter token in logs or screenshots.
- Do not retry `create_container` until the existing ambiguous state is resolved.

## Follow-Up

- Record the root cause: agent offline, image missing, Jupyter startup failure, network timeout, or unknown.
- If this repeats for the same agent, disable ML workspace scheduling on that agent until reachability and runtime are verified.
