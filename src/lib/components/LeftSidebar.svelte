<script lang="ts">
	import iconHostname from '$lib/assets/icons/sidebar-hostname.svg';
	import iconOs from '$lib/assets/icons/sidebar-os.svg';
	import iconCpu from '$lib/assets/icons/sidebar-cpu.svg';
	import iconMemory from '$lib/assets/icons/sidebar-memory.svg';
	import iconDisk from '$lib/assets/icons/sidebar-disk.svg';
	import iconNetwork from '$lib/assets/icons/sidebar-network.svg';
	import iconLogins from '$lib/assets/icons/sidebar-logins.svg';
	import iconProcess from '$lib/assets/icons/sidebar-process.svg';

	interface SystemInfo {
		hostname: string;
		os: string;
		cpu: { cores: number; model: string; usage: number };
		memory: { total: string; used: string; free: string; usage: number };
		disk: { total: string; used: string; free: string; usage: number };
		docker: { version: string; containers: number; images: number };
		network?: { connections?: number; interfaces?: string[] };
		logins?: { total?: number; active?: number };
		processes?: { total?: number; running?: number };
	}

	let {
		systemInfo = null,
		totalContainers = 0,
	}: {
		systemInfo: SystemInfo | null;
		totalContainers: number;
	} = $props();

	function getHealthPercent(info: SystemInfo): number {
		const cpuHealth = Math.max(0, 100 - info.cpu.usage);
		const memHealth = Math.max(0, 100 - info.memory.usage);
		const diskHealth = Math.max(0, 100 - info.disk.usage);
		return Math.round((cpuHealth + memHealth + diskHealth) / 3);
	}
</script>

<aside class="sidebar">
	<div class="server-section">
		<div class="section-header">
			<span class="heading">서버 정보</span>
			{#if systemInfo}
				<span class="ip-badge">192.168.0.16</span>
			{/if}
		</div>

		{#if systemInfo}
			<div class="info-list">
				<div class="info-row">
					<div class="info-label-group">
						<img src={iconHostname} alt="" class="icon" />
						<span class="label">Hostname</span>
					</div>
					<span class="value">{systemInfo.hostname}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<img src={iconOs} alt="" class="icon" />
						<span class="label">OS</span>
					</div>
					<span class="value small">{systemInfo.os}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<img src={iconCpu} alt="" class="icon" />
						<span class="label">CPU Cores</span>
					</div>
					<span class="value">{systemInfo.cpu.cores}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<img src={iconMemory} alt="" class="icon" />
						<span class="label">Memory</span>
					</div>
					<span class="value">{systemInfo.memory.total}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<img src={iconDisk} alt="" class="icon" />
						<span class="label">Disk Total</span>
					</div>
					<span class="value">{systemInfo.disk.total}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<img src={iconNetwork} alt="" class="icon" />
						<span class="label">Network</span>
					</div>
					<span class="value">{systemInfo.network?.connections ?? '-'}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<img src={iconLogins} alt="" class="icon" />
						<span class="label">Logins</span>
					</div>
					<span class="value">{systemInfo.logins?.total ?? 0}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<img src={iconProcess} alt="" class="icon" />
						<span class="label">Process Total</span>
					</div>
					<span class="value">{systemInfo.processes?.total ?? '-'}</span>
				</div>
			</div>
		{:else}
			<div class="loading">Loading...</div>
		{/if}
	</div>

	<div class="spacer"></div>

	{#if systemInfo}
		<div class="health-card">
			<div class="health-header">
				<span class="health-label">Health Status</span>
			</div>
			<div class="health-bar-track">
				<div
					class="health-bar-fill"
					style="width: {getHealthPercent(systemInfo)}%"
				></div>
			</div>
			<div class="health-footer">
				<span class="health-percent">{getHealthPercent(systemInfo)}% Stable</span>
				<span class="health-uptime">Uptime: 14d</span>
			</div>
		</div>
	{/if}
</aside>

<style>
	.sidebar {
		width: 288px;
		min-width: 288px;
		background: var(--bg-base);
		border-right: 1px solid var(--border);
		padding: 24px;
		display: flex;
		flex-direction: column;
		gap: 24px;
		overflow-y: auto;
	}

	.section-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 24px;
	}

	.heading {
		font-size: 13px;
		font-weight: 700;
		color: var(--text-secondary);
	}

	.ip-badge {
		background: var(--tag-bg);
		color: var(--text-primary);
		padding: 2px 8px;
		border-radius: var(--radius-sm);
		font-size: 10px;
	}

	.info-list {
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.info-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.info-row.border-top {
		padding-top: 20px;
		border-top: 1px solid var(--border);
	}

	.info-label-group {
		display: flex;
		align-items: center;
		gap: 12px;
		color: var(--text-primary);
	}

	.icon {
		width: 16px;
		height: 16px;
		flex-shrink: 0;
	}

	.label {
		font-size: 13px;
		font-weight: 700;
		color: var(--text-primary);
	}

	.value {
		font-size: 12px;
		color: var(--text-primary);
	}

	.value.small {
		font-size: 10px;
	}

	.spacer {
		flex: 1;
		min-height: 0;
	}

	.health-card {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		padding: 16px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.health-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.health-label {
		font-size: 13px;
		font-weight: 700;
		color: var(--text-secondary);
	}

	.health-bar-track {
		height: 6px;
		background: var(--tag-bg);
		border-radius: var(--radius-full);
		overflow: hidden;
	}

	.health-bar-fill {
		height: 100%;
		background: var(--accent);
		border-radius: var(--radius-full);
		transition: width 0.5s ease;
	}

	.health-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.health-percent {
		font-size: 13px;
		color: var(--text-primary);
	}

	.health-uptime {
		font-size: 13px;
		color: var(--accent);
	}

	.loading {
		color: var(--text-secondary);
		font-size: 12px;
		text-align: center;
		padding: 20px;
	}
</style>
