---
last-updated: 2026-05-08 (B3 완료, B4 정책 결정만 남음)
status: living document — 세션마다 갱신
benchmark: Portainer container detail UI
related-pages: /user/containers/[containerId]
---

# Container Dashboard Roadmap

`/user/containers/[containerId]` 페이지를 Portainer 수준의 operability + HyperCube 시계열 분석 강점을 결합한 대시보드로 끌어올리기 위한 작업 로드맵. **세션마다 진행 상황과 결정 사항을 갱신한다**.

## 현재 상태 (요약 — 다음 세션 시작 시 여기부터 읽기)

**기능 단위 작업**: D / A1 / B1 / B2 / B3 / C1 모두 완료 → Portainer parity 100%.
**남은 마지막 단계**: B4 (Console exec / xterm). 정책 결정 완료 (아래 §B4 참조), agent prompt 만 만들면 시작 가능.
**별도 scope** (현재 로드맵 외): UI/UX 폴리싱은 다음 세션에서 별도 진행. 컨테이너 modification (limit edit 등) 은 admin 도구 영역으로 분리.

## 큰 그림

| 축 | HyperCube 현재 | Portainer | 목표 |
|---|---|---|---|
| 시계열 차트 (history, sync, zoom, pause, period) | ✅✅ | △ live only | 유지 + 강화 (events markLine, rate 토글) |
| Lifecycle 컨트롤 (start/stop/restart/...) | ❌ | ✅ | A1에서 채움 |
| Live log stream + 검색/필터 | ❌ | ✅ | B1 |
| Console exec (shell) | ❌ | ✅ | B4 (마지막) |
| Inspect / Health / Mount / Network / Image | ❌ / △ | ✅ | A1 |
| Container events log | ❌ | ✅ | B2 |
| Per-container processes | ❌ | ✅ | B3 |
| Resource limit / restart policy edit | ❌ | ✅ | 추후 (스코프 외) |

## 진행 상황

| 세션 | 묶음 | 상태 | Agent repo 작업 |
|---|---|---|---|
| 0 (완료) | D — 차트 sync / zoom / pause / period KPI | ✅ commit `d65bce4` | ❌ |
| 1 (완료) | A1 — Container Ops Panel | ✅ | ❌ |
| 2 (완료) | B2 — Events 타임라인 + 차트 markLine | ✅ | ✅ agent 송출 추가 완료 |
| 3 (완료) | B1 — Live log streaming | ✅ | ✅ agent logs_subscribe/unsubscribe 추가 완료 |
| 4 (완료) | C1 — Rate 차트 + 임계 markLine | ✅ | ❌ |
| 5 (완료) | B3 — Per-container processes top-N | ✅ 이번 세션 | ✅ agent container_processes 추가 완료 |
| 6 | **B4 — Console exec (xterm)** | 🔜 다음 (가장 위험) | ✅ 선행 필요 |

상태 이모지: ✅ 완료 · ⏳ 진행 중 · 🔜 대기 · ⚠️ 블록 / 재설계

## A1. Container Ops Panel  (✅ 완료)

**목표**: Portainer parity 30~40%를 한 세션에. Agent repo 안 건드림.

### 범위

1. **Lifecycle 컨트롤 버튼** (hero 영역)
   - Start / Stop / Restart / Pause / Unpause / Kill
   - 컨테이너 현재 상태에 따라 valid action만 활성화
   - 파괴적 동작 (Stop/Kill/Restart) 클릭 시 확인 모달
   - 호출: 기존 `agent.control` 명령 (`docs/agent-protocol.md` §3) — backend WS routing 그대로
   - 권한: 본인 소유 컨테이너만 (multi-tenant 기존 정책)
   - 호출 후 즉시 `loadCurrentMetrics` + `loadDetail` 재호출 → state 반영

2. **Health / Lifecycle indicator**
   - hero meta 또는 stat-card에 표시
   - 출처: `inspect.state` (running/paused/restarting/oomKilled), `restartCount`, `startedAt`, `exitCode`, `health` (null 가능)
   - exit code 비-0이면 빨간 표시
   - oomKilled true면 OOM 배지

3. **Inspect raw JSON 패널** (collapsible)
   - `agent.inspect` 호출 결과 JSON view
   - 검색/접기/복사 지원

4. **Network / Mount / Image 패널** (inspect 응답에서 정리)
   - Network: `networkSettings.networks`, `networkSettings.ports`
   - Mount: `mounts[]` (type, source, destination, mode)
   - Image: `image`, `config.cmd`, `config.entrypoint`, `config.workingDir`
   - 기존 "런타임 정보 / 요청 시 설정" 패널과 어떻게 합칠지 결정 필요 → 기존 패널은 요청 시점 데이터, 신규는 실제 inspect 결과

### 영향 파일

- `frontend/src/routes/user/containers/[containerId]/+page.svelte` — UI 변경
- `frontend/src/lib/components/` — 신규 컴포넌트 (`ContainerActions.svelte`, `InspectPanel.svelte`, `ConfirmDialog.svelte` 또는 inline)
- `backend/apps/containers/viewsets.py` — `/api/my-containers/<id>/control/`, `/api/my-containers/<id>/inspect/` 엔드포인트 (REST → WS dispatch)
  - 기존에 admin 페이지에서 control 부르는 viewset이 있을 수 있음 — 확인 후 재사용
- `docs/api.md` — 신규 endpoint 문서 (sync hook reminder)

### 결정 필요

- 기존 "런타임 정보" 패널을 신규 inspect 패널로 통합할지, 분리 유지할지
  → **선택**: 분리. 요청 시점 정보 = audit 가치, inspect = 현재 상태 가치
- 모달 스타일: 기존 `NewRequestModal.svelte` 패턴 따라가기
- 위험한 동작에 대해 비밀번호 재입력 요구할지 → **선택**: 첫 단계는 확인 모달만, 추후 audit 정책 시 재고

### 검증 체크리스트 (실제 결과)

- [x] Pause / Unpause 200 OK + agent round-trip 성공
- [x] Invalid action → 400 + valid actions 목록
- [x] running 상태에서 시작/재개 disabled, 일시정지/재시작/중지/강제종료 active
- [x] 콘솔 에러 0건
- [x] InspectPanel 4개 카드 (상태/네트워크/Mount/이미지) + Raw JSON toggle 정상 렌더링
- [x] EnvelopeJSONRenderer 더블래핑 회피 (`_agent_resp_to_http`)
- [ ] 실제 destructive 동작 (Stop/Kill/Restart) UI flow — 확인 모달까지는 코드상 정상, 실제 클릭 + 모달 확인은 운영 컨테이너에 영향 있어 추후 검증

### 실제 변경 (commit 시점)

- `backend/apps/common/command_router.py` — `store_response`, `fetch_response`, `REST_SENTINEL`
- `backend/apps/common/consumers.py` — `_route_command_response` 가 sentinel 분기
- `backend/apps/containers/viewsets.py` — `MyContainerViewSet.control` / `inspect` action 추가, `_dispatch_and_wait` helper
- `frontend/src/lib/components/ContainerActions.svelte` — 신규
- `frontend/src/lib/components/InspectPanel.svelte` — 신규
- `frontend/src/lib/components/ConfirmDialog.svelte` — busy state 추가
- `frontend/src/routes/user/containers/[containerId]/+page.svelte` — Ops bar + InspectPanel 통합, `loadInspect`, `handleControlDone/Error`
- `docs/api.md` — `/api/my-containers/{id}/inspect|control/` 엔드포인트 추가

## B2. Events 타임라인 + 차트 markLine  (✅ 완료)

### 실제 변경

- Agent (별도 repo, 이미 완료): `container_events` 메시지 송출, 100ms batch, 9 kind 매핑, signal 정규화
- Backend
  - `apps/containers/models.ContainerEvent` + migration 0003
  - `apps/common/consumers._handle_container_events` 핸들러 (bulk_create, agent_id + short ID 매칭, 알 수 없는 컨테이너 silently skip)
  - `apps/containers/serializers.ContainerEventSerializer`
  - `MyContainerViewSet.events` REST action (`?since=&limit=`)
- Frontend
  - `lib/components/charts/types.MarkLineEntry` 타입
  - `EChartLine.markLines` prop + `buildMarkLine` (dashed, opacity 0.7, color per kind)
  - `UserMetricChart.markLines` passthrough
  - `lib/utils/container-events.ts` (kind→color/label 단일 source)
  - `EventList.svelte` 신규
  - `[id]/+page.svelte`: events state, 10s polling (paused 시 skip), `chartMarkLines = $derived(buildChartMarkLines)` (event ts → 가까운 bucket idx)
- Docs: `agent-payload-contract.md` (`container_events` 섹션), `api.md` (events endpoint)

### 검증 (chrome 실측)

- pause + unpause 클릭 → agent가 송출 → backend가 받아 DB 저장 → REST 응답에 2건 → EventList 2건 표시 → 5개 차트 모두 markLine 표시
- markLine 위치: 5분 단위 (63 bucket 중 마지막 62번 — 두 이벤트가 1초 차로 같은 bucket)
- 콘솔 에러 0건

### 알려진 한계 / 후속

- 폴링 10s — 실시간성 떨어짐. 향후 WS push 로 전환 (server group broadcast 는 이미 됨, 사용자 페이지에서 WS 구독만 추가하면 됨)
- 같은 bucket 안에 여러 이벤트가 떨어지면 markLine 이 겹쳐 보임. tooltip 으로 분리 가능하지만 현재 label.show=false. 호버 가시성 향후 개선 후보.
- 알 수 없는 컨테이너 이벤트 silently skip — start 이벤트가 containers snapshot 보다 먼저 도착할 때 lost 가능. retry queue 도입 후보.

## ~~B2. Events 타임라인 + 차트 markLine  (다음 세션 후보)~~ (위로 이동, 완료)

**Agent 작업 (별도 세션)**:
- Dockerode `events()` stream 구독 (filter: type=container)
- 이벤트 → 새 메시지 타입 `container_events` 로 backend push
  ```jsonc
  {
    "type": "container_events",
    "timestamp": "...",
    "data": {
      "containerId": "...",
      "events": [
        { "ts": "...", "kind": "start" | "stop" | "die" | "restart" | "oom" | "kill" | "health_status",
          "exitCode": 0, "signal": "SIGTERM", "healthStatus": "healthy" | "unhealthy" }
      ]
    }
  }
  ```
- 재접속 시 최근 N분 events backfill (또는 backend 보관)

**This repo 작업**:
- Backend
  - `apps/containers/models.py` 에 `ContainerEvent` 추가 (FK Container, ts, kind, payload jsonb, indexed by container+ts)
  - `apps/common/consumers.py` `_handle_container_events` 핸들러 (DB 저장 + 사용자 채널 broadcast)
  - REST `/api/my-containers/<id>/events/?since=...&limit=...`
- Frontend
  - 이벤트 패널 컴포넌트 (`EventList.svelte`)
  - `EChartLine` 에 `markLines?: { ts, label, color }[]` prop 추가 → 5개 차트 모두 같은 시각에 vertical line 표시
  - 5초 폴링 또는 WS 실시간 push (B1 stream 인프라 와 같이 검토)

**가치**: HC 차트 강점 ↑ — "왜 metric이 0이 됐지?" 답이 차트 위에 직접.

## B1. Live Log Streaming  (✅ 완료)

### 실제 변경

- Agent (별도 repo, 완료): `logs_subscribe / logs_unsubscribe` 명령, `log_chunk / log_stream_end` flat-envelope 메시지, 200ms / 50줄 batch, demuxStream(stdout/stderr)
- Backend
  - `command_router`: `record_stream / get_stream_info / remove_stream / streams_by_channel` (TTL 1h)
  - `_handle_browser_command`: `logs_subscribe` forward 시 record_stream, `logs_unsubscribe` 시 optimistic remove
  - `_route_log_stream_message`: streamId → browser_channel 매핑 후 forward, `log_stream_end` 시 registry 정리
  - `disconnect`: Browser disconnect 시 활성 stream 마다 `logs_unsubscribe` agent 발송 + registry 정리
- Frontend
  - `LogTailPanel.svelte`: 자체 WS 연결, regex 필터, auto-scroll / pause 토글, 복사 / 다운로드, MAX_LINES=5000 cap, stdout/stderr 색 구분
  - `[id]/+page.svelte`: 차트 패널 다음 위치에 패널 통합

### 검증 (chrome 실측)

- 패널 열기 → WS 연결 → command_response(success:true, subscribed:true) → 27줄 tail backfill 즉시 표시 ("● 수신 중")
- 정규식 필터 "WARNING" → 4 / 27줄 매치, 빈 필터 복귀 시 27줄 전체
- 닫기 → unsubscribe 발송 + WS close → UI 정리
- 콘솔 에러 0건

### 알려진 한계

- 한 페이지에 LogTailPanel 1개. 다중 streams 지원은 의도적 미구현.
- log_stream_end 의 `container_removed` reason 은 agent 가 `container_stopped` 로 통합 (inspect 호출 비용 회피). backend 가 `container_events.die` 와 cross-reference 가능.
- 가상 스크롤 없음 — 5000줄 cap 으로 메모리 보호. 폭주 환경에선 후속 가상 스크롤 도입 검토.
- WS 끊김 자동 reconnect 없음. 사용자가 재시작 버튼 또는 패널 닫기/열기로 재구독.

## ~~B1. Live Log Streaming~~ (위로 이동, 완료)

**Agent 작업 (별도 세션)**:
- 새 명령 `logs_subscribe(containerId, tail, since, timestamps)` — Dockerode `logs({follow:true, tail, since})` stream 시작
- subscription id (or requestId) 보관, `log_chunk` 메시지로 backend push
  ```jsonc
  { "type": "log_chunk", "requestId": "<id>", "lines": ["..."], "stream": "stdout" | "stderr" }
  ```
- 명령 `logs_unsubscribe(requestId)` — stream 정리
- backend disconnect 감지 시 dangling stream 정리

**This repo 작업**:
- Backend
  - subscription map (`requestId → browser_channel`) — 기존 `command_router.record_pending` 패턴 확장 (multi-response 허용)
  - `log_chunk` consumer 핸들러 → browser channel forward
  - browser disconnect 시 자동 unsubscribe 호출
- Frontend
  - 가상 스크롤 패널 (예: `svelte-virtual` 또는 직접 IntersectionObserver)
  - level/regex 필터, auto-scroll 토글, 검색, 다운로드, "최근 N줄" 단위 prune
  - WS 메시지 처리 hook

**위험**: 다중 사용자 다중 컨테이너 stream 동시 → 메모리 / 백프레셔. 한 페이지당 1 subscription 제한.

## C1. Rate 차트 + 임계 markLine  (✅ 완료)

### 실제 변경 (스코프 조정)

원래 roadmap 의 "CPU 에 cores_quota markLine, Memory 에 limit markLine" 은
% 정규화 차트라 의미 없어 변경: **80%/90% 임계** horizontal markLine 으로
교체 (capacity planning 용).

- types: `ValueFormat` 에 `'bytes_per_sec'` 추가 / `MarkLineEntry` 에 `yAxis?: number` 지원 (xAxis|yAxis OR)
- `EChartLine`: bytes_per_sec format ("X/s" 접미사), buildMarkLine 이 yAxis 분기, percent 차트 yAxis.max=100 강제 (임계 라인 항상 보이게)
- `[id]/+page.svelte`:
  - `networkMode` / `diskMode` state ('cumulative' | 'rate')
  - `bucketSeconds` API 응답에서 capture
  - `rateOf(values, secs)` — 누적 → bucket 간 delta/sec, 컨테이너 재시작(음수) 은 0 hold
  - `THRESHOLD_LINES` const + `percentChartMarkLines` 결합 (events vertical + thresholds horizontal)
  - Network/Disk chart-head 에 "누적 / 속도" 토글 UI

### 부수 fix

- `data-adapter.formatBytes`: `bytes < 1` 일 때 `Math.log` 음수 → idx=-1 → `UNITS[-1]=undefined` 라벨 표시 버그. `Math.max(0, idx)` 로 clamp.

### 검증 (chrome 실측)

- Network 누적 → 속도 토글 → yAxis "0.4 B/s, 0.2 B/s..." 정확 표시, burst pattern 시각화
- CPU/Memory 차트 yAxis 0~100 강제, 80% 노란 + 90% 빨간 dashed line 표시
- ECharts instance 검증: `markCount=14` (events 12 + thresholds 2), `yAxisMax=100`
- 콘솔 에러 0건

## ~~C1. Rate 차트~~ (위로 이동, 완료)

- Backend: `buckets()` 응답에 derived 필드 (`network_rx_rate_avg = (rx_max - prev_rx_max) / bucket_seconds`, 같은 방식으로 `tx_rate`, `disk_read_rate`, `disk_write_rate`). 음수일 땐 (컨테이너 재시작) `null` 또는 0.
- Frontend
  - 네트워크/디스크 차트에 "누적 / 속도" 토글 segmented control
  - CPU 차트에 `cores_quota` (있으면) markLine
  - Memory 차트에 `limit` markLine
  - markLine 인프라는 B2와 공유

## B3. Per-Container Processes (top-N)  (✅ 완료)

### 실제 변경

- Agent (별도 repo, 완료): `container_processes` 명령. `dockerode container.top()` 우선 + `/proc/<pid>/stat` 100ms 2회 sample CPU% + `/proc/<pid>/status` VmRSS. busy loop alpine 으로 cpu_percent=99 측정 검증됨.
- Backend
  - `MyContainerViewSet.processes` REST action — 기존 `_dispatch_and_wait` 헬퍼 재사용
  - sortBy clamp(`cpu`/`mem`), limit clamp(1~100)
- Frontend
  - `ProcessTopPanel.svelte` 신규 — sortBy(CPU/Mem) seg toggle, limit select(10/20/50/100), 5초 폴링 (visibilityState hidden 또는 paused 시 skip), state 배지(R/S/D/Z/T/I), CPU%/RSS/PID/UID/Command 표시
  - `[id]/+page.svelte`: 차트 패널 다음 위치에 Panel 통합

### 검증 (chrome 실측)

- Redis (1 process) → total=1, redis-server 표시 (cpu=0, rss=8.5MB, state=S)
- API 200 OK, 콘솔 에러 0건
- agent dev 측 검증: nginx multi-process / busy loop CPU=99 / paused / stopped / unknown ID / limit clamp / sortBy fallback 모두 통과

## ~~B3. Per-Container Processes~~ (위로 이동, 완료)

**Agent 작업**:
- 새 명령 `container_processes(containerId, sortBy='cpu'|'mem', limit=20)`
- 구현: `/sys/fs/cgroup/<container_cgroup>/cgroup.procs` 읽고, 각 PID 의 `/proc/<pid>/stat` + `status` 파싱 → CPU% (delta) / RSS / cmdline / state
- minimal image 의존 X (no `ps` needed). 단 cgroup v1/v2 분기 처리 필요.

**This repo 작업**:
- Frontend: 새 패널, sortBy 토글, 5초 폴링 (페이지 active 시만)
- Backend routing 만

## B4. Console Exec (xterm.js)  (🔜 대기 — 정책 결정 완료, agent prompt 만들기부터 시작)

### 정책 결정 (Portainer 모델 채택)

| 항목 | 결정 |
|---|---|
| 권한 | 본인 소유 컨테이너에 한해 console 가능 (control 과 동급). admin grant 별도 X. |
| Audit | **세션 레벨만** — `ConsoleSession` 모델 (user, container, opened_at, closed_at, duration). 키스트로크 미기록. |
| 명령 차단 | **없음** (Portainer 와 동일 — escape 우회 막을 수 없음). console 권한 = full shell 권한. |
| Session timeout | WS 끊김 시 자동 종료. 별도 idle 타이머 없음. JWT 만료 (8h) 가 자연 한계. |
| UI | xterm.js, shell 선택 (sh / bash), user 선택 (--user UID), 터미널 resize 자동 전달. 끊김 시 reconnect = 새 세션. |

### Agent 작업

새 long-running 명령 (B1 logs_subscribe 패턴 참조 — streamId 기반 라우팅):

- `exec_open(containerId, cmd, user, tty)` → 즉시 `command_response { execId, ready:true }`. execId 가 streamId 역할.
- `exec_input(execId, data)` — stdin 데이터 (base64? raw? 결정 필요)
- `exec_resize(execId, cols, rows)` — 터미널 크기 변경
- `exec_close(execId)` — 정리
- 새 push 메시지 `exec_chunk { execId, stream: stdout|stderr, data }` (raw bytes — base64 권장, xterm 가 ANSI escape 처리)
- 새 push 메시지 `exec_end { execId, exitCode, reason }`
- 구현: Dockerode `container.exec({ AttachStdin, AttachStdout, AttachStderr, Tty, User, Cmd })` + duplex stream

### This repo 작업

- Backend
  - `apps/containers/models.ConsoleSession` 신규 (FK Container, FK User, opened_at, closed_at, duration_seconds)
  - WS routing: B1 의 stream registry 패턴 재활용 (execId == streamId)
  - Browser disconnect 시 `exec_close` 자동 발송 (B1 cleanup 패턴)
  - REST `/api/my-containers/<id>/console-sessions/` (audit 조회) — admin 또는 본인
- Frontend
  - `ConsolePanel.svelte` — xterm.js 통합 (npm 의존성 추가 필요)
  - shell / user 선택 dropdown
  - 터미널 resize observer → exec_resize 발송
  - Ctrl+Shift+C/V 복사/붙여넣기 (Ctrl+C 는 SIGINT 로 컨테이너에 전달)

### 진행 절차

1. Agent prompt 만들기 (B1 prompt 형식 따라)
2. agent 작업 끝나면 backend WS routing + ConsoleSession 모델 + REST + frontend xterm 통합
3. chrome 검증: redis-cli 실행 / sh 진입 / Ctrl+C SIGINT 전달 / resize / 끊김 시 cleanup

## 코딩 룰 (반복 실수 방지 — 모든 세션 공통)

(상세는 `CLAUDE.md` "핵심 룰" 참조)

- 로컬에서 dev server 띄우지 말 것 (63번 sync). 검증은 항상 `http://192.168.0.63:3000`.
- `+page.svelte`는 NON-runes → `let` 사용 (`$state()` 금지). 컴포넌트(.svelte)만 runes.
- Windows `\r\n` 으로 Edit 매칭 실패 시 `Write`로 전체 재작성.
- Python backend는 serena LSP 미지원 → Read/Grep 유지.
- Agent 소스 수정은 별도 세션 (이 repo는 Backend + Frontend만).

## 변경 이력

- 2026-05-08: B3 (Per-container processes top-N) 완료. 다음 세션 = B4 (Console exec, 가장 위험 — 권한/감사 모델 신중).
- 2026-05-08: C1 (Rate 차트 + 80/90% 임계 markLine) 완료 + formatBytes < 1 버그 fix.
- 2026-05-08: B1 (Live log streaming) 완료.
- 2026-05-08: B2 (Events 타임라인 + 차트 markLine) 완료.
- 2026-05-08: A1 (Container Ops Panel) 완료.
- 2026-05-08: 초안 작성.
- 2026-05-08: D (차트 sync/zoom/pause/period KPI) 완료 — commit `d65bce4`.
