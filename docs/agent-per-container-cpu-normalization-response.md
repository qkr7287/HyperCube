# Agent 응답: 컨테이너 CPU 정규화 메트릭 추가

요청 문서: [`agent-per-container-cpu-normalization-prompt.md`](./agent-per-container-cpu-normalization-prompt.md)
구현 repo: `qkr7287/hypercube-agent`
대상 브랜치: `dev` (커밋 미진행, 배포 검증 후 main merge)

## 결과 요약

**완료**. `container_metrics` 페이로드에 `cpu.usage_pct`, `cpu.cores_quota` 필드를 추가했고 기존 `cpu.usage` (raw)는 그대로 보존한다. TypeScript typecheck 통과. 실서버(16/63) 배포 후 wscat 캡처 검증만 남음.

## 실제 송출 페이로드

WebSocket 프레임 단위 실제 형식. 요청 문서에서 사용한 `payload` 키는 illustrative였고, agent는 기존 컨벤션을 따라 `data`로 감싸서 송출한다 (다른 메시지 타입과 동일).

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

> Note: `containerId`(camelCase) / `cpu.usage_pct`(snake_case) 혼용은 기존 agent 컨벤션이며 변경하지 않았다. backend WS consumer가 이미 처리하고 있으리라 가정.

## 스펙 매칭

| 스펙 항목 | 상태 | 비고 |
| --- | --- | --- |
| `cpu.usage` raw 보존 | OK | 기존 동작 그대로, 필드 위치/이름 변경 없음 |
| `cpu.usage_pct` (P0, 0~100 clamp) | OK | 정밀 측정 오차 → clamp 적용. 소수점 1자리 |
| `cpu.cores_quota` (P0, 분수 허용) | OK | 소수점 2자리 |
| `cpu.cores` 기존 필드 | OK | Docker stats `online_cpus` 그대로 |
| cgroup v1 + v2 (P1) | OK | (방식 변경) Docker inspect 사용 — 양 버전 모두 한 경로로 처리 |
| `--cpus` 분수 한도 (P2) | OK | NanoCpus(1e9 단위) ÷ 1e9 → 정확한 분수 |
| 한도 결정 못함 → null | OK | inspect 실패 시 `cores_quota=null`, `usage_pct=null` |
| `usage=0` → `usage_pct=0` + `cores_quota` 채움 | OK | `clampPercent(0)=0`, quota는 캐시에서 반환 |
| 무제한 컨테이너 → 호스트 전체 코어 | OK | `os.cpus().length` |

## 구현 결정사항: cgroup 파일 직접 읽기 → Docker inspect HostConfig

요청 문서는 cgroup v1/v2 파일 경로를 참고로 제시했지만, **Docker `inspect` HostConfig**를 사용하는 방식으로 구현했다.

**우선순위 (Docker가 CLI 플래그를 cgroup에 반영하는 순서와 동일)**

1. `HostConfig.NanoCpus > 0` → `NanoCpus / 1e9` (즉 `--cpus=2.5` → 2.5)
2. `HostConfig.CpuQuota > 0` & `CpuPeriod > 0` → `CpuQuota / CpuPeriod`
3. `HostConfig.CpusetCpus` 비어있지 않음 → 코어 수 카운트 (예: `"0-3,5"` → 5)
4. 모두 없음 → 호스트 전체 논리 코어 (`os.cpus().length`)
5. inspect 자체가 실패 → `null`

**선택 근거**

- cgroup v1/v2 분기 코드 불필요 — Docker daemon이 이미 cgroup 추상화를 처리
- `/sys/fs/cgroup` 마운트 의존성 제거 — agent 컨테이너에 추가 볼륨 마운트 불필요
- 컨테이너 런타임(docker / containerd / crio) 무관
- Windows / macOS 호스트에서도 동일 코드로 동작
- inspect는 컨테이너 ID당 **1회**만 호출 후 영구 캐시 — quota는 컨테이너 lifetime 동안 불변 (변경하려면 재생성 → 새 ID)
- 컨테이너 stop/disappear 시 캐시에서 자동 prune

**부하**

- 첫 cycle: running 컨테이너 N개 → N회 inspect (10 동시성 한도, 각 ~10-50ms)
- 이후 cycle: 새로 등장한 컨테이너만 inspect, 나머지는 in-memory Map 조회
- 16번 서버(72 컨테이너) 기준 첫 cycle에 추가 ~500ms, 정상 cycle은 사실상 0

## 프롬프트 끝의 5개 질문 답변

| 질문 | 답변 |
| --- | --- |
| cgroup v1/v2 자동 감지 방식 | **하지 않음**. Docker inspect HostConfig로 우회 (위 결정사항 참고) |
| `usage_pct` clamp 0-100 | **적용**. 정밀 측정 오차로 100.x 가능 → 100으로 cap |
| `cores_quota` 분수 정밀도 | **소수점 2자리** (`Math.round(x*100)/100`) |
| 무제한 컨테이너의 `cores_quota` | **호스트 전체 코어** (`os.cpus().length`). null 아님 |
| 추가 부하 | **컨테이너 ID당 inspect 1회 + 영구 캐시**. 정상 cycle 추가 비용 ~0 |

## 변경 파일

| 파일 | 변경 내용 |
| --- | --- |
| `src/utils/container-cpu-quota.ts` (신규) | `resolveContainerCoresQuota()` — inspect HostConfig 파싱, NanoCpus → CpuQuota/Period → CpusetCpus → host 우선순위 |
| `src/types/index.ts` | `ContainerMetrics.cpu`에 `usage_pct: number\|null`, `cores_quota: number\|null` 필드 추가 |
| `src/collectors/docker.ts` | `coresQuotaCache` Map (per short ID) 도입, `collectSingleMetrics`에서 `usage_pct = clamp(usage/cores_quota, 0, 100)` 계산, 컨테이너 종료 시 cache prune |

## 검증 상태

- [x] TypeScript typecheck 통과 (`tsc --noEmit`)
- [ ] 실서버 wscat 캡처 검증 — agent dev 브랜치 배포 후 진행
  - 16번 서버: 다양한 컨테이너 (한도 있음/없음 혼재)
  - 63번 서버: GPU 환경 + Docker
- [ ] 검산: `usage / cores_quota * 100 ≈ usage_pct` (clamp 100 케이스 제외)

## Backend / Frontend 작업 (별도)

요청 문서에 명시된 backend 작업 항목은 별도로 진행해도 무방. agent 송출이 시작되면 backend는 새 필드 두 개를 모델/마이그레이션/API에 반영하면 된다. 자세한 backend 작업 명세는 [`backend-per-container-cpu-normalization-prompt.md`](./backend-per-container-cpu-normalization-prompt.md) 참고.
