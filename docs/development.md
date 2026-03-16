# 개발 가이드

## 로컬 개발 환경

### 필요 조건

- Node.js 20 이상
- npm

Docker는 로컬에 없어도 됩니다. dev 모드에서는 192.168.0.16 서버의 API를 프록시합니다.

### 설치 및 실행

```bash
# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
# -> http://localhost:3334
```

### 개발 모드 동작 방식

`npm run dev` 실행 시:
- UI: 로컬 Vite dev server에서 렌더링 (HMR 지원)
- API: `src/hooks.server.ts`에서 모든 `/api/*` 요청을 `192.168.0.16:3334`로 전달
- 즉, 로컬에 Docker가 없어도 16번 서버의 실제 컨테이너 데이터로 개발 가능

### 환경 설정

`.env` 파일:
```
API_TARGET=http://192.168.0.16:3334
```

## 브랜치 전략

```
dev (개발) → PR → main (배포)
```

- **dev**: 모든 개발 작업은 여기서
- **main**: 안정 버전만. PR merge 시 자동으로 DCMTool에 동기화

### 작업 흐름

1. `dev` 브랜치에서 코드 수정
2. commit & push
3. GitHub에서 `dev → main` Pull Request 생성
4. 리뷰 후 merge
5. 자동으로 `dev-agics/DCMTool` dev 브랜치에 동기화
6. `dev-agics/DCMTool`에서 `dev → main` PR 생성 & merge
7. 16번 서버에 자동 배포

## 커밋 규칙

Conventional Commits 형식을 따릅니다:

```
<type>(<scope>): <description>
```

### 타입

| 타입 | 설명 |
|------|------|
| `feat` | 새로운 기능 |
| `fix` | 버그 수정 |
| `refactor` | 기능 변경 없는 코드 개선 |
| `docs` | 문서 변경 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, 설정 등 기타 변경 |
| `style` | 코드 포맷팅 |
| `perf` | 성능 개선 |

### 예시

```
feat(ui): add container search filter
fix(api): handle Docker socket connection timeout
refactor(deploy): remove BASE_PATH from Dockerfile
docs: update CI/CD pipeline documentation
```

## 주의사항

### Svelte 5 runes

- `+page.svelte`는 runes mode가 **아닙니다** -> `$state()` 사용 불가, `let` 사용
- 컴포넌트 파일(.svelte)은 runes mode -> `$props()`, `$state()` 등 사용 가능
- `+page.svelte`에서 `$state()` 사용하면 빈 화면이 됩니다

### Windows 환경

- Edit 도구 문자열 매칭 실패 시: Windows `\r\n` 줄바꿈 문제. Write로 전체 파일 재작성
- `.js` 스크립트 ESM 에러: `"type": "module"` 설정 때문. `.cjs` 확장자 사용
- `/tmp/` 경로 실패: Windows 환경에서는 `__dirname` 상대 경로 사용

## 프로젝트 구조 상세

```
src/
├── hooks.server.ts                   # dev 모드: API 요청을 16번 서버로 프록시
├── app.html                          # HTML 템플릿
├── app.d.ts                          # 전역 타입 정의
├── routes/
│   ├── +layout.svelte                # 전역 레이아웃 + CSS 변수
│   ├── +page.svelte                  # 메인 대시보드 (NON-runes, ~970줄)
│   ├── +page.ts                      # ssr = false 설정
│   └── api/
│       ├── containers/
│       │   ├── +server.ts            # GET 전체 컨테이너
│       │   └── [id]/
│       │       ├── +server.ts        # GET inspect + stats
│       │       ├── control/+server.ts # POST start/stop/restart/...
│       │       ├── logs/+server.ts    # GET 로그
│       │       └── metrics/+server.ts # GET CPU/Memory/Network/Disk
│       ├── server/ip/+server.ts      # GET 서버 IP
│       └── system/
│           ├── +server.ts            # GET 시스템 정보
│           ├── logins/+server.ts     # GET 로그인 사용자
│           ├── network/+server.ts    # GET 네트워크 연결
│           └── processes/+server.ts  # GET 프로세스
├── lib/
│   ├── components/
│   │   ├── ContainerDetailModal.svelte  # 컨테이너 상세 (Info/Metrics/Logs 탭)
│   │   ├── LeftSidebar.svelte           # 좌측 시스템 정보 패널
│   │   ├── RightSidebar.svelte          # 우측 GROUP/LIST 뷰
│   │   ├── ProjectCard.svelte           # 프로젝트 카드 + 헥사곤 컨테이너
│   │   ├── StatCard.svelte              # Total/Running/Waiting/Stopped 카드
│   │   ├── TopologyToolbar.svelte       # Screenshot/Rotate/Zoom 툴바
│   │   ├── RackUtilization.svelte       # 랙 사용률 표시
│   │   ├── NetworkDetailModal.svelte    # 네트워크 상세 모달
│   │   ├── LoginDetailModal.svelte      # 로그인 상세 모달
│   │   └── ProcessDetailModal.svelte    # 프로세스 상세 모달
│   └── assets/icons/                    # SVG 아이콘 파일들
```
