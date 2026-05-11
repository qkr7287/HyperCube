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
		datasets = [],
		yFormat = 'percent' as ValueFormat,
		group,
		enableZoom = false,
		markLines = [],
		height = 200,
	}: {
		labels?: string[];
		datasets?: Series[];
		yFormat?: ValueFormat;
		group?: string;
		enableZoom?: boolean;
		markLines?: MarkLineEntry[];
		height?: number;
	} = $props();
</script>

<div class="chart-shell" style="--chart-h: {height}px">
	<EChartLine {labels} series={datasets} {yFormat} height="100%" {group} {enableZoom} {markLines} />
</div>

<style>
	.chart-shell {
		position: relative;
		/* 반응형: viewport 높이에 따라 자동. compact 우선 (1080p 한 화면 안에 다른 panel 도). */
		height: clamp(100px, 11vh, var(--chart-h, 180px));
		min-height: 100px;
		overflow: hidden;
	}
</style>
