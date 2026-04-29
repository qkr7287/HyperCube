# Claude Code 설정 (HyperCube)

CLAUDE.md 다이어트 + on-demand docs 인덱스 + sync hook + 프로젝트 전용 skill 구조 가이드. **2026-04-29** 도입(Option Z).

## 왜 이렇게 했는가

- 이전 CLAUDE.md ~250줄 → 매 턴 ~5,000 tokens 소비
- "Current Work 2026-04-10" 같은 시점성 정보 stale
- 메모리(`progress.md`)와 중복

→ **CLAUDE.md를 60줄 인덱스로 다이어트**, 상세는 docs/에 두고 필요 시 read, 코드 변경 시 docs sync는 hook이 자동 reminder. 매 턴 베이스라인 컨텍스트 약 **40% 절감 추정**.

## 새 구조 한눈에

```
HyperCube/
├── CLAUDE.md (60줄)              # 핵심 룰 + doc 인덱스 + sync 룰 + 과거 이슈 표
├── docs/
│   ├── (기존 22개 그대로)         # api.md, agent-protocol.md 등은 위치 유지
│   ├── specs/
│   │   └── design-tokens.md      # 신규 (CSS 변수 source-of-truth = +layout.svelte)
│   └── runbooks/
│       ├── deploy.md             # 신규 (배포 절차, 16번 runner)
│       └── claude-code-setup.md  # 이 문서
└── .claude/
    ├── settings.json             # PostToolUse hook 등록 (팀 공유)
    ├── settings.local.json       # 개인 권한 (gitignored)
    ├── hooks/
    │   └── sync-reminder.sh      # code 변경 → docs sync reminder
    └── skills/
        └── hc-api-sync/SKILL.md  # API/WS/Agent 변경 시 docs sync 절차
```

## 사용법

### 1. 평소 작업 (변화 없음)

평소처럼 Claude Code에 작업 요청. CLAUDE.md가 60줄로 줄었지만 **인덱스가 들어있어** 필요 시 Claude가 docs/에서 알아서 읽어옴. 사용자는 신경 쓸 게 없음.

### 2. API/WS/Agent 코드 변경했을 때

**자동 동작**:
- Claude가 `backend/apps/containers/viewsets.py` 같은 파일을 Edit/Write하면 → `.claude/hooks/sync-reminder.sh`가 PostToolUse hook으로 발동 → stderr에 `[sync] REST API 변경? → docs/api.md ... 확인` reminder 1줄 출력
- Claude가 reminder 보고 docs도 함께 업데이트해야 함

**사용자 책임**:
- Claude가 코드만 고치고 docs는 안 고치는 경우 → "docs도 sync해" 한마디
- reminder를 무시하지 않게끔 모니터

### 3. CSS 변수 / Figma 변경

- `frontend/src/routes/+layout.svelte`의 `:root` 변경 시 reminder 자동 발동
- `docs/specs/design-tokens.md`도 함께 업데이트

### 4. 배포 / Docker Compose 변경

- `docker-compose*.yml`, `.github/workflows/deploy*.yml` 변경 시 reminder 발동
- `docs/runbooks/deploy.md` sync

### 5. 새 기능 만들 때

- Claude가 인덱스 보고 관련 docs 미리 읽어오는지 확인 (보통 자동)
- 인덱스에 없는 새 영역이면 → CLAUDE.md 인덱스에 1줄 추가하라고 요청

## 검증 — 잘 동작하는지 확인하는 법

### 검증 1: Hook이 실제로 발동하는가

수동 테스트 (코드 안 건드리고 hook 스크립트만 검증):

```bash
cd "C:/Users/agics/Desktop/workspace/01. git/HyperCube"
echo '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/containers/viewsets.py"}}' | bash .claude/hooks/sync-reminder.sh
```

**예상 출력** (stderr):
```
[sync] REST API 변경? → docs/api.md + docs/agent-payload-contract.md 확인
```

다른 케이스도:
```bash
# WS consumers
echo '{"tool_name":"Edit","tool_input":{"file_path":"backend/apps/common/consumers.py"}}' | bash .claude/hooks/sync-reminder.sh

# CSS 변수
echo '{"tool_name":"Edit","tool_input":{"file_path":"frontend/src/routes/+layout.svelte"}}' | bash .claude/hooks/sync-reminder.sh

# Docker
echo '{"tool_name":"Edit","tool_input":{"file_path":"docker-compose.yml"}}' | bash .claude/hooks/sync-reminder.sh

# 매칭 안 되는 케이스 (침묵해야 함)
echo '{"tool_name":"Edit","tool_input":{"file_path":"frontend/src/routes/+page.svelte"}}' | bash .claude/hooks/sync-reminder.sh
```

매칭은 알림, 비매칭은 침묵 — 모두 exit 0.

### 검증 2: 실제 Claude 세션에서 hook 동작

다음 요청을 Claude에 던지기:

> "backend/apps/containers/viewsets.py에 빈 줄 1줄 추가하고 다시 지워줘"

Claude의 Edit 결과 직후 `[sync] ...` 메시지가 stderr에 떠야 함. 안 뜨면:
- `.claude/settings.json`이 잘 로드됐는지 확인
- `bash` 명령이 PATH에 있는지 확인
- Claude Code 재시작 후 재시도

### 검증 3: Skill 자동 invocation

> "API 엔드포인트 추가하려는데 docs도 같이 봐야 해?"

Claude가 `hc-api-sync` skill을 인용하거나 절차를 따르는지 확인. 자동 매칭이 안 뜨면:
- `.claude/skills/hc-api-sync/SKILL.md`의 `description` 필드 보강
- 또는 사용자가 명시적으로 `/skills` 또는 "hc-api-sync skill로 docs sync해" 요청

### 검증 4: CLAUDE.md 사이즈

```bash
wc -l "C:/Users/agics/Desktop/workspace/01. git/HyperCube/CLAUDE.md"
```

**60줄 정도** 유지. 80줄 넘으면 다시 다이어트 검토.

### 검증 5: docs frontmatter sync 상태

`docs/specs/design-tokens.md` 또는 `docs/runbooks/deploy.md` 상단 frontmatter:
```yaml
last-synced-commit: 36a827e
```

현재 HEAD와 다르면(예: 한참 commit이 진행됐는데 last-synced-commit이 옛날 sha면) **doc이 stale일 가능성**.

확인: `git rev-parse --short HEAD` vs frontmatter 비교. 다르면 frontmatter `verify` 명령 실행해서 코드와 docs 일치 여부 검증.

## 트러블슈팅

### Hook reminder가 안 뜸

1. `bash --version` 확인 (git bash 필요)
2. `.claude/settings.json` 형식 검증: `cat .claude/settings.json | python -m json.tool`
3. 직접 실행: `echo '{}' | bash .claude/hooks/sync-reminder.sh; echo "exit=$?"` → exit=0 떠야 함
4. Claude Code 재시작

### Hook이 너무 자주 떠서 거슬림

- 매칭 패턴을 좁히려면 `.claude/hooks/sync-reminder.sh`의 `case` 블록 수정
- 임시 비활성: `.claude/settings.local.json`에서 hook override 가능

### Skill이 자동 호출 안 됨

자동 invocation은 description 매칭에 의존하므로 100% 보장 X. fallback:
- CLAUDE.md "sync 룰" 표가 1차 방어
- 사용자가 명시적 호출 (`/skills`, "hc-api-sync 따라해" 등)

### docs/specs, docs/runbooks가 git에 안 잡힘

- `.gitignore`의 `docs/plans/` 만 막힘. specs/runbooks는 추적됨
- `git status`에 안 보이면 untracked 가능 — `git add docs/specs docs/runbooks`

### .claude/ 파일이 다른 머신에서 안 보임

`.gitignore` 룰:
```
.claude/*               # 모두 ignore
!.claude/settings.json  # 단, 이 3개는 추적
!.claude/hooks/
!.claude/skills/
.claude/settings.local.json  # local 권한은 다시 ignore
```

`.claude/`의 PNG, settings.local.json은 의도적으로 추적 안 함.

## 향후 확장 (Option Y로 발전 시)

이번 세션은 **Option Z (단계적)**. 1~2주 운영 후 효과 좋으면 Y로 확장:

- 기존 `docs/api.md` 등 → `docs/specs/api-rest.md`로 git mv (이름 통일)
- 모든 docs에 frontmatter 추가
- skill 추가 (예: `hc-deploy`, `hc-frontend-design`)
- CLAUDE.md를 ~40줄로 추가 다이어트

확장 결정 기준:
- Hook reminder 따라 docs sync 잘 되고 있는가?
- Skill 자동 invocation 성공률은?
- CLAUDE.md 60줄로 충분한가, 더 줄여도 되는가?
