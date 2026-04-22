<script lang="ts">
	import { untrack } from 'svelte';
	import { sendCommand } from '$lib/stores/ws-store';
	import { adaptCpuDetail } from '$lib/utils/data-adapter';
	import LiveSparkline from './LiveSparkline.svelte';
	import InfoTooltip from './InfoTooltip.svelte';

	let {
		open = false,
		systemInfo = null,
		onClose = () => {},
	}: {
		open: boolean;
		systemInfo: any;
		onClose: () => void;
	} = $props();

	// Pull live CPU % straight off the WS-fed systemInfo prop so the
	// trend chart updates on every agent tick (no extra polling).
	const liveCpuPct = $derived(Math.round(systemInfo?.cpu?.usage ?? 0));
	const cpuSpec = $derived(systemInfo?.cpu ?? null);

	function formatSpecLine(spec: any): string {
		if (!spec) return '—';
		const cores = spec.cores ?? 0;
		const threads = spec.threads ?? cores;
		const sockets = spec.sockets ?? 1;
		if (spec.isHybrid) {
			const p = spec.performanceCores ?? 0;
			const e = spec.efficiencyCores ?? 0;
			return `${p}P + ${e}E / ${threads} threads`;
		}
		if (!cores && threads) return `${threads} threads`;
		if (sockets > 1) {
			return `${sockets} sockets × ${cores / sockets} cores / ${threads} threads`;
		}
		return `${cores} cores / ${threads} threads`;
	}

	let loading = $state(true);
	let data: any = $state(null);
	let pollInterval: ReturnType<typeof setInterval> | null = null;

	function getHeatColor(usage: number): string {
		if (usage < 15) return '#0d4f3c';
		if (usage < 30) return '#166534';
		if (usage < 45) return '#15803d';
		if (usage < 60) return '#a3a310';
		if (usage < 75) return '#ca8a04';
		if (usage < 85) return '#ea580c';
		if (usage < 95) return '#dc2626';
		return '#991b1b';
	}

	function getHeatGlow(usage: number): string {
		if (usage < 30) return 'none';
		if (usage < 60) return '0 0 8px rgba(202,138,4,0.3)';
		if (usage < 85) return '0 0 12px rgba(234,88,12,0.4)';
		return '0 0 16px rgba(220,38,38,0.5)';
	}

	async function fetchData() {
		try {
			const raw = await sendCommand('system_info', { subCommand: 'cpu_detail' });
			data = adaptCpuDetail(raw);
			loading = false;
		} catch (e) {
			console.error('[CpuDetailModal] sendCommand failed:', e);
			loading = false;
		}
	}

	function startPolling() {
		stopPolling();
		fetchData();
		pollInterval = setInterval(fetchData, 3000);
	}

	function stopPolling() {
		if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}

	$effect(() => {
		const isOpen = open;
		untrack(() => {
			if (isOpen) {
				loading = true;
				startPolling();
				document.addEventListener('keydown', handleKeydown);
			} else {
				stopPolling();
				document.removeEventListener('keydown', handleKeydown);
			}
		});
	});
</script>

{#if open}
<div class="overlay" onclick={onClose} role="dialog">
	<div class="modal" onclick={(e) => e.stopPropagation()}>
		<div class="modal-header">
			<span class="modal-title">CPU 상세 정보</span>
			<button class="close-btn" onclick={onClose}>
				<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2.5">
					<path d="M18 6L6 18M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="modal-content">
			{#if loading}
				<div class="loading-state">CPU 정보를 불러오는 중...</div>
			{:else if data}
				<!-- Overall stats -->
				<div class="stats-row">
					<div class="stat-card">
						<div class="stat-icon overall">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">전체 사용률</span>
							<span class="stat-value">{data.overall?.toFixed(1) ?? 0}<small>%</small></span>
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon cores">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="12" y1="2" x2="12" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="7" x2="22" y2="7"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="17" x2="22" y2="17"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">코어 / 스레드</span>
							{#if cpuSpec && cpuSpec.cores}
								<span class="stat-value">{cpuSpec.cores}<small>C</small> / {cpuSpec.threads ?? data.cores}<small>T</small></span>
							{:else}
								<span class="stat-value">{data.cores} <small>threads</small></span>
							{/if}
						</div>
					</div>
					<div class="stat-card">
						<div class="stat-icon load">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
						</div>
						<div class="stat-info">
							<span class="stat-label">Load Average</span>
							<span class="stat-value load-values">{data.loadAvg?.avg1?.toFixed(2)} <small>/</small> {data.loadAvg?.avg5?.toFixed(2)} <small>/</small> {data.loadAvg?.avg15?.toFixed(2)}</span>
						</div>
					</div>
				</div>

				<!-- Model + topology spec -->
				<div class="model-row">
					<span class="model-label">Processor</span>
					<span class="model-text">{data.model}</span>
				</div>
				{#if cpuSpec}
					<div class="spec-row">
						<span class="spec-pill">{formatSpecLine(cpuSpec)}</span>
						{#if (cpuSpec.sockets ?? 1) > 1}
							<span class="spec-pill">{cpuSpec.sockets} sockets</span>
						{/if}
						{#if cpuSpec.isHybrid}
							<span class="spec-pill hybrid">Hybrid (P + E)</span>
						{/if}
					</div>
				{/if}

				<!-- Live usage trend -->
				<div class="section-label">
					CPU 사용률 추이
					<span class="section-sub">실시간 · 최근 2분</span>
					<InfoTooltip
						placement="right"
						text="CPU가 얼마나 바쁜지 보여주는 그래프예요. 0% = 한가, 100% = 완전 포화. 80% 이상이 길게 이어지면 서버가 힘들어하는 신호라 작업을 줄이거나 서버를 키워야 할 수 있어요."
					/>
				</div>
				<div class="chart-legend">
					<span class="legend-dot" style="background:#30d5c8;"></span>
					<span class="legend-text">전체 CPU 사용률</span>
					<span class="legend-value">{liveCpuPct}%</span>
				</div>
				<div class="chart-frame">
					<LiveSparkline
						value={liveCpuPct}
						min={0}
						max={100}
						width={720}
						height={140}
						bufferSize={120}
						stroke="#30d5c8"
						fill="rgba(48,213,200,0.18)"
						smoothMs={1000}
					/>
					<div class="chart-axis">
						<span>0%</span>
						<span>50%</span>
						<span>100%</span>
					</div>
				</div>

				<!-- Load Average explanation -->
				{#if data.loadAvg}
					<div class="section-label">
						Load Average
						<InfoTooltip
							placement="right"
							text={`최근 1분/5분/15분 동안 평균 몇 개 작업이 CPU를 쓰려고 줄 서 있었는지 보여주는 숫자예요. 내 서버 스레드 수(${cpuSpec?.threads ?? data.cores}개)보다 작으면 여유, 비슷하면 딱 찬 상태, 더 크면 작업이 밀리는 중. 꾸준히 넘으면 서버가 모자라요.`}
						/>
					</div>
					<div class="load-display">
						<div class="load-cell">
							<span class="load-label">1 min</span>
							<span class="load-num">{data.loadAvg.avg1?.toFixed(2) ?? '—'}</span>
						</div>
						<div class="load-cell">
							<span class="load-label">5 min</span>
							<span class="load-num">{data.loadAvg.avg5?.toFixed(2) ?? '—'}</span>
						</div>
						<div class="load-cell">
							<span class="load-label">15 min</span>
							<span class="load-num">{data.loadAvg.avg15?.toFixed(2) ?? '—'}</span>
						</div>
					</div>
				{/if}

				<!-- Per-core heatmap -->
				<div class="section-label">
					코어별 사용률 히트맵
					<span class="section-sub">스레드 {data.perCore?.length ?? 0}개</span>
					<InfoTooltip
						placement="right"
						text="스레드 하나하나가 지금 얼마나 바쁜지 색으로 표시해요. 초록=한가, 노랑=적당, 빨강=꽉 참. 한 칸만 계속 빨강이면 어떤 프로그램이 그 스레드만 쓰고 있는 거라, 부하 분산이 잘 안 되는 상태일 수 있어요."
					/>
				</div>
				<div class="heatmap-legend">
					<span class="legend-label">Low</span>
					<div class="legend-gradient"></div>
					<span class="legend-label">High</span>
				</div>
				<div class="heatmap-grid" style="grid-template-columns: repeat({Math.min(data.perCore?.length ?? 4, 8)}, 1fr);">
					{#each (data.perCore || []) as core}
						<div
							class="heat-cell"
							style="background: {getHeatColor(core.usage)}; box-shadow: {getHeatGlow(core.usage)};"
							title="Core {core.core}: {core.usage.toFixed(1)}%"
						>
							<span class="heat-core-id">C{core.core}</span>
							<span class="heat-value">{core.usage.toFixed(0)}%</span>
						</div>
					{/each}
				</div>

				<!-- Legend scale -->
				<div class="scale-row">
					<span class="scale-item" style="background: #0d4f3c;">0-15%</span>
					<span class="scale-item" style="background: #166534;">15-30%</span>
					<span class="scale-item" style="background: #15803d;">30-45%</span>
					<span class="scale-item" style="background: #a3a310;">45-60%</span>
					<span class="scale-item" style="background: #ca8a04;">60-75%</span>
					<span class="scale-item" style="background: #ea580c;">75-85%</span>
					<span class="scale-item" style="background: #dc2626;">85-95%</span>
					<span class="scale-item" style="background: #991b1b;">95%+</span>
				</div>
			{/if}
		</div>
	</div>
</div>
{/if}

<style>
	.overlay {
		position: fixed; inset: 0; z-index: 100;
		background: rgba(0,0,0,0.6); display: flex;
		align-items: center; justify-content: center;
		backdrop-filter: blur(4px);
	}
	.modal {
		width: 720px; max-height: 85vh;
		background: #0d1117; border: 1px solid #30d5c8;
		border-radius: 12px; display: flex;
		flex-direction: column; overflow: hidden;
	}
	.modal-header {
		display: flex; justify-content: space-between; align-items: center;
		padding: 24px 28px; border-bottom: 1px solid #1f2937;
	}
	.modal-title { font-size: 17px; font-weight: 700; color: #d9d9d9; }
	.close-btn { background: none; border: none; cursor: pointer; padding: 6px; display: flex; }
	.close-btn:hover svg { stroke: #cbd5e1; }
	.modal-content {
		flex: 1;
		overflow-y: auto;
		padding: 28px;
		display: flex;
		flex-direction: column;
		gap: 20px;
		/* Firefox */
		scrollbar-width: thin;
		scrollbar-color: rgba(148, 163, 184, 0.35) transparent;
	}
	.modal-content::-webkit-scrollbar { width: 10px; }
	.modal-content::-webkit-scrollbar-track { background: transparent; }
	.modal-content::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.3);
		border: 2px solid transparent;
		border-radius: 8px;
		background-clip: padding-box;
	}
	.modal-content::-webkit-scrollbar-thumb:hover {
		background: rgba(48, 213, 200, 0.55);
		background-clip: padding-box;
	}
	.loading-state { text-align: center; color: #64748b; font-size: 14px; padding: 32px; }
	.section-label {
		font-size: 14px;
		font-weight: 700;
		color: #64748b;
		display: flex;
		align-items: baseline;
		gap: 10px;
	}
	.section-sub {
		font-size: 11px;
		font-weight: 500;
		color: #475569;
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}

	.section-desc {
		margin: 0;
		font-size: 12px;
		line-height: 1.55;
		color: #94a3b8;
		background: rgba(15, 23, 42, 0.6);
		border-left: 3px solid rgba(48, 213, 200, 0.5);
		padding: 10px 14px;
		border-radius: 0 6px 6px 0;
	}
	.section-desc strong {
		color: #cbd5e1;
		font-weight: 600;
	}

	/* Topology pill row */
	.spec-row {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	.spec-pill {
		font-size: 12px;
		color: #cbd5e1;
		background: #1f2937;
		border: 1px solid #334155;
		border-radius: 999px;
		padding: 4px 12px;
		font-weight: 600;
	}
	.spec-pill.hybrid {
		background: rgba(139, 92, 246, 0.14);
		border-color: rgba(139, 92, 246, 0.5);
		color: #c4b5fd;
	}

	/* Live trend chart */
	.chart-legend {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 0 4px;
	}
	.legend-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.legend-text {
		font-size: 12px;
		color: #cbd5e1;
	}
	.legend-value {
		margin-left: auto;
		font-size: 13px;
		font-weight: 700;
		color: #30d5c8;
		font-variant-numeric: tabular-nums;
	}
	.chart-frame {
		position: relative;
		background: #0f172a;
		border: 1px solid rgba(148, 163, 184, 0.12);
		border-radius: 12px;
		padding: 14px 48px 28px 48px;
	}
	.chart-axis {
		position: absolute;
		left: 12px;
		top: 12px;
		bottom: 12px;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		font-size: 10px;
		color: #475569;
		font-variant-numeric: tabular-nums;
	}

	/* Load average display */
	.load-display {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 10px;
	}
	.load-cell {
		background: #121720;
		border-radius: 10px;
		padding: 12px 14px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.load-label {
		font-size: 10px;
		color: #64748b;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		font-weight: 600;
	}
	.load-num {
		font-size: 20px;
		font-weight: 700;
		color: #cbd5e1;
		font-variant-numeric: tabular-nums;
	}

	.stats-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
	.stat-card {
		background: #121720; border-radius: 10px; padding: 16px;
		display: flex; align-items: center; gap: 12px;
	}
	.stat-icon {
		width: 40px; height: 40px; border-radius: 50%;
		display: flex; align-items: center; justify-content: center; flex-shrink: 0;
	}
	.stat-icon.overall { background: rgba(48,213,200,0.15); color: #30d5c8; }
	.stat-icon.cores { background: rgba(99,102,241,0.15); color: #6366f1; }
	.stat-icon.load { background: rgba(245,158,11,0.15); color: #f59e0b; }
	.stat-info { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
	.stat-label { font-size: 12px; color: #64748b; }
	.stat-value { font-size: 15px; font-weight: 700; color: #cbd5e1; }
	.stat-value small { font-size: 12px; font-weight: 400; color: #64748b; }
	.load-values { font-size: 13px; }

	.model-row {
		background: #121720; border-radius: 10px; padding: 12px 16px;
		display: flex; align-items: center; gap: 12px;
	}
	.model-label { font-size: 12px; color: #64748b; white-space: nowrap; }
	.model-text { font-size: 12px; color: #cbd5e1; font-family: monospace; }

	/* Heatmap */
	.heatmap-legend {
		display: flex; align-items: center; gap: 8px;
	}
	.legend-label { font-size: 10px; color: #475569; }
	.legend-gradient {
		flex: 1; height: 6px; border-radius: 3px;
		background: linear-gradient(to right, #0d4f3c, #166534, #15803d, #a3a310, #ca8a04, #ea580c, #dc2626, #991b1b);
	}

	.heatmap-grid {
		display: grid;
		gap: 6px;
	}

	.heat-cell {
		aspect-ratio: 1;
		border-radius: 8px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		transition: background 0.5s ease, box-shadow 0.5s ease;
		cursor: default;
		min-height: 56px;
	}

	.heat-core-id {
		font-size: 10px;
		font-weight: 700;
		color: rgba(255,255,255,0.5);
		font-family: monospace;
	}

	.heat-value {
		font-size: 14px;
		font-weight: 700;
		color: rgba(255,255,255,0.9);
		font-family: monospace;
	}

	.scale-row {
		display: flex; gap: 4px; justify-content: center;
	}
	.scale-item {
		padding: 3px 8px; border-radius: 4px;
		font-size: 9px; font-weight: 600; color: rgba(255,255,255,0.7);
		font-family: monospace;
	}
</style>
