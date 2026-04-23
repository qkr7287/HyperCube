<script lang="ts">
	import type { FleetSummary } from '$lib/stores/fleet-store';
	import MetricHelp from './MetricHelp.svelte';

	let {
		summary = null,
	}: {
		summary?: FleetSummary | null;
	} = $props();

	let ops = $derived(summary?.operations_summary ?? null);
	let containers = $derived(summary?.container_summary ?? {});
	let totalContainers = $derived(Number(containers.total ?? 0));
	let runningRatio = $derived(totalContainers > 0 ? Math.round((Number(containers.running ?? 0) / totalContainers) * 100) : 0);
</script>

<aside class="ops-panel">
	<div class="head">
		<h2>Operations <MetricHelp text="Compact process, login, container, and metric freshness summary." placement="bottom-end" /></h2>
	</div>

	<div class="ops-grid">
		<div class="ops-card">
			<span>Processes</span>
			<strong>{ops?.processes_total ?? 0}</strong>
			<small>avg {Number(ops?.processes_avg ?? 0).toFixed(0)}</small>
		</div>
		<div class="ops-card">
			<span>Logins</span>
			<strong>{ops?.logins_total ?? 0}</strong>
			<small>avg {Number(ops?.logins_avg ?? 0).toFixed(1)}</small>
		</div>
	</div>

	<div class="section">
		<div class="section-title">Container Distribution</div>
		<div class="bar" aria-label="Running container ratio">
			<span style="width: {runningRatio}%"></span>
		</div>
		<div class="split">
			<span>{containers.running ?? 0} running</span>
			<span>{containers.non_running ?? 0} other</span>
			<span>{containers.problem ?? 0} problem</span>
		</div>
	</div>

	<div class="section">
		<div class="section-title">Freshness</div>
		<div class="freshness">
			<div><strong>{ops?.fresh_agents ?? 0}</strong><span>fresh</span></div>
			<div><strong>{ops?.warm_agents ?? 0}</strong><span>warm</span></div>
			<div><strong>{ops?.stale_agents ?? 0}</strong><span>stale</span></div>
			<div><strong>{ops?.expired_agents ?? 0}</strong><span>expired</span></div>
		</div>
	</div>
</aside>

<style>
	.ops-panel {
		min-width: 0;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 10px;
	}
	.head {
		margin-bottom: 8px;
	}
	h2,
	.section-title,
	.ops-card span {
		display: inline-flex;
		align-items: center;
		color: var(--text-primary);
	}
	h2 {
		margin: 0;
		font-size: 15px;
	}
	.ops-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 8px;
	}
	.ops-card,
	.section {
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
	}
	.ops-card {
		padding: 9px;
	}
	.ops-card span,
	.section-title {
		color: var(--text-secondary);
		font-size: 11px;
		font-weight: 800;
		text-transform: uppercase;
	}
	.ops-card strong {
		display: block;
		margin-top: 4px;
		color: var(--text-primary);
		font-size: 18px;
	}
	.ops-card small {
		color: var(--text-muted);
		font-size: 11px;
	}
	.section {
		margin-top: 8px;
		padding: 9px;
	}
	.bar {
		height: 8px;
		margin: 8px 0;
		border-radius: var(--radius-full);
		background: rgba(100, 116, 139, 0.22);
		overflow: hidden;
	}
	.bar span {
		display: block;
		height: 100%;
		background: linear-gradient(90deg, #22c55e, #30d5c8);
	}
	.split {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	.split span {
		color: var(--text-secondary);
		font-size: 11px;
		font-weight: 700;
	}
	.freshness {
		margin-top: 8px;
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 6px;
	}
	.freshness div {
		padding: 6px;
		border-radius: var(--radius-sm);
		background: var(--bg-tab);
		text-align: center;
	}
	.freshness strong {
		display: block;
		color: var(--text-primary);
		font-size: 14px;
	}
	.freshness span {
		color: var(--text-muted);
		font-size: 10px;
	}
</style>
