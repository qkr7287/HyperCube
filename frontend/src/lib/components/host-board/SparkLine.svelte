<script lang="ts">
  // 작은 SVG sparkline. 60s 시계열.
  interface Props {
    values: number[];
    width?: number;
    height?: number;
    stroke?: string;
    label?: string;
  }
  const { values, width = 72, height = 18, stroke = 'var(--accent)', label = '' }: Props = $props();

  const path = $derived.by(() => {
    if (!values.length) return '';
    const n = values.length;
    const stepX = (width - 2) / Math.max(1, n - 1);
    const pts = values.map((v, i) => {
      const x = 1 + i * stepX;
      const y = height - 1 - (Math.max(0, Math.min(100, v)) / 100) * (height - 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return `M${pts.join(' L')}`;
  });
</script>

<svg class="sl" {width} {height} viewBox="0 0 {width} {height}" role="img" aria-label={label || `sparkline ${values.length}s`}>
  {#if values.length}
    <path d={path} fill="none" {stroke} stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
  {:else}
    <line x1="1" y1={height / 2} x2={width - 1} y2={height / 2} stroke="var(--offline)" stroke-width="1" stroke-dasharray="2 2" />
  {/if}
</svg>

<style>
  .sl { display: inline-block; vertical-align: middle; }
</style>
