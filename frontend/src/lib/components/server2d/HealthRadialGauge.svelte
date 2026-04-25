<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { ArcElement, Chart, DoughnutController, type ChartData } from 'chart.js';

	Chart.register(ArcElement, DoughnutController);

	let {
		score = 0,
		label = '건강 점수',
		tone = 'ok' as 'ok' | 'warn' | 'hot' | 'dim',
	}: {
		score?: number;
		label?: string;
		tone?: 'ok' | 'warn' | 'hot' | 'dim';
	} = $props();

	let canvas: HTMLCanvasElement | null = null;
	let chart: Chart | null = null;

	const toneColors: Record<'ok' | 'warn' | 'hot' | 'dim', string> = {
		ok: '#34d399',
		warn: '#fbbf24',
		hot: '#f87171',
		dim: '#64748b',
	};

	function buildData(): ChartData<'doughnut'> {
		const value = Math.max(0, Math.min(100, Math.round(score)));
		return {
			labels: ['점수', '여유'],
			datasets: [
				{
					data: [value, 100 - value],
					backgroundColor: [toneColors[tone], 'rgba(51, 65, 85, 0.5)'],
					borderColor: ['rgba(15, 23, 42, 0.95)', 'rgba(15, 23, 42, 0.95)'],
					borderWidth: 1,
					circumference: 270,
					rotation: 225,
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
				cutout: '74%',
				animation: { duration: 280 },
				plugins: { legend: { display: false }, tooltip: { enabled: false } },
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
		score;
		tone;
		sync();
	});

	onMount(sync);
	onDestroy(() => chart?.destroy());
</script>

<div class="radial">
	<div class="chart-wrap">
		<div class="canvas-square">
			<canvas bind:this={canvas}></canvas>
			<div class="center-label">
				<strong style={`color:${toneColors[tone]}`}>{Math.round(score)}</strong>
				<small>{label}</small>
			</div>
		</div>
	</div>
</div>

<style>
	.radial {
		width: 100%;
		height: 100%;
		min-height: 100px;
		min-width: 0;
	}

	.chart-wrap {
		position: relative;
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.canvas-square {
		position: relative;
		height: 100%;
		width: auto;
		aspect-ratio: 1 / 1;
		max-width: 100%;
		max-height: 100%;
		margin: 0 auto;
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
		font-size: 26px;
		font-weight: 900;
		line-height: 1;
	}

	.center-label small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
	}
</style>
