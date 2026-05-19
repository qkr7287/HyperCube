<!--
  PowerTempGauge — CPU / GPU 한 쌍의 값(전력 W 또는 온도 °C)을 듀얼 반원 게이지로 표시.
  ECharts 안 씀 (가벼움 + 두 게이지 동시에 컴팩트하게).
  null/undefined 는 "—" 로 표시.
-->
<script lang="ts">
	type Entry = {
		label: string;
		value: number | null | undefined;
		max: number;
		warn?: number;
		crit?: number;
	};

	let {
		title,
		unit,
		cpu,
		gpu,
	}: {
		title: string;
		unit: string;
		cpu: Entry;
		gpu: Entry;
	} = $props();

	function levelFor(v: number | null | undefined, warn?: number, crit?: number): 'normal' | 'warn' | 'danger' {
		if (v == null || !Number.isFinite(v)) return 'normal';
		if (crit != null && v >= crit) return 'danger';
		if (warn != null && v >= warn) return 'warn';
		return 'normal';
	}

	function colorFor(level: 'normal' | 'warn' | 'danger'): string {
		return level === 'danger' ? '#f87171' : level === 'warn' ? '#fbbf24' : '#34d399';
	}

	// 반원 arc: r=42, cx=50, cy=50. start (-180°) → end (0°), length = π·r ≈ 132.
	const R = 42;
	const ARC_LEN = Math.PI * R;

	function arcOffset(value: number | null | undefined, max: number): number {
		if (value == null || !Number.isFinite(value) || max <= 0) return ARC_LEN;
		const pct = Math.max(0, Math.min(1, value / max));
		return ARC_LEN * (1 - pct);
	}

	function fmt(value: number | null | undefined): string {
		if (value == null || !Number.isFinite(value)) return '—';
		return value >= 100 ? value.toFixed(0) : value >= 10 ? value.toFixed(1) : value.toFixed(1);
	}

	let cpuLevel = $derived(levelFor(cpu.value, cpu.warn, cpu.crit));
	let gpuLevel = $derived(levelFor(gpu.value, gpu.warn, gpu.crit));
</script>

<div class="wrap">
	<div class="title">{title}</div>
	<div class="grid">
		{#each [{ entry: cpu, level: cpuLevel }, { entry: gpu, level: gpuLevel }] as { entry, level }}
			<div class="cell" data-level={level}>
				<svg class="dial" viewBox="0 0 100 60" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
					<!-- track -->
					<path d="M 8 50 A 42 42 0 0 1 92 50" fill="none" stroke="rgba(100,116,139,0.18)" stroke-width="8" stroke-linecap="round" />
					<!-- value -->
					<path
						d="M 8 50 A 42 42 0 0 1 92 50"
						fill="none"
						stroke={colorFor(level)}
						stroke-width="8"
						stroke-linecap="round"
						stroke-dasharray={ARC_LEN}
						stroke-dashoffset={arcOffset(entry.value, entry.max)}
					/>
				</svg>
				<div class="readout">
					<strong class="value" style:color={colorFor(level)}>
						{fmt(entry.value)}<span class="unit">{unit}</span>
					</strong>
					<span class="label">{entry.label}</span>
				</div>
			</div>
		{/each}
	</div>
</div>

<style>
	.wrap {
		display: flex;
		flex-direction: column;
		height: 100%;
		gap: 6px;
		min-height: 0;
	}
	.title {
		font-size: var(--font-xs);
		font-weight: 800;
		color: var(--text-secondary);
		letter-spacing: 0.3px;
	}
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 6px;
		flex: 1;
		min-height: 0;
	}
	.cell {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 4px 2px 6px;
		background: rgba(15, 23, 42, 0.32);
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-radius: 6px;
		min-width: 0;
	}
	.cell[data-level='warn'] {
		border-color: rgba(245, 158, 11, 0.45);
	}
	.cell[data-level='danger'] {
		border-color: rgba(239, 68, 68, 0.55);
	}
	.dial {
		width: 100%;
		max-height: 56px;
	}
	.readout {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1px;
		margin-top: -10px;
	}
	.value {
		font-size: 16px;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
		letter-spacing: -0.3px;
		line-height: 1;
	}
	.value .unit {
		font-size: 10px;
		font-weight: 700;
		margin-left: 2px;
		opacity: 0.85;
	}
	.label {
		font-size: 10px;
		font-weight: 700;
		color: var(--text-muted);
		letter-spacing: 0.4px;
	}
</style>
