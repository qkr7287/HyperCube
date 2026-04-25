<script lang="ts">
	import { view } from '$lib/stores/server2d-view.svelte';

	type LegendEntry = {
		label: string;
		color: string;
		value: number;
	};

	let {
		entries = [] as LegendEntry[],
		format = (value: number) => `${value.toFixed(1)}%`,
		maxChips = 3,
	}: {
		entries?: LegendEntry[];
		format?: (value: number) => string;
		maxChips?: number;
	} = $props();

	function toggleSolo(label: string) {
		view.soloStack = view.soloStack === label ? null : label;
	}

	function clearSolo() {
		view.soloStack = null;
	}

	const topEntries = $derived(
		[...entries].sort((a, b) => b.value - a.value).slice(0, maxChips),
	);
	const soloed = $derived(view.soloStack);
</script>

<div class="legend">
	{#each topEntries as entry (entry.label)}
		<button
			type="button"
			class="chip"
			class:active={soloed === entry.label}
			class:dim={soloed && soloed !== entry.label}
			onclick={() => toggleSolo(entry.label)}
			style={`--chip-color:${entry.color}`}
		>
			<i class="dot"></i>
			<b>{entry.label}</b>
			<small>{format(entry.value)}</small>
		</button>
	{/each}
	{#if entries.length > maxChips}
		<span class="more">+{entries.length - maxChips}</span>
	{/if}
	{#if soloed}
		<button type="button" class="clear" onclick={clearSolo}>× 전체 보기</button>
	{/if}
</div>

<style>
	.legend {
		display: flex;
		flex-wrap: nowrap;
		align-items: center;
		gap: 3px;
		min-width: 0;
		overflow: hidden;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 7px 2px 6px;
		border: 1px solid var(--chip-color, #64748b);
		border-radius: 999px;
		background: color-mix(in srgb, var(--chip-color, #64748b) 14%, rgba(13, 17, 23, 0.5));
		color: var(--text-primary);
		font-size: 10px;
		font-weight: 700;
		cursor: pointer;
		flex: 0 1 auto;
		min-width: 0;
		overflow: hidden;
		transition: opacity 0.12s ease, transform 0.12s ease;
	}

	.chip.active {
		box-shadow: 0 0 0 2px var(--chip-color, #64748b);
		transform: translateY(-1px);
	}

	.chip.dim {
		opacity: 0.32;
	}

	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--chip-color, #64748b);
		box-shadow: 0 0 6px color-mix(in srgb, var(--chip-color, #64748b) 55%, transparent);
		flex: 0 0 auto;
	}

	.chip b {
		font-weight: 800;
		max-width: 80px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.chip small {
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 800;
	}

	.more {
		padding: 1px 7px;
		border-radius: 999px;
		background: rgba(15, 23, 42, 0.55);
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
	}

	.clear {
		padding: 2px 8px;
		border: 1px solid rgba(248, 113, 113, 0.5);
		border-radius: 999px;
		background: rgba(248, 113, 113, 0.12);
		color: #f87171;
		font-size: 10px;
		font-weight: 800;
		cursor: pointer;
	}

	.clear:hover {
		background: rgba(248, 113, 113, 0.22);
	}
</style>
