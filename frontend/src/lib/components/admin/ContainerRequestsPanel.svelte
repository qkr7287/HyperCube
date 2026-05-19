<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';
	import { statusEvents, pendingRequestCount } from '$lib/stores/global-events';
	import RequestDetailModal from '$lib/components/RequestDetailModal.svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';

	type RequestRow = {
		id: string;
		requester_username: string;
		action: 'create' | 'delete';
		status: string;
		template_name?: string | null;
		target_agent_hostname?: string | null;
		target_container_name?: string | null;
		custom_name?: string;
		created_at: string;
		[k: string]: any;
	};

	let filter = $state<'pending' | 'all'>('pending');
	let requests = $state<RequestRow[]>([]);
	let loading = $state(false);
	let errorMsg = $state('');
	let selected = $state<RequestRow | null>(null);
	let processingId = $state('');
	let search = $state('');
	type SortField = 'requester' | 'action' | 'template' | 'agent' | 'name' | 'status' | 'created_at';
	let sortField = $state<SortField>('created_at');
	let sortDir = $state<'asc' | 'desc'>('desc');

	function setSort(f: SortField) {
		if (sortField === f) sortDir = sortDir === 'asc' ? 'desc' : 'asc';
		else { sortField = f; sortDir = f === 'created_at' ? 'desc' : 'asc'; }
	}

	let filteredRequests = $derived.by(() => {
		const q = search.trim().toLowerCase();
		const filtered = q
			? requests.filter((r) => {
					const hay = `${r.requester_username} ${r.template_name ?? ''} ${r.target_agent_hostname ?? ''} ${r.custom_name ?? ''} ${r.target_container_name ?? ''}`.toLowerCase();
					return hay.includes(q);
				})
			: requests.slice();
		const dir = sortDir === 'asc' ? 1 : -1;
		return filtered.sort((a, b) => {
			switch (sortField) {
				case 'requester': return (a.requester_username || '').localeCompare(b.requester_username || '') * dir;
				case 'action': return (a.action || '').localeCompare(b.action || '') * dir;
				case 'template': return (a.template_name || '').localeCompare(b.template_name || '') * dir;
				case 'agent': return (a.target_agent_hostname || '').localeCompare(b.target_agent_hostname || '') * dir;
				case 'name': return ((a.custom_name || a.target_container_name || '') as string).localeCompare((b.custom_name || b.target_container_name || '') as string) * dir;
				case 'status': return (a.status || '').localeCompare(b.status || '') * dir;
				case 'created_at':
				default:
					return (new Date(a.created_at).getTime() - new Date(b.created_at).getTime()) * dir;
			}
		});
	});

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
			const params = new URLSearchParams();
			if (filter === 'pending') params.set('status', 'pending');
			params.set('page_size', '100');
			params.set('ordering', '-created_at');
			const res = await fetch(`${base}/api/requests/?${params.toString()}`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (!res.ok) {
				errorMsg = `HTTP ${res.status}`;
				return;
			}
			const json = await res.json();
			requests = json.data?.results ?? [];
			// pending count 동기화
			if (filter === 'pending') pendingRequestCount.set(json.data?.count ?? 0);
		} catch (e: any) {
			errorMsg = e?.message || '로드 실패';
		} finally {
			loading = false;
		}
	}

	async function approveAction(id: string, note: string) {
		const t = token();
		if (!t) throw new Error('no token');
		const res = await fetch(`${base}/api/requests/${id}/approve/`, {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${t}`,
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ note }),
		});
		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			throw new Error(body?.error?.detail || body?.detail || `HTTP ${res.status}`);
		}
		await load();
	}

	async function rejectAction(id: string, note: string) {
		const t = token();
		if (!t) throw new Error('no token');
		const res = await fetch(`${base}/api/requests/${id}/reject/`, {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${t}`,
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ note }),
		});
		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			throw new Error(body?.error?.detail || body?.detail || `HTTP ${res.status}`);
		}
		await load();
	}

	// WS 이벤트가 들어오면 목록 갱신. statusEvents는 agent online/offline용이지만
	// global-events store는 이미 request_created/request_status_change 이벤트 수신 시
	// pendingRequestCount를 갱신한다. pendingRequestCount 변화를 신호로 삼아 refresh.
	let lastSeenCount = 0;
	const unsub = pendingRequestCount.subscribe((n) => {
		if (n !== lastSeenCount) {
			lastSeenCount = n;
			load();
		}
	});

	onMount(load);
	onDestroy(unsub);

	function onFilterChange() {
		load();
	}

	function statusColor(s?: string): string {
		return ({
			pending: '#f59e0b',
			approved: '#3b82f6',
			deploying: '#8b5cf6',
			deployed: '#22c55e',
			failed: '#ef4444',
			rejected: '#6b7280',
		} as any)[s ?? ''] ?? '#6b7280';
	}

	function statusLabel(s?: string): string {
		return ({
			pending: '대기중',
			approved: '승인됨',
			deploying: '배포중',
			deployed: '완료',
			failed: '실패',
			rejected: '반려됨',
		} as any)[s ?? ''] ?? s ?? '-';
	}

	function relativeTime(iso: string): string {
		try {
			const d = new Date(iso);
			const diff = Math.floor((Date.now() - d.getTime()) / 1000);
			if (diff < 60) return `${diff}초 전`;
			if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
			if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
			return `${Math.floor(diff / 86400)}일 전`;
		} catch {
			return iso;
		}
	}
</script>

<div class="page">
	<div class="page-header">
		<div>
			<h1>컨테이너 요청 <InfoTooltip text={"일반 사용자가 \"이 컨테이너를 만들어 주세요\" 또는 \"이 컨테이너를 지워 주세요\"라고 보낸 신청을 관리자가 검토하는 화면입니다.\n\n• 승인하면 해당 서버에서 실제로 컨테이너 생성/삭제가 진행됩니다.\n• 반려하면 사용자에게 사유와 함께 거절됩니다.\n• 처리 결과는 사용자 화면에서도 즉시 확인됩니다."} placement="bottom-start" /></h1>
			<p class="subtitle">사용자가 제출한 컨테이너 생성/삭제 요청을 검토합니다.</p>
		</div>
		<div class="controls">
			<input
				class="search-input"
				type="search"
				bind:value={search}
				placeholder="검색 (제출자·템플릿·서버·이름)"
			/>
			<div class="filter-group">
				<button
					class="filter-btn"
					class:active={filter === 'pending'}
					onclick={() => { filter = 'pending'; onFilterChange(); }}
				>대기중만</button>
				<button
					class="filter-btn"
					class:active={filter === 'all'}
					onclick={() => { filter = 'all'; onFilterChange(); }}
				>전체</button>
			</div>
			<button class="refresh-btn" onclick={load} disabled={loading}>
				{loading ? '불러오는 중...' : '↻ 새로고침'}
			</button>
		</div>
	</div>

	{#if errorMsg}
		<div class="error-box">요청 목록을 불러오지 못했습니다: {errorMsg}</div>
	{/if}

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th class="col-user sortable" class:active={sortField === 'requester'} onclick={() => setSort('requester')}>
						제출자{sortField === 'requester' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-action sortable" class:active={sortField === 'action'} onclick={() => setSort('action')}>
						타입{sortField === 'action' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-template sortable" class:active={sortField === 'template'} onclick={() => setSort('template')}>
						템플릿{sortField === 'template' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-agent sortable" class:active={sortField === 'agent'} onclick={() => setSort('agent')}>
						대상 서버{sortField === 'agent' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-name sortable" class:active={sortField === 'name'} onclick={() => setSort('name')}>
						이름{sortField === 'name' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-status sortable" class:active={sortField === 'status'} onclick={() => setSort('status')}>
						상태{sortField === 'status' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-time sortable" class:active={sortField === 'created_at'} onclick={() => setSort('created_at')}>
						제출{sortField === 'created_at' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-detail">상세</th>
					<th class="col-review">검토</th>
				</tr>
			</thead>
			<tbody>
				{#if !loading && filteredRequests.length === 0}
					<tr class="empty-row">
						<td colspan="8">
							<div class="empty-inline">
								<div class="empty-icon">📭</div>
								<div class="empty-text">
									{search.trim() ? '검색 결과가 없습니다.' : (filter === 'pending' ? '대기 중인 요청이 없습니다.' : '요청 이력이 없습니다.')}
								</div>
							</div>
						</td>
					</tr>
				{:else}
					{#each filteredRequests as req (req.id)}
						<tr>
							<td class="col-user dim">{req.requester_username}</td>
							<td class="col-action">
								<span class="action-tag" class:delete={req.action === 'delete'}>
									{req.action === 'create' ? '생성' : '삭제'}
								</span>
							</td>
							<td><span class="cell-strong" title={req.template_name ?? '-'}>{req.template_name ?? '-'}</span></td>
							<td class="dim">{req.target_agent_hostname ?? '-'}</td>
							<td><span class="cell-strong" title={req.custom_name || req.target_container_name || '-'}>{req.custom_name || req.target_container_name || '-'}</span></td>
							<td class="col-status">
								<span class="status-pill" data-status={req.status} style="--tone: {statusColor(req.status)};">
									{statusLabel(req.status)}
								</span>
							</td>
							<td class="col-time dim">{relativeTime(req.created_at)}</td>
							<td class="col-detail">
								<button class="detail-btn" onclick={() => selected = req}>상세</button>
							</td>
							<td class="col-review">
								{#if req.status === 'pending'}
									<div class="row-actions">
										<button
											class="approve-btn"
											disabled={!!processingId}
											onclick={async (e) => { e.stopPropagation(); processingId = req.id; try { await approveAction(req.id, ''); } catch (err: any) { errorMsg = err?.message || '승인 실패'; } finally { processingId = ''; } }}
										>{processingId === req.id ? '…' : '승인'}</button>
										<button
											class="reject-btn"
											disabled={!!processingId}
											onclick={async (e) => { e.stopPropagation(); const note = window.prompt('반려 사유를 입력하세요.', ''); if (note === null) return; processingId = req.id; try { await rejectAction(req.id, note); } catch (err: any) { errorMsg = err?.message || '반려 실패'; } finally { processingId = ''; } }}
										>반려</button>
									</div>
								{:else}
									<span class="dim">{req.reviewer_username || '—'}</span>
								{/if}
							</td>
						</tr>
					{/each}
				{/if}
			</tbody>
		</table>
	</div>
</div>

<RequestDetailModal
	request={selected}
	onClose={() => selected = null}
	onApprove={approveAction}
	onReject={rejectAction}
/>

<style>
	/* Shared chrome (.page / .page-header / h1 / .subtitle / .controls /
	   .filter-group / .filter-btn / .refresh-btn / .error-box / .empty /
	   .table-wrap / table / thead / tbody) is defined in admin layout
	   :global(). Panel only owns its own row decorations. */
	.dim { color: var(--text-muted); font-size: 11px; }

	.table-wrap :global(table) {
		min-width: 1080px;
		table-layout: fixed;
	}
	.table-wrap :global(tbody tr) {
		height: 46px;
	}
	.table-wrap :global(tbody td) {
		vertical-align: middle !important;
		padding: 6px 10px !important;
	}

	.action-tag {
		display: inline-block; padding: 2px 8px; border-radius: 4px;
		background: rgba(48, 213, 200, 0.15); color: var(--accent);
		font-size: 11px; font-weight: 700; white-space: nowrap;
	}
	.action-tag.delete {
		background: rgba(239, 68, 68, 0.15); color: var(--error);
	}
	.status-pill {
		display: inline-block;
		padding: 3px 10px;
		border-radius: 999px;
		color: var(--tone);
		background: color-mix(in srgb, var(--tone) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--tone) 38%, transparent);
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.02em;
		white-space: nowrap;
	}
	.detail-btn {
		background: var(--bg-tab); border: 1px solid var(--border);
		color: var(--text-primary); padding: 4px 10px; font-size: 11px;
		font-weight: 700;
		border-radius: var(--radius-sm); cursor: pointer; font-family: inherit;
		white-space: nowrap;
	}
	.detail-btn:hover { border-color: var(--accent); color: var(--accent); }

	.table-wrap :global(tbody td) { text-align: center !important; }
	.table-wrap :global(thead th) { text-align: center !important; }

	.cell-strong {
		display: block;
		font-weight: 700;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.search-input {
		font: inherit;
		font-size: 12px;
		padding: 6px 10px;
		min-width: 220px;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--bg-base);
		color: var(--text-primary);
	}
	.search-input:focus {
		outline: none;
		border-color: var(--accent);
	}

	.table-wrap :global(thead th.sortable) {
		cursor: pointer;
		user-select: none;
	}
	.table-wrap :global(thead th.sortable:hover) {
		color: var(--text-primary);
	}
	.table-wrap :global(thead th.sortable.active) {
		color: var(--accent);
	}

	.col-user { width: 110px; }
	.col-action { width: 70px; text-align: center; }
	.col-template { width: 260px; }
	.col-agent { width: 160px; }
	.col-name { width: auto; } /* fills slack */
	.col-status { width: 80px; text-align: center; }
	.col-time { width: 110px; white-space: nowrap; }
	.col-detail { width: 70px; }
	.col-review { width: 140px; }
	.row-actions {
		display: inline-flex;
		gap: 4px;
		justify-content: center;
	}
	.approve-btn, .reject-btn {
		font: inherit;
		font-size: 11px;
		font-weight: 700;
		padding: 4px 10px;
		border-radius: var(--radius-sm);
		cursor: pointer;
		white-space: nowrap;
	}
	.approve-btn {
		color: #86efac;
		background: rgba(34, 197, 94, 0.10);
		border: 1px solid rgba(34, 197, 94, 0.40);
	}
	.approve-btn:hover:not(:disabled) {
		background: rgba(34, 197, 94, 0.18);
		border-color: rgba(34, 197, 94, 0.65);
	}
	.reject-btn {
		color: #fca5a5;
		background: rgba(239, 68, 68, 0.10);
		border: 1px solid rgba(239, 68, 68, 0.40);
	}
	.reject-btn:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.18);
		border-color: rgba(239, 68, 68, 0.65);
	}
	.approve-btn:disabled, .reject-btn:disabled { opacity: 0.5; cursor: not-allowed; }
	.col-status :global(.status-pill) { min-width: 56px; text-align: center; }
	.col-action :global(.action-tag) { min-width: 38px; text-align: center; }
</style>
