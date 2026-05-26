<script lang="ts">
  // Zenius 풍 honeycomb resource map — 2D canvas + flower cluster per GPU.
  // - 슬라이스 = 1 hex (최소 유닛)
  // - GPU = 7-hex flower cluster (1 center + 6 둘레) + 외곽 테두리 + label
  // - 색 = 사용률 step heatmap
  // - canvas drag panning (hex 클릭 제외)
  // - hex 클릭 → 하단 detail
  import type { GpuMock, SliceMock, HostMock, MountedModel } from '$lib/mock/gpu-hosting';
  import { effectiveGpuSeverity } from '$lib/utils/gpu-severity';
  import { SEMANTIC_HEX } from '$lib/utils/gpu-palette';

  interface Props {
    gpus: GpuMock[];
    host: HostMock;
    mountedModels: MountedModel[];
    selectedGpuId: string | null;
    onGpuSelect: (gpuId: string) => void;
  }
  const { gpus, host, selectedGpuId, onGpuSelect }: Props = $props();

  // ─── geometry ─────────────────────────────────────────────────────────
  const HEX_SIZE = 7; // hex radius (center → vertex) — viewport fit
  const HEX_W = Math.sqrt(3) * HEX_SIZE; // pointy-top width
  const HEX_H = 2 * HEX_SIZE;            // pointy-top height
  // honeycomb mosaic: cluster center 들이 자체 hex grid (axial distance 3) — 외곽 hex 끼리 변 공유.
  const CLUSTER_GAP_X = HEX_W * 3;       // ≈ axial 3 가로
  const CLUSTER_GAP_Y = HEX_SIZE * 4.5;  // ≈ axial 3 세로 (pointy-top)
  const CLUSTER_ROW_OFFSET_X = HEX_W * 1.5; // 짝수/홀수 row 가로 offset (mosaic)
  const CLUSTER_COLS = 4;                // 한 행 GPU 수 (12 GPU = 3 row, 가로/세로 균형)

  // 7-cell flower offsets (axial → pixel). 중심부터 시계 방향 6.
  type Axial = { q: number; r: number };
  const FLOWER: Axial[] = [
    { q: 0, r: 0 },
    { q: 1, r: -1 },
    { q: 1, r: 0 },
    { q: 0, r: 1 },
    { q: -1, r: 1 },
    { q: -1, r: 0 },
    { q: 0, r: -1 },
  ];

  function axialPx(a: Axial): { x: number; y: number } {
    return {
      x: HEX_W * (a.q + a.r / 2),
      y: HEX_SIZE * 1.5 * a.r,
    };
  }

  // pointy-top hex polygon points (center 0,0).
  const HEX_POINTS = Array.from({ length: 6 }, (_, i) => {
    const ang = (Math.PI / 3) * i - Math.PI / 2; // pointy-top
    return [HEX_SIZE * Math.cos(ang), HEX_SIZE * Math.sin(ang)].map((n) => n.toFixed(2)).join(',');
  }).join(' ');

  // ─── slice → hex 매핑 ───────────────────────────────────────────────────
  // GPU 의 slices 를 weight 단위로 펼쳐 7 cell 까지 채움. 부족분은 null (unused).
  type Cell = { slice: SliceMock | null; weightIndex: number };
  function expandSlices(gpu: GpuMock): Cell[] {
    const cells: Cell[] = [];
    for (const s of gpu.slices) {
      for (let i = 0; i < s.profileWeight; i++) cells.push({ slice: s, weightIndex: i });
    }
    while (cells.length < 7) cells.push({ slice: null, weightIndex: 0 });
    return cells.slice(0, 7);
  }

  // ─── color (heatmap) ──────────────────────────────────────────────────
  function sliceUsagePct(s: SliceMock): number {
    if (!s.containerId) return 0;
    return s.vramTotalGB > 0 ? (s.vramUsedGB / s.vramTotalGB) * 100 : 0;
  }
  function heatmapColor(pct: number, allocated: boolean, sev: string): string {
    if (!allocated) return 'rgba(255, 255, 255, 0.05)';
    if (sev === 'offline') return 'rgba(71, 85, 105, 0.4)';
    if (sev === 'error') return 'rgba(217, 112, 112, 0.7)';
    if (pct < 25) return 'rgba(77, 191, 179, 0.55)';
    if (pct < 50) return 'rgba(132, 204, 156, 0.65)';
    if (pct < 75) return 'rgba(224, 185, 107, 0.75)';
    if (pct < 90) return 'rgba(232, 138, 92, 0.85)';
    return 'rgba(217, 112, 112, 0.9)';
  }

  // ─── GPU 격자 위치 ────────────────────────────────────────────────────
  type Placed = { gpu: GpuMock; cx: number; cy: number };
  const placed = $derived.by<Placed[]>(() =>
    gpus.map((g, i) => {
      const col = i % CLUSTER_COLS;
      const row = Math.floor(i / CLUSTER_COLS);
      const offsetX = row % 2 === 1 ? CLUSTER_ROW_OFFSET_X : 0;
      return { gpu: g, cx: col * CLUSTER_GAP_X + offsetX, cy: row * CLUSTER_GAP_Y };
    }),
  );

  // ─── pan + zoom ───────────────────────────────────────────────────────
  let pan = $state({ x: 0, y: 0 });
  let zoom = $state(1);
  let panning = $state(false);
  let panStart = { x: 0, y: 0, ox: 0, oy: 0 };

  const ZOOM_MIN = 0.3;
  const ZOOM_MAX = 3;

  function onCanvasDown(e: PointerEvent) {
    const t = e.target as HTMLElement;
    if (t.closest('[data-hex]')) return; // hex 클릭은 select, pan 아님
    panning = true;
    panStart = { x: e.clientX, y: e.clientY, ox: pan.x, oy: pan.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onCanvasMove(e: PointerEvent) {
    if (!panning) return;
    pan = { x: panStart.ox + (e.clientX - panStart.x), y: panStart.oy + (e.clientY - panStart.y) };
  }
  function onCanvasUp(e: PointerEvent) {
    panning = false;
    try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId); } catch {}
  }
  function onCanvasWheel(e: WheelEvent) {
    // Ctrl/Cmd + wheel 일 때만 zoom — 일반 스크롤 보존.
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.12 : 0.12;
    zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, zoom + delta));
  }
  function zoomIn() { zoom = Math.min(ZOOM_MAX, zoom + 0.2); }
  function zoomOut() { zoom = Math.max(ZOOM_MIN, zoom - 0.2); }
  function resetView() { pan = { x: 0, y: 0 }; zoom = 1; }

  // ─── viewBox (initial center fit) ─────────────────────────────────────
  const viewBox = $derived.by(() => {
    if (placed.length === 0) return '0 0 100 100';
    const xs = placed.map((p) => p.cx);
    const ys = placed.map((p) => p.cy);
    // cluster 의 외곽 hex 가 center ± HEX_H, label 은 cluster 위 HEX_H*1.4 + 28px box. 충분히 padding.
    const padX = HEX_W * 2;
    const padTop = HEX_H * 3.2;   // label box 위 잘림 방지
    const padBot = HEX_H * 1.6;
    const minX = Math.min(...xs) - padX;
    const minY = Math.min(...ys) - padTop;
    const maxX = Math.max(...xs) + padX;
    const maxY = Math.max(...ys) + padBot;
    return `${minX} ${minY} ${maxX - minX} ${maxY - minY}`;
  });
</script>

<section class="map">
  <div class="legend">
    <span class="lg-key">사용률</span>
    <span class="lg-step" style="background: rgba(255,255,255,0.05)"></span><span class="lg-lbl">비어있음</span>
    <span class="lg-step" style="background: rgba(77, 191, 179, 0.55)"></span><span class="lg-lbl">&lt;25%</span>
    <span class="lg-step" style="background: rgba(132, 204, 156, 0.65)"></span><span class="lg-lbl">25–50</span>
    <span class="lg-step" style="background: rgba(224, 185, 107, 0.75)"></span><span class="lg-lbl">50–75</span>
    <span class="lg-step" style="background: rgba(232, 138, 92, 0.85)"></span><span class="lg-lbl">75–90</span>
    <span class="lg-step" style="background: rgba(217, 112, 112, 0.9)"></span><span class="lg-lbl">&gt;90% / 오류</span>
    <div class="zoom-controls">
      <button type="button" onclick={zoomOut} aria-label="축소">−</button>
      <span class="zoom-val">{Math.round(zoom * 100)}%</span>
      <button type="button" onclick={zoomIn} aria-label="확대">+</button>
      <button type="button" class="z-reset" onclick={resetView} aria-label="화면 중심으로">⌂</button>
    </div>
  </div>

  <div
    class="canvas"
    class:panning
    onpointerdown={onCanvasDown}
    onpointermove={onCanvasMove}
    onpointerup={onCanvasUp}
    onpointercancel={onCanvasUp}
    onwheel={onCanvasWheel}
    role="application"
    aria-label="GPU 자원 맵 2D 캔버스 — 드래그하여 이동, 휠로 확대/축소, hex 클릭하여 슬라이스 선택"
  >
    <svg class="board" width="100%" height="100%" {viewBox} preserveAspectRatio="xMidYMid meet" style="transform: translate({pan.x}px, {pan.y}px) scale({zoom}); transform-origin: center center;">
      {#each placed as p (p.gpu.id)}
        {@const sev = effectiveGpuSeverity(p.gpu, host)}
        {@const cells = expandSlices(p.gpu)}
        {@const isSel = selectedGpuId === p.gpu.id}
        <g class="cluster" class:selected={isSel} transform="translate({p.cx}, {p.cy})">
          <!-- 7-hex flower outer outline as 12-gon — slice 묶음 테두리 -->
          <polygon
            class="frame-shape"
            points={frameOutlinePoints()}
            data-sev={sev}
            class:sel={isSel}
          />

          <!-- slices = 7 hexes -->
          {#each cells as c, i (p.gpu.id + ':' + i)}
            {@const allocated = !!(c.slice && c.slice.containerId)}
            {@const pct = c.slice ? sliceUsagePct(c.slice) : 0}
            {@const off = axialPx(FLOWER[i])}
            <g transform="translate({off.x}, {off.y})">
              <polygon
                data-hex
                class="hex"
                class:empty={!allocated}
                points={HEX_POINTS}
                fill={heatmapColor(pct, allocated, sev)}
                onclick={() => onGpuSelect(p.gpu.id)}
              />
            </g>
          {/each}

          <!-- GPU label (hover 시만) — SVG text, viewBox-unit 폰트 -->
          <g class="g-label-grp" transform="translate(0, {-HEX_H * 1.8})">
            <rect
              class="g-label-bg"
              x={-32}
              y={-9}
              width="64"
              height="16"
              rx="2"
              stroke={SEMANTIC_HEX[sev === 'offline' ? 'offline' : sev === 'error' ? 'error' : sev === 'warn' ? 'warn' : 'ok']}
            />
            <text class="g-label" text-anchor="middle" y="-3" fill={sev === 'ok' ? '#f8fafc' : SEMANTIC_HEX[sev]}>{p.gpu.label}</text>
            <text class="g-meta" text-anchor="middle" y="4">
              {p.gpu.model}·{p.gpu.mode === 'mig' ? 'MIG' : 'W'} {p.gpu.vramUsedGB}/{p.gpu.vramTotalGB}G
            </text>
          </g>
        </g>
      {/each}
    </svg>
  </div>
</section>

<script context="module" lang="ts">
  // 7-hex flower 외곽 12-gon — slice 묶음 테두리 (정확한 boundary).
  // 각 외곽 hex 의 outer 변들을 모아 polygon points 생성.
  export function frameOutlinePoints(): string {
    const HEX_SIZE = 7;
    const HEX_W = Math.sqrt(3) * HEX_SIZE;
    type Axial = { q: number; r: number };
    const OUTER: Axial[] = [
      { q: 1, r: -1 }, { q: 1, r: 0 }, { q: 0, r: 1 },
      { q: -1, r: 1 }, { q: -1, r: 0 }, { q: 0, r: -1 },
    ];
    function axial(a: Axial) {
      return { x: HEX_W * (a.q + a.r / 2), y: HEX_SIZE * 1.5 * a.r };
    }
    function corner(cx: number, cy: number, i: number): [number, number] {
      const ang = (Math.PI / 3) * i - Math.PI / 2;
      return [cx + HEX_SIZE * Math.cos(ang), cy + HEX_SIZE * Math.sin(ang)];
    }
    // 외곽 hex 6개 각각의 outer 4 corner (4·5·0·1 or 시계방향 셋). 시계방향 1·2·3·4 corner.
    const pts: [number, number][] = [];
    for (let k = 0; k < 6; k++) {
      const c = axial(OUTER[k]);
      // pointy-top hex corner index 0..5 start top, clockwise.
      // 외부로 향한 corner 시작 index = k (회전 대칭).
      pts.push(corner(c.x, c.y, (k + 5) % 6));
      pts.push(corner(c.x, c.y, k));
      pts.push(corner(c.x, c.y, (k + 1) % 6));
    }
    return pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  }
</script>

<style>
  .map {
    background: #181d26;
    border-radius: 8px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }

  .legend {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: var(--text-muted);
    flex-wrap: wrap;
  }
  .lg-key { color: var(--text-primary); font-weight: 700; margin-right: 4px; }
  .lg-step {
    width: 12px; height: 14px;
    clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
    flex-shrink: 0;
  }
  .lg-lbl { font-variant-numeric: tabular-nums; }
  .zoom-controls {
    margin-left: auto;
    display: inline-flex;
    align-items: center;
    gap: 2px;
    background: rgba(255, 255, 255, 0.04);
    border-radius: 9999px;
    padding: 2px;
  }
  .zoom-controls button {
    appearance: none;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    font: inherit;
    font-size: 13px;
    font-weight: 700;
    width: 22px;
    height: 22px;
    cursor: pointer;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
  .zoom-controls button:hover { background: rgba(77, 191, 179, 0.15); color: var(--accent); }
  .zoom-controls .zoom-val {
    color: var(--text-muted);
    font-size: 10px;
    font-variant-numeric: tabular-nums;
    min-width: 36px;
    text-align: center;
  }
  .zoom-controls .z-reset { font-size: 11px; }

  .canvas {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    background: radial-gradient(ellipse at center, rgba(255,255,255,0.025), transparent 70%);
    border-radius: 6px;
    position: relative;
    cursor: grab;
    user-select: none;
  }
  .canvas.panning { cursor: grabbing; }

  .board {
    width: 100%;
    height: 100%;
    overflow: visible;
    transition: transform 0.04s linear;
  }

  .frame-shape {
    fill: none;
    stroke: rgba(255, 255, 255, 0.55);
    stroke-width: 2;
    stroke-linejoin: round;
    pointer-events: none;
  }
  .frame-shape[data-sev='warn']    { stroke: var(--warn); stroke-opacity: 0.85; }
  .frame-shape[data-sev='error']   { stroke: var(--error); stroke-opacity: 0.95; }
  .frame-shape[data-sev='offline'] { stroke: var(--offline); stroke-opacity: 0.8; stroke-dasharray: 4 3; }
  .frame-shape.sel {
    stroke: var(--accent) !important;
    stroke-opacity: 1 !important;
    stroke-width: 2.5;
  }

  .hex {
    stroke: rgba(13, 17, 23, 0.9);
    stroke-width: 0.8;
    cursor: pointer;
    transition: filter 0.12s;
    transform-origin: center;
    transform-box: fill-box;
  }
  .hex:hover { filter: brightness(1.3); }
  .hex.empty { cursor: pointer; }

  .g-label-grp {
    opacity: 0;
    transition: opacity 0.12s;
    pointer-events: none;
  }
  .cluster:hover .g-label-grp { opacity: 1; }

  .g-label-bg {
    fill: rgba(13, 17, 23, 0.95);
    stroke-opacity: 0.8;
    stroke-width: 0.6;
  }
  .g-label {
    font-size: 5px;
    font-weight: 700;
    dominant-baseline: middle;
  }
  .g-meta {
    fill: #94a3b8;
    font-size: 3.5px;
    font-family: "JetBrains Mono", Consolas, monospace;
    dominant-baseline: middle;
  }

</style>
