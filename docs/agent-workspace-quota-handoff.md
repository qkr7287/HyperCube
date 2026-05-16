# HyperCube-agent Handoff: Workspace Quota (XFS prjquota on loop file)

Date: 2026-05-16
Scope: `qkr7287/HyperCube-agent`
Core counterpart: HyperCube container resource limits + workspace quota slice
Tracking issue: https://github.com/qkr7287/HyperCube-agent/issues/16
Superseded PR: `#17` (LVM thin implementation — rework into a new PR or force-push the same branch with the changes below).

Core implementation baseline:

```text
agents/0009_workspace_quota_capacity   # rename lvm_pool_size_gb → workspace_pool_total_gb + add free/mount/hard_enforcement
containers/0012_workspace_quota_metadata  # add workspace_project_id + widen workspace_device to 255
```

Core-side tests already green (2026-05-16):

```text
backend: 100 tests OK
frontend vitest: 58 passed
frontend svelte-check: 0 errors
```

Do not change HyperCube core from this issue unless the backend-agent
contract proves impossible. Core-side contract, docs, migrations,
backend tests, frontend tests, and Playwright E2E are already pushed.

## Why the rewrite

The earlier LVM thin plan (`#17`) is blocked by the host: server-63
has no `lvm2`, the operator response on partition reshape is pending,
and there is no `/mnt/datasets` / `/mnt/models`. Plan moved to option
4b on 2026-05-16:

- Loop-mounted xfs file at `/var/lib/hypercube/workspaces` with
  `prjquota`.
- Per-container subdir gets its own XFS project id + `setquota`
  hard limit.
- Zero reboot / partition reshape; 5-line operator host setup
  (see `docs/runbooks/workspace-quota-full-validation.md` §1).

## Required Agent Work

### 1. `src/workspace-lvm.ts` → `src/workspace-quota.ts`

Rename file and rewrite the prepare/teardown loop. New signature:

```ts
export async function prepareContainerWorkspace(opts: {
  shortId: string;          // 12-char container id
  hardGb: number;           // backend payload `params.workspace.hardGb`
  mountTarget: string;      // backend payload `params.workspace.mountTarget`, default "/workspace"
}): Promise<{
  path: string;             // /var/lib/hypercube/workspaces/<shortId>
  projectId: number;        // stable project id derived from shortId
  hardGb: number;
}> {
  const root = process.env.WORKSPACE_QUOTA_MOUNT
    ?? "/var/lib/hypercube/workspaces";
  const path = `${root}/${opts.shortId}`;
  const projectId = projectIdFor(opts.shortId);  // see below

  await mkdir(path, { recursive: true });
  await runQuotaCmd(["project", "-s", "-p", path, `${projectId}`]);
  await setQuota(projectId, opts.hardGb);
  return { path, projectId, hardGb: opts.hardGb };
}
```

`projectIdFor(shortId)` must be deterministic and collision-resistant.
Recommended: first 6 hex chars of `sha256(shortId)` → integer in
`[100000, 16_877_215]`. Persist a mapping file
`/var/lib/hypercube/workspaces/.projects` in the format
`<projectId>:hc-<shortId>` so `xfs_quota report -h` shows useful names.

`setQuota` runs:

```bash
xfs_quota -x -c "limit -p bsoft=${hardGb}g bhard=${hardGb}g <projectId>" /var/lib/hypercube/workspaces
```

Both `bsoft` and `bhard` are set to the same `${hardGb}g` value so a
single threshold blocks writes — matches user expectation that the
limit is a hard cap.

**Do NOT use `setquota -P <id> <hardBytes> <hardBytes> 0 0 <mount>`.**
The `block-soft` / `block-hard` arguments of `setquota` are 1 KiB
blocks, not bytes. Passing `hardGb * 1024**3` (bytes) directly is
interpreted as KiB and silently inflates the cap by 1024× (a
10 GB request became 10 TiB in PR #17's first cut — see
`qkr7287/HyperCube-agent#16`). Always prefer the `xfs_quota -x -c
"limit -p ..."` form with explicit `g` / `m` suffix.

Teardown (called from `delete_container`):

```ts
export async function teardownContainerWorkspace(opts: {
  shortId: string;
}): Promise<void> {
  const root = process.env.WORKSPACE_QUOTA_MOUNT
    ?? "/var/lib/hypercube/workspaces";
  const path = `${root}/${opts.shortId}`;
  const projectId = projectIdFor(opts.shortId);
  await setQuota(projectId, 0);                 // clears the limit
  await runQuotaCmd(["project", "-C", "-p", path, `${projectId}`]);
  await rm(path, { recursive: true, force: true });
}
```

Tooling: use `child_process.execFile` (never shell-string) and bubble
stderr into the agent's existing error reporting. `xfs_quota` exits 0
on success and prints diagnostics to stderr on failure.

### 2. Bind into `create_container`

In whichever module reads `params.workspace` (currently
`src/commands/create_container.ts` per the LVM branch), replace the
`lvcreate / mkfs / mount` block with:

```ts
const ws = await prepareContainerWorkspace({
  shortId: dockerId.slice(0, 12),
  hardGb: params.workspace.hardGb,
  mountTarget: params.workspace.mountTarget ?? "/workspace",
});

hostConfig.Binds = [
  ...(hostConfig.Binds ?? []),
  `${ws.path}:${params.workspace.mountTarget ?? "/workspace"}`,
];
```

`hostConfig.{Memory, MemorySwap, CpuQuota, CpuPeriod, OomKillDisable}`
mapping from backend `params.hostConfig.*` stays exactly as in #17 —
that mapping is correct.

Return shape in `create_container_result`:

```json
{
  "type": "create_container_result",
  "requestId": "<request-uuid>",
  "data": {
    "ok": true,
    "containerId": "<12-char short id>",
    "workspace": {
      "path": "/var/lib/hypercube/workspaces/<shortId>",
      "projectId": 100456,
      "hardGb": 100
    }
  }
}
```

Backend persists these onto `Container.workspace_device` (path),
`Container.workspace_project_id`, and `Container.workspace_gb_limit`
respectively. The old `{ device, mountPoint, sizeGb }` field names are
still accepted as fallbacks during a partially upgraded fleet but new
builds must emit `{ path, projectId, hardGb }`.

### 3. `src/collectors/system.ts` → workspace quota pool

Replace `collectLvmThinPoolInfo()` with `collectWorkspaceQuotaInfo()`:

```ts
async function collectWorkspaceQuotaInfo() {
  const root = process.env.WORKSPACE_QUOTA_MOUNT
    ?? "/var/lib/hypercube/workspaces";
  if (!fs.existsSync(root)) {
    return { available: false };
  }
  // df -B1G --output=size,avail $root  →  parse line 2
  const { stdout: dfOut } = await execFile("df", ["-B1G", "--output=size,avail", root]);
  const [totalGbStr, freeGbStr] = dfOut.trim().split("\n")[1].trim().split(/\s+/);

  // Check that the mount has prjquota and that xfs_quota report runs.
  let hardEnforced = false;
  try {
    await execFile("xfs_quota", ["-x", "-c", "state", root]);
    const { stdout: mountOut } = await execFile("findmnt", ["-no", "OPTIONS", root]);
    hardEnforced = mountOut.includes("prjquota");
  } catch {
    hardEnforced = false;
  }

  return {
    available: true,
    mountPath: root,
    totalGb: Number(totalGbStr),
    freeGb: Number(freeGbStr),
    hardEnforced,
  };
}
```

Emit into `capacity_report.data.disk.workspaceQuota` (see core contract
in `docs/agent-payload-contract.md`). The old `disk.lvm` block is
removed.

### 4. `src/collectors/docker.ts` → workspace usage

For each running container with a known project id (look up from the
mapping file or from `workspace.path` parsed against the mount root),
add:

```ts
metrics.workspace = {
  path: `${root}/${shortId}`,
  projectId,
  hardGb,                   // remembered from create time
  usedGb,                   // parsed from `xfs_quota -x -c "report -h" $root`
  availableGb: Math.max(hardGb - usedGb, 0),
  usedPct: Math.round((usedGb / hardGb) * 100 * 10) / 10,
};
```

Backend already accepts both the new (`hardGb`) and legacy (`sizeGb`)
field names so the frontend KPI meter renders during the transition.

### 5. Config flag rename

`config.ts`:

```ts
- LVM_WORKSPACE_ENABLED: bool("LVM_WORKSPACE_ENABLED", false),
+ WORKSPACE_QUOTA_ENABLED: bool("WORKSPACE_QUOTA_ENABLED", false),
+ WORKSPACE_QUOTA_MOUNT: str("WORKSPACE_QUOTA_MOUNT", "/var/lib/hypercube/workspaces"),
```

All call sites that gated on `LVM_WORKSPACE_ENABLED` move to
`WORKSPACE_QUOTA_ENABLED`. Default off — operators flip it on after
the host setup (step 1 of the full-validation runbook) is complete.

### 6. Self-test

Rename `src/self-tests/resource-limits-lvm.ts` →
`src/self-tests/resource-limits-quota.ts`. The test should:

1. Refuse to run unless `WORKSPACE_QUOTA_ENABLED=true`.
2. `prepareContainerWorkspace({ shortId: "selftest1234", hardGb: 1, mountTarget: "/workspace" })`.
3. Mount-bind into a `busybox` container, run
   `dd if=/dev/zero of=/workspace/big bs=1M count=1100`,
   assert it exits non-zero with `ENOSPC`.
4. `teardownContainerWorkspace({ shortId: "selftest1234" })`.

The script's output is one of the PASS rows in
`docs/runbooks/workspace-quota-full-validation.md` §3.

### 7. Agent container permissions

The agent container needs:

- Bind mount: `/var/lib/hypercube/workspaces:/var/lib/hypercube/workspaces:rshared`.
- Either `privileged: true` **or** `cap_add: [SYS_ADMIN]` plus the
  `/dev/loop-control` device — XFS quota writes require it.
- The image must include `xfsprogs` and `quota` packages.

Document the chosen permission path in the PR description so the
operator can mirror it in the systemd unit / docker-compose.

## Validation expected on server_63_dev

```bash
bash docs/runbooks/workspace-quota-preflight.sh hypercube-agent-dev-63 hc-backend
# Expected:
#   RESULT: PASS — workspace quota gate is open.
```

Full 8-step integration gate (mirrors the LVM list, all in quota terms):

1. Agent sends `capacity_report` with
   `disk.workspaceQuota.available=true` and `hardEnforced=true`.
2. Backend Agent row updates `workspace_pool_total_gb`,
   `workspace_pool_free_gb`, `workspace_hard_enforcement=true`.
3. User creates a PyTorch Jupyter request — the recommend API returns
   a workspace size based on the new pool.
4. Backend sends `create_container` with `hostConfig`,
   `workspace.{hardGb, mountTarget}`, and `sharedMounts`.
5. Agent runs `mkdir` + `xfs_quota project` + `setquota` and bind-mounts
   `path` into the container.
6. Agent reports `create_container_result.workspace.{path, projectId, hardGb}`.
7. Backend stores `Container.workspace_device` (path),
   `workspace_project_id`, `workspace_gb_limit`.
8. Container `df /workspace` shows requested hard size; `dd` over it
   fails with `ENOSPC`; another container on the same host is
   unaffected.

## Regression rules

- Existing `create_container` requests without `params.workspace` must
  keep working (no quota slice).
- Existing hosts without the loop mount must stay in legacy mode and
  the agent must not crash on missing `xfs_quota`.
- Existing `update_container` / `update-limits` behavior must keep
  working — workspace hard limit is set once at create time and not
  modified by `update-limits` (no requirement to live-resize).
- Existing GPU allocation, model mount, network policy, logs, exec,
  and metrics behaviour must not regress.
- Do not add runtime downloads in the agent hot path.

## PR #17 disposition

Two acceptable options, agent owner picks:

1. **Force-push** the existing branch with the rewritten commits and
   change the PR title / description to "workspace quota (option 4b)".
2. **Close #17 unmerged** with a comment pointing to this handoff and
   open a fresh PR off `main`.

Either way, `qkr7287/HyperCube-agent#16` (tracking issue) stays open
until the full-validation runbook has every PASS marker filled in.
