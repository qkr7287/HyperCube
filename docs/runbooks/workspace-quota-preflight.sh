#!/usr/bin/env bash
# Read-only preflight for the XFS project quota workspace gate.
#
# Verifies the five things that must be true before per-container
# /workspace hard enforcement can be claimed complete on a host:
#
#   1. Host has xfsprogs (`xfs_quota`) and `setquota`.
#   2. Loop file exists at WORKSPACE_LOOP_FILE.
#   3. WORKSPACE_MOUNT is mounted with the prjquota option.
#   4. The agent container can invoke `xfs_quota -x -c "report -h"` on the mount.
#   5. Backend Agent row has workspace_pool_total_gb non-null + workspace_hard_enforcement=true.
#
# Exits 0 only when all five pass; otherwise prints a one-line reason
# per failed check and exits non-zero. Safe to re-run.
#
# Usage:
#   docs/runbooks/workspace-quota-preflight.sh [agent-container] [backend-container]
#
# Override defaults via env if your hostnames differ.

set -u

AGENT_CONTAINER="${1:-hypercube-agent-dev-63}"
BACKEND_CONTAINER="${2:-hc-backend}"
WORKSPACE_MOUNT="${WORKSPACE_MOUNT:-/var/lib/hypercube/workspaces}"
WORKSPACE_LOOP_FILE="${WORKSPACE_LOOP_FILE:-/var/lib/hypercube/workspaces.img}"
STATUS=0

section() {
  echo
  echo "== $1"
}

check() {
  local desc="$1"
  shift
  if "$@" >/tmp/preflight.out 2>&1; then
    echo "  PASS: $desc"
  else
    echo "  FAIL: $desc"
    sed 's/^/        /' </tmp/preflight.out
    STATUS=1
  fi
}

section "Host xfsprogs / quota tooling"
check "xfs_quota present" command -v xfs_quota
check "setquota present"  command -v setquota
check "mkfs.xfs present"  command -v mkfs.xfs

section "Workspace loop file + mount"
check "loop file exists at $WORKSPACE_LOOP_FILE" test -f "$WORKSPACE_LOOP_FILE"
check "$WORKSPACE_MOUNT is mounted" mountpoint -q "$WORKSPACE_MOUNT"
check "$WORKSPACE_MOUNT mounted with prjquota" \
  bash -c "mount | grep -E ' on $WORKSPACE_MOUNT type xfs ' | grep -q prjquota"

section "Agent runtime can drive xfs_quota"
check "agent container running" docker inspect --type=container "$AGENT_CONTAINER"
check "agent container sees the mount" \
  docker exec "$AGENT_CONTAINER" sh -lc "test -d $WORKSPACE_MOUNT"
check "agent container can run xfs_quota report" \
  docker exec "$AGENT_CONTAINER" sh -lc "xfs_quota -x -c 'report -h' $WORKSPACE_MOUNT"

section "Backend Agent capacity row"
check "backend Agent has workspace_pool_total_gb non-null + hard enforcement" \
  docker exec "$BACKEND_CONTAINER" python manage.py shell -c "
from apps.agents.models import Agent
rows = list(Agent.objects.values('hostname','workspace_pool_total_gb','workspace_hard_enforcement','capacity_updated_at'))
print(rows)
import sys
sys.exit(0 if any(r['workspace_pool_total_gb'] and r['workspace_hard_enforcement'] for r in rows) else 1)
"

echo
if [ "$STATUS" -eq 0 ]; then
  echo "RESULT: PASS — workspace quota gate is open."
else
  echo "RESULT: FAIL — fix the items above before flipping any container to hard quota."
fi
exit "$STATUS"
