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
	let searchQuery = $state('');
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
			const qs = new URLSearchParams({ sortBy, limit: String(limit) });
			const url = `${base}/api/my-containers/${containerId}/processes/?${qs.toString()}`;
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

	function sumOf(values: number[]): number {
		return values.reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0);
	}

	function topBy(field: 'cpu_percent' | 'memory_rss'): ProcessRow | null {
		if (visibleProcesses.length === 0) return null;
		return visibleProcesses.reduce((best, row) => (row[field] > best[field] ? row : best), visibleProcesses[0]);
	}

	function countStates(states: string[]): number {
		return visibleProcesses.filter((row) => states.includes(row.state)).length;
	}

	function countShare(count: number): number {
		if (visibleProcesses.length === 0) return 0;
		return Math.max(0, Math.min(100, (count / visibleProcesses.length) * 100));
	}

	function rowShare(value: number, max: number): number {
		if (value <= 0) return 0;
		if (max <= 0) return 0;
		return Math.max(2, Math.min(100, (value / max) * 100));
	}

	function normalized(value: unknown): string {
		return String(value ?? '').trim().toLowerCase();
	}

	function matchesQuery(row: ProcessRow, query: string): boolean {
		if (!query) return true;
		return String(row.pid).includes(query)
			|| normalized(row.name).includes(query)
			|| normalized(row.command).includes(query)
			|| normalized(row.user).includes(query)
			|| normalized(row.state).includes(query);
	}

	function showMore() {
		if (limit < 50) {
			limit = 50;
			return;
		}
		limit = 100;
	}

	let query = $derived(normalized(searchQuery));
	let searchActive = $derived(query.length > 0);
	let visibleProcesses = $derived.by<ProcessRow[]>(() => processes.filter((row) => matchesQuery(row, query)));
	let canLoadMore = $derived(processes.length < total && limit < 100);
	let reachedSafeLimit = $derived(total > processes.length && limit >= 100);
	let runningCount = $derived(countStates(['R']));
	let waitingCount = $derived(countStates(['S', 'I']));
	let blockedCount = $derived(countStates(['D', 'T']));
	let zombieCount = $derived(countStates(['Z']));
	let visibleCpuTotal = $derived(sumOf(visibleProcesses.map((row) => row.cpu_percent)));
	let visibleMemoryTotal = $derived(sumOf(visibleProcesses.map((row) => row.memory_rss)));
	let topCpuProcess = $derived(topBy('cpu_percent'));
	let topMemProcess = $derived(topBy('memory_rss'));
	let maxCpu = $derived(Math.max(1, ...visibleProcesses.map((row) => row.cpu_percent)));
	let maxMemory = $derived(Math.max(1, ...visibleProcesses.map((row) => row.memory_rss)));
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
				{#each [20, 50, 100] as n}
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
		<div class="process-summary" aria-label="프로세스 요약">
			<div class="summary-card">
				<span>{searchActive ? '검색/불러옴' : '표시/전체'}</span>
				<strong>{visibleProcesses.length}/{searchActive ? processes.length : total}</strong>
				<em>{searchActive ? 'filtered' : `top ${limit}`}</em>
			</div>
			<div class="summary-card">
				<span>실행/대기</span>
				<strong>{runningCount}/{waitingCount}</strong>
				<em>R / S·I</em>
			</div>
			<div class="summary-card" title={`표시 프로세스 CPU 합계 ${visibleCpuTotal.toFixed(1)}%`}>
				<span>Top CPU</span>
				<strong>{topCpuProcess ? topCpuProcess.cpu_percent.toFixed(1) : '0.0'}%</strong>
				<em title={topCpuProcess?.command || topCpuProcess?.name}>{topCpuProcess?.name ?? '-'}</em>
			</div>
			<div class="summary-card">
				<span>RSS 합계</span>
				<strong>{formatBytesValue(visibleMemoryTotal)}</strong>
				<em title={topMemProcess?.command || topMemProcess?.name}>최대 {topMemProcess?.name ?? '-'}</em>
			</div>
		</div>
		<div
			class="state-strip"
			aria-label="프로세스 상태 분포"
			style={`--run:${countShare(runningCount)}%;--wait:${countShare(waitingCount)}%;--blocked:${countShare(blockedCount)}%;--zombie:${countShare(zombieCount)}%;`}
		>
			<span class="run" title={`실행 ${runningCount}개`}></span>
			<span class="wait" title={`대기 ${waitingCount}개`}></span>
			<span class="blocked" title={`I/O·정지 ${blockedCount}개`}></span>
			<span class="zombie" title={`좀비 ${zombieCount}개`}></span>
		</div>
		<div class="process-filter">
			<label>
				<span>검색</span>
				<input
					type="search"
					bind:value={searchQuery}
					placeholder="PID / 이름 / 명령 / UID"
					aria-label="프로세스 검색"
				/>
			</label>
			{#if searchActive}
				<button class="clear-search" onclick={() => (searchQuery = '')}>초기화</button>
			{/if}
		</div>
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="pid">PID</th>
						<th>이름</th>
						<th class="num">CPU%</th>
						<th class="num">RSS</th>
						<th>상태</th>
						<th>UID</th>
						<th>Command</th>
					</tr>
				</thead>
				<tbody>
					{#each visibleProcesses as p (p.pid)}
						{@const st = stateMeta(p.state)}
						<tr>
							<td class="pid mono">{p.pid}</td>
							<td class="mono name">{p.name}</td>
							<td class="num metric-cell">
								<span>{p.cpu_percent.toFixed(1)}</span>
								<i class="row-bar cpu" aria-hidden="true" style={`--row:${rowShare(p.cpu_percent, maxCpu)}%;`}></i>
							</td>
							<td class="num metric-cell">
								<span>{formatBytesValue(p.memory_rss)}</span>
								<i class="row-bar mem" aria-hidden="true" style={`--row:${rowShare(p.memory_rss, maxMemory)}%;`}></i>
							</td>
							<td><span class="badge {st.tone}" title={p.state}>{st.label}</span></td>
							<td class="mono">{p.user}</td>
							<td class="mono cmd">{p.command || p.name}</td>
						</tr>
					{:else}
						<tr>
							<td class="empty-row" colspan="7">
								{searchActive ? '현재 불러온 프로세스 안에서 검색 결과가 없습니다.' : '표시할 프로세스가 없습니다.'}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="footer">
			<span>
				{#if searchActive}
					검색 {visibleProcesses.length}건 · 불러온 {processes.length} / 전체 {total}건
				{:else}
					{processes.length} / {total}건 표시
				{/if}
			</span>
			<div class="footer-actions">
				{#if searchActive && processes.length < total}
					<span class="scope-note">검색은 현재 불러온 {processes.length}건 기준</span>
				{/if}
				{#if reachedSafeLimit}
					<span class="scope-note">부하 방지를 위해 한 번에 최대 100건</span>
				{/if}
				<button onclick={showMore} disabled={loading || !canLoadMore}>
					{limit < 50 ? '50개 보기' : '100개 보기'}
				</button>
			</div>
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
		font-size: 15px;
		margin-bottom: 0;
	}
	.panel-header p {
		display: none;
		font-size: 12px;
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
		padding: 3px 6px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-family: inherit;
		font-size: 11px;
		cursor: pointer;
	}

	.refresh {
		padding: 3px 7px;
		border-radius: 7px;
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

	.process-filter {
		display: flex;
		align-items: center;
		gap: 6px;
		margin-bottom: 5px;
		flex: 0 0 auto;
		min-width: 0;
	}

	.process-filter label {
		display: flex;
		align-items: center;
		gap: 6px;
		flex: 1 1 auto;
		min-width: 0;
		padding: 5px 7px;
		border-radius: 8px;
		background: rgba(2, 6, 12, 0.36);
		border: 1px solid rgba(100, 116, 139, 0.16);
	}

	.process-filter span {
		color: var(--text-muted);
		font-size: 10.5px;
		font-weight: 850;
		white-space: nowrap;
	}

	.process-filter input {
		flex: 1 1 auto;
		min-width: 0;
		border: 0;
		outline: none;
		background: transparent;
		color: var(--text-primary);
		font-family: inherit;
		font-size: 12px;
	}

	.process-filter input::placeholder {
		color: rgba(148, 163, 184, 0.62);
	}

	.clear-search,
	.footer-actions button {
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.78);
		color: var(--text-secondary);
		font-family: inherit;
		font-size: 10.5px;
		font-weight: 800;
		cursor: pointer;
		white-space: nowrap;
	}

	.clear-search {
		padding: 5px 7px;
	}

	.clear-search:hover,
	.footer-actions button:hover:not(:disabled) {
		color: var(--accent);
		border-color: rgba(48, 213, 200, 0.38);
	}

	.footer-actions button:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.process-summary {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 4px;
		margin-bottom: 4px;
		flex: 0 0 auto;
	}

	.summary-card {
		min-width: 0;
		min-height: 40px;
		padding: 6px 7px;
		border-radius: 8px;
		background:
			linear-gradient(180deg, rgba(13, 17, 23, 0.72), rgba(8, 12, 19, 0.66)),
			rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(100, 116, 139, 0.16);
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 2px;
	}

	.summary-card span {
		color: var(--text-muted);
		font-size: 9.5px;
		font-weight: 800;
	}

	.summary-card strong {
		color: var(--text-primary);
		font-size: 13px;
		line-height: 1;
		font-weight: 900;
		font-variant-numeric: tabular-nums;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.summary-card em {
		color: var(--text-secondary);
		font-size: 9.5px;
		font-style: normal;
		font-weight: 650;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.state-strip {
		display: flex;
		gap: 2px;
		height: 7px;
		padding: 1px;
		margin-bottom: 4px;
		border-radius: 999px;
		background: rgba(2, 6, 12, 0.62);
		border: 1px solid rgba(100, 116, 139, 0.14);
		flex: 0 0 auto;
	}

	.state-strip span {
		min-width: 0;
		flex: 0 0 auto;
		border-radius: 999px;
	}

	.state-strip .run { width: var(--run, 0%); background: rgba(16, 185, 129, 0.9); }
	.state-strip .wait { width: var(--wait, 0%); background: rgba(100, 116, 139, 0.75); }
	.state-strip .blocked { width: var(--blocked, 0%); background: rgba(234, 179, 8, 0.86); }
	.state-strip .zombie { width: var(--zombie, 0%); background: rgba(239, 68, 68, 0.88); }

	.empty {
		padding: 10px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
		font-size: 12px;
		color: var(--text-secondary);
	}
	.empty.error {
		color: #fecaca;
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(127, 29, 29, 0.18);
	}

	.table-wrap {
		flex: 1 1 158px;
		min-height: 150px;
		min-width: 0;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
		max-height: none;
		overflow: auto;
		position: relative;
		scrollbar-gutter: stable;
		background: rgba(2, 6, 12, 0.28);
		border-radius: 8px;
		border: 1px solid rgba(100, 116, 139, 0.16);
	}

	table {
		width: 100%;
		min-width: 600px;
		table-layout: fixed;
		border-collapse: separate;
		border-spacing: 0;
		font-size: 11.5px;
	}

	thead {
		background: #02060c;
	}

	th {
		position: sticky;
		top: 0;
		z-index: 3;
		text-align: left;
		padding: 4px 6px;
		font-size: 10.5px;
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		border-bottom: 1px solid rgba(31, 41, 55, 0.7);
		background: #02060c;
		box-shadow: 0 1px 0 rgba(31, 41, 55, 0.85);
	}
	th,
	td {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	th:nth-child(1),
	td:nth-child(1) { width: 74px; }
	th:nth-child(2),
	td:nth-child(2) { width: 90px; }
	th:nth-child(3),
	td:nth-child(3) { width: 66px; }
	th:nth-child(4),
	td:nth-child(4) { width: 84px; }
	th:nth-child(5),
	td:nth-child(5) { width: 68px; }
	th:nth-child(6),
	td:nth-child(6) { width: 60px; }
	th.num,
	td.num {
		text-align: right;
	}
	th.pid,
	td.pid {
		text-align: left;
	}

	td {
		padding: 4px 6px;
		border-bottom: 1px solid rgba(31, 41, 55, 0.4);
		color: var(--text-primary);
	}

	.empty-row {
		text-align: center;
		color: var(--text-muted);
		padding: 18px 8px;
	}

	tr:last-child td {
		border-bottom: none;
	}

	tr:hover td {
		background: rgba(48, 213, 200, 0.04);
	}

	.metric-cell {
		position: relative;
		vertical-align: middle;
	}

	.metric-cell > span {
		position: relative;
		z-index: 1;
	}

	.row-bar {
		position: absolute;
		left: 6px;
		right: 6px;
		bottom: 2px;
		height: 2px;
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.22);
		overflow: hidden;
	}

	.row-bar::before {
		content: '';
		display: block;
		width: var(--row, 0%);
		height: 100%;
		border-radius: inherit;
		background: rgba(48, 213, 200, 0.86);
	}

	.row-bar.mem::before {
		background: rgba(96, 165, 250, 0.88);
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
		font-size: 11px;
	}

	.badge {
		display: inline-flex;
		padding: 1px 6px;
		border-radius: 999px;
		font-size: 10.5px;
		font-weight: 700;
	}
	.badge.success { background: rgba(16, 185, 129, 0.18); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); }
	.badge.warn    { background: rgba(234, 179, 8, 0.18);  color: #fde047; border: 1px solid rgba(234, 179, 8, 0.35); }
	.badge.danger  { background: rgba(239, 68, 68, 0.18);  color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.4); }
	.badge.muted   { background: rgba(100, 116, 139, 0.16); color: var(--text-secondary); border: 1px solid rgba(100, 116, 139, 0.32); }

	.footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 6px;
		font-size: 11px;
		color: var(--text-muted);
		margin-top: 5px;
		flex-wrap: wrap;
	}

	.footer-actions {
		display: inline-flex;
		align-items: center;
		justify-content: flex-end;
		gap: 5px;
		margin-left: auto;
		min-width: 0;
	}

	.footer-actions button {
		padding: 3px 7px;
	}

	.scope-note {
		max-width: 150px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
