<script lang="ts">
	import type { FleetAgentSeries, FleetHistoryPoint, FleetSummary } from '$lib/stores/fleet-store';
	import MetricHelp from './MetricHelp.svelte';
	import FleetLineChart from './FleetLineChart.svelte';

	let {
		history = [],
		agentSeries = [],
		summary = null,
		loading = false,
	}: {
		history?: FleetHistoryPoint[];
		agentSeries?: FleetAgentSeries[];
		summary?: FleetSummary | null;
		loading?: boolean;
	} = $props();

	function labelFor(iso: string): string {
		const date = new Date(iso);
		if (Number.isNaN(date.getTime())) return '';
		return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	let labels = $derived(history.map((point) => labelFor(point.timestamp)));
	let hiddenAgentIds = $state<Set<string>>(new Set());
	let hasGpu = $derived((summary?.metric_summary.gpu_max ?? 0) > 0 || agentSeries.some((agent) => agent.gpu.some((value) => value > 0)));

	function isHidden(agentId: string): boolean {
		return hiddenAgentIds.has(agentId);
	}

	function toggleAgent(agentId: string) {
		const next = new Set(hiddenAgentIds);
		if (next.has(agentId)) next.delete(agentId);
		else next.add(agentId);
		hiddenAgentIds = next;
	}

	function seriesFor(metric: keyof Pick<FleetAgentSeries, 'cpu' | 'memory' | 'disk' | 'network' | 'gpu'>) {
		return agentSeries.map((agent) => ({
			label: agent.hostname,
			values: agent[metric],
			color: agent.color,
			hidden: isHidden(agent.agent_id),
		}));
	}

	let cpuSeries = $derived(seriesFor('cpu'));
	let memorySeries = $derived(seriesFor('memory'));
	let diskSeries = $derived(seriesFor('disk'));
	let networkSeries = $derived(seriesFor('network'));
	let gpuSeries = $derived(seriesFor('gpu'));
</script>

<section class="trend-panel">
	<div class="panel-head">
		<div class="title-wrap">
			<h2>Fleet Trends</h2>
			<MetricHelp text="Compare resource trends by server over the selected time range. Use the legend to hide or show a server." />
			<span class="count">{agentSeries.length} servers</span>
		</div>
		{#if agentSeries.length}
			<div class="agent-legend" aria-label="Server series">
				{#each agentSeries as agent (agent.agent_id)}
					<button
						class="legend-item"
						class:muted={isHidden(agent.agent_id)}
						type="button"
						onclick={() => toggleAgent(agent.agent_id)}
						aria-pressed={!isHidden(agent.agent_id)}
						title={`${agent.hostname}: show or hide`}
					>
						<i style={`background: ${agent.color}`}></i>{agent.hostname}
					</button>
				{/each}
			</div>
		{/if}
	</div>

	<div class="charts" class:with-gpu={hasGpu}>
		<FleetLineChart
			title="CPU Usage"
			help="CPU utilization by server. Spikes above 90% are classified as critical."
			{labels}
			series={cpuSeries}
			{loading}
		/>
		<FleetLineChart
			title="Memory Usage"
			help="Memory utilization by server. Sustained pressure above 90% is critical."
			{labels}
			series={memorySeries}
			{loading}
		/>
		<FleetLineChart
			title="Disk Usage"
			help="Disk utilization by server. High disk pressure is surfaced early because it often causes container failures."
			{labels}
			series={diskSeries}
			{loading}
		/>
		<FleetLineChart
			title="Network Throughput"
			help="Combined receive and transmit throughput by server."
			{labels}
			unit="rate"
			series={networkSeries}
			{loading}
		/>
		{#if hasGpu}
			<FleetLineChart
				title="GPU Usage"
				help="GPU utilization by server when GPU metrics are available."
				{labels}
				series={gpuSeries}
				{loading}
			/>
		{/if}
	</div>
</section>

<style>
	.trend-panel {
		min-width: 0;
	}
	.panel-head {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		align-items: center;
		flex-wrap: wrap;
		margin-bottom: 8px;
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
	.count {
		padding: 2px 7px;
		border-radius: var(--radius-full);
		background: rgba(48, 213, 200, 0.12);
		color: var(--accent);
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.agent-legend {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
		color: var(--text-secondary);
		font-size: 11px;
	}
	.legend-item {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		border: 1px solid rgba(100, 116, 139, 0.16);
		color: var(--text-secondary);
		font-family: inherit;
		cursor: pointer;
		padding: 4px 7px;
		border-radius: var(--radius-full);
		background: rgba(13, 17, 23, 0.48);
		font-weight: 700;
		max-width: 160px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.legend-item:hover {
		border-color: rgba(48, 213, 200, 0.42);
		color: var(--text-primary);
	}
	.legend-item.muted {
		opacity: 0.38;
		text-decoration: line-through;
	}
	.legend-item i {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		box-shadow: 0 0 8px currentColor;
		flex-shrink: 0;
	}
	.charts {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 8px;
	}
	.charts.with-gpu {
		grid-template-columns: repeat(5, minmax(0, 1fr));
	}
	@media (max-width: 1640px) {
		.charts,
		.charts.with-gpu {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 820px) {
		.panel-head {
			align-items: flex-start;
			flex-direction: column;
		}
		.charts,
		.charts.with-gpu {
			grid-template-columns: 1fr;
		}
	}
</style>
