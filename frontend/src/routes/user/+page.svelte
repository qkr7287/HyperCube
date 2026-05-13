<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import NewRequestModal from '$lib/components/NewRequestModal.svelte';
	import {
		formatDateTime,
		formatRelativeTime,
		statusLabel,
		statusTone,
	} from '$lib/utils/container-dashboard';

	type RequestRow = {
		id: string;
		action: string;
		status: string;
		template_name?: string | null;
		target_agent_hostname?: string | null;
		target_container?: string | null;
		target_container_name?: string | null;
		custom_name?: string;
		progress_message?: string;
		progress_percent?: number | null;
		review_note?: string;
		created_at: string;
	};

	let requests = $state<RequestRow[]>([]);
	let loading = $state(false);
	let newModalOpen = $state(false);

	const ACTIVE_STATUSES = new Set(['pending', 'approved', 'deploying']);
	let pollTimer: ReturnType<typeof setInterval> | null = null;
	const requestPageHelp = `이 페이지는 내가 요청한 컨테이너의 전체 진행 상황을 모아보는 곳입니다.

• 새 요청 만들기: 새 컨테이너 생성 요청 시작
• 카드 상태: 승인 대기 → 승인 완료 → 배포 중 → 배포 완료
• 모니터링 열기: 배포가 끝난 뒤 상세 관제 화면으로 이동

처음에는 빈 화면일 수 있으며, 요청을 만들면 목록이 자동으로 채워집니다.`;
	const totalRequestsHelp = `지금까지 내가 제출한 전체 요청 수입니다.

생성 요청과 삭제 요청이 모두 포함되며, 완료된 요청도 함께 집계됩니다.`;
	const activeFlowHelp = `아직 처리가 끝나지 않은 요청 수입니다.

여기에는 승인 대기, 승인 완료, 배포 중 상태가 포함됩니다.
숫자가 0이 되면 현재 진행 중인 작업이 없다는 뜻입니다.`;
	const readyToMonitorHelp = `배포가 끝나 바로 확인할 수 있는 컨테이너 수입니다.

이 숫자에 포함된 항목은 카드 아래의 "모니터링 열기" 버튼으로 상세 화면에 들어갈 수 있습니다.`;
	const requestCardHelp = `각 카드는 컨테이너 요청 1건을 뜻합니다.

위쪽에는 이름, 요청 종류, 템플릿, 배치 서버가 보이고
아래쪽에는 배포 진행률, 검토 메모, 생성 시각이 표시됩니다.`;
	const reviewNoteHelp = `검토 메모는 관리자 또는 시스템이 남긴 안내입니다.

반려 사유, 배포 중 참고사항, 확인이 필요한 설정이 적힐 수 있으니 먼저 읽어보는 것이 좋습니다.`;

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
		} catch {
			// ignore
		} finally {
			loading = false;
			syncPolling();
		}
	}

	function syncPolling() {
		const hasActive = requests.some((request) => ACTIVE_STATUSES.has(request.status));
		if (hasActive && !pollTimer) {
			pollTimer = setInterval(load, 2000);
		} else if (!hasActive && pollTimer) {
			clearInterval(pollTimer);
			pollTimer = null;
		}
	}

	function openDashboard(request: RequestRow) {
		if (!request.target_container) return;
		goto(`${base}/user/containers/${request.target_container}`);
	}

	let totalRequests = $derived(requests.length);
	let activeRequests = $derived(requests.filter((request) => ACTIVE_STATUSES.has(request.status)).length);
	let deployedRequests = $derived(requests.filter((request) => request.status === 'deployed').length);

	onMount(() => {
		load();
		return () => {
			if (pollTimer) clearInterval(pollTimer);
		};
	});
</script>

<div class="page">
	<section class="hero">
		<div>
			<p class="eyebrow">사용자 작업공간</p>
			<div class="title-row">
				<h1>컨테이너 요청 현황</h1>
				<InfoTooltip
					text={requestPageHelp}
					label="요청 현황 페이지 도움말"
					placement="bottom-start"
					maxWidth={380}
				/>
			</div>
			<p class="subtitle">승인부터 배포 완료까지 한눈에 확인하고, 준비된 컨테이너는 바로 모니터링 화면으로 열 수 있습니다.</p>
		</div>
		<button class="new-btn" onclick={() => (newModalOpen = true)}>새 요청 만들기</button>
	</section>

	<section class="summary-grid">
		<div class="summary-card">
			<span class="summary-label">
				전체 요청
				<InfoTooltip text={totalRequestsHelp} label="전체 요청 도움말" placement="bottom-start" />
			</span>
			<strong>{totalRequests}</strong>
			<span class="summary-meta">지금까지 제출한 모든 요청</span>
		</div>
		<div class="summary-card">
			<span class="summary-label">
				진행 중
				<InfoTooltip text={activeFlowHelp} label="진행 중 도움말" placement="bottom-start" />
			</span>
			<strong>{activeRequests}</strong>
			<span class="summary-meta">승인 대기, 승인 완료, 배포 중</span>
		</div>
		<div class="summary-card">
			<span class="summary-label">
				모니터링 가능
				<InfoTooltip text={readyToMonitorHelp} label="모니터링 가능 도움말" placement="bottom-start" />
			</span>
			<strong>{deployedRequests}</strong>
			<span class="summary-meta">배포가 완료된 항목</span>
		</div>
	</section>

	{#if !loading && requests.length === 0}
		<div class="empty">
			<div class="empty-badge">아직 요청이 없습니다</div>
			<div class="empty-title">아직 컨테이너를 요청하지 않았습니다</div>
			<p class="empty-text">첫 요청을 만들면 승인과 배포 흐름이 여기에서 자동으로 보이기 시작합니다.</p>
			<button class="empty-btn" onclick={() => (newModalOpen = true)}>첫 요청 만들기</button>
		</div>
	{:else}
		<div class="cards">
			{#each requests as request (request.id)}
				<div class="request-card">
					<div class="card-main">
						<div class="card-heading">
							<div class="request-identity">
								<span class="request-mark" aria-hidden="true">
									{(request.custom_name || request.target_container_name || '?').slice(0, 1).toUpperCase()}
								</span>
								<div class="request-copy">
									<div class="name-row">
										<div class="card-name" title={request.custom_name || request.target_container_name || '이름 없는 컨테이너'}>
											{request.custom_name || request.target_container_name || '이름 없는 컨테이너'}
										</div>
										<InfoTooltip
											text={requestCardHelp}
											label="요청 카드 도움말"
											placement="bottom-start"
											maxWidth={360}
										/>
									</div>
									<div class="card-meta">
										<span><b>작업</b>{request.action === 'create' ? '생성 요청' : '삭제 요청'}</span>
										<span><b>템플릿</b>{request.template_name ?? '템플릿 없음'}</span>
										<span><b>서버</b>{request.target_agent_hostname ?? '배치 서버 없음'}</span>
									</div>
								</div>
							</div>
							<div class="card-status">
								<span class="status-pill" style="background: {statusTone(request.status)};">{statusLabel(request.status)}</span>
								<span class="card-time">{formatRelativeTime(request.created_at)}</span>
							</div>
						</div>

						{#if request.progress_message}
							<div class="progress-block">
								<div class="progress-track">
									<div class="progress-fill" style="width: {request.progress_percent ?? 0}%"></div>
								</div>
								<div class="progress-text">
									<span>{request.progress_message}</span>
									<span>{request.progress_percent != null ? `${request.progress_percent}%` : formatDateTime(request.created_at)}</span>
								</div>
							</div>
						{/if}

						{#if request.review_note}
							<div class="review-note">
								<span class="review-label">
									검토 메모
									<InfoTooltip text={reviewNoteHelp} label="검토 메모 도움말" placement="bottom-start" />
								</span>
								<p>{request.review_note}</p>
							</div>
						{/if}
					</div>

					<div class="card-actions">
						<span class="requested-at">{formatDateTime(request.created_at)}</span>
						{#if request.status === 'deployed' && request.target_container}
							<button class="monitor-btn" onclick={() => openDashboard(request)}>모니터링 열기</button>
						{:else if request.status === 'deployed'}
							<span class="pending-link">컨테이너 동기화 대기 중</span>
						{/if}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<NewRequestModal
	open={newModalOpen}
	onClose={() => (newModalOpen = false)}
	onSubmitted={load}
/>

<style>
	/* admin-shell parity: max-width 제거, padding clamp (관리자 / 와 동일 톤). */
	.page {
		padding: clamp(12px, 1vw, 22px) clamp(14px, 1.4vw, 28px) 32px;
		max-width: none;
		margin: 0;
	}

	.hero {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 14px;
		padding: clamp(10px, 0.7vw, 16px) clamp(14px, 1vw, 20px);
		margin-bottom: clamp(10px, 0.7vw, 14px);
		background:
			linear-gradient(135deg, rgba(48, 213, 200, 0.12), rgba(9, 75, 102, 0.14)),
			var(--bg-card);
		border: 1px solid rgba(48, 213, 200, 0.18);
		border-radius: 12px;
	}

	.eyebrow {
		display: none;
	}

	h1 {
		font-size: clamp(18px, 1.4vw, 24px);
		line-height: 1.1;
		margin-bottom: 4px;
		font-weight: 800;
	}

	.title-row,
	.name-row,
	.summary-label,
	.review-label {
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	.subtitle {
		font-size: 12px;
		color: var(--text-secondary);
		max-width: 720px;
	}

	.new-btn,
	.empty-btn,
	.monitor-btn {
		border: none;
		border-radius: 8px;
		padding: 8px 14px;
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
		background: var(--accent);
		color: var(--accent-dark);
	}

	.new-btn:hover,
		.empty-btn:hover,
		.monitor-btn:hover {
		filter: brightness(1.06);
	}

	/* FleetStatusBar 패턴: auto-fit minmax 로 화면폭에 맞춰 자동 분할.
	   1920에서 3개 균등, 좁아지면 그대로 wrap. */
	.summary-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(clamp(170px, 12vw, 240px), 1fr));
		gap: clamp(6px, 0.5vw, 12px);
		margin-bottom: clamp(10px, 0.7vw, 14px);
	}

	.summary-card {
		padding: clamp(9px, 0.6vw, 14px);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: clamp(6px, 0.4vw, 10px);
		display: flex;
		flex-direction: column;
		gap: 3px;
		min-height: clamp(80px, 6.5vh, 110px);
	}

	.summary-label {
		font-size: clamp(10px, 0.62vw, 13px);
		color: var(--text-muted);
		font-weight: 800;
		letter-spacing: 0.3px;
	}

	.summary-card strong {
		font-size: clamp(20px, 1.4vw, 28px);
		color: var(--text-primary);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.summary-meta {
		font-size: clamp(10px, 0.62vw, 13px);
		color: var(--text-muted);
		font-weight: 600;
		margin-top: auto;
	}

	.empty {
		padding: 60px 24px;
		text-align: center;
		background: rgba(18, 23, 32, 0.92);
		border: 1px solid var(--border);
		border-radius: 18px;
	}

	.empty-badge {
		display: inline-flex;
		padding: 6px 10px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 700;
		color: var(--accent);
		background: rgba(48, 213, 200, 0.12);
		margin-bottom: 14px;
	}

	.empty-title {
		font-size: 18px;
		font-weight: 700;
		margin-bottom: 6px;
	}

	.empty-text {
		font-size: 13px;
		color: var(--text-secondary);
		margin-bottom: 20px;
	}

	/* 요청 카드: vertical stack 대신 auto-fit grid 다열. 1920에서 ~3-4 column
	   minmax 440 = 한 카드 충분히 정보 표시 가능한 폭, 좁아지면 자동 wrap. */
	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
		gap: clamp(8px, 0.6vw, 14px);
		align-items: start;
	}

	.request-card {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		align-items: start;
		gap: 10px;
		padding: 12px 14px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 12px;
	}

	.card-main {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.card-heading {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		min-width: 0;
	}

	.request-identity {
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		gap: 0;
		min-width: 0;
		flex: 1 1 auto;
		align-items: start;
	}

	.request-mark {
		display: none;
		align-items: center;
		justify-content: center;
		width: 38px;
		height: 38px;
		border-radius: 10px;
		background:
			linear-gradient(135deg, rgba(48, 213, 200, 0.2), rgba(96, 165, 250, 0.08)),
			rgba(13, 17, 23, 0.72);
		border: 1px solid rgba(48, 213, 200, 0.24);
		color: var(--accent);
		font-size: 16px;
		font-weight: 950;
	}

	.request-copy {
		display: flex;
		flex-direction: column;
		gap: 5px;
		min-width: 0;
	}

	.name-row {
		min-width: 0;
		max-width: 100%;
	}

	.card-name {
		min-width: 0;
		font-size: 16px;
		line-height: 1.15;
		font-weight: 900;
		letter-spacing: 0;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.card-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-top: 0;
		font-size: 11.5px;
		color: var(--text-secondary);
		min-width: 0;
	}

	.card-meta span {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		max-width: 100%;
		padding: 3px 7px;
		background: rgba(13, 17, 23, 0.42);
		border: 1px solid rgba(100, 116, 139, 0.12);
		border-radius: 7px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.card-meta b {
		color: var(--text-muted);
		font-size: 9.5px;
		font-weight: 900;
		letter-spacing: 0.08em;
	}

	.card-status {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 6px;
	}

	.status-pill {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 24px;
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 11.5px;
		font-weight: 850;
		color: white;
		white-space: nowrap;
		box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset;
	}

	.card-time {
		font-size: 11px;
		color: var(--text-muted);
	}

	.progress-block {
		padding: 10px;
		background: rgba(13, 17, 23, 0.88);
		border: 1px solid rgba(31, 41, 55, 0.92);
		border-radius: 9px;
	}

	.progress-track {
		height: 7px;
		background: rgba(30, 41, 59, 0.85);
		border-radius: 999px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--accent), #6be6dc);
		transition: width 0.3s ease;
	}

	.progress-text {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		margin-top: 8px;
		font-size: 11px;
		color: var(--text-secondary);
	}

	.review-note {
		padding: 10px;
		background: rgba(21, 28, 39, 0.92);
		border-radius: 9px;
	}

	.review-label {
		font-size: 11px;
		font-weight: 700;
		color: var(--text-muted);
		margin-bottom: 4px;
	}

	.review-note p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.card-actions {
		min-width: 0;
		width: 100%;
		display: flex;
		flex-direction: row;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		padding-top: 6px;
		border-top: 1px solid rgba(100, 116, 139, 0.12);
	}

	.requested-at {
		font-size: 11px;
		color: var(--text-muted);
		text-align: left;
	}

	.pending-link {
		font-size: 12px;
		color: var(--text-secondary);
	}

	@media (max-width: 840px) {
		.page {
			padding: 20px 16px 28px;
		}

		.hero,
		.request-card,
		.card-heading {
			flex-direction: column;
			align-items: stretch;
		}

		.summary-grid {
			grid-template-columns: 1fr;
		}

		.cards {
			grid-template-columns: 1fr;
		}

		.card-status,
		.card-actions {
			align-items: flex-start;
		}
	}
</style>
