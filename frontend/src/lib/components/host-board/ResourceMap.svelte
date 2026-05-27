<script lang="ts">
  // Zenius 풍 honeycomb resource map — 2D canvas + flower cluster per GPU.
  // - 슬라이스 = 1 hex (최소 유닛)
  // - GPU = 7-hex flower cluster (1 center + 6 둘레) + 외곽 테두리 + label
  // - 색 = 사용률 step heatmap
  // - canvas drag panning (hex 클릭 제외)
  // - hex 클릭 → 하단 detail
  import type { GpuMock, HostMock, MountedModel } from '$lib/mock/gpu-hosting';
  import { effectiveGpuSeverity } from '$lib/utils/gpu-severity';
  import { SEMANTIC_HEX } from '$lib/utils/gpu-palette';
  import {
    FLOWER, axialPx as flowerAxialPx, hexPoints,
    expandSlicesToFlower, sliceUsagePct, heatmapColor,
    frameOutlinePoints,
  } from '$lib/utils/hex-flower';

  interface Props {
    gpus: GpuMock[];
    host: HostMock;
    mountedModels: MountedModel[];
    selectedGpuId: string | null;
    onGpuSelect: (gpuId: string | null) => void;
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

  const HEX_POINTS = hexPoints(HEX_SIZE);
  const FRAME_POINTS = frameOutlinePoints(HEX_SIZE);
  const axialPx = (a: { q: number; r: number }) => flowerAxialPx(a, HEX_SIZE);

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

  // 배경 click 감지 — pan 시작점과 종료점이 거의 같으면 click 으로 간주 → selection clear.
  let downAt = { x: 0, y: 0 };
  function onCanvasDown(e: PointerEvent) {
    const t = e.target as HTMLElement;
    if (t.closest('[data-hex]')) return; // hex 클릭은 select, pan 아님
    panning = true;
    panStart = { x: e.clientX, y: e.clientY, ox: pan.x, oy: pan.y };
    downAt = { x: e.clientX, y: e.clientY };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onCanvasMove(e: PointerEvent) {
    if (!panning) return;
    pan = { x: panStart.ox + (e.clientX - panStart.x), y: panStart.oy + (e.clientY - panStart.y) };
  }
  function onCanvasUp(e: PointerEvent) {
    panning = false;
    try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId); } catch {}
    // 거의 안 움직인 배경 클릭 = selection 풀기
    const dx = Math.abs(e.clientX - downAt.x);
    const dy = Math.abs(e.clientY - downAt.y);
    if (dx < 4 && dy < 4 && selectedGpuId !== null) {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-hex]')) onGpuSelect(null);
    }
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
    <span class="lg-step" style="background: rgba(132, 204, 156, 0.65)"></span><span class="lg-lbl">25–50%</span>
    <span class="lg-step" style="background: rgba(224, 185, 107, 0.75)"></span><span class="lg-lbl">50–75%</span>
    <span class="lg-step" style="background: rgba(232, 138, 92, 0.85)"></span><span class="lg-lbl">75–90%</span>
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
      <defs>
        <!-- 분할 안 됨 / 할당 안 됨 표시 — 대각선 빗금 패턴 -->
        <pattern id="hatched-unalloc" patternUnits="userSpaceOnUse" width="3" height="3" patternTransform="rotate(45)">
          <rect width="3" height="3" fill="rgba(255,255,255,0.025)"/>
          <line x1="0" y1="0" x2="0" y2="3" stroke="rgba(255,255,255,0.18)" stroke-width="0.6"/>
        </pattern>
      </defs>
      {#each placed as p (p.gpu.id)}
        {@const sev = effectiveGpuSeverity(p.gpu, host)}
        {@const cells = expandSlicesToFlower(p.gpu)}
        {@const isSel = selectedGpuId === p.gpu.id}
        {@const dimmed = selectedGpuId !== null && !isSel}
        <g class="cluster" class:selected={isSel} class:dimmed transform="translate({p.cx}, {p.cy})">
          <!-- 7-hex flower outer outline as 12-gon — slice 묶음 테두리 -->
          <polygon
            class="frame-shape"
            points={FRAME_POINTS}
            data-sev={sev}
            class:sel={isSel}
          />

          <!-- slices = 7 hexes (할당 안 된 hex 는 빗금) -->
          {#each cells as c, i (p.gpu.id + ':' + i)}
            {@const allocated = !!(c.slice && c.slice.containerId)}
            {@const isUnalloc = !c.slice}
            {@const pct = c.slice ? sliceUsagePct(c.slice) : 0}
            {@const off = axialPx(FLOWER[i])}
            {@const cellColor = isUnalloc ? 'url(#hatched-unalloc)' : heatmapColor(pct, allocated, sev)}
            <g transform="translate({off.x}, {off.y})">
              <polygon
                data-hex
                class="hex"
                class:empty={!allocated}
                class:unalloc={isUnalloc}
                points={HEX_POINTS}
                fill={cellColor}
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

  .cluster { transition: opacity 0.18s; }
  .cluster.dimmed { opacity: 0.32; }
  .cluster.dimmed:hover { opacity: 0.65; }

  .frame-shape {
    fill: none;
    stroke: rgba(255, 255, 255, 0.4);
    stroke-width: 1;
    stroke-linejoin: round;
    pointer-events: none;
  }
  .frame-shape[data-sev='warn']    { stroke: var(--warn); stroke-opacity: 0.7; }
  .frame-shape[data-sev='error']   { stroke: var(--error); stroke-opacity: 0.8; }
  .frame-shape[data-sev='offline'] { stroke: var(--offline); stroke-opacity: 0.7; stroke-dasharray: 3 2; }
  .frame-shape.sel {
    stroke: var(--accent) !important;
    stroke-opacity: 0.85 !important;
    stroke-width: 1.4;
  }

  .hex {
    stroke: rgba(13, 17, 23, 0.7);
    stroke-width: 0.3;
    cursor: pointer;
    transition: filter 0.12s;
    transform-origin: center;
    transform-box: fill-box;
  }
  .hex:hover { filter: brightness(1.3); }
  .hex.empty { cursor: pointer; }
  /* 할당 안 됨 (빗금) — stroke 색을 빗금 배경과 동일하게 해서 인접 빗금 hex 사이 분할선 안 보이게 */
  .hex.unalloc {
    stroke: rgba(255, 255, 255, 0.04);
    stroke-width: 0.2;
  }

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
