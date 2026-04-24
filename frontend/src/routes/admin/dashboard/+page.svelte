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
	import { rangeBucketLabel, rangeLabel } from '$lib/utils/fleet-format';
	import FleetStatusBar from '$lib/components/fleet/FleetStatusBar.svelte';
	import FleetCardRotator from '$lib/components/fleet/FleetCardRotator.svelte';
	import AgentHealthTable from '$lib/components/fleet/AgentHealthTable.svelte';
	import TimeRangeSelector from '$lib/components/fleet/TimeRangeSelector.svelte';
	import MetricHelp from '$lib/components/fleet/MetricHelp.svelte';

	let range = $state<TimeRange>('1h');
	let selectedAgentId = $state<string | null>(null);

	let displayedAgents = $derived($fleetAgents);

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
		goto(`${base}/`);
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
		if (token) startFleetMonitoring(token, range);
	});

	onDestroy(stopFleetMonitoring);
</script>

<svelte:head>
	<title>전체 서버 모니터링 - HyperCube</title>
</svelte:head>

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
		<FleetCardRotator agents={displayedAgents} selectedId={selectedAgentId} {range} onSelect={selectAgent} onOpen3d={open3d} />
	</div>

	<div class="table-area">
		<AgentHealthTable agents={displayedAgents} selectedId={selectedAgentId} onSelect={selectAgent} onOpen3d={open3d} />
	</div>
</div>

<style>
	.dashboard {
		--dash-pad: clamp(14px, 1vw, 24px);
		--dash-gap: clamp(8px, 0.7vh, 14px);

		box-sizing: border-box;
		width: 100%;
		/* 고정 viewport 높이 제약 제거 — 테이블이 길어지면 페이지 전체가 스크롤되도록. */
		min-height: calc(100vh - 48px);
		padding: var(--dash-pad);
		color: var(--text-primary);
		display: flex;
		flex-direction: column;
		gap: var(--dash-gap);
	}
	.rotator-area {
		/* rotator 는 viewport 의 고정 비율. medium 카드가 2 row (count=3/4/5) 에서
		   세로 공간 필요 → 48vh 로 복원 (44vh 는 content 가 잘림). */
		flex: 0 0 auto;
		height: clamp(280px, 48vh, 580px);
		min-height: 0;
	}
	.table-area {
		/* 내부 스크롤 대신 테이블 전체 높이가 자연스럽게 늘어남 → 페이지 스크롤로 이동. */
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
