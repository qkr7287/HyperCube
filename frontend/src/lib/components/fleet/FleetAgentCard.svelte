<script lang="ts">
	import type { FleetAgentRow } from '$lib/stores/fleet-store';
	import { formatBytes, formatPercent, formatRate, formatRelative, healthLabel, humanizeReason, shortReason } from '$lib/utils/fleet-format';
	import MetricHelp from './MetricHelp.svelte';
	import FleetCardChart from './FleetCardChart.svelte';

	let {
		agent,
		variant = 'medium',
		selected = false,
		range = '1h',
		onSelect = () => {},
		onOpen3d,
	}: {
		agent: FleetAgentRow;
		variant?: 'full' | 'medium' | 'compact';
		selected?: boolean;
		range?: '1m' | '5m' | '1h' | '24h' | '7d';
		onSelect?: (agentId: string) => void;
		onOpen3d?: (agentId: string) => void;
	} = $props();

	let cpuSeries = $derived(agent.sparkline.cpu);
	let memorySeries = $derived(agent.sparkline.memory);
	let diskSeries = $derived(agent.sparkline.disk);
	let gpuSeries = $derived(agent.sparkline.gpu);
	let hasGpu = $derived((agent.latest?.gpu_count ?? 0) > 0);
	let memoryTotal = $derived(agent.latest?.memory_total ?? 0);
	let memoryUsed = $derived(agent.latest?.memory_used ?? 0);
	// null = Backend serializer가 필드 노출 안 함 (예: 구버전 배포). 0과 구별해서
	// "-" 로 보여줘야 "정말 0 개"인지 "아직 안 내려오는지"를 구분할 수 있다.
	let processesTotal = $derived(agent.latest?.processes_total ?? null);
	let processesRunning = $derived(agent.latest?.processes_running ?? null);
	let loginsTotal = $derived(agent.latest?.logins_total ?? null);
	let gpuTemp = $derived(agent.latest?.gpu_temperature);
	let gpuMemUsed = $derived(agent.latest?.gpu_memory_used ?? 0);
	let gpuMemTotal = $derived(agent.latest?.gpu_memory_total ?? 0);
	let cpuCores = $derived(agent.latest?.cpu_threads ?? agent.latest?.cpu_cores ?? 0);
	let diskUsed = $derived(agent.latest?.disk_used ?? 0);
	let diskTotal = $derived(agent.latest?.disk_total ?? 0);
	let loadAvg1m = $derived(agent.latest?.cpu_load_avg_1m);
	let networkTotal = $derived((agent.latest?.network_rx_rate ?? 0) + (agent.latest?.network_tx_rate ?? 0));

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
		rx: '#22d3ee',
		tx: '#fbbf24',
	};

	// Docker 실제 상태: running / paused / restarting / exited / dead
	// "stopped"는 Docker native 상태가 아니고 "exited"의 동의어로 쓰이므로 둘을 "종료"로 통합.
	// "dead"는 복구 불가 상태이므로 "비정상"으로 구분 표기.
	let exitedCombined = $derived(Number(agent.containers.exited ?? 0) + Number(agent.containers.stopped ?? 0));
	let ctSegments = $derived([
		{ key: 'running', label: '실행', color: '#22c55e', value: Number(agent.containers.running ?? 0) },
		{ key: 'paused', label: '일시정지', color: '#60a5fa', value: Number(agent.containers.paused ?? 0) },
		{ key: 'restarting', label: '재시작', color: '#fbbf24', value: Number(agent.containers.restarting ?? 0) },
		{ key: 'exited', label: '종료', color: '#a78bfa', value: exitedCombined },
		{ key: 'dead', label: '비정상', color: '#ef4444', value: Number(agent.containers.dead ?? 0) },
	].filter((seg) => seg.value > 0));
	let ctTotal = $derived(Number(agent.containers.total ?? 0));
	let procRatio = $derived(
		processesTotal && processesRunning != null && processesTotal > 0
			? Math.round((processesRunning / processesTotal) * 100)
			: null,
	);

	function peak(values: number[]): number {
		if (!values?.length) return 0;
		let max = -Infinity;
		for (const v of values) if (Number.isFinite(v) && v > max) max = v;
		return max === -Infinity ? 0 : max;
	}

	let rangeLabelMap: Record<string, string> = {
		'1m': '1분',
		'5m': '5분',
		'1h': '1시간',
		'24h': '24시간',
		'7d': '7일',
	};

	function cpuSub(): string {
		const parts: string[] = [];
		if (cpuCores > 0) {
			const usedCores = (peak(cpuSeries) / 100) * cpuCores;
			parts.push(`${usedCores.toFixed(1)} / ${cpuCores}코어`);
		}
		if (loadAvg1m != null && Number.isFinite(loadAvg1m)) {
			parts.push(`load ${loadAvg1m.toFixed(2)}`);
		}
		return parts.join(' · ');
	}

	function diskSub(): string {
		if (diskTotal > 0) {
			return `${formatBytes(diskUsed)} / ${formatBytes(diskTotal)}`;
		}
		return '루트(/) 파티션';
	}

	function gpuSub(): string {
		if (!hasGpu) return '';
		const parts: string[] = [];
		parts.push(`${agent.latest?.gpu_count ?? 0}장`);
		if (gpuMemTotal > 0) {
			parts.push(`${formatBytes(gpuMemUsed)} / ${formatBytes(gpuMemTotal)}`);
		}
		if (gpuTemp != null) parts.push(`${gpuTemp}°C`);
		return parts.join(' · ');
	}

	let peaks = $derived([
		{
			key: 'cpu',
			label: 'CPU',
			color: CHART_COLORS.cpu,
			value: peak(cpuSeries),
			sub: cpuSub(),
			level: severity(peak(cpuSeries), 70, 90),
		},
		{
			key: 'mem',
			label: '메모리',
			color: CHART_COLORS.memory,
			value: peak(memorySeries),
			sub: memoryTotal > 0 ? `${formatBytes((peak(memorySeries) / 100) * memoryTotal)} / ${formatBytes(memoryTotal)}` : '',
			level: severity(peak(memorySeries), 75, 90),
		},
		{
			key: 'dsk',
			label: '디스크',
			color: CHART_COLORS.disk,
			value: peak(diskSeries),
			sub: diskSub(),
			level: severity(peak(diskSeries), 80, 90),
		},
		{
			key: 'gpu',
			label: 'GPU',
			color: CHART_COLORS.gpu,
			value: peak(gpuSeries),
			sub: gpuSub(),
			level: severity(peak(gpuSeries), 80, 95),
		},
	].filter((p) => p.key !== 'gpu' || hasGpu));

	let containerDetails = $derived.by(() => {
		const total = Number(agent.containers.total ?? 0);
		return [
			{ key: 'running', label: '실행', value: Number(agent.containers.running ?? 0), color: '#22c55e' },
			{ key: 'paused', label: '일시정지', value: Number(agent.containers.paused ?? 0), color: '#60a5fa' },
			{ key: 'restarting', label: '재시작', value: Number(agent.containers.restarting ?? 0), color: '#fbbf24' },
			{ key: 'exited', label: '종료', value: exitedCombined, color: '#a78bfa' },
			{ key: 'dead', label: '비정상', value: Number(agent.containers.dead ?? 0), color: '#ef4444' },
		].map((item) => ({
			...item,
			ratio: total > 0 ? (item.value / total) * 100 : 0,
		}));
	});

	// compact variant: metric rows (CPU/MEM/DSK/GPU only - all percent-based)
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
	class="card {agent.health} variant-{variant}"
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
					<span
						class="live-dot"
						aria-hidden="true"
						title="Agent 실시간 연결 중"
					></span>
				{/if}
				<strong title={agent.agent.hostname}>{agent.agent.hostname}</strong>
				<span class="ip-inline">{agent.agent.ip_address}</span>
				{#if variant === 'compact'}
					<MetricHelp text={"각 막대 = 리소스 사용률(%)\n0% = 거의 안 씀, 100% = 완전 사용 중\n\n위험 임계\n• CPU 90% / 메모리 90%\n• 디스크 90% / GPU 95%"} />
				{/if}
				<!-- 메타(상태 · 메트릭 시각 · reason chip) 를 hostname/IP 우측으로 붙임.
				     좁아지면 flex-wrap 으로 다음 줄에 떨어지지만 공간 있는 동안은 한 줄. -->
				<span class="meta">
					<span class="health-tag {agent.health}">{healthLabel(agent.health)}</span>
					{#if variant !== 'compact'}
						<span
							class="age"
							title={"마지막 메트릭이 수신된 시점입니다.\n\n왜 서버마다 다를까?\n• Agent의 전송 주기 (5~15초)\n• 네트워크 지연\n• 조회 시점과의 어긋남\n\n15초 이내는 정상(실시간), 60초 초과는 지연으로 표시됩니다."}
						>메트릭 {formatRelative(agent.latest?.timestamp)}</span>
					{/if}
					{#if agent.health_reasons.length > 0}
						<span
							class="reason-chip"
							title={agent.health_reasons.map(humanizeReason).join(' · ')}
						>
							{shortReason(agent.health_reasons[0])}
							{#if agent.health_reasons.length > 1}
								<b>+{agent.health_reasons.length - 1}</b>
							{/if}
						</span>
					{/if}
				</span>
			</span>
		</div>
		<div class="head-actions">
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
					<span class="monitor-label">상세</span>
				</button>
			{/if}
		</div>
	</header>


	{#if variant === 'compact'}
		<div class="compact-body">
			<div class="bar-rows">
				{#each compactRows as row}
					<div
						class="bar-row"
						data-level={row.level}
						title={`${row.label} 사용률 ${formatPercent(row.value, 1)}`}
					>
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
				<span class="age-small" title="최신 메트릭 수신 시점">{formatRelative(agent.latest?.timestamp)}</span>
			</div>
		</div>
	{:else}
		<div class="metrics" class:grid4={variant === 'full'} class:grid2x2={variant === 'medium'}>
			<div class="metric" data-level={cpuLevel}>
				<div class="m-head">
					<span class="m-label">
						CPU
						<MetricHelp text={"CPU 사용률(%)\n\n계산 기준\n• 모든 논리 코어 사용량의 평균\n• 예: 8코어 중 2코어만 100% → 전체 25%\n• 100%에 가까울수록 과부하\n\n축 설명\n• x축 = 시간, y축 = 0~100%"} />
					</span>
					<strong class="m-value">{formatPercent(agent.latest?.cpu_usage)}</strong>
				</div>
				<div class="chart">
					<FleetCardChart
						series={{ values: cpuSeries, color: CHART_COLORS.cpu, label: 'CPU' }}
						{range}
						showAxes={variant !== 'medium' ? true : true}
					/>
				</div>
			</div>

			<div class="metric" data-level={memLevel}>
				<div class="m-head">
					<span class="m-label">
						메모리
						<MetricHelp text={"메모리 사용률(%)\n\n계산 기준\n• 사용 중 메모리 ÷ 전체 RAM × 100\n• 리눅스 buff/cache 포함 (실제 free memory 기준 아님)\n• 90%↑ = 위험 (OOM 가능성)\n\n카드에 GB/GB 절대값도 함께 표시"} />
					</span>
					<strong class="m-value">{formatPercent(agent.latest?.memory_usage)}</strong>
				</div>
				{#if variant === 'full' && memoryTotal > 0}
					<span class="m-sub">{formatBytes(memoryUsed)} / {formatBytes(memoryTotal)}</span>
				{/if}
				<div class="chart">
					<FleetCardChart
						series={{ values: memorySeries, color: CHART_COLORS.memory, label: '메모리' }}
						{range}
					/>
				</div>
			</div>

			<div class="metric" data-level={diskLevel}>
				<div class="m-head">
					<span class="m-label">
						디스크
						<MetricHelp text={"디스크 사용률(%)\n\n계산 기준\n• 루트 파티션(/) 사용 용량 ÷ 전체 용량 × 100\n• 다른 마운트 지점은 제외\n\n임계치\n• 80%↑ 주의\n• 90%↑ 위험 (공간 부족 직전)"} />
					</span>
					<strong class="m-value">{formatPercent(agent.latest?.disk_usage)}</strong>
				</div>
				<div class="chart">
					<FleetCardChart
						series={{ values: diskSeries, color: CHART_COLORS.disk, label: '디스크' }}
						{range}
					/>
				</div>
			</div>

			{#if hasGpu}
				<div class="metric" data-level={gpuLevel}>
					<div class="m-head">
						<span class="m-label">
							GPU
							<MetricHelp text={"GPU 사용률(%)\n\n계산 기준\n• 장착된 모든 GPU의 평균\n• NVIDIA: nvidia-smi utilization.gpu\n• AMD: rocm-smi util\n• 2장 이상이면 평균값 사용\n\n임계치\n• 80%↑ 주의, 95%↑ 위험\n\nGPU 개수·온도는 카드에 별도 표기"} />
						</span>
						<strong class="m-value">{formatPercent(agent.latest?.gpu_usage)}</strong>
					</div>
					{#if variant === 'full'}
						<span class="m-sub">
							{agent.latest?.gpu_count ?? 0}개
							{#if gpuTemp != null} · {gpuTemp}°C{/if}
						</span>
					{/if}
					<div class="chart">
						<FleetCardChart
							series={{ values: gpuSeries, color: CHART_COLORS.gpu, label: 'GPU' }}
							{range}
						/>
					</div>
				</div>
			{/if}
		</div>

		{#if variant === 'full'}
			<section class="extra">
				<div class="extra-col">
					<div class="row-label">
						<span>컨테이너 분포</span>
						<MetricHelp
							placement="top-start"
							text={"컨테이너 상태 분포 (Docker 기준)\n\n• 실행 — 정상 동작 중\n• 일시정지 — docker pause 상태\n• 재시작 — 재시작 진행 중 (주의)\n• 종료 — exited / stopped 통합 (정상 종료)\n• 비정상 — dead, 복구 불가 (즉시 확인)\n\n재시작·비정상 상태는 즉시 확인이 필요합니다."}
						/>
						<span class="row-count">총 {ctTotal}개</span>
					</div>
					{#if ctTotal > 0}
						<div class="ct-bar" aria-hidden="true">
							{#each ctSegments as seg}
								<span class="seg" style={`flex: ${seg.value}; background: ${seg.color};`} title={`${seg.label} ${seg.value}개`}></span>
							{/each}
						</div>
						<div class="ct-list">
							{#each containerDetails as item}
								<div class="ct-row" class:zero={item.value === 0}>
									<span class="ct-row-dot" style={`background: ${item.color};`}></span>
									<span class="ct-row-label">{item.label}</span>
									<div class="ct-row-track">
										<span class="ct-row-fill" style={`width: ${item.ratio}%; background: ${item.color};`}></span>
									</div>
									<span class="ct-row-count"><strong>{item.value}</strong><small>{Math.round(item.ratio)}%</small></span>
								</div>
							{/each}
						</div>
					{:else}
						<div class="ct-empty">컨테이너 없음</div>
					{/if}
				</div>

				<div class="extra-col">
					<div class="row-label">
						<span>프로세스 · 네트워크 · 에이전트</span>
						<MetricHelp
							placement="top-start"
							text={"서버 운영 상태 요약\n\n• 프로세스 — OS 전체 프로세스 수 (실행/총 개수)\n• 로그인 — 현재 접속 중인 활성 세션 수\n• 네트워크 — RX(수신) + TX(송신) 초당 처리량\n• 에이전트 — HyperCube Agent 연결 상태\n\n마지막 응답은 Agent→Backend WS 핑 시각입니다."}
						/>
					</div>
					<div class="spec-grid">
						<div class="spec">
							<span class="spec-label">프로세스</span>
							<strong>{processesTotal ?? '-'}</strong>
							<span class="spec-sub">{processesRunning != null ? `실행 ${processesRunning}${procRatio != null ? ` · ${procRatio}%` : ''}` : '데이터 없음'}</span>
						</div>
						<div class="spec">
							<span class="spec-label">로그인</span>
							<strong>{loginsTotal ?? '-'}</strong>
							<span class="spec-sub">{loginsTotal != null ? '활성 세션' : '데이터 없음'}</span>
						</div>
						<div class="spec">
							<span class="spec-label">네트워크</span>
							<strong class="small">{formatRate(networkTotal)}</strong>
							<span class="spec-sub">↓ {formatRate(agent.latest?.network_rx_rate)} · ↑ {formatRate(agent.latest?.network_tx_rate)}</span>
						</div>
						<div class="spec">
							<span class="spec-label">에이전트</span>
							<strong class="small agent-status" class:off={!agent.agent.is_active}>
								{#if agent.agent.is_active}
									<span class="live-dot" aria-hidden="true"></span>
								{/if}
								{agent.agent.is_active ? '실시간' : '오프라인'}
							</strong>
							<span class="spec-sub">마지막 응답 {formatRelative(agent.agent.last_seen_at)}</span>
						</div>
					</div>
				</div>

				<div class="extra-col">
					<div class="row-label">
						<span>최근 {rangeLabelMap[range] ?? ''} 피크값</span>
						<MetricHelp
							placement="top-end"
							text={"조회 범위 동안 기록된 최고 사용률과 실제 값.\n\n• CPU — 피크% + 사용 코어 수 (피크% × 논리 코어)\n  (Agent가 load avg 전송 시 1분 load도 표시)\n• 메모리 — 피크% + 추정 사용량 GB (피크% × 전체 RAM)\n• 디스크 — 피크% + 현재 사용 GB / 전체 GB (루트 파티션)\n• GPU — 피크% + 장치 수 · VRAM 사용량 · 온도\n\n현재값이 낮아도 피크가 높으면\n과거 과부하 흔적이 있다는 신호입니다."}
						/>
					</div>
					<div class="peak-grid">
						{#each peaks as p}
							<div class="peak-cell" data-level={p.level}>
								<div class="peak-head">
									<span class="peak-label" style={`color: ${p.color};`}>{p.label}</span>
									<strong class="peak-value">{formatPercent(p.value, 0)}</strong>
								</div>
								{#if p.sub}
									<span class="peak-sub">{p.sub}</span>
								{/if}
								<div class="peak-track">
									<span class="peak-fill" style={`width: ${Math.min(100, p.value)}%; background: ${p.color};`}></span>
								</div>
							</div>
						{/each}
					</div>
				</div>
			</section>
		{:else}
			<footer class="card-foot">
				<div class="ct-line">
					<span class="ct-label">컨테이너</span>
					<strong>{ctTotal}</strong>
					<span class="ct-chip running"><b>{agent.containers.running ?? 0}</b> 실행</span>
					<span class="ct-chip other"><b>{agent.containers.non_running ?? 0}</b> 기타</span>
					<span class="ct-chip problem" class:active={(agent.containers.problem ?? 0) > 0}>
						<b>{agent.containers.problem ?? 0}</b> 이상
					</span>
				</div>
			</footer>
		{/if}
	{/if}
</div>

<style>
	.card {
		--card-radius: clamp(8px, 0.5vw, 12px);
		--card-pad: clamp(10px, 0.75vw, 18px);
		--card-gap: clamp(6px, 0.45vw, 12px);
		--font-xs: clamp(10px, 0.62vw, 13px);
		--font-sm: clamp(11px, 0.72vw, 15px);
		--font-md: clamp(13px, 0.85vw, 17px);
		--font-lg: clamp(17px, 1.1vw, 24px);
		--font-xl: clamp(20px, 1.35vw, 30px);

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
	.card.variant-compact {
		--card-pad: clamp(8px, 0.55vw, 14px);
		--card-gap: clamp(4px, 0.35vw, 8px);
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
		align-items: flex-start;
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
	/* hostname / IP 뒤에 meta 를 밀어 우측 정렬. row 공간 좁으면 아래로 wrap. */
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
		font-size: var(--font-md);
		font-weight: 800;
		letter-spacing: -0.1px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
	.card.variant-compact .title strong {
		font-size: var(--font-sm);
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
	.ip,
	.age,
	.age-small {
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.head-actions {
		display: flex;
		align-items: flex-start;
		gap: 6px;
	}
	.head-stat {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
	}
	.head-stat .hs-label {
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 800;
	}
	.head-stat strong {
		color: var(--text-primary);
		font-size: var(--font-md);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
	}
	.monitor-btn {
		height: clamp(22px, 1.8vw, 32px);
		padding: 0 clamp(7px, 0.55vw, 14px);
		display: inline-flex;
		align-items: center;
		gap: 4px;
		border: 1px solid rgba(48, 213, 200, 0.6);
		border-radius: var(--radius-sm);
		/* 카드의 gradient(critical/warning) 배경 위에서도 일관되게 보이도록 합성 배경 사용. */
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
		gap: 4px;
		padding: 2px 7px;
		border-radius: var(--radius-sm);
		background: rgba(239, 68, 68, 0.14);
		color: #fca5a5;
		border: 1px solid rgba(239, 68, 68, 0.22);
		font-weight: 700;
		white-space: nowrap;
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

	/* Medium / Full metrics grid */
	.metrics {
		display: grid;
		gap: var(--card-gap);
		min-height: 0;
	}
	.metrics.grid4 {
		grid-template-columns: repeat(auto-fit, minmax(0, 1fr));
		grid-auto-flow: column;
		flex: 1;
	}
	.metrics.grid2x2 {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		grid-auto-rows: minmax(0, 1fr);
		flex: 1;
	}
	.metric {
		min-width: 0;
		min-height: 0;
		padding: clamp(6px, 0.5vw, 10px);
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		display: flex;
		flex-direction: column;
		gap: 3px;
		/* overflow visible — 툴팁 말풍선이 카드 영역 밖으로 나갈 때 잘리지 않도록 */
		overflow: visible;
		position: relative;
	}
	.metric .chart {
		overflow: hidden;
	}
	.metric[data-level='warn'] {
		border-color: rgba(251, 191, 36, 0.3);
	}
	.metric[data-level='warn'] .m-value {
		color: #fbbf24;
	}
	.metric[data-level='danger'] {
		border-color: rgba(248, 113, 113, 0.35);
	}
	.metric[data-level='danger'] .m-value {
		color: #f87171;
	}
	.m-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 6px;
		min-width: 0;
	}
	.m-label {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.m-value {
		color: var(--text-primary);
		/* 그래프 위 퍼센트 숫자 — 기존 --font-lg (18~26px) 에서 한 단계 축소.
		   카드 높이를 크게 잡지 않고도 차트에 가용 높이를 더 넘겨주기 위함. */
		font-size: clamp(15px, 1vw, 21px);
		font-weight: 700;
		line-height: 1.05;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.m-value.small {
		font-size: clamp(12px, 0.8vw, 16px);
	}
	.m-sub {
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 700;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.chart {
		flex: 1;
		min-height: 0;
		margin-top: auto;
	}
	.card.variant-medium .chart {
		/* 그래프가 위아래 여유 없이 잘리는 현상 해결 — min-height 상·하한 ↑. */
		min-height: clamp(52px, 6vh, 110px);
		flex: 1 1 auto;
	}
	.card.variant-medium .metric {
		min-height: clamp(90px, 10vh, 160px);
	}
	.card.variant-full .chart {
		min-height: clamp(64px, 8vh, 140px);
	}
	.chart :global(svg) {
		width: 100%;
		height: 100%;
		max-width: none;
	}

	/* Compact variant (horizontal progress bars) */
	.compact-body {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: clamp(5px, 0.4vw, 10px);
	}
	.bar-rows {
		display: grid;
		gap: clamp(4px, 0.35vw, 8px);
		grid-auto-rows: minmax(0, 1fr);
		flex: 1;
		min-height: 0;
		align-content: center;
	}
	.bar-row {
		display: grid;
		grid-template-columns: 34px 1fr 50px;
		align-items: center;
		gap: 8px;
	}
	.br-label {
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 800;
		letter-spacing: 0.3px;
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
	.compact-foot .ct-chip {
		font-size: calc(var(--font-xs) - 1px);
		padding: 2px 5px;
	}
	.age-small {
		margin-left: auto;
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 700;
	}

	/* Full variant extras */
	.extra {
		display: grid;
		grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) minmax(0, 1fr);
		gap: var(--card-gap);
	}
	.peak-grid {
		flex: 1;
		min-height: 0;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		grid-auto-rows: minmax(0, 1fr);
		gap: 6px;
	}
	.peak-cell {
		min-width: 0;
		min-height: 0;
		padding: 6px 8px;
		background: rgba(13, 17, 23, 0.45);
		border-radius: var(--radius-sm);
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		gap: 3px;
	}
	.peak-cell[data-level='warn'] .peak-value {
		color: #fbbf24;
	}
	.peak-cell[data-level='danger'] .peak-value {
		color: #f87171;
	}
	.peak-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 4px;
		min-width: 0;
	}
	.peak-label {
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.peak-value {
		color: var(--text-primary);
		font-size: var(--font-sm);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		line-height: 1;
	}
	.peak-sub {
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 2px);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.peak-track {
		height: 4px;
		border-radius: var(--radius-full);
		background: rgba(100, 116, 139, 0.2);
		overflow: hidden;
	}
	.peak-fill {
		display: block;
		height: 100%;
		border-radius: inherit;
		transition: width 0.4s ease;
		opacity: 0.9;
	}
	.ct-list {
		flex: 1;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		gap: 4px;
		min-height: 0;
	}
	.ct-row {
		display: grid;
		grid-template-columns: 8px 56px 1fr 48px;
		align-items: center;
		gap: 8px;
		font-size: var(--font-xs);
		font-weight: 700;
	}
	.ct-row.zero {
		opacity: 0.45;
	}
	.ct-row-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}
	.ct-row-label {
		color: var(--text-secondary);
		font-weight: 700;
	}
	.ct-row-track {
		height: 6px;
		border-radius: var(--radius-full);
		background: rgba(100, 116, 139, 0.2);
		overflow: hidden;
	}
	.ct-row-fill {
		display: block;
		height: 100%;
		border-radius: inherit;
		transition: width 0.4s ease;
	}
	.ct-row-count {
		display: inline-flex;
		align-items: baseline;
		justify-content: flex-end;
		gap: 4px;
		color: var(--text-muted);
		font-variant-numeric: tabular-nums;
	}
	.ct-row-count strong {
		color: var(--text-primary);
		font-weight: 800;
	}
	.ct-row-count small {
		font-size: calc(var(--font-xs) - 1px);
	}
	.extra-col {
		min-width: 0;
		padding: clamp(6px, 0.5vw, 10px);
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-height: 0;
		/* 툴팁이 카드 경계 밖으로 나갈 수 있도록 overflow visible 유지 */
		overflow: visible;
		position: relative;
	}
	.row-label {
		display: flex;
		align-items: center;
		gap: 4px;
		color: var(--text-muted);
		font-size: var(--font-xs);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.row-count {
		margin-left: auto;
		padding: 1px 7px;
		border-radius: var(--radius-full);
		background: rgba(48, 213, 200, 0.12);
		color: var(--accent);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 800;
		letter-spacing: 0;
	}
	.ct-bar {
		display: flex;
		height: clamp(8px, 0.7vh, 12px);
		border-radius: var(--radius-full);
		overflow: hidden;
		background: rgba(100, 116, 139, 0.2);
	}
	.ct-bar .seg {
		display: block;
		height: 100%;
	}
	.ct-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 700;
	}
	.ct-legend span {
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}
	.ct-legend span::before {
		content: '';
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--c);
	}
	.ct-legend b {
		color: var(--text-primary);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
	}
	.ct-empty {
		color: var(--text-muted);
		font-size: var(--font-xs);
		padding: 6px 0;
	}
	.spec-grid {
		flex: 1;
		min-height: 0;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		grid-auto-rows: minmax(0, 1fr);
		gap: 5px;
	}
	.spec {
		min-width: 0;
		min-height: 0;
		padding: 6px 8px;
		background: rgba(13, 17, 23, 0.45);
		border-radius: var(--radius-sm);
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		gap: 2px;
	}
	.spec-label {
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 1px);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.spec strong {
		color: var(--text-primary);
		font-size: var(--font-sm);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.spec strong.small {
		font-size: var(--font-xs);
	}
	.spec strong.off {
		color: #f87171;
	}
	.spec strong.agent-status {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: #34d399;
	}
	.spec strong.agent-status.off {
		color: #f87171;
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
	.spec-sub {
		color: var(--text-muted);
		font-size: calc(var(--font-xs) - 2px);
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* Medium footer */
	.card-foot {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.ct-line {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
		font-size: var(--font-xs);
	}
	.ct-label {
		color: var(--text-muted);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.ct-line > strong {
		color: var(--text-primary);
		font-size: var(--font-sm);
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
	.ct-chip {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		padding: 2px 6px;
		border-radius: var(--radius-sm);
		background: rgba(13, 17, 23, 0.55);
		color: var(--text-secondary);
		font-weight: 700;
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
</style>
