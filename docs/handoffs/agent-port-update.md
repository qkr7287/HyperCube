# Agent .env 업데이트 요청 — HyperCube 호스트 포트 변경

작성일: 2026-05-19
대상: `qkr7287/HyperCube-agent` 메인테이너

## 무엇을 바꾸나

HyperCube 백엔드를 띄우는 모든 곳의 **호스트(외부) 포트 default 값**이 바뀝니다.
기본 포트(5432 / 6379 / 8000 / 3000 / 7003) 가 너무 흔해서 다른 서비스랑 자주
충돌해서, 앞에 `3` 을 붙인 5자리 포트로 통일했습니다.

| 컴포넌트 | 이전 host 포트 (default) | 새 host 포트 (default) | 컨테이너 안 포트 |
|---|---|---|---|
| postgres | 5432 / 15432(dev) | **35432** | 5432 (unchanged) |
| redis | 6379 / 16379(dev) | **36379** | 6379 (unchanged) |
| backend (dev) | 8000 | **38000** | 8000 (unchanged) |
| frontend dev | 3000 | **33000** | 3000 (unchanged) |
| prod nginx | 7003 | **37003** | 7003 (unchanged) |

**중요**: 컨테이너 *내부* 포트는 그대로입니다. 바뀐 건 **호스트에서 노출되는
값(default)** 뿐. agent 가 backend 에 연결할 때 사용하는 URL 의 포트 부분만
영향받습니다.

## 16번 prod 서버는?

여전히 `HC_PORT=3334` 로 override 중이라 **외부 URL `http://192.168.0.16:3334`
는 그대로** 입니다. 새 default 37003 은 새로 띄우는 호스트의 시작값일 뿐.

## 63번 dev 서버는?

곧 docker compose 재기동되면서 **backend 호스트 포트가 `:8000` → `:38000`**,
frontend 가 `:3000` → `:33000` 으로 바뀝니다. **agent 의 BACKEND_URL 도 같이
업데이트 필요**.

## 해줘야 할 일 (agent repo)

### 1. `.env.example` 갱신

현재:
```env
BACKEND_URL=ws://192.168.0.16:3334
BACKEND_API_URL=http://192.168.0.16:3334
```

dev 용 example 도 있으면 (예: `.env.dev.example`) 그쪽 포트도 같이 정리:
```env
BACKEND_URL=ws://192.168.0.63:38000
BACKEND_API_URL=http://192.168.0.63:38000
```

prod 용은 16번 서버가 여전히 3334 override 라 변경 불필요. 만약 새 prod 서버를
세팅할 거라면 default 37003 도 보여주는 게 좋음.

### 2. 문서 (README / quickstart) 의 포트 언급 검색·치환

```
:5432  → :35432
:6379  → :36379
:8000  → :38000
:3000  → :33000
:7003  → :37003
:15432 → :35432  (옛 dev default)
:16379 → :36379  (옛 dev default)
```

3334 / 192.168.0.16:3334 는 그대로 (운영 서버 override).

### 3. 코드 영향 없음

agent 는 이미 `BACKEND_URL` 환경변수만 보고 동작하니 코드 변경은 필요 없습니다.
.env / 문서만 갱신.

### 4. 실 dev 환경 (63번) agent 가 떠있다면

새 backend 가 38000 으로 올라오면 기존 agent 가 8000 에 붙어있어서 끊깁니다.
- 63번에 떠있는 `hypercube-agent-dev-63` 컨테이너의 `.env` 에서
  `BACKEND_URL` / `BACKEND_API_URL` 의 `:8000` → `:38000` 으로 갱신
- `docker compose -f docker-compose.dev.yml up -d` 로 재기동

## 완료 확인

- [ ] `.env.example` (모든 env example 변형 포함) port 갱신
- [ ] README · 운영 문서의 포트 표기 갱신
- [ ] dev 환경의 실 agent .env 갱신 + 재기동
- [ ] 갱신 후 agent 로그에서 `Connected to server <agent_uuid>` 확인

문의: HyperCube 메인 PR `8cd2d8b` ~ 후속 commit. 자세한 컨텍스트는
`docs/multimodal-auto-launch-handoff.md` + `progress.md` 메모리.
