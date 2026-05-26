// GPU Hosting palette utilities.
// brief: §5.3 색 체계 — semantic palette ↔ identity palette 분리.

import type { Severity } from '$lib/mock/gpu-hosting';

// Semantic palette: status / KPI threshold / badge stroke 전용.
// HyperCube 토큰과 정합. offline 은 신규 (#475569).
export const SEMANTIC = {
  ok: 'var(--accent)',
  warn: 'var(--warn)',
  error: 'var(--error)',
  offline: 'var(--offline)',
} as const satisfies Record<Severity, string>;

export function severityColor(s: Severity): string {
  return SEMANTIC[s];
}

// Hex versions for SVG fill where CSS var 가 안 먹는 곳 (sparkline path stroke 등).
export const SEMANTIC_HEX: Record<Severity, string> = {
  ok: '#4dbfb3',
  warn: '#e0b96b',
  error: '#d97070',
  offline: '#475569',
};

// Identity palette: GPU 별 line/area 구분 전용. 절대 severity 와 섞지 않음.
// Deterministic — 같은 GPU id 는 항상 같은 색.
const IDENTITY_PALETTE = [
  '#7dd3fc', // sky
  '#c4b5fd', // violet
  '#fda4af', // rose
  '#86efac', // green
  '#fcd34d', // amber
  '#67e8f9', // cyan
  '#f0abfc', // fuchsia
  '#fdba74', // orange
  '#a5b4fc', // indigo
  '#5eead4', // teal
];

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return h;
}

export function identityColor(gpuId: string): string {
  return IDENTITY_PALETTE[hashString(gpuId) % IDENTITY_PALETTE.length];
}

// For ECharts series — return both stroke and a light fill for area.
export function identityColorPair(gpuId: string): { stroke: string; area: string } {
  const stroke = identityColor(gpuId);
  return { stroke, area: stroke + '22' }; // ~13% alpha hex
}
