<script lang="ts">
  // cuda_monitoring 풍 60칸 가로 막대 히스토그램.
  // 채워진 칸은 위치 기반 컬러 (녹→노→주→빨), 빈 칸은 어둠.
  // 우측에 큰 MiB 숫자.
  interface Props {
    usedGB: number;
    totalGB: number;
    height?: number;
  }
  const { usedGB, totalGB, height = 22 }: Props = $props();

  const CELLS = 60;
  const pct = $derived(totalGB > 0 ? (usedGB / totalGB) * 100 : 0);
  const filledCells = $derived(Math.round((pct / 100) * CELLS));
  const usedMiB = $derived(Math.round(usedGB * 1024));

  function cellColor(idx: number): string {
    const r = idx / CELLS;
    if (r < 0.4) return '#65a30d';   // green
    if (r < 0.6) return '#a3a31a';   // olive
    if (r < 0.8) return '#d97706';   // orange
    return '#dc2626';                // red
  }
</script>

<div class="vb" style="--h: {height}px">
  <div class="bar">
    {#each Array(CELLS) as _, i}
      <span class="cell" class:on={i < filledCells} style={i < filledCells ? `background: ${cellColor(i)};` : ''}></span>
    {/each}
  </div>
  <div class="num">
    <span class="big">{usedMiB.toLocaleString()}</span>
    <span class="unit">MiB</span>
    <span class="of">/ {totalGB} GB</span>
    <span class="pct">{Math.round(pct)}%</span>
  </div>
</div>

<style>
  .vb {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 14px;
    width: 100%;
  }
  .bar {
    display: grid;
    grid-template-columns: repeat(60, 1fr);
    gap: 1px;
    height: var(--h);
    min-width: 0;
  }
  .cell {
    background: #14181f;
    border-radius: 1px;
  }
  .num {
    display: flex;
    align-items: baseline;
    gap: 6px;
    white-space: nowrap;
  }
  .big {
    font-size: 22px;
    font-weight: 800;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    line-height: 1;
    letter-spacing: -0.02em;
  }
  .unit { color: var(--text-secondary); font-size: 12px; font-weight: 600; }
  .of { color: var(--text-muted); font-size: 11px; }
  .pct {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: 700;
    background: var(--tag-bg);
    padding: 1px 7px;
    border-radius: 9999px;
    font-variant-numeric: tabular-nums;
  }
</style>
