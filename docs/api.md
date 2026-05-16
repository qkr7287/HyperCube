---
last-synced-commit: 7f82ff8
source-of-truth: backend/config/urls.py + backend/apps/*/urls.py + backend/apps/*/viewsets.py
verify: cd backend && python -c "from config.urls import urlpatterns; print('\n'.join(str(p.pattern) for p in urlpatterns))"
---

# REST API

## GPU Inventory Endpoint

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/agents/{id}/gpus/` | GET | Authenticated | Latest GPU devices and allocatable slices reported by the Agent. |

## GPU Allocation Request Fields

```json
{
  "gpu_slice_ids": [1],
  "gpu_share_ok": false
}
```

`gpu_slice_ids` writes `ContainerRequestGpuSlice` rows and
`gpu_slice_ids_snapshot`; approval reserves those rows as `GpuAllocation`
records before dispatching `create_container.gpus`.

전체 REST 엔드포인트 카탈로그. Swagger UI는 `/api/docs/`, OpenAPI schema는 `/api/schema/`.

## Entry Points

`backend/config/urls.py`:

| Path | Method | Auth | Notes |
|------|--------|------|-------|
| `/api/health/` | GET | AllowAny | health check (`{"status": "ok"}`) |
| `/api/schema/` | GET | AllowAny | OpenAPI 3.0 schema (drf-spectacular) |
| `/api/docs/` | GET | AllowAny | Swagger UI |
| `/api/auth/token/` | POST | AllowAny | JWT 발급 (`CustomTokenObtainPairView`) |
| `/api/auth/token/refresh/` | POST | AllowAny | JWT refresh (`TokenRefreshView`) |
| `/api/auth/logout/` | POST | Authenticated | refresh token 블랙리스트 (`LogoutView`) |
| `/django-admin/` | — | — | Django admin (frontend `/admin` 과 분리) |
| `/__debug__/` | — | DEBUG only | django-debug-toolbar |

App APIs는 `/api/` 아래에 mount: `apps.agents.urls`, `apps.containers.urls`, `apps.users.urls`, `apps.metrics.urls`.
Container APIs are also mounted under `/api/v1/` for the resource-limit rollout contract.

## Authentication

JWT (SimpleJWT). `CustomTokenObtainPairView` (`apps.users.token_views`) 사용.

```http
POST /api/auth/token/
{
  "username": "admin",
  "password": "..."
}

→ { "access": "<token>", "refresh": "<token>" }
```

이후 `Authorization: Bearer <access>` 헤더로 요청. 만료 시 `/api/auth/token/refresh/`로 갱신.

## Agents — `/api/agents/`

`apps.agents.viewsets.AgentViewSet` (ModelViewSet).

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/agents/` | GET | Authenticated | 목록. `?active=true`로 5분 이내 활성만, `?status=`, `?search=hostname` |
| `/api/agents/` | POST | **AllowAny** | Agent 자가 등록 + 자동 승인 (idempotent: hostname 중복이면 기존 토큰 반환) |
| `/api/agents/{id}/` | GET | Authenticated | 상세 |
| `/api/agents/{id}/` | PATCH/PUT | ServerAdmin+ | 수정 |
| `/api/agents/{id}/` | DELETE | SuperAdmin | 삭제 (연결 컨테이너도 cascade) |
| `/api/agents/{id}/status/` | GET | **AllowAny** | 상태 + token 조회 (Agent 부팅 시 사용) |
| `/api/agents/{id}/latest-metrics/` | GET | Authenticated | Redis에서 system_metrics 최신값 (`server:{id}:system`) |

**자동 승인 동작 주의**: `POST /api/agents/`는 hostname 중복 시 기존 Agent의 token을 그대로 반환. 새 Agent면 즉시 `status=approved`, `approved_at=now`, token 발급. IP는 백엔드가 관측한 nginx peer (X-Real-IP > REMOTE_ADDR > X-Forwarded-For)로 강제.

Agent 응답에는 host capacity/report 상태도 포함된다:
`cpu_cores`, `cpu_model`, `ram_total_mb`, `disk_total_gb`,
`workspace_pool_total_gb`, `workspace_pool_free_gb`, `workspace_pool_mount`,
`workspace_hard_enforcement`, `nic_speed_mbps`, `filesystem`, `target_users`,
`safety_margin`, `capacity_updated_at`. `capacity_report` WebSocket 메시지가
도착하면 backend가 이 필드를 갱신한다.

## Containers — admin 전용

`apps.containers.viewsets.ContainerViewSet` (ModelViewSet, IsAdmin).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/containers/` | GET / POST | 전체 컨테이너 CRUD (admin) |
| `/api/containers/recommend/?template=<uuid>&agent=<uuid>` | GET | 인증 사용자용 자원 한도 추천. template weight + agent capacity 기반으로 `cpu_percent`, `memory_mb`, `workspace_gb` 반환 |
| `/api/v1/containers/recommend/?template=<uuid>&agent=<uuid>` | GET | Same recommendation endpoint exposed at the sprint contract path. |
| `/api/containers/{id}/` | GET / PATCH / DELETE | |

**필터**: `?agent=<uuid>`, `?status=`, `?requester=<uuid>`, `?search=name|image`.

## MyContainers — 사용자별 컨테이너

`apps.containers.viewsets.MyContainerViewSet` (ReadOnlyModelViewSet, IsAuthenticated). 자기가 직접 요청해 생성된 컨테이너만 조회.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/my-containers/` | GET | 자기 컨테이너 목록 |
| `/api/my-containers/{id}/` | GET | 상세 |
| `/api/my-containers/{id}/current-metrics/` | GET | Redis 캐시에서 실시간 cpu/memory/network/disk/workspace |
| `/api/my-containers/{id}/metrics-history/?range=1h&limit=240` | GET | DB에서 시계열 (range: `1m/5m/1h/6h/24h/7d`, limit max 500) |
| `/api/my-containers/{id}/inspect/` | GET | Agent에 inspect 명령을 보내고 응답까지 동기 대기 (최대 15s). state.health, mounts, networkSettings 등 포함 |
| `/api/my-containers/{id}/control/` | POST | 라이프사이클 제어. body `{"action": "start\|stop\|restart\|pause\|unpause\|kill"}`. remove 는 `/api/requests/` (action=delete) 로 분리. |
| `/api/my-containers/{id}/events/?since=&limit=100` | GET | 라이프사이클 이벤트 (ContainerEvent). agent의 `container_events` 메시지 누적. 시간 오름차순. limit max 500. |
| `/api/my-containers/{id}/processes/?sortBy=cpu&limit=20` | GET | 컨테이너 내부 process top-N. agent `container_processes` 명령 dispatch + 동기 대기 (15s). sortBy: `cpu` \| `mem`, limit 1~100. minimal image 도 동작 (호스트 관찰). |
| `/api/my-containers/{id}/console-sessions/?limit=50` | GET | B4 Console exec audit 조회. 세션 레벨만 (user / cmd / opened_at / closed_at / duration_seconds / exit_code / close_reason). 키스트로크 미기록. limit max 200. |
| `/api/my-containers/{id}/update-limits/` | POST | P0 자원 한도 / 재시작 정책 수정. body `{memory_mb?, cpu_percent?, restart_policy?, restart_max_retry?}`. agent `update_container` 명령 dispatch + 동기 대기. 한 필드만 보내도 그것만 갱신. |

Container 응답에는 현재 limit snapshot 필드가 포함된다:
`cpu_percent_limit`, `memory_mb_limit`, `workspace_gb_limit`,
`workspace_device` (mount path), `workspace_project_id` (XFS project id),
`limit_updated_at`. `cpu_percent_limit`은 100 = 1 core quota 기준이다.
생성 요청의 resource limit 값은 Agent 성공 응답으로 Container row가
만들어질 때 이 snapshot으로 복사된다. `update-limits` 성공 시
CPU/메모리 snapshot과 `limit_updated_at`도 갱신된다.
`current-metrics`는 agent가 보낸 `workspace.usedGb`, `workspace.hardGb`
(legacy `sizeGb` 도 fallback), `workspace.usedPct`를 그대로 반환하고,
DB의 `workspace_gb_limit` / `workspace_device` / `workspace_project_id`
를 보조 분모로 merge한다.

## Workspaces — `/api/workspaces/`

ML/Jupyter workspace containers. Plaintext Jupyter tokens are kept in Redis and
are not serialized through this API.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/workspaces/` | GET | admin은 전체, user는 자기 workspace만 |
| `/api/workspaces/{container_id}/` | GET | workspace 상세 |
| `/api/workspaces/{container_id}/open/` | POST | one-time open ticket URL 발급. 응답: `{url, expiresInSeconds}` |
| `/api/workspaces/{container_id}/extend-runtime/` | POST | body `{additional_hours}`. runtime expiry와 Redis token TTL 연장 |

Open URL은 `/workspace/<workspace_key>/lab?ticket=...` 형태다.
MVP의 `workspace_key`는 `ContainerRequest.id`다. Docker container ID는
생성 후에만 알 수 있으므로, agent `create_container` 시점에 주입해야 하는
Jupyter `baseUrl`은 request ID 기반 path를 사용한다.

## Model Catalog — `/api/model-assets/`

Airgap model storage. No external URL import path is exposed.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/model-assets/` | GET / POST | 모델 asset 목록/생성. user는 자기 asset + shared asset 조회 |
| `/api/model-assets/{id}/` | GET / PATCH / DELETE | owner/admin만 수정/삭제 |
| `/api/model-assets/{id}/versions/upload/` | POST multipart | body `version`, `file`, optional `metadata`. `HC_MODEL_STORAGE_DIR`에 저장하고 sha256 계산 |
| `/api/model-assets/{id}/versions/import/` | POST | admin only. `HC_MODEL_IMPORT_DIR` 내부 파일만 import |
| `/api/model-versions/` | GET | 접근 가능한 모델 version 목록 |

`current-metrics` 응답:
```json
{
  "timestamp": "2026-04-29T14:00:00Z",
  "containerId": "abc123def456",
  "cpu": { "usage": 605.2, "cores_quota": 8, "usage_pct": 75.65 },
  "memory": { "usage": 1073741824, "limit": 4294967296, "percent": 25.0 },
  "network": { "rx": 12345, "tx": 6789 },
  "disk": { "read": 12698, "write": 4194304 },
  "workspace": {
    "device": "/dev/vg0/cid_abc123def456",
    "sizeGb": 100,
    "usedGb": 12,
    "availableGb": 88,
    "usedPct": 12.0
  }
}
```
캐시 미스 시 모든 값 null.

`inspect` / `control` 동작:
- 둘 다 backend → Agent WS로 명령 발송 → Agent의 `command_response`를 Redis에 저장 → REST endpoint가 polling (100ms 간격, 15s 타임아웃) 후 반환.
- Agent 오프라인 → `503 Service Unavailable`, 타임아웃 → `504 Gateway Timeout`, dispatch 실패 → `502 Bad Gateway`.
- Agent의 inspect/control schema 는 `agent-protocol.md` §2 / §3 참조. `inspect` 응답 본문은 Agent `data` 그대로 (`state`, `image`, `config`, `networkSettings`, `mounts`, `restartCount`).
- `control` 성공 시 `{ "containerId": "...", "action": "...", "success": true }`. 권한: `IsAuthenticated` + `MyContainerViewSet.get_queryset` 가 `requester=self.request.user` 로 필터하므로 본인 컨테이너만 가능.

## Templates — `/api/templates/`

`apps.containers.viewsets.ContainerTemplateViewSet`. 컨테이너 생성 시 사용할 사전 정의 템플릿.

| Method | Auth | Description |
|--------|------|-------------|
| GET (list/retrieve) | Authenticated | 모든 사용자 조회 |
| POST/PATCH/DELETE | IsAdmin | 작성/수정/삭제 |

**Filter**: `?kind=` (`compose` | `image`), `?search=name|description`.

Template payload에는 자원 추천/하한 필드가 포함된다:
`cpu_weight`, `ram_weight`, `disk_weight`, `min_cpu_percent`,
`min_memory_mb`, `min_workspace_gb`. 추천 helper는 Agent capacity와 이 weight를
조합하고, 요청값 검증은 min floor 아래 값을 거부한다.

## Requests — `/api/requests/`

컨테이너 생성/삭제 요청. `apps.containers.viewsets.ContainerRequestViewSet`.

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/requests/` | GET | Authenticated | admin은 전체, user는 자기 것만 |
| `/api/requests/` | POST | Authenticated | `action=create` 또는 `action=delete`로 새 요청. 상태=pending |
| `/api/requests/{id}/` | GET | Authenticated | 상세 |
| `/api/requests/{id}/` | DELETE | Authenticated | pending/rejected/failed 상태만 삭제 가능 |
| `/api/requests/{id}/approve/` | POST | **IsAdmin** | 승인 + Agent에 명령 발송 (compose_up / create_container / delete_container) |
| `/api/requests/{id}/reject/` | POST | **IsAdmin** | 반려 |

`action=create` 요청은 resource limit 필드를 받을 수 있다:
`cpu_percent`, `memory_mb`, `workspace_gb`. 모두 optional이며 누락 시
backend가 `target_agent` capacity와 template weight로 추천값을 계산해 저장한다.
Template의 `min_cpu_percent`, `min_memory_mb`, `min_workspace_gb`보다 작은 값은
`400 Bad Request`로 거부된다.

approve 시 dispatch 흐름은 `agent-protocol.md` 참조. requestId = ContainerRequest.id로 사용되며, Agent의 `command_response`/`command_progress`가 같은 requestId로 라우팅된다.

## Users — `/api/users/`

`apps.users.viewsets.UserViewSet` (ModelViewSet).

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/users/` | GET / POST / PATCH / DELETE | **SuperAdmin** | CRUD |
| `/api/users/me/` | GET | Authenticated | 내 정보 (모든 viewer 이상) |

**Roles**: `super_admin` (전체) / `server_admin` (할당 서버 관리) / `viewer` (읽기 전용).

## Metrics — 시계열 / 집계

`apps.metrics.viewsets.{System,Container,Stack}MetricsViewSet`. 모두 IsViewer (admin은 전체, viewer는 본인 소유 데이터만).

### System metrics

`SystemMetricsHistory` 시계열.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metrics/system/` | GET | 시계열 raw rows. `?agent=<uuid>`, `?range=1h`, `?limit=N` (max 2000), `?from_time=`, `?to_time=` |
| `/api/metrics/system/{id}/` | GET | 단일 row + raw_data JSONB |
| `/api/metrics/system/buckets/?range=7d&bucket=1d` | GET | bucket 집계 (60s 캐시). bucket: `30s/1m/5m/...1w` 또는 초 단위 정수 |

집계 응답:
```json
{
  "bucket_seconds": 86400,
  "results": [
    {
      "agent": "...",
      "bucket_epoch": 1714521600,
      "bucket_start": "2026-04-30T00:00:00+09:00",
      "cpu_avg": 45.2, "cpu_max": 99.1,
      "memory_avg": 46.6, "memory_max": 50.1,
      "memory_used_avg": 19419971584,
      "memory_total_avg": 41691742208,
      "memory_available_avg": 22271770624,
      "disk_avg": 81.8, "disk_max": 81.9,
      "network_rx_max": 535472170965, "network_tx_max": 123826608774,
      "gpu_avg": 12.3, "gpu_max": 80.4,
      "gpu_memory_used_avg": 2147483648, "gpu_memory_total_avg": 8589934592,
      "gpu_temperature_max": 72.0,
      "sample_count": 8640
    }
  ]
}
```
GPU / memory_available 필드는 migration 0005 적용된 환경에서만 채워짐. 미적용 시 omitted.

### Container metrics

`ContainerMetricsHistory` 시계열.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metrics/containers/` | GET | `?agent=` 또는 `?container_id=` 필수 (cross-server 폭발 방지) |
| `/api/metrics/containers/{id}/` | GET | 단일 row |
| `/api/metrics/containers/buckets/` | GET | bucket 집계 |

bucket 응답에 cpu가 3가지 형태: `cpu_usage_pct_avg/max` (0-100 정규화), `cpu_usage_avg/max` (raw 코어 합산), `cpu_avg/max` (호환용 = pct 와 동일). `cpu_cores_quota_avg`도 포함.

### Stack metrics

`docker compose project` 또는 `hypercube.stack` 라벨 단위 집계.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/metrics/stacks/buckets/?stack=<name>&range=1h&bucket=1m` | GET | 스택별 bucket 집계 (list/retrieve 미노출) |

## WebSocket

REST가 아니라 별도 channels routing (`backend/config/routing.py`):

| Path | Consumer | 용도 |
|------|----------|------|
| `/ws/server/{server_id}/` | `MonitoringConsumer` | Agent 송신 + Browser 수신 + browser → agent command |
| `/ws/global/` | `GlobalEventsConsumer` | global 이벤트 (agent_status_change 등) browser broadcast |

상세는 `agent-payload-contract.md` (메시지 schema) 와 `agent-protocol.md` (command 4종 + 컨테이너 배포 3종).

## 변경 시 절차

1. `backend/apps/{containers,agents,metrics,users}/{urls,viewsets,serializers}.py` 수정
2. 이 파일 (`docs/api.md`) 동기화
3. frontmatter `last-synced-commit`을 `git rev-parse --short HEAD`로 갱신
4. `python manage.py spectacular --file schema.yaml` 로 OpenAPI 검증
