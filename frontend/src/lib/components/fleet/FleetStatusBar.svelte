<script lang="ts">
	import { onDestroy } from 'svelte';
	import MetricHelp from './MetricHelp.svelte';
	import MetricSparkline from './MetricSparkline.svelte';
	import { formatClock, formatCompact, formatPercent, formatRate, rangePollLabel, type RangeKey } from '$lib/utils/fleet-format';
	import type { FleetHistoryPoint, FleetSummary } from '$lib/stores/fleet-store';

	// fleet-store의 POLL_INTERVAL_MS와 동일해야 progress bar 정확도 유지.
	const POLL_INTERVAL_MS: Record<RangeKey, number> = {
		'1m': 10000,
		'5m': 30000,
		'1h': 60000,
		'24h': 600000,
		'7d': 3600000,
	};

	let {
		summary,
		history = [],
		lastUpdated = null,
		loading = false,
		connected = false,
		range = '1h',
	}: {
		summary: FleetSummary | null;
		history?: FleetHistoryPoint[];
		lastUpdated?: Date | null;
		loading?: boolean;
		connected?: boolean;
		range?: RangeKey;
	} = $props();

	let counts = $derived(summary?.agent_counts ?? {});
	let metrics = $derived(summary?.metric_summary ?? null);
	let ops = $derived(summary?.operations_summary ?? null);
	let containers = $derived(summary?.container_summary ?? {});

	let cpuTrend = $derived(history.map((point) => point.cpu_avg));
	let memTrend = $derived(history.map((point) => point.memory_avg));
	let diskTrend = $derived(history.map((point) => point.disk_avg));
	let gpuTrend = $derived(history.map((point) => point.gpu_avg ?? 0));
	let netTrend = $derived(history.map((point) => point.network_rx_rate + point.network_tx_rate));
	let gpuActive = $derived(gpuTrend.some((value) => value > 0) || (metrics?.gpu_max ?? 0) > 0);

	function count(key: string): number {
		return Number(counts[key] ?? 0);
	}

	function severity(value: number, warn: number, crit: number): 'normal' | 'warn' | 'danger' {
		if (value >= crit) return 'danger';
		if (value >= warn) return 'warn';
		return 'normal';
	}

	// 다음 poll까지 남은 시간을 1초마다 tick — progress bar·카운트다운용.
	let now = $state(Date.now());
	const tick = setInterval(() => (now = Date.now()), 1000);
	onDestroy(() => clearInterval(tick));

	let pollMs = $derived(POLL_INTERVAL_MS[range]);
	let elapsed = $derived(lastUpdated ? Math.max(0, now - lastUpdated.getTime()) : 0);
	let progress = $derived(Math.min(100, (elapsed / pollMs) * 100));
	let countdownSec = $derived(Math.max(0, Math.ceil((pollMs - elapsed) / 1000)));
	function formatCountdown(sec: number): string {
		if (sec < 60) return `${sec}초`;
		if (sec < 3600) return `${Math.floor(sec / 60)}분 ${sec % 60}초`;
		return `${Math.floor(sec / 3600)}시간 ${Math.floor((sec % 3600) / 60)}분`;
	}

	let cpuLevel = $derived(severity(metrics?.cpu_max ?? 0, 70, 90));
	let memLevel = $derived(severity(metrics?.memory_max ?? 0, 75, 90));
	let diskLevel = $derived(severity(metrics?.disk_max ?? 0, 80, 90));
	let gpuLevel = $derived(severity(metrics?.gpu_max ?? 0, 80, 95));

	let containerTotal = $derived(Number(containers.total ?? 0));
	let containerRunning = $derived(Number(containers.running ?? 0));
	let containerProblem = $derived(Number(containers.problem ?? 0));
	let runningPct = $derived(containerTotal > 0 ? (containerRunning / containerTotal) * 100 : 0);
	let problemPct = $derived(containerTotal > 0 ? (containerProblem / containerTotal) * 100 : 0);

	let freshnessSegs = $derived([
		{ key: 'fresh', label: '실시간', value: ops?.fresh_agents ?? 0, color: '#34d399' },
		{ key: 'warm', label: '관찰', value: ops?.warm_agents ?? 0, color: '#60a5fa' },
		{ key: 'stale', label: '지연', value: ops?.stale_agents ?? 0, color: '#fbbf24' },
		{ key: 'expired', label: '만료', value: ops?.expired_agents ?? 0, color: '#f87171' },
	]);
	let freshnessTotal = $derived(freshnessSegs.reduce((acc, seg) => acc + seg.value, 0));
</script>

<section class="status-bar" class:with-gpu={gpuActive} aria-label="전체 서버 요약">
	<div class="kpi kpi-state" class:danger={count('critical') > 0}>
		<span class="label">
			<span class="dot" class:danger={count('critical') > 0} class:offline={!connected}></span>
			전체 서버
			<MetricHelp text="대시보드에서 감시 중인 승인된 서버의 상태입니다. 아래 위험·주의·지연·중지(오프라인) 카운트로 어떤 상태에 몇 대가 있는지 확인합니다." />
		</span>
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

	<div class="kpi" data-level={cpuLevel}>
		<span class="label">CPU <MetricHelp text={"모든 서버 CPU 사용률의 평균과 최대치.\n\n개별 서버 기준\n• 논리 코어 사용량의 평균\n• 100% = 모든 코어 완전 사용\n\n차트: 조회 범위 동안 avg 추이"} /></span>
		<strong class="value">{formatPercent(metrics?.cpu_avg, 1)}</strong>
		<span class="sub">최대 {formatPercent(metrics?.cpu_max, 0)}</span>
		<div class="spark"><MetricSparkline values={cpuTrend} color="#30d5c8" label="CPU 평균 추이" /></div>
	</div>

	<div class="kpi" data-level={memLevel}>
		<span class="label">메모리 <MetricHelp text={"모든 서버 메모리 사용률의 평균과 최대치.\n\n개별 서버 기준\n• 사용 중 메모리 ÷ 전체 RAM × 100\n• buff/cache 포함\n\n차트: 조회 범위 동안 avg 추이"} /></span>
		<strong class="value">{formatPercent(metrics?.memory_avg, 1)}</strong>
		<span class="sub">최대 {formatPercent(metrics?.memory_max, 0)}</span>
		<div class="spark"><MetricSparkline values={memTrend} color="#60a5fa" label="메모리 평균 추이" /></div>
	</div>

	<div class="kpi" data-level={diskLevel}>
		<span class="label">디스크 <MetricHelp text={"모든 서버 디스크 사용률의 평균과 최대치.\n\n개별 서버 기준\n• 루트 파티션(/) 사용량 ÷ 전체 용량 × 100\n• 다른 마운트는 제외\n\n차트: 조회 범위 동안 avg 추이"} /></span>
		<strong class="value">{formatPercent(metrics?.disk_avg, 1)}</strong>
		<span class="sub">최대 {formatPercent(metrics?.disk_max, 0)}</span>
		<div class="spark"><MetricSparkline values={diskTrend} color="#a78bfa" label="디스크 평균 추이" /></div>
	</div>

	{#if gpuActive}
		<div class="kpi" data-level={gpuLevel}>
			<span class="label">GPU <MetricHelp text={"GPU를 보고하는 서버들의 평균·최대 사용률.\n\n개별 서버 기준\n• 장착된 모든 GPU의 평균\n• NVIDIA: nvidia-smi util\n• AMD: rocm-smi util\n\nGPU 0개 서버는 집계에서 제외"} /></span>
			<strong class="value">{formatPercent(metrics?.gpu_avg, 1)}</strong>
			<span class="sub">최대 {formatPercent(metrics?.gpu_max, 0)}</span>
			<div class="spark"><MetricSparkline values={gpuTrend} color="#f472b6" label="GPU 평균 추이" /></div>
		</div>
	{/if}

	<div class="kpi">
		<span class="label">네트워크 <MetricHelp text="모든 서버의 수신(RX)과 송신(TX)을 합친 총 트래픽 속도입니다." /></span>
		<strong class="value net">{formatRate((metrics?.network_rx_rate ?? 0) + (metrics?.network_tx_rate ?? 0))}</strong>
		<span class="sub">↓ {formatRate(metrics?.network_rx_rate)} · ↑ {formatRate(metrics?.network_tx_rate)}</span>
		<div class="spark"><MetricSparkline values={netTrend} color="#fbbf24" label="네트워크 추이" /></div>
	</div>

	<div class="kpi">
		<span class="label">컨테이너 <MetricHelp text="모든 서버에서 실행 중·기타·이상 상태 컨테이너 합계입니다. 초록 막대는 실행 비율, 빨간 막대는 문제 비율입니다." /></span>
		<strong class="value compact" title={`실행 중 ${Number(containerRunning).toLocaleString('en-US')} 컨테이너`}>{formatCompact(containerRunning)}</strong>
		<span class="sub">실행 · 기타 {formatCompact(containers.non_running)} · 이상 {formatCompact(containerProblem)}</span>
		<div class="container-bar" aria-hidden={containerTotal === 0}>
			<span class="seg running" style={`width: ${runningPct}%`}></span>
			<span class="seg problem" style={`width: ${problemPct}%`}></span>
		</div>
	</div>

	<div class="kpi">
		<span class="label">프로세스 · 로그인 <MetricHelp text="모든 서버의 프로세스 합계와 로그인 세션 합계입니다." /></span>
		<div class="pl-row">
			<div class="pl-col">
				<span class="pl-label">프로세스</span>
				<strong class="value compact" title={`총 ${Number(ops?.processes_total ?? 0).toLocaleString('en-US')} 프로세스`}>
					{formatCompact(ops?.processes_total)}
				</strong>
				<span class="pl-avg">평균 {formatCompact(Math.round(Number(ops?.processes_avg ?? 0)))}</span>
			</div>
			<div class="pl-divider"></div>
			<div class="pl-col">
				<span class="pl-label">로그인</span>
				<strong class="value compact">{formatCompact(ops?.logins_total)}</strong>
				<span class="pl-avg">평균 {Number(ops?.logins_avg ?? 0).toFixed(1)}</span>
			</div>
		</div>
	</div>

	<div class="kpi kpi-freshness">
		<span class="label">데이터 신선도 <MetricHelp text="서버별 최신 메트릭이 얼마나 최근 것인지 분포입니다. 오래된(지연/만료)이 많으면 에이전트 상태를 확인하세요." placement="bottom-end" /></span>
		<div class="fresh-bar" aria-hidden={freshnessTotal === 0}>
			{#each freshnessSegs as seg}
				<span class="fresh-seg" style={`flex: ${seg.value || 0.001}; background: ${seg.color};`} title={`${seg.label} ${seg.value}대`}></span>
			{/each}
		</div>
		<div class="fresh-legend">
			{#each freshnessSegs as seg}
				<span class="fresh-chip" style={`--c: ${seg.color};`}><b>{seg.value}</b> {seg.label}</span>
			{/each}
		</div>
	</div>

	<div class="kpi kpi-refresh" class:loading class:connected class:disconnected={!connected && !loading}>
		<span class="label">{loading ? '갱신 중' : connected ? '자동 갱신' : '연결 끊김'}</span>
		<strong class="clock">{lastUpdated ? formatClock(lastUpdated.toISOString()) : '-'}</strong>
		<span class="sub">{rangePollLabel(range)}</span>

		<!-- 나머지 공간을 채우는 progress — 다음 poll까지 경과/남은 시간 시각화 -->
		<div class="refresh-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progress)}>
			<div class="progress-track">
				<div class="progress-fill" style={`width: ${progress}%;`}></div>
			</div>
			<div class="progress-meta">
				<span>{connected && !loading ? `다음 갱신 ${formatCountdown(countdownSec)}` : loading ? '불러오는 중' : '대기 중'}</span>
				<span class="progress-pct">{Math.round(progress)}%</span>
			</div>
		</div>
	</div>
</section>

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
		/* KPI 9~10개를 FHD(1920) 한 줄에 담아야 해서 minmax 하한을 낮춤.
		   1920에서 9.2vw ≈ 176px → 10개 × 176 + gap < 1900. QHD/4K는 clamp 상한에
		   걸려 1fr 로 균등 분배됨. */
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
	.kpi-state.danger {
		border-color: rgba(248, 113, 113, 0.38);
		background: linear-gradient(180deg, rgba(248, 113, 113, 0.08), var(--bg-card) 60%);
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
		margin-top: auto;
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

	.container-bar {
		margin-top: auto;
		height: clamp(6px, 0.55vh, 10px);
		border-radius: var(--radius-full);
		background: rgba(100, 116, 139, 0.22);
		overflow: hidden;
		display: flex;
	}
	.seg.running {
		background: linear-gradient(90deg, #22c55e, #30d5c8);
	}
	.seg.problem {
		background: #f87171;
	}

	.pl-row {
		display: flex;
		align-items: stretch;
		gap: 8px;
		flex: 1;
		margin-top: 2px;
		min-width: 0;
	}
	/* container-type 을 pl-col 에 두면 자식 .value 가 cqw 로 col 폭 기반 폰트 사용. */
	.pl-col {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
		flex: 1;
		container-type: inline-size;
	}
	/* "..." 으로 잘리던 문제 → 숫자 자릿수가 늘어도 안 잘리게 cqw 로 폰트 자동 축소.
	   pl-col 폭이 좁으면 작아지고 넓으면 var(--font-lg) 한계까지 커진다.
	   25cqw 는 폭의 25% — 4~6자리 숫자가 항상 한 줄에 들어가는 안전 비율. */
	.pl-col .value {
		font-size: clamp(12px, 25cqw, 26px);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: clip;
	}
	.pl-label {
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.pl-avg {
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 600;
		margin-top: auto;
	}
	.pl-divider {
		width: 1px;
		background: rgba(100, 116, 139, 0.25);
	}

	.kpi-freshness {
		gap: 5px;
	}
	.fresh-bar {
		display: flex;
		height: clamp(8px, 0.7vh, 14px);
		border-radius: var(--radius-full);
		overflow: hidden;
		background: rgba(100, 116, 139, 0.22);
	}
	.fresh-seg {
		display: block;
		height: 100%;
	}
	.fresh-legend {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 3px;
		margin-top: auto;
	}
	.fresh-chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 6px;
		border-radius: var(--radius-sm);
		background: rgba(13, 17, 23, 0.5);
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 700;
	}
	.fresh-chip::before {
		content: '';
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--c);
	}
	.fresh-chip b {
		color: var(--text-primary);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
	}

	.kpi-refresh {
		border-color: rgba(52, 211, 153, 0.22);
		background: rgba(52, 211, 153, 0.06);
	}
	.kpi-refresh .label {
		color: #34d399;
	}
	.kpi-refresh.loading {
		border-color: rgba(251, 191, 36, 0.3);
		background: rgba(251, 191, 36, 0.06);
	}
	.kpi-refresh.loading .label {
		color: #fbbf24;
	}
	.kpi-refresh.disconnected {
		border-color: rgba(100, 116, 139, 0.35);
		background: rgba(100, 116, 139, 0.08);
	}
	.kpi-refresh.disconnected .label {
		color: #cbd5e1;
	}
	.clock {
		color: var(--text-primary);
		font-size: var(--font-md);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	/* 자동 갱신 타일이 다른 KPI (sparkline 있는) 와 높이·비율 맞추도록, 남는 공간을
	   progress bar + countdown 으로 채움. flex 레이아웃이라 strong·sub 아래 자동 확장. */
	.refresh-progress {
		margin-top: auto;
		padding-top: clamp(4px, 0.35vw, 8px);
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.progress-track {
		position: relative;
		width: 100%;
		height: clamp(5px, 0.45vh, 9px);
		background: rgba(148, 163, 184, 0.14);
		border-radius: var(--kpi-radius);
		overflow: hidden;
	}
	.progress-fill {
		height: 100%;
		background: linear-gradient(90deg, #34d399, #30d5c8);
		border-radius: inherit;
		transition: width 0.9s linear;
	}
	.kpi-refresh.loading .progress-fill {
		background: linear-gradient(90deg, #fbbf24, #f59e0b);
	}
	.kpi-refresh.disconnected .progress-fill {
		background: rgba(100, 116, 139, 0.5);
	}
	.progress-meta {
		display: flex;
		justify-content: space-between;
		font-size: calc(var(--font-xs) - 1px);
		color: var(--text-muted);
		font-weight: 600;
	}
	.progress-pct {
		font-variant-numeric: tabular-nums;
		color: var(--text-secondary);
	}
</style>
