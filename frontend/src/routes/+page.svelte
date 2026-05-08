<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
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
	import {
		EACH_STATUS_ORDER,
		buildSimulatedAgents,
		isSimulatedAgentId,
	} from '$lib/utils/fleet-simulate';
	import {
		connectGlobal,
		disconnectGlobal,
		seedActiveAgents,
		seedStatusEvents,
		seedStatusEventsFromBackend,
	} from '$lib/stores/global-events';
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

	type ViewMode = 'card' | 'list';
	const VIEW_MODE_KEY = 'hc_fleet_view_mode';
	let viewMode = $state<ViewMode>('card');

	function setViewMode(next: ViewMode) {
		viewMode = next;
		if (browser) localStorage.setItem(VIEW_MODE_KEY, next);
	}

	// Auth state
	let ready = $state(false);
	let isLoggedIn = $state(false);
	let username = $state('');
	let totalAgents = $state(0);
	let loginUsername = $state('');
	let loginPassword = $state('');
	let loginError = $state('');
	let loginLoading = $state(false);
	let redirecting = $state(false);

	// URL flag 기반 가상 서버 주입 — 카드/테이블에만 머지되고 KPI 바(상단 요약)는
	// 실제 fleet 만 집계한다.
	//   ?sim=N        → N대 가상 서버 (1~200)
	//   ?sim=each     → 상태별 1대씩 (critical / warning / stale / offline / healthy)
	//   ?only=sim     → 실제 fleet 숨기고 가상만
	let simMode = $derived($page.url.searchParams.get('sim') ?? '');
	let onlySim = $derived($page.url.searchParams.get('only') === 'sim');
	let simCount = $derived.by(() => {
		if (!simMode || simMode === 'each') return 0;
		const parsed = parseInt(simMode, 10);
		if (!Number.isFinite(parsed) || parsed <= 0) return 0;
		return Math.min(parsed, 200);
	});
	let simAgents = $derived.by(() => {
		if (simMode === 'each') return buildSimulatedAgents(0, 0, EACH_STATUS_ORDER);
		return simCount > 0 ? buildSimulatedAgents(simCount) : [];
	});
	let displayedAgents = $derived.by(() => {
		if (onlySim) return simAgents;
		if (simAgents.length === 0) return $fleetAgents;
		return [...$fleetAgents, ...simAgents];
	});

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
				// Fallback synthetic events from current is_active state — overridden
				// below if the persisted log is reachable.
				seedStatusEvents(agents);
			}
		} catch {
			/* ignore */
		}
		// Persisted transition log: covers events fired while the browser was
		// closed or the backend itself was down at the moment of transition.
		try {
			const res = await fetch(`${base}/api/agents/status-events/?limit=20`, {
				headers: { Authorization: `Bearer ${token}` },
			});
			if (res.ok) {
				const json = await res.json();
				const events = json.data ?? json.results ?? json ?? [];
				if (Array.isArray(events) && events.length > 0) {
					seedStatusEventsFromBackend(events);
				}
			}
		} catch {
			/* ignore */
		}
	}

	function selectAgent(agentId: string) {
		selectedAgentId = agentId;
		if (isSimulatedAgentId(agentId)) return;
		loadSelectedAgent(agentId);
	}

	async function changeRange(next: TimeRange) {
		range = next;
		await setFleetRange(next);
	}

	function open3d(agentId: string) {
		if (isSimulatedAgentId(agentId)) return;
		if (browser) localStorage.setItem('hc_selected_server', agentId);
		goto(`${base}/server-3d`);
	}

	function open2d(agentId: string) {
		if (isSimulatedAgentId(agentId)) return;
		if (browser) localStorage.setItem('hc_selected_server', agentId);
		goto(`${base}/server-2d`);
	}

	async function doLogin() {
		if (loginLoading) return;
		loginError = '';
		loginLoading = true;
		try {
			const res = await fetch(`${base}/api/auth/token/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username: loginUsername, password: loginPassword }),
			});
			const json = await res.json();
			if (!res.ok) {
				loginError = json.error?.detail || json.detail || '로그인 실패. 사용자명·비밀번호를 확인하세요.';
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
			loginError = '서버에 연결할 수 없습니다.';
		} finally {
			loginLoading = false;
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
		ready = true;
		redirecting = false;
		username = '';
		totalAgents = 0;
		loginError = '';
		loginLoading = false;
		loginPassword = '';
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
		if (!isSimulatedAgentId(firstAgentId)) loadSelectedAgent(firstAgentId);
	});

	onMount(() => {
		if (!browser) return;
		const savedView = localStorage.getItem(VIEW_MODE_KEY);
		if (savedView === 'card' || savedView === 'list') viewMode = savedView;
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
		<!-- background accents (radial gradients + grid lines) — 시각적 깊이 -->
		<div class="auth-bg" aria-hidden="true">
			<span class="bg-glow bg-glow-1"></span>
			<span class="bg-glow bg-glow-2"></span>
			<span class="bg-grid"></span>
		</div>

		<div class="auth-card">
			<header class="auth-header">
				<img class="auth-logo" src={logoHypercube} alt="HyperCube" />
				<p class="auth-tagline">Container Monitoring Platform</p>
			</header>

			<div class="auth-divider"></div>

			<form class="auth-form" onsubmit={(e) => { e.preventDefault(); doLogin(); }}>
				<h1 class="auth-title">로그인</h1>
				<p class="auth-hint">계정 정보를 입력하면 모니터링 대시보드로 이동합니다.</p>

				<div class="auth-field">
					<label for="login-user">사용자명</label>
					<div class="auth-input-wrap">
						<svg class="auth-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
							<circle cx="12" cy="7" r="4" />
						</svg>
						<input id="login-user" type="text" bind:value={loginUsername} placeholder="admin" autocomplete="username" disabled={loginLoading} />
					</div>
				</div>

				<div class="auth-field">
					<label for="login-pass">비밀번호</label>
					<div class="auth-input-wrap">
						<svg class="auth-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
							<path d="M7 11V7a5 5 0 0 1 10 0v4" />
						</svg>
						<input id="login-pass" type="password" bind:value={loginPassword} placeholder="••••••••" autocomplete="current-password" disabled={loginLoading} />
					</div>
				</div>

				{#if loginError}
					<p class="auth-error" role="alert">
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<circle cx="12" cy="12" r="10" />
							<line x1="12" y1="8" x2="12" y2="12" />
							<line x1="12" y1="16" x2="12.01" y2="16" />
						</svg>
						{loginError}
					</p>
				{/if}

				<button class="auth-btn" type="submit" disabled={loginLoading || !loginUsername || !loginPassword}>
					{#if loginLoading}
						<span class="auth-spinner" aria-hidden="true"></span>
						로그인 중...
					{:else}
						로그인
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
							<line x1="5" y1="12" x2="19" y2="12" />
							<polyline points="12 5 19 12 12 19" />
						</svg>
					{/if}
				</button>
			</form>

			<footer class="auth-footer">
				<span>HyperCube · Server Monitoring</span>
			</footer>
		</div>
	</div>
{:else if displayedAgents.length === 0 && $fleetLoading}
	<LoadingOverlay text="서버 정보 불러오는 중" />
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
							조회 단위
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

				{#if simAgents.length > 0}
					<div class="sim-banner">
						<span>
							가상 서버 <b>{simAgents.length}</b>대를 시뮬레이션 중입니다.
							{#if simMode === 'each'}(상태별 1대씩 — critical / warning / stale / offline / healthy){/if}
							{#if onlySim}
								실제 fleet 은 숨김 (<code>?only=sim</code>).
							{:else}
								실제 서버 <b>{$fleetAgents.length}</b>대와 함께 표시됩니다 (<code>?sim={simMode}</code>).
							{/if}
							상단 KPI 요약은 실제 fleet 만 집계합니다.
						</span>
						<a href="?" title="시뮬레이션 종료">시뮬레이션 종료</a>
					</div>
				{/if}

				<FleetStatusBar
					summary={$fleetSummary}
					history={$fleetHistory}
					lastUpdated={$lastFleetUpdate}
					loading={$fleetLoading}
					connected={$fleetConnected}
					{range}
				/>

				<div class="fleet-view">
					<div class="fleet-view-tabs" role="tablist" aria-label="서버 보기 방식">
						<button
							type="button"
							role="tab"
							class="fleet-tab"
							class:active={viewMode === 'card'}
							aria-selected={viewMode === 'card'}
							onclick={() => setViewMode('card')}
						>
							<svg class="fleet-tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<rect x="3" y="3" width="7" height="7" rx="1.5" />
								<rect x="14" y="3" width="7" height="7" rx="1.5" />
								<rect x="3" y="14" width="7" height="7" rx="1.5" />
								<rect x="14" y="14" width="7" height="7" rx="1.5" />
							</svg>
							<span>카드</span>
							<span class="fleet-tab-count">{displayedAgents.length}</span>
						</button>
						<button
							type="button"
							role="tab"
							class="fleet-tab"
							class:active={viewMode === 'list'}
							aria-selected={viewMode === 'list'}
							onclick={() => setViewMode('list')}
						>
							<svg class="fleet-tab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<line x1="8" y1="6" x2="21" y2="6" />
								<line x1="8" y1="12" x2="21" y2="12" />
								<line x1="8" y1="18" x2="21" y2="18" />
								<circle cx="4" cy="6" r="1.2" />
								<circle cx="4" cy="12" r="1.2" />
								<circle cx="4" cy="18" r="1.2" />
							</svg>
							<span>리스트</span>
							<span class="fleet-tab-count">{displayedAgents.length}</span>
						</button>
					</div>
					<div class="fleet-view-body">
						{#if viewMode === 'card'}
							<FleetCardRotator agents={displayedAgents} selectedId={selectedAgentId} {range} onSelect={selectAgent} onOpen2d={open2d} onOpen3d={open3d} />
						{:else}
							<AgentHealthTable agents={displayedAgents} selectedId={selectedAgentId} onSelect={selectAgent} onOpen2d={open2d} onOpen3d={open3d} />
						{/if}
					</div>
				</div>
			</div>
		</main>
	</div>
	<StatusToasts />
{/if}

<style>
	.auth-page {
		position: relative;
		min-height: 100vh;
		display: grid;
		place-items: center;
		padding: 24px;
		background: radial-gradient(circle at 20% 30%, rgba(48, 213, 200, 0.06), transparent 55%),
			radial-gradient(circle at 80% 70%, rgba(96, 165, 250, 0.05), transparent 55%),
			var(--bg-base);
		overflow: hidden;
	}
	.auth-bg {
		position: absolute;
		inset: 0;
		pointer-events: none;
		z-index: 0;
	}
	.bg-glow {
		position: absolute;
		border-radius: 50%;
		filter: blur(96px);
		opacity: 0.5;
	}
	.bg-glow-1 {
		width: 480px;
		height: 480px;
		top: -120px;
		left: -160px;
		background: radial-gradient(circle, rgba(48, 213, 200, 0.32), transparent 70%);
		animation: drift1 18s ease-in-out infinite;
	}
	.bg-glow-2 {
		width: 540px;
		height: 540px;
		bottom: -180px;
		right: -180px;
		background: radial-gradient(circle, rgba(96, 165, 250, 0.28), transparent 70%);
		animation: drift2 22s ease-in-out infinite;
	}
	@keyframes drift1 {
		0%, 100% { transform: translate(0, 0); }
		50% { transform: translate(40px, 30px); }
	}
	@keyframes drift2 {
		0%, 100% { transform: translate(0, 0); }
		50% { transform: translate(-30px, -40px); }
	}
	.bg-grid {
		position: absolute;
		inset: 0;
		background-image:
			linear-gradient(to right, rgba(100, 116, 139, 0.06) 1px, transparent 1px),
			linear-gradient(to bottom, rgba(100, 116, 139, 0.06) 1px, transparent 1px);
		background-size: 56px 56px;
		mask-image: radial-gradient(circle at center, black 30%, transparent 75%);
	}

	.auth-card {
		position: relative;
		z-index: 1;
		width: min(440px, 100%);
		padding: 36px 36px 24px;
		border: 1px solid rgba(48, 213, 200, 0.18);
		border-radius: 16px;
		background: linear-gradient(180deg, rgba(18, 23, 32, 0.85), rgba(13, 17, 23, 0.95));
		backdrop-filter: blur(12px);
		display: grid;
		gap: 20px;
		box-shadow:
			0 1px 0 rgba(255, 255, 255, 0.04) inset,
			0 24px 60px -20px rgba(0, 0, 0, 0.6),
			0 0 0 1px rgba(48, 213, 200, 0.04);
	}

	.auth-header {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		text-align: center;
	}
	.auth-logo {
		height: 44px;
		width: fit-content;
		filter: drop-shadow(0 0 12px rgba(48, 213, 200, 0.35));
	}
	.auth-tagline {
		margin: 0;
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.18em;
		text-transform: uppercase;
	}

	.auth-divider {
		height: 1px;
		background: linear-gradient(to right, transparent, rgba(48, 213, 200, 0.22), transparent);
	}

	.auth-form {
		display: grid;
		gap: 14px;
	}
	.auth-title {
		margin: 0;
		font-size: 18px;
		font-weight: 800;
		color: var(--text-primary);
		letter-spacing: -0.01em;
	}
	.auth-hint {
		margin: -8px 0 4px;
		color: var(--text-muted);
		font-size: 12px;
		font-weight: 600;
		line-height: 1.5;
	}

	.auth-field {
		display: grid;
		gap: 6px;
	}
	.auth-field label {
		font-size: 11px;
		font-weight: 800;
		color: var(--text-secondary);
		letter-spacing: 0.04em;
	}
	.auth-input-wrap {
		position: relative;
		display: flex;
		align-items: center;
	}
	.auth-icon {
		position: absolute;
		left: 12px;
		width: 16px;
		height: 16px;
		color: var(--text-muted);
		pointer-events: none;
		transition: color 0.15s ease;
	}
	.auth-input-wrap:focus-within .auth-icon {
		color: var(--accent);
	}
	.auth-field input {
		width: 100%;
		height: 42px;
		padding: 0 12px 0 38px;
		border: 1px solid rgba(100, 116, 139, 0.22);
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.6);
		color: var(--text-primary);
		font: inherit;
		font-size: 14px;
		transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease;
	}
	.auth-field input::placeholder {
		color: var(--text-muted);
		opacity: 0.6;
	}
	.auth-field input:hover:not(:disabled) {
		border-color: rgba(48, 213, 200, 0.3);
	}
	.auth-field input:focus {
		outline: none;
		border-color: var(--accent);
		background: rgba(13, 17, 23, 0.85);
		box-shadow: 0 0 0 3px rgba(48, 213, 200, 0.14);
	}
	.auth-field input:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.auth-error {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		padding: 10px 12px;
		border-radius: 8px;
		background: rgba(239, 68, 68, 0.12);
		border: 1px solid rgba(239, 68, 68, 0.22);
		color: #fca5a5;
		font-size: 12px;
		font-weight: 700;
		line-height: 1.4;
	}
	.auth-error svg {
		width: 16px;
		height: 16px;
		flex: 0 0 auto;
	}

	.auth-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		height: 44px;
		margin-top: 4px;
		border: none;
		border-radius: 10px;
		background: linear-gradient(135deg, var(--accent), #20a89c);
		color: var(--bg-base);
		font-family: inherit;
		font-size: 14px;
		font-weight: 800;
		letter-spacing: 0.02em;
		cursor: pointer;
		transition: transform 0.12s ease, box-shadow 0.15s ease, opacity 0.12s ease;
		box-shadow: 0 6px 20px -6px rgba(48, 213, 200, 0.5);
	}
	.auth-btn svg {
		width: 16px;
		height: 16px;
		transition: transform 0.15s ease;
	}
	.auth-btn:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: 0 10px 28px -8px rgba(48, 213, 200, 0.6);
	}
	.auth-btn:hover:not(:disabled) svg {
		transform: translateX(2px);
	}
	.auth-btn:active:not(:disabled) {
		transform: translateY(0);
	}
	.auth-btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
		box-shadow: none;
	}
	.auth-spinner {
		width: 14px;
		height: 14px;
		border: 2px solid rgba(13, 17, 23, 0.25);
		border-top-color: var(--bg-base);
		border-radius: 50%;
		animation: auth-spin 0.7s linear infinite;
	}
	@keyframes auth-spin {
		to { transform: rotate(360deg); }
	}

	.auth-footer {
		display: flex;
		justify-content: center;
		padding-top: 8px;
		border-top: 1px solid rgba(100, 116, 139, 0.1);
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
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
	.fleet-view {
		--tab-border: rgba(148, 163, 184, 0.22);
		flex: 1 1 0;
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
	}
	.fleet-view-tabs {
		display: flex;
		gap: 2px;
		padding: 0;
	}
	.fleet-tab {
		appearance: none;
		position: relative;
		bottom: -1px;
		display: inline-flex;
		align-items: center;
		gap: 8px;
		border: 1px solid var(--tab-border);
		border-bottom: 0;
		background: rgba(13, 17, 23, 0.4);
		color: var(--text-secondary);
		font-size: clamp(11px, 0.72vw, 13px);
		font-weight: 800;
		letter-spacing: 0.2px;
		padding: 9px 18px;
		border-top-left-radius: var(--radius-md);
		border-top-right-radius: var(--radius-md);
		cursor: pointer;
		transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
	}
	.fleet-tab:hover {
		color: var(--text-primary);
		background: rgba(48, 213, 200, 0.06);
		border-color: rgba(48, 213, 200, 0.3);
	}
	.fleet-tab.active {
		color: var(--accent);
		background: var(--bg-card);
		border-color: var(--tab-border);
		border-bottom-color: var(--bg-card);
	}
	.fleet-tab.active::before {
		content: '';
		position: absolute;
		top: 0;
		left: 10px;
		right: 10px;
		height: 2px;
		background: var(--accent);
		border-radius: 2px;
		box-shadow: 0 0 8px rgba(48, 213, 200, 0.5);
	}
	.fleet-tab-icon {
		width: 14px;
		height: 14px;
		flex: 0 0 auto;
		opacity: 0.85;
	}
	.fleet-tab.active .fleet-tab-icon {
		opacity: 1;
	}
	.fleet-tab-count {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 22px;
		height: 18px;
		padding: 0 6px;
		border-radius: var(--radius-full);
		background: rgba(148, 163, 184, 0.15);
		color: var(--text-secondary);
		font-size: 10px;
		font-weight: 700;
		letter-spacing: 0;
	}
	.fleet-tab.active .fleet-tab-count {
		background: rgba(48, 213, 200, 0.15);
		color: var(--accent);
	}
	.fleet-view-body {
		flex: 1 1 0;
		min-height: clamp(440px, 60vh, 760px);
		min-width: 0;
		display: flex;
		flex-direction: column;
		padding: clamp(12px, 0.9vw, 18px);
		border: 1px solid rgba(148, 163, 184, 0.32);
		border-radius: 0 var(--radius-md) var(--radius-md) var(--radius-md);
		background: var(--bg-card);
		box-shadow: 0 4px 18px rgba(0, 0, 0, 0.25);
		box-sizing: border-box;
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
		display: inline-flex;
		align-items: center;
		justify-content: center;
		color: var(--text-muted);
		font-size: clamp(10px, 0.68vw, 12px);
		font-weight: 600;
		padding: 0 4px;
		min-width: clamp(150px, 11vw, 200px);
		flex: 0 0 auto;
		white-space: nowrap;
		text-align: center;
	}
	.refresh {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		height: clamp(30px, 2.4vw, 38px);
		min-width: clamp(82px, 5.5vw, 100px);
		padding: 0 clamp(10px, 0.8vw, 18px);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--bg-card);
		color: var(--text-primary);
		font-size: clamp(11px, 0.72vw, 14px);
		font-weight: 800;
		cursor: pointer;
		flex: 0 0 auto;
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
	.sim-banner {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		padding: 8px 12px;
		border: 1px solid rgba(167, 139, 250, 0.35);
		border-radius: var(--radius-md);
		background: rgba(167, 139, 250, 0.08);
		color: #ddd6fe;
		font-size: 12px;
	}
	.sim-banner code {
		padding: 1px 5px;
		background: rgba(0, 0, 0, 0.3);
		border-radius: 4px;
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
	}
	.sim-banner a {
		color: #c4b5fd;
		text-decoration: none;
		font-weight: 700;
		white-space: nowrap;
	}
	.sim-banner a:hover {
		color: #ffffff;
	}
	.fleet-view-body :global(.table-panel) {
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
