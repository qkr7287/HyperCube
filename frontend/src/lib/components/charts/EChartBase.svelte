<!--
  EChartBase — ECharts instance lifecycle 전담 wrapper.

  책임 (단일):
   1) host div 생성 후 echarts.init
   2) option props 변화 시 setOption (in-place — chart.js 와 달리 안전)
   3) ResizeObserver 로 부모 크기 변화 감지 → resize
   4) onDestroy / HMR dispose 시 chart.dispose

  바깥에 ECharts 인스턴스 노출 안 함. 모든 sub-wrapper (EChartLine 등) 가
  이 컴포넌트의 props 인터페이스로만 통신. svelte 5 $state proxy 그대로 넘겨도
  ECharts 가 내부 평탄 순회만 하므로 chart.js 같은 RangeError cycle 없음.
-->
<script lang="ts">
	import { onMount, onDestroy, untrack } from 'svelte';
	import { echarts, type EChartsType, type EChartsOption } from './echart-registry';

	let {
		option,
		notMerge = false,
		replaceMerge,
		lazyUpdate = true,
		height = '100%',
		width = '100%',
		ariaLabel = '',
		group,
	}: {
		option: EChartsOption;
		notMerge?: boolean;
		replaceMerge?: string | string[];
		lazyUpdate?: boolean;
		height?: string | number;
		width?: string | number;
		ariaLabel?: string;
		// 같은 group 문자열을 가진 차트들끼리 axisPointer / tooltip 이 동기화된다.
		// echarts.connect(group) 으로 horizontal cursor sync.
		group?: string;
	} = $props();

	let host: HTMLDivElement | undefined = $state(undefined);
	let inst: EChartsType | null = null;
	let resizeObs: ResizeObserver | null = null;

	let firstApply = true;

	function applyOption(o: EChartsOption) {
		if (!inst || inst.isDisposed()) return;
		// 첫 setOption 만 notMerge:true 로 깨끗하게 시작 — 이전 instance 의 잔여
		// option (특히 prop 변경으로 series 개수가 바뀐 직후) 을 깔끔히 치움.
		// 두 번째부터는 merge 모드로 series.data 만 diff → 실시간 streaming 처럼
		// 점이 좌측으로 흐르는 smooth animation. series 는 id 기반 replaceMerge
		// 로 추가/제거가 자유롭고 axis (특히 xAxis.data 새 array) 도 같은 호출에서
		// merge 로 update 되어 dangling index 없음 (호버 tooltip 이 잘리지 않음).
		if (firstApply) {
			inst.setOption(o, { notMerge: true, lazyUpdate, replaceMerge });
			firstApply = false;
			return;
		}
		const mergeReplace = replaceMerge ?? 'series';
		inst.setOption(o, { notMerge: false, lazyUpdate, replaceMerge: mergeReplace });
	}

	onMount(() => {
		if (!host) return;
		// host 가 0×0 으로 mount 된 직후 init 하면 ECharts 가 width=0 캔버스를
		// 만들어 첫 frame 이 비게 보일 수 있다. ResizeObserver 의 첫 dispatch
		// 에서 init 하면 자연스럽게 부모 사이즈 잡힌 후 그려짐.
		const initIfReady = () => {
			if (!host) return;
			const r = host.getBoundingClientRect();
			if (r.width <= 0 || r.height <= 0) return false;
			if (!inst) {
				inst = echarts.init(host, undefined, { renderer: 'canvas', useDirtyRect: true });
				if (group) {
					inst.group = group;
					echarts.connect(group);
				}
				applyOption(option);
			}
			return true;
		};

		if (!initIfReady()) {
			// requestAnimationFrame 한 번 더 시도 (svelte mount 직후엔 layout 안 잡힘)
			requestAnimationFrame(() => initIfReady());
		}

		if (typeof ResizeObserver !== 'undefined') {
			resizeObs = new ResizeObserver(() => {
				if (!inst) {
					initIfReady();
					return;
				}
				inst.resize();
			});
			resizeObs.observe(host);
		}
	});

	// option props 변화 → setOption. untrack 으로 setOption 안에서 발생할 수 있는
	// 다른 reactive read 가 의존성으로 잡히지 않게 한다.
	$effect(() => {
		const next = option;
		untrack(() => applyOption(next));
	});

	onDestroy(() => {
		resizeObs?.disconnect();
		resizeObs = null;
		if (inst && !inst.isDisposed()) inst.dispose();
		inst = null;
	});
</script>

<div
	class="echart-host"
	style:height={typeof height === 'number' ? `${height}px` : height}
	style:width={typeof width === 'number' ? `${width}px` : width}
	bind:this={host}
	role="img"
	aria-label={ariaLabel}
></div>

<style>
	.echart-host {
		min-width: 0;
		min-height: 0;
		display: block;
	}
</style>
