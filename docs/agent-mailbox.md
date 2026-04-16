# Agent Mailbox (HyperCube → Agent)

HyperCube(Backend/Frontend)가 `qkr7287/HyperCube-agent`로 보내는
**outbox**. 이 파일에는 HyperCube 측이 Agent 측에 요청하거나
공지하는 항목만 들어간다. 반대 방향(Agent → HyperCube)은 Agent
repo에 별도 mailbox가 있다.

| 방향 | 위치 | 작성자 |
|---|---|---|
| HyperCube → Agent | `qkr7287/HyperCube/docs/agent-mailbox.md` (이 파일) | HyperCube |
| Agent → HyperCube | `qkr7287/HyperCube-agent/docs/hypercube-mailbox.md` | Agent |

원칙: **각 측은 자기 repo의 mailbox에만 쓴다**. 상대방은 읽기만.
cross-repo PR로 회신 끼워넣지 않는다.

URL (이 mailbox):
<https://github.com/qkr7287/HyperCube/blob/dev/docs/agent-mailbox.md>

## 우편함 규칙

### 작성 (HyperCube가 새 요청 보낼 때)

- **새 항목은 최상단**. 위에서 아래로 시간 역순
- 헤더 형식: `## YYYY-MM-DD — 제목 (상태)`
- 상태 라벨:
  - `(대기)` — 보냈고 Agent가 아직 손 안 댐
  - `(처리 중)` — Agent 측 mailbox에 처리 시작 회신이 옴
  - `(완료 — agent <hash>)` — Agent 측에서 완료 회신. 가능하면
    HyperCube 측 후속 commit hash도 함께 (예: `완료 — agent 1a1f59f / hypercube c26c5d9`)
- Agent 측 mailbox의 회신을 확인하면 이 파일의 상태 라벨을 갱신

### Agent 측 회신은 어디에?

- 회신은 **Agent repo의 mailbox**(`hypercube-mailbox.md`)에 새 항목으로 작성
- 헤더에 원본 식별: `## YYYY-MM-DD — Re: 2026-04-14 자동 승인 흐름 전환 (완료 — <hash>)`
- HyperCube가 Agent mailbox를 읽고 이 파일의 상태 라벨을 갱신

### 종료된 항목 (축약 + archive)

- 완료 확인 후에는 **본문을 1~2줄 요약으로 축약**. 상세는 commit/PR에
  남아있으니 여기선 제목·날짜·commit hash·한 줄 결과만 유지
- 축약된 완료 항목은 파일 하단 `## Archive` 섹션으로 이동
- 파일이 100줄을 넘으면 `docs/agent-mailbox-archive-YYYYHN.md`로 분할

## 다른 세션에 전달하는 방법

Agent 작업이 필요할 때는 mailbox URL + 짧은 안내만 보낸다.

### Agent 세션에 보낼 메시지 템플릿

```
HyperCube → Agent mailbox 최상단 (대기) 항목을 처리해줘.

이 mailbox (HyperCube가 Agent에게 보내는 outbox):
https://github.com/qkr7287/HyperCube/blob/dev/docs/agent-mailbox.md

너의 회신은 Agent repo의 hypercube-mailbox에 적어줘:
qkr7287/HyperCube-agent/docs/hypercube-mailbox.md
(없으면 새로 만들어줘. 양쪽 repo가 각자 outbox를 갖는 구조)

처리 시:
1. 본문 요구사항대로 Agent 측 코드 수정 + 커밋
2. Agent repo의 hypercube-mailbox.md 최상단에 새 항목 추가:
     ## YYYY-MM-DD — Re: <원본 제목> (완료 — <agent commit hash>)
3. 회신 본문에 다음 포함:
   - 처리 커밋 hash
   - 검증 결과 (어떤 시나리오 통과/실패)
   - 추가 정보 요청이나 후속 이슈
```

### HyperCube가 Agent 회신을 받은 뒤

- Agent repo의 `hypercube-mailbox.md` 확인
- 이 파일에서 해당 항목 상태 라벨 갱신:
  `(대기)` → `(완료 — agent <hash>)` (필요시 후속 hypercube hash 추가)
- 필요한 후속 작업 (Frontend/Backend 적용) 진행

---

## 2026-04-16 — container_metrics 주기 full snapshot 추가 요청 (대기)

### 배경

`container_metrics`는 Delta Sync 방식이라 값이 변한 컨테이너만 전송됩니다.
idle 컨테이너(예: 갓 생성된 redis, 유입 없는 nginx)는 CPU/Mem이 거의
고정이라 Delta가 발사되지 않고, Backend Redis 캐시 TTL(60s)가 지나면
캐시에서 사라져 UI에 메트릭이 표시되지 않습니다.

16번 서버는 활발한 컨테이너 90개가 있어서 이 버그가 드러나지 않았고,
로컬 PC에 신규로 `test-container`(redis 유휴) 만들자 재현되었습니다.

### 요청

`containers` 리스트가 쓰는 `CONTAINERS_FULL_SNAPSHOT_INTERVAL_MS`와
동일한 패턴으로, **모든 running 컨테이너의 metrics를 일정 주기로
full snapshot 전송**해 주세요. Delta와 병행 유지.

- 권장 주기: 30~60초 (`containers`와 동일하거나 약간 길게)
- 전송 시 `type: "container_metrics"`, 기존 포맷 그대로. 개별 컨테이너
  단위로 여러 메시지 (기존 Delta와 같은 구조)
- Agent 쪽 상수명 예: `CONTAINER_METRICS_FULL_SNAPSHOT_INTERVAL_MS`

### Backend 측 대응 불필요

Redis 캐시 merge 로직이 이미 있어 full snapshot이 오면 자연스럽게
TTL 갱신 + 최신값 유지됩니다. Agent 쪽 변경만 있으면 됩니다.

### 테스트 시나리오

1. Agent 재시작 후 idle 컨테이너 1개만 있는 상태
2. 60초 이상 대기
3. Backend Redis(`server:<agent_id>:container:<cid>:metrics`) 키가
   계속 유지되는지 확인
4. Frontend UI에서 해당 컨테이너 메트릭이 끊김 없이 표시되는지 확인

---

## Archive (완료 항목 축약)

완료된 요청은 한 줄로 요약. 상세는 commit 메시지와 PR을 참조.

- **2026-04-15** — 컨테이너 lifecycle 명령 4종(`create_container`, `compose_up`, `delete_container`, `update_container`) + `command_progress` 이벤트 추가. agent `184b287` / hypercube `bf983fa`. E2E 통과 (server_16 + local).
- **2026-04-14** — Agent 자가 등록 + 자동 승인 흐름 전환. agent `beded33` / hypercube `837b23e`.
- **2026-04-14** — Agent 환경/소스 개선 (utmp parser, network netns, streaming processes/logins, periodic snapshot). agent `1a1f59f`.
- **2026-04-13** — 명령 라우팅 프로토콜 도입 (4종 명령 응답 schema 확정, `docs/PROTOCOL.md`). agent `16bb0b9` / hypercube `cf6c2c4` + `a11490d`.
