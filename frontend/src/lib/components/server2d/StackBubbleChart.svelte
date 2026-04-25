<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import {
		BubbleController,
		Chart,
		LinearScale,
		PointElement,
		Tooltip,
		type ChartData,
		type Plugin,
	} from 'chart.js';
	import { view } from '$lib/stores/server2d-view.svelte';

	Chart.register(BubbleController, PointElement, LinearScale, Tooltip);

	type StackBubble = {
		name: string;
		color: string;
		cpu: number;
		memory: number;
		network: number;
		containers: number;
		problem: number;
	};

	let {
		stacks = [] as StackBubble[],
	}: {
		stacks?: StackBubble[];
	} = $props();

	let canvas: HTMLCanvasElement | null = null;
	let chart: Chart | null = null;

	const soloed = $derived(view.soloStack);

	function computeAxisMax(values: number[]): number {
		const dataMax = Math.max(0, ...values);
		if (dataMax <= 0) return 30;
		const padded = dataMax * 1.08 + 4;
		const stepped = Math.ceil(padded / 10) * 10;
		return Math.max(20, Math.min(100, stepped));
	}

	const xMax = $derived(computeAxisMax(stacks.map((s) => s.cpu)));
	const yMax = $derived(computeAxisMax(stacks.map((s) => s.memory)));

	const quadrantPlugin: Plugin = {
		id: 'bubbleQuadrants',
		beforeDraw(chart) {
			const { ctx, chartArea, scales } = chart;
			if (!chartArea || !scales.x || !scales.y) return;
			const xHalf = (scales.x.max ?? 100) / 2;
			const yHalf = (scales.y.max ?? 100) / 2;
			const midX = scales.x.getPixelForValue(xHalf);
			const midY = scales.y.getPixelForValue(yHalf);
			ctx.save();
			ctx.fillStyle = 'rgba(248, 113, 113, 0.06)';
			ctx.fillRect(midX, chartArea.top, chartArea.right - midX, midY - chartArea.top);
			ctx.fillStyle = 'rgba(96, 165, 250, 0.04)';
			ctx.fillRect(chartArea.left, midY, midX - chartArea.left, chartArea.bottom - midY);

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

			ctx.fillStyle = 'rgba(248, 113, 113, 0.75)';
			ctx.font = '700 10px system-ui';
			ctx.textAlign = 'right';
			ctx.fillText('고부하', chartArea.right - 6, chartArea.top + 13);
			ctx.textAlign = 'left';
			ctx.fillStyle = 'rgba(148, 163, 184, 0.55)';
			ctx.fillText('여유', chartArea.left + 6, chartArea.bottom - 6);
			ctx.restore();
		},
	};

	function bubbleRadius(count: number, maxCount: number): number {
		if (count <= 0) return 4;
		const min = 6;
		const max = 26;
		const ratio = Math.sqrt(count / Math.max(1, maxCount));
		return Math.max(min, Math.min(max, min + (max - min) * ratio));
	}

	function buildData(): ChartData<'bubble'> {
		const maxCount = Math.max(1, ...stacks.map((s) => s.containers));
		const points = stacks.map((s) => {
			const isDim = soloed && soloed !== s.name;
			const color = s.color;
			const fill = isDim ? `${color}18` : `${color}cc`;
			const stroke = isDim ? `${color}55` : color;
			return {
				data: [
					{
						x: Math.max(0, Math.min(100, s.cpu)),
						y: Math.max(0, Math.min(100, s.memory)),
						r: bubbleRadius(s.containers, maxCount),
						label: s.name,
						containers: s.containers,
						problem: s.problem,
						network: s.network,
					},
				],
				backgroundColor: fill,
				borderColor: stroke,
				borderWidth: isDim ? 1 : 1.8,
				hoverBorderWidth: 3,
			};
		});
		return {
			datasets: points as any,
		};
	}

	function formatRate(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let idx = 0;
		while (next >= 1024 && idx < units.length - 1) {
			next /= 1024;
			idx += 1;
		}
		return `${next.toFixed(next >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
	}

	function render() {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'bubble',
			data: buildData(),
			plugins: [quadrantPlugin],
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 260 },
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: 'rgba(13, 17, 23, 0.96)',
						borderColor: 'rgba(148, 163, 184, 0.22)',
						borderWidth: 1,
						displayColors: false,
						callbacks: {
							title: (items) => (items[0]?.raw as any)?.label ?? '스택',
							label: (ctx) => {
								const raw = ctx.raw as any;
								return [
									`CPU 평균: ${Number(raw.x ?? 0).toFixed(1)}%`,
									`메모리 평균: ${Number(raw.y ?? 0).toFixed(1)}%`,
									`컨테이너: ${raw.containers}개${raw.problem ? ` (문제 ${raw.problem})` : ''}`,
									`트래픽 평균: ${formatRate(raw.network ?? 0)}`,
								];
							},
						},
					},
				},
				layout: { padding: { top: 4, right: 8, bottom: 2, left: 2 } },
				scales: {
					x: {
						min: 0,
						max: xMax,
						title: { display: false },
						grid: { color: 'rgba(100, 116, 139, 0.08)' },
						ticks: { color: '#64748b', maxTicksLimit: 5, font: { size: 9 }, padding: 1 },
					},
					y: {
						min: 0,
						max: yMax,
						title: { display: false },
						grid: { color: 'rgba(100, 116, 139, 0.12)' },
						ticks: { color: '#64748b', maxTicksLimit: 5, font: { size: 9 }, padding: 1 },
					},
				},
			},
		});
	}

	function sync() {
		if (!canvas) return;
		if (!chart) return render();
		chart.data = buildData();
		const scales = chart.options.scales as any;
		if (scales?.x) scales.x.max = xMax;
		if (scales?.y) scales.y.max = yMax;
		chart.resize();
		chart.update('none');
	}

	$effect(() => {
		stacks;
		soloed;
		xMax;
		yMax;
		sync();
	});

	onMount(sync);
	onDestroy(() => chart?.destroy());
</script>

<div class="bubble">
	<canvas bind:this={canvas}></canvas>
</div>

<style>
	.bubble {
		position: relative;
		width: 100%;
		height: 100%;
		min-width: 0;
		min-height: 0;
	}

	.bubble canvas {
		display: block;
	}
</style>
