<!--
  ProcessTopPanel — 컨테이너 내부 프로세스 top-N 표시.

  REST `/api/my-containers/<id>/processes/?sortBy=&limit=` 폴링 (5s).
  paused / 페이지 background 시엔 폴링 멈춤 (visibilitychange).
-->
<script lang="ts">
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { onDestroy, onMount } from 'svelte';
	import { formatBytesValue } from '$lib/utils/container-dashboard';

	type ProcessRow = {
		pid: number;
		name: string;
		command: string;
		cpu_percent: number;
		memory_rss: number;
		state: string;
		user: string;
	};

	let {
		containerId,
		paused = false,
	}: {
		containerId: string;
		paused?: boolean;
	} = $props();

	let sortBy = $state<'cpu' | 'mem'>('cpu');
	let limit = $state<number>(20);
	let processes = $state<ProcessRow[]>([]);
	let total = $state<number>(0);
	let loading = $state(false);
	let errorMsg = $state('');
	let lastFetched = $state<Date | null>(null);
	let timer: ReturnType<typeof setInterval> | null = null;

	const STATE_LABEL: Record<string, { label: string; tone: string }> = {
		R: { label: '실행', tone: 'success' },
		S: { label: '대기', tone: 'muted' },
		D: { label: 'I/O', tone: 'warn' },
		Z: { label: '좀비', tone: 'danger' },
		T: { label: '정지', tone: 'warn' },
		I: { label: 'idle', tone: 'muted' },
	};

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function load() {
		if (!containerId) return;
		const t = token();
		if (!t) return;
		loading = true;
		try {
			const url = `${base}/api/my-containers/${containerId}/processes/?sortBy=${sortBy}&limit=${limit}`;
			const r = await fetch(url, { headers: { Authorization: `Bearer ${t}` } });
			const j = await r.json().catch(() => ({}));
			if (!r.ok) {
				errorMsg = j?.error?.detail || j?.detail || `HTTP ${r.status}`;
				return;
			}
			const data = j?.data ?? {};
			processes = Array.isArray(data.processes) ? data.processes : [];
			total = Number(data.total ?? 0);
			errorMsg = '';
			lastFetched = new Date();
		} catch (err: any) {
			errorMsg = err?.message || '프로세스 조회 실패';
		} finally {
			loading = false;
		}
	}

	function tick() {
		if (paused) return;
		if (typeof document !== 'undefined' && document.hidden) return;
		load();
	}

	$effect(() => {
		// sortBy / limit 변경 시 즉시 재조회.
		void sortBy;
		void limit;
		void containerId;
		load();
	});

	onMount(() => {
		// 즉시 초기 fetch + 5s 폴링.
		load();
		timer = setInterval(tick, 5000);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});

	function stateMeta(s: string) {
		return STATE_LABEL[s] || { label: s || '-', tone: 'muted' };
	}
</script>

<section class="panel">
	<div class="panel-header slim">
		<div>
			<h2>컨테이너 내부 프로세스</h2>
			<p>호스트 관찰 기반 실시간 프로세스 (5초 폴링). agent 가 컨테이너 내부 ps 사용 안 해 minimal image 도 동작.</p>
		</div>
		<div class="tools">
			<div class="seg" role="group" aria-label="정렬 기준">
				<button class:active={sortBy === 'cpu'} onclick={() => (sortBy = 'cpu')}>CPU</button>
				<button class:active={sortBy === 'mem'} onclick={() => (sortBy = 'mem')}>Mem</button>
			</div>
			<select class="lim" bind:value={limit}>
				{#each [10, 20, 50, 100] as n}
					<option value={n}>top {n}</option>
				{/each}
			</select>
			<button class="refresh" onclick={load} disabled={loading}>
				{loading ? '불러오는 중...' : '지금 새로고침'}
			</button>
		</div>
	</div>

	{#if errorMsg}
		<div class="empty error">{errorMsg}</div>
	{:else if processes.length === 0 && !loading}
		<div class="empty">표시할 프로세스가 없습니다.</div>
	{:else}
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="num">PID</th>
						<th>이름</th>
						<th class="num">CPU%</th>
						<th class="num">RSS</th>
						<th>상태</th>
						<th>UID</th>
						<th>Command</th>
					</tr>
				</thead>
				<tbody>
					{#each processes as p (p.pid)}
						{@const st = stateMeta(p.state)}
						<tr>
							<td class="num mono">{p.pid}</td>
							<td class="mono name">{p.name}</td>
							<td class="num">{p.cpu_percent.toFixed(1)}</td>
							<td class="num">{formatBytesValue(p.memory_rss)}</td>
							<td><span class="badge {st.tone}" title={p.state}>{st.label}</span></td>
							<td class="mono">{p.user}</td>
							<td class="mono cmd">{p.command || p.name}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="footer">
			<span>{processes.length} / {total}건 표시</span>
			{#if lastFetched}
				<span>마지막 갱신: {lastFetched.toLocaleTimeString()}</span>
			{/if}
		</div>
	{/if}
</section>

<style>
	.panel {
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		border-radius: 18px;
		padding: 20px;
		margin-top: 18px;
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 18px;
		margin-bottom: 14px;
		flex-wrap: wrap;
	}
	h2 {
		font-size: 20px;
		margin-bottom: 4px;
	}
	.panel-header p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.tools {
		display: inline-flex;
		gap: 8px;
		align-items: center;
		flex-wrap: wrap;
	}

	.seg {
		display: inline-flex;
		border: 1px solid rgba(31, 41, 55, 0.9);
		border-radius: 8px;
		overflow: hidden;
	}
	.seg button {
		padding: 6px 12px;
		background: rgba(13, 17, 23, 0.86);
		border: none;
		color: var(--text-muted);
		font-family: inherit;
		font-size: 11px;
		font-weight: 700;
		cursor: pointer;
	}
	.seg button + button {
		border-left: 1px solid rgba(31, 41, 55, 0.9);
	}
	.seg button.active {
		background: rgba(48, 213, 200, 0.18);
		color: var(--accent);
	}

	.lim {
		padding: 6px 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 11px;
		cursor: pointer;
	}

	.refresh {
		padding: 6px 12px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-secondary);
		font-family: inherit;
		font-size: 11px;
		font-weight: 700;
		cursor: pointer;
	}
	.refresh:hover:not(:disabled) {
		color: var(--accent);
		border-color: rgba(48, 213, 200, 0.4);
	}
	.refresh:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.empty {
		padding: 16px;
		border-radius: 12px;
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
		font-size: 13px;
		color: var(--text-secondary);
	}
	.empty.error {
		color: #fecaca;
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(127, 29, 29, 0.18);
	}

	.table-wrap {
		max-height: 480px;
		overflow: auto;
		border-radius: 10px;
		border: 1px solid rgba(31, 41, 55, 0.7);
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 12px;
	}

	thead {
		position: sticky;
		top: 0;
		background: rgba(2, 6, 12, 0.95);
		z-index: 1;
	}

	th {
		text-align: left;
		padding: 10px 12px;
		font-size: 11px;
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		border-bottom: 1px solid rgba(31, 41, 55, 0.7);
	}
	th.num,
	td.num {
		text-align: right;
	}

	td {
		padding: 8px 12px;
		border-bottom: 1px solid rgba(31, 41, 55, 0.4);
		color: var(--text-primary);
	}

	tr:last-child td {
		border-bottom: none;
	}

	tr:hover td {
		background: rgba(48, 213, 200, 0.04);
	}

	.mono {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.name {
		max-width: 180px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.cmd {
		max-width: 360px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--text-secondary);
		font-size: 11px;
	}

	.badge {
		display: inline-flex;
		padding: 2px 8px;
		border-radius: 999px;
		font-size: 10px;
		font-weight: 700;
	}
	.badge.success { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); }
	.badge.warn    { background: rgba(234, 179, 8, 0.18);  color: #fde047; border: 1px solid rgba(234, 179, 8, 0.35); }
	.badge.danger  { background: rgba(239, 68, 68, 0.18);  color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
	.badge.muted   { background: rgba(100, 116, 139, 0.16); color: var(--text-secondary); border: 1px solid rgba(100, 116, 139, 0.32); }

	.footer {
		display: flex;
		justify-content: space-between;
		font-size: 11px;
		color: var(--text-muted);
		margin-top: 10px;
	}
</style>
