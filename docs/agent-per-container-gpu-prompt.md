# Agent 작업 요청: 컨테이너별 GPU 사용량 메트릭 추가

## 배경

HyperCube 서버 2D 관제(`/server-2d`)에서 다음 두 가지 새로운 시각화를 만들 예정이다.

1. **스택 평균 추이 차트의 `디스크 I/O` 자리를 `GPU` 라인 차트로 교체**
   - 4개 차트 = CPU · 메모리 · 트래픽 · **GPU(신규)**
   - "어떤 스택이 GPU를 가장 많이 쓰는가"를 시간축으로 비교
2. **전체 컨테이너 패널의 정렬 기능 (GPU / MEM / CPU 우선)**
   - GPU 카드는 GPU 사용량 내림차순으로 정렬
   - 카드의 NET 자리를 GPU > 0인 컨테이너에서는 `GPU x.x%`로 대체

이 두 기능을 켜기 위해 **컨테이너 단위 GPU 메트릭**이 필요하다. 현재 Agent는 호스트 단위(systemInfo.gpu) GPU만 송출 중이다.

## 요청 사항

`hypercube-agent`가 주기적으로 송출하는 `container_metrics` 페이로드에 **`gpu` 객체 1개**를 컨테이너당 추가해 달라.

### 페이로드 형식 (확정)

기존 메트릭 페이로드 끝에 `gpu` 객체를 추가한다.

```json
{
  "type": "container_metrics",
  "payload": {
    "container_id": "abc123def456",
    "cpu": { "usage": 12.4, "cores": 4 },
    "memory": { "usage": 268435456, "limit": 2147483648, "percent": 12.5 },
    "network": { "rx": 102400, "tx": 51200 },
    "disk": { "read": 4096, "write": 8192 },
    "gpu": {
      "usage": 73.2,
      "memory_used": 1840,
      "memory_total": 24576,
      "indices": [0]
    }
  }
}
```

| 필드 | 타입 | 단위 | 의미 |
| --- | --- | --- | --- |
| `gpu.usage` | float | % (0~100) | 컨테이너의 GPU 코어 사용률. 다중 GPU 사용 시 평균. **필수** |
| `gpu.memory_used` | int | MiB | 컨테이너가 점유 중인 GPU 메모리. **필수** |
| `gpu.memory_total` | int | MiB | 접근 가능한 GPU 메모리 총량. **필수** |
| `gpu.indices` | int[] | - | 사용 중인 GPU 디바이스 인덱스 (예: `[0]`, `[0, 1]`). **필수** |

### 빈 값 정책 (확정)

- **GPU 미장착 호스트** → `gpu` 키를 페이로드에서 **생략**한다 (null/0 송출 X). 프론트가 자동으로 GPU 라인을 숨김.
- **GPU 장착 호스트인데 해당 컨테이너가 GPU를 쓰지 않음** → `gpu: { usage: 0, memory_used: 0, memory_total: <접근 가능 총량>, indices: [] }` 송출.
   - 또는 `gpu` 키를 통째로 생략해도 동일 동작 (프론트는 0으로 처리).

### 데이터 수집 방식

#### NVIDIA GPU (필수 지원)

1. **NVML 사용 권장** (`pynvml.nvmlDeviceGetComputeRunningProcesses_v3` 또는 `nvmlDeviceGetGraphicsRunningProcesses_v3`)
   - `nvmlDeviceGetUtilizationRates`는 **GPU 전체** 사용률만 줌. PID별 사용률은 NVML도 직접 제공하지 않음 → `nvidia-smi pmon -c 1 -s u` 또는 `nvidia-smi --query-compute-apps=pid,used_memory,gpu_uuid` 조합 필요.
2. **PID → 컨테이너 매핑**
   - `/proc/<pid>/cgroup` 파싱 (cgroup v1: `/docker/<full_id>`, cgroup v2: `/system.slice/docker-<full_id>.scope` 또는 kubepods)
   - 또는 `docker inspect <id>`의 `State.Pid` 역인덱스 사용
   - 한 컨테이너에서 여러 PID가 GPU를 쓰면 `usage`는 **합산**, `memory_used`도 합산
3. **사용률 계산 옵션**
   - 옵션 A (정확): `nvidia-smi pmon`의 `sm` 컬럼(% SM 사용)을 PID별 합산 후 컨테이너 단위로 누적
   - 옵션 B (근사): 호스트 GPU 사용률 × (컨테이너 VRAM / GPU 전체 VRAM) — 빠르지만 부정확
   - **옵션 A 권장**

#### 기타

- AMD GPU (rocm-smi) / Intel GPU는 후순위 — 우선 NVIDIA만 처리

### 권한

- NVML / `nvidia-smi` 호출에 root 권한 또는 `nvidia` 그룹 멤버십 필요
- systemd unit이라면 `User=root` 또는 `SupplementaryGroups=video,render` 검토
- Docker 컨테이너로 Agent 실행 시 `--gpus all` 또는 `nvidia-container-runtime` 마운트 필요

### 호스트 GPU 메트릭 (이미 송출 중인 부분 — 유지)

`systemInfo.gpu[]` 배열은 그대로 유지. 누락된 항목만 채워 주세요:

| 필드 | 단위 | 비고 |
| --- | --- | --- |
| `gpu[i].name` 또는 `model` | str | 모델명 (예: `NVIDIA RTX 4090`) |
| `gpu[i].usage` | % | 코어 사용률 |
| `gpu[i].memory_used` / `memory_total` | bytes | VRAM (MiB가 아니라 bytes — 기존 형식 유지) |
| `gpu[i].temperature` | °C | (선택) |
| `gpu[i].power_draw` | W | (선택) |

> ⚠️ 호스트 GPU의 `memory_*`는 bytes, **컨테이너별 GPU의 `memory_*`는 MiB** (페이로드 크기·가독성 기준). 단위 혼동 주의.

## 우선순위

| 우선 | 항목 |
| --- | --- |
| **P0** | 컨테이너당 `gpu.usage`, `gpu.memory_used`, `gpu.memory_total`, `gpu.indices` (NVIDIA만) |
| **P1** | GPU 미장착 / 미사용 컨테이너의 빈 값 정책 (위 정책대로) |
| **P2** | 호스트 GPU 누락 필드 보완 (name, temperature, power_draw) |
| **P3** | AMD/Intel GPU 지원 |

## 검증 방법

1. **GPU 워크로드가 실제로 도는 컨테이너 1개**에서 `nvidia-smi`로 실제 사용률 확인
2. WebSocket 메시지를 캡처해 새 `gpu` 객체가 0이 아닌 값으로 채워지는지 확인 (브라우저 DevTools → Network → WS 또는 `wscat`)
3. **GPU 미사용 컨테이너**의 페이로드에 `gpu` 키가 없거나 0으로 채워졌는지 확인
4. **여러 컨테이너가 동일 GPU를 공유**할 때 합산이 정확한지 확인 (`nvidia-smi pmon`과 비교)

### 대상 서버

| 서버 | 환경 | 기대 동작 |
| --- | --- | --- |
| `192.168.0.63` | NVIDIA GPU 장착 | 컨테이너별 `gpu` 객체 송출 |
| `192.168.0.16` | CPU only | `gpu` 키 생략 또는 모든 컨테이너 0 |

## 진행 시 알려 주세요

- 사용률 계산 방식 (옵션 A vs B)
- 예상 추가 부하 (1초 주기 NVML 호출 시 CPU/GPU 영향)
- `nvidia-smi pmon` 호출 빈도 (실시간 1초 vs 5초 평균 등)
- 기존 메트릭 송출 주기와 동일하게 1초로 가져갈 수 있는지

## 프론트 측 수신 처리 (참고용)

Agent가 위 형식으로 송출하면 프론트는 다음과 같이 매핑한다 — 필드명이 일치하면 추가 작업 없음.

```ts
// frontend/src/routes/server-2d/+page.svelte (이미 적용됨)
function metricGpu(metric: any): number {
  return Number(metric?.gpu?.usage ?? metric?.gpu_usage ?? 0);
}
```

스택 평균 추이의 GPU 라인은 `historyModel.stackMap.<stack>.gpu`로, 컨테이너 정렬은 `containersGrouped[].containers[].gpu`로 사용된다. 백엔드/`SystemMetricsHistory`/`ContainerMetricsHistory` 스키마 확장은 이 PR과 별개로 진행한다.
