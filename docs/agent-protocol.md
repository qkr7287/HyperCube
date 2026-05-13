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
| subCommand | string | yes      | `cpu_detail` \| `processes` \| `network_detail` \| `users` \| `gpu_inventory` |
| sortBy     | string | no       | `processes`만 — `cpu` (default) 또는 `mem`                 |

Invalid `subCommand` → `"Invalid subCommand: <x>. Valid: cpu_detail, processes, network_detail, users"`.

Current valid set also includes `gpu_inventory`.

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

#### 4.5 `gpu_inventory`

Backend dispatches this subCommand from Celery beat with a request id prefixed
by `gpu-inventory:`. The response is consumed by HyperCube core inventory
upsert logic and is not interpreted as a `ContainerRequest` response.

**request**

```json
{
  "type": "command",
  "requestId": "gpu-inventory:<agent_id>:<uuid>",
  "command": "system_info",
  "params": { "subCommand": "gpu_inventory" }
}
```

**success.data**

```json
{
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
```

If `nvidia-smi` or NVIDIA runtime discovery is unavailable, return
`command_response { success:false, error:"nvidia-smi not available" }`.
HyperCube core marks existing inventory for that agent offline and keeps other
agent metrics working. If a host has no GPU, return `success:true` with
`data.gpus=[]`.

### 5. `logs_subscribe` / `logs_unsubscribe`

Live log tail. 단발 명령이 아니라 long-running stream 시작/종료. `logs_subscribe`
의 `requestId` 가 그대로 `streamId` 로 사용되고, 이후 모든 `log_chunk` /
`log_stream_end` 메시지가 이 streamId 를 참조.

#### `logs_subscribe` — params

| field        | type    | required | default | notes                                         |
|--------------|---------|----------|---------|-----------------------------------------------|
| containerId  | string  | yes      |         | full ID 또는 short ID                         |
| tail         | number  | no       | 100     | 시작 전 backfill 라인 수. 0 = 현재 시점부터만. |
| since        | string  | no       |         | ISO8601 또는 relative (`5m`, `1h`, `30s`)     |
| timestamps   | boolean | no       | true    | Docker timestamp prefix 포함                  |

**즉시 응답**: `command_response { success:true, data:{ streamId, subscribed:true } }`. 이후 라인이 들어올 때마다 `log_chunk` 메시지가 흐름. 자연 종료 시 `log_stream_end` 1회.

#### `logs_unsubscribe` — params

| field    | type   | required | notes                                  |
|----------|--------|----------|----------------------------------------|
| streamId | string | yes      | 종료할 subscribe 의 `streamId` |

**응답**: `command_response { success:true, data:{ ended:true, streamId } }`. unknown streamId 도 `success:true` (idempotent — agent 결정).

`logs_unsubscribe` 로 인한 종료에는 `log_stream_end` emit 안 함.

#### 메시지 schema

`log_chunk`, `log_stream_end` 의 정확한 schema 와 backend routing 동작은
`agent-payload-contract.md` 참조. 두 메시지 모두 **flat envelope** (data/timestamp 없음).

---

### 6. `container_processes`

컨테이너 내부 프로세스 목록 (host 관찰 기반, minimal image 도 동작).

**params**

| field        | type   | required | default | notes                          |
|--------------|--------|----------|---------|--------------------------------|
| containerId  | string | yes      |         | full ID 또는 short ID          |
| sortBy       | string | no       | `cpu`   | `cpu` \| `mem`. 그 외 → cpu fallback |
| limit        | number | no       | 20      | 1~100 clamp                    |

**success.data**

```jsonc
{
  "containerId": "abc123def456",   // 12자 short ID
  "total": 42,                     // limit 적용 전 전체 process 수
  "processes": [
    {
      "pid": 1234,                  // host PID
      "name": "redis-server",
      "command": "redis-server *:6379",
      "cpu_percent": 1.2,           // 코어 합산 (Docker stats 와 동일 정의)
      "memory_rss": 12582912,       // bytes (RSS)
      "state": "S",                 // /proc/<pid>/stat 의 state code
      "user": "999"                 // uid (string)
    }
  ]
}
```

**errors** — `containerId is required` / `container_not_found` / `container_not_running` (stopped 만, paused 는 정상 처리) / `permission_denied` / Dockerode 에러.

**구현 (agent)**: `dockerode container.top()` 우선 (호스트 ps 사용 — 컨테이너 내부 ps 무관) + `/proc/<pid>/stat` 100ms 간격 2회 sample 로 CPU% 계산 + `/proc/<pid>/status` VmRSS 읽음. CLK_TCK=100 가정 (Linux x86/x64).

---

### 7. `exec_open` / `exec_input` / `exec_resize` / `exec_close`

Web 기반 console (B4 Console exec). 컨테이너 안에 shell 을 띄워 양방향 stdin/stdout
스트림을 WS 로 노출. `logs_subscribe` 패턴과 동일하게 `exec_open` 의 `requestId`
가 그대로 `execId`(== streamId) 로 사용되어 이후 모든 `exec_chunk` / `exec_end`
메시지가 이 키로 라우팅됨. 정책: 본인 소유 컨테이너에 한해 console 가능, 명령
차단 없음 (Portainer 모델). 세션 audit 은 backend `ConsoleSession` 모델에만 기록.

#### `exec_open` — params

| field        | type    | required | default       | notes                                |
|--------------|---------|----------|---------------|--------------------------------------|
| containerId  | string  | yes      |               | full 또는 short ID                    |
| cmd          | string[] | no      | `["/bin/sh"]` | 실행 명령. 예: `["/bin/bash"]`, `["sh","-lc","ls"]` |
| user         | string  | no       |               | `--user` 옵션. UID 또는 `uid:gid`     |
| tty          | boolean | no       | true          | TTY 할당 여부                          |
| env          | string[] | no      |               | `["KEY=VAL", ...]`                    |
| cols         | number  | no       | 80            | 초기 터미널 width                       |
| rows         | number  | no       | 24            | 초기 터미널 height                      |

**즉시 응답** (`command_response`):

```json
{ "success": true, "data": { "execId": "<requestId>", "ready": true } }
```

이후 stdout/stderr 가 발생할 때마다 `exec_chunk` 메시지가 흐름. 자연 종료
(shell exit) 시 `exec_end` 1회.

**errors** — `containerId is required`, `container_not_found`, `container_not_running`,
`cmd_not_found` (`exec /bin/bash: no such file or directory`), dockerode 에러.

#### `exec_input` — params

| field    | type   | required | notes                                                        |
|----------|--------|----------|--------------------------------------------------------------|
| execId   | string | yes      | exec_open 의 requestId                                       |
| data     | string | yes      | **base64** encoded raw bytes (binary safe, Ctrl 키 / UTF-8) |

응답: `command_response { success: true, data: { execId, wrote: <bytes> } }`.
unknown execId → `success: false, error: "unknown execId"`.

#### `exec_resize` — params

| field   | type   | required | notes      |
|---------|--------|----------|------------|
| execId  | string | yes      |            |
| cols    | number | yes      | 1~500      |
| rows    | number | yes      | 1~200      |

응답: `command_response { success: true, data: { execId, resized: true } }`.

#### `exec_close` — params

| field   | type   | required | notes                       |
|---------|--------|----------|-----------------------------|
| execId  | string | yes      | 종료할 exec 의 execId       |

응답: `command_response { success: true, data: { execId, closed: true } }`.
unknown execId 도 `success: true` (idempotent — agent 결정). `exec_close` 로
인한 종료에는 `exec_end` 도 emit (exitCode 전달 필요).

#### 메시지 schema

`exec_chunk`, `exec_end` 의 정확한 schema 와 backend routing 동작은
`agent-payload-contract.md` 참조. 두 메시지 모두 **flat envelope** (data/timestamp
없음, `log_chunk` 와 동일 형식).

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

Additional optional GPU parameter for ML Workspace Track 2:

```json
{
  "gpus": [
    { "deviceId": "GPU-...", "kind": "full" }
  ]
}
```

Empty or missing `gpus` means no GPU. When `gpus` is present, HyperCube core has
already reserved the selected `GpuSlice` rows. Agent must fail clearly if a
requested `deviceId` is not present or NVIDIA runtime setup is missing. Core
moves the allocation from `reserved` to `active` only after this command
succeeds; failure marks reserved allocations failed.

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

### 8. `update_container`

컨테이너 자원 한도 / 재시작 정책 즉시 변경 (재시작 없음). Portainer container
settings parity. Dockerode `container.update()` 호출.

**params**

| field | type | required | notes |
|-------|------|----------|-------|
| containerId | string | yes | full 또는 short ID |
| memory_mb | number | no | MB. 0 = unlimited. 미전송 = 변경 X |
| cpu_percent | number | no | 100 = 1 core. 0 = unlimited |
| restart_policy | string | no | `no` \| `on-failure` \| `unless-stopped` \| `always` |
| restart_max_retry | number | no | on-failure 일 때만 의미 |

**success.data**

```json
{
  "containerId": "abc123def456",
  "warnings": [],
  "updated": { "memory_mb": 256, "cpu_percent": 50, "restart_policy": "unless-stopped" }
}
```

errors: `containerId is required`, `container_not_found`, dockerode 에러 forward.

agent 구현: `Memory = memory_mb * 1024 * 1024`, `CpuPeriod = 100000`,
`CpuQuota = cpu_percent * 1000`, `RestartPolicy = { Name, MaximumRetryCount }`.

---

## 변경 이력

- 2026-05-11: `update_container` (P0 — Resource limit edit) 추가. memory/cpu/restart 한 명령 patch. dockerode container.update() 위임.
- 2026-05-11: `exec_open` / `exec_input` / `exec_resize` / `exec_close` (B4 Console exec) 추가. `execId == streamId` 라우팅 패턴 (`logs_subscribe` 재사용).
- 2026-04-29 (`7f82ff8`): `compose_up`, `create_container`, `delete_container` 추가 (Backend dispatch). routing 동작 표 추가.
- 2026-03-31: 초안 (Browser-issued 4개 command).
## Workspace/Jupyter extension

`create_container.params.workspace` is optional. Existing agents must preserve
the old behavior when it is absent.

```json
{
  "workspace": {
    "kind": "jupyter",
    "token": "<plaintext token, do not log>",
    "port": 8888,
    "baseUrl": "/workspace/<container-request-id>/",
    "workdir": "/workspace"
  },
  "networkPolicy": "internal_only"
}
```

The agent should inject the token/base URL/port into the image runtime and
return workspace reachability metadata. For normal workspaces, bind the
workspace port to a host port reachable from HyperCube backend and return:

```json
{
  "workspace": {
    "kind": "jupyter",
    "hostPort": 39021,
    "internalPort": 8888,
    "baseUrl": "/workspace/<container-request-id>/",
    "health": {}
  }
}
```

For `networkPolicy=internal_only`, the agent must not publish the workspace
port on the host. The workspace container should be attached to the shared
Docker internal network used by the backend, and the backend will reach it via
Docker DNS:

```json
{
  "workspace": {
    "kind": "jupyter",
    "hostPort": null,
    "internalPort": 8888,
    "baseUrl": "/workspace/<container-request-id>/",
    "health": {
      "networkPolicy": "internal_only",
      "networkName": "hc-ml-internal"
    }
  }
}
```

The backend falls back to `<container name>:<internalPort>` for internal-only
workspace upstreams. `hc-backend` must be joined to `hc-ml-internal` for this
path to work.

The backend stores only `workspace_token_ref` and expiry metadata in Postgres.
The plaintext token exists in Redis and in the agent command payload only.

## Model Prepare Extension

`prepare_model_assets` is a separate command. It is never folded into
`create_container`. HyperCube core uses `ModelPrepareJob.id` as the
`requestId`, so every `command_progress` and final `command_response` for a
prepare operation must echo that job id.

Example command:

```json
{
  "type": "command",
  "requestId": "<model-prepare-job-id>",
  "command": "prepare_model_assets",
  "params": {
    "jobId": "<model-prepare-job-id>",
    "transferMode": "backend_stream",
    "assets": [
      {
        "versionId": "<model-version-id>",
        "assetSlug": "tiny-local-model",
        "version": "v1",
        "sizeBytes": 1234,
        "sha256": "<sha256>",
        "checksum": "<sha256>",
        "source": {
          "type": "backend_stream",
          "contentUrl": "/api/model-versions/<model-version-id>/content/",
          "auth": "agent_bearer",
          "sha256": "<sha256>",
          "checksum": "<sha256>",
          "sizeBytes": 1234
        },
        "mountPath": "/workspace/models/tiny-local-model@v1"
      }
    ]
  }
}
```

The agent must call the content URL with its approved agent token in an
Authorization bearer header. The token must not be placed in a query string.
The agent writes to a temp path, verifies SHA256, then atomically moves into its
local cache.

`assets[].sha256` is the canonical checksum. `assets[].checksum`,
`assets[].source.sha256`, and `assets[].source.checksum` are sent as
compatibility aliases for agent builds that validate the checksum near the
stream source object.

Successful response:

```json
{
  "type": "command_response",
  "requestId": "<model-prepare-job-id>",
  "success": true,
  "data": {
    "cachePath": "/var/lib/hypercube-agent/model-cache/tiny-local-model/v1",
    "sha256": "<sha256>"
  }
}
```

After all prepare jobs for a `ContainerRequest` are ready, the backend dispatches
`create_container` with:

```json
{
  "modelMounts": [
    {
      "versionId": "<model-version-id>",
      "assetSlug": "tiny-local-model",
      "sourcePath": "/var/lib/hypercube-agent/model-cache/tiny-local-model/v1",
      "mountPath": "/workspace/models/tiny-local-model@v1",
      "readOnly": true,
      "sha256": "<sha256>",
      "sizeBytes": 1234
    }
  ]
}
```
