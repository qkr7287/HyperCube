<!--
  ContainerKpiBar — 컨테이너 KPI bar.

  카드 안 4 element 통일:
    1. head    : label + severity chip
    2. hero    : 현재 raw + % 동급 ("2.40 % · 384 MB")
    3. range   : 0~100% 가로 막대 + 평균/현재/피크 marker (% 카드)
                 또는 RX/TX share split bar (bytes 카드)
    4. foot    : 평균/피크 raw+% 2 행 + Δ (% 카드) / RX·TX·Δ 한 줄 (bytes 카드)

  추이는 별도 UserMetricChart 가 처리. glow/drop-shadow 0, mono 단일 시스템.
  카드 외곽 크기 ~213px 유지 (Hero 영역과 같은 row stretch).
-->
<script lang="ts">
	import InfoTooltip from './InfoTooltip.svelte';
	import { formatBytesValue, formatPercent } from '$lib/utils/container-dashboard';
	import {
		asNumber,
		clampPercent,
		compactBytes,
		deltaTone,
		formatDelta,
		levelLabel,
		severity,
		shareOf,
		splitBytesLabel,
	} from '$lib/utils/container-kpi';

	type MetricsSnapshot = {
		cpu?: { usage?: number; cores?: number };
		memory?: { usage?: number; limit?: number; percent?: number };
		network?: { rx?: number; tx?: number };
		disk?: { read?: number; write?: number };
		gpu?:
			| {
					usage?: number;
					memoryUsed?: number;
					memoryTotal?: number;
			  }
			| Array<{ usage?: number; memoryUsed?: number; memoryTotal?: number }>;
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

	// --- 현재 스냅샷 값 -------------------------------------------------
	let cpuNow = $derived(asNumber(currentMetrics?.cpu?.usage));
	let cpuCores = $derived(asNumber(currentMetrics?.cpu?.cores));
	let memNow = $derived(asNumber(currentMetrics?.memory?.percent));
	let memUsed = $derived(asNumber(currentMetrics?.memory?.usage));
	let memLimit = $derived(asNumber(currentMetrics?.memory?.limit));

	let gpuFirst = $derived(
		Array.isArray(currentMetrics?.gpu)
			? currentMetrics?.gpu?.[0] ?? null
			: currentMetrics?.gpu ?? null,
	);
	let vramUsed = $derived(asNumber(gpuFirst?.memoryUsed));
	let vramTotal = $derived(asNumber(gpuFirst?.memoryTotal));

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

	// --- raw 환산 (평균/피크) --------------------------------------------
	// limit / cores / memoryTotal 이 0 일 때는 raw 환산이 무의미 → null 표시
	let cpuAvgCores = $derived(cpuCores > 0 ? (cpuAvg * cpuCores) / 100 : null);
	let cpuPeakCores = $derived(cpuCores > 0 ? (cpuPeak * cpuCores) / 100 : null);
	let memAvgBytes = $derived(memLimit > 0 ? (memAvgPct * memLimit) / 100 : null);
	let memPeakBytes = $derived(memLimit > 0 ? (memPeakPct * memLimit) / 100 : null);
	let vramAvgBytes = $derived(vramTotal > 0 ? (gpuMemAvg * vramTotal) / 100 : null);
	let vramPeakBytes = $derived(vramTotal > 0 ? (gpuMemPeak * vramTotal) / 100 : null);

	// --- severity / Δ ---------------------------------------------------
	let cpuLevel = $derived(severity(cpuNow, 70, 90));
	let memLevel = $derived(severity(memNow, 75, 90));
	let gpuLevel = $derived(severity(currentGpuUsage ?? 0, 80, 95));
	let gpuMemLevel = $derived(severity(currentGpuMemPct ?? 0, 80, 95));

	let cpuDelta = $derived(cpuNow - cpuAvg);
	let memDelta = $derived(memNow - memAvgPct);
	let gpuDelta = $derived((currentGpuUsage ?? 0) - gpuAvg);
	let gpuMemDelta = $derived((currentGpuMemPct ?? 0) - gpuMemAvg);

	// --- bytes 카드용 hero raw split ------------------------------------
	let netValueParts = $derived(splitBytesLabel(formatBytesValue(netTotal)));
	let diskValueParts = $derived(splitBytesLabel(formatBytesValue(diskTotal)));

	// --- helpers --------------------------------------------------------
	function formatCores(v: number | null): string {
		if (v === null) return '—';
		if (v < 0.1) return '0 cores';
		return `${v.toFixed(2)} cores`;
	}
	function formatBytesShort(v: number | null): string {
		if (v === null) return '—';
		return compactBytes(v);
	}

	// hover/focus 시 띄울 bar-tooltip key (예전 meter 의 detail tooltip 복원)
	let activeBarTooltip = $state<string | null>(null);
	function showTip(k: string) {
		activeBarTooltip = k;
	}
	function hideTip(k: string) {
		if (activeBarTooltip === k) activeBarTooltip = null;
	}
</script>

<!-- ===== pctCard ===== % 메트릭 카드 (CPU / 메모리 / GPU 코어 / GPU VRAM) -->
{#snippet pctCard(opts: {
	label: string;
	help?: string;
	value: number;
	rawText: string;
	avg: number;
	peak: number;
	avgRawText: string;
	peakRawText: string;
	warn: number;
	crit: number;
	level: 'normal' | 'warn' | 'danger';
	delta: number;
	deltaRaw?: string;
	meterClass?: 'memory' | 'gpu' | 'gpu-mem';
	tipKey: string;
	tipTitle: string;
})}
	<div class="kpi" data-level={opts.level}>
		<header class="kpi-head">
			<span class="kpi-label">
				{opts.label}
				{#if opts.help}<InfoTooltip text={opts.help} placement="bottom-start" />{/if}
			</span>
			<span class="kpi-chip" data-level={opts.level} title="상태 {levelLabel(opts.level)}">
				{levelLabel(opts.level)}
			</span>
		</header>

		<div class="kpi-hero" aria-label="{opts.label} 현재 {formatPercent(opts.value, 2)} {opts.rawText}">
			<span class="hero-pct"><span class="num">{opts.value.toFixed(2)}</span><span class="unit">%</span></span>
			<span class="hero-sep" aria-hidden="true">·</span>
			<span class="hero-raw">{opts.rawText}</span>
		</div>

		<div
			class="meter {opts.meterClass ?? ''}"
			tabindex="0"
			aria-label="{opts.label} 현재 {formatPercent(opts.value, 2)} ({opts.rawText}), 평균 {formatPercent(opts.avg, 1)} ({opts.avgRawText}), 피크 {formatPercent(opts.peak, 1)} ({opts.peakRawText})"
			onmouseenter={() => showTip(opts.tipKey)}
			onfocus={() => showTip(opts.tipKey)}
			onmouseleave={() => hideTip(opts.tipKey)}
			onblur={() => hideTip(opts.tipKey)}
			style={`--value:${clampPercent(opts.value)}%;--avg:${clampPercent(opts.avg)}%;--peak:${clampPercent(opts.peak)}%;`}
		>
			<span class="meter-fill"></span>
			{#if opts.avg > 0.01}
				<span class="meter-marker avg" title="평균 {formatPercent(opts.avg, 1)}"></span>
			{/if}
			{#if opts.peak > 0.01}
				<span class="meter-marker peak" title="피크 {formatPercent(opts.peak, 1)}"></span>
			{/if}
			{#if activeBarTooltip === opts.tipKey}
				<span class="bar-tooltip" role="tooltip">
					<strong>{opts.tipTitle}</strong>
					<span><em>현재</em><b>{formatPercent(opts.value, 2)} · {opts.rawText}</b></span>
					<span><em>{rangeLabel} 평균</em><b>{formatPercent(opts.avg, 1)} · {opts.avgRawText}</b></span>
					<span><em>{rangeLabel} 피크</em><b>{formatPercent(opts.peak, 1)} · {opts.peakRawText}</b></span>
				</span>
			{/if}
		</div>

		<footer class="kpi-foot">
			<div class="foot-row">
				<i class="dot dot-avg" aria-hidden="true"></i>
				<b><span class="ab">AVG</span><span class="ko">평균</span></b>
				<em class="pct">{formatPercent(opts.avg, 1)}</em>
				<span class="raw">{opts.avgRawText}</span>
			</div>
			<div class="foot-row">
				<i class="dot dot-peak" aria-hidden="true"></i>
				<b><span class="ab">PEAK</span><span class="ko">피크</span></b>
				<em class="pct">{formatPercent(opts.peak, 1)}</em>
				<span class="raw">{opts.peakRawText}</span>
			</div>
			<div class="foot-row delta" data-tone={deltaTone(opts.delta)} title="현재값 − {rangeLabel} 평균">
				<i class="dot dot-delta" aria-hidden="true"></i>
				<b><span class="ab">DIFF</span><span class="ko">평소 대비</span></b>
				<em>{formatDelta(opts.delta)}</em>
				{#if opts.deltaRaw}<span class="raw">{opts.deltaRaw}</span>{:else}<span class="raw"></span>{/if}
			</div>
		</footer>
	</div>
{/snippet}

<!-- ===== flowCard ===== bytes 메트릭 카드 (네트워크 / 디스크) -->
{#snippet flowCard(opts: {
	label: string;
	help?: string;
	totalParts: { num: string; unit: string };
	totalRaw: number;
	aShare: number;
	bShare: number;
	aLabel: string;
	bLabel: string;
	aLabelKo: string;
	bLabelKo: string;
	aBytes: number;
	bBytes: number;
	deltaTotal: number;
	colorA: 'teal' | 'violet';
	colorB: 'amber' | 'blue';
	tipKey: string;
	tipTitle: string;
	splitClass?: 'disk';
})}
	<div class="kpi flow" data-color-a={opts.colorA} data-color-b={opts.colorB}>
		<header class="kpi-head">
			<span class="kpi-label">
				{opts.label}
				{#if opts.help}<InfoTooltip text={opts.help} placement="bottom-start" />{/if}
			</span>
			<span class="kpi-chip" data-level="flow">누적</span>
		</header>

		<div class="kpi-hero" aria-label="{opts.label} 누적 {formatBytesValue(opts.totalRaw)}">
			<span class="hero-raw hero-bytes">
				<span class="num">{opts.totalParts.num}</span><span class="unit">{opts.totalParts.unit}</span>
			</span>
		</div>

		<div
			class="split-meter {opts.splitClass ?? ''}"
			tabindex="0"
			aria-label="{opts.label} 누적 {formatBytesValue(opts.totalRaw)}, {opts.aLabel} {formatBytesValue(opts.aBytes)}, {opts.bLabel} {formatBytesValue(opts.bBytes)}, {rangeLabel} 증가 {formatBytesValue(opts.deltaTotal)}"
			onmouseenter={() => showTip(opts.tipKey)}
			onfocus={() => showTip(opts.tipKey)}
			onmouseleave={() => hideTip(opts.tipKey)}
			onblur={() => hideTip(opts.tipKey)}
			style={`--a:${opts.aShare}%;--b:${opts.bShare}%;`}
		>
			<span class="split-a"></span>
			<span class="split-b"></span>
			{#if activeBarTooltip === opts.tipKey}
				<span class="bar-tooltip" role="tooltip">
					<strong>{opts.tipTitle}</strong>
					<span><em>전체</em><b>{formatBytesValue(opts.totalRaw)}</b></span>
					<span><em>{opts.aLabel}</em><b>{formatBytesValue(opts.aBytes)}</b></span>
					<span><em>{opts.bLabel}</em><b>{formatBytesValue(opts.bBytes)}</b></span>
					<span><em>{rangeLabel} 증가</em><b>{formatBytesValue(opts.deltaTotal)}</b></span>
				</span>
			{/if}
		</div>

		<footer class="kpi-foot">
			<div class="foot-row">
				<i class="dot dot-flow-a" aria-hidden="true"></i>
				<b><span class="ab">{opts.aLabel}</span><span class="ko">{opts.aLabelKo}</span></b>
				<em class="pct">{compactBytes(opts.aBytes)}</em>
			</div>
			<div class="foot-row">
				<i class="dot dot-flow-b" aria-hidden="true"></i>
				<b><span class="ab">{opts.bLabel}</span><span class="ko">{opts.bLabelKo}</span></b>
				<em class="pct">{compactBytes(opts.bBytes)}</em>
			</div>
			<div class="foot-row delta" data-tone={opts.deltaTotal > 0 ? 'up' : 'flat'} title="{rangeLabel} 증가">
				<i class="dot dot-delta" aria-hidden="true"></i>
				<b><span class="ab">DIFF</span><span class="ko">{rangeLabel} 증가</span></b>
				<em>{opts.deltaTotal > 0 ? `+${compactBytes(opts.deltaTotal)}` : '—'}</em>
				<span class="raw"></span>
			</div>
		</footer>
	</div>
{/snippet}

<section class="kpi-bar" class:with-gpu={hasGpu || hasGpuMem} aria-label="컨테이너 메트릭 요약">
	{@render pctCard({
		label: 'CPU',
		help: cpuHelp,
		value: cpuNow,
		rawText: formatCores(cpuCores > 0 ? (cpuNow * cpuCores) / 100 : null),
		avg: cpuAvg,
		peak: cpuPeak,
		avgRawText: formatCores(cpuAvgCores),
		peakRawText: formatCores(cpuPeakCores),
		warn: 70,
		crit: 90,
		level: cpuLevel,
		delta: cpuDelta,
		tipKey: 'cpu',
		tipTitle: 'CPU 사용률',
	})}

	{@render pctCard({
		label: '메모리',
		help: memoryHelp,
		value: memNow,
		rawText: formatBytesShort(memUsed),
		avg: memAvgPct,
		peak: memPeakPct,
		avgRawText: formatBytesShort(memAvgBytes),
		peakRawText: formatBytesShort(memPeakBytes),
		warn: 75,
		crit: 90,
		level: memLevel,
		delta: memDelta,
		meterClass: 'memory',
		tipKey: 'memory',
		tipTitle: '메모리 사용량',
	})}

	{@render flowCard({
		label: '네트워크',
		help: networkHelp,
		totalParts: netValueParts,
		totalRaw: netTotal,
		aShare: netRxShare,
		bShare: netTxShare,
		aLabel: 'RX',
		bLabel: 'TX',
		aLabelKo: '수신',
		bLabelKo: '송신',
		aBytes: netRx,
		bBytes: netTx,
		deltaTotal: netDeltaTotal,
		colorA: 'teal',
		colorB: 'amber',
		tipKey: 'network',
		tipTitle: '네트워크 누적',
	})}

	{@render flowCard({
		label: '디스크',
		help: diskHelp,
		totalParts: diskValueParts,
		totalRaw: diskTotal,
		aShare: diskReadShare,
		bShare: diskWriteShare,
		aLabel: 'READ',
		bLabel: 'WRITE',
		aLabelKo: '읽기',
		bLabelKo: '쓰기',
		aBytes: diskRead,
		bBytes: diskWrite,
		deltaTotal: diskDeltaTotal,
		colorA: 'violet',
		colorB: 'blue',
		tipKey: 'disk',
		tipTitle: '디스크 누적',
		splitClass: 'disk',
	})}

	{#if hasGpu}
		{@render pctCard({
			label: 'GPU 코어',
			value: currentGpuUsage ?? 0,
			rawText: '—',
			avg: gpuAvg,
			peak: gpuPeak,
			avgRawText: '—',
			peakRawText: '—',
			warn: 80,
			crit: 95,
			level: gpuLevel,
			delta: gpuDelta,
			meterClass: 'gpu',
			tipKey: 'gpu',
			tipTitle: 'GPU 코어 사용률',
		})}
	{/if}

	{#if hasGpuMem}
		{@render pctCard({
			label: 'GPU VRAM',
			value: currentGpuMemPct ?? 0,
			rawText: formatBytesShort(vramUsed),
			avg: gpuMemAvg,
			peak: gpuMemPeak,
			avgRawText: formatBytesShort(vramAvgBytes),
			peakRawText: formatBytesShort(vramPeakBytes),
			warn: 80,
			crit: 95,
			level: gpuMemLevel,
			delta: gpuMemDelta,
			meterClass: 'gpu-mem',
			tipKey: 'gpuMem',
			tipTitle: 'GPU 메모리 (VRAM)',
		})}
	{/if}
</section>

<style>
	/* ========================================================================
	   Layout
	   ======================================================================== */
	.kpi-bar {
		--pad: clamp(8px, 0.55vw, 11px);
		--radius: 12px;
		--text-strong: #e6ebf2;
		--text-mid: rgba(203, 213, 225, 0.78);
		--text-faint: rgba(148, 163, 184, 0.6);
		--bg-card: linear-gradient(180deg, rgba(20, 26, 36, 0.96), rgba(12, 16, 23, 0.96));
		--border-soft: rgba(100, 116, 139, 0.18);
		--font-mono: ui-monospace, SFMono-Regular, Consolas, monospace;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(clamp(160px, 9vw, 200px), 1fr));
		grid-template-rows: auto auto auto auto;
		column-gap: clamp(4px, 0.3vw, 6px);
		row-gap: 8px;
		align-content: stretch;
	}

	.kpi {
		min-width: 0;
		min-height: clamp(180px, 16vh, 210px);
		padding: var(--pad);
		background: var(--bg-card);
		border: 1px solid var(--border-soft);
		border-radius: var(--radius);
		display: grid;
		grid-template-rows: subgrid;
		grid-row: span 4;
		row-gap: 6px;
		position: relative;
		overflow: hidden;
		transition: border-color 0.16s ease;
	}
	.kpi:hover {
		border-color: rgba(48, 213, 200, 0.32);
	}
	.kpi::before {
		content: '';
		position: absolute;
		left: 0;
		top: 10px;
		bottom: 10px;
		width: 2.5px;
		border-radius: 0 3px 3px 0;
		background: rgba(48, 213, 200, 0.55);
	}
	.kpi[data-level='warn']::before { background: #fbbf24; }
	.kpi[data-level='danger']::before { background: #f87171; }
	.kpi[data-level='warn'] { border-color: rgba(251, 191, 36, 0.32); }
	.kpi[data-level='danger'] { border-color: rgba(239, 68, 68, 0.38); }

	/* ========================================================================
	   1. head
	   ======================================================================== */
	.kpi-head {
		min-width: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
	}
	.kpi-label {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: var(--text-mid);
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.015em;
		white-space: nowrap;
	}
	.kpi-chip {
		display: inline-flex;
		align-items: center;
		padding: 2.5px 9px;
		/* 박스형 chip — meter 트랙과 시각 통일 */
		border-radius: 4px;
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.04em;
		color: var(--text-faint);
		background: rgba(2, 6, 12, 0.42);
		border: 1px solid var(--border-soft);
		white-space: nowrap;
	}
	.kpi-chip[data-level='normal'] {
		color: #6ee7b7;
		background: rgba(16, 185, 129, 0.06);
		border-color: rgba(16, 185, 129, 0.28);
	}
	.kpi-chip[data-level='warn'] {
		color: #fde68a;
		background: rgba(251, 191, 36, 0.07);
		border-color: rgba(251, 191, 36, 0.32);
	}
	.kpi-chip[data-level='danger'] {
		color: #fca5a5;
		background: rgba(239, 68, 68, 0.08);
		border-color: rgba(239, 68, 68, 0.36);
	}

	/* ========================================================================
	   2. hero — raw + % 동급
	   ======================================================================== */
	.kpi-hero {
		min-width: 0;
		display: flex;
		align-items: baseline;
		gap: 6px;
		color: var(--text-strong);
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
	}
	.hero-pct,
	.hero-raw {
		display: inline-flex;
		align-items: baseline;
		min-width: 0;
		font-size: clamp(16px, 1.05vw, 21px);
		font-weight: 700;
		line-height: 1;
		letter-spacing: -0.02em;
	}
	.hero-pct .num,
	.hero-raw .num {
		color: var(--text-strong);
	}
	.hero-pct .unit,
	.hero-raw .unit {
		font-size: 0.58em;
		font-weight: 700;
		color: var(--text-faint);
		letter-spacing: 0.02em;
		margin-left: 2px;
	}
	.hero-sep {
		color: var(--text-faint);
		font-size: 13px;
		font-weight: 400;
		font-family: system-ui, -apple-system, sans-serif;
		flex: 0 0 auto;
		transform: translateY(-1px);
		opacity: 0.55;
	}
	.hero-bytes {
		font-size: clamp(20px, 1.3vw, 26px);
	}
	.kpi[data-level='warn'] .hero-pct .num,
	.kpi[data-level='warn'] .hero-raw .num { color: #fde68a; }
	.kpi[data-level='danger'] .hero-pct .num,
	.kpi[data-level='danger'] .hero-raw .num { color: #fca5a5; }

	/* ========================================================================
	   3. meter / split-meter — 예전 풀-퀄리티 시각 그대로 복원
	      트랙(어두운 bed + inset shadow) + 카드별 grad fill + avg/peak vertical
	      marker + warn/crit 영역 ::before grad + hover bar-tooltip.
	   ======================================================================== */
	.meter,
	.split-meter {
		position: relative;
		height: 16px;
		/* 박스 형태 — sharp 한 사각 트랙 (dashboard 톤). 둥근 모서리 없음. */
		border-radius: 0;
		background: rgba(2, 6, 12, 0.62);
		border: 1px solid rgba(100, 116, 139, 0.24);
		overflow: visible;
		outline: none;
		box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.32);
	}
	.meter::before {
		content: '';
		position: absolute;
		inset: 0;
		border-radius: inherit;
		background: linear-gradient(
			90deg,
			transparent 69%,
			rgba(251, 191, 36, 0.24) 70%,
			rgba(251, 191, 36, 0.24) 89%,
			rgba(239, 68, 68, 0.22) 90%
		);
		pointer-events: none;
	}
	.meter-fill {
		position: absolute;
		inset: 0 auto 0 0;
		width: var(--value, 0%);
		border-radius: inherit;
		background: linear-gradient(90deg, rgba(48, 213, 200, 0.9), rgba(96, 165, 250, 0.85));
		box-shadow: 0 0 5px rgba(48, 213, 200, 0.28);
	}
	.meter.memory .meter-fill {
		background: linear-gradient(90deg, rgba(96, 165, 250, 0.9), rgba(129, 140, 248, 0.82));
		box-shadow: 0 0 5px rgba(96, 165, 250, 0.28);
	}
	.meter.gpu .meter-fill {
		background: linear-gradient(90deg, rgba(244, 114, 182, 0.9), rgba(168, 85, 247, 0.8));
		box-shadow: 0 0 5px rgba(244, 114, 182, 0.28);
	}
	.meter.gpu-mem .meter-fill {
		background: linear-gradient(90deg, rgba(167, 139, 250, 0.9), rgba(129, 140, 248, 0.8));
		box-shadow: 0 0 5px rgba(167, 139, 250, 0.28);
	}
	.meter-marker {
		position: absolute;
		top: -5px;
		width: 2.5px;
		height: 26px;
		/* sharp 사각 marker — 박스형 트랙과 시각 통일 */
		border-radius: 0;
		background: rgba(255, 255, 255, 0.78);
		box-shadow:
			0 0 0 1px rgba(2, 6, 12, 0.78),
			0 0 2px rgba(255, 255, 255, 0.18);
	}
	.meter-marker.avg {
		left: var(--avg, 0%);
		opacity: 0.65;
	}
	.meter-marker.peak {
		left: var(--peak, 0%);
		background: rgba(251, 191, 36, 0.9);
		box-shadow:
			0 0 0 1px rgba(2, 6, 12, 0.78),
			0 0 4px rgba(251, 191, 36, 0.3);
	}
	/* peak marker 위 ▼ caret — 피크 위치 sharp 한 시각 cue. glow 줄임 */
	.meter-marker.peak::before {
		content: '';
		position: absolute;
		top: -6px;
		left: 50%;
		transform: translateX(-50%);
		width: 0;
		height: 0;
		border-left: 4px solid transparent;
		border-right: 4px solid transparent;
		border-top: 5px solid rgba(251, 191, 36, 0.9);
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
		border-radius: 0;
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

	/* hover/focus 시 띄울 detail tooltip — 카드 아래쪽에 floating, accent border. */
	.bar-tooltip {
		position: absolute;
		left: 0;
		top: calc(100% + 7px);
		z-index: 30;
		min-width: min(218px, calc(100vw - 28px));
		max-width: 240px;
		padding: 8px 9px;
		border-radius: 8px;
		background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(2, 6, 12, 0.98));
		border: 1px solid rgba(48, 213, 200, 0.28);
		box-shadow: 0 14px 30px rgba(0, 0, 0, 0.36);
		color: var(--text-strong);
		pointer-events: none;
		animation: bar-tooltip-in 0.12s ease-out;
	}
	@keyframes bar-tooltip-in {
		from {
			transform: translateY(-4px);
			opacity: 0;
		}
		to {
			transform: translateY(0);
			opacity: 1;
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
		color: rgba(48, 213, 200, 0.92);
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
		color: var(--text-faint);
		font-style: normal;
		font-weight: 700;
		white-space: nowrap;
	}
	.bar-tooltip b {
		color: var(--text-strong);
		font-weight: 900;
		font-variant-numeric: tabular-nums;
		text-align: right;
		overflow-wrap: anywhere;
	}

	/* ========================================================================
	   4. foot — 평균/피크 raw+% 2 행 + Δ
	   ======================================================================== */
	.kpi-foot {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 5px;
		font-family: var(--font-mono);
		font-variant-numeric: tabular-nums;
	}
	.foot-row {
		display: grid;
		/* 카드 안 row 정렬 일관성 — dot 9px / label 64px 고정 / pct 가변 / raw 우측.
		   label 너비 고정으로 모든 row 의 pct 시작점이 동일해진다. */
		grid-template-columns: 9px 64px minmax(0, 1fr) minmax(0, auto);
		align-items: center;
		gap: 7px;
		min-width: 0;
		font-size: clamp(11.5px, 0.7vw, 13px);
		font-weight: 600;
		color: var(--text-mid);
		white-space: nowrap;
	}
	/* 라벨 — 영문 약자(.ab) + 한글 부연(.ko). 약자는 mono uppercase, 한글은
	   system-ui muted 작은 글씨. 두 톤을 줄 맞춰 보여줌. */
	.foot-row b {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
		min-width: 0;
	}
	.foot-row b .ab {
		font-family: var(--font-mono);
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.05em;
		color: var(--text-mid);
		text-transform: uppercase;
	}
	.foot-row b .ko {
		font-family: system-ui, -apple-system, 'Segoe UI', 'Malgun Gothic', sans-serif;
		font-size: 9.5px;
		font-weight: 500;
		color: var(--text-faint);
		letter-spacing: 0;
		white-space: nowrap;
	}
	.foot-row .pct {
		font-style: normal;
		color: var(--text-strong);
		font-weight: 700;
		font-size: 1.02em;
		letter-spacing: -0.01em;
		text-align: left;
	}
	.foot-row .raw {
		color: var(--text-mid);
		font-weight: 600;
		font-size: 0.95em;
		text-align: right;
		overflow: hidden;
		text-overflow: ellipsis;
		min-width: 0;
	}
	.foot-row .dot {
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}
	.dot-avg { background: rgba(226, 232, 240, 0.85); }
	.dot-peak { background: rgba(251, 191, 36, 0.9); }
	.dot-flow-a { background: rgba(48, 213, 200, 0.9); }
	.dot-flow-b { background: rgba(251, 191, 36, 0.9); }
	.flow[data-color-a='violet'] .dot-flow-a { background: rgba(167, 139, 250, 0.95); }
	.flow[data-color-b='blue'] .dot-flow-b { background: rgba(96, 165, 250, 0.95); }

	/* Δ row — tone 색조 */
	.foot-row.delta em {
		font-size: 1.02em;
	}
	/* Δ row 의 dot — tone 별 색조 (flat=muted, up=amber, up-warn=red, down=green) */
	.dot-delta { background: rgba(148, 163, 184, 0.45); }
	.foot-row.delta[data-tone='up'] .dot-delta { background: rgba(251, 191, 36, 0.85); }
	.foot-row.delta[data-tone='up-warn'] .dot-delta { background: rgba(248, 113, 113, 0.9); }
	.foot-row.delta[data-tone='down'] .dot-delta { background: rgba(110, 231, 183, 0.85); }
	.foot-row.delta b { color: var(--text-faint); }
	.foot-row.delta em {
		font-style: normal;
		color: var(--text-strong);
		font-weight: 700;
	}
	.foot-row.delta[data-tone='up'] em { color: #fde68a; }
	.foot-row.delta[data-tone='up-warn'] em { color: #fca5a5; }
	.foot-row.delta[data-tone='down'] em { color: #6ee7b7; }
</style>
