<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import {
		fleetAgents,
		fleetConnected,
		fleetError,
		fleetHistory,
		fleetLoading,
		fleetSummary,
		lastFleetUpdate,
		loadSelectedAgent,
		refreshFleet,
		setFleetRange,
		startFleetMonitoring,
		stopFleetMonitoring,
		type FleetAgentRow,
		type TimeRange,
	} from '$lib/stores/fleet-store';
	import { connectGlobal, disconnectGlobal, seedActiveAgents, seedStatusEvents } from '$lib/stores/global-events';
	import { rangeBucketLabel, rangeLabel } from '$lib/utils/fleet-format';
	import FleetStatusBar from '$lib/components/fleet/FleetStatusBar.svelte';
	import FleetCardRotator from '$lib/components/fleet/FleetCardRotator.svelte';
	import AgentHealthTable from '$lib/components/fleet/AgentHealthTable.svelte';
	import TimeRangeSelector from '$lib/components/fleet/TimeRangeSelector.svelte';
	import MetricHelp from '$lib/components/fleet/MetricHelp.svelte';
	import AdminHeader from '$lib/components/AdminHeader.svelte';
	import StatusToasts from '$lib/components/StatusToasts.svelte';
	import LoadingOverlay from '$lib/components/LoadingOverlay.svelte';
	import logoHypercube from '$lib/assets/logo_hypercube.png';

	let range = $state<TimeRange>('1h');
	let selectedAgentId = $state<string | null>(null);

	// Auth state
	let ready = $state(false);
	let isLoggedIn = $state(false);
	let username = $state('');
	let totalAgents = $state(0);
	let loginUsername = $state('');
	let loginPassword = $state('');
	let loginError = $state('');
	let redirecting = $state(false);

	let displayedAgents = $derived($fleetAgents);

	function decodeRole(token: string): string | null {
		try {
			return JSON.parse(atob(token.split('.')[1])).role ?? null;
		} catch {
			return null;
		}
	}

	function decodeUsername(token: string): string {
		try {
			return JSON.parse(atob(token.split('.')[1])).username ?? '';
		} catch {
			return '';
		}
	}

	async function loadAgentCount(token: string) {
		try {
			const res = await fetch(`${base}/api/agents/?status=approved&page_size=200`, {
				headers: { Authorization: `Bearer ${token}` },
			});
			if (res.ok) {
				const json = await res.json();
				totalAgents = json.data?.count ?? 0;
				const agents = json.data?.results ?? [];
				seedActiveAgents(agents.filter((agent: any) => agent.is_active).map((agent: any) => agent.id));
				seedStatusEvents(agents);
			}
		} catch {
			/* ignore */
		}
	}

	function selectAgent(agentId: string) {
		selectedAgentId = agentId;
		loadSelectedAgent(agentId);
	}

	async function changeRange(next: TimeRange) {
		range = next;
		await setFleetRange(next);
	}

	function open3d(agentId: string) {
		if (browser) localStorage.setItem('hc_selected_server', agentId);
		goto(`${base}/server-3d`);
	}

	function open2d(agentId: string) {
		if (browser) localStorage.setItem('hc_selected_server', agentId);
		goto(`${base}/server-2d`);
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
			const accessToken = json.data?.access || json.access;
			if (browser) localStorage.setItem('hc_access_token', accessToken);
			if (decodeRole(accessToken) === 'user') {
				redirecting = true;
				goto(`${base}/user`);
				return;
			}
			username = decodeUsername(accessToken);
			isLoggedIn = true;
			ready = true;
			connectGlobal(accessToken);
			loadAgentCount(accessToken);
			startFleetMonitoring(accessToken, range);
		} catch {
			loginError = 'Connection failed';
		}
	}

	function doLogout() {
		if (browser) {
			localStorage.removeItem('hc_access_token');
			localStorage.removeItem('hc_selected_server');
		}
		disconnectGlobal();
		stopFleetMonitoring();
		isLoggedIn = false;
		ready = false;
		username = '';
	}

	$effect(() => {
		const list = displayedAgents;
		if (list.length === 0) {
			selectedAgentId = null;
			return;
		}
		if (selectedAgentId && list.some((row: FleetAgentRow) => row.agent.id === selectedAgentId)) return;
		const firstAgentId = list[0].agent.id;
		selectedAgentId = firstAgentId;
		loadSelectedAgent(firstAgentId);
	});

	onMount(() => {
		if (!browser) return;
		const token = localStorage.getItem('hc_access_token');
		if (!token) {
			ready = true;
			return;
		}
		const role = decodeRole(token);
		if (role === 'user') {
			redirecting = true;
			goto(`${base}/user`);
			return;
		}
		if (role !== 'admin') {
			localStorage.removeItem('hc_access_token');
			ready = true;
			return;
		}
		username = decodeUsername(token);
		isLoggedIn = true;
		ready = true;
		connectGlobal(token);
		loadAgentCount(token);
		startFleetMonitoring(token, range);
	});

	onDestroy(stopFleetMonitoring);
</script>

<svelte:head>
	<title>전체 서버 모니터링 - HyperCube</title>
</svelte:head>

{#if redirecting}
	<LoadingOverlay text="이동 중" />
{:else if !ready}
	<LoadingOverlay text="초기화 중" />
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
{:else}
	<div class="admin-shell">
		<AdminHeader {totalAgents} {username} onLogout={doLogout} />
		<main class="admin-body">
			<div class="dashboard">
				<header class="page-head">
					<div class="title-block">
						<h1>전체 서버 모니터링</h1>
						<p>승인된 모든 서버의 리소스와 상태를 한 화면에서 확인합니다.</p>
					</div>
					<div class="head-actions">
						<span class="live-state" class:connected={$fleetConnected}>
							<span></span>
							{$fleetConnected ? '실시간 연결' : '연결 끊김'}
						</span>
						<div class="range-label">
							조회 범위
							<MetricHelp text="모든 그래프와 서버 카드 스파크라인이 보여주는 시간 범위입니다. 데이터는 15초마다 자동으로 갱신됩니다." placement="bottom-end" />
						</div>
						<TimeRangeSelector value={range} onChange={changeRange} />
						<span class="range-hint">{rangeLabel(range)} · {rangeBucketLabel(range)}</span>
						<button class="refresh" type="button" onclick={refreshFleet} disabled={$fleetLoading}>
							{$fleetLoading ? '갱신 중' : '새로고침'}
						</button>
					</div>
				</header>

				{#if $fleetError}
					<div class="error-box">대시보드를 갱신하지 못했습니다. {$fleetError}</div>
				{/if}

				<FleetStatusBar
					summary={$fleetSummary}
					history={$fleetHistory}
					lastUpdated={$lastFleetUpdate}
					loading={$fleetLoading}
					connected={$fleetConnected}
					{range}
				/>

				<div class="rotator-area">
					<FleetCardRotator agents={displayedAgents} selectedId={selectedAgentId} {range} onSelect={selectAgent} onOpen2d={open2d} onOpen3d={open3d} />
				</div>

				<div class="table-area">
					<AgentHealthTable agents={displayedAgents} selectedId={selectedAgentId} onSelect={selectAgent} onOpen2d={open2d} onOpen3d={open3d} />
				</div>
			</div>
		</main>
	</div>
	<StatusToasts />
{/if}

<style>
	.auth-page {
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: 24px;
		background: var(--bg-base);
	}
	.auth-card {
		width: min(420px, 100%);
		padding: 32px;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--bg-card);
		display: grid;
		gap: 14px;
	}
	.auth-logo {
		height: 36px;
		width: fit-content;
	}
	.auth-subtitle {
		color: var(--text-muted);
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.04em;
	}
	.auth-field {
		display: grid;
		gap: 6px;
		font-size: 12px;
		color: var(--text-secondary);
		font-weight: 700;
	}
	.auth-field input {
		height: 36px;
		padding: 0 10px;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--bg-base);
		color: var(--text-primary);
		font: inherit;
	}
	.auth-error {
		color: #fca5a5;
		font-size: 12px;
	}
	.auth-btn {
		height: 40px;
		border: none;
		border-radius: 8px;
		background: var(--accent);
		color: var(--bg-base);
		font-weight: 800;
		cursor: pointer;
	}

	.admin-shell {
		min-height: 100vh;
		display: flex;
		flex-direction: column;
		background: var(--bg-base);
	}
	.admin-body {
		flex: 1;
		overflow-y: auto;
	}

	.dashboard {
		--dash-pad: clamp(14px, 1vw, 24px);
		--dash-gap: clamp(8px, 0.7vh, 14px);
		box-sizing: border-box;
		width: 100%;
		min-height: calc(100vh - 48px);
		padding: var(--dash-pad);
		color: var(--text-primary);
		display: flex;
		flex-direction: column;
		gap: var(--dash-gap);
	}
	.rotator-area {
		flex: 0 0 auto;
		height: clamp(280px, 48vh, 580px);
		min-height: 0;
	}
	.table-area {
		flex: 0 0 auto;
	}
	.page-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: clamp(10px, 1vw, 18px);
		flex-wrap: wrap;
	}
	.title-block {
		min-width: 0;
	}
	h1 {
		margin: 0;
		font-size: clamp(16px, 1.15vw, 24px);
		font-weight: 850;
		color: var(--text-primary);
		letter-spacing: -0.1px;
	}
	p {
		margin: 3px 0 0;
		color: var(--text-muted);
		font-size: clamp(11px, 0.72vw, 14px);
	}
	.head-actions {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		justify-content: flex-end;
	}
	.live-state,
	.range-label {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: var(--text-secondary);
		font-size: clamp(10px, 0.68vw, 12px);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.live-state span {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #64748b;
	}
	.live-state.connected span {
		background: #34d399;
		box-shadow: 0 0 8px rgba(52, 211, 153, 0.55);
	}
	.range-hint {
		color: var(--text-muted);
		font-size: clamp(10px, 0.68vw, 12px);
		font-weight: 600;
		padding: 0 4px;
	}
	.refresh {
		height: clamp(30px, 2.4vw, 38px);
		padding: 0 clamp(10px, 0.8vw, 18px);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--bg-card);
		color: var(--text-primary);
		font-size: clamp(11px, 0.72vw, 14px);
		font-weight: 800;
		cursor: pointer;
		transition: border-color 0.12s ease, background 0.12s ease;
	}
	.refresh:hover:not(:disabled) {
		border-color: var(--accent);
		background: rgba(48, 213, 200, 0.08);
	}
	.refresh:disabled {
		color: var(--text-muted);
		cursor: wait;
	}
	.error-box {
		padding: 10px 12px;
		border: 1px solid rgba(239, 68, 68, 0.35);
		border-radius: var(--radius-md);
		background: rgba(239, 68, 68, 0.08);
		color: #fecaca;
		font-size: 12px;
	}
	.rotator-area,
	.table-area {
		min-height: 0;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}
	.table-area :global(.table-panel) {
		height: 100%;
	}
	@media (max-width: 900px) {
		.dashboard {
			height: auto;
			overflow: visible;
		}
		.page-head {
			align-items: flex-start;
			flex-direction: column;
		}
		.head-actions {
			justify-content: flex-start;
		}
	}
</style>
