<!--
  Lightweight SVG sparkline for the left sidebar.
  Keeps an internal ring buffer of the last N samples and redraws
  smoothly as new values arrive. No Chart.js; the path element itself
  CSS-transitions to its new shape so a stream of point-updates feels
  continuous rather than stepped.
-->
<script lang="ts">
	let {
		value,
		history = [],
		min = 0,
		max = 100,
		bufferSize = 60,
		width = 120,
		height = 28,
		stroke = '#30d5c8',
		fill = 'rgba(48, 213, 200, 0.18)',
		smoothMs = 1400,
	}: {
		value: number;
		history?: number[]; // optional external history; if empty, component keeps its own
		min?: number;
		max?: number;
		bufferSize?: number;
		width?: number;
		height?: number;
		stroke?: string;
		fill?: string;
		smoothMs?: number;
	} = $props();

	// Internal ring-buffer when caller doesn't pass history explicitly.
	let buffer = $state<number[]>([]);

	$effect(() => {
		if (typeof value !== 'number' || Number.isNaN(value)) return;
		buffer = [...buffer, value].slice(-bufferSize);
	});

	const samples = $derived(history.length > 0 ? history : buffer);

	function toPath(values: number[], w: number, h: number, lo: number, hi: number) {
		if (values.length === 0) return { line: '', area: '' };
		const span = Math.max(1e-6, hi - lo);
		const step = values.length > 1 ? w / (values.length - 1) : w;
		const pts = values.map((v, i) => {
			const x = i * step;
			const norm = Math.max(0, Math.min(1, (v - lo) / span));
			const y = h - norm * h;
			return [x, y] as const;
		});
		const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
		const area = `${line} L${w.toFixed(2)},${h.toFixed(2)} L0,${h.toFixed(2)} Z`;
		return { line, area };
	}

	const paths = $derived(toPath(samples, width, height, min, max));
</script>

<svg
	class="sparkline"
	viewBox={`0 0 ${width} ${height}`}
	preserveAspectRatio="none"
	aria-hidden="true"
	style="--smooth-ms:{smoothMs}ms;"
>
	{#if paths.area}
		<path class="area" d={paths.area} style="fill:{fill};" />
	{/if}
	{#if paths.line}
		<path class="line" d={paths.line} style="stroke:{stroke};" />
	{/if}
</svg>

<style>
	.sparkline {
		display: block;
		width: 100%;
		height: 100%;
		overflow: visible;
	}

	.area {
		stroke: none;
		transition: d var(--smooth-ms, 1400ms) cubic-bezier(0.22, 0.61, 0.36, 1);
	}

	.line {
		fill: none;
		stroke-width: 1.5;
		stroke-linejoin: round;
		stroke-linecap: round;
		transition: d var(--smooth-ms, 1400ms) cubic-bezier(0.22, 0.61, 0.36, 1);
	}
</style>
