# HyperCube

서버 & 컨테이너 모니터링 플랫폼. SvelteKit + Django + Docker. Figma 디자인(`MM5pHeO3gfXDchAlBVfs89`) 재현.

## 핵심 룰 (반복 실수 방지)

- **로컬에서 dev server 띄우지 말 것** (`npm run dev` 금지). dev는 63번 서버에서 돌아가고, 로컬 폴더가 63번에 sync → Docker bind-mount → 자동 hot-reload. 테스트 URL은 항상 `http://192.168.0.63:3000` (frontend) / `:8000` (backend). 컨테이너는 `hc-frontend-dev` / `hc-backend`.
- `+page.svelte`는 NON-runes 모드 → `let` 사용 (`$state()` 금지, 빈 화면 발생)
- 컴포넌트(.svelte)는 runes mode → `$props()`, `$state()` OK
- Windows 환경 → Edit 매칭 실패 시 `Write`로 전체 재작성 (`\r\n` 줄바꿈 이슈)
- 스크립트는 `.cjs` 확장자 (`"type": "module"` 때문에 `.js` ESM 에러)
- serena LSP는 TypeScript만 활성. Python 백엔드는 Read/Grep 유지
- Agent 소스 수정은 별도 세션 (이 repo는 Backend + Frontend만)

## 작업별 doc 인덱스 (필요 시 읽기)

- REST API 명세: `docs/api.md`
- WS / Agent payload: `docs/agent-payload-contract.md`
- Agent 명령 4종 (get_logs / inspect / control / system_info): `docs/agent-protocol.md`
- 디자인 토큰 (CSS 변수, Figma): `docs/specs/design-tokens.md`
- 배포 절차 (16번, deploy-prod.yml): `docs/runbooks/deploy.md`
- 로컬 개발 / Docker Compose: `docs/docker-workflow.md`
- 아키텍처: `docs/architecture.md`, `docs/to-be-architecture.md`
- 운영 메모: `docs/operations.md`

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

## 환경 정보 (자주 쓰이는 값만)

- 개발 superuser: `admin / agics12!@`
- **dev 서버**: 192.168.0.63 (63번). 로컬 폴더 → 63번 sync → Docker bind-mount → hot-reload. SSH alias `hc-dev-63`, 소스 위치 `/home/agics/ts/HyperCube`
- 16번 SSH: `ssh -i ~/.ssh/dcmtool_sync -p 2022 root@192.168.0.16`
- 메인 대시보드 (dev): `http://192.168.0.63:3000`
- Admin (dev): `http://192.168.0.63:8000/admin`
- prod URL: `http://192.168.0.16:3334/hypercube`

## 현황 / 진행 상황

`progress.md` 메모리 참조. CLAUDE.md엔 시점성 정보(Current Work, 다음 작업 등) 안 적음.
