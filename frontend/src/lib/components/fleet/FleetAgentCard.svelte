<script lang="ts">
	import type { FleetAgentRow } from '$lib/stores/fleet-store';
	import { formatPercent, formatRelative, healthLabel, humanizeReason, shortReason } from '$lib/utils/fleet-format';
	import MetricHelp from './MetricHelp.svelte';

	let {
		agent,
		selected = false,
		onSelect = () => {},
		onOpen2d,
		onOpen3d,
	}: {
		agent: FleetAgentRow;
		selected?: boolean;
		onSelect?: (agentId: string) => void;
		onOpen2d?: (agentId: string) => void;
		onOpen3d?: (agentId: string) => void;
	} = $props();

	let hasGpu = $derived((agent.latest?.gpu_count ?? 0) > 0);

	function severity(value: number, warn: number, crit: number): 'normal' | 'warn' | 'danger' {
		if (value >= crit) return 'danger';
		if (value >= warn) return 'warn';
		return 'normal';
	}

	let cpuLevel = $derived(severity(agent.latest?.cpu_usage ?? 0, 70, 90));
	let memLevel = $derived(severity(agent.latest?.memory_usage ?? 0, 75, 90));
	let diskLevel = $derived(severity(agent.latest?.disk_usage ?? 0, 80, 90));
	let gpuLevel = $derived(severity(agent.latest?.gpu_usage ?? 0, 80, 95));

	const CHART_COLORS = {
		cpu: '#30d5c8',
		memory: '#60a5fa',
		disk: '#a78bfa',
		gpu: '#f472b6',
	};

	let compactRows = $derived.by(() => {
		const rows: { key: string; label: string; value: number; level: 'normal' | 'warn' | 'danger'; color: string }[] = [
			{ key: 'cpu', label: 'CPU', value: agent.latest?.cpu_usage ?? 0, level: cpuLevel, color: CHART_COLORS.cpu },
			{ key: 'mem', label: 'MEM', value: agent.latest?.memory_usage ?? 0, level: memLevel, color: CHART_COLORS.memory },
			{ key: 'dsk', label: 'DSK', value: agent.latest?.disk_usage ?? 0, level: diskLevel, color: CHART_COLORS.disk },
		];
		if (hasGpu) {
			rows.push({ key: 'gpu', label: 'GPU', value: agent.latest?.gpu_usage ?? 0, level: gpuLevel, color: CHART_COLORS.gpu });
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
				<strong title={agent.agent.hostname}>{agent.agent.hostname}</strong>
				<span class="ip-inline">{agent.agent.ip_address}</span>
				<MetricHelp text={"각 막대 = 리소스 사용률(%)\n0% = 거의 안 씀, 100% = 완전 사용 중\n\n위험 임계\n• CPU 90% / 메모리 90%\n• 디스크 90% / GPU 95%"} />
				<span class="meta">
					<span class="health-tag {agent.health}">{healthLabel(agent.health)}</span>
				</span>
			</span>
		</div>
		<div class="head-actions">
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
		</div>
	</header>

	<div class="compact-body">
		<div class="bar-rows">
			{#each compactRows as row}
				<div class="bar-row" data-level={row.level} title={`${row.label} 사용률 ${formatPercent(row.value, 1)}`}>
					<span class="br-label">{row.label}</span>
					<div class="br-track">
						<span class="br-fill" style={`width: ${Math.min(100, row.value)}%; background: ${row.color};`}></span>
					</div>
					<span class="br-value">{formatPercent(row.value, 0)}</span>
				</div>
			{/each}
		</div>
		<div class="compact-foot">
			<span class="ct-chip running" title="실행 중 컨테이너"><b>{agent.containers.running ?? 0}</b> 실행</span>
			<span class="ct-chip other" title="정지·종료·일시정지 컨테이너"><b>{agent.containers.non_running ?? 0}</b> 기타</span>
			<span class="ct-chip problem" class:active={(agent.containers.problem ?? 0) > 0} title="재시작·비정상(dead) 상태의 컨테이너">
				<b>{agent.containers.problem ?? 0}</b> 이상
			</span>
			{#if agent.health_reasons.length > 0}
				<span class="reason-chip" title={agent.health_reasons.map(humanizeReason).join(' · ')}>
					{shortReason(agent.health_reasons[0])}
					{#if agent.health_reasons.length > 1}
						<b>+{agent.health_reasons.length - 1}</b>
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
		flex-wrap: wrap;
		gap: 8px;
		min-width: 0;
		width: 100%;
	}
	.title-line .meta {
		margin-left: auto;
	}
	.ip-inline {
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		letter-spacing: 0;
	}
	.title strong {
		color: var(--text-primary);
		font-size: var(--font-sm);
		font-weight: 800;
		letter-spacing: -0.1px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
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
		padding: 2px 6px;
		border-radius: var(--radius-sm);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.health-tag.healthy { color: #34d399; background: rgba(52, 211, 153, 0.14); }
	.health-tag.warning { color: #fbbf24; background: rgba(245, 158, 11, 0.18); }
	.health-tag.critical { color: #f87171; background: rgba(239, 68, 68, 0.18); }
	.health-tag.stale { color: #c4b5fd; background: rgba(167, 139, 250, 0.18); }
	.health-tag.offline { color: #cbd5e1; background: rgba(100, 116, 139, 0.18); }

	.head-actions {
		display: inline-flex;
		gap: 5px;
		flex-wrap: nowrap;
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
	.bar-rows {
		display: grid;
		gap: clamp(3px, 0.3vw, 7px);
		grid-auto-rows: minmax(0, 1fr);
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}
	.bar-row {
		display: grid;
		grid-template-columns: 34px 1fr 50px;
		align-items: center;
		gap: 8px;
		min-height: 0;
		line-height: 1;
	}
	.br-label {
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 800;
		letter-spacing: 0.3px;
		line-height: 1.1;
	}
	.br-track {
		height: 8px;
		border-radius: var(--radius-full);
		background: rgba(100, 116, 139, 0.2);
		overflow: hidden;
	}
	.br-fill {
		display: block;
		height: 100%;
		border-radius: inherit;
		transition: width 0.4s ease;
		box-shadow: 0 0 6px currentColor;
		opacity: 0.92;
	}
	.br-value {
		color: var(--text-primary);
		font-size: var(--font-xs);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		text-align: right;
		white-space: nowrap;
		line-height: 1.1;
	}
	.bar-row[data-level='warn'] .br-value {
		color: #fbbf24;
	}
	.bar-row[data-level='danger'] .br-value {
		color: #f87171;
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
