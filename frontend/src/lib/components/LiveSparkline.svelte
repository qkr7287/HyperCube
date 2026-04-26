<!--
  Lightweight SVG sparkline for the left sidebar.

  Time-based ring buffer: each sample is tagged with a timestamp and
  samples older than `windowMs` (default 10 min) are discarded on each
  new tick. This keeps the visible window an actual fixed duration
  rather than "last N samples" — tick-rate changes don't distort the
  apparent time axis.

  The path element CSS-transitions between shapes so streamed updates
  feel continuous rather than stepped.
-->
<script lang="ts">
	import { untrack } from 'svelte';

	let {
		value,
		history = [],
		initialHistory = [],
		min = 0,
		max = 100,
		windowMs = 10 * 60 * 1000,
		width = 120,
		height = 28,
		stroke = '#30d5c8',
		fill = 'rgba(48, 213, 200, 0.18)',
		smoothMs = 1400,
	}: {
		value: number;
		history?: number[]; // optional external history; if empty, component keeps its own
		/** Past samples {t, v} used to seed the buffer once — so the sparkline
		 *  shows the same window shape as the detail modal's chart instead of
		 *  starting empty. */
		initialHistory?: { t: number; v: number }[];
		min?: number;
		max?: number;
		/** Rolling time window in ms. Samples older than this get dropped. */
		windowMs?: number;
		width?: number;
		height?: number;
		stroke?: string;
		fill?: string;
		smoothMs?: number;
	} = $props();

	type Sample = { t: number; v: number };

	// Internal ring-buffer when caller doesn't pass history explicitly.
	// Read untracked inside the effect so we only react to `value`, never to
	// our own append. Writing back to $state would otherwise re-trigger the
	// effect indefinitely (Svelte 5 `effect_update_depth_exceeded`).
	//
	// Every tick is recorded even when the value is identical to the previous
	// one — with a rounded integer feed (e.g. memPct jittering in the 90–91
	// range) a dedupe filter would leave the buffer stuck at a single sample
	// and the sparkline would collapse into a triangle from the first point
	// down to the right edge.
	let buffer = $state<Sample[]>([]);
	let seededKey = '';

	// Seed the buffer once per initialHistory payload. Key on length+firstTs so
	// a new agent (or a new fetch after server switch) re-seeds.
	$effect(() => {
		if (initialHistory.length === 0) return;
		const key = `${initialHistory.length}|${initialHistory[0]?.t ?? 0}|${initialHistory[initialHistory.length - 1]?.t ?? 0}`;
		if (key === seededKey) return;
		seededKey = key;
		const cutoff = Date.now() - windowMs;
		buffer = initialHistory.filter((s) => s.t >= cutoff);
	});

	$effect(() => {
		const v = value;
		if (typeof v !== 'number' || Number.isNaN(v)) return;
		const now = Date.now();
		const cutoff = now - windowMs;
		const prev = untrack(() => buffer);
		buffer = [...prev.filter((s) => s.t >= cutoff), { t: now, v }];
	});

	const samples = $derived(
		history.length > 0 ? history : buffer.map((s) => s.v),
	);

	function toPath(values: number[], w: number, h: number, lo: number, hi: number) {
		if (values.length === 0) return { line: '', area: '' };
		const span = Math.max(1e-6, hi - lo);
		// One sample = horizontal line across the width (avoids the
		// top-left-to-bottom-right triangle fallback that looks like
		// a down-slope).
		if (values.length === 1) {
			const norm = Math.max(0, Math.min(1, (values[0] - lo) / span));
			const y = h - norm * h;
			const line = `M0,${y.toFixed(2)} L${w.toFixed(2)},${y.toFixed(2)}`;
			const area = `${line} L${w.toFixed(2)},${h.toFixed(2)} L0,${h.toFixed(2)} Z`;
			return { line, area };
		}
		const step = w / (values.length - 1);
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
