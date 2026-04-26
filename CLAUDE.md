# HyperCube - Server & Container Monitoring Platform

## Current Work (2026-04-10)

### 완료된 작업 (이번 세션)
- **WBS 2.3**: Celery + Redis 캐시 + PG 메트릭 저장 (`183e4f4`)
  - Celery worker/beat 컨테이너 추가 (30초 flush, 매일 03:00 cleanup)
  - Consumer → Redis 캐시 (DB 1, TTL 60s) → Celery → PG bulk insert
  - metrics 앱 (SystemMetricsHistory, ContainerMetricsHistory 모델)
  - Delta Sync merge: Consumer에서 partial data를 기존 캐시와 병합
  - django-unfold 다크 테마 + whitenoise static 서빙
- **WBS 2.3.2~2.3.4**: 서버 관리 UI (`7037f0a`)
  - `/agents` 관리 페이지: 탭 필터, 승인/거부/삭제 + ConfirmDialog
  - `latest-metrics` API (Redis → CPU/Mem/Disk 실시간 표시)
  - 10초 polling 실시간 알림 (NEW 배지)
- **Mock API → 실제 Backend WebSocket 연동** (`d70f99b`)
  - ws-store.ts 재작성: Django Channels `/ws/server/{id}/` 연결
  - data-adapter.ts: Agent bytes → Frontend 문자열 변환
  - 메인 대시보드에 로그인 + 서버 선택 플로우 추가
  - Frontend Delta merge: WS partial data 덮어쓰기 방지

### 현재 상태
- **브랜치**: dev (커밋 `d70f99b`)
- **Docker 컨테이너**: backend, celery-worker, celery-beat, postgres, redis, nginx 6개
- **Agent**: server_16 (192.168.0.16) 승인 완료, 실시간 데이터 수신 중
- **메인 대시보드** (`localhost:3000`): 실제 Agent 데이터로 동작 (CPU 99%, Mem 98%, Disk 78%, 컨테이너 23개)
- **관리 페이지** (`localhost:3000/agents`): 서버 관리 동작 확인 완료
- **Admin** (`localhost:8000/admin`): unfold 다크 테마 적용, 메트릭 히스토리 조회 가능

### 세션 시작 시 해야 할 것
1. Docker Desktop 실행 대기 후 개발 스택 기동:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d
   ```
2. 6개 컨테이너 확인: hc-backend(:8000), hc-nginx-dev(:3000), hc-postgres(:5432), hc-redis(:6379), hc-celery-worker, hc-celery-beat
3. Agent(16번 서버)가 자동으로 재연결됨 (30초 backoff 후 WS 연결)
4. `localhost:3000` 접속 → 로그인(admin/admin1234) → server_16 선택 → 대시보드 확인

### 다음 작업 (우선순위 순)
1. **Agent on-demand 명령 연동** (Backend Consumer 수정)
   - Agent가 지원하는 명령 4종: `get_logs`, `inspect`, `control`, `system_info`
   - Agent 프로토콜: `{type: "command", requestId, command, params}` → `{type: "command_response", requestId, success, data}`
   - Backend Consumer에서 Browser → Agent 명령 전달 + 응답 라우팅 구현
   - Frontend 모달들 (ContainerDetail, CPU, Network, Process, Login)을 실제 데이터로 전환
   - 현재 Mock API를 대체하는 것이 목표
2. **WBS 2.4**: 멀티서버 뷰 (서버 카드 그리드, 헤더 드롭다운, 필터링)
3. **Delta Sync 히스토리 개선**: PG 저장 시에도 merge 적용 (현재 0값 레코드 존재)

### 결정사항
- Celery를 Phase 2에서 미리 도입 (Phase 3 AI 분석 기반, 리팩토링 비용 절감)
- On-demand 데이터(로그, inspect, 제어)는 Agent 명령 기능으로 구현 (Mock API 제거 예정)
- 실시간 데이터는 Backend WebSocket, on-demand는 REST or WS command로 분리 (하이브리드 접근)
- Redis DB 0: Channel Layer, DB 1: 메트릭 캐시 (분리)

### 주의점
- `+page.svelte`는 NON-runes 모드 (`$state()` 사용 금지, `let` 사용)
- Agent 소스 수정은 별도 세션에서 진행 (이 세션은 Backend + Frontend만)
- 16번 서버 SSH: `ssh -i ~/.ssh/dcmtool_sync -p 2022 root@192.168.0.16`
- superuser: admin / admin1234 (dev DB)

## 프로젝트 개요

Docker 컨테이너 모니터링 대시보드. Figma 디자인(`MM5pHeO3gfXDchAlBVfs89`)을 정확히 재현하는 것이 목표.
이전 프로젝트(`C:\Users\agics\Desktop\workspace\01. git\DCMTool`)의 TS 리빌드 버전.
To-Be: 멀티 서버 모니터링 플랫폼 (Django Backend + Agent 기반).

## 기술 스택

### Frontend
- **SvelteKit 2.22.0 + Svelte 5** (runes mode: `$props()`, `$state()`, `$derived()`, `$effect()`)
- **adapter-static** (SPA 모드, SSR 비활성화) → nginx에서 정적 파일 서빙
- **3d-force-graph + three.js** - 3D 토폴로지 시각화
- **html2canvas** - 페이지 스크린샷
- `"type": "module"` in package.json → 스크립트는 `.cjs` 확장자 사용

### Backend
- **Django 5 + DRF + Channels** (uvicorn ASGI)
- **PostgreSQL 16 + pgvector** - 데이터 영구 저장 + 벡터 검색
- **Redis 7** - 실시간 캐시 + Celery 큐 + Channel Layer
- **djangorestframework-simplejwt** - JWT 인증

### Infrastructure
- **nginx** - 정적 파일 서빙 + API/WS 리버스 프록시
- **Docker Compose** - 개발/배포 환경 관리 (override 패턴)

## 중요: serena LSP 범위 (이 프로젝트 한정)

전역 "파일 탐색 규칙 (serena 우선)" 규칙(`~/.claude/CLAUDE.md`) 적용 시 주의:
- 이 프로젝트 `.serena/project.yml`은 **typescript LSP만** 활성 → Python 백엔드는 Read/Grep 유지.
- `.svelte`는 `<script lang="ts">` 내부 심볼만 detected. 마크업 구조 조사는 Read 필요.

## 중요: Svelte 5 runes 주의사항

- **`+page.svelte`는 runes mode가 아님** → `$state()` 사용 불가. 반드시 `let` 사용.
- **컴포넌트 파일(.svelte)은 runes mode** → `$props()`, `$state()` 등 사용 가능.
- `+page.svelte`에서 `$state()` 사용하면 전체 페이지가 깨짐 (빈 화면).

## CSS 디자인 토큰

```
--bg-base: #0d1117    --bg-card: #121720     --bg-tab: #151c27
--accent: #30d5c8     --accent-dark: #094b66  --border: #1f2937
--error: #ef4444      --error-soft: #ef3e5e
--text-primary: #cbd5e1  --text-secondary: #64748b  --text-muted: #475569
--tag-bg: #334155     --radius-md: 8px       --radius-full: 9999px
```

## 프로젝트 구조

```
HyperCube/                           # Monorepo root
├── frontend/                        # SvelteKit (adapter-static)
│   ├── src/
│   │   ├── routes/
│   │   │   ├── +page.svelte         # 메인 페이지 (NON-runes, ~970줄)
│   │   │   ├── +layout.svelte       # CSS 변수, 전역 스타일
│   │   │   ├── +layout.ts           # SSR 비활성화 (ssr = false)
│   │   │   └── api/containers/      # API Routes (Django 이관 전까지 유지)
│   │   └── lib/
│   │       ├── components/          # Svelte 컴포넌트 (runes mode)
│   │       └── assets/icons/        # Figma SVG 아이콘
│   ├── Dockerfile                   # prod: 빌드 → nginx 서빙
│   ├── Dockerfile.dev               # dev: 빌드 → nginx 서빙
│   └── svelte.config.js             # adapter-static, BASE_PATH
├── backend/                         # Django + DRF + Channels
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py              # DB, Redis, Channels, DRF 설정
│   │   │   └── dev.py               # DEBUG, CORS, debug-toolbar
│   │   ├── urls.py                  # admin + api/ 라우팅
│   │   └── asgi.py                  # Channels ProtocolTypeRouter
│   ├── apps/
│   │   ├── agents/                  # Agent 앱 (Phase 1.2에서 구현)
│   │   └── containers/              # Container 앱 (Phase 1.2에서 구현)
│   ├── requirements/
│   │   ├── base.txt                 # Django, DRF, Channels, psycopg 등
│   │   └── dev.txt                  # debug-toolbar, ipython
│   └── Dockerfile.dev               # python:3.12-slim, dev 의존성
├── nginx/
│   ├── nginx.conf                   # prod: :7003, /hypercube 경로
│   └── nginx.dev.conf               # dev: :3000, / 경로
├── docker-compose.yml               # 공통 base (postgres, redis, backend)
├── docker-compose.dev.yml           # 개발 override (볼륨 마운트, nginx dev)
├── docker-compose.prod.yml          # 배포 override (빌드, nginx prod)
├── .env.dev                         # 개발 환경변수 (git 미포함)
├── .env.example                     # 환경변수 템플릿
└── docs/
    ├── to-be-architecture.md        # 목표 시스템 아키텍처
    ├── docker-workflow.md           # Docker 개발/배포 워크플로우
    ├── api.md                       # API 명세
    └── development.md               # 개발 가이드
```

## Docker 개발 환경

### 컨테이너 구성 (dev)
```
nginx (:3000)      → 정적 파일 서빙 + API 프록시
backend (:8000)    → Django (uvicorn --reload)
postgres (:5432)   → pgvector/pgvector:pg16
redis (:6379)      → redis:7-alpine
```

### 실행 명령
```bash
# 전체 스택 실행
docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up

# Backend만 재빌드
docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up backend --build

# Django 마이그레이션
docker compose exec hc-backend python manage.py migrate

# Django 관리자 계정
docker compose exec hc-backend python manage.py createsuperuser
```

### 볼륨 마운트 (개발)
- `./backend:/app` → Backend 소스 변경 시 uvicorn 자동 리로드
- Frontend는 빌드 후 nginx에서 서빙 (소스 변경 시 재빌드 필요)

## API 응답 구조 (핵심)

### GET /api/containers/[id]
```json
{ "success": true, "data": { "inspect": { Docker inspect }, "stats": { Docker stats } } }
```
- `data.inspect.Config.Cmd` / `.WorkingDir` / `.Env`
- `data.inspect.State.Status` / `.StartedAt`
- `data.stats.memory_stats.usage` (bytes)

### GET /api/containers/[id]/metrics
```json
{ "success": true, "data": {
  "cpu": { "usage": 0.08, "cores": 4 },
  "memory": { "usage": 69087232, "limit": 8350298112, "percent": 0.83 },
  "network": { "rx": 2516582, "tx": 838860 },
  "disk": { "read": 12698, "write": 4194304 }
}}
```
- `memory.usage`는 **bytes** → MB 변환 필요 (`/ 1048576`)
- `network`는 `rx`/`tx` (NOT `rx_bytes`/`tx_bytes`)

### GET /api/containers/[id]/logs?tail=100
```json
{ "success": true, "data": { "logs": ["line1", "line2", ...], "containerId": "..." } }
```
- `data.logs`는 string 배열 (raw 로그 라인)
- Docker 8바이트 헤더는 서버에서 이미 제거됨

## 구현 완료 기능

- [x] 3D Force Graph 토폴로지 뷰 (프로젝트별 그룹핑, convex hull)
- [x] GROUP 뷰: ProjectCard + 헥사곤 컨테이너 클릭
- [x] LIST 뷰: 검색(컨테이너명/프로젝트명), 컬럼 정렬, 상세보기 버튼
- [x] StatCard: Total/Running/Waiting/Stopped (Figma 스타일)
- [x] Auto-rotate 토글 (requestAnimationFrame)
- [x] 전체 페이지 스크린샷 (html2canvas)
- [x] 컨테이너 상세 모달 (Info/Metrics/Logs 3탭)
- [x] Docker Compose 인프라 (PostgreSQL + Redis + Django + nginx)
- [x] adapter-static 전환 (SSR 제거, nginx 정적 서빙)

## 과거 이슈 & 해결책 (반복 방지)

| 이슈 | 원인 | 해결 |
|------|------|------|
| `+page.svelte`에서 `$state()` 사용 → 빈 화면 | runes mode 아닌 파일 | `let` 사용 |
| Edit 도구 문자열 매칭 실패 | Windows `\r\n` 줄바꿈 | `Write`로 전체 파일 재작성 |
| `.js` 스크립트 ESM 에러 | `"type": "module"` | `.cjs` 확장자 사용 |
| `/tmp/` 경로 실패 | Windows 환경 | `__dirname` 상대 경로 사용 |
| inspect 데이터 안 불러와짐 | `$effect` 타이밍 이슈 | `loadData()`에서 `Promise.allSettled` + 순차 실행 |
| sparkline 차트 안 그려짐 | `history.length < 2` 조건 | 1개 데이터도 수평선으로 표시 |
| 로그 0줄 표시 | `parseLogs`로 과도한 파싱 | raw string 배열 그대로 표시 |

## Figma 참조

- File key: `MM5pHeO3gfXDchAlBVfs89`
- Token: `figd_3_dtSGt3F8ZiqwQJuC-7nfu6vg1kPw2OpxjSaqNx`
- 주요 프레임: `01.메인`, `02.메인 > 리스트`, `04~06.컨테이너 상세 정보`
- 아이콘은 이미 `frontend/src/lib/assets/icons/`에 추출 완료

## 배포 아키텍처

### 인프라 구조
- **개발 (63번)**: Docker Compose (nginx:3000 + backend:8000 + postgres + redis), bind-mount 소스 + vite HMR
- **운영 (16번)**: GHCR pre-built image pull 방식. `/home/agics-ai/docker/hypercube` 에서 docker compose 실행
- **운영 접속 URL**: `http://192.168.0.16:3334/hypercube` (HC_PORT=3334 → 컨테이너 7003)

### 배포 설정 (adapter-static + nginx)
- `svelte.config.js`: adapter-static, `paths.base: process.env.BASE_PATH || ''`
- `frontend/Dockerfile`: multi-stage build → nginx:alpine 서빙
- `nginx/nginx.conf`: `/hypercube` 정적 파일 + `/hypercube/api` → backend 프록시
- Docker Compose override 패턴: base + dev/prod

### prod 배포 (16번 서버) — 표준 절차

**현행 방식: dev → main 머지만 하면 자동 배포 (deploy-prod.yml)**

```bash
# 1. dev → main PR 생성 + 머지.
gh pr create --base main --head dev --title "..."
gh pr merge <num> --merge

# 끝. 자동으로:
# - Build and push images: GHCR 에 sha-<short> + latest 태그 push (~3분)
# - Deploy to 16 prod: 16번 self-hosted runner (label: hc16-prod) 가
#   /home/agics-ai/docker/hypercube .env 의 IMAGE_TAG 갱신 + docker compose
#   pull && up -d. Health check (curl http://localhost:3334/hypercube/) 통과 시 success.
```

수동 redeploy 또는 특정 sha pin:
```bash
gh workflow run deploy-prod.yml -f sha=14e92fa
# 또는 GitHub Actions UI 의 "Run workflow"
```

- Migration 은 backend container entrypoint 가 자동 처리 (`manage.py migrate --noinput`).
- workflow 가 health check 까지 통과해야 success — 실패 시 알림 / log 확인.

### 16번 self-hosted runner 운영 메모

- 위치: `/home/agics-ai/actions-runner-hypercube/` (가칭, 실제 경로 확인 필요)
- 등록: `qkr7287/HyperCube` repo, label `self-hosted`, `hc16-prod`
- systemd: `actions.runner.qkr7287-HyperCube.<runner-name>.service` 로 자동시작
- offline 됐을 때 복구: `sudo systemctl start actions.runner.qkr7287-HyperCube.<name>`

**금지 (절대 쓰지 말 것)**: `dev-agics/DCMTool` repo 의 sync-to-dcmtool.yml / deploy.yml 경로.
구식 chain (HyperCube main → DCMTool dev/main → self-hosted runner) 폐지.
DCMTool 측에 잔여 workflow 파일 / runner 등록은 **무시**. runner 등록 풀려있고
HyperCube 만 단독으로 배포 책임진다.

### prod 배포 정보
- **prod 폴더**: `/home/agics-ai/docker/hypercube` (16번)
- **포트**: 3334 (HC_PORT)
- **Image registry**: `ghcr.io/qkr7287/hypercube-backend`, `ghcr.io/qkr7287/hypercube-nginx`
- **Tag 형식**: `sha-<7chars>` (commit pin 권장) 또는 `latest` (항상 최신 main)

### Repo 정보
- **HyperCube**: `qkr7287/HyperCube` — 작업 + 배포 대상 single source of truth
- **DCMTool**: `dev-agics/DCMTool` — **deprecated**. 과거 자동 sync 흔적은 무시.

## 참고: 이전 프로젝트

`C:\Users\agics\Desktop\workspace\01. git\DCMTool` - Svelte 4 버전. 192.168.0.16 서버에서 운영.
ContainerDetails.svelte, ContainerMetricsChart.svelte(Chart.js) 등 참고 가능.
