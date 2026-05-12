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
		datasets = [],
		yFormat = 'percent' as ValueFormat,
		group,
		enableZoom = false,
		markLines = [],
		height = 200,
	}: {
		labels?: string[];
		tooltipLabels?: string[];
		datasets?: Series[];
		yFormat?: ValueFormat;
		group?: string;
		enableZoom?: boolean;
		markLines?: MarkLineEntry[];
		height?: number;
	} = $props();
</script>

<div class="chart-shell" style="--chart-h: {height}px">
	<EChartLine {labels} {tooltipLabels} series={datasets} {yFormat} height="100%" {group} {enableZoom} {markLines} />
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
</style>
