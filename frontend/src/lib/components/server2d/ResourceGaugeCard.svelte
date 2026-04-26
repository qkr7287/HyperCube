<script lang="ts">
	import MetricSparkline from '$lib/components/fleet/MetricSparkline.svelte';

	type Severity = 'ok' | 'warn' | 'hot' | 'dim';

	let {
		label,
		value,
		valueText,
		sparkValues = [],
		sparkColor = '#30d5c8',
		hint = '',
		tooltip = '',
		severity = 'ok' as Severity,
		disabled = false,
		onOpen = null as null | (() => void),
		loading = false,
	}: {
		label: string;
		value: number;
		valueText?: string;
		sparkValues?: number[];
		sparkColor?: string;
		hint?: string;
		tooltip?: string;
		severity?: Severity;
		disabled?: boolean;
		onOpen?: null | (() => void);
		loading?: boolean;
	} = $props();

	const clamped = $derived(Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0)));
	const display = $derived(valueText ?? `${clamped.toFixed(1)}%`);
</script>

<button
	type="button"
	class="gauge {severity}"
	class:disabled
	onclick={disabled || !onOpen ? undefined : onOpen}
	aria-label={`${label} 상세 보기`}
	title={tooltip || label}
	disabled={disabled || !onOpen}
>
	<div class="head">
		<span class="label">{label}</span>
		<strong class="value">{display}</strong>
	</div>
	<div class="bar"><b style={`width:${clamped}%`}></b></div>
	<div class="foot">
		<div class="spark"><MetricSparkline values={sparkValues} color={sparkColor} label={label} {loading} /></div>
		{#if hint}<small class="hint">{hint}</small>{/if}
	</div>
</button>

<style>
	.gauge {
		display: grid;
		grid-template-rows: auto auto auto;
		gap: 3px;
		padding: 6px 10px 7px;
		border: 1px solid var(--border);
		border-radius: 9px;
		background: rgba(15, 23, 42, 0.55);
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
		min-width: 0;
		min-height: 0;
		transition: border-color 0.12s ease, background-color 0.12s ease, transform 0.12s ease;
	}

	.gauge:hover:not(.disabled) {
		border-color: rgba(48, 213, 200, 0.4);
		transform: translateY(-1px);
	}

	.gauge.disabled {
		cursor: default;
		opacity: 0.72;
	}

	.head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 8px;
		min-width: 0;
	}

	.label {
		color: var(--text-muted);
		font-size: 12px;
		font-weight: 800;
		display: inline-flex;
		align-items: center;
		letter-spacing: 0.02em;
		flex: 0 0 auto;
	}

	.value {
		font-size: 18px;
		font-weight: 900;
		color: var(--text-primary);
		line-height: 1.05;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
		text-align: right;
	}

	.bar {
		height: 8px;
		border-radius: 999px;
		background: rgba(30, 41, 59, 0.92);
		overflow: hidden;
	}

	.bar b {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: linear-gradient(90deg, #30d5c8, #60a5fa);
		transition: width 0.24s ease;
	}

	.gauge.warn .bar b {
		background: linear-gradient(90deg, #fbbf24, #f97316);
	}

	.gauge.hot .bar b {
		background: linear-gradient(90deg, #f87171, #dc2626);
	}

	.gauge.dim .bar b {
		background: linear-gradient(90deg, #64748b, #94a3b8);
	}

	.gauge.warn {
		border-color: rgba(251, 191, 36, 0.28);
	}

	.gauge.hot {
		border-color: rgba(248, 113, 113, 0.32);
	}

	.foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		min-width: 0;
	}

	.spark {
		flex: 1;
		min-width: 0;
	}

	.hint {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
