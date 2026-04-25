<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { ArcElement, Chart, DoughnutController, Tooltip, type ChartData } from 'chart.js';

	Chart.register(ArcElement, DoughnutController, Tooltip);

	type Segment = {
		label: string;
		value: number;
		color: string;
	};

	let {
		title = '',
		segments = [] as Segment[],
		centerLabel = '',
		centerValue = '',
	}: {
		title?: string;
		segments?: Segment[];
		centerLabel?: string;
		centerValue?: string;
	} = $props();

	let canvas: HTMLCanvasElement | null = null;
	let chart: Chart | null = null;

	function buildData(): ChartData<'doughnut'> {
		const visible = segments.filter((s) => s.value > 0);
		if (visible.length === 0) {
			return {
				labels: ['데이터 없음'],
				datasets: [
					{
						data: [1],
						backgroundColor: ['rgba(100, 116, 139, 0.25)'],
						borderColor: ['rgba(15, 23, 42, 0.9)'],
						borderWidth: 2,
					},
				],
			};
		}
		return {
			labels: visible.map((s) => s.label),
			datasets: [
				{
					data: visible.map((s) => s.value),
					backgroundColor: visible.map((s) => s.color),
					borderColor: visible.map(() => 'rgba(15, 23, 42, 0.95)'),
					borderWidth: 2,
					hoverOffset: 6,
				},
			],
		};
	}

	function render() {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'doughnut',
			data: buildData(),
			options: {
				responsive: true,
				maintainAspectRatio: false,
				cutout: '66%',
				animation: { duration: 260 },
				plugins: {
					legend: { display: false },
					tooltip: {
						backgroundColor: 'rgba(13, 17, 23, 0.96)',
						borderColor: 'rgba(148, 163, 184, 0.22)',
						borderWidth: 1,
						displayColors: true,
						callbacks: {
							label: (ctx) => `${ctx.label}: ${ctx.parsed} 개`,
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
		chart.data = buildData();
		chart.update('none');
	}

	$effect(() => {
		segments;
		sync();
	});

	onMount(sync);
	onDestroy(() => chart?.destroy());
</script>

<div class="donut-card">
	{#if title}
		<div class="title">{title}</div>
	{/if}
	<div class="chart-wrap">
		<div class="canvas-square">
			<canvas bind:this={canvas}></canvas>
			{#if centerLabel || centerValue}
				<div class="center-label" aria-hidden="true">
					<strong>{centerValue}</strong>
					<small>{centerLabel}</small>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.donut-card {
		display: grid;
		grid-template-rows: minmax(0, 1fr);
		min-width: 0;
		min-height: 0;
		padding: 0;
		border: 0;
		border-radius: 0;
		background: transparent;
	}

	.title {
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 850;
	}

	.chart-wrap {
		position: relative;
		width: 100%;
		height: 100%;
		min-height: 0;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.canvas-square {
		position: relative;
		width: min(100%, 100cqh);
		aspect-ratio: 1 / 1;
		max-width: 100%;
		max-height: 100%;
	}

	canvas {
		width: 100% !important;
		height: 100% !important;
	}

	.center-label {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		pointer-events: none;
	}

	.center-label strong {
		color: var(--text-primary);
		font-size: clamp(14px, 3.2vw, 22px);
		font-weight: 900;
		line-height: 1;
	}

	.center-label small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 3px 8px;
		font-size: 9px;
	}

	.row {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: var(--text-secondary);
	}

	.row i {
		width: 7px;
		height: 7px;
		border-radius: 2px;
	}

	.row span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.row b {
		color: var(--text-primary);
		font-weight: 800;
	}
</style>
