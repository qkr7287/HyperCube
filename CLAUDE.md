# HyperCube - Server & Container Monitoring Platform

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
- **개발**: Docker Compose (nginx:3000 + backend:8000 + postgres + redis)
- **운영**: nginx(:7003) → 정적 파일 + API/WS 프록시 → Django(:8000)
- **접속 URL**: `http://192.168.0.16:7003/hypercube`

### 배포 설정 (adapter-static + nginx)
- `svelte.config.js`: adapter-static, `paths.base: process.env.BASE_PATH || ''`
- `frontend/Dockerfile`: multi-stage build → nginx:alpine 서빙
- `nginx/nginx.conf`: `/hypercube` 정적 파일 + `/hypercube/api` → backend 프록시
- Docker Compose override 패턴: base + dev/prod

### CI/CD 플로우 (GitHub Actions)
```
1. HyperCube dev → PR → HyperCube main  (수동 승인)
2. HyperCube main → DCMTool dev          (자동, sync-to-dcmtool.yml)
3. DCMTool dev → PR → DCMTool main         (수동 승인)
4. DCMTool main 머지 → 16번 서버 배포       (자동, deploy.yml, self-hosted runner)
```

### Repo 정보
- **HyperCube**: `qkr7287/HyperCube` (개인 작업 repo, Claude Code MCP 연결)
- **DCMTool**: `dev-agics/DCMTool` (팀 공유 repo, 배포 대상)

## 참고: 이전 프로젝트

`C:\Users\agics\Desktop\workspace\01. git\DCMTool` - Svelte 4 버전. 192.168.0.16 서버에서 운영.
ContainerDetails.svelte, ContainerMetricsChart.svelte(Chart.js) 등 참고 가능.
