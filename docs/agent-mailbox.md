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

### 종료된 항목

- 완료 항목은 보존 (히스토리). 삭제 금지. 상세는 아래 **압축 정책**에
  따라 순차적으로 요약
- 상세가 필요한 경우는 `git show <commit>` 또는 GitHub commit 페이지로
  복원 (원본은 git history에 영구 보존)
- 파일이 지나치게 길어지면 `docs/agent-mailbox-archive-YYYYHN.md`로 분할

## 압축 정책 (하이브리드)

mailbox가 무한정 길어지지 않도록 완료된 요청은 시간이 지나면 한 줄로
압축한다. Agent 측 `hypercube-mailbox.md`도 동일 정책(bfb5acf).

### 규칙

1. **최근 5개 항목은 full detail 유지** — 검증 결과, 시나리오, 질문/답변 등
2. 그 이전 완료 항목은 한 줄 요약으로 rewrite
   - 헤더(`## YYYY-MM-DD — 제목 (상태)`)는 유지
   - 본문은 `> <핵심 한 줄>. 상세: git show <hash>` 만 남긴다
   - hypercube 측 후속 commit이 있으면 함께 기재
     (예: `git show <agent hash> / hypercube <hash>`)
3. 원본 상세는 **git history에 영구 보존** — 언제든 복원 가능
4. **트리거**: 새 항목 추가로 총 6개가 되면, 같은 커밋에서 **가장 오래된
   full entry 1개**를 위 형식으로 압축
5. **예외**: 미완료/진행 중 항목(`(대기)`, `(처리 중)`)은 나이 무관
   full detail 유지

### 압축 예시

**Before**

```markdown
## 2026-04-13 — 명령 라우팅 프로토콜 도입 (완료 — agent `16bb0b9`)

### 처리된 항목
- 4종 명령 (system_info, inspect, get_logs, control) 응답 schema 확정
- docs/PROTOCOL.md 작성 (HyperCube에 docs/agent-protocol.md로 미러링)

### HyperCube 측 대응
- cf6c2c4 Agent on-demand command routing over WebSocket
- a11490d Redis cache snapshot replay on Browser reconnect
```

**After**

```markdown
## 2026-04-13 — 명령 라우팅 프로토콜 도입 (완료 — agent `16bb0b9`)

> 4종 on-demand 명령 프로토콜 확정 + PROTOCOL.md 작성.
> HyperCube 대응: cf6c2c4, a11490d. 상세: git show 16bb0b9
```

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

## 2026-04-17 — containers 메시지에 `networks` / `mounts` 필드 추가 (완료 — agent `f17b9e7`)

회신 확인: <https://github.com/qkr7287/HyperCube-agent/blob/main/docs/hypercube-mailbox.md>

### 검증 결과 (4/4 통과)

1. 필드 제공 — server_16 81/81 컨테이너가 `networks`/`mounts` 키 포함,
   server-41 17/17도 동일.
2. bridge/host/none 필터 — 두 서버 모두 leak 0.
3. volume-only mounts — 두 서버 모두 non-volume leak 0
   (예: server-41 agent 컨테이너 bind mount 제외 확인).
4. Frontend 시각 — Network 토글 ON 시 18개 torus 허브(server_16 공유
   네트워크) + 짧은 점선 라인, Volume 토글 ON 시 1개 octahedron 허브
   (`agdooturi-api_media_data`) + 긴 대시선 렌더 확인.

### HyperCube 측 후속 커밋

- `data-adapter.transformContainers` / `+page.svelte`의 Container
  매핑이 `networks`/`mounts` 필드를 Topology까지 전달하지 않던
  버그 발견 → 함께 수정.

### Agent 세션 질문에 대한 회신

> 혹시 실제 원문에 추가 제약(드라이버 필터, 이름 규칙 등)이 있으면
> 알려주시면 보완 가능합니다.

현재 시점엔 추가 제약 없음. Agent 현 구현(bridge/host/none 제외 +
type==volume)으로 충분하고, `MIN_HUB_MEMBERS=2` 정책은 Frontend
쪽에서 처리하므로 Agent는 그대로 두면 됨. 추후 드라이버별
(예: overlay/macvlan 구분) 필터가 필요해지면 별도 mailbox로 요청.

---



Frontend 3D topology가 **네트워크 허브**와 **볼륨 허브**를 추가로
렌더할 수 있도록, `containers` WS 메시지의 각 container 객체에
optional 필드 두 개를 추가해주세요. 상세 스펙은 HyperCube repo의
`docs/agent-schema-v2.md` 에 있고 아래는 핵심 요약입니다.

### 변경 전 (v1, 현재)

```json
{
  "id": "b9e8962d9acd",
  "name": "hypercube-agent-agent-1",
  "image": "hypercube-agent-agent",
  "state": "running",
  "status": "Up About an hour",
  "ports": [],
  "created": 1776397672,
  "labels": { "...": "..." }
}
```

### 변경 후 (v2)

```json
{
  "id": "b9e8962d9acd",
  "name": "hypercube-agent-agent-1",
  "image": "hypercube-agent-agent",
  "state": "running",
  "status": "Up About an hour",
  "ports": [],
  "created": 1776397672,
  "labels": { "...": "..." },

  "networks": ["hypercube-agent_default"],
  "mounts": [
    { "name": "hypercube-agent_data", "type": "volume" }
  ]
}
```

### 필드 규격

**`networks: string[]`** (optional)
- `docker inspect` 결과의 `NetworkSettings.Networks` 객체의 **키**만
  배열로.
- 기본 네트워크 `bridge` / `host` / `none` 은 Agent 측에서 제외.
  (모든 컨테이너가 기본으로 하나씩 물려 있어 허브로 만들면 노이즈.)

**`mounts: { name: string; type: 'volume' }[]`** (optional)
- `Mounts[]` 배열에서 `Type === "volume"` 인 것만.
- bind mount는 제외 (stack 허브와 거의 중복).
- 각 원소: `{ name: Mounts[i].Name, type: 'volume' }`.

### 호환성

두 필드 모두 **optional** 입니다. 필드가 없으면 Frontend는 Network /
Volume 허브를 만들지 않고 Stack 허브만 렌더하는 graceful degradation
상태로 동작합니다. 즉 Agent 배포와 Frontend 배포 순서 제약 없음
(Frontend 수신 로직은 이미 `7e4d556` 에 들어가 있음).

### 검증 시나리오

1. **필드 제공 확인** — Agent 배포 후 Backend Redis에서 확인:
   ```bash
   docker exec hc-redis redis-cli -n 1 GET "server:<id>:containers" \
     | python -c "import json,sys; print(json.load(sys.stdin)['data']['containers'][0].keys())"
   ```
   각 container 객체 키에 `networks`, `mounts` 포함.

2. **기본 네트워크 필터** — `docker run --rm alpine` 같은 단순 컨테이너의
   `networks` 배열이 빈 배열 (또는 필드 자체 생략) 이어야 함.

3. **volume-only mounts** — bind mount만 가진 컨테이너의 `mounts` 배열이
   비어 있어야 함. named volume 사용 시 해당 name만.

4. **Frontend 시각 검증** — Agent 배포 후 3D 화면 좌측 상단 토글의
   Network / Volume 체크박스 켜면:
   - 2+ 컨테이너가 공유하는 custom 네트워크에 대해 torus 허브 + 짧은 점선
   - 2+ 컨테이너가 공유하는 named volume에 대해 octahedron 허브 + 긴 대시선
   - 단일 컨테이너만 쓰는 네트워크/볼륨은 허브 X (노이즈 방지용
     `MIN_HUB_MEMBERS = 2`).

### HyperCube 측 준비 상태

- Phase 3 커밋 `7e4d556` 에서 `networks` / `mounts` 파싱 + 허브 렌더
  + 토글 UI 완료.
- Agent 배포 즉시 HyperCube 재빌드 없이 자동으로 허브가 표시됨.
- `docs/topology-rewrite.md` 의 Phase 3 섹션도 참고.

### 우선순위

| # | 작업 | 우선순위 | 비고 |
|---|------|----------|------|
| 1 | `networks` 필드 추가 (bridge/host/none 제외) | P1 | 시각 효과가 가장 명확 |
| 2 | `mounts` 필드 추가 (type=volume only) | P2 | 공유 named volume 드문 환경에선 효과 제한적 |

회신 시 검증 결과 + 처리 커밋 hash를 `hypercube-mailbox.md` 에 부탁드립니다.

---

## 2026-04-16 — container_metrics 주기 full snapshot 추가 요청 (완료 — agent `293f84f`)

회신 확인: <https://github.com/qkr7287/HyperCube-agent/blob/main/docs/hypercube-mailbox.md>
Agent `293f84f`: `CONTAINER_METRICS_FULL_SNAPSHOT_INTERVAL_MS=60_000`,
delta와 병행 유지, 재접속 시 즉시 full snapshot. mailbox `b92fd0b`.

HyperCube 측 추가 조치 (TTL 갱신 갭 방지):
- Agent snapshot 주기(60s)와 Backend Redis TTL(60s)이 동일해서 1~2초
  gap 관찰됨. `CONTAINER_METRICS_CACHE_TTL=150s`로 분리해 해결 예정.
  (별도 constant로 `REDIS_CACHE_TTL`과 분리, `_cache_to_redis`의
  container_metrics 분기에만 적용).

---

## 2026-04-15 — 컨테이너 lifecycle 명령 + progress 이벤트 (완료 — agent `184b287` / hypercube `bf983fa`)

회신 확인: <https://github.com/qkr7287/HyperCube-agent/blob/main/docs/hypercube-mailbox.md>
검증 6/6 시나리오 통과. 16번 서버 + Windows 배포 완료. PROTOCOL.md 확장됨.
Agent 질문 2건: (1) progress UI=progress bar (User 카드 내) (2) compose env=변수 치환용(현 구현 그대로 OK).
Backend 결선 `bf983fa`: approve→dispatch, command_progress/response 처리, container_id 12자 정규화 + target_container FK 링크. E2E 검증 server_16/local 모두 통과.

### 배경

HyperCube에 사용자(end-user) 페이지를 새로 도입합니다. 사용자가
"컨테이너 생성/삭제 요청 → admin 승인 → Backend가 해당 Agent에
실제 docker 작업 명령" 흐름이 됩니다. Agent 측에 4종 신규 명령과
1종 신규 비동기 이벤트가 필요합니다.

기존 4종 명령(`system_info`, `inspect`, `get_logs`, `control`)은
변경 없습니다.

### 추가 명령 4종

기존 `command` / `command_response` envelope 그대로 사용.

#### 1. `create_container` (단일 컨테이너 생성)

**params**
```json
{
  "image": "postgres:15",
  "name": "my-pg",                 // 컨테이너 이름. 중복 시 에러
  "env": { "POSTGRES_PASSWORD": "..." },
  "ports": [
    { "host": 15432, "container": 5432, "protocol": "tcp" }
  ],
  "volumes": [
    { "host": "/var/data/pg", "container": "/var/lib/postgresql/data", "mode": "rw" }
  ],
  "restart_policy": "unless-stopped",   // 선택. 기본 unless-stopped
  "pull_if_missing": true               // 선택. 기본 true
}
```

**success.data**
```json
{
  "containerId": "abc123def456...",   // 64-char or 12-char short — 기존 inspect/get_logs와 동일 형식
  "name": "my-pg",
  "image": "postgres:15",
  "state": "running"
}
```

**errors** — `"image is required"`, `"name is required"`,
`"name already exists: <n>"`, `"image pull failed: <reason>"`,
`"create failed: <reason>"`, `"start failed: <reason>"`,
Dockerode 원본 에러 등.

#### 2. `compose_up` (여러 컨테이너를 docker-compose로 한 번에 생성)

**params**
```json
{
  "projectName": "my-stack",       // docker-compose -p
  "composeYaml": "<여러 줄 yaml 문자열>",
  "env": { "TAG": "v1.2", "DB_PASSWORD": "..." },   // 선택. compose 변수 치환용
  "pull_if_missing": true
}
```

**success.data**
```json
{
  "projectName": "my-stack",
  "containers": [
    { "containerId": "abc...", "name": "my-stack-web-1", "image": "nginx:1.27", "state": "running" },
    { "containerId": "def...", "name": "my-stack-db-1",  "image": "postgres:15", "state": "running" }
  ]
}
```

**errors** — `"projectName is required"`, `"composeYaml is required"`,
`"yaml parse failed: <reason>"`, `"compose up failed: <reason>"` 등.

구현 노트: `docker compose -p <projectName> -f <tmpfile> up -d` 또는
dockerode-compose 라이브러리. 둘 다 OK. 사용자 측은 결과 schema만 보장되면 됨.

#### 3. `delete_container` (단일 삭제)

**params**
```json
{
  "containerId": "abc123",
  "force": true,        // 선택. 기본 false. running 컨테이너도 강제 삭제
  "removeVolumes": false // 선택. 기본 false
}
```

**success.data**
```json
{ "containerId": "abc123", "removed": true }
```

**errors** — `"containerId is required"`, `"container not found"`,
`"running container, set force=true to remove"` 등.

#### 4. `compose_down` (compose 그룹 통째 삭제)

**params**
```json
{
  "projectName": "my-stack",
  "removeVolumes": false,
  "removeImages": false   // 선택. 기본 false
}
```

**success.data**
```json
{ "projectName": "my-stack", "removedContainerIds": ["abc...", "def..."] }
```

**errors** — `"projectName is required"`, `"compose down failed: <reason>"`.

---

### 신규 비동기 이벤트: `command_progress`

긴 작업(특히 image pull, compose up)의 진행 상황을 사용자가 보게 하기
위해 **`create_container`/`compose_up` 두 명령에 한해** 중간 progress
이벤트를 보냅니다. **`delete_container`/`compose_down`은 일반적으로
빠르므로 progress 불필요** — 마지막 `command_response`만 보내면 됨.

#### 메시지 형식 (Agent → Backend)

```json
{
  "type": "command_progress",
  "requestId": "<원본 command의 requestId 그대로>",
  "step": "pulling_image" | "creating" | "starting" | "running_check",
  "percent": 30,                     // 0~100. 정확히 모르면 null 가능
  "message": "Pulling layer 3/5: 12.3 MB / 40.0 MB",
  "context": { "image": "postgres:15", "containerName": "my-pg" }   // 선택. UI 표시용 추가 정보
}
```

#### 발사 권장 시점

| 명령 | step 시퀀스 |
|---|---|
| `create_container` | pulling_image (image pull 중 N%) → creating (도커 create) → starting (start) → running_check (헬스 체크 시) → final command_response |
| `compose_up` | 각 서비스마다 pulling_image → creating → starting (또는 컨테이너별로 step 발사) → final command_response |

**중요**: 마지막에는 반드시 일반 `command_response` 1건 (성공/실패 결정)
보내야 함. progress event만으로 종료 X. requestId로 묶임.

#### 라우팅 (Backend 측 처리, 참고만)

Backend는 `command_progress`를 수신하면:
1. `cmd_pending:{requestId}` Redis 키에서 요청자(Browser) channel 조회
2. 해당 Browser로 직접 forward (기존 command_response 라우팅과 동일)
3. ContainerRequest DB row의 progress_message/percent 갱신 (UI 새로고침 시에도 보임)
4. global channel에도 broadcast (사용자 페이지가 자기 요청 progress 받음)

이 routing은 Backend 책임. Agent는 `command_progress` 보내기만 하면 됨.

---

### 검증 시나리오

1. **단순 create**: postgres:15, env에 POSTGRES_PASSWORD 포함
   - progress events 4~5건 (pulling 진행률 + create + start)
   - 최종 command_response success, containerId 반환
   - `inspect`로 해당 containerId 조회 시 정상 응답

2. **이름 중복 create**: 같은 name으로 두 번 → 두 번째 호출이
   `name already exists` 에러. progress event 0건, 즉시 실패 응답.

3. **compose up**: 2~3 서비스 yaml
   - 각 서비스마다 pulling/create/start progress
   - 최종 containers[] 반환
   - 모든 컨테이너 `inspect`로 검증 가능

4. **delete (running 컨테이너, force=false)**: 에러
   - `delete_container` with force=true → 정상 삭제
   - 삭제 후 `inspect` → "container not found"

5. **compose down**: removedContainerIds 리스트 반환, 각 id `inspect` → not found

6. **image pull 실패**: 존재하지 않는 image (예: `notexist:latest`)
   - progress event 1건 정도 → command_response success=false, error 메시지

### 우선순위

| # | 작업 | 우선순위 |
|---|------|----------|
| 1 | create_container + delete_container (progress 포함) | P0 |
| 2 | compose_up + compose_down (progress 포함) | P1 |
| 3 | command_progress 발사 정밀화 (정확한 percent) | P2 |

### 호환성

- 기존 4종 명령 변경 없음
- 기존 `command_response` envelope 변경 없음
- `command_progress`는 새 type. Backend가 모르면 무시되므로 Agent가 먼저 배포돼도 안전

### 참고

- HyperCube 측 진행 상황: DB 모델/Backend API/Admin UI/User UI 작업 동시 진행 중
- 회신 시 검증 결과 + 처리 커밋 hash를 hypercube-mailbox.md에 부탁드립니다.

---

## 2026-04-14 — 자동 승인 흐름 전환 (완료 — agent `beded33` / hypercube `837b23e`)

회신 확인: <https://github.com/qkr7287/HyperCube-agent/blob/main/docs/hypercube-mailbox.md>
신규 hostname `local-windows`가 자동 승인되어 WS 연결 중 (registry에 등록됨).

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

> 4종 on-demand 명령(system_info/inspect/get_logs/control) 프로토콜 확정 + PROTOCOL.md 작성.
> HyperCube 대응: cf6c2c4, a11490d. 상세: git show 16bb0b9
