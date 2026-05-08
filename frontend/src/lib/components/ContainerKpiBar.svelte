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
		<strong class="value">{formatPercent(currentMetrics?.cpu?.usage, 2)}</strong>
		<span class="sub">{rangeLabel} 평균 {formatPercent(cpuAvg, 1)} · 피크 {formatPercent(cpuPeak, 1)}</span>
		<div class="spark"><MetricSparkline values={cpuTrend} color="#30d5c8" label="CPU 추이" /></div>
	</div>

	<div class="kpi" data-level={memLevel}>
		<span class="label">
			메모리
			{#if memoryHelp}<InfoTooltip text={memoryHelp} placement="bottom-start" />{/if}
		</span>
		<strong class="value">{formatPercent(currentMetrics?.memory?.percent, 2)}</strong>
		<span class="sub">{formatMemoryUsage(currentMetrics?.memory?.usage, currentMetrics?.memory?.limit)} · 평균 {formatPercent(memAvgPct, 1)} · 피크 {formatPercent(memPeakPct, 1)}</span>
		<div class="spark"><MetricSparkline values={memTrend} color="#60a5fa" label="메모리 추이" /></div>
	</div>

	<div class="kpi">
		<span class="label">
			네트워크
			{#if networkHelp}<InfoTooltip text={networkHelp} placement="bottom-start" />{/if}
		</span>
		<strong class="value net">↓ {formatBytesValue(currentMetrics?.network?.rx)} · ↑ {formatBytesValue(currentMetrics?.network?.tx)}</strong>
		<span class="sub">{rangeLabel} 증가 ↓ {formatBytesValue(netRxDelta)} · ↑ {formatBytesValue(netTxDelta)}</span>
		<div class="spark"><MetricSparkline values={netTrend} color="#fbbf24" label="네트워크 추이" /></div>
	</div>

	<div class="kpi">
		<span class="label">
			디스크
			{#if diskHelp}<InfoTooltip text={diskHelp} placement="bottom-start" />{/if}
		</span>
		<strong class="value net">R {formatBytesValue(currentMetrics?.disk?.read)} · W {formatBytesValue(currentMetrics?.disk?.write)}</strong>
		<span class="sub">{rangeLabel} 증가 R {formatBytesValue(diskReadDelta)} · W {formatBytesValue(diskWriteDelta)}</span>
		<div class="spark"><MetricSparkline values={diskTrend} color="#a78bfa" label="디스크 추이" /></div>
	</div>

	{#if hasGpu}
		<div class="kpi" data-level={gpuLevel}>
			<span class="label">GPU</span>
			<strong class="value">{currentGpuUsage !== null ? formatPercent(currentGpuUsage, 2) : '-'}</strong>
			<span class="sub">{rangeLabel} 평균 {formatPercent(gpuAvg, 1)} · 피크 {formatPercent(gpuPeak, 1)}</span>
			<div class="spark"><MetricSparkline values={gpuTrend} color="#f472b6" label="GPU 추이" /></div>
		</div>
	{/if}
</section>

<style>
	.kpi-bar {
		--kpi-pad: clamp(9px, 0.6vw, 16px);
		--kpi-radius: clamp(6px, 0.4vw, 10px);
		--font-xs: clamp(10px, 0.62vw, 13px);
		--font-sm: clamp(11px, 0.72vw, 15px);
		--font-md: clamp(13px, 0.85vw, 17px);
		--font-lg: clamp(18px, 1.25vw, 26px);

		display: grid;
		/* CPU/메모리/네트워크/디스크 (+GPU) → 4~5개 KPI. 1920 한 줄 보장.
		   minmax 하한을 작게 둬서 좁아지면 자동 wrap. */
		grid-template-columns: repeat(auto-fit, minmax(clamp(170px, 12vw, 240px), 1fr));
		gap: clamp(6px, 0.5vw, 12px);
		margin-top: 14px;
	}
	.kpi {
		min-width: 0;
		min-height: clamp(96px, 8.5vh, 140px);
		padding: var(--kpi-pad);
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--kpi-radius);
		display: flex;
		flex-direction: column;
		gap: 3px;
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
</style>
