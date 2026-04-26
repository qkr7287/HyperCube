# Agent Payload Contract

HyperCube Agent → Backend WebSocket payload 스펙. Agent / Backend / Frontend
세 layer 가 같은 metric 을 다르게 해석하지 않도록 한 곳에서 정의한다.

## 원칙

1. **Agent 는 raw 만 보낸다.** 관찰값 (bytes, °C, count) 이 1차. 파생값 (%, rate) 은
   raw 와 함께 보낸다 — backend 가 cross-check / 재계산 가능하도록.
2. **Linux 메모리는 MemAvailable 사용.** `(total - free) / total` 은 buffer/cache 를
   used 로 카운트하므로 금지. `(total - available) / total` 만 정확.
3. **누적 카운터는 그대로.** `network.rx`, `network.tx`, `disk.read`, `disk.write`
   는 boot 이후 누적 bytes. Backend 가 bucket 간 delta 로 rate 계산.
4. **새 metric 추가 = 이 문서 먼저 갱신.** 그 다음 backend `payload_map.py`
   / migration / frontend mapping. 코드 보다 contract 가 source of truth.
5. **하위 호환.** 새 필드는 optional / nullable. 기존 필드 의미 변경은 버전 bump
   + 명시적 migration plan 필요.

## WebSocket message envelope

```jsonc
{
  "type": "system_metrics" | "container_metrics" | "command_response" | ...,
  "timestamp": "2026-04-27T00:07:23.614Z",   // ISO8601 UTC
  "data": { ... }                              // type 별 payload
}
```

## type: system_metrics

서버 호스트 단위 메트릭. Agent 가 5~15 초마다 push.

```jsonc
{
  "type": "system_metrics",
  "timestamp": "2026-04-27T00:07:23.614Z",
  "data": {
    "hostname": "server_16_dev",
    "os": "Linux 6.8.0-101-generic",
    "uptime": 4541677.02,                     // seconds

    "cpu": {
      "model": "Intel Core i5-10400",
      "cores": 6,                              // physical cores
      "threads": 12,                           // logical cores (hyperthread 포함)
      "sockets": 1,
      "isHybrid": false,
      "performanceCores": 6,
      "efficiencyCores": 0,
      "usage": 70.8,                           // 0-100, 모든 thread 평균
      "perCore": [100, 100, ...],              // length = threads
      "loadAvg1m": 8.84                        // optional, Linux 만
    },

    "memory": {
      "total": 41691742208,                    // bytes
      "free": 654454784,                       // bytes (MemFree)
      "available": 22271770624,                // bytes (MemAvailable) — REQUIRED on Linux
      "used": 19419971584,                     // total - available (NOT total - free)
      "usage": 46.6                            // (total - available) / total * 100
    },

    "disk": {
      "total": 490577010688,                   // bytes (root partition)
      "free": 84922978304,
      "used": 380658814976,
      "usage": 81.8                            // used / total * 100
    },

    "gpu": [                                    // 배열. GPU 없으면 [] 또는 생략.
      {
        "index": 0,
        "vendor": "NVIDIA",
        "model": "NVIDIA GeForce RTX 3060 Ti",
        "usage": 0,                            // 0-100
        "memoryTotal": 8589934592,             // bytes
        "memoryUsed": 6910115840,              // bytes
        "memoryPercent": 80.4,                 // (used/total)*100, optional
        "temperature": 61                      // °C, optional
      }
    ],

    "network": {
      "interfaces": ["enp1s0"],
      "rx": 535472170965,                      // 누적 수신 bytes since boot
      "tx": 123826608774,                      // 누적 송신 bytes
      "connections": 112                       // optional, 활성 connection 수
    },

    "processes": {
      "total": 866,
      "running": 3                             // R 상태만
    },

    "logins": {
      "active": 2,                             // 현재 세션
      "total": 2                               // optional, accumulated
    },

    "docker": {
      "version": "26.1.4",
      "containers": 88,
      "images": 723
    }
  }
}
```

### 메모리 계산 (가장 흔한 버그)

Linux 에서 reclaimable buffer/cache 를 used 로 카운트하면 90%+ 로 항상 잘못 보인다.
정확한 방식:

| 필드 | 출처 (`/proc/meminfo`) | 의미 |
|---|---|---|
| `total` | `MemTotal` | 전체 RAM |
| `free` | `MemFree` | 어디에도 안 쓰이는 바이트 (작음, 의미 없음) |
| `available` | `MemAvailable` | 새 프로그램이 쓸 수 있는 추정치 (이게 진짜 "여유") |
| `used` | `total - available` | 실질적으로 묶여있는 메모리 |
| `usage` | `(total - available) / total * 100` | 사용률 % |

라이브러리:
- Go: `gopsutil/v3/mem` `VirtualMemory()` → `Available` 필드
- Node: `/proc/meminfo` 직접 파싱 (`os.freemem()` 은 MemFree 라서 부정확)
- Python: `psutil.virtual_memory().available`

Windows / macOS 는 `available` 의미가 다르지만 OS 가 정확한 값 제공 → 그대로 사용.

## type: container_metrics

Docker container 단위. Agent 가 stats stream 으로 모음.

```jsonc
{
  "type": "container_metrics",
  "timestamp": "2026-04-27T00:07:23.614Z",
  "data": {
    "containerId": "abc123def456",
    "name": "/myapp-web-1",
    "image": "myapp:latest",
    "state": "running",

    "cpu": {
      "usage": 605.2,                          // raw 코어 합산 % (Docker stats 그대로)
      "cores_quota": 8,                        // 이 컨테이너에 허용된 논리 코어 수.
                                                // cgroup cpu.max 또는 호스트 코어 수.
                                                // 결정 못 하면 null.
      "usage_pct": 75.65                       // 정규화 0-100 (= usage / cores_quota).
                                                // cores_quota 가 null 이면 null.
    },

    "memory": {
      "usage": 1073741824,                     // bytes
      "limit": 4294967296,                     // bytes
      "percent": 25.0                          // usage / limit * 100
    },

    "network": {
      "rx": 12345678,                          // 누적
      "tx": 9876543
    },

    "disk": {
      "read": 12698,                           // 누적
      "write": 4194304
    },

    "gpu": {                                    // optional, 컨테이너에 GPU 할당된 경우만
      "usage": 45,                             // 0-100
      "memoryUsed": 2147483648,
      "memoryTotal": 8589934592,
      "source": "nvidia-smi"                   // 데이터 출처
    }
  }
}
```

### CPU 정규화 (Docker stats 함정)

Docker stats `CPUPerc` 는 코어 합산이라 4-core 컨테이너가 100% 면 400% 로 나옴.
정규화:
- `cores_quota` = `min(cgroup_cpu_max, host_cores)`
- `usage_pct` = `usage / cores_quota` (0-100)

`cores_quota` 결정 실패 시 (예: cgroupv1 read 권한 없음) **null 로 보낸다**. 0 이나
host_cores fallback 금지 — 0 이면 분모 폭발, fallback 이면 잘못된 값 저장.

## Backend 저장 정책

- 모든 raw 필드 → `system_metrics_history.raw_data` JSONB 에 그대로.
- Hot path 필드 (sparkline / aggregation 대상) → `payload_map.py` 정의 따라 column 화.
- Migration 적용 안 된 필드 → `_db_columns()` 체크해서 raw_data 만 저장 (fallback).

새 필드 추가 절차:
1. 이 문서 schema 갱신
2. `apps/metrics/payload_map.py` 매핑 추가
3. `python manage.py makemigrations metrics` (column 추가 자동 생성)
4. `tasks.py` 의 `_collect_*_metrics` 가 map 따라 자동 extract — 코드 변경 최소화
5. `viewsets.py` `buckets()` annotations 에 Avg/Max 추가
6. Frontend `bucketsToSparkline` / chart 매핑에서 새 필드 사용

## 변경 이력

- 2026-04-27 초안. memory.available + gpu 배열 표준화 명시.
