<!--
  Mini scatter plot: CPU (x) × Memory (y). Points are historical samples,
  latest has a halo. Header tooltip explains the axes; the cell stays minimal.
-->
<script lang="ts">
	let {
		cpu = [],
		memory = [],
		color = '#30d5c8',
		label = 'CPU-Memory 분포',
	}: {
		cpu?: number[];
		memory?: number[];
		color?: string;
		label?: string;
	} = $props();

	const width = 110;
	const height = 44;
	const pad = 2;

	let pairs = $derived.by(() => {
		const n = Math.min(cpu.length, memory.length);
		const out: { x: number; y: number; age: number }[] = [];
		const plotW = width - pad * 2;
		const plotH = height - pad * 2;
		for (let i = 0; i < n; i += 1) {
			const c = Number(cpu[i] ?? 0);
			const m = Number(memory[i] ?? 0);
			if (!Number.isFinite(c) || !Number.isFinite(m)) continue;
			const cx = pad + (Math.min(100, Math.max(0, c)) / 100) * plotW;
			const cy = pad + (1 - Math.min(100, Math.max(0, m)) / 100) * plotH;
			out.push({ x: cx, y: cy, age: n - 1 - i });
		}
		return out;
	});
	let latest = $derived(pairs.at(-1) ?? null);
</script>

<svg class="scatter" viewBox="0 0 {width} {height}" role="img" aria-label={label}>
	<rect class="frame" x={pad} y={pad} width={width - pad * 2} height={height - pad * 2} />
	<line class="guide" x1={width / 2} y1={pad} x2={width / 2} y2={height - pad} />
	<line class="guide" x1={pad} y1={height / 2} x2={width - pad} y2={height / 2} />

	{#if pairs.length === 0}
		<text x={width / 2} y={height / 2 + 3} text-anchor="middle">데이터 없음</text>
	{:else}
		{#each pairs as p (p.age)}
			<circle
				cx={p.x}
				cy={p.y}
				r={p.age === 0 ? 2.4 : 1.3}
				style={`fill: ${color}; opacity: ${Math.max(0.15, 1 - p.age * 0.045)};`}
			/>
		{/each}
		{#if latest}
			<circle class="halo" cx={latest.x} cy={latest.y} r="3.8" style={`stroke: ${color};`} />
		{/if}
	{/if}
</svg>

<style>
	.scatter {
		display: block;
		width: 100%;
		max-width: 130px;
		min-width: 90px;
		height: 44px;
	}
	.frame {
		fill: rgba(13, 17, 23, 0.4);
		stroke: rgba(100, 116, 139, 0.2);
		stroke-width: 0.5;
		rx: 3;
	}
	.guide {
		stroke: rgba(100, 116, 139, 0.22);
		stroke-width: 0.5;
		stroke-dasharray: 2 2;
	}
	text {
		fill: var(--text-muted);
		font-size: 8px;
	}
	circle {
		stroke: none;
	}
	circle.halo {
		fill: none;
		stroke-width: 1;
		opacity: 0.55;
	}
</style>
