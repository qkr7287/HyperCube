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
		workspace?: {
			path?: string | null;
			device?: string | null;
			projectId?: number | null;
			hardGb?: number;
			sizeGb?: number;
			usedGb?: number | null;
			availableGb?: number | null;
			usedPct?: number | null;
			rwLayerGb?: number | null;
			rootFsGb?: number | null;
			source?: 'du' | 'rw-layer' | 'xfs-quota' | null;
		} | null;
		gpu?:
			| {
					usage?: number | null;
					memoryUsed?: number | null;
					memoryTotal?: number | null;
			  }
			| Array<{ usage?: number | null; memoryUsed?: number | null; memoryTotal?: number | null }>
			| null;
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
		workspaceHelp = '',
		cpuPercentLimit = null,
		memoryMbLimit = null,
		workspaceGbLimit = null,
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
		workspaceHelp?: string;
		cpuPercentLimit?: number | null;
		memoryMbLimit?: number | null;
		workspaceGbLimit?: number | null;
	} = $props();

	// --- 현재 스냅샷 값 -------------------------------------------------
	let cpuNow = $derived(asNumber(currentMetrics?.cpu?.usage));
	let cpuCores = $derived(asNumber(currentMetrics?.cpu?.cores));
	let memNow = $derived(asNumber(currentMetrics?.memory?.percent));
	let memUsed = $derived(asNumber(currentMetrics?.memory?.usage));
	let memLimit = $derived(asNumber(currentMetrics?.memory?.limit));
	let workspace = $derived(currentMetrics?.workspace ?? null);
	let memoryQuotaBytes = $derived(memoryMbLimit ? memoryMbLimit * 1024 * 1024 : memLimit);
	let cpuQuotaCores = $derived(cpuPercentLimit ? cpuPercentLimit / 100 : null);
	let cpuRawDenominatorCores = $derived(cpuQuotaCores ?? cpuCores);
	// `hardGb` is the workspace-quota wire; `sizeGb` is the legacy LVM-era
	// wire — keep both so a partially-upgraded fleet still renders the meter.
	let workspaceSizeGb = $derived(
		asNumber(workspace?.hardGb) || asNumber(workspace?.sizeGb) || (workspaceGbLimit ?? 0),
	);
	// usedGb 는 측정 안 됐을 때 null/undefined 가 정상이라 number coerce 전에
	// raw 값을 살려둬야 "—" 분기가 가능하다 (asNumber 는 null → 0 으로 떨군다).
	let workspaceUsedGbRaw = $derived<number | null>(
		typeof workspace?.usedGb === 'number' && Number.isFinite(workspace.usedGb) ? workspace.usedGb : null,
	);
	let workspaceUsedGb = $derived(workspaceUsedGbRaw ?? 0);
	let workspaceMeasured = $derived(workspaceUsedGbRaw !== null);
	let workspaceSource = $derived<'du' | 'rw-layer' | 'xfs-quota' | null>(
		workspace?.source ?? null,
	);
	let workspaceSourceLabel = $derived(
		workspaceSource === 'rw-layer'
			? 'RW 레이어 기준'
			: workspaceSource === 'xfs-quota'
				? 'XFS quota 기준'
				: '',
	);
	let workspaceUsedPct = $derived(
		workspaceMeasured
			? (typeof workspace?.usedPct === 'number' && Number.isFinite(workspace.usedPct)
					? workspace.usedPct
					: workspaceSizeGb > 0 ? (workspaceUsedGb / workspaceSizeGb) * 100 : 0)
			: 0,
	);
	// 컨테이너 writable layer / rootfs 크기 — workspace quota 가 없는 일반
	// 서비스 컨테이너 (Redis 등) 도 디스크에 적재는 하므로, quota 사용량이
	// 없을 땐 이 값으로 디스크 카드를 채운다. (agent payload contract 의
	// workspace.rwLayerGb / rootFsGb)
	let rwLayerGbRaw = $derived<number | null>(
		typeof workspace?.rwLayerGb === 'number' && Number.isFinite(workspace.rwLayerGb)
			? workspace.rwLayerGb
			: null,
	);
	let rootFsGbRaw = $derived<number | null>(
		typeof workspace?.rootFsGb === 'number' && Number.isFinite(workspace.rootFsGb)
			? workspace.rootFsGb
			: null,
	);
	// 디스크 카드 소스 — agent 의 `source` 필드가 1차 기준.
	//   du / xfs-quota → /workspace quota 실측 (ML workspace 컨테이너)
	//   rw-layer       → 컨테이너 writable layer 크기 (Redis 등 일반 컨테이너)
	// source 가 없을 땐 quota 한도 유무로 fallback. usedGb=0 도 valid 측정값
	// 이라 measured 만으로 workspace 모드를 단정하지 않는다.
	let diskMode = $derived<'workspace' | 'layer' | 'pending'>(
		workspaceSource === 'du' || workspaceSource === 'xfs-quota' || workspaceSizeGb > 0
			? 'workspace'
			: workspaceSource === 'rw-layer' || rwLayerGbRaw !== null
				? 'layer'
				: workspaceMeasured
					? 'workspace'
					: 'pending',
	);
	// 디스크 카드는 모든 컨테이너에 항상 표시 (quota 없어도 적재량/대기 상태).
	let hasWorkspaceMetric = $derived(true);

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
	let cpuNowCores = $derived(cpuRawDenominatorCores > 0 ? (cpuNow * cpuRawDenominatorCores) / 100 : null);
	let cpuAvgCores = $derived(cpuRawDenominatorCores > 0 ? (cpuAvg * cpuRawDenominatorCores) / 100 : null);
	let cpuPeakCores = $derived(cpuRawDenominatorCores > 0 ? (cpuPeak * cpuRawDenominatorCores) / 100 : null);
	let memAvgBytes = $derived(memoryQuotaBytes > 0 ? (memAvgPct * memoryQuotaBytes) / 100 : null);
	let memPeakBytes = $derived(memoryQuotaBytes > 0 ? (memPeakPct * memoryQuotaBytes) / 100 : null);
	let vramAvgBytes = $derived(vramTotal > 0 ? (gpuMemAvg * vramTotal) / 100 : null);
	let vramPeakBytes = $derived(vramTotal > 0 ? (gpuMemPeak * vramTotal) / 100 : null);

	// --- severity / Δ ---------------------------------------------------
	let cpuLevel = $derived(severity(cpuNow, 70, 90));
	let memLevel = $derived(severity(memNow, 75, 90));
	let workspaceLevel = $derived(severity(workspaceUsedPct, 80, 90));
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
		if (v < 0.005) return '0 cores';
		return `${v.toFixed(2)} cores`;
	}
	function formatBytesShort(v: number | null): string {
		if (v === null) return '—';
		return compactBytes(v).replace(/\.0([BKMGTP])$/, '$1');
	}
	function formatCoreLimit(v: number): string {
		return Number.isInteger(v) ? `${v} cores` : `${v.toFixed(1)} cores`;
	}
	function formatGb(mb: number): string {
		const gb = mb / 1024;
		return Number.isInteger(gb) ? String(gb) : gb.toFixed(1);
	}
	function cpuLimitChip(): string {
		return cpuPercentLimit ? `limit ${formatCoreLimit(cpuPercentLimit / 100)}` : 'unlimited ⚠';
	}
	function memoryLimitChip(): string {
		return memoryMbLimit ? `limit ${formatGb(memoryMbLimit)} GB` : 'unlimited ⚠';
	}
	function workspaceLimitChip(): string {
		return workspaceGbLimit ? `limit ${workspaceGbLimit} GB` : 'unlimited ⚠';
	}
	function cpuRawText(): string {
		if (cpuQuotaCores) return `${formatCores(cpuNowCores)} / ${formatCoreLimit(cpuQuotaCores)}`;
		return formatCores(cpuNowCores);
	}
	function memoryRawText(): string {
		if (memoryQuotaBytes > 0) return `${formatBytesShort(memUsed)} / ${formatBytesShort(memoryQuotaBytes)}`;
		return formatBytesShort(memUsed);
	}
	function workspaceRawText(): string {
		// usedGb 가 측정 안 됐으면 0 으로 떨어트리지 말고 "—" 로 명시.
		const usedText = workspaceMeasured ? `${workspaceUsedGb.toFixed(1)} GB` : '—';
		if (workspaceSizeGb > 0) return `${usedText} / ${workspaceSizeGb} GB`;
		return usedText;
	}
	function workspaceUsedText() {
		return workspaceMeasured ? `${workspaceUsedGb.toFixed(1)} GB` : '—';
	}

	// --- 디스크 카드 (3-mode: workspace quota / 컨테이너 layer / 측정 대기) ---
	function diskCardPct(): number {
		if (diskMode === 'workspace') return workspaceUsedPct;
		// layer 모드: rootFs 대비 writable layer 비율 (rootFs 가 있으면), 없으면 0.
		if (diskMode === 'layer' && rootFsGbRaw && rootFsGbRaw > 0 && rwLayerGbRaw !== null) {
			return Math.min(100, (rwLayerGbRaw / rootFsGbRaw) * 100);
		}
		return 0;
	}
	function diskCardUsedText(): string {
		if (diskMode === 'workspace') return workspaceMeasured ? `${workspaceUsedGb.toFixed(1)} GB` : '—';
		if (diskMode === 'layer') return `${(rwLayerGbRaw ?? 0).toFixed(2)} GB`;
		return '—';
	}
	function diskCardRawText(): string {
		if (diskMode === 'workspace') return workspaceRawText();
		if (diskMode === 'layer') {
			const rw = `${(rwLayerGbRaw ?? 0).toFixed(2)} GB`;
			return rootFsGbRaw && rootFsGbRaw > 0 ? `${rw} / ${rootFsGbRaw.toFixed(2)} GB` : rw;
		}
		return '측정 대기';
	}
	function diskCardLimitText(): string {
		if (diskMode === 'workspace') return workspaceLimitChip();
		if (diskMode === 'layer') return 'no quota';
		return '';
	}
	function diskCardDenominator(): string {
		if (diskMode === 'workspace') return workspaceGbLimit ? `${workspaceGbLimit} GB quota` : 'unlimited';
		if (diskMode === 'layer') return 'container layer';
		return 'agent 보고 대기';
	}
	function diskCardHelp(): string {
		if (diskMode === 'workspace') return workspaceHelp;
		if (diskMode === 'layer') {
			return '컨테이너 writable layer 적재량입니다. workspace quota 가 없는 서비스 컨테이너(Redis 등)는 이미지 위에 쓴 데이터 크기(SizeRw)를 보여줍니다. 분모는 rootfs 전체 크기입니다.';
		}
		return '디스크 사용량을 agent 가 아직 보고하지 않았습니다. workspace quota 컨테이너는 du 기반 점유율, 일반 컨테이너는 writable layer 크기가 표시됩니다.';
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
	limitText?: string;
	denominatorText?: string;
})}
	<div class="kpi" data-level={opts.level}>
		<header class="kpi-head">
			<span class="kpi-label">
				{opts.label}
				{#if opts.help}<InfoTooltip text={opts.help} placement="bottom-start" />{/if}
			</span>
			<span class="chip-stack">
				<span class="kpi-chip" data-level={opts.level} title="상태 {levelLabel(opts.level)}">
					{levelLabel(opts.level)}
				</span>
				{#if opts.limitText}
					<span class="limit-chip" title={opts.denominatorText || opts.limitText}>{opts.limitText}</span>
				{/if}
			</span>
		</header>

		<div class="kpi-hero" aria-label="{opts.label} 현재 {formatPercent(opts.value, 2)} {opts.rawText}">
			<span class="hero-pct"><span class="num">{opts.value.toFixed(2)}</span><span class="unit">%</span></span>
			<span class="hero-sep" aria-hidden="true">·</span>
			<span class="hero-raw" title={opts.rawText}>{opts.rawText}</span>
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
					{#if opts.denominatorText}<span><em>분모</em><b>{opts.denominatorText}</b></span>{/if}
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
				<b><span class="ab">DIFF</span><span class="ko">대비</span></b>
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
				<b><span class="ab">DIFF</span><span class="ko">증가</span></b>
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
		rawText: cpuRawText(),
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
		limitText: cpuLimitChip(),
		denominatorText: cpuPercentLimit ? `${formatCoreLimit(cpuPercentLimit / 100)} quota` : 'host 전체',
	})}

	{@render pctCard({
		label: '메모리',
		help: memoryHelp,
		value: memNow,
		rawText: memoryRawText(),
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
		limitText: memoryLimitChip(),
		denominatorText: memoryMbLimit ? `${formatGb(memoryMbLimit)} GB quota` : 'host 전체',
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

	{@render pctCard({
		label: '디스크',
		help: diskCardHelp(),
		value: diskCardPct(),
		rawText: diskCardRawText(),
		avg: diskCardPct(),
		peak: diskCardPct(),
		avgRawText: diskCardUsedText(),
		peakRawText: diskCardUsedText(),
		warn: 80,
		crit: 90,
		level: diskMode === 'workspace' ? workspaceLevel : 'normal',
		delta: 0,
		meterClass: 'memory',
		tipKey: 'workspace',
		tipTitle: diskMode === 'layer' ? '컨테이너 디스크 적재량' : '디스크 사용량',
		limitText: diskCardLimitText(),
		denominatorText: diskCardDenominator(),
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
		grid-template-columns: repeat(auto-fit, minmax(clamp(140px, 7.5vw, 180px), 1fr));
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
		top: 8px;
		bottom: 8px;
		width: 3px;
		background: rgba(48, 213, 200, 0.7);
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
	.chip-stack {
		display: inline-flex;
		align-items: center;
		justify-content: flex-end;
		gap: 4px;
		min-width: 0;
	}
	.limit-chip {
		display: inline-flex;
		align-items: center;
		max-width: 92px;
		padding: 2.5px 7px;
		border-radius: 4px;
		background: rgba(48, 213, 200, 0.08);
		border: 1px solid rgba(48, 213, 200, 0.24);
		color: rgba(226, 232, 240, 0.9);
		font-size: 10px;
		font-weight: 800;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
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
		font-size: clamp(16px, 1.05vw, 21px);
		font-weight: 700;
		line-height: 1;
		letter-spacing: -0.02em;
	}
	.hero-pct {
		/* % 값은 KPI 의 헤드라인 — 절대 잘리지 않게 고정 폭 유지. */
		flex: 0 0 auto;
		white-space: nowrap;
	}
	.hero-raw {
		font-size: clamp(13px, 0.85vw, 17px);
		flex: 1 1 auto;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
