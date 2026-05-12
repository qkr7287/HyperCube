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
		buildOption(labels, series, unit, topNames, soloLabel, rightPadding),
	);

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

	function percentAxisMax(list: Series[], soloName: string | null): number {
		const peak = peakValue(list, soloName);
		if (peak <= 0) return 5;
		const padded = peak * 1.2;
		const stops = [2, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100];
		for (const stop of stops) {
			if (padded <= stop) return stop;
		}
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
		seriesList: Series[],
		u: 'percent' | 'rate',
		tops: string[],
		soloName: string | null,
		padRight: number,
	): EChartsOption {
		const yMax = u === 'percent' ? percentAxisMax(seriesList, soloName) : rateAxisMax(seriesList, soloName);

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
			return {
				type: 'line' as const,
				name: item.label,
				data: forceHidden || item.hidden ? [] : item.values,
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
						}
					: { show: false },
			};
		}) as NonNullable<EChartsOption['series']>;

		return {
			animationDuration: 200,
			animationDurationUpdate: 600,
			animationEasingUpdate: 'cubicInOut',
			grid: {
				top: 8,
				left: 8,
				right: padRight > 0 ? padRight : 90, // endLabel 공간
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
				axisPointer: { type: 'line', lineStyle: { color: 'rgba(148, 163, 184, 0.3)' } },
				formatter: (params: any) => {
					const arr = Array.isArray(params) ? params : [params];
					if (arr.length === 0) return '';
					// soloLabel / topNames 필터 동등 — chart.js tooltip.filter
					const filtered = arr.filter((p: any) => {
						const name = p.seriesName ?? '';
						if (soloName) return name === soloName;
						if (tops.length === 0) return true;
						return tops.includes(name);
					});
					if (filtered.length === 0) return '';
					const title = filtered[0].axisValueLabel ?? '';
					const lines = filtered.map((p: any) => {
						const val = formatValue(Number(p.value ?? 0), u);
						return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <strong>${val}</strong>`;
					});
					return `<div style="color:#e2e8f0;font-weight:700;margin-bottom:4px">${title}</div>${lines.join('<br/>')}`;
				},
			},
			legend: { show: false },
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
			series: echSeries,
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
		<EChartBase {option} ariaLabel={title} />
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
