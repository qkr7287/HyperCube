# Claude 작업 지시서: Agent GPU Metrics 수집 추가

Status: **Agent 개발 세션에 바로 전달 가능한 구현 지시서**

목표는 HyperCube Agent가 매 system 수집 payload에 `gpu` 배열을 항상 포함하도록 만드는 것이다. GPU가 없는 서버에서는 `gpu: []`를 보내고, NVIDIA GPU가 있는 서버에서는 `nvidia-smi`로 실시간 usage/memory/temperature를 수집한다. macOS/Windows Docker Desktop 또는 `nvidia-smi`가 없는 환경에서는 `systeminformation.graphics()`를 fallback으로 사용한다.

이 작업은 **Agent repository**에서 수행한다. HyperCube backend/frontend repository에는 Agent 소스가 없을 수 있다.

## 0. 절대 요구사항

- system payload에는 항상 `gpu` 필드가 있어야 한다.
- GPU가 없거나 수집 실패 시 반드시 `gpu: []`를 보낸다.
- GPU 수집 실패가 Agent heartbeat/system collection 전체를 실패시키면 안 된다.
- `nvidia-smi` 호출 timeout은 500ms로 둔다.
- `nvidia-smi` parse 실패, command 없음, 권한 없음, timeout, non-zero exit은 모두 조용히 `[]`로 처리한다.
- 정상 GPU 서버에서는 매 collection tick마다 `usage`, `memoryUsed`, `temperature`를 새로 수집한다.
- process lifetime cache는 `index/vendor/model/memoryTotal` 같은 static topology만 허용한다.
- `memoryTotal`, `memoryUsed`는 bytes 단위다.
- backend schema/migration 변경은 하지 않는다.

## 1. 작업 전 Repository 확인

Agent repo에서 먼저 아래를 확인한다.

```bash
pwd
ls
find src -maxdepth 3 -type f | sort
cat package.json
```

확인할 항목:

- package manager:
  - `pnpm-lock.yaml` 있으면 `pnpm`
  - `yarn.lock` 있으면 `yarn`
  - `package-lock.json` 있으면 `npm`
  - lockfile이 없으면 기존 README/package scripts 기준
- 테스트 프레임워크:
  - `vitest`, `jest`, `node:test` 중 실제 사용 중인 것
- 기존 system collector 위치:
  - 우선 `src/collectors/system.ts`
  - 없으면 `src`에서 system payload를 만드는 파일 검색
- 기존 utils import style:
  - extension 없는 import인지, `.js` extension을 쓰는 ESM style인지
  - 새 import는 기존 style에 맞춘다.
- `systeminformation` dependency 존재 여부:
  - 이미 있으면 그대로 사용
  - 없으면 이 작업 요구사항상 dependency 추가를 허용한다.
  - 단, repo가 dependency 추가를 엄격히 제한하는 구조라면 dynamic import fallback으로 구현하고, dependency 없음은 `[]`로 처리한다.

## 2. 구현 파일

### 2.1 새 파일: `src/utils/gpu-topology.ts`

이 파일은 GPU 수집 로직을 모두 캡슐화한다.

Public API:

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

`clearGpuTopologyCacheForTests()`는 테스트에서만 사용한다. 프로젝트가 test-only export를 싫어하면 생략 가능하지만, cache reset 방법은 테스트에 있어야 한다.

### 2.2 수정 파일: `src/collectors/system.ts`

매 system collection 시 `collectGpuMetrics()`를 호출하고 outgoing payload에 `gpu`를 추가한다.

예시:

```ts
import { collectGpuMetrics } from '../utils/gpu-topology';

const gpu = await collectGpuMetrics().catch(() => []);

return {
  ...existingSystemPayload,
  gpu
};
```

collector가 여러 return branch를 가진다면 모든 branch에 `gpu`가 들어가야 한다. 실패 fallback branch도 `gpu: []`를 포함해야 한다.

## 3. NVIDIA 수집 상세

명령:

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits
```

예상 출력:

```text
0, GeForce RTX 3090, 24576, 1024, 45, 62
```

Mapping:

```json
{
  "index": 0,
  "vendor": "NVIDIA",
  "model": "GeForce RTX 3090",
  "memoryTotal": 25769803776,
  "memoryUsed": 1073741824,
  "usage": 45,
  "temperature": 62
}
```

Parsing rule:

- stdout를 newline 기준으로 나눈다.
- 빈 줄은 버린다.
- 각 row는 comma split 후 trim한다.
- 최소 6개 field가 없으면 해당 row skip.
- 숫자 field가 finite number가 아니면 해당 row skip.
- 모든 row가 invalid면 `[]`.
- 여러 GPU row가 있으면 `index` 오름차순으로 반환한다.
- memory 값은 MiB로 간주하고 bytes로 변환한다.

Conversion:

```ts
const mibToBytes = (value: number) => value * 1024 * 1024;
```

주의:

- `nvidia-smi` query 결과에서 GPU name에 comma가 들어갈 가능성은 낮다. 이 command shape에서는 단순 comma split을 허용한다.
- 그래도 repo에 CSV parser가 이미 있다면 기존 parser를 사용해도 된다. 새 dependency를 CSV parsing만 위해 추가하지는 않는다.

## 4. `nvidia-smi` 실행 방식

권장 구현:

```ts
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

const NVIDIA_SMI_ARGS = [
  '--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu',
  '--format=csv,noheader,nounits'
];

async function queryNvidiaSmi(): Promise<string> {
  const result = await execFileAsync('nvidia-smi', NVIDIA_SMI_ARGS, {
    timeout: 500,
    windowsHide: true,
    maxBuffer: 1024 * 1024
  });
  return result.stdout;
}
```

Failure handling:

- `ENOENT` -> `[]`
- timeout -> `[]`
- non-zero exit -> `[]`
- stdout empty -> fallback 시도
- stderr exists but stdout parse 가능 -> stderr 무시
- 예상 밖 exception -> `[]`

로그:

- 일반 실패는 `console.error` 금지.
- 기존 logger가 있다면 debug level에서만 기록.
- logger 패턴이 없으면 완전히 silent 처리.

## 5. Topology Cache 정책

Cache 가능한 값:

- `index`
- `vendor`
- `model`
- `memoryTotal`

Cache 금지 값:

- `memoryUsed`
- `usage`
- `temperature`

권장 internal type:

```ts
interface GpuTopologyEntry {
  index: number;
  vendor: string;
  model: string;
  memoryTotal: number;
}

let cachedTopology: GpuTopologyEntry[] | null = null;
```

Flow:

1. 매 tick마다 `nvidia-smi`를 호출한다.
2. parse 가능한 dynamic rows가 있으면 반환한다.
3. `cachedTopology`가 비어 있으면 rows에서 static topology를 채운다.
4. 이후 tick에서는 같은 index의 cached topology가 있으면 static 값은 cache 기준으로 merge한다.
5. 단, dynamic rows가 없는 tick에서는 stale cache를 payload로 내보내지 않는다. 그 tick은 fallback 또는 `[]`다.

이유:

- GPU 존재 정보는 안정적이지만 usage/memory/temperature는 실시간 값이다.
- `nvidia-smi`가 한 번 성공했다가 나중에 실패했을 때 stale usage를 보여주면 운영자가 오판할 수 있다.

## 6. `systeminformation.graphics()` fallback

Fallback은 `nvidia-smi`가 없거나 usable row가 없을 때만 시도한다.

권장 import:

```ts
import si from 'systeminformation';
```

만약 repo의 ESM/CJS 설정 때문에 default import가 맞지 않으면 기존 repo style에 맞춰 수정한다.

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

Fallback filtering:

- `model`/`name`이 전혀 없으면 skip.
- 아래 virtual/software display로 보이는 항목은 skip 권장:
  - `Microsoft Basic Display`
  - `llvmpipe`
  - `VirtualBox`
  - `VMware SVGA`
  - `Parallels`
  - `Basic Render`
  - `Software Adapter`
- 단, filtering 때문에 모든 row가 사라지면 `[]`.

Dependency decision:

- `systeminformation`이 이미 dependency면 normal import 사용.
- 없다면 package manager에 맞춰 dependency 추가:
  - `pnpm add systeminformation`
  - `yarn add systeminformation`
  - `npm install systeminformation`
- dependency 추가가 프로젝트 정책상 위험하면 다음 fallback helper를 사용한다:

```ts
async function collectGraphicsFallback(): Promise<GpuMetric[]> {
  try {
    const si = await import('systeminformation');
    const graphics = await si.default.graphics();
    // map controllers...
  } catch {
    return [];
  }
}
```

## 7. 동시성/성능

- system collector가 이미 `Promise.all`로 독립 metric을 병렬 수집한다면 GPU도 같은 그룹에 넣는다.
- sequential collector라면 우선 최소 변경으로 sequential 추가해도 된다. timeout 500ms가 있으므로 worst-case delay는 제한된다.
- `nvidia-smi`를 한 tick에서 두 번 이상 호출하지 않는다.
- 실패 시 retry하지 않는다.
- child process가 timeout 이후 남지 않도록 `execFile` timeout 또는 AbortController를 사용한다.

## 8. Payload Contract

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

Field table:

| field | type | required | unit | source |
| --- | --- | --- | --- | --- |
| `index` | number | yes | none | `nvidia-smi` index or fallback array index |
| `vendor` | string | yes | none | `"NVIDIA"` or fallback vendor |
| `model` | string | yes | none | GPU name/model |
| `memoryTotal` | number | yes | bytes | static topology |
| `memoryUsed` | number | yes | bytes | realtime, fallback `0` |
| `usage` | number | yes | percent | realtime, fallback `0` |
| `temperature` | number | no | Celsius | realtime if available |

## 9. 테스트 지시

Agent repo의 기존 테스트 프레임워크와 파일 위치를 따른다.

권장 테스트 파일:

- `src/utils/gpu-topology.test.ts`
- 또는 기존 convention이 `tests/`면 `tests/gpu-topology.test.ts`
- `system.ts` 테스트가 이미 있으면 해당 파일에 payload test 추가

필수 unit test:

1. NVIDIA single row parse
   - input: `0, GeForce RTX 3090, 24576, 1024, 45, 62`
   - expected:
     - `index: 0`
     - `vendor: "NVIDIA"`
     - `model: "GeForce RTX 3090"`
     - `memoryTotal: 24576 * 1024 * 1024`
     - `memoryUsed: 1024 * 1024 * 1024`
     - `usage: 45`
     - `temperature: 62`

2. NVIDIA multiple rows
   - two valid rows
   - expected sorted by index

3. Malformed rows are skipped
   - one invalid row and one valid row
   - expected only valid row

4. All malformed rows return `[]`

5. `nvidia-smi` missing returns `[]` when fallback has no usable controllers

6. `nvidia-smi` timeout returns `[]` when fallback has no usable controllers

7. fallback graphics controller maps to `GpuMetric`
   - `memoryUsed: 0`
   - `usage: 0`
   - `memoryTotal` bytes

8. virtual/software fallback controllers are filtered

9. `collectGpuMetrics()` never throws on command/fallback failure

10. `system.ts` outgoing payload always includes `gpu`
    - when collector returns `[]`
    - when collector throws unexpectedly

Mocking:

- If using `vitest`, mock `node:child_process` or wrap exec helper for easier mocking.
- If using `jest`, use `jest.mock`.
- If tests are difficult because `execFile` is promisified at module load, expose small internal parser helpers or inject command runner.

Recommended testable internal helpers:

```ts
export function parseNvidiaSmiCsvForTests(stdout: string): GpuMetric[];
```

Only add this if existing repo allows test-only exports. Otherwise keep parser private and test through mocked command runner.

## 10. Manual verification

### GPU 없는 서버

Targets mentioned by product:

- server 16
- server 41
- server 63

Expected:

- Agent log has no GPU error spam.
- system payload includes `"gpu": []`.
- existing CPU/memory/disk/network/container behavior unchanged.

Redis cache check if backend stack is available:

```bash
docker exec hc-redis redis-cli -n 1 GET "server:<id>:system"
```

### NVIDIA GPU 서버

Before Agent run:

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu --format=csv,noheader,nounits
```

Expected:

- payload `gpu.length >= 1`
- `gpu[0].vendor === "NVIDIA"`
- `gpu[0].memoryTotal` equals `memory.total MiB * 1024 * 1024`
- `gpu[0].memoryUsed` updates across ticks
- `gpu[0].usage` updates across ticks
- `gpu[0].temperature` exists when command returns temperature

Smoke:

1. Observe 3 consecutive system payloads.
2. Start a small GPU workload.
3. Confirm `usage` or `memoryUsed` changes.

## 11. Completion checklist

- [ ] `src/utils/gpu-topology.ts` exists.
- [ ] `collectGpuMetrics()` returns `Promise<GpuMetric[]>`.
- [ ] `nvidia-smi` command uses fixed args and no shell string.
- [ ] `nvidia-smi` timeout is 500ms.
- [ ] all normal failure paths return `[]`.
- [ ] no noisy `console.error` on GPU-free servers.
- [ ] fallback uses `systeminformation.graphics()` when available.
- [ ] `src/collectors/system.ts` always includes `gpu`.
- [ ] GPU-free tests pass.
- [ ] NVIDIA parse tests pass.
- [ ] system payload tests pass.
- [ ] typecheck passes.
- [ ] existing tests pass.
- [ ] no backend schema/migration changes.

## 12. Commands to run before final response

Use the Agent repo's package manager.

Examples:

```bash
npm test
npm run typecheck
npm run lint
```

or:

```bash
pnpm test
pnpm typecheck
pnpm lint
```

If scripts have different names, inspect `package.json` and run the closest equivalents. If a command cannot run because dependencies are missing or environment is unavailable, report that clearly.

## 13. Final response requirement for Agent developer

Final response must include:

- changed files
- exact payload behavior
- test/typecheck commands run and results
- any command not run and reason
- manual verification notes if available

Do not claim NVIDIA hardware verification unless it was actually performed on a GPU host.

## 14. Out of scope

- Backend schema changes
- Backend migration
- Frontend GPU chart/sidebar UI
- Historical GPU persistence
- AMD/Intel realtime utilization
- per-container GPU attribution
- alert thresholds based on GPU

