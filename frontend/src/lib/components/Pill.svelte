<script lang="ts">
	import { statusTone } from '$lib/utils/container-dashboard';

	type Size = 'sm' | 'md';
	type Variant = 'outline' | 'soft' | 'filled';
	type Kind =
		| 'success'
		| 'danger'
		| 'warning'
		| 'info'
		| 'progress'
		| 'neutral'
		| 'accent';

	const KIND_TONES: Record<Kind, string> = {
		success: '#5fba85',
		danger: '#d97070',
		warning: '#d4a25b',
		info: '#6c9bd0',
		progress: '#a087d9',
		neutral: '#64748b',
		accent: 'var(--accent)'
	};

	let {
		tone = 'var(--text-secondary)',
		kind = undefined,
		status = undefined,
		size = 'md',
		variant = 'outline',
		dot = false,
		mono = false,
		truncate = false,
		maxWidth = '',
		minWidth = '',
		title = undefined,
		class: extraClass = '',
		children
	}: {
		tone?: string;
		kind?: Kind;
		status?: string | null;
		size?: Size;
		variant?: Variant;
		dot?: boolean;
		mono?: boolean;
		truncate?: boolean;
		maxWidth?: string;
		minWidth?: string;
		title?: string;
		class?: string;
		children?: import('svelte').Snippet;
	} = $props();

	const resolvedTone = $derived(
		status ? statusTone(status) : kind ? KIND_TONES[kind] : tone
	);

	const styleStr = $derived(
		[
			`--pill-tone: ${resolvedTone};`,
			maxWidth ? `max-width: ${maxWidth};` : '',
			minWidth ? `min-width: ${minWidth};` : ''
		]
			.filter(Boolean)
			.join(' ')
	);
</script>

<span
	class="pill pill--{size} pill--{variant} {mono ? 'pill--mono' : ''} {truncate ? 'pill--truncate' : ''} {extraClass}"
	style={styleStr}
	{title}
>
	{#if dot}
		<span class="pill__dot" aria-hidden="true"></span>
	{/if}
	{#if truncate}
		<span class="pill__label">{@render children?.()}</span>
	{:else}
		{@render children?.()}
	{/if}
</span>

<style>
	.pill {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 6px;
		box-sizing: border-box;
		white-space: nowrap;
		flex-shrink: 0;
		letter-spacing: 0.01em;
		font-weight: 750;
		line-height: 1;
	}

	/* sizes ------------------------------------------------------------- */
	.pill--sm {
		height: 26px;
		padding: 0 10px;
		border-radius: 5px;
		font-size: 12px;
	}

	.pill--md {
		height: 30px;
		padding: 0 12px;
		border-radius: 6px;
		font-size: 13px;
	}

	/* variants ---------------------------------------------------------- */
	.pill--outline {
		background: transparent;
		border: 1px solid color-mix(in srgb, var(--pill-tone) 42%, transparent);
		color: var(--pill-tone);
	}

	.pill--soft {
		background: color-mix(in srgb, var(--pill-tone) 14%, transparent);
		border: 1px solid color-mix(in srgb, var(--pill-tone) 28%, transparent);
		color: var(--pill-tone);
	}

	.pill--filled {
		background: var(--pill-tone);
		border: 1px solid var(--pill-tone);
		color: var(--bg-base, #0d1117);
		font-weight: 800;
	}

	.pill--mono {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.pill--truncate {
		overflow: hidden;
	}

	.pill__label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.pill__dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--pill-tone);
		flex-shrink: 0;
	}

	.pill--filled .pill__dot {
		background: var(--bg-base, #0d1117);
	}
</style>
