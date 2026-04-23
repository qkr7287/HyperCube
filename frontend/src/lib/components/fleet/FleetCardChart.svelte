<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import {
		CategoryScale,
		Chart,
		Filler,
		Legend,
		LineController,
		LineElement,
		LinearScale,
		PointElement,
		Tooltip,
	} from 'chart.js';

	Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler, Legend);

	type Series = { values: number[]; color: string; label?: string };

	type RangeKey = '1m' | '5m' | '1h' | '24h' | '7d';

	let {
		series,
		unit = 'percent',
		maxY,
		showLegend = false,
		range = '1h',
		showAxes = true,
	}: {
		series: Series | Series[];
		unit?: 'percent' | 'rate';
		maxY?: number;
		showLegend?: boolean;
		range?: RangeKey;
		showAxes?: boolean;
	} = $props();

	const BUCKET_SEC: Record<RangeKey, number> = { '1m': 5, '5m': 15, '1h': 60, '24h': 300, '7d': 1800 };

	function buildTimeLabels(count: number): string[] {
		if (count === 0) return [];
		const interval = BUCKET_SEC[range] * 1000;
		const now = Date.now();
		const labels: string[] = [];
		for (let i = 0; i < count; i += 1) {
			const at = now - (count - 1 - i) * interval;
			const d = new Date(at);
			if (range === '7d') {
				const mo = String(d.getMonth() + 1).padStart(2, '0');
				const day = String(d.getDate()).padStart(2, '0');
				const hh = String(d.getHours()).padStart(2, '0');
				labels.push(`${mo}/${day} ${hh}h`);
			} else if (range === '24h') {
				const hh = String(d.getHours()).padStart(2, '0');
				const mm = String(d.getMinutes()).padStart(2, '0');
				labels.push(`${hh}:${mm}`);
			} else if (range === '1m') {
				const mm = String(d.getMinutes()).padStart(2, '0');
				const ss = String(d.getSeconds()).padStart(2, '0');
				labels.push(`${mm}:${ss}`);
			} else {
				const hh = String(d.getHours()).padStart(2, '0');
				const mm = String(d.getMinutes()).padStart(2, '0');
				labels.push(`${hh}:${mm}`);
			}
		}
		return labels;
	}

	let canvas: HTMLCanvasElement | null = null;
	let chart: Chart | null = null;
	let seriesList = $derived(Array.isArray(series) ? series : [series]);

	function formatValue(value: number): string {
		if (unit === 'percent') return `${value.toFixed(1)}%`;
		if (value < 1) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let idx = 0;
		while (next >= 1000 && idx < units.length - 1) {
			next /= 1024;
			idx += 1;
		}
		const digits = next >= 10 ? 0 : 1;
		return `${next.toFixed(digits)} ${units[idx]}`;
	}

	function peakValue(list: Series[]): number {
		let peak = 0;
		for (const item of list) {
			for (const value of item.values) if (value > peak) peak = value;
		}
		return peak;
	}

	function buildGradient(ctx: CanvasRenderingContext2D, color: string): CanvasGradient {
		const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.clientHeight || 100);
		gradient.addColorStop(0, `${color}60`);
		gradient.addColorStop(0.6, `${color}18`);
		gradient.addColorStop(1, `${color}00`);
		return gradient;
	}

	function buildDatasets(list: Series[]) {
		if (!canvas) return [];
		const ctx = canvas.getContext('2d');
		return list.map((item) => ({
			label: item.label ?? '',
			data: [...item.values],
			borderColor: item.color,
			backgroundColor: ctx ? buildGradient(ctx, item.color) : `${item.color}30`,
			borderWidth: 2,
			pointRadius: 0,
			pointHoverRadius: 3,
			tension: 0.35,
			fill: list.length === 1 ? 'origin' : false,
			cubicInterpolationMode: 'monotone' as const,
		}));
	}

	function maxLabels(list: Series[]): number {
		let n = 0;
		for (const item of list) if (item.values.length > n) n = item.values.length;
		return n;
	}

	function render() {
		if (!canvas) return;
		const list = seriesList;
		const n = maxLabels(list);
		const suggestedMax = unit === 'percent' ? 100 : Math.max(peakValue(list) * 1.15, 1024);
		chart = new Chart(canvas, {
			type: 'line',
			data: {
				labels: buildTimeLabels(n),
				datasets: buildDatasets(list),
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: {
					duration: 1400,
					easing: 'easeInOutQuart',
				},
				animations: {
					x: { duration: 1400, easing: 'easeInOutQuart' },
					y: { duration: 1000, easing: 'easeOutQuart' },
					numbers: { duration: 1400, easing: 'easeInOutQuart' },
				},
				transitions: {
					active: { animation: { duration: 1400, easing: 'easeInOutQuart' } },
				},
				interaction: { mode: 'index', intersect: false },
				plugins: {
					legend: {
						display: showLegend || list.length > 1,
						position: 'top' as const,
						align: 'end' as const,
						labels: {
							color: 'rgba(203,213,225,0.85)',
							boxWidth: 8,
							boxHeight: 8,
							padding: 8,
							font: { size: 10, weight: 700 },
							usePointStyle: true,
							pointStyle: 'rectRounded' as const,
						},
					},
					tooltip: {
						backgroundColor: 'rgba(13,17,23,0.96)',
						borderColor: 'rgba(48,213,200,0.35)',
						borderWidth: 1,
						padding: 8,
						displayColors: true,
						callbacks: {
							title: (items) => (items?.[0]?.label ? String(items[0].label) : ''),
							label: (ctx) => {
								const label = ctx.dataset.label ? `${ctx.dataset.label}: ` : '';
								return `${label}${formatValue(Number(ctx.parsed.y ?? 0))}`;
							},
						},
					},
				},
				scales: {
					x: {
						display: showAxes,
						grid: { display: false },
						border: { display: false },
						ticks: {
							color: '#64748b',
							font: { size: 9 },
							maxTicksLimit: 4,
							maxRotation: 0,
							autoSkip: true,
							autoSkipPadding: 12,
						},
					},
					y: {
						display: showAxes,
						beginAtZero: true,
						min: 0,
						max: unit === 'percent' ? (maxY ?? 100) : undefined,
						suggestedMax: unit === 'rate' ? suggestedMax : undefined,
						grid: { color: 'rgba(100,116,139,0.08)' },
						border: { display: false },
						ticks: {
							color: '#64748b',
							font: { size: 9 },
							maxTicksLimit: 4,
							callback: (v) => formatValue(Number(v)),
						},
					},
				},
			},
		});
	}

	function streamUpdate(list: Series[]) {
		if (!chart) return;
		const datasets = chart.data.datasets;
		const targetLength = maxLabels(list);
		// Keep label count stable to force chart.js to animate each point in place,
		// creating a left-flowing stream when new values are appended.
		chart.data.labels = buildTimeLabels(targetLength);

		for (let i = 0; i < list.length; i += 1) {
			const item = list[i];
			if (!datasets[i]) continue;
			const current = (datasets[i].data as number[]) ?? [];
			const incoming = [...item.values];
			// Align lengths so each point animates to its neighbor's previous position
			// (point N is now at position N-1, producing a scroll-left effect).
			while (current.length < incoming.length) current.unshift(incoming[0] ?? 0);
			while (current.length > incoming.length) current.shift();
			for (let j = 0; j < incoming.length; j += 1) current[j] = incoming[j];
			datasets[i].data = current;
		}
	}

	function sync() {
		if (!canvas) return;
		if (!chart) {
			render();
			return;
		}
		const list = seriesList;
		const structureChanged = chart.data.datasets.length !== list.length;

		if (structureChanged) {
			chart.data.labels = buildTimeLabels(maxLabels(list));
			chart.data.datasets = buildDatasets(list);
		} else {
			streamUpdate(list);
		}

		if (unit === 'rate' && chart.options.scales?.y) {
			(chart.options.scales.y as any).suggestedMax = Math.max(peakValue(list) * 1.15, 1024);
		}
		chart.update(structureChanged ? 'none' : 'active');
	}

	$effect(() => {
		seriesList;
		range;
		sync();
	});

	onMount(sync);
	onDestroy(() => {
		chart?.destroy();
		chart = null;
	});
</script>

<div class="wrap">
	<canvas bind:this={canvas}></canvas>
</div>

<style>
	.wrap {
		width: 100%;
		height: 100%;
		min-height: 0;
		min-width: 0;
	}
	canvas {
		width: 100% !important;
		height: 100% !important;
	}
</style>
