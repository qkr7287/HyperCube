# Agent 작업 채널 (GitHub Issues)

HyperCube(backend+frontend) ↔ `qkr7287/HyperCube-agent` 두 repo 사이의 작업 요청·회신 채널 정의. **이 문서가 single source of truth**. CLAUDE.md / 메모리는 이 문서를 가리키기만 함.

## 결정 사실 (변경 금지)

- 채널: **GitHub Issues** (`qkr7287/HyperCube-agent`)
- 폐기: 파일 기반 mailbox 방식 (`docs/agent-mailbox.md`, agent 측 `docs/hypercube-mailbox.md`)
- 결정일: 2026-05-08
- 첫 dogfooding 사례: <https://github.com/qkr7287/HyperCube-agent/issues/11>

폐기 사유: 일회성 prompt/handoff/response 파일이 4개월 동안 11개 누적 → 정리 비용 큼. mailbox도 같은 누적 패턴이었음. Issues는 상태 트래킹 + 검색 + cross-repo 참조 + commit 자동 close가 모두 가능해 mailbox와 prompt의 단점을 함께 해소.

## 작업 흐름 (5단계)

1. **요청 생성** — HyperCube 측에서 `gh issue create -R qkr7287/HyperCube-agent -t "..." -b "..."`. body는 아래 템플릿.
2. **HyperCube 측 작업** — 같은 작업이 양쪽 repo 변경을 동시에 요구하면 HyperCube 측 변경 먼저 진행. commit message에 `Refs qkr7287/HyperCube-agent#NN` 포함.
3. **Agent 측 작업** — agent repo 폴더에서 별도 Claude 세션 시작 후 `이슈 NN번 작업해줘` 한 마디. 세션이 `gh issue view NN` 으로 본문 읽고 진행.
4. **Close** — agent 측 commit 또는 PR description에 `Closes #NN` (같은 repo) → 머지되면 issue 자동 closed.
5. **검증** — HyperCube 측에서 `gh issue view -R qkr7287/HyperCube-agent NN` 으로 closed 상태 확인. 필요한 후속 docs 갱신 (`docs/agent-protocol.md` / `docs/agent-payload-contract.md`).

## Issue body 템플릿

```markdown
## Background
(왜 필요한가 — 1~3줄. 어떤 화면/기능이 막혀있는지)

## Goal
(한 문장 — 무엇을 추가/변경하는가)

## Schema (정확한 형식)
- 추가/변경할 명령 또는 메시지 타입
- params, success.data, error 케이스
- 예시 JSON

## 동작 사양
(Dockerode / cgroup / /proc 등 구현 힌트는 OK, 강제 X)

## 백워드 호환성
- 기존 메시지에 영향 없음 (또는 영향 + 마이그레이션 계획)

## 테스트 시나리오
- offline 컨테이너
- 권한 부족
- minimal image (alpine 등)
- 그 외 엣지 케이스

## HyperCube 측 갱신 대상 docs
- `docs/agent-protocol.md` 의 어느 섹션
- `docs/agent-payload-contract.md` 의 어느 섹션

## Verification
- [ ] 검증 항목 1
- [ ] 검증 항목 2
```

## Close 규칙

| 상황 | 사용 표기 |
|------|-----------|
| Agent repo 안의 PR/commit이 issue를 끝낼 때 | `Closes #NN` |
| HyperCube repo의 commit이 단순 참조만 할 때 | `Refs qkr7287/HyperCube-agent#NN` |
| HyperCube repo의 commit이 cross-repo로 close 시도 | `Closes qkr7287/HyperCube-agent#NN` (PR 머지 시점에만 동작, 단순 commit ref면 자동 close 안 됨 — `Refs` 권장) |

## 급할 때 보조 채널 (prompt fallback)

Issue 만들기 어려운 즉시성이 필요할 때만 self-contained prompt를 user에게 대화창으로 출력해 즉시 전달. 단 **prompt도 동일한 사양 형식 사용** + **issue도 같이 만들어 둠** (issue가 SSoT, prompt는 사본).

## 검증 체크리스트 (이 문서 따른 작업이 끝났을 때)

- [ ] 요청 issue가 `qkr7287/HyperCube-agent` 에 존재
- [ ] HyperCube 측 commit에 issue ref 포함 (`Refs ...` 또는 `Closes ...`)
- [ ] Agent 측 작업 commit에 `Closes #NN`
- [ ] Issue가 closed 상태
- [ ] 필요 시 `docs/agent-protocol.md` / `docs/agent-payload-contract.md` 갱신

## 사례 archive

| Issue | 제목 | 상태 |
|-------|------|------|
| [#11](https://github.com/qkr7287/HyperCube-agent/issues/11) | Retire mailbox docs in favor of GitHub Issues (cross-repo channel) | 첫 dogfooding 사례. HyperCube 측 commit `5d1065b` |
