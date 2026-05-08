# Development Guide

This document describes the practical development workflow for the current repository.

## Prerequisites

- Node.js 20+
- npm
- Python 3.12+ if you want to run backend code outside containers
- Docker Desktop or Docker Engine for local service dependencies

## Repository Structure

```text
frontend/   Svelte dashboard
backend/    Django backend and domain apps
docs/       project documentation
nginx/      reverse proxy configuration
```

## Frontend Workflow

From `frontend/`:

```bash
npm install
npm run dev
```

Useful scripts:

- `npm run dev`
- `npm run build`
- `npm run check`

Notes:

- the dashboard is client-heavy and uses WebSocket stores for live state
- the current frontend build/deployment path is under active cleanup, so treat production frontend docs conservatively

## Backend Workflow

The backend uses Django with PostgreSQL and Redis.
The root compose file currently defines the service dependencies used by the backend stack.

Typical local tasks:

```bash
docker compose up -d postgres redis
```

Then run backend commands in your preferred Python environment from `backend/`.

Example tasks:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

If you use Celery locally, the backend expects Redis-backed broker/result settings.

## Branching

Recommended branch flow:

1. work on `dev`
2. open a pull request into `main`
3. merge only reviewed/stable changes into `main`

Do not push directly to `main` unless you explicitly intend to trigger downstream sync automation.

## Commits

This repository follows Conventional Commits.

Examples:

- `feat(ui): add agent status badge`
- `fix(api): guard request approval transition`
- `docs(readme): rewrite architecture overview`

## Documentation Rule Of Thumb

When updating docs, keep these distinctions explicit:

- `architecture.md`: current implementation
- `to-be-architecture.md`: target state
- `README.md`: high-level overview and entry links

Mixing current state and future state in one document is what made the documentation harder to trust before.

## Current Known Friction

Be aware of these active cleanup areas:

- frontend adapter/runtime mismatch
- incomplete production backend compose path
- some older comments and docs were previously affected by encoding issues

When writing new docs, prefer short, accurate, current statements over optimistic claims.

## Engineering Principles (Lessons Learned)

These rules exist because we hit the exact failure they prevent.
Skipping one of them reliably produces the same class of bug again.

### 1. Delta Sync은 반드시 "주기 full snapshot"과 짝지어 구현

**원인 사례**: `container_metrics`는 Delta Sync만 구현되어 있어, idle
컨테이너처럼 값이 변하지 않는 경우 전송 자체가 끊기고 Backend 캐시 TTL이
만료되면 UI에서 사라짐. 같은 묶음의 `containers`는 full snapshot
interval이 있어 문제없었음.

**원칙**
- 새로운 stream 데이터에 Delta/diff 방식을 쓰려면 **동시에** 주기적인
  full snapshot 경로를 반드시 페어로 추가한다.
- Backend 캐시 TTL < full snapshot 주기가 되도록 설정한다 (즉, 캐시가
  끊기기 전에 항상 한 번은 덮어쓰기가 옴).
- 코드 리뷰 시 Delta 전송 로직만 보이고 snapshot 경로가 없으면 reject.

### 2. 테스트 시나리오는 "활발한 경우"와 "idle한 경우" 양쪽을 커버

**원인 사례**: server_16(컨테이너 90개 + 실트래픽)은 메트릭이 항상
변동해서 Delta 경로가 계속 발사 → 버그가 숨음. 갓 생성된 idle
`test-container`에서 첫 재현.

**원칙**
- 신기능 테스트 시 최소 2개 환경: **busy**(정상 트래픽), **idle**(갓
  생성/유휴) 양쪽.
- "살아있는 서버에서 잘 된다"는 증거를 **충분 조건**으로 삼지 않는다.
- Phase 종료 체크리스트에 "idle 재현 1회" 넣기.

### 3. 분산 프로세스는 "코드 배포" ≠ "실행 중 프로세스 버전"

**원인 사례**: Agent 184b287을 repo에 merge 했어도, 로컬 PC에서
그 이전에 띄워진 node 프로세스는 구버전. "Unknown command:
create_container" 에러. 16번 서버는 재배포되어 OK, 로컬은 안 됐음.

**원칙**
- 신기능 배포 시 관련 Agent/worker 프로세스를 모두 **재시작**하는 단계를
  절차에 포함.
- Agent는 `READY` 이벤트 등으로 **자기 버전/커밋 hash** 를 보고하도록
  하고, Backend가 필요 시 기대 버전과 비교 경고.
- 테스트 전 반드시 `last_started_at` / 버전 확인.

### 4. WBS 단위 기능 묶음은 "같은 패턴을 모든 경로에 적용"까지가 완료

같은 WBS 안에 있는 2개 이상 경로가 **한쪽에만** 안전장치를 넣고
끝나는 것을 허용하지 않는다. 예: `containers` snapshot은 있는데
`container_metrics` snapshot은 빠진 것.

**원칙**
- WBS 서브태스크 완료 기준에 "동일 계열 경로 전수 점검" 포함.
- 리팩토링이 아닌 신기능 추가 시에도 "대칭성 체크" 한 번.

### 5. 완료 체크리스트 (각 WBS 서브태스크 종료 시)

- [ ] busy 서버 + idle 서버 양쪽 재현 테스트
- [ ] 관련 Agent/worker 프로세스 재시작 확인
- [ ] Delta가 있다면 full snapshot 페어 존재 확인
- [ ] 같은 계열 다른 경로와 안전장치 대칭 여부 확인
- [ ] Agent repo issue 링크 / 커밋 hash 기록
