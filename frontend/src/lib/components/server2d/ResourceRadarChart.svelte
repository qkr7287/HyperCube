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
	let chart: Chart | null = null;

	function buildData(): ChartData<'radar'> {
		const hasReference = axes.some((a) => typeof a.reference === 'number');
		const datasets: any[] = [
			{
				label: '현재',
				data: axes.map((a) => Math.max(0, Math.min(100, a.value))),
				backgroundColor: `${primaryColor}33`,
				borderColor: primaryColor,
				borderWidth: 2,
				pointBackgroundColor: primaryColor,
				pointBorderColor: 'rgba(15, 23, 42, 0.9)',
				pointBorderWidth: 1.2,
				pointRadius: 3,
				pointHoverRadius: 5,
				fill: true,
			},
		];
		if (hasReference) {
			datasets.push({
				label: '평균',
				data: axes.map((a) => Math.max(0, Math.min(100, a.reference ?? 0))),
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

	function render() {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'radar',
			data: buildData(),
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
						max: 100,
						beginAtZero: true,
						angleLines: { color: 'rgba(100, 116, 139, 0.25)' },
						grid: { color: 'rgba(100, 116, 139, 0.18)' },
						pointLabels: {
							color: '#cbd5e1',
							font: { size: 11, weight: 700 },
						},
						ticks: {
							display: false,
							stepSize: 25,
						},
					},
				},
			},
		});
	}

	function sync() {
		if (!canvas) return;
		if (!chart) return render();
		chart.data = buildData();
		chart.update('none');
	}

	$effect(() => {
		axes;
		primaryColor;
		sync();
	});

	onMount(sync);
	onDestroy(() => chart?.destroy());
</script>

<div class="radar">
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
