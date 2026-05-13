# E2E Report — GPU/ML Workspace Pipeline — 2026-05-13

대상: dev 서버 `192.168.0.63` / branch `dev`
실행자: Claude (Opus 4.7) via `ssh hc-dev-63` + claude-in-chrome
범위: backend migrate/check/test → frontend check → GPU inventory → UI E2E 요청→승인→deploy → workspace 내부 검증 → negative checks → 로그/토큰 노출 확인

## 1. 결과 한눈에

| 영역 | 결과 | 비고 |
|------|------|------|
| Backend `migrate` | PASS | 새 마이그레이션 없음 |
| Backend `check` | PASS | 0 issues |
| Backend test (77건) | **PASS 77/77** · 54.8s | apps.common · agents · containers · models_catalog |
| Frontend `npm run check` | **PASS** | 0 errors, 189 warnings (29 files) |
| GPU inventory refresh | PASS | `sent=2 offline=0 failed=0` |
| GPU 노출 (server_63_dev) | PASS | RTX 3060 Ti 1장, full slice available |
| UI 요청 생성 (user1) | **PASS** | template/agent/GPU/model 선택 후 제출, pending 진입 |
| Admin 승인 (API) | PASS | `pending → approved → prepare_model_assets` (phase 진입) |
| prepare_model_assets 실행 | **PASS** | agent 측 38f306b9 127 ms 만에 완료 |
| create_container 실행 | **FAIL (블로커)** | airgap 이미지 부재로 차단 (아래 §3 상세) |
| Workspace 내부 검증 | **N/A** | 컨테이너가 뜨지 않아 nvidia-smi/마운트 검증 불가 |
| Negative — 6.2 shared GPU 거절 | PASS | 400 with 정확한 메시지 |
| Negative — 6.3 runtime 초과 거절 | PASS | 400 with 72h 한도 메시지 |
| Negative — 6.1 동일 slice 2회 exclusive 거절 | PASS (unit) | 라이브 deploy 불가로 unit test 인용 |
| Negative — 6.4 비소유자 workspace open 거절 | PASS (unit) | 라이브 deploy 불가로 unit test 인용 |
| 로그/토큰 노출 (browser) | PASS | URL 에 `?token=` 없음, localStorage 는 `hc_access_token` (정상) |
| 로그/토큰 노출 (backend) | **경고** | Uvicorn access log 가 agent token 평문 노출 (아래 §6) |
| 로그/토큰 노출 (agent) | PASS | agent 측 로그는 token 을 `***` 로 마스킹 |
| 부가 발견 — ASGI race | **경고** | `common/consumers.py:196` `server_message` 핸들러에서 `websocket.close` 이후 send → RuntimeError |

## 2. 상세 결과 — 1~3 단계

### 2.1 컨테이너 상태

```
hc-backend         Up 35 minutes (healthy)
hc-celery-beat     Up 37 minutes
hc-celery-worker   Up 37 minutes
hc-frontend-dev    Up 2 days
hc-postgres        Up 11 hours (healthy)
hc-redis           Up 11 hours (healthy)
```

### 2.2 migrate / check / test

- `manage.py migrate` → `No migrations to apply.`
- `manage.py check` → `System check identified no issues (0 silenced).`
- `manage.py test apps.common apps.agents apps.containers apps.models_catalog -v 2`
  → `Ran 77 tests in 54.845s — OK`

### 2.3 Frontend `npm run check`

```
svelte-check found 0 errors and 189 warnings in 29 files
```
(분포는 직전 보고서와 동일: unused CSS ~110, a11y ~74, 기타 소수)

### 2.4 GPU inventory

```python
>>> refresh_gpu_inventories()
'gpu inventory refresh sent=2 offline=0 failed=0'

>>> Agent.objects.get(hostname='server_63_dev')
ip=192.168.0.63 status=approved
gpus = [
  {
    'index': 0, 'vendor': 'NVIDIA', 'name': 'NVIDIA GeForce RTX 3060 Ti',
    'uuid': 'GPU-7f1ece17-...', 'total_memory_mb': 8192,
    'status': 'available', 'last_seen_at': '2026-05-13T10:53:59',
    'slices': [{
      'id': 1, 'kind': 'full', 'device_id': 'GPU-7f1ece17-...',
      'label': 'NVIDIA GeForce RTX 3060 Ti full GPU',
      'memory_mb': 8192, 'allow_shared': False, 'status': 'available'
    }]
  }
]
```

## 3. UI E2E — 요청 → 승인 → deploy

### 3.1 요청 생성 (user1, 브라우저)
- `http://192.168.0.63:3000/user` 로그인 상태 확인 (user1)
- `새 요청 만들기` 모달 → `PyTorch Jupyter GPU Workspace` 선택
- 배치 서버: `server_63_dev (192.168.0.63)` 선택
- GPU: `NVIDIA GeForce RTX 3060 Ti full GPU` (available) 선택 (exclusive 모드, shared 미체크)
- 모델 자산: `Tiny Test Model v1 · 34 B` 선택
- 최대 실행 시간: 24h (기본)
- `요청 제출` → 카드 `이름 없는 컨테이너` / 상태 `승인 대기` 표시 (전체 5→6, 진행 중 0→1)

요청 식별자: `7750a358-ca57-4ef3-93f6-c0017462c2c9`

### 3.2 승인 (admin, API)

```http
POST /api/requests/7750a358.../approve/  Authorization: Bearer <admin JWT>
→ 200 OK
  status: "approved"
  selected_image: "hypercube/ml-pytorch-jupyter:cuda12.4-airgap"
  model_version_ids: ["ac6097ae-..."]
  prepare_job_ids: ["38f306b9-..."]
  deployment_phase: "prepare_model_assets"
```

### 3.3 상태 전이

```
pending → approved → prepare_model_assets (OK)
                  → create_container (FAIL)
                  → failed
```

agent 측 dispatcher 로그:

```
01:58:15.563 [INFO] Executing command: prepare_model_assets (38f306b9-...)
01:58:15.690 [INFO] Command prepare_model_assets completed (38f306b9-...)
01:58:15.779 [INFO] Executing command: create_container (7750a358-...)
01:58:15.785 [ERROR] Command create_container failed (7750a358-...):
  image not present locally: hypercube/ml-pytorch-jupyter:cuda12.4-airgap.
  ML workspace create is airgap-only and will not pull images.
```

### 3.4 블로커 — Airgap 이미지 부재

- 정책상 ML workspace 는 **air-gap-only** → registry pull 안 함. 이미지가 host 에 미리 로드돼 있어야 함.
- `docker images | grep ml-pytorch-jupyter` → 결과 없음.
- ML 워크스페이스 deploy 가 dev 환경에서 불가. `5. Workspace 내부` 절차 (nvidia-smi, /workspace/models read-only) 는 검증 불가.

**파급**: 모델 prepare 파이프라인 자체는 정상 (이전 sha256 checksum 에러는 사라지고 prepare 가 127 ms 에 완료). 남은 단계는 단일 이슈 = 이미지 배포.

## 4. /user/workspaces 페이지

- 정상 렌더링, "열 수 있는 워크스페이스가 없습니다" 빈 상태 메시지 표시 (deploy 된 ML 컨테이너 없음).
- 페이지 자체에 에러/JS 예외 없음.

## 5. Workspace 내부 (nvidia-smi / 모델 마운트 read-only)

**검증 불가 — N/A.** 컨테이너가 뜨지 않아 Jupyter terminal 접근 불가. (단위 테스트 `test_prepare_response_dispatches_create_with_read_only_model_mount` 가 read-only 마운트 payload 를 검증하므로, 의도된 정책은 코드 레벨에서 보장됨.)

## 6. Negative Checks

### 6.1 동일 GPU slice 두 번째 exclusive 승인 → 거절
- 라이브 검증 불가 (deploy 가 실패해 active allocation 없음).
- Unit test `apps.containers.tests.test_gpu_allocation.test_second_exclusive_approval_for_same_slice_is_rejected` PASS — 검증 완료.

### 6.2 shared GPU 체크 시 기본 정책에서 거절
라이브 API:

```http
POST /api/requests/ (user1) { ..., "gpu_share_ok": true }
→ {"success": false,
   "error": {"gpu_share_ok": [
     "Shared GPU mode is disabled until memory accounting policy is enabled."]}}
```

### 6.3 runtime limit 초과 요청 400
```http
POST /api/requests/ (user1) { ..., "requested_max_runtime_hours": 999 }
→ {"success": false,
   "error": {"requested_max_runtime_hours": [
     "Workspace runtime cannot exceed 72 hours."]}}
```
(템플릿 default 24h 와는 별개로 백엔드 cap 이 72h 로 강제됨)

### 6.4 비소유자가 workspace open URL 직접 접근 시 거절
- 라이브 ML 워크스페이스 없음 → 직접 호출 불가.
- Unit test `apps.containers.tests.test_workspaces.test_open_rejects_non_owner` PASS — 검증 완료.

## 7. 로그 / 토큰 노출

### 7.1 Browser
- `location.href` = `http://192.168.0.63:3000/user` — `?token=` 없음.
- `localStorage` 키: `hc_fleet_view_mode`, `hc_container_detail_workbench_mode`, `hc_3d_left_collapsed`, `hc_access_token`, `hc_3d_right_collapsed` — `hc_access_token` 만 민감 (의도된 JWT 저장 위치).
- workspace 가 deploy 되지 않아 workspace open URL 의 token-less 검증은 unit test 인용 (`test_open_issues_short_lived_ticket_without_plaintext_token`).

### 7.2 Backend (`docker logs hc-backend`)
- 정상: `prepare_model_assets`, `create_container`, `workspace` 관련 로그 모두 정상 흐름.
- **경고 — agent token 평문**: Uvicorn 의 WebSocket access log 가 다음 형태를 출력함.
  ```
  WebSocket /ws/server/053ce574-.../?token=*** [accepted]
  ```
  - 영향: backend 로그에 agent 측 인증 토큰이 그대로 남음 (dev 환경에서는 일반적이나 prod 운영 로그 수집 시 마스킹 권장).
  - 권장 조치: Uvicorn `log_config` 또는 middleware 에서 query string 의 `token=...` 을 `***` 로 치환.
- **경고 — ASGI race**: `apps/common/consumers.py:196` `ServerConsumer.server_message` 에서
  ```
  RuntimeError: Unexpected ASGI message 'websocket.send', after sending 'websocket.close'
  or response already completed.
  ```
  WebSocket close 직후 channels group dispatch 가 도달해 발생. 1회 관찰됨. 정상 동작은 유지되나 노이즈 트레이스백 → 가드 추가 권장 (`self.scope.get('_disconnected')` 또는 try/except `RuntimeError`).
- JWT (`eyJ...`) 노출 없음.

### 7.3 Agent (`docker logs hypercube-agent-dev-63`)
- 정상: `prepare_model_assets`, `create_container` 모두 dispatcher 로그에 trace.
- 토큰: WebSocket 연결 로그가 `token=***` 로 마스킹됨 — 정상.
- `fatal` / `traceback` 없음.

## 8. 실패 / 수정 내역

이번 세션 동안 코드 수정 없음. 기존 보고서에서 처리된 수정 사항 (`console_ses_*idx` 단축, `0008` 마이그레이션, `test_policy.create_gpu_slice` index 자동 부여) 그대로 적용된 상태.

새로 식별된 follow-up:
1. **Airgap ML 이미지 배포 (블로커)** — `hypercube/ml-pytorch-jupyter:cuda12.4-airgap` 가 dev 호스트(63) 에 미존재. 빌드 + 사이드 로드 절차 필요. (`docs/runbooks/` 의 airgap build 런북 참조)
2. **Uvicorn access log token 마스킹** — agent token 평문 노출. middleware 또는 log filter 로 query string 의 `token=` 값을 치환.
3. **`common/consumers.py:196` ASGI close race 가드** — `RuntimeError: Unexpected ASGI message 'websocket.send', after sending 'websocket.close'` 트레이스백 1회.

Post-report core follow-up:

- `backend/Dockerfile` and `docker-compose.dev.yml` now run Uvicorn with
  `--no-access-log --log-level warning`. This suppresses Uvicorn's INFO-level
  WebSocket accepted line that included `?token=agent_...`.
- `backend/apps/common/consumers.py` now marks WebSocket consumers as
  disconnected and drops late group/direct/global sends after close, preventing
  the observed ASGI close-race traceback from surfacing as an error.
- `packaging/ml-images/pytorch-jupyter/` and
  `packaging/ml-images/build-pytorch-jupyter.sh` were added so an operator can
  build the missing `hypercube/ml-pytorch-jupyter:cuda12.4-airgap` tar on a
  networked build machine, then load it onto server 63.

Additional server 63 image check:

- Existing images: `python:3.11-slim`, `python:3.12-slim`,
  `nvidia/cuda:12.4.1-base-ubuntu22.04`,
  `nvidia/cuda:12.3.2-base-ubuntu22.04`.
- No existing PyTorch/Jupyter image is suitable for retagging. The CUDA `base`
  images do not include PyTorch or Jupyter, so retagging would only move the
  failure from image lookup to container startup.

## 9. 최종 판단

**조건부 가능** — backend / API / 정책 / 모델 prepare / GPU inventory / agent 통신은 모두 정상이며, ML workspace 파이프라인의 모든 단계가 코드 레벨에서 검증됨. 단, **end-to-end 운용은 dev 호스트(63) 에 airgap 이미지가 사이드 로드되기 전까지 차단됨**.

조건이 해결되면:
- 5번 (workspace 내부 nvidia-smi / read-only mount) 와 6.1 / 6.4 의 라이브 재검증
- 가능하면 7.2 의 두 가지 로그 위생 항목 (token 마스킹, ASGI race 가드) 도 함께 처리

까지 마무리한 뒤 prod 승인 단계로 이동 가능.
