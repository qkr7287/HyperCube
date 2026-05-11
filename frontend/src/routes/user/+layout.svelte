<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import logoHypercube from '$lib/assets/logo_hypercube.png';
	import { connectGlobal, disconnectGlobal, seedActiveAgents } from '$lib/stores/global-events';

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

	async function seedAgentsFromBackend(token: string) {
		// agent_status_change 는 transition 시점에만 broadcast 됨 → 페이지 진입 시
		// store 가 비어있으면 AgentStatusIndicator 가 잠깐 offline 으로 깜빡인다.
		// admin 페이지들과 동일하게 active 한 agent 목록을 fetch 해 seed.
		try {
			const res = await fetch(`${base}/api/agents/?status=approved&active=true&page_size=200`, {
				headers: { Authorization: `Bearer ${token}` },
			});
			if (!res.ok) return;
			const json = await res.json();
			const agents = json.data?.results ?? json.results ?? [];
			seedActiveAgents(
				agents.filter((a: any) => a.is_active).map((a: any) => String(a.id)),
			);
		} catch {
			/* ignore — fallback (currentMetrics.timestamp < 120s) 가 동작 */
		}
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
		// agent_status_change 같은 cross-cutting 이벤트 받기 위해 global WS 연결
		// (admin 만 받던 거 → user 페이지에서도 agent online/offline 표시 위해)
		connectGlobal(token);
		// active agent 목록을 seed — transition event 만 의지하면 첫 로드 깜빡임.
		seedAgentsFromBackend(token);
	});

	onDestroy(() => {
		if (browser) disconnectGlobal();
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
		min-height: 0;
		/* desktop 에선 컨테이너 상세가 viewport 안에 fit → 세로 스크롤 제거.
		   ≤980 모바일은 1열 stack 이라 스크롤 필요 → @media 로 풀어줌. */
		overflow-y: hidden;
	}

	@media (max-width: 980px) {
		.user-body {
			overflow-y: auto;
		}
	}
</style>
