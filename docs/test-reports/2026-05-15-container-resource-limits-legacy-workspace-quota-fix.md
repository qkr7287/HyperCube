# Legacy Workspace Quota Fix - 2026-05-15

Follow-up after the resource-limit rollout: legacy/no-LVM create responses must not leave an unenforced `workspace_gb_limit` on the Container row.

## Change

- `backend/apps/containers/services/workspace.py` now clears `workspace_gb_limit` and `workspace_device` when the agent create response has no `workspace` object.
- This keeps CPU and memory request limits visible while preventing the UI from showing a disk quota that the agent did not actually create.
- New tests cover both the service-level metadata clear and the `MonitoringConsumer` create-response path for a no-LVM agent.

## Validation

Run on `server_63_dev` after sync:

```text
python manage.py test apps.containers.tests.test_workspaces apps.common.tests.test_consumers --verbosity 1
Found 14 test(s).
Ran 14 tests in 19.526s
OK

python manage.py test --verbosity 1
Found 111 test(s).
Ran 111 tests in 85.666s
OK
```

The LVM end-to-end scenario remains blocked until the 63 host and deployed agent expose `lvcreate`/`lvs`, the thin pool, and shared mount directories.
