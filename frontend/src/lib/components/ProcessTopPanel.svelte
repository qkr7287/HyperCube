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
	import StateBox from './StateBox.svelte';

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
		<StateBox kind="error" message={errorMsg} action={load} actionLabel="다시 시도" />
	{:else if loading && processes.length === 0}
		<StateBox kind="loading" message="프로세스 목록 불러오는 중..." />
	{:else if processes.length === 0}
		<StateBox kind="empty" message="표시할 프로세스가 없습니다." icon="🛈" />
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
		background:
			linear-gradient(180deg, rgba(21, 27, 38, 0.98), rgba(15, 20, 29, 0.98)),
			rgba(18, 23, 32, 0.96);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: var(--radius-panel);
		padding: clamp(5px, 0.45vw, 8px);
		margin-top: 0;
		transition: border-color var(--ease-fast);
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		height: 100%;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		overflow: hidden;
		position: relative;
		box-shadow:
			0 8px 24px rgba(0, 0, 0, 0.16),
			inset 0 1px 0 rgba(255, 255, 255, 0.025);
	}
	.panel::before {
		content: '';
		position: absolute;
		inset: 0 0 auto;
		height: 2px;
		background: linear-gradient(90deg, rgba(48, 213, 200, 0.66), rgba(96, 165, 250, 0.12));
		opacity: 0.7;
	}
	.panel:hover {
		border-color: rgba(48, 213, 200, 0.22);
	}
	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		margin-bottom: 5px;
		flex-wrap: wrap;
		padding-bottom: 5px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.12);
	}
	h2 {
		font-size: 14px;
		margin-bottom: 0;
	}
	.panel-header p {
		display: none;
		font-size: 11px;
		color: var(--text-secondary);
	}

	.tools {
		display: inline-flex;
		gap: 4px;
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
		padding: 3px 7px;
		background: rgba(13, 17, 23, 0.86);
		border: none;
		color: var(--text-muted);
		font-family: inherit;
		font-size: 10px;
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
		padding: 3px 6px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 10px;
		cursor: pointer;
	}

	.refresh {
		padding: 3px 7px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-secondary);
		font-family: inherit;
		font-size: 10px;
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
		padding: 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
		font-size: 11px;
		color: var(--text-secondary);
	}
	.empty.error {
		color: #fecaca;
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(127, 29, 29, 0.18);
	}

	.table-wrap {
		flex: 1 1 0;
		min-height: 0;
		min-width: 0;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		max-height: none;
		overflow: auto;
		border-radius: 8px;
		border: 1px solid rgba(100, 116, 139, 0.16);
	}

	table {
		width: 100%;
		min-width: 0;
		table-layout: fixed;
		border-collapse: collapse;
		font-size: 10.5px;
	}

	thead {
		position: sticky;
		top: 0;
		background: rgba(2, 6, 12, 0.95);
		z-index: 1;
	}

	th {
		text-align: left;
		padding: 4px 6px;
		font-size: 9.5px;
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		border-bottom: 1px solid rgba(31, 41, 55, 0.7);
	}
	th,
	td {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	th:nth-child(1),
	td:nth-child(1) { width: 46px; }
	th:nth-child(2),
	td:nth-child(2) { width: 46px; }
	th:nth-child(3),
	td:nth-child(3) { width: 38px; }
	th:nth-child(4),
	td:nth-child(4) { width: 52px; }
	th:nth-child(5),
	td:nth-child(5) { width: 44px; }
	th:nth-child(6),
	td:nth-child(6) { width: 32px; }
	th.num,
	td.num {
		text-align: right;
	}

	td {
		padding: 4px 6px;
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
		max-width: none;
	}

	.cmd {
		max-width: none;
		color: var(--text-secondary);
		font-size: 10px;
	}

	.badge {
		display: inline-flex;
		padding: 1px 6px;
		border-radius: 999px;
		font-size: 9.5px;
		font-weight: 700;
	}
	.badge.success { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); }
	.badge.warn    { background: rgba(234, 179, 8, 0.18);  color: #fde047; border: 1px solid rgba(234, 179, 8, 0.35); }
	.badge.danger  { background: rgba(239, 68, 68, 0.18);  color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
	.badge.muted   { background: rgba(100, 116, 139, 0.16); color: var(--text-secondary); border: 1px solid rgba(100, 116, 139, 0.32); }

	.footer {
		display: flex;
		justify-content: space-between;
		font-size: 10px;
		color: var(--text-muted);
		margin-top: 5px;
	}
</style>
