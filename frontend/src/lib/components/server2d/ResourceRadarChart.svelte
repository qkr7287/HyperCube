<!--
  ResourceRadarChart — CPU/메모리/네트워크/디스크/GPU 같은 지표를 레이더로.
  ECharts radar wrapper. axis max 변경은 setOption 으로 안전 (chart.js 의
  in-place SET trap RangeError 위험 없음 → lastMax 추적/destroy+recreate 폐기).
-->
<script lang="ts">
	import EChartBase from '$lib/components/charts/EChartBase.svelte';
	import type { EChartsOption } from '$lib/components/charts/echart-registry';

	type Axis = {
		label: string;
		value: number;
		reference?: number;
	};

	let {
		axes = [] as Axis[],
		primaryColor = '#30d5c8',
		referenceColor = '#94a3b8',
	}: {
		axes?: Axis[];
		primaryColor?: string;
		referenceColor?: string;
	} = $props();

	let option = $derived<EChartsOption>(buildOption(axes, primaryColor, referenceColor));

	function computeMax(list: Axis[]): number {
		let peak = 0;
		for (const a of list) {
			peak = Math.max(peak, a.value || 0, a.reference || 0);
		}
		if (peak <= 0) return 1;
		const stops = [1, 2, 5, 10, 15, 20, 30, 50, 75, 100];
		for (const s of stops) {
			if (peak <= s) return s;
		}
		return 100;
	}

	function buildOption(list: Axis[], primary: string, reference: string): EChartsOption {
		const max = computeMax(list);
		const hasReference = list.some((a) => typeof a.reference === 'number');

		const indicator = list.map((a) => ({ name: a.label, max }));
		const series: any[] = [];

		// 기준선(평균) 시리즈 — 먼저 넣어야 현재 시리즈가 위에 그려짐
		if (hasReference) {
			series.push({
				type: 'radar',
				name: '평균',
				data: [
					{
						value: list.map((a) => Math.max(0, a.reference ?? 0)),
						lineStyle: { color: `${reference}88`, type: 'dashed', width: 1 },
						areaStyle: { color: `${reference}14` },
						itemStyle: { color: `${reference}88` },
						symbol: 'none',
					},
				],
			});
		}

		series.push({
			type: 'radar',
			name: '현재',
			data: [
				{
					value: list.map((a) => Math.max(0, a.value)),
					lineStyle: { color: primary, width: 2.4 },
					areaStyle: { color: `${primary}55` },
					itemStyle: { color: primary, borderColor: 'rgba(15, 23, 42, 0.9)', borderWidth: 1.4 },
					symbolSize: 6,
				},
			],
		});

		return {
			animationDuration: 320,
			animationDurationUpdate: 480,
			animationEasingUpdate: 'cubicInOut',
			tooltip: {
				trigger: 'item',
				backgroundColor: 'rgba(13, 17, 23, 0.96)',
				borderColor: 'rgba(148, 163, 184, 0.22)',
				borderWidth: 1,
				textStyle: { color: '#e2e8f0', fontSize: 11 },
				formatter: (params: any) => {
					const name = params.seriesName;
					const vals = (params.value as number[]) || [];
					const lines = list.map((a, i) => `${a.label}: ${(vals[i] ?? 0).toFixed(1)}%`);
					return `<strong>${name}</strong><br/>${lines.join('<br/>')}`;
				},
			},
			legend: { show: false },
			radar: {
				indicator,
				center: ['50%', '50%'],
				radius: '70%',
				shape: 'polygon',
				// splitNumber=4 (max=100 → step=25) 일 때 ECharts alignScaleTicks
				// 가 align 후 interval precision 이 어긋나 readable 경고 발생.
				// splitNumber=5 (step=20, nice number) 로 두면 검사 통과.
				splitNumber: 5,
				axisName: {
					color: '#cbd5e1',
					fontSize: 11,
					fontWeight: 700,
				},
				axisLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.25)' } },
				splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.18)' } },
				splitArea: { show: false },
			},
			series,
		};
	}
</script>

<div class="radar">
	<EChartBase {option} ariaLabel="자원 밸런스 레이더" />
</div>

<style>
	.radar {
		width: 100%;
		height: 100%;
		min-width: 0;
		min-height: 0;
	}
</style>
