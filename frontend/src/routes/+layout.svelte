<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<meta name="viewport" content="width=device-width, initial-scale=1.0" />
	<title>AGICS Container Monitor</title>
</svelte:head>

{@render children?.()}

<style>
	:global(html, body) {
		margin: 0;
		padding: 0;
		font-family: 'Pretendard GOV', 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
		background-color: var(--bg-base);
		color: var(--text-primary);
		line-height: 1.5;
	}

	:global(*) {
		box-sizing: border-box;
	}

	:global(h1, h2, h3, h4, h5, h6) {
		margin: 0;
		font-weight: 700;
	}

	:global(p) {
		margin: 0;
	}

	:global(button) {
		font-family: inherit;
	}

	:global(:root) {
		--bg-base: #0d1117;
		--bg-card: #121720;
		--bg-card-hover: #1e293b;
		--bg-tab: #151c27;
		--border: #1f2937;
		--accent: #30d5c8;
		--accent-dark: #094b66;
		--error: #ef4444;
		--error-soft: #ef3e5e;
		--text-primary: #cbd5e1;
		--text-secondary: #64748b;
		--text-muted: #475569;
		--tag-bg: #334155;
		--radius-sm: 8px;
		--radius-md: 12px;
		--radius-full: 9999px;
	}

	:global(body) {
		overflow: hidden;
	}

	:global(::-webkit-scrollbar) {
		width: 4px;
	}

	:global(::-webkit-scrollbar-track) {
		background: transparent;
	}

	:global(::-webkit-scrollbar-thumb) {
		background: rgba(100, 116, 139, 0.3);
		border-radius: 2px;
	}
</style>
