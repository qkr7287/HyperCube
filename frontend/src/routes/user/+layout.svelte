<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import logoHypercube from '$lib/assets/logo_hypercube.png';

	let { children } = $props();
	let ready = $state(false);
	let username = $state('');

	function decodeJwt(token: string): any {
		try {
			return JSON.parse(atob(token.split('.')[1]));
		} catch {
			return {};
		}
	}

	function doLogout() {
		if (browser) {
			localStorage.removeItem('hc_access_token');
			localStorage.removeItem('hc_selected_server');
		}
		goto(`${base}/`);
	}

	onMount(() => {
		if (!browser) return;
		const token = localStorage.getItem('hc_access_token');
		if (!token) {
			goto(`${base}/`);
			return;
		}
		const payload = decodeJwt(token);
		username = payload.username ?? '';
		ready = true;
	});

	let currentPath = $derived($page.url.pathname);
</script>

{#if ready}
<div class="user-shell">
	<header class="user-header">
		<span
			class="brand"
			onclick={() => goto(`${base}/user`)}
			role="button"
			tabindex="0"
			onkeydown={(e) => e.key === 'Enter' && goto(`${base}/user`)}
		>
			<img class="brand-logo" src={logoHypercube} alt="HyperCube" />
		</span>
		<nav class="nav">
			<a
				href={base + '/user'}
				class="nav-link"
				class:active={currentPath === `${base}/user` || currentPath === `${base}/user/`}
			>요청 현황</a>
			<a
				href={base + '/user/containers'}
				class="nav-link"
				class:active={currentPath.startsWith(`${base}/user/containers`)}
			>내 컨테이너</a>
		</nav>
		<div class="right">
			<span class="user-name">{username}</span>
			<button class="logout-btn" onclick={doLogout}>로그아웃</button>
		</div>
	</header>
	<main class="user-body">
		{@render children()}
	</main>
</div>
{/if}

<style>
	.user-shell {
		height: 100vh;
		display: flex;
		flex-direction: column;
		background:
			radial-gradient(circle at top right, rgba(48, 213, 200, 0.08), transparent 26%),
			var(--bg-base);
	}

	.user-header {
		height: 56px;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 20px;
		background: rgba(18, 23, 32, 0.92);
		border-bottom: 1px solid var(--border);
		backdrop-filter: blur(14px);
	}

	.brand {
		cursor: pointer;
		user-select: none;
		display: inline-flex;
		align-items: center;
	}

	.brand-logo {
		display: block;
		height: 22px;
		width: auto;
	}

	.nav {
		display: flex;
		gap: 6px;
	}

	.nav-link {
		padding: 8px 14px;
		font-size: 13px;
		font-weight: 600;
		color: var(--text-secondary);
		text-decoration: none;
		border-radius: var(--radius-md);
		transition: color 0.12s, background 0.12s, box-shadow 0.12s;
	}

	.nav-link:hover {
		color: var(--text-primary);
		background: rgba(21, 28, 39, 0.92);
	}

	.nav-link.active {
		color: var(--text-primary);
		background: rgba(21, 28, 39, 0.98);
		box-shadow: inset 0 -2px 0 var(--accent);
	}

	.right {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.user-name {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.logout-btn {
		background: var(--bg-tab);
		border: 1px solid var(--border);
		color: var(--text-primary);
		padding: 6px 12px;
		font-size: 11px;
		border-radius: var(--radius-sm);
		cursor: pointer;
		font-family: inherit;
	}

	.logout-btn:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	.user-body {
		flex: 1;
		overflow-y: auto;
	}
</style>
