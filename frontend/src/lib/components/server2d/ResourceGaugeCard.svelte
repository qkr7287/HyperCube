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
	class:empty={disabled}
	onclick={disabled || !onOpen ? undefined : onOpen}
	aria-label={`${label} 상세 보기`}
	title={tooltip || label}
	disabled={disabled || !onOpen}
>
	<div class="head">
		<span class="label">{label}</span>
		{#if disabled}
			<span class="empty-tag">데이터 없음</span>
		{:else}
			<strong class="value">{display}</strong>
		{/if}
	</div>
	<div class="bar" class:empty={disabled}>
		{#if !disabled}<b style={`width:${clamped}%`}></b>{/if}
	</div>
	<div class="foot">
		<div class="spark">
			{#if disabled}
				<span class="spark-empty" aria-hidden="true"></span>
			{:else}
				<MetricSparkline values={sparkValues} color={sparkColor} label={label} {loading} stretch />
			{/if}
		</div>
		{#if hint}<small class="hint">{hint}</small>{/if}
	</div>
</button>

<style>
	.gauge {
		display: grid;
		grid-template-rows: auto auto auto;
		gap: 7px;
		padding: 9px 12px 10px;
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
	}
	.gauge.empty {
		border-style: dashed;
		border-color: rgba(100, 116, 139, 0.28);
		background: rgba(15, 23, 42, 0.32);
	}
	.empty-tag {
		font-size: 10px;
		font-weight: 800;
		color: rgba(148, 163, 184, 0.78);
		letter-spacing: 0.3px;
		padding: 3px 8px;
		border-radius: 999px;
		background: rgba(100, 116, 139, 0.12);
		border: 1px solid rgba(100, 116, 139, 0.24);
		white-space: nowrap;
	}
	.bar.empty {
		background:
			repeating-linear-gradient(
				90deg,
				rgba(100, 116, 139, 0.18) 0 6px,
				rgba(30, 41, 59, 0.55) 6px 12px
			);
		opacity: 0.55;
	}
	.spark-empty {
		display: block;
		height: 100%;
		width: 100%;
		border-radius: 4px;
		background:
			linear-gradient(
				90deg,
				transparent 0,
				transparent 30%,
				rgba(100, 116, 139, 0.18) 30%,
				rgba(100, 116, 139, 0.18) 32%,
				transparent 32%,
				transparent 60%,
				rgba(100, 116, 139, 0.18) 60%,
				rgba(100, 116, 139, 0.18) 62%,
				transparent 62%
			);
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
		margin-top: 10px;
	}

	.spark {
		flex: 1;
		min-width: 0;
		height: 20px;
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
