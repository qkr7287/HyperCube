import hashlib
import math
import random
import time
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# --- Mock container definitions ---

_CONTAINER_DEFS = [
    {"name": "agdreamlog-api-api-1", "image": "agdreamlog-api-api:latest", "project": "agdreamlog-api", "state": "running", "mem_base": 256},
    {"name": "agdreamlog-api-nginx-1", "image": "nginx:alpine", "project": "agdreamlog-api", "state": "running", "mem_base": 32},
    {"name": "agdreamlog-api-postgres-1", "image": "postgres:16", "project": "agdreamlog-api", "state": "running", "mem_base": 128},
    {"name": "agdreamlog-api-redis-1", "image": "redis:7-alpine", "project": "agdreamlog-api", "state": "running", "mem_base": 16},
    {"name": "agdevblog-app-1", "image": "agdevblog-app:latest", "project": "agdevblog", "state": "running", "mem_base": 192},
    {"name": "agdevblog-nginx-1", "image": "nginx:alpine", "project": "agdevblog", "state": "running", "mem_base": 24},
    {"name": "agsafecat-backend-1", "image": "agsafecat-backend:latest", "project": "agsafecat-backend", "state": "running", "mem_base": 320},
    {"name": "agsafecat-frontend-1", "image": "node:20-alpine", "project": "agsafecat-backend", "state": "running", "mem_base": 180},
    {"name": "agsafecat-postgres-1", "image": "postgres:16", "project": "agsafecat-backend", "state": "running", "mem_base": 96},
    {"name": "aitranslateplatform-api-1", "image": "python:3.12-slim", "project": "aitranslateplatform", "state": "running", "mem_base": 512},
    {"name": "aitranslateplatform-worker-1", "image": "python:3.12-slim", "project": "aitranslateplatform", "state": "running", "mem_base": 768},
    {"name": "aitranslateplatform-redis-1", "image": "redis:7-alpine", "project": "aitranslateplatform", "state": "running", "mem_base": 24},
    {"name": "hypercube-backend-1", "image": "hypercube-backend:latest", "project": "hypercube", "state": "running", "mem_base": 210},
    {"name": "hypercube-nginx-1", "image": "nginx:alpine", "project": "hypercube", "state": "running", "mem_base": 28},
    {"name": "hypercube-postgres-1", "image": "pgvector/pgvector:pg16", "project": "hypercube", "state": "running", "mem_base": 112},
    {"name": "hypercube-redis-1", "image": "redis:7-alpine", "project": "hypercube", "state": "running", "mem_base": 18},
    {"name": "portainer-1", "image": "portainer/portainer-ce:latest", "project": "portainer", "state": "running", "mem_base": 64},
    {"name": "watchtower-1", "image": "containrrr/watchtower:latest", "project": "watchtower", "state": "running", "mem_base": 32},
    {"name": "gitlab-runner-1", "image": "gitlab/gitlab-runner:latest", "project": "gitlab", "state": "exited", "mem_base": 0},
    {"name": "old-test-container", "image": "alpine:3.18", "project": "test", "state": "exited", "mem_base": 0},
    {"name": "dev-jupyter-1", "image": "jupyter/scipy-notebook:latest", "project": "dev-tools", "state": "paused", "mem_base": 400},
]


def _make_id(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:64]


def _make_short_id(full_id: str) -> str:
    return full_id[:12]


def _make_created_timestamp(index: int) -> int:
    base = int(time.time()) - 86400 * 30
    return base - index * 86400


def _status_text(state: str, index: int) -> str:
    if state == "running":
        days = random.randint(1, 30)
        return f"Up {days} days"
    if state == "exited":
        hours = random.randint(1, 48)
        return f"Exited (0) {hours} hours ago"
    if state == "paused":
        return "Up 5 days (Paused)"
    return state


# Build in-memory container registry
MOCK_CONTAINERS = []
_CONTAINER_MAP = {}

for i, defn in enumerate(_CONTAINER_DEFS):
    cid = _make_id(defn["name"])
    container = {
        "id": cid,
        "shortId": _make_short_id(cid),
        "names": [f"/{defn['name']}"],
        "image": defn["image"],
        "imageId": f"sha256:{hashlib.sha256(defn['image'].encode()).hexdigest()}",
        "command": "/docker-entrypoint.sh" if "nginx" in defn["image"] else "python manage.py runserver",
        "created": _make_created_timestamp(i),
        "state": defn["state"],
        "status": _status_text(defn["state"], i),
        "ports": [],
        "labels": {
            "com.docker.compose.project": defn["project"],
            "com.docker.compose.service": defn["name"].rsplit("-", 1)[0],
        },
        "sizeRw": random.randint(0, 1048576),
        "sizeRootFs": random.randint(50000000, 500000000),
        "hostConfig": {"NetworkMode": "default"},
        "networkSettings": {"Networks": {"bridge": {"IPAddress": f"172.17.0.{i + 2}"}}},
        "mounts": [],
        "_mem_base": defn["mem_base"],
        "_index": i,
    }
    MOCK_CONTAINERS.append(container)
    _CONTAINER_MAP[cid] = container
    _CONTAINER_MAP[_make_short_id(cid)] = container


def get_container_list() -> list[dict]:
    result = []
    for c in MOCK_CONTAINERS:
        out = {k: v for k, v in c.items() if not k.startswith("_")}
        result.append(out)
    return result


def get_container_by_id(container_id: str) -> dict | None:
    return _CONTAINER_MAP.get(container_id)


def get_container_inspect(container_id: str) -> dict | None:
    c = get_container_by_id(container_id)
    if not c:
        return None

    started = datetime.now(KST) - timedelta(days=random.randint(1, 20))
    return {
        "Id": c["id"],
        "Name": c["names"][0],
        "State": {
            "Status": c["state"],
            "Running": c["state"] == "running",
            "Paused": c["state"] == "paused",
            "StartedAt": started.isoformat(),
            "FinishedAt": "0001-01-01T00:00:00Z" if c["state"] == "running" else datetime.now(KST).isoformat(),
        },
        "Config": {
            "Image": c["image"],
            "Cmd": [c["command"]],
            "WorkingDir": "/app",
            "Env": [
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "NODE_ENV=production",
                f"CONTAINER_NAME={c['names'][0].lstrip('/')}",
            ],
            "Labels": c["labels"],
        },
        "HostConfig": c["hostConfig"],
        "NetworkSettings": c["networkSettings"],
        "Mounts": c["mounts"],
    }


def get_container_stats(container_id: str) -> dict | None:
    c = get_container_by_id(container_id)
    if not c:
        return None

    mem_base = c["_mem_base"] * 1048576  # MB → bytes
    mem_usage = int(mem_base * (0.6 + 0.4 * random.random())) if mem_base > 0 else 0
    mem_limit = 8 * 1073741824  # 8GB

    return {
        "memory_stats": {
            "usage": mem_usage,
            "limit": mem_limit,
            "max_usage": int(mem_usage * 1.2),
        },
        "cpu_stats": {
            "cpu_usage": {"total_usage": random.randint(1000000, 9000000000)},
            "system_cpu_usage": random.randint(100000000000, 900000000000),
            "online_cpus": 8,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": random.randint(1000000, 9000000000)},
            "system_cpu_usage": random.randint(100000000000, 900000000000),
        },
        "networks": {
            "eth0": {
                "rx_bytes": random.randint(100000, 50000000),
                "tx_bytes": random.randint(50000, 20000000),
            }
        },
        "blkio_stats": {
            "io_service_bytes_recursive": [
                {"op": "Read", "value": random.randint(0, 50000000)},
                {"op": "Write", "value": random.randint(0, 20000000)},
            ]
        },
    }


def get_container_metrics(container_id: str) -> dict | None:
    c = get_container_by_id(container_id)
    if not c:
        return None

    idx = c["_index"]
    t = time.time()
    mem_base_mb = c["_mem_base"]

    # Dynamic CPU with sin wave + noise
    cpu_usage = max(0.01, abs(
        3.0 + 5.0 * math.sin(t / 10 + idx) + random.gauss(0, 1.5)
    ))
    mem_usage_bytes = int(mem_base_mb * 1048576 * (0.7 + 0.3 * math.sin(t / 30 + idx) + random.gauss(0, 0.05)))
    mem_limit = 8 * 1073741824

    if c["state"] != "running":
        cpu_usage = 0.0
        mem_usage_bytes = 0

    return {
        "timestamp": datetime.now(KST).isoformat(),
        "cpu": {
            "usage": round(cpu_usage, 2),
            "cores": 8,
        },
        "memory": {
            "usage": max(0, mem_usage_bytes),
            "limit": mem_limit,
            "percent": round(max(0, mem_usage_bytes) / mem_limit * 100, 2),
        },
        "network": {
            "rx": random.randint(100000, 5000000),
            "tx": random.randint(50000, 2000000),
        },
        "disk": {
            "read": random.randint(0, 30000000),
            "write": random.randint(0, 10000000),
        },
    }


_LOG_TEMPLATES = {
    "nginx": [
        '{ip} - - [{ts}] "GET / HTTP/1.1" 200 612 "-" "Mozilla/5.0"',
        '{ip} - - [{ts}] "GET /api/health HTTP/1.1" 200 15 "-" "curl/7.88"',
        '{ip} - - [{ts}] "POST /api/auth/token HTTP/1.1" 200 324 "-" "axios/1.6"',
        '{ip} - - [{ts}] "GET /static/js/main.js HTTP/1.1" 304 0 "-" "Mozilla/5.0"',
    ],
    "postgres": [
        "{ts} UTC [1] LOG:  database system is ready to accept connections",
        "{ts} UTC [42] LOG:  checkpoint starting: time",
        "{ts} UTC [42] LOG:  checkpoint complete: wrote 128 buffers (0.8%)",
        "{ts} UTC [55] LOG:  statement: SELECT count(*) FROM agents WHERE status = 'approved'",
    ],
    "redis": [
        "{pid}:M {ts} * Ready to accept connections tcp",
        "{pid}:M {ts} # Server started, Redis version=7.2.4",
        "{pid}:M {ts} * DB saved on disk",
        "{pid}:M {ts} - Accepted 127.0.0.1:{port}",
    ],
    "default": [
        "[{ts}] INFO: Application started on port 8000",
        "[{ts}] INFO: Connected to database",
        "[{ts}] DEBUG: Processing request {method} {path}",
        "[{ts}] INFO: Health check passed",
        "[{ts}] WARN: Slow query detected (duration: {duration}ms)",
    ],
}


def _get_log_type(image: str) -> str:
    if "nginx" in image:
        return "nginx"
    if "postgres" in image or "pgvector" in image:
        return "postgres"
    if "redis" in image:
        return "redis"
    return "default"


def get_container_logs(container_id: str, tail: int = 100) -> list[str] | None:
    c = get_container_by_id(container_id)
    if not c:
        return None

    log_type = _get_log_type(c["image"])
    templates = _LOG_TEMPLATES[log_type]
    logs = []

    for i in range(tail):
        ts = (datetime.now(KST) - timedelta(seconds=(tail - i) * 2)).strftime("%d/%b/%Y:%H:%M:%S +0900")
        template = random.choice(templates)
        line = template.format(
            ts=ts,
            ip=f"192.168.0.{random.randint(1, 254)}",
            pid=random.randint(1, 100),
            port=random.randint(30000, 65535),
            method=random.choice(["GET", "POST", "PUT"]),
            path=random.choice(["/api/health", "/api/containers", "/api/agents", "/"]),
            duration=random.randint(50, 3000),
        )
        logs.append(line)

    return logs


ALLOWED_ACTIONS = {"start", "stop", "restart", "pause", "unpause", "kill", "remove"}

_ACTION_STATE_MAP = {
    "start": "running",
    "stop": "exited",
    "restart": "running",
    "pause": "paused",
    "unpause": "running",
    "kill": "exited",
    "remove": None,
}


def perform_container_action(container_id: str, action: str) -> dict | None:
    c = get_container_by_id(container_id)
    if not c:
        return None

    if action not in ALLOWED_ACTIONS:
        return {"error": f"Unsupported action: {action}"}

    new_state = _ACTION_STATE_MAP.get(action)
    if new_state:
        c["state"] = new_state
        c["status"] = _status_text(new_state, c["_index"])

    return {
        "message": f"Container {action} successful",
        "result": None,
    }
