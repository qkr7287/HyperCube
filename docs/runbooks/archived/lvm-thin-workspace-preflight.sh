#!/usr/bin/env bash
# SUPERSEDED 2026-05-16 — workspace enforcement moved from LVM thin to
# XFS project quota on a loop file. Use workspace-quota-preflight.sh instead.
set -u

AGENT_CONTAINER="${1:-hypercube-agent-dev-63}"
BACKEND_CONTAINER="${2:-hc-backend}"
STATUS=0

section() {
  printf '\n[%s]\n' "$1"
}

ok() {
  printf 'OK   %s\n' "$1"
}

warn() {
  printf 'WARN %s\n' "$1"
}

fail() {
  printf 'FAIL %s\n' "$1"
  STATUS=1
}

check_command() {
  label="$1"
  command_name="$2"
  if command -v "$command_name" >/dev/null 2>&1; then
    ok "$label command '$command_name' -> $(command -v "$command_name")"
  else
    fail "$label command '$command_name' is missing"
  fi
}

check_agent_command() {
  command_name="$1"
  if docker exec "$AGENT_CONTAINER" sh -lc "command -v '$command_name' >/dev/null 2>&1"; then
    path="$(docker exec "$AGENT_CONTAINER" sh -lc "command -v '$command_name'" 2>/dev/null | tr -d '\r')"
    ok "agent command '$command_name' -> $path"
  else
    fail "agent command '$command_name' is missing"
  fi
}

check_dir() {
  dir="$1"
  if [ -d "$dir" ]; then
    ok "$dir exists"
  else
    fail "$dir is missing"
  fi
}

section "host tools"
for cmd in lvcreate lvs mkfs.ext4 mount umount lvremove; do
  check_command host "$cmd"
done

section "host storage"
if command -v lsblk >/dev/null 2>&1; then
  lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
else
  warn "lsblk is missing"
fi

for dir in /mnt/datasets /mnt/models /var/lib/hypercube/workspaces; do
  check_dir "$dir"
done

section "host lvm"
if command -v lvs >/dev/null 2>&1; then
  if lvs --units g; then
    ok "host lvs succeeded"
  else
    fail "host lvs command failed"
  fi
else
  fail "host lvs unavailable; cannot inspect thin pool"
fi

section "agent runtime"
if ! docker inspect "$AGENT_CONTAINER" >/dev/null 2>&1; then
  fail "agent container '$AGENT_CONTAINER' not found"
else
  ok "agent container '$AGENT_CONTAINER' exists"
  for cmd in lvcreate lvs mkfs.ext4 mount umount lvremove; do
    check_agent_command "$cmd"
  done
  if docker exec "$AGENT_CONTAINER" sh -lc "lvs --units g" >/tmp/hc-agent-lvs-preflight.$$ 2>&1; then
    ok "agent lvs succeeded"
    cat /tmp/hc-agent-lvs-preflight.$$
  else
    fail "agent lvs command failed"
    cat /tmp/hc-agent-lvs-preflight.$$ || true
  fi
  rm -f /tmp/hc-agent-lvs-preflight.$$
fi

section "backend capacity"
if ! docker inspect "$BACKEND_CONTAINER" >/dev/null 2>&1; then
  warn "backend container '$BACKEND_CONTAINER' not found; skipping Agent row check"
else
  docker exec "$BACKEND_CONTAINER" python manage.py shell -c "
from apps.agents.models import Agent
for a in Agent.objects.order_by('hostname'):
    print(a.hostname, a.cpu_cores, a.ram_total_mb, a.lvm_pool_size_gb, a.capacity_updated_at)
"
fi

section "result"
if [ "$STATUS" -eq 0 ]; then
  ok "LVM thin workspace host preflight passed"
else
  fail "LVM thin workspace host preflight failed"
fi

exit "$STATUS"
