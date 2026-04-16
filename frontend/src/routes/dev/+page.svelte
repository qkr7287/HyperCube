<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';

	type RedisSection = { title: string; keys: { key: string; ttl: number; value: string }[] };

	let sections = $state<RedisSection[]>([]);
	let loading = $state(false);
	let errorMsg = $state('');
	let username = $state('');

	function decodeJwt(token: string): any {
		try { return JSON.parse(atob(token.split('.')[1])); } catch { return {}; }
	}

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function load() {
		const t = token();
		if (!t) return;
		loading = true;
		errorMsg = '';
		try {
			const res = await fetch(`${base}/api/dev/redis-snapshot/`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (!res.ok) {
				errorMsg = `HTTP ${res.status}`;
				return;
			}
			const json = await res.json();
			sections = json.data ?? json ?? [];
		} catch (e: any) {
			errorMsg = e?.message || 'Load failed';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		if (!browser) return;
		const t = token();
		if (!t) { goto(`${base}/`); return; }
		const payload = decodeJwt(t);
		if (payload.role !== 'admin') { goto(`${base}/`); return; }
		username = payload.username ?? '';
		load();
	});

	function doLogout() {
		if (browser) {
			localStorage.removeItem('hc_access_token');
			localStorage.removeItem('hc_selected_server');
		}
		goto(`${base}/`);
	}

	function truncate(s: string, max: number): string {
		return s.length > max ? s.slice(0, max) + '...' : s;
	}
</script>

<div class="dev-shell">
	<header class="dev-header">
		<span class="brand" onclick={() => goto(`${base}/`)} role="button" tabindex="0"
			onkeydown={(e) => e.key === 'Enter' && goto(`${base}/`)}>HyperCube</span>
		<span class="dev-badge">DEV</span>
		<div class="right">
			<button class="refresh-btn" onclick={load} disabled={loading}>
				{loading ? '...' : '↻ Refresh'}
			</button>
			<span class="user">{username}</span>
			<button class="logout-btn" onclick={doLogout}>로그아웃</button>
		</div>
	</header>

	<main class="dev-body">
		<h1>Redis 내부 상태</h1>
		<p class="subtitle">Agent 레지스트리, 명령 pending, 메트릭 캐시 등 시스템 내부 상태를 진단합니다.</p>

		{#if errorMsg}
			<div class="error-box">{errorMsg}</div>
		{/if}

		{#if sections.length === 0 && !loading}
			<div class="empty">데이터 없음. Backend에 /api/dev/redis-snapshot/ 엔드포인트가 아직 없으면 아래 안내를 따라 추가하세요.</div>
		{/if}

		{#each sections as section (section.title)}
			<div class="section">
				<div class="section-title">{section.title} <span class="count">{section.keys.length}</span></div>
				{#if section.keys.length === 0}
					<div class="section-empty">(비어있음)</div>
				{:else}
					<div class="key-list">
						{#each section.keys as entry (entry.key)}
							<div class="key-row">
								<div class="key-name">{entry.key}</div>
								<div class="key-ttl">{entry.ttl >= 0 ? `${entry.ttl}s` : 'persist'}</div>
								<div class="key-value">{truncate(entry.value, 300)}</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		{/each}
	</main>
</div>

<style>
	.dev-shell { height: 100vh; display: flex; flex-direction: column; background: var(--bg-base); }
	.dev-header {
		height: 48px; flex-shrink: 0; display: flex; align-items: center;
		padding: 0 20px; gap: 12px; background: var(--bg-card); border-bottom: 1px solid var(--border);
	}
	.brand { font-size: 16px; font-weight: 800; color: var(--accent); cursor: pointer; }
	.dev-badge {
		background: #7c3aed; color: white; font-size: 10px; font-weight: 700;
		padding: 2px 8px; border-radius: 4px;
	}
	.right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
	.refresh-btn {
		background: var(--bg-tab); border: 1px solid var(--border); color: var(--text-primary);
		padding: 5px 12px; font-size: 11px; border-radius: var(--radius-sm); cursor: pointer; font-family: inherit;
	}
	.refresh-btn:hover:not(:disabled) { border-color: var(--accent); }
	.user { font-size: 12px; color: var(--text-secondary); }
	.logout-btn {
		background: var(--bg-tab); border: 1px solid var(--border); color: var(--text-primary);
		padding: 5px 12px; font-size: 11px; border-radius: var(--radius-sm); cursor: pointer; font-family: inherit;
	}

	.dev-body { flex: 1; overflow-y: auto; padding: 28px 32px; max-width: 1100px; }
	h1 { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: 0 0 6px; }
	.subtitle { font-size: 12px; color: var(--text-muted); margin: 0 0 24px; }

	.error-box {
		background: rgba(239,68,68,0.1); border: 1px solid var(--error);
		color: var(--error); padding: 10px 14px; border-radius: var(--radius-sm);
		font-size: 12px; margin-bottom: 16px;
	}
	.empty { color: var(--text-muted); font-size: 13px; padding: 40px 0; text-align: center; }

	.section {
		background: var(--bg-card); border: 1px solid var(--border);
		border-radius: var(--radius-md); margin-bottom: 16px; overflow: hidden;
	}
	.section-title {
		padding: 12px 16px; font-size: 13px; font-weight: 700; color: var(--accent);
		background: var(--bg-tab); border-bottom: 1px solid var(--border);
		display: flex; align-items: center; gap: 8px;
	}
	.count {
		background: var(--bg-base); color: var(--text-secondary);
		padding: 1px 8px; border-radius: 10px; font-size: 11px;
	}
	.section-empty { padding: 16px; color: var(--text-muted); font-size: 12px; }

	.key-list { display: flex; flex-direction: column; }
	.key-row {
		display: grid; grid-template-columns: 1fr 60px 2fr;
		padding: 8px 16px; border-bottom: 1px solid var(--border);
		font-size: 11px; gap: 12px; align-items: start;
	}
	.key-row:last-child { border-bottom: none; }
	.key-name {
		font-family: 'JetBrains Mono', monospace; color: var(--text-primary);
		word-break: break-all;
	}
	.key-ttl { color: var(--text-muted); text-align: right; font-family: monospace; }
	.key-value {
		font-family: 'JetBrains Mono', monospace; color: var(--text-secondary);
		font-size: 10px; word-break: break-all; max-height: 80px; overflow: hidden;
	}
</style>
