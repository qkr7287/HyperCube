# Agent .env 업데이트 요청 — HyperCube 인프라 변경

작성일: 2026-05-19 (최초) / 2026-05-19 갱신 (prod 16번→63번 이전 반영)
대상: `qkr7287/HyperCube-agent` 메인테이너

## 변경 사항 한 줄 요약

1. **호스트 포트 default 5자리 재정렬** — 충돌 회피 위해 앞에 "3" prefix
2. **prod 서버 이전** — 16번 종료, 63번 한 머신에서 dev + prod 공존

## 새 엔드포인트

| 환경 | host:port | WS | API | 컨테이너 prefix |
|---|---|---|---|---|
| **dev** | 192.168.0.63:38000 (backend), :33000 (frontend) | `ws://192.168.0.63:38000` | `http://192.168.0.63:38000` | `hc-*` |
| **prod** | **192.168.0.63:37003** (nginx, all-in-one) | `ws://192.168.0.63:37003` | `http://192.168.0.63:37003` | `hcprod-*` |

### 옛 값 (전부 폐기)

- `192.168.0.16:3334` (16번 prod) — 16번 서버 종료
- `192.168.0.63:8000` (dev backend) → 38000
- `192.168.0.63:3000` (dev frontend) → 33000
- postgres :5432 / :15432 → :35432 (host only)
- redis :6379 / :16379 → :36379 (host only)

### 포트 정책

- **컨테이너 *내부* 포트는 표준 그대로** (postgres 5432, redis 6379, backend 8000, frontend 3000, nginx 7003). 바뀐 건 **호스트로 노출되는 default** 뿐.
- prod 는 nginx 단일 host port (37003) 가 frontend + API + WS + workspace proxy 다 처리. nginx 내부에서 backend:8000 으로 reverse proxy.

## 해줘야 할 일 (agent repo)

### 1. `.env` / `.env.example` / `.env.prod.example` 갱신

**prod 용**:
```env
BACKEND_URL=ws://192.168.0.63:37003
BACKEND_API_URL=http://192.168.0.63:37003
```

**dev 용** (있으면):
```env
BACKEND_URL=ws://192.168.0.63:38000
BACKEND_API_URL=http://192.168.0.63:38000
```

기존 `192.168.0.16:3334` 라인은 모두 제거.

### 2. README / 운영 문서 검색·치환

```
:5432  → :35432
:6379  → :36379
:8000  → :38000
:3000  → :33000
:7003  → :37003
:15432 → :35432  (옛 dev default)
:16379 → :36379  (옛 dev default)
:3334  → :37003  (16번 → 63번 prod)
192.168.0.16 → 192.168.0.63  (모든 운영 IP)
```

### 3. 코드 영향 없음

agent 는 이미 `BACKEND_URL` 환경변수만 보고 동작. .env / 문서만.

### 4. 운영 agent 컨테이너 재시작

**dev agent** (`hypercube-agent-dev-63` 가 dev backend 가리킬 때):
- `.env` 의 BACKEND_URL/API_URL `:8000` → `:38000`
- `docker compose -f docker-compose.dev.yml up -d`

**prod agent** (16번 prod 가리키던 것):
- `.env` 의 BACKEND_URL/API_URL → `192.168.0.63:37003`
- 적절한 compose 로 재기동

> dev / prod 두 agent 가 한 호스트에서 동시에 떠 있으면 BACKEND_URL 만 다르면 됨. 한 agent 가 양쪽 동시 reporting 은 metric 섞이므로 권장 X.

## 완료 확인

- [ ] `.env.example` 종류별 (prod / dev) 갱신
- [ ] README · quickstart 의 포트·IP 표기 갱신
- [ ] 운영 agent 컨테이너 .env 갱신 + 재기동
- [ ] 새 접속 확인:
  - dev: `ssh hc-dev-63 "docker logs hc-backend --tail 20 | grep -i agent"`
  - prod: `ssh hc-dev-63 "docker logs hcprod-backend --tail 20 | grep -i agent"`
  - 또는 admin UI fleet 카드에서 online 표시 (`http://192.168.0.63:37003/admin/agents` 또는 dev 의 `:38000/admin/agents`)

## 참조

- HyperCube `docs/handoffs/63-prod-setup.md` — prod 셋업
- HyperCube `docs/multimodal-auto-launch-handoff.md` — Phase 2 시스템 컨텍스트
- 첫 prod 배포: GitHub Actions run `26086787486` (success)
- main HEAD: `f87a2ac` (PR #24)
