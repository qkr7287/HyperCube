<!--
  UserMetricChart — 사용자(컨테이너 상세) 페이지의 시계열 metric chart.
  EChartLine 위임. 기존 props (labels, datasets, yFormat) 그대로 유지 →
  /user/containers/[id] 호출처 변경 0건.
-->
<script lang="ts">
	import EChartLine from './charts/EChartLine.svelte';
	import type { LineSeries, ValueFormat } from './charts/types';

	type Series = LineSeries;

	let {
		labels = [],
		datasets = [],
		yFormat = 'percent' as ValueFormat,
	}: {
		labels?: string[];
		datasets?: Series[];
		yFormat?: ValueFormat;
	} = $props();
</script>

<div class="chart-shell">
	<EChartLine {labels} series={datasets} {yFormat} height={240} />
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
