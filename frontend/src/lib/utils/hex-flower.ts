// 7-hex flower geometry + heatmap — ResourceMap 과 GpuPanel mini-flower 공통.
import type { GpuMock, SliceMock, Severity } from '$lib/mock/gpu-hosting';

export type Axial = { q: number; r: number };

// 7-cell flower: 중심 + 6 둘레.
export const FLOWER: Axial[] = [
  { q: 0, r: 0 },
  { q: 1, r: -1 },
  { q: 1, r: 0 },
  { q: 0, r: 1 },
  { q: -1, r: 1 },
  { q: -1, r: 0 },
  { q: 0, r: -1 },
];

// 외곽 hex (7-flower 의 가장자리 6개 — frame outline 계산용).
export const FLOWER_OUTER: Axial[] = [
  { q: 1, r: -1 }, { q: 1, r: 0 }, { q: 0, r: 1 },
  { q: -1, r: 1 }, { q: -1, r: 0 }, { q: 0, r: -1 },
];

// pointy-top hex: width = √3 * size, height = 2 * size.
export function hexW(size: number) { return Math.sqrt(3) * size; }
export function hexH(size: number) { return 2 * size; }

// axial → pixel (pointy-top).
export function axialPx(a: Axial, size: number): { x: number; y: number } {
  return {
    x: hexW(size) * (a.q + a.r / 2),
    y: size * 1.5 * a.r,
  };
}

// pointy-top hex polygon points centered at (0,0).
export function hexPoints(size: number): string {
  return Array.from({ length: 6 }, (_, i) => {
    const ang = (Math.PI / 3) * i - Math.PI / 2;
    return [size * Math.cos(ang), size * Math.sin(ang)].map((n) => n.toFixed(2)).join(',');
  }).join(' ');
}

// 7-flower outer boundary as 12-gon polygon points.
export function frameOutlinePoints(size: number): string {
  function corner(cx: number, cy: number, i: number): [number, number] {
    const ang = (Math.PI / 3) * i - Math.PI / 2;
    return [cx + size * Math.cos(ang), cy + size * Math.sin(ang)];
  }
  const pts: [number, number][] = [];
  for (let k = 0; k < 6; k++) {
    const c = axialPx(FLOWER_OUTER[k], size);
    pts.push(corner(c.x, c.y, (k + 5) % 6));
    pts.push(corner(c.x, c.y, k));
    pts.push(corner(c.x, c.y, (k + 1) % 6));
  }
  return pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
}

// GPU slices → 7 hex cells.
// - MIG mode: slice weight 만큼 인접 hex 가 같은 slice 공유 (분할 그대로 표현)
// - Whole mode: 1 slice 가 GPU 전체이지만 "분할 안 함" 표현 위해 1 hex 만 차지, 나머지 6 hex 는 null (= 빗금)
// 부족분 null.
export type Cell = { slice: SliceMock | null; weightIndex: number };
export function expandSlicesToFlower(gpu: GpuMock): Cell[] {
  const cells: Cell[] = [];
  for (const s of gpu.slices) {
    const span = gpu.mode === 'whole' ? 1 : s.profileWeight;
    for (let i = 0; i < span; i++) cells.push({ slice: s, weightIndex: i });
  }
  while (cells.length < 7) cells.push({ slice: null, weightIndex: 0 });
  return cells.slice(0, 7);
}

// slice 사용률 % (0-100).
export function sliceUsagePct(s: SliceMock): number {
  if (!s.containerId) return 0;
  return s.vramTotalGB > 0 ? (s.vramUsedGB / s.vramTotalGB) * 100 : 0;
}

// 5단 step heatmap (cool teal → warm red, 비어있음/오프라인/오류 별도).
export function heatmapColor(pct: number, allocated: boolean, sev: Severity): string {
  if (!allocated) return 'rgba(255, 255, 255, 0.05)';
  if (sev === 'offline') return 'rgba(71, 85, 105, 0.4)';
  if (sev === 'error') return 'rgba(217, 112, 112, 0.7)';
  if (pct < 25) return 'rgba(77, 191, 179, 0.55)';
  if (pct < 50) return 'rgba(132, 204, 156, 0.65)';
  if (pct < 75) return 'rgba(224, 185, 107, 0.75)';
  if (pct < 90) return 'rgba(232, 138, 92, 0.85)';
  return 'rgba(217, 112, 112, 0.9)';
}
