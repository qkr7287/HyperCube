<script lang="ts">
	import { fleetEventHistory, loadResourceEventHistory } from '$lib/stores/fleet-store';
	import { metricLabel, type FleetEvent } from '$lib/utils/fleet-events';

	let { open = false, onClose }: { open?: boolean; onClose: () => void } = $props();

	let loading = $state(false);

	// 검색 / 컬럼별 필터.
	let search = $state('');
	let filterServer = $state('all');
	let filterMetric = $state('all');
	let filterKind = $state('all');
	let filterSeverity = $state('all');
	let filterStatus = $state('all');

	// 정렬 — 수치·시간·이름 컬럼만 (자원/종류/원인 컨테이너는 필터로 충분).
	type SortKey = 'host' | 'severity' | 'started' | 'duration' | 'peak';
	let sortKey = $state<SortKey>('started');
	let sortDir = $state<'asc' | 'desc'>('desc');

	// 데이터가 적어도 표 형태를 유지하도록 최소 행 수를 빈 행으로 채운다.
	const MIN_ROWS = 24;

	// 모달이 열릴 때마다 백엔드에서 history 를 새로 로드.
	$effect(() => {
		if (open) {
			loading = true;
			loadResourceEventHistory({ limit: 100 }).finally(() => (loading = false));
		}
	});

	let serverOptions = $derived(
		[...new Set($fleetEventHistory.map((e) => e.hostname))].sort(),
	);

	function durationMs(ev: FleetEvent): number {
		return (ev.endedAt ?? Date.now()) - ev.occurredAt;
	}

	function statusOf(ev: FleetEvent): string {
		return ev.isActive ? 'active' : (ev.endedReason ?? 'resolved');
	}

	let viewRows = $derived.by(() => {
		const kw = search.trim().toLowerCase();
		const filtered = $fleetEventHistory.filter((ev) => {
			if (filterServer !== 'all' && ev.hostname !== filterServer) return false;
			if (filterMetric !== 'all' && ev.metric !== filterMetric) return false;
			if (filterKind !== 'all' && ev.kind !== filterKind) return false;
			if (filterSeverity !== 'all' && ev.severity !== filterSeverity) return false;
			if (filterStatus !== 'all' && statusOf(ev) !== filterStatus) return false;
			if (kw) {
				const hay = `${ev.hostname} ${ev.container?.name ?? ''}`.toLowerCase();
				if (!hay.includes(kw)) return false;
			}
			return true;
		});
		const dir = sortDir === 'asc' ? 1 : -1;
		return [...filtered].sort((a, b) => {
			let cmp = 0;
			switch (sortKey) {
				case 'host':
					cmp = a.hostname.localeCompare(b.hostname);
					break;
				case 'severity':
					cmp = (a.severity === 'critical' ? 1 : 0) - (b.severity === 'critical' ? 1 : 0);
					break;
				case 'started':
					cmp = a.occurredAt - b.occurredAt;
					break;
				case 'duration':
					cmp = durationMs(a) - durationMs(b);
					break;
				case 'peak':
					cmp = a.peakValue - b.peakValue;
					break;
			}
			return cmp * dir;
		});
	});

	let emptyRows = $derived(Math.max(0, MIN_ROWS - viewRows.length));

	function toggleSort(key: SortKey) {
		if (sortKey === key) {
			sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		} else {
			sortKey = key;
			sortDir = key === 'host' ? 'asc' : 'desc';
		}
	}

	function sortArrow(key: SortKey): string {
		if (sortKey !== key) return '';
		return sortDir === 'asc' ? ' ▲' : ' ▼';
	}

	function fmtDateTime(ms: number): string {
		return new Date(ms).toLocaleString('ko-KR', {
			month: '2-digit',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit',
		});
	}

	function fmtDuration(ev: FleetEvent): string {
		const sec = Math.max(0, Math.floor(durationMs(ev) / 1000));
		if (sec < 60) return `${sec}초`;
		if (sec < 3600) return `${Math.floor(sec / 60)}분`;
		if (sec < 86400) {
			const h = Math.floor(sec / 3600);
			const m = Math.floor((sec % 3600) / 60);
			return m > 0 ? `${h}시간 ${m}분` : `${h}시간`;
		}
		return `${Math.floor(sec / 86400)}일`;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}
</script>

<svelte:window onkeydown={open ? onKeydown : undefined} />

{#if open}
	<div class="modal-overlay" role="presentation" onclick={onClose}>
		<div
			class="modal-card"
			role="dialog"
			aria-modal="true"
			aria-label="서버 자원 이벤트 기록"
			onclick={(e) => e.stopPropagation()}
		>
			<header class="modal-head">
				<div class="head-title">
					<h2>서버 자원 이벤트 기록</h2>
					<p>임계 초과·자원 급증 이벤트의 전체 이력 (최근 100건). 진행 중·해소·확인 포함.</p>
				</div>
				<button class="modal-close" type="button" onclick={onClose} aria-label="닫기">×</button>
			</header>

			<div class="modal-toolbar">
				<input
					class="tb-search"
					type="search"
					placeholder="서버·컨테이너 검색"
					bind:value={search}
				/>
				<select class="tb-select" bind:value={filterServer} aria-label="서버 필터">
					<option value="all">전체 서버</option>
					{#each serverOptions as host (host)}
						<option value={host}>{host}</option>
					{/each}
				</select>
				<select class="tb-select" bind:value={filterMetric} aria-label="자원 필터">
					<option value="all">전체 자원</option>
					<option value="cpu">CPU</option>
					<option value="memory">메모리</option>
					<option value="disk">디스크</option>
					<option value="gpu">GPU</option>
				</select>
				<select class="tb-select" bind:value={filterKind} aria-label="종류 필터">
					<option value="all">전체 종류</option>
					<option value="threshold">임계</option>
					<option value="spike">급증</option>
				</select>
				<select class="tb-select" bind:value={filterSeverity} aria-label="심각도 필터">
					<option value="all">전체 심각도</option>
					<option value="critical">위험</option>
					<option value="warning">주의</option>
				</select>
				<select class="tb-select" bind:value={filterStatus} aria-label="상태 필터">
					<option value="all">전체 상태</option>
					<option value="active">진행 중</option>
					<option value="resolved">해소됨</option>
					<option value="acknowledged">확인됨</option>
				</select>
				<span class="tb-count">{viewRows.length}건</span>
			</div>

			<div class="modal-body">
				{#if loading}
					<div class="modal-msg">불러오는 중…</div>
				{:else}
					<table class="hist-table">
						<thead>
							<tr>
								<th><button class="th-sort" type="button" onclick={() => toggleSort('host')}>서버{sortArrow('host')}</button></th>
								<th>자원</th>
								<th>종류</th>
								<th><button class="th-sort" type="button" onclick={() => toggleSort('severity')}>심각도{sortArrow('severity')}</button></th>
								<th><button class="th-sort" type="button" onclick={() => toggleSort('started')}>시작{sortArrow('started')}</button></th>
								<th><button class="th-sort" type="button" onclick={() => toggleSort('duration')}>지속{sortArrow('duration')}</button></th>
								<th><button class="th-sort" type="button" onclick={() => toggleSort('peak')}>최고치{sortArrow('peak')}</button></th>
								<th>원인 컨테이너</th>
								<th>상태</th>
							</tr>
						</thead>
						<tbody>
							{#each viewRows as ev (ev.id)}
								<tr class:row-critical={ev.severity === 'critical'}>
									<td class="td-host">{ev.hostname}</td>
									<td>{metricLabel(ev.metric)}</td>
									<td>{ev.kind === 'spike' ? '급증' : '임계'}</td>
									<td>
										<span class="sev sev-{ev.severity}">
											{ev.severity === 'critical' ? '위험' : '주의'}
										</span>
									</td>
									<td class="td-time">{fmtDateTime(ev.occurredAt)}</td>
									<td class="td-time">{fmtDuration(ev)}</td>
									<td class="td-num">
										{Math.round(ev.peakValue)}%{#if ev.kind === 'spike' && ev.delta != null}<span class="dim"> (+{Math.round(ev.delta)}%p)</span>{/if}
									</td>
									<td class="td-cont">
										{#if ev.container}
											📦 {ev.container.name} {Math.round(ev.container.value)}%
										{:else}
											<span class="dim">—</span>
										{/if}
									</td>
									<td>
										{#if ev.isActive}
											<span class="st st-active">진행 중</span>
										{:else if ev.endedReason === 'acknowledged'}
											<span class="st st-ack">확인됨</span>
										{:else}
											<span class="st st-resolved">해소됨</span>
										{/if}
									</td>
								</tr>
							{/each}
							{#each Array(emptyRows) as _, i (i)}
								<tr class="empty-row"><td colspan="9"></td></tr>
							{/each}
						</tbody>
					</table>
					{#if viewRows.length === 0}
						<div class="empty-overlay">
							{$fleetEventHistory.length === 0
								? '기록된 자원 이벤트가 없습니다.'
								: '검색·필터 조건에 맞는 이벤트가 없습니다.'}
						</div>
					{/if}
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.modal-overlay {
		position: fixed;
		inset: 0;
		z-index: 1000;
		display: grid;
		place-items: center;
		padding: 24px;
		background: rgba(0, 0, 0, 0.6);
		backdrop-filter: blur(2px);
	}
	.modal-card {
		width: min(1040px, 100%);
		height: 86vh;
		display: flex;
		flex-direction: column;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		box-shadow: 0 24px 60px -20px rgba(0, 0, 0, 0.7);
		overflow: hidden;
	}
	.modal-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
		padding: 16px 22px;
		border-bottom: 1px solid var(--border);
	}
	.head-title h2 {
		margin: 0;
		font-size: 15px;
		font-weight: 800;
		color: var(--text-primary);
	}
	.head-title p {
		margin: 4px 0 0;
		font-size: 11.5px;
		font-weight: 600;
		color: var(--text-muted);
	}
	.modal-close {
		flex: 0 0 auto;
		width: 28px;
		height: 28px;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text-secondary);
		font-size: 18px;
		line-height: 1;
		cursor: pointer;
	}
	.modal-close:hover {
		color: var(--text-primary);
		border-color: var(--accent);
	}

	/* 검색·필터 toolbar */
	.modal-toolbar {
		flex: 0 0 auto;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 7px;
		padding: 11px 22px;
		border-bottom: 1px solid var(--border);
	}
	.tb-search,
	.tb-select {
		height: 30px;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: rgba(13, 17, 23, 0.5);
		color: var(--text-primary);
		font: inherit;
		font-size: 12px;
		font-weight: 600;
	}
	.tb-search {
		flex: 1 1 200px;
		min-width: 160px;
		padding: 0 10px;
	}
	.tb-select {
		padding: 0 8px;
		cursor: pointer;
	}
	.tb-search:focus,
	.tb-select:focus {
		outline: none;
		border-color: var(--accent);
	}
	.tb-count {
		margin-left: auto;
		color: var(--text-muted);
		font-size: 11.5px;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	/* modal-body 는 스크롤하지 않는다 — 스크롤은 tbody 가 담당해
	   스크롤바가 헤더(thead) 아래에서 시작하게 한다. */
	.modal-body {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		padding: 0 22px 16px;
		display: flex;
		position: relative;
	}
	.modal-msg {
		margin: auto;
		padding: 48px 0;
		text-align: center;
		color: var(--text-muted);
		font-size: 13px;
		font-weight: 600;
	}
	.empty-overlay {
		position: absolute;
		left: 0;
		right: 0;
		top: 90px;
		text-align: center;
		color: var(--text-muted);
		font-size: 13px;
		font-weight: 600;
		pointer-events: none;
	}

	/* 표를 flex 컬럼으로 — thead 는 고정, tbody 만 스크롤. */
	.hist-table {
		width: 100%;
		display: flex;
		flex-direction: column;
		font-size: 12.5px;
	}
	.hist-table thead {
		display: block;
		flex: 0 0 auto;
	}
	.hist-table tbody {
		display: block;
		flex: 1 1 0;
		min-height: 0;
		overflow-y: auto;
	}
	.hist-table thead tr,
	.hist-table tbody tr {
		display: table;
		width: 100%;
		table-layout: fixed;
	}
	.hist-table th:nth-child(1), .hist-table td:nth-child(1) { width: 15%; }
	.hist-table th:nth-child(2), .hist-table td:nth-child(2) { width: 8%; }
	.hist-table th:nth-child(3), .hist-table td:nth-child(3) { width: 7%; }
	.hist-table th:nth-child(4), .hist-table td:nth-child(4) { width: 9%; }
	.hist-table th:nth-child(5), .hist-table td:nth-child(5) { width: 13%; }
	.hist-table th:nth-child(6), .hist-table td:nth-child(6) { width: 11%; }
	.hist-table th:nth-child(7), .hist-table td:nth-child(7) { width: 11%; }
	.hist-table th:nth-child(8), .hist-table td:nth-child(8) { width: 16%; }
	.hist-table th:nth-child(9), .hist-table td:nth-child(9) { width: 10%; }
	.hist-table th {
		padding: 11px 12px 9px;
		text-align: center;
		color: var(--text-muted);
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.3px;
		border-bottom: 1px solid var(--border);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.th-sort {
		border: none;
		background: none;
		color: inherit;
		font: inherit;
		letter-spacing: inherit;
		cursor: pointer;
		padding: 2px 4px;
		border-radius: 4px;
		white-space: nowrap;
	}
	.th-sort:hover {
		color: var(--text-primary);
		background: rgba(148, 163, 184, 0.1);
	}
	.hist-table td {
		padding: 8px 12px;
		text-align: center;
		color: var(--text-secondary);
		border-bottom: 1px solid rgba(148, 163, 184, 0.1);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.hist-table tbody tr:not(.empty-row):hover td {
		background: rgba(148, 163, 184, 0.06);
	}
	.empty-row td {
		height: 32px;
		border-bottom: 1px solid rgba(148, 163, 184, 0.05);
	}
	.row-critical td:first-child {
		box-shadow: inset 3px 0 0 #f87171;
	}
	.td-host {
		color: var(--text-primary);
		font-weight: 700;
	}
	.td-time {
		font-variant-numeric: tabular-nums;
	}
	.td-num {
		font-variant-numeric: tabular-nums;
		color: var(--text-primary);
		font-weight: 700;
	}
	.dim {
		color: var(--text-muted);
		font-weight: 600;
	}
	.sev {
		display: inline-block;
		padding: 1px 7px;
		border-radius: var(--radius-full);
		font-size: 10.5px;
		font-weight: 800;
	}
	.sev-critical {
		color: #fca5a5;
		background: rgba(248, 113, 113, 0.16);
	}
	.sev-warning {
		color: #fcd34d;
		background: rgba(251, 191, 36, 0.16);
	}
	.st {
		display: inline-block;
		padding: 1px 7px;
		border-radius: var(--radius-full);
		font-size: 10.5px;
		font-weight: 800;
	}
	.st-active {
		color: #fca5a5;
		background: rgba(248, 113, 113, 0.16);
	}
	.st-ack {
		color: #93c5fd;
		background: rgba(96, 165, 250, 0.16);
	}
	.st-resolved {
		color: #6ee7b7;
		background: rgba(52, 211, 153, 0.14);
	}
</style>
