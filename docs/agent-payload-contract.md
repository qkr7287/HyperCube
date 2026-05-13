---
last-synced-commit: 7f82ff8
source-of-truth: backend/apps/common/consumers.py + backend/apps/metrics/payload_map.py
verify: grep -nE "msg_type ==|\"type\":" backend/apps/common/consumers.py
---

# Agent Payload Contract

## GPU Inventory Response

`system_info { subCommand: "gpu_inventory" }` responses use request ids prefixed
with `gpu-inventory:` and pending browser sentinel `__gpu_inventory__`. Backend
applies the payload to `GpuDevice` / `GpuSlice` inventory and does not route it
through `ContainerRequest` deployment-state handling.

If the agent lacks `nvidia-smi` or GPU discovery support, it should return
`command_response { success:false, error:"nvidia-smi not available" }`; the core
repo marks existing inventory for that agent offline.

HyperCube WebSocket payload 스펙. Agent / Backend / Frontend 세 layer 가 같은 metric 을 다르게 해석하지 않도록 한 곳에서 정의한다.

## 원칙

1. **Agent 는 raw 만 보낸다.** 관찰값 (bytes, °C, count) 이 1차. 파생값 (%, rate) 은
   raw 와 함께 보낸다 — backend 가 cross-check / 재계산 가능하도록.
2. **Linux 메모리는 MemAvailable 사용.** `(total - free) / total` 은 buffer/cache 를
   used 로 카운트하므로 금지. `(total - available) / total` 만 정확.
3. **누적 카운터는 그대로.** `network.rx`, `network.tx`, `disk.read`, `disk.write`
   는 boot 이후 누적 bytes. Backend 가 bucket 간 delta 로 rate 계산.
4. **새 metric 추가 = 이 문서 먼저 갱신.** 그 다음 backend `payload_map.py`
   / migration / frontend mapping. 코드 보다 contract 가 source of truth.
5. **하위 호환.** 새 필드는 optional / nullable. 기존 필드 의미 변경은 버전 bump
   + 명시적 migration plan 필요.

## WebSocket message envelope

```jsonc
{
  "type": "<msg_type>",
  "timestamp": "2026-04-27T00:07:23.614Z",   // ISO8601 UTC (data 메시지만)
  "data": { ... }                              // type 별 payload
}
```

## 메시지 카탈로그 (현재 구현)

| `type` | 방향 | 빈도 | 용도 | Backend 처리 |
|--------|------|------|------|--------------|
| `system_metrics` | Agent → Backend | 5~15s | 호스트 메트릭 (Delta Sync) | Redis 캐시 merge + Browser broadcast + Celery → PG |
| `container_metrics` | Agent → Backend | stats stream | 컨테이너 메트릭 | 동일 (per-container 캐시) |
| `containers` | Agent → Backend | 60s snapshot | 컨테이너 목록 sync | Redis (10분 TTL) + Container 모델 update_or_create |
| `command` | Browser → Backend → Agent | on-demand | 명령 발행 | requestId pending map 등록 후 Agent 채널로 forward |
| `command_response` | Agent → Backend → Browser | command 완료 시 | 최종 결과 | pending map pop + Browser 라우팅 + ContainerRequest DB 갱신 |
| `command_progress` | Agent → Backend → Browser | command 진행 중 | 진행률 (0-100) | Browser 라우팅 + ContainerRequest.progress_message/percent 갱신 + global broadcast |
| `heartbeat` | Backend → Agent | 15s | 좀비 세션 감지 | Agent가 수신 침묵 시 재접속 |
| `connection` | Backend → Agent/Browser | connect 직후 | 접속 확인 | client side 만 |
| `agent_status_change` | Backend → Browser (global) | online↔offline 전환 | global event broadcast | `GlobalEventsConsumer` group_send |
| `container_events` | Agent → Backend | 이벤트 발생 시 (100ms batch) | 컨테이너 라이프사이클 이벤트 (start/stop/die/restart/pause/unpause/kill/oom/health_status) | `ContainerEvent` 모델 저장 + 서버 group broadcast |
| `log_chunk` | Agent → Backend → Browser | tail 시 (200ms batch / 50줄 threshold) | 로그 라인 chunk | `streamId` 로 browser channel 매핑 후 forward (DB 저장 X) |
| `log_stream_end` | Agent → Backend → Browser | stream 자연 종료 시 1회 | 컨테이너 stop / docker error 등 | forward + stream registry 정리 |
| `exec_chunk` | Agent → Backend → Browser | exec 활성 (50ms batch / 64KB threshold 권장) | console stdout/stderr raw bytes (base64) | `execId` 로 browser channel 매핑 후 forward (DB 저장 X) |
| `exec_end` | Agent → Backend → Browser | exec 종료 시 1회 | shell exit / disconnect / container_stopped | forward + stream registry 정리 + `ConsoleSession` close 갱신 |

WS path:
- `/ws/server/{server_id}/` → `MonitoringConsumer` (Agent + 그 서버 보는 Browser)
- `/ws/global/` → `GlobalEventsConsumer` (모든 인증 Browser, global 이벤트만)

## type: `system_metrics`

서버 호스트 단위. Agent 가 5~15 초마다 push (Delta Sync — 변경된 필드만).

```jsonc
{
  "type": "system_metrics",
  "timestamp": "2026-04-27T00:07:23.614Z",
  "data": {
    "hostname": "server_16_dev",
    "os": "Linux 6.8.0-101-generic",
    "uptime": 4541677.02,                     // seconds

    "cpu": {
      "model": "Intel Core i5-10400",
      "cores": 6,                              // physical cores
      "threads": 12,                           // logical cores (hyperthread 포함)
      "sockets": 1,
      "isHybrid": false,
      "performanceCores": 6,
      "efficiencyCores": 0,
      "usage": 70.8,                           // 0-100, 모든 thread 평균
      "perCore": [100, 100, ...],              // length = threads
      "loadAvg1m": 8.84                        // optional, Linux 만
    },

    "memory": {
      "total": 41691742208,                    // bytes
      "free": 654454784,                       // bytes (MemFree)
      "available": 22271770624,                // bytes (MemAvailable) — REQUIRED on Linux
      "used": 19419971584,                     // total - available (NOT total - free)
      "usage": 46.6                            // (total - available) / total * 100
    },

    "disk": {
      "total": 490577010688,                   // bytes (root partition)
      "free": 84922978304,
      "used": 380658814976,
      "usage": 81.8                            // used / total * 100
    },

    "gpu": [                                    // 배열. GPU 없으면 [] 또는 생략.
      {
        "index": 0,
        "vendor": "NVIDIA",
        "model": "NVIDIA GeForce RTX 3060 Ti",
        "usage": 0,                            // 0-100
        "memoryTotal": 8589934592,             // bytes
        "memoryUsed": 6910115840,              // bytes
        "memoryPercent": 80.4,                 // (used/total)*100, optional
        "temperature": 61                      // °C, optional
      }
    ],

    "network": {
      "interfaces": ["enp1s0"],
      "rx": 535472170965,                      // 누적 수신 bytes since boot
      "tx": 123826608774,                      // 누적 송신 bytes
      "connections": 112                       // optional, 활성 connection 수
    },

    "processes": {
      "total": 866,
      "running": 3                             // R 상태만
    },

    "logins": {
      "active": 2,                             // 현재 세션
      "total": 2                               // optional, accumulated
    },

    "docker": {
      "version": "26.1.4",
      "containers": 88,
      "images": 723
    }
  }
}
```

### 메모리 계산 (가장 흔한 버그)

Linux 에서 reclaimable buffer/cache 를 used 로 카운트하면 90%+ 로 항상 잘못 보인다.
정확한 방식:

| 필드 | 출처 (`/proc/meminfo`) | 의미 |
|---|---|---|
| `total` | `MemTotal` | 전체 RAM |
| `free` | `MemFree` | 어디에도 안 쓰이는 바이트 (작음, 의미 없음) |
| `available` | `MemAvailable` | 새 프로그램이 쓸 수 있는 추정치 (이게 진짜 "여유") |
| `used` | `total - available` | 실질적으로 묶여있는 메모리 |
| `usage` | `(total - available) / total * 100` | 사용률 % |

라이브러리:
- Go: `gopsutil/v3/mem` `VirtualMemory()` → `Available` 필드
- Node: `/proc/meminfo` 직접 파싱 (`os.freemem()` 은 MemFree 라서 부정확)
- Python: `psutil.virtual_memory().available`

Windows / macOS 는 `available` 의미가 다르지만 OS 가 정확한 값 제공 → 그대로 사용.

## type: `container_metrics`

Docker container 단위. Agent 가 stats stream 으로 모음.

```jsonc
{
  "type": "container_metrics",
  "timestamp": "2026-04-27T00:07:23.614Z",
  "data": {
    "containerId": "abc123def456",
    "name": "/myapp-web-1",
    "image": "myapp:latest",
    "state": "running",

    "cpu": {
      "usage": 605.2,                          // raw 코어 합산 % (Docker stats 그대로)
      "cores_quota": 8,                        // 이 컨테이너에 허용된 논리 코어 수.
                                                // cgroup cpu.max 또는 호스트 코어 수.
                                                // 결정 못 하면 null.
      "usage_pct": 75.65                       // 정규화 0-100 (= usage / cores_quota).
                                                // cores_quota 가 null 이면 null.
    },

    "memory": {
      "usage": 1073741824,                     // bytes
      "limit": 4294967296,                     // bytes
      "percent": 25.0                          // usage / limit * 100
    },

    "network": {
      "rx": 12345678,                          // 누적
      "tx": 9876543
    },

    "disk": {
      "read": 12698,                           // 누적
      "write": 4194304
    },

    "gpu": {                                    // optional, 컨테이너에 GPU 할당된 경우만
      "usage": 45,                             // 0-100
      "memoryUsed": 2147483648,
      "memoryTotal": 8589934592,
      "source": "nvidia-smi"                   // 데이터 출처
    }
  }
}
```

### CPU 정규화 (Docker stats 함정)

Docker stats `CPUPerc` 는 코어 합산이라 4-core 컨테이너가 100% 면 400% 로 나옴.
정규화:
- `cores_quota` = `min(cgroup_cpu_max, host_cores)`
- `usage_pct` = `usage / cores_quota` (0-100)

`cores_quota` 결정 실패 시 (예: cgroupv1 read 권한 없음) **null 로 보낸다**. 0 이나
host_cores fallback 금지 — 0 이면 분모 폭발, fallback 이면 잘못된 값 저장.

## type: `containers` (snapshot)

Agent가 60초마다 자기가 본 모든 컨테이너 목록을 push. Backend는 Container 모델을
update_or_create 하고, 보고에서 빠진 컨테이너는 `exited`로 마킹.

```jsonc
{
  "type": "containers",
  "timestamp": "2026-04-27T00:07:23.614Z",
  "data": {
    "containers": [
      {
        "id": "abc123def456",        // 12자 short ID 또는 full
        "name": "myapp-web-1",
        "image": "myapp:latest",
        "state": "running"           // running | stopped | paused | exited | created | restarting | dead
      }
    ]
  }
}
```

state 값이 위 7개 외면 `created`로 정규화 (`_normalize_status`).

## type: `container_events`

Agent 가 Dockerode `events()` stream 을 구독해 컨테이너 라이프사이클 이벤트를 push.
100ms batch window 로 묶여서 옴. `events` 배열은 1개 이상.

```jsonc
{
  "type": "container_events",
  "timestamp": "2026-05-08T11:30:00.000Z",  // 메시지 송신 시각
  "data": {
    "events": [
      {
        "containerId": "abc123def456...",    // Docker full ID. Backend는 12자 short 로 매칭.
        "name": "verify-redis-2",            // optional
        "ts": "2026-05-08T11:29:58.123Z",    // Docker 이벤트 발생 시각 (UTC)
        "kind": "start",                      // 아래 9종 중 하나
        "exitCode": 0,                        // optional, "die" 일 때
        "signal": "SIGTERM",                  // optional, "kill" 일 때 (숫자는 agent 가 SIGKILL 등으로 정규화)
        "healthStatus": "healthy"             // optional, "health_status" 일 때 (healthy|unhealthy|starting)
      }
    ]
  }
}
```

### kind (Docker Action → kind)

| Docker `Action` | `kind` | 추가 필드 |
|---|---|---|
| `start` | `start` | — |
| `stop` | `stop` | — |
| `die` | `die` | `exitCode` |
| `restart` | `restart` | — |
| `pause` | `pause` | — |
| `unpause` | `unpause` | — |
| `kill` | `kill` | `signal` |
| `oom` | `oom` | — (die가 뒤이어 옴) |
| `health_status: <state>` | `health_status` | `healthStatus` |

`create / destroy / exec_* / attach / commit / rename / update / top` 등은 송출 안 함.

### Backend 처리

`MonitoringConsumer._handle_container_events`:
1. `events` 배열 순회, agent_id + containerId(short 12) 로 `Container` 매칭
2. `ContainerEvent` row 생성 (bulk_create)
3. 알 수 없는 컨테이너는 silently skip (방금 생성됐지만 containers snapshot 미도착 케이스)
4. 같은 메시지를 server group 에 broadcast (admin/소유자 viewer 의 향후 WS push 전환 대비)

## type: `log_chunk` / `log_stream_end`

Live log tail 용 push 메시지. envelope 다른 메시지(`type`+`timestamp`+`data`)
와 달리 **flat 구조** (agent 측 결정사항).

### `log_chunk`

```jsonc
{
  "type": "log_chunk",
  "streamId": "<sub-uuid>",          // logs_subscribe 의 requestId
  "stream": "stdout",                 // "stdout" | "stderr" | "mixed" (tty-mode 만)
  "lines": [
    "2026-05-08T15:30:00.123Z [info] hello",
    "..."
  ]
}
```

Backend 처리: `command_router.get_stream_info(streamId)` 로 browser channel
조회 후 그대로 forward. DB 저장 안 함.

### `log_stream_end`

```jsonc
{
  "type": "log_stream_end",
  "streamId": "<sub-uuid>",
  "reason": "container_stopped",      // container_stopped | container_removed (현재 통합) | stream_error | agent_shutdown
  "error": "<optional>"
}
```

Backend 처리: forward + `remove_stream(streamId)` 로 registry 정리.
`logs_unsubscribe` 로 인한 종료에는 emit 되지 않음 (그건 command_response 로
충분).

## 새 명령: `logs_subscribe` / `logs_unsubscribe`

`docs/agent-protocol.md` §5 / §6 참조 (envelope 은 일반 `command` 형식).
`logs_subscribe` 의 requestId 가 곧 `streamId` 가 되고, 이후 `log_chunk` /
`log_stream_end` 모든 메시지가 이 streamId 를 참조.

Backend `_handle_browser_command` 에서:
- `logs_subscribe` forward 직전 → `command_router.record_stream(requestId, browser_channel, server_id, kind="logs")`
- `logs_unsubscribe` forward 직전 → `command_router.remove_stream(streamId)` (optimistic)

Browser disconnect 시 `_cleanup_browser_streams` 가 활성 stream 마다 kind
별로 `logs_unsubscribe` 또는 `exec_close` 발송 + registry 정리.

## type: `exec_chunk` / `exec_end`

Console exec (B4) 용 push 메시지. envelope 형식은 `log_chunk` / `log_stream_end`
와 동일한 **flat 구조** (`type` + key fields 직접). `execId == streamId` 로
라우팅됨.

### `exec_chunk`

```jsonc
{
  "type": "exec_chunk",
  "execId": "<exec-uuid>",            // exec_open 의 requestId
  "stream": "stdout",                  // "stdout" | "stderr". TTY 모드면 stdout 단일
  "data": "<base64-bytes>"             // raw bytes (ANSI escape 포함). xterm.js 가 해석
}
```

Backend 처리: `command_router.get_stream_info(execId)` 로 browser channel 조회
후 그대로 forward. DB 저장 안 함.

### `exec_end`

```jsonc
{
  "type": "exec_end",
  "execId": "<exec-uuid>",
  "exitCode": 0,                       // null 가능 (detach / TTY)
  "reason": "natural"                  // natural | kill | container_stopped | error | browser_disconnect
}
```

Backend 처리: forward + `remove_stream(execId)` + `ConsoleSession` row 의
`closed_at` / `duration_seconds` / `exit_code` / `close_reason` 갱신.

## 새 명령: `exec_open` / `exec_input` / `exec_resize` / `exec_close`

`docs/agent-protocol.md` §7 참조. `exec_open` 의 requestId 가 곧 `execId`
(== streamId), 이후 `exec_chunk` / `exec_end` 가 이 키로 라우팅. Backend
`_handle_browser_command` 에서:

- `exec_open` forward 직전 → `command_router.record_stream(requestId, browser_channel, server_id, kind="exec")` + `ConsoleSession.objects.create(...)`
- `exec_close` forward 직전 → `command_router.remove_stream(execId)` (optimistic)
- `exec_open` 실패 응답 시 → registry 정리 + `ConsoleSession.close_reason = error`
- Browser disconnect 시 → `_cleanup_browser_streams` 가 kind="exec" entry 별로 `exec_close` 발송 + `ConsoleSession.close_reason = "browser_disconnect"`

## type: `command_response` (Agent → Browser)

명령 처리 최종 결과. requestId로 라우팅.

```jsonc
{
  "type": "command_response",
  "requestId": "<uuid>",
  "success": true,                  // false 면 data 생략, error 필드 사용
  "data": { ... },                  // command 별 schema (agent-protocol.md 참조)
  "error": "<msg>"                  // success=false 일 때만
}
```

Backend `MonitoringConsumer._update_request_from_response`가 ContainerRequest DB 갱신:
- `success=true` + `action=create` → Container row create/update + status=`deployed` + percent=100
- `success=true` + `action=delete` → Container row delete
- `success=false` → status=`failed` + progress_message=`error`

## type: `command_progress` (배포 진행률)

장기 명령(compose_up, create_container 등) 중간 진행률. Agent가 여러 번 push.

```jsonc
{
  "type": "command_progress",
  "requestId": "<uuid>",
  "message": "이미지 pull 중... (3/5)",
  "percent": 60                     // 0-100, optional
}
```

Backend 처리:
1. 같은 requestId로 매칭되는 Browser 채널에 그대로 forward
2. `ContainerRequest.progress_message` / `progress_percent` DB 갱신
3. 첫 progress 수신 시 status `approved` → `deploying` 전환
4. global 채널로도 broadcast (사용자 페이지가 자기 요청 progress 받음)

## type: `heartbeat` (좀비 세션 감지)

Backend → Agent, 15초 간격. payload: `{"type": "heartbeat"}` (다른 필드 없음).

Agent가 일정 시간 heartbeat 수신 안 되면 WS 끊고 재접속. `MonitoringConsumer._send_heartbeat_loop`.

## type: `connection` (접속 확인)

Backend가 connect 직후 1회 송신.

```jsonc
{
  "type": "connection",
  "message": "Connected to server <id>",
  "server_id": "<id>",
  "client_type": "agent" | "browser"
}
```

`/ws/global/`은 `{ "type": "connection", "channel": "global", "message": "Connected to global events channel." }`.

## type: `agent_status_change` (global)

Agent online ↔ offline 전환 시 `GlobalEventsConsumer` group으로 broadcast.

```jsonc
{
  "type": "agent_status_change",
  "status": "online",                // 또는 "offline"
  "server_id": "<uuid>",
  "hostname": "server_16",
  "last_seen_at": "2026-04-29T14:00:00Z",
  "previous_offline_seconds": 320    // null 가능 (최초 접속 시)
}
```

## Backend 저장 정책

- 모든 raw 필드 → `system_metrics_history.raw_data` JSONB 에 그대로.
- Hot path 필드 (sparkline / aggregation 대상) → `payload_map.py` 정의 따라 column 화.
- Migration 적용 안 된 필드 → `_db_columns()` 체크해서 raw_data 만 저장 (fallback).

새 필드 추가 절차:
1. 이 문서 schema 갱신 + frontmatter `last-synced-commit` 갱신
2. `apps/metrics/payload_map.py` 매핑 추가
3. `python manage.py makemigrations metrics` (column 추가 자동 생성)
4. `tasks.py` 의 `_collect_*_metrics` 가 map 따라 자동 extract — 코드 변경 최소화
5. `viewsets.py` `buckets()` annotations 에 Avg/Max 추가
6. Frontend `bucketsToSparkline` / chart 매핑에서 새 필드 사용

## 변경 이력

- 2026-04-29 (`7f82ff8`): `containers` / `command_progress` / `heartbeat` / `connection` /
  `agent_status_change` 메시지 카탈로그에 추가. 기존 system/container metrics 변경 없음.
- 2026-04-27: 초안. memory.available + gpu 배열 표준화 명시.
## Optional workspace payload

When a template enables ML workspace access, backend `create_container` includes
`params.workspace`:

```json
{
  "kind": "jupyter",
  "token": "<plaintext token, do not log>",
  "port": 8888,
  "baseUrl": "/workspace/<container-request-id>/",
  "workdir": "/workspace"
}
```

Agent success response should include `data.workspace.internalPort`,
`baseUrl`, `kind`, and optional `health`. For normal workspace networking,
include `hostPort`. For `networkPolicy=internal_only`, do not publish the
workspace port on the host; return `hostPort: null` or omit it, keep the
workspace container on the shared internal Docker network, and include
`health.networkPolicy="internal_only"` plus the network name when available.
The backend then reaches `<container name>:<internalPort>` over Docker DNS. If
the `workspace` field is absent, existing non-workspace container creation
behavior is unchanged.

## Optional model preparation payload

`prepare_model_assets` uses `ModelPrepareJob.id` as `requestId`. Progress
messages should include:

```json
{
  "type": "command_progress",
  "requestId": "<model-prepare-job-id>",
  "message": "copying model bytes",
  "percent": 42,
  "data": {
    "bytesDone": 4200,
    "percent": 42
  }
}
```

Final success must include an agent-local cache path that can later be mounted
read-only by `create_container.params.modelMounts[]`:

```json
{
  "type": "command_response",
  "requestId": "<model-prepare-job-id>",
  "success": true,
  "data": {
    "cachePath": "/var/lib/hypercube-agent/model-cache/<asset>/<version>",
    "sha256": "<sha256>"
  }
}
```

The backend stream endpoint is `/api/model-versions/{id}/content/`. It accepts
only `Authorization: Bearer agent_...` for an approved agent with an active
prepare job for the same model version. External URLs, public registries,
Hugging Face, Git, S3, package installs, and arbitrary user URLs are not valid
model sources.

For `prepare_model_assets`, `assets[].sha256` is canonical. The backend also
sends `assets[].checksum`, `assets[].source.sha256`, and
`assets[].source.checksum` as compatibility aliases. Agent implementations
should accept the canonical field and may use the aliases only as fallback.
