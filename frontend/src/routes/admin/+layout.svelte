<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { connectGlobal, disconnectGlobal } from '$lib/stores/global-events';
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
			const res = await fetch(`${base}/api/agents/?status=approved&page_size=1`, {
				headers: { Authorization: `Bearer ${token}` },
			});
			if (res.ok) {
				const json = await res.json();
				totalAgents = json.data?.count ?? 0;
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
</style>
