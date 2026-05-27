// GPU severity derivation.
// brief: §4 결정 로그 · §7.3 Compute 색 · §14 Row state.
//
// 규칙:
//   1. host.isOnline === false  →  하위 GPU severity = 'offline' (override)
//   2. host stale 60-180s         →  host severity 'warn', GPU 자기 severity 유지
//   3. host stale ≤ 60s           →  host 'ok'
//   4. GPU 자기 severity 는 incident > saturation > idle_waste > ok 우선순위로 결정

import type { GpuMock, HostMock, SliceMock, Severity } from '$lib/mock/gpu-hosting';

export const STALE_WARN_SEC = 60;
export const STALE_OFFLINE_SEC = 180;

export type RowState = 'ok' | 'no_data' | 'stale' | 'agent_offline' | 'permission_hidden';

export function hostSeverity(host: HostMock): Severity {
  if (!host.isOnline) return 'offline';
  if (host.staleSec > STALE_OFFLINE_SEC) return 'offline';
  if (host.staleSec > STALE_WARN_SEC) return 'warn';
  return 'ok';
}

export function hostRowState(host: HostMock): RowState {
  if (!host.isOnline || host.staleSec > STALE_OFFLINE_SEC) return 'agent_offline';
  if (host.staleSec > STALE_WARN_SEC) return 'stale';
  return 'ok';
}

// Effective GPU severity considering host offline precedence.
export function effectiveGpuSeverity(gpu: GpuMock, host: HostMock | undefined): Severity {
  if (host && !host.isOnline) return 'offline';
  return gpu.severity;
}

export function gpuRowState(gpu: GpuMock, host: HostMock | undefined): RowState {
  if (host && !host.isOnline) return 'agent_offline';
  if (gpu.computePct === null) return 'no_data';
  if (host && host.staleSec > STALE_WARN_SEC) return 'stale';
  return 'ok';
}

// Aria label generator — color must never be the only signal (brief §5.5).
export function severityLabel(s: Severity): string {
  switch (s) {
    case 'ok': return '정상';
    case 'warn': return '주의';
    case 'error': return '장애';
    case 'offline': return '오프라인';
  }
}

// Idle-allocated detection — slice allocated but qualityState === 'idle_waste'.
export function isIdleWaste(slice: SliceMock): boolean {
  return slice.containerId !== null && slice.qualityState === 'idle_waste';
}

export function isSaturation(slice: SliceMock): boolean {
  return slice.qualityState === 'saturation';
}

// Sort key: incidents first, then by compute descending.
// Returns negative number when `a` should appear before `b`.
export function fleetSortCompare(a: GpuMock, b: GpuMock): number {
  const sevRank: Record<Severity, number> = { error: 0, warn: 1, ok: 2, offline: 3 };
  const r = sevRank[a.severity] - sevRank[b.severity];
  if (r !== 0) return r;
  return (b.computePct ?? -1) - (a.computePct ?? -1);
}
