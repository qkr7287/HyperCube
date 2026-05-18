<!--
  FleetLineChart — 스택별 평균 추이 비교용 multi-series 시계열.
  ECharts line wrapper. 기존 chart.js 의 다음 우회 코드 모두 폐기:
   - rightEdgeLabelsPlugin (107 LOC) → series.endLabel + labelLayout 충돌 회피
   - streamPatchArray (array reference 보존) → ECharts 자체 alpha-merge
   - lastYMax 추적 + 조건부 destroy+recreate → setOption 으로 안전
   - toChartPayload deep clone → ECharts 가 plain object 만 사용

  Props 인터페이스 그대로 유지 (호출처 server-2d/+page.svelte 변경 0건).
  단 extraPlugins 는 ECharts 에선 의미 없음 — 무시.
-->
<script lang="ts">
	import EChartBase from '$lib/components/charts/EChartBase.svelte';
	import type { EChartsOption } from '$lib/components/charts/echart-registry';
	import MetricHelp from './MetricHelp.svelte';

	type Series = {
		label: string;
		color: string;
		values: number[];
		hidden?: boolean;
	};

	let {
		title,
		labels,
		timestamps,
		tickInterval,
		series,
		unit = 'percent',
		help = '',
		topNames = [],
		soloLabel = null,
		rightPadding = 0,
		loading = false,
	}: {
		title: string;
		labels: string[];
		// epoch ms. 있으면 xAxis.type='time' 으로 부드러운 streaming (좌측 흘러감).
		// 없으면 기존 category 동작 유지 (호환성).
		timestamps?: number[];
		// polling 주기 (ms). xAxis tick 을 그 간격으로 강제 + 라벨 정밀도 자동.
		tickInterval?: number;
		series: Series[];
		unit?: 'percent' | 'rate';
		help?: string;
		topNames?: string[];
		soloLabel?: string | null;
		extraPlugins?: any[];
		rightPadding?: number;
		loading?: boolean;
	} = $props();

	let option = $derived<EChartsOption>(
		buildOption(labels, timestamps, tickInterval, series, unit, topNames, soloLabel, rightPadding),
	);

	function pad2(n: number): string {
		return n < 10 ? `0${n}` : `${n}`;
	}

	function formatAxisTimeShort(value: number, ts: number[] | undefined, intervalMs?: number): string {
		const d = new Date(value);
		const DAY = 86_400_000;
		const HOUR = 3600_000;
		const eff = intervalMs && intervalMs > 0
			? intervalMs
			: (Array.isArray(ts) && ts.length >= 2 ? ts[ts.length - 1] - ts[0] : 0);
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
		return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
	}

	function formatTooltipTime(value: number): string {
		const d = new Date(value);
		return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
	}

	// bucket 시작/끝을 명시 — bucket epoch 가 자정/주 경계랑 안 떨어져서
	// (UTC 기준 floor 라 KST 에선 목요일 09:00 같은 식으로 떨어짐) x축 라벨과
	// 시각이 어긋나 보이는 문제 해결. 데이터 한 점은 [start, start+interval) 구간 평균.
	function formatTooltipBucket(value: number, intervalMs: number | undefined): string {
		if (!intervalMs || intervalMs <= 0) return formatTooltipTime(value);
		const start = new Date(value);
		const end = new Date(value + intervalMs);
		const DAY = 86_400_000;
		const HOUR = 3_600_000;
		const fmtDay = (d: Date) => `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}`;
		const fmtHM = (d: Date) => `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
		const fmtHMS = (d: Date) => `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
		if (intervalMs >= DAY) {
			return `${fmtDay(start)} ~ ${fmtDay(end)}`;
		}
		if (intervalMs >= HOUR) {
			return `${fmtDay(start)} ${fmtHM(start)} ~ ${fmtHM(end)}`;
		}
		return `${fmtHMS(start)} ~ ${fmtHMS(end)}`;
	}

	function formatValue(value: number, u: 'percent' | 'rate'): string {
		if (u === 'percent') return `${value.toFixed(1)}%`;
		if (value < 1) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let idx = 0;
		while (next >= 1000 && idx < units.length - 1) {
			next /= 1024;
			idx += 1;
		}
		const digits = next >= 10 ? 0 : 1;
		return `${next.toFixed(digits)} ${units[idx]}`;
	}

	function peakValue(list: Series[], soloName: string | null): number {
		let peak = 0;
		for (const item of list) {
			if (item.hidden) continue;
			if (soloName && item.label !== soloName) continue;
			for (const value of item.values) {
				if (value > peak) peak = value;
			}
		}
		return peak;
	}

	function percentAxisMax(_list: Series[], _soloName: string | null): number {
		// 항상 0~100 고정 → 70/90 threshold band 가 시각 anchor 역할.
		// 작은 값(0~5%)은 평탄해 보이지만 의미적으로 "안전 구간"이 분명히 전달됨.
		// 정확한 수치는 endLabel/tooltip 으로 보완.
		return 100;
	}

	function rateAxisMax(list: Series[], soloName: string | null): number {
		const peak = peakValue(list, soloName);
		if (peak <= 0) return 1024;
		const padded = peak * 1.2;
		const magnitude = Math.pow(10, Math.floor(Math.log10(padded)));
		return Math.ceil(padded / magnitude) * magnitude;
	}

	function dimColor(color: string, opacity = 0.48): string {
		// 6자 hex → rgba (ECharts 가 8자 hex 일부 케이스 인식 실패)
		const m = /^#?([0-9a-fA-F]{6})$/.exec(color.startsWith('#') ? color.slice(1) : color);
		if (!m) return color;
		const r = parseInt(m[1].slice(0, 2), 16);
		const g = parseInt(m[1].slice(2, 4), 16);
		const b = parseInt(m[1].slice(4, 6), 16);
		return `rgba(${r}, ${g}, ${b}, ${opacity})`;
	}

	function buildOption(
		lbls: string[],
		ts: number[] | undefined,
		intervalMs: number | undefined,
		seriesList: Series[],
		u: 'percent' | 'rate',
		tops: string[],
		soloName: string | null,
		padRight: number,
	): EChartsOption {
		const yMax = u === 'percent' ? percentAxisMax(seriesList, soloName) : rateAxisMax(seriesList, soloName);
		const useTimeAxis = Array.isArray(ts) && ts.length > 0;

		const isHighlighted = (label: string): boolean => {
			if (soloName) return label === soloName;
			if (tops.length === 0) return true;
			return tops.includes(label);
		};
		const topSet = new Set(tops);

		const echSeries = seriesList.map((item) => {
			const highlighted = isHighlighted(item.label);
			const forceHidden = !!soloName && item.label !== soloName;
			const color = highlighted ? item.color : dimColor(item.color);
			const showEndLabel = topSet.has(item.label) && !forceHidden;
			// time axis 일 때 데이터는 [timestamp, value] 튜플. category 는 그대로 number[].
			// 이게 ECharts streaming animation 의 핵심 — 각 점이 절대 시간 좌표를 가지면
			// data 길이 바뀌어도 기존 점은 같은 자리에 머물고 새 점만 우측에 추가됨.
			const rawValues = forceHidden || item.hidden ? [] : item.values;
			const data = useTimeAxis
				? rawValues.map((v, i) => [ts![i], v] as [number, number])
				: rawValues;
			return {
				type: 'line' as const,
				name: item.label,
				data,
				smooth: 0.32,
				symbol: 'none',
				lineStyle: { color, width: highlighted ? 2.4 : 1.4 },
				itemStyle: { color },
				z: highlighted ? 10 : 1,
				emphasis: { focus: 'series', lineStyle: { width: highlighted ? 3 : 2 } },
				endLabel: showEndLabel
					? {
							show: true,
							formatter: (p: any) => {
								const v = Array.isArray(p.value) ? p.value[1] : p.value;
								return `${item.label} ${formatValue(Number(v ?? 0), u)}`;
							},
							color,
							backgroundColor: 'rgba(13, 17, 23, 0.78)',
							borderColor: color,
							borderWidth: 1,
							borderRadius: 4,
							padding: [3, 6],
							fontSize: 10,
							fontWeight: 700,
							distance: 6,
							// box width cap → 긴 stack 이름이 panel 밖으로 잘리는 대신 ellipsis 처리
							width: 110,
							overflow: 'truncate',
							ellipsis: '…',
						}
					: { show: false },
			};
		}) as NonNullable<EChartsOption['series']>;

		// Threshold band — percent 단위 차트에만 의미. yMax 가 70% 넘을 때만 warn
		// band, 90% 넘을 때만 critical band 추가. yMax 가 5~10% 같이 낮은 평탄
		// 구간에선 band 자체가 view 밖이라 그리지 않음 (시각 잡음 회피).
		const thresholdSeries: any[] = [];
		if (u === 'percent' && yMax > 70) {
			const areas: any[] = [
				[
					{ yAxis: 70, itemStyle: { color: 'rgba(245, 158, 11, 0.10)' } },
					{ yAxis: Math.min(90, yMax) },
				],
			];
			if (yMax > 90) {
				areas.push([
					{ yAxis: 90, itemStyle: { color: 'rgba(239, 68, 68, 0.13)' } },
					{ yAxis: Math.min(100, yMax) },
				]);
			}
			thresholdSeries.push({
				type: 'line',
				name: '__threshold__',
				data: [],
				silent: true,
				showInLegend: false,
				tooltip: { show: false },
				markArea: { silent: true, data: areas, label: { show: false } },
				markLine: {
					silent: true,
					symbol: 'none',
					data: [
						{
							yAxis: 70,
							lineStyle: { color: 'rgba(245, 158, 11, 0.55)', type: 'dashed', width: 1 },
							label: { show: true, position: 'insideStartTop', formatter: '70%', color: '#fbbf24', fontSize: 9, fontWeight: 700 },
						},
						...(yMax > 90 ? [{
							yAxis: 90,
							lineStyle: { color: 'rgba(239, 68, 68, 0.6)', type: 'dashed', width: 1 },
							label: { show: true, position: 'insideStartTop', formatter: '90%', color: '#f87171', fontSize: 9, fontWeight: 700 },
						}] : []),
					],
				},
			});
		}
		const allSeries = [...(echSeries as any[]), ...thresholdSeries] as NonNullable<EChartsOption['series']>;

		return {
			animationDuration: 200,
			animationDurationUpdate: 600,
			animationEasingUpdate: 'cubicInOut',
			grid: {
				top: 8,
				left: 8,
				right: padRight > 0 ? padRight : 130, // endLabel 공간 (width:110 + padding/border/distance)
				bottom: 22,
				containLabel: true,
			},
			tooltip: {
				appendToBody: true,
				trigger: 'axis',
				backgroundColor: 'rgba(13, 17, 23, 0.96)',
				borderColor: 'rgba(48, 213, 200, 0.35)',
				borderWidth: 1,
				textStyle: { color: '#cbd5e1', fontSize: 11 },
				axisPointer: { type: 'line', lineStyle: { color: 'rgba(148, 163, 184, 0.3)' }, snap: false },
				formatter: (params: any) => {
					const arr = Array.isArray(params) ? params : [params];
					if (arr.length === 0) return '';
					// soloLabel / topNames 필터 동등 — chart.js tooltip.filter
					const filtered = arr.filter((p: any) => {
						const name = p.seriesName ?? '';
						// threshold dummy series 는 tooltip 에 등장 안 함
						if (name === '__threshold__') return false;
						if (soloName) return name === soloName;
						if (tops.length === 0) return true;
						return tops.includes(name);
					});
					if (filtered.length === 0) return '';
					let title = '';
					if (useTimeAxis) {
						const tsValue = Number(filtered[0]?.axisValue);
						title = Number.isFinite(tsValue) ? formatTooltipBucket(tsValue, intervalMs) : '';
					} else {
						title = filtered[0].axisValueLabel ?? '';
					}
					const lines = filtered.map((p: any) => {
						// time axis 의 series.data 는 [ts, val] 튜플 → value 가 배열
						const rawVal = Array.isArray(p.value) ? p.value[1] : p.value;
						const val = formatValue(Number(rawVal ?? 0), u);
						return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <strong>${val}</strong>`;
					});
					return `<div style="color:#e2e8f0;font-weight:700;margin-bottom:4px">${title}</div>${lines.join('<br/>')}`;
				},
			},
			legend: { show: false },
			xAxis: useTimeAxis
				? {
						type: 'time',
						...(intervalMs && intervalMs > 0
							? { interval: intervalMs, minInterval: intervalMs }
							: {}),
						axisTick: { show: false },
						axisLine: { show: false },
						axisLabel: {
							color: '#64748b',
							hideOverlap: true,
							fontSize: 10,
							// timestamp 직접 포맷 — intervalMs 가 있으면 그 단위 기준,
							// 없으면 ts span 으로 fallback.
							formatter: (value: number) => formatAxisTimeShort(value, ts, intervalMs),
						},
						splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.08)' } },
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
							fontSize: 10,
						},
						splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.08)' } },
					},
			yAxis: {
				type: 'value',
				min: 0,
				max: yMax,
				axisTick: { show: false },
				axisLine: { show: false },
				axisLabel: {
					color: '#64748b',
					fontSize: 10,
					formatter: (v: number) => formatValue(v, u),
				},
				splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.12)' } },
			},
			series: allSeries,
		};
	}
</script>

<div class="card">
	<div class="head">
		<strong>{title}</strong>
		{#if help}
			<MetricHelp text={help} />
		{/if}
	</div>
	<div class="body" class:loading>
		<EChartBase {option} ariaLabel={title} dataOnly />
	</div>
</div>

<style>
	.card {
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		height: 100%;
		gap: 4px;
	}

	.head {
		display: none; /* 부모 layout 의 chart-head 가 별도 */
	}

	.body {
		position: relative;
		flex: 1 1 auto;
		min-width: 0;
		min-height: 0;
	}

	.body.loading {
		opacity: 0.5;
	}
</style>
