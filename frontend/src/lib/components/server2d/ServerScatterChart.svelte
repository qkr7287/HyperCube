<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import {
		Chart,
		type ChartData,
		type Plugin,
		Legend,
		LinearScale,
		PointElement,
		ScatterController,
		Tooltip,
	} from 'chart.js';

	type ScatterPoint = {
		x: number;
		y: number;
		r: number;
		rawX?: number;
		rawY?: number;
		label: string;
		stack: string;
		state: string;
		network: number;
		color: string;
	};

	let {
		points = [],
		soloStack = null as string | null,
	}: {
		points?: ScatterPoint[];
		soloStack?: string | null;
	} = $props();

	Chart.register(ScatterController, PointElement, LinearScale, Tooltip, Legend);

	const quadrantPlugin: Plugin<'scatter'> = {
		id: 'quadrants',
		beforeDraw(chart) {
			const { ctx, chartArea, scales } = chart;
			if (!chartArea || !scales.x || !scales.y) return;
			const midX = scales.x.getPixelForValue(50);
			const midY = scales.y.getPixelForValue(50);
			ctx.save();
			ctx.fillStyle = 'rgba(248, 113, 113, 0.08)';
			ctx.fillRect(midX, chartArea.top, chartArea.right - midX, midY - chartArea.top);
			ctx.fillStyle = 'rgba(251, 191, 36, 0.06)';
			ctx.fillRect(chartArea.left, chartArea.top, midX - chartArea.left, midY - chartArea.top);
			ctx.fillStyle = 'rgba(96, 165, 250, 0.06)';
			ctx.fillRect(chartArea.left, midY, midX - chartArea.left, chartArea.bottom - midY);
			ctx.fillStyle = 'rgba(52, 211, 153, 0.06)';
			ctx.fillRect(midX, midY, chartArea.right - midX, chartArea.bottom - midY);

			ctx.strokeStyle = 'rgba(148, 163, 184, 0.22)';
			ctx.setLineDash([4, 4]);
			ctx.lineWidth = 1;
			ctx.beginPath();
			ctx.moveTo(midX, chartArea.top);
			ctx.lineTo(midX, chartArea.bottom);
			ctx.moveTo(chartArea.left, midY);
			ctx.lineTo(chartArea.right, midY);
			ctx.stroke();
			ctx.setLineDash([]);

			ctx.fillStyle = 'rgba(148, 163, 184, 0.75)';
			ctx.font = '700 10px system-ui';
			ctx.textAlign = 'right';
			ctx.fillText('HOT', chartArea.right - 6, chartArea.top + 13);
			ctx.textAlign = 'left';
			ctx.fillStyle = 'rgba(148, 163, 184, 0.55)';
			ctx.fillText('IDLE', chartArea.left + 6, chartArea.bottom - 6);
			ctx.restore();
		},
	};

	let canvas: HTMLCanvasElement | null = null;
	let canvasWrap: HTMLDivElement | null = null;
	let chart: Chart | null = null;
	let resizeObs: ResizeObserver | null = null;

	function formatRate(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let index = 0;
		while (next >= 1024 && index < units.length - 1) {
			next /= 1024;
			index += 1;
		}
		return `${next.toFixed(next >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
	}

	function visiblePoints() {
		if (!soloStack) return points;
		return points.filter((point) => point.stack === soloStack);
	}

	function buildData(): ChartData<'scatter'> {
		const shown = visiblePoints();
		return {
			datasets: [
				{
					label: '컨테이너 평균 분포',
					data: shown.map((point) => ({
						x: point.x,
						y: point.y,
						r: point.r,
						rawX: point.rawX ?? point.x,
						rawY: point.rawY ?? point.y,
						label: point.label,
						stack: point.stack,
						state: point.state,
						network: point.network,
					})),
					pointBackgroundColor: shown.map((point) => point.color),
					pointBorderColor: shown.map(() => 'rgba(15, 23, 42, 0.9)'),
					pointBorderWidth: shown.map(() => 1.2),
					pointHoverRadius: shown.map((point) => point.r + 2),
				},
			],
		};
	}

	function renderChart() {
		if (!canvas) return;
		chart?.destroy();
		chart = new Chart(canvas, {
			type: 'scatter',
			data: buildData(),
			plugins: [quadrantPlugin],
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 180 },
				interaction: { mode: 'nearest', intersect: true },
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: 'rgba(15, 23, 42, 0.96)',
						borderColor: 'rgba(148, 163, 184, 0.22)',
						borderWidth: 1,
						displayColors: false,
						callbacks: {
							title(items) {
								const raw = items[0]?.raw as any;
								return raw?.label ?? '컨테이너';
							},
							label(item) {
								const raw = item.raw as any;
								return [
									`스택: ${raw.stack}`,
									`상태: ${raw.state}`,
									`메모리 평균: ${Number(raw.rawX ?? raw.x ?? 0).toFixed(1)}%`,
									`CPU 평균: ${Number(raw.rawY ?? raw.y ?? 0).toFixed(1)}%`,
									`트래픽 평균: ${formatRate(Number(raw.network ?? 0))}`,
								];
							},
						},
					},
				},
				layout: { padding: { top: 14, right: 14, bottom: 4, left: 4 } },
				clip: false,
				scales: {
					x: {
						min: 0,
						max: 100,
						title: {
							display: true,
							text: '메모리 %',
							color: '#94a3b8',
							font: { size: 9, weight: 700 },
							padding: { top: 0, bottom: 0 },
						},
						grid: { color: 'rgba(100, 116, 139, 0.08)' },
						ticks: { color: '#64748b', stepSize: 25, font: { size: 9 }, padding: 2 },
					},
					y: {
						min: 0,
						max: 100,
						title: {
							display: true,
							text: 'CPU %',
							color: '#94a3b8',
							font: { size: 9, weight: 700 },
							padding: { top: 0, bottom: 0 },
						},
						grid: { color: 'rgba(100, 116, 139, 0.12)' },
						ticks: { color: '#64748b', stepSize: 25, font: { size: 9 }, padding: 2 },
					},
				},
			},
		});
	}

	$effect(() => {
		points;
		soloStack;
		if (canvas) renderChart();
	});

	onMount(() => {
		renderChart();
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

<div class="scatter-wrap" bind:this={canvasWrap}>
	<canvas bind:this={canvas}></canvas>
	{#if soloStack}
		<div class="solo-tag">솔로: {soloStack}</div>
	{/if}
</div>

<style>
	.scatter-wrap {
		width: 100%;
		height: 100%;
		min-width: 0;
		min-height: 0;
		position: relative;
	}

	canvas {
		width: 100%;
		height: 100%;
	}

	.solo-tag {
		position: absolute;
		top: 8px;
		left: 8px;
		padding: 2px 8px;
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.16);
		color: #30d5c8;
		border: 1px solid rgba(48, 213, 200, 0.4);
		font-size: 10px;
		font-weight: 800;
		pointer-events: none;
	}
</style>
