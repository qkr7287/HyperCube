<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import NewRequestModal from '$lib/components/NewRequestModal.svelte';
	import {
		formatDateTime,
		formatRelativeTime,
		statusLabel,
		statusTone,
	} from '$lib/utils/container-dashboard';

	type RequestRow = {
		id: string;
		action: string;
		status: string;
		template_name?: string | null;
		target_agent_hostname?: string | null;
		target_container?: string | null;
		target_container_name?: string | null;
		custom_name?: string;
		progress_message?: string;
		progress_percent?: number | null;
		review_note?: string;
		created_at: string;
	};

	let requests = $state<RequestRow[]>([]);
	let loading = $state(false);
	let newModalOpen = $state(false);

	const ACTIVE_STATUSES = new Set(['pending', 'approved', 'deploying']);
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
			const res = await fetch(`${base}/api/requests/?page_size=100&ordering=-created_at`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (res.ok) {
				const json = await res.json();
				requests = json.data?.results ?? [];
			}
		} catch {
			// ignore
		} finally {
			loading = false;
			syncPolling();
		}
	}

	function syncPolling() {
		const hasActive = requests.some((request) => ACTIVE_STATUSES.has(request.status));
		if (hasActive && !pollTimer) {
			pollTimer = setInterval(load, 2000);
		} else if (!hasActive && pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	function openDashboard(request: RequestRow) {
		if (!request.target_container) return;
		goto(`${base}/user/containers/${request.target_container}`);
	}

	let totalRequests = $derived(requests.length);
	let activeRequests = $derived(requests.filter((request) => ACTIVE_STATUSES.has(request.status)).length);
	let deployedRequests = $derived(requests.filter((request) => request.status === 'deployed').length);

	onMount(() => {
		load();
		return () => {
			if (pollTimer) clearInterval(pollTimer);
		};
	});
</script>

<div class="page">
	<section class="hero">
		<div>
			<p class="eyebrow">User Workspace</p>
			<h1>Container Requests</h1>
			<p class="subtitle">Track approvals, deployment progress, and jump into the monitoring dashboard when a container is ready.</p>
		</div>
		<button class="new-btn" onclick={() => (newModalOpen = true)}>New Request</button>
	</section>

	<section class="summary-grid">
		<div class="summary-card">
			<span class="summary-label">Total Requests</span>
			<strong>{totalRequests}</strong>
			<span class="summary-meta">All submitted items</span>
		</div>
		<div class="summary-card">
			<span class="summary-label">Active Flow</span>
			<strong>{activeRequests}</strong>
			<span class="summary-meta">Pending, approved, or deploying</span>
		</div>
		<div class="summary-card">
			<span class="summary-label">Ready To Monitor</span>
			<strong>{deployedRequests}</strong>
			<span class="summary-meta">Deployment completed</span>
		</div>
	</section>

	{#if !loading && requests.length === 0}
		<div class="empty">
			<div class="empty-badge">No Requests Yet</div>
			<div class="empty-title">You have not requested a container yet</div>
			<p class="empty-text">Create your first request to start the approval and deployment flow.</p>
			<button class="empty-btn" onclick={() => (newModalOpen = true)}>Create First Request</button>
		</div>
	{:else}
		<div class="cards">
			{#each requests as request (request.id)}
				<div class="request-card">
					<div class="card-main">
						<div class="card-heading">
							<div>
								<div class="card-name">{request.custom_name || request.target_container_name || 'Untitled Container'}</div>
								<div class="card-meta">
									<span>{request.action === 'create' ? 'Create' : 'Delete'}</span>
									<span>{request.template_name ?? 'No Template'}</span>
									<span>{request.target_agent_hostname ?? 'No Host'}</span>
								</div>
							</div>
							<div class="card-status">
								<span class="status-pill" style="background: {statusTone(request.status)};">{statusLabel(request.status)}</span>
								<span class="card-time">{formatRelativeTime(request.created_at)}</span>
							</div>
						</div>

						{#if request.progress_message}
							<div class="progress-block">
								<div class="progress-track">
									<div class="progress-fill" style="width: {request.progress_percent ?? 0}%"></div>
								</div>
								<div class="progress-text">
									<span>{request.progress_message}</span>
									<span>{request.progress_percent != null ? `${request.progress_percent}%` : formatDateTime(request.created_at)}</span>
								</div>
							</div>
						{/if}

						{#if request.review_note}
							<div class="review-note">
								<span class="review-label">Review Note</span>
								<p>{request.review_note}</p>
							</div>
						{/if}
					</div>

					<div class="card-actions">
						<span class="requested-at">{formatDateTime(request.created_at)}</span>
						{#if request.status === 'deployed' && request.target_container}
							<button class="monitor-btn" onclick={() => openDashboard(request)}>Open Monitoring</button>
						{:else if request.status === 'deployed'}
							<span class="pending-link">Waiting for container sync</span>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<NewRequestModal
	open={newModalOpen}
	onClose={() => (newModalOpen = false)}
	onSubmitted={load}
/>

<style>
	.page {
		padding: 28px 32px 36px;
		max-width: 1120px;
		margin: 0 auto;
	}

	.hero {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 24px;
		padding: 26px 28px;
		margin-bottom: 20px;
		background:
			linear-gradient(135deg, rgba(48, 213, 200, 0.18), rgba(9, 75, 102, 0.22)),
			var(--bg-card);
		border: 1px solid rgba(48, 213, 200, 0.18);
		border-radius: 18px;
	}

	.eyebrow {
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 8px;
	}

	h1 {
		font-size: 28px;
		line-height: 1.1;
		margin-bottom: 8px;
	}

	.subtitle {
		font-size: 13px;
		color: var(--text-secondary);
		max-width: 620px;
	}

	.new-btn,
	.empty-btn,
	.monitor-btn {
		border: none;
		border-radius: 10px;
		padding: 11px 18px;
		font-size: 13px;
		font-weight: 700;
		cursor: pointer;
		background: var(--accent);
		color: var(--accent-dark);
	}

	.new-btn:hover,
		.empty-btn:hover,
		.monitor-btn:hover {
		filter: brightness(1.06);
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 14px;
		margin-bottom: 22px;
	}

	.summary-card {
		padding: 18px 20px;
		background: rgba(18, 23, 32, 0.92);
		border: 1px solid var(--border);
		border-radius: 14px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.summary-label {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.summary-card strong {
		font-size: 28px;
		color: var(--text-primary);
	}

	.summary-meta {
		font-size: 11px;
		color: var(--text-muted);
	}

	.empty {
		padding: 60px 24px;
		text-align: center;
		background: rgba(18, 23, 32, 0.92);
		border: 1px solid var(--border);
		border-radius: 18px;
	}

	.empty-badge {
		display: inline-flex;
		padding: 6px 10px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 700;
		color: var(--accent);
		background: rgba(48, 213, 200, 0.12);
		margin-bottom: 14px;
	}

	.empty-title {
		font-size: 18px;
		font-weight: 700;
		margin-bottom: 6px;
	}

	.empty-text {
		font-size: 13px;
		color: var(--text-secondary);
		margin-bottom: 20px;
	}

	.cards {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.request-card {
		display: flex;
		justify-content: space-between;
		gap: 18px;
		padding: 18px 20px;
		background: rgba(18, 23, 32, 0.94);
		border: 1px solid var(--border);
		border-radius: 16px;
	}

	.card-main {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.card-heading {
		display: flex;
		justify-content: space-between;
		gap: 12px;
	}

	.card-name {
		font-size: 16px;
		font-weight: 700;
		color: var(--text-primary);
	}

	.card-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 4px;
		font-size: 11px;
		color: var(--text-secondary);
	}

	.card-meta span {
		padding: 4px 8px;
		background: rgba(21, 28, 39, 0.95);
		border: 1px solid rgba(31, 41, 55, 0.9);
		border-radius: 999px;
	}

	.card-status {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 6px;
	}

	.status-pill {
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 700;
		color: white;
	}

	.card-time {
		font-size: 11px;
		color: var(--text-muted);
	}

	.progress-block {
		padding: 12px;
		background: rgba(13, 17, 23, 0.88);
		border: 1px solid rgba(31, 41, 55, 0.92);
		border-radius: 12px;
	}

	.progress-track {
		height: 7px;
		background: rgba(30, 41, 59, 0.85);
		border-radius: 999px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--accent), #6be6dc);
		transition: width 0.3s ease;
	}

	.progress-text {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		margin-top: 8px;
		font-size: 11px;
		color: var(--text-secondary);
	}

	.review-note {
		padding: 12px;
		background: rgba(21, 28, 39, 0.92);
		border-radius: 12px;
	}

	.review-label {
		display: block;
		font-size: 11px;
		font-weight: 700;
		color: var(--text-muted);
		margin-bottom: 4px;
	}

	.review-note p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.card-actions {
		min-width: 168px;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		justify-content: space-between;
		gap: 12px;
	}

	.requested-at {
		font-size: 11px;
		color: var(--text-muted);
		text-align: right;
	}

	.pending-link {
		font-size: 12px;
		color: var(--text-secondary);
	}

	@media (max-width: 840px) {
		.page {
			padding: 20px 16px 28px;
		}

		.hero,
		.request-card,
		.card-heading {
			flex-direction: column;
			align-items: stretch;
		}

		.summary-grid {
			grid-template-columns: 1fr;
		}

		.card-status,
		.card-actions {
			align-items: flex-start;
		}
	}
</style>
