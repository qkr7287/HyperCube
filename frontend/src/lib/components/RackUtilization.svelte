<script lang="ts">
	import InfoTooltip from './InfoTooltip.svelte';

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
		<span class="rack-title">Rack Utilization <InfoTooltip text={"이 서버 한 대의 CPU·메모리·스토리지가 얼마나 차 있는지 한눈에 보는 게이지입니다.\n\n• 0~70% — 여유 (초록)\n• 70~90% — 주의 (노랑)\n• 90% 이상 — 위험 (빨강)\n\n실시간 값이며, 좌측 사이드바의 같은 지표와 동일한 데이터를 사용합니다."} placement="bottom-end" /></span>
	</div>
	<div class="rack-items">
		<div class="rack-item">
			<div class="rack-item-header">
				<span class="rack-label">CPU</span>
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
				<span class="rack-label">Memory</span>
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
		top: 56px;
		right: 24px;
		z-index: 10;
		width: 208px;
		background: rgba(13, 17, 23, 0.55);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 14px 16px;
		display: flex;
		flex-direction: column;
		gap: 14px;
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
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
