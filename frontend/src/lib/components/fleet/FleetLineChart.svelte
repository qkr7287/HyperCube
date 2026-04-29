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
		type Plugin,
	} from 'chart.js';
	import MetricHelp from './MetricHelp.svelte';
	import { toChartPayload } from '$lib/utils/chart-helpers';

	Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler);

	type Series = { label: string; values: number[]; color: string; hidden?: boolean };

	let {
		title,
		labels,
		series,
		unit = 'percent',
		help = '',
		topNames = [],
		soloLabel = null,
		extraPlugins = [],
		rightPadding = 0,
		loading = false,
	}: {
		title: string;
		labels: string[];
		series: Series[];
		unit?: 'percent' | 'rate';
		help?: string;
		topNames?: string[];
		soloLabel?: string | null;
		extraPlugins?: Plugin[];
		rightPadding?: number;
		loading?: boolean;
	} = $props();

	let canvas: HTMLCanvasElement | null = null;
	let canvasWrap: HTMLDivElement | null = null;
	let chart: Chart | null = null;
	let resizeObs: ResizeObserver | null = null;

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
			if (soloLabel && item.label !== soloLabel) continue;
			for (const value of item.values) {
				if (value > peak) peak = value;
			}
		}
		return peak;
	}

	function percentAxisMax(): number {
		const peak = peakValue();
		if (peak <= 0) return 5;
		const padded = peak * 1.2;
		const stops = [2, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100];
		for (const stop of stops) {
			if (padded <= stop) return stop;
		}
		return 100;
	}

	function rateAxisMax(): number {
		const peak = peakValue();
		if (peak <= 0) return 1024;
		const padded = peak * 1.2;
		const magnitude = Math.pow(10, Math.floor(Math.log10(padded)));
		return Math.ceil(padded / magnitude) * magnitude;
	}

	function isHighlighted(label: string): boolean {
		if (soloLabel) return label === soloLabel;
		if (topNames.length === 0) return true;
		return topNames.includes(label);
	}

	function dimColor(color: string): string {
		if (color.startsWith('#') && color.length === 7) {
			return color + '7a';
		}
		return color;
	}

	function buildDatasets() {
		return series.map((item) => {
			const highlighted = isHighlighted(item.label);
			const forceHidden = Boolean(soloLabel) && item.label !== soloLabel;
			const color = highlighted ? item.color : dimColor(item.color);
			return {
				label: item.label,
				data: [...item.values],
				borderColor: color,
				backgroundColor: `${color}18`,
				borderWidth: highlighted ? 2.4 : 1.4,
				pointRadius: 0,
				pointHoverRadius: highlighted ? 3 : 0,
				tension: 0.32,
				fill: false,
				hidden: (item.hidden ?? false) || forceHidden,
				order: highlighted ? 0 : 1,
			};
		});
	}

	function render() {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'line',
			data: toChartPayload({
				labels: [...labels],
				datasets: buildDatasets(),
			}),
			plugins: extraPlugins,
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 200 },
				interaction: { mode: 'index', intersect: false },
				layout: rightPadding > 0 ? { padding: { right: rightPadding } } : undefined,
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: 'rgba(13,17,23,0.96)',
						borderColor: 'rgba(48,213,200,0.35)',
						borderWidth: 1,
						filter: (item: any) => {
							const label = item.dataset.label ?? '';
							if (soloLabel) return label === soloLabel;
							if (topNames.length === 0) return true;
							return topNames.includes(label);
						},
						callbacks: {
							label: (ctx: any) => `${ctx.dataset.label}: ${formatValue(Number(ctx.parsed.y ?? 0))}`,
						},
					},
					rightEdgeLabels: {
						enabled: topNames.length > 0,
						topNames: new Set(topNames),
						format: formatValue,
					},
				} as any,
				scales: {
					x: {
						grid: { color: 'rgba(100,116,139,0.08)' },
						ticks: { color: '#64748b', maxRotation: 0, autoSkipPadding: 18, font: { size: 10 } },
					},
					y: {
						beginAtZero: true,
						max: unit === 'percent' ? percentAxisMax() : rateAxisMax(),
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
		// chart.js v4 의 in-place options mutation (plugins / layout / scales 직접
		// 변경) 은 internal options resolver scope cache 를 dirty 하게 만들어
		// 장시간 사용 시 _resolveWithContext 무한 재귀 (RangeError) 가 발생할 수
		// 있다. polling 마다 데이터/플러그인/스케일을 모두 in-place 로 갈아치우는
		// 본 컴포넌트가 가장 mutation 빈도가 높아 destroy + recreate 으로 통일.
		if (chart) {
			chart.destroy();
			chart = null;
		}
		render();
	}

	$effect(() => {
		labels;
		series;
		topNames;
		soloLabel;
		sync();
	});

	onMount(() => {
		sync();
		if (canvasWrap && typeof ResizeObserver !== 'undefined') {
			resizeObs = new ResizeObserver(() => chart?.resize());
			resizeObs.observe(canvasWrap);
		}
	});
	onDestroy(() => {
		resizeObs?.disconnect();
		chart?.destroy();
	});
</script>

<div class="chart">
	<div class="chart-title">
		<span>{title}</span>
		{#if help}<MetricHelp text={help} placement="bottom-end" />{/if}
	</div>
	<div class="canvas-wrap" bind:this={canvasWrap}>
		<canvas bind:this={canvas}></canvas>
		{#if loading}
			<div class="loading-overlay" role="status" aria-live="polite">
				<span class="spinner"></span>
				<span class="loading-label">갱신 중...</span>
			</div>
		{/if}
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
		position: relative;
		height: 190px;
		width: 100%;
		min-width: 0;
		overflow: hidden;
	}
	.canvas-wrap canvas {
		max-width: 100% !important;
		max-height: 100% !important;
	}
	.loading-overlay {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 6px;
		background: rgba(13, 17, 23, 0.55);
		backdrop-filter: blur(1px);
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 600;
		border-radius: 4px;
		pointer-events: none;
		z-index: 2;
	}
	.spinner {
		width: 22px;
		height: 22px;
		border: 2px solid rgba(48, 213, 200, 0.2);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spin 0.85s linear infinite;
	}
	.loading-label {
		color: var(--text-secondary);
		letter-spacing: 0.4px;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
</style>
