<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import ModelRequestDetailModal from '$lib/components/ModelRequestDetailModal.svelte';

	type ModelUploadRequest = {
		id: string;
		requester_username: string;
		reviewer_username?: string | null;
		name: string;
		slug?: string;
		description?: string;
		framework?: string;
		task?: string;
		version: string;
		template_name?: string;
		base_image: string;
		requires_gpu: boolean;
		min_memory_mb: number;
		min_workspace_gb: number;
		original_filename: string;
		size_bytes: number;
		sha256: string;
		status: string;
		review_note?: string;
		created_template_name?: string | null;
		created_at: string;
		reviewed_at?: string | null;
	};

	let filter = $state<'pending' | 'all'>('pending');
	let requests = $state<ModelUploadRequest[]>([]);
	let loading = $state(false);
	let processingId = $state('');
	let errorMsg = $state('');
	let search = $state('');
	let selected = $state<ModelUploadRequest | null>(null);
	type SortField = 'requester' | 'name' | 'file' | 'template' | 'status' | 'created_at';
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
					const hay = `${r.requester_username} ${r.name} ${r.original_filename ?? ''} ${r.template_name ?? ''} ${r.created_template_name ?? ''} ${r.framework ?? ''}`.toLowerCase();
					return hay.includes(q);
				})
			: requests.slice();
		const dir = sortDir === 'asc' ? 1 : -1;
		return filtered.sort((a, b) => {
			switch (sortField) {
				case 'requester': return (a.requester_username || '').localeCompare(b.requester_username || '') * dir;
				case 'name': return (a.name || '').localeCompare(b.name || '') * dir;
				case 'file': return (a.original_filename || '').localeCompare(b.original_filename || '') * dir;
				case 'template': return ((a.created_template_name || a.template_name || '') as string).localeCompare((b.created_template_name || b.template_name || '') as string) * dir;
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
			const res = await fetch(`${base}/api/model-upload-requests/?${params.toString()}`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || `HTTP ${res.status}`);
			requests = json.data?.results ?? [];
		} catch (error: any) {
			errorMsg = error?.message || '모델 요청을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	async function review(id: string, action: 'approve' | 'reject', note = '') {
		const t = token();
		if (!t || processingId) return;
		processingId = id;
		errorMsg = '';
		try {
			const res = await fetch(`${base}/api/model-upload-requests/${id}/${action}/`, {
				method: 'POST',
				headers: {
					Authorization: `Bearer ${t}`,
					'Content-Type': 'application/json',
				},
				body: JSON.stringify({ note }),
			});
			const json = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(json?.detail || json?.error?.detail || `HTTP ${res.status}`);
			await load();
		} catch (error: any) {
			errorMsg = error?.message || '요청 처리에 실패했습니다.';
		} finally {
			processingId = '';
		}
	}

	async function reject(row: ModelUploadRequest) {
		const note = window.prompt('반려 사유를 입력하세요.', row.review_note || '');
		if (note === null) return;
		await review(row.id, 'reject', note);
	}

	async function approveFromModal(id: string, note: string) {
		await review(id, 'approve', note);
	}
	async function rejectFromModal(id: string, note: string) {
		await review(id, 'reject', note);
	}

	function onFilterChange(next: 'pending' | 'all') {
		filter = next;
		load();
	}

	function statusLabel(status: string): string {
		return (
			{
				pending: '대기',
				approved: '승인',
				rejected: '반려',
				failed: '실패',
			} as Record<string, string>
		)[status] ?? status;
	}

	function statusTone(status: string): string {
		return (
			{
				pending: '#f59e0b',
				approved: '#22c55e',
				rejected: '#6b7280',
				failed: '#ef4444',
			} as Record<string, string>
		)[status] ?? '#64748b';
	}

	function formatBytes(bytes?: number): string {
		const value = Number(bytes || 0);
		if (value >= 1024 * 1024 * 1024) return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
		if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(2)} MB`;
		if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
		return `${value} B`;
	}

	function formatTime(iso?: string | null): string {
		if (!iso) return '-';
		try {
			return new Date(iso).toLocaleString('ko-KR');
		} catch {
			return iso;
		}
	}

	onMount(load);
</script>

<div class="page">
	<div class="page-header">
		<div>
			<h1>모델 등록 요청 <InfoTooltip text={"일반 사용자가 \"이 모델 파일을 공유 모델로 등록해 주세요\"라고 보낸 업로드 신청을 관리자가 검토하는 화면입니다.\n\n• 승인하면 ModelAsset + ModelVersion + ContainerTemplate이 한 번에 만들어져 모든 사용자가 공유 카탈로그에서 바로 선택할 수 있습니다.\n• 반려하면 사용자에게 사유와 함께 거절됩니다."} placement="bottom-start" /></h1>
			<p class="subtitle">사용자가 브라우저로 업로드한 모델 파일을 검토하고 공유 모델/컨테이너 템플릿으로 등록합니다.</p>
		</div>
		<div class="controls">
			<input
				class="search-input"
				type="search"
				bind:value={search}
				placeholder="검색 (제출자·모델·파일·템플릿)"
			/>
			<div class="filter-group">
				<button
					class="filter-btn"
					class:active={filter === 'pending'}
					onclick={() => onFilterChange('pending')}
				>대기중만</button>
				<button
					class="filter-btn"
					class:active={filter === 'all'}
					onclick={() => onFilterChange('all')}
				>전체</button>
			</div>
			<button class="refresh-btn" onclick={load} disabled={loading}>
				{loading ? '불러오는 중...' : '↻ 새로고침'}
			</button>
		</div>
	</div>

	{#if errorMsg}
		<div class="error-box">{errorMsg}</div>
	{/if}

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th class="col-user sortable" class:active={sortField === 'requester'} onclick={() => setSort('requester')}>
						제출자{sortField === 'requester' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-model sortable" class:active={sortField === 'name'} onclick={() => setSort('name')}>
						모델{sortField === 'name' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-file sortable" class:active={sortField === 'file'} onclick={() => setSort('file')}>
						파일{sortField === 'file' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-template sortable" class:active={sortField === 'template'} onclick={() => setSort('template')}>
						생성 템플릿{sortField === 'template' ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
					</th>
					<th class="col-spec">실행 조건</th>
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
									{search.trim() ? '검색 결과가 없습니다.' : (filter === 'pending' ? '대기 중인 모델 등록 요청이 없습니다.' : '모델 등록 요청 이력이 없습니다.')}
								</div>
							</div>
						</td>
					</tr>
				{:else}
					{#each filteredRequests as req (req.id)}
						<tr>
							<td class="col-user">{req.requester_username}</td>
							<td class="col-model cell-stack">
								<strong>{req.name}</strong>
								<em>{req.version}{req.framework ? ` · ${req.framework}` : ''}{req.task ? ` · ${req.task}` : ''}</em>
							</td>
							<td class="col-file cell-stack">
								<strong title={req.original_filename}>{req.original_filename || '-'}</strong>
								<em>{formatBytes(req.size_bytes)}{req.sha256 ? ` · ${req.sha256.slice(0, 8)}` : ''}</em>
							</td>
							<td class="col-template cell-stack">
								<strong title={req.created_template_name || req.template_name || '-'}>{req.created_template_name || req.template_name || '-'}</strong>
								<em title={req.base_image}>{req.base_image}</em>
							</td>
							<td class="col-spec dim">
								{req.requires_gpu ? 'GPU' : 'CPU'} · {req.min_memory_mb}MB · {req.min_workspace_gb}GB
							</td>
							<td class="col-status">
								<span class="status-pill" data-status={req.status} style="--tone: {statusTone(req.status)};">
									{statusLabel(req.status)}
								</span>
							</td>
							<td class="col-time dim">{formatTime(req.created_at)}</td>
							<td class="col-detail">
								<button class="detail-btn" onclick={() => selected = req}>상세</button>
							</td>
							<td class="col-review">
								{#if req.status === 'pending'}
									<div class="row-actions">
										<button
											class="approve-btn"
											disabled={!!processingId}
											onclick={(e) => { e.stopPropagation(); review(req.id, 'approve', ''); }}
										>{processingId === req.id ? '…' : '승인'}</button>
										<button
											class="reject-btn"
											disabled={!!processingId}
											onclick={(e) => { e.stopPropagation(); reject(req); }}
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

<ModelRequestDetailModal
	request={selected}
	onClose={() => selected = null}
	onApprove={approveFromModal}
	onReject={rejectFromModal}
/>

<style>
	/* Shared chrome via admin layout :global(). Panel keeps only its own
	   row-cell layouts and approve/reject button colors. */
	.approve-btn:disabled,
	.reject-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.table-wrap :global(table) {
		min-width: 1100px;
		table-layout: fixed;
	}
	.table-wrap :global(tbody) {
		display: table-row-group;
	}
	.table-wrap :global(tbody tr) {
		height: 50px;
	}
	.table-wrap :global(tbody td) {
		vertical-align: middle !important;
		padding: 6px 10px !important;
	}
	.cell-stack {
		min-width: 0;
		max-width: 100%;
		line-height: 1.25;
	}
	.cell-stack strong {
		display: block;
		font-size: 12.5px;
		font-weight: 800;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.cell-stack em {
		display: block;
		font-style: normal;
		color: var(--text-muted);
		font-size: 10.5px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.dim {
		color: var(--text-muted);
		font-size: 11px;
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
		font: inherit;
		font-size: 11px;
		font-weight: 700;
		padding: 4px 10px;
		color: var(--text-primary);
		background: var(--bg-tab);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		cursor: pointer;
		white-space: nowrap;
	}
	.detail-btn:hover { border-color: var(--accent); color: var(--accent); }

	.table-wrap :global(tbody td) { text-align: center !important; }
	.table-wrap :global(thead th) { text-align: center !important; }
	.actions {
		display: flex;
		gap: 6px;
		justify-content: flex-end;
		align-items: center;
	}
	.approve-btn,
	.reject-btn {
		border: 1px solid var(--border);
		padding: 5px 10px;
		font-size: 11px;
		border-radius: var(--radius-sm);
		cursor: pointer;
		font-family: inherit;
		white-space: nowrap;
	}
	.approve-btn {
		background: rgba(34, 197, 94, 0.16);
		border-color: rgba(34, 197, 94, 0.42);
		color: #86efac;
	}
	.reject-btn {
		background: rgba(239, 68, 68, 0.12);
		border-color: rgba(239, 68, 68, 0.36);
		color: #fca5a5;
	}
	.search-input {
		font: inherit;
		font-size: 12px;
		padding: 6px 10px;
		min-width: 240px;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--bg-base);
		color: var(--text-primary);
	}
	.search-input:focus { outline: none; border-color: var(--accent); }

	.table-wrap :global(thead th.sortable) { cursor: pointer; user-select: none; }
	.table-wrap :global(thead th.sortable:hover) { color: var(--text-primary); }
	.table-wrap :global(thead th.sortable.active) { color: var(--accent); }

	.col-user { width: 100px; }
	.col-model { width: 240px; }
	.col-file { width: 280px; }
	.col-template { width: auto; } /* absorbs the remaining horizontal slack */
	.col-spec { width: 170px; white-space: nowrap; font-size: 10.5px; }
	.col-status { width: 80px; text-align: center; }
	.col-time { width: 150px; white-space: nowrap; font-size: 11px; }
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
</style>
