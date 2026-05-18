<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import {
		connectGlobal,
		disconnectGlobal,
		seedActiveAgents,
		seedStatusEvents,
		seedStatusEventsFromBackend,
	} from '$lib/stores/global-events';
	import AdminHeader from '$lib/components/AdminHeader.svelte';
	import StatusToasts from '$lib/components/StatusToasts.svelte';

	let { children } = $props();

	let ready = $state(false);
	let username = $state('');
	let totalAgents = $state(0);

	function decodeRole(token: string): string | null {
		try {
			const payload = JSON.parse(atob(token.split('.')[1]));
			return payload.role ?? null;
		} catch {
			return null;
		}
	}

	function decodeUsername(token: string): string {
		try {
			const payload = JSON.parse(atob(token.split('.')[1]));
			return payload.username ?? '';
		} catch {
			return '';
		}
	}

	function doLogout() {
		if (browser) {
			localStorage.removeItem('hc_access_token');
			localStorage.removeItem('hc_selected_server');
		}
		disconnectGlobal();
		goto(`${base}/`);
	}

	async function loadAgentCount(token: string) {
		try {
			const res = await fetch(`${base}/api/agents/?status=approved&page_size=200`, {
				headers: { Authorization: `Bearer ${token}` },
			});
			if (res.ok) {
				const json = await res.json();
				totalAgents = json.data?.count ?? 0;
				const agents = json.data?.results ?? [];
				seedActiveAgents(agents.filter((agent: any) => agent.is_active).map((agent: any) => agent.id));
				// offline 인 agent 들을 synthetic 이벤트로 seed → 페이지 첫 진입 때도
				// "최근 상태 변화" 가 비어있지 않고 현재 offline 상태 reflects.
				seedStatusEvents(agents);
			}
		} catch {
			/* ignore */
		}
		// Persisted transition log overrides the synthetic seed when present.
		try {
			const res = await fetch(`${base}/api/agents/status-events/?limit=20`, {
				headers: { Authorization: `Bearer ${token}` },
			});
			if (res.ok) {
				const json = await res.json();
				const events = json.data ?? json.results ?? json ?? [];
				if (Array.isArray(events) && events.length > 0) {
					seedStatusEventsFromBackend(events);
				}
			}
		} catch {
			/* ignore */
		}
	}

	onMount(() => {
		if (!browser) return;
		const token = localStorage.getItem('hc_access_token');
		if (!token) {
			goto(`${base}/`);
			return;
		}
		const role = decodeRole(token);
		if (role !== 'admin') {
			goto(`${base}/`);
			return;
		}
		username = decodeUsername(token);
		connectGlobal(token);
		loadAgentCount(token);
		ready = true;
	});
</script>

{#if ready}
	<div class="admin-shell">
		<AdminHeader {totalAgents} {username} onLogout={doLogout} />
		<main class="admin-body">
			{@render children()}
		</main>
	</div>
	<StatusToasts />
{/if}

<style>
	.admin-shell {
		height: 100vh;
		display: flex;
		flex-direction: column;
		background: var(--bg-base);
	}
	.admin-body {
		flex: 1;
		overflow-y: auto;
	}

	/* Canonical admin styles — applied to every panel/page under
	   /admin via :global() so the catalog/approvals tabs look like one
	   page even though they render different components underneath. */

	.admin-body :global(.page) {
		padding: 28px 32px;
	}
	.admin-body :global(.page-header) {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 20px;
		flex-wrap: wrap;
		margin-bottom: 20px;
	}
	.admin-body :global(.page-header h1) {
		margin: 0 0 6px;
		font-size: 20px;
		font-weight: 800;
		color: var(--text-primary);
		letter-spacing: 0.01em;
	}
	.admin-body :global(.page-header .subtitle) {
		margin: 0;
		max-width: 720px;
		font-size: 12px;
		line-height: 1.5;
		color: var(--text-muted);
	}
	.admin-body :global(.controls) {
		display: flex;
		gap: 10px;
		align-items: center;
		flex-shrink: 0;
	}

	.admin-body :global(.filter-group) {
		display: flex;
		gap: 2px;
		padding: 3px;
		background: var(--bg-card);
		border-radius: var(--radius-md);
	}
	.admin-body :global(.filter-btn) {
		padding: 6px 14px;
		font: inherit;
		font-size: 12px;
		color: var(--text-secondary);
		background: transparent;
		border: none;
		border-radius: var(--radius-sm);
		cursor: pointer;
	}
	.admin-body :global(.filter-btn:hover) {
		color: var(--text-primary);
	}
	.admin-body :global(.filter-btn.active) {
		background: var(--accent);
		color: var(--bg-base);
		font-weight: 800;
	}

	.admin-body :global(.refresh-btn),
	.admin-body :global(.ghost-btn) {
		padding: 7px 14px;
		font: inherit;
		font-size: 12px;
		color: var(--text-primary);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		cursor: pointer;
	}
	.admin-body :global(.refresh-btn:hover:not(:disabled)),
	.admin-body :global(.ghost-btn:hover:not(:disabled)) {
		border-color: var(--accent);
	}
	.admin-body :global(.refresh-btn:disabled),
	.admin-body :global(.ghost-btn:disabled) {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.admin-body :global(.error-box) {
		margin-bottom: 12px;
		padding: 10px 14px;
		font-size: 13px;
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid var(--error);
		color: var(--error);
		border-radius: var(--radius-sm);
	}

	.admin-body :global(.empty) {
		padding: 60px 20px;
		text-align: center;
		color: var(--text-muted);
	}
	.admin-body :global(.empty-icon) {
		font-size: 36px;
		margin-bottom: 10px;
	}
	.admin-body :global(.empty-text) {
		font-size: 13px;
		margin-bottom: 16px;
	}

	.admin-body :global(.table-wrap) {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		overflow: auto;
	}
	.admin-body :global(.table-wrap table) {
		width: 100%;
		border-collapse: collapse;
		font-size: 12.5px;
		font-variant-numeric: tabular-nums;
	}
	.admin-body :global(.table-wrap thead th) {
		position: sticky;
		top: 0;
		z-index: 1;
		padding: 10px 12px;
		text-align: left;
		font-weight: 800;
		font-size: 11px;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		background: rgba(13, 17, 23, 0.65);
		border-bottom: 1px solid var(--border);
	}
	.admin-body :global(.table-wrap tbody td) {
		padding: 10px 12px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.12);
		vertical-align: top;
		color: var(--text-primary);
	}
	.admin-body :global(.table-wrap tbody tr:hover) {
		background: rgba(77, 191, 179, 0.04);
	}
	.admin-body :global(.table-wrap tbody tr:last-child td) {
		border-bottom: none;
	}
	.admin-body :global(.table-wrap .num) {
		text-align: right;
	}

	/* Inline status / kind / framework badges. Use .chip in panels. */
	.admin-body :global(.chip) {
		display: inline-flex;
		align-items: center;
		padding: 2px 8px;
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.04em;
		color: var(--text-secondary);
		background: rgba(100, 116, 139, 0.18);
		border-radius: 5px;
		text-transform: uppercase;
	}
	.admin-body :global(.chip.accent) {
		color: var(--accent);
		background: rgba(77, 191, 179, 0.10);
		text-transform: none;
		letter-spacing: 0;
	}
</style>
