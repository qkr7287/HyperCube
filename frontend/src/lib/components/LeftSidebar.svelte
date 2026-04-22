<script lang="ts">
	import iconHostname from '$lib/assets/icons/sidebar-hostname.svg';
	import iconOs from '$lib/assets/icons/sidebar-os.svg';
	import iconCpu from '$lib/assets/icons/sidebar-cpu.svg';
	import iconMemory from '$lib/assets/icons/sidebar-memory.svg';
	import iconDisk from '$lib/assets/icons/sidebar-disk.svg';
	import iconNetwork from '$lib/assets/icons/sidebar-network.svg';
	import iconLogins from '$lib/assets/icons/sidebar-logins.svg';
	import iconProcess from '$lib/assets/icons/sidebar-process.svg';
	import LiveSparkline from './LiveSparkline.svelte';

	interface SystemInfo {
		hostname: string;
		os: string;
		uptime?: number;
		cpu: {
			cores: number;
			threads?: number;
			sockets?: number;
			isHybrid?: boolean;
			performanceCores?: number;
			efficiencyCores?: number;
			model: string;
			usage: number;
		};
		memory: { total: string; used: string; free: string; usage: number };
		disk: { total: string; used: string; free: string; usage: number };
		docker: { version: string; containers: number; images: number };
		network?: { connections?: number; interfaces?: string[] };
		logins?: { total?: number; active?: number };
		processes?: { total?: number; running?: number };
	}

	interface AgentOption {
		id: string;
		hostname: string;
		ip_address: string;
	}

	let {
		systemInfo = null,
		totalContainers = 0,
		agents = [],
		selectedServerId = '',
		onSwitchServer = (_id: string) => {},
		onOpenCpu = () => {},
		onOpenMemory = () => {},
		onOpenDisk = () => {},
		onOpenNetwork = () => {},
		onOpenLogin = () => {},
		onOpenProcess = () => {},
	}: {
		systemInfo: SystemInfo | null;
		totalContainers: number;
		agents?: AgentOption[];
		selectedServerId?: string;
		onSwitchServer?: (id: string) => void;
		onOpenCpu: () => void;
		onOpenMemory: () => void;
		onOpenDisk: () => void;
		onOpenNetwork: () => void;
		onOpenLogin: () => void;
		onOpenProcess: () => void;
	} = $props();

	let switcherOpen = $state(false);
	let currentAgent = $derived(agents.find((a) => a.id === selectedServerId) ?? null);
	let otherAgents = $derived(agents.filter((a) => a.id !== selectedServerId));

	function toggleSwitcher(e: MouseEvent) {
		e.stopPropagation();
		switcherOpen = !switcherOpen;
	}

	function switchTo(id: string) {
		switcherOpen = false;
		if (id !== selectedServerId) onSwitchServer(id);
	}

	function handleDocClick(e: MouseEvent) {
		if (!switcherOpen) return;
		const target = e.target as HTMLElement;
		if (!target.closest('.server-switcher')) switcherOpen = false;
	}

	$effect(() => {
		document.addEventListener('click', handleDocClick);
		return () => document.removeEventListener('click', handleDocClick);
	});

	function formatCpuSpec(cpu: SystemInfo['cpu']): string {
		const cores = cpu.cores ?? 0;
		const threads = cpu.threads ?? cores;
		const sockets = cpu.sockets ?? 1;
		const hybrid = !!cpu.isHybrid;

		// Hybrid CPU (Intel 12+ / Apple Silicon): emphasise P+E breakdown.
		if (hybrid) {
			const p = cpu.performanceCores ?? 0;
			const e = cpu.efficiencyCores ?? 0;
			return `${p}P + ${e}E / ${threads} threads`;
		}

		// Legacy agent: only `cores` field, physical count unknown.
		if (!cores && threads) return `${threads} threads`;

		// Multi-socket server: call it out.
		if (sockets > 1) {
			return `${sockets}× ${cores / sockets} cores / ${threads} threads`;
		}

		return `${cores} cores / ${threads} threads`;
	}

</script>

<aside class="sidebar">
	<div class="server-section">
		{#if systemInfo}
			<div class="info-group">
				<div class="group-label">Identity</div>
				<div class="info-row">
					<div class="info-label-group">
						<img src={iconHostname} alt="" class="icon" />
						<span class="label">Hostname</span>
					</div>
					<div class="server-switcher">
						<button
							class="hostname-trigger"
							class:clickable={agents.length > 1}
							onclick={toggleSwitcher}
							disabled={agents.length <= 1}
							title={agents.length > 1 ? '다른 서버로 전환' : systemInfo.hostname}
						>
							<span class="value">{systemInfo.hostname}</span>
							{#if agents.length > 1}
								<svg class="chevron" class:open={switcherOpen} width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
							{/if}
						</button>
						{#if switcherOpen && otherAgents.length > 0}
							<div class="switcher-menu">
								{#each otherAgents as a (a.id)}
									<button class="switcher-item" onclick={() => switchTo(a.id)}>
										<span class="switcher-hostname">{a.hostname}</span>
										<span class="switcher-ip">{a.ip_address}</span>
									</button>
								{/each}
							</div>
						{/if}
					</div>
				</div>

				{#if currentAgent}
					<div class="info-row">
						<div class="info-label-group">
							<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
							<span class="label">IP</span>
						</div>
						<span class="value mono">{currentAgent.ip_address}</span>
					</div>
				{/if}

				<div class="info-row">
					<div class="info-label-group">
						<img src={iconOs} alt="" class="icon" />
						<span class="label">OS</span>
					</div>
					<span class="value value-small" title={systemInfo.os}>{systemInfo.os}</span>
				</div>
			</div>

			{@const cpuSpec = formatCpuSpec(systemInfo.cpu)}
			{@const memPct = Math.round(systemInfo.memory.usage ?? 0)}
			{@const diskPct = Math.round(systemInfo.disk.usage ?? 0)}
			{@const cpuPct = Math.round(systemInfo.cpu.usage ?? 0)}
			{@const netCount = systemInfo.network?.connections ?? 0}
			{@const procCount = systemInfo.processes?.total ?? 0}

			<div class="info-group">
				<div class="group-label">Resources</div>

				<div class="metric-card clickable" onclick={onOpenCpu} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && onOpenCpu()}>
					<div class="metric-head">
						<img src={iconCpu} alt="" class="icon" />
						<span class="metric-name">CPU</span>
						<span class="metric-spec" title={systemInfo.cpu.model}>{cpuSpec}</span>
						<span class="metric-value">{cpuPct}%</span>
					</div>
					<div class="metric-chart">
						<LiveSparkline value={cpuPct} stroke="#30d5c8" fill="rgba(48,213,200,0.16)" />
					</div>
				</div>

				<div class="metric-card clickable" onclick={onOpenMemory} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && onOpenMemory()}>
					<div class="metric-head">
						<img src={iconMemory} alt="" class="icon" />
						<span class="metric-name">Memory</span>
						<span class="metric-spec">{systemInfo.memory.total}</span>
						<span class="metric-value">{memPct}%</span>
					</div>
					<div class="metric-chart">
						<LiveSparkline value={memPct} stroke="#8b5cf6" fill="rgba(139,92,246,0.18)" />
					</div>
				</div>

				<div class="metric-card clickable" onclick={onOpenDisk} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && onOpenDisk()}>
					<div class="metric-head">
						<img src={iconDisk} alt="" class="icon" />
						<span class="metric-name">Disk</span>
						<span class="metric-spec">{systemInfo.disk.total}</span>
						<span class="metric-value">{diskPct}%</span>
					</div>
					<div class="metric-chart">
						<LiveSparkline value={diskPct} stroke="#f59e0b" fill="rgba(245,158,11,0.18)" />
					</div>
				</div>
			</div>

			<div class="info-group">
				<div class="group-label">Activity</div>

				<div class="metric-card clickable" onclick={onOpenNetwork} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && onOpenNetwork()}>
					<div class="metric-head">
						<img src={iconNetwork} alt="" class="icon" />
						<span class="metric-name">Network</span>
						<span class="metric-spec">conns</span>
						<span class="metric-value">{netCount}</span>
					</div>
					<div class="metric-chart">
						<LiveSparkline value={netCount} min={0} max={Math.max(netCount * 1.4, 10)} stroke="#4ade80" fill="rgba(74,222,128,0.15)" />
					</div>
				</div>

				<div class="info-row clickable" onclick={onOpenLogin} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && onOpenLogin()}>
					<div class="info-label-group">
						<img src={iconLogins} alt="" class="icon" />
						<span class="label">Logins</span>
					</div>
					<span class="value">{systemInfo.logins?.total ?? 0}</span>
				</div>

				<div class="metric-card clickable" onclick={onOpenProcess} role="button" tabindex="0" onkeydown={(e) => e.key === 'Enter' && onOpenProcess()}>
					<div class="metric-head">
						<img src={iconProcess} alt="" class="icon" />
						<span class="metric-name">Processes</span>
						<span class="metric-spec">total</span>
						<span class="metric-value">{procCount}</span>
					</div>
					<div class="metric-chart">
						<LiveSparkline value={procCount} min={0} max={Math.max(procCount * 1.3, 100)} stroke="#f87171" fill="rgba(248,113,113,0.14)" />
					</div>
				</div>
			</div>
		{:else}
			<div class="loading">
				<div class="loading-title">Agent 연결 대기 중</div>
				<div class="loading-sub">
					선택한 서버의 Agent에서 아직 데이터가 도착하지 않았습니다.
					{#if agents.length > 1}
						<br />다른 서버로 전환하려면 상단 IP 배지를 눌러주세요.
					{/if}
				</div>
			</div>
		{/if}
	</div>

</aside>

<style>
	.sidebar {
		width: 288px;
		min-width: 288px;
		background: var(--bg-base);
		border-right: 1px solid var(--border);
		padding: 22px 20px 20px;
		display: flex;
		flex-direction: column;
		gap: 20px;
		overflow-y: auto;
	}

	.server-section {
		display: flex;
		flex-direction: column;
		gap: 18px;
	}

	.info-group {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding-bottom: 14px;
		border-bottom: 1px solid rgba(148, 163, 184, 0.08);
	}

	.info-group:last-child {
		border-bottom: none;
		padding-bottom: 4px;
	}

	.group-label {
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: rgba(148, 163, 184, 0.7);
		margin-bottom: 4px;
	}

	.server-switcher {
		position: relative;
	}

	.hostname-trigger {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		background: none;
		border: none;
		padding: 0;
		font-family: inherit;
		cursor: default;
		color: var(--text-primary);
	}
	.hostname-trigger[disabled] { cursor: default; }
	.hostname-trigger.clickable {
		cursor: pointer;
		transition: color 0.15s;
	}
	.hostname-trigger.clickable:hover .value,
	.hostname-trigger.clickable:hover .chevron {
		color: var(--accent);
	}

	.chevron {
		transition: transform 0.15s, color 0.15s;
		color: var(--text-secondary);
	}
	.chevron.open {
		transform: rotate(180deg);
	}

	.switcher-menu {
		position: absolute;
		top: calc(100% + 6px);
		right: 0;
		min-width: 180px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
		padding: 6px;
		z-index: 50;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.switcher-item {
		background: none;
		border: none;
		color: var(--text-primary);
		text-align: left;
		padding: 8px 10px;
		border-radius: var(--radius-sm);
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-family: inherit;
	}

	.switcher-item:hover {
		background: var(--bg-tab);
	}

	.switcher-hostname {
		font-size: 12px;
		font-weight: 600;
	}

	.switcher-ip {
		font-size: 10px;
		color: var(--text-secondary);
		font-family: monospace;
	}

	.info-row {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		min-height: 32px;
	}

	.info-row.clickable {
		cursor: pointer;
		border-radius: 8px;
		padding: 6px 10px;
		margin: -6px -10px;
		transition: background 0.15s ease;
	}

	.info-row.clickable:hover {
		background: rgba(48, 213, 200, 0.08);
	}
	.info-row.clickable:hover .icon {
		filter: drop-shadow(0 0 6px rgba(48, 213, 200, 0.45));
	}

	.info-label-group {
		display: flex;
		align-items: center;
		gap: 10px;
		color: var(--text-primary);
		min-width: 0;
	}

	.icon {
		width: 18px;
		height: 18px;
		flex-shrink: 0;
		opacity: 0.9;
	}

	.label {
		font-size: 12px;
		font-weight: 600;
		color: var(--text-secondary);
		letter-spacing: 0.01em;
	}

	.value {
		font-size: 14px;
		font-weight: 600;
		color: var(--text-primary);
		text-align: right;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 170px;
	}

	.value.mono {
		font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
		font-size: 12.5px;
		letter-spacing: 0.01em;
	}

	.value.value-small {
		font-size: 11px;
		font-weight: 500;
		color: var(--text-secondary);
		max-width: 180px;
	}

	/* ---------- Metric card (CPU/Memory/Disk/Network/Processes) ---------- */
	.metric-card {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 8px 10px 6px;
		margin: -2px -10px;
		border-radius: 10px;
		background: rgba(15, 23, 42, 0.55);
		border: 1px solid rgba(148, 163, 184, 0.08);
		cursor: pointer;
		transition: background-color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
	}

	.metric-card:hover {
		background: rgba(48, 213, 200, 0.07);
		border-color: rgba(48, 213, 200, 0.18);
		transform: translateY(-1px);
	}
	.metric-card:hover .icon {
		filter: drop-shadow(0 0 6px rgba(48, 213, 200, 0.5));
	}

	.metric-head {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.metric-head .icon {
		width: 16px;
		height: 16px;
		flex-shrink: 0;
		opacity: 0.9;
	}

	.metric-name {
		font-size: 12px;
		font-weight: 700;
		color: var(--text-primary);
		letter-spacing: 0.02em;
	}

	.metric-spec {
		flex: 1;
		min-width: 0;
		font-size: 10px;
		color: rgba(148, 163, 184, 0.72);
		text-align: left;
		margin-left: 4px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.metric-value {
		font-size: 13px;
		font-weight: 700;
		color: var(--text-primary);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.metric-chart {
		width: 100%;
		height: 28px;
	}

	.loading {
		color: var(--text-secondary);
		font-size: 12px;
		text-align: center;
		padding: 24px 16px;
	}

	.loading-title {
		font-size: 13px;
		font-weight: 600;
		color: var(--text-primary);
		margin-bottom: 8px;
	}

	.loading-sub {
		font-size: 11px;
		line-height: 1.5;
		color: var(--text-secondary);
	}
</style>
