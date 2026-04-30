<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { base } from '$app/paths';
	import { Topology, type TopologyCallbacks, type TopologyContainerData, type LoadingStage, type LayoutMode } from '$lib/topology/Topology';
	import type { GroupVisualMode } from '$lib/topology/hubs/GroupMesh';
	import type { TrafficFxStyle, TunnelStyle, VolumeEnergyStyle } from '$lib/topology/lines/Connection';
	import type { TopologyNetworkTrafficIndex } from '$lib/topology/traffic-adapter';
	import type { NetworkPaletteMode } from '$lib/topology/hubs/NetworkHub';
	import logoHypercube from '$lib/assets/logo_hypercube.png';
	import InfoTooltip from './InfoTooltip.svelte';

	const STAGE_LABELS: Record<LoadingStage, string> = {
		models: 'Loading models…',
		scene: 'Building scene…',
		stabilizing: 'Stabilizing…',
		ready: '',
	};

	interface Props {
		containers: TopologyContainerData[];
		stackHealth?: Record<string, { running: number; total: number }>;
		onContainerClick?: (id: string) => void;
		onHubClick?: (hubId: string, hubType: 'stack' | 'network' | 'volume') => void;
		onEmptyClick?: () => void;
		showStack?: boolean;
		showNetwork?: boolean;
		showVolume?: boolean;
		curvedLines?: boolean;
		groupVisualMode?: GroupVisualMode;
		tunnelStyle?: TunnelStyle;
		networkTunnelThickness?: number;
		trafficFxStyle?: TrafficFxStyle;
		volumeEnergyStyle?: VolumeEnergyStyle;
		networkPaletteMode?: NetworkPaletteMode;
		networkTraffic?: TopologyNetworkTrafficIndex;
		layoutMode?: LayoutMode;
	}

	let {
		containers,
		stackHealth,
		onContainerClick,
		onHubClick,
		onEmptyClick,
		showStack = true,
		showNetwork = false,
		showVolume = false,
		curvedLines = true,
		groupVisualMode = 'soft',
		tunnelStyle = 'subsea',
		networkTunnelThickness = 0.7,
		trafficFxStyle = 'soft',
		volumeEnergyStyle = 'tendril',
		networkPaletteMode = 'cyan',
		networkTraffic = new Map(),
		layoutMode = 'force',
	}: Props = $props();

	let host: HTMLDivElement | undefined = $state();
	let topology: Topology | null = null;
	let mounted = $state(false);
	let tooltipInfo = $state<{ text: string; x: number; y: number } | null>(null);
	let tooltipRaf: number | null = null;
	let loadingStage = $state<LoadingStage>('models');
	let overlayHidden = $state(false);

	function buildCallbacks(): TopologyCallbacks {
		const cb: TopologyCallbacks = {};
		if (onContainerClick) cb.onContainerClick = onContainerClick;
		if (onHubClick) cb.onHubClick = onHubClick;
		if (onEmptyClick) cb.onEmptyClick = onEmptyClick;
		cb.onLoadingStage = (stage) => {
			loadingStage = stage;
			if (stage === 'ready') {
				// Let the CSS cross-fade play, then drop the node entirely
				// so it can't intercept clicks or cost a layer.
				setTimeout(() => {
					overlayHidden = true;
				}, 520);
			} else {
				overlayHidden = false;
			}
		};
		return cb;
	}

	function disposeTopology(): void {
		stopTooltipLoop();
		if (!topology) return;
		topology.dispose();
		topology = null;
	}

	function startTooltipLoop(): void {
		if (tooltipRaf !== null) return;
		const tick = () => {
			tooltipRaf = requestAnimationFrame(tick);
			if (!topology || !host) return;
			tooltipInfo = topology.getActiveTooltip(host);
		};
		tooltipRaf = requestAnimationFrame(tick);
	}

	function stopTooltipLoop(): void {
		if (tooltipRaf !== null) {
			cancelAnimationFrame(tooltipRaf);
			tooltipRaf = null;
		}
		tooltipInfo = null;
	}

	function mountTopology(): void {
		if (!host) return;
		topology = new Topology();
		// Model base URL (honours SvelteKit's BASE_PATH) — Topology
		// uses it to locate /models/container.glb and friends.
		topology.setModelBaseUrl(base);
		// Apply the current visibility props before mount so the first
		// update() inside mount() already honours them. Without this,
		// resetFocus() would always bring the scene up with the facade's
		// default (stack only) regardless of the checkbox state.
		topology.setHubVisibility('stack', showStack);
		topology.setHubVisibility('network', showNetwork);
		topology.setHubVisibility('volume', showVolume);
		topology.setCurvedLines(curvedLines);
		topology.setGroupVisualMode(groupVisualMode);
		topology.setTunnelStyle(tunnelStyle);
		topology.setNetworkTunnelThickness(networkTunnelThickness);
		topology.setTrafficFxStyle(trafficFxStyle);
		topology.setVolumeEnergyStyle(volumeEnergyStyle);
		topology.setNetworkPaletteMode(networkPaletteMode);
		topology.setLayoutMode(layoutMode);
		topology.mount(host, { containers, stackHealth, networkTraffic }, buildCallbacks());
		mounted = true;
		startTooltipLoop();
	}

	function reloadTopology(): void {
		disposeTopology();
		mountTopology();
	}

	onMount(async () => {
		await tick();
		if (!host) return;
		mountTopology();
	});

	onDestroy(() => {
		disposeTopology();
	});

	$effect(() => {
		if (!mounted || !topology) return;
		topology.update({ containers, stackHealth });
	});

	$effect(() => {
		if (!mounted || !topology) return;
		topology.setNetworkTraffic(networkTraffic);
	});

	// Re-apply visibility whenever the topology instance is (re)created
	// — e.g. after resetFocus() which remounts the scene — or when the
	// parent's toggle values change. Without this, ESC would snap back
	// to the default (stack only) regardless of what the user picked.
	$effect(() => {
		if (!mounted || !topology) return;
		topology.setHubVisibility('stack', showStack);
		topology.setHubVisibility('network', showNetwork);
		topology.setHubVisibility('volume', showVolume);
		topology.setCurvedLines(curvedLines);
		topology.setGroupVisualMode(groupVisualMode);
		topology.setTunnelStyle(tunnelStyle);
		topology.setNetworkTunnelThickness(networkTunnelThickness);
		topology.setTrafficFxStyle(trafficFxStyle);
		topology.setVolumeEnergyStyle(volumeEnergyStyle);
		topology.setNetworkPaletteMode(networkPaletteMode);
	});

	$effect(() => {
		if (!mounted || !topology) return;
		topology.setLayoutMode(layoutMode);
	});

	// External API — let the page (or future TopologyToolbar) trigger
	// focus / reset without exposing the Topology instance itself.
	//
	// resetFocus performs an in-place reset (camera + selection +
	// layout reheat) via Topology.resetFocus(). The previous
	// implementation called reloadTopology() which disposed and
	// remounted the whole scene — that re-ran GLB loading and showed
	// the loading overlay every time the user pressed Reset / ESC.
	// Use reloadTopologyHard() if a full teardown is ever needed.
	export function resetFocus(): void {
		topology?.resetFocus();
	}
	export function reloadTopologyHard(): void {
		reloadTopology();
	}
	export function focusContainer(id: string): void {
		topology?.focusContainer(id);
	}
	export function focusHub(id: string, type: 'stack' | 'network' | 'volume'): void {
		topology?.focusHub(id, type);
	}
	export function setHubVisibility(type: 'stack' | 'network' | 'volume', visible: boolean): void {
		topology?.setHubVisibility(type, visible);
	}
	export function setAutoRotate(enabled: boolean): void {
		topology?.setAutoRotate(enabled);
	}
	export function setCurvedLines(enabled: boolean): void {
		topology?.setCurvedLines(enabled);
	}
	export function setGroupVisualMode(mode: GroupVisualMode): void {
		topology?.setGroupVisualMode(mode);
	}
</script>

<div class="topology-canvas" bind:this={host}>
	{#if tooltipInfo}
		<div
			class="selection-tooltip"
			style="left: {tooltipInfo.x}px; top: {tooltipInfo.y}px;"
		>
			{tooltipInfo.text}
		</div>
	{/if}

	{#if !overlayHidden}
		<div class="loading-overlay" class:loading-overlay-ready={loadingStage === 'ready'}>
			<div class="loading-inner">
				<img class="loading-logo" src={logoHypercube} alt="HyperCube" />
				<div class="loading-stage">{STAGE_LABELS[loadingStage]}</div>
				<div class="loading-bar">
					<div class="loading-bar-shimmer"></div>
				</div>
			</div>
		</div>
	{/if}

	<div
		class="health-legend"
		class:health-legend-visible={loadingStage === 'ready'}
	>
		<div class="legend-title">
			Stack Health
			<InfoTooltip text={"각 Stack(Compose 프로젝트)의 \"건강 점수\"를 색으로 보여줍니다.\n\n• 점수 = 실행 중 컨테이너 비율, 평균 CPU·메모리 부하, 재시작/오류 발생 등을 합산\n• 0% (빨강) — 거의 모든 컨테이너가 비정상\n• 50% (노랑) — 일부 컨테이너에 문제 또는 고부하\n• 100% (초록) — 모든 컨테이너가 안정적으로 실행 중\n\n토폴로지 위 Stack 영역의 색이 이 게이지의 색과 매핑됩니다."} placement="top-end" />
		</div>
		<div class="legend-bar" aria-hidden="true"></div>
		<div class="legend-labels" aria-hidden="true">
			<span>0%</span>
			<span>50%</span>
			<span>100%</span>
		</div>
	</div>
</div>

<style>
	.topology-canvas {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		overflow: hidden;
	}

	.topology-canvas :global(canvas) {
		display: block;
		width: 100% !important;
		height: 100% !important;
	}

	.selection-tooltip {
		position: absolute;
		transform: translate(-50%, calc(-100% - 8px));
		pointer-events: none;
		background: rgba(13, 17, 23, 0.94);
		color: #e6fffb;
		border: 1px solid var(--accent);
		border-radius: 12px;
		padding: 10px 20px;
		font-size: 14px;
		font-weight: 700;
		letter-spacing: 0.01em;
		text-align: center;
		white-space: nowrap;
		backdrop-filter: blur(8px);
		min-width: 170px;
		max-width: 360px;
		overflow: hidden;
		text-overflow: ellipsis;
		z-index: 30;
		box-shadow:
			0 0 0 1px rgba(48, 213, 200, 0.15),
			0 10px 28px rgba(0, 0, 0, 0.55),
			0 0 32px rgba(48, 213, 200, 0.22);
	}

	/* Small downward arrow pointing at the selected entity. */
	.selection-tooltip::after {
		content: '';
		position: absolute;
		left: 50%;
		bottom: -6px;
		width: 10px;
		height: 10px;
		background: rgba(13, 17, 23, 0.94);
		border-right: 1px solid var(--accent);
		border-bottom: 1px solid var(--accent);
		transform: translateX(-50%) rotate(45deg);
	}

	/* ---------- Loading overlay (A + C hybrid) ---------- */
	.loading-overlay {
		position: absolute;
		inset: 0;
		z-index: 40;
		display: flex;
		align-items: center;
		justify-content: center;
		background:
			radial-gradient(
				ellipse at center,
				rgba(48, 213, 200, 0.06) 0%,
				rgba(13, 17, 23, 0.82) 45%,
				rgba(13, 17, 23, 0.96) 100%
			);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		opacity: 1;
		transition: opacity 480ms ease-out, backdrop-filter 480ms ease-out;
		pointer-events: none;
	}

	.loading-overlay-ready {
		opacity: 0;
		backdrop-filter: blur(0px);
		-webkit-backdrop-filter: blur(0px);
	}

	.loading-inner {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 22px;
		padding: 0 32px;
	}

	.loading-logo {
		width: 168px;
		max-width: 42vw;
		height: auto;
		opacity: 0.95;
		filter: drop-shadow(0 0 24px rgba(48, 213, 200, 0.32));
		animation: logo-breathe 2400ms ease-in-out infinite;
	}

	.loading-overlay-ready .loading-logo {
		animation: logo-ignite 420ms ease-out forwards;
	}

	.loading-stage {
		font-family: inherit;
		font-size: 12px;
		letter-spacing: 0.22em;
		text-transform: uppercase;
		color: rgba(203, 213, 225, 0.78);
		min-height: 14px;
	}

	.loading-bar {
		position: relative;
		width: 220px;
		max-width: 48vw;
		height: 2px;
		border-radius: 2px;
		background: rgba(48, 213, 200, 0.14);
		overflow: hidden;
	}

	.loading-bar-shimmer {
		position: absolute;
		inset: 0;
		width: 38%;
		background: linear-gradient(
			90deg,
			rgba(48, 213, 200, 0) 0%,
			rgba(48, 213, 200, 0.9) 50%,
			rgba(48, 213, 200, 0) 100%
		);
		box-shadow: 0 0 14px rgba(48, 213, 200, 0.55);
		animation: bar-shimmer 1400ms ease-in-out infinite;
	}

	@keyframes logo-breathe {
		0%, 100% { opacity: 0.82; transform: scale(0.99); }
		50%      { opacity: 1;    transform: scale(1.015); }
	}

	@keyframes logo-ignite {
		0%   { opacity: 1; transform: scale(1); filter: drop-shadow(0 0 28px rgba(48, 213, 200, 0.5)); }
		60%  { opacity: 1; transform: scale(1.06); filter: drop-shadow(0 0 48px rgba(48, 213, 200, 0.9)); }
		100% { opacity: 0; transform: scale(1.12); filter: drop-shadow(0 0 12px rgba(48, 213, 200, 0)); }
	}

	@keyframes bar-shimmer {
		0%   { transform: translateX(-80%); }
		100% { transform: translateX(260%); }
	}

	/* ---------- Stack Health legend (bottom-right overlay) ---------- */
	.health-legend {
		position: absolute;
		right: 16px;
		bottom: 16px;
		z-index: 20;
		padding: 10px 14px 9px;
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.78);
		border: 1px solid rgba(48, 213, 200, 0.16);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		pointer-events: none;
		min-width: 148px;
		opacity: 0;
		transform: translateY(4px);
		transition: opacity 360ms ease-out, transform 360ms ease-out;
		box-shadow: 0 6px 20px rgba(0, 0, 0, 0.38);
	}

	.health-legend-visible {
		opacity: 1;
		transform: translateY(0);
	}

	.legend-title {
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: rgba(203, 213, 225, 0.78);
		margin-bottom: 8px;
	}

	.legend-bar {
		height: 6px;
		border-radius: 3px;
		background: linear-gradient(90deg, #f87171 0%, #facc15 50%, #4ade80 100%);
		box-shadow:
			inset 0 0 0 1px rgba(15, 23, 42, 0.35),
			0 0 10px rgba(250, 204, 21, 0.18);
	}

	.legend-labels {
		display: flex;
		justify-content: space-between;
		margin-top: 5px;
		font-size: 10px;
		color: rgba(148, 163, 184, 0.85);
		font-weight: 600;
		letter-spacing: 0.02em;
	}
</style>
