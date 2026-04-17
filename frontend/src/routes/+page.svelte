<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { systemStore, containersStore, connect, disconnect } from '$lib/stores/ws-store';
	import { connectGlobal, disconnectGlobal, seedActiveAgents } from '$lib/stores/global-events';
	import LeftSidebar from '$lib/components/LeftSidebar.svelte';
	import StatusToasts from '$lib/components/StatusToasts.svelte';
	import AgentStatusBadge from '$lib/components/AgentStatusBadge.svelte';
	import AdminHeader from '$lib/components/AdminHeader.svelte';
	import RightSidebar from '$lib/components/RightSidebar.svelte';
	import RackUtilization from '$lib/components/RackUtilization.svelte';
	import TopologyCanvas from '$lib/components/TopologyCanvas.svelte';
	import ContainerDetailModal from '$lib/components/ContainerDetailModal.svelte';
	import NetworkDetailModal from '$lib/components/NetworkDetailModal.svelte';
	import LoginDetailModal from '$lib/components/LoginDetailModal.svelte';
	import ProcessDetailModal from '$lib/components/ProcessDetailModal.svelte';
	import CpuDetailModal from '$lib/components/CpuDetailModal.svelte';
	import MemoryDetailModal from '$lib/components/MemoryDetailModal.svelte';
	import DiskDetailModal from '$lib/components/DiskDetailModal.svelte';
	import logoHypercube from '$lib/assets/logo_hypercube.png';
	import { resolveGroup, groupContainersByStack } from '$lib/utils/container-grouping';
	import type { TopologyContainerData } from '$lib/topology/Topology';

	interface Container {
		id: string;
		shortId: string;
		names: string[];
		image: string;
		state: string;
		status: string;
		labels: any;
	}

	interface Project {
		name: string;
		containers: Container[];
		color: string;
		stats: { total: number; running: number; stopped: number; paused: number };
	}

	interface SystemInfo {
		hostname: string;
		os: string;
		cpu: { cores: number; model: string; usage: number };
		memory: { total: string; used: string; free: string; usage: number };
		disk: { total: string; used: string; free: string; usage: number };
		docker: { version: string; containers: number; images: number };
		uptime?: number;
	}

	const projectColors = [
		'#4fc3f7', '#ff7043', '#66bb6a', '#ffa726', '#ab47bc',
		'#26c6da', '#ef5350', '#5c6bc0', '#ffca28', '#ec407a'
	];

	let containers: Container[] = [];
	let projects: Project[] = [];
	let systemInfo: SystemInfo | null = null;
	let selectedProject: string | null = null;
	let lastUpdate = new Date();
	let unsubSystem: (() => void) | null = null;
	let unsubContainers: (() => void) | null = null;
	let fallbackInterval: ReturnType<typeof setInterval> | null = null;
	let wsDataReceived = false;
	let viewMode = 'group';
	let selectedContainer: Container | null = null;
	let cpuModalOpen = false;
	let memoryModalOpen = false;
	let diskModalOpen = false;
	let networkModalOpen = false;
	let loginModalOpen = false;
	let processModalOpen = false;

	// ----- Auth + Server Selection -----
	let accessToken = '';
	let isLoggedIn = false;
	let agents: any[] = [];
	let selectedServerId = '';
	let loginUsername = '';
	let currentUsername = '';
	let loginPassword = '';
	let loginError = '';
	let agentsLoading = false;

	// Topology input — projected from live container state.
	// Phase 3 will also feed networks / mounts once the Agent emits them.
	let topologyContainers: TopologyContainerData[] = [];
	$: topologyContainers = containers.map((c) => ({
		id: c.id,
		name: c.names?.[0]?.replace('/', '') || c.shortId,
		state: c.state,
		stack: resolveGroup(c).name,
	}));

	// TopologyCanvas exposes resetFocus/focusContainer/focusHub as
	// component methods. Bind so ESC and Phase 4 sidebar wiring can
	// drive the 3D scene without exposing the Topology facade.
	let topologyCanvas: {
		resetFocus?: () => void;
		focusContainer?: (id: string) => void;
		focusHub?: (id: string, type: 'stack' | 'network' | 'volume') => void;
		setHubVisibility?: (type: 'stack' | 'network' | 'volume', visible: boolean) => void;
	} | null = null;

	// Hub visibility toggles (req #5). Defaults: stack ON, others OFF.
	let showStackHub = true;
	let showNetworkHub = false;
	let showVolumeHub = false;
	$: topologyCanvas?.setHubVisibility?.('stack', showStackHub);
	$: topologyCanvas?.setHubVisibility?.('network', showNetworkHub);
	$: topologyCanvas?.setHubVisibility?.('volume', showVolumeHub);

	function anyModalOpen(): boolean {
		return cpuModalOpen || memoryModalOpen || diskModalOpen
			|| networkModalOpen || loginModalOpen || processModalOpen
			|| selectedContainer !== null;
	}

	function handleGlobalKeydown(e: KeyboardEvent) {
		if (e.key !== 'Escape') return;
		// Codex P2: modals own ESC. Topology only claims it when no
		// overlay is active and the event didn't originate inside a
		// text field.
		const target = e.target as HTMLElement | null;
		const inField = target && (
			target.tagName === 'INPUT' ||
			target.tagName === 'TEXTAREA' ||
			target.isContentEditable
		);
		if (inField || anyModalOpen()) return;
		topologyCanvas?.resetFocus?.();
	}

	function decodeUsername(token: string): string {
		try {
			return JSON.parse(atob(token.split('.')[1])).username ?? '';
		} catch {
			return '';
		}
	}

	function decodeRole(token: string): string {
		try {
			return JSON.parse(atob(token.split('.')[1])).role ?? '';
		} catch {
			return '';
		}
	}

	async function doLogin() {
		loginError = '';
		try {
			const res = await fetch(`${base}/api/auth/token/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username: loginUsername, password: loginPassword }),
			});
			const json = await res.json();
			if (!res.ok) {
				loginError = json.error?.detail || json.detail || 'Login failed';
				return;
			}
			accessToken = json.data?.access || json.access;
			isLoggedIn = true;
			currentUsername = decodeUsername(accessToken);
			if (browser) {
				localStorage.setItem('hc_access_token', accessToken);
			}
			if (decodeRole(accessToken) === 'user') {
				goto(`${base}/user`);
				return;
			}
			connectGlobal(accessToken);
			await loadApprovedAgents();
		} catch {
			loginError = 'Connection failed';
		}
	}

	function doLogout() {
		disconnect();
		disconnectGlobal();
		accessToken = '';
		isLoggedIn = false;
		selectedServerId = '';
		agents = [];
		if (browser) {
			localStorage.removeItem('hc_access_token');
			localStorage.removeItem('hc_selected_server');
		}
	}

	async function loadApprovedAgents() {
		agentsLoading = true;
		try {
			const res = await fetch(`${base}/api/agents/?status=approved&active=true`, {
				headers: { 'Authorization': `Bearer ${accessToken}` },
			});
			if (res.status === 401) { doLogout(); return; }
			const json = await res.json();
			const data = json.data;
			agents = data.results ?? data ?? [];
			seedActiveAgents(agents.map((a: any) => a.id));

			if (agents.length === 1) {
				selectServer(agents[0].id);
			} else if (browser) {
				const saved = localStorage.getItem('hc_selected_server');
				if (saved && agents.find((a: any) => a.id === saved)) {
					selectServer(saved);
				}
			}
		} catch {
			agents = [];
		} finally {
			agentsLoading = false;
		}
	}

	function selectServer(serverId: string) {
		if (serverId === selectedServerId) return;
		disconnect();
		selectedServerId = serverId;
		if (browser) {
			localStorage.setItem('hc_selected_server', serverId);
		}
		// Reset local view state — the TopologyCanvas will rebuild itself
		// once `topologyContainers` flips to [] and back to the new list.
		systemInfo = null;
		containers = [];
		projects = [];
		selectedProject = null;
		selectedContainer = null;
		cpuModalOpen = false;
		memoryModalOpen = false;
		diskModalOpen = false;
		networkModalOpen = false;
		loginModalOpen = false;
		processModalOpen = false;
		connect(selectedServerId, accessToken);
	}

	function openContainerDetail(container: Container) {
		selectedContainer = container;
		// Phase 4 — also focus that container in the 3D scene
		// (req #15: LIST-detail / group-card-member click should
		// drive the topology).
		topologyCanvas?.focusContainer?.(container.id);
	}

	function closeContainerDetail() {
		selectedContainer = null;
	}

	function onProjectSelect(name: string | null) {
		selectedProject = name;
		// Phase 4 — group card click mirrors clicking the stack hub
		// in 3D. Deselect (null) returns the scene to its initial
		// clustered state.
		if (name) {
			topologyCanvas?.focusHub?.(`stack:${name}`, 'stack');
		} else {
			topologyCanvas?.resetFocus?.();
		}
	}

	function groupContainers(containerList: Container[]) {
		projects = groupContainersByStack(containerList, projectColors) as Project[];
	}

	onMount(async () => {
		if (browser) {
			const savedToken = localStorage.getItem('hc_access_token');
			if (savedToken) {
				if (decodeRole(savedToken) === 'user') {
					goto(`${base}/user`);
					return;
				}
				accessToken = savedToken;
				isLoggedIn = true;
				currentUsername = decodeUsername(accessToken);
				connectGlobal(accessToken);
				await loadApprovedAgents();
			}
		}

		unsubSystem = systemStore.subscribe((data) => {
			if (data) {
				systemInfo = data;
				wsDataReceived = true;
				if (fallbackInterval) { clearInterval(fallbackInterval); fallbackInterval = null; }
			}
		});

		unsubContainers = containersStore.subscribe((data) => {
			containers = data ?? [];
			groupContainers(containers);
			lastUpdate = new Date();
		});

		if (selectedServerId && accessToken) {
			connect(selectedServerId, accessToken);
		}
	});

	onDestroy(() => {
		if (unsubSystem) unsubSystem();
		if (unsubContainers) unsubContainers();
		if (fallbackInterval) clearInterval(fallbackInterval);
		disconnect();
	});
</script>

<svelte:head>
	<title>AGICS Container Monitor</title>
</svelte:head>

<svelte:window on:keydown={handleGlobalKeydown} />

{#if !isLoggedIn}
<div class="auth-page">
	<div class="auth-card">
		<img class="auth-logo" src={logoHypercube} alt="HyperCube" />
		<p class="auth-subtitle">Container Monitoring Platform</p>
		<form onsubmit={(e) => { e.preventDefault(); doLogin(); }}>
			<div class="auth-field">
				<label for="login-user">Username</label>
				<input id="login-user" type="text" bind:value={loginUsername} placeholder="admin" />
			</div>
			<div class="auth-field">
				<label for="login-pass">Password</label>
				<input id="login-pass" type="password" bind:value={loginPassword} />
			</div>
			{#if loginError}
				<p class="auth-error">{loginError}</p>
			{/if}
			<button class="auth-btn" type="submit">Login</button>
		</form>
	</div>
</div>
{:else if !selectedServerId}
<StatusToasts />
<div class="select-header">
	<AgentStatusBadge totalKnown={agents.length} />
</div>
<div class="auth-page">
	<div class="server-select-card">
		<h2 class="auth-title">Select Server</h2>
		<p class="auth-subtitle">Monitor a connected server</p>
		{#if agentsLoading}
			<p class="auth-subtitle">Loading servers...</p>
		{:else if agents.length === 0}
			<p class="auth-subtitle">연결된 서버가 아직 없습니다. 서버에서 Agent를 실행하면 자동으로 등록됩니다.</p>
		{:else}
			<div class="server-list">
				{#each agents as agent (agent.id)}
					<button class="server-item" onclick={() => selectServer(agent.id)}>
						<span class="server-hostname">{agent.hostname}</span>
						<span class="server-ip">{agent.ip_address}</span>
						<span class="server-badge">
							{agent.container_count ?? 0} containers
						</span>
					</button>
				{/each}
			</div>
		{/if}
		<button class="auth-btn-outline" onclick={doLogout}>Logout</button>
	</div>
</div>
{:else}
<StatusToasts />
<div class="admin-shell">
<AdminHeader totalAgents={agents.length} username={currentUsername} onLogout={doLogout} />
<div class="layout">
	<!-- Left Sidebar: Server Info -->
	<LeftSidebar
		{systemInfo}
		totalContainers={containers.length}
		{agents}
		{selectedServerId}
		onSwitchServer={selectServer}
		onOpenCpu={() => { cpuModalOpen = true; }}
		onOpenMemory={() => { memoryModalOpen = true; }}
		onOpenDisk={() => { diskModalOpen = true; }}
		onOpenNetwork={() => { networkModalOpen = true; }}
		onOpenLogin={() => { loginModalOpen = true; }}
		onOpenProcess={() => { processModalOpen = true; }}
	/>

	<!-- Center: 3D Topology (새 OOP topology layer, Phase 1) -->
	<main class="topology-area">
		<div class="graph-wrapper">
			{#key selectedServerId}
				<TopologyCanvas containers={topologyContainers} bind:this={topologyCanvas} />
			{/key}
			<div class="topology-overlay topology-overlay-title">
				<span class="topology-title">SYSTEM TOPOLOGY</span>
			</div>
			<div class="topology-overlay topology-overlay-toggles">
				<label class="hub-toggle hub-toggle-stack">
					<input type="checkbox" bind:checked={showStackHub} />
					<span class="dot"></span>
					<span class="label">Stack</span>
				</label>
				<label class="hub-toggle hub-toggle-network">
					<input type="checkbox" bind:checked={showNetworkHub} />
					<span class="dot"></span>
					<span class="label">Network</span>
				</label>
				<label class="hub-toggle hub-toggle-volume">
					<input type="checkbox" bind:checked={showVolumeHub} />
					<span class="dot"></span>
					<span class="label">Volume</span>
				</label>
			</div>
			<div class="topology-overlay topology-overlay-live">
				<span class="live-dot"></span>
				<span class="live-text">LIVE RENDER</span>
			</div>
			<RackUtilization {systemInfo} />
		</div>
	</main>

	<!-- Right Sidebar: Container Info -->
	<RightSidebar
		{projects}
		{containers}
		{selectedProject}
		onSelectProject={onProjectSelect}
		onSelectContainer={openContainerDetail}
		{viewMode}
		onViewModeChange={(mode) => { viewMode = mode; }}
	/>
</div>

<ContainerDetailModal
	container={selectedContainer}
	onClose={closeContainerDetail}
/>

<CpuDetailModal
	open={cpuModalOpen}
	{systemInfo}
	onClose={() => { cpuModalOpen = false; }}
/>

<MemoryDetailModal
	open={memoryModalOpen}
	{systemInfo}
	onClose={() => { memoryModalOpen = false; }}
/>

<DiskDetailModal
	open={diskModalOpen}
	{systemInfo}
	onClose={() => { diskModalOpen = false; }}
/>

<NetworkDetailModal
	open={networkModalOpen}
	onClose={() => { networkModalOpen = false; }}
/>

<LoginDetailModal
	open={loginModalOpen}
	onClose={() => { loginModalOpen = false; }}
	uptimeSeconds={systemInfo?.uptime ?? 0}
/>

<ProcessDetailModal
	open={processModalOpen}
	onClose={() => { processModalOpen = false; }}
/>
</div>
{/if}

<style>
	.admin-shell {
		display: flex;
		flex-direction: column;
		height: 100vh;
		width: 100vw;
		background: var(--bg-base);
	}

	.layout {
		display: flex;
		flex: 1;
		min-height: 0;
		width: 100%;
		background: var(--bg-base);
	}

	.topology-area {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		background: var(--bg-base);
	}

	.topology-overlay {
		position: absolute;
		top: 24px;
		display: flex;
		align-items: center;
		gap: 6px;
		pointer-events: none;
		z-index: 5;
	}
	.topology-overlay-title { left: 24px; }
	.topology-overlay-live { right: 24px; }

	.topology-overlay-toggles {
		top: 56px;
		left: 24px;
		flex-direction: column;
		align-items: flex-start;
		gap: 8px;
		padding: 10px 12px;
		background: rgba(13, 17, 23, 0.55);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		backdrop-filter: blur(6px);
		pointer-events: auto;
	}

	.hub-toggle {
		display: grid;
		grid-template-columns: 14px 8px auto;
		align-items: center;
		gap: 8px;
		justify-content: flex-start;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-secondary);
		cursor: pointer;
		user-select: none;
	}

	.hub-toggle input[type='checkbox'] {
		appearance: none;
		width: 14px;
		height: 14px;
		border: 1.5px solid var(--border);
		border-radius: 3px;
		background: transparent;
		cursor: pointer;
		position: relative;
	}

	.hub-toggle input[type='checkbox']:checked {
		background: var(--accent);
		border-color: var(--accent);
	}

	.hub-toggle input[type='checkbox']:checked::after {
		content: '';
		position: absolute;
		left: 3px;
		top: 0px;
		width: 4px;
		height: 8px;
		border: solid var(--bg-base);
		border-width: 0 2px 2px 0;
		transform: rotate(45deg);
	}

	.hub-toggle .dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
	}
	.hub-toggle-stack .dot { background: #30d5c8; }
	.hub-toggle-network .dot { background: #22d3ee; box-shadow: 0 0 4px #22d3ee; }
	.hub-toggle-volume .dot { background: #fb923c; box-shadow: 0 0 4px #fb923c; }

	.hub-toggle .label {
		color: var(--text-primary);
	}

	.topology-title {
		font-size: 13px;
		font-weight: 700;
		color: var(--text-secondary);
		letter-spacing: -0.01em;
		text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
	}

	.select-header {
		position: fixed;
		top: 16px;
		right: 24px;
		z-index: 50;
	}

	.live-dot {
		width: 6px;
		height: 6px;
		border-radius: var(--radius-full);
		background: var(--accent);
		animation: pulse 2s ease-in-out infinite;
	}

	.live-text {
		font-size: 13px;
		font-weight: 700;
		color: var(--accent);
		letter-spacing: -0.01em;
		text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
	}

	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.4; }
	}

	.graph-wrapper {
		flex: 1;
		position: relative;
		overflow: hidden;
	}

	/* Auth & Server Selection */
	.auth-page {
		display: flex;
		align-items: center;
		justify-content: center;
		height: 100vh;
		width: 100vw;
		background: var(--bg-base);
	}

	.auth-card, .server-select-card {
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 40px;
		width: 100%;
		max-width: 420px;
	}

	.server-select-card {
		max-width: 500px;
	}

	.auth-title {
		font-size: 22px;
		font-weight: 700;
		color: var(--accent);
		margin-bottom: 4px;
	}
	.auth-logo {
		display: block;
		height: 40px;
		width: auto;
		margin-bottom: 8px;
	}

	.auth-subtitle {
		font-size: 13px;
		color: var(--text-secondary);
		margin-bottom: 28px;
	}

	.auth-field {
		margin-bottom: 16px;
	}

	.auth-field label {
		display: block;
		font-size: 13px;
		color: var(--text-secondary);
		margin-bottom: 6px;
	}

	.auth-field input {
		width: 100%;
		padding: 10px 14px;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text-primary);
		font-size: 14px;
		outline: none;
		box-sizing: border-box;
	}

	.auth-field input:focus {
		border-color: var(--accent);
	}

	.auth-error {
		color: var(--error);
		font-size: 13px;
		margin-bottom: 12px;
	}

	.auth-error a {
		color: var(--accent);
	}

	.auth-btn {
		width: 100%;
		padding: 11px;
		margin-top: 8px;
		background: var(--accent);
		color: var(--bg-base);
		border: none;
		border-radius: 8px;
		font-size: 14px;
		font-weight: 600;
		cursor: pointer;
	}

	.auth-btn:hover { opacity: 0.9; }

	.auth-btn-outline {
		width: 100%;
		padding: 10px;
		margin-top: 16px;
		background: transparent;
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text-secondary);
		font-size: 13px;
		cursor: pointer;
	}

	.auth-btn-outline:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	.server-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-bottom: 8px;
	}

	.server-item {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 14px 18px;
		background: var(--bg-base);
		border: 1px solid var(--border);
		border-radius: 10px;
		cursor: pointer;
		transition: all 0.15s;
		text-align: left;
		width: 100%;
	}

	.server-item:hover {
		border-color: var(--accent);
		background: rgba(48, 213, 200, 0.05);
	}

	.server-hostname {
		font-size: 14px;
		font-weight: 600;
		color: var(--accent);
	}

	.server-ip {
		font-size: 12px;
		color: var(--text-secondary);
		font-family: monospace;
	}

	.server-badge {
		margin-left: auto;
		font-size: 11px;
		color: var(--text-muted);
		background: var(--bg-tab);
		padding: 3px 10px;
		border-radius: 9999px;
	}
</style>
