<script lang="ts">
  // Grafana 14574 / OVH DCGM 풍 시계열 차트 strip.
  // VRAM / 온도 / 전력 60초 mini line.
  import type { GpuMock } from '$lib/mock/gpu-hosting';
  import { identityColor } from '$lib/utils/gpu-palette';
  import SparkLine from './SparkLine.svelte';

  interface Props {
    gpu: GpuMock;
  }
  const { gpu }: Props = $props();

  // 60s 시계열 mock (현재 값 기준 jitter).
  const vramSeries = $derived.by(() => {
    const base = gpu.vramTotalGB > 0 ? (gpu.vramUsedGB / gpu.vramTotalGB) * 100 : 0;
    return Array.from({ length: 60 }, (_, i) => {
      const w = Math.sin((i + 3) / 7) * 1.5 + Math.cos((i + 1) / 5) * 1.2;
      return Math.max(0, Math.min(100, base + w));
    });
  });
  const tempSeries = $derived.by(() => {
    if (gpu.tempC === null) return Array(60).fill(0);
    const base = gpu.tempC;
    return Array.from({ length: 60 }, (_, i) => {
      const w = Math.sin((i + 5) / 6) * 0.8 + Math.cos((i + 7) / 8) * 0.5;
      // 0-100 normalize (max 100°C 기준)
      return Math.max(0, Math.min(100, base + w));
    });
  });
  const powerSeries = $derived.by(() => {
    if (gpu.powerW === null) return Array(60).fill(0);
    const base = gpu.powerW;
    return Array.from({ length: 60 }, (_, i) => {
      const w = Math.sin((i + 2) / 8) * (base * 0.04) + Math.cos((i + 4) / 6) * (base * 0.025);
      // power → 0-100 normalize (powerCap 기준)
      const v = ((base + w) / gpu.powerCapW) * 100;
      return Math.max(0, Math.min(100, v));
    });
  });

  const idColor = $derived(identityColor(gpu.id));
</script>

<div class="charts">
  <div class="ch">
    <div class="ch-head">
      <span class="ch-key">메모리</span>
      <span class="ch-en">VRAM</span>
      <span class="ch-now">{Math.round((gpu.vramUsedGB / Math.max(1, gpu.vramTotalGB)) * 100)}%</span>
    </div>
    <div class="ch-body"><SparkLine values={vramSeries} width={210} height={50} stroke="#fb923c" label="VRAM 60s" /></div>
    <div class="ch-foot">최근 60초 · {gpu.vramUsedGB} / {gpu.vramTotalGB} GB</div>
  </div>

  <div class="ch">
    <div class="ch-head">
      <span class="ch-key">온도</span>
      <span class="ch-en">Temperature</span>
      <span class="ch-now">{gpu.tempC ?? '—'}{gpu.tempC !== null ? '°C' : ''}</span>
    </div>
    <div class="ch-body"><SparkLine values={tempSeries} width={210} height={50} stroke="#facc15" label="Temp 60s" /></div>
    <div class="ch-foot">최근 60초 · 추세 {gpu.tempTrendC5m >= 0 ? '+' : ''}{gpu.tempTrendC5m.toFixed(1)}°/5분</div>
  </div>

  <div class="ch">
    <div class="ch-head">
      <span class="ch-key">전력</span>
      <span class="ch-en">Power Draw</span>
      <span class="ch-now">{gpu.powerW ?? '—'}{gpu.powerW !== null ? 'W' : ''}</span>
    </div>
    <div class="ch-body"><SparkLine values={powerSeries} width={210} height={50} stroke={idColor} label="Power 60s" /></div>
    <div class="ch-foot">최근 60초 · 한도 {gpu.powerCapW} W</div>
  </div>
</div>

<style>
  .charts {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1px;
    background: var(--border);
    border-radius: 6px;
    overflow: hidden;
  }
  .ch {
    background: #181d26;
    padding: 12px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }
  .ch-head {
    display: flex; align-items: baseline; gap: 8px;
  }
  .ch-key {
    color: var(--text-primary);
    font-size: 14px;
    font-weight: 700;
  }
  .ch-en {
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 500;
  }
  .ch-now {
    margin-left: auto;
    color: var(--text-primary);
    font-size: 22px;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
  }
  .ch-body { width: 100%; }
  .ch-body :global(svg) { width: 100%; }
  .ch-foot {
    color: var(--text-muted);
    font-size: 12px;
  }
</style>
