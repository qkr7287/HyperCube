<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { systemStore, containersStore, containerMetricsStore, connect, disconnect } from '$lib/stores/ws-store';
	import { connectGlobal, disconnectGlobal, seedActiveAgents } from '$lib/stores/global-events';
	import LeftSidebar from '$lib/components/LeftSidebar.svelte';
	import LoadingOverlay from '$lib/components/LoadingOverlay.svelte';
	import StatusToasts from '$lib/components/StatusToasts.svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import AgentStatusBadge from '$lib/components/AgentStatusBadge.svelte';
	import AdminHeader from '$lib/components/AdminHeader.svelte';
	import RightSidebar from '$lib/components/RightSidebar.svelte';
	import RackUtilization from '$lib/components/RackUtilization.svelte';
	import SelectionHud from '$lib/components/SelectionHud.svelte';
	import type { HudSelection } from '$lib/components/SelectionHud.svelte';
	import TopologyCanvas from '$lib/components/TopologyCanvas.svelte';
	import TopologyToolbar from '$lib/components/TopologyToolbar.svelte';
	import ContainerDetailModal from '$lib/components/ContainerDetailModal.svelte';
	import NetworkDetailModal from '$lib/components/NetworkDetailModal.svelte';
	import LoginDetailModal from '$lib/components/LoginDetailModal.svelte';
	import ProcessDetailModal from '$lib/components/ProcessDetailModal.svelte';
	import CpuDetailModal from '$lib/components/CpuDetailModal.svelte';
	import MemoryDetailModal from '$lib/components/MemoryDetailModal.svelte';
	import DiskDetailModal from '$lib/components/DiskDetailModal.svelte';
	import GpuDetailModal from '$lib/components/GpuDetailModal.svelte';
	import logoHypercube from '$lib/assets/logo_hypercube.png';
	import { buildNetworkTrafficIndex, type TopologyNetworkTrafficIndex } from '$lib/topology/traffic-adapter';
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
		networks?: string[];
		mounts?: { name: string; type: 'volume' }[];
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

	// Teal/cyan family is reserved for running containers + network
	// tunnels, so it's intentionally excluded from the group palette to
	// keep group membranes visually distinct from network state.
	const projectColors = [
		'#d4a574', '#ff7043', '#66bb6a', '#ffa726', '#ab47bc',
		'#8e24aa', '#ef5350', '#5c6bc0', '#ffca28', '#ec407a'
	];

	let containers: Container[] = [];
	let projects: Project[] = [];
	let systemInfo: SystemInfo | null = null;
	let selectedProject: string | null = null;
	let lastUpdate = new Date();
	let unsubSystem: (() => void) | null = null;
	let unsubContainers: (() => void) | null = null;
	let unsubMetrics: (() => void) | null = null;
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
	let gpuModalOpen = false;

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
	let redirecting = false;

	// Topology input — projected from live container state.
	// Phase 3 will also feed networks / mounts once the Agent emits them.
	let topologyContainers: TopologyContainerData[] = [];
	$: topologyContainers = containers.map((c) => ({
		id: c.id,
		name: c.names?.[0]?.replace('/', '') || c.shortId,
		state: c.state,
		stack: resolveGroup(c).name,
		networks: c.networks,
		mounts: c.mounts,
	}));

	// Per-stack running/total counts driven straight from projects[].
	// The membrane (group mesh) colours itself from this via
	// healthColor() — see $lib/utils/health-color. Stacks missing from
	// the map are treated as fully-healthy on the 3D side.
	let topologyStackHealth: Record<string, { running: number; total: number }> = {};
	$: topologyStackHealth = Object.fromEntries(
		projects.map((p) => [p.name, { running: p.stats.running, total: p.stats.total }])
	);
	let topologyNetworkTraffic: TopologyNetworkTrafficIndex = new Map();

	// TopologyCanvas exposes resetFocus/focusContainer/focusHub as
	// component methods. Bind so ESC and Phase 4 sidebar wiring can
	// drive the 3D scene without exposing the Topology facade.
	let topologyCanvas: {
		resetFocus?: () => void;
		focusContainer?: (id: string) => void;
		focusHub?: (id: string, type: 'stack' | 'network' | 'volume') => void;
		setHubVisibility?: (type: 'stack' | 'network' | 'volume', visible: boolean) => void;
		setAutoRotate?: (enabled: boolean) => void;
	} | null = null;

	// Toolbar state (Phase 5 — restored)
	let autoRotating = false;
	function handleToolbarReset() {
		topologyCanvas?.resetFocus?.();
		autoRotating = false;
		topologyCanvas?.setAutoRotate?.(false);
		clearHudSelection();
	}
	function handleToolbarRotate() {
		autoRotating = !autoRotating;
		topologyCanvas?.setAutoRotate?.(autoRotating);
	}
	async function handleToolbarScreenshot() {
		try {
			const html2canvas = (await import('html2canvas')).default;
			const canvas = await html2canvas(document.body, {
				backgroundColor: '#0d1117',
				scale: 2,
				useCORS: true,
				logging: false,
			});
			const link = document.createElement('a');
			link.download = `hypercube-${Date.now()}.png`;
			link.href = canvas.toDataURL('image/png');
			link.click();
		} catch {
			// html2canvas can choke on tainted canvases; ignore silently.
		}
	}

	// Hub visibility toggles (req #5). Defaults: stack ON, others OFF.
	// Values are passed into TopologyCanvas as props so visibility is
	// re-applied when the scene is remounted (e.g. after resetFocus).
	let showStackHub = true;
	let showNetworkHub = true;
	let showVolumeHub = true;
	let groupVisualMode: 'soft' = 'soft';
	const tunnelStyle: 'subsea' = 'subsea';

	// HUD selection — driven by 3D click callbacks. Null when nothing
	// is currently selected in the scene.
	let hudSelection: HudSelection | null = null;
	// List-mode filter/highlight set. When non-null the sidebar list
	// narrows to exactly these ids.
	let listHighlightIds: Set<string> | null = null;
	// Specific container active from a 3D click — used by the sidebar
	// to emphasise the matching row (list mode) or dot (group mode).
	let selectedContainerId: string | null = null;

	function clearHudSelection() {
		hudSelection = null;
		listHighlightIds = null;
		selectedContainerId = null;
	}

	function dismissHudSelection() {
		hudSelection = null;
	}

	// Full reset — used when the user presses Enter on an empty search
	// or wants to get back to the initial clustered view. Also drops
	// the 3D focus so the tooltip and camera return to default.
	function resetAllSelection() {
		clearHudSelection();
		selectedProject = null;
		topologyCanvas?.resetFocus?.();
	}

	function handle3dContainerClick(id: string) {
		const c = containers.find((x) => x.id === id);
		if (!c) return;
		hudSelection = { kind: 'container', container: c };
		selectedProject = resolveGroup(c).name;
		selectedContainerId = c.id;
		// List mode: narrow the table to the single clicked container.
		listHighlightIds = viewMode === 'list' ? new Set([c.id]) : null;
	}

	function handle3dHubClick(hubId: string, hubType: 'stack' | 'network' | 'volume') {
		const colonIdx = hubId.indexOf(':');
		const name = colonIdx >= 0 ? hubId.slice(colonIdx + 1) : hubId;

		if (hubType === 'stack') {
			const proj = projects.find((p) => p.name === name);
			hudSelection = {
				kind: 'stack',
				name,
				total: proj?.stats.total ?? 0,
				running: proj?.stats.running ?? 0,
				stopped: proj?.stats.stopped ?? 0,
			};
			selectedProject = name;
			selectedContainerId = null;
			// List mode: narrow to the stack's containers.
			if (viewMode === 'list') {
				const ids = containers
					.filter((c) => resolveGroup(c).name === name)
					.map((c) => c.id);
				listHighlightIds = new Set(ids);
			} else {
				listHighlightIds = null;
			}
			return;
		}

		// Network / Volume hub — collect members from live container state.
		const members = containers.filter((c) =>
			hubType === 'network'
				? (c.networks ?? []).includes(name)
				: (c.mounts ?? []).some((m) => m.type === 'volume' && m.name === name)
		);
		const stackSet = new Set<string>();
		for (const c of members) stackSet.add(resolveGroup(c).name);
		const stacks = Array.from(stackSet).sort();

		hudSelection =
			hubType === 'network'
				? { kind: 'network', name, memberCount: members.length, stacks }
				: { kind: 'volume', name, memberCount: members.length, stacks };

		selectedContainerId = null;
		// Network / Volume hubs can span stacks, so only filter+highlight
		// the sidebar list when the list view is open. In group mode we
		// just show the HUD — no sidebar changes.
		if (viewMode === 'list') {
			listHighlightIds = new Set(members.map((m) => m.id));
			selectedProject = null;
		} else {
			listHighlightIds = null;
		}
	}
	let networkTunnelThickness = 0.7;
	const trafficFxStyle: 'soft' = 'soft';
	const volumeEnergyStyle: 'tendril' = 'tendril';

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
		// ESC only dismisses the HUD + tooltip. Camera / layout / focus
		// stay untouched — press the Reset button for a full reset.
		clearHudSelection();
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
			goto(`${base}/`);
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

			if (agents.length === 0) {
				// nothing to select
			} else if (browser) {
				const saved = localStorage.getItem('hc_selected_server');
				if (saved && agents.find((a: any) => a.id === saved)) {
					selectServer(saved);
				} else {
					// no saved server (or saved id is gone) — fall back to the first agent
					// so the 3D detail page is never empty when entered from the nav tab.
					selectServer(agents[0].id);
				}
			} else if (agents.length >= 1) {
				selectServer(agents[0].id);
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
					redirecting = true;
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

		unsubMetrics = containerMetricsStore.subscribe((metrics) => {
			topologyNetworkTraffic = buildNetworkTrafficIndex(metrics);
		});

		if (selectedServerId && accessToken) {
			connect(selectedServerId, accessToken);
		}
	});

	onDestroy(() => {
		if (unsubSystem) unsubSystem();
		if (unsubContainers) unsubContainers();
		if (unsubMetrics) unsubMetrics();
		if (fallbackInterval) clearInterval(fallbackInterval);
		disconnect();
	});
</script>

<svelte:head>
	<title>AGICS Container Monitor</title>
</svelte:head>

<svelte:window on:keydown={handleGlobalKeydown} />

{#if redirecting}
<LoadingOverlay text="이동 중" />
{:else if !isLoggedIn}
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
{:else if !selectedServerId && agentsLoading}
<LoadingOverlay text="서버 정보 불러오는 중" />
{:else if !selectedServerId}
<StatusToasts />
<div class="auth-page">
	<div class="server-select-card">
		<h2 class="auth-title">서버 없음</h2>
		<p class="auth-subtitle">아직 등록·승인된 서버가 없습니다. Agent를 실행하면 자동으로 등록됩니다.</p>
		<button class="auth-btn" onclick={() => goto(`${base}/`)}>전체 서버 모니터링으로 이동</button>
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
		{accessToken}
		onSwitchServer={selectServer}
		onOpenCpu={() => { cpuModalOpen = true; }}
		onOpenMemory={() => { memoryModalOpen = true; }}
		onOpenDisk={() => { diskModalOpen = true; }}
		onOpenNetwork={() => { networkModalOpen = true; }}
		onOpenLogin={() => { loginModalOpen = true; }}
		onOpenProcess={() => { processModalOpen = true; }}
		onOpenGpu={() => { gpuModalOpen = true; }}
	/>

	<!-- Center: 3D Topology (새 OOP topology layer, Phase 1) -->
	<main class="topology-area">
		<div class="graph-wrapper">
			{#key selectedServerId}
				<TopologyCanvas
					containers={topologyContainers}
					stackHealth={topologyStackHealth}
					networkTraffic={topologyNetworkTraffic}
					showStack={showStackHub}
					showNetwork={showNetworkHub}
					showVolume={showVolumeHub}
					groupVisualMode={groupVisualMode}
					{tunnelStyle}
					{networkTunnelThickness}
					{trafficFxStyle}
					{volumeEnergyStyle}
					onContainerClick={handle3dContainerClick}
					onHubClick={handle3dHubClick}
					onEmptyClick={dismissHudSelection}
					bind:this={topologyCanvas}
				/>
			{/key}
			<div class="topology-overlay topology-overlay-title">
				<span class="topology-title">SYSTEM TOPOLOGY</span>
				<InfoTooltip text={"이 서버에서 돌고 있는 컨테이너들과 그들 사이의 연결을 3D 공간에 그린 그림입니다.\n\n• 점(육면체) = 컨테이너 1개\n• 같은 색 영역 안에 묶여 있으면 같은 Stack 또는 같은 Network·Volume을 공유\n• 선 = 컨테이너 간 네트워크/볼륨 연결\n\n드래그로 회전, 휠로 확대/축소할 수 있습니다."} placement="bottom-start" />
			</div>
			<div class="topology-overlay topology-overlay-toggles">
				<label class="hub-toggle hub-toggle-stack" title="같은 Docker Compose 스택(프로젝트) 컨테이너끼리 그룹으로 감싸 보이게/숨기게 합니다.">
					<input type="checkbox" bind:checked={showStackHub} />
					<span class="dot"></span>
					<span class="label">Stack</span>
				</label>
				<label class="hub-toggle hub-toggle-network" title="같은 Docker 네트워크에 연결된 컨테이너끼리 묶음 표시합니다 (네트워크 트래픽 흐름 파악용).">
					<input type="checkbox" bind:checked={showNetworkHub} />
					<span class="dot"></span>
					<span class="label">Network</span>
				</label>
				<label class="hub-toggle hub-toggle-volume" title="같은 Docker 볼륨을 공유하는 컨테이너끼리 묶음 표시합니다 (DB·파일 공유 관계 파악용).">
					<input type="checkbox" bind:checked={showVolumeHub} />
					<span class="dot"></span>
					<span class="label">Volume</span>
				</label>
				<InfoTooltip text={"각 토글을 켜면 그 종류의 그룹이 토폴로지 위에 색깔 영역으로 떠오릅니다.\n\n• Stack — Docker Compose 프로젝트 단위 묶음\n• Network — 같은 docker network에 연결된 컨테이너 묶음\n• Volume — 같은 docker volume을 공유하는 컨테이너 묶음\n\n여러 개 동시에 켜서 어느 컨테이너가 어떤 그룹에 동시에 속해 있는지 한눈에 비교할 수 있습니다."} placement="bottom-end" />
			</div>
			<div class="topology-overlay topology-overlay-live">
				<span class="live-dot"></span>
				<span class="live-text">LIVE RENDER</span>
				<InfoTooltip text={"WebSocket으로 Agent 메트릭을 실시간 수신해 토폴로지를 업데이트하고 있다는 표시입니다.\n\n• 점이 깜빡이면 = 연결됨, 새 데이터가 들어오는 중\n• 점이 회색이거나 사라지면 = Agent와의 연결이 끊긴 상태\n\n끊겼을 때는 페이지를 새로고침하거나 Agent 상태를 점검하세요."} placement="bottom-end" />
			</div>
			<RackUtilization {systemInfo} />
			<TopologyToolbar
				onScreenshot={handleToolbarScreenshot}
				onRotate={handleToolbarRotate}
				onReset={handleToolbarReset}
				isRotating={autoRotating}
			/>
			<SelectionHud
				selection={hudSelection}
				onClose={clearHudSelection}
				onOpenDetail={openContainerDetail}
			/>
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
		onViewModeChange={(mode) => { viewMode = mode; listHighlightIds = null; }}
		highlightedContainerIds={listHighlightIds}
		{selectedContainerId}
		onClearFilters={resetAllSelection}
	/>
</div>

<ContainerDetailModal
	container={selectedContainer}
	agentId={selectedServerId}
	{accessToken}
	onClose={closeContainerDetail}
/>

<CpuDetailModal
	open={cpuModalOpen}
	{systemInfo}
	agentId={selectedServerId}
	{accessToken}
	onClose={() => { cpuModalOpen = false; }}
/>

<MemoryDetailModal
	open={memoryModalOpen}
	{systemInfo}
	agentId={selectedServerId}
	{accessToken}
	onClose={() => { memoryModalOpen = false; }}
/>

<DiskDetailModal
	open={diskModalOpen}
	{systemInfo}
	agentId={selectedServerId}
	{accessToken}
	onClose={() => { diskModalOpen = false; }}
/>

<NetworkDetailModal
	open={networkModalOpen}
	{systemInfo}
	agentId={selectedServerId}
	{accessToken}
	onClose={() => { networkModalOpen = false; }}
/>

<LoginDetailModal
	open={loginModalOpen}
	{systemInfo}
	agentId={selectedServerId}
	{accessToken}
	onClose={() => { loginModalOpen = false; }}
	uptimeSeconds={systemInfo?.uptime ?? 0}
/>

<ProcessDetailModal
	open={processModalOpen}
	{systemInfo}
	agentId={selectedServerId}
	{accessToken}
	onClose={() => { processModalOpen = false; }}
/>

<GpuDetailModal
	open={gpuModalOpen}
	{systemInfo}
	agentId={selectedServerId}
	{accessToken}
	onClose={() => { gpuModalOpen = false; }}
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
	.topology-overlay-title { left: 24px; pointer-events: auto; }
	.topology-overlay-live { right: 24px; pointer-events: auto; }

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
	.hub-toggle-mode-static {
		grid-template-columns: 8px auto minmax(110px, 1fr);
		width: 100%;
	}

	.hub-toggle-mode-static .dot { background: #cbd5e1; box-shadow: 0 0 4px rgba(203, 213, 225, 0.25); }

	.mode-value {
		justify-self: end;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-secondary);
	}

	.hub-toggle .label {
		color: var(--text-primary);
	}

	.hub-select {
		display: grid;
		grid-template-columns: auto minmax(108px, 1fr);
		align-items: center;
		gap: 10px;
		width: 100%;
		font-size: 12px;
		font-weight: 600;
		color: var(--text-secondary);
	}

	.hub-select .label {
		color: var(--text-primary);
	}

	.hub-select select {
		width: 100%;
		padding: 6px 8px;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: rgba(22, 27, 34, 0.82);
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 600;
		outline: none;
	}

	.hub-select select:focus {
		border-color: var(--accent);
		box-shadow: 0 0 0 1px rgba(48, 213, 200, 0.25);
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
