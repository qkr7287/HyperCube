<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { base } from '$app/paths';
	import { Topology, type TopologyCallbacks, type TopologyContainerData } from '$lib/topology/Topology';

	interface Props {
		containers: TopologyContainerData[];
		onContainerClick?: (id: string) => void;
		onHubClick?: (hubId: string, hubType: 'stack' | 'network' | 'volume') => void;
		showStack?: boolean;
		showNetwork?: boolean;
		showVolume?: boolean;
	}

	let {
		containers,
		onContainerClick,
		onHubClick,
		showStack = true,
		showNetwork = false,
		showVolume = false,
	}: Props = $props();

	let host: HTMLDivElement | undefined = $state();
	let topology: Topology | null = null;
	let mounted = $state(false);

	function buildCallbacks(): TopologyCallbacks {
		const cb: TopologyCallbacks = {};
		if (onContainerClick) cb.onContainerClick = onContainerClick;
		if (onHubClick) cb.onHubClick = onHubClick;
		return cb;
	}

	function disposeTopology(): void {
		if (!topology) return;
		topology.dispose();
		topology = null;
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
		topology.mount(host, { containers }, buildCallbacks());
		mounted = true;
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
		topology.update({ containers });
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
	});

	// External API — let the page (or future TopologyToolbar) trigger
	// focus / reset without exposing the Topology instance itself.
	export function resetFocus(): void {
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
</script>

<div class="topology-canvas" bind:this={host}></div>

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
</style>
