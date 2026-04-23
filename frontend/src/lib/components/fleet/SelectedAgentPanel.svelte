<script lang="ts">
	import type { AgentHistoryPoint, FleetAgentRow } from '$lib/stores/fleet-store';
	import { formatPercent, formatRate, formatRelative, healthLabel } from '$lib/utils/fleet-format';
	import MetricHelp from './MetricHelp.svelte';
	import MetricSparkline from './MetricSparkline.svelte';

	let {
		agent = null,
		history = [],
		onOpen3d,
	}: {
		agent?: FleetAgentRow | null;
		history?: AgentHistoryPoint[];
		onOpen3d: (agentId: string) => void;
	} = $props();

	let cpu = $derived(history.map((point) => point.cpu_usage));
	let memory = $derived(history.map((point) => point.memory_usage));
	let disk = $derived(history.map((point) => point.disk_usage));
	let gpu = $derived(history.map((point) => point.gpu_usage).filter((value) => value > 0));
	let network = $derived(history.map((point) => point.network_rx_rate + point.network_tx_rate));
</script>

<section class="detail">
	{#if !agent}
		<div class="empty">
			<h2>Selected Server</h2>
			<p>Select a server row to inspect its latest metrics, containers, and 3D topology shortcut.</p>
		</div>
	{:else}
		<div class="head">
			<div class="head-title">
				<h2 title={agent.agent.hostname}>{agent.agent.hostname}</h2>
				<div class="head-meta">
					<span class="health-tag {agent.health}">{healthLabel(agent.health)}</span>
					<span class="ip">{agent.agent.ip_address}</span>
					<span class="age">metric {formatRelative(agent.latest?.timestamp)}</span>
				</div>
			</div>
			<button type="button" onclick={() => onOpen3d(agent.agent.id)}>Open 3D</button>
		</div>

		{#if agent.health_reasons.length > 0}
			<div class="reasons">
				{#each agent.health_reasons.slice(0, 3) as reason}
					<span>{reason}</span>
				{/each}
			</div>
		{/if}

		<div class="metrics">
			<div class="metric-card">
				<span class="m-label">CPU <MetricHelp text="Latest CPU utilization and recent trend for the selected server." /></span>
				<strong class="m-value">{formatPercent(agent.latest?.cpu_usage)}</strong>
				<div class="sparkline-wrap"><MetricSparkline values={cpu} /></div>
			</div>
			<div class="metric-card">
				<span class="m-label">Memory <MetricHelp text="Latest memory utilization and recent trend for the selected server." /></span>
				<strong class="m-value">{formatPercent(agent.latest?.memory_usage)}</strong>
				<div class="sparkline-wrap"><MetricSparkline values={memory} color="#60a5fa" /></div>
			</div>
			<div class="metric-card">
				<span class="m-label">Disk <MetricHelp text="Latest disk utilization and recent trend for the selected server." /></span>
				<strong class="m-value">{formatPercent(agent.latest?.disk_usage)}</strong>
				<div class="sparkline-wrap"><MetricSparkline values={disk} color="#a78bfa" /></div>
			</div>
			<div class="metric-card">
				<span class="m-label">Network <MetricHelp text="Latest receive/transmit throughput and recent combined trend." placement="bottom-end" /></span>
				<strong class="m-value small">{formatRate((agent.latest?.network_rx_rate ?? 0) + (agent.latest?.network_tx_rate ?? 0))}</strong>
				<div class="net-split">
					<span>RX {formatRate(agent.latest?.network_rx_rate)}</span>
					<span>TX {formatRate(agent.latest?.network_tx_rate)}</span>
				</div>
				<div class="sparkline-wrap"><MetricSparkline values={network} color="#fbbf24" /></div>
			</div>
			{#if (agent.latest?.gpu_count ?? 0) > 0}
				<div class="metric-card metric-card-wide">
					<span class="m-label">GPU <MetricHelp text="Average GPU utilization and maximum reported temperature for this server." /></span>
					<strong class="m-value">{formatPercent(agent.latest?.gpu_usage)}</strong>
					<div class="net-split">
						<span>{agent.latest?.gpu_count} device(s)</span>
						<span>{agent.latest?.gpu_temperature ?? '-'} C</span>
					</div>
					<div class="sparkline-wrap"><MetricSparkline values={gpu} color="#fb7185" /></div>
				</div>
			{/if}
		</div>

		<div class="containers">
			<div class="ct-head">
				<span>Containers <MetricHelp text="Container state counts for the selected server." /></span>
				<strong>{agent.containers.total ?? 0}</strong>
			</div>
			<div class="ct-counts">
				<span class="ct running"><b>{agent.containers.running ?? 0}</b> running</span>
				<span class="ct other"><b>{agent.containers.non_running ?? 0}</b> other</span>
				<span class="ct problem" class:active={(agent.containers.problem ?? 0) > 0}>
					<b>{agent.containers.problem ?? 0}</b> problem
				</span>
			</div>
		</div>

		<div class="ops-row">
			<div>
				<span class="ops-label">Processes</span>
				<strong>{agent.latest?.processes_total ?? 0}</strong>
			</div>
			<div>
				<span class="ops-label">Logins</span>
				<strong>{agent.latest?.logins_total ?? 0}</strong>
			</div>
			<div>
				<span class="ops-label">Agent</span>
				<strong class="small">{agent.agent.is_active ? 'Online' : 'Offline'}</strong>
			</div>
		</div>
	{/if}
</section>

<style>
	.detail {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 12px;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.empty {
		display: grid;
		align-content: center;
		min-height: 132px;
		color: var(--text-muted);
	}
	h2 {
		margin: 0;
		color: var(--text-primary);
		font-size: 15px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	p {
		margin: 3px 0 0;
		color: var(--text-muted);
		font-size: 12px;
	}
	.head {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		align-items: flex-start;
	}
	.head-title {
		min-width: 0;
		flex: 1;
	}
	.head-meta {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		margin-top: 4px;
	}
	.health-tag {
		display: inline-flex;
		padding: 2px 7px;
		border-radius: var(--radius-sm);
		font-size: 10px;
		font-weight: 800;
		text-transform: uppercase;
	}
	.health-tag.healthy { color: #34d399; background: rgba(52, 211, 153, 0.14); }
	.health-tag.warning { color: #fbbf24; background: rgba(245, 158, 11, 0.18); }
	.health-tag.critical { color: #f87171; background: rgba(239, 68, 68, 0.18); }
	.health-tag.stale { color: #c4b5fd; background: rgba(167, 139, 250, 0.18); }
	.health-tag.offline { color: #cbd5e1; background: rgba(100, 116, 139, 0.18); }
	.ip,
	.age {
		color: var(--text-muted);
		font-size: 11px;
		font-variant-numeric: tabular-nums;
	}
	button {
		height: 30px;
		padding: 0 12px;
		border: 1px solid rgba(48, 213, 200, 0.4);
		border-radius: var(--radius-sm);
		background: rgba(48, 213, 200, 0.1);
		color: var(--accent);
		font-size: 12px;
		font-weight: 800;
		cursor: pointer;
		white-space: nowrap;
		flex-shrink: 0;
	}
	button:hover {
		background: rgba(48, 213, 200, 0.18);
	}
	.reasons {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.reasons span {
		padding: 3px 7px;
		border-radius: var(--radius-sm);
		background: rgba(239, 68, 68, 0.12);
		color: #fca5a5;
		font-size: 11px;
		font-weight: 700;
		border: 1px solid rgba(239, 68, 68, 0.25);
	}
	.metrics {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
	}
	.metric-card {
		min-width: 0;
		padding: 8px 10px;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-height: 82px;
	}
	.metric-card-wide {
		grid-column: 1 / -1;
	}
	.m-label {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: var(--text-secondary);
		font-size: 10px;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.3px;
	}
	.m-value {
		color: var(--text-primary);
		font-size: 18px;
		font-weight: 750;
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}
	.m-value.small {
		font-size: 15px;
	}
	.net-split {
		display: flex;
		justify-content: space-between;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		margin-top: -2px;
	}
	.sparkline-wrap {
		margin-top: auto;
		height: 22px;
	}
	.sparkline-wrap :global(svg) {
		width: 100%;
		height: 100%;
	}
	.containers {
		padding: 8px 10px;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
	}
	.ct-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}
	.ct-head span {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: var(--text-secondary);
		font-size: 10px;
		font-weight: 800;
		text-transform: uppercase;
	}
	.ct-head strong {
		color: var(--text-primary);
		font-size: 18px;
		font-weight: 750;
		font-variant-numeric: tabular-nums;
	}
	.ct-counts {
		display: flex;
		gap: 6px;
		margin-top: 6px;
	}
	.ct {
		flex: 1;
		display: flex;
		align-items: baseline;
		gap: 4px;
		padding: 4px 7px;
		background: var(--bg-tab);
		border-radius: var(--radius-sm);
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
	}
	.ct b {
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
	}
	.ct.running b {
		color: #34d399;
	}
	.ct.problem.active {
		background: rgba(239, 68, 68, 0.12);
	}
	.ct.problem.active b {
		color: #f87171;
	}
	.ops-row {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 8px;
	}
	.ops-row > div {
		padding: 7px 10px;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.ops-label {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		text-transform: uppercase;
		letter-spacing: 0.3px;
	}
	.ops-row strong {
		color: var(--text-primary);
		font-size: 16px;
		font-weight: 750;
		font-variant-numeric: tabular-nums;
	}
	.ops-row strong.small {
		font-size: 13px;
	}
	@media (max-width: 700px) {
		.head,
		.ct-counts {
			display: block;
		}
		button {
			margin-top: 10px;
		}
		.metrics,
		.ops-row {
			grid-template-columns: 1fr;
		}
	}
</style>
