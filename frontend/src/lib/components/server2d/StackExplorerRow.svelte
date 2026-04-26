<script lang="ts">
	import StackHeatStrip from './StackHeatStrip.svelte';
	import { view, type Server2dMetric } from '$lib/stores/server2d-view.svelte';

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
		stack,
		networkMax = 1,
		metric = 'cpu' as Server2dMetric,
		onSelectContainer = (_container: any) => {},
	}: {
		stack: StackRowData;
		networkMax?: number;
		metric?: Server2dMetric;
		onSelectContainer?: (container: any) => void;
	} = $props();

	const expanded = $derived(view.expandedStack === stack.name);

	function toggleExpand() {
		view.expandedStack = expanded ? null : stack.name;
	}

	function handleEnter() {
		view.soloStack = stack.name;
	}

	function handleLeave() {
		view.soloStack = null;
	}

	function formatRate(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let index = 0;
		while (next >= 1024 && index < units.length - 1) {
			next /= 1024;
			index += 1;
		}
		return `${next.toFixed(next >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
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
		if (state === 'restarting') return '재시작';
		if (state === 'dead') return '장애';
		if (state === 'paused') return '일시정지';
		return state || '-';
	}

	const networkPeak = $derived(Math.max(networkMax, 1));
</script>

<div
	class="row"
	class:expanded
	class:soloed={view.soloStack === stack.name}
	role="listitem"
	onmouseenter={handleEnter}
	onmouseleave={handleLeave}
>
	<button type="button" class="header" style={`--stack-color:${stack.color}`} onclick={toggleExpand}>
		<span class="stripe" aria-hidden="true"></span>
		<span class="name">
			<strong>{stack.name}</strong>
			<span class="counts">
				<em class="running">{stack.running}/{stack.total}</em>
				{#if stack.problem > 0}
					<em class="problem">문제 {stack.problem}</em>
				{/if}
			</span>
		</span>
		<div class="heat" aria-hidden="true">
			<StackHeatStrip
				cells={stack.cells}
				metric={metric}
				networkMax={networkPeak}
				onSelect={(container) => onSelectContainer(container)}
			/>
		</div>
		<div class="bars">
			<span>
				<b>CPU</b>
				<i class="mini"><u style={`width:${Math.min(100, stack.cpuAvg)}%`}></u></i>
				<u class="val">{stack.cpuAvg.toFixed(1)}%</u>
			</span>
			<span>
				<b>MEM</b>
				<i class="mini"><u style={`width:${Math.min(100, stack.memoryAvg)}%`}></u></i>
				<u class="val">{stack.memoryAvg.toFixed(1)}%</u>
			</span>
			<span>
				<b>NET</b>
				<i class="mini"><u style={`width:${Math.min(100, (stack.networkAvg / networkPeak) * 100)}%`}></u></i>
				<u class="val">{formatRate(stack.networkAvg)}</u>
			</span>
		</div>
		<span class="chevron" class:open={expanded} aria-hidden="true">▾</span>
	</button>

	{#if expanded}
		<div class="body">
			<div class="cards">
				{#each stack.cells as cell (cell.id)}
					<button
						type="button"
						class={`card ${stateClass(cell.state)}`}
						onclick={(event) => { event.stopPropagation(); onSelectContainer(cell.container); }}
					>
						<header>
							<span class="card-name">
								<i class={`dot ${stateClass(cell.state)}`}></i>
								<strong>{cell.name}</strong>
							</span>
							<span class="state">{stateLabel(cell.state)}</span>
						</header>
						<div class="card-metrics">
							<span><b>CPU</b><small>{cell.cpu.toFixed(1)}%</small></span>
							<span><b>MEM</b><small>{cell.memory.toFixed(1)}%</small></span>
							<span><b>NET</b><small>{formatRate(cell.network)}</small></span>
						</div>
					</button>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
	.row {
		display: flex;
		flex-direction: column;
		border: 1px solid rgba(100, 116, 139, 0.14);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.46);
		overflow: hidden;
		transition: border-color 0.12s ease, background-color 0.12s ease;
	}

	.row:hover {
		border-color: rgba(48, 213, 200, 0.28);
	}

	.row.soloed {
		border-color: rgba(48, 213, 200, 0.55);
		background: rgba(48, 213, 200, 0.06);
	}

	.row.expanded {
		border-color: rgba(48, 213, 200, 0.38);
	}

	.header {
		display: grid;
		grid-template-columns: 4px minmax(130px, 0.8fr) minmax(0, 1.6fr) minmax(190px, 1fr) 18px;
		align-items: center;
		gap: 10px;
		padding: 6px 10px 6px 0;
		border: none;
		background: transparent;
		color: var(--text-primary);
		cursor: pointer;
		text-align: left;
		min-height: 44px;
	}

	.stripe {
		height: 100%;
		min-height: 32px;
		background: var(--stack-color, #30d5c8);
		border-radius: 2px 0 0 2px;
	}

	.name {
		display: grid;
		gap: 2px;
		min-width: 0;
	}

	.name strong {
		font-size: 12px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.counts {
		display: inline-flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.counts em {
		font-style: normal;
		padding: 1px 6px;
		border-radius: 999px;
		background: rgba(2, 6, 23, 0.48);
		font-size: 10px;
		font-weight: 800;
		color: var(--text-secondary);
	}

	.counts em.running {
		background: rgba(52, 211, 153, 0.12);
		color: #34d399;
	}

	.counts em.problem {
		background: rgba(248, 113, 113, 0.15);
		color: #f87171;
	}

	.heat {
		min-width: 0;
	}

	.bars {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 6px;
		min-width: 0;
	}

	.bars span {
		display: grid;
		grid-template-columns: 28px minmax(0, 1fr) auto;
		align-items: center;
		gap: 5px;
		min-width: 0;
	}

	.bars b {
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 800;
	}

	.mini {
		height: 6px;
		border-radius: 999px;
		background: rgba(30, 41, 59, 0.92);
		overflow: hidden;
		display: block;
	}

	.mini u {
		display: block;
		height: 100%;
		text-decoration: none;
		background: linear-gradient(90deg, #30d5c8, #60a5fa);
		border-radius: inherit;
		transition: width 0.2s ease;
	}

	.val {
		font-size: 10px;
		font-weight: 800;
		color: var(--text-primary);
		text-decoration: none;
		text-align: right;
		min-width: 48px;
	}

	.chevron {
		color: var(--text-muted);
		font-size: 12px;
		transition: transform 0.12s ease;
	}

	.chevron.open {
		transform: rotate(180deg);
	}

	.body {
		padding: 8px 10px 10px 18px;
		border-top: 1px dashed rgba(100, 116, 139, 0.18);
		background: rgba(2, 6, 23, 0.24);
	}

	.cards {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
		gap: 6px;
	}

	.card {
		display: grid;
		gap: 4px;
		padding: 6px 8px;
		border: 1px solid rgba(100, 116, 139, 0.16);
		border-left: 4px solid #94a3b8;
		border-radius: 7px;
		background: rgba(15, 23, 42, 0.55);
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
	}

	.card.running { border-left-color: #34d399; }
	.card.paused { border-left-color: #fbbf24; }
	.card.problem { border-left-color: #f87171; }
	.card.stopped { border-left-color: #94a3b8; }

	.card:hover {
		border-color: rgba(48, 213, 200, 0.4);
	}

	.card header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 6px;
		min-width: 0;
	}

	.card-name {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		flex: 0 0 auto;
	}

	.dot.running { background: #34d399; }
	.dot.paused { background: #fbbf24; }
	.dot.problem { background: #f87171; }
	.dot.stopped { background: #94a3b8; }

	.card strong {
		font-size: 11px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.card .state {
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 700;
		flex: 0 0 auto;
	}

	.card-metrics {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 3px;
	}

	.card-metrics span {
		display: grid;
		gap: 1px;
		padding: 3px 4px;
		border-radius: 5px;
		background: rgba(2, 6, 23, 0.4);
	}

	.card-metrics b {
		color: var(--text-muted);
		font-size: 8px;
		font-weight: 800;
	}

	.card-metrics small {
		color: var(--text-primary);
		font-size: 10px;
		font-weight: 800;
	}

	@media (max-width: 1100px) {
		.header {
			grid-template-columns: 4px minmax(120px, 0.9fr) minmax(0, 1.3fr) minmax(150px, 0.9fr) 18px;
		}
	}

	@media (max-width: 820px) {
		.header {
			grid-template-columns: 4px minmax(0, 1fr) 18px;
		}
		.heat, .bars {
			display: none;
		}
	}
</style>
