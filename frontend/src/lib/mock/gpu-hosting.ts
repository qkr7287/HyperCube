// GPU Hosting Dashboard mock data.
//
// brief: docs/specs/gpu-hosting-dashboard-brief.html §9 / §13 (Read Model Contract).
// 1차 mock 데이터로 백엔드 변경 0. 실제 API 연결은 후속 작업.
//
// Fixture: 4 hosts · 8 GPUs (H100×5 [MIG×3 + Whole×2], A100×2 [MIG], RTX 4090×1 [Whole])
// 실패 시드 6종: host_offline · driver_error · allocation_failed · oom · mig_reconfiguring · xid_ecc_error
// Quality state 시드 2종: idle_waste (A100-02), saturation (H100-02 slice[0])

export type GpuMode = 'mig' | 'whole';
export type MigProfile = '1g.10gb' | '2g.20gb' | '3g.40gb' | '7g.80gb' | 'whole';
export type Severity = 'ok' | 'warn' | 'error' | 'offline';
export type QualityState = 'idle_waste' | 'saturation' | null;

export type EventKind =
  | 'allocated'
  | 'released'
  | 'host_offline'
  | 'driver_error'
  | 'mig_reconfiguring'
  | 'allocation_failed'
  | 'oom'
  | 'health_unhealthy'
  | 'xid_ecc_error'
  | 'requested'
  | 'approved'
  | 'rejected'
  | 'container_created'
  | 'container_started'
  | 'container_stopped'
  | 'model_loaded'
  | 'model_unloaded'
  | 'market_shared'
  | 'market_unshared'
  | 'quota_exceeded'
  | 'auto_recovered'
  | 'maintenance';

export type EventSource =
  | 'agent_heartbeat'
  | 'resource_event'
  | 'container_event'
  | 'allocation_service'
  | 'synthetic';

export interface HostMock {
  id: string;
  hostname: string;
  location: string;
  agentLastSeenISO: string;
  isOnline: boolean;
  staleSec: number;
  gpuIds: string[];
}

export interface SliceMock {
  id: string;
  profile: MigProfile;
  profileWeight: number; // 1 | 2 | 3 | 7
  containerId: string | null;
  user: { id: string; name: string } | null;
  model: { name: string; versionId: string } | null;
  computePct: number | null;
  computePctSustained5m: number | null;
  computePctSustained10m: number | null;
  qualityState: QualityState;
  queueDepth: number | null;
  latencyP95Ms: number | null;
  vramUsedGB: number;
  vramTotalGB: number;
}

export interface GpuMock {
  id: string;
  label: string;
  hostId: string;
  model: 'H100' | 'A100' | 'L40S' | 'RTX 4090';
  mode: GpuMode;
  severity: Severity;
  incident: EventKind | null;
  slices: SliceMock[];
  computePct: number | null;
  computePctP95_1h: number | null;
  vramUsedGB: number;
  vramTotalGB: number;
  tempC: number | null;
  tempTrendC5m: number;
  powerW: number | null;
  powerCapW: number;
  sparkline60s: number[];
  recentEvents: EventMock[];
}

export interface EventMock {
  ts: string;
  kind: EventKind;
  source: EventSource;
  severity: Severity;
  gpuId?: string;
  hostId?: string;
  containerId?: string;
  requestId?: string;
  message: string;
}

export interface ReqVramShare {
  reqId: string;
  user: string;
  gpuLabel: string;
  usedGB: number;
  totalGB: number;
}

export interface MountedModel {
  modelName: string;
  modelVersionId: string;
  modelAssetId: string;
  mountedOn: Array<{ gpuLabel: string; containerId: string; user: string }>;
  marketSharedAt: string | null;  // ISO 시각. null = 마켓 미공유
  marketCalls7d: number;          // 7일 누적 호출 (마켓 공유 시)
}

// ─── fixture utility ───────────────────────────────────────────────────────────
const NOW_ISO = '2026-05-26T12:03:00Z';
const NOW_MS = Date.parse(NOW_ISO);

function isoAt(offsetMin: number): string {
  return new Date(NOW_MS + offsetMin * 60_000).toISOString();
}

// Reproducible jitter sparkline.
// `wave` mixes two sinusoids; `seed` shifts phase per GPU so each line differs.
function makeSparkline(base: number, amplitude: number, seed: number, length = 60): number[] {
  const out: number[] = [];
  for (let i = 0; i < length; i++) {
    const a = Math.sin((i + seed) / 5) * amplitude;
    const b = Math.cos((i + seed * 1.7) / 8) * (amplitude * 0.4);
    const v = base + a + b;
    out.push(Math.max(0, Math.min(100, v)));
  }
  return out;
}

function flatLowSparkline(length = 60): number[] {
  return Array.from({ length }, () => 0);
}

// ─── hosts ─────────────────────────────────────────────────────────────────────
// hostname / ip / location 은 backend 에 등록된 agent 와 일치 (server_41_dev / 63_dev / 16_dev).
// host-gpu-03 은 미등록 offline 서버 시나리오용 가공 데이터.
export const HOSTS: HostMock[] = [
  {
    id: 'host-gpu-01',
    hostname: 'server_41_dev',
    location: '192.168.0.41',
    agentLastSeenISO: isoAt(-0.2),
    isOnline: true,
    staleSec: 12,
    gpuIds: [
      'h100-01', 'h100-02', 'h100-03',
      'a100-03', 'a100-04', 'l40s-01',
      'h100-06', 'h100-07', 'h100-08',
      'a100-05', 'a100-06', 'l40s-02',
    ],
  },
  {
    id: 'host-gpu-02',
    hostname: 'server_63_dev',
    location: '192.168.0.63',
    agentLastSeenISO: isoAt(-0.15),
    isOnline: true,
    staleSec: 9,
    gpuIds: ['rtx4090-01', 'rtx4090-02', 'rtx4090-03'],
  },
  {
    // 미등록 offline 시나리오 — agent stale > 180s → isOnline=false → 하위 GPU offline override.
    id: 'host-gpu-03',
    hostname: 'server_88_busan',
    location: '192.168.0.88',
    agentLastSeenISO: isoAt(-5.5),
    isOnline: false,
    staleSec: 332,
    gpuIds: ['h100-04', 'h100-05'],
  },
  {
    id: 'host-gpu-04',
    hostname: 'server_16_dev',
    location: '192.168.0.16',
    agentLastSeenISO: isoAt(-0.1),
    isOnline: true,
    staleSec: 6,
    gpuIds: ['a100-01', 'a100-02'],
  },
];

// ─── slice helpers ─────────────────────────────────────────────────────────────
function emptySlice(id: string, profile: MigProfile, weight: number, vramTotal: number): SliceMock {
  return {
    id,
    profile,
    profileWeight: weight,
    containerId: null,
    user: null,
    model: null,
    computePct: null,
    computePctSustained5m: null,
    computePctSustained10m: null,
    qualityState: null,
    queueDepth: null,
    latencyP95Ms: null,
    vramUsedGB: 0,
    vramTotalGB: vramTotal,
  };
}

// ─── GPUs ──────────────────────────────────────────────────────────────────────
export const GPUS: GpuMock[] = [
  // host-gpu-01 ── H100-01 (MIG 7 slice, 5 alloc + 2 free) ───────────────────────
  {
    id: 'h100-01',
    label: 'H100-01',
    hostId: 'host-gpu-01',
    model: 'H100',
    mode: 'mig',
    severity: 'ok',
    incident: 'xid_ecc_error', // synthetic, surfaced in recentEvents only
    slices: [
      {
        id: 'h100-01-s1', profile: '1g.10gb', profileWeight: 1,
        containerId: 'cont-llama3-01',
        user: { id: 'u-kim', name: '김민준' },
        model: { name: 'Llama 3 70B', versionId: 'mv-llama3-70b' },
        computePct: 38, computePctSustained5m: 41, computePctSustained10m: 39, qualityState: null,
        queueDepth: 0, latencyP95Ms: 95, vramUsedGB: 9, vramTotalGB: 10,
      },
      {
        id: 'h100-01-s2', profile: '1g.10gb', profileWeight: 1,
        containerId: 'cont-llama3-01',
        user: { id: 'u-kim', name: '김민준' },
        model: { name: 'Llama 3 70B', versionId: 'mv-llama3-70b' },
        computePct: 42, computePctSustained5m: 44, computePctSustained10m: 41, qualityState: null,
        queueDepth: 0, latencyP95Ms: 102, vramUsedGB: 9, vramTotalGB: 10,
      },
      {
        id: 'h100-01-s3', profile: '1g.10gb', profileWeight: 1,
        containerId: 'cont-llama3-01',
        user: { id: 'u-kim', name: '김민준' },
        model: { name: 'Llama 3 70B', versionId: 'mv-llama3-70b' },
        computePct: 44, computePctSustained5m: 42, computePctSustained10m: 40, qualityState: null,
        queueDepth: 0, latencyP95Ms: 88, vramUsedGB: 9, vramTotalGB: 10,
      },
      emptySlice('h100-01-s4', '1g.10gb', 1, 10),
      emptySlice('h100-01-s5', '1g.10gb', 1, 10),
      {
        id: 'h100-01-s6', profile: '1g.10gb', profileWeight: 1,
        containerId: 'cont-mistral-01',
        user: { id: 'u-lee', name: '이서연' },
        model: { name: 'Mistral 7B', versionId: 'mv-mistral-7b' },
        computePct: 36, computePctSustained5m: 38, computePctSustained10m: 35, qualityState: null,
        queueDepth: 0, latencyP95Ms: 48, vramUsedGB: 8, vramTotalGB: 10,
      },
      {
        id: 'h100-01-s7', profile: '1g.10gb', profileWeight: 1,
        containerId: 'cont-mistral-01',
        user: { id: 'u-lee', name: '이서연' },
        model: { name: 'Mistral 7B', versionId: 'mv-mistral-7b' },
        computePct: 47, computePctSustained5m: 45, computePctSustained10m: 43, qualityState: null,
        queueDepth: 0, latencyP95Ms: 52, vramUsedGB: 8, vramTotalGB: 10,
      },
    ],
    computePct: 41,
    computePctP95_1h: 58,
    vramUsedGB: 43,
    vramTotalGB: 80,
    tempC: 75,
    tempTrendC5m: 0.2,
    powerW: 340,
    powerCapW: 700,
    sparkline60s: makeSparkline(41, 7, 1),
    recentEvents: [], // populated below
  },
  // host-gpu-01 ── H100-02 (Whole, saturation seed) ─────────────────────────────
  {
    id: 'h100-02',
    label: 'H100-02',
    hostId: 'host-gpu-01',
    model: 'H100',
    mode: 'whole',
    severity: 'warn', // derived from saturation slice
    incident: null,
    slices: [
      {
        id: 'h100-02-whole', profile: 'whole', profileWeight: 7,
        containerId: 'cont-qwen2-01',
        user: { id: 'u-park', name: '박지호' },
        model: { name: 'Qwen2 72B', versionId: 'mv-qwen2-72b' },
        computePct: 93, computePctSustained5m: 93, computePctSustained10m: 89,
        qualityState: 'saturation',
        queueDepth: 4, latencyP95Ms: 820,
        vramUsedGB: 72, vramTotalGB: 80,
      },
    ],
    computePct: 93,
    computePctP95_1h: 95,
    vramUsedGB: 72,
    vramTotalGB: 80,
    tempC: 82,
    tempTrendC5m: 1.8,
    powerW: 670,
    powerCapW: 700,
    sparkline60s: makeSparkline(78, 12, 7),
    recentEvents: [],
  },
  // host-gpu-01 ── H100-03 (Whole, driver_error incident) ───────────────────────
  {
    id: 'h100-03',
    label: 'H100-03',
    hostId: 'host-gpu-01',
    model: 'H100',
    mode: 'whole',
    severity: 'error',
    incident: 'driver_error',
    slices: [emptySlice('h100-03-whole', 'whole', 7, 80)],
    computePct: null,
    computePctP95_1h: null,
    vramUsedGB: 0,
    vramTotalGB: 80,
    tempC: null,
    tempTrendC5m: 0,
    powerW: null,
    powerCapW: 700,
    sparkline60s: flatLowSparkline(),
    recentEvents: [],
  },
  // host-gpu-02 ── RTX 4090-01 (Whole) ──────────────────────────────────────────
  {
    id: 'rtx4090-01',
    label: 'RTX 4090-01',
    hostId: 'host-gpu-02',
    model: 'RTX 4090',
    mode: 'whole',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'rtx4090-01-whole', profile: 'whole', profileWeight: 7,
        containerId: 'cont-codellama-01',
        user: { id: 'u-choi', name: '최유진' },
        model: { name: 'CodeLlama 34B', versionId: 'mv-codellama-34b' },
        computePct: 64, computePctSustained5m: 62, computePctSustained10m: 60,
        qualityState: null,
        queueDepth: 1, latencyP95Ms: 210,
        vramUsedGB: 19, vramTotalGB: 24,
      },
    ],
    computePct: 64,
    computePctP95_1h: 71,
    vramUsedGB: 19,
    vramTotalGB: 24,
    tempC: 68,
    tempTrendC5m: 0.4,
    powerW: 320,
    powerCapW: 450,
    sparkline60s: makeSparkline(64, 9, 13),
    recentEvents: [],
  },
  // host-gpu-01 ── A100-03 (MIG 4 slice, 박소연 DeepSeek) ───────────────────────
  {
    id: 'a100-03',
    label: 'A100-03',
    hostId: 'host-gpu-01',
    model: 'A100',
    mode: 'mig',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'a100-03-s1', profile: '2g.20gb', profileWeight: 2,
        containerId: 'cont-deepseek-01',
        user: { id: 'u-park-soyeon', name: '박소연' },
        model: { name: 'DeepSeek 67B', versionId: 'mv-deepseek-67b' },
        computePct: 56, computePctSustained5m: 54, computePctSustained10m: 52, qualityState: null,
        queueDepth: 1, latencyP95Ms: 240, vramUsedGB: 17, vramTotalGB: 20,
      },
      {
        id: 'a100-03-s2', profile: '2g.20gb', profileWeight: 2,
        containerId: 'cont-deepseek-01',
        user: { id: 'u-park-soyeon', name: '박소연' },
        model: { name: 'DeepSeek 67B', versionId: 'mv-deepseek-67b' },
        computePct: 58, computePctSustained5m: 57, computePctSustained10m: 55, qualityState: null,
        queueDepth: 1, latencyP95Ms: 232, vramUsedGB: 17, vramTotalGB: 20,
      },
      emptySlice('a100-03-s3', '1g.10gb', 1, 10),
      emptySlice('a100-03-s4', '1g.10gb', 1, 10),
      emptySlice('a100-03-s5', '1g.10gb', 1, 10),
    ],
    computePct: 57,
    computePctP95_1h: 68,
    vramUsedGB: 34,
    vramTotalGB: 80,
    tempC: 71,
    tempTrendC5m: 0.6,
    powerW: 280,
    powerCapW: 400,
    sparkline60s: makeSparkline(57, 8, 29),
    recentEvents: [],
  },
  // host-gpu-01 ── A100-04 (Whole, 정승호 Falcon) ───────────────────────────────
  {
    id: 'a100-04',
    label: 'A100-04',
    hostId: 'host-gpu-01',
    model: 'A100',
    mode: 'whole',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'a100-04-whole', profile: 'whole', profileWeight: 7,
        containerId: 'cont-falcon-01',
        user: { id: 'u-jung-seungho', name: '정승호' },
        model: { name: 'Falcon 40B', versionId: 'mv-falcon-40b' },
        computePct: 71, computePctSustained5m: 70, computePctSustained10m: 68, qualityState: null,
        queueDepth: 2, latencyP95Ms: 310, vramUsedGB: 52, vramTotalGB: 80,
      },
    ],
    computePct: 71,
    computePctP95_1h: 79,
    vramUsedGB: 52,
    vramTotalGB: 80,
    tempC: 73,
    tempTrendC5m: 0.3,
    powerW: 380,
    powerCapW: 400,
    sparkline60s: makeSparkline(71, 6, 31),
    recentEvents: [],
  },
  // host-gpu-01 ── L40S-01 (Whole, 한지원 Yi 34B) ────────────────────────────────
  {
    id: 'l40s-01',
    label: 'L40S-01',
    hostId: 'host-gpu-01',
    model: 'L40S',
    mode: 'whole',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'l40s-01-whole', profile: 'whole', profileWeight: 7,
        containerId: 'cont-yi-01',
        user: { id: 'u-han-jiwon', name: '한지원' },
        model: { name: 'Yi 34B', versionId: 'mv-yi-34b' },
        computePct: 38, computePctSustained5m: 41, computePctSustained10m: 39, qualityState: null,
        queueDepth: 0, latencyP95Ms: 145, vramUsedGB: 28, vramTotalGB: 48,
      },
    ],
    computePct: 38,
    computePctP95_1h: 52,
    vramUsedGB: 28,
    vramTotalGB: 48,
    tempC: 64,
    tempTrendC5m: 0.1,
    powerW: 240,
    powerCapW: 350,
    sparkline60s: makeSparkline(38, 7, 37),
    recentEvents: [],
  },
  // host-gpu-01 ── H100-06 (MIG 5 slice, weight 2+2+1+1+1=7) ────────────────────
  {
    id: 'h100-06',
    label: 'H100-06',
    hostId: 'host-gpu-01',
    model: 'H100',
    mode: 'mig',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'h100-06-s1', profile: '2g.20gb', profileWeight: 2,
        containerId: 'cont-mixtral-01',
        user: { id: 'u-kang-seoah', name: '강서아' },
        model: { name: 'Mixtral 8x7B', versionId: 'mv-mixtral-8x7b' },
        computePct: 62, computePctSustained5m: 60, computePctSustained10m: 58, qualityState: null,
        queueDepth: 1, latencyP95Ms: 198, vramUsedGB: 18, vramTotalGB: 20,
      },
      {
        id: 'h100-06-s2', profile: '2g.20gb', profileWeight: 2,
        containerId: 'cont-mixtral-01',
        user: { id: 'u-kang-seoah', name: '강서아' },
        model: { name: 'Mixtral 8x7B', versionId: 'mv-mixtral-8x7b' },
        computePct: 59, computePctSustained5m: 61, computePctSustained10m: 60, qualityState: null,
        queueDepth: 1, latencyP95Ms: 205, vramUsedGB: 18, vramTotalGB: 20,
      },
      {
        id: 'h100-06-s3', profile: '1g.10gb', profileWeight: 1,
        containerId: 'cont-bge-01',
        user: { id: 'u-oh-minseo', name: '오민서' },
        model: { name: 'BGE-M3 임베딩', versionId: 'mv-bge-m3' },
        computePct: 24, computePctSustained5m: 22, computePctSustained10m: 21, qualityState: null,
        queueDepth: 0, latencyP95Ms: 36, vramUsedGB: 6, vramTotalGB: 10,
      },
      emptySlice('h100-06-s4', '1g.10gb', 1, 10),
      emptySlice('h100-06-s5', '1g.10gb', 1, 10),
    ],
    computePct: 52,
    computePctP95_1h: 64,
    vramUsedGB: 42,
    vramTotalGB: 80,
    tempC: 72,
    tempTrendC5m: 0.3,
    powerW: 360,
    powerCapW: 700,
    sparkline60s: makeSparkline(52, 8, 41),
    recentEvents: [],
  },
  // host-gpu-01 ── H100-07 (Whole, 백지원 Hyperion 30B) ─────────────────────────
  {
    id: 'h100-07',
    label: 'H100-07',
    hostId: 'host-gpu-01',
    model: 'H100',
    mode: 'whole',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'h100-07-whole', profile: 'whole', profileWeight: 7,
        containerId: 'cont-hyperion-01',
        user: { id: 'u-baek-jiwon', name: '백지원' },
        model: { name: 'Hyperion 30B', versionId: 'mv-hyperion-30b' },
        computePct: 84, computePctSustained5m: 82, computePctSustained10m: 80, qualityState: null,
        queueDepth: 2, latencyP95Ms: 412, vramUsedGB: 64, vramTotalGB: 80,
      },
    ],
    computePct: 84,
    computePctP95_1h: 88,
    vramUsedGB: 64,
    vramTotalGB: 80,
    tempC: 79,
    tempTrendC5m: 0.5,
    powerW: 580,
    powerCapW: 700,
    sparkline60s: makeSparkline(84, 5, 43),
    recentEvents: [],
  },
  // host-gpu-01 ── H100-08 (MIG 7, idle_waste seed on s1) ───────────────────────
  {
    id: 'h100-08',
    label: 'H100-08',
    hostId: 'host-gpu-01',
    model: 'H100',
    mode: 'mig',
    severity: 'warn',
    incident: null,
    slices: [
      {
        id: 'h100-08-s1', profile: '3g.40gb', profileWeight: 3,
        containerId: 'cont-sandbox-01',
        user: { id: 'u-jang-haru', name: '장하루' },
        model: { name: '실험용 (점유만)', versionId: 'mv-sandbox' },
        computePct: 4, computePctSustained5m: 5, computePctSustained10m: 6,
        qualityState: 'idle_waste',
        queueDepth: 0, latencyP95Ms: null,
        vramUsedGB: 9, vramTotalGB: 40,
      },
      {
        id: 'h100-08-s2', profile: '1g.10gb', profileWeight: 1,
        containerId: 'cont-whisper-01',
        user: { id: 'u-noh-yura', name: '노유라' },
        model: { name: 'Whisper Large v3', versionId: 'mv-whisper-l3' },
        computePct: 31, computePctSustained5m: 28, computePctSustained10m: 27, qualityState: null,
        queueDepth: 0, latencyP95Ms: 88, vramUsedGB: 7, vramTotalGB: 10,
      },
      emptySlice('h100-08-s3', '1g.10gb', 1, 10),
      emptySlice('h100-08-s4', '1g.10gb', 1, 10),
      emptySlice('h100-08-s5', '1g.10gb', 1, 10),
    ],
    computePct: 11,
    computePctP95_1h: 22,
    vramUsedGB: 16,
    vramTotalGB: 80,
    tempC: 58,
    tempTrendC5m: 0,
    powerW: 180,
    powerCapW: 700,
    sparkline60s: makeSparkline(11, 4, 47),
    recentEvents: [],
  },
  // host-gpu-01 ── A100-05 (Whole, 윤서아 Bart Large) ────────────────────────────
  {
    id: 'a100-05',
    label: 'A100-05',
    hostId: 'host-gpu-01',
    model: 'A100',
    mode: 'whole',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'a100-05-whole', profile: 'whole', profileWeight: 7,
        containerId: 'cont-bart-01',
        user: { id: 'u-yoon-seoa', name: '윤서아' },
        model: { name: 'BART Large', versionId: 'mv-bart-large' },
        computePct: 46, computePctSustained5m: 44, computePctSustained10m: 42, qualityState: null,
        queueDepth: 0, latencyP95Ms: 168, vramUsedGB: 38, vramTotalGB: 80,
      },
    ],
    computePct: 46,
    computePctP95_1h: 55,
    vramUsedGB: 38,
    vramTotalGB: 80,
    tempC: 68,
    tempTrendC5m: 0.1,
    powerW: 240,
    powerCapW: 400,
    sparkline60s: makeSparkline(46, 6, 53),
    recentEvents: [],
  },
  // host-gpu-01 ── A100-06 (MIG, xid_ecc_error 누적 — warn) ──────────────────────
  {
    id: 'a100-06',
    label: 'A100-06',
    hostId: 'host-gpu-01',
    model: 'A100',
    mode: 'mig',
    severity: 'warn',
    incident: 'xid_ecc_error',
    slices: [
      {
        id: 'a100-06-s1', profile: '2g.20gb', profileWeight: 2,
        containerId: 'cont-roberta-01',
        user: { id: 'u-han-jiwon', name: '한지원' },
        model: { name: 'RoBERTa Large', versionId: 'mv-roberta-large' },
        computePct: 38, computePctSustained5m: 36, computePctSustained10m: 35, qualityState: null,
        queueDepth: 0, latencyP95Ms: 76, vramUsedGB: 15, vramTotalGB: 20,
      },
      emptySlice('a100-06-s2', '1g.10gb', 1, 10),
      emptySlice('a100-06-s3', '1g.10gb', 1, 10),
      emptySlice('a100-06-s4', '1g.10gb', 1, 10),
      emptySlice('a100-06-s5', '1g.10gb', 1, 10),
      emptySlice('a100-06-s6', '1g.10gb', 1, 10),
    ],
    computePct: 38,
    computePctP95_1h: 48,
    vramUsedGB: 15,
    vramTotalGB: 80,
    tempC: 74,
    tempTrendC5m: 0.4,
    powerW: 220,
    powerCapW: 400,
    sparkline60s: makeSparkline(38, 6, 59),
    recentEvents: [],
  },
  // host-gpu-01 ── L40S-02 (Whole, 오영민 SDXL) ──────────────────────────────────
  {
    id: 'l40s-02',
    label: 'L40S-02',
    hostId: 'host-gpu-01',
    model: 'L40S',
    mode: 'whole',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'l40s-02-whole', profile: 'whole', profileWeight: 7,
        containerId: 'cont-sdxl-01',
        user: { id: 'u-oh-youngmin', name: '오영민' },
        model: { name: 'Stable Diffusion XL', versionId: 'mv-sdxl' },
        computePct: 72, computePctSustained5m: 70, computePctSustained10m: 68, qualityState: null,
        queueDepth: 3, latencyP95Ms: 1840, vramUsedGB: 33, vramTotalGB: 48,
      },
    ],
    computePct: 72,
    computePctP95_1h: 81,
    vramUsedGB: 33,
    vramTotalGB: 48,
    tempC: 76,
    tempTrendC5m: 0.6,
    powerW: 310,
    powerCapW: 350,
    sparkline60s: makeSparkline(72, 9, 61),
    recentEvents: [],
  },
  // host-gpu-02 ── RTX 4090-02 (Whole, 김도현 CodeLlama 13B) ────────────────────
  {
    id: 'rtx4090-02',
    label: 'RTX 4090-02',
    hostId: 'host-gpu-02',
    model: 'RTX 4090',
    mode: 'whole',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'rtx4090-02-whole', profile: 'whole', profileWeight: 7,
        containerId: 'cont-codellama13-01',
        user: { id: 'u-kim-dohyun', name: '김도현' },
        model: { name: 'CodeLlama 13B', versionId: 'mv-codellama-13b' },
        computePct: 41, computePctSustained5m: 39, computePctSustained10m: 38, qualityState: null,
        queueDepth: 0, latencyP95Ms: 96, vramUsedGB: 13, vramTotalGB: 24,
      },
    ],
    computePct: 41,
    computePctP95_1h: 52,
    vramUsedGB: 13,
    vramTotalGB: 24,
    tempC: 66,
    tempTrendC5m: 0.2,
    powerW: 240,
    powerCapW: 450,
    sparkline60s: makeSparkline(41, 7, 67),
    recentEvents: [],
  },
  // host-gpu-02 ── RTX 4090-03 (Whole, 비어 있음 — 가용 자원) ─────────────────────
  {
    id: 'rtx4090-03',
    label: 'RTX 4090-03',
    hostId: 'host-gpu-02',
    model: 'RTX 4090',
    mode: 'whole',
    severity: 'ok',
    incident: null,
    slices: [emptySlice('rtx4090-03-whole', 'whole', 7, 24)],
    computePct: 0,
    computePctP95_1h: 4,
    vramUsedGB: 0,
    vramTotalGB: 24,
    tempC: 42,
    tempTrendC5m: 0,
    powerW: 38,
    powerCapW: 450,
    sparkline60s: makeSparkline(2, 1, 71),
    recentEvents: [],
  },
  // host-gpu-03 ── H100-04 (Whole, host_offline override) ───────────────────────
  {
    id: 'h100-04',
    label: 'H100-04',
    hostId: 'host-gpu-03',
    model: 'H100',
    mode: 'whole',
    severity: 'offline', // override by host
    incident: 'host_offline',
    slices: [emptySlice('h100-04-whole', 'whole', 7, 80)],
    computePct: null,
    computePctP95_1h: null,
    vramUsedGB: 0,
    vramTotalGB: 80,
    tempC: null,
    tempTrendC5m: 0,
    powerW: null,
    powerCapW: 700,
    sparkline60s: flatLowSparkline(),
    recentEvents: [],
  },
  // host-gpu-03 ── H100-05 (MIG, mig_reconfiguring + host_offline override) ─────
  {
    id: 'h100-05',
    label: 'H100-05',
    hostId: 'host-gpu-03',
    model: 'H100',
    mode: 'mig',
    severity: 'offline',
    incident: 'mig_reconfiguring',
    slices: [
      emptySlice('h100-05-s1', '1g.10gb', 1, 10),
      emptySlice('h100-05-s2', '2g.20gb', 2, 20),
    ],
    computePct: null,
    computePctP95_1h: null,
    vramUsedGB: 0,
    vramTotalGB: 80,
    tempC: null,
    tempTrendC5m: 0,
    powerW: null,
    powerCapW: 700,
    sparkline60s: flatLowSparkline(),
    recentEvents: [],
  },
  // host-gpu-04 ── A100-01 (MIG, mixed alloc) ───────────────────────────────────
  {
    id: 'a100-01',
    label: 'A100-01',
    hostId: 'host-gpu-04',
    model: 'A100',
    mode: 'mig',
    severity: 'ok',
    incident: null,
    slices: [
      {
        id: 'a100-01-s1', profile: '1g.10gb', profileWeight: 1,
        containerId: 'cont-phi3-01',
        user: { id: 'u-jeong', name: '정다은' },
        model: { name: 'Phi-3 Mini', versionId: 'mv-phi3-mini' },
        computePct: 12, computePctSustained5m: 14, computePctSustained10m: 13, qualityState: null,
        queueDepth: 0, latencyP95Ms: 42, vramUsedGB: 8, vramTotalGB: 10,
      },
      emptySlice('a100-01-s2', '1g.10gb', 1, 10),
      emptySlice('a100-01-s3', '1g.10gb', 1, 10),
      emptySlice('a100-01-s4', '1g.10gb', 1, 10),
      emptySlice('a100-01-s5', '1g.10gb', 1, 10),
      emptySlice('a100-01-s6', '1g.10gb', 1, 10),
      emptySlice('a100-01-s7', '1g.10gb', 1, 10),
    ],
    computePct: 12,
    computePctP95_1h: 18,
    vramUsedGB: 8,
    vramTotalGB: 80,
    tempC: 62,
    tempTrendC5m: -0.1,
    powerW: 180,
    powerCapW: 400,
    sparkline60s: makeSparkline(12, 4, 19),
    recentEvents: [],
  },
  // host-gpu-04 ── A100-02 (MIG, idle_waste seed) ───────────────────────────────
  {
    id: 'a100-02',
    label: 'A100-02',
    hostId: 'host-gpu-04',
    model: 'A100',
    mode: 'mig',
    severity: 'warn', // derived from idle_waste
    incident: null,
    slices: [
      {
        id: 'a100-02-s1', profile: '2g.20gb', profileWeight: 2,
        containerId: 'cont-gemma-01',
        user: { id: 'u-jeong', name: '정다은' },
        model: { name: 'Gemma 7B', versionId: 'mv-gemma-7b' },
        computePct: 3, computePctSustained5m: 8, computePctSustained10m: 12,
        qualityState: 'idle_waste',
        queueDepth: 0, latencyP95Ms: 30,
        vramUsedGB: 5, vramTotalGB: 20,
      },
      emptySlice('a100-02-s2', '1g.10gb', 1, 10),
      emptySlice('a100-02-s3', '1g.10gb', 1, 10),
    ],
    computePct: 3,
    computePctP95_1h: 7,
    vramUsedGB: 5,
    vramTotalGB: 40,
    tempC: 31,
    tempTrendC5m: 0,
    powerW: 38,
    powerCapW: 400,
    sparkline60s: makeSparkline(5, 3, 23),
    recentEvents: [],
  },
];

// ─── events (global timeline + per-GPU mirror) ────────────────────────────────
export const EVENTS: EventMock[] = [
  {
    ts: isoAt(0),
    kind: 'driver_error',
    source: 'resource_event',
    severity: 'error',
    gpuId: 'h100-03',
    hostId: 'host-gpu-01',
    message: 'NVRM Xid (PCI:0000:01:00): 79, GPU has fallen off the bus.',
  },
  {
    ts: isoAt(-2),
    kind: 'host_offline',
    source: 'agent_heartbeat',
    severity: 'error',
    hostId: 'host-gpu-03',
    message: 'Agent heartbeat missing for 5m32s; host marked offline.',
  },
  {
    ts: isoAt(-4),
    kind: 'oom',
    source: 'container_event',
    severity: 'error',
    gpuId: 'h100-02',
    hostId: 'host-gpu-01',
    containerId: 'cont-qwen2-01',
    message: 'Container cont-qwen2-01 killed by OOMKiller (exit 137).',
  },
  {
    ts: isoAt(-6),
    kind: 'mig_reconfiguring',
    source: 'allocation_service',
    severity: 'warn',
    gpuId: 'h100-05',
    hostId: 'host-gpu-03',
    message: 'MIG reconfigure 1g→2g requested; instances draining.',
  },
  {
    ts: isoAt(-8),
    kind: 'allocation_failed',
    source: 'allocation_service',
    severity: 'warn',
    requestId: 'REQ-008',
    message: 'No free MIG slice matching 3g.40gb on any online host.',
  },
  {
    ts: isoAt(-12),
    kind: 'xid_ecc_error',
    source: 'synthetic',
    severity: 'warn',
    gpuId: 'h100-01',
    hostId: 'host-gpu-01',
    message: '[mock-only] XID 48 (DBE ECC) recorded once; auto-recovered.',
  },
  {
    ts: isoAt(-15),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'a100-01',
    requestId: 'REQ-003',
    message: 'Slice a100-01-s1 (1g.10gb) allocated to REQ-003 (정다은).',
  },
  {
    ts: isoAt(-22),
    kind: 'health_unhealthy',
    source: 'container_event',
    severity: 'warn',
    containerId: 'cont-mistral-01',
    gpuId: 'h100-01',
    message: 'Container cont-mistral-01 health=unhealthy (3 consecutive failures).',
  },
  {
    ts: isoAt(-28),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'a100-03',
    requestId: 'REQ-011',
    message: 'Slice a100-03-s1 (2g.20gb) allocated to REQ-011 (박소연).',
  },
  {
    ts: isoAt(-33),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'a100-04',
    requestId: 'REQ-012',
    message: 'Slice a100-04-whole allocated to REQ-012 (정승호).',
  },
  {
    ts: isoAt(-45),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'l40s-01',
    requestId: 'REQ-013',
    message: 'Slice l40s-01-whole allocated to REQ-013 (한지원).',
  },
  {
    ts: isoAt(-52),
    kind: 'released',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'a100-01',
    message: '정다은 님이 a100-01-s2 (1g.10gb) 슬라이스 사용을 종료했습니다.',
  },
  {
    ts: isoAt(-3),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'h100-01',
    requestId: 'REQ-014',
    message: '김민준 님이 h100-01 에 1g.10gb 슬라이스 1개 추가 신청 → 자동 승인.',
  },
  {
    ts: isoAt(-7),
    kind: 'health_unhealthy',
    source: 'container_event',
    severity: 'warn',
    containerId: 'cont-qwen2-01',
    gpuId: 'h100-02',
    message: 'Qwen2 72B 가 H100-02 에서 sustained 90% 5분 진입 — 포화 위험.',
  },
  {
    ts: isoAt(-11),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'a100-03',
    requestId: 'REQ-011',
    message: '박소연 님이 a100-03 에 2g.20gb 슬라이스 2개 신청 → 승인.',
  },
  {
    ts: isoAt(-14),
    kind: 'mig_reconfiguring',
    source: 'allocation_service',
    severity: 'warn',
    gpuId: 'a100-03',
    message: 'A100-03 MIG profile 재구성 (1g×4 → 2g×2 + 1g×2). 약 2초 소요.',
  },
  {
    ts: isoAt(-18),
    kind: 'oom',
    source: 'container_event',
    severity: 'error',
    containerId: 'cont-falcon-test',
    gpuId: 'a100-04',
    message: '정승호 님의 cont-falcon-test 가 OOM 종료 (78GB / 80GB 초과 시도).',
  },
  {
    ts: isoAt(-25),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'l40s-01',
    requestId: 'REQ-013',
    message: '한지원 님이 l40s-01 전체 슬라이스 신청 → 승인 (Yi 34B 로드).',
  },
  {
    ts: isoAt(-31),
    kind: 'released',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'h100-01',
    message: '이서연 님이 h100-01-s7 (1g.10gb) 슬라이스 회수.',
  },
  {
    ts: isoAt(-36),
    kind: 'allocation_failed',
    source: 'allocation_service',
    severity: 'warn',
    gpuId: 'h100-02',
    requestId: 'REQ-009',
    message: 'H100-02 에 3g.40gb 슬라이스 신청 실패 — 이미 Whole 점유 중.',
  },
  {
    ts: isoAt(-5),
    kind: 'xid_ecc_error',
    source: 'agent_heartbeat',
    severity: 'warn',
    gpuId: 'a100-06',
    hostId: 'host-gpu-01',
    message: 'A100-06 에서 XID 63 (ECC) 3회 누적 — 교체 검토 권장.',
  },
  {
    ts: isoAt(-9),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'h100-06',
    requestId: 'REQ-015',
    message: '강서아 님이 h100-06 에 2g.20gb 슬라이스 2개 신청 → 승인 (Mixtral 8x7B).',
  },
  {
    ts: isoAt(-13),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'h100-07',
    requestId: 'REQ-016',
    message: '백지원 님이 h100-07 전체 슬라이스 신청 → 승인 (Hyperion 30B).',
  },
  {
    ts: isoAt(-17),
    kind: 'health_unhealthy',
    source: 'container_event',
    severity: 'warn',
    gpuId: 'h100-08',
    containerId: 'cont-sandbox-01',
    message: '장하루 님의 cont-sandbox-01 가 10분 평균 5% 사용 — 자원 회수 후보.',
  },
  {
    ts: isoAt(-19),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'l40s-02',
    requestId: 'REQ-017',
    message: '오영민 님이 l40s-02 전체 슬라이스 신청 → 승인 (SDXL 이미지 생성).',
  },
  {
    ts: isoAt(-24),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'rtx4090-02',
    requestId: 'REQ-018',
    message: '김도현 님이 rtx4090-02 전체 슬라이스 신청 → 승인 (CodeLlama 13B).',
  },
  {
    ts: isoAt(-26),
    kind: 'released',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'rtx4090-03',
    message: 'RTX 4090-03 슬라이스 회수 — 가용 자원으로 복귀.',
  },
  {
    ts: isoAt(-35),
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'a100-05',
    requestId: 'REQ-019',
    message: '윤서아 님이 a100-05 전체 슬라이스 신청 → 승인 (BART Large).',
  },
  // ─── 신청 → 승인 → 생성 → 모델 로드 흐름 (사용자 별) ───────────────────────────
  {
    ts: isoAt(-1),
    kind: 'requested',
    source: 'allocation_service',
    severity: 'ok',
    requestId: 'REQ-020',
    message: '강서아 님이 h100-06 에 1g.10gb 슬라이스 1개 추가 신청 (BGE-M3 임베딩 워크로드).',
  },
  {
    ts: isoAt(-1.5),
    kind: 'approved',
    source: 'allocation_service',
    severity: 'ok',
    requestId: 'REQ-020',
    gpuId: 'h100-06',
    hostId: 'host-gpu-01',
    message: 'admin 님이 REQ-020 승인 → 강서아 님 신청 통과.',
  },
  {
    ts: isoAt(-10),
    kind: 'requested',
    source: 'allocation_service',
    severity: 'ok',
    requestId: 'REQ-021',
    message: '김도현 님이 RTX 4090 1대 통째 신청 (CodeLlama 13B 추론, 7일).',
  },
  {
    ts: isoAt(-11),
    kind: 'approved',
    source: 'allocation_service',
    severity: 'ok',
    requestId: 'REQ-021',
    gpuId: 'rtx4090-02',
    hostId: 'host-gpu-02',
    message: 'admin 님이 REQ-021 승인 → 김도현 님에게 rtx4090-02 배정.',
  },
  {
    ts: isoAt(-11.2),
    kind: 'container_created',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-codellama13-01',
    gpuId: 'rtx4090-02',
    message: '김도현 님 컨테이너 cont-codellama13-01 생성 (이미지: vllm/vllm-openai:0.6.3).',
  },
  {
    ts: isoAt(-11.4),
    kind: 'container_started',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-codellama13-01',
    gpuId: 'rtx4090-02',
    message: 'cont-codellama13-01 시작 — 포트 8080 노출, healthcheck 통과.',
  },
  {
    ts: isoAt(-11.7),
    kind: 'model_loaded',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-codellama13-01',
    gpuId: 'rtx4090-02',
    message: 'CodeLlama 13B 모델 로드 완료 (13.0 GB VRAM, 38초 소요).',
  },
  // ─── 마켓 공유 흐름 ──────────────────────────────────────────────────────────
  {
    ts: isoAt(-16),
    kind: 'market_shared',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'h100-07',
    message: '백지원 님이 Hyperion 30B 모델을 마켓에 공개 — 사내 누구나 호출 가능.',
  },
  {
    ts: isoAt(-30),
    kind: 'market_shared',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'h100-06',
    message: '오민서 님이 BGE-M3 임베딩 마켓 공개 — 검색팀 등 18,650회 호출 도달.',
  },
  {
    ts: isoAt(-40),
    kind: 'market_unshared',
    source: 'allocation_service',
    severity: 'warn',
    gpuId: 'a100-04',
    message: '정승호 님이 Falcon 40B 마켓 공유 중단 — 응답 지연으로 회수.',
  },
  // ─── 컨테이너 lifecycle ──────────────────────────────────────────────────────
  {
    ts: isoAt(-20),
    kind: 'container_stopped',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-llama3-old',
    gpuId: 'h100-01',
    message: '김민준 님이 cont-llama3-old 수동 중지 — 새 버전 컨테이너로 교체.',
  },
  {
    ts: isoAt(-21),
    kind: 'container_created',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-llama3-01',
    gpuId: 'h100-01',
    message: '김민준 님 새 컨테이너 cont-llama3-01 생성 (Llama 3 70B Q4, 3 슬라이스).',
  },
  {
    ts: isoAt(-21.3),
    kind: 'model_loaded',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-llama3-01',
    gpuId: 'h100-01',
    message: 'Llama 3 70B (Q4 양자화) 모델 로드 완료 (27.2 GB VRAM, 1분 12초).',
  },
  // ─── 신청 실패 / 반려 / 쿼터 ────────────────────────────────────────────────
  {
    ts: isoAt(-37),
    kind: 'rejected',
    source: 'allocation_service',
    severity: 'warn',
    requestId: 'REQ-022',
    message: 'admin 님이 REQ-022 반려 — 신청 사유 불명확 (장하루 님, 3g.40gb).',
  },
  {
    ts: isoAt(-44),
    kind: 'quota_exceeded',
    source: 'allocation_service',
    severity: 'warn',
    gpuId: 'a100-04',
    message: '정승호 님의 GPU 사용 총량이 개인 한도 80% 도달 — 추가 신청 시 승인 필요.',
  },
  // ─── 자동 복구 / 점검 ───────────────────────────────────────────────────────
  {
    ts: isoAt(-50),
    kind: 'auto_recovered',
    source: 'agent_heartbeat',
    severity: 'ok',
    gpuId: 'h100-01',
    hostId: 'host-gpu-01',
    message: 'XID 48 (DBE ECC) 1회 발생 후 자동 복구 — 워크로드 영향 없음.',
  },
  {
    ts: isoAt(-58),
    kind: 'maintenance',
    source: 'synthetic',
    severity: 'warn',
    hostId: 'host-gpu-03',
    message: 'Busan-A 호스트 점검 시작 — 드라이버 555.42 → 555.85 업그레이드 (예상 30분).',
  },
  // ─── 시간 단위 (3-12시간 전) ────────────────────────────────────────────────
  {
    ts: isoAt(-180), // 3시간 전
    kind: 'container_started',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-qwen2-01',
    gpuId: 'h100-02',
    message: '박지호 님이 Qwen2 72B 컨테이너 재시작 — VRAM 캐시 정리 후 복구.',
  },
  {
    ts: isoAt(-300), // 5시간 전
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'a100-06',
    requestId: 'REQ-018',
    message: '한지원 님이 a100-06 에 2g.20gb 슬라이스 신청 → 자동 승인 (RoBERTa Large).',
  },
  {
    ts: isoAt(-420), // 7시간 전
    kind: 'health_unhealthy',
    source: 'container_event',
    severity: 'warn',
    containerId: 'cont-sdxl-01',
    gpuId: 'l40s-02',
    message: 'cont-sdxl-01 응답 지연 1.8초 → 1.5분 동안 health=degraded, 자동 회복.',
  },
  {
    ts: isoAt(-600), // 10시간 전
    kind: 'model_loaded',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-hyperion-01',
    gpuId: 'h100-07',
    message: '백지원 님이 Hyperion 30B 모델을 첫 로드 — 64.0 GB VRAM, 2분 8초.',
  },
  // ─── 1-3일 전 ───────────────────────────────────────────────────────────────
  {
    ts: isoAt(-1440), // 1일 전
    kind: 'requested',
    source: 'allocation_service',
    severity: 'ok',
    requestId: 'REQ-016',
    message: '백지원 님이 H100 1대 통째 신청 — Hyperion 30B 추론 운영 (사용 기간 30일).',
  },
  {
    ts: isoAt(-1450),
    kind: 'approved',
    source: 'allocation_service',
    severity: 'ok',
    requestId: 'REQ-016',
    gpuId: 'h100-07',
    hostId: 'host-gpu-01',
    message: 'admin 님이 REQ-016 승인 — 백지원 님에게 h100-07 배정.',
  },
  {
    ts: isoAt(-1480),
    kind: 'container_created',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-hyperion-01',
    gpuId: 'h100-07',
    message: '백지원 님 컨테이너 cont-hyperion-01 생성 (이미지: tgi:2.3.1).',
  },
  {
    ts: isoAt(-2000), // 1.4일 전
    kind: 'market_shared',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'h100-06',
    message: '강서아 님이 Mixtral 8x7B 마켓 공개 — 첫 24시간 동안 5,230 회 호출.',
  },
  {
    ts: isoAt(-2880), // 2일 전
    kind: 'allocated',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'a100-04',
    requestId: 'REQ-012',
    message: '정승호 님이 A100 1대 통째 신청 → 승인 (Falcon 40B 학습 시작).',
  },
  {
    ts: isoAt(-3600), // 2.5일 전
    kind: 'maintenance',
    source: 'synthetic',
    severity: 'ok',
    hostId: 'host-gpu-01',
    message: 'Seoul-A 호스트 NVIDIA 드라이버 555.85 업데이트 완료 — 다운타임 12분.',
  },
  // ─── 4-7일 전 ───────────────────────────────────────────────────────────────
  {
    ts: isoAt(-5760), // 4일 전
    kind: 'container_stopped',
    source: 'container_event',
    severity: 'ok',
    containerId: 'cont-deepseek-old',
    gpuId: 'a100-03',
    message: '박소연 님이 DeepSeek 67B 이전 버전 (cont-deepseek-old) 중지 — 신모델 교체.',
  },
  {
    ts: isoAt(-7200), // 5일 전
    kind: 'market_shared',
    source: 'allocation_service',
    severity: 'ok',
    gpuId: 'h100-02',
    message: '박지호 님이 Qwen2 72B 마켓 공개 — 사내 추론 API 로 활용.',
  },
  {
    ts: isoAt(-8640), // 6일 전
    kind: 'requested',
    source: 'allocation_service',
    severity: 'ok',
    requestId: 'REQ-008',
    message: '오영민 님이 L40S 1대 통째 신청 — Stable Diffusion XL 이미지 생성 워크로드.',
  },
  {
    ts: isoAt(-10080), // 7일 전
    kind: 'approved',
    source: 'allocation_service',
    severity: 'ok',
    requestId: 'REQ-008',
    gpuId: 'l40s-02',
    hostId: 'host-gpu-01',
    message: 'admin 님이 REQ-008 승인 — 오영민 님에게 l40s-02 배정 (사용 기간 60일).',
  },
  // ─── H100-01 추가 활동 (다양 시간) ──────────────────────────────────────────
  { ts: isoAt(-45), kind: 'allocated', source: 'allocation_service', severity: 'ok', gpuId: 'h100-01', requestId: 'REQ-023', message: '이서연 님이 h100-01 에 1g.10gb 슬라이스 1개 추가 → 자동 승인 (Mistral 7B 인스턴스 증설).' },
  { ts: isoAt(-90), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'h100-01', containerId: 'cont-mistral-01', message: 'Mistral 7B v0.3 모델 로드 — 7.2 GB VRAM, 14초 소요.' },
  { ts: isoAt(-150), kind: 'container_started', source: 'container_event', severity: 'ok', gpuId: 'h100-01', containerId: 'cont-mistral-01', message: '이서연 님 cont-mistral-01 시작 — vLLM 0.6.3, port 8081.' },
  { ts: isoAt(-240), kind: 'released', source: 'allocation_service', severity: 'ok', gpuId: 'h100-01', message: '김민준 님이 h100-01-s4 슬라이스 자발 회수 — 메모리 절약.' },
  { ts: isoAt(-360), kind: 'auto_recovered', source: 'agent_heartbeat', severity: 'ok', gpuId: 'h100-01', hostId: 'host-gpu-01', message: 'XID 79 (PCIe link drop) 1회 발생, 0.4초 만에 자동 복구.' },
  { ts: isoAt(-720), kind: 'requested', source: 'allocation_service', severity: 'ok', requestId: 'REQ-014', message: '김민준 님이 h100-01 에 1g.10gb 슬라이스 1개 추가 신청 (Llama 3 70B 처리량 증설).' },
  { ts: isoAt(-1200), kind: 'approved', source: 'allocation_service', severity: 'ok', gpuId: 'h100-01', requestId: 'REQ-014', message: 'admin 님이 REQ-014 자동 승인 (개인 한도 내).' },
  { ts: isoAt(-1320), kind: 'market_shared', source: 'allocation_service', severity: 'ok', gpuId: 'h100-01', message: '김민준 님이 Llama 3 70B 마켓 공유 시작 — 첫 1시간에 412 회 호출 도달.' },
  { ts: isoAt(-2160), kind: 'health_unhealthy', source: 'container_event', severity: 'warn', gpuId: 'h100-01', containerId: 'cont-llama3-01', message: 'cont-llama3-01 healthcheck 1회 실패 → 즉시 자동 복구, 영향 없음.' },
  { ts: isoAt(-4320), kind: 'model_unloaded', source: 'container_event', severity: 'ok', gpuId: 'h100-01', message: '김민준 님이 이전 Llama 3 70B 모델 (Q8) 언로드 — Q4 양자화 버전으로 교체.' },
  { ts: isoAt(-5400), kind: 'requested', source: 'allocation_service', severity: 'ok', requestId: 'REQ-011', message: '이서연 님이 h100-01 에 1g.10gb 슬라이스 2개 신청 (Mistral 7B 추론 시작).' },
  { ts: isoAt(-5460), kind: 'approved', source: 'allocation_service', severity: 'ok', gpuId: 'h100-01', requestId: 'REQ-011', message: 'admin 님이 REQ-011 승인 — 이서연 님에게 h100-01-s6, s7 배정.' },
  { ts: isoAt(-5520), kind: 'container_created', source: 'container_event', severity: 'ok', gpuId: 'h100-01', containerId: 'cont-mistral-old', message: '이서연 님 첫 컨테이너 cont-mistral-old 생성.' },
  { ts: isoAt(-6480), kind: 'container_stopped', source: 'container_event', severity: 'ok', gpuId: 'h100-01', containerId: 'cont-mistral-old', message: '이서연 님이 이전 Mistral 컨테이너 (cont-mistral-old) 정리 — 신규 버전 생성.' },
  // ─── H100-02 (Whole, 포화) ─────────────────────────────────────────────────
  { ts: isoAt(-120), kind: 'quota_exceeded', source: 'allocation_service', severity: 'warn', gpuId: 'h100-02', message: '박지호 님 Qwen2 72B 가 GPU 100% 5분 지속 — 자동 알림 전송, 추가 인스턴스 권장.' },
  { ts: isoAt(-540), kind: 'auto_recovered', source: 'agent_heartbeat', severity: 'ok', gpuId: 'h100-02', message: 'OOMKiller 후 컨테이너 재시작 자동 완료 — 박지호 님 워크로드 복구.' },
  { ts: isoAt(-2520), kind: 'requested', source: 'allocation_service', severity: 'ok', requestId: 'REQ-009', message: '박지호 님이 H100 1대 통째 신청 (Qwen2 72B 추론).' },
  { ts: isoAt(-2580), kind: 'approved', source: 'allocation_service', severity: 'ok', gpuId: 'h100-02', requestId: 'REQ-009', message: 'admin 님이 REQ-009 승인 → 박지호 님에게 h100-02 통째 배정 (사용 기간 30일).' },
  // ─── A100-03 (박소연 DeepSeek) ─────────────────────────────────────────────
  { ts: isoAt(-95), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'a100-03', containerId: 'cont-deepseek-01', message: '박소연 님이 DeepSeek 67B 모델 재로드 — Q5 양자화, 33.4 GB VRAM, 1분 28초.' },
  { ts: isoAt(-700), kind: 'market_shared', source: 'allocation_service', severity: 'ok', gpuId: 'a100-03', message: '박소연 님이 DeepSeek 67B 마켓 공개 → 6,840 회 누적 호출 (7일).' },
  { ts: isoAt(-2700), kind: 'mig_reconfiguring', source: 'allocation_service', severity: 'warn', gpuId: 'a100-03', message: 'A100-03 MIG profile 재구성 (4 slice → 2g×2 + 1g×3 → 2g×2 + 1g×1). 약 6초 소요.' },
  { ts: isoAt(-4800), kind: 'container_created', source: 'container_event', severity: 'ok', gpuId: 'a100-03', containerId: 'cont-deepseek-01', message: '박소연 님 컨테이너 cont-deepseek-01 생성 (DeepSeek 67B).' },
  // ─── A100-04 (정승호 Falcon) ──────────────────────────────────────────────
  { ts: isoAt(-180), kind: 'oom', source: 'container_event', severity: 'error', gpuId: 'a100-04', containerId: 'cont-falcon-test', message: '정승호 님 cont-falcon-test 가 OOM 종료 (78GB / 80GB 초과 시도).' },
  { ts: isoAt(-900), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'a100-04', containerId: 'cont-falcon-01', message: 'Falcon 40B 모델 로드 완료 — 52.0 GB VRAM, 2분 4초.' },
  { ts: isoAt(-1080), kind: 'container_started', source: 'container_event', severity: 'ok', gpuId: 'a100-04', containerId: 'cont-falcon-01', message: '정승호 님 cont-falcon-01 시작 — TGI 2.3.1.' },
  { ts: isoAt(-3300), kind: 'requested', source: 'allocation_service', severity: 'ok', requestId: 'REQ-012', message: '정승호 님이 A100 1대 통째 신청 (Falcon 40B 학습).' },
  // ─── L40S-01 (한지원 Yi 34B) ──────────────────────────────────────────────
  { ts: isoAt(-200), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'l40s-01', containerId: 'cont-yi-01', message: 'Yi 34B 모델 로드 완료 — 28.0 GB VRAM, 52초 소요.' },
  { ts: isoAt(-560), kind: 'market_unshared', source: 'allocation_service', severity: 'warn', gpuId: 'l40s-01', message: '한지원 님이 Yi 34B 마켓 공유 중단 — 개인 실험 전환.' },
  { ts: isoAt(-1620), kind: 'container_created', source: 'container_event', severity: 'ok', gpuId: 'l40s-01', containerId: 'cont-yi-01', message: '한지원 님 cont-yi-01 생성 (Yi 34B).' },
  { ts: isoAt(-2700), kind: 'allocated', source: 'allocation_service', severity: 'ok', gpuId: 'l40s-01', requestId: 'REQ-013', message: '한지원 님이 l40s-01 전체 슬라이스 신청 → 승인 (Yi 34B 로드).' },
  // ─── H100-06 (강서아 Mixtral + 오민서 BGE-M3) ──────────────────────────────
  { ts: isoAt(-65), kind: 'auto_recovered', source: 'agent_heartbeat', severity: 'ok', gpuId: 'h100-06', message: 'cont-mixtral-01 일시 응답 지연 → 30초 만에 자동 복구.' },
  { ts: isoAt(-280), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'h100-06', containerId: 'cont-bge-01', message: '오민서 님이 BGE-M3 임베딩 모델 로드 — 6.4 GB VRAM, 8초.' },
  { ts: isoAt(-840), kind: 'container_started', source: 'container_event', severity: 'ok', gpuId: 'h100-06', containerId: 'cont-mixtral-01', message: '강서아 님 cont-mixtral-01 시작 — vLLM 0.6.3, 멀티 GPU 슬라이스 활용.' },
  { ts: isoAt(-1800), kind: 'allocated', source: 'allocation_service', severity: 'ok', gpuId: 'h100-06', requestId: 'REQ-015', message: '강서아 님이 h100-06 에 2g.20gb 슬라이스 2개 신청 → 승인 (Mixtral 8x7B).' },
  // ─── H100-07 (백지원 Hyperion) ─────────────────────────────────────────────
  { ts: isoAt(-150), kind: 'auto_recovered', source: 'agent_heartbeat', severity: 'ok', gpuId: 'h100-07', message: 'XID 31 (memory error) 1회 발생 후 자동 복구.' },
  { ts: isoAt(-420), kind: 'health_unhealthy', source: 'container_event', severity: 'warn', gpuId: 'h100-07', containerId: 'cont-hyperion-01', message: 'cont-hyperion-01 응답 시간 0.8초 초과 (정상 0.4초) — 워밍업 추정.' },
  // ─── H100-08 (장하루 sandbox + 노유라 Whisper) ──────────────────────────────
  { ts: isoAt(-90), kind: 'health_unhealthy', source: 'container_event', severity: 'warn', gpuId: 'h100-08', containerId: 'cont-sandbox-01', message: '장하루 님 cont-sandbox-01 가 10분 평균 5% 미만 사용 → 자원 회수 후보 안내.' },
  { ts: isoAt(-360), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'h100-08', containerId: 'cont-whisper-01', message: '노유라 님이 Whisper Large v3 로드 — 6.8 GB VRAM, 12초.' },
  // ─── A100-05 (윤서아 BART) ─────────────────────────────────────────────────
  { ts: isoAt(-1500), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'a100-05', containerId: 'cont-bart-01', message: '윤서아 님이 BART Large 로드 — 38.0 GB VRAM, 1분 16초.' },
  // ─── A100-06 (한지원 RoBERTa + XID/ECC) ────────────────────────────────────
  { ts: isoAt(-220), kind: 'xid_ecc_error', source: 'agent_heartbeat', severity: 'warn', gpuId: 'a100-06', hostId: 'host-gpu-01', message: 'XID 63 (page retirement) 2회 누적 — 임계치 5회 도달 시 교체 권장.' },
  { ts: isoAt(-1380), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'a100-06', containerId: 'cont-roberta-01', message: '한지원 님이 RoBERTa Large 로드 — 15.0 GB VRAM, 22초.' },
  // ─── L40S-02 (오영민 SDXL) ────────────────────────────────────────────────
  { ts: isoAt(-110), kind: 'quota_exceeded', source: 'allocation_service', severity: 'warn', gpuId: 'l40s-02', message: '오영민 님 SDXL 작업이 대기열 3건 초과 — 추가 인스턴스 권장.' },
  { ts: isoAt(-1100), kind: 'model_loaded', source: 'container_event', severity: 'ok', gpuId: 'l40s-02', containerId: 'cont-sdxl-01', message: 'Stable Diffusion XL 모델 로드 — 33.0 GB VRAM, 1분 6초.' },
];

// Per-GPU mirror — last 8 events touching each GPU.
for (const gpu of GPUS) {
  // host-level event (host_offline / maintenance) 도 그 host 의 모든 GPU 에 mirror.
  const HOST_LEVEL: EventKind[] = ['host_offline', 'maintenance'];
  gpu.recentEvents = EVENTS
    .filter((e) => e.gpuId === gpu.id || (e.hostId === gpu.hostId && HOST_LEVEL.includes(e.kind)))
    .sort((a, b) => b.ts.localeCompare(a.ts)) // 최신 우선
    .slice(0, 40);
}

// ─── side panel fixtures ──────────────────────────────────────────────────────
export const REQ_VRAM_SHARES: ReqVramShare[] = [
  { reqId: 'REQ-001', user: '김민준', gpuLabel: 'H100×3 slice (1g×5)', usedGB: 43, totalGB: 50 },
  { reqId: 'REQ-002', user: '이서연', gpuLabel: 'H100-01 slice (1g×2)', usedGB: 16, totalGB: 20 },
  { reqId: 'REQ-003', user: '박지호', gpuLabel: 'H100-02 Whole', usedGB: 72, totalGB: 80 },
  { reqId: 'REQ-004', user: '최유진', gpuLabel: 'RTX 4090-01 Whole', usedGB: 19, totalGB: 24 },
  { reqId: 'REQ-005', user: '정다은', gpuLabel: 'A100-01 slice (1g×1)', usedGB: 8, totalGB: 10 },
  { reqId: 'REQ-006', user: '정다은', gpuLabel: 'A100-02 slice (2g×1)', usedGB: 5, totalGB: 20 },
  { reqId: 'REQ-011', user: '박소연', gpuLabel: 'A100-03 slice (2g×2)', usedGB: 34, totalGB: 40 },
  { reqId: 'REQ-012', user: '정승호', gpuLabel: 'A100-04 Whole', usedGB: 52, totalGB: 80 },
  { reqId: 'REQ-013', user: '한지원', gpuLabel: 'L40S-01 Whole', usedGB: 28, totalGB: 48 },
];

export const MOUNTED_MODELS: MountedModel[] = [
  {
    modelName: 'Llama 3 70B', modelVersionId: 'mv-llama3-70b', modelAssetId: 'ma-llama3-70b',
    mountedOn: [{ gpuLabel: 'H100-01', containerId: 'cont-llama3-01', user: '김민준' }],
    marketSharedAt: '2026-05-12T10:00:00Z', marketCalls7d: 8420,
  },
  {
    modelName: 'Mistral 7B', modelVersionId: 'mv-mistral-7b', modelAssetId: 'ma-mistral-7b',
    mountedOn: [{ gpuLabel: 'H100-01', containerId: 'cont-mistral-01', user: '이서연' }],
    marketSharedAt: '2026-04-28T09:30:00Z', marketCalls7d: 3210,
  },
  {
    modelName: 'Qwen2 72B', modelVersionId: 'mv-qwen2-72b', modelAssetId: 'ma-qwen2-72b',
    mountedOn: [{ gpuLabel: 'H100-02', containerId: 'cont-qwen2-01', user: '박지호' }],
    marketSharedAt: '2026-05-20T14:15:00Z', marketCalls7d: 12400,
  },
  {
    modelName: 'CodeLlama 34B', modelVersionId: 'mv-codellama-34b', modelAssetId: 'ma-codellama-34b',
    mountedOn: [{ gpuLabel: 'RTX 4090-01', containerId: 'cont-codellama-01', user: '최유진' }],
    marketSharedAt: '2026-05-05T11:00:00Z', marketCalls7d: 1820,
  },
  {
    modelName: 'Phi-3 Mini', modelVersionId: 'mv-phi3-mini', modelAssetId: 'ma-phi3-mini',
    mountedOn: [{ gpuLabel: 'A100-01', containerId: 'cont-phi3-01', user: '정다은' }],
    marketSharedAt: null, marketCalls7d: 0,
  },
  {
    modelName: 'Gemma 7B', modelVersionId: 'mv-gemma-7b', modelAssetId: 'ma-gemma-7b',
    mountedOn: [{ gpuLabel: 'A100-02', containerId: 'cont-gemma-01', user: '정다은' }],
    marketSharedAt: null, marketCalls7d: 0,
  },
  {
    modelName: 'DeepSeek 67B', modelVersionId: 'mv-deepseek-67b', modelAssetId: 'ma-deepseek-67b',
    mountedOn: [{ gpuLabel: 'A100-03', containerId: 'cont-deepseek-01', user: '박소연' }],
    marketSharedAt: '2026-05-18T09:00:00Z', marketCalls7d: 6840,
  },
  {
    modelName: 'Falcon 40B', modelVersionId: 'mv-falcon-40b', modelAssetId: 'ma-falcon-40b',
    mountedOn: [{ gpuLabel: 'A100-04', containerId: 'cont-falcon-01', user: '정승호' }],
    marketSharedAt: '2026-05-08T14:30:00Z', marketCalls7d: 4250,
  },
  {
    modelName: 'Yi 34B', modelVersionId: 'mv-yi-34b', modelAssetId: 'ma-yi-34b',
    mountedOn: [{ gpuLabel: 'L40S-01', containerId: 'cont-yi-01', user: '한지원' }],
    marketSharedAt: null, marketCalls7d: 0,
  },
  {
    modelName: 'Mixtral 8x7B', modelVersionId: 'mv-mixtral-8x7b', modelAssetId: 'ma-mixtral-8x7b',
    mountedOn: [{ gpuLabel: 'H100-06', containerId: 'cont-mixtral-01', user: '강서아' }],
    marketSharedAt: '2026-05-14T10:00:00Z', marketCalls7d: 5230,
  },
  {
    modelName: 'BGE-M3 임베딩', modelVersionId: 'mv-bge-m3', modelAssetId: 'ma-bge-m3',
    mountedOn: [{ gpuLabel: 'H100-06', containerId: 'cont-bge-01', user: '오민서' }],
    marketSharedAt: '2026-05-22T13:00:00Z', marketCalls7d: 18650,
  },
  {
    modelName: 'Hyperion 30B', modelVersionId: 'mv-hyperion-30b', modelAssetId: 'ma-hyperion-30b',
    mountedOn: [{ gpuLabel: 'H100-07', containerId: 'cont-hyperion-01', user: '백지원' }],
    marketSharedAt: '2026-05-19T08:30:00Z', marketCalls7d: 9870,
  },
  {
    modelName: 'Whisper Large v3', modelVersionId: 'mv-whisper-l3', modelAssetId: 'ma-whisper-l3',
    mountedOn: [{ gpuLabel: 'H100-08', containerId: 'cont-whisper-01', user: '노유라' }],
    marketSharedAt: '2026-04-15T11:00:00Z', marketCalls7d: 2340,
  },
  {
    modelName: 'BART Large', modelVersionId: 'mv-bart-large', modelAssetId: 'ma-bart-large',
    mountedOn: [{ gpuLabel: 'A100-05', containerId: 'cont-bart-01', user: '윤서아' }],
    marketSharedAt: null, marketCalls7d: 0,
  },
  {
    modelName: 'RoBERTa Large', modelVersionId: 'mv-roberta-large', modelAssetId: 'ma-roberta-large',
    mountedOn: [{ gpuLabel: 'A100-06', containerId: 'cont-roberta-01', user: '한지원' }],
    marketSharedAt: '2026-05-02T09:00:00Z', marketCalls7d: 880,
  },
  {
    modelName: 'Stable Diffusion XL', modelVersionId: 'mv-sdxl', modelAssetId: 'ma-sdxl',
    mountedOn: [{ gpuLabel: 'L40S-02', containerId: 'cont-sdxl-01', user: '오영민' }],
    marketSharedAt: '2026-05-10T16:00:00Z', marketCalls7d: 7120,
  },
  {
    modelName: 'CodeLlama 13B', modelVersionId: 'mv-codellama-13b', modelAssetId: 'ma-codellama-13b',
    mountedOn: [{ gpuLabel: 'RTX 4090-02', containerId: 'cont-codellama13-01', user: '김도현' }],
    marketSharedAt: '2026-04-30T10:00:00Z', marketCalls7d: 1450,
  },
];

// ─── fleet KPI derivation ─────────────────────────────────────────────────────
export interface FleetKpis {
  computeAvgPct: number;
  computeP95Pct: number;
  vramUsedGB: number;
  vramTotalGB: number;
  slicesAllocated: number;
  slicesTotal: number;
  issuesCount: number;
  idleAllocatedCount: number;
  gpuTotal: number;
  tempAvgC: number;
}

export function deriveKpis(gpus: GpuMock[]): FleetKpis {
  const live = gpus.filter(g => g.computePct !== null);
  const liveTemp = gpus.filter(g => g.tempC !== null);
  const slices = gpus.flatMap(g => g.slices);
  const allocated = slices.filter(s => s.containerId !== null);
  const issues = gpus.filter(g => g.severity === 'error');
  const idle = gpus.filter(g => g.severity === 'warn'
    && g.slices.some(s => s.qualityState === 'idle_waste'));

  const avg = (xs: number[]) => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;

  return {
    computeAvgPct: Math.round(avg(live.map(g => g.computePct as number))),
    computeP95Pct: Math.round(Math.max(0, ...live.map(g => g.computePctP95_1h ?? 0))),
    vramUsedGB: gpus.reduce((a, g) => a + g.vramUsedGB, 0),
    vramTotalGB: gpus.reduce((a, g) => a + g.vramTotalGB, 0),
    slicesAllocated: allocated.length,
    slicesTotal: slices.length,
    issuesCount: issues.length,
    idleAllocatedCount: idle.length,
    gpuTotal: gpus.length,
    tempAvgC: Math.round(avg(liveTemp.map(g => g.tempC as number))),
  };
}

// ─── 자연어 라벨 (한국어) ─────────────────────────────────────────────────────
export const INCIDENT_LABEL_KO: Record<EventKind, string> = {
  allocated: '슬라이스 할당',
  released: '슬라이스 회수',
  host_offline: '호스트 오프라인',
  driver_error: '드라이버 오류',
  mig_reconfiguring: 'MIG 재구성 중',
  allocation_failed: '신청 실패',
  oom: '메모리 부족 (OOM)',
  health_unhealthy: '건강 상태 비정상',
  xid_ecc_error: 'XID/ECC 오류',
  requested: '슬라이스 신청',
  approved: '신청 승인',
  rejected: '신청 반려',
  container_created: '컨테이너 생성',
  container_started: '컨테이너 시작',
  container_stopped: '컨테이너 중지',
  model_loaded: '모델 로드',
  model_unloaded: '모델 언로드',
  market_shared: '마켓 공유 시작',
  market_unshared: '마켓 공유 중단',
  quota_exceeded: '쿼터 초과',
  auto_recovered: '자동 복구',
  maintenance: '점검 작업',
};

// ─── derived insights — 데이터 나열 → 인사이트 + 액션 ──────────────────────────
export interface Insight {
  kind: 'urgent' | 'opportunity' | 'highlight';
  icon: 'alert' | 'idle' | 'free' | 'star';
  title: string;          // 짧은 한 줄 ("Qwen2 72B 포화 위험")
  detail: string;         // 한 줄 보충 ("최근 5분 sustained 93%")
  action?: string;        // 추천 액션 ("추가 인스턴스 권장")
  target?: { gpuId?: string; modelName?: string; userId?: string; reqId?: string };
}

export function deriveUrgentActions(gpus: GpuMock[], hosts: HostMock[], events: EventMock[]): Insight[] {
  const out: Insight[] = [];

  // 1) 드라이버 오류 / 호스트 오프라인 등 incident.
  for (const g of gpus) {
    if (g.incident === 'driver_error') {
      out.push({
        kind: 'urgent', icon: 'alert',
        title: `${g.label} 드라이버 오류`,
        detail: `${g.model} 카드가 응답하지 않음 (PCI bus 단절 가능성)`,
        action: '즉시 점검 필요',
        target: { gpuId: g.id },
      });
    }
  }
  for (const h of hosts) {
    if (!h.isOnline) {
      out.push({
        kind: 'urgent', icon: 'alert',
        title: `${h.location} 호스트 오프라인`,
        detail: `에이전트 응답 없음 ${Math.floor(h.staleSec / 60)}분 ${h.staleSec % 60}초 · 하위 GPU 사용 불가`,
        action: '호스트 재시작 확인',
      });
    }
  }

  // 2) 포화 위험.
  for (const g of gpus) {
    const sat = g.slices.find((s) => s.qualityState === 'saturation');
    if (sat) {
      out.push({
        kind: 'urgent', icon: 'alert',
        title: `${sat.model?.name ?? 'GPU'} 포화 위험`,
        detail: `${g.label} 5분 지속 사용률 ${sat.computePctSustained5m ?? 90}% · 대기열 ${sat.queueDepth ?? 0}건 · 응답 ${sat.latencyP95Ms ?? 0}ms`,
        action: '추가 인스턴스 또는 분산 권장',
        target: { gpuId: g.id, modelName: sat.model?.name },
      });
    }
  }
  return out;
}

export function findIdleWaste(gpus: GpuMock[]): Insight | null {
  for (const g of gpus) {
    const idle = g.slices.find((s) => s.qualityState === 'idle_waste');
    if (idle) {
      return {
        kind: 'opportunity', icon: 'idle',
        title: '자원 회수 후보',
        detail: `${g.label} · ${idle.user?.name} · ${idle.model?.name} 10분간 ${idle.computePctSustained10m ?? 10}% 미만 사용`,
        action: '다른 신청자에게 재할당 가능',
        target: { gpuId: g.id, userId: idle.user?.id, modelName: idle.model?.name },
      };
    }
  }
  return null;
}

export function findAvailableSlots(gpus: GpuMock[], hosts: HostMock[]): Insight | null {
  let bestGpu: GpuMock | null = null;
  let bestFree = 0;
  for (const g of gpus) {
    const host = hosts.find((h) => h.id === g.hostId);
    if (host && !host.isOnline) continue;
    if (g.incident) continue;
    const free = g.slices.filter((s) => s.containerId === null).length;
    if (free > bestFree) { bestFree = free; bestGpu = g; }
  }
  if (!bestGpu || bestFree === 0) return null;
  const freeVram = bestGpu.slices.filter((s) => s.containerId === null).reduce((a, s) => a + s.vramTotalGB, 0);
  return {
    kind: 'opportunity', icon: 'free',
    title: '가용 자원',
    detail: `${bestGpu.label} 슬라이스 ${bestFree}개 비어 있음 (총 VRAM ${freeVram} GB)`,
    action: '신규 신청 받을 수 있음',
    target: { gpuId: bestGpu.id },
  };
}

export function findTopService(models: MountedModel[]): Insight | null {
  const sharing = models.filter((m) => m.marketSharedAt && m.marketCalls7d > 0);
  if (!sharing.length) return null;
  const top = [...sharing].sort((a, b) => b.marketCalls7d - a.marketCalls7d)[0];
  const on = top.mountedOn[0];
  return {
    kind: 'highlight', icon: 'star',
    title: '가장 인기 서비스',
    detail: `${top.modelName} · ${on.user} 님 · ${on.gpuLabel} · 7일간 ${top.marketCalls7d.toLocaleString()}회 호출`,
    action: '회사 내 핵심 모델',
    target: { gpuLabel: on.gpuLabel, modelName: top.modelName } as { gpuId?: string; modelName?: string },
  };
}

export interface UserUsage {
  name: string;
  slicesUsed: number;
  vramUsedGB: number;
  gpus: string[];
  models: string[];
}

export function deriveUserUsage(gpus: GpuMock[]): UserUsage[] {
  const map = new Map<string, UserUsage>();
  for (const g of gpus) {
    for (const s of g.slices) {
      if (!s.user) continue;
      const prev = map.get(s.user.name) ?? {
        name: s.user.name, slicesUsed: 0, vramUsedGB: 0, gpus: [], models: [],
      };
      prev.slicesUsed += 1;
      prev.vramUsedGB += s.vramUsedGB;
      if (!prev.gpus.includes(g.label)) prev.gpus.push(g.label);
      if (s.model && !prev.models.includes(s.model.name)) prev.models.push(s.model.name);
      map.set(s.user.name, prev);
    }
  }
  return Array.from(map.values()).sort((a, b) => b.slicesUsed - a.slicesUsed);
}

// ─── jitter for LIVE simulation (default 5s) ──────────────────────────────────
export function jitterGpus(gpus: GpuMock[]): GpuMock[] {
  return gpus.map(g => {
    if (g.computePct === null) return g;
    const delta = (Math.random() - 0.5) * 6;
    const next = Math.max(0, Math.min(100, g.computePct + delta));
    const nextSpark = [...g.sparkline60s.slice(1), next];
    return { ...g, computePct: Math.round(next), sparkline60s: nextSpark };
  });
}
