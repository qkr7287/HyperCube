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
	import {
		asNumber,
		clampPercent,
		compactBytes,
		deltaTone,
		formatDelta,
		levelLabel,
		pctRangeStatus,
		severity,
		shareOf,
	} from '$lib/utils/container-kpi';

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

	// 현재값과 기간 평균 간 편차 — "지금 평소보다 +N% 위" / "−N% 아래" 직관용.
	// 음수면 안정·하락, 양수면 상승. 0 근처면 평균 유지.
	let cpuDelta = $derived(cpuNow - cpuAvg);
	let memDelta = $derived(memNow - memAvgPct);
	let gpuDelta = $derived((currentGpuUsage ?? 0) - gpuAvg);
	let gpuMemDelta = $derived((currentGpuMemPct ?? 0) - gpuMemAvg);

	let cpuStatus = $derived(pctRangeStatus(cpuLevel, 70, 90));
	let memStatus = $derived(pctRangeStatus(memLevel, 75, 90));
	let gpuStatus = $derived(pctRangeStatus(gpuLevel, 80, 95));
	let gpuMemStatus = $derived(pctRangeStatus(gpuMemLevel, 80, 95));

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
			<span class="scope dot" data-level={cpuLevel} title={levelLabel(cpuLevel)} aria-label="상태 {levelLabel(cpuLevel)}"></span>
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
		<div class="status-line" data-level={cpuLevel}>{cpuStatus}</div>
		<div class="insight-row triple">
			<span>
				<b>평균</b>
				<span>{formatPercent(cpuAvg, 1)}</span>
			</span>
			<span>
				<b>피크</b>
				<span>{formatPercent(cpuPeak, 1)}</span>
			</span>
			<span data-tone={deltaTone(cpuDelta)} title="현재값 − {rangeLabel} 평균">
				<b>Δ 평균</b>
				<span>{formatDelta(cpuDelta)}</span>
			</span>
		</div>
	</div>

	<div class="kpi" data-level={memLevel}>
		<div class="kpi-top">
			<span class="label">
				메모리
				{#if memoryHelp}<InfoTooltip text={memoryHelp} placement="bottom-start" />{/if}
			</span>
			<span class="scope dot" data-level={memLevel} title={levelLabel(memLevel)} aria-label="상태 {levelLabel(memLevel)}"></span>
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
		<div class="status-line" data-level={memLevel}>{memStatus}</div>
		<div class="insight-row triple">
			<span title={formatMemoryUsage(memUsed, memLimit)}>
				<b>사용</b>
				<span>{compactBytes(memUsed)}</span>
			</span>
			<span title="여유 {formatBytesValue(memFree)}">
				<b>여유</b>
				<span>{compactBytes(memFree)}</span>
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
		<div class="status-line" data-flow={netDeltaTotal > 0 ? 'active' : 'idle'}>
			{netDeltaTotal > 0 ? `${rangeLabel} 트래픽 +${formatBytesValue(netDeltaTotal)}` : `${rangeLabel} 트래픽 정체`}
		</div>
		<div class="flow-grid">
			<span title="RX {formatBytesValue(netRx)}">
				<b>RX</b>
				<span>{compactBytes(netRx)}</span>
				{#if netRxDelta > 0}<em>Δ {compactBytes(netRxDelta)}</em>{:else}<em class="muted">—</em>{/if}
			</span>
			<span title="TX {formatBytesValue(netTx)}">
				<b>TX</b>
				<span>{compactBytes(netTx)}</span>
				{#if netTxDelta > 0}<em>Δ {compactBytes(netTxDelta)}</em>{:else}<em class="muted">—</em>{/if}
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
		<div class="status-line" data-flow={diskDeltaTotal > 0 ? 'active' : 'idle'}>
			{diskDeltaTotal > 0 ? `${rangeLabel} I/O +${formatBytesValue(diskDeltaTotal)}` : `${rangeLabel} I/O 정체`}
		</div>
		<div class="flow-grid">
			<span title="Read {formatBytesValue(diskRead)}">
				<b>Read</b>
				<span>{compactBytes(diskRead)}</span>
				{#if diskReadDelta > 0}<em>Δ {compactBytes(diskReadDelta)}</em>{:else}<em class="muted">—</em>{/if}
			</span>
			<span title="Write {formatBytesValue(diskWrite)}">
				<b>Write</b>
				<span>{compactBytes(diskWrite)}</span>
				{#if diskWriteDelta > 0}<em>Δ {compactBytes(diskWriteDelta)}</em>{:else}<em class="muted">—</em>{/if}
			</span>
		</div>
	</div>

	{#if hasGpu}
		<div class="kpi" data-level={gpuLevel}>
			<div class="kpi-top">
				<span class="label">GPU (코어)</span>
				<span class="scope dot" data-level={gpuLevel} title={levelLabel(gpuLevel)} aria-label="상태 {levelLabel(gpuLevel)}"></span>
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
			<div class="status-line" data-level={gpuLevel}>{gpuStatus}</div>
			<div class="insight-row triple">
				<span>
					<b>평균</b>
					<span>{formatPercent(gpuAvg, 1)}</span>
				</span>
				<span>
					<b>피크</b>
					<span>{formatPercent(gpuPeak, 1)}</span>
				</span>
				<span data-tone={deltaTone(gpuDelta)} title="현재값 − {rangeLabel} 평균">
					<b>Δ 평균</b>
					<span>{formatDelta(gpuDelta)}</span>
				</span>
			</div>
		</div>
	{/if}

	{#if hasGpuMem}
		<div class="kpi" data-level={gpuMemLevel}>
			<div class="kpi-top">
				<span class="label">GPU (VRAM)</span>
				<span class="scope dot" data-level={gpuMemLevel} title={levelLabel(gpuMemLevel)} aria-label="상태 {levelLabel(gpuMemLevel)}"></span>
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
			<div class="status-line" data-level={gpuMemLevel}>{gpuMemStatus}</div>
			<div class="insight-row triple">
				<span>
					<b>평균</b>
					<span>{formatPercent(gpuMemAvg, 1)}</span>
				</span>
				<span>
					<b>피크</b>
					<span>{formatPercent(gpuMemPeak, 1)}</span>
				</span>
				<span data-tone={deltaTone(gpuMemDelta)} title="현재값 − {rangeLabel} 평균">
					<b>Δ 평균</b>
					<span>{formatDelta(gpuMemDelta)}</span>
				</span>
			</div>
		</div>
	{/if}
</section>

<style>
	/* 5-row 서브그리드 — 6 카드 모두 같은 row 트랙(kpi-top / metric-hero / meter /
	   status-line / insight)을 공유해 행 위치가 카드별로 같은 y에 정렬된다.
	   align-content: space-between 으로 카드 stretch 시 남는 세로 공간이 행 사이로 균등 분산. */
	.kpi-bar {
		--kpi-pad: clamp(5px, 0.4vw, 7px);
		--kpi-radius: 10px;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(clamp(136px, 8vw, 178px), 1fr));
		grid-template-rows: auto auto auto auto auto;
		column-gap: clamp(3px, 0.28vw, 5px);
		row-gap: 6px;
		margin-top: 0;
		align-content: space-between;
	}

	.kpi {
		min-width: 0;
		min-height: clamp(118px, 11vh, 140px);
		padding: var(--kpi-pad);
		background:
			linear-gradient(180deg, rgba(23, 30, 42, 0.98), rgba(13, 18, 27, 0.98)),
			var(--bg-card);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: var(--kpi-radius);
		display: grid;
		grid-template-rows: subgrid;
		grid-row: span 5;
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
	.flow-grid,
	.status-line {
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
	/* .scope.dot — severity 정보가 status-line 으로 옮겨간 뒤 우상단 chip 은
	   "지금 위치" 시각 cue 만 남긴 형태. dot 만 보이도록 padding/text 제거.
	   라벨은 title/aria-label 로만 접근. */
	.scope.dot {
		padding: 0;
		min-width: 14px;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		justify-content: center;
		font-size: 0;
	}
	.scope.dot::before {
		width: 8px;
		height: 8px;
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
		font-size: clamp(22px, 1.4vw, 28px);
		font-weight: 900;
		line-height: 1.0;
		letter-spacing: -0.02em;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		font-variant-numeric: tabular-nums;
	}
	.value.net {
		font-size: clamp(16px, 1.0vw, 20px);
	}
	/* severity 시 value 자체에도 색조 부여 — 한 카드 안 시각 정보 응집. */
	.kpi[data-level='warn'] .value { color: #fde68a; }
	.kpi[data-level='danger'] .value { color: #fca5a5; }
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
		height: 16px;
		border-radius: 999px;
		background: rgba(2, 6, 12, 0.62);
		border: 1px solid rgba(100, 116, 139, 0.2);
		overflow: visible;
		outline: none;
		box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.32);
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
		background: linear-gradient(90deg, rgba(48, 213, 200, 0.92), rgba(96, 165, 250, 0.88));
		box-shadow: 0 0 8px rgba(48, 213, 200, 0.45);
	}
	.meter.memory .meter-fill {
		background: linear-gradient(90deg, rgba(96, 165, 250, 0.94), rgba(129, 140, 248, 0.86));
		box-shadow: 0 0 8px rgba(96, 165, 250, 0.45);
	}
	.meter.gpu .meter-fill {
		background: linear-gradient(90deg, rgba(244, 114, 182, 0.92), rgba(168, 85, 247, 0.82));
		box-shadow: 0 0 8px rgba(244, 114, 182, 0.45);
	}
	.meter.gpu-mem .meter-fill {
		background: linear-gradient(90deg, rgba(167, 139, 250, 0.92), rgba(129, 140, 248, 0.82));
		box-shadow: 0 0 8px rgba(167, 139, 250, 0.45);
	}
	.meter-marker {
		position: absolute;
		top: -5px;
		width: 2.5px;
		height: 26px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.82);
		box-shadow: 0 0 0 1px rgba(2, 6, 12, 0.82), 0 0 4px rgba(255, 255, 255, 0.3);
	}
	.meter-marker.avg {
		left: var(--avg, 0%);
		opacity: 0.7;
	}
	.meter-marker.peak {
		left: var(--peak, 0%);
		background: rgba(251, 191, 36, 0.96);
		box-shadow: 0 0 0 1px rgba(2, 6, 12, 0.82), 0 0 8px rgba(251, 191, 36, 0.55);
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
		gap: 3px;
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
		padding: 5px 4px 4px;
		border-radius: 7px;
		background: rgba(2, 6, 12, 0.38);
		border: 1px solid rgba(100, 116, 139, 0.16);
		color: var(--text-primary);
		font-size: clamp(10px, 0.58vw, 11px);
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		line-height: 1.15;
		letter-spacing: -0.01em;
	}
	.insight-row b,
	.flow-grid b {
		display: block;
		margin-bottom: 3px;
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 900;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	/* Δ 평균 pill 색조 — 평균 대비 현재 위치를 운영자가 한눈에. */
	.insight-row > span[data-tone='up'] {
		border-color: rgba(251, 191, 36, 0.32);
		background: rgba(251, 191, 36, 0.07);
	}
	.insight-row > span[data-tone='up'] > span { color: #fde68a; }
	.insight-row > span[data-tone='up-warn'] {
		border-color: rgba(239, 68, 68, 0.38);
		background: rgba(239, 68, 68, 0.08);
	}
	.insight-row > span[data-tone='up-warn'] > span { color: #fca5a5; }
	.insight-row > span[data-tone='down'] {
		border-color: rgba(16, 185, 129, 0.3);
		background: rgba(16, 185, 129, 0.06);
	}
	.insight-row > span[data-tone='down'] > span { color: #6ee7b7; }
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

	/* status-line — meter 아래 한 줄 자연어 요약. severity 별 색조 + 좌측 dot.
	   sparkline 대신 "지금 어떤 위치에 있는가" 텍스트로 KPI 카드 공백 채움. */
	.status-line {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 4px 8px;
		border-radius: 6px;
		font-size: clamp(10px, 0.6vw, 11px);
		font-weight: 800;
		line-height: 1.15;
		letter-spacing: 0.005em;
		background: rgba(2, 6, 12, 0.34);
		border: 1px solid rgba(100, 116, 139, 0.14);
		color: var(--text-secondary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.status-line::before {
		content: '';
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: currentColor;
		box-shadow: 0 0 6px currentColor;
		opacity: 0.85;
		flex: 0 0 auto;
	}
	.status-line[data-level='normal'] {
		color: #6ee7b7;
		border-color: rgba(16, 185, 129, 0.28);
		background: rgba(16, 185, 129, 0.06);
	}
	.status-line[data-level='warn'] {
		color: #fde68a;
		border-color: rgba(251, 191, 36, 0.32);
		background: rgba(251, 191, 36, 0.07);
	}
	.status-line[data-level='danger'] {
		color: #fca5a5;
		border-color: rgba(239, 68, 68, 0.36);
		background: rgba(239, 68, 68, 0.08);
	}
	.status-line[data-flow='active'] {
		color: #93c5fd;
		border-color: rgba(96, 165, 250, 0.28);
		background: rgba(96, 165, 250, 0.06);
	}
	.status-line[data-flow='idle'] {
		color: rgba(148, 163, 184, 0.7);
	}
</style>
