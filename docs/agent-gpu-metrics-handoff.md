# Agent 개발 세션 전달문: GPU Metrics 수집 구현

아래 내용을 Agent repository의 Claude/Codex 개발 세션에 그대로 전달하세요.

---

## 작업 요청

HyperCube Agent에 GPU metrics 수집을 추가해주세요.

상세 구현 스펙은 다음 문서를 기준으로 합니다:

```text
docs/agent-gpu-metrics-plan.md
```

Agent repo에 해당 문서가 없다면, 이 전달문 아래의 핵심 요구사항을 기준으로 구현하세요.

## 핵심 목표

Agent가 매 system collection payload에 `gpu` 필드를 항상 포함해야 합니다.

GPU 없는 서버:

```json
{
  "gpu": []
}
```

NVIDIA GPU 서버:

```json
{
  "gpu": [
    {
      "index": 0,
      "vendor": "NVIDIA",
      "model": "GeForce RTX 3090",
      "memoryTotal": 25769803776,
      "memoryUsed": 1073741824,
      "usage": 45.2,
      "temperature": 62
    }
  ]
}
```

## 반드시 수정할 파일

1. 새 파일 추가:

```text
src/utils/gpu-topology.ts
```

2. 기존 system collector 수정:

```text
src/collectors/system.ts
```

만약 실제 Agent repo에서 파일명이 다르면, system payload를 만드는 실제 collector 파일을 찾아 동일한 변경을 적용하세요.

## `src/utils/gpu-topology.ts` 요구사항

다음 public API를 제공하세요.

```ts
export interface GpuMetric {
  index: number;
  vendor: string;
  model: string;
  memoryTotal: number;
  memoryUsed: number;
  usage: number;
  temperature?: number;
}

export async function collectGpuMetrics(): Promise<GpuMetric[]>;
export function clearGpuTopologyCacheForTests(): void;
```

`clearGpuTopologyCacheForTests()`는 repo test convention상 부적절하면 생략 가능하지만, cache를 테스트에서 reset할 방법은 있어야 합니다.

## NVIDIA 수집 방식

`nvidia-smi`를 shell string이 아니라 fixed args로 실행하세요.

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits
```

예상 출력:

```text
0, GeForce RTX 3090, 24576, 1024, 45, 62
```

Parsing:

- row split: newline
- column split: comma + trim
- field 순서:
  - index
  - name
  - memory.total MiB
  - memory.used MiB
  - utilization.gpu percent
  - temperature.gpu Celsius
- MiB to bytes: `value * 1024 * 1024`
- malformed row는 skip
- 모든 row가 invalid면 `[]`
- 여러 GPU는 index 오름차순

Timeout:

- 500ms

Failure:

- `nvidia-smi` 없음
- timeout
- non-zero exit
- 권한 없음
- parse failure

위 경우 모두 throw하지 말고 fallback 또는 `[]` 처리하세요. GPU 없는 서버에서 error log spam이 없어야 합니다.

## Fallback

`nvidia-smi`가 없거나 usable row가 없으면 `systeminformation.graphics()` fallback을 사용하세요.

Mapping:

```ts
{
  index,
  vendor: controller.vendor || 'Unknown',
  model: controller.model || controller.name || 'Unknown GPU',
  memoryTotal: controller.vram ? controller.vram * 1024 * 1024 : 0,
  memoryUsed: 0,
  usage: 0,
  temperature: undefined
}
```

`systeminformation` dependency가 이미 있으면 그대로 사용하세요. 없으면 Agent repo의 package manager에 맞춰 추가해도 됩니다. dependency 추가가 repo 정책상 부담이면 dynamic import로 감싸고, import 실패 시 `[]`를 반환하세요.

Virtual/software display adapter는 가능하면 filter하세요:

- `Microsoft Basic Display`
- `llvmpipe`
- `VirtualBox`
- `VMware SVGA`
- `Parallels`
- `Basic Render`
- `Software Adapter`

## Cache 정책

Process lifetime cache는 static topology만 허용됩니다.

Cache 가능:

- `index`
- `vendor`
- `model`
- `memoryTotal`

Cache 금지:

- `memoryUsed`
- `usage`
- `temperature`

`nvidia-smi`가 한 번 성공했다가 다음 tick에서 실패하면 stale usage를 반환하지 말고 fallback 또는 `[]`를 반환하세요.

## `src/collectors/system.ts` 연결

system payload 생성 시 다음처럼 GPU를 추가하세요.

```ts
import { collectGpuMetrics } from '../utils/gpu-topology';

const gpu = await collectGpuMetrics().catch(() => []);

return {
  ...existingSystemPayload,
  gpu
};
```

중요:

- 모든 return branch에 `gpu`가 있어야 합니다.
- GPU collector throw가 system collector 전체 실패로 이어지면 안 됩니다.
- backend schema/migration은 변경하지 마세요.

## 테스트 요구사항

기존 Agent repo의 테스트 프레임워크를 따르세요.

필수 테스트:

1. `nvidia-smi` single row parse
2. multiple GPU rows parse
3. malformed row skip
4. all malformed rows -> `[]`
5. `nvidia-smi` missing -> fallback 없으면 `[]`
6. timeout -> fallback 없으면 `[]`
7. `systeminformation.graphics()` fallback mapping
8. virtual/software adapter filtering
9. `collectGpuMetrics()`가 일반 실패에서 throw하지 않음
10. system payload가 항상 `gpu` 포함

가능하면 parser/command runner를 테스트하기 쉬운 작은 함수로 나누세요.

## 검증 명령

Agent repo의 package manager와 scripts를 확인한 뒤 실행하세요.

예:

```bash
npm test
npm run typecheck
npm run lint
```

또는:

```bash
pnpm test
pnpm typecheck
pnpm lint
```

실제 script 이름이 다르면 `package.json` 기준으로 가장 가까운 테스트/typecheck/lint를 실행하세요.

## 수용 기준

- GPU 없는 서버에서 payload에 `"gpu": []`가 나온다.
- GPU 없는 서버에서 Agent log에 GPU error spam이 없다.
- NVIDIA 서버에서 `gpu[0].usage`와 `gpu[0].memoryUsed`가 tick마다 갱신된다.
- `temperature`는 command가 값을 줄 때만 포함된다.
- `nvidia-smi` timeout은 500ms다.
- backend schema 변경이 없다.
- 기존 CPU/memory/disk/network 수집 동작이 유지된다.

## 최종 응답에 포함할 것

작업 완료 후 다음을 보고해주세요.

- 변경 파일 목록
- payload에 `gpu`가 어떻게 들어가는지
- 실행한 test/typecheck/lint 명령과 결과
- 실행하지 못한 명령과 이유
- NVIDIA 실기기 검증 여부

NVIDIA GPU가 없는 환경에서 작업했다면 GPU 실기기 검증을 했다고 말하지 마세요.

