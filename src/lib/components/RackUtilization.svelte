<script lang="ts">
	interface SystemInfo {
		hostname: string;
		os: string;
		cpu: { cores: number; model: string; usage: number };
		memory: { total: string; used: string; free: string; usage: number };
		disk: { total: string; used: string; free: string; usage: number };
		docker: { version: string; containers: number; images: number };
	}

	let {
		systemInfo = null,
	}: {
		systemInfo: SystemInfo | null;
	} = $props();
</script>

{#if systemInfo}
<div class="rack-panel">
	<div class="rack-header">
		<span class="rack-title">Rack Utilization</span>
	</div>
	<div class="rack-items">
		<div class="rack-item">
			<div class="rack-item-header">
				<span class="rack-label">Node 01</span>
				<span class="rack-value" class:danger={systemInfo.cpu.usage > 90}>
					{systemInfo.cpu.usage.toFixed(0)}%
				</span>
			</div>
			<div class="bar-track">
				<div
					class="bar-fill"
					class:danger={systemInfo.cpu.usage > 90}
					style="width: {systemInfo.cpu.usage}%"
				></div>
			</div>
		</div>

		<div class="rack-item">
			<div class="rack-item-header">
				<span class="rack-label">Node 02</span>
				<span class="rack-value" class:danger={systemInfo.memory.usage > 90}>
					{systemInfo.memory.usage.toFixed(0)}%
				</span>
			</div>
			<div class="bar-track">
				<div
					class="bar-fill"
					class:danger={systemInfo.memory.usage > 90}
					style="width: {systemInfo.memory.usage}%"
				></div>
			</div>
		</div>

		<div class="rack-item">
			<div class="rack-item-header">
				<span class="rack-label">Storage</span>
				<span class="rack-value">{systemInfo.disk.usage.toFixed(0)}%</span>
			</div>
			<div class="bar-track">
				<div class="bar-fill" style="width: {systemInfo.disk.usage}%"></div>
			</div>
		</div>
	</div>
</div>
{/if}

<style>
	.rack-panel {
		position: absolute;
		top: 80px;
		right: 24px;
		z-index: 10;
		width: 208px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 16px;
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
	}

	.rack-header {
		padding-bottom: 8px;
		border-bottom: 1px solid var(--border);
	}

	.rack-title {
		font-size: 13px;
		font-weight: 700;
		color: var(--accent);
	}

	.rack-items {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.rack-item {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.rack-item-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.rack-label {
		font-size: 13px;
		color: var(--text-primary);
	}

	.rack-value {
		font-size: 13px;
		color: var(--accent);
	}

	.rack-value.danger {
		color: var(--error);
	}

	.bar-track {
		height: 4px;
		background: rgba(255, 255, 255, 0.06);
		border-radius: var(--radius-full);
		overflow: hidden;
	}

	.bar-fill {
		height: 100%;
		background: var(--accent);
		border-radius: var(--radius-full);
		transition: width 0.5s ease;
	}

	.bar-fill.danger {
		background: var(--error);
	}
</style>
