<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import {
		Chart,
		Filler,
		LineElement,
		PointElement,
		RadarController,
		RadialLinearScale,
		Tooltip,
		type ChartData,
	} from 'chart.js';
	import { toChartPayload } from '$lib/utils/chart-helpers';

	Chart.register(RadarController, PointElement, LineElement, Filler, RadialLinearScale, Tooltip);

	type Axis = {
		label: string;
		value: number;
		reference?: number;
	};

	let {
		axes = [] as Axis[],
		primaryColor = '#30d5c8',
		referenceColor = '#94a3b8',
	}: {
		axes?: Axis[];
		primaryColor?: string;
		referenceColor?: string;
	} = $props();

	let canvas: HTMLCanvasElement | null = null;
	let canvasWrap: HTMLDivElement | null = null;
	let chart: Chart | null = null;
	let resizeObs: ResizeObserver | null = null;

	function buildData(): ChartData<'radar'> {
		const hasReference = axes.some((a) => typeof a.reference === 'number');
		const datasets: any[] = [
			{
				label: '현재',
				data: axes.map((a) => Math.max(0, a.value)),
				backgroundColor: `${primaryColor}55`,
				borderColor: primaryColor,
				borderWidth: 2.4,
				pointBackgroundColor: primaryColor,
				pointBorderColor: 'rgba(15, 23, 42, 0.9)',
				pointBorderWidth: 1.4,
				pointRadius: 3,
				pointHoverRadius: 5,
				fill: true,
			},
		];
		if (hasReference) {
			datasets.push({
				label: '평균',
				data: axes.map((a) => Math.max(0, a.reference ?? 0)),
				backgroundColor: `${referenceColor}14`,
				borderColor: `${referenceColor}88`,
				borderWidth: 1,
				borderDash: [4, 4],
				pointRadius: 0,
				fill: true,
			});
		}
		return {
			labels: axes.map((a) => a.label),
			datasets,
		};
	}

	function computeMax(): number {
		let peak = 0;
		for (const a of axes) {
			peak = Math.max(peak, a.value || 0, a.reference || 0);
		}
		if (peak <= 0) return 1;
		// peak에 padding을 거의 주지 않음 — 작은 값일수록 화면에 큼직하게
		// 그려지도록 가장 가까운 다음 stop만 사용
		const stops = [1, 2, 5, 10, 15, 20, 30, 50, 75, 100];
		for (const s of stops) {
			if (peak <= s) return s;
		}
		return 100;
	}

	function render() {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'radar',
			data: toChartPayload(buildData()),
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 320 },
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: 'rgba(13, 17, 23, 0.96)',
						borderColor: 'rgba(148, 163, 184, 0.22)',
						borderWidth: 1,
						displayColors: true,
						callbacks: {
							label: (ctx) => `${ctx.dataset.label}: ${Number(ctx.parsed.r ?? 0).toFixed(1)}%`,
						},
					},
				},
				scales: {
					r: {
						min: 0,
						max: computeMax(),
						beginAtZero: true,
						angleLines: { color: 'rgba(100, 116, 139, 0.25)' },
						grid: { color: 'rgba(100, 116, 139, 0.18)' },
						pointLabels: {
							color: '#cbd5e1',
							font: { size: 11, weight: 700 },
						},
						ticks: {
							display: true,
							color: '#475569',
							font: { size: 9 },
							backdropColor: 'transparent',
							stepSize: undefined,
							maxTicksLimit: 4,
							callback: (v) => `${Number(v).toFixed(0)}%`,
						},
					},
				},
			},
		});
	}

	// Streaming update: data 배열 reference 보존하며 element 만 in-place 갱신.
	function syncDatasets() {
		if (!chart) return;
		const incoming = buildData().datasets as any[];
		const cur = chart.data.datasets as any[];
		if (cur.length !== incoming.length) {
			chart.data.datasets = incoming;
			return;
		}
		for (let i = 0; i < incoming.length; i += 1) {
			const c = cur[i];
			const n = incoming[i];
			const cd = c.data as any[];
			const nd = n.data as any[];
			if (cd.length > nd.length) cd.length = nd.length;
			for (let j = 0; j < nd.length; j += 1) cd[j] = nd[j];
			c.backgroundColor = n.backgroundColor;
			c.borderColor = n.borderColor;
		}
	}

	function sync() {
		if (!canvas) return;
		if (!chart) return render();
		syncDatasets();
		const r = chart.options.scales?.r as any;
		if (r) r.max = computeMax();
		chart.update('none');
	}

	$effect(() => {
		axes;
		primaryColor;
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

<div class="radar" bind:this={canvasWrap}>
	<canvas bind:this={canvas}></canvas>
</div>

<style>
	.radar {
		width: 100%;
		height: 100%;
		min-width: 0;
		min-height: 0;
	}

	canvas {
		width: 100% !important;
		height: 100% !important;
	}
</style>
