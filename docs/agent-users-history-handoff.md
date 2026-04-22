# Agent 개발 세션 전달문: 로그인 히스토리 수집 (`users_history` subCommand)

아래 내용을 Agent repository의 Claude/Codex 개발 세션에 그대로 전달하세요.

---

## 작업 요청

HyperCube Agent의 `system_info` command에 **새 subCommand `users_history`** 를 추가해주세요.
이미 존재하는 `users` subCommand는 "현재 로그인되어 있는 사용자"만 반환하지만,
`users_history`는 **로그아웃한 사용자를 포함한 과거 로그인 세션 기록** 을 반환해야 합니다.

Frontend의 로그인 상세 모달에서 "누가 언제 접속했다 나갔는지" 를 표시하기 위해 필요합니다.

---

## 핵심 목표

Linux `last` / `lastlog` 명령으로 wtmp 기록을 파싱하여 JSON으로 반환.

---

## Command protocol

### Request (Frontend → Backend → Agent)

```json
{
  "type": "command",
  "requestId": "<uuid>",
  "command": "system_info",
  "params": {
    "subCommand": "users_history",
    "limit": 100
  }
}
```

- `limit` (number, optional, default 100, max 500) — 반환할 최대 세션 수. 최신순.

### Response (Agent → Backend → Frontend)

```json
{
  "type": "command_response",
  "requestId": "<uuid>",
  "success": true,
  "data": {
    "sessions": [
      {
        "user": "agics",
        "terminal": "pts/0",
        "host": "192.168.0.5",
        "startTime": "2026-04-22T08:30:00Z",
        "endTime": null,
        "durationSeconds": null,
        "active": true
      },
      {
        "user": "root",
        "terminal": "pts/1",
        "host": "192.168.0.3",
        "startTime": "2026-04-21T23:00:00Z",
        "endTime": "2026-04-22T08:30:00Z",
        "durationSeconds": 34200,
        "active": false
      },
      {
        "user": "ts",
        "terminal": "pts/2",
        "host": "192.168.0.7",
        "startTime": "2026-04-21T14:00:00Z",
        "endTime": null,
        "durationSeconds": null,
        "active": false,
        "endReason": "crash"
      }
    ],
    "totalSessions": 150,
    "truncated": true,
    "source": "wtmp"
  }
}
```

### Field spec

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sessions[].user` | string | yes | 사용자명 |
| `sessions[].terminal` | string | yes | 터미널 (`pts/0`, `tty1`, etc.). 없으면 빈 문자열 |
| `sessions[].host` | string | yes | 원격 IP/호스트. 로컬 콘솔이면 빈 문자열 |
| `sessions[].startTime` | ISO 8601 string | yes | 로그인 시각 (UTC, `Z` suffix 필수) |
| `sessions[].endTime` | ISO 8601 string \| null | yes | 로그아웃 시각. `still logged in`이면 `null` |
| `sessions[].durationSeconds` | number \| null | yes | 세션 지속 초. `still logged in`이면 `null` |
| `sessions[].active` | boolean | yes | 지금도 로그인되어 있으면 `true` |
| `sessions[].endReason` | `"logout"` \| `"crash"` \| `"shutdown"` \| `"reboot"` | no | `last` 출력의 `gone - no logout` / `down` / `crash` 분류. 기본 `logout`. 불명확하면 생략 |
| `totalSessions` | number | yes | wtmp에 기록된 전체 세션 수 (limit 전) |
| `truncated` | boolean | yes | `sessions.length < totalSessions` 이면 `true` |
| `source` | `"wtmp"` \| `"btmp"` \| `"journal"` | yes | 파싱한 원본 소스 |

**정렬**: `startTime` **내림차순** (최신 세션이 배열 맨 앞).

**제외 규칙**: wtmp의 `reboot` / `runlevel` / `shutdown` pseudo-entry는 sessions 배열에서 제외 (사용자 로그인 세션이 아니므로).

---

## 반드시 해야 할 일

### 1. collector / subCommand handler 추가

`system_info` subCommand 라우팅에 `users_history` 케이스 추가. `limit` 파라미터를 받아 기본값 100 / 상한 500으로 clamp.

### 2. 파싱 구현

**권장**: `last --time-format iso -n <limit>` 를 Node `child_process`로 실행하여 출력 파싱.

- `last -F` (full date) 도 가능하지만 iso 포맷이 파싱하기 쉽고 timezone이 명시됨
- `last` 명령이 없는 환경에서는 직접 `/var/log/wtmp`를 파싱 (`utmpx` 바이너리 포맷, Node 라이브러리 `node-utmp` 등 사용 가능)

**`last` 출력 예시**:

```
agics    pts/0        192.168.0.5      Tue Apr 22 08:30:00 2026   still logged in
agics    pts/1        192.168.0.5      Tue Apr 22 07:00:00 2026 - 08:30:00 2026  (01:30)
root     pts/0        192.168.0.3      Mon Apr 21 23:00:00 2026 - 08:30:00 2026  (09:30)
ts       pts/2        192.168.0.7      Mon Apr 21 14:00:00 2026 - gone - no logout
ts       pts/2        192.168.0.7      Sun Apr 20 10:00:00 2026 - crash  (02:15)
```

- `"still logged in"` → `endTime: null`, `active: true`, `durationSeconds: null`
- `"gone - no logout"` → `endTime: null`, `active: false`, `endReason: "crash"`
- `"crash"` / `"down"` → `endReason` 채우고 duration 계산
- 정상 종료 → duration 계산해서 초 단위로 반환

### 3. Docker compose 마운트 확인

wtmp 접근을 위해 Agent 컨테이너에 아래 마운트가 필요합니다 (`users`와 동일한 메커니즘):

```yaml
volumes:
  - /var/log/wtmp:/host/var/log/wtmp:ro
  - /etc/passwd:/host/etc/passwd:ro
```

만약 `HOST_PROC`/`HOST_VAR` 같은 패턴으로 호스트 경로를 이미 사용 중이면 그 컨벤션을 따르세요.

마운트가 없으면:

```json
{
  "type": "command_response",
  "requestId": "<uuid>",
  "success": true,
  "data": {
    "sessions": [],
    "totalSessions": 0,
    "truncated": false,
    "source": "wtmp",
    "unavailable": true,
    "reason": "wtmp not mounted"
  }
}
```

`success: true` + 빈 배열 + `unavailable: true` 로 반환 (에러가 아니라 "수집 불가" 신호). Frontend가 이걸 감지해 안내 메시지를 띄웁니다.

### 4. 에러 처리

- 마운트 없음 → 위처럼 `unavailable: true`
- 파싱 실패 → `success: false`, `error: "Failed to parse wtmp: <reason>"`
- `last` 명령 없음 → `unavailable: true`, `reason: "last command not available"`

---

## 프로토콜 문서 업데이트

Agent repo에 `docs/agent-protocol.md`와 동등한 문서가 있다면 `4.5 users_history` 섹션을 추가해주세요.
HyperCube repo에도 동일한 섹션을 PR로 추가하고 싶다면 알려주세요 (이 전달문 작성자가 같이 업데이트).

---

## 검증 방법

Agent 구현 완료 후 아래로 확인:

```bash
# Agent 쪽
docker exec <agent-container> last --time-format iso -n 20

# Frontend 쪽 (HyperCube)
# 로그인 상세 모달 열기 → "로그인 히스토리" 섹션에 테이블 표시 확인
```

---

## 참고

- 현재 HyperCube Frontend는 이 응답을 받으면 `adaptLoginHistory()`로 정규화해서
  `LoginDetailModal`의 "로그인 히스토리" 섹션에 테이블로 표시합니다.
- Agent가 아직 이 subCommand를 지원하지 않으면 Frontend는 "Agent가 지원하지 않는 명령입니다"
  안내를 띄우고 모달의 나머지 영역은 정상 동작합니다.
- 관련 PR을 열면 HyperCube side도 docs/agent-protocol.md를 함께 업데이트하겠습니다.
