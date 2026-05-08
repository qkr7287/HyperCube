<!--
  EChartLine — 시계열 line/area chart 의 thin wrapper.

  ECharts setOption alpha-merge 로 streaming 자동 처리. chart.js 시절의
  streamPatchArray / array reference 보존 / lastYMax 추적 같은 우회 코드
  모두 불필요. svelte 5 $state proxy 그대로 받아도 ECharts 가 평탄 순회만
  하므로 RangeError cycle 없음.

  yFormat 별 axis label / tooltip formatter 가 분기. percent 모드에선 데이터
  최댓값에 맞춰 소수 자릿수 자동 조정.
-->
<script lang="ts">
	import EChartBase from './EChartBase.svelte';
	import type { EChartsOption } from './echart-registry';
	import type { LineSeries, ValueFormat } from './types';
	import { formatBytesValue } from '$lib/utils/container-dashboard';

	let {
		labels = [],
		series = [],
		yFormat = 'percent' as ValueFormat,
		height = '100%',
		showLegend,
		ariaLabel = '',
		group,
		enableZoom = false,
	}: {
		labels?: string[];
		series?: LineSeries[];
		yFormat?: ValueFormat;
		height?: string | number;
		showLegend?: boolean;
		ariaLabel?: string;
		// 같은 group 문자열을 가진 차트끼리 cursor / tooltip 동기화 (axisPointer link)
		group?: string;
		// 마우스 휠 / 드래그로 x축 zoom (DataZoomInsideComponent 필요)
		enableZoom?: boolean;
	} = $props();

	let option = $derived<EChartsOption>(buildOption(labels, series, yFormat, showLegend, enableZoom));

	function percentDecimals(seriesList: LineSeries[]): number {
		// 모두 0 이거나 작은 값이면 axis 가 "0%" 로 뭉개지지 않게 소수점 조정.
		let maxAbs = 0;
		for (const ds of seriesList) {
			for (const v of ds.values) {
				if (Number.isFinite(v) && Math.abs(v) > maxAbs) maxAbs = Math.abs(v);
			}
		}
		if (maxAbs === 0) return 0;
		if (maxAbs < 0.1) return 3;
		if (maxAbs < 1) return 2;
		if (maxAbs < 10) return 1;
		return 0;
	}

	function formatValue(value: number, fmt: ValueFormat, decimals: number): string {
		if (fmt === 'bytes') return formatBytesValue(value);
		if (fmt === 'count') return `${Math.round(value)}`;
		const d = fmt === 'percent' ? Math.max(decimals, 2) : 1;
		return `${value.toFixed(d)}%`;
	}

	function buildOption(
		lbls: string[],
		seriesList: LineSeries[],
		fmt: ValueFormat,
		legend: boolean | undefined,
		zoom: boolean,
	): EChartsOption {
		const decimals = percentDecimals(seriesList);
		const showLegendResolved = legend ?? seriesList.length > 1;

		return {
			animationDuration: 250,
			animationDurationUpdate: 600,
			animationEasingUpdate: 'cubicInOut',
			grid: {
				top: showLegendResolved ? 32 : 8,
				left: 8,
				right: 8,
				bottom: 24,
				containLabel: true,
			},
			// 같은 group 의 차트 간 axisPointer/tooltip 동기화는 EChartBase
			// 의 echarts.connect 가 처리. 여기선 snap 만 켜서 가까운 점에 흡착.
			axisPointer: { snap: true },
			dataZoom: zoom
				? [
						{ type: 'inside', xAxisIndex: 0, throttle: 50, zoomLock: false },
					]
				: undefined,
			tooltip: {
				appendToBody: true,
				trigger: 'axis',
				backgroundColor: '#121720',
				borderColor: '#1f2937',
				borderWidth: 1,
				textStyle: { color: '#cbd5e1', fontSize: 11 },
				axisPointer: { type: 'line', lineStyle: { color: 'rgba(148, 163, 184, 0.3)' } },
				formatter: (params: any) => {
					const arr = Array.isArray(params) ? params : [params];
					if (arr.length === 0) return '';
					const title = arr[0].axisValueLabel ?? '';
					const lines = arr.map((p: any) => {
						const sIdx = p.seriesIndex ?? 0;
						const ds = seriesList[sIdx];
						const f = ds?.format ?? fmt;
						const val = formatValue(Number(p.value ?? 0), f, decimals);
						return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <strong>${val}</strong>`;
					});
					return `<div style="color:#e2e8f0;font-weight:700;margin-bottom:4px">${title}</div>${lines.join('<br/>')}`;
				},
			},
			legend: showLegendResolved
				? {
						show: true,
						top: 0,
						left: 0,
						textStyle: { color: '#94a3b8', fontSize: 11 },
						icon: 'circle',
						itemWidth: 8,
						itemHeight: 8,
						itemGap: 14,
					}
				: { show: false },
			xAxis: {
				type: 'category',
				data: lbls,
				boundaryGap: false,
				axisTick: { show: false },
				axisLine: { show: false },
				axisLabel: {
					color: '#64748b',
					hideOverlap: true,
					fontSize: 10,
				},
				splitLine: { show: false },
			},
			yAxis: {
				type: 'value',
				min: 0,
				axisLabel: {
					color: '#64748b',
					fontSize: 10,
					formatter: (v: number) => formatValue(v, fmt, decimals),
				},
				axisLine: { show: false },
				axisTick: { show: false },
				splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
			},
			series: seriesList.map((ds) => ({
				type: 'line',
				name: ds.label,
				data: ds.values,
				smooth: 0.32,
				symbol: 'none',
				lineStyle: { color: ds.color, width: 2 },
				itemStyle: { color: ds.color },
				areaStyle: ds.fill !== false ? { color: `${ds.color}1f` } : undefined,
				emphasis: { focus: 'series' },
			})),
		};
	}
</script>

<div class="line-host" style:height={typeof height === 'number' ? `${height}px` : height}>
	<EChartBase {option} {ariaLabel} {height} {group} />
</div>

<style>
	.line-host {
		position: relative;
		width: 100%;
		min-width: 0;
		min-height: 0;
	}
</style>
