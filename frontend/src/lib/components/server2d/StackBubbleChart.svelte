<!--
  StackBubbleChart — 스택별 CPU x 메모리 부하 분포 + 컨테이너 수(반지름).
  ECharts scatter wrapper. quadrantPlugin (chart.js inline 35 LOC) 은
  ECharts graphic[] (rect + line + text) 로 대체. midX/midY 는 axis convertToPixel
  로 axis 변경 시 자동 재계산.
-->
<script lang="ts">
	import EChartBase from '$lib/components/charts/EChartBase.svelte';
	import type { EChartsOption } from '$lib/components/charts/echart-registry';
	import { view } from '$lib/stores/server2d-view.svelte';

	type StackBubble = {
		name: string;
		color: string;
		cpu: number;
		memory: number;
		network: number;
		containers: number;
		problem: number;
	};

	let {
		stacks = [] as StackBubble[],
	}: {
		stacks?: StackBubble[];
	} = $props();

	const soloed = $derived(view.soloStack);

	function computeAxisMax(values: number[]): number {
		const dataMax = Math.max(0, ...values);
		if (dataMax <= 0) return 30;
		const padded = dataMax * 1.08 + 4;
		const stepped = Math.ceil(padded / 10) * 10;
		return Math.max(20, Math.min(100, stepped));
	}

	const xMax = $derived(computeAxisMax(stacks.map((s) => s.cpu)));
	const yMax = $derived(computeAxisMax(stacks.map((s) => s.memory)));

	function bubbleRadius(count: number, maxCount: number): number {
		if (count <= 0) return 3;
		const min = 4;
		const max = 12;
		const ratio = Math.sqrt(count / Math.max(1, maxCount));
		return Math.max(min, Math.min(max, min + (max - min) * ratio));
	}

	function formatRate(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let idx = 0;
		while (next >= 1024 && idx < units.length - 1) {
			next /= 1024;
			idx += 1;
		}
		return `${next.toFixed(next >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
	}

	let option = $derived<EChartsOption>(buildOption(stacks, xMax, yMax, soloed));

	function buildOption(
		stackList: StackBubble[],
		xMaxVal: number,
		yMaxVal: number,
		soloName: string | null,
	): EChartsOption {
		const maxCount = Math.max(1, ...stackList.map((s) => s.containers));
		// 6자 hex (#rrggbb) → rgba(r,g,b,a). ECharts 는 8자 hex (#rrggbbaa) 의
		// 일부 케이스에서 색을 인식하지 못하고 점을 안 그리는 케이스가 있어
		// rgba() 표기로 변환.
		function withAlpha(hex: string, alpha: number): string {
			const m = /^#?([0-9a-fA-F]{6})$/.exec(hex.startsWith('#') ? hex.slice(1) : hex);
			if (!m) return hex;
			const r = parseInt(m[1].slice(0, 2), 16);
			const g = parseInt(m[1].slice(2, 4), 16);
			const b = parseInt(m[1].slice(4, 6), 16);
			return `rgba(${r}, ${g}, ${b}, ${alpha})`;
		}
		// 모든 stack 을 단일 series 의 data points 로. 26 series 보다 가볍고
		// ECharts 정공법. 각 point 의 itemStyle 로 색상/dim 개별 지정.
		const points = stackList.map((s) => {
			const isDim = !!soloName && soloName !== s.name;
			const fill = isDim ? withAlpha(s.color, 0.09) : withAlpha(s.color, 0.8);
			const stroke = isDim ? withAlpha(s.color, 0.33) : s.color;
			const r = bubbleRadius(s.containers, maxCount);
			return {
				value: [
					Math.max(0, Math.min(100, s.cpu)),
					Math.max(0, Math.min(100, s.memory)),
				],
				symbolSize: r * 2,
				itemStyle: {
					color: fill,
					borderColor: stroke,
					borderWidth: isDim ? 1 : 1.8,
				},
				stackName: s.name,
				containers: s.containers,
				problem: s.problem,
				network: s.network,
			} as any;
		});
		const series: any[] = [
			{
				type: 'scatter',
				name: 'stacks',
				data: points,
				emphasis: { itemStyle: { borderWidth: 3 } },
			},
		];

		// quadrantPlugin → 별도 guide series 로 분리. 각 stack series 에 markArea
		// 를 박으면 첫 series 만 가이드 그리고, 그게 다른 series scatter point 의
		// 렌더링과 z-index 충돌 일으킬 수 있어 dedicated guide series 추가.
		const guideSeries: any = {
			type: 'scatter',
			name: '__guide',
			data: [],
			silent: true,
			tooltip: { show: false },
			animation: false,
			markArea: {
				silent: true,
				itemStyle: { color: 'transparent' },
				z: -10,
				data: [
					[
						// 우상단: 고부하 (빨강) — y 축 위쪽 = yMax/2 ~ yMax
						{ coord: [xMaxVal / 2, yMaxVal / 2], itemStyle: { color: 'rgba(248, 113, 113, 0.06)' } },
						{ coord: [xMaxVal, yMaxVal] },
					],
					[
						// 좌하단: 여유 (파랑)
						{ coord: [0, 0], itemStyle: { color: 'rgba(96, 165, 250, 0.04)' } },
						{ coord: [xMaxVal / 2, yMaxVal / 2] },
					],
				],
			},
			markLine: {
				silent: true,
				symbol: 'none',
				lineStyle: { color: 'rgba(148, 163, 184, 0.22)', type: 'dashed', width: 1 },
				label: { show: false },
				animation: false,
				data: [
					{ xAxis: xMaxVal / 2 },
					{ yAxis: yMaxVal / 2 },
				],
			},
		};

		return {
			animationDuration: 260,
			animationDurationUpdate: 480,
			animationEasingUpdate: 'cubicInOut',
			grid: { top: 4, right: 8, bottom: 18, left: 2, containLabel: true },
			tooltip: {
				appendToBody: true,
				trigger: 'item',
				backgroundColor: 'rgba(13, 17, 23, 0.96)',
				borderColor: 'rgba(148, 163, 184, 0.22)',
				borderWidth: 1,
				textStyle: { color: '#e2e8f0', fontSize: 11 },
				formatter: (p: any) => {
					const raw: any = p.data ?? {};
					const lines = [
						`<strong>${raw.stackName ?? p.seriesName}</strong>`,
						`CPU 평균: ${Number(raw.value?.[0] ?? 0).toFixed(1)}%`,
						`메모리 평균: ${Number(raw.value?.[1] ?? 0).toFixed(1)}%`,
						`컨테이너: ${raw.containers ?? 0}개${raw.problem ? ` (문제 ${raw.problem})` : ''}`,
						`트래픽 평균: ${formatRate(raw.network ?? 0)}`,
					];
					return lines.join('<br/>');
				},
			},
			legend: { show: false },
			xAxis: {
				type: 'value',
				min: 0,
				max: xMaxVal,
				axisTick: { show: false },
				axisLine: { show: false },
				axisLabel: { color: '#64748b', fontSize: 9 },
				splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.08)' } },
				splitNumber: 4,
			},
			yAxis: {
				type: 'value',
				min: 0,
				max: yMaxVal,
				axisTick: { show: false },
				axisLine: { show: false },
				axisLabel: { color: '#64748b', fontSize: 9 },
				splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.12)' } },
				splitNumber: 4,
			},
			// 코너 라벨 (고부하 / 여유) 은 graphic 으로 — chart 가 그려진 후
			// chart container 의 padding 안에서 절대 위치.
			graphic: [
				{
					type: 'text',
					right: 8,
					top: 6,
					silent: true,
					style: {
						text: '고부하',
						fill: 'rgba(248, 113, 113, 0.75)',
						font: '700 10px system-ui',
						align: 'right',
					},
				},
				{
					type: 'text',
					left: 8,
					bottom: 22,
					silent: true,
					style: {
						text: '여유',
						fill: 'rgba(148, 163, 184, 0.55)',
						font: '700 10px system-ui',
						align: 'left',
					},
				},
			],
			series: [guideSeries, ...series],
		};
	}
</script>

<div class="bubble">
	<EChartBase {option} ariaLabel="스택 부하 (CPU x 메모리) 버블 차트" dataOnly />
</div>

<style>
	.bubble {
		position: relative;
		width: 100%;
		height: 100%;
		min-width: 0;
		min-height: 0;
	}
</style>
