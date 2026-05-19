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
	import type { LineSeries, MarkLineEntry, ValueFormat } from './types';
	import { formatBytesValue } from '$lib/utils/container-dashboard';

	let {
		labels = [],
		tooltipLabels = [],
		timestamps,
		tickInterval,
		series = [],
		yFormat = 'percent' as ValueFormat,
		height = '100%',
		showLegend,
		ariaLabel = '',
		group,
		enableZoom = false,
		markLines = [],
		yAxisName = '',
	}: {
		labels?: string[];
		tooltipLabels?: string[];
		// epoch ms. 있으면 xAxis.type='time' (진짜 streaming — 새 점만 우측 슬라이드 in).
		// 없으면 기존 category axis 동작 유지 (호환성).
		timestamps?: number[];
		// polling 주기(ms). 있으면 xAxis tick 을 정확히 이 간격으로 강제 + axisLabel 정밀도도
		// interval 기준 자동 (30s→HH:MM:SS, 1m/5m→HH:MM, 1h→MM/DD HH:MM, 24h+→MM/DD).
		// 없으면 ECharts 자동 분배 + ts span 기반 fallback.
		tickInterval?: number;
		series?: LineSeries[];
		yFormat?: ValueFormat;
		height?: string | number;
		showLegend?: boolean;
		ariaLabel?: string;
		// 같은 group 문자열을 가진 차트끼리 cursor / tooltip 동기화 (axisPointer link)
		group?: string;
		// 마우스 휠 / 드래그로 x축 zoom (DataZoomInsideComponent 필요)
		enableZoom?: boolean;
		// 이벤트 시각을 차트 위 vertical line 으로 표시 (MarkLineComponent 사용)
		markLines?: MarkLineEntry[];
		yAxisName?: string;
	} = $props();

	let option = $derived<EChartsOption>(
		buildOption(labels, tooltipLabels, timestamps, tickInterval, series, yFormat, showLegend, enableZoom, markLines, yAxisName),
	);

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

	function pad2(n: number): string {
		return n < 10 ? `0${n}` : `${n}`;
	}

	function formatAxisTime(value: number, ts: number[] | undefined, intervalMs: number | undefined): string {
		const d = new Date(value);
		// 정밀도 선택 우선순위: tickInterval(명시) > ts span(휴리스틱) > HH:MM default
		const HOUR = 3600_000;
		const DAY = 86_400_000;
		const eff = intervalMs && intervalMs > 0
			? intervalMs
			: (Array.isArray(ts) && ts.length >= 2 ? ts[ts.length - 1] - ts[0] : 0);
		// 30초 이하 (polling 단위) = HH:MM:SS, 1m~10m = HH:MM, ~1d = HH:MM,
		// 1d~7d = MM/DD HH:MM, 7d+ = MM/DD
		if (eff > 0 && eff < 60_000) {
			return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
		}
		if (eff > 0 && eff < HOUR) {
			return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
		}
		if (eff > 0 && eff < DAY) {
			return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
		}
		if (eff >= DAY) {
			return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}`;
		}
		return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
	}

	function formatTooltipTime(value: number): string {
		// tooltip 은 항상 정밀한 시각 (초까지). 운영자가 정확한 점 시각 확인용.
		const d = new Date(value);
		return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
	}

	function formatValue(value: number, fmt: ValueFormat, decimals: number): string {
		if (fmt === 'bytes') return formatBytesValue(value);
		if (fmt === 'bytes_per_sec') return `${formatBytesValue(value)}/s`;
		if (fmt === 'count') return `${Math.round(value)}`;
		const d = fmt === 'percent' ? Math.max(decimals, 2) : 1;
		return `${value.toFixed(d)}%`;
	}

	function buildMarkLine(marks: MarkLineEntry[]) {
		if (!marks.length) return undefined;
		return {
			symbol: ['none', 'none'],
			silent: false,
			label: { show: false },
			data: marks.map((m) => {
				// xAxis (vertical) vs yAxis (horizontal) 분기. 둘 중 하나만 정의됨.
				const axis = typeof m.yAxis === 'number' ? { yAxis: m.yAxis } : { xAxis: m.index ?? 0 };
				return {
					...axis,
					name: m.label,
					lineStyle: { color: m.color, width: 1, type: 'dashed' as const, opacity: 0.7 },
					emphasis: { lineStyle: { width: 2, opacity: 1 } },
					label: { show: false },
				};
			}),
		};
	}

	function buildOption(
		lbls: string[],
		tipLbls: string[],
		ts: number[] | undefined,
		intervalMs: number | undefined,
		seriesList: LineSeries[],
		fmt: ValueFormat,
		legend: boolean | undefined,
		zoom: boolean,
		marks: MarkLineEntry[],
		axisName: string,
	): EChartsOption {
		const decimals = percentDecimals(seriesList);
		const showLegendResolved = legend ?? seriesList.length > 1;
		const hasDateLabels = lbls.some((label) => /\d{1,2}\/\d{1,2}/.test(label));
		const useTimeAxis = Array.isArray(ts) && ts.length > 0;

		return {
			animationDuration: 250,
			animationDurationUpdate: 600,
			animationEasingUpdate: 'cubicInOut',
			grid: {
				top: showLegendResolved ? 28 : 6,
				left: 4,
				right: 6,
				bottom: hasDateLabels ? 24 : 18,
				containLabel: true,
			},
			// 같은 group 의 차트 간 axisPointer/tooltip 동기화는 EChartBase 의
			// echarts.connect 가 처리. snap 은 짧은 간격(30s 등) 점들이 화면에서
			// 거의 같은 x 좌표라 일부 점만 호버 인식되는 버그를 일으켜서 끔.
			axisPointer: { snap: false },
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
					let title = '';
					if (useTimeAxis) {
						// time axis: axisValue 는 timestamp. 정밀한 시각 직접 포맷.
						const tsValue = Number(arr[0]?.axisValue);
						title = Number.isFinite(tsValue) ? formatTooltipTime(tsValue) : '';
					} else {
						const dataIndex = Number(arr[0]?.dataIndex);
						title =
							(Number.isInteger(dataIndex) ? tipLbls[dataIndex] : undefined) ??
							arr[0].axisValueLabel ??
							'';
					}
					const lines = arr.map((p: any) => {
						const sIdx = p.seriesIndex ?? 0;
						const ds = seriesList[sIdx];
						const f = ds?.format ?? fmt;
						// time axis 의 series.data 는 [ts, val] 튜플 → value 가 [ts, val] 배열로 들어옴
						const rawVal = Array.isArray(p.value) ? p.value[1] : p.value;
						const val = formatValue(Number(rawVal ?? 0), f, decimals);
						return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <strong>${val}</strong>`;
					});
					return `<div style="color:#e2e8f0;font-weight:700;margin-bottom:4px;white-space:nowrap">${title}</div>${lines.join('<br/>')}`;
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
			xAxis: useTimeAxis
				? {
						type: 'time',
						// polling 주기를 그대로 tick 간격으로 강제 — caller 가 보낸 점마다
						// 라벨이 박힘 (자동 분배가 멋대로 4~6 ticks 만 그리는 걸 회피).
						...(intervalMs && intervalMs > 0
							? { interval: intervalMs, minInterval: intervalMs }
							: {}),
						axisTick: { show: false },
						axisLine: { show: false },
						axisLabel: {
							color: '#64748b',
							hideOverlap: true,
							fontSize: hasDateLabels ? 8 : 9,
							margin: hasDateLabels ? 9 : 6,
							formatter: (value: number) => formatAxisTime(value, ts, intervalMs),
						},
						splitLine: { show: false },
					}
				: {
						type: 'category',
						data: lbls,
						boundaryGap: false,
						axisTick: { show: false },
						axisLine: { show: false },
						axisLabel: {
							color: '#64748b',
							hideOverlap: true,
							fontSize: hasDateLabels ? 8 : 9,
							margin: hasDateLabels ? 9 : 6,
						},
						splitLine: { show: false },
					},
			yAxis: {
				type: 'value',
				min: 0,
				// yAxis 좌측 name (예 "CPU %") 은 의도적으로 안 그림. UserMetricChart 가
				// 우상단 .chart-denominator 로 라벨/분모를 더 큰 글씨로 보여주는데,
				// 좁은 차트 (~110px) 좌측 34px 공간에 회전된 axis name 까지 넣으면
				// tick label 과 겹쳐서 둘 다 못 읽힌다.
				// percent 차트는 항상 0~100 범위 강제. 임계 markLine (80/90 등) 이
				// 데이터 max 보다 위에 있어도 화면 안에 보이도록. 작은 값일 때 그래프가
				// 바닥에 깔리는 트레이드오프는 capacity 시야 우위로 수용.
				max: fmt === 'percent' ? 100 : undefined,
				axisLabel: {
					color: '#64748b',
					fontSize: 9,
					hideOverlap: true,
					margin: 4,
					// axis tick 은 정수로만 표시 (0% / 25% / 50% / 75% / 100%). 소수점은
					// tooltip 에서. 좁은 차트에서 "0.00%" 같은 7 글자 라벨이 5 줄로
					// 들어가면 무조건 겹친다.
					formatter: (v: number) =>
						fmt === 'percent' ? `${Math.round(v)}%` : formatValue(v, fmt, decimals),
				},
				axisLine: { show: false },
				axisTick: { show: false },
				splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
				/* percent 차트 yAxis 라벨 자릿수 통일 — split 4 면 0/25/50/75/100 */
				splitNumber: fmt === 'percent' ? 4 : undefined,
			},
			series: seriesList.map((ds, i) => ({
				// id 는 ECharts 가 두 setOption 사이에서 같은 series 인지 식별하는 키.
				// id 가 일치하면 series 통째 교체 대신 data 만 diff → animation smooth
				// (실시간 streaming 처럼 점이 좌측으로 흐르는 느낌). id 가 없으면
				// notMerge:false + replaceMerge:['series'] 조합이라도 매번 새 series
				// 로 인식해 enter animation 다시 시작.
				id: ds.label || `s_${i}`,
				type: 'line',
				name: ds.label,
				// time axis 일 때 각 점에 절대 timestamp 부여 — streaming animation 의 핵심.
				data: useTimeAxis
					? ds.values.map((v, j) => [ts![j], v] as [number, number])
					: ds.values,
				smooth: 0.32,
				smoothMonotone: 'x',
				symbol: 'none',
				lineStyle: {
					color: ds.color,
					width: ds.dashed ? 1.4 : 2,
					type: ds.dashed ? 'dashed' : 'solid',
					opacity: ds.dashed ? 0.7 : 1,
				},
				itemStyle: { color: ds.color },
				areaStyle: ds.fill !== false ? { color: `${ds.color}1f` } : undefined,
				emphasis: { focus: 'series' },
				// markLine 은 첫 series 에만 부착해도 차트 전체 폭에 그려진다.
				markLine: i === 0 ? buildMarkLine(marks) : undefined,
			})),
		};
	}
</script>

<div class="line-host" style:height={typeof height === 'number' ? `${height}px` : height}>
	<EChartBase {option} {ariaLabel} {height} {group} dataOnly />
</div>

<style>
	.line-host {
		position: relative;
		width: 100%;
		min-width: 0;
		min-height: 0;
	}
</style>
