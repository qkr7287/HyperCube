<script lang="ts">
	let {
		request = null,
		onClose = () => {},
		onApprove = (_id: string, _note: string) => Promise.resolve(),
		onReject = (_id: string, _note: string) => Promise.resolve(),
	}: {
		request: any | null;
		onClose?: () => void;
		onApprove?: (id: string, note: string) => Promise<void>;
		onReject?: (id: string, note: string) => Promise<void>;
	} = $props();

	let note = $state('');
	let busy = $state('');
	let errorMsg = $state('');

	$effect(() => {
		if (request) {
			note = '';
			errorMsg = '';
		}
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	$effect(() => {
		if (request) {
			document.addEventListener('keydown', handleKeydown);
			return () => document.removeEventListener('keydown', handleKeydown);
		}
	});

	async function approve() {
		if (!request || busy) return;
		busy = 'approve';
		errorMsg = '';
		try {
			await onApprove(request.id, note);
			onClose();
		} catch (e: any) {
			errorMsg = e?.message || '승인 실패';
		} finally {
			busy = '';
		}
	}

	async function reject() {
		if (!request || busy) return;
		busy = 'reject';
		errorMsg = '';
		try {
			await onReject(request.id, note);
			onClose();
		} catch (e: any) {
			errorMsg = e?.message || '반려 실패';
		} finally {
			busy = '';
		}
	}

	function formatTime(iso?: string | null): string {
		if (!iso) return '-';
		try {
			return new Date(iso).toLocaleString('ko-KR');
		} catch {
			return iso;
		}
	}

	function formatBytes(b?: number): string {
		const v = Number(b || 0);
		if (v >= 1024 ** 3) return `${(v / 1024 ** 3).toFixed(2)} GB`;
		if (v >= 1024 ** 2) return `${(v / 1024 ** 2).toFixed(2)} MB`;
		if (v >= 1024) return `${(v / 1024).toFixed(1)} KB`;
		return `${v} B`;
	}

	function statusColor(s?: string): string {
		return ({
			pending: '#f59e0b',
			approved: '#22c55e',
			rejected: '#6b7280',
			failed: '#ef4444',
		} as any)[s ?? ''] ?? '#6b7280';
	}

	function statusLabel(s?: string): string {
		return ({
			pending: '대기',
			approved: '승인',
			rejected: '반려',
			failed: '실패',
		} as any)[s ?? ''] ?? s ?? '-';
	}
</script>

{#if request}
<div class="overlay" onclick={onClose} role="dialog" aria-modal="true">
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<div class="title-row">
				<span class="title">모델 등록 요청 상세</span>
				<span class="status-pill" style="background: {statusColor(request.status)};">
					{statusLabel(request.status)}
				</span>
			</div>
			<button class="close-btn" onclick={onClose} aria-label="닫기">
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			<section class="section">
				<div class="section-title">기본 정보</div>
				<div class="grid-2">
					<div class="field">
						<span class="label">제출자</span>
						<span class="value">{request.requester_username}</span>
					</div>
					<div class="field">
						<span class="label">제출 시각</span>
						<span class="value">{formatTime(request.created_at)}</span>
					</div>
					<div class="field">
						<span class="label">모델</span>
						<span class="value strong">{request.name} <em class="version">{request.version}</em></span>
					</div>
					<div class="field">
						<span class="label">프레임워크 · 태스크</span>
						<span class="value">{request.framework || '-'}{request.task ? ` · ${request.task}` : ''}</span>
					</div>
					{#if request.description}
						<div class="field span-2">
							<span class="label">설명</span>
							<span class="value">{request.description}</span>
						</div>
					{/if}
					{#if request.tags && request.tags.length > 0}
						<div class="field span-2">
							<span class="label">태그</span>
							<div class="tag-row">
								{#each request.tags as t}<span class="tag">{t}</span>{/each}
							</div>
						</div>
					{/if}
				</div>
			</section>

			<section class="section">
				<div class="section-title">파일</div>
				<div class="grid-2">
					<div class="field span-2">
						<span class="label">파일명</span>
						<span class="value mono" title={request.original_filename}>{request.original_filename || '-'}</span>
					</div>
					<div class="field">
						<span class="label">크기</span>
						<span class="value">{formatBytes(request.size_bytes)}</span>
					</div>
					<div class="field">
						<span class="label">sha256</span>
						<span class="value mono small" title={request.sha256}>{request.sha256 ? request.sha256.slice(0, 32) + '…' : '-'}</span>
					</div>
				</div>
			</section>

			<section class="section">
				<div class="section-title">실행 환경 · 자원</div>
				<div class="grid-2">
					<div class="field span-2">
						<span class="label">base image</span>
						<span class="value mono small">{request.base_image}</span>
					</div>
					<div class="field">
						<span class="label">워크스페이스</span>
						<span class="value">{request.workspace_kind || '-'}{request.workspace_port ? ` · ${request.workspace_port}` : ''}</span>
					</div>
					<div class="field">
						<span class="label">GPU 필요</span>
						<span class="value">{request.requires_gpu ? '예' : '아니오'}</span>
					</div>
					<div class="field">
						<span class="label">최소 RAM</span>
						<span class="value">{request.min_memory_mb} MB</span>
					</div>
					<div class="field">
						<span class="label">최소 디스크</span>
						<span class="value">{request.min_workspace_gb} GB</span>
					</div>
					<div class="field">
						<span class="label">최대 가동 시간</span>
						<span class="value">{request.default_max_runtime_hours ? `${request.default_max_runtime_hours}h` : '-'}</span>
					</div>
					{#if request.launcher_recipe_id}
						<div class="field">
							<span class="label">추론 레시피</span>
							<span class="value mono small">{request.launcher_recipe_id}</span>
						</div>
					{/if}
				</div>
			</section>

			<section class="section">
				<div class="section-title">생성될 템플릿</div>
				<div class="field">
					<span class="label">이름</span>
					<span class="value strong">{request.created_template_name || request.template_name || '(자동 생성)'}</span>
				</div>
				{#if request.template_description}
					<div class="field">
						<span class="label">설명</span>
						<span class="value">{request.template_description}</span>
					</div>
				{/if}
			</section>

			{#if request.status !== 'pending'}
				<section class="section section-review">
					<div class="section-title">검토 결과</div>
					<div class="grid-2">
						<div class="field">
							<span class="label">검토자</span>
							<span class="value">{request.reviewer_username || '-'}</span>
						</div>
						<div class="field">
							<span class="label">검토 시각</span>
							<span class="value">{formatTime(request.reviewed_at)}</span>
						</div>
						{#if request.review_note}
							<div class="field span-2">
								<span class="label">검토 메모</span>
								<div class="note-box">{request.review_note}</div>
							</div>
						{/if}
					</div>
				</section>
			{/if}
		</div>

		{#if request.status === 'pending'}
			<div class="modal-footer">
				<div class="note-input-wrap">
					<label for="note-input" class="note-label">메모 (선택)</label>
					<input id="note-input" type="text" bind:value={note}
						placeholder="승인/반려 사유 또는 추가 설명..." />
				</div>
				{#if errorMsg}
					<div class="error">{errorMsg}</div>
				{/if}
				<div class="action-row">
					<button class="btn-reject" disabled={!!busy} onclick={reject}>
						{busy === 'reject' ? '반려 중…' : '반려'}
					</button>
					<button class="btn-approve" disabled={!!busy} onclick={approve}>
						{busy === 'approve' ? '승인 중…' : '승인'}
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>
{/if}

<style>
	.overlay {
		position: fixed; inset: 0; z-index: 200;
		background: rgba(0, 0, 0, 0.62); backdrop-filter: blur(4px);
		display: flex; align-items: center; justify-content: center;
	}
	.modal {
		width: 760px; max-width: 92vw; max-height: 88vh;
		background: var(--bg-card); border: 1px solid var(--border);
		border-radius: 10px;
		display: flex; flex-direction: column; overflow: hidden;
		box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
	}
	.modal-header {
		display: flex; justify-content: space-between; align-items: center;
		padding: 16px 22px; border-bottom: 1px solid var(--border);
		background: rgba(13, 17, 23, 0.4);
	}
	.title-row { display: flex; align-items: center; gap: 12px; }
	.title { font-size: 15px; font-weight: 800; color: var(--text-primary); }
	.status-pill {
		padding: 3px 10px; border-radius: 10px;
		font-size: 11px; font-weight: 800; color: white;
	}
	.close-btn {
		background: none; border: none; cursor: pointer;
		padding: 4px; display: flex; color: var(--text-muted);
	}
	.close-btn:hover { color: var(--text-primary); }

	.modal-content {
		flex: 1; overflow-y: auto;
		padding: 18px 22px 22px;
		display: flex; flex-direction: column; gap: 22px;
	}
	.section { display: flex; flex-direction: column; gap: 8px; }
	.section-review { padding: 12px 14px; background: rgba(13, 17, 23, 0.4); border-radius: 8px; }
	.section-title {
		font-size: 11px; font-weight: 800; color: var(--text-muted);
		text-transform: uppercase; letter-spacing: 0.06em;
		padding-bottom: 4px; border-bottom: 1px solid var(--border);
	}
	.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 18px; }
	.field { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
	.field.span-2 { grid-column: 1 / -1; }
	.label { font-size: 10.5px; color: var(--text-muted); font-weight: 700; letter-spacing: 0.02em; }
	.value { font-size: 13px; color: var(--text-primary); word-break: break-all; }
	.value.strong { font-weight: 800; }
	.value .version {
		display: inline-block; padding: 1px 6px; margin-left: 4px;
		font-style: normal; font-size: 10px; font-weight: 800;
		color: var(--accent); background: rgba(77, 191, 179, 0.14);
		border-radius: 3px;
	}
	.mono { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 11.5px; }
	.mono.small { font-size: 10.5px; }

	.tag-row { display: flex; flex-wrap: wrap; gap: 4px; }
	.tag {
		display: inline-flex; align-items: center;
		padding: 2px 7px; font-size: 10.5px; font-weight: 700;
		color: var(--text-muted); background: rgba(100, 116, 139, 0.18);
		border-radius: 3px;
	}

	.note-box {
		background: var(--bg-base); border: 1px solid var(--border);
		border-radius: 6px; padding: 9px 12px;
		font-size: 12px; color: var(--text-primary);
		white-space: pre-wrap;
	}

	.modal-footer {
		padding: 14px 22px; border-top: 1px solid var(--border);
		display: flex; flex-direction: column; gap: 10px;
		background: rgba(13, 17, 23, 0.4);
	}
	.note-input-wrap { display: flex; flex-direction: column; gap: 4px; }
	.note-label {
		font-size: 10.5px; font-weight: 700; color: var(--text-muted);
		letter-spacing: 0.02em;
	}
	.note-input-wrap input {
		background: var(--bg-base); border: 1px solid var(--border);
		border-radius: 6px; padding: 8px 12px;
		color: var(--text-primary); font-family: inherit; font-size: 13px;
	}
	.note-input-wrap input:focus { outline: none; border-color: var(--accent); }
	.error { font-size: 12px; color: var(--error); }
	.action-row { display: flex; justify-content: flex-end; gap: 8px; }
	.btn-approve, .btn-reject {
		padding: 8px 18px; border: 1px solid transparent; border-radius: 6px;
		font-size: 13px; font-weight: 800; cursor: pointer;
		font-family: inherit;
	}
	.btn-approve { background: var(--accent); color: var(--bg-base); }
	.btn-approve:hover:not(:disabled) { filter: brightness(1.08); }
	.btn-reject {
		background: rgba(239, 68, 68, 0.10); color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.42);
	}
	.btn-reject:hover:not(:disabled) { background: rgba(239, 68, 68, 0.18); }
	button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
