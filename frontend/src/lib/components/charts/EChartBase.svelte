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
	}: {
		option: EChartsOption;
		notMerge?: boolean;
		replaceMerge?: string | string[];
		lazyUpdate?: boolean;
		height?: string | number;
		width?: string | number;
		ariaLabel?: string;
	} = $props();

	let host: HTMLDivElement | undefined = $state(undefined);
	let inst: EChartsType | null = null;
	let resizeObs: ResizeObserver | null = null;

	function applyOption(o: EChartsOption) {
		if (!inst || inst.isDisposed()) return;
		inst.setOption(o, { notMerge, lazyUpdate, replaceMerge });
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
