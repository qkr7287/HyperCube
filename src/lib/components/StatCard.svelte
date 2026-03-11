<script lang="ts">
	let {
		count = 0,
		label = '',
		type = 'default',
	}: {
		count: number;
		label: string;
		type: 'running' | 'waiting' | 'stopped' | 'default';
	} = $props();

	const iconMap = {
		running: { bg: 'var(--accent)', icon: 'play' },
		waiting: { bg: 'var(--bg-tab)', icon: 'pause' },
		stopped: { bg: 'var(--error-soft)', icon: 'stop' },
		default: { bg: 'var(--bg-tab)', icon: 'circle' },
	};

	let config = $derived(iconMap[type] || iconMap.default);
</script>

<div class="stat-card">
	<div class="icon-circle" style="background: {config.bg}">
		{#if type === 'running'}
			<svg width="11" height="12" viewBox="0 0 11 12" fill="none">
				<path d="M1 1L10 6L1 11V1Z" fill={type === 'running' ? '#0d1117' : '#cbd5e1'} stroke="none"/>
			</svg>
		{:else if type === 'waiting'}
			<svg width="9" height="15" viewBox="0 0 9 15" fill="none">
				<rect x="0" y="0" width="3" height="15" rx="1" fill="#cbd5e1"/>
				<rect x="6" y="0" width="3" height="15" rx="1" fill="#cbd5e1"/>
			</svg>
		{:else}
			<svg width="15" height="15" viewBox="0 0 15 15" fill="none">
				<rect width="15" height="15" rx="2" fill="#0d1117"/>
			</svg>
		{/if}
	</div>
	<div class="stat-text">
		<span class="stat-label">{label}</span>
		<span class="stat-count" class:error={type === 'stopped' && count > 0}>{count}</span>
	</div>
</div>

<style>
	.stat-card {
		flex: 1;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 16px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 8px;
	}

	.icon-circle {
		width: 36px;
		height: 36px;
		border-radius: var(--radius-full);
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.stat-text {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0;
	}

	.stat-label {
		font-size: 13px;
		color: var(--text-muted);
	}

	.stat-count {
		font-size: 24px;
		font-weight: 500;
		color: var(--text-primary);
		line-height: 1.2;
	}

	.stat-count.error {
		font-weight: 700;
		color: var(--error);
	}
</style>
