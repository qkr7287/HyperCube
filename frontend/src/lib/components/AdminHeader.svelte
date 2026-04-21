<script lang="ts">
	import { page } from '$app/stores';
	import { base } from '$app/paths';
	import { onDestroy, onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { pendingRequestCount } from '$lib/stores/global-events';
	import AgentStatusBadge from '$lib/components/AgentStatusBadge.svelte';
	import logoHypercube from '$lib/assets/logo_hypercube.png';

	let {
		totalAgents = 0,
		username = '',
		onLogout = () => {},
	}: {
		totalAgents?: number;
		username?: string;
		onLogout?: () => void;
	} = $props();

	let pending = $state(0);
	const unsub = pendingRequestCount.subscribe((n) => (pending = n));

	// 헤더 mount 시 pending 갯수 REST로 1회 조회 (이후 WS 이벤트로 증감)
	async function refreshPending() {
		if (!browser) return;
		const token = localStorage.getItem('hc_access_token');
		if (!token) return;
		try {
			const res = await fetch(`${base}/api/requests/?status=pending&page_size=1`, {
				headers: { Authorization: `Bearer ${token}` },
			});
			if (!res.ok) return;
			const json = await res.json();
			pendingRequestCount.set(json.data?.count ?? 0);
		} catch {
			/* ignore */
		}
	}

	onMount(refreshPending);
	onDestroy(unsub);

	let currentPath = $derived($page.url.pathname);
	function isActive(prefix: string): boolean {
		if (prefix === '/') return currentPath === '/' || currentPath.startsWith('/?') ;
		return currentPath.startsWith(prefix);
	}

	const navItems = [
		{ href: `${base}/`, label: '메인', match: '/' },
		{ href: `${base}/admin/requests`, label: '승인', match: '/admin/requests', badge: () => pending },
		{ href: `${base}/admin/templates`, label: '템플릿', match: '/admin/templates' },
	];

	let menuOpen = $state(false);
	function toggleMenu(e: MouseEvent) {
		e.stopPropagation();
		menuOpen = !menuOpen;
	}
	function handleDocClick(e: MouseEvent) {
		if (!menuOpen) return;
		const t = e.target as HTMLElement;
		if (!t.closest('.user-menu')) menuOpen = false;
	}
	$effect(() => {
		document.addEventListener('click', handleDocClick);
		return () => document.removeEventListener('click', handleDocClick);
	});
</script>

<header class="admin-header">
	<div class="brand" onclick={() => goto(`${base}/`)} role="button" tabindex="0"
		onkeydown={(e) => e.key === 'Enter' && goto(`${base}/`)}>
		<img class="brand-logo" src={logoHypercube} alt="HyperCube" />
	</div>

	<nav class="nav">
		{#each navItems as item (item.href)}
			<a
				href={item.href}
				class="nav-link"
				class:active={isActive(item.match)}
			>
				{item.label}
				{#if item.badge && item.badge() > 0}
					<span class="nav-badge">{item.badge()}</span>
				{/if}
			</a>
		{/each}
	</nav>

	<div class="right-cluster">
		<AgentStatusBadge totalKnown={totalAgents} />
		<div class="user-menu">
			<button class="user-btn" onclick={toggleMenu}>
				{username || 'user'} <span class="chev" class:open={menuOpen}>▾</span>
			</button>
			{#if menuOpen}
				<div class="user-dropdown">
					<button class="user-item" onclick={onLogout}>로그아웃</button>
				</div>
			{/if}
		</div>
	</div>
</header>

<style>
	.admin-header {
		height: 48px;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0 20px;
		background: var(--bg-card);
		border-bottom: 1px solid var(--border);
	}

	.brand {
		cursor: pointer;
		user-select: none;
	}
	.brand-text {
		font-size: 16px;
		font-weight: 800;
		color: var(--accent);
		letter-spacing: 0.02em;
	}
	.brand-logo {
		display: block;
		height: 22px;
		width: auto;
	}

	.nav {
		display: flex;
		gap: 4px;
	}
	.nav-link {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 7px 14px;
		font-size: 13px;
		font-weight: 500;
		color: var(--text-secondary);
		text-decoration: none;
		border-radius: var(--radius-md);
		transition: color 0.12s, background 0.12s;
	}
	.nav-link:hover {
		color: var(--text-primary);
		background: var(--bg-tab);
	}
	.nav-link.active {
		color: var(--text-primary);
		background: var(--bg-tab);
		box-shadow: inset 0 -2px 0 var(--accent);
	}
	.nav-badge {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 18px;
		height: 18px;
		padding: 0 5px;
		background: var(--error);
		color: white;
		font-size: 10px;
		font-weight: 700;
		border-radius: 9px;
	}

	.right-cluster {
		display: flex;
		align-items: center;
		gap: 14px;
	}

	.user-menu {
		position: relative;
	}
	.user-btn {
		background: none;
		border: 1px solid var(--border);
		color: var(--text-primary);
		padding: 5px 10px;
		border-radius: var(--radius-md);
		font-size: 12px;
		cursor: pointer;
		display: inline-flex;
		align-items: center;
		gap: 4px;
		font-family: inherit;
	}
	.user-btn:hover {
		border-color: var(--accent);
	}
	.chev {
		font-size: 10px;
		transition: transform 0.15s;
	}
	.chev.open {
		transform: rotate(180deg);
	}
	.user-dropdown {
		position: absolute;
		top: calc(100% + 4px);
		right: 0;
		min-width: 140px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
		padding: 4px;
		z-index: 100;
	}
	.user-item {
		width: 100%;
		text-align: left;
		background: none;
		border: none;
		color: var(--text-primary);
		padding: 8px 10px;
		font-size: 12px;
		cursor: pointer;
		border-radius: var(--radius-sm);
		font-family: inherit;
	}
	.user-item:hover {
		background: var(--bg-tab);
	}
</style>
