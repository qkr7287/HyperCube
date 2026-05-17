<!--
  UserMetricChart — 사용자(컨테이너 상세) 페이지의 시계열 metric chart.
  EChartLine 위임. compact 모드용 height prop 추가 (default 컴팩트).
-->
<script lang="ts">
	import EChartLine from './charts/EChartLine.svelte';
	import type { LineSeries, MarkLineEntry, ValueFormat } from './charts/types';

	type Series = LineSeries;

	let {
		labels = [],
		tooltipLabels = [],
		timestamps,
		datasets = [],
		yFormat = 'percent' as ValueFormat,
		group,
		enableZoom = false,
		markLines = [],
		height = 200,
		yAxisLabel = '',
		denominatorText = '',
	}: {
		labels?: string[];
		tooltipLabels?: string[];
		// epoch ms. 있으면 EChartLine 이 time axis 로 자동 streaming.
		timestamps?: number[];
		datasets?: Series[];
		yFormat?: ValueFormat;
		group?: string;
		enableZoom?: boolean;
		markLines?: MarkLineEntry[];
		height?: number;
		yAxisLabel?: string;
		denominatorText?: string;
	} = $props();
</script>

<div class="chart-shell" style="--chart-h: {height}px">
	{#if yAxisLabel || denominatorText}
		<div class="chart-denominator">
			{#if yAxisLabel}<span>{yAxisLabel}</span>{/if}
			{#if denominatorText}<em>{denominatorText}</em>{/if}
		</div>
	{/if}
	<EChartLine {labels} {tooltipLabels} {timestamps} series={datasets} {yFormat} height="100%" {group} {enableZoom} {markLines} yAxisName={yAxisLabel} />
</div>

<style>
	.chart-shell {
		position: relative;
		/* viewport-fit 모드: 부모 chart-card 가 flex column 이라 자기 영역을 채움.
		   ResizeObserver 가 ECharts resize 자동 처리. fallback height clamp 는 부모
		   가 flex 환경이 아닐 때 (예: 모달 안) 안전망. */
		flex: 1 1 0;
		min-height: 0;
		height: clamp(100px, 11vh, var(--chart-h, 180px));
		overflow: hidden;
	}
	.chart-denominator {
		position: absolute;
		top: 0;
		right: 0;
		z-index: 2;
		display: inline-flex;
		align-items: baseline;
		gap: 8px;
		max-width: 100%;
		padding: 1px 2px 3px 8px;
		background: linear-gradient(90deg, rgba(18, 23, 32, 0), rgba(18, 23, 32, 0.96) 18%);
		color: rgba(203, 213, 225, 0.86);
		font-size: 10.5px;
		font-weight: 800;
		white-space: nowrap;
		pointer-events: none;
	}
	.chart-denominator em {
		color: rgba(148, 163, 184, 0.82);
		font-style: normal;
		font-weight: 700;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
