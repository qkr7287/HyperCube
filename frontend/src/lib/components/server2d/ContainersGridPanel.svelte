<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import AutoSlideCarousel from './AutoSlideCarousel.svelte';
	import { view, type Server2dStateFilter, stateFilterLabel } from '$lib/stores/server2d-view.svelte';

	type ContainerCard = {
		id: string;
		name: string;
		stack: string;
		stackColor: string;
		state: string;
		cpu: number;
		memory: number;
		network: number;
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
			container: any;
		}[];
	};

	let {
		stacks = [] as StackGroup[],
		pageSize = 16,
		intervalMs = 7000,
		onSelectContainer = (_container: any) => {},
	}: {
		stacks?: StackGroup[];
		pageSize?: number;
		intervalMs?: number;
		onSelectContainer?: (container: any) => void;
	} = $props();

	const soloed = $derived(view.soloStack);
	const search = $derived(view.searchQuery.trim().toLowerCase());
	const stateFilter = $derived(view.stateFilter);

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
					container: cell.container,
				});
			}
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
	const paused = $derived(Boolean(search) || stateFilter !== 'all' || Boolean(soloed));
</script>

<aside class="container-panel">
	<div class="head">
		<div class="title">
			<span>전체 컨테이너</span>
			<InfoTooltip text="서버의 모든 컨테이너를 한 화면에 표시합니다. 많을 때는 자동 슬라이드로 순환합니다. 검색·상태 필터·Solo를 지정하면 순환이 멈추고, 해제하면 다시 시작합니다. 각 카드 상단의 컬러 스트립은 해당 스택의 색입니다." placement="bottom-end" />
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

	<div class="body">
		{#if flatCards.length === 0}
			<div class="empty">조건에 맞는 컨테이너가 없습니다.</div>
		{:else}
			<AutoSlideCarousel items={flatCards} pageSize={pageSize} intervalMs={intervalMs} paused={paused}>
				{#snippet children(pageItems: ContainerCard[])}
					<div class="cards">
						{#each pageItems as cell (cell.id)}
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
								<div class="metrics">
									<em><b>CPU</b><u>{cell.cpu.toFixed(1)}%</u></em>
									<em><b>MEM</b><u>{cell.memory.toFixed(1)}%</u></em>
									<em><b>NET</b><u>{formatRate(cell.network)}</u></em>
								</div>
							</button>
						{/each}
					</div>
				{/snippet}
			</AutoSlideCarousel>
		{/if}
	</div>
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

	.body {
		min-height: 0;
		flex: 1;
		display: flex;
		flex-direction: column;
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
		gap: 7px;
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
</style>
