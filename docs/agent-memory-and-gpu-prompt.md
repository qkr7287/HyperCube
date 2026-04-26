# Agent v3 prompt — system_metrics 메모리 정확도 + GPU 표준화

## 배경 (TL;DR)

HyperCube 대시보드에서 **메모리 사용률이 항상 90%+ 로 잘못 표시** 되는 문제 발견.
실측 (`free -m`):
- 16서버: 17.5 GB used / 39.7 GB total = 44%, MemAvailable 21.2 GB
- 63서버: 7.2 GB used / 15.9 GB total = 45%, MemAvailable 8.1 GB

Agent payload 의 `memory.usage`:
- 16서버: 98.4%
- 63서버: 93.8%

Agent 가 Linux 에서 `(total - free) / total` 로 계산하는 게 원인. `MemFree` 는
"어디에도 안 쓰이는 바이트" 라 항상 작고, **reclaimable buffer/cache 까지 used 로
잘못 카운트**. 정확한 계산은 **`MemAvailable` 사용**.

추가로 GPU 데이터를 fleet trend chart 에서 활용할 수 있도록 schema 표준화 필요
(payload contract 새로 작성, `docs/agent-payload-contract.md`).

## 작업 범위

Agent (`hypercube-agent`) v2 → v3.

1. system_metrics payload `memory` 필드에 `available` 추가 + `used` / `usage` 재계산
2. system_metrics payload `gpu` 배열 필드 표준화 (필드명 / 타입)

Backend / Frontend 는 nullable 컬럼으로 이미 준비 완료. Agent 만 수정하면 자동
정상화. backend migration 0005 + payload contract 문서 이미 머지됨 (커밋 `7856ac2`).

---

## 변경사항 1: 메모리 정확도

### Linux

`/proc/meminfo` 를 직접 파싱하든 라이브러리 쓰든 **MemAvailable 사용 의무**.

| Payload 필드 | 출처 | 계산 |
|---|---|---|
| `memory.total` | `MemTotal * 1024` | bytes |
| `memory.free` | `MemFree * 1024` | bytes — 그대로 보고 (디버그용 보존) |
| `memory.available` | `MemAvailable * 1024` | bytes — **신규 필수** |
| `memory.used` | `total - available` | bytes — **계산식 변경** |
| `memory.usage` | `(total - available) / total * 100` | % — **계산식 변경** |

**변경 전 (현재)**:
```js
const used = total - free;
const usage = (used / total) * 100;
```

**변경 후**:
```js
const used = total - available;       // available 우선
const usage = (used / total) * 100;
```

라이브러리:
- Go: `gopsutil/v3/mem` `VirtualMemory()` → `Available` 필드 (이미 정확)
- Node: `fs.readFileSync('/proc/meminfo')` 직접 파싱
  ```js
  function parseMeminfo() {
    const text = fs.readFileSync('/proc/meminfo', 'utf-8');
    const get = (key) => {
      const m = text.match(new RegExp(`^${key}:\\s+(\\d+)\\s+kB`, 'm'));
      return m ? parseInt(m[1], 10) * 1024 : null;
    };
    return {
      total: get('MemTotal'),
      free: get('MemFree'),
      available: get('MemAvailable'),
    };
  }
  ```
- Python: `psutil.virtual_memory().available`

### Windows / macOS

OS 가 제공하는 `available` (또는 동등) 그대로 사용. 의미가 Linux 와 다르긴 해도
플랫폼 native 값이 정확함. 없으면 fallback 으로 `total - free`.

---

## 변경사항 2: GPU 배열 표준화

다중 GPU 호스트도 일관되게 처리할 수 있도록 array 형식 + 필드명 고정.

### 표준 schema

```jsonc
"gpu": [
  {
    "index": 0,                          // 0부터
    "vendor": "NVIDIA",                  // "NVIDIA" | "AMD" | "Intel"
    "model": "NVIDIA GeForce RTX 3060 Ti",
    "usage": 45.2,                       // 0-100, GPU compute 사용률
    "memoryTotal": 8589934592,           // bytes
    "memoryUsed": 6910115840,            // bytes
    "memoryPercent": 80.4,               // optional, used/total*100
    "temperature": 61,                   // °C, optional
    "source": "nvidia-smi"               // 어디서 가져왔는지 (디버그용, optional)
  }
]
```

### 호스트에 GPU 가 없을 때

`"gpu": []` 빈 배열 (필드는 항상 존재, 배열만 비어있음).

### 다중 GPU

배열에 여러 dict. Backend 가 평균/합산/최대값으로 정규화해서 컬럼 저장:
- `gpu_usage` = 모든 GPU usage 의 평균
- `gpu_memory_used` = 합산
- `gpu_memory_total` = 합산
- `gpu_temperature_max` = 최대값

Agent 는 raw array 만 보내면 되고 정규화는 backend 가 함.

### 현재 Agent 보고 형식과 차이

지금:
```jsonc
"gpu": [
  { "index": 0, "memoryTotal": 268435456, "memoryUsed": 0,
    "model": "...", "usage": 0, "vendor": "Intel Corporation" }
]
```

거의 맞음. **추가만 하면 됨**:
- `temperature` (°C) — NVIDIA 만 있어도 됨 (Intel 통합그래픽은 보통 안 나옴)
- `source` (optional, 디버깅용)

---

## 검증 방법

### 메모리

Agent 배포 후 `/api/metrics/system/?limit=1&ordering=recorded_at` 호출:

```jsonc
"memory": {
    "total": 41691742208,
    "free": 654454784,
    "available": 22271770624,    // ← 신규 필드 존재
    "used": 19419971584,         // total - available 와 일치
    "usage": 46.6                // (used/total)*100 와 일치, 90%+ 아니어야 함
}
```

또는 16서버에서 직접:
```bash
ssh root@192.168.0.16 "free -m"
# total used 와 dashboard 표시값이 ±5% 이내여야 함
```

### GPU

`/api/metrics/system/buckets/?bucket=300` 응답에서:

```jsonc
{
  "gpu_avg": 12.5,                // null 아님 (GPU 있는 호스트는)
  "gpu_temperature_max": 65,
  ...
}
```

대시보드 GPU sparkline 에 변동선 그려져야 함 (현재는 평탄선 0).

### Backend 로그

Agent v3 가 새 payload 보내면:
```
hc-celery-worker logs:
[INFO] flushed 2 system + N container records
```

여전히 정상 동작해야 함 (schema 추가는 호환성 유지).

---

## 배포 순서 (운영 노트)

1. 이 변경 적용한 agent 빌드 → 16서버 / 63서버 배포
2. 5초 후 backend Redis cache 만료 → 다음 flush 사이클에서 새 payload DB 저장
3. 60초 후 frontend buckets API cache 만료 → dashboard 가 정상값 표시
4. **사용자 입장에서 메모리 % 가 갑자기 90% → 45% 로 변하는 현상 발생** —
   장애 아님. 운영 채널에 미리 공지.

---

## 참고 문서

- `docs/agent-payload-contract.md` — 전체 payload 스펙 (이번에 함께 머지됨)
- 이전 GPU 작업: `docs/agent-per-container-cpu-normalization-response.md`
- Backend migration: `backend/apps/metrics/migrations/0005_system_gpu_and_memory_available.py`
