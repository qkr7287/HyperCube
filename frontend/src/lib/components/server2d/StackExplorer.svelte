<script lang="ts">
	import StackExplorerRow from './StackExplorerRow.svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import { view, type Server2dMetric, type Server2dSortMode, type Server2dStateFilter, stateFilterLabel } from '$lib/stores/server2d-view.svelte';

	type HeatCell = {
		id: string;
		name: string;
		state: string;
		cpu: number;
		memory: number;
		network: number;
		container: any;
	};

	type StackRowData = {
		name: string;
		color: string;
		running: number;
		total: number;
		problem: number;
		cpuAvg: number;
		memoryAvg: number;
		networkAvg: number;
		cells: HeatCell[];
	};

	let {
		stacks = [] as StackRowData[],
		onSelectContainer = (_container: any) => {},
	}: {
		stacks?: StackRowData[];
		onSelectContainer?: (container: any) => void;
	} = $props();

	function setMetric(next: Server2dMetric) {
		view.selectedMetric = next;
	}

	function setSort(next: Server2dSortMode) {
		view.sortMode = next;
	}

	function resetStateFilter() {
		view.stateFilter = 'all';
	}

	function stateMatches(cell: HeatCell, filter: Server2dStateFilter): boolean {
		if (filter === 'all') return true;
		if (filter === 'running') return cell.state === 'running';
		if (filter === 'paused') return cell.state === 'paused';
		if (filter === 'problem') return cell.state === 'dead' || cell.state === 'restarting';
		if (filter === 'stopped') return cell.state === 'exited' || cell.state === 'stopped';
		return true;
	}

	const search = $derived(view.searchQuery.trim().toLowerCase());
	const stateFilter = $derived(view.stateFilter);
	const sortMode = $derived(view.sortMode);
	const metric = $derived(view.selectedMetric);

	const filteredStacks = $derived.by(() => {
		return stacks
			.map((stack) => {
				const filteredCells = stack.cells.filter((cell) => {
					if (!stateMatches(cell, stateFilter)) return false;
					if (search) {
						const searchBlob = `${cell.name} ${stack.name}`.toLowerCase();
						if (!searchBlob.includes(search)) return false;
					}
					return true;
				});
				const problemCount = filteredCells.filter(
					(cell) => cell.state === 'dead' || cell.state === 'restarting',
				).length;
				return {
					...stack,
					cells: filteredCells,
					problem: problemCount,
					running: filteredCells.filter((cell) => cell.state === 'running').length,
					total: filteredCells.length,
				};
			})
			.filter((stack) => {
				if (search && !stack.name.toLowerCase().includes(search) && stack.cells.length === 0) {
					return false;
				}
				if (!search && stack.cells.length === 0 && stateFilter !== 'all') return false;
				return true;
			})
			.sort((a, b) => {
				if (sortMode === 'name') return a.name.localeCompare(b.name);
				if (sortMode === 'problem') return b.problem - a.problem;
				if (metric === 'memory') return b.memoryAvg - a.memoryAvg;
				if (metric === 'network') return b.networkAvg - a.networkAvg;
				return b.cpuAvg - a.cpuAvg;
			});
	});

	const networkMax = $derived(
		Math.max(
			1,
			...stacks.flatMap((stack) => stack.cells.map((cell) => cell.network)),
		),
	);

	const totalShown = $derived(filteredStacks.reduce((sum, stack) => sum + stack.total, 0));
</script>

<section class="explorer">
	<div class="head">
		<div class="title">
			스택 Explorer
			<InfoTooltip text="서버의 모든 스택(Docker Compose 프로젝트)과 그 안의 컨테이너를 한 줄씩 보여줍니다. 행을 가리키면(hover) 우측 추이 차트/산점도가 해당 스택만 보여주고, 행을 클릭하면 아래에 컨테이너 카드가 펼쳐집니다." placement="bottom-start" />
		</div>
		<small class="subtitle">{filteredStacks.length}개 스택 · {totalShown}개 컨테이너</small>
	</div>

	<div class="controls">
		<div class="metric-toggle" role="tablist" aria-label="열지도 지표">
			{#each ['cpu', 'memory', 'network'] as key (key)}
				<button
					type="button"
					role="tab"
					aria-selected={metric === key}
					class:active={metric === key}
					onclick={() => setMetric(key as Server2dMetric)}
				>
					{key === 'cpu' ? 'CPU' : key === 'memory' ? '메모리' : '트래픽'}
				</button>
			{/each}
		</div>
		<div class="sort-toggle" role="tablist" aria-label="정렬">
			{#each ['load', 'problem', 'name'] as key (key)}
				<button
					type="button"
					role="tab"
					aria-selected={sortMode === key}
					class:active={sortMode === key}
					onclick={() => setSort(key as Server2dSortMode)}
				>
					{key === 'load' ? '부하순' : key === 'problem' ? '문제순' : '이름순'}
				</button>
			{/each}
		</div>
		<input
			type="search"
			placeholder="스택/컨테이너 이름 검색"
			bind:value={view.searchQuery}
			aria-label="스택 및 컨테이너 검색"
		/>
		{#if stateFilter !== 'all'}
			<button type="button" class="chip-reset" onclick={resetStateFilter}>
				상태: {stateFilterLabel(stateFilter)} ✕
			</button>
		{/if}
	</div>

	<div class="body" role="list">
		{#each filteredStacks as stack (stack.name)}
			<StackExplorerRow
				{stack}
				networkMax={networkMax}
				metric={metric}
				onSelectContainer={onSelectContainer}
			/>
		{/each}
		{#if filteredStacks.length === 0}
			<div class="empty">조건에 맞는 스택 또는 컨테이너가 없습니다. 검색어와 필터를 확인하세요.</div>
		{/if}
	</div>
</section>

<style>
	.explorer {
		display: flex;
		flex-direction: column;
		gap: 8px;
		height: 100%;
		min-height: 0;
	}

	.head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 8px;
	}

	.title {
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 850;
		display: inline-flex;
		align-items: center;
	}

	.subtitle {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
	}

	.controls {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
	}

	.metric-toggle,
	.sort-toggle {
		display: inline-flex;
		border: 1px solid rgba(100, 116, 139, 0.24);
		border-radius: 999px;
		padding: 2px;
		background: rgba(15, 23, 42, 0.6);
	}

	.metric-toggle button,
	.sort-toggle button {
		border: none;
		background: transparent;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		padding: 4px 10px;
		border-radius: 999px;
		cursor: pointer;
	}

	.metric-toggle button.active,
	.sort-toggle button.active {
		background: rgba(48, 213, 200, 0.18);
		color: #30d5c8;
	}

	.controls input[type='search'] {
		flex: 1 1 180px;
		min-width: 160px;
		height: 28px;
		padding: 0 10px;
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
		height: 26px;
		padding: 0 10px;
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
		display: flex;
		flex-direction: column;
		gap: 6px;
		overflow-y: auto;
		min-height: 0;
		padding-right: 2px;
	}

	.body::-webkit-scrollbar {
		width: 6px;
	}
	.body::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.24);
		border-radius: 3px;
	}

	.empty {
		padding: 18px;
		text-align: center;
		color: var(--text-muted);
		font-size: 11px;
		border: 1px dashed rgba(100, 116, 139, 0.3);
		border-radius: 8px;
	}
</style>
