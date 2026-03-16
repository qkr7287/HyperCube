# DCMTool_TS - Docker Container Monitor Tool

## 프로젝트 개요

Docker 컨테이너 모니터링 대시보드. Figma 디자인(`MM5pHeO3gfXDchAlBVfs89`)을 정확히 재현하는 것이 목표.
이전 프로젝트(`C:\Users\agics\Desktop\workspace\01. git\DCMTool`)의 TS 리빌드 버전.

## 기술 스택

- **SvelteKit 2.22.0 + Svelte 5** (runes mode: `$props()`, `$state()`, `$derived()`, `$effect()`)
- **dockerode** - Docker API 클라이언트
- **3d-force-graph + three.js** - 3D 토폴로지 시각화
- **html2canvas** - 페이지 스크린샷
- `"type": "module"` in package.json → 스크립트는 `.cjs` 확장자 사용

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
src/
├── routes/
│   ├── +page.svelte              # 메인 페이지 (NON-runes, ~970줄)
│   ├── +layout.svelte            # CSS 변수, 전역 스타일
│   └── api/containers/
│       ├── +server.ts            # GET 전체 컨테이너 목록
│       └── [id]/
│           ├── +server.ts        # GET inspect+stats → { inspect, stats }
│           ├── metrics/+server.ts # GET 메트릭 → { cpu, memory, network:{rx,tx}, disk }
│           ├── logs/+server.ts    # GET 로그 → { logs: string[], containerId }
│           └── control/+server.ts # POST { action } → start/stop/restart/pause/unpause/kill/remove
├── lib/
│   ├── components/
│   │   ├── RightSidebar.svelte   # GROUP/LIST 탭, 검색, 정렬, 상세보기 버튼
│   │   ├── ProjectCard.svelte    # 프로젝트 카드 + 컨테이너 헥사곤 클릭
│   │   ├── ContainerDetailModal.svelte  # 컨테이너 상세 팝업 (Info/Metrics/Logs)
│   │   ├── StatCard.svelte       # Total/Running/Waiting/Stopped 카드
│   │   └── TopologyToolbar.svelte # Screenshot/Rotate/Zoom 툴바
│   └── assets/icons/             # Figma에서 추출한 SVG 아이콘들
```

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
  - Info: 기본정보, 설정(명령어/WorkDir/환경변수 펼치기), 리소스 사용량
  - Metrics: CPU/Memory sparkline 차트 (SVG, 5초 간격), Network, Disk I/O
  - Logs: 터미널 스타일, 검색, Auto-refresh(3초), Auto-scroll, Download
  - Footer: 상태별 조건부 버튼 (running→중지/재시작/일시정지, paused→재개, stopped→시작)
  - 컨트롤 후 상태 자동 갱신 + 메인 페이지 컨테이너 목록 갱신

## 과거 이슈 & 해결책 (반복 방지)

| 이슈 | 원인 | 해결 |
|------|------|------|
| `+page.svelte`에서 `$state()` 사용 → 빈 화면 | runes mode 아닌 파일 | `let` 사용 |
| Edit 도구 문자열 매칭 실패 | Windows `\r\n` 줄바꿈 | `Write`로 전체 파일 재작성 |
| `.js` 스크립트 ESM 에러 | `"type": "module"` | `.cjs` 확장자 사용 |
| `/tmp/` 경로 실패 | Windows 환경 | `__dirname` 상대 경로 사용 |
| Figma MCP 서브에이전트 실패 | Bash 도구 없음 | 메인 컨텍스트에서 curl 직접 실행 |
| inspect 데이터 안 불러와짐 | `$effect` 타이밍 이슈 | `loadData()`에서 `Promise.allSettled` + 순차 실행 |
| sparkline 차트 안 그려짐 | `history.length < 2` 조건 | 1개 데이터도 수평선으로 표시 |
| 로그 0줄 표시 | `parseLogs`로 과도한 파싱 | raw string 배열 그대로 표시 |

## Figma 참조

- File key: `MM5pHeO3gfXDchAlBVfs89`
- Token: `figd_3_dtSGt3F8ZiqwQJuC-7nfu6vg1kPw2OpxjSaqNx`
- 주요 프레임: `01.메인`, `02.메인 > 리스트`, `04~06.컨테이너 상세 정보`
- 아이콘은 이미 `src/lib/assets/icons/`에 추출 완료

## 배포 아키텍처

### 인프라 구조
- **개발**: Windows PC → `npm run dev` (localhost:5173) → vite proxy → 192.168.0.16:3334
- **운영**: nginx(agdevblog_frontend, port 7003) → `/dcmtool` reverse proxy → dcm-frontend 컨테이너(port 3334)
- **접속 URL**: `http://192.168.0.16:7003/dcmtool`

### 배포 설정 (adapter-node)
- `svelte.config.js`: `paths.base: process.env.BASE_PATH || ''`
- `vite.config.ts`: `API_TARGET` 환경변수로 프록시 대상 설정
- 모든 fetch 경로에 `${base}` 적용 완료 (`import { base } from '$app/paths'`)
- Dockerfile: multi-stage build, `BASE_PATH=/dcmtool`, port 3334
- docker-compose.yml: docker.sock, /proc, /etc/hostname, utmp 마운트, pid:host, privileged
- 로컬 빌드 테스트: `MSYS_NO_PATHCONV=1 BASE_PATH=/dcmtool npm run build` (Git Bash path conversion 방지)

### CI/CD 플로우 (GitHub Actions)
```
1. DCMTool_TS dev → PR → DCMTool_TS main  (수동 승인)
2. DCMTool_TS main → DCMTool dev           (자동, sync-to-dcmtool.yml)
3. DCMTool dev → PR → DCMTool main         (수동 승인)
4. DCMTool main 머지 → 16번 서버 배포       (자동, deploy.yml, self-hosted runner)
```

### Repo 정보
- **DCMTool_TS**: `qkr7287/DCMTool_TS` (개인 작업 repo, Claude Code MCP 연결)
- **DCMTool**: `dev-agics/DCMTool` (팀 공유 repo, 배포 대상)

### CI/CD 진행상황 (TODO)
- [x] adapter-node 전환 + BASE_PATH 설정
- [x] 모든 fetch 경로 `${base}` 적용
- [x] Dockerfile, docker-compose.yml, .dockerignore 작성
- [x] 로컬 빌드 테스트 통과
- [x] DCMTool_TS: `.github/workflows/sync-to-dcmtool.yml` 작성
- [x] DCMTool: `.github/workflows/deploy.yml` 작성 (self-hosted runner)
- [ ] 두 repo에 `dev` 브랜치 생성
- [ ] GitHub Secrets 설정:
  - DCMTool_TS: `DCMTOOL_PAT` (dev-agics/DCMTool push 권한 PAT)
  - DCMTool: `DEPLOY_PATH` (16번 서버의 DCMTool 프로젝트 경로)
- [ ] 16번 서버에 self-hosted runner 설치 (Settings → Actions → Runners)
- [ ] DCMTool_TS 변경사항 commit + push
- [ ] DCMTool에 workflow 파일 commit + push
- [ ] 전체 플로우 테스트 (dev→main PR → 동기화 → 배포)

## 참고: 이전 프로젝트

`C:\Users\agics\Desktop\workspace\01. git\DCMTool` - Svelte 4 버전. 192.168.0.16 서버에서 운영.
ContainerDetails.svelte, ContainerMetricsChart.svelte(Chart.js) 등 참고 가능.
