<script lang="ts">
	import type { FleetAgentRow } from '$lib/stores/fleet-store';
	import { healthLabel } from '$lib/utils/fleet-format';

	let {
		agents = [],
		onSelect = () => {},
	}: {
		agents?: FleetAgentRow[];
		onSelect?: (agentId: string) => void;
	} = $props();

	let risks = $derived(agents.filter((row) => row.health !== 'healthy').slice(0, 8));
</script>

<section class="panel">
	<h2>Risk Servers</h2>
	{#if risks.length === 0}
		<p>No active risk servers.</p>
	{:else}
		<div class="list">
			{#each risks as row (row.agent.id)}
				<button type="button" class="row {row.health}" onclick={() => onSelect(row.agent.id)}>
					<span>
						<strong>{row.agent.hostname}</strong>
						<small>{row.health_reasons[0] ?? healthLabel(row.health)}</small>
					</span>
					<b>{healthLabel(row.health)}</b>
				</button>
			{/each}
		</div>
	{/if}
</section>

<style>
	.panel {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 10px;
	}
	h2 {
		margin: 0 0 8px;
		color: var(--text-primary);
		font-size: 15px;
	}
	p {
		margin: 0;
		color: var(--text-muted);
		font-size: 12px;
	}
	.list {
		display: grid;
		gap: 6px;
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: 10px;
		width: 100%;
		padding: 8px;
		text-align: left;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-left: 3px solid var(--border);
		border-radius: var(--radius-sm);
		color: var(--text-primary);
		cursor: pointer;
	}
	.row.critical {
		border-left-color: #ef4444;
	}
	.row.warning {
		border-left-color: #f59e0b;
	}
	.row strong,
	.row small {
		display: block;
	}
	.row small {
		margin-top: 2px;
		color: var(--text-muted);
		font-size: 11px;
	}
	.row b {
		color: var(--text-secondary);
		font-size: 11px;
		text-transform: uppercase;
	}
</style>
