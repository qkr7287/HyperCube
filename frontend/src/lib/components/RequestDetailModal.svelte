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
		// 모달 열리면 note/error 초기화
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

	function formatTime(iso?: string): string {
		if (!iso) return '-';
		try {
			return new Date(iso).toLocaleString('ko-KR');
		} catch {
			return iso;
		}
	}

	function statusColor(s?: string): string {
		switch (s) {
			case 'pending': return '#f59e0b';
			case 'approved': return '#3b82f6';
			case 'deploying': return '#8b5cf6';
			case 'deployed': return '#22c55e';
			case 'failed': return '#ef4444';
			case 'rejected': return '#6b7280';
			default: return '#6b7280';
		}
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
</script>

{#if request}
<div class="overlay" onclick={onClose} role="dialog">
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<div class="title-row">
				<span class="title">요청 상세</span>
				<span class="status-pill" style="background: {statusColor(request.status)};">
					{statusLabel(request.status)}
				</span>
			</div>
			<button class="close-btn" onclick={onClose} aria-label="close">
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			<!-- 요청 기본 정보 -->
			<section class="section">
				<div class="section-title">기본 정보</div>
				<div class="grid-2">
					<div class="field">
						<span class="label">요청 ID</span>
						<span class="value mono">{request.id}</span>
					</div>
					<div class="field">
						<span class="label">제출자</span>
						<span class="value">{request.requester_username}</span>
					</div>
					<div class="field">
						<span class="label">타입</span>
						<span class="value">{request.action === 'create' ? '생성' : '삭제'}</span>
					</div>
					<div class="field">
						<span class="label">제출 시각</span>
						<span class="value">{formatTime(request.created_at)}</span>
					</div>
					{#if request.reviewer_username}
						<div class="field">
							<span class="label">검토자</span>
							<span class="value">{request.reviewer_username}</span>
						</div>
						<div class="field">
							<span class="label">검토 시각</span>
							<span class="value">{formatTime(request.reviewed_at)}</span>
						</div>
					{/if}
				</div>
			</section>

			{#if request.action === 'create'}
				<section class="section">
					<div class="section-title">생성 요청 상세</div>
					<div class="field">
						<span class="label">템플릿</span>
						<span class="value">{request.template_name ?? '-'}</span>
					</div>
					<div class="field">
						<span class="label">대상 서버</span>
						<span class="value">{request.target_agent_hostname ?? '-'}</span>
					</div>
					<div class="field">
						<span class="label">컨테이너 이름</span>
						<span class="value">{request.custom_name || '(자동)'}</span>
					</div>
					{#if request.selected_image}
						<div class="field">
							<span class="label">선택된 이미지</span>
							<span class="value mono">{request.selected_image}</span>
						</div>
					{/if}
					{#if request.custom_env && Object.keys(request.custom_env).length > 0}
						<div class="field">
							<span class="label">환경 변수</span>
							<pre class="json-box">{JSON.stringify(request.custom_env, null, 2)}</pre>
						</div>
					{/if}
					{#if Array.isArray(request.custom_ports) && request.custom_ports.length > 0}
						<div class="field">
							<span class="label">포트</span>
							<pre class="json-box">{JSON.stringify(request.custom_ports, null, 2)}</pre>
						</div>
					{/if}
				</section>
			{:else}
				<section class="section">
					<div class="section-title">삭제 대상</div>
					<div class="field">
						<span class="label">컨테이너</span>
						<span class="value">{request.target_container_name ?? '-'}</span>
					</div>
					{#if request.target_container}
						<div class="field">
							<span class="label">ID</span>
							<span class="value mono">{request.target_container}</span>
						</div>
					{/if}
				</section>
			{/if}

			{#if request.review_note}
				<section class="section">
					<div class="section-title">검토 메모</div>
					<div class="note-box">{request.review_note}</div>
				</section>
			{/if}

			{#if request.deployment_log}
				<section class="section">
					<div class="section-title">배포 로그</div>
					<pre class="log-box">{request.deployment_log}</pre>
				</section>
			{/if}

			{#if request.progress_message}
				<section class="section">
					<div class="section-title">진행 상황</div>
					{#if request.progress_percent !== null && request.progress_percent !== undefined}
						<div class="progress-bar">
							<div class="progress-fill" style="width: {request.progress_percent}%"></div>
						</div>
						<div class="progress-text">{request.progress_percent}% · {request.progress_message}</div>
					{:else}
						<div class="note-box">{request.progress_message}</div>
					{/if}
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
						{busy === 'reject' ? '반려 중...' : '반려'}
					</button>
					<button class="btn-approve" disabled={!!busy} onclick={approve}>
						{busy === 'approve' ? '승인 중...' : '승인'}
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
		background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(4px);
		display: flex; align-items: center; justify-content: center;
	}
	.modal {
		width: 720px; max-width: 90vw; max-height: 88vh;
		background: var(--bg-card); border: 1px solid var(--border);
		border-radius: var(--radius-md);
		display: flex; flex-direction: column; overflow: hidden;
	}
	.modal-header {
		display: flex; justify-content: space-between; align-items: center;
		padding: 18px 22px; border-bottom: 1px solid var(--border);
	}
	.title-row {
		display: flex; align-items: center; gap: 12px;
	}
	.title {
		font-size: 16px; font-weight: 700; color: var(--text-primary);
	}
	.status-pill {
		padding: 3px 10px; border-radius: 10px;
		font-size: 11px; font-weight: 700; color: white;
	}
	.close-btn {
		background: none; border: none; cursor: pointer; padding: 4px; display: flex;
	}
	.close-btn:hover svg { stroke: var(--text-primary); }

	.modal-content {
		flex: 1; overflow-y: auto;
		padding: 18px 22px 22px;
		display: flex; flex-direction: column; gap: 18px;
	}
	.section { display: flex; flex-direction: column; gap: 8px; }
	.section-title {
		font-size: 12px; font-weight: 700; color: var(--text-secondary);
		text-transform: uppercase; letter-spacing: 0.02em;
	}
	.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 14px; }
	.field { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
	.label { font-size: 10px; color: var(--text-muted); }
	.value { font-size: 13px; color: var(--text-primary); word-break: break-all; }
	.mono { font-family: 'JetBrains Mono', monospace; font-size: 11px; }

	.json-box, .log-box {
		background: var(--bg-base); border: 1px solid var(--border);
		border-radius: var(--radius-sm); padding: 10px 12px;
		font-family: 'JetBrains Mono', monospace; font-size: 11px;
		color: var(--text-primary); white-space: pre-wrap;
		max-height: 200px; overflow: auto; margin: 0;
	}
	.note-box {
		background: var(--bg-base); border: 1px solid var(--border);
		border-radius: var(--radius-sm); padding: 10px 12px;
		font-size: 12px; color: var(--text-primary);
	}

	.progress-bar {
		height: 8px; background: var(--bg-base);
		border-radius: 4px; overflow: hidden;
	}
	.progress-fill {
		height: 100%; background: var(--accent);
		transition: width 0.3s ease;
	}
	.progress-text {
		font-size: 11px; color: var(--text-secondary); margin-top: 4px;
	}

	.modal-footer {
		padding: 16px 22px; border-top: 1px solid var(--border);
		display: flex; flex-direction: column; gap: 10px;
	}
	.note-input-wrap { display: flex; flex-direction: column; gap: 4px; }
	.note-label {
		font-size: 11px; color: var(--text-secondary);
	}
	.note-input-wrap input {
		background: var(--bg-base); border: 1px solid var(--border);
		border-radius: var(--radius-sm); padding: 8px 12px;
		color: var(--text-primary); font-family: inherit; font-size: 13px;
	}
	.note-input-wrap input:focus {
		outline: none; border-color: var(--accent);
	}
	.error {
		font-size: 12px; color: var(--error);
	}
	.action-row { display: flex; justify-content: flex-end; gap: 10px; }
	.btn-approve, .btn-reject {
		padding: 8px 18px; border: none; border-radius: var(--radius-sm);
		font-size: 13px; font-weight: 600; cursor: pointer;
		font-family: inherit;
	}
	.btn-approve {
		background: var(--accent); color: var(--bg-base);
	}
	.btn-approve:hover:not(:disabled) { filter: brightness(1.1); }
	.btn-reject {
		background: var(--bg-tab); color: var(--error);
		border: 1px solid var(--error);
	}
	.btn-reject:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.1);
	}
	button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
