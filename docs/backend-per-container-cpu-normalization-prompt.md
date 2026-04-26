# Backend 작업 요청: container_metrics CPU 정규화 컬럼 + API 노출

선행 문서:
- 원 요청: [`agent-per-container-cpu-normalization-prompt.md`](./agent-per-container-cpu-normalization-prompt.md)
- Agent 응답: [`agent-per-container-cpu-normalization-response.md`](./agent-per-container-cpu-normalization-response.md)

## 배경

`server-2d` 대시보드와 fleet 카드의 컨테이너 CPU 게이지가 0~100%를 가정하지만, agent가 송출하던 `cpu.usage`는 Docker 표준의 **코어 합산 %** (4코어 풀 사용 = 400). Frontend가 임시로 0-100 clamp를 걸어두어 50%인데 100%로 잘리는 데이터 손실 발생 (실측 605% 케이스 있음).

Agent는 이미 정규화 필드를 송출하기 시작했다 (dev 브랜치, 배포 검증 단계). Backend는 페이로드 두 개의 새 필드를 받아 저장 + API에 노출하면 된다.

## Agent가 송출하는 실제 페이로드

```json
{
  "type": "container_metrics",
  "timestamp": "2026-04-26T01:58:57.123Z",
  "data": {
    "containerId": "abc123def456",
    "cpu": {
      "usage": 250.4,
      "cores": 4,
      "usage_pct": 62.6,
      "cores_quota": 2.5
    },
    "memory": { "usage": 268435456, "limit": 2147483648, "percent": 12.5 },
    "network": { "rx": 102400, "tx": 51200 },
    "disk": { "read": 4096, "write": 8192 },
    "network_stats": [],
    "gpu": { "...": "(있을 때만)" }
  }
}
```

| 필드 | 타입 | 의미 | null 가능 |
| --- | --- | --- | --- |
| `cpu.usage` | float | Docker stats raw (코어 합산 %, 0~N×100) | No (기존 동작) |
| `cpu.usage_pct` | float \| null | 정규화 사용률 (0~100) | **Yes** (cores_quota 결정 실패 시) |
| `cpu.cores_quota` | float \| null | 컨테이너 허용 논리 코어 수 (분수 가능) | **Yes** (inspect 실패 시) |
| `cpu.cores` | int | Docker stats `online_cpus` (참고용) | No |

> `usage=0`이어도 `cores_quota`는 채워져 옴 (null 아님). `cores_quota=null`이면 `usage_pct`도 항상 null.

## 작업 항목

### 1. 모델 / 마이그레이션

`ContainerMetricsHistory` 모델 (또는 동등 모델) 에 컬럼 3개 추가:

| 컬럼 | 타입 | nullable | 매핑 |
| --- | --- | --- | --- |
| `cpu_usage_raw` | `FloatField` | False | `data.cpu.usage` (기존 `cpu_usage` 컬럼이 raw였다면 rename + 컬럼 추가 검토) |
| `cpu_usage_pct` | `FloatField` | **True** | `data.cpu.usage_pct` |
| `cpu_cores_quota` | `FloatField` | **True** | `data.cpu.cores_quota` |

마이그레이션 시 주의: 기존 `cpu_usage` 컬럼이 이미 raw값을 저장 중이었다면 의미 변경 없음, 컬럼 추가만. 만약 frontend clamp 가정 하에 0-100으로 저장하던 컬럼이 있다면 컬럼명 분리 + 데이터 의미 명시 필요.

### 2. WS Consumer

`container_metrics` 메시지 처리 핸들러에서 새 필드 두 개 추출 및 저장. 누락 시(구버전 agent) `None` 처리.

```python
# pseudo
cpu = payload["data"]["cpu"]
ContainerMetricsHistory.objects.create(
    container_id=payload["data"]["containerId"],
    cpu_usage_raw=cpu["usage"],
    cpu_usage_pct=cpu.get("usage_pct"),
    cpu_cores_quota=cpu.get("cores_quota"),
    ...
)
```

### 3. Bucket / 집계 API

`/api/metrics/containers/buckets/` 응답에 정규화 평균 추가:

| 필드 | 산식 | 비고 |
| --- | --- | --- |
| `cpu_usage_avg` (기존) | avg(`cpu_usage_raw`) | 기존 의미 유지. AI 분석/raw 해석용 |
| `cpu_usage_pct_avg` (신규) | avg(`cpu_usage_pct`) | **null 제외하고 평균**. frontend가 차트에 직접 사용 |
| `cpu_cores_quota` (신규, 옵션) | mode 또는 last value | 컨테이너 lifetime 동안 불변이지만 시리즈 표시할 일 있으면 |

null exclusion 정책: 버킷 내 모든 샘플의 `cpu_usage_pct`가 null이면 응답에서도 `cpu_usage_pct_avg=null`로 내려보낸다 (0이 아님 — frontend "—"로 렌더 가능하게).

### 4. Frontend

- `cpu_usage_pct_avg`를 차트/카드에 그대로 사용
- 기존 0-100 clamp 코드 제거
- null인 경우 "—" 또는 "측정 불가" 표시 (0%로 그리지 말 것 — 정렬에서 silently 바닥 침)

## 검증

1. **단일 코어 한도 컨테이너**

   ```bash
   docker run --cpus=1 --rm progrium/stress --cpu 1
   ```

   기대: `cpu.usage ≈ 100`, `cores_quota = 1`, `usage_pct ≈ 100` → DB 저장 후 bucket API의 `cpu_usage_pct_avg ≈ 100`

2. **2.5코어 한도 컨테이너**

   ```bash
   docker run --cpus=2.5 --rm progrium/stress --cpu 4
   ```

   기대: `cpu.usage ≈ 250`, `cores_quota = 2.5`, `usage_pct ≈ 100`

3. **무제한 컨테이너 (호스트 8코어)**

   ```bash
   docker run --rm alpine sleep infinity
   ```

   기대: `cores_quota = 8`, `usage_pct = usage / 8`

4. **WS 직접 캡처**

   ```bash
   wscat -c ws://192.168.0.63:8000/ws/server/<agent-id>/?token=<JWT>
   ```

   매 cycle 페이로드의 `data.cpu`에 `usage_pct`, `cores_quota` 두 키 존재 확인.

## 호환성

- **구버전 agent와의 공존**: 새 필드는 둘 다 nullable. 구버전 agent가 송출하면 두 필드는 자연스럽게 `None`으로 저장됨. WS consumer는 `cpu.get("usage_pct")` 형태로 안전하게 추출.
- **롤백**: 컬럼 추가만 하므로 마이그레이션 down 가능. 단, 데이터는 사라짐.

## 우선순위

| 우선 | 항목 |
| --- | --- |
| **P0** | 모델 + 마이그레이션 + WS consumer 저장 |
| **P0** | Frontend clamp 제거 (선행 조건: bucket API에 `cpu_usage_pct_avg` 노출) |
| **P1** | bucket API `cpu_usage_pct_avg` (frontend 작업과 같이 진행) |
| **P2** | 과거 raw 데이터 백필 — `cpu_usage_pct = NULL`로 그대로 두는 것 권장 (cores_quota 정보가 과거엔 없었음) |
