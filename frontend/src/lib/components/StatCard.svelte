<script lang="ts">
	import iconRunning from '$lib/assets/icons/stat-running.svg';
	import iconWaiting from '$lib/assets/icons/stat-waiting.svg';
	import iconStopped from '$lib/assets/icons/stat-stopped.svg';

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
		running: { bg: 'rgba(48, 213, 200, 0.1)', icon: iconRunning },
		waiting: { bg: '#151C27', icon: iconWaiting },
		stopped: { bg: 'rgba(239, 62, 94, 0.1)', icon: iconStopped },
		default: { bg: '#151C27', icon: iconWaiting },
	};

	let config = $derived(iconMap[type] || iconMap.default);
</script>

<div class="stat-card">
	<div class="icon-circle" style="background: {config.bg}">
		<img src={config.icon} alt="" class="stat-icon" />
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

	.stat-icon {
		width: 16px;
		height: 16px;
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
