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

	const soloed = $derived(view.soloStack);
	const topEntries = $derived.by(() => {
		const sorted = [...entries].sort((a, b) => b.value - a.value);
		if (soloed) {
			const active = sorted.find((entry) => entry.label === soloed);
			return active ? [active] : sorted.slice(0, maxChips);
		}
		return sorted.slice(0, maxChips);
	});
	const hiddenCount = $derived(
		Math.max(0, entries.length - topEntries.length - (soloed && entries.find((e) => e.label === soloed) ? 0 : 0)),
	);
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
	{#if hiddenCount > 0}
		<span class="more">+{hiddenCount}</span>
	{/if}
	{#if soloed}
		<button type="button" class="clear" onclick={clearSolo} title="전체 스택 보기">
			<svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true">
				<path d="M19 6.41 17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
			</svg>
			<span>전체</span>
		</button>
	{/if}
</div>

<style>
	.legend {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 4px;
		min-width: 0;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 3px 8px 3px 7px;
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
		white-space: nowrap;
		line-height: 1.2;
		transition: opacity 0.12s ease, transform 0.12s ease;
	}

	.chip:hover {
		filter: brightness(1.2);
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
		box-shadow: 0 0 5px color-mix(in srgb, var(--chip-color, #64748b) 55%, transparent);
		flex: 0 0 auto;
	}

	.chip b {
		font-weight: 800;
		max-width: 110px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.chip small {
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 800;
		white-space: nowrap;
		flex: 0 0 auto;
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
		display: inline-flex;
		align-items: center;
		gap: 3px;
		padding: 2px 8px;
		border: 1px solid rgba(248, 113, 113, 0.5);
		border-radius: 999px;
		background: rgba(248, 113, 113, 0.12);
		color: #f87171;
		font-size: 10px;
		font-weight: 800;
		cursor: pointer;
		flex: 0 0 auto;
		white-space: nowrap;
		line-height: 1;
		min-width: 0;
	}

	.clear span {
		white-space: nowrap;
	}

	.clear:hover {
		background: rgba(248, 113, 113, 0.22);
	}
</style>
