<script lang="ts">
	import type { FleetAgentRow } from '$lib/stores/fleet-store';
	import { formatPercent, healthLabel } from '$lib/utils/fleet-format';

	let {
		agent = null,
	}: {
		agent?: FleetAgentRow | null;
	} = $props();
</script>

<section class="summary">
	{#if !agent}
		<p>Select a server to see a compact summary.</p>
	{:else}
		<div class="head">
			<h2>{agent.agent.hostname}</h2>
			<span class={agent.health}>{healthLabel(agent.health)}</span>
		</div>
		<div class="grid">
			<div><small>CPU</small><strong>{formatPercent(agent.latest?.cpu_usage)}</strong></div>
			<div><small>Memory</small><strong>{formatPercent(agent.latest?.memory_usage)}</strong></div>
			<div><small>Disk</small><strong>{formatPercent(agent.latest?.disk_usage)}</strong></div>
			<div><small>Containers</small><strong>{agent.containers.running ?? 0}/{agent.containers.total ?? 0}</strong></div>
		</div>
	{/if}
</section>

<style>
	.summary {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 10px;
	}
	p {
		margin: 0;
		color: var(--text-muted);
		font-size: 12px;
	}
	.head {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		align-items: center;
	}
	h2 {
		margin: 0;
		color: var(--text-primary);
		font-size: 15px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.head span {
		padding: 2px 7px;
		border-radius: var(--radius-sm);
		font-size: 10px;
		font-weight: 800;
		text-transform: uppercase;
	}
	.head span.healthy { color: #34d399; background: rgba(52, 211, 153, 0.12); }
	.head span.warning { color: #fbbf24; background: rgba(251, 191, 36, 0.12); }
	.head span.critical { color: #f87171; background: rgba(248, 113, 113, 0.12); }
	.head span.stale,
	.head span.offline { color: #94a3b8; background: rgba(148, 163, 184, 0.12); }
	.grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 8px;
		margin-top: 10px;
	}
	.grid div {
		padding: 8px;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
	}
	small {
		display: block;
		color: var(--text-muted);
		font-size: 10px;
		text-transform: uppercase;
	}
	strong {
		display: block;
		margin-top: 3px;
		color: var(--text-primary);
		font-size: 14px;
	}
</style>
