<script lang="ts">
	interface SystemInfo {
		hostname: string;
		os: string;
		cpu: { cores: number; model: string; usage: number };
		memory: { total: string; used: string; free: string; usage: number };
		disk: { total: string; used: string; free: string; usage: number };
		docker: { version: string; containers: number; images: number };
		network?: { speed?: string };
		logins?: number;
		processTotal?: number;
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
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M7 12h10M12 7v10"/></svg>
						<span class="label">Hostname</span>
					</div>
					<span class="value">{systemInfo.hostname}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<svg width="15" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
						<span class="label">OS</span>
					</div>
					<span class="value small">{systemInfo.os}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/></svg>
						<span class="label">CPU Cores</span>
					</div>
					<span class="value">{systemInfo.cpu.cores}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<svg width="15" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="6" width="20" height="12" rx="1"/><path d="M6 10h2M10 10h2M14 10h2"/></svg>
						<span class="label">Memory</span>
					</div>
					<span class="value">{systemInfo.memory.total}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
						<span class="label">Disk Total</span>
					</div>
					<span class="value">{systemInfo.disk.total}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
						<span class="label">Network</span>
					</div>
					<span class="value">{systemInfo.network?.speed || '-'}</span>
				</div>

				<div class="info-row">
					<div class="info-label-group">
						<svg width="15" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
						<span class="label">Logins</span>
					</div>
					<span class="value">{systemInfo.logins ?? 0}</span>
				</div>

				<div class="info-row border-top">
					<div class="info-label-group">
						<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8M16 17H8M10 9H8"/></svg>
						<span class="label">Process Total</span>
					</div>
					<span class="value">{systemInfo.processTotal ?? '-'}</span>
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

	.info-label-group svg {
		color: var(--text-secondary);
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
