<script lang="ts">
	import { onDestroy, onMount, tick } from 'svelte';
	import { Topology, type TopologyCallbacks, type TopologyContainerData } from '$lib/topology/Topology';

	interface Props {
		containers: TopologyContainerData[];
		onContainerClick?: (id: string) => void;
		onHubClick?: (hubId: string, hubType: 'stack' | 'network' | 'volume') => void;
	}

	let { containers, onContainerClick, onHubClick }: Props = $props();

	let host: HTMLDivElement | undefined = $state();
	let topology: Topology | null = null;
	let mounted = $state(false);

	onMount(async () => {
		await tick();
		if (!host) return;
		const cb: TopologyCallbacks = {};
		if (onContainerClick) cb.onContainerClick = onContainerClick;
		if (onHubClick) cb.onHubClick = onHubClick;
		topology = new Topology();
		topology.mount(host, { containers }, cb);
		mounted = true;
	});

	onDestroy(() => {
		if (topology) {
			topology.dispose();
			topology = null;
		}
	});

	$effect(() => {
		if (!mounted || !topology) return;
		topology.update({ containers });
	});

	// External API — let the page (or future TopologyToolbar) trigger
	// focus / reset without exposing the Topology instance itself.
	export function resetFocus(): void {
		topology?.resetFocus();
	}
	export function focusContainer(id: string): void {
		topology?.focusContainer(id);
	}
	export function focusHub(id: string, type: 'stack' | 'network' | 'volume'): void {
		topology?.focusHub(id, type);
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
