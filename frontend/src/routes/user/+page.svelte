<script lang="ts">
	import { onMount } from 'svelte';
	import { base } from '$app/paths';
	import { browser } from '$app/environment';
	import NewRequestModal from '$lib/components/NewRequestModal.svelte';

	type RequestRow = {
		id: string;
		action: string;
		status: string;
		template_name?: string | null;
		target_agent_hostname?: string | null;
		target_container_name?: string | null;
		custom_name?: string;
		progress_message?: string;
		progress_percent?: number | null;
		review_note?: string;
		created_at: string;
		[k: string]: any;
	};

	let requests = $state<RequestRow[]>([]);
	let loading = $state(false);
	let newModalOpen = $state(false);

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function load() {
		const t = token();
		if (!t) return;
		loading = true;
		try {
			const res = await fetch(`${base}/api/requests/?page_size=100&ordering=-created_at`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (res.ok) {
				const json = await res.json();
				requests = json.data?.results ?? [];
			}
		} catch { /* ignore */ }
		loading = false;
	}

	onMount(load);

	function statusColor(s?: string): string {
		return ({ pending: '#f59e0b', approved: '#3b82f6', deploying: '#8b5cf6', deployed: '#22c55e', failed: '#ef4444', rejected: '#6b7280' } as any)[s ?? ''] ?? '#6b7280';
	}

	function statusLabel(s?: string): string {
		return ({ pending: '검토 대기', approved: '승인됨', deploying: '배포 중', deployed: '완료', failed: '실패', rejected: '반려됨' } as any)[s ?? ''] ?? s ?? '-';
	}

	function statusIcon(s?: string): string {
		return ({ pending: '⏳', approved: '✅', deploying: '🔄', deployed: '🟢', failed: '🔴', rejected: '⛔' } as any)[s ?? ''] ?? '❓';
	}

	function relativeTime(iso: string): string {
		try {
			const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
			if (diff < 60) return `${diff}초 전`;
			if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
			if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
			return `${Math.floor(diff / 86400)}일 전`;
		} catch { return iso; }
	}
</script>

<div class="page">
	<div class="page-header">
		<div>
			<h1>내 컨테이너 요청</h1>
			<p class="subtitle">요청한 컨테이너의 진행 상황을 확인하고 새 요청을 제출합니다.</p>
		</div>
		<button class="new-btn" onclick={() => newModalOpen = true}>+ 새 요청</button>
	</div>

	{#if !loading && requests.length === 0}
		<div class="empty">
			<div class="empty-icon">🐳</div>
			<div class="empty-title">아직 요청이 없습니다</div>
			<div class="empty-text">템플릿을 선택해서 첫 컨테이너를 요청해보세요.</div>
			<button class="empty-btn" onclick={() => newModalOpen = true}>첫 요청 만들기</button>
		</div>
	{:else}
		<div class="cards">
			{#each requests as req (req.id)}
				<div class="request-card" class:pending={req.status === 'pending'} class:rejected={req.status === 'rejected'} class:failed={req.status === 'failed'}>
					<div class="card-top">
						<div class="card-left">
							<span class="card-icon">{statusIcon(req.status)}</span>
							<div>
								<div class="card-name">{req.custom_name || req.target_container_name || '(이름 없음)'}</div>
								<div class="card-meta">
									{req.action === 'create' ? '생성' : '삭제'} · {req.template_name ?? '-'} · {req.target_agent_hostname ?? '-'}
								</div>
							</div>
						</div>
						<div class="card-right">
							<span class="status-pill" style="background: {statusColor(req.status)};">{statusLabel(req.status)}</span>
							<span class="card-time">{relativeTime(req.created_at)}</span>
						</div>
					</div>

					{#if req.progress_message}
						<div class="card-progress">
							{#if req.progress_percent != null}
								<div class="progress-bar">
									<div class="progress-fill" style="width: {req.progress_percent}%"></div>
								</div>
							{/if}
							<div class="progress-text">{req.progress_message}</div>
						</div>
					{/if}

					{#if req.review_note}
						<div class="card-note">
							<span class="note-label">검토 메모:</span> {req.review_note}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>

<NewRequestModal
	open={newModalOpen}
	onClose={() => newModalOpen = false}
	onSubmitted={load}
/>

<style>
	.page { padding: 28px 32px; max-width: 900px; margin: 0 auto; }
	.page-header {
		display: flex; justify-content: space-between; align-items: flex-end;
		margin-bottom: 24px; gap: 20px; flex-wrap: wrap;
	}
	h1 { font-size: 22px; font-weight: 700; color: var(--text-primary); margin: 0 0 6px; }
	.subtitle { margin: 0; font-size: 13px; color: var(--text-muted); }
	.new-btn {
		background: var(--accent); color: var(--bg-base); border: none;
		padding: 10px 20px; border-radius: var(--radius-sm);
		font-size: 14px; font-weight: 600; cursor: pointer; font-family: inherit; white-space: nowrap;
	}
	.new-btn:hover { filter: brightness(1.1); }

	.empty {
		padding: 60px 20px; text-align: center;
		background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--radius-md);
	}
	.empty-icon { font-size: 48px; margin-bottom: 12px; }
	.empty-title { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 6px; }
	.empty-text { color: var(--text-muted); font-size: 13px; margin-bottom: 20px; }
	.empty-btn {
		background: var(--accent); color: var(--bg-base); border: none;
		padding: 10px 20px; border-radius: var(--radius-sm);
		font-size: 13px; font-weight: 600; cursor: pointer; font-family: inherit;
	}

	.cards { display: flex; flex-direction: column; gap: 10px; }
	.request-card {
		background: var(--bg-card); border: 1px solid var(--border);
		border-radius: var(--radius-md); padding: 16px 18px;
		border-left-width: 4px; border-left-color: var(--accent);
	}
	.request-card.pending { border-left-color: #f59e0b; }
	.request-card.rejected { border-left-color: #6b7280; }
	.request-card.failed { border-left-color: #ef4444; }

	.card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
	.card-left { display: flex; gap: 10px; align-items: flex-start; }
	.card-icon { font-size: 20px; }
	.card-name { font-size: 14px; font-weight: 700; color: var(--text-primary); }
	.card-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
	.card-right { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; flex-shrink: 0; }
	.status-pill {
		display: inline-block; padding: 2px 10px; border-radius: 10px;
		color: white; font-size: 11px; font-weight: 700;
	}
	.card-time { font-size: 10px; color: var(--text-muted); }

	.card-progress { margin-top: 10px; }
	.progress-bar {
		height: 6px; background: var(--bg-base); border-radius: 3px; overflow: hidden;
	}
	.progress-fill { height: 100%; background: var(--accent); transition: width 0.3s; }
	.progress-text { font-size: 11px; color: var(--text-secondary); margin-top: 4px; }

	.card-note {
		margin-top: 8px; font-size: 11px; color: var(--text-secondary);
		background: var(--bg-base); padding: 8px 10px; border-radius: var(--radius-sm);
	}
	.note-label { color: var(--text-muted); font-weight: 600; }
</style>
