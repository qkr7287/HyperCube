<script lang="ts">
	import type { FleetAgentRow } from '$lib/stores/fleet-store';
	import { formatPercent, formatRate, formatRelative, healthLabel, humanizeReason, shortReason } from '$lib/utils/fleet-format';
	import MetricHelp from './MetricHelp.svelte';
	import MetricSparkline from './MetricSparkline.svelte';

	let {
		agent,
		selected = false,
		onSelect = () => {},
		onOpen2d,
		onOpen3d,
		canManage = false,
		onDeleted,
	}: {
		agent: FleetAgentRow;
		selected?: boolean;
		onSelect?: (agentId: string) => void;
		onOpen2d?: (agentId: string) => void;
		onOpen3d?: (agentId: string) => void;
		// admin 만 톱니바퀴 메뉴 노출. backend (IsSuperAdmin=IsAdmin) 가 어차피
		// 한 번 더 막지만, 일반 사용자에겐 안 보이는 게 UX 깔끔.
		canManage?: boolean;
		onDeleted?: (agentId: string) => void;
	} = $props();

	import { base } from '$app/paths';

	let menuOpen = $state(false);
	let modalOpen = $state(false);
	let deleting = $state(false);
	let deleteError = $state<string | null>(null);

	function toggleMenu(e: MouseEvent) {
		e.stopPropagation();
		menuOpen = !menuOpen;
		deleteError = null;
	}

	function closeMenu() {
		menuOpen = false;
	}

	function openDeleteModal(e: MouseEvent) {
		e.stopPropagation();
		menuOpen = false;
		modalOpen = true;
		deleteError = null;
	}

	function closeModal() {
		if (deleting) return;
		modalOpen = false;
	}

	async function confirmDelete() {
		deleting = true;
		deleteError = null;
		try {
			const token = localStorage.getItem('hc_access_token') || '';
			const res = await fetch(`${base}/api/agents/${agent.agent.id}/`, {
				method: 'DELETE',
				headers: { Authorization: `Bearer ${token}` },
			});
			if (res.status === 204 || res.ok) {
				modalOpen = false;
				onDeleted?.(agent.agent.id);
			} else if (res.status === 403) {
				deleteError = '권한이 없습니다 (admin 전용).';
			} else {
				deleteError = `삭제 실패 (HTTP ${res.status})`;
			}
		} catch (err) {
			deleteError = String(err);
		} finally {
			deleting = false;
		}
	}

	let hasGpu = $derived((agent.latest?.gpu_count ?? 0) > 0);

	function severity(value: number, warn: number, crit: number): 'normal' | 'warn' | 'danger' {
		if (value >= crit) return 'danger';
		if (value >= warn) return 'warn';
		return 'normal';
	}

	// GPU 온도: 실측 (gpu_temperature_max from agent). nvidia-smi 보고 안 들어오면 null.
	// 전력: 실측 없음 → GPU 사용률 기반 선형 추정. idle 30W + (TDP−idle)·usage/100,
	// TDP 기본값 300W (일반적 데이터센터 GPU 대표값). 모델 다양해서 실측과 ±100W 오차 가능.
	const POWER_TDP_W = 300;
	const POWER_IDLE_W = 30;
	let gpuTemp = $derived<number | null>(agent.latest?.gpu_temperature ?? null);
	let estimatedPowerW = $derived(
		hasGpu
			? POWER_IDLE_W + (POWER_TDP_W - POWER_IDLE_W) * (Math.max(0, Math.min(100, agent.latest?.gpu_usage ?? 0)) / 100)
			: 0,
	);
	function tempLevel(t: number | null): 'normal' | 'warn' | 'danger' {
		if (t == null) return 'normal';
		if (t >= 85) return 'danger';
		if (t >= 75) return 'warn';
		return 'normal';
	}
	let gpuTempLevel = $derived(tempLevel(gpuTemp));

	let cpuLevel = $derived(severity(agent.latest?.cpu_usage ?? 0, 70, 90));
	let memLevel = $derived(severity(agent.latest?.memory_usage ?? 0, 75, 90));
	let gpuLevel = $derived(severity(agent.latest?.gpu_usage ?? 0, 80, 95));

	const CHART_COLORS = {
		cpu: '#30d5c8',
		memory: '#60a5fa',
		network: '#fbbf24',
		gpu: '#f472b6',
	};

	let networkTotal = $derived((agent.latest?.network_rx_rate ?? 0) + (agent.latest?.network_tx_rate ?? 0));
	let networkSeries = $derived.by(() => {
		const rx = agent.sparkline.rx ?? [];
		const tx = agent.sparkline.tx ?? [];
		const len = Math.max(rx.length, tx.length);
		const out: number[] = [];
		for (let i = 0; i < len; i += 1) {
			out.push((rx[i] ?? 0) + (tx[i] ?? 0));
		}
		return out;
	});

	type CompactRow = {
		key: string;
		label: string;
		display: string;
		title: string;
		level: 'normal' | 'warn' | 'danger';
		color: string;
		series: number[];
	};

	// reason 표시에서 디스크 항목 제외 (사용자 요청 — 카드 폭 wrap 줄임)
	let visibleReasons = $derived(agent.health_reasons.filter((r) => !/^Disk\s*>=/i.test(r)));

	let compactRows = $derived.by(() => {
		const cpuValue = agent.latest?.cpu_usage ?? 0;
		const memValue = agent.latest?.memory_usage ?? 0;
		const gpuValue = agent.latest?.gpu_usage ?? 0;
		const rows: CompactRow[] = [
			{
				key: 'cpu',
				label: 'CPU',
				display: formatPercent(cpuValue, 0),
				title: `CPU 사용률 ${formatPercent(cpuValue, 1)}`,
				level: cpuLevel,
				color: CHART_COLORS.cpu,
				series: agent.sparkline.cpu,
			},
			{
				key: 'mem',
				label: 'MEM',
				display: formatPercent(memValue, 0),
				title: `메모리 사용률 ${formatPercent(memValue, 1)}`,
				level: memLevel,
				color: CHART_COLORS.memory,
				series: agent.sparkline.memory,
			},
			{
				key: 'net',
				label: 'NET',
				display: formatRate(networkTotal),
				title: `네트워크 ↓ ${formatRate(agent.latest?.network_rx_rate)} · ↑ ${formatRate(agent.latest?.network_tx_rate)}`,
				level: 'normal',
				color: CHART_COLORS.network,
				series: networkSeries,
			},
		];
		if (hasGpu) {
			rows.push({
				key: 'gpu',
				label: 'GPU',
				display: formatPercent(gpuValue, 0),
				title: `GPU 사용률 ${formatPercent(gpuValue, 1)}`,
				level: gpuLevel,
				color: CHART_COLORS.gpu,
				series: agent.sparkline.gpu,
			});
		}
		return rows;
	});

	function handleMonitor(event: MouseEvent) {
		event.stopPropagation();
		onOpen3d?.(agent.agent.id);
	}

	function handleMonitor2d(event: MouseEvent) {
		event.stopPropagation();
		onOpen2d?.(agent.agent.id);
	}

	function handleCardClick() {
		onSelect(agent.agent.id);
	}

	function handleCardKey(event: KeyboardEvent) {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			onSelect(agent.agent.id);
		}
	}
</script>

<div
	class="card {agent.health}"
	class:selected
	role="button"
	tabindex="0"
	onclick={handleCardClick}
	onkeydown={handleCardKey}
>
	<header class="card-head">
		<div class="title">
			<span class="title-line">
				{#if agent.agent.is_active}
					<span class="live-dot" aria-hidden="true" title="Agent 실시간 연결 중"></span>
				{/if}
				<strong class="hostname" title={agent.agent.hostname}>{agent.agent.hostname}</strong>
			</span>
			<span class="ip-row">{agent.agent.ip_address}</span>
		</div>
		<div class="head-actions">
			<span class="health-tag {agent.health}">{healthLabel(agent.health)}</span>
			<MetricHelp text={"각 막대 = 리소스 사용률(%)\n0% = 거의 안 씀, 100% = 완전 사용 중\n\n위험 임계\n• CPU 90% / 메모리 90%\n• 디스크 90% / GPU 95%"} />
			{#if onOpen2d}
				{@const isSim = agent.agent.id.startsWith('sim-')}
				<button
					type="button"
					class="monitor-btn monitor-2d"
					class:disabled={isSim}
					disabled={isSim}
					onclick={handleMonitor2d}
					title={isSim ? '시뮬레이션 서버는 2D 뷰로 연결할 실제 데이터가 없습니다' : '이 서버를 2D 관제 대시보드에서 상세 모니터링'}
				>
					<span aria-hidden="true">▦</span>
					<span class="monitor-label">2D</span>
				</button>
			{/if}
			{#if onOpen3d}
				{@const isSim = agent.agent.id.startsWith('sim-')}
				<button
					type="button"
					class="monitor-btn"
					class:disabled={isSim}
					disabled={isSim}
					onclick={handleMonitor}
					title={isSim ? '시뮬레이션 서버는 3D 뷰로 연결할 실제 토폴로지가 없습니다' : '이 서버를 3D 토폴로지 뷰에서 상세 모니터링'}
				>
					<span aria-hidden="true">◆</span>
					<span class="monitor-label">3D</span>
				</button>
			{/if}
			{#if canManage}
				<div class="settings-wrap" role="presentation" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
					<button
						type="button"
						class="settings-btn"
						aria-label="Agent 관리"
						title="Agent 관리"
						onclick={toggleMenu}
					>
						<span aria-hidden="true">⚙</span>
					</button>
					{#if menuOpen}
						<div class="settings-menu" role="menu">
							<button type="button" class="menu-item danger" onclick={openDeleteModal}>
								Agent 삭제
							</button>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	</header>

	{#if modalOpen}
		<div
			class="modal-backdrop"
			role="presentation"
			onclick={closeModal}
			onkeydown={(e) => e.stopPropagation()}
		>
			<div
				class="modal"
				role="dialog"
				aria-modal="true"
				aria-labelledby="delete-agent-title-{agent.agent.id}"
				onclick={(e) => e.stopPropagation()}
			>
				<h3 id="delete-agent-title-{agent.agent.id}" class="modal-title">Agent 삭제 확인</h3>
				<p class="modal-body">
					<strong>{agent.agent.hostname}</strong> 을(를) 정말 삭제하시겠습니까?<br />
					이 동작은 되돌릴 수 없으며, 연결된 컨테이너·메트릭 이력도 함께 삭제됩니다.
				</p>
				{#if deleteError}
					<div class="modal-error">{deleteError}</div>
				{/if}
				<div class="modal-actions">
					<button type="button" class="modal-btn" disabled={deleting} onclick={closeModal}>
						취소
					</button>
					<button type="button" class="modal-btn danger" disabled={deleting} onclick={confirmDelete}>
						{deleting ? '삭제 중…' : '삭제'}
					</button>
				</div>
			</div>
		</div>
	{/if}

	<div class="compact-body">
		<div class="metric-cards" class:has-gpu={hasGpu}>
			{#each compactRows as row}
				<div class="metric-card" data-level={row.level} title={row.title}>
					<div class="mc-head">
						<span class="mc-label" style={`color: ${row.color};`}>{row.label}</span>
						<strong class="mc-value">{row.display}</strong>
					</div>
					<div class="mc-chart">
						<MetricSparkline values={row.series} color={row.color} label={row.label} />
					</div>
				</div>
			{/each}
		</div>
		<div class="compact-foot">
			<span class="ct-chip running" title="실행 중 컨테이너"><b>{agent.containers.running ?? 0}</b> 실행</span>
			<span class="ct-chip other" title="정지·종료·일시정지 컨테이너"><b>{agent.containers.non_running ?? 0}</b> 기타</span>
			<span class="ct-chip problem" class:active={(agent.containers.problem ?? 0) > 0} title="재시작·비정상(dead) 상태의 컨테이너">
				<b>{agent.containers.problem ?? 0}</b> 이상
			</span>
			{#if hasGpu}
				<span class="ct-chip thermal" data-level={gpuTempLevel} title={gpuTemp != null ? `GPU 최고 온도 (nvidia-smi 실측, 임계 75/85°C)` : 'nvidia-smi 가 온도값을 보내지 않음'}>
					<b>{gpuTemp != null ? `${Math.round(gpuTemp)}°C` : '—'}</b> 온도
				</span>
				<span class="ct-chip power" title={`GPU 사용률 기반 추정치 · TDP ${POWER_TDP_W}W 가정 (실제 모델에 따라 ±100W 오차)`}>
					<b>~{Math.round(estimatedPowerW)}W</b> 전력
				</span>
			{/if}
			{#if visibleReasons.length > 0}
				<span class="reason-chip" title={visibleReasons.map(humanizeReason).join(' · ')}>
					{shortReason(visibleReasons[0])}
					{#if visibleReasons.length > 1}
						<b>+{visibleReasons.length - 1}</b>
					{/if}
				</span>
			{/if}
			<span class="age-small" title="최신 메트릭 수신 시점">{formatRelative(agent.latest?.timestamp)}</span>
		</div>
	</div>
</div>

<style>
	.card {
		--card-radius: clamp(8px, 0.5vw, 12px);
		--card-pad: clamp(8px, 0.55vw, 14px);
		--card-gap: clamp(4px, 0.35vw, 8px);
		--font-xs: clamp(10px, 0.62vw, 13px);
		--font-sm: clamp(11px, 0.72vw, 15px);
		--font-md: clamp(13px, 0.85vw, 17px);

		width: 100%;
		height: 100%;
		min-width: 0;
		min-height: 0;
		padding: var(--card-pad);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-left: 3px solid var(--border);
		border-radius: var(--card-radius);
		color: inherit;
		font-family: inherit;
		text-align: left;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: var(--card-gap);
		position: relative;
		transition: border-color 0.12s ease, background 0.12s ease;
	}
	.card:hover {
		background: var(--bg-tab);
	}
	.card.selected {
		outline: 1px solid rgba(48, 213, 200, 0.55);
		outline-offset: -1px;
	}
	.card.critical {
		border-left-color: #ef4444;
		background: linear-gradient(180deg, rgba(239, 68, 68, 0.08), var(--bg-card) 55%);
	}
	.card.warning {
		border-left-color: #f59e0b;
		background: linear-gradient(180deg, rgba(245, 158, 11, 0.06), var(--bg-card) 55%);
	}
	.card.stale { border-left-color: #a78bfa; }
	.card.offline { border-left-color: #64748b; }
	.card.healthy { border-left-color: #34d399; }

	.card-head {
		display: flex;
		justify-content: space-between;
		gap: var(--card-gap);
		align-items: center;
	}
	.title {
		min-width: 0;
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 3px;
	}
	.title-line {
		display: flex;
		align-items: center;
		flex-wrap: nowrap;
		gap: 8px;
		min-width: 0;
		width: 100%;
	}
	.ip-row {
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		letter-spacing: 0;
		line-height: 1.1;
		padding-left: 15px; /* live-dot(7) + gap(8) 만큼 들여쓰기 */
	}
	.title strong.hostname {
		color: var(--text-primary);
		font-size: var(--font-sm);
		font-weight: 800;
		letter-spacing: -0.1px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
		flex: 0 1 auto;
	}
	.meta {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
		font-size: var(--font-xs);
	}
	.health-tag {
		display: inline-flex;
		align-items: center;
		padding: 2px 7px;
		height: 22px;
		border-radius: var(--radius-sm);
		font-size: var(--font-xs);
		font-weight: 800;
		letter-spacing: 0.3px;
		white-space: nowrap;
	}
	.health-tag.healthy { color: #34d399; background: rgba(52, 211, 153, 0.14); }
	.health-tag.warning { color: #fbbf24; background: rgba(245, 158, 11, 0.18); }
	.health-tag.critical { color: #f87171; background: rgba(239, 68, 68, 0.18); }
	.health-tag.stale { color: #c4b5fd; background: rgba(167, 139, 250, 0.18); }
	.health-tag.offline { color: #cbd5e1; background: rgba(100, 116, 139, 0.18); }

	.head-actions {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		flex-wrap: nowrap;
		flex-shrink: 0;
	}
	.monitor-btn {
		height: clamp(20px, 1.35vw, 26px);
		padding: 0 clamp(6px, 0.45vw, 11px);
		display: inline-flex;
		align-items: center;
		gap: 4px;
		border: 1px solid rgba(48, 213, 200, 0.6);
		border-radius: var(--radius-sm);
		background: linear-gradient(rgba(48, 213, 200, 0.18), rgba(48, 213, 200, 0.18)), var(--bg-card);
		color: var(--accent);
		font-family: inherit;
		font-size: var(--font-xs);
		font-weight: 800;
		letter-spacing: 0.2px;
		cursor: pointer;
		transition: background 0.12s ease, border-color 0.12s ease;
		white-space: nowrap;
	}
	.monitor-btn:hover:not(.disabled) {
		background: linear-gradient(rgba(48, 213, 200, 0.3), rgba(48, 213, 200, 0.3)), var(--bg-card);
		border-color: rgba(48, 213, 200, 0.8);
	}
	.monitor-btn.monitor-2d {
		border-color: rgba(96, 165, 250, 0.55);
		background: linear-gradient(rgba(96, 165, 250, 0.18), rgba(96, 165, 250, 0.18)), var(--bg-card);
		color: #60a5fa;
	}
	.monitor-btn.monitor-2d:hover:not(.disabled) {
		background: linear-gradient(rgba(96, 165, 250, 0.3), rgba(96, 165, 250, 0.3)), var(--bg-card);
		border-color: rgba(96, 165, 250, 0.8);
	}
	.monitor-btn.disabled,
	.monitor-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
		background: rgba(100, 116, 139, 0.1);
		color: var(--text-muted);
		border-color: rgba(100, 116, 139, 0.3);
	}

	.settings-wrap {
		position: relative;
		display: inline-flex;
	}
	.settings-btn {
		width: 28px;
		height: 28px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 1px solid rgba(148, 163, 184, 0.55);
		border-radius: var(--radius-sm, 4px);
		background: rgba(148, 163, 184, 0.12);
		color: var(--text-primary);
		font-size: 15px;
		line-height: 1;
		cursor: pointer;
		transition: background 0.12s ease, border-color 0.12s ease, transform 0.12s ease;
	}
	.settings-btn:hover {
		background: rgba(148, 163, 184, 0.28);
		border-color: rgba(148, 163, 184, 0.9);
		transform: rotate(30deg);
	}
	.settings-menu {
		position: absolute;
		top: calc(100% + 4px);
		right: 0;
		min-width: 140px;
		padding: 4px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md, 6px);
		box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
		z-index: 50;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.menu-item {
		display: block;
		width: 100%;
		padding: 6px 10px;
		border: none;
		background: transparent;
		color: var(--text-primary);
		font-size: 12px;
		text-align: left;
		border-radius: 4px;
		cursor: pointer;
	}
	.menu-item:hover:not(:disabled) {
		background: var(--bg-tab);
	}
	.menu-item.danger {
		color: #ef4444;
	}
	.menu-item.danger:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.12);
	}
	.menu-item:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.modal-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(2, 6, 23, 0.65);
		backdrop-filter: blur(2px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 200;
	}
	.modal {
		min-width: 320px;
		max-width: 440px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md, 8px);
		padding: 18px 20px 14px;
		box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
	}
	.modal-title {
		margin: 0 0 10px;
		font-size: 14px;
		font-weight: 800;
		color: var(--text-primary);
	}
	.modal-body {
		margin: 0 0 14px;
		font-size: 12.5px;
		line-height: 1.55;
		color: var(--text-secondary);
	}
	.modal-body strong {
		color: var(--text-primary);
	}
	.modal-error {
		margin-bottom: 10px;
		padding: 6px 10px;
		font-size: 11.5px;
		color: #ef4444;
		background: rgba(239, 68, 68, 0.1);
		border-radius: 4px;
	}
	.modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}
	.modal-btn {
		padding: 6px 14px;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm, 4px);
		background: transparent;
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 700;
		cursor: pointer;
	}
	.modal-btn:hover:not(:disabled) {
		background: var(--bg-tab);
	}
	.modal-btn.danger {
		border-color: rgba(239, 68, 68, 0.6);
		background: rgba(239, 68, 68, 0.12);
		color: #ef4444;
	}
	.modal-btn.danger:hover:not(:disabled) {
		background: rgba(239, 68, 68, 0.22);
	}
	.modal-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.reason-chip {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		padding: 1px 6px;
		border-radius: var(--radius-sm);
		background: rgba(239, 68, 68, 0.14);
		color: #fca5a5;
		border: 1px solid rgba(239, 68, 68, 0.22);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 700;
		white-space: nowrap;
		line-height: 1.3;
	}
	.reason-chip b {
		font-weight: 800;
		opacity: 0.75;
	}
	.card.warning .reason-chip {
		background: rgba(245, 158, 11, 0.14);
		color: #fcd34d;
		border-color: rgba(245, 158, 11, 0.25);
	}
	.card.stale .reason-chip {
		background: rgba(167, 139, 250, 0.12);
		color: #c4b5fd;
		border-color: rgba(167, 139, 250, 0.25);
	}
	.card.offline .reason-chip {
		background: rgba(100, 116, 139, 0.16);
		color: #cbd5e1;
		border-color: rgba(100, 116, 139, 0.25);
	}

	.compact-body {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: clamp(5px, 0.4vw, 10px);
		overflow: hidden;
	}
	.metric-cards {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: clamp(4px, 0.4vw, 8px);
		flex: 1;
		min-height: 0;
		min-width: 0;
	}
	.metric-cards.has-gpu {
		grid-template-columns: repeat(4, minmax(0, 1fr));
	}
	.metric-card {
		min-width: 0;
		min-height: 0;
		padding: clamp(5px, 0.45vw, 9px);
		background: rgba(13, 17, 23, 0.55);
		border: 1px solid rgba(148, 163, 184, 0.12);
		border-radius: var(--radius-sm);
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		gap: clamp(4px, 0.35vw, 7px);
		overflow: hidden;
		/* 카드 폭 기준 컨테이너 — mc-head 가로/세로 전환의 기준 */
		container-type: inline-size;
	}
	.metric-card[data-level='warn'] {
		border-color: rgba(251, 191, 36, 0.3);
	}
	.metric-card[data-level='warn'] .mc-value {
		color: #fbbf24;
	}
	.metric-card[data-level='danger'] {
		border-color: rgba(248, 113, 113, 0.35);
	}
	.metric-card[data-level='danger'] .mc-value {
		color: #f87171;
	}
	/* 기본(좁은 카드): 라벨 위·값 아래 세로 스택 — 값이 라벨과 폭 경쟁 안 해 안 잘림 */
	.mc-head {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 2px;
		min-width: 0;
	}
	/* 카드가 충분히 넓으면 라벨·값을 한 줄로 (컴팩트) */
	@container (min-width: 120px) {
		.mc-head {
			flex-direction: row;
			justify-content: space-between;
			align-items: baseline;
			gap: 4px;
		}
	}
	.mc-label {
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.mc-value {
		color: var(--text-primary);
		font-size: var(--font-sm);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		line-height: 1;
		white-space: nowrap;
	}
	.mc-chart {
		flex: 1;
		min-height: 22px;
		display: flex;
		overflow: hidden;
	}
	.mc-chart :global(.spark-wrap) {
		width: 100%;
		height: 100%;
	}
	.mc-chart :global(svg.spark) {
		width: 100%;
		height: 100%;
		max-width: none;
		min-width: 0;
	}
	.compact-foot {
		display: flex;
		align-items: center;
		gap: 4px;
		flex-wrap: wrap;
		padding-top: 4px;
		border-top: 1px solid rgba(100, 116, 139, 0.15);
	}
	.ct-chip {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		padding: 2px 5px;
		border-radius: var(--radius-sm);
		background: rgba(13, 17, 23, 0.55);
		color: var(--text-secondary);
		font-weight: 700;
		white-space: nowrap;
		flex: 0 0 auto;
		font-size: calc(var(--font-xs) - 1px);
	}
	.ct-chip b {
		color: var(--text-primary);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
	}
	.ct-chip.running b {
		color: #34d399;
	}
	.ct-chip.problem.active {
		background: rgba(239, 68, 68, 0.14);
	}
	.ct-chip.problem.active b {
		color: #f87171;
	}

	/* GPU thermal chips — 온도(실측, severity) / 전력(추정, neutral). */
	.ct-chip.thermal b { color: #fda4af; }
	.ct-chip.thermal[data-level='warn'] {
		background: rgba(251, 191, 36, 0.12);
	}
	.ct-chip.thermal[data-level='warn'] b { color: #fde68a; }
	.ct-chip.thermal[data-level='danger'] {
		background: rgba(239, 68, 68, 0.14);
	}
	.ct-chip.thermal[data-level='danger'] b { color: #fca5a5; }
	.ct-chip.power b { color: #c4b5fd; }
	.age-small {
		margin-left: auto;
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 700;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.live-dot {
		display: inline-block;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #34d399;
		box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.7);
		animation: live-pulse 1.6s ease-out infinite;
	}
	@keyframes live-pulse {
		0%   { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0.55); }
		70%  { box-shadow: 0 0 0 6px rgba(52, 211, 153, 0); }
		100% { box-shadow: 0 0 0 0 rgba(52, 211, 153, 0); }
	}
</style>
