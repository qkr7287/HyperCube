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
		cpu_usage_max?: number;
		memory_percent: number;
		memory_percent_max?: number;
		network_rx: number;
		network_tx: number;
		disk_read: number;
		disk_write: number;
		gpu_usage: number | null;
		gpu_usage_max?: number | null;
		gpu_memory_used?: number | null;
		gpu_memory_total?: number | null;
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
		hasGpuMem = false,
		currentGpuMemPct = null,
		gpuMemAvg = 0,
		gpuMemPeak = 0,
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
		hasGpuMem?: boolean;
		currentGpuMemPct?: number | null;
		gpuMemAvg?: number;
		gpuMemPeak?: number;
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
	let gpuMemLevel = $derived(severity(currentGpuMemPct ?? 0, 80, 95));
	let activeBarTooltip = $state<string | null>(null);

	function showBarTooltip(key: string) {
		activeBarTooltip = key;
	}

	function hideBarTooltip(key: string) {
		if (activeBarTooltip === key) activeBarTooltip = null;
	}
</script>

<section class="kpi-bar" class:with-gpu={hasGpu || hasGpuMem} aria-label="컨테이너 메트릭 요약">
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
		<div
			class="meter"
			tabindex="0"
			aria-label={`CPU 현재 ${formatPercent(cpuNow, 2)}, ${rangeLabel} 평균 ${formatPercent(cpuAvg, 1)}, 피크 ${formatPercent(cpuPeak, 1)}`}
			onmouseenter={() => showBarTooltip('cpu')}
			onfocus={() => showBarTooltip('cpu')}
			onmouseleave={() => hideBarTooltip('cpu')}
			onblur={() => hideBarTooltip('cpu')}
			style={`--value:${clampPercent(cpuNow)}%;--avg:${clampPercent(cpuAvg)}%;--peak:${clampPercent(cpuPeak)}%;`}
		>
			<span class="meter-fill"></span>
			<span class="meter-marker avg" title="{rangeLabel} 평균 {formatPercent(cpuAvg, 1)}"></span>
			<span class="meter-marker peak" title="{rangeLabel} 피크 {formatPercent(cpuPeak, 1)}"></span>
			{#if activeBarTooltip === 'cpu'}
				<span class="bar-tooltip" role="tooltip">
					<strong>CPU 사용률</strong>
					<span><em>현재</em><b>{formatPercent(cpuNow, 2)}</b></span>
					<span><em>{rangeLabel} 평균</em><b>{formatPercent(cpuAvg, 1)}</b></span>
					<span><em>{rangeLabel} 피크</em><b>{formatPercent(cpuPeak, 1)}</b></span>
				</span>
			{/if}
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
		<div
			class="meter memory"
			tabindex="0"
			aria-label={`메모리 현재 ${formatPercent(memNow, 2)}, 사용 ${formatBytesValue(memUsed)}, 한도 ${formatBytesValue(memLimit)}, 여유 ${formatBytesValue(memFree)}`}
			onmouseenter={() => showBarTooltip('memory')}
			onfocus={() => showBarTooltip('memory')}
			onmouseleave={() => hideBarTooltip('memory')}
			onblur={() => hideBarTooltip('memory')}
			style={`--value:${clampPercent(memNow)}%;--avg:${clampPercent(memAvgPct)}%;--peak:${clampPercent(memPeakPct)}%;`}
		>
			<span class="meter-fill"></span>
			<span class="meter-marker avg" title="{rangeLabel} 평균 {formatPercent(memAvgPct, 1)}"></span>
			<span class="meter-marker peak" title="{rangeLabel} 피크 {formatPercent(memPeakPct, 1)}"></span>
			{#if activeBarTooltip === 'memory'}
				<span class="bar-tooltip" role="tooltip">
					<strong>메모리 사용량</strong>
					<span><em>현재</em><b>{formatPercent(memNow, 2)}</b></span>
					<span><em>사용</em><b>{formatBytesValue(memUsed)}</b></span>
					<span><em>한도</em><b>{formatBytesValue(memLimit)}</b></span>
					<span><em>여유</em><b>{formatBytesValue(memFree)}</b></span>
				</span>
			{/if}
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
		<div
			class="split-meter"
			tabindex="0"
			aria-label={`네트워크 누적 ${formatBytesValue(netTotal)}, RX ${formatBytesValue(netRx)}, TX ${formatBytesValue(netTx)}, ${rangeLabel} 증가 ${formatBytesValue(netDeltaTotal)}`}
			onmouseenter={() => showBarTooltip('network')}
			onfocus={() => showBarTooltip('network')}
			onmouseleave={() => hideBarTooltip('network')}
			onblur={() => hideBarTooltip('network')}
			style={`--a:${netRxShare}%;--b:${netTxShare}%;`}
		>
			<span class="split-a"></span>
			<span class="split-b"></span>
			{#if activeBarTooltip === 'network'}
				<span class="bar-tooltip" role="tooltip">
					<strong>네트워크 누적</strong>
					<span><em>전체</em><b>{formatBytesValue(netTotal)}</b></span>
					<span><em>RX</em><b>{formatBytesValue(netRx)}</b></span>
					<span><em>TX</em><b>{formatBytesValue(netTx)}</b></span>
					<span><em>{rangeLabel} 증가</em><b>{formatBytesValue(netDeltaTotal)}</b></span>
				</span>
			{/if}
		</div>
		<div class="flow-grid">
			<span>
				<b>RX</b>
				<span>{formatBytesValue(netRx)}</span>
				{#if netRxDelta > 0}<em>Δ {formatBytesValue(netRxDelta)}</em>{:else}<em class="muted">—</em>{/if}
			</span>
			<span>
				<b>TX</b>
				<span>{formatBytesValue(netTx)}</span>
				{#if netTxDelta > 0}<em>Δ {formatBytesValue(netTxDelta)}</em>{:else}<em class="muted">—</em>{/if}
			</span>
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
		<div
			class="split-meter disk"
			tabindex="0"
			aria-label={`디스크 누적 ${formatBytesValue(diskTotal)}, Read ${formatBytesValue(diskRead)}, Write ${formatBytesValue(diskWrite)}, ${rangeLabel} 증가 ${formatBytesValue(diskDeltaTotal)}`}
			onmouseenter={() => showBarTooltip('disk')}
			onfocus={() => showBarTooltip('disk')}
			onmouseleave={() => hideBarTooltip('disk')}
			onblur={() => hideBarTooltip('disk')}
			style={`--a:${diskReadShare}%;--b:${diskWriteShare}%;`}
		>
			<span class="split-a"></span>
			<span class="split-b"></span>
			{#if activeBarTooltip === 'disk'}
				<span class="bar-tooltip" role="tooltip">
					<strong>디스크 누적</strong>
					<span><em>전체</em><b>{formatBytesValue(diskTotal)}</b></span>
					<span><em>Read</em><b>{formatBytesValue(diskRead)}</b></span>
					<span><em>Write</em><b>{formatBytesValue(diskWrite)}</b></span>
					<span><em>{rangeLabel} 증가</em><b>{formatBytesValue(diskDeltaTotal)}</b></span>
				</span>
			{/if}
		</div>
		<div class="flow-grid">
			<span>
				<b>Read</b>
				<span>{formatBytesValue(diskRead)}</span>
				{#if diskReadDelta > 0}<em>Δ {formatBytesValue(diskReadDelta)}</em>{:else}<em class="muted">—</em>{/if}
			</span>
			<span>
				<b>Write</b>
				<span>{formatBytesValue(diskWrite)}</span>
				{#if diskWriteDelta > 0}<em>Δ {formatBytesValue(diskWriteDelta)}</em>{:else}<em class="muted">—</em>{/if}
			</span>
		</div>
	</div>

	{#if hasGpu}
		<div class="kpi" data-level={gpuLevel}>
			<div class="kpi-top">
				<span class="label">GPU (코어)</span>
				<span class="scope" data-level={gpuLevel}>{levelLabel(gpuLevel)}</span>
			</div>
			<div class="metric-hero">
				<strong class="value">{currentGpuUsage !== null ? formatPercent(currentGpuUsage, 2) : '-'}</strong>
				<span class="hero-note">{rangeLabel} 기준</span>
			</div>
			<div
				class="meter gpu"
				tabindex="0"
				aria-label={`GPU 코어 현재 ${currentGpuUsage !== null ? formatPercent(currentGpuUsage, 2) : '-'}, ${rangeLabel} 평균 ${formatPercent(gpuAvg, 1)}, 피크 ${formatPercent(gpuPeak, 1)}`}
				onmouseenter={() => showBarTooltip('gpu')}
				onfocus={() => showBarTooltip('gpu')}
				onmouseleave={() => hideBarTooltip('gpu')}
				onblur={() => hideBarTooltip('gpu')}
				style={`--value:${clampPercent(currentGpuUsage ?? 0)}%;--avg:${clampPercent(gpuAvg)}%;--peak:${clampPercent(gpuPeak)}%;`}
			>
				<span class="meter-fill"></span>
				<span class="meter-marker avg" title="{rangeLabel} 평균 {formatPercent(gpuAvg, 1)}"></span>
				<span class="meter-marker peak" title="{rangeLabel} 피크 {formatPercent(gpuPeak, 1)}"></span>
				{#if activeBarTooltip === 'gpu'}
					<span class="bar-tooltip" role="tooltip">
						<strong>GPU 코어 사용률</strong>
						<span><em>현재</em><b>{currentGpuUsage !== null ? formatPercent(currentGpuUsage, 2) : '-'}</b></span>
						<span><em>{rangeLabel} 평균</em><b>{formatPercent(gpuAvg, 1)}</b></span>
						<span><em>{rangeLabel} 피크</em><b>{formatPercent(gpuPeak, 1)}</b></span>
					</span>
				{/if}
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
		</div>
	{/if}

	{#if hasGpuMem}
		<div class="kpi" data-level={gpuMemLevel}>
			<div class="kpi-top">
				<span class="label">GPU (VRAM)</span>
				<span class="scope" data-level={gpuMemLevel}>{levelLabel(gpuMemLevel)}</span>
			</div>
			<div class="metric-hero">
				<strong class="value">{currentGpuMemPct !== null ? formatPercent(currentGpuMemPct, 2) : '-'}</strong>
				<span class="hero-note">{rangeLabel} 기준</span>
			</div>
			<div
				class="meter gpu-mem"
				tabindex="0"
				aria-label={`GPU VRAM 현재 ${currentGpuMemPct !== null ? formatPercent(currentGpuMemPct, 2) : '-'}, ${rangeLabel} 평균 ${formatPercent(gpuMemAvg, 1)}, 피크 ${formatPercent(gpuMemPeak, 1)}`}
				onmouseenter={() => showBarTooltip('gpuMem')}
				onfocus={() => showBarTooltip('gpuMem')}
				onmouseleave={() => hideBarTooltip('gpuMem')}
				onblur={() => hideBarTooltip('gpuMem')}
				style={`--value:${clampPercent(currentGpuMemPct ?? 0)}%;--avg:${clampPercent(gpuMemAvg)}%;--peak:${clampPercent(gpuMemPeak)}%;`}
			>
				<span class="meter-fill"></span>
				<span class="meter-marker avg" title="{rangeLabel} 평균 {formatPercent(gpuMemAvg, 1)}"></span>
				<span class="meter-marker peak" title="{rangeLabel} 피크 {formatPercent(gpuMemPeak, 1)}"></span>
				{#if activeBarTooltip === 'gpuMem'}
					<span class="bar-tooltip" role="tooltip">
						<strong>GPU 메모리 (VRAM)</strong>
						<span><em>현재</em><b>{currentGpuMemPct !== null ? formatPercent(currentGpuMemPct, 2) : '-'}</b></span>
						<span><em>{rangeLabel} 평균</em><b>{formatPercent(gpuMemAvg, 1)}</b></span>
						<span><em>{rangeLabel} 피크</em><b>{formatPercent(gpuMemPeak, 1)}</b></span>
					</span>
				{/if}
			</div>
			<div class="insight-row">
				<span>
					<b>평균</b>
					<span>{formatPercent(gpuMemAvg, 1)}</span>
				</span>
				<span>
					<b>피크</b>
					<span>{formatPercent(gpuMemPeak, 1)}</span>
				</span>
			</div>
		</div>
	{/if}
</section>

<style>
	/* 4-row 서브그리드 — 6 카드 모두 같은 row 트랙(kpi-top / metric-hero / meter / insight)
	   을 공유해 행 위치가 카드별로 같은 y에 정렬된다. align-content: space-between 으로
	   카드 stretch 시 남는 세로 공간이 행 사이로 균등 분산. */
	.kpi-bar {
		--kpi-pad: clamp(7px, 0.55vw, 10px);
		--kpi-radius: 10px;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(clamp(136px, 8vw, 178px), 1fr));
		grid-template-rows: auto auto auto auto;
		column-gap: clamp(5px, 0.4vw, 8px);
		row-gap: 7px;
		margin-top: 0;
		align-content: space-between;
	}

	.kpi {
		min-width: 0;
		min-height: clamp(98px, 9vh, 118px);
		padding: var(--kpi-pad);
		background:
			linear-gradient(180deg, rgba(23, 30, 42, 0.98), rgba(13, 18, 27, 0.98)),
			var(--bg-card);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: var(--kpi-radius);
		display: grid;
		grid-template-rows: subgrid;
		grid-row: span 4;
		position: relative;
		overflow: visible;
		box-shadow:
			0 8px 22px rgba(0, 0, 0, 0.14),
			inset 0 1px 0 rgba(255, 255, 255, 0.03);
		transition: border-color 0.15s ease, transform 0.15s ease;
	}

	.kpi:hover {
		border-color: rgba(48, 213, 200, 0.32);
		transform: translateY(-1px);
		z-index: 20;
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
	.flow-grid {
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
		font-size: clamp(10px, 0.62vw, 12px);
		font-weight: 850;
		letter-spacing: 0;
		white-space: nowrap;
	}
	.scope {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		justify-content: center;
		padding: 2px 7px 2px 6px;
		border-radius: 999px;
		background: rgba(2, 6, 12, 0.5);
		border: 1px solid rgba(100, 116, 139, 0.22);
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 900;
		letter-spacing: 0.02em;
		line-height: 1;
		white-space: nowrap;
	}
	.scope[data-level]::before {
		content: '';
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: currentColor;
		box-shadow: 0 0 6px currentColor;
		opacity: 0.85;
	}
	.scope[data-level='normal'] {
		color: #6ee7b7;
		border-color: rgba(16, 185, 129, 0.32);
		background: rgba(16, 185, 129, 0.08);
	}
	.scope[data-level='warn'] {
		color: #fde68a;
		border-color: rgba(251, 191, 36, 0.36);
		background: rgba(251, 191, 36, 0.08);
	}
	.scope[data-level='danger'] {
		color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.4);
		background: rgba(239, 68, 68, 0.1);
	}

	.metric-hero {
		display: flex;
		flex-direction: column;
		align-items: stretch;
		justify-content: flex-start;
		gap: 3px;
	}
	.value {
		color: var(--text-primary);
		font-size: clamp(19px, 1.16vw, 23px);
		font-weight: 850;
		line-height: 1.08;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		font-variant-numeric: tabular-nums;
	}
	.value.net {
		font-size: clamp(15px, 0.9vw, 18px);
	}
	.hero-note {
		max-width: 100%;
		color: var(--text-muted);
		font-size: clamp(9.5px, 0.58vw, 11px);
		font-weight: 700;
		line-height: 1.2;
		text-align: left;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.meter,
	.split-meter {
		position: relative;
		height: 14px;
		border-radius: 999px;
		background: rgba(2, 6, 12, 0.58);
		border: 1px solid rgba(100, 116, 139, 0.18);
		overflow: visible;
		outline: none;
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
		top: -5px;
		width: 2.5px;
		height: 24px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.78);
		box-shadow: 0 0 0 1px rgba(2, 6, 12, 0.78);
	}
	.meter-marker.avg {
		left: var(--avg, 0%);
		opacity: 0.62;
	}
	.meter-marker.peak {
		left: var(--peak, 0%);
		background: rgba(251, 191, 36, 0.94);
	}

	.meter:focus-visible,
	.split-meter:focus-visible {
		box-shadow:
			0 0 0 2px rgba(48, 213, 200, 0.34),
			inset 0 0 0 1px rgba(2, 6, 12, 0.82);
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

	.bar-tooltip {
		position: absolute;
		left: 0;
		top: calc(100% + 7px);
		z-index: 30;
		min-width: min(218px, calc(100vw - 28px));
		max-width: 240px;
		padding: 8px 9px;
		border-radius: 8px;
		background:
			linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 12, 0.98)),
			rgba(2, 6, 12, 0.96);
		border: 1px solid rgba(48, 213, 200, 0.28);
		box-shadow: 0 14px 30px rgba(0, 0, 0, 0.36);
		color: var(--text-primary);
		pointer-events: none;
		transform: translateY(0);
		animation: bar-tooltip-in 0.12s ease-out;
	}

	@keyframes bar-tooltip-in {
		from {
			transform: translateY(-4px);
		}
		to {
			transform: translateY(0);
		}
	}

	.bar-tooltip::before {
		content: '';
		position: absolute;
		left: 14px;
		top: -5px;
		width: 9px;
		height: 9px;
		background: rgba(15, 23, 42, 0.98);
		border-left: 1px solid rgba(48, 213, 200, 0.28);
		border-top: 1px solid rgba(48, 213, 200, 0.28);
		transform: rotate(45deg);
	}

	.bar-tooltip > strong {
		display: block;
		margin-bottom: 6px;
		color: var(--accent);
		font-size: 11.5px;
		font-weight: 900;
		line-height: 1;
	}

	.bar-tooltip span {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
		padding: 3px 0;
		border-top: 1px solid rgba(100, 116, 139, 0.12);
		font-size: 11.5px;
		line-height: 1.15;
	}

	.bar-tooltip span:first-of-type {
		border-top: 0;
	}

	.bar-tooltip em {
		color: var(--text-muted);
		font-style: normal;
		font-weight: 700;
		white-space: nowrap;
	}

	.bar-tooltip b {
		color: var(--text-primary);
		font-weight: 900;
		font-variant-numeric: tabular-nums;
		text-align: right;
		overflow-wrap: anywhere;
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
		font-size: clamp(10px, 0.6vw, 11px);
		font-weight: 750;
		font-variant-numeric: tabular-nums;
	}
	.insight-row b,
	.flow-grid b {
		display: block;
		margin-bottom: 3px;
		color: var(--text-muted);
		font-size: 9.5px;
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
		font-size: 9.5px;
		font-style: normal;
		font-weight: 700;
	}
	.flow-grid em.muted {
		color: rgba(100, 116, 139, 0.45);
		letter-spacing: 0.06em;
	}

</style>
