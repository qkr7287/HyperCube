"""Developer diagnostic endpoints (admin only)."""

import json

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAdmin
from apps.common.redis_client import get_redis_client


class RedisSnapshotView(APIView):
    """Redis 전체 키를 카테고리별로 반환. /dev 페이지용."""

    permission_classes = [IsAdmin]

    def get(self, request):
        r = get_redis_client()
        sections = []

        # 1. Agent 레지스트리
        agent_keys = list(r.scan_iter(match="agent_channel:*", count=100))
        sections.append({
            "title": "Agent Channel Registry",
            "keys": [
                {"key": k, "ttl": r.ttl(k), "value": r.get(k) or ""}
                for k in sorted(agent_keys)
            ],
        })

        # 2. Agent active set
        active = r.smembers("agents:notified_active") or set()
        sections.append({
            "title": "Active Agent Set",
            "keys": [{"key": "agents:notified_active", "ttl": -1, "value": ", ".join(sorted(active))}]
            if active
            else [],
        })

        # 3. Pending commands
        pending_keys = list(r.scan_iter(match="cmd_pending:*", count=100))
        sections.append({
            "title": "Pending Commands",
            "keys": [
                {"key": k, "ttl": r.ttl(k), "value": r.get(k) or ""}
                for k in sorted(pending_keys)
            ],
        })

        # 4. System metrics cache
        sys_keys = list(r.scan_iter(match="server:*:system", count=100))
        sections.append({
            "title": "System Metrics Cache",
            "keys": [
                {"key": k, "ttl": r.ttl(k), "value": _truncate_json(r.get(k))}
                for k in sorted(sys_keys)
            ],
        })

        # 5. Containers cache
        ctr_keys = list(r.scan_iter(match="server:*:containers", count=100))
        sections.append({
            "title": "Containers Cache",
            "keys": [
                {"key": k, "ttl": r.ttl(k), "value": f"{_count_containers(r.get(k))} containers"}
                for k in sorted(ctr_keys)
            ],
        })

        # 6. Container metrics cache
        cm_keys = list(r.scan_iter(match="server:*:container:*:metrics", count=200))
        sections.append({
            "title": "Container Metrics Cache",
            "keys": [
                {"key": k, "ttl": r.ttl(k), "value": _truncate_json(r.get(k), 120)}
                for k in sorted(cm_keys)[:50]  # cap at 50
            ],
        })

        # 7. Active IDs
        active_ids = r.smembers("server:active_ids") or set()
        sections.append({
            "title": "Active Server IDs",
            "keys": [{"key": "server:active_ids", "ttl": r.ttl("server:active_ids"), "value": ", ".join(sorted(active_ids))}]
            if active_ids
            else [],
        })

        return Response(sections)


def _truncate_json(raw, max_len=200):
    if not raw:
        return ""
    if len(raw) <= max_len:
        return raw
    return raw[:max_len] + "..."


def _count_containers(raw):
    if not raw:
        return 0
    try:
        data = json.loads(raw)
        return len(data.get("data", {}).get("containers", []))
    except (json.JSONDecodeError, TypeError):
        return "?"
