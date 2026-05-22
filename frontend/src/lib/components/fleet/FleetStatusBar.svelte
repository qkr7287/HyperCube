<script lang="ts">
	import { onDestroy } from 'svelte';
	import MetricHelp from './MetricHelp.svelte';
	import MetricSparkline from './MetricSparkline.svelte';
	import { formatPercent, formatRate } from '$lib/utils/fleet-format';
	import type { FleetHistoryPoint, FleetSummary } from '$lib/stores/fleet-store';
	import { fleetEvents, fleetEventWindow, fleetAgents, acknowledgeResourceEvent } from '$lib/stores/fleet-store';
	import { metricLabel } from '$lib/utils/fleet-events';
	import ResourceEventHistoryModal from './ResourceEventHistoryModal.svelte';

	let {
		summary,
		history = [],
		connected = false,
	}: {
		summary: FleetSummary | null;
		history?: FleetHistoryPoint[];
		connected?: boolean;
	} = $props();

	let counts = $derived(summary?.agent_counts ?? {});
	let metrics = $derived(summary?.metric_summary ?? null);

	let cpuTrend = $derived(history.map((point) => point.cpu_avg));
	let memTrend = $derived(history.map((point) => point.memory_avg));
	let diskTrend = $derived(history.map((point) => point.disk_avg));
	let gpuTrend = $derived(history.map((point) => point.gpu_avg ?? 0));
	let netTrend = $derived(history.map((point) => point.network_rx_rate + point.network_tx_rate));
	let gpuActive = $derived(
		gpuTrend.some((value) => value > 0)
			|| (metrics?.gpu_max ?? 0) > 0
			|| (metrics?.gpu_memory_total_bytes ?? 0) > 0,
	);

	function formatBytes(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B';
		const units = ['B', 'KB', 'MB', 'GB', 'TB'];
		let next = value;
		let index = 0;
		while (next >= 1024 && index < units.length - 1) {
			next /= 1024;
			index += 1;
		}
		return `${next.toFixed(next >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
	}

	function count(key: string): number {
		return Number(counts[key] ?? 0);
	}

	function severity(value: number, warn: number, crit: number): 'normal' | 'warn' | 'danger' {
		if (value >= crit) return 'danger';
		if (value >= warn) return 'warn';
		return 'normal';
	}

	let cpuLevel = $derived(severity(metrics?.cpu_max ?? 0, 70, 90));
	let memLevel = $derived(severity(metrics?.memory_max ?? 0, 75, 90));
	let diskLevel = $derived(severity(metrics?.disk_max ?? 0, 80, 90));
	let gpuLevel = $derived(severity(metrics?.gpu_max ?? 0, 80, 95));

	let historyOpen = $state(false);

	let criticalCount = $derived($fleetEvents.filter((event) => event.severity === 'critical').length);

	// 카드는 2개 고정 슬롯 — 빈 슬롯은 placeholder, 3개 이상이면 상위 2건만 노출.
	let slotEvents = $derived([$fleetEvents[0] ?? null, $fleetEvents[1] ?? null]);

	// 헤더 요약 — 최근 1시간 발생 이벤트(종료 포함)의 심각도별 집계.
	let windowCritical = $derived(
		$fleetEventWindow.filter((event) => event.severity === 'critical').length,
	);
	let windowWarning = $derived(
		$fleetEventWindow.filter((event) => event.severity === 'warning').length,
	);

	// 우측 1/3 — 서버 구성 현황. GPU 장착 여부로 나눈다.
	let gpuServerCount = $derived(
		$fleetAgents.filter((row) => (row.latest?.gpu_count ?? 0) > 0).length,
	);
	let normalServerCount = $derived($fleetAgents.length - gpuServerCount);

	// 이벤트 타일의 상대 시각 라벨을 주기적으로 갱신 (30초 단위면 충분).
	let now = $state(Date.now());
	const tick = setInterval(() => (now = Date.now()), 30000);
	onDestroy(() => clearInterval(tick));

	function eventAgo(ts: number): string {
		if (!ts) return '';
		const sec = Math.floor((now - ts) / 1000);
		if (sec < 10) return '방금';
		if (sec < 60) return `${sec}초 전`;
		if (sec < 3600) return `${Math.floor(sec / 60)}분 전`;
		if (sec < 86400) return `${Math.floor(sec / 3600)}시간 전`;
		return `${Math.floor(sec / 86400)}일 전`;
	}
</script>

<section class="status-bar" class:with-gpu={gpuActive} aria-label="전체 서버 요약">
	<div class="kpi kpi-state" class:danger={count('critical') > 0}>
		<span class="label">
			<span class="dot" class:danger={count('critical') > 0} class:offline={!connected}></span>
			전체 서버
			<MetricHelp text="대시보드에서 감시 중인 승인된 서버의 상태입니다. 아래 위험·주의·지연·중지(오프라인) 카운트로 어떤 상태에 몇 대가 있는지 확인합니다." />
		</span>
		<div class="state-body">
			<div class="state-main">
				<div class="state-row">
					<strong>{count('online')}</strong>
					<span class="slash">/ {count('total')} 온라인</span>
				</div>
				<div class="state-chips">
					<span class="chip critical" class:zero={count('critical') === 0} title="위험: CPU/메모리/디스크/GPU 중 하나가 임계치를 넘었거나 컨테이너 장애·재시작 발생">위험 <b>{count('critical')}</b></span>
					<span class="chip warning" class:zero={count('warning') === 0} title="주의: 자원 사용률이 경고 구간에 있거나 일시정지·고부하 컨테이너가 있음">주의 <b>{count('warning')}</b></span>
					<span class="chip stale" class:zero={count('stale') === 0} title="지연: Agent가 보고는 하지만 마지막 메트릭이 1분 이상 늦게 도착했음">지연 <b>{count('stale')}</b></span>
					<span class="chip offline" class:zero={count('offline') === 0} title="중지: Agent와의 연결이 끊겨 메트릭이 수신되지 않음 (오프라인)">중지 <b>{count('offline')}</b></span>
				</div>
			</div>
			<div class="ss-grid">
				<div class="ss-item gpu">
					<span class="ss-num">{gpuServerCount}</span>
					<span class="ss-label">GPU 서버</span>
				</div>
				<div class="ss-item">
					<span class="ss-num">{normalServerCount}</span>
					<span class="ss-label">일반 서버</span>
				</div>
			</div>
		</div>
	</div>

	<div class="kpi" data-level={cpuLevel}>
		<span class="label">CPU <MetricHelp text={"모든 서버 CPU 사용률의 평균과 최대치.\n\n개별 서버 기준\n• 논리 코어 사용량의 평균\n• 100% = 모든 코어 완전 사용\n\n차트: 조회 범위 동안 avg 추이"} /></span>
		<strong class="value">{formatPercent(metrics?.cpu_avg, 1)}</strong>
		<span class="sub">최대 {formatPercent(metrics?.cpu_max, 0)}</span>
		<div class="spark"><MetricSparkline values={cpuTrend} color="#30d5c8" label="CPU 평균 추이" stretch /></div>
	</div>

	<div class="kpi" data-level={memLevel}>
		<span class="label">메모리 <MetricHelp text={"모든 서버 메모리 사용률의 평균과 최대치.\n\n개별 서버 기준\n• 사용 중 메모리 ÷ 전체 RAM × 100\n• buff/cache 포함\n\n차트: 조회 범위 동안 avg 추이"} /></span>
		<strong class="value">{formatPercent(metrics?.memory_avg, 1)}</strong>
		<span class="sub">최대 {formatPercent(metrics?.memory_max, 0)}</span>
		<div class="spark"><MetricSparkline values={memTrend} color="#60a5fa" label="메모리 평균 추이" stretch /></div>
	</div>

	<div class="kpi" data-level={diskLevel}>
		<span class="label">디스크 <MetricHelp text={"모든 서버 디스크 사용률의 평균과 최대치.\n\n개별 서버 기준\n• 루트 파티션(/) 사용량 ÷ 전체 용량 × 100\n• 다른 마운트는 제외\n\n차트: 조회 범위 동안 avg 추이"} /></span>
		<strong class="value">{formatPercent(metrics?.disk_avg, 1)}</strong>
		<span class="sub">최대 {formatPercent(metrics?.disk_max, 0)}</span>
		<div class="spark"><MetricSparkline values={diskTrend} color="#a78bfa" label="디스크 평균 추이" stretch /></div>
	</div>

	{#if gpuActive}
		<div class="kpi" data-level={gpuLevel}>
			<span class="label">GPU <MetricHelp text={"위 값은 GPU 코어 사용률(usage). hint 는 VRAM 점유율 — 사용률 0% 라도 VRAM 이 차있으면 모델이 로드된 idle 상태입니다.\n\n개별 서버 기준\n• 사용률: 장착된 모든 GPU 평균 (NVIDIA: nvidia-smi util / AMD: rocm-smi util)\n• VRAM: memoryUsed 합 ÷ memoryTotal 합\n\nGPU 0개 서버는 집계에서 제외"} /></span>
			<strong class="value">{formatPercent(metrics?.gpu_avg, 1)}</strong>
			<span class="sub">
				{#if (metrics?.gpu_memory_total_bytes ?? 0) > 0}
					VRAM {formatPercent(metrics?.gpu_memory_percent, 1)} · {formatBytes(metrics?.gpu_memory_used_bytes ?? 0)} / {formatBytes(metrics?.gpu_memory_total_bytes ?? 0)}
				{:else}
					최대 {formatPercent(metrics?.gpu_max, 0)}
				{/if}
			</span>
			<div class="spark"><MetricSparkline values={gpuTrend} color="#f472b6" label="GPU 평균 추이" stretch /></div>
		</div>
	{/if}

	<div class="kpi">
		<span class="label">네트워크 <MetricHelp text="모든 서버의 수신(RX)과 송신(TX)을 합친 총 트래픽 속도입니다." /></span>
		<strong class="value net">{formatRate((metrics?.network_rx_rate ?? 0) + (metrics?.network_tx_rate ?? 0))}</strong>
		<span class="sub">↓ {formatRate(metrics?.network_rx_rate)} · ↑ {formatRate(metrics?.network_tx_rate)}</span>
		<div class="spark"><MetricSparkline values={netTrend} color="#fbbf24" label="네트워크 추이" stretch /></div>
	</div>

	<!-- 자원 임계 초과(●) / 급증(▲) 서버 이벤트 — 진행 중 이벤트 가로 행 리스트.
	     헤더에 최근 1시간 발생 건수를 요약한다. -->
	<div class="kpi kpi-events" class:has-critical={criticalCount > 0}>
		<span class="label">
			<span class="dot" class:danger={criticalCount > 0} class:offline={$fleetEvents.length === 0}></span>
			서버 이벤트
			<span class="event-summary">최근 1시간 · 위험 {windowCritical} · 주의 {windowWarning}</span>
			<MetricHelp text="자원 임계치를 넘었거나(●) 사용량이 급증한(▲) 서버를 보여줍니다. 리스트는 현재 진행 중인 이벤트와 원인 컨테이너(📦)를, 헤더는 최근 1시간 발생 건수를 요약합니다. 백엔드가 1분 단위로 판정합니다." placement="bottom-end" />
			<button class="event-log-btn" type="button" onclick={() => (historyOpen = true)}>기록</button>
		</span>
		<div class="event-list" role="list" aria-label="진행 중 서버 자원 이벤트">
			{#each slotEvents as ev, slot (slot)}
				{#if ev}
					<div class="event-row" role="listitem" class:critical={ev.severity === 'critical'} class:warning={ev.severity === 'warning'}>
						<span class="er-server">
							<span class="er-kind" title={ev.kind === 'spike' ? '자원 급증' : '임계 초과'}>{ev.kind === 'spike' ? '▲' : '●'}</span>
							<span class="er-name" title={ev.hostname}>{ev.hostname}</span>
						</span>
						<span class="er-gauge" title="{metricLabel(ev.metric)} {Math.round(ev.value)}%">
							<span class="er-mname">{metricLabel(ev.metric)}</span>
							<span class="er-bar">
								<span class="er-bar-fill" style="width:{Math.min(100, Math.max(0, ev.value))}%"></span>
							</span>
							<span class="er-mval">{#if ev.kind === 'spike'}+{Math.round(ev.delta ?? 0)}%p{:else}{Math.round(ev.value)}%{/if}</span>
						</span>
						<span class="er-cause" class:unknown={!ev.container} title={ev.container ? `원인 컨테이너 ${ev.container.name}` : '원인 컨테이너 미확인'}>
							<span class="er-cause-icon" aria-hidden="true">📦</span>
							{#if ev.container}
								<span class="er-cname">{ev.container.name}</span>
							{:else}
								<span class="er-cname er-none">원인 미확인</span>
							{/if}
						</span>
						<span class="er-time" title={ev.kind === 'spike' ? '급등 시각' : '임계 초과 시작'}>{eventAgo(ev.occurredAt)}</span>
						<button
							class="er-ack"
							type="button"
							title="확인 처리 — 이 이벤트를 종료합니다"
							aria-label="{ev.hostname} 이벤트 확인 처리"
							onclick={() => acknowledgeResourceEvent(ev.id)}
						>✓</button>
					</div>
				{:else}
					<div class="event-row event-row-empty" role="listitem" aria-label="이벤트 없음">
						<span class="empty-mark" aria-hidden="true">✓</span>
						<span class="empty-text">이벤트 없음</span>
					</div>
				{/if}
			{/each}
		</div>
	</div>

</section>

<ResourceEventHistoryModal open={historyOpen} onClose={() => (historyOpen = false)} />

<style>
	.status-bar {
		--kpi-pad: clamp(9px, 0.6vw, 16px);
		--kpi-radius: clamp(6px, 0.4vw, 10px);
		--font-xs: clamp(10px, 0.62vw, 13px);
		--font-sm: clamp(11px, 0.72vw, 15px);
		--font-md: clamp(13px, 0.85vw, 17px);
		--font-lg: clamp(18px, 1.25vw, 26px);
		--font-xl: clamp(22px, 1.5vw, 32px);

		display: grid;
		/* KPI 타일을 FHD(1920) 한 줄에 담는 minmax 하한. 이벤트 카드는
		   .kpi-events 에서 span 으로 더 넓게 차지한다. */
		grid-template-columns: repeat(auto-fit, minmax(clamp(140px, 9.2vw, 210px), 1fr));
		gap: clamp(6px, 0.5vw, 12px);
		flex-shrink: 0;
	}
	.kpi {
		min-width: 0;
		min-height: clamp(100px, 8.5vh, 150px);
		padding: var(--kpi-pad);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--kpi-radius);
		display: flex;
		flex-direction: column;
		gap: 3px;
		position: relative;
	}
	.kpi::after {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
		pointer-events: none;
	}
	.kpi::before {
		content: '';
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 3px;
		background: transparent;
	}
	.kpi[data-level='warn']::before {
		background: #fbbf24;
	}
	.kpi[data-level='danger']::before {
		background: #f87171;
	}
	.kpi[data-level='warn'] .value {
		color: #fbbf24;
	}
	.kpi[data-level='danger'] .value {
		color: #f87171;
	}
	.label {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 800;
		letter-spacing: 0.3px;
		white-space: nowrap;
	}
	.value {
		color: var(--text-primary);
		font-size: var(--font-lg);
		font-weight: 700;
		line-height: 1.1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		font-variant-numeric: tabular-nums;
	}
	.value.net {
		font-size: var(--font-md);
	}
	.sub {
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.spark {
		margin-top: auto;
		height: clamp(24px, 2.4vh, 42px);
		overflow: hidden;
	}
	.spark :global(svg) {
		width: 100%;
		height: 100%;
		max-width: none;
	}
	/* 전체 서버 카드 — 좌 상태 / 우 서버 구성 2열을 담아 span 2 로 넓힌다. */
	.kpi-state {
		grid-column: span 2;
	}
	.kpi-state.danger {
		border-color: rgba(248, 113, 113, 0.38);
		background: linear-gradient(180deg, rgba(248, 113, 113, 0.08), var(--bg-card) 60%);
	}
	.state-body {
		flex: 1 1 0;
		min-height: 0;
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
		align-items: center;
	}
	.state-main {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 7px;
	}
	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #34d399;
		box-shadow: 0 0 8px rgba(52, 211, 153, 0.55);
	}
	.dot.danger {
		background: #f87171;
		box-shadow: 0 0 8px rgba(248, 113, 113, 0.55);
	}
	.dot.offline {
		background: #64748b;
		box-shadow: none;
	}
	.state-row {
		display: flex;
		align-items: baseline;
		gap: 6px;
	}
	.state-row strong {
		color: var(--text-primary);
		font-size: var(--font-xl);
		font-weight: 800;
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}
	.state-row .slash {
		color: var(--text-secondary);
		font-size: var(--font-sm);
		font-weight: 700;
	}
	.state-chips {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 3px;
	}
	.chip {
		display: inline-flex;
		justify-content: center;
		align-items: center;
		gap: 3px;
		height: clamp(18px, 1.4vw, 22px);
		padding: 0 5px;
		border-radius: var(--radius-sm);
		font-size: clamp(9px, 0.6vw, 10.5px);
		font-weight: 800;
		letter-spacing: 0.2px;
		white-space: nowrap;
	}
	.chip b {
		font-variant-numeric: tabular-nums;
	}
	.chip.critical {
		color: #fecaca;
		background: rgba(239, 68, 68, 0.18);
		border: 1px solid rgba(239, 68, 68, 0.32);
	}
	.chip.warning {
		color: #fcd34d;
		background: rgba(251, 191, 36, 0.16);
		border: 1px solid rgba(251, 191, 36, 0.3);
	}
	.chip.stale {
		color: #c4b5fd;
		background: rgba(167, 139, 250, 0.14);
		border: 1px solid rgba(167, 139, 250, 0.28);
	}
	.chip.offline {
		color: #cbd5e1;
		background: rgba(100, 116, 139, 0.16);
		border: 1px solid rgba(100, 116, 139, 0.3);
	}
	.chip.zero {
		color: var(--text-muted);
		background: rgba(30, 41, 59, 0.4);
		border-color: rgba(71, 85, 105, 0.3);
	}

	/* ── 서버 이벤트 카드 (span 3) + 서버 구성 카드 (span 1) ────── */
	.kpi-events {
		grid-column: span 3;
		gap: 6px;
	}
	.kpi-events.has-critical {
		border-color: rgba(248, 113, 113, 0.4);
	}
	.event-summary {
		display: inline-flex;
		align-items: center;
		padding: 0 6px;
		height: 15px;
		border-radius: var(--radius-full);
		background: rgba(148, 163, 184, 0.16);
		color: var(--text-secondary);
		font-size: 9.5px;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		letter-spacing: 0;
	}
	.event-log-btn {
		margin-left: 2px;
		padding: 1px 9px;
		border: 1px solid rgba(148, 163, 184, 0.3);
		border-radius: var(--radius-full);
		background: rgba(148, 163, 184, 0.1);
		color: var(--text-secondary);
		font-size: 9.5px;
		font-weight: 800;
		letter-spacing: 0.3px;
		cursor: pointer;
		transition: color 0.12s ease, border-color 0.12s ease;
	}
	.event-log-btn:hover {
		color: var(--text-primary);
		border-color: var(--accent);
	}
	/* 리스트를 카드 흐름에서 분리(absolute) — 카드 높이는 label 만으로
	   결정되어 다른 KPI 타일과 동일한 세로 크기를 유지한다.
	   top offset 을 키워 헤더(label)와 리스트 사이에 숨 쉴 공간을 둔다. */
	.event-list {
		position: absolute;
		left: var(--kpi-pad);
		right: var(--kpi-pad);
		bottom: var(--kpi-pad);
		top: calc(var(--kpi-pad) + 30px);
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
		overflow-y: auto;
	}

	/* ── 서버 구성 카드 ── */
	.ss-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		padding-left: 12px;
		border-left: 1px solid rgba(148, 163, 184, 0.14);
	}
	.ss-item {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 3px;
		padding: 9px 6px;
		border-radius: 7px;
		background: rgba(148, 163, 184, 0.06);
		border: 1px solid rgba(148, 163, 184, 0.1);
	}
	.ss-item.gpu {
		background: rgba(244, 114, 182, 0.08);
		border-color: rgba(244, 114, 182, 0.2);
	}
	.ss-num {
		color: var(--text-primary);
		font-size: clamp(17px, 1.2vw, 24px);
		font-weight: 800;
		line-height: 1;
		font-variant-numeric: tabular-nums;
	}
	.ss-item.gpu .ss-num {
		color: #f472b6;
	}
	.ss-label {
		color: var(--text-secondary);
		font-size: clamp(9px, 0.6vw, 11px);
		font-weight: 700;
		white-space: nowrap;
	}
	.event-row {
		display: grid;
		grid-template-columns: minmax(110px, auto) minmax(0, 1fr) minmax(0, auto) auto auto;
		align-items: center;
		column-gap: clamp(10px, 1vw, 20px);
		flex: 1 1 0;
		min-height: 32px;
		padding: 0 11px 0 12px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.5);
		border: 1px solid rgba(148, 163, 184, 0.12);
		border-left: 3px solid #64748b;
		box-sizing: border-box;
	}
	.event-row.critical {
		border-left-color: #f87171;
		background: linear-gradient(
			90deg,
			rgba(248, 113, 113, 0.14),
			rgba(248, 113, 113, 0.04) 38%,
			rgba(13, 17, 23, 0.5)
		);
	}
	.event-row.warning {
		border-left-color: #fbbf24;
		background: linear-gradient(
			90deg,
			rgba(251, 191, 36, 0.13),
			rgba(251, 191, 36, 0.035) 38%,
			rgba(13, 17, 23, 0.5)
		);
	}

	/* 서버 */
	.er-server {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		min-width: 0;
	}
	.er-kind {
		flex: 0 0 auto;
		font-size: 9px;
		line-height: 1;
		color: #64748b;
	}
	.event-row.critical .er-kind {
		color: #f87171;
	}
	.event-row.warning .er-kind {
		color: #fbbf24;
	}
	.er-name {
		min-width: 0;
		color: var(--text-primary);
		font-weight: 700;
		font-size: clamp(11.5px, 0.78vw, 14px);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* 자원 사용률 게이지 */
	.er-gauge {
		display: flex;
		align-items: center;
		gap: 9px;
		min-width: 0;
	}
	.er-mname {
		flex: 0 0 auto;
		color: var(--text-secondary);
		font-size: clamp(10px, 0.66vw, 12px);
		font-weight: 700;
	}
	.er-bar {
		flex: 1 1 0;
		min-width: 30px;
		height: 7px;
		border-radius: var(--radius-full);
		background: rgba(148, 163, 184, 0.16);
		overflow: hidden;
	}
	.er-bar-fill {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: #64748b;
		transition: width 0.3s ease;
	}
	.event-row.critical .er-bar-fill {
		background: linear-gradient(90deg, #ef4444, #f87171);
	}
	.event-row.warning .er-bar-fill {
		background: linear-gradient(90deg, #f59e0b, #fbbf24);
	}
	.er-mval {
		flex: 0 0 auto;
		min-width: 40px;
		text-align: right;
		font-size: clamp(13px, 0.92vw, 16px);
		font-weight: 800;
		line-height: 1.05;
		font-variant-numeric: tabular-nums;
		color: var(--text-primary);
	}
	.event-row.critical .er-mval {
		color: #fca5a5;
	}
	.event-row.warning .er-mval {
		color: #fcd34d;
	}

	/* 원인 컨테이너 — 칩(pill) */
	.er-cause {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		min-width: 0;
		max-width: 100%;
		padding: 3px 9px;
		border-radius: var(--radius-full);
		background: rgba(148, 163, 184, 0.1);
		border: 1px solid rgba(148, 163, 184, 0.18);
	}
	.er-cause.unknown {
		background: rgba(148, 163, 184, 0.05);
		border-style: dashed;
	}
	.er-cause-icon {
		flex: 0 0 auto;
		font-size: 10px;
		line-height: 1;
	}
	.er-cname {
		min-width: 0;
		color: var(--text-secondary);
		font-size: clamp(10px, 0.68vw, 12px);
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.er-none {
		color: var(--text-muted);
		font-weight: 600;
	}
	.er-time {
		color: var(--text-muted);
		font-size: clamp(9.5px, 0.62vw, 11px);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.er-ack {
		width: 22px;
		height: 22px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		border: 1px solid rgba(148, 163, 184, 0.3);
		border-radius: 6px;
		background: rgba(148, 163, 184, 0.08);
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 800;
		cursor: pointer;
		transition: color 0.12s ease, border-color 0.12s ease, background 0.12s ease;
	}
	.er-ack:hover {
		color: #34d399;
		border-color: #34d399;
		background: rgba(52, 211, 153, 0.14);
	}
	/* 빈 슬롯 placeholder — 카드는 항상 2칸 고정. */
	.event-row-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		border: 1px dashed rgba(148, 163, 184, 0.2);
		background: rgba(148, 163, 184, 0.03);
	}
	.empty-mark {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		background: rgba(52, 211, 153, 0.12);
		color: #34d399;
		font-size: 10px;
		font-weight: 800;
	}
	.empty-text {
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 700;
	}
</style>
