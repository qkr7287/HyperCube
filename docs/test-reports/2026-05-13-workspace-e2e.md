# Workspace E2E Report — networkPolicy 이후 — 2026-05-13

대상: dev 서버 `192.168.0.63` / branch `dev`
실행자: Claude (Opus 4.7) via `ssh hc-dev-63` + claude-in-chrome + REST API
선행 보고서: `docs/test-reports/2026-05-13-airgap-image-verify.md`
container: `e2e-netpolicy` (`d6a7042dd62d`) / request `a32ecc79-ce8c-4cdd-ba0f-69d3fb2a8f9c`

이번 세션 미션: agent 가 `networkPolicy=internal_only` 를 구현했다는 가정 하에, ML workspace E2E 를 deploy → Jupyter open → 컨테이너 내부 / 호스트 가드까지 검증.

## 1. 결과 한눈에

| 단계 | 결과 |
|------|------|
| agent 컨테이너 재기동 (Up 7 min) | PASS — 업데이트됨 |
| 요청 생성/승인 → `deployed` (5초) | **PASS** |
| docker 네트워크 = `hc-ml-internal` (`internal=true`) | **PASS** |
| egress block (`socket.connect 1.1.1.1:443`) | **PASS** (`Network is unreachable`) |
| 컨테이너 내부 `nvidia-smi` (RTX 3060 Ti 노출) | **PASS** |
| model 마운트 표시 (`/workspace/models/tiny-test-modeltiny-test@v1`) | **PASS** |
| model 디렉토리 read-only (안쪽 `touch` 실패) | **PASS** (`Read-only file system`) |
| `/user/workspaces` 카드 표시 (status=running) | **PASS** |
| `Jupyter 열기` 클릭 → 새 탭 + ticket URL | **PASS** |
| 프록시 라우팅 (Vite dev `/workspace/*`) | **PASS** (이번 세션에서 1줄 추가) |
| backend `/workspace/.../lab` proxy → upstream | **FAIL** — `Workspace upstream fetch failed (502)` |
| Jupyter UI 로드 | **불가** (위 502 때문) |

부수 발견 1: 사용자 빠른 테스트 `touch /workspace/models/write-test` 는 모델 _parent_ (overlay-fs writable) 를 친 것이라 통과됨. 실제 모델 마운트는 RO. 직전 보고서의 "UNEXPECTED_WRITE" 라인은 false alarm.

부수 발견 2: 프록시 라우팅 누락 (Vite dev) — 본 세션에서 `frontend/vite.config.ts` 에 `/workspace` 한 줄 추가하고 frontend 재기동했음.

## 2. 상세

### 2.1 agent + 신규 요청

- `hypercube-agent-dev-63` `Up 7 minutes` (재기동 확인).
- 신규 요청 `a32ecc79-...` (custom_name `e2e-netpolicy`) → admin 승인 → **5초 만에 `status=deployed`**, `target_container=d6a7042dd62d`.

### 2.2 네트워크 정책 enforce 확인

```
$ docker inspect d6a7042dd62d --format 'network_mode={{.HostConfig.NetworkMode}}'
network_mode=hc-ml-internal

$ docker network inspect hc-ml-internal --format 'internal={{.Internal}} driver={{.Driver}} containers_count={{len .Containers}}'
internal=true driver=bridge containers_count=1

$ docker exec d6a7042dd62d python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('1.1.1.1', 443))"
EGRESS_BLOCKED OSError [Errno 101] Network is unreachable
```

→ ML workspace 가 `internal=true` 브리지에만 attach 되었고, 외부 egress 차단됨.

### 2.3 GPU passthrough (컨테이너 내부)

```
$ docker exec d6a7042dd62d nvidia-smi
NVIDIA-SMI 580.142  Driver 580.142  CUDA 13.0
0  NVIDIA GeForce RTX 3060 Ti  Off | 00000000:01:00.0 Off
0% 59C P8 26W/200W | 5458MiB/8192MiB | 0% Default
```

### 2.4 모델 마운트 read-only

`/workspace/models` 디렉토리 구조 + mount 정보:
```
drwxrwxrwx 1 root root /workspace/models             (overlay-fs writable)
└── drwxr-xr-x 2 root root tiny-test-modeltiny-test@v1
    └─ /dev/sda2 on /workspace/models/tiny-test-modeltiny-test@v1 type ext4 (ro,relatime,errors=remount-ro)
```

```
$ docker exec d6a7042dd62d touch /workspace/models/write-test
$ echo $?  → 0  (parent overlay-fs, writable)

$ docker exec d6a7042dd62d touch /workspace/models/tiny-test-modeltiny-test@v1/inner-write
touch: cannot touch '...': Read-only file system  → INNER_READ_ONLY_OK
```

→ 실제 모델 디렉토리는 RO bind-mount, 정책 의도대로 동작.
→ 단, 사용자의 "빠른 검증" 스크립트가 parent path 를 치면 false-pass(=UNEXPECTED_WRITE) 가 나옴. **runbook 의 검증 한 줄을 `touch /workspace/models/<model-dir>/write-test` 로 수정** 권장.

### 2.5 /user/workspaces UI

브라우저 (user1 로그인 상태) → `/user/workspaces` 진입 시:
- 카드 표시: name `e2e-netpolicy`, image `hypercube/ml-pytorch-jupyter:cuda12.4-airgap`, agent `server_63_dev`, template `PyTorch Jupyter GPU Workspace`, type `jupyter`, badge `running`(녹색), tags `GPU 1` `Tiny Test Model:v1` `Port 8888`, 만료 시각, `/workspace/<req-id>/` 경로, `Jupyter 열기` 버튼.

### 2.6 Jupyter open — 프록시 라우팅 누락 → 추가 → 502

- 첫 시도: `http://192.168.0.63:3000/workspace/.../lab?ticket=...` → **404 (SvelteKit catch-all)**.
- 원인: `frontend/vite.config.ts` 의 dev proxy 에 `/workspace` 항목 누락 (`/api`, `/django-admin`, `/static`, `/ws` 만 정의). SvelteKit 이 자기 라우트로 처리하고 없으니 404.
- 조치 (이번 세션):
  ```ts
  '/workspace': { target: apiTarget, changeOrigin: true, ws: true }
  ```
  `frontend/vite.config.ts:30` 에 추가, `docker restart hc-frontend-dev`.
- 두 번째 시도: 프록시는 도달, 그러나 backend 가 ticket 검증 후 upstream(Jupyter) 패치에서 **502 — "Workspace upstream fetch failed"**.

### 2.7 502 의 원인 — backend ↔ workspace 도달 불가

```
$ docker inspect d6a7042dd62d --format '{{json .NetworkSettings.Ports}}'
{"8888/tcp": null}        # ← 호스트로 publish 안 됨

DB: Container.workspace_host_port = 8888

$ docker exec hc-backend sh -c 'echo > /dev/tcp/192.168.0.63/8888 2>&1 && echo OPEN || echo FAIL'
FAIL
```

`workspace_proxy.py:105` 가 `f"{agent.ip_address}:{container.workspace_host_port}"` 로 직결하는데:
- agent 가 workspace 컨테이너를 `hc-ml-internal` (internal=true) 에만 attach.
- 그 결과 `8888/tcp` 가 호스트 publish 안 됨 (internal 정책상 외부 노출 차단).
- backend 가 `192.168.0.63:8888` 로 가지만 호스트 측 LISTEN 가 없으니 connection refused → 502.

**구조적 문제**: 한 컨테이너에 "egress 차단(internal=true)" 과 "ingress 허용(host publish 또는 proxy reachable)" 을 동시에 요구하는데, 단일 internal-only 네트워크로는 양립 불가. 옵션:

1. **(권장) workspace 컨테이너를 2개 network 에 attach**:
   - `hc-ml-internal` (`internal=true`) — egress 차단용.
   - `hc-ml-proxy` (`internal=false`) — backend 가 접근 가능. backend 컨테이너를 이 네트워크에 join.
   이 경우 `workspace_proxy.py` 는 `agent.ip:host_port` 대신 docker DNS (`<container_name>:8888`) 또는 backend↔proxy network 내부 IP 로 접속.
2. **agent 가 publish 하되 source 제약**: `--publish 127.0.0.1:<host_port>:8888` 로 loopback 만 노출 + backend 컨테이너가 host network mode 거나 socket forwarding.
3. **agent 가 자체 proxy port 운영**: agent 컨테이너가 8888 → 내부 컨테이너 8888 으로 TCP 포워딩. 단점: 부하 + 추가 컴포넌트.

권장은 (1). 구현 영역은 agent (네트워크 attach) + backend (proxy upstream URL 산정) 양쪽.

## 3. 실패/수정 내역

| # | 변경 | 위치 |
|---|------|------|
| 1 | Vite dev proxy 에 `/workspace` 라우트 추가 | `frontend/vite.config.ts` |
| - | agent 변경 | (이번 세션엔 없음, 직전 prompt 로 적용된 networkPolicy 만 검증) |

## 4. 후속 트랙

1. **agent + backend 협업 이슈**: workspace 컨테이너를 backend-reachable proxy network 에도 attach 하고, backend `workspace_proxy._fetch_upstream` 이 이 네트워크 경로로 접속하도록 변경. (예: `agent.dns_for_container(container.name) + workspace_port` 또는 docker compose level 의 alias.)
2. **runbook 정정**: `docs/runbooks/ml-image-airgap-build.md` 의 RO 검증 한 줄을 `/workspace/models/<model-dir>/` 로 수정 (false-pass 방지).
3. (option) backend 측에서 upstream 실패 시 에러 메시지에 `upstream_url` 디버그 정보 같이 노출하도록 dev 전용 로깅 강화.

## 5. 최종 판단

**조건부 가능** — 핵심 보안/격리 정책은 **모두 통과**:
- ✅ networkPolicy=internal_only 적용 (docker internal network).
- ✅ egress 차단 라이브 검증.
- ✅ GPU passthrough.
- ✅ 모델 RO bind-mount.
- ✅ UI workspace 카드 + 티켓 발행.

다음 단일 블로커:
- ❌ **backend ↔ workspace container ingress 경로 부재**. agent 가 internal-only network 만 attach 하고 host publish 도 안 해서 backend proxy 가 upstream 에 도달 못함.

이 블로커가 풀리면 (위 §2.7 옵션 1 권장), Jupyter UI 가 실제로 떠야 마지막 한 칸 (Jupyter 내부에서 `nvidia-smi` GUI 확인 + 모델 디렉토리 보임) 이 닫힘.
