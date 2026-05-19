# Workspace E2E SUCCESS Report — 2026-05-13

대상: dev 서버 `192.168.0.63` / branch `dev`
실행자: Claude (Opus 4.7) via `ssh hc-dev-63` + REST API + claude-in-chrome
선행 보고서: `docs/test-reports/2026-05-13-workspace-e2e.md` (502 블로커 잡힌 상태)
container: `e2e-netpolicy` (`d6a7042dd62d`)

이번 세션: backend 재기동 + `hc-ml-internal` 네트워크 합류 후 workspace 프록시 / Jupyter UI / 컨테이너 내부 검증 완주.

## 1. 결과 한눈에

| 단계 | 결과 |
|------|------|
| backend `up -d --force-recreate` | PASS (Up 7s, healthy) |
| `docker network connect hc-ml-internal hc-backend` | PASS (`hc-ml-internal` + `hypercube_hc-network` 둘 다 attach) |
| `manage.py test test_workspaces test_workspace_ws` | **PASS 11/11** · 7.4s (신규 `test_internal_policy_uses_container_dns_and_internal_port` 포함) |
| backend → workspace 직결 (`socket.create_connection('e2e-netpolicy', 8888)`) | **PASS** (`BACKEND_TO_WORKSPACE_OK`) |
| `/user/workspaces` Jupyter 열기 → 새 탭 + ticket URL | **PASS** |
| `/workspace/.../lab?ticket=...` → backend proxy → Jupyter UI 로드 | **PASS** (`title=JupyterLab`, file browser `models/`) |
| 티켓 consume 후 URL 정리 (`/lab` 만 남고 `?ticket=` 사라짐) | **PASS** |
| Terminal 열고 kernel/PTY WebSocket 연결 | **PASS** (`Terminal 1` 활성) |
| Jupyter terminal 내 `nvidia-smi` | **PASS** (`NVIDIA GeForce RTX 3060 Ti, 580.142, 8192 MiB`) |
| Jupyter terminal 내 `python -c "import torch ..."` | **PASS** (`torch 2.5.1+cu124 cuda True NVIDIA GeForce RTX 3060 Ti`) |
| 모델 디렉토리 안에서 `touch` 실패 (RO) | **PASS** (`Read-only file system` → `READONLY_OK`) |
| Jupyter terminal 에서 egress 차단 (`connect 1.1.1.1:443`) | **PASS** (`EGRESS_BLOCKED OSError [Errno 101] Network is unreachable`) |

## 2. 코드 / 인프라 변경 (이번 세션)

| # | 변경 | 위치 | 비고 |
|---|------|------|------|
| 1 | backend 컨테이너 `hc-ml-internal` 네트워크 합류 | `docker network connect` 실행 | 직전 보고서의 502 원인 해결. compose 영구화는 별도 작업 (아래 §5) |
| 2 | (직전 세션) Vite dev proxy `/workspace` 라우트 추가 | `frontend/vite.config.ts` | 그대로 유지 |

## 3. 상세

### 3.1 backend 재기동 + 네트워크 합류
```
$ docker compose ... up -d --force-recreate backend
 Container hc-backend  Recreated
[6s] hc-backend Up 7 seconds (healthy)

$ docker network connect hc-ml-internal hc-backend
$ docker inspect hc-backend --format '{{range $k,$v := .NetworkSettings.Networks}}{{println $k}}{{end}}'
hc-ml-internal
hypercube_hc-network
```

### 3.2 backend test
```
Ran 11 tests in 7.426s
OK
```
신규/관련 테스트:
- `test_internal_policy_uses_container_dns_and_internal_port` ok
- `test_none_policy_uses_agent_host_port` ok
- `test_open_allows_internal_policy_without_host_port` ok

이 3건이 `network_policy=internal_only` 인 컨테이너에 대해 upstream URL 을 `<container_name>:<workspace_port>` 로 산정하도록 보장.

### 3.3 backend → workspace 도달성
```
$ docker exec hc-backend python -c "import socket; socket.create_connection(('e2e-netpolicy', 8888), 5).close(); print('BACKEND_TO_WORKSPACE_OK')"
BACKEND_TO_WORKSPACE_OK
```

### 3.4 Jupyter UI
- 새 탭에서 `http://192.168.0.63:3000/workspace/a32ecc79-.../lab?ticket=...` 진입.
- `title=JupyterLab`, file browser 에 `models/` 표시, Launcher (Notebook / Console / Terminal …) 정상 로드.
- 진입 직후 URL 이 `/lab` 로 정리됨 (ticket consumed → 쿠키/세션 교환). 토큰 누출 없음.

### 3.5 Jupyter terminal 내부 명령 결과

```
# nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
NVIDIA GeForce RTX 3060 Ti, 580.142, 8192 MiB

# python -c 'import torch;print("torch", torch.__version__, "cuda", torch.cuda.is_available(), torch.cuda.get_device_name(0))'
torch 2.5.1+cu124 cuda True NVIDIA GeForce RTX 3060 Ti

# ls -la /workspace/models/
total 16
drwxrwxrwx 1 root root 4096 May 13 04:31 .
drwxrwxrwx 1 root root 4096 May 13 02:38 ..
drwxr-xr-x 2 root root 4096 May 13 04:30 tiny-test-modeltiny-test@v1

# touch /workspace/models/tiny-test-modeltiny-test@v1/jupyter-write-test 2>&1 && echo UNEXPECTED || echo READONLY_OK
touch: cannot touch '/workspace/models/tiny-test-modeltiny-test@v1/jupyter-write-test': Read-only file system
READONLY_OK

# python -c '...connect("1.1.1.1",443)...'
EGRESS_BLOCKED OSError [Errno 101] Network is unreachable
```

부가:
- 이미지에 `curl` 미설치 (`curl: No such file or directory`). 운영 영향 없음, 디버깅 편의를 위해 next 빌드에 추가 검토는 가능.

## 4. 종합 — Pass 기준 매트릭스

| 사용자 정의 PASS 조건 | 결과 |
|----------------------|------|
| `hc-ml-internal` `internal=true` | ✅ (이전 보고서 §2.2) |
| workspace 컨테이너가 외부 bridge 에 안 붙음 | ✅ (단일 `hc-ml-internal` 만 attach) |
| `/user/workspaces` Jupyter open 성공 | ✅ |
| Jupyter 내부 `nvidia-smi` 성공 | ✅ |
| `/workspace/models` write 실패 | ✅ (모델 디렉토리 RO; parent overlay 는 write-able 이지만 mount 자체는 RO bind) |
| egress `EGRESS_BLOCKED` | ✅ (Jupyter terminal 내부에서 직접 확인) |

**모두 PASS.**

## 5. Follow-up (영구화)

이번 세션은 `docker network connect` 를 즉시 적용했지만 backend 재기동 시 휘발됨. 영구화 필요:

1. **`docker-compose.dev.yml` (그리고 prod 동등 파일)** 에 backend 서비스를 `hc-ml-internal` external network 에 join.
   ```yaml
   services:
     backend:
       networks:
         - hc-network
         - hc-ml-internal
   networks:
     hc-ml-internal:
       external: true   # agent 가 생성/관리
   ```
2. compose 가 backend 컨테이너를 새로 만들 때 자동으로 두 네트워크에 attach 되도록 보장.
3. `docs/runbooks/ml-image-airgap-build.md` 의 RO 검증 한 줄을 `touch /workspace/models/<model-dir>/write-test` 로 정정 (직전 보고서 §2.4 의 false-pass 방지).

## 6. 최종 판단

**운용 가능.**

- airgap 이미지 빌드 → load → inspect → GPU sanity ✅
- ML workspace deploy (`networkPolicy=internal_only` 적용) ✅
- backend proxy ↔ workspace container 도달 ✅
- 사용자 브라우저 Jupyter open + kernel/PTY WebSocket ✅
- 컨테이너 내부 GPU + PyTorch CUDA ✅
- 모델 RO 마운트 ✅
- egress 차단 ✅

남은 작업은 §5 의 compose 영구화 + runbook 정정 두 줄뿐. 기능적/보안적 차단요소는 없음.
