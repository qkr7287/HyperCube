<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { base } from '$app/paths';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import StatusTabs from '$lib/components/StatusTabs.svelte';

	interface Agent {
		id: string;
		hostname: string;
		ip_address: string;
		status: 'pending' | 'approved' | 'rejected';
		registered_at: string;
		approved_at: string | null;
		container_count: number;
	}

	interface AgentMetrics {
		cpu: { usage: number; cores?: number } | null;
		memory: { usage: number; total?: number; used?: number } | null;
		disk: { usage: number } | null;
		timestamp: string | null;
	}

	// Auth
	let username = '';
	let password = '';
	let accessToken = '';
	let loginError = '';
	let isLoggedIn = false;

	// Data
	let agents: Agent[] = [];
	let metricsMap: Record<string, AgentMetrics | null> = {};
	let loading = false;
	let error = '';
	let actionLoading = '';

	// Tabs + Polling
	let activeTab = 'all';
	let pollInterval: ReturnType<typeof setInterval> | null = null;
	let previousPendingCount = 0;
	let newPendingAlert = false;

	// Confirm dialog
	let dialogOpen = false;
	let dialogTitle = '';
	let dialogMessage = '';
	let dialogVariant: 'primary' | 'danger' = 'primary';
	let dialogConfirmLabel = 'Confirm';
	let dialogAction: () => void = () => {};

	// Reactive
	$: filteredAgents = activeTab === 'all'
		? agents
		: agents.filter(a => a.status === activeTab);
	$: pendingCount = agents.filter(a => a.status === 'pending').length;
	$: approvedCount = agents.filter(a => a.status === 'approved').length;
	$: rejectedCount = agents.filter(a => a.status === 'rejected').length;
	$: tabs = [
		{ value: 'all', label: 'All', count: agents.length },
		{ value: 'pending', label: 'Pending', count: pendingCount },
		{ value: 'approved', label: 'Approved', count: approvedCount },
		{ value: 'rejected', label: 'Rejected', count: rejectedCount },
	];

	// ----- Auth -----

	async function login() {
		loginError = '';
		try {
			const res = await fetch(`${base}/api/auth/token/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password })
			});
			const json = await res.json();
			if (!res.ok) {
				loginError = json.error?.detail || json.detail || 'Login failed';
				return;
			}
			accessToken = json.data?.access || json.access;
			isLoggedIn = true;
			await loadAgents();
			startPolling();
		} catch {
			loginError = 'Connection failed';
		}
	}

	function logout() {
		stopPolling();
		accessToken = '';
		isLoggedIn = false;
		agents = [];
		metricsMap = {};
	}

	// ----- Data Loading -----

	async function loadAgents() {
		loading = true;
		error = '';
		try {
			const res = await fetch(`${base}/api/agents/`, {
				headers: { 'Authorization': `Bearer ${accessToken}` }
			});
			if (res.status === 401) { logout(); return; }
			const json = await res.json();
			if (!res.ok) {
				error = json.error?.detail || 'Failed to load agents';
				return;
			}
			const data = json.data;
			agents = data.results ?? data;
			await loadMetrics();
		} catch {
			error = 'Connection failed';
		} finally {
			loading = false;
		}
	}

	async function loadMetrics() {
		const approved = agents.filter(a => a.status === 'approved');
		if (approved.length === 0) { metricsMap = {}; return; }

		const results = await Promise.allSettled(
			approved.map(async (agent) => {
				const res = await fetch(`${base}/api/agents/${agent.id}/latest-metrics/`, {
					headers: { 'Authorization': `Bearer ${accessToken}` }
				});
				if (!res.ok) return { id: agent.id, metrics: null };
				const json = await res.json();
				return { id: agent.id, metrics: json.data as AgentMetrics };
			})
		);

		const newMap: Record<string, AgentMetrics | null> = {};
		for (const r of results) {
			if (r.status === 'fulfilled' && r.value) {
				newMap[r.value.id] = r.value.metrics;
			}
		}
		metricsMap = newMap;
	}

	// ----- Actions -----

	function confirmApprove(agent: Agent) {
		dialogTitle = 'Approve Agent';
		dialogMessage = `Approve "${agent.hostname}" (${agent.ip_address})? This will generate a WebSocket token.`;
		dialogConfirmLabel = 'Approve';
		dialogVariant = 'primary';
		dialogAction = () => manageAgent(agent.id, 'approve');
		dialogOpen = true;
	}

	function confirmReject(agent: Agent) {
		dialogTitle = 'Reject Agent';
		dialogMessage = `Reject "${agent.hostname}" (${agent.ip_address})? The agent will not be able to connect.`;
		dialogConfirmLabel = 'Reject';
		dialogVariant = 'danger';
		dialogAction = () => manageAgent(agent.id, 'reject');
		dialogOpen = true;
	}

	function confirmDelete(agent: Agent) {
		dialogTitle = 'Delete Agent';
		dialogMessage = `Permanently delete "${agent.hostname}" (${agent.ip_address})? All associated container data and metrics will be lost.`;
		dialogConfirmLabel = 'Delete';
		dialogVariant = 'danger';
		dialogAction = () => deleteAgent(agent.id);
		dialogOpen = true;
	}

	function closeDialog() {
		dialogOpen = false;
	}

	async function manageAgent(agentId: string, action: 'approve' | 'reject') {
		actionLoading = agentId;
		try {
			const res = await fetch(`${base}/api/agents/${agentId}/manage-status/`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${accessToken}`
				},
				body: JSON.stringify({ action })
			});
			if (res.ok) {
				await loadAgents();
			}
		} catch {
			error = 'Action failed';
		} finally {
			actionLoading = '';
		}
	}

	async function deleteAgent(agentId: string) {
		actionLoading = agentId;
		try {
			const res = await fetch(`${base}/api/agents/${agentId}/`, {
				method: 'DELETE',
				headers: { 'Authorization': `Bearer ${accessToken}` }
			});
			if (res.ok || res.status === 204) {
				await loadAgents();
			}
		} catch {
			error = 'Delete failed';
		} finally {
			actionLoading = '';
		}
	}

	// ----- Polling (WBS 2.3.4) -----

	function startPolling() {
		stopPolling();
		previousPendingCount = agents.filter(a => a.status === 'pending').length;
		pollInterval = setInterval(async () => {
			const prevCount = agents.filter(a => a.status === 'pending').length;
			await loadAgents();
			const newCount = agents.filter(a => a.status === 'pending').length;
			if (newCount > prevCount) {
				newPendingAlert = true;
				activeTab = 'pending';
			}
		}, 10000);
	}

	function stopPolling() {
		if (pollInterval) {
			clearInterval(pollInterval);
			pollInterval = null;
		}
	}

	function handleTabChange(value: string) {
		activeTab = value;
		if (value === 'pending') newPendingAlert = false;
	}

	// ----- Helpers -----

	function formatDate(dateStr: string | null) {
		if (!dateStr) return '-';
		return new Date(dateStr).toLocaleString('ko-KR', {
			year: 'numeric', month: '2-digit', day: '2-digit',
			hour: '2-digit', minute: '2-digit'
		});
	}

	function formatMetric(value: number | undefined | null): string {
		if (value == null) return '--';
		return `${value.toFixed(1)}%`;
	}

	onDestroy(() => stopPolling());
</script>

<div class="page">
	<header class="page-header">
		<h1>Server Management</h1>
		{#if isLoggedIn}
			<button class="btn btn-outline" onclick={logout}>Logout</button>
		{/if}
	</header>

	{#if !isLoggedIn}
		<div class="login-card">
			<h2>Admin Login</h2>
			<form onsubmit={(e) => { e.preventDefault(); login(); }}>
				<div class="field">
					<label for="username">Username</label>
					<input id="username" type="text" bind:value={username} placeholder="admin" />
				</div>
				<div class="field">
					<label for="password">Password</label>
					<input id="password" type="password" bind:value={password} />
				</div>
				{#if loginError}
					<p class="error-text">{loginError}</p>
				{/if}
				<button class="btn btn-primary" type="submit">Login</button>
			</form>
		</div>
	{:else}
		<div class="toolbar">
			<StatusTabs {tabs} active={activeTab} onchange={handleTabChange} />
			<div class="toolbar-right">
				{#if newPendingAlert}
					<span class="alert-badge">NEW</span>
				{/if}
				<button class="btn btn-outline" onclick={loadAgents} disabled={loading}>
					{loading ? 'Loading...' : 'Refresh'}
				</button>
			</div>
		</div>

		{#if error}
			<p class="error-text">{error}</p>
		{/if}

		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th>Hostname</th>
						<th>IP Address</th>
						<th>Status</th>
						<th>Containers</th>
						<th>CPU</th>
						<th>Memory</th>
						<th>Disk</th>
						<th>Registered</th>
						<th>Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredAgents as agent (agent.id)}
						{@const metrics = metricsMap[agent.id]}
						<tr>
							<td class="hostname">{agent.hostname}</td>
							<td class="monospace">{agent.ip_address}</td>
							<td>
								<span class="badge badge-{agent.status}">{agent.status}</span>
							</td>
							<td>{agent.container_count}</td>
							<td class="metric">{agent.status === 'approved' ? formatMetric(metrics?.cpu?.usage) : '--'}</td>
							<td class="metric">{agent.status === 'approved' ? formatMetric(metrics?.memory?.usage) : '--'}</td>
							<td class="metric">{agent.status === 'approved' ? formatMetric(metrics?.disk?.usage) : '--'}</td>
							<td class="date">{formatDate(agent.registered_at)}</td>
							<td class="actions">
								{#if agent.status === 'pending'}
									<button
										class="btn btn-approve btn-sm"
										onclick={() => confirmApprove(agent)}
										disabled={actionLoading === agent.id}
									>
										Approve
									</button>
									<button
										class="btn btn-reject btn-sm"
										onclick={() => confirmReject(agent)}
										disabled={actionLoading === agent.id}
									>
										Reject
									</button>
								{:else}
									<button
										class="btn btn-delete btn-sm"
										onclick={() => confirmDelete(agent)}
										disabled={actionLoading === agent.id}
									>
										Delete
									</button>
								{/if}
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="9" class="empty">No agents in this category</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<ConfirmDialog
	open={dialogOpen}
	title={dialogTitle}
	message={dialogMessage}
	confirmLabel={dialogConfirmLabel}
	confirmVariant={dialogVariant}
	onconfirm={() => { dialogAction(); closeDialog(); }}
	oncancel={closeDialog}
/>

<style>
	.page {
		max-width: 1400px;
		margin: 0 auto;
		padding: 40px 24px;
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 28px;
	}

	.page-header h1 {
		font-size: 22px;
		font-weight: 700;
		color: var(--text-primary);
	}

	/* Login */
	.login-card {
		max-width: 400px;
		margin: 80px auto;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 32px;
	}

	.login-card h2 {
		font-size: 18px;
		color: var(--text-primary);
		margin-bottom: 24px;
	}

	.field {
		margin-bottom: 16px;
	}

	.field label {
		display: block;
		font-size: 13px;
		color: var(--text-secondary);
		margin-bottom: 6px;
	}

	.field input {
		width: 100%;
		padding: 10px 14px;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text-primary);
		font-size: 14px;
		outline: none;
		transition: border-color 0.2s;
		box-sizing: border-box;
	}

	.field input:focus {
		border-color: var(--accent);
	}

	/* Toolbar */
	.toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 20px;
		gap: 16px;
		flex-wrap: wrap;
	}

	.toolbar-right {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.alert-badge {
		font-size: 11px;
		font-weight: 700;
		padding: 2px 8px;
		border-radius: 9999px;
		background: var(--error);
		color: #fff;
		animation: pulse 1.5s infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}

	/* Buttons */
	.btn {
		padding: 8px 16px;
		border-radius: 8px;
		font-size: 13px;
		font-weight: 600;
		cursor: pointer;
		border: 1px solid transparent;
		transition: all 0.15s;
	}

	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-sm {
		padding: 5px 12px;
		font-size: 12px;
	}

	.btn-primary {
		width: 100%;
		margin-top: 8px;
		background: var(--accent);
		color: var(--bg-base);
		border: none;
	}

	.btn-primary:hover:not(:disabled) {
		opacity: 0.9;
	}

	.btn-outline {
		background: transparent;
		border: 1px solid var(--border);
		color: var(--text-primary);
	}

	.btn-outline:hover:not(:disabled) {
		border-color: var(--accent);
		color: var(--accent);
	}

	.btn-approve {
		background: rgba(34, 197, 94, 0.12);
		color: #22c55e;
		border: 1px solid rgba(34, 197, 94, 0.25);
	}

	.btn-approve:hover:not(:disabled) {
		background: rgba(34, 197, 94, 0.22);
	}

	.btn-reject {
		background: rgba(239, 68, 68, 0.12);
		color: #ef4444;
		border: 1px solid rgba(239, 68, 68, 0.25);
	}

	.btn-reject:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.22);
	}

	.btn-delete {
		background: rgba(239, 68, 68, 0.08);
		color: #f87171;
		border: 1px solid rgba(239, 68, 68, 0.2);
	}

	.btn-delete:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.18);
		color: #ef4444;
	}

	/* Table */
	.table-wrap {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 12px;
		overflow-x: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		min-width: 900px;
	}

	th {
		text-align: left;
		padding: 13px 16px;
		font-size: 11px;
		font-weight: 700;
		color: var(--text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.5px;
		border-bottom: 1px solid var(--border);
		background: var(--bg-tab);
		white-space: nowrap;
	}

	td {
		padding: 13px 16px;
		font-size: 13px;
		color: var(--text-primary);
		border-bottom: 1px solid rgba(31, 41, 55, 0.4);
		white-space: nowrap;
	}

	tr:last-child td {
		border-bottom: none;
	}

	tr:hover td {
		background: rgba(255, 255, 255, 0.02);
	}

	.hostname {
		font-weight: 600;
		color: var(--accent);
	}

	.monospace {
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		font-size: 12px;
	}

	.metric {
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		font-size: 12px;
		color: var(--text-secondary);
	}

	.date {
		font-size: 12px;
		color: var(--text-muted);
	}

	.actions {
		display: flex;
		gap: 6px;
	}

	.empty {
		text-align: center;
		padding: 48px 16px !important;
		color: var(--text-muted);
		font-size: 14px;
	}

	/* Badge */
	.badge {
		display: inline-block;
		padding: 3px 10px;
		border-radius: 9999px;
		font-size: 11px;
		font-weight: 700;
		text-transform: capitalize;
	}

	.badge-pending {
		color: #fbbf24;
		background: rgba(251, 191, 36, 0.12);
	}

	.badge-approved {
		color: #22c55e;
		background: rgba(34, 197, 94, 0.12);
	}

	.badge-rejected {
		color: #ef4444;
		background: rgba(239, 68, 68, 0.12);
	}

	.error-text {
		color: var(--error);
		font-size: 13px;
		margin-bottom: 16px;
	}
</style>
