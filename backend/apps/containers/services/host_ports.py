"""Agent host port 점유 집계.

backend 가 확실히 아는 점유 포트(HyperCube 가 띄운 컨테이너 + 진행 중 요청)를
모은다. host 의 다른 프로세스가 쓰는 포트는 여기에 안 잡히므로, 완전한
목록은 agent 의 host port 스캔으로 보완한다 (used-ports API tier2).
"""

from apps.containers.models import Container, ContainerRequest

# 포트를 실제로 바인딩하고 있는 컨테이너 상태.
_PORT_HOLDING_STATUSES = (
    Container.Status.RUNNING,
    Container.Status.PAUSED,
    Container.Status.RESTARTING,
)

# host port 를 아직 점유하지는 않지만 곧 deploy 될 요청 상태.
_PENDING_REQUEST_STATUSES = (
    ContainerRequest.Status.PENDING,
    ContainerRequest.Status.APPROVED,
    ContainerRequest.Status.DEPLOYING,
)


def collect_managed_host_ports(agent, *, exclude_request_id=None) -> list[dict]:
    """agent 의 backend-known host port 점유 목록.

    각 항목: {"port": int, "proto": str, "source": str}.
    exclude_request_id 는 충돌 검사 시 자기 자신을 제외하기 위함.
    """
    used: list[dict] = []

    for container in (
        Container.objects.filter(agent=agent, workspace_host_port__isnull=False)
        .filter(status__in=_PORT_HOLDING_STATUSES)
        .only("name", "workspace_host_port", "status")
    ):
        used.append({
            "port": container.workspace_host_port,
            "proto": "tcp",
            "source": f"container:{container.name}",
        })

    requests = ContainerRequest.objects.filter(
        target_agent=agent,
        action=ContainerRequest.Action.CREATE,
        status__in=_PENDING_REQUEST_STATUSES,
    ).only("workspace_host_port", "custom_ports")
    if exclude_request_id:
        requests = requests.exclude(id=exclude_request_id)

    for request in requests:
        if request.workspace_host_port:
            used.append({
                "port": request.workspace_host_port,
                "proto": "tcp",
                "source": "request:workspace",
            })
        for spec in request.custom_ports or []:
            if not isinstance(spec, dict):
                continue
            host = spec.get("host")
            if host in (None, ""):
                continue
            try:
                port = int(host)
            except (TypeError, ValueError):
                continue
            used.append({
                "port": port,
                "proto": str(spec.get("protocol") or "tcp"),
                "source": "request:port",
            })

    return used


def host_port_in_use(agent, port: int, *, exclude_request_id=None) -> bool:
    """agent 에서 host port 가 backend-known 점유와 충돌하는지."""
    return any(
        entry["port"] == port
        for entry in collect_managed_host_ports(
            agent, exclude_request_id=exclude_request_id
        )
    )
