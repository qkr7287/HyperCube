<script lang="ts">
	import { onDestroy } from 'svelte';
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
		type ChartDataset,
	} from 'chart.js';
	import { formatBytesValue } from '$lib/utils/container-dashboard';

	Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, Legend);

	type ValueFormat = 'percent' | 'bytes' | 'count';
	type Series = {
		label: string;
		color: string;
		values: number[];
		fill?: boolean;
		format?: ValueFormat;
	};

	let {
		labels = [],
		datasets = [],
		yFormat = 'percent',
	}: {
		labels?: string[];
		datasets?: Series[];
		yFormat?: ValueFormat;
	} = $props();

	let canvas = $state<HTMLCanvasElement | null>(null);
	let chart: Chart | null = null;

	function percentDecimals(): number {
		// y축이 모두 "0%" 로 뭉개지지 않도록, 데이터 절대 최댓값에 맞춰 소수 자릿수를 조정한다.
		// 모두 0 인 경우엔 axis 가 자동으로 0~1 까지 그려지므로 "0%" 정수로 표기.
		let maxAbs = 0;
		for (const ds of datasets) {
			for (const v of ds.values) {
				if (Number.isFinite(v) && Math.abs(v) > maxAbs) maxAbs = Math.abs(v);
			}
		}
		if (maxAbs === 0) return 0;
		if (maxAbs < 0.1) return 3;
		if (maxAbs < 1) return 2;
		if (maxAbs < 10) return 1;
		return 0;
	}

	function formatValue(value: number, format: ValueFormat): string {
		if (format === 'bytes') return formatBytesValue(value);
		if (format === 'count') return `${Math.round(value)}`;
		const decimals = format === 'percent' ? Math.max(percentDecimals(), 2) : 1;
		return `${value.toFixed(decimals)}%`;
	}

	function axisLabel(value: number): string {
		if (yFormat === 'bytes') return formatBytesValue(value);
		if (yFormat === 'count') return `${Math.round(value)}`;
		return `${value.toFixed(percentDecimals())}%`;
	}

	function buildDatasets(): ChartDataset<'line'>[] {
		return datasets.map((dataset) => ({
			label: dataset.label,
			data: [...dataset.values],
			borderColor: dataset.color,
			backgroundColor: dataset.fill ? `${dataset.color}1f` : `${dataset.color}12`,
			borderWidth: 2,
			fill: dataset.fill ?? false,
			tension: 0.32,
			pointRadius: 0,
			pointHoverRadius: 4,
			pointHoverBackgroundColor: dataset.color,
			pointHoverBorderColor: '#0d1117',
			pointHoverBorderWidth: 2,
		}));
	}

	function ensureChart() {
		if (!canvas || chart) return;
		const context = canvas.getContext('2d');
		if (!context) return;

		chart = new Chart(context, {
			type: 'line',
			data: {
				labels: [...labels],
				datasets: buildDatasets(),
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 250 },
				interaction: { intersect: false, mode: 'index' },
				plugins: {
					legend: {
						display: datasets.length > 1,
						position: 'top',
						align: 'start',
						labels: {
							color: '#94a3b8',
							boxWidth: 10,
							boxHeight: 10,
							usePointStyle: true,
							pointStyle: 'circle',
						},
					},
					tooltip: {
						backgroundColor: '#121720',
						borderColor: '#1f2937',
						borderWidth: 1,
						titleColor: '#e2e8f0',
						bodyColor: '#cbd5e1',
						displayColors: datasets.length > 1,
						callbacks: {
							label: (item) => {
								const format = datasets[item.datasetIndex]?.format ?? yFormat;
								return `${item.dataset.label}: ${formatValue(Number(item.parsed.y ?? 0), format)}`;
							},
						},
					},
				},
				scales: {
					x: {
						grid: { color: 'rgba(255,255,255,0.04)' },
						ticks: {
							color: '#64748b',
							maxTicksLimit: 8,
							autoSkip: true,
						},
						border: { display: false },
					},
					y: {
						grid: { color: 'rgba(255,255,255,0.05)' },
						ticks: {
							color: '#64748b',
							callback: (value) => axisLabel(Number(value)),
						},
						border: { display: false },
						beginAtZero: true,
					},
				},
			},
		});
	}

	function updateChart() {
		if (!canvas) return;
		ensureChart();
		if (!chart) return;

		chart.data.labels = [...labels];
		chart.data.datasets = buildDatasets();
		chart.update('none');
	}

	$effect(() => {
		canvas;
		labels;
		datasets;
		yFormat;
		updateChart();
	});

	onDestroy(() => {
		chart?.destroy();
		chart = null;
	});
</script>

<div class="chart-shell">
	<canvas bind:this={canvas}></canvas>
</div>

<style>
	.chart-shell {
		position: relative;
		height: 240px;
		min-height: 240px;
		max-height: 240px;
		overflow: hidden;
	}

	canvas {
		display: block;
		width: 100% !important;
		height: 240px !important;
		max-height: 240px !important;
	}
</style>
