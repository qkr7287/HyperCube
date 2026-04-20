<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import UserMetricChart from '$lib/components/UserMetricChart.svelte';
	import {
		formatBytesValue,
		formatDateTime,
		formatMemoryUsage,
		formatPercent,
		statusLabel,
		statusTone,
	} from '$lib/utils/container-dashboard';

	type ContainerDetail = {
		container_id: string;
		name: string;
		image: string;
		status: string;
		last_seen: string;
		agent_hostname?: string;
		template_name?: string | null;
		request_id?: string | null;
		requested_at?: string | null;
		request_status?: string | null;
		review_note?: string;
		custom_env?: Record<string, string>;
		custom_ports?: Array<{ host?: number; container?: number; protocol?: string }>;
		selected_image?: string;
	};

	type MetricsSnapshot = {
		timestamp?: string | null;
		containerId?: string;
		cpu?: { usage?: number };
		memory?: { usage?: number; limit?: number; percent?: number };
		network?: { rx?: number; tx?: number };
		disk?: { read?: number; write?: number };
	};

	type MetricsHistoryRow = {
		recorded_at: string;
		cpu_usage: number;
		memory_usage: number;
		memory_limit: number;
		memory_percent: number;
		network_rx: number;
		network_tx: number;
		disk_read: number;
		disk_write: number;
	};

	const RANGE_OPTIONS = [
		{ key: '1h', label: '1H' },
		{ key: '6h', label: '6H' },
		{ key: '24h', label: '24H' },
		{ key: '7d', label: '7D' },
	] as const;

	let container = $state<ContainerDetail | null>(null);
	let currentMetrics = $state<MetricsSnapshot | null>(null);
	let history = $state<MetricsHistoryRow[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let errorMsg = $state('');
	let selectedRange = $state<(typeof RANGE_OPTIONS)[number]['key']>('1h');
	let refreshTimer: ReturnType<typeof setInterval> | null = null;

	let containerId = $derived($page.params.containerId);

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function api<T>(path: string): Promise<T> {
		const t = token();
		if (!t) throw new Error('Authentication required.');
		const response = await fetch(`${base}${path}`, {
			headers: { Authorization: `Bearer ${t}` },
		});
		const json = await response.json().catch(() => ({}));
		if (!response.ok) {
			throw new Error(json?.error?.detail || json?.detail || `HTTP ${response.status}`);
		}
		return json.data as T;
	}

	function normalizeHistory(rows: MetricsHistoryRow[], snapshot: MetricsSnapshot | null): MetricsHistoryRow[] {
		if (rows.length > 0 || !snapshot?.timestamp) return rows;
		return [
			{
				recorded_at: snapshot.timestamp,
				cpu_usage: snapshot.cpu?.usage ?? 0,
				memory_usage: snapshot.memory?.usage ?? 0,
				memory_limit: snapshot.memory?.limit ?? 0,
				memory_percent: snapshot.memory?.percent ?? 0,
				network_rx: snapshot.network?.rx ?? 0,
				network_tx: snapshot.network?.tx ?? 0,
				disk_read: snapshot.disk?.read ?? 0,
				disk_write: snapshot.disk?.write ?? 0,
			},
		];
	}

	async function loadDetail() {
		container = await api<ContainerDetail>(`/api/my-containers/${containerId}/`);
	}

	async function loadCurrentMetrics() {
		currentMetrics = await api<MetricsSnapshot>(`/api/my-containers/${containerId}/current-metrics/`);
	}

	async function loadHistory() {
		history = await api<MetricsHistoryRow[]>(
			`/api/my-containers/${containerId}/metrics-history/?range=${selectedRange}&limit=240`,
		);
	}

	async function loadDashboard(options: { withDetail?: boolean } = {}) {
		const { withDetail = false } = options;
		if (!containerId) return;
		if (!container || withDetail) loading = true;
		else refreshing = true;
		errorMsg = '';
		try {
			const tasks: Promise<unknown>[] = [loadCurrentMetrics(), loadHistory()];
			if (withDetail || !container) tasks.unshift(loadDetail());
			await Promise.all(tasks);
			history = normalizeHistory(history, currentMetrics);
		} catch (error: any) {
			errorMsg = error?.message || 'Could not load dashboard.';
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	function handleRangeChange(rangeKey: (typeof RANGE_OPTIONS)[number]['key']) {
		selectedRange = rangeKey;
		loadDashboard();
	}

	let envEntries = $derived(Object.entries(container?.custom_env ?? {}));
	let portMappings = $derived(container?.custom_ports ?? []);
	let historyLabels = $derived(
		history.map((row) =>
			new Date(row.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
		),
	);

	let cpuDatasets = $derived([
		{
			label: 'CPU',
			color: '#30d5c8',
			values: history.map((row) => row.cpu_usage),
			fill: true,
			format: 'percent' as const,
		},
	]);
	let memoryDatasets = $derived([
		{
			label: 'Memory',
			color: '#4fc3f7',
			values: history.map((row) => row.memory_percent),
			fill: true,
			format: 'percent' as const,
		},
	]);
	let networkDatasets = $derived([
		{
			label: 'RX',
			color: '#30d5c8',
			values: history.map((row) => row.network_rx),
			format: 'bytes' as const,
		},
		{
			label: 'TX',
			color: '#f59e0b',
			values: history.map((row) => row.network_tx),
			format: 'bytes' as const,
		},
	]);
	let diskDatasets = $derived([
		{
			label: 'Read',
			color: '#38bdf8',
			values: history.map((row) => row.disk_read),
			format: 'bytes' as const,
		},
		{
			label: 'Write',
			color: '#a78bfa',
			values: history.map((row) => row.disk_write),
			format: 'bytes' as const,
		},
	]);

	onMount(() => {
		loadDashboard({ withDetail: true });
		refreshTimer = setInterval(() => loadDashboard(), 15000);
		return () => {
			if (refreshTimer) clearInterval(refreshTimer);
		};
	});
</script>

<div class="page">
	<button class="back-link" onclick={() => goto(`${base}/user/containers`)}>Back to my containers</button>

	{#if loading}
		<div class="state-box">Loading dashboard...</div>
	{:else if errorMsg}
		<div class="state-box error">{errorMsg}</div>
	{:else if container}
		<section class="hero">
			<div class="hero-left">
				<div class="hero-title">
					<div>
						<p class="eyebrow">2D Monitoring Dashboard</p>
						<h1>{container.name}</h1>
					</div>
					<span class="status-pill" style="background: {statusTone(container.status)};">
						{statusLabel(container.status)}
					</span>
				</div>
				<p class="hero-subtitle">{container.selected_image || container.image}</p>
				<div class="hero-meta">
					<span>Host {container.agent_hostname ?? '-'}</span>
					<span>Template {container.template_name ?? '-'}</span>
					<span>Requested {formatDateTime(container.requested_at)}</span>
					<span>Last sample {formatDateTime(currentMetrics?.timestamp || container.last_seen)}</span>
				</div>
			</div>
			<div class="hero-actions">
				<button class="refresh-btn" onclick={() => loadDashboard({ withDetail: true })} disabled={refreshing}>
					{refreshing ? 'Refreshing...' : 'Refresh now'}
				</button>
			</div>
		</section>

		{#if container.status !== 'running'}
			<div class="banner">
				The container is currently <strong>{statusLabel(container.status)}</strong>. Live metrics may be missing or stale until it is running again.
			</div>
		{/if}

		<section class="stat-grid">
			<div class="stat-card">
				<span class="stat-label">CPU Usage</span>
				<strong>{formatPercent(currentMetrics?.cpu?.usage, 2)}</strong>
				<span class="stat-meta">Latest sample</span>
			</div>
			<div class="stat-card">
				<span class="stat-label">Memory Usage</span>
				<strong>{formatMemoryUsage(currentMetrics?.memory?.usage, currentMetrics?.memory?.limit)}</strong>
				<span class="stat-meta">{formatPercent(currentMetrics?.memory?.percent, 2)} in use</span>
			</div>
			<div class="stat-card">
				<span class="stat-label">Network I/O</span>
				<strong>{formatBytesValue(currentMetrics?.network?.rx)} / {formatBytesValue(currentMetrics?.network?.tx)}</strong>
				<span class="stat-meta">RX / TX cumulative</span>
			</div>
			<div class="stat-card">
				<span class="stat-label">Disk I/O</span>
				<strong>{formatBytesValue(currentMetrics?.disk?.read)} / {formatBytesValue(currentMetrics?.disk?.write)}</strong>
				<span class="stat-meta">Read / Write cumulative</span>
			</div>
		</section>

		<section class="panel">
			<div class="panel-header">
				<div>
					<h2>Time Series</h2>
					<p>Track the core container metrics you need for day to day Docker monitoring.</p>
				</div>
				<div class="range-tabs">
					{#each RANGE_OPTIONS as option}
						<button
							class="range-btn"
							class:active={selectedRange === option.key}
							onclick={() => handleRangeChange(option.key)}
						>{option.label}</button>
					{/each}
				</div>
			</div>

			<div class="chart-grid">
				<div class="chart-card">
					<div class="chart-head">
						<h3>CPU Usage</h3>
						<span>{formatPercent(currentMetrics?.cpu?.usage, 2)}</span>
					</div>
					<UserMetricChart labels={historyLabels} datasets={cpuDatasets} yFormat="percent" />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>Memory Usage</h3>
						<span>{formatPercent(currentMetrics?.memory?.percent, 2)}</span>
					</div>
					<UserMetricChart labels={historyLabels} datasets={memoryDatasets} yFormat="percent" />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>Network Traffic</h3>
						<span>{formatBytesValue(currentMetrics?.network?.rx)} / {formatBytesValue(currentMetrics?.network?.tx)}</span>
					</div>
					<UserMetricChart labels={historyLabels} datasets={networkDatasets} yFormat="bytes" />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>Disk Throughput</h3>
						<span>{formatBytesValue(currentMetrics?.disk?.read)} / {formatBytesValue(currentMetrics?.disk?.write)}</span>
					</div>
					<UserMetricChart labels={historyLabels} datasets={diskDatasets} yFormat="bytes" />
				</div>
			</div>
		</section>

		<section class="details-grid">
			<div class="panel">
				<div class="panel-header slim">
					<div>
						<h2>Runtime Details</h2>
						<p>Deployment metadata for the current monitored container.</p>
					</div>
				</div>
				<div class="info-grid">
					<div class="info-item">
						<span class="info-label">Container ID</span>
						<span class="info-value mono">{container.container_id}</span>
					</div>
					<div class="info-item">
						<span class="info-label">Request ID</span>
						<span class="info-value mono">{container.request_id ?? '-'}</span>
					</div>
					<div class="info-item">
						<span class="info-label">Request Status</span>
						<span class="info-value">{statusLabel(container.request_status)}</span>
					</div>
					<div class="info-item">
						<span class="info-label">Last Container Sync</span>
						<span class="info-value">{formatDateTime(container.last_seen)}</span>
					</div>
				</div>
				{#if container.review_note}
					<div class="note-box">
						<span class="info-label">Review Note</span>
						<p>{container.review_note}</p>
					</div>
				{/if}
			</div>

			<div class="panel">
				<div class="panel-header slim">
					<div>
						<h2>Config Snapshot</h2>
						<p>Port mappings and environment variables captured at request time.</p>
					</div>
				</div>
				<div class="config-split">
					<div class="config-card">
						<span class="config-title">Port Mapping</span>
						{#if portMappings.length > 0}
							<div class="tag-list">
								{#each portMappings as port}
									<span class="tag">{port.host ?? '-'} to {port.container ?? '-'} {port.protocol ?? 'tcp'}</span>
								{/each}
							</div>
						{:else}
							<p class="config-empty">No custom port mapping was recorded.</p>
						{/if}
					</div>
					<div class="config-card">
						<span class="config-title">Environment Variables</span>
						{#if envEntries.length > 0}
							<div class="env-list">
								{#each envEntries as [key, value]}
									<div class="env-row">
										<span>{key}</span>
										<span>{value}</span>
									</div>
								{/each}
							</div>
						{:else}
							<p class="config-empty">No extra environment variables were recorded.</p>
						{/if}
					</div>
				</div>
			</div>
		</section>
	{/if}
</div>

<style>
	.page {
		max-width: 1280px;
		margin: 0 auto;
		padding: 24px 32px 40px;
	}

	.back-link,
	.refresh-btn,
	.range-btn {
		border: none;
		font-family: inherit;
		cursor: pointer;
	}

	.back-link {
		padding: 0;
		background: transparent;
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 700;
		margin-bottom: 14px;
	}

	.back-link:hover {
		color: var(--accent);
	}

	.state-box,
	.banner {
		padding: 16px 18px;
		border-radius: 14px;
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		color: var(--text-secondary);
	}

	.state-box.error {
		color: #fecaca;
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(127, 29, 29, 0.18);
	}

	.hero {
		display: flex;
		justify-content: space-between;
		gap: 20px;
		padding: 24px 26px;
		border-radius: 20px;
		background:
			linear-gradient(140deg, rgba(48, 213, 200, 0.16), rgba(9, 75, 102, 0.18)),
			rgba(18, 23, 32, 0.98);
		border: 1px solid rgba(48, 213, 200, 0.18);
	}

	.hero-title {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}

	.eyebrow {
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 6px;
	}

	h1 {
		font-size: 32px;
		line-height: 1.1;
	}

	.hero-subtitle {
		margin-top: 8px;
		font-size: 14px;
		color: var(--text-secondary);
		word-break: break-all;
	}

	.hero-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 14px;
	}

	.hero-meta span {
		padding: 6px 10px;
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.52);
		border: 1px solid rgba(31, 41, 55, 0.8);
		font-size: 12px;
		color: var(--text-secondary);
	}

	.status-pill {
		padding: 5px 12px;
		border-radius: 999px;
		font-size: 12px;
		font-weight: 700;
		color: white;
	}

	.hero-actions {
		display: flex;
		align-items: flex-start;
	}

	.refresh-btn {
		padding: 10px 16px;
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 700;
	}

	.banner {
		margin-top: 14px;
	}

	.stat-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 14px;
		margin-top: 18px;
	}

	.stat-card,
	.panel,
	.chart-card,
	.config-card {
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
	}

	.stat-card {
		padding: 18px 20px;
		border-radius: 16px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.stat-label {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.stat-card strong {
		font-size: 22px;
		color: var(--text-primary);
		word-break: break-word;
	}

	.stat-meta {
		font-size: 11px;
		color: var(--text-muted);
	}

	.panel {
		border-radius: 18px;
		padding: 20px;
		margin-top: 18px;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 18px;
		margin-bottom: 18px;
	}

	.panel-header.slim {
		margin-bottom: 16px;
	}

	h2 {
		font-size: 20px;
		margin-bottom: 4px;
	}

	h2 + p,
	.panel-header p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.range-tabs {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.range-btn {
		padding: 8px 12px;
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.8);
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 700;
	}

	.range-btn.active {
		background: rgba(48, 213, 200, 0.18);
		color: var(--accent);
	}

	.chart-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
	}

	.chart-card {
		border-radius: 16px;
		padding: 16px;
	}

	.chart-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		margin-bottom: 12px;
	}

	.chart-head h3 {
		font-size: 15px;
	}

	.chart-head span {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.details-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
		gap: 18px;
	}

	.info-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}

	.info-item,
	.note-box,
	.config-card {
		padding: 14px;
		border-radius: 14px;
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
	}

	.info-label,
	.config-title {
		display: block;
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 4px;
	}

	.info-value {
		font-size: 12px;
		color: var(--text-primary);
		word-break: break-word;
	}

	.info-value.mono {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.note-box {
		margin-top: 12px;
	}

	.note-box p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.config-split {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.tag-list {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.tag {
		padding: 6px 10px;
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.12);
		color: var(--accent);
		font-size: 11px;
		font-weight: 700;
	}

	.env-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.env-row {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		font-size: 12px;
		color: var(--text-primary);
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(31, 41, 55, 0.7);
	}

	.env-row:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.config-empty {
		font-size: 12px;
		color: var(--text-secondary);
	}

	@media (max-width: 980px) {
		.page {
			padding: 20px 16px 28px;
		}

		.hero,
		.panel-header,
		.chart-head,
		.env-row {
			flex-direction: column;
			align-items: stretch;
		}

		.stat-grid,
		.chart-grid,
		.details-grid,
		.info-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
