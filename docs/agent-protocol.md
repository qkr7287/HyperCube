---
last-synced-commit: 7f82ff8
source-of-truth: backend/apps/common/consumers.py + backend/apps/containers/viewsets.py (_dispatch_to_agent)
verify: grep -nE '"command":\s*"' backend/apps/containers/viewsets.py
---

# HyperCube Agent — Command Protocol

Bidirectional command routing over WebSocket. 명령은 두 출처에서 발행됨:

1. **Browser → Backend → Agent** (실시간 조회/제어): `get_logs`, `inspect`, `control`, `system_info`
2. **Backend → Agent** (관리자 승인 후 자동 dispatch): `compose_up`, `create_container`, `delete_container` — `ContainerRequestViewSet.approve`에서 발송

응답은 `command_response` (최종 결과) 또는 `command_progress` (진행률, 장기 명령 한정). 자세한 envelope과 routing 동작은 `agent-payload-contract.md` 참조.

## Envelope

```
Browser → Backend → Agent:   {"type": "command", "requestId": "<uuid>", "command": "<name>", "params": {...}}
Backend → Agent (admin 승인): 위와 동일. requestId = ContainerRequest.id
Agent   → Backend → Browser: {"type": "command_response", "requestId": "<uuid>", "success": true|false, "data": {...}, "error": "<msg>"}
Agent   → Backend → Browser: {"type": "command_progress", "requestId": "<uuid>", "message": "...", "percent": 0-100}
```

- `requestId`는 Agent가 그대로 echo.
- 실패 시 `data` 생략, `error`에 사람이 읽을 메시지.
- Docker가 필요한 명령에서 socket 접근 불가 시 `error: "Docker is not available on this agent."`.
- `command_progress`는 장기 명령(compose_up, create_container 등) 중간에 여러 번 올 수 있음. 최종 응답은 `command_response`.

## Commands — 조회/제어 (Browser 발행)

### 1. `get_logs`

컨테이너 로그 fetch (non-streaming).

**params**
| field        | type    | required | default | notes                          |
|--------------|---------|----------|---------|--------------------------------|
| containerId  | string  | yes      |         | full ID 또는 short ID           |
| tail         | number  | no       | 100     | 최근 N 줄                       |
| since        | string  | no       |         | RFC3339 또는 Unix seconds       |
| timestamps   | boolean | no       | false   | 로그 timestamp prepend          |

**success.data**
```json
{
  "containerId": "abc123",
  "lines": ["log line 1", "log line 2", "..."]
}
```

**errors** — `"containerId is required"`, Dockerode errors (container not found 등)

---

### 2. `inspect`

컨테이너 메타데이터 (Docker Inspect subset).

**params**
| field       | type   | required |
|-------------|--------|----------|
| containerId | string | yes      |

**success.data**
```json
{
  "id": "abc123...",
  "name": "nginx",
  "created": "2026-03-31T10:00:00Z",
  "state": {
    "status": "running",
    "running": true,
    "paused": false,
    "restarting": false,
    "oomKilled": false,
    "dead": false,
    "pid": 1234,
    "exitCode": 0,
    "startedAt": "2026-03-31T10:00:01Z",
    "finishedAt": "0001-01-01T00:00:00Z",
    "health": null
  },
  "image": "nginx:latest",
  "config": {
    "hostname": "abc123",
    "env": ["PATH=..."],
    "cmd": ["nginx", "-g", "daemon off;"],
    "labels": { "com.docker.compose.project": "..." },
    "workingDir": "",
    "entrypoint": ["/docker-entrypoint.sh"]
  },
  "networkSettings": {
    "ports": { "80/tcp": [{ "HostIp": "0.0.0.0", "HostPort": "8080" }] },
    "networks": { "bridge": { "IPAddress": "172.17.0.2", "...": "..." } }
  },
  "mounts": [
    { "type": "bind", "source": "/host/path", "destination": "/container/path", "mode": "rw", "rw": true }
  ],
  "restartCount": 0
}
```

**errors** — `"containerId is required"`, Dockerode errors.

---

### 3. `control`

컨테이너 라이프사이클 액션.

**params**
| field       | type    | required | default | notes                      |
|-------------|---------|----------|---------|----------------------------|
| containerId | string  | yes      |         |                            |
| action      | string  | yes      |         | 아래 목록 참조              |
| force       | boolean | no       | false   | `remove`만 적용             |

**Valid actions**: `start`, `stop`, `restart`, `pause`, `unpause`, `kill`, `remove`

**success.data**
```json
{ "containerId": "abc123", "action": "restart", "success": true }
```

**errors** — `"containerId is required"`, `"Invalid action: <x>. Valid: start, stop, ..."`, Dockerode errors.

---

### 4. `system_info`

호스트 시스템 정보. 한 호출당 하나의 subcommand.

**params**
| field      | type   | required | notes                                                    |
|------------|--------|----------|----------------------------------------------------------|
| subCommand | string | yes      | `cpu_detail` \| `processes` \| `network_detail` \| `users` |
| sortBy     | string | no       | `processes`만 — `cpu` (default) 또는 `mem`                 |

Invalid `subCommand` → `"Invalid subCommand: <x>. Valid: cpu_detail, processes, network_detail, users"`.

#### 4.1 `cpu_detail`

```json
{
  "model": "Intel Core i5-10400",
  "speed": 2.9,
  "cores": 12,
  "usage": 45.2,
  "perCore": [{ "core": 0, "load": 30.1 }, { "core": 1, "load": 50.4 }],
  "temperature": { "main": 55, "cores": [54, 56, 55, 57], "max": 57 },
  "loadAvg": { "avg1": 1.23, "avg5": 1.45, "avg15": 1.30 }
}
```

- `temperature`는 sensors 없으면 `null`.
- `loadAvg`는 `/host/proc/loadavg`에서 read (fallback: `os.loadavg()`).

#### 4.2 `processes`

```json
{
  "total": 350,
  "running": 2,
  "blocked": 0,
  "list": [
    {
      "pid": 1234,
      "name": "node",
      "cpu": 3.2,
      "mem": 128.5,
      "state": "running",
      "user": "root",
      "command": "node /app/dist/index.js"
    }
  ]
}
```

- `list`는 50개로 cap, `cpu` 또는 `mem` 정렬 (`sortBy` param).
- `mem`은 RSS in MB.
- 호스트 process 보려면 compose에 `pid: host` 필요.

#### 4.3 `network_detail`

```json
{
  "interfaces": [
    {
      "iface": "eth0",
      "ip4": "192.168.0.16",
      "ip6": "fe80::...",
      "mac": "aa:bb:cc:dd:ee:ff",
      "type": "wired",
      "speed": 1000,
      "operstate": "up"
    }
  ],
  "stats": {
    "rx_bytes": 123456789,
    "tx_bytes": 987654321,
    "rx_packets": 1234567,
    "tx_packets": 7654321,
    "rx_errors": 0,
    "tx_errors": 0
  },
  "connections": 42
}
```

- `stats`는 `lo` 제외 모든 interface의 합 (`/host/proc/net/dev` 파싱).
- `connections`는 활성 connection 수 (unavailable 시 0).

#### 4.4 `users`

```json
{
  "users": [
    {
      "user": "agics-ai",
      "terminal": "pts/0",
      "date": "2026-04-13",
      "time": "10:30",
      "ip": "192.168.0.47",
      "command": "-bash"
    }
  ]
}
```

- compose에 `/var/run/utmp` mount 필요. mount 안 됐으면 빈 배열.

---

## Commands — 컨테이너 배포 (Backend dispatch)

`apps.containers.viewsets.ContainerRequestViewSet.approve`에서 admin이 요청을 승인하면 자동 발송.
`requestId` = `ContainerRequest.id` (UUID). Agent가 진행률을 `command_progress`로 push, 최종 결과는
`command_response`. Backend `_update_request_from_response`가 결과를 받아 Container DB 갱신.

### 5. `compose_up`

Docker Compose 프로젝트 배포. `ContainerTemplate.kind == "compose"`인 템플릿 기반 요청 시.

**params**
| field        | type   | required | notes                                       |
|--------------|--------|----------|---------------------------------------------|
| projectName  | string | yes      | compose project 이름. `custom_name` 또는 `hc-<8>` |
| composeYaml  | string | yes      | template의 compose YAML 내용                 |
| env          | object | no       | 사용자 추가 env (`{"KEY": "VALUE"}`)         |

**success.data** (예시)
```json
{
  "projectName": "hc-abc12345",
  "containers": [
    { "containerId": "abc123def456", "name": "hc-abc12345-web-1", "image": "nginx:latest", "state": "running" }
  ]
}
```

여러 컨테이너 생성 시 `containers` 배열에 모두 포함. Backend는 첫 번째를 `ContainerRequest.target_container`로 링크.

**command_progress** 예시: `{"message": "이미지 pull 중... (3/5)", "percent": 60}`

---

### 6. `create_container`

단일 컨테이너 생성. `ContainerTemplate.kind == "image"` 또는 직접 image 지정.

**params**
| field    | type    | required | notes                                |
|----------|---------|----------|--------------------------------------|
| image    | string  | yes      | `selected_image` 또는 `template.image` |
| name     | string  | yes      | container 이름 (`custom_name` or `hc-<8>`) |
| env      | object  | no       | env vars                             |
| ports    | array   | no       | `[{"HostPort": "8080", "ContainerPort": "80"}, ...]` (dict 형식만) |
| volumes  | array   | no       | template의 default_volumes            |

**success.data**
```json
{
  "containerId": "abc123def456",
  "name": "hc-abc12345",
  "image": "nginx:latest",
  "state": "running"
}
```

---

### 7. `delete_container`

컨테이너 삭제. `ContainerRequest.action == "delete"` 시.

**params**
| field       | type    | required | default | notes                       |
|-------------|---------|----------|---------|-----------------------------|
| containerId | string  | yes      |         | `target_container_id`        |
| force       | boolean | no       | true    | running 상태면 강제 삭제      |

**success.data**
```json
{ "containerId": "abc123", "deleted": true }
```

성공 시 Backend가 `Container` row를 DB에서 삭제 + `ContainerRequest.target_container = None`.

---

## Routing 동작 (Backend 측 요약)

`MonitoringConsumer` (`apps/common/consumers.py`):

| 수신 | 처리 |
|------|------|
| Browser `command` | requestId 검증 → `command_router.record_pending(requestId, browser_channel, server_id)` → Agent 채널로 forward |
| Agent `command_response` | `pop_pending(requestId)` → Browser 채널로 forward + `_update_request_from_response` (DB 갱신) |
| Agent `command_progress` | pending map peek (pop 안 함, progress 여러 번 옴) → Browser forward + `_update_request_progress` (DB) + global broadcast |

Backend → Agent dispatch (`ContainerRequestViewSet._dispatch_to_agent`):

1. `command_router.get_agent_channel(server_id)` — Agent 오프라인이면 즉시 `status=failed`
2. `command_router.record_pending(req.id, "__api__", server_id)` — browser_channel 자리에 sentinel
3. `channel_layer.send(agent_channel, {"type": "ws.send", "payload": {...command...}})`
4. Agent 응답 시 위 routing 표대로 처리. browser_channel이 `__api__`이면 forward 생략, DB 갱신만.

## 변경 이력

- 2026-04-29 (`7f82ff8`): `compose_up`, `create_container`, `delete_container` 추가 (Backend dispatch). routing 동작 표 추가.
- 2026-03-31: 초안 (Browser-issued 4개 command).
