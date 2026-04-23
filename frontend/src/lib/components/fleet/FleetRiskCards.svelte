<script lang="ts">
	import MetricHelp from './MetricHelp.svelte';
	import { formatPercent, formatRelative, healthLabel } from '$lib/utils/fleet-format';
	import type { FleetAgentRow } from '$lib/stores/fleet-store';

	let {
		agents = [],
		selectedId = null,
		onSelect,
	}: {
		agents?: FleetAgentRow[];
		selectedId?: string | null;
		onSelect: (agentId: string) => void;
	} = $props();

	let problematic = $derived(agents.filter((row) => row.health !== 'healthy'));
	let visible = $derived(problematic.slice(0, 12));
	let remaining = $derived(Math.max(0, problematic.length - visible.length));

	function worstMetric(row: FleetAgentRow): { label: string; value: number } {
		const cpu = row.latest?.cpu_usage ?? 0;
		const memory = row.latest?.memory_usage ?? 0;
		const disk = row.latest?.disk_usage ?? 0;
		const gpu = row.latest?.gpu_usage ?? 0;
		const max = Math.max(cpu, memory, disk, gpu);
		if (max === memory) return { label: 'Memory', value: memory };
		if (max === disk) return { label: 'Disk', value: disk };
		if (max === gpu) return { label: 'GPU', value: gpu };
		return { label: 'CPU', value: cpu };
	}
</script>

<section class="risk-strip" aria-label="Servers needing attention">
	<div class="head">
		<div class="title-wrap">
			<h2>Needs Attention</h2>
			<MetricHelp text="Critical, warning, stale, and offline servers are surfaced here before the full table." />
			<span class="badge" class:ok={problematic.length === 0}>
				{problematic.length === 0 ? 'All clear' : `${problematic.length} servers`}
			</span>
		</div>
		<p class="hint">
			{problematic.length === 0
				? 'Every monitored server is inside the healthy threshold.'
				: 'Select a card to focus the detail panel and table row.'}
		</p>
	</div>

	{#if problematic.length > 0}
		<div class="cards">
			{#each visible as row (row.agent.id)}
				{@const worst = worstMetric(row)}
				<button
					type="button"
					class="card {row.health}"
					class:selected={selectedId === row.agent.id}
					onclick={() => onSelect(row.agent.id)}
					title={`${row.agent.hostname} details`}
				>
					<div class="card-head">
						<strong>{row.agent.hostname}</strong>
						<span class="health-tag {row.health}">{healthLabel(row.health)}</span>
					</div>
					<div class="card-meta">{row.agent.ip_address}</div>
					<div class="card-metric">
						<span class="metric-label">{worst.label}</span>
						<strong class="metric-value">{formatPercent(worst.value, 0)}</strong>
					</div>
					<div class="card-tiny">
						<span>CPU {formatPercent(row.latest?.cpu_usage, 0)}</span>
						<span>MEM {formatPercent(row.latest?.memory_usage, 0)}</span>
						<span>DSK {formatPercent(row.latest?.disk_usage, 0)}</span>
						{#if (row.latest?.gpu_count ?? 0) > 0}
							<span>GPU {formatPercent(row.latest?.gpu_usage, 0)}</span>
						{/if}
					</div>
					<div class="card-reason">
						<span>{row.health_reasons[0] ?? 'Check server state'}</span>
						<span class="age">{formatRelative(row.latest?.timestamp)}</span>
					</div>
				</button>
			{/each}
			{#if remaining > 0}
				<div class="card more">
					<strong>+{remaining}</strong>
					<span>more servers</span>
					<span class="hint-small">Open the table below</span>
				</div>
			{/if}
		</div>
	{/if}
</section>

<style>
	.risk-strip {
		display: flex;
		flex-direction: column;
		gap: 8px;
		flex-shrink: 0;
	}
	.head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
	}
	.title-wrap {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}
	h2 {
		margin: 0;
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 800;
		letter-spacing: 0;
	}
	.badge {
		display: inline-flex;
		align-items: center;
		padding: 2px 7px;
		border-radius: var(--radius-full);
		background: rgba(248, 113, 113, 0.18);
		color: #fca5a5;
		font-size: 10px;
		font-weight: 800;
		border: 1px solid rgba(248, 113, 113, 0.3);
	}
	.badge.ok {
		background: rgba(52, 211, 153, 0.12);
		color: #34d399;
		border-color: rgba(52, 211, 153, 0.3);
	}
	.hint {
		margin: 0;
		color: var(--text-muted);
		font-size: 11px;
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
		gap: 8px;
	}
	.card {
		text-align: left;
		min-width: 0;
		padding: 10px 12px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-left: 3px solid var(--border);
		border-radius: var(--radius-md);
		color: inherit;
		font-family: inherit;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: 4px;
		transition: border-color 0.12s ease, transform 0.12s ease, background 0.12s ease;
	}
	.card:hover {
		background: var(--bg-tab);
		transform: translateY(-1px);
	}
	.card.selected {
		outline: 1px solid rgba(48, 213, 200, 0.55);
		outline-offset: -1px;
	}
	.card.critical {
		border-left-color: #ef4444;
		background: linear-gradient(180deg, rgba(239, 68, 68, 0.06), var(--bg-card) 55%);
	}
	.card.warning {
		border-left-color: #f59e0b;
		background: linear-gradient(180deg, rgba(245, 158, 11, 0.05), var(--bg-card) 55%);
	}
	.card.stale {
		border-left-color: #a78bfa;
	}
	.card.offline {
		border-left-color: #64748b;
	}
	.card-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
	}
	.card-head strong {
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
	.health-tag {
		display: inline-flex;
		padding: 2px 6px;
		border-radius: var(--radius-sm);
		font-size: 10px;
		font-weight: 800;
		text-transform: uppercase;
		white-space: nowrap;
	}
	.health-tag.critical {
		color: #fecaca;
		background: rgba(239, 68, 68, 0.22);
	}
	.health-tag.warning {
		color: #fcd34d;
		background: rgba(245, 158, 11, 0.22);
	}
	.health-tag.stale {
		color: #c4b5fd;
		background: rgba(167, 139, 250, 0.22);
	}
	.health-tag.offline {
		color: #cbd5e1;
		background: rgba(100, 116, 139, 0.22);
	}
	.card-meta {
		color: var(--text-muted);
		font-size: 11px;
		font-variant-numeric: tabular-nums;
	}
	.card-metric {
		display: flex;
		align-items: baseline;
		gap: 6px;
		margin-top: 2px;
	}
	.metric-label {
		color: var(--text-secondary);
		font-size: 10px;
		font-weight: 800;
		text-transform: uppercase;
	}
	.metric-value {
		color: var(--text-primary);
		font-size: 20px;
		font-weight: 750;
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}
	.card.critical .metric-value {
		color: #f87171;
	}
	.card.warning .metric-value {
		color: #fbbf24;
	}
	.card-tiny {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}
	.card-tiny span {
		display: inline-flex;
		align-items: center;
		padding: 2px 6px;
		border-radius: var(--radius-sm);
		background: rgba(13, 17, 23, 0.55);
		color: var(--text-secondary);
		font-size: 10px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.card-reason {
		display: flex;
		justify-content: space-between;
		gap: 6px;
		padding-top: 3px;
		border-top: 1px solid rgba(100, 116, 139, 0.12);
		color: var(--text-muted);
		font-size: 11px;
	}
	.card-reason .age {
		white-space: nowrap;
	}
	.card.more {
		justify-content: center;
		align-items: center;
		text-align: center;
		cursor: default;
		color: var(--text-muted);
	}
	.card.more strong {
		color: var(--text-primary);
		font-size: 18px;
	}
	.card.more span {
		font-size: 11px;
	}
	.hint-small {
		color: var(--text-muted);
		font-size: 10px;
	}
	@media (max-width: 760px) {
		.head {
			align-items: flex-start;
			flex-direction: column;
		}
	}
</style>
