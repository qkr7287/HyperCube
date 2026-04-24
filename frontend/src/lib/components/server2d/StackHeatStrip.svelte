<script lang="ts">
	import type { Server2dMetric } from '$lib/stores/server2d-view.svelte';

	type HeatCell = {
		id: string;
		name: string;
		state: string;
		cpu: number;
		memory: number;
		network: number;
		container: any;
	};

	let {
		cells = [] as HeatCell[],
		metric = 'cpu' as Server2dMetric,
		networkMax = 1,
		onSelect = (_container: any) => {},
	}: {
		cells?: HeatCell[];
		metric?: Server2dMetric;
		networkMax?: number;
		onSelect?: (container: any) => void;
	} = $props();

	function valueFor(cell: HeatCell): number {
		if (metric === 'cpu') return cell.cpu;
		if (metric === 'memory') return cell.memory;
		return cell.network;
	}

	function intensity(cell: HeatCell): number {
		if (metric === 'network') {
			if (!networkMax) return 0;
			return Math.max(0, Math.min(100, (cell.network / networkMax) * 100));
		}
		return Math.max(0, Math.min(100, valueFor(cell)));
	}

	function formatValue(cell: HeatCell): string {
		if (metric === 'network') {
			const value = cell.network;
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
		return `${valueFor(cell).toFixed(1)}%`;
	}

	function stateClass(state: string): string {
		if (state === 'running') return 'running';
		if (state === 'paused') return 'paused';
		if (state === 'dead' || state === 'restarting') return 'problem';
		return 'stopped';
	}
</script>

<div class="strip" role="list" aria-label={`${metric} 부하 스트립`}>
	{#each cells as cell (cell.id)}
		<button
			type="button"
			role="listitem"
			class={`cell ${stateClass(cell.state)}`}
			style={`--v:${intensity(cell).toFixed(0)}%;`}
			title={`${cell.name}\n${metric.toUpperCase()}: ${formatValue(cell)}`}
			aria-label={`${cell.name} ${formatValue(cell)}`}
			onclick={(event) => { event.stopPropagation(); onSelect(cell.container); }}
		></button>
	{/each}
	{#if cells.length === 0}
		<span class="empty">컨테이너 없음</span>
	{/if}
</div>

<style>
	.strip {
		display: flex;
		gap: 2px;
		overflow-x: auto;
		padding: 2px;
		border: 1px solid rgba(100, 116, 139, 0.14);
		border-radius: 6px;
		background: rgba(2, 6, 23, 0.4);
		min-height: 22px;
		align-items: stretch;
	}

	.strip::-webkit-scrollbar {
		height: 4px;
	}
	.strip::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.24);
		border-radius: 2px;
	}

	.cell {
		flex: 1 1 0;
		min-width: 6px;
		max-width: 18px;
		height: 18px;
		border: 1px solid rgba(100, 116, 139, 0.16);
		border-radius: 2px;
		padding: 0;
		cursor: pointer;
		background:
			linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0)),
			color-mix(in srgb, #f87171 var(--v), rgba(51, 65, 85, 0.6));
		transition: transform 0.1s ease, box-shadow 0.1s ease;
		flex-shrink: 0;
	}

	.cell:hover {
		transform: scale(1.25);
		z-index: 2;
		box-shadow: 0 0 0 2px rgba(48, 213, 200, 0.5);
	}

	.cell.running {
		box-shadow: inset 0 0 0 1px rgba(52, 211, 153, 0.22);
	}
	.cell.paused {
		box-shadow: inset 0 0 0 1px rgba(251, 191, 36, 0.36);
	}
	.cell.problem {
		box-shadow: inset 0 0 0 1px rgba(248, 113, 113, 0.5);
	}
	.cell.stopped {
		box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.24);
	}

	.empty {
		color: var(--text-muted);
		font-size: 10px;
		padding: 3px 6px;
	}
</style>
