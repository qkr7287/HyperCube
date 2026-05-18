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
			<h1>컨테이너 요청 승인 <InfoTooltip text={"일반 사용자가 \"이 컨테이너를 만들어 주세요\" 또는 \"이 컨테이너를 지워 주세요\"라고 보낸 신청을 관리자가 검토하는 화면입니다.\n\n• 승인하면 해당 서버에서 실제로 컨테이너 생성/삭제가 진행됩니다.\n• 반려하면 사용자에게 사유와 함께 거절됩니다.\n• 처리 결과는 사용자 화면에서도 즉시 확인됩니다."} placement="bottom-start" /></h1>
			<p class="subtitle">사용자가 제출한 컨테이너 생성/삭제 요청을 검토합니다.</p>
		</div>
		<div class="controls">
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
				<InfoTooltip text={"필터 옵션\n\n• 대기중만 — 아직 승인/반려되지 않은 요청만 보여줍니다. 헤더의 빨간 배지 숫자와 같습니다.\n• 전체 — 처리 끝난 요청까지 모두 보여줍니다. 누가 언제 어떤 요청을 했는지 이력 확인용으로 쓰세요."} placement="bottom-end" />
			</div>
			<button class="refresh-btn" onclick={load} disabled={loading}>
				{loading ? '불러오는 중...' : '↻ 새로고침'}
			</button>
		</div>
	</div>

	{#if errorMsg}
		<div class="error-box">요청 목록을 불러오지 못했습니다: {errorMsg}</div>
	{/if}

	{#if !loading && requests.length === 0}
		<div class="empty">
			<div class="empty-icon">📭</div>
			<div class="empty-text">
				{filter === 'pending' ? '대기 중인 요청이 없습니다.' : '요청 이력이 없습니다.'}
			</div>
		</div>
	{:else}
		<div class="table-wrap">
			<table>
				<thead>
					<tr>
						<th class="col-user">제출자 <InfoTooltip text={"이 요청을 보낸 사용자 계정입니다.\n사용자명은 사용자의 로그인 ID와 동일합니다."} placement="bottom-start" /></th>
						<th class="col-action">타입 <InfoTooltip text={"요청 종류\n\n• 생성 — 새 컨테이너를 띄워 달라는 요청\n• 삭제 — 기존 컨테이너를 내려 달라는 요청"} placement="bottom-start" /></th>
						<th>템플릿 <InfoTooltip text={"생성 요청 시 어떤 템플릿(이미지 + 기본 옵션 묶음)을 사용했는지 보여줍니다.\n\n삭제 요청에는 적용되지 않아 \"-\"로 표시됩니다.\n\n템플릿 자체는 \"템플릿\" 메뉴에서 만들고 수정할 수 있습니다."} placement="bottom-start" /></th>
						<th>대상 서버 <InfoTooltip text={"요청이 적용될 서버(Agent)입니다.\n\n• 생성 — 이 서버에 새 컨테이너가 만들어집니다.\n• 삭제 — 이 서버에서 기존 컨테이너가 제거됩니다."} placement="bottom-start" /></th>
						<th>이름 <InfoTooltip text={"컨테이너 이름입니다.\n\n• 생성 요청 — 사용자가 입력한 새 컨테이너 이름\n• 삭제 요청 — 지우려는 기존 컨테이너 이름"} placement="bottom-start" /></th>
						<th class="col-status">상태 <InfoTooltip text={"요청의 진행 상태\n\n• 대기 — 관리자 검토 전\n• 승인 — 관리자가 승인했고 곧 배포 시작\n• 배포중 — Agent가 실제로 docker 명령 실행 중\n• 완료 — 컨테이너가 정상적으로 생성/삭제됨\n• 실패 — 배포 도중 오류 발생\n• 반려 — 관리자가 거절"} placement="bottom-start" /></th>
						<th class="col-time">제출 <InfoTooltip text={"사용자가 이 요청을 제출한 시각입니다 (현재 기준 상대 시간).\n\n오래된 요청부터 처리하고 싶으면 이 컬럼을 기준으로 살펴보세요."} placement="bottom-start" /></th>
						<th class="col-actions"></th>
					</tr>
				</thead>
				<tbody>
					{#each requests as req (req.id)}
						<tr>
							<td>{req.requester_username}</td>
							<td>
								<span class="action-tag" class:delete={req.action === 'delete'}>
									{req.action === 'create' ? '생성' : '삭제'}
								</span>
							</td>
							<td>{req.template_name ?? '-'}</td>
							<td>{req.target_agent_hostname ?? '-'}</td>
							<td>{req.custom_name || req.target_container_name || '-'}</td>
							<td>
								<span class="status-pill" style="background: {statusColor(req.status)};">
									{statusLabel(req.status)}
								</span>
							</td>
							<td class="dim">{relativeTime(req.created_at)}</td>
							<td>
								<button class="detail-btn" onclick={() => selected = req}>상세보기</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<RequestDetailModal
	request={selected}
	onClose={() => selected = null}
	onApprove={approveAction}
	onReject={rejectAction}
/>

<style>
	.page {
		padding: 28px 32px;
	}
	.page-header {
		display: flex; justify-content: space-between; align-items: flex-end;
		margin-bottom: 20px; gap: 20px; flex-wrap: wrap;
	}
	h1 {
		font-size: 20px; font-weight: 700; color: var(--text-primary);
		margin: 0 0 6px;
	}
	.subtitle {
		margin: 0; font-size: 12px; color: var(--text-muted);
	}
	.controls { display: flex; gap: 10px; align-items: center; }
	.filter-group { display: flex; gap: 2px; background: var(--bg-card); border-radius: var(--radius-md); padding: 3px; }
	.filter-btn {
		background: none; border: none; color: var(--text-secondary);
		padding: 6px 14px; font-size: 12px; cursor: pointer;
		border-radius: var(--radius-sm); font-family: inherit;
	}
	.filter-btn:hover { color: var(--text-primary); }
	.filter-btn.active {
		background: var(--accent); color: var(--bg-base); font-weight: 600;
	}
	.refresh-btn {
		background: var(--bg-card); border: 1px solid var(--border);
		color: var(--text-primary); padding: 7px 14px; font-size: 12px;
		border-radius: var(--radius-sm); cursor: pointer; font-family: inherit;
	}
	.refresh-btn:hover:not(:disabled) { border-color: var(--accent); }
	.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

	.error-box {
		background: rgba(239, 68, 68, 0.1); border: 1px solid var(--error);
		color: var(--error); padding: 10px 14px; border-radius: var(--radius-sm);
		font-size: 12px; margin-bottom: 16px;
	}

	.empty {
		padding: 60px 20px; text-align: center;
		background: var(--bg-card); border: 1px solid var(--border);
		border-radius: var(--radius-md);
	}
	.empty-icon { font-size: 36px; margin-bottom: 10px; }
	.empty-text { color: var(--text-muted); font-size: 13px; }

	.table-wrap {
		background: var(--bg-card); border: 1px solid var(--border);
		border-radius: var(--radius-md); overflow: hidden;
	}
	table {
		width: 100%; border-collapse: collapse;
	}
	th, td {
		padding: 10px 14px; text-align: left; font-size: 12px;
		border-bottom: 1px solid var(--border);
	}
	th {
		background: var(--bg-tab); color: var(--text-secondary);
		font-weight: 600; font-size: 11px;
		text-transform: uppercase; letter-spacing: 0.02em;
	}
	tbody tr:hover { background: var(--bg-tab); }
	tbody tr:last-child td { border-bottom: none; }
	.dim { color: var(--text-muted); }

	.action-tag {
		display: inline-block; padding: 2px 8px; border-radius: 4px;
		background: rgba(48, 213, 200, 0.15); color: var(--accent);
		font-size: 11px; font-weight: 600; white-space: nowrap;
	}
	.action-tag.delete {
		background: rgba(239, 68, 68, 0.15); color: var(--error);
	}
	.status-pill {
		display: inline-block; padding: 2px 8px; border-radius: 10px;
		color: white; font-size: 10px; font-weight: 700;
	}
	.detail-btn {
		background: var(--bg-tab); border: 1px solid var(--border);
		color: var(--text-primary); padding: 4px 10px; font-size: 11px;
		border-radius: var(--radius-sm); cursor: pointer; font-family: inherit;
	}
	.detail-btn:hover { border-color: var(--accent); }

	.col-user { width: 100px; }
	.col-action { width: 80px; }
	.col-status { width: 90px; }
	.col-time { width: 100px; }
	.col-actions { width: 100px; text-align: right; }
</style>
