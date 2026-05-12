<!--
  ContainerKpiBar — 단일 컨테이너 dashboard KPI bar.

  관리자 메인의 FleetStatusBar 와 동일 시각 언어:
  - clamp() 기반 padding/font (반응형 일관성)
  - data-level 좌측 stripe (warn/danger)
  - 라벨 + value + sub + sparkline 하단

  metric 4~5개를 한 줄 grid (auto-fit minmax) 로 압축. 좁은 화면에서는
  자동으로 wrap.
-->
<script lang="ts">
	import InfoTooltip from './InfoTooltip.svelte';
	import MetricSparkline from './fleet/MetricSparkline.svelte';
	import {
		formatBytesValue,
		formatMemoryUsage,
		formatPercent,
	} from '$lib/utils/container-dashboard';

	type MetricsSnapshot = {
		cpu?: { usage?: number };
		memory?: { usage?: number; limit?: number; percent?: number };
		network?: { rx?: number; tx?: number };
		disk?: { read?: number; write?: number };
	};

	type MetricsHistoryRow = {
		cpu_usage: number;
		memory_percent: number;
		network_rx: number;
		network_tx: number;
		disk_read: number;
		disk_write: number;
		gpu_usage: number | null;
	};

	let {
		currentMetrics,
		history,
		rangeLabel,
		cpuAvg,
		cpuPeak,
		memAvgPct,
		memPeakPct,
		netRxDelta,
		netTxDelta,
		diskReadDelta,
		diskWriteDelta,
		hasGpu = false,
		currentGpuUsage = null,
		gpuAvg = 0,
		gpuPeak = 0,
		cpuHelp = '',
		memoryHelp = '',
		networkHelp = '',
		diskHelp = '',
	}: {
		currentMetrics: MetricsSnapshot | null;
		history: MetricsHistoryRow[];
		rangeLabel: string;
		cpuAvg: number;
		cpuPeak: number;
		memAvgPct: number;
		memPeakPct: number;
		netRxDelta: number;
		netTxDelta: number;
		diskReadDelta: number;
		diskWriteDelta: number;
		hasGpu?: boolean;
		currentGpuUsage?: number | null;
		gpuAvg?: number;
		gpuPeak?: number;
		cpuHelp?: string;
		memoryHelp?: string;
		networkHelp?: string;
		diskHelp?: string;
	} = $props();

	function severity(value: number, warn: number, crit: number): 'normal' | 'warn' | 'danger' {
		if (value >= crit) return 'danger';
		if (value >= warn) return 'warn';
		return 'normal';
	}

	function asNumber(value: number | null | undefined): number {
		const n = Number(value ?? 0);
		return Number.isFinite(n) ? n : 0;
	}

	function clampPercent(value: number): number {
		return Math.max(0, Math.min(100, value));
	}

	function shareOf(value: number, total: number): number {
		if (total <= 0) return 0;
		return clampPercent((value / total) * 100);
	}

	function levelLabel(level: 'normal' | 'warn' | 'danger'): string {
		if (level === 'danger') return '위험';
		if (level === 'warn') return '주의';
		return '정상';
	}

	let cpuTrend = $derived(history.map((r) => r.cpu_usage));
	let memTrend = $derived(history.map((r) => r.memory_percent));
	let netTrend = $derived(history.map((r) => (r.network_rx ?? 0) + (r.network_tx ?? 0)));
	let diskTrend = $derived(history.map((r) => (r.disk_read ?? 0) + (r.disk_write ?? 0)));
	let gpuTrend = $derived(history.map((r) => r.gpu_usage ?? 0));

	let cpuNow = $derived(asNumber(currentMetrics?.cpu?.usage));
	let memNow = $derived(asNumber(currentMetrics?.memory?.percent));
	let memUsed = $derived(asNumber(currentMetrics?.memory?.usage));
	let memLimit = $derived(asNumber(currentMetrics?.memory?.limit));
	let memFree = $derived(Math.max(0, memLimit - memUsed));
	let netRx = $derived(asNumber(currentMetrics?.network?.rx));
	let netTx = $derived(asNumber(currentMetrics?.network?.tx));
	let netTotal = $derived(netRx + netTx);
	let netDeltaTotal = $derived(netRxDelta + netTxDelta);
	let diskRead = $derived(asNumber(currentMetrics?.disk?.read));
	let diskWrite = $derived(asNumber(currentMetrics?.disk?.write));
	let diskTotal = $derived(diskRead + diskWrite);
	let diskDeltaTotal = $derived(diskReadDelta + diskWriteDelta);

	let netRxShare = $derived(shareOf(netRx, netTotal));
	let netTxShare = $derived(shareOf(netTx, netTotal));
	let diskReadShare = $derived(shareOf(diskRead, diskTotal));
	let diskWriteShare = $derived(shareOf(diskWrite, diskTotal));

	let cpuLevel = $derived(severity(cpuNow, 70, 90));
	let memLevel = $derived(severity(memNow, 75, 90));
	let gpuLevel = $derived(severity(currentGpuUsage ?? 0, 80, 95));
</script>

<section class="kpi-bar" class:with-gpu={hasGpu} aria-label="컨테이너 메트릭 요약">
	<div class="kpi" data-level={cpuLevel}>
		<div class="kpi-top">
			<span class="label">
				CPU
				{#if cpuHelp}<InfoTooltip text={cpuHelp} placement="bottom-start" />{/if}
			</span>
			<span class="scope" data-level={cpuLevel}>{levelLabel(cpuLevel)}</span>
		</div>
		<div class="metric-hero">
			<strong class="value">{formatPercent(cpuNow, 2)}</strong>
			<span class="hero-note">{rangeLabel} 기준</span>
		</div>
		<div class="meter" style={`--value:${clampPercent(cpuNow)}%;--avg:${clampPercent(cpuAvg)}%;--peak:${clampPercent(cpuPeak)}%;`}>
			<span class="meter-fill"></span>
			<span class="meter-marker avg" title="{rangeLabel} 평균 {formatPercent(cpuAvg, 1)}"></span>
			<span class="meter-marker peak" title="{rangeLabel} 피크 {formatPercent(cpuPeak, 1)}"></span>
		</div>
		<div class="insight-row">
			<span>
				<b>평균</b>
				<span>{formatPercent(cpuAvg, 1)}</span>
			</span>
			<span>
				<b>피크</b>
				<span>{formatPercent(cpuPeak, 1)}</span>
			</span>
		</div>
		<div class="trend-strip">
			<span>추이</span>
			<MetricSparkline values={cpuTrend} color="#30d5c8" label="CPU 추이" />
		</div>
	</div>

	<div class="kpi" data-level={memLevel}>
		<div class="kpi-top">
			<span class="label">
				메모리
				{#if memoryHelp}<InfoTooltip text={memoryHelp} placement="bottom-start" />{/if}
			</span>
			<span class="scope" data-level={memLevel}>{levelLabel(memLevel)}</span>
		</div>
		<div class="metric-hero">
			<strong class="value">{formatPercent(memNow, 2)}</strong>
			<span class="hero-note">{formatMemoryUsage(memUsed, memLimit)}</span>
		</div>
		<div class="meter memory" style={`--value:${clampPercent(memNow)}%;--avg:${clampPercent(memAvgPct)}%;--peak:${clampPercent(memPeakPct)}%;`}>
			<span class="meter-fill"></span>
			<span class="meter-marker avg" title="{rangeLabel} 평균 {formatPercent(memAvgPct, 1)}"></span>
			<span class="meter-marker peak" title="{rangeLabel} 피크 {formatPercent(memPeakPct, 1)}"></span>
		</div>
		<div class="insight-row triple">
			<span title={formatMemoryUsage(memUsed, memLimit)}>
				<b>사용</b>
				<span>{formatBytesValue(memUsed)}</span>
			</span>
			<span>
				<b>여유</b>
				<span>{formatBytesValue(memFree)}</span>
			</span>
			<span>
				<b>피크</b>
				<span>{formatPercent(memPeakPct, 1)}</span>
			</span>
		</div>
		<div class="trend-strip">
			<span>추이</span>
			<MetricSparkline values={memTrend} color="#60a5fa" label="메모리 추이" />
		</div>
	</div>

	<div class="kpi">
		<div class="kpi-top">
			<span class="label">
				네트워크
				{#if networkHelp}<InfoTooltip text={networkHelp} placement="bottom-start" />{/if}
			</span>
			<span class="scope">누적</span>
		</div>
		<div class="metric-hero">
			<strong class="value net">{formatBytesValue(netTotal)}</strong>
			<span class="hero-note">{rangeLabel} 증가 {formatBytesValue(netDeltaTotal)}</span>
		</div>
		<div class="split-meter" style={`--a:${netRxShare}%;--b:${netTxShare}%;`}>
			<span class="split-a"></span>
			<span class="split-b"></span>
		</div>
		<div class="flow-grid">
			<span>
				<b>RX 누적</b>
				<span>{formatBytesValue(netRx)}</span>
				<em>Δ {formatBytesValue(netRxDelta)}</em>
			</span>
			<span>
				<b>TX 누적</b>
				<span>{formatBytesValue(netTx)}</span>
				<em>Δ {formatBytesValue(netTxDelta)}</em>
			</span>
		</div>
		<div class="trend-strip">
			<span>합계</span>
			<MetricSparkline values={netTrend} color="#fbbf24" label="네트워크 추이" />
		</div>
	</div>

	<div class="kpi">
		<div class="kpi-top">
			<span class="label">
				디스크
				{#if diskHelp}<InfoTooltip text={diskHelp} placement="bottom-start" />{/if}
			</span>
			<span class="scope">누적</span>
		</div>
		<div class="metric-hero">
			<strong class="value net">{formatBytesValue(diskTotal)}</strong>
			<span class="hero-note">{rangeLabel} 증가 {formatBytesValue(diskDeltaTotal)}</span>
		</div>
		<div class="split-meter disk" style={`--a:${diskReadShare}%;--b:${diskWriteShare}%;`}>
			<span class="split-a"></span>
			<span class="split-b"></span>
		</div>
		<div class="flow-grid">
			<span>
				<b>Read</b>
				<span>{formatBytesValue(diskRead)}</span>
				<em>Δ {formatBytesValue(diskReadDelta)}</em>
			</span>
			<span>
				<b>Write</b>
				<span>{formatBytesValue(diskWrite)}</span>
				<em>Δ {formatBytesValue(diskWriteDelta)}</em>
			</span>
		</div>
		<div class="trend-strip">
			<span>합계</span>
			<MetricSparkline values={diskTrend} color="#a78bfa" label="디스크 추이" />
		</div>
	</div>

	{#if hasGpu}
		<div class="kpi" data-level={gpuLevel}>
			<div class="kpi-top">
				<span class="label">GPU</span>
				<span class="scope" data-level={gpuLevel}>{levelLabel(gpuLevel)}</span>
			</div>
			<div class="metric-hero">
				<strong class="value">{currentGpuUsage !== null ? formatPercent(currentGpuUsage, 2) : '-'}</strong>
				<span class="hero-note">{rangeLabel} 기준</span>
			</div>
			<div class="meter gpu" style={`--value:${clampPercent(currentGpuUsage ?? 0)}%;--avg:${clampPercent(gpuAvg)}%;--peak:${clampPercent(gpuPeak)}%;`}>
				<span class="meter-fill"></span>
				<span class="meter-marker avg" title="{rangeLabel} 평균 {formatPercent(gpuAvg, 1)}"></span>
				<span class="meter-marker peak" title="{rangeLabel} 피크 {formatPercent(gpuPeak, 1)}"></span>
			</div>
			<div class="insight-row">
				<span>
					<b>평균</b>
					<span>{formatPercent(gpuAvg, 1)}</span>
				</span>
				<span>
					<b>피크</b>
					<span>{formatPercent(gpuPeak, 1)}</span>
				</span>
			</div>
			<div class="trend-strip">
				<span>추이</span>
				<MetricSparkline values={gpuTrend} color="#f472b6" label="GPU 추이" />
			</div>
		</div>
	{/if}
</section>

<style>
	.kpi-bar {
		--kpi-pad: clamp(7px, 0.55vw, 10px);
		--kpi-radius: 10px;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(clamp(136px, 8vw, 178px), 1fr));
		gap: clamp(5px, 0.4vw, 8px);
		margin-top: 0;
		align-items: stretch;
	}

	.kpi {
		min-width: 0;
		min-height: clamp(136px, 12vh, 156px);
		padding: var(--kpi-pad);
		background:
			linear-gradient(180deg, rgba(23, 30, 42, 0.98), rgba(13, 18, 27, 0.98)),
			var(--bg-card);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: var(--kpi-radius);
		display: flex;
		flex-direction: column;
		gap: 7px;
		position: relative;
		overflow: hidden;
		box-shadow:
			0 8px 22px rgba(0, 0, 0, 0.14),
			inset 0 1px 0 rgba(255, 255, 255, 0.03);
		transition: border-color 0.15s ease, transform 0.15s ease;
	}

	.kpi:hover {
		border-color: rgba(48, 213, 200, 0.32);
		transform: translateY(-1px);
	}

	.kpi::before {
		content: '';
		position: absolute;
		inset: 0 auto 0 0;
		width: 3px;
		background: rgba(48, 213, 200, 0.5);
	}

	.kpi[data-level='warn'] {
		border-color: rgba(251, 191, 36, 0.34);
		background:
			linear-gradient(90deg, rgba(251, 191, 36, 0.09), transparent 42%),
			linear-gradient(180deg, rgba(23, 30, 42, 0.98), rgba(13, 18, 27, 0.98));
	}
	.kpi[data-level='warn']::before {
		background: #fbbf24;
	}
	.kpi[data-level='danger'] {
		border-color: rgba(239, 68, 68, 0.42);
		background:
			linear-gradient(90deg, rgba(239, 68, 68, 0.12), transparent 45%),
			linear-gradient(180deg, rgba(23, 30, 42, 0.98), rgba(13, 18, 27, 0.98));
	}
	.kpi[data-level='danger']::before {
		background: #f87171;
		box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);
	}

	.kpi-top,
	.metric-hero,
	.insight-row,
	.flow-grid,
	.trend-strip {
		min-width: 0;
	}

	.kpi-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
	}
	.label {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: var(--text-muted);
		font-size: clamp(9px, 0.55vw, 11px);
		font-weight: 850;
		letter-spacing: 0;
		white-space: nowrap;
	}
	.scope {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 2px 6px;
		border-radius: 999px;
		background: rgba(2, 6, 12, 0.42);
		border: 1px solid rgba(100, 116, 139, 0.18);
		color: var(--text-muted);
		font-size: 8.5px;
		font-weight: 850;
		line-height: 1;
		white-space: nowrap;
	}
	.scope[data-level='normal'] {
		color: #6ee7b7;
		border-color: rgba(16, 185, 129, 0.28);
	}
	.scope[data-level='warn'] {
		color: #fde68a;
		border-color: rgba(251, 191, 36, 0.32);
	}
	.scope[data-level='danger'] {
		color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.36);
	}

	.metric-hero {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 8px;
	}
	.value {
		color: var(--text-primary);
		font-size: clamp(18px, 1.1vw, 22px);
		font-weight: 850;
		line-height: 1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		font-variant-numeric: tabular-nums;
	}
	.value.net {
		font-size: clamp(14px, 0.84vw, 17px);
	}
	.hero-note {
		max-width: 58%;
		color: var(--text-muted);
		font-size: clamp(8.5px, 0.52vw, 10px);
		font-weight: 700;
		line-height: 1.15;
		text-align: right;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meter,
	.split-meter {
		position: relative;
		height: 12px;
		border-radius: 999px;
		background: rgba(2, 6, 12, 0.58);
		border: 1px solid rgba(100, 116, 139, 0.18);
		overflow: hidden;
	}
	.meter {
		overflow: visible;
	}
	.meter::before {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
		background: linear-gradient(90deg, transparent 69%, rgba(251, 191, 36, 0.24) 70%, rgba(251, 191, 36, 0.24) 89%, rgba(239, 68, 68, 0.22) 90%);
		pointer-events: none;
	}
	.meter-fill {
		position: absolute;
		inset: 0 auto 0 0;
		width: var(--value, 0%);
		border-radius: inherit;
		background: linear-gradient(90deg, rgba(48, 213, 200, 0.86), rgba(96, 165, 250, 0.82));
	}
	.meter.memory .meter-fill {
		background: linear-gradient(90deg, rgba(96, 165, 250, 0.9), rgba(129, 140, 248, 0.82));
	}
	.meter.gpu .meter-fill {
		background: linear-gradient(90deg, rgba(244, 114, 182, 0.88), rgba(168, 85, 247, 0.78));
	}
	.meter-marker {
		position: absolute;
		top: -4px;
		width: 2px;
		height: 20px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.72);
		box-shadow: 0 0 0 1px rgba(2, 6, 12, 0.7);
	}
	.meter-marker.avg {
		left: var(--avg, 0%);
		opacity: 0.62;
	}
	.meter-marker.peak {
		left: var(--peak, 0%);
		background: rgba(251, 191, 36, 0.94);
	}

	.split-meter {
		display: flex;
		gap: 2px;
		padding: 2px;
	}
	.split-a,
	.split-b {
		min-width: 4px;
		border-radius: 999px;
	}
	.split-a {
		width: var(--a, 0%);
		background: rgba(48, 213, 200, 0.86);
	}
	.split-b {
		width: var(--b, 0%);
		background: rgba(251, 191, 36, 0.82);
	}
	.split-meter.disk .split-a {
		background: rgba(167, 139, 250, 0.86);
	}
	.split-meter.disk .split-b {
		background: rgba(96, 165, 250, 0.82);
	}

	.insight-row,
	.flow-grid {
		display: grid;
		gap: 4px;
	}
	.insight-row {
		grid-template-columns: repeat(auto-fit, minmax(42px, 1fr));
	}
	.insight-row.triple {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	.flow-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
	.insight-row > span,
	.flow-grid > span {
		min-width: 0;
		padding: 5px 6px;
		border-radius: 7px;
		background: rgba(2, 6, 12, 0.32);
		border: 1px solid rgba(100, 116, 139, 0.12);
		color: var(--text-secondary);
		font-size: clamp(9px, 0.55vw, 10px);
		font-weight: 750;
		font-variant-numeric: tabular-nums;
	}
	.insight-row b,
	.flow-grid b {
		display: block;
		margin-bottom: 3px;
		color: var(--text-muted);
		font-size: 7.5px;
		font-weight: 900;
		letter-spacing: 0;
		text-transform: uppercase;
	}
	.insight-row span span,
	.flow-grid span span,
	.flow-grid em {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.flow-grid em {
		margin-top: 2px;
		color: var(--text-muted);
		font-size: 8.5px;
		font-style: normal;
		font-weight: 700;
	}

	.trend-strip {
		position: relative;
		display: block;
		margin-top: auto;
		height: 38px;
		min-height: 38px;
		padding: 1px 0 2px;
		border-radius: 8px;
		background:
			linear-gradient(180deg, rgba(2, 6, 12, 0.34), rgba(2, 6, 12, 0.2)),
			rgba(2, 6, 12, 0.26);
		border: 1px solid rgba(100, 116, 139, 0.14);
		overflow: hidden;
	}
	.trend-strip > span {
		position: absolute;
		left: 6px;
		top: 5px;
		z-index: 1;
		padding: 2px 5px;
		border-radius: 999px;
		background: rgba(2, 6, 12, 0.64);
		border: 1px solid rgba(100, 116, 139, 0.16);
		color: var(--text-muted);
		font-size: 8px;
		font-weight: 900;
		letter-spacing: 0;
		line-height: 1;
		pointer-events: none;
	}
	.trend-strip :global(.spark-wrap) {
		position: absolute;
		inset: 1px 0 2px;
		width: 100%;
		height: auto;
		align-items: stretch;
	}
	.trend-strip :global(svg) {
		display: block;
		width: 100%;
		height: 100%;
		max-width: none;
		min-height: 0;
		overflow: visible;
	}
	.trend-strip :global(line) {
		transform: translateY(-2px);
	}
	.trend-strip :global(polyline) {
		stroke-width: 2.5;
		vector-effect: non-scaling-stroke;
	}
</style>
