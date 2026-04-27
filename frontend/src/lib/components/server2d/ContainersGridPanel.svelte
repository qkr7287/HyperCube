<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import SortDirToggle from './SortDirToggle.svelte';
	import {
		view,
		type Server2dStateFilter,
		type Server2dContainerSort,
		type Server2dSortDir,
		stateFilterLabel,
	} from '$lib/stores/server2d-view.svelte';

	type ContainerCard = {
		id: string;
		name: string;
		stack: string;
		stackColor: string;
		state: string;
		cpu: number;
		memory: number;
		network: number;
		gpu: number | null;
		gpuMemoryUsed?: number | null;
		gpuMemoryTotal?: number | null;
		container: any;
	};

	type StackGroup = {
		name: string;
		color: string;
		running: number;
		total: number;
		containers: {
			id: string;
			name: string;
			state: string;
			cpu: number;
			memory: number;
			network: number;
			gpu?: number | null;
			gpuMemoryUsed?: number | null;
			gpuMemoryTotal?: number | null;
			container: any;
		}[];
	};

	let {
		stacks = [] as StackGroup[],
		metricRotateMs = 27000,
		onSelectContainer = (_container: any) => {},
	}: {
		stacks?: StackGroup[];
		metricRotateMs?: number;
		onSelectContainer?: (container: any) => void;
	} = $props();

	const METRIC_TICK_MS = 80;
	const ROTATION_CYCLE: Server2dContainerSort[] = ['total', 'cpu', 'memory', 'network', 'gpu'];

	const soloed = $derived(view.soloStack);
	const search = $derived(view.searchQuery.trim().toLowerCase());
	const stateFilter = $derived(view.stateFilter);
	const containerSort = $derived(view.containerSort);
	const containerSortDir = $derived(view.containerSortDir);
	let scrollContainer = $state<HTMLDivElement | null>(null);
	let metricProgress = $state(0);
	let metricTimer: ReturnType<typeof setInterval> | null = null;

	const metricAutoPaused = $derived(view.containersPaused);
	const metricRotating = $derived(!metricAutoPaused);

	function scrollToTop() {
		if (scrollContainer) scrollContainer.scrollTop = 0;
	}

	function nextMetric(current: Server2dContainerSort, gpuAllowed: boolean): Server2dContainerSort {
		const cycle = gpuAllowed ? ROTATION_CYCLE : ROTATION_CYCLE.filter((m) => m !== 'gpu');
		const idx = cycle.indexOf(current as Server2dContainerSort);
		const start = idx === -1 ? -1 : idx;
		return cycle[(start + 1) % cycle.length];
	}

	function advanceMetric() {
		view.containerSort = nextMetric(view.containerSort, hasGpuData);
		metricProgress = 0;
		scrollToTop();
	}

	function metricTick() {
		if (!metricRotating) return;
		const steps = Math.max(1, Math.floor(metricRotateMs / METRIC_TICK_MS));
		const next = metricProgress + 100 / steps;
		if (next >= 100) advanceMetric();
		else metricProgress = next;
	}

	function togglePause() {
		view.containersPaused = !view.containersPaused;
		metricProgress = 0;
	}

	function setContainerSort(next: Server2dContainerSort) {
		view.containerSort = view.containerSort === next ? 'total' : next;
		view.containersPaused = true;
		metricProgress = 0;
		scrollToTop();
	}

	function setContainerSortDir(next: Server2dSortDir) {
		view.containerSortDir = next;
		view.containersPaused = true;
		metricProgress = 0;
		scrollToTop();
	}

	$effect(() => {
		metricRotateMs;
		if (metricTimer) clearInterval(metricTimer);
		metricTimer = setInterval(metricTick, METRIC_TICK_MS);
		return () => {
			if (metricTimer) clearInterval(metricTimer);
		};
	});

	onMount(() => {
		metricTimer = setInterval(metricTick, METRIC_TICK_MS);
	});

	onDestroy(() => {
		if (metricTimer) clearInterval(metricTimer);
	});

	function sortKey(card: ContainerCard, mode: Server2dContainerSort): number {
		if (mode === 'gpu') return typeof card.gpu === 'number' ? card.gpu : -1;
		if (mode === 'memory') return card.memory;
		if (mode === 'cpu') return card.cpu;
		if (mode === 'network') return card.network;
		return 0;
	}

	function isGpuNull(card: ContainerCard): boolean {
		return card.gpu === null || card.gpu === undefined;
	}

	function stateClass(state: string): string {
		if (state === 'running') return 'running';
		if (state === 'paused') return 'paused';
		if (state === 'dead' || state === 'restarting') return 'problem';
		return 'stopped';
	}

	function stateLabel(state: string): string {
		if (state === 'running') return '실행';
		if (state === 'exited' || state === 'stopped') return '중지';
		if (state === 'paused') return '일시정지';
		if (state === 'restarting') return '재시작';
		if (state === 'dead') return '장애';
		return state || '-';
	}

	function formatRate(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0';
		const units = ['B', 'K', 'M', 'G'];
		let next = value;
		let idx = 0;
		while (next >= 1024 && idx < units.length - 1) {
			next /= 1024;
			idx += 1;
		}
		return `${next.toFixed(next >= 10 || idx === 0 ? 0 : 1)}${units[idx]}`;
	}

	function matchesStateFilter(state: string, filter: Server2dStateFilter): boolean {
		if (filter === 'all') return true;
		if (filter === 'running') return state === 'running';
		if (filter === 'paused') return state === 'paused';
		if (filter === 'problem') return state === 'dead' || state === 'restarting';
		if (filter === 'stopped') return state === 'exited' || state === 'stopped';
		return true;
	}

	const flatCards = $derived.by<ContainerCard[]>(() => {
		const out: ContainerCard[] = [];
		for (const stack of stacks) {
			if (soloed && stack.name !== soloed) continue;
			for (const cell of stack.containers) {
				if (!matchesStateFilter(cell.state, stateFilter)) continue;
				if (search) {
					const blob = `${cell.name} ${stack.name}`.toLowerCase();
					if (!blob.includes(search)) continue;
				}
				out.push({
					id: cell.id,
					name: cell.name,
					stack: stack.name,
					stackColor: stack.color,
					state: cell.state,
					cpu: cell.cpu,
					memory: cell.memory,
					network: cell.network,
					gpu: cell.gpu === null || cell.gpu === undefined ? null : Number(cell.gpu),
					gpuMemoryUsed: cell.gpuMemoryUsed ?? null,
					gpuMemoryTotal: cell.gpuMemoryTotal ?? null,
					container: cell.container,
				});
			}
		}
		if (containerSort !== 'default') {
			const sign = containerSortDir === 'asc' ? 1 : -1;
			const netMax = Math.max(1, ...out.map((c) => c.network));
			const score = (c: ContainerCard) => {
				if (containerSort === 'total') {
					const gpu = typeof c.gpu === 'number' ? c.gpu : 0;
					const netPct = Math.min(100, (c.network / netMax) * 100);
					return c.cpu + c.memory + gpu + netPct;
				}
				return sortKey(c, containerSort);
			};
			out.sort((a, b) => {
				if (containerSort === 'gpu') {
					const aNull = isGpuNull(a);
					const bNull = isGpuNull(b);
					if (aNull && !bNull) return 1;
					if (!aNull && bNull) return -1;
					if (aNull && bNull) return 0;
				}
				return sign * (score(a) - score(b));
			});
		}
		return out;
	});

	function resetStateFilter() {
		view.stateFilter = 'all';
	}

	function clearSolo() {
		view.soloStack = null;
	}

	const totalVisible = $derived(flatCards.length);
	const hasGpuData = $derived(flatCards.some((card) => typeof card.gpu === 'number'));
</script>

<aside class="container-panel">
	<div class="head">
		<div class="title">
			<span>전체 컨테이너</span>
			<InfoTooltip text={`서버의 모든 컨테이너를 한 화면에.\n\n• 세로 스크롤로 전체 탐색\n• TOTAL/CPU/MEM/NET/GPU 정렬 + 오름·내림 토글\n• 카드 왼쪽 컬러 스트립 = 소속 스택\n• 카드 클릭 = 상세 모달`} placement="bottom-end" />
		</div>
		<small>{totalVisible}개 표시</small>
	</div>

	<div class="controls">
		<input
			type="search"
			placeholder="컨테이너 · 스택 검색"
			bind:value={view.searchQuery}
			aria-label="컨테이너 검색"
		/>
		{#if stateFilter !== 'all'}
			<button type="button" class="chip-reset" onclick={resetStateFilter}>
				상태: {stateFilterLabel(stateFilter)} ✕
			</button>
		{/if}
		{#if soloed}
			<button type="button" class="chip-reset" onclick={clearSolo}>
				Solo: {soloed} ✕
			</button>
		{/if}
	</div>

	<div class="sort-row" role="group" aria-label="컨테이너 정렬">
		<div class="sort-chips">
			<small class="sort-label">정렬</small>
			<button
				type="button"
				class="sort-chip"
				class:active={containerSort === 'total'}
				title="종합 사용량(CPU+MEM+NET%+GPU) 우선"
				onclick={() => setContainerSort('total')}
			>TOTAL</button>
			<button
				type="button"
				class="sort-chip"
				class:active={containerSort === 'cpu'}
				title="CPU 사용량 우선"
				onclick={() => setContainerSort('cpu')}
			>CPU</button>
			<button
				type="button"
				class="sort-chip"
				class:active={containerSort === 'memory'}
				title="메모리 사용량 우선"
				onclick={() => setContainerSort('memory')}
			>MEM</button>
			<button
				type="button"
				class="sort-chip"
				class:active={containerSort === 'network'}
				title="네트워크 트래픽 우선"
				onclick={() => setContainerSort('network')}
			>NET</button>
			<button
				type="button"
				class="sort-chip"
				class:active={containerSort === 'gpu'}
				disabled={!hasGpuData}
				title={hasGpuData ? 'GPU 사용량 우선' : 'GPU 데이터 없음'}
				onclick={() => setContainerSort('gpu')}
			>GPU</button>
		</div>
		<SortDirToggle value={containerSortDir} onChange={setContainerSortDir} />
	</div>

	<div class="body">
		{#if flatCards.length === 0}
			<div class="empty">조건에 맞는 컨테이너가 없습니다.</div>
		{:else}
			<div class="cards" bind:this={scrollContainer}>
				{#each flatCards as cell (cell.id)}
					<button
						type="button"
						class={`card ${stateClass(cell.state)}`}
						style={`--stack-color:${cell.stackColor}`}
						onclick={() => onSelectContainer(cell.container)}
					>
						<div class="stack-bar"></div>
						<div class="card-head">
							<div class="card-identity">
								<i class={`dot ${stateClass(cell.state)}`}></i>
								<strong>{cell.name}</strong>
							</div>
							<small class={`state ${stateClass(cell.state)}`}>{stateLabel(cell.state)}</small>
						</div>
						<small class="stack-tag">{cell.stack}</small>
						<div class="metrics" class:has-gpu={typeof cell.gpu === 'number'}>
							<em class:hot={containerSort === 'cpu'}><b>CPU</b><u>{cell.cpu.toFixed(1)}%</u></em>
							<em class:hot={containerSort === 'memory'}><b>MEM</b><u>{cell.memory.toFixed(1)}%</u></em>
							{#if containerSort === 'gpu'}
								<em class="hot" class:dim={cell.gpu === null}><b>GPU</b><u>{cell.gpu === null ? '—' : `${(cell.gpu as number).toFixed(1)}%`}</u></em>
							{:else if typeof cell.gpu === 'number' && cell.gpu > 0 && containerSort !== 'network'}
								<em><b>GPU</b><u>{cell.gpu.toFixed(1)}%</u></em>
							{:else}
								<em class:hot={containerSort === 'network'}><b>NET</b><u>{formatRate(cell.network)}</u></em>
							{/if}
						</div>
					</button>
				{/each}
			</div>
		{/if}
	</div>

	{#if flatCards.length > 0}
		<div class="scroll-foot">
			<button
				type="button"
				class="scroll-pause"
				class:paused={metricAutoPaused}
				title={metricAutoPaused ? '정렬 자동 전환 재개' : '정렬 자동 전환 일시정지'}
				aria-label={metricAutoPaused ? '재개' : '일시정지'}
				onclick={togglePause}
			>
				{#if metricAutoPaused}
					<svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor"><polygon points="6,4 20,12 6,20"/></svg>
					<span>재생</span>
				{:else}
					<svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>
					<span>정지</span>
				{/if}
			</button>
			<div class="scroll-progress" class:idle={!metricRotating} aria-hidden="true">
				<i style={`width:${metricRotating ? metricProgress.toFixed(1) : metricAutoPaused ? 0 : 100}%`}></i>
			</div>
		</div>
	{/if}
</aside>

<style>
	.container-panel {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
		min-width: 0;
		height: 100%;
	}

	.head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 8px;
	}

	.title {
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 900;
		display: inline-flex;
		align-items: center;
		letter-spacing: 0.02em;
	}

	.head small {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
	}

	.controls {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
	}

	.controls input[type='search'] {
		flex: 1 1 160px;
		min-width: 140px;
		height: 30px;
		padding: 0 12px;
		border: 1px solid var(--border);
		border-radius: 999px;
		background: rgba(15, 23, 42, 0.65);
		color: var(--text-primary);
		font-size: 12px;
	}

	.controls input[type='search']:focus {
		outline: none;
		border-color: rgba(48, 213, 200, 0.5);
	}

	.chip-reset {
		padding: 4px 10px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 800;
		background: rgba(48, 213, 200, 0.14);
		color: #30d5c8;
		border: 1px solid rgba(48, 213, 200, 0.4);
		cursor: pointer;
	}

	.chip-reset:hover {
		background: rgba(48, 213, 200, 0.22);
	}

	.sort-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		flex-wrap: wrap;
	}

	.sort-chips {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		flex-wrap: wrap;
	}

	.sort-label {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.04em;
		margin-right: 2px;
	}

	.sort-chip {
		height: 22px;
		padding: 0 9px;
		border: 1px solid rgba(100, 116, 139, 0.35);
		border-radius: 999px;
		background: rgba(15, 23, 42, 0.7);
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.04em;
		cursor: pointer;
	}

	.sort-chip:hover:not(:disabled) {
		color: var(--text-secondary);
		border-color: rgba(48, 213, 200, 0.45);
	}

	.sort-chip.active {
		background: rgba(48, 213, 200, 0.22);
		border-color: rgba(48, 213, 200, 0.6);
		color: #30d5c8;
	}

	.sort-chip:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.body {
		min-height: 0;
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
		grid-auto-rows: min-content;
		gap: 6px;
		overflow-y: auto;
		min-height: 0;
		flex: 1;
		padding-right: 2px;
		align-content: start;
	}

	.cards::-webkit-scrollbar {
		width: 4px;
	}

	.cards::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.22);
		border-radius: 2px;
	}

	.card {
		position: relative;
		display: grid;
		gap: 3px;
		padding: 6px 9px 7px 12px;
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.6);
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
		min-width: 0;
		overflow: hidden;
		transition: border-color 0.12s ease, transform 0.12s ease, box-shadow 0.12s ease;
	}

	.card:hover {
		border-color: rgba(48, 213, 200, 0.45);
		transform: translateY(-1px);
		box-shadow: 0 6px 18px rgba(15, 23, 42, 0.5);
	}

	.stack-bar {
		position: absolute;
		inset: 0 auto 0 0;
		width: 4px;
		background: var(--stack-color, #30d5c8);
		box-shadow: 0 0 8px color-mix(in srgb, var(--stack-color, #30d5c8) 55%, transparent);
	}

	.card.running { border-left-color: transparent; }
	.card.paused { border-color: rgba(251, 191, 36, 0.32); }
	.card.problem { border-color: rgba(248, 113, 113, 0.45); }
	.card.stopped { border-color: rgba(148, 163, 184, 0.3); }

	.card-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
		min-width: 0;
	}

	.card-identity {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex: 0 0 auto;
	}
	.dot.running { background: #34d399; box-shadow: 0 0 8px rgba(52, 211, 153, 0.6); }
	.dot.paused { background: #fbbf24; box-shadow: 0 0 8px rgba(251, 191, 36, 0.6); }
	.dot.problem { background: #f87171; box-shadow: 0 0 8px rgba(248, 113, 113, 0.6); }
	.dot.stopped { background: #94a3b8; }

	.card strong {
		font-size: 12px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.stack-tag {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.metrics {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 3px;
	}

	.metrics em {
		font-style: normal;
		display: inline-flex;
		align-items: baseline;
		gap: 3px;
		padding: 3px 6px;
		border-radius: 5px;
		background: rgba(2, 6, 23, 0.5);
		font-size: 10px;
		font-weight: 800;
		min-width: 0;
	}

	.metrics em.hot {
		background: rgba(48, 213, 200, 0.22);
		box-shadow: inset 0 0 0 1px rgba(48, 213, 200, 0.45);
	}

	.metrics em.hot u {
		color: #30d5c8;
	}

	.metrics em.dim u {
		color: var(--text-muted);
	}

	.metrics b {
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 800;
		flex: 0 0 auto;
	}

	.metrics u {
		text-decoration: none;
		color: var(--text-primary);
		font-size: 10px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.state {
		font-size: 10px;
		font-weight: 800;
		text-align: right;
		flex: 0 0 auto;
	}

	.state.running { color: #34d399; }
	.state.paused { color: #fbbf24; }
	.state.problem { color: #f87171; }
	.state.stopped { color: #94a3b8; }

	.empty {
		padding: 16px;
		border: 1px dashed rgba(100, 116, 139, 0.28);
		border-radius: 8px;
		color: var(--text-muted);
		font-size: 12px;
		text-align: center;
	}

	.scroll-foot {
		flex: 0 0 auto;
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 8px;
		padding-top: 6px;
		border-top: 1px dashed rgba(100, 116, 139, 0.25);
	}

	.scroll-pause {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 5px;
		height: 22px;
		padding: 0 9px 0 8px;
		border: 1px solid rgba(248, 113, 113, 0.5);
		border-radius: 999px;
		background: rgba(248, 113, 113, 0.16);
		color: #f87171;
		cursor: pointer;
		flex: 0 0 auto;
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.02em;
		white-space: nowrap;
		transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
	}

	.scroll-pause:hover {
		background: rgba(248, 113, 113, 0.26);
	}

	.scroll-pause.paused {
		background: rgba(52, 211, 153, 0.2);
		border-color: rgba(52, 211, 153, 0.6);
		color: #34d399;
		box-shadow: 0 0 12px rgba(52, 211, 153, 0.35);
		animation: scroll-paused-glow 1.6s ease-in-out infinite;
	}

	.scroll-pause.paused:hover {
		background: rgba(52, 211, 153, 0.3);
	}

	@keyframes scroll-paused-glow {
		0%, 100% { box-shadow: 0 0 12px rgba(52, 211, 153, 0.3); }
		50% { box-shadow: 0 0 18px rgba(52, 211, 153, 0.55); }
	}

	.scroll-pause span {
		line-height: 1;
	}

	.scroll-progress {
		flex: 1;
		height: 5px;
		border-radius: 999px;
		background: rgba(30, 41, 59, 0.65);
		overflow: hidden;
	}

	.scroll-progress i {
		display: block;
		height: 100%;
		background: linear-gradient(90deg, #30d5c8, #60a5fa);
		width: 0%;
		transition: width 80ms linear;
	}

	.scroll-progress.idle i {
		background: repeating-linear-gradient(
			-45deg,
			rgba(248, 113, 113, 0.4) 0,
			rgba(248, 113, 113, 0.4) 4px,
			rgba(248, 113, 113, 0.15) 4px,
			rgba(248, 113, 113, 0.15) 8px
		);
	}
</style>
