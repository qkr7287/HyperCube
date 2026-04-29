<!--
  HealthRadialGauge — 종합 건강 점수 270° gauge.
  ECharts pie chart 의 startAngle:225 / endAngle:-45 로 chart.js 의
  rotation:225 / circumference:270 동등 재현.
-->
<script lang="ts">
	import EChartBase from '$lib/components/charts/EChartBase.svelte';
	import type { EChartsOption } from '$lib/components/charts/echart-registry';

	let {
		score = 0,
		label = '건강 점수',
		tone = 'ok' as 'ok' | 'warn' | 'hot' | 'dim',
	}: {
		score?: number;
		label?: string;
		tone?: 'ok' | 'warn' | 'hot' | 'dim';
	} = $props();

	const toneColors: Record<'ok' | 'warn' | 'hot' | 'dim', string> = {
		ok: '#34d399',
		warn: '#fbbf24',
		hot: '#f87171',
		dim: '#64748b',
	};

	let option = $derived<EChartsOption>(buildOption(score, tone));

	function buildOption(scoreVal: number, toneVal: typeof tone): EChartsOption {
		const value = Math.max(0, Math.min(100, Math.round(scoreVal)));
		const fillColor = toneColors[toneVal];
		return {
			animationDuration: 280,
			animationDurationUpdate: 480,
			animationEasingUpdate: 'cubicOut',
			tooltip: { show: false },
			legend: { show: false },
			series: [
				{
					type: 'pie',
					radius: ['74%', '100%'],
					center: ['50%', '50%'],
					// chart.js circumference:270 + rotation:225 와 동등.
					// ECharts 의 각도 체계: 0°=오른쪽, 시계 반대 방향 증가.
					// chart.js rotation:225 = 시작 각도가 -135° = ECharts startAngle 225.
					startAngle: 225,
					endAngle: -45,
					avoidLabelOverlap: false,
					label: { show: false },
					labelLine: { show: false },
					silent: true,
					data: [
						{
							name: '점수',
							value,
							itemStyle: { color: fillColor, borderColor: 'rgba(15, 23, 42, 0.95)', borderWidth: 1 },
						},
						{
							name: '여유',
							value: 100 - value,
							itemStyle: { color: 'rgba(51, 65, 85, 0.5)', borderColor: 'rgba(15, 23, 42, 0.95)', borderWidth: 1 },
						},
					],
				},
			],
		};
	}
</script>

<div class="radial">
	<div class="chart-wrap">
		<div class="canvas-square">
			<EChartBase {option} ariaLabel="{label} {Math.round(score)}점" />
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
