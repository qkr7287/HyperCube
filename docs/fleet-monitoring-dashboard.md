# HyperCube Always-On Fleet Monitoring Dashboard Plan

이 문서는 Claude Code 또는 다른 구현 에이전트가 바로 작업에 들어갈 수 있도록 작성한 상세 구현 계획이다.

목표는 기존 HyperCube의 "선택한 단일 서버를 3D 토폴로지로 보는 화면"과 별개로, 관리자용 **항상 켜두는 전체 서버 2D 모니터링 대시보드**를 만드는 것이다.

## 0. Implementation Command Brief

Claude Code가 처음 구현할 때는 아래 범위를 우선한다.

### First Target: REST-Only MVP

1. `/admin/dashboard`를 만든다.
2. 모든 approved, non-archived agent 서버를 한 화면에 표시한다.
3. 서버를 선택하지 않아도 전체 상태와 전체 사용 추이를 볼 수 있어야 한다.
4. Phase 1에서는 fleet WebSocket을 만들지 않는다.
5. Phase 1에서는 REST polling만 사용한다.
6. polling 주기는 기본 15초로 둔다.
7. 전체 trend chart는 Chart.js를 사용한다.
8. 테이블 row sparkline은 간단한 SVG 또는 canvas로 만든다. Chart.js를 row마다 만들지 않는다.
9. UI는 기존 admin page 분위기를 따른다.
10. 기존 admin page보다 더 간결하고 밀도 높은 monitoring UI로 만든다.
11. 모든 주요 데이터 라벨 옆에는 `?` 도움말 아이콘을 둔다.
12. `?` 아이콘 hover/focus 시 짧은 설명 tooltip을 보여준다.
13. `/admin/requests`, `/admin/templates`, 기존 3D 화면은 깨지면 안 된다.

### Do Not Do In First Target

- fleet WebSocket 구현
- 7일 이상 장기 trend
- per-container 상세 metric table
- 알림/경보 설정 UI
- 대규모 DB aggregation 최적화
- 새로운 chart library 도입
- 기존 3D topology 대규모 수정

### First Target Acceptance Criteria

- `/admin/dashboard`가 admin login 후 접근된다.
- 상단에서 total, online, offline, warning, critical, stale 개수를 볼 수 있다.
- 전체 CPU, memory, disk, network 사용 추이를 볼 수 있다.
- 서버별 CPU, memory, disk, network, container summary, last seen을 볼 수 있다.
- 위험 서버가 table 상단 또는 right panel에 자연스럽게 노출된다.
- data age가 보인다.
- 데이터가 없거나 agent가 offline이어도 화면이 깨지지 않는다.
- 모든 metric 제목 옆 `?` tooltip이 keyboard focus와 mouse hover에서 동작한다.
- 1920x1080에서 핵심 monitoring 정보가 한 화면에 들어온다.
- 1366x768에서도 주요 상태가 겹치지 않는다.
- frontend `npm run check`가 통과한다.

## 1. Product Goal

새 대시보드는 운영자가 브라우저 한 탭을 계속 띄워두는 화면이다.

이 화면 하나만 보고도 다음을 즉시 판단할 수 있어야 한다.

- 현재 연결된 전체 agent 서버 수
- online, offline, warning, critical 서버 수
- 전체 서버의 CPU, memory, disk, network 사용 추이
- 서버별 최신 사용률과 최근 5분/1시간 추이
- 어떤 서버가 위험한지
- 어떤 서버에서 container 상태 이상이 있는지
- 마지막 metric 수신 시각과 데이터 신선도

중요한 점:

- 이 화면의 핵심은 컨테이너 관계 탐색이 아니라 **fleet monitoring**이다.
- 3D 화면은 선택 서버 상세/탐색용으로 유지한다.
- 2D 대시보드는 전체 agent 서버를 동시에 감시하는 NOC 스타일 화면이다.

## 2. Existing Codebase Context

현재 구조에서 재사용할 수 있는 기반:

- Frontend: `frontend/src/routes/admin/+layout.svelte`
- Admin header: `frontend/src/lib/components/AdminHeader.svelte`
- Global events WS: `frontend/src/lib/stores/global-events.ts`
- Single-server WS store: `frontend/src/lib/stores/ws-store.ts`
- Agent model/API: `backend/apps/agents/models.py`, `backend/apps/agents/viewsets.py`
- Metric history model/API: `backend/apps/metrics/models.py`, `backend/apps/metrics/viewsets.py`
- Redis latest metric cache: `backend/apps/common/consumers.py`
- Metric persistence task: `backend/apps/metrics/tasks.py`
- Container model: `backend/apps/containers/models.py`

현재 metric 흐름:

```text
Agent
  -> /ws/server/{agent_id}/
  -> MonitoringConsumer
  -> Redis latest cache
     - server:{agent_id}:system
     - server:{agent_id}:containers
     - server:{agent_id}:container:{container_id}:metrics
     - server:active_ids
  -> Celery flush_metrics_to_db
  -> SystemMetricsHistory / ContainerMetricsHistory
```

현재 한계:

- 기존 `ws-store.ts`는 selected server 1개 기준이다.
- `/api/agents/{id}/latest-metrics/`는 단일 agent 기준이다.
- `/api/metrics/system/`은 history list는 가능하지만 fleet dashboard에 바로 쓰기 좋은 aggregate API가 없다.
- global WS는 agent online/offline event 중심이고, 모든 서버의 live metric stream을 주지는 않는다.

따라서 새 기능은 **admin fleet API + admin fleet WebSocket + admin dashboard frontend**로 나눈다.

## 3. Target Route

관리자 대시보드 기본 진입점:

```text
/admin/dashboard
```

선택 사항:

- `/admin` 접근 시 `/admin/dashboard`로 redirect한다.
- 기존 `/admin/requests`, `/admin/templates`는 유지한다.
- `AdminHeader.svelte` nav에 `Dashboard` 항목을 추가한다.

추천 nav:

```text
Dashboard | Requests | Templates | 3D View
```

`3D View`는 기존 `/` 또는 별도 이름으로 연결한다.

## 4. Dashboard UX Requirements

### 4.1 Always-On Behavior

대시보드는 장시간 켜둘 화면이다.

필수 UX:

- 자동 갱신
- WebSocket 연결 상태 표시
- 마지막 수신 시각 표시
- 데이터 stale 여부 표시
- offline 서버는 숨기지 않고 계속 표시
- warning/critical 서버는 화면 상단 또는 별도 패널에 노출
- 테이블 정렬은 위험도 우선이 기본값
- 수동 refresh 버튼 제공
- 시간 범위 선택: `5m`, `1h`, `24h`

초기 MVP는 `5m`, `1h`, `24h`만 구현한다.

### 4.2 Visual Direction

UI는 현재 HyperCube 관리자 페이지와 같은 제품군처럼 보여야 한다.

기존 admin UI에서 유지할 것:

- 어두운 배경 기반의 운영 도구 분위기
- `AdminHeader.svelte` 기반 상단 navigation
- 기존 CSS 변수와 spacing 감각
- compact table, muted border, restrained accent color
- 요청/템플릿 관리 페이지와 이질감 없는 패널 스타일

새 dashboard에서 더 강화할 것:

- 더 간결한 정보 구조
- monitoring 목적에 맞는 빠른 스캔성
- 상태와 추이를 우선하는 화면 배치
- 불필요한 장식 제거
- 같은 의미의 숫자와 chart를 가까이 배치
- 위험 상태는 더 빨리 눈에 들어오게 표현
- 세부 정보는 필요할 때 자연스럽게 펼쳐지는 흐름

피해야 할 것:

- landing page 같은 hero layout
- 과한 카드 나열
- 카드 안의 카드
- 큰 marketing headline
- 장식용 그래픽
- 3D canvas
- 의미 없는 gradient background
- 한 화면에서 너무 많은 색상 사용
- 모든 데이터를 같은 강도로 강조하는 UI

### 4.3 Visual Priority

관제 화면이므로 다음 우선순위를 지킨다.

1. 위험 상태가 멀리서도 보여야 한다.
2. 전체 추이가 가장 먼저 보여야 한다.
3. 서버별 상태는 스캔하기 쉬운 표 형태가 기본이다.
4. 카드 남발보다 밀도 있는 정보 배치가 낫다.
5. 3D, decorative visual, hero section은 사용하지 않는다.

추천 레이아웃:

```text
[Admin Header]

[Fleet Status Bar]
Total | Online | Offline | Warning | Critical | Last Updated | WS State

[Global Trend Area]
CPU avg/max chart | Memory avg/max chart | Disk avg/max chart | Network RX/TX chart

[Main Monitoring Grid]
Left / Main:
  Agent Health Table
  hostname | state | CPU | Memory | Disk | Network | Containers | last seen | sparkline

Right:
  Risk Servers
  Stale Agents
  Pending Requests Summary

[Selected Agent Drawer or Lower Panel]
  selected server detailed trend
  container state distribution
  link to 3D detail view
```

### 4.4 UX Flow

사용자가 화면을 보는 자연스러운 순서는 다음과 같아야 한다.

1. 상단 status bar에서 전체 fleet 상태를 본다.
2. global trend chart에서 전체 사용 추이가 안정적인지 본다.
3. risk panel에서 지금 가장 위험한 서버를 본다.
4. agent table에서 서버별 상태를 비교한다.
5. 특정 서버가 궁금하면 row를 클릭해 selected agent panel을 연다.
6. 컨테이너 관계 탐색이 필요할 때만 기존 3D view로 이동한다.

이 흐름을 위해 UI는 다음을 지켜야 한다.

- 첫 화면에서 사용자가 서버를 선택하게 만들지 않는다.
- server selector 중심 UI로 만들지 않는다.
- 기본 정렬은 위험도 우선이다.
- row click은 상세 보기이고, destructive action은 없어야 한다.
- chart range 변경은 전체 chart와 selected agent panel에 자연스럽게 반영된다.
- filter/search는 table의 보조 도구이며, 핵심 정보보다 앞에 나오지 않는다.
- refresh는 가능하되 자동 갱신이 기본이다.
- loading state가 전체 화면을 막지 않게 한다. 기존 데이터를 유지하고 작은 updating 표시를 사용한다.

### 4.5 Help Tooltip Requirement

모든 주요 데이터 라벨 옆에는 `?` 도움말 아이콘을 둔다.

목표:

- 사용자가 metric의 의미와 계산 기준을 즉시 이해할 수 있게 한다.
- 화면 안에 긴 설명문을 늘어놓지 않는다.
- monitoring 화면의 밀도와 간결함을 유지한다.

적용 대상:

- Total Agents
- Online
- Offline
- Warning
- Critical
- Stale
- CPU Avg
- CPU Max
- Memory Avg
- Memory Max
- Disk Avg
- Disk Max
- Network RX
- Network TX
- Containers
- Running
- Non-running
- Last Seen
- Metric Age
- Health
- Trend

Tooltip 규칙:

- 아이콘은 라벨 바로 옆에 둔다.
- 화면에 보이는 문자는 `?`를 사용한다.
- 버튼처럼 focus 가능해야 한다.
- hover와 keyboard focus 모두에서 tooltip이 열린다.
- tooltip 내용은 1-2문장으로 짧게 쓴다.
- tooltip은 metric의 의미, 단위, 계산 기준을 설명한다.
- tooltip 때문에 table/chart layout이 밀리면 안 된다.
- tooltip은 viewport 밖으로 잘리지 않게 배치한다.
- mobile에서는 tap으로 열리고 바깥을 누르면 닫히게 한다.

권장 컴포넌트:

```text
frontend/src/lib/components/fleet/MetricHelp.svelte
```

사용 예:

```svelte
<span class="metric-label">
  CPU Avg
  <MetricHelp text="All online agents' CPU usage averaged over the selected time range." />
</span>
```

Tooltip 문구 예:

```text
Total Agents: Approved, non-archived agents included in this monitoring view.
Online: Agents that reported activity within the active grace window.
Stale: Agents still online, but latest metrics are older than the freshness threshold.
CPU Avg: Average CPU usage across monitored agents for each chart bucket.
CPU Max: Highest CPU usage reported by any monitored agent in the same bucket.
Network RX: Received network traffic rate, calculated from byte counter deltas.
Metric Age: Time since the latest metric payload was received for this agent.
Health: Operational health derived from latest metrics, freshness, and container status.
```

Implementation notes:

- Prefer a small reusable tooltip component over repeated ad hoc markup.
- Do not import a new tooltip library for MVP.
- Use CSS absolute positioning and `aria-describedby` or `role="tooltip"` where practical.
- Keep the icon visually quiet: small circle, muted border, muted text.
- On hover/focus, raise contrast enough to be discoverable.

### 4.6 Server Health States

대시보드에서 agent status와 operational health를 분리한다.

Agent approval status:

- `pending`
- `approved`
- `rejected`
- `archived`

Operational health:

- `healthy`
- `warning`
- `critical`
- `offline`
- `stale`

판정 기준:

```text
offline:
  agent is not active or last_seen_at is null

stale:
  last metric timestamp older than 60 seconds

critical:
  cpu >= 90
  or memory >= 90
  or disk >= 90
  or dead/restarting container exists

warning:
  cpu >= 70
  or memory >= 75
  or disk >= 80
  or stopped/exited containers increased recently
  or last metric timestamp older than 30 seconds

healthy:
  online and below warning thresholds
```

Thresholds should be centralized in frontend and backend helpers so the UI and API agree.

Suggested frontend file:

```text
frontend/src/lib/utils/fleet-thresholds.ts
```

Suggested backend helper:

```text
backend/apps/metrics/fleet.py
```

## 5. Backend Implementation Plan

### 5.1 Add Fleet API

Add fleet-specific API endpoints under metrics or a small dedicated module.

Recommended path:

```text
backend/apps/metrics/fleet.py
backend/apps/metrics/urls.py
backend/apps/metrics/viewsets.py
```

Keep it in `apps.metrics` because this is monitoring/metric aggregation, not agent CRUD.

Endpoints:

```text
GET /api/metrics/fleet/summary/
GET /api/metrics/fleet/agents/
GET /api/metrics/fleet/history/?range=5m|1h|24h
GET /api/metrics/fleet/agents/{agent_id}/history/?range=5m|1h|24h
```

If DRF router style makes nested route awkward, use action methods:

```text
GET /api/metrics/fleet-summary/
GET /api/metrics/fleet-agents/
GET /api/metrics/fleet-history/
GET /api/metrics/fleet-agent-history/?agent=<uuid>
```

Prefer clean routes if low-risk.

Permissions:

- Admin only for fleet-wide data.
- Use `IsServerAdminOrAbove` or equivalent admin permission.
- Do not expose all-server fleet metrics to normal users.

### 5.2 Summary API Response

`GET /api/metrics/fleet/summary/`

Response shape:

```json
{
  "generated_at": "2026-04-22T08:00:00Z",
  "agent_counts": {
    "total": 12,
    "online": 10,
    "offline": 2,
    "warning": 3,
    "critical": 1,
    "stale": 1
  },
  "metric_summary": {
    "cpu_avg": 42.1,
    "cpu_max": 93.2,
    "memory_avg": 61.4,
    "memory_max": 91.0,
    "disk_avg": 57.8,
    "disk_max": 86.3,
    "network_rx_rate": 1240000,
    "network_tx_rate": 930000
  },
  "container_summary": {
    "total": 148,
    "running": 130,
    "stopped": 12,
    "paused": 1,
    "exited": 3,
    "restarting": 2,
    "dead": 0
  },
  "top_risks": [
    {
      "agent_id": "uuid",
      "hostname": "server-01",
      "health": "critical",
      "reason": "memory >= 90",
      "cpu_usage": 81.4,
      "memory_usage": 91.0,
      "disk_usage": 72.5,
      "last_seen_at": "2026-04-22T08:00:00Z",
      "metric_timestamp": "2026-04-22T07:59:57Z"
    }
  ]
}
```

Implementation notes:

- Use `Agent.objects.prefetch_related("containers")`.
- Read latest metrics from Redis keys `server:{agent.id}:system`.
- Read latest containers from DB relation first; Redis `server:{agent.id}:containers` can be used if a more live count is needed.
- If Redis latest metric is missing, fall back to latest `SystemMetricsHistory`.
- Do not query one history row per agent in a loop if avoidable. For MVP, N+1 is acceptable for small fleets, but add a comment or helper so it can be optimized later.

### 5.3 Fleet Agents API Response

`GET /api/metrics/fleet/agents/`

This feeds the main table.

Response shape:

```json
{
  "generated_at": "2026-04-22T08:00:00Z",
  "results": [
    {
      "agent": {
        "id": "uuid",
        "hostname": "server-01",
        "ip_address": "10.0.0.11",
        "status": "approved",
        "is_active": true,
        "last_seen_at": "2026-04-22T08:00:00Z"
      },
      "health": "warning",
      "health_reasons": ["disk >= 80"],
      "latest": {
        "timestamp": "2026-04-22T07:59:57Z",
        "cpu_usage": 48.2,
        "memory_usage": 62.1,
        "memory_used": 123456789,
        "memory_total": 987654321,
        "disk_usage": 82.0,
        "network_rx": 1000000000,
        "network_tx": 400000000,
        "network_rx_rate": 120000,
        "network_tx_rate": 90000,
        "processes_total": 208,
        "logins_total": 3
      },
      "containers": {
        "total": 18,
        "running": 15,
        "stopped": 2,
        "paused": 0,
        "exited": 1,
        "restarting": 0,
        "dead": 0
      },
      "sparkline": {
        "cpu": [32.1, 35.4, 38.9],
        "memory": [60.2, 61.1, 62.1],
        "disk": [81.7, 81.8, 82.0]
      }
    }
  ]
}
```

Implementation notes:

- `sparkline` should be short and cheap, around 20 points.
- For MVP, sparkline can be omitted from initial response and fetched through history endpoint after render. But including it improves the always-on dashboard.
- Network rates require delta calculation from cumulative `network_rx`/`network_tx`. Use adjacent history points.

### 5.4 Fleet History API Response

`GET /api/metrics/fleet/history/?range=5m|1h|24h`

This feeds aggregate charts across all agents.

Response shape:

```json
{
  "range": "1h",
  "bucket_seconds": 60,
  "points": [
    {
      "timestamp": "2026-04-22T07:00:00Z",
      "agent_count": 10,
      "cpu_avg": 42.1,
      "cpu_max": 88.0,
      "memory_avg": 61.4,
      "memory_max": 91.0,
      "disk_avg": 57.8,
      "disk_max": 86.3,
      "network_rx_rate": 1240000,
      "network_tx_rate": 930000,
      "running_containers": 130,
      "non_running_containers": 18
    }
  ]
}
```

Bucket recommendations:

```text
5m: 10 second or 30 second buckets, depending available data
1h: 60 second buckets
24h: 5 minute buckets
```

Current Celery persistence appears to flush every 30 seconds, so:

- `5m`: 30s buckets are acceptable
- `1h`: 60s buckets
- `24h`: 5m buckets

Implementation can initially use Python bucketing after fetching rows. Keep max rows bounded.

### 5.5 Single Agent History API Response

`GET /api/metrics/fleet/agents/{agent_id}/history/?range=5m|1h|24h`

Feeds selected server drawer/panel.

Response shape:

```json
{
  "agent": {
    "id": "uuid",
    "hostname": "server-01"
  },
  "range": "1h",
  "points": [
    {
      "timestamp": "2026-04-22T07:00:00Z",
      "cpu_usage": 42.1,
      "memory_usage": 61.4,
      "disk_usage": 57.8,
      "network_rx_rate": 1240000,
      "network_tx_rate": 930000,
      "processes_total": 208,
      "logins_total": 3
    }
  ]
}
```

### 5.6 Add Admin Fleet WebSocket

Add an admin-only WebSocket that broadcasts fleet-level metric updates.

Route:

```text
/ws/admin/fleet/
```

Files:

```text
backend/apps/common/consumers.py
backend/config/routing.py
frontend/src/lib/stores/fleet-store.ts
```

Consumer name:

```python
class AdminFleetConsumer(AsyncWebsocketConsumer):
    ...
```

Authentication:

- Must require authenticated user.
- Must reject agents.
- Must require admin role.

Suggested message types:

```json
{
  "type": "fleet_snapshot",
  "summary": {},
  "agents": []
}
```

```json
{
  "type": "agent_metric_update",
  "agent_id": "uuid",
  "hostname": "server-01",
  "health": "warning",
  "latest": {},
  "containers": {}
}
```

```json
{
  "type": "agent_status_change",
  "agent_id": "uuid",
  "hostname": "server-01",
  "status": "offline",
  "last_seen_at": "..."
}
```

Implementation options:

Option A, simple MVP:

- Frontend polls REST every 15 seconds.
- Reuse existing `/ws/global/` for online/offline events.
- Add admin fleet WS in Phase 2.

Option B, better always-on experience:

- Add `ADMIN_FLEET_GROUP = "admin_fleet"`.
- When `MonitoringConsumer` receives `system_metrics`, after caching Redis, also sends a compact update to `admin_fleet`.
- `AdminFleetConsumer` joins that group and replays a full snapshot on connect.

Recommended implementation:

- Start with Option A if time is tight.
- Implement Option B before calling the feature complete.

### 5.7 Backend Helper Design

Create:

```text
backend/apps/metrics/fleet.py
```

Suggested functions:

```python
def get_latest_system_payload(agent_id: str) -> dict | None:
    """Read latest system metric from Redis; return normalized dict."""

def get_latest_container_payload(agent_id: str) -> dict | None:
    """Read latest container snapshot from Redis when available."""

def summarize_container_status(agent: Agent, redis_payload: dict | None = None) -> dict:
    """Return counts by status."""

def classify_agent_health(agent: Agent, latest: dict | None, containers: dict) -> tuple[str, list[str]]:
    """Return operational health and reasons."""

def build_fleet_agent_row(agent: Agent) -> dict:
    """Build one row for fleet-agents endpoint."""

def build_fleet_summary(rows: list[dict]) -> dict:
    """Aggregate counts, avg/max metrics, top risks."""

def build_fleet_history(range_key: str) -> dict:
    """Aggregate SystemMetricsHistory into chart buckets."""

def build_agent_history(agent_id: str, range_key: str) -> dict:
    """Return one agent's bucketed history."""
```

Do not put large aggregation logic directly in viewsets.

## 6. Frontend Implementation Plan

### 6.1 New Route and Components

Add:

```text
frontend/src/routes/admin/dashboard/+page.svelte
frontend/src/lib/stores/fleet-store.ts
frontend/src/lib/utils/fleet-thresholds.ts
frontend/src/lib/utils/fleet-format.ts
frontend/src/lib/components/fleet/FleetStatusBar.svelte
frontend/src/lib/components/fleet/FleetTrendCharts.svelte
frontend/src/lib/components/fleet/AgentHealthTable.svelte
frontend/src/lib/components/fleet/AgentUsageRow.svelte
frontend/src/lib/components/fleet/RiskServersPanel.svelte
frontend/src/lib/components/fleet/SelectedAgentPanel.svelte
frontend/src/lib/components/fleet/MetricSparkline.svelte
frontend/src/lib/components/fleet/TimeRangeSelector.svelte
frontend/src/lib/components/fleet/MetricHelp.svelte
```

If component count feels high for the first pass, combine as:

```text
FleetStatusBar.svelte
FleetTrendCharts.svelte
AgentHealthTable.svelte
SelectedAgentPanel.svelte
MetricHelp.svelte
```

Do not skip `MetricHelp.svelte`; the help icon requirement is part of MVP.

### 6.2 Store Contract

Create `frontend/src/lib/stores/fleet-store.ts`.

Responsibilities:

- Load fleet summary
- Load fleet agents
- Load fleet aggregate history
- Load selected agent history
- Connect/disconnect admin fleet WS if implemented
- Poll REST as fallback
- Expose loading/error/stale state

Suggested exports:

```ts
export type TimeRange = '5m' | '1h' | '24h';

export const fleetSummary = writable<FleetSummary | null>(null);
export const fleetAgents = writable<FleetAgentRow[]>([]);
export const fleetHistory = writable<FleetHistoryPoint[]>([]);
export const selectedAgentHistory = writable<AgentHistoryPoint[]>([]);
export const fleetLoading = writable(false);
export const fleetError = writable<string>('');
export const fleetConnected = writable(false);
export const lastFleetUpdate = writable<Date | null>(null);

export function startFleetMonitoring(token: string, range: TimeRange): void;
export function stopFleetMonitoring(): void;
export function setFleetRange(range: TimeRange): Promise<void>;
export function refreshFleet(): Promise<void>;
export function loadSelectedAgent(agentId: string): Promise<void>;
```

Polling cadence:

```text
summary: every 15s
agents: every 15s
history: every 30s for 5m/1h, every 60s for 24h
selected agent history: every 30s while selected
```

If WS is connected:

- Apply `agent_metric_update` immediately.
- Still run periodic REST refresh every 60s to avoid drift.

### 6.3 Charting

The project already has Chart.js:

```json
"chart.js": "^4.5.0"
```

Use Chart.js for line charts.

Do not introduce a new chart library unless necessary.

Recommended chart components:

- Aggregate CPU avg/max line
- Aggregate memory avg/max line
- Disk max line
- Network RX/TX area or line
- Server row mini sparkline rendered with lightweight canvas or SVG

For MVP:

- Use Chart.js for main trend charts.
- Use simple inline SVG polyline for row sparklines to avoid too many Chart.js instances.

### 6.4 Main Page State

`frontend/src/routes/admin/dashboard/+page.svelte` should:

- Require browser token from `localStorage.hc_access_token`.
- Use admin layout's auth guard already present in `admin/+layout.svelte`.
- Start fleet monitoring on mount.
- Stop monitoring on destroy.
- Keep selected range in local component state.
- Keep selected agent id in local state.
- Render empty/loading/error states clearly.

Pseudo structure:

```svelte
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import FleetStatusBar from '$lib/components/fleet/FleetStatusBar.svelte';
  import FleetTrendCharts from '$lib/components/fleet/FleetTrendCharts.svelte';
  import AgentHealthTable from '$lib/components/fleet/AgentHealthTable.svelte';
  import RiskServersPanel from '$lib/components/fleet/RiskServersPanel.svelte';
  import SelectedAgentPanel from '$lib/components/fleet/SelectedAgentPanel.svelte';
  import {
    startFleetMonitoring,
    stopFleetMonitoring,
    setFleetRange,
    loadSelectedAgent,
  } from '$lib/stores/fleet-store';

  let range = $state<'5m' | '1h' | '24h'>('1h');
  let selectedAgentId = $state<string | null>(null);

  onMount(() => {
    const token = localStorage.getItem('hc_access_token');
    if (token) startFleetMonitoring(token, range);
  });

  onDestroy(stopFleetMonitoring);
</script>
```

### 6.5 Agent Table Columns

Default table columns:

```text
Health
Hostname
IP
CPU
Memory
Disk
Network RX/TX
Containers
Last Seen
Metric Age
Trend
```

Row interactions:

- Click row: select agent and show details.
- Double click or button: go to existing 3D view with this server selected if supported.
- Sort:
  - default: critical, warning, stale, offline, healthy
  - then highest max(cpu, memory, disk)
  - then hostname

### 6.6 Selected Agent Panel

This panel is not the main focus, but it helps operators drill in without leaving the dashboard.

Display:

- Hostname, IP, agent status
- Current CPU/memory/disk/network
- 1h chart for selected server
- Container status counts
- Top health reasons
- Button/link to existing 3D server view

If linking to selected server in current 3D view is not supported, add a TODO and link to `/`.

### 6.7 Styling Guidance

Style should match existing admin shell variables:

- `var(--bg-base)`
- `var(--bg-card)`
- `var(--bg-tab)`
- `var(--text-primary)`
- `var(--text-secondary)`
- `var(--text-muted)`
- `var(--border)`
- `var(--accent)`
- `var(--error)`
- `var(--radius-sm)`
- `var(--radius-md)`

Use a dense operational layout:

- No landing page
- No hero section
- No 3D scene
- No decorative gradient blobs
- Cards only for specific panels, not nested cards
- Tables and compact panels are preferred
- Text must not overflow buttons or cells
- Critical states should use strong but controlled red
- Warning states should use amber
- Healthy states should use green
- Stale/offline states should use gray or muted red

Suggested desktop sizing:

```text
Admin header: existing 48px
Page padding: 20-24px
Fleet status bar: 64-76px
Global trend area: 260-320px
Right risk panel: 300-360px wide
Agent table row height: 48-60px
Selected agent panel: 280-360px high, or right-side drawer if vertical space is tight
```

Responsive behavior:

```text
>= 1440px:
  charts and table share the main area, right risk panel visible.

1366px:
  keep status bar, charts, and table readable; right panel may move below charts or become narrower.

tablet/mobile:
  stack panels vertically; table can become horizontally scrollable.
```

Typography:

- Use compact headings inside panels.
- Do not use hero-sized type.
- Metric values may be larger than labels, but should not dominate the whole screen.
- Long hostnames must truncate with tooltip/title or wrap cleanly.
- No negative letter spacing.

Interaction polish:

- Row hover should make it clear the row is selectable.
- Selected row should remain visibly selected.
- Refresh button should not shift layout while loading.
- Time range selector should use segmented controls.
- Search should not steal focus on page load.
- Tooltip icons must not enlarge table rows on hover.

## 7. Data Freshness Rules

The dashboard must show data age.

Definitions:

```text
metric_age_seconds = now - latest.metric_timestamp
last_seen_age_seconds = now - agent.last_seen_at
```

Display examples:

```text
Live
12s ago
1m 20s ago
stale
offline
```

Freshness classes:

```text
fresh: metric_age <= 15s
warm: 15s < metric_age <= 30s
stale: 30s < metric_age <= 60s
expired: metric_age > 60s or missing
```

If `last_seen_at` is recent but metric is stale, show `stale metrics`.

If `last_seen_at` is old, show `offline`.

## 8. Network Rate Calculation

Existing models store cumulative bytes:

- `SystemMetricsHistory.network_rx`
- `SystemMetricsHistory.network_tx`
- `ContainerMetricsHistory.network_rx`
- `ContainerMetricsHistory.network_tx`

Dashboard needs rates.

Calculate:

```text
rx_rate_bps = (current.network_rx - previous.network_rx) / seconds_delta
tx_rate_bps = (current.network_tx - previous.network_tx) / seconds_delta
```

Rules:

- If previous point missing, rate is `0`.
- If counter decreased, treat rate as `0` because interface/container probably reset.
- Clamp negative values to `0`.
- Use bytes per second internally.
- Format in UI as `KB/s`, `MB/s`, `GB/s`.

## 9. Container Summary Rules

Status groups:

```text
running: running
stopped: stopped
paused: paused
exited: exited
restarting: restarting
dead: dead
created: created
```

Operational grouping:

```text
healthy_containers = running
non_running_containers = total - running
problem_containers = restarting + dead
```

Risk impact:

- `restarting > 0` should at least be warning.
- `dead > 0` should be critical.
- Many `exited` containers should not always be critical because some jobs exit normally. Treat as informational unless recently increased or requested otherwise.

## 10. Implementation Phases

### Phase 1: REST MVP

Goal: Full dashboard works by polling REST, with no new WebSocket requirement.

Backend:

- Add `backend/apps/metrics/fleet.py`.
- Add fleet summary API.
- Add fleet agents API.
- Add fleet history API.
- Add single-agent history API.
- Add tests for health classification and summary aggregation.

Frontend:

- Add `/admin/dashboard`.
- Add fleet store with REST polling.
- Add status bar.
- Add aggregate trend charts.
- Add agent health table.
- Add risk servers panel.
- Update `AdminHeader.svelte` nav.

Acceptance:

- Admin can open `/admin/dashboard`.
- All approved agents are visible.
- Offline agents remain visible.
- CPU/memory/disk latest values appear.
- CPU/memory/disk aggregate trends appear.
- Server rows sort by risk.
- Page keeps refreshing without manual interaction.

### Phase 2: Fleet WebSocket

Goal: Metric updates feel live and do not wait for polling.

Backend:

- Add `AdminFleetConsumer`.
- Add `/ws/admin/fleet/`.
- Add `ADMIN_FLEET_GROUP`.
- Broadcast compact metric updates from `MonitoringConsumer`.
- Replay fleet snapshot when admin connects.

Frontend:

- Extend `fleet-store.ts` to connect WS.
- Apply `agent_metric_update`.
- Keep REST refresh as drift correction.
- Show WS connected/disconnected state.

Acceptance:

- When an agent sends new metrics, table values update quickly.
- If WS disconnects, REST polling continues.
- Dashboard shows clear WS state.

### Phase 3: Operator Polish

Goal: Make the dashboard comfortable for real always-on monitoring.

Tasks:

- Add selected agent detail panel.
- Add table sorting controls.
- Add search/filter by hostname/status.
- Add display density tuning for 1080p screens.
- Add stale data indicators.
- Add keyboard-safe interactions.
- Add mobile fallback, but optimize primarily for desktop/NOC display.

### Phase 4: Historical Depth

Goal: Improve trend fidelity.

Tasks:

- Optimize history queries.
- Consider DB indexes or materialized aggregation if fleets grow.
- Add 7d range after 24h works well.
- Add per-agent high-water marks for CPU/memory/disk.
- Add container count trend if history exists or can be derived.

## 11. Backend Test Plan

Add tests under:

```text
backend/apps/metrics/tests/test_fleet_api.py
backend/apps/metrics/tests/test_fleet_helpers.py
```

Test cases:

- Admin can access fleet endpoints.
- Normal user cannot access fleet-wide endpoints.
- Summary includes approved agents.
- Offline agent with no latest metric appears in fleet agents response.
- Critical CPU >= 90 classifies as critical.
- Warning memory >= 75 classifies as warning.
- Disk >= 90 classifies as critical.
- Dead container classifies as critical.
- Network rate clamps negative counter deltas to 0.
- History endpoint returns oldest-to-newest points.
- Invalid range falls back to `1h` or returns 400. Choose one behavior and test it.

Recommended behavior:

- Invalid range returns `400` with clear error.

## 12. Frontend Verification Plan

Run:

```text
cd frontend
npm run check
npm run build
```

Manual checks:

- Login as admin.
- Open `/admin/dashboard`.
- Verify dashboard renders with no selected server.
- Verify all agents appear.
- Verify offline/stale server row styling.
- Verify time range changes update charts.
- Verify table remains usable at 1366x768 and 1920x1080.
- Verify long hostnames do not overflow.
- Verify all major metric labels have `?` help icons.
- Verify help tooltip opens on hover.
- Verify help tooltip opens on keyboard focus.
- Verify help tooltip text is short and does not shift layout.
- Verify default sorting surfaces critical/warning servers first.
- Verify loading refresh keeps old data visible instead of blanking the page.
- Verify pending requests count still works in header.
- Verify existing `/admin/requests` and `/admin/templates` still work.

If Playwright is available:

- Capture desktop screenshot at 1920x1080.
- Capture smaller desktop screenshot at 1366x768.
- Check no major text overlap.
- Check charts are non-empty when data exists.

## 13. Performance Notes

Initial target fleet size:

```text
10-100 agents
```

Keep the dashboard cheap:

- Do not open one WebSocket per agent.
- Do not instantiate Chart.js per table row.
- Do not fetch full container metrics for every container on every refresh.
- Limit history points per chart.
- Aggregate server history on backend.
- Use compact row sparklines.

Recommended point limits:

```text
5m: max 20 points
1h: max 60 points
24h: max 288 points
```

## 14. Open Questions

These do not block MVP, but implementation should make reasonable defaults.

- Should `archived` agents appear by default? Recommendation: no, unless filter enabled.
- Should `pending` agents appear? Recommendation: show in a small admin count, but exclude from monitoring table unless they have metrics.
- Should stopped containers count as warnings? Recommendation: no, because stopped may be intentional.
- Should exited containers count as warnings? Recommendation: no by default.
- Should users ever see fleet dashboard? Recommendation: no, admin only.

## 15. Definition of Done

The feature is complete when:

- `/admin/dashboard` exists and is reachable by admin.
- It monitors all approved, non-archived agent servers.
- It does not require selecting a server.
- It shows overall usage trends.
- It shows per-server latest CPU, memory, disk, network, container status.
- It highlights warning, critical, stale, and offline servers.
- It updates automatically while left open.
- It has a clear last updated/freshness indicator.
- It uses a compact UI consistent with the current admin pages.
- It includes `?` help tooltips for major data labels.
- Its primary UX flow starts from fleet status, then trends, then risk, then per-server detail.
- It preserves existing admin request/template workflows.
- Backend and frontend checks pass.

## 16. Suggested File Change Checklist

Backend:

- [ ] `backend/apps/metrics/fleet.py`
- [ ] `backend/apps/metrics/viewsets.py`
- [ ] `backend/apps/metrics/urls.py`
- [ ] `backend/apps/common/consumers.py`
- [ ] `backend/config/routing.py`
- [ ] `backend/apps/metrics/tests/test_fleet_helpers.py`
- [ ] `backend/apps/metrics/tests/test_fleet_api.py`

Frontend:

- [ ] `frontend/src/routes/admin/dashboard/+page.svelte`
- [ ] `frontend/src/lib/stores/fleet-store.ts`
- [ ] `frontend/src/lib/utils/fleet-thresholds.ts`
- [ ] `frontend/src/lib/utils/fleet-format.ts`
- [ ] `frontend/src/lib/components/fleet/FleetStatusBar.svelte`
- [ ] `frontend/src/lib/components/fleet/FleetTrendCharts.svelte`
- [ ] `frontend/src/lib/components/fleet/AgentHealthTable.svelte`
- [ ] `frontend/src/lib/components/fleet/RiskServersPanel.svelte`
- [ ] `frontend/src/lib/components/fleet/SelectedAgentPanel.svelte`
- [ ] `frontend/src/lib/components/fleet/MetricHelp.svelte`
- [ ] `frontend/src/lib/components/AdminHeader.svelte`

Docs:

- [ ] Update `docs/api.md` after endpoints are implemented.
- [ ] Link this plan from `README.md` or `docs/to-be-architecture.md` if desired.
