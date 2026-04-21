<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import {
		formatDateTime,
		formatRelativeTime,
		statusLabel,
		statusTone,
	} from '$lib/utils/container-dashboard';

	type ContainerRow = {
		container_id: string;
		name: string;
		image: string;
		status: string;
		last_seen: string;
		agent_hostname?: string;
		template_name?: string | null;
		requested_at?: string | null;
		request_status?: string | null;
	};

	let loading = $state(false);
	let containers = $state<ContainerRow[]>([]);
	let search = $state('');
	let pollTimer: ReturnType<typeof setInterval> | null = null;

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function load() {
		const t = token();
		if (!t) return;
		loading = true;
		try {
			const res = await fetch(`${base}/api/my-containers/?page_size=100&ordering=-last_seen`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (res.ok) {
				const json = await res.json();
				containers = json.data?.results ?? [];
			}
		} catch {
			// ignore
		} finally {
			loading = false;
		}
	}

	function openContainer(containerId: string) {
		goto(`${base}/user/containers/${containerId}`);
	}

	let filteredContainers = $derived(
		containers.filter((container) => {
			const keyword = search.trim().toLowerCase();
			if (!keyword) return true;
			return [
				container.name,
				container.image,
				container.agent_hostname,
				container.template_name,
			].some((value) => String(value ?? '').toLowerCase().includes(keyword));
		}),
	);

	let runningCount = $derived(containers.filter((container) => container.status === 'running').length);
	let warningCount = $derived(containers.filter((container) => ['paused', 'restarting'].includes(container.status)).length);
	let totalCount = $derived(containers.length);

	onMount(() => {
		load();
		pollTimer = setInterval(load, 15000);
		return () => {
			if (pollTimer) clearInterval(pollTimer);
		};
	});
</script>

<div class="page">
	<section class="page-header">
		<div>
			<p class="eyebrow">Container Fleet</p>
			<h1>My Containers</h1>
			<p class="subtitle">Only containers requested by the current user appear here. Open any card to see the 2D monitoring dashboard.</p>
		</div>
		<button class="refresh-btn" onclick={load} disabled={loading}>
			{loading ? 'Refreshing...' : 'Refresh'}
		</button>
	</section>

	<section class="toolbar">
		<div class="search-shell">
			<input bind:value={search} type="text" placeholder="Search by name, image, or host" />
		</div>
		<div class="summary">
			<span><strong>{totalCount}</strong> total</span>
			<span><strong>{runningCount}</strong> running</span>
			<span><strong>{warningCount}</strong> attention</span>
		</div>
	</section>

	{#if !loading && filteredContainers.length === 0}
		<div class="empty">
			<div class="empty-title">No containers to show</div>
			<p class="empty-text">Once a request is deployed, the container will appear here automatically.</p>
		</div>
	{:else}
		<div class="grid">
			{#each filteredContainers as container (container.container_id)}
				<button class="container-card" onclick={() => openContainer(container.container_id)}>
					<div class="card-top">
						<div>
							<div class="name-row">
								<h2>{container.name}</h2>
								<span class="status-pill" style="background: {statusTone(container.status)};">
									{statusLabel(container.status)}
								</span>
							</div>
							<p class="image">{container.image}</p>
						</div>
						<span class="last-seen">{formatRelativeTime(container.last_seen)}</span>
					</div>

					<div class="meta-grid">
						<div class="meta-item">
							<span class="meta-label">Host</span>
							<span class="meta-value">{container.agent_hostname ?? '-'}</span>
						</div>
						<div class="meta-item">
							<span class="meta-label">Template</span>
							<span class="meta-value">{container.template_name ?? '-'}</span>
						</div>
						<div class="meta-item">
							<span class="meta-label">Requested At</span>
							<span class="meta-value">{formatDateTime(container.requested_at)}</span>
						</div>
						<div class="meta-item">
							<span class="meta-label">Last Sync</span>
							<span class="meta-value">{formatDateTime(container.last_seen)}</span>
						</div>
					</div>

					<div class="card-footer">
						<span class="request-status">Request: {statusLabel(container.request_status)}</span>
						<span class="open-link">Open dashboard</span>
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.page {
		max-width: 1180px;
		margin: 0 auto;
		padding: 28px 32px 36px;
	}

	.page-header,
	.toolbar {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 18px;
	}

	.page-header {
		margin-bottom: 18px;
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
		font-size: 30px;
		margin-bottom: 8px;
	}

	.subtitle {
		font-size: 13px;
		color: var(--text-secondary);
	}

	.refresh-btn {
		padding: 10px 16px;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: var(--bg-card);
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
	}

	.toolbar {
		margin-bottom: 22px;
	}

	.search-shell {
		flex: 1;
		max-width: 420px;
		padding: 12px 14px;
		border-radius: 12px;
		border: 1px solid var(--border);
		background: rgba(18, 23, 32, 0.94);
	}

	.search-shell input {
		width: 100%;
		border: none;
		outline: none;
		background: transparent;
		color: var(--text-primary);
		font-size: 13px;
	}

	.search-shell input::placeholder {
		color: var(--text-muted);
	}

	.summary {
		display: flex;
		gap: 14px;
		flex-wrap: wrap;
		font-size: 12px;
		color: var(--text-secondary);
	}

	.summary strong {
		color: var(--text-primary);
		font-size: 16px;
		margin-right: 4px;
	}

	.empty {
		padding: 54px 20px;
		text-align: center;
		background: rgba(18, 23, 32, 0.94);
		border: 1px solid var(--border);
		border-radius: 18px;
	}

	.empty-title {
		font-size: 18px;
		font-weight: 700;
		margin-bottom: 6px;
	}

	.empty-text {
		font-size: 13px;
		color: var(--text-secondary);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
	}

	.container-card {
		padding: 20px;
		text-align: left;
		background:
			linear-gradient(180deg, rgba(48, 213, 200, 0.06), transparent 28%),
			rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		border-radius: 18px;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: 18px;
		transition: transform 0.14s ease, border-color 0.14s ease;
	}

	.container-card:hover {
		transform: translateY(-2px);
		border-color: rgba(48, 213, 200, 0.4);
	}

	.card-top {
		display: flex;
		justify-content: space-between;
		gap: 12px;
	}

	.name-row {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	h2 {
		font-size: 18px;
		color: var(--text-primary);
	}

	.status-pill {
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 700;
		color: white;
	}

	.image {
		margin-top: 6px;
		font-size: 12px;
		color: var(--text-secondary);
		word-break: break-all;
	}

	.last-seen {
		font-size: 11px;
		color: var(--text-muted);
		white-space: nowrap;
	}

	.meta-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}

	.meta-item {
		padding: 12px;
		background: rgba(13, 17, 23, 0.8);
		border: 1px solid rgba(31, 41, 55, 0.86);
		border-radius: 12px;
	}

	.meta-label {
		display: block;
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 4px;
	}

	.meta-value {
		font-size: 12px;
		color: var(--text-primary);
	}

	.card-footer {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		align-items: center;
		font-size: 12px;
	}

	.request-status {
		color: var(--text-secondary);
	}

	.open-link {
		color: var(--accent);
		font-weight: 700;
	}

	@media (max-width: 900px) {
		.page {
			padding: 20px 16px 28px;
		}

		.page-header,
		.toolbar,
		.card-top,
		.card-footer {
			flex-direction: column;
			align-items: stretch;
		}

		.grid,
		.meta-grid {
			grid-template-columns: 1fr;
		}

		.last-seen {
			white-space: normal;
		}
	}
</style>
