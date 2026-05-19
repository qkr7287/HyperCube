# Airgap ML Image Verify Report — 2026-05-13

대상: dev 서버 `192.168.0.63`
실행자: Claude (Opus 4.7) via `ssh hc-dev-63`
선행 보고서: `docs/test-reports/2026-05-13-airgap-image-build.md`

이번 세션 미션: airgap PyTorch+Jupyter 이미지의 4단계 sanity 검증 (build → inspect → nvidia-smi → torch CUDA).

## 1. 결과 한눈에

| # | 단계 | 결과 |
|---|------|------|
| 1 | `bash packaging/ml-images/build-pytorch-jupyter.sh` | **PASS** (전 layer cache hit, sanity 컨테이너 통과, tar 재저장) |
| 2 | `docker image inspect hypercube/ml-pytorch-jupyter:cuda12.4-airgap` | **PASS** |
| 3 | `docker run --entrypoint nvidia-smi ...` | **PASS** (RTX 3060 Ti 노출) |
| 4 | `docker run --entrypoint python ... -c "import torch; ..."` | **PASS** (torch 2.5.1+cu124, CUDA True, device name OK) |

## 2. 상세

### 2.1 빌드 (cache hit)
스크립트 마지막 출력:
```
Step 11/11 : ENTRYPOINT ["/usr/local/bin/start-jupyter.sh"]
 ---> Using cache
 ---> 70e4bd660439
Successfully built 70e4bd660439
Successfully tagged hypercube/ml-pytorch-jupyter:cuda12.4-airgap
torch 2.5.1+cu124
cuda_available True
jupyterlab 4.5.7
image=[hypercube/ml-pytorch-jupyter:cuda12.4-airgap] id=sha256:70e4bd660439... size=6612689270
saved=/tmp/hypercube-ml-pytorch-jupyter-cuda12.4-airgap.tar
```

→ Step 1~11 전부 `Using cache`. 빌드 자체엔 변화 없음.

### 2.2 inspect
```
RepoTags  = ["hypercube/ml-pytorch-jupyter:cuda12.4-airgap"]
Id        = sha256:70e4bd660439dde084624c90094da72c7da60cd1805dc4397af149753d72d146
Size      = 6,612,689,270 bytes (≈ 6.16 GiB)
Entrypoint= ["/usr/local/bin/start-jupyter.sh"]
Created   = 2026-05-13T02:38:21.656298192Z
```

### 2.3 nvidia-smi (entrypoint override)
```
$ docker run --rm --gpus all --entrypoint nvidia-smi hypercube/ml-pytorch-jupyter:cuda12.4-airgap
Wed May 13 04:05:04 2026
NVIDIA-SMI 580.142  Driver Version: 580.142  CUDA Version: 13.0
0  NVIDIA GeForce RTX 3060 Ti  Off | 00000000:01:00.0 Off | N/A
0% 60C P8 26W/200W | 5458MiB/8192MiB | 0% Default
Processes: No running processes found
```

- 컨테이너 안에서 host GPU 가 정상 노출됨 (RTX 3060 Ti).
- `5458MiB / 8192MiB` 는 host 의 다른 프로세스가 차지한 메모리 (현재 컨테이너에서 사용 중 프로세스 없음).
- Driver 580.142 / CUDA 13.0 (host) 이 컨테이너의 CUDA 12.4 런타임과 호환됨 (NVIDIA 컨테이너 toolkit forward-compat).

### 2.4 PyTorch CUDA
```
$ docker run --rm --gpus all --entrypoint python <image> -c "import torch; ..."
2.5.1+cu124
True
NVIDIA GeForce RTX 3060 Ti
```

- `torch.__version__` = `2.5.1+cu124`
- `torch.cuda.is_available()` = `True`
- `torch.cuda.get_device_name(0)` = `NVIDIA GeForce RTX 3060 Ti`

→ PyTorch 가 컨테이너 내에서 CUDA 가속을 정상 인식.

### 2.5 직전 보고서의 entrypoint 주의사항 확인
- 원본 명령 (`docker run ... <image> nvidia-smi`) 은 entrypoint(`start-jupyter.sh`) 가 인자를 소비해 nvidia-smi 가 실행되지 않고 Jupyter 가 떴음 — 직전 보고서(`docs/test-reports/2026-05-13-airgap-image-build.md §2.3`) 에 기록.
- `--entrypoint nvidia-smi` / `--entrypoint python` override 로 정상 동작 확인 (이번 세션).
- 권장: `docs/runbooks/ml-image-airgap-build.md` 의 검증 단계에 `--entrypoint` override 한 줄 추가.

## 3. 결론

이미지 트랙 자체는 **운용 가능 상태**:
- 빌드 산출물 안정 (sha256 / size 동일).
- 컨테이너 안 GPU passthrough OK.
- PyTorch + CUDA 12.4 OK.
- JupyterLab 4.5.7 entrypoint OK.

다음 단계는 직전 보고서의 단일 블로커 — **agent 측 `networkPolicy=internal_only` enforcement 미구현** 이 풀려야 E2E 가 `deployed` 까지 도달함. 이미지 트랙은 더 검증할 항목 없음.
