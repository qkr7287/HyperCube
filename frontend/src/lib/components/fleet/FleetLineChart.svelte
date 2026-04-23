<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import {
		CategoryScale,
		Chart,
		LineController,
		LineElement,
		LinearScale,
		PointElement,
		Tooltip,
		Filler,
	} from 'chart.js';
	import MetricHelp from './MetricHelp.svelte';

	Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler);

	type Series = { label: string; values: number[]; color: string; hidden?: boolean };

	let {
		title,
		labels,
		series,
		unit = 'percent',
		help = '',
	}: {
		title: string;
		labels: string[];
		series: Series[];
		unit?: 'percent' | 'rate';
		help?: string;
	} = $props();

	let canvas: HTMLCanvasElement | null = null;
	let chart: Chart | null = null;

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

	function peakValue(): number {
		let peak = 0;
		for (const item of series) {
			if (item.hidden) continue;
			for (const value of item.values) {
				if (value > peak) peak = value;
			}
		}
		return peak;
	}

	function buildDatasets() {
		return series.map((item) => ({
			label: item.label,
			data: [...item.values],
			borderColor: item.color,
			backgroundColor: `${item.color}24`,
			borderWidth: 2,
			pointRadius: 0,
			pointHoverRadius: 3,
			tension: 0.32,
			fill: false,
			hidden: item.hidden ?? false,
		}));
	}

	function render() {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'line',
			data: {
				labels: [...labels],
				datasets: buildDatasets(),
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 200 },
				interaction: { mode: 'index', intersect: false },
				plugins: {
					legend: {
						display: series.length > 1,
						labels: { color: '#94a3b8', boxWidth: 10, font: { size: 10 } },
					},
					tooltip: {
						backgroundColor: 'rgba(13,17,23,0.96)',
						borderColor: 'rgba(48,213,200,0.35)',
						borderWidth: 1,
						callbacks: {
							label: (ctx) => `${ctx.dataset.label}: ${formatValue(Number(ctx.parsed.y ?? 0))}`,
						},
					},
				},
				scales: {
					x: {
						grid: { color: 'rgba(100,116,139,0.08)' },
						ticks: { color: '#64748b', maxRotation: 0, autoSkipPadding: 18, font: { size: 10 } },
					},
					y: {
						beginAtZero: true,
						max: unit === 'percent' ? 100 : undefined,
						suggestedMax: unit === 'rate' ? Math.max(peakValue() * 1.15, 1024) : undefined,
						grid: { color: 'rgba(100,116,139,0.12)' },
						ticks: {
							color: '#64748b',
							font: { size: 10 },
							maxTicksLimit: 6,
							callback: (v) => formatValue(Number(v)),
						},
					},
				},
			},
		});
	}

	function sync() {
		if (!canvas) return;
		if (!chart) {
			render();
			return;
		}
		chart.data.labels = [...labels];
		chart.data.datasets = buildDatasets();
		if (unit === 'rate' && chart.options.scales?.y) {
			(chart.options.scales.y as any).suggestedMax = Math.max(peakValue() * 1.15, 1024);
		}
		chart.update('none');
	}

	$effect(() => {
		labels;
		series;
		sync();
	});

	onMount(sync);
	onDestroy(() => chart?.destroy());
</script>

<div class="chart">
	<div class="chart-title">
		<span>{title}</span>
		{#if help}<MetricHelp text={help} placement="bottom-end" />{/if}
	</div>
	<div class="canvas-wrap">
		<canvas bind:this={canvas}></canvas>
	</div>
</div>

<style>
	.chart {
		min-width: 0;
		padding: 10px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
	}
	.chart-title {
		display: flex;
		align-items: center;
		gap: 2px;
		margin-bottom: 6px;
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 800;
	}
	.canvas-wrap {
		height: 190px;
		min-width: 0;
	}
</style>
