<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';

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
			<h1>모델 등록 요청</h1>
			<p class="subtitle">사용자가 브라우저로 업로드한 모델 파일을 검토하고 공유 모델/컨테이너 템플릿으로 등록합니다.</p>
		</div>
		<div class="controls">
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
				{loading ? '불러오는 중...' : '새로고침'}
			</button>
		</div>
	</div>

	{#if errorMsg}
		<div class="error-box">{errorMsg}</div>
	{/if}

	{#if !loading && requests.length === 0}
		<div class="empty">
			<div class="empty-text">
				{filter === 'pending' ? '대기 중인 모델 등록 요청이 없습니다.' : '모델 등록 요청 이력이 없습니다.'}
			</div>
		</div>
	{:else}
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th>제출자</th>
						<th>모델</th>
						<th>파일</th>
						<th>생성 템플릿</th>
						<th>실행 조건</th>
						<th class="col-status">상태</th>
						<th class="col-time">제출</th>
						<th class="col-actions"></th>
					</tr>
				</thead>
				<tbody>
					{#each requests as req (req.id)}
						<tr>
							<td>{req.requester_username}</td>
							<td class="model-cell">
								<strong>{req.name}</strong>
								<span>{req.version} · {req.framework || '-'}{req.task ? ` · ${req.task}` : ''}</span>
							</td>
							<td class="file-cell">
								<strong>{req.original_filename || '-'}</strong>
								<span>{formatBytes(req.size_bytes)} · {req.sha256 ? req.sha256.slice(0, 12) : '-'}</span>
							</td>
							<td class="template-cell">
								<strong>{req.created_template_name || req.template_name || '-'}</strong>
								<span>{req.base_image}</span>
							</td>
							<td class="dim">
								{req.requires_gpu ? 'GPU' : 'CPU'} · RAM {req.min_memory_mb} MB · WS {req.min_workspace_gb} GB
							</td>
							<td>
								<span class="status-pill" style="background: {statusTone(req.status)};">
									{statusLabel(req.status)}
								</span>
							</td>
							<td class="dim">{formatTime(req.created_at)}</td>
							<td class="actions">
								{#if req.status === 'pending'}
									<button
										class="approve-btn"
										disabled={!!processingId}
										onclick={() => review(req.id, 'approve', '')}
									>
										{processingId === req.id ? '처리 중' : '승인'}
									</button>
									<button
										class="reject-btn"
										disabled={!!processingId}
										onclick={() => reject(req)}
									>반려</button>
								{:else}
									<span class="dim">{req.reviewer_username || '-'}</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<style>
	/* Shared chrome via admin layout :global(). Panel keeps only its own
	   row-cell layouts and approve/reject button colors. */
	.approve-btn:disabled,
	.reject-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.table-wrap table {
		min-width: 1120px;
	}
	.table-wrap tbody td {
		vertical-align: middle;
	}
	.model-cell,
	.file-cell,
	.template-cell {
		display: grid;
		gap: 3px;
		min-width: 0;
	}
	.model-cell strong,
	.file-cell strong,
	.template-cell strong {
		color: var(--text-primary);
		font-size: 12px;
	}
	.model-cell span,
	.file-cell span,
	.template-cell span,
	.dim {
		color: var(--text-muted);
		font-size: 11px;
	}
	.template-cell span {
		max-width: 260px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.status-pill {
		display: inline-block;
		padding: 2px 8px;
		border-radius: 10px;
		color: white;
		font-size: 10px;
		font-weight: 700;
	}
	.actions {
		display: flex;
		gap: 6px;
		justify-content: flex-end;
	}
	.approve-btn,
	.reject-btn {
		border: 1px solid var(--border);
		padding: 5px 10px;
		font-size: 11px;
		border-radius: var(--radius-sm);
		cursor: pointer;
		font-family: inherit;
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
	.col-status {
		width: 80px;
	}
	.col-time {
		width: 150px;
	}
	.col-actions {
		width: 130px;
		text-align: right;
	}
</style>
