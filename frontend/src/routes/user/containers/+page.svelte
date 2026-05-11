<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import {
		formatDateTime,
		formatRelativeTime,
		statusLabel,
		statusTone,
	} from '$lib/utils/container-dashboard';

	type ContainerRow = {
		container_id: string;
		name: string;
		image: string;
		status: string;
		last_seen: string;
		agent_hostname?: string;
		template_name?: string | null;
		requested_at?: string | null;
		request_status?: string | null;
	};

	let loading = $state(false);
	let containers = $state<ContainerRow[]>([]);
	let search = $state('');
	let pollTimer: ReturnType<typeof setInterval> | null = null;
	const containersPageHelp = `이 페이지는 내가 요청해서 실제로 만들어진 컨테이너만 모아보는 목록입니다.

• 카드 클릭: 컨테이너 상세 모니터링 화면으로 이동
• 검색창: 이름, 이미지, 서버 이름으로 빠르게 찾기
• 상태 배지: 실행 중인지, 주의가 필요한지 바로 확인

배포가 완료된 요청만 이 목록에 나타납니다.`;
	const searchHelp = `검색창에서는 다음 정보를 한 번에 찾을 수 있습니다.

• 컨테이너 이름
• Docker 이미지 이름
• 배치된 서버 이름
• 요청에 사용한 템플릿 이름

일부만 입력해도 포함된 항목이 바로 걸러집니다.`;
	const summaryHelp = `오른쪽 숫자는 현재 보이는 전체 컨테이너 현황입니다.

• 전체: 목록에 있는 모든 컨테이너 수
• 실행 중: 정상 동작 중인 컨테이너 수
• 주의 필요: 일시정지 또는 재시작 상태인 컨테이너 수`;
	const cardStatusHelp = `카드에는 컨테이너의 핵심 정보가 요약되어 있습니다.

• 서버: 어느 서버에 배치되었는지
• 템플릿: 어떤 요청 템플릿으로 만들어졌는지
• 요청 시각: 처음 요청한 시간
• 최근 동기화: 상태 정보를 마지막으로 받은 시간`;

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function load() {
		const t = token();
		if (!t) return;
		loading = true;
		try {
			const res = await fetch(`${base}/api/my-containers/?page_size=100&ordering=-last_seen`, {
				headers: { Authorization: `Bearer ${t}` },
			});
			if (res.ok) {
				const json = await res.json();
				containers = json.data?.results ?? [];
			}
		} catch {
			// ignore
		} finally {
			loading = false;
		}
	}

	function openContainer(containerId: string) {
		goto(`${base}/user/containers/${containerId}`);
	}

	let filteredContainers = $derived(
		containers.filter((container) => {
			const keyword = search.trim().toLowerCase();
			if (!keyword) return true;
			return [
				container.name,
				container.image,
				container.agent_hostname,
				container.template_name,
			].some((value) => String(value ?? '').toLowerCase().includes(keyword));
		}),
	);

	let runningCount = $derived(containers.filter((container) => container.status === 'running').length);
	let warningCount = $derived(containers.filter((container) => ['paused', 'restarting'].includes(container.status)).length);
	let totalCount = $derived(containers.length);

	onMount(() => {
		load();
		pollTimer = setInterval(load, 15000);
		return () => {
			if (pollTimer) clearInterval(pollTimer);
		};
	});
</script>

<div class="page">
	<section class="page-header">
		<div>
			<p class="eyebrow">컨테이너 목록</p>
			<div class="title-row">
				<h1>내 컨테이너</h1>
				<InfoTooltip
					text={containersPageHelp}
					label="내 컨테이너 페이지 도움말"
					placement="bottom-start"
					maxWidth={380}
				/>
			</div>
			<p class="subtitle">현재 사용자 계정으로 요청한 컨테이너만 표시되며, 카드를 누르면 2D 모니터링 대시보드로 이동합니다.</p>
		</div>
		<button class="refresh-btn" onclick={load} disabled={loading}>
			{loading ? '새로고침 중...' : '새로고침'}
		</button>
	</section>

	<section class="toolbar">
		<div class="search-shell">
			<div class="search-label">
				<span>검색</span>
				<InfoTooltip text={searchHelp} label="검색 도움말" placement="bottom-start" maxWidth={360} />
			</div>
			<input bind:value={search} type="text" placeholder="이름, 이미지, 서버 이름으로 검색" />
		</div>
		<div class="summary" aria-label="컨테이너 요약">
			<span class="summary-title">
				현황 요약
				<InfoTooltip text={summaryHelp} label="현황 요약 도움말" placement="bottom-end" maxWidth={360} />
			</span>
			<span><strong>{totalCount}</strong> 전체</span>
			<span><strong>{runningCount}</strong> 실행 중</span>
			<span><strong>{warningCount}</strong> 주의 필요</span>
		</div>
	</section>

	{#if !loading && filteredContainers.length === 0}
		<div class="empty">
			<div class="empty-title">표시할 컨테이너가 없습니다</div>
			<p class="empty-text">요청이 배포 완료되면 이 목록에 컨테이너가 자동으로 나타납니다.</p>
		</div>
	{:else}
		<div class="grid">
			{#each filteredContainers as container (container.container_id)}
				<button class="container-card" onclick={() => openContainer(container.container_id)}>
					<div class="card-top">
						<div>
							<div class="name-row">
								<h2>{container.name}</h2>
								<InfoTooltip
									text={cardStatusHelp}
									label="컨테이너 카드 도움말"
									placement="bottom-start"
									maxWidth={360}
								/>
								<span class="status-pill" style="background: {statusTone(container.status)};">
									{statusLabel(container.status)}
								</span>
							</div>
							<p class="image">{container.image}</p>
						</div>
						<span class="last-seen">{formatRelativeTime(container.last_seen)}</span>
					</div>

					<div class="meta-grid">
						<div class="meta-item">
							<span class="meta-label">배치 서버</span>
							<span class="meta-value">{container.agent_hostname ?? '-'}</span>
						</div>
						<div class="meta-item">
							<span class="meta-label">템플릿</span>
							<span class="meta-value">{container.template_name ?? '-'}</span>
						</div>
						<div class="meta-item">
							<span class="meta-label">요청 시각</span>
							<span class="meta-value">{formatDateTime(container.requested_at)}</span>
						</div>
						<div class="meta-item">
							<span class="meta-label">최근 동기화</span>
							<span class="meta-value">{formatDateTime(container.last_seen)}</span>
						</div>
					</div>

					<div class="card-footer">
						<span class="request-status">요청 상태: {statusLabel(container.request_status)}</span>
						<span class="open-link">대시보드 열기</span>
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	/* admin-shell parity: max-width 제거, padding clamp. */
	.page {
		max-width: none;
		margin: 0;
		padding: clamp(12px, 1vw, 22px) clamp(14px, 1.4vw, 28px) 32px;
	}

	.page-header,
	.toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 14px;
	}

	.page-header {
		margin-bottom: clamp(8px, 0.6vw, 12px);
		padding: clamp(8px, 0.6vw, 14px) clamp(12px, 1vw, 18px);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 12px;
	}

	.eyebrow {
		display: none;
	}

	h1 {
		font-size: clamp(18px, 1.4vw, 24px);
		margin-bottom: 4px;
		font-weight: 800;
	}

	.title-row,
	.search-label,
	.summary-title {
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	.subtitle {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.refresh-btn {
		padding: 7px 12px;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--bg-card);
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
		flex-shrink: 0;
	}

	.toolbar {
		margin-bottom: clamp(10px, 0.7vw, 14px);
	}

	.search-shell {
		flex: 1;
		max-width: 480px;
		padding: 8px 12px;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: var(--bg-card);
	}

	.search-label {
		font-size: 11px;
		font-weight: 700;
		color: var(--text-secondary);
		margin-bottom: 8px;
	}

	.search-shell input {
		width: 100%;
		border: none;
		outline: none;
		background: transparent;
		color: var(--text-primary);
		font-size: 13px;
	}

	.search-shell input::placeholder {
		color: var(--text-muted);
	}

	.summary {
		display: flex;
		align-items: center;
		gap: 14px;
		flex-wrap: wrap;
		font-size: 12px;
		color: var(--text-secondary);
	}

	.summary-title {
		font-size: 11px;
		font-weight: 700;
		color: var(--text-muted);
		margin-right: 2px;
	}

	.summary strong {
		color: var(--text-primary);
		font-size: 16px;
		margin-right: 4px;
	}

	.empty {
		padding: 54px 20px;
		text-align: center;
		background: rgba(18, 23, 32, 0.94);
		border: 1px solid var(--border);
		border-radius: 18px;
	}

	.empty-title {
		font-size: 18px;
		font-weight: 700;
		margin-bottom: 6px;
	}

	.empty-text {
		font-size: 13px;
		color: var(--text-secondary);
	}

	/* auto-fit minmax 다열 — 1920에서 ~5열, 1440에서 ~4열, 1280에서 ~3열. */
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
		gap: clamp(8px, 0.6vw, 14px);
	}

	.container-card {
		padding: clamp(12px, 0.8vw, 16px);
		text-align: left;
		background:
			linear-gradient(180deg, rgba(48, 213, 200, 0.06), transparent 28%),
			var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 12px;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: 12px;
		transition: transform 0.14s ease, border-color 0.14s ease;
	}

	.container-card:hover {
		transform: translateY(-2px);
		border-color: rgba(48, 213, 200, 0.4);
	}

	.card-top {
		display: flex;
		justify-content: space-between;
		gap: 12px;
	}

	.name-row {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	h2 {
		font-size: 15px;
		color: var(--text-primary);
		font-weight: 700;
	}

	.status-pill {
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 700;
		color: white;
	}

	.image {
		margin-top: 6px;
		font-size: 12px;
		color: var(--text-secondary);
		word-break: break-all;
	}

	.last-seen {
		font-size: 11px;
		color: var(--text-muted);
		white-space: nowrap;
	}

	.meta-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}

	.meta-item {
		padding: 12px;
		background: rgba(13, 17, 23, 0.8);
		border: 1px solid rgba(31, 41, 55, 0.86);
		border-radius: 12px;
	}

	.meta-label {
		display: block;
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 4px;
	}

	.meta-value {
		font-size: 12px;
		color: var(--text-primary);
	}

	.card-footer {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		align-items: center;
		font-size: 12px;
	}

	.request-status {
		color: var(--text-secondary);
	}

	.open-link {
		color: var(--accent);
		font-weight: 700;
	}

	@media (max-width: 900px) {
		.page {
			padding: 20px 16px 28px;
		}

		.page-header,
		.toolbar,
		.card-top,
		.card-footer {
			flex-direction: column;
			align-items: stretch;
		}

		.grid,
		.meta-grid {
			grid-template-columns: 1fr;
		}

		.last-seen {
			white-space: normal;
		}
	}
</style>
