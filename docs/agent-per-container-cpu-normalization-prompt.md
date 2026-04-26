# Agent 작업 요청: 컨테이너 CPU 정규화 메트릭 추가

## 배경

`HyperCube/server-2d` 대시보드와 fleet 카드 모두 컨테이너 CPU%를 0~100% 게이지/차트로 표시한다.
하지만 현재 Agent가 송출하는 `container_metrics`의 `cpu.usage`는 **Docker 표준 형식 — 모든
할당된 코어 사용량의 합산 %**이다.

```
4코어 컨테이너가 코어를 모두 풀로 쓰면 cpu.usage = 400
```

이 값을 DB에 그대로 저장하니 차트 y축이 100%를 넘어 깨진다 (실측 한 컨테이너에서 605% 관측).

Frontend에선 임시로 0~100으로 clamp 해두었지만 데이터 손실이 발생한다 (50%인데 100%로 잘림).
근원적 해결을 위해 **Agent가 정규화된 % 값과 코어 수를 둘 다 송출**하도록 요청한다.

## 요청 사항

`container_metrics` 페이로드의 `cpu` 객체를 다음 형식으로 확장한다.

### 페이로드 형식 (확정)

```json
{
  "type": "container_metrics",
  "payload": {
    "container_id": "abc123def456",
    "cpu": {
      "usage": 250.4,            // ✱ 기존 필드 — Docker stats 코어 합산 % (raw, 보존)
      "usage_pct": 62.6,         // ✱ NEW — 정규화 값 (0-100). usage / cores_quota
      "cores_quota": 4,          // ✱ NEW — 이 컨테이너에 할당된 논리 코어 수
      "cores": 4                 // 기존(있다면 유지) — Docker가 보고하는 코어 수
    },
    "memory": { ... },
    "network": { ... },
    "disk": { ... },
    "gpu": { ... }
  }
}
```

| 필드 | 타입 | 단위 | 의미 | 비고 |
| --- | --- | --- | --- | --- |
| `cpu.usage` | float | % (0~N×100) | Docker stats raw 값 (코어 합산) | **유지**. DB에 그대로 저장 |
| `cpu.usage_pct` | float | % (0~100) | 정규화 사용률 | **신규 필수** |
| `cpu.cores_quota` | float | cores | 컨테이너에 허용된 논리 코어 수 | **신규 필수**. cgroup 한도. 미설정이면 호스트 전체 코어 |

### 정규화 계산 규칙

```
cores_quota = (cgroup CPU 한도가 설정됨)
                ? cgroup_quota_us / cgroup_period_us
                : host_logical_cores

usage_pct = usage / cores_quota   # clamp 0-100 권장 (정밀 측정 오차 방지)
```

#### cgroup CPU 한도 읽는 곳 (참고)

| cgroup 버전 | 경로 |
| --- | --- |
| v1 | `/sys/fs/cgroup/cpu/docker/<id>/cpu.cfs_quota_us` ÷ `cpu.cfs_period_us` |
| v2 | `/sys/fs/cgroup/system.slice/docker-<id>.scope/cpu.max` (`max` 또는 `quota period`) |

- `quota_us = -1` 또는 `cpu.max`의 첫 토큰이 `max` → 한도 없음 → `cores_quota = host_logical_cores`
- Docker `--cpus=2.5` 옵션 사용 시 `cores_quota = 2.5` (분수 허용)

호스트 코어 수는 이미 `system_metrics.cpu.cores`(또는 `threads`)에서 보내고 있을 가능성. 동일 정보 재활용.

### 빈 값 / 예외 처리

- `cores_quota`를 결정하지 못한 경우 → `cores_quota = null`, `usage_pct = null` 송출 (절대 0이나 추정값 보내지 말 것)
- `usage`가 0이면 → `usage_pct = 0`, `cores_quota`는 그대로 채워서 송출
- 일시적으로 cgroup 정보 못 읽음 → 마지막 알려진 `cores_quota` 재사용 (또는 null)

## 우선순위

| 우선 | 항목 |
| --- | --- |
| **P0** | `cpu.usage_pct` (frontend가 즉시 채택할 필드) |
| **P0** | `cpu.cores_quota` (backend 분석/AI에서 raw 해석 시 필요) |
| **P1** | cgroup v1 + v2 둘 다 지원 |
| **P2** | `--cpus` 분수 한도 정확 처리 (소수점 한 자리 이상) |

## 검증 방법

1. **단일 코어 한도 컨테이너**:
   ```
   docker run --cpus=1 stress --cpu 1
   ```
   → `cpu.usage ≈ 100`, `cores_quota = 1`, `usage_pct ≈ 100`

2. **2.5코어 한도 컨테이너**:
   ```
   docker run --cpus=2.5 stress --cpu 4
   ```
   → `cpu.usage ≈ 250`, `cores_quota = 2.5`, `usage_pct ≈ 100`

3. **무제한 컨테이너 (호스트 8코어)**:
   ```
   docker run alpine sleep infinity     # 한도 없음
   ```
   → `cpu.usage` = 코어 합산 raw, `cores_quota = 8`, `usage_pct = usage/8`

4. WS 메시지 캡처:
   ```bash
   wscat -c ws://192.168.0.63:8000/ws/server/<agent-id>/?token=...
   ```
   매 cycle 페이로드에 `cpu.usage_pct` / `cpu.cores_quota` 두 필드가 모두 들어 있고, `usage` × `cores_quota / 100` ≈ `usage` 검산 일치.

### 대상 서버

| 서버 | 환경 | 기대 동작 |
| --- | --- | --- |
| `192.168.0.16` | Docker, 다양한 컨테이너 | 컨테이너마다 `cores_quota` 정확히 산출, `usage_pct` 0-100 |
| `192.168.0.63` | Docker + GPU | 동일. GPU 메트릭은 별도 (이미 docs/agent-per-container-gpu-prompt.md 적용 완료) |

## Backend / Frontend 연동 계획 (Agent 측 참고)

Agent가 위 페이로드를 송출하면 Backend는:
- `ContainerMetricsHistory` 모델에 `cpu_usage_raw`, `cpu_cores_quota`, `cpu_usage_pct` 세 컬럼 추가 (마이그레이션)
- WS consumer가 세 값 모두 저장
- `/api/metrics/containers/buckets/` 응답에 정규화 평균(`cpu_usage_pct_avg`) 노출
- Frontend는 `cpu_usage_pct_avg`를 차트에 그대로 사용 → clamp/정규화 로직 제거

해당 backend 작업은 이 프롬프트와 별개로 진행 중이니, Agent 측은 **페이로드 스펙만 정확히 맞춰서 송출**해 주면 됩니다.

## 진행 시 알려 주세요

- cgroup v1 / v2 자동 감지 방식 (어디서 결정?)
- `cpu.usage_pct` 계산 시 clamp 0-100 여부 (권장: clamp)
- `cores_quota`가 분수일 때 정밀도 (소수점 1~2자리면 충분)
- 무제한 컨테이너의 `cores_quota`를 호스트 전체로 잡을지, `null`로 보낼지 (권장: 호스트 전체)
- 예상 추가 부하 (cgroup 파일 매 cycle 읽기)
