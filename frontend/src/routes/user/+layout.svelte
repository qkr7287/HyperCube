<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import logoHypercube from '$lib/assets/logo_hypercube.png';
	import { connectGlobal, disconnectGlobal, seedActiveAgents } from '$lib/stores/global-events';
	import { userHeaderStore } from '$lib/stores/user-header';

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
		<div class="hero-slot">
			{#if $userHeaderStore}
				{#if $userHeaderStore.title}
					<div class="hero-title">
						<strong>{$userHeaderStore.title}</strong>
						{#if $userHeaderStore.subtitle}<em>{$userHeaderStore.subtitle}</em>{/if}
					</div>
				{/if}
				{#if $userHeaderStore.kpis && $userHeaderStore.kpis.length > 0}
					<div class="hero-kpis">
						{#each $userHeaderStore.kpis as k (k.key)}
							<span class="kpi-pill" data-tone={k.tone || 'default'} class:on={k.on} title={k.title || ''}>
								<span class="kpi-dot"></span>
								<span class="kpi-num">{k.value}</span>
								<span class="kpi-label">{k.label}</span>
							</span>
						{/each}
					</div>
				{/if}
				{#if $userHeaderStore.actions && $userHeaderStore.actions.length > 0}
					<div class="hero-actions">
						{#each $userHeaderStore.actions as a, idx (idx)}
							<button
								class="hero-btn"
								class:primary={a.variant === 'primary'}
								class:icon-only={a.variant === 'icon'}
								onclick={a.onclick}
								disabled={a.disabled}
								title={a.label}
							>
								{#if a.spinning}<span class="hero-btn-spin"></span>{/if}
								{#if a.variant === 'icon'}
									<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
										<path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
										<path d="M21 3v5h-5" />
										<path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
										<path d="M3 21v-5h5" />
									</svg>
								{:else}
									{a.label}
								{/if}
							</button>
						{/each}
					</div>
				{/if}
			{/if}
		</div>
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
		gap: 12px;
		padding: 0 20px;
		background: rgba(18, 23, 32, 0.92);
		border-bottom: 1px solid var(--border);
		backdrop-filter: blur(14px);
		min-width: 0;
	}

	.brand {
		cursor: pointer;
		user-select: none;
		display: inline-flex;
		align-items: center;
		flex: 0 1 auto;
		min-width: 0;
	}

	.brand-logo {
		display: block;
		height: 22px;
		width: auto;
		max-width: 100%;
	}

	.hero-slot {
		display: flex;
		align-items: center;
		gap: 16px;
		flex: 1 1 auto;
		justify-content: flex-start;
		min-width: 0;
		padding-left: 20px;
	}

	.hero-title {
		display: flex;
		align-items: baseline;
		gap: 8px;
		flex-shrink: 0;
	}

	.hero-title strong {
		font-size: 14px;
		font-weight: 800;
		color: var(--text-primary);
		white-space: nowrap;
	}

	.hero-title em {
		font-style: normal;
		font-size: 11.5px;
		color: var(--text-muted);
		white-space: nowrap;
	}

	.hero-kpis {
		display: flex;
		gap: 8px;
		flex-wrap: nowrap;
		overflow: hidden;
	}

	.kpi-pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 10px;
		font-size: 11.5px;
		font-weight: 700;
		color: var(--text-muted);
		background: rgba(13, 17, 23, 0.6);
		border: 1px solid var(--border);
		border-radius: 999px;
		white-space: nowrap;
	}

	.kpi-pill.on {
		color: var(--text-primary);
		border-color: rgba(77, 191, 179, 0.45);
	}

	.kpi-pill .kpi-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--text-muted);
		flex-shrink: 0;
	}

	.kpi-pill[data-tone="container"] .kpi-dot { background: #22c55e; }
	.kpi-pill[data-tone="request"] .kpi-dot { background: #f59e0b; }
	.kpi-pill[data-tone="gpu"] .kpi-dot { background: #a855f7; }
	.kpi-pill[data-tone="ws"] .kpi-dot { background: var(--accent); }

	.kpi-pill:not(.on) .kpi-dot { background: rgba(100, 116, 139, 0.5); }

	.kpi-num {
		font-weight: 900;
		color: var(--text-primary);
	}

	.kpi-pill:not(.on) .kpi-num { color: var(--text-muted); }

	.kpi-label {
		color: var(--text-muted);
		font-size: 10.5px;
	}

	.hero-actions {
		display: flex;
		gap: 6px;
	}

	.hero-btn {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 6px 12px;
		font: inherit;
		font-size: 11.5px;
		font-weight: 700;
		color: var(--text-primary);
		background: transparent;
		border: 1px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
		white-space: nowrap;
	}

	.hero-btn:hover:not(:disabled) {
		border-color: var(--accent);
		color: var(--accent);
	}

	.hero-btn.primary {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--bg-base);
	}

	.hero-btn.primary:hover:not(:disabled) {
		filter: brightness(1.08);
	}

	.hero-btn.icon-only {
		padding: 6px 8px;
		color: var(--text-muted);
	}

	.hero-btn.icon-only:hover:not(:disabled) {
		color: var(--accent);
		border-color: var(--accent);
	}

	.hero-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.hero-btn-spin {
		width: 10px;
		height: 10px;
		border: 2px solid currentColor;
		border-top-color: transparent;
		border-radius: 50%;
		animation: hero-spin 0.8s linear infinite;
	}

	@keyframes hero-spin {
		to { transform: rotate(360deg); }
	}

	.right {
		display: flex;
		align-items: center;
		gap: 12px;
		flex: 0 0 auto;
		min-width: 0;
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
		/* 자연 스크롤. viewport-fit 강제는 정보 밀도만 높이고 짤림을 유발해서 포기.
		   페이지 자체가 height 를 자연스럽게 차지하고 user-body 가 스크롤 컨테이너. */
		overflow-y: auto;
	}
	@media (max-width: 640px) {
		.user-shell {
			height: 100dvh;
		}
		.user-header {
			height: auto;
			min-height: 72px;
			display: grid;
			grid-template-columns: minmax(0, 1fr) auto;
			grid-template-areas:
				"brand right"
				"nav nav";
			align-items: center;
			gap: 8px 10px;
			padding: 8px 12px;
		}
		.brand {
			grid-area: brand;
		}
		.brand-logo {
			height: 20px;
			max-width: 170px;
		}
		.nav {
			grid-area: nav;
			width: 100%;
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			gap: 4px;
			padding: 3px;
			border-radius: 12px;
			background: rgba(13, 17, 23, 0.62);
			border: 1px solid rgba(100, 116, 139, 0.18);
		}
		.nav-link {
			display: flex;
			align-items: center;
			justify-content: center;
			min-height: 32px;
			padding: 0 8px;
			border-radius: 9px;
			font-size: 12px;
			font-weight: 800;
		}
		.right {
			grid-area: right;
			justify-self: end;
			gap: 6px;
		}
		.user-name {
			max-width: 72px;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.logout-btn {
			padding: 5px 9px;
			font-size: 10.5px;
		}
	}

	@media (max-width: 420px) {
		.brand-logo {
			max-width: 150px;
		}
		.user-name {
			display: none;
		}
	}
</style>
