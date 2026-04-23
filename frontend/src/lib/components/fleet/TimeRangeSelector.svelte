<script lang="ts">
	import type { TimeRange } from '$lib/stores/fleet-store';

	let {
		value,
		onChange,
	}: {
		value: TimeRange;
		onChange: (value: TimeRange) => void;
	} = $props();

	const options: { value: TimeRange; label: string }[] = [
		{ value: '1m', label: '1m' },
		{ value: '5m', label: '5m' },
		{ value: '1h', label: '1h' },
		{ value: '24h', label: '24h' },
		{ value: '7d', label: '7d' },
	];
</script>

<div class="range" aria-label="Time range">
	{#each options as option}
		<button
			type="button"
			class:active={value === option.value}
			aria-pressed={value === option.value}
			onclick={() => onChange(option.value)}
		>
			{option.label}
		</button>
	{/each}
</div>

<style>
	.range {
		display: inline-flex;
		gap: 2px;
		padding: 3px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
	}
	button {
		min-width: 50px;
		height: 28px;
		border: none;
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 750;
		cursor: pointer;
	}
	button:hover {
		color: var(--text-primary);
		background: var(--bg-tab);
	}
	button.active {
		color: var(--bg-base);
		background: var(--accent);
	}
</style>
