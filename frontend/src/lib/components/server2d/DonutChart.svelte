<!--
  DonutChart — 컨테이너 상태 등의 segment 비율을 도넛 형태로 표시.
  ECharts pie chart wrapper. inner radius 66% 로 chart.js doughnut cutout 동등.
  중앙 텍스트(centerLabel/centerValue) 는 svelte 측 absolute div 로 유지 —
  reactivity 가 즉시 반영되고 ECharts graphic 보다 가볍다.

  Props 인터페이스는 chart.js 시절 그대로 유지 (호출처 server-2d 변경 없음).
-->
<script lang="ts">
	import EChartBase from '$lib/components/charts/EChartBase.svelte';
	import type { EChartsOption } from '$lib/components/charts/echart-registry';

	type Segment = { label: string; value: number; color: string };

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

	let option = $derived<EChartsOption>(buildOption(segments));

	function buildOption(seg: Segment[]): EChartsOption {
		const visible = seg.filter((s) => s.value > 0);
		const data =
			visible.length === 0
				? [
						{
							name: '데이터 없음',
							value: 1,
							itemStyle: { color: 'rgba(100, 116, 139, 0.25)', borderColor: 'rgba(15, 23, 42, 0.9)', borderWidth: 2 },
						},
					]
				: visible.map((s) => ({
						name: s.label,
						value: s.value,
						itemStyle: { color: s.color, borderColor: 'rgba(15, 23, 42, 0.95)', borderWidth: 2 },
					}));

		return {
			animationDuration: 260,
			animationDurationUpdate: 400,
			animationEasingUpdate: 'cubicInOut',
			tooltip: {
				trigger: 'item',
				backgroundColor: 'rgba(13, 17, 23, 0.96)',
				borderColor: 'rgba(148, 163, 184, 0.22)',
				borderWidth: 1,
				textStyle: { color: '#e2e8f0', fontSize: 11 },
				formatter: (params: any) => `${params.name}: ${params.value} 개`,
			},
			legend: { show: false },
			series: [
				{
					type: 'pie',
					radius: ['66%', '92%'],
					center: ['50%', '50%'],
					avoidLabelOverlap: false,
					label: { show: false },
					labelLine: { show: false },
					data,
					emphasis: { scaleSize: 6 },
				},
			],
		};
	}
</script>

<div class="donut-card">
	{#if title}
		<div class="title">{title}</div>
	{/if}
	<div class="chart-wrap">
		<div class="canvas-square">
			<EChartBase {option} ariaLabel={title || '도넛 차트'} />
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
		height: 100%;
		padding: 0;
		border: 0;
		border-radius: 0;
		background: transparent;
		overflow: hidden;
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
		width: 100%;
		height: auto;
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
</style>
