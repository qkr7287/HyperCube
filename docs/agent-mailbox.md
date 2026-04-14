# Agent Mailbox

HyperCube(Backend/Frontend) ↔ `qkr7287/HyperCube-agent` 양쪽 팀이
공유하는 단일 우편함. 모든 작업 요청 / 회신을 이 한 문서에서만
주고받는다. 슬랙·이메일 등 외부 메신저는 사용해도 좋지만, 본문은
반드시 이 mailbox에 남기고 외부에는 URL만 첨부한다.

URL: <https://github.com/qkr7287/HyperCube/blob/dev/docs/agent-mailbox.md>

## 우편함 규칙

### 작성

- **새 요청은 최상단**. 위에서 아래로 시간 역순.
- 각 요청 헤더: `## YYYY-MM-DD — 제목 (상태)`
- 상태 라벨:
  - `(대기)` — HyperCube가 보냈고 Agent가 아직 손 안 댐
  - `(처리 중)` — Agent가 작업 시작
  - `(완료 — agent <hash>)` — Agent가 완료. 가능하면 hypercube 측 대응 commit hash도 함께 표기
- 누가 보낸 요청인지 명확히 구분되는 경우는 본문 첫 줄에
  `From: HyperCube` / `From: Agent` 로 명시 (대부분 HyperCube → Agent
  방향이라 생략 가능)

### 회신

- Agent 측이 작업을 마치면 같은 요청 블록 하단에
  `### 회신 (Agent, YYYY-MM-DD)` 섹션을 덧붙이고 상태 라벨을 갱신
- 추가 질문/이슈가 있으면 같은 블록 안에서 짧게 주고받기. 새 요청
  수준의 분량이 되면 별도 헤더로 분리

### 종료된 항목

- 완료 항목은 그대로 보존 (히스토리). 삭제 금지
- 너무 길어지면 분기 시점에 `docs/agent-mailbox-archive-YYYYHN.md`로
  분할 (지금은 분할 불필요)

## 다른 세션에 전달하는 방법

Agent 작업이 필요할 때는 **이 mailbox 자체**를 매개로 전달한다.
긴 prompt를 매번 복붙하지 않고 URL + 한 줄 안내만 보내면 충분.

### 1. mailbox URL 복사

```
https://github.com/qkr7287/HyperCube/blob/dev/docs/agent-mailbox.md
```

### 2. Agent 세션에 보낼 메시지 템플릿

```
HyperCube mailbox 최상단 (대기) 항목을 처리해줘.

URL: https://github.com/qkr7287/HyperCube/blob/dev/docs/agent-mailbox.md

처리 시:
1. 본문 요구사항대로 코드 수정 + 커밋
2. 같은 mailbox 파일을 PR로 수정해서 (대기) → (완료 — <agent commit hash>) 로 갱신
3. 같은 블록 하단에 `### 회신 (Agent, YYYY-MM-DD)` 섹션 추가:
   - 어떤 커밋으로 처리했는지
   - 검증 결과 (어떤 시나리오 통과/실패)
   - 추가로 필요한 정보가 있으면 질문
```

### 3. Agent 회신을 받은 뒤 HyperCube 측에서

- mailbox 갱신본을 dev 브랜치에 pull → 회신 확인
- 필요하면 후속 commit (Frontend/Backend 적용) 해시도 같은 블록에 추가
- 다음 작업이 있으면 새 요청을 mailbox 최상단에 추가

---

## 2026-04-14 — 자동 승인 흐름 전환 (대기)

### 변경 요약

HyperCube에서 운영자 수동 승인 단계를 제거하고 모든 Agent
등록을 즉시 자동 승인합니다.

- **유지**: token 기반 식별 + WS 인증 (보안 모델 동일)
- **제거**: 수동 승인 단계 (관리자가 approve 버튼 누르는 흐름)
- **결과**: Agent의 등록 → 가동 시간이 0초 (이전엔 운영자 승인 대기)

### Backend 신규 동작 (HyperCube 측 처리)

#### POST /api/agents/ (register)

응답에 즉시 token 포함, status는 `"approved"`로 반환.

요청 (변경 없음):
```json
{
  "hostname": "server_16",
  "ip_address": "192.168.0.16",
  "metadata": {}
}
```

응답 (변경 후):
```json
{
  "id": "uuid-...",
  "hostname": "server_16",
  "ip_address": "192.168.0.16",
  "status": "approved",
  "token": "agent_<secret>",
  "registered_at": "2026-04-14T...",
  "approved_at": "2026-04-14T..."
}
```

idempotency: hostname 중복 시 기존 Agent 그대로 반환 (기존 token
유지) — 변경 없음.

#### GET /api/agents/{id}/status

유지하지만 항상 status=approved 반환.
Agent 측이 polling을 완전히 제거하면 호출 안 됨.

#### POST /api/agents/{id}/manage-status

제거됩니다. 호출 시 404.

### Agent 측 변경

#### 필수: polling 루프 제거

기존 흐름:
```
1. POST /api/agents/  → status=pending, token=""
2. while status != approved:
     wait 5s; GET /api/agents/{id}/status
3. status==approved → token 수령 → WS 연결
```

새 흐름:
```
1. POST /api/agents/  → status=approved + token 즉시 수령
2. WS 연결 시작
```

→ 등록과 동시에 token 사용 가능. 폴링 단계 통째로 삭제.

#### 권장: 호환 처리 유지

이미 .env에 token 있으면 register 호출 없이 바로 WS 시도 →
401일 때만 register 재호출. 현재 동작과 동일하면 그대로 유지.

#### 선택: dead code 정리

`check_status` polling 모듈 제거. Backend는 호출 받아도 200 OK +
status=approved 반환하므로 두어도 안전하지만, 단순화 차원에서
제거 추천.

### 검증 시나리오

1. **신규 등록**: 깨끗한 호스트
   - POST /api/agents/ 1회 호출 → 응답에 token 즉시 포함 확인
   - 즉시 WS 연결 → Backend 로그에서 [accepted] 확인
   - 등록부터 데이터 송신까지 거의 0초

2. **재시작**: 기존 token으로 재실행
   - .env의 token 그대로 사용 → register 호출 없이 WS 즉시 연결

3. **token 손실 복구**: .env에서 token 지우고 재실행
   - register 재호출 → 동일 hostname이라 idempotent하게 기존
     Agent + 기존 token 반환 → WS 연결

4. **manage-status 호출**: 외부에서 호출해도 404 응답 확인
   (Agent가 호출하지 않으므로 영향 없음)

### 우선순위

| # | 작업 | 우선순위 | 비고 |
|---|------|----------|------|
| 1 | polling 루프 제거 + register 응답의 token 즉시 사용 | P1 | Agent 시작 지연 단축 |
| 2 | check_status 호출 dead code 정리 | P2 | 선택 |

### 일정/호환성

- HyperCube Backend 변경: 본 세션에서 진행 (수동 승인 API 제거,
  register가 자동 승인 + token 발급)
- Agent 측 변경 시점: 자유. Agent가 polling을 유지해도 즉시
  approved 응답 받아 정상 동작 (1회만 polling하고 끝)
- 즉, **Backend 배포가 먼저 나가도 기존 Agent에 영향 없음**

---

## 2026-04-14 — Agent 환경/소스 개선 (완료 — agent `1a1f59f`)

### 처리된 4건

1. utmp 파서 자체 구현 → users 정상 반환 (agics-ai, root 등)
2. /host/proc/1/net/dev 사용 → 호스트 net stats 정확 (rx 676 GB)
3. system_metrics streaming에 processes/logins 포함 → 좌측 패널 즉시 갱신
4. containers 60초 주기 스냅샷 → 재접속 시 즉시 full snapshot

### 함께 나간 docker-compose 변경

```yaml
services:
  agent:
    build: .
    restart: unless-stopped
    env_file: .env
    privileged: true
    pid: host
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /proc:/host/proc:ro
      - /var/run/utmp:/var/run/utmp:ro
      - /etc/hostname:/host/etc/hostname:ro
    group_add:
      - "${DOCKER_GID:-999}"
```

### HyperCube 측 대응

- `c26c5d9` Agent registry TTL refresh + adapter 정렬
- `6fdac9c` Frontend system 모달 4종을 sendCommand로 이관
- `fb07c58` ContainerDetailModal 이관 (inspect/get_logs/control)

---

## 2026-04-13 — 명령 라우팅 프로토콜 도입 (완료 — agent `16bb0b9`)

### 처리된 항목

- 4종 명령 (`system_info`, `inspect`, `get_logs`, `control`) 응답 schema 확정
- `docs/PROTOCOL.md` 작성 (HyperCube에 `docs/agent-protocol.md`로 미러링)

### HyperCube 측 대응

- `cf6c2c4` Agent on-demand command routing over WebSocket
- `a11490d` Redis cache snapshot replay on Browser reconnect
