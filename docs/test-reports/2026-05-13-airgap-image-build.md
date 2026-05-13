# Airgap ML Image Build + E2E Resume Report — 2026-05-13

대상: dev 서버 `192.168.0.63` / branch `dev`
실행자: Claude (Opus 4.7) via `ssh hc-dev-63` + REST API
선행 보고서: `docs/test-reports/2026-05-13-e2e-gpu-ml-workspace.md` (이미지 부재로 차단)

이번 세션의 미션: 63 호스트에 airgap PyTorch+Jupyter 이미지를 만들어 올리고, 직전에 막혔던 ML workspace E2E 를 재개.

## 1. 결과 한눈에

| 단계 | 결과 |
|------|------|
| 빌드 재료 sync (`packaging/ml-images/...`) | PASS |
| `build-pytorch-jupyter.sh` (pull base + pip install + sanity check + save tar) | **PASS** |
| `docker image inspect hypercube/ml-pytorch-jupyter:cuda12.4-airgap` | PASS |
| `docker run --rm --gpus all --entrypoint nvidia-smi <image>` | **PASS** |
| 신규 요청 생성 (user1, API) | PASS |
| Admin 승인 → `create_container` 진입 | PASS (직전과 다르게 prepare_model_assets 스킵 — 이미 cached) |
| `create_container` 실행 | **FAIL — 새 블로커**: `networkPolicy internal_only is not enforced by this agent` |
| Workspace open / 내부 nvidia-smi / read-only mount | N/A (컨테이너 못 뜸) |

## 2. 이미지 빌드 결과

### 2.1 build script
`bash packaging/ml-images/build-pytorch-jupyter.sh` 실행 (base = `pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime`).

빌드 단계:
- `Step 2/11 ... 2.5.1-cuda12.4-cudnn9-runtime: Pulling ...` (pytorch 베이스 5.5GB pull)
- `Step 7/11` JupyterLab + 보조 패키지 64건 pip install (jupyterlab 4.5.7 등)
- 빌드 직후 sanity 컨테이너 실행 결과:
  ```
  torch 2.5.1+cu124
  cuda_available True
  jupyterlab 4.5.7
  ```
- `docker save` → `/tmp/hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar`

`Successfully tagged hypercube/ml-pytorch-jupyter:cuda12.4-airgap` 확인.

### 2.2 image inspect

```
RepoTags=["hypercube/ml-pytorch-jupyter:cuda12.4-airgap"]
Id=sha256:70e4bd660439dde084624c90094da72c7da60cd1805dc4397af149753d72d146
Size=6,612,689,270 bytes (≈ 6.16 GiB)
Entrypoint=["/usr/local/bin/start-jupyter.sh"]
```

### 2.3 nvidia-smi inside container

```
$ docker run --rm --gpus all --entrypoint nvidia-smi hypercube/ml-pytorch-jupyter:cuda12.4-airgap
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.142                Driver Version: 580.142        CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
|   0  NVIDIA GeForce RTX 3060 Ti     Off |   00000000:01:00.0 Off |                  N/A |
|  0%   52C    P8             23W /  200W |    5458MiB /   8192MiB |      0%      Default |
+-----------------------------------------+------------------------+----------------------+
```

**참고**: 사용자가 원래 적은 명령 (`docker run --rm --gpus all hypercube/...:cuda12.4-airgap nvidia-smi`) 은 이미지의 `ENTRYPOINT=["start-jupyter.sh"]` 때문에 인자 `nvidia-smi` 가 entrypoint script 에 전달돼 무시되고 Jupyter 가 그대로 떴다. `--entrypoint nvidia-smi` 로 override 해야 의도대로 동작 → 런북 또는 docs 에 한 줄 추가 권장.

## 3. E2E 재개

### 3.1 신규 요청
- 식별자: `7dc0a18e-c6b8-489b-a031-13a61cf60f4b`
- requester: user1
- template: PyTorch Jupyter GPU Workspace
- target_agent: server_63_dev
- gpu_slice: RTX 3060 Ti full (exclusive), shared off
- model: Tiny Test Model v1
- custom_name: `e2e-pytorch-airgap`
- runtime: 24h

### 3.2 승인 응답
```
status=approved  phase=create_container  image=(empty in response)
```
→ 직전 시도와 차이: `prepare_model_assets` phase 가 안 보임. 이는 직전 prepare(38f306b9) 이후 agent 가 모델을 캐시했고, 백엔드 정책상 cache 가 ready 면 prepare 단계 스킵하기 때문 (`test_approval_skips_prepare_when_agent_cache_is_ready` 와 일치).

### 3.3 5초 후 상태
```
[5s] failed | create_container | networkPolicy internal_only is not enforced by this agent | cont=None
```

agent dispatcher 로그:
```
02:43:51.770 [INFO] Executing command: create_container (7dc0a18e-...)
02:43:51.782 [ERROR] Command create_container failed (7dc0a18e-...):
  networkPolicy internal_only is not enforced by this agent
```

### 3.4 재시도 #2 (이미지 검증 후 동일 조건)
- 이미지 / inspect / GPU sanity 모두 통과 (이미 캐시됨, sha256:70e4bd66...).
- agent dev 컨테이너 `Up 12 hours` — 미업데이트.
- 신규 요청 `e4a7091b-b570-4a55-b19e-0aa7c820031f` (custom_name=`e2e-retry-2`) → 승인 → 5초 만에 동일 실패.
- 결론: blocker 가 그대로며, agent 측 변경 없이는 재현 결과 동일.

## 4. 새 블로커 분석 — agent 측 networkPolicy 미지원

### 4.1 경로
- `backend/apps/containers/migrations/0007_seed_ml_workspace_templates.py:82`
  → 모든 ML 워크스페이스 템플릿이 `network_policy = "internal_only"` 로 seed.
- `backend/apps/containers/services/deployment.py:113` / `viewsets.py:732`
  → create 페이로드의 `params.networkPolicy` 에 그대로 전송.
- agent (`hypercube-agent-dev-63`) 는 이 값을 받아 "enforced by this agent 아님" 으로 reject.

### 4.2 영향
- 모든 ML workspace 카테고리 deploy 가 dev agent 에선 차단됨 (image 이슈 해소된 이후의 두 번째 단일 블로커).
- 이미지 파이프라인은 정상 (image 존재 확인 통과해 다음 검증으로 전진).

### 4.3 조치 (선택지)

권장 우선순위:

1. **(추천) agent repo 이슈 생성** — `qkr7287/HyperCube-agent` 에 "Implement networkPolicy=internal_only enforcement on create_container" 발행. 본 코드 참조: `backend/apps/containers/services/deployment.py:111-113`, `viewsets.py:730-732`, template seed `network_policy="internal_only"`.
2. **(임시 우회) 백엔드 fallback** — 환경변수 또는 setting (`HC_DEFAULT_NETWORK_POLICY`) 으로 dev 에서 `none` 또는 `host` 로 다운그레이드. 단, 이는 보안 기본값 약화 → 명시적 dev-only guard 필수.
3. **(테스트 한정 우회)** dev DB 에서 해당 템플릿의 `network_policy` 컬럼을 `none` 으로 수동 변경. 다음 마이그레이션/seed 가 덮어쓰므로 휘발적.

이번 세션에서는 어떤 우회도 적용하지 않음 — `feedback_validation_and_root_cause` ("돌려막기 말고 원인 고치기") 와 `feedback_agent_change_prompt` 정책 (agent repo 작업은 별도 트랙) 에 따라 **단계 4 의 (1) 이슈 발행** 으로 핸드오프.

## 5. 후속 검증 (지연)

이미지 + agent networkPolicy 양쪽이 정상화된 이후 재실행 대상:
- `/user/workspaces` → 새 ML 컨테이너 카드 + Jupyter open 동작
- 내부 `nvidia-smi` (이번에 host 에서 single-shot 으론 검증됨; 컨테이너 deploy 후엔 GPU mount + cgroup limit 검증)
- `/workspace/models` read-only mount: `touch /workspace/models/write-test` 가 EROFS / EACCES 로 실패해야 함
- Negative 6.1 / 6.4 의 라이브 재검증

## 6. 산출물

- 신규 이미지: `hypercube/ml-pytorch-jupyter:cuda12.4-airgap` (sha256:70e4bd66...)
- tar: `/tmp/hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar` on 63
- 빌드 스크립트/Dockerfile: `packaging/ml-images/pytorch-jupyter/...` (이번 세션엔 사용자가 추가, 그대로 PASS)

## 7. 최종 판단

**조건부 가능** — airgap 이미지 트랙(이번 미션) 은 **PASS**. 다음 단일 블로커는 코드 변경 없이 agent 측 enforcement 만 추가되면 E2E 가 단발에 끝남.

- 이미지 빌드/inspect/GPU sanity = ✅
- 백엔드 `create_container` 페이로드 송신 = ✅
- agent `create_container` 처리 = ❌ (`internal_only` 미구현)

다음 단계: **agent repo 에 networkPolicy 이슈 발행** → 적용 후 §5 재검증.
