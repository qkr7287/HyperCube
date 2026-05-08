<!--
  UserMetricChart — 사용자(컨테이너 상세) 페이지의 시계열 metric chart.
  EChartLine 위임. 기존 props (labels, datasets, yFormat) 그대로 유지 →
  /user/containers/[id] 호출처 변경 0건.
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
	}: {
		labels?: string[];
		datasets?: Series[];
		yFormat?: ValueFormat;
		group?: string;
		enableZoom?: boolean;
		markLines?: MarkLineEntry[];
	} = $props();
</script>

<div class="chart-shell">
	<EChartLine {labels} series={datasets} {yFormat} height={240} {group} {enableZoom} {markLines} />
</div>

<style>
	.chart-shell {
		position: relative;
		height: 240px;
		min-height: 240px;
		max-height: 240px;
		overflow: hidden;
	}
</style>
