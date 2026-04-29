---
name: hc-api-sync
description: Use when modifying backend/apps/containers/**, backend/apps/agents/**, or backend/apps/common/consumers.py to keep docs/api.md, docs/agent-protocol.md, docs/agent-payload-contract.md in sync with code. Trigger on REST endpoint additions, WS message type changes, or Agent command updates.
---

# HC API Sync Skill

HyperCube backend의 API/WS/Agent 코드 변경 시 docs를 코드와 일치시키는 절차.

## When to invoke

- REST endpoint 추가/변경/삭제 (`backend/apps/containers/viewsets.py`, `backend/apps/agents/viewsets.py`)
- WebSocket message type 추가 (`backend/apps/common/consumers.py`)
- Agent command 추가 (4종: `get_logs`, `inspect`, `control`, `system_info`)
- Agent payload schema 변경

## 매핑 (코드 ↔ docs)

| 변경된 코드 | 동기화 대상 docs |
|-------------|----------------|
| `backend/apps/containers/viewsets.py`, `urls.py`, `serializers.py` | `docs/api.md` |
| `backend/apps/agents/viewsets.py`, `urls.py`, `serializers.py` | `docs/api.md` |
| `backend/apps/common/consumers.py` (WS message) | `docs/agent-protocol.md`, `docs/agent-payload-contract.md` |
| Agent command_router 4종 추가/변경 | `docs/agent-protocol.md` |
| Agent → Backend payload 구조 변경 | `docs/agent-payload-contract.md` |

## Steps

1. **변경된 코드 read**: 수정한 viewsets / consumers 의 실제 endpoint path, method, response schema 추출
2. **대상 docs open**: 위 매핑 표 따라 해당 .md 파일 read
3. **Update**:
   - REST: endpoint path, method, query params, response JSON 구조
   - WS: message `type` 종류, payload schema, requestId 라우팅
   - Agent: command 명령 + params + response 구조
4. **frontmatter 갱신**: 해당 doc에 frontmatter가 있다면 `last-synced-commit`을 `git rev-parse --short HEAD` 결과로 교체
5. **Verify** (있는 경우): frontmatter `verify` 명령 실행 후 통과 확인

## 주의

- `docs/api.md`, `docs/agent-protocol.md`, `docs/agent-payload-contract.md`는 현재 frontmatter 없음. 점진 도입 — 이번 세션에 손대지 않아도 됨
- 하지만 코드↔doc drift는 즉시 잡아야 함 (frontmatter 없어도)
- WS 메시지 type 추가만 하고 docs 안 고치는 상황이 가장 흔함 — 특히 주의

## Reference

- 현재 노출 중인 REST endpoint: `GET /api/containers/`, `/api/my-containers/{id}/current-metrics`, `/api/my-containers/{id}/metrics-history`, `POST /api/containers/requests/approve`
- WS path: `/ws/server/{server_id}/`, `/ws/global/`
- Agent command 4종: `get_logs`, `inspect`, `control`, `system_info`
