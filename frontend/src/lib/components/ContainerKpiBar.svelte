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

	let cpuTrend = $derived(history.map((r) => r.cpu_usage));
	let memTrend = $derived(history.map((r) => r.memory_percent));
	let netTrend = $derived(history.map((r) => (r.network_rx ?? 0) + (r.network_tx ?? 0)));
	let diskTrend = $derived(history.map((r) => (r.disk_read ?? 0) + (r.disk_write ?? 0)));
	let gpuTrend = $derived(history.map((r) => r.gpu_usage ?? 0));

	let cpuLevel = $derived(severity(currentMetrics?.cpu?.usage ?? 0, 70, 90));
	let memLevel = $derived(severity(currentMetrics?.memory?.percent ?? 0, 75, 90));
	let gpuLevel = $derived(severity(currentGpuUsage ?? 0, 80, 95));
</script>

<section class="kpi-bar" class:with-gpu={hasGpu} aria-label="컨테이너 메트릭 요약">
	<div class="kpi" data-level={cpuLevel}>
		<span class="label">
			CPU
			{#if cpuHelp}<InfoTooltip text={cpuHelp} placement="bottom-start" />{/if}
		</span>
		<div class="value-line">
			<strong class="value">{formatPercent(currentMetrics?.cpu?.usage, 2)}</strong>
			<span class="trend" title="{rangeLabel} 평균 {formatPercent(cpuAvg, 1)} · 피크 {formatPercent(cpuPeak, 1)}">
				avg {formatPercent(cpuAvg, 1)} · pk {formatPercent(cpuPeak, 1)}
			</span>
		</div>
		<div class="spark"><MetricSparkline values={cpuTrend} color="#30d5c8" label="CPU 추이" /></div>
	</div>

	<div class="kpi" data-level={memLevel}>
		<span class="label">
			메모리
			{#if memoryHelp}<InfoTooltip text={memoryHelp} placement="bottom-start" />{/if}
		</span>
		<div class="value-line">
			<strong class="value">{formatPercent(currentMetrics?.memory?.percent, 2)}</strong>
			<span class="trend" title="{formatMemoryUsage(currentMetrics?.memory?.usage, currentMetrics?.memory?.limit)} · {rangeLabel} 평균 {formatPercent(memAvgPct, 1)} · 피크 {formatPercent(memPeakPct, 1)}">
				{formatMemoryUsage(currentMetrics?.memory?.usage, currentMetrics?.memory?.limit)}
			</span>
		</div>
		<div class="spark"><MetricSparkline values={memTrend} color="#60a5fa" label="메모리 추이" /></div>
	</div>

	<div class="kpi">
		<span class="label">
			네트워크
			{#if networkHelp}<InfoTooltip text={networkHelp} placement="bottom-start" />{/if}
		</span>
		<div class="value-line">
			<strong class="value net">↓ {formatBytesValue(currentMetrics?.network?.rx)} · ↑ {formatBytesValue(currentMetrics?.network?.tx)}</strong>
		</div>
		<span class="trend" title="{rangeLabel} 증가 ↓ {formatBytesValue(netRxDelta)} · ↑ {formatBytesValue(netTxDelta)}">
			Δ ↓ {formatBytesValue(netRxDelta)} · ↑ {formatBytesValue(netTxDelta)}
		</span>
		<div class="spark"><MetricSparkline values={netTrend} color="#fbbf24" label="네트워크 추이" /></div>
	</div>

	<div class="kpi">
		<span class="label">
			디스크
			{#if diskHelp}<InfoTooltip text={diskHelp} placement="bottom-start" />{/if}
		</span>
		<div class="value-line">
			<strong class="value net">R {formatBytesValue(currentMetrics?.disk?.read)} · W {formatBytesValue(currentMetrics?.disk?.write)}</strong>
		</div>
		<span class="trend" title="{rangeLabel} 증가 R {formatBytesValue(diskReadDelta)} · W {formatBytesValue(diskWriteDelta)}">
			Δ R {formatBytesValue(diskReadDelta)} · W {formatBytesValue(diskWriteDelta)}
		</span>
		<div class="spark"><MetricSparkline values={diskTrend} color="#a78bfa" label="디스크 추이" /></div>
	</div>

	{#if hasGpu}
		<div class="kpi" data-level={gpuLevel}>
			<span class="label">GPU</span>
			<div class="value-line">
				<strong class="value">{currentGpuUsage !== null ? formatPercent(currentGpuUsage, 2) : '-'}</strong>
				<span class="trend" title="{rangeLabel} 평균 {formatPercent(gpuAvg, 1)} · 피크 {formatPercent(gpuPeak, 1)}">
					avg {formatPercent(gpuAvg, 1)} · pk {formatPercent(gpuPeak, 1)}
				</span>
			</div>
			<div class="spark"><MetricSparkline values={gpuTrend} color="#f472b6" label="GPU 추이" /></div>
		</div>
	{/if}
</section>

<style>
	.kpi-bar {
		/* 정보는 그대로, 여백만 한 번 더 압축. min-height / padding / gap 추가 축소. */
		--kpi-pad: clamp(5px, 0.4vw, 9px);
		--kpi-radius: clamp(6px, 0.4vw, 10px);
		--font-xs: clamp(9px, 0.55vw, 12px);
		--font-sm: clamp(10px, 0.65vw, 13px);
		--font-md: clamp(12px, 0.8vw, 15px);
		--font-lg: clamp(16px, 1.1vw, 22px);

		display: grid;
		/* CPU/메모리/네트워크/디스크 (+GPU) → 4~5개 KPI. 1920 한 줄 보장.
		   minmax 하한을 작게 둬서 좁아지면 자동 wrap. */
		grid-template-columns: repeat(auto-fit, minmax(clamp(160px, 11vw, 220px), 1fr));
		gap: clamp(3px, 0.3vw, 8px);
		margin-top: 0;
	}
	.kpi {
		min-width: 0;
		min-height: clamp(52px, 4.5vh, 78px);
		padding: var(--kpi-pad) calc(var(--kpi-pad) + 2px);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--kpi-radius);
		display: flex;
		flex-direction: column;
		gap: 1px;
		position: relative;
		overflow: hidden;
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
	/* warn: 노란 stripe + 살짝 노란 background */
	.kpi[data-level='warn'] {
		background: linear-gradient(90deg, rgba(251, 191, 36, 0.08), var(--bg-card) 60%);
		border-color: rgba(251, 191, 36, 0.32);
	}
	.kpi[data-level='warn']::before {
		background: #fbbf24;
		width: 4px;
	}
	.kpi[data-level='warn'] .value {
		color: #fbbf24;
	}
	/* danger: 빨간 stripe (두꺼움) + 빨간 background + value pulse */
	.kpi[data-level='danger'] {
		background: linear-gradient(90deg, rgba(239, 68, 68, 0.14), var(--bg-card) 60%);
		border-color: rgba(239, 68, 68, 0.4);
		box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.15);
	}
	.kpi[data-level='danger']::before {
		background: #f87171;
		width: 5px;
		box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
	}
	.kpi[data-level='danger'] .value {
		color: #f87171;
		animation: danger-pulse 1.6s ease-in-out infinite;
	}
	@keyframes danger-pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.65; }
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
		height: clamp(14px, 1.5vh, 26px);
		overflow: hidden;
	}

	/* value-line: value (큰 글씨) 와 trend (작은 인라인 텍스트) 가 같은 row.
	   평균/피크 정보를 별도 줄로 두지 않고 value 옆 baseline 정렬해 정보 손실 X +
	   세로 공간 절약. trend hover tooltip 에 정식 텍스트 fallback. */
	.value-line {
		display: flex;
		align-items: baseline;
		gap: clamp(4px, 0.4vw, 8px);
		flex-wrap: wrap;
		min-width: 0;
	}
	.trend {
		color: var(--text-muted);
		font-size: clamp(9px, 0.55vw, 11px);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		cursor: help;
	}
	/* sub 는 deprecated — 혹시 남아있는 markup safe-guard */
	.sub {
		display: none;
	}
	.spark :global(svg) {
		width: 100%;
		height: 100%;
		max-width: none;
	}
</style>
