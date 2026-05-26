# HyperCube

서버 & 컨테이너 모니터링 플랫폼. SvelteKit + Django + Docker. Figma 디자인(`MM5pHeO3gfXDchAlBVfs89`) 재현.

## 핵심 룰 (반복 실수 방지)

- **로컬에서 dev server 띄우지 말 것** (`npm run dev` 금지). dev는 63번 서버에서 돌아가고, 로컬 폴더가 63번에 sync → Docker bind-mount → 자동 hot-reload. 테스트 URL은 항상 `http://192.168.0.63:3000` (frontend) / `:8000` (backend). 컨테이너는 `hc-frontend-dev` / `hc-backend`.
- `+page.svelte`는 NON-runes 모드 → `let` 사용 (`$state()` 금지, 빈 화면 발생)
- 컴포넌트(.svelte)는 runes mode → `$props()`, `$state()` OK
- Windows 환경 → Edit 매칭 실패 시 `Write`로 전체 재작성 (`\r\n` 줄바꿈 이슈)
- 스크립트는 `.cjs` 확장자 (`"type": "module"` 때문에 `.js` ESM 에러)
- serena LSP는 TypeScript만 활성. Python 백엔드는 Read/Grep 유지
- Agent repo(`qkr7287/HyperCube-agent`)는 별도 세션. 작업 요청은 GitHub Issues로 — 절차/템플릿/예시는 `docs/agent-channel.md` 보고 그대로 이행

## 작업별 doc 인덱스 (필요 시 읽기)

- REST API 명세: `docs/api.md`
- WS / Agent payload: `docs/agent-payload-contract.md`
- Agent 명령 4종 (get_logs / inspect / control / system_info): `docs/agent-protocol.md`
- 디자인 토큰 (CSS 변수, Figma): `docs/specs/design-tokens.md`
- 배포 절차 (16번, deploy-prod.yml): `docs/runbooks/deploy.md`
- 로컬 개발 / Docker Compose: `docs/docker-workflow.md`
- 아키텍처: `docs/architecture.md`, `docs/to-be-architecture.md`
- 운영 메모: `docs/operations.md`
- Agent 작업 요청 흐름 (Issues): `docs/agent-channel.md`
- **컨테이너 대시보드 개선 로드맵**: `docs/dashboard-roadmap.md` — 다음 세션은 여기 보고 어디부터 할지 결정. 세션 시작/끝마다 진행 상황 갱신.

## sync 룰 (코드 변경 시 docs 업데이트 필수)

`.claude/hooks/sync-reminder.sh`가 PostToolUse hook으로 자동 reminder 출력. reminder가 뜨면 해당 docs 즉시 업데이트.

| 변경된 코드 | sync 대상 docs |
|-------------|----------------|
| `backend/apps/{containers,agents}/**` | `docs/api.md` + `docs/agent-payload-contract.md` |
| `backend/apps/common/consumers.py` | `docs/agent-protocol.md` + `docs/agent-payload-contract.md` |
| `frontend/src/routes/+layout.svelte` (`:root`) | `docs/specs/design-tokens.md` |
| `docker-compose*.yml`, `.github/workflows/deploy*.yml`/`build*.yml` | `docs/runbooks/deploy.md` |

`hc-api-sync` skill (`.claude/skills/hc-api-sync/SKILL.md`)이 자동 invocation 시도.

## 과거 이슈 (반복 방지)

| 이슈 | 원인 | 해결 |
|------|------|------|
| `+page.svelte`에서 `$state()` → 빈 화면 | NON-runes 파일 | `let` 사용 |
| Edit 도구 매칭 실패 | Windows `\r\n` | `Write`로 재작성 |
| `.js` ESM 에러 | `"type": "module"` | `.cjs` 확장자 |
| `/tmp/` 경로 실패 | Windows | `__dirname` 상대 경로 |
| inspect 안 불러와짐 | `$effect` 타이밍 | `Promise.allSettled` + 순차 |
| sparkline 안 그려짐 | `history.length < 2` 조건 | 1개도 수평선 |
| 로그 0줄 표시 | 과도한 파싱 | raw string 그대로 |
| `chordTimer is not defined` 런타임 폭발 | 단축키 변수 지우고 `onDestroy` cleanup 한 줄 누락 | lifecycle 변수 제거 시 grep 으로 사용처 전수 확인 |
| Chrome MCP `Cannot access chrome-extension://` | 다른 확장(password manager 등) popup 이 활성 탭 점유 | curl 로 token 받아 `localStorage.setItem('hc_access_token', ...)` + reload 우회 |
| ECharts 라인이 한 점에 cram, x 라벨 1개만 노출 | bucket epoch 가 초 단위인데 time-axis 는 ms 로 해석 → 90ms span | timestamps 에 ×1000 (예: `historyModel.buckets.map(s => s * 1000)`) |
| DELETE 호출 시 Chrome "Failed to fetch" / 500 | `EnvelopeJSONRenderer` 가 204 응답에도 `{success:true,data:null}` (28 bytes) wrap → RFC 7230 위반 | renderer 에서 204 면 `return b""` |
| `mergeSystemInfo` 후 새 컬럼이 `undefined` 로 떨어짐 | delta merge 가 새 필드 카피 안 함 | merge fn 에 새 필드 `?? prev ?? null` 추가 (`||` 는 의미있는 0 도 falsy 처리) |
| API bucket viewset cache 가 매번 miss | cache key 가 `Date.now()` 기준 ISO 라 매 호출 다름 | `_floor_iso_to_bucket` 으로 bucket 경계 정규화 |
| 외부 IP/포트포워딩 으로 접속 시 로그인이 "서버에 연결할 수 없습니다" | prod `.env` 의 `DJANGO_ALLOWED_HOSTS` 가 좁혀져 있어 Django `DisallowedHost` (400 HTML) → 프론트가 fetch error 로 인식 | `.env` 는 `DJANGO_ALLOWED_HOSTS=*`, 로그인 view 는 `authentication_classes=[]` (CSRF 우회). 변경 후 반드시 `docker compose up -d backend` (restart 아님 — env_file 재로드 안 됨) |
| ECharts 차트가 박스보다 작게 그려져 아래가 빔 (예: canvas-wrap 116px / host 90px) | flex 로 크기가 정해진 부모 안에서 자식의 `height: 100%` 가 부모의 flex 계산 높이를 못 잡음 | 부모를 `position: relative` 로 두고 EChartBase host 를 `position: absolute; inset: 0` 로 채움 (위 여백 필요하면 `inset: 10px 0 0 0`) |

## 자동 테스트 (2026-05-15 추가, 총 56건)

- **Frontend unit/component**: `cd frontend && npm test` — Vitest. utils 30 + ContainerKpiBar 12 + FleetAgentCard 7 = 49건. `npm run test:watch` 도 있음.
- **Backend**: `ssh hc-dev-63 "docker exec hc-backend python manage.py test apps.metrics.tests.test_viewsets.ContainerBucketsContractTest"` — 4건. `cpu_max` % 단위 contract.
- **E2E**: `cd frontend && E2E_USER=user1 E2E_PASS='agics12!@' E2E_CONTAINER_ID=560f94bf39ff npm run e2e` — Playwright. 3건. admin 으로 돌리면 컨테이너 owner 아니라 graceful skip.
- **타입 체크**: `cd frontend && npm run check` (svelte-check) — 회귀 lifecycle / 타입 오류.
- **변경 후 권장 사이클**: 코드 → `npm test` (3-7초) → 필요시 `npm run check` → commit → push.

## 환경 정보 (자주 쓰이는 값만)

- 개발 superuser: `admin / agics12!@`
- **dev 서버**: 192.168.0.63 (63번). 로컬 폴더 → 63번 sync → Docker bind-mount → hot-reload. SSH alias `hc-dev-63`, 소스 위치 `/home/agics/ts/HyperCube`
- 16번 SSH: `ssh -i ~/.ssh/dcmtool_sync -p 2022 root@192.168.0.16`
- 메인 대시보드 (dev): `http://192.168.0.63:33000`
- Admin (dev): `http://192.168.0.63:38000/admin`
- prod URL: `http://192.168.0.16:3334/hypercube` (서버 16번이 HC_PORT=3334 로 override; default 는 37003)
- **포트 규칙**: 모든 default host port 에 `3` prefix — postgres `35432`, redis `36379`, backend `38000`, frontend `33000`, prod nginx `37003`. 컨테이너 안 포트는 표준 (5432/6379/8000/3000/7003) 그대로

## 현황 / 진행 상황

`progress.md` 메모리 참조. CLAUDE.md엔 시점성 정보(Current Work, 다음 작업 등) 안 적음.
