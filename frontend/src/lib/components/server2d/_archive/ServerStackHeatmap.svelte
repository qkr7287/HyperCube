<script lang="ts">
	type HeatCell = {
		id: string;
		name: string;
		stack: string;
		state: string;
		cpu: number;
		memory: number;
		network: number;
		container: any;
	};

	type HeatStack = {
		name: string;
		color: string;
		containers: HeatCell[];
	};

	let {
		stacks = [],
		metric = 'cpu',
		onSelect = (_container: any) => {},
		onMetricChange = (_metric: 'cpu' | 'memory' | 'network') => {},
	}: {
		stacks?: HeatStack[];
		metric?: 'cpu' | 'memory' | 'network';
		onSelect?: (container: any) => void;
		onMetricChange?: (metric: 'cpu' | 'memory' | 'network') => void;
	} = $props();

	const metricLabels: Record<'cpu' | 'memory' | 'network', string> = {
		cpu: 'CPU',
		memory: '메모리',
		network: '트래픽',
	};

	let networkMax = $derived(
		Math.max(1, ...stacks.flatMap((stack) => stack.containers.map((c) => c.network))),
	);

	let totalContainers = $derived(stacks.reduce((sum, stack) => sum + stack.containers.length, 0));

	function valueFor(cell: HeatCell, active: 'cpu' | 'memory' | 'network'): number {
		if (active === 'cpu') return cell.cpu;
		if (active === 'memory') return cell.memory;
		return cell.network;
	}

	function intensity(cell: HeatCell, active: 'cpu' | 'memory' | 'network'): number {
		if (active === 'network') {
			return Math.max(0, Math.min(100, (cell.network / networkMax) * 100));
		}
		const raw = valueFor(cell, active);
		return Math.max(0, Math.min(100, raw));
	}

	function formatValue(cell: HeatCell, active: 'cpu' | 'memory' | 'network'): string {
		if (active === 'network') {
			const value = cell.network;
			if (!Number.isFinite(value) || value <= 0) return '0 B/s';
			const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
			let next = value;
			let idx = 0;
			while (next >= 1024 && idx < units.length - 1) {
				next /= 1024;
				idx += 1;
			}
			return `${next.toFixed(next >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
		}
		return `${valueFor(cell, active).toFixed(1)}%`;
	}

	let totalMax = $derived(Math.max(...stacks.map((s) => s.containers.length), 1));

	function cellSize(totalContainersMax: number): number {
		if (totalContainersMax >= 48) return 10;
		if (totalContainersMax >= 32) return 12;
		if (totalContainersMax >= 16) return 14;
		return 16;
	}
</script>

<div class="heatmap">
	<div class="heatmap-head">
		<div class="legend">
			<span class="swatch low"></span>
			<small>낮음</small>
			<span class="swatch mid"></span>
			<small>보통</small>
			<span class="swatch high"></span>
			<small>높음</small>
		</div>
		<div class="metric-switch" role="tablist" aria-label="열지도 지표 선택">
			{#each ['cpu', 'memory', 'network'] as key (key)}
				<button
					type="button"
					role="tab"
					aria-selected={metric === key}
					class:active={metric === key}
					onclick={() => onMetricChange(key as 'cpu' | 'memory' | 'network')}
				>
					{metricLabels[key as 'cpu' | 'memory' | 'network']}
				</button>
			{/each}
		</div>
		<small class="summary">총 {totalContainers}개 컨테이너 · {stacks.length}개 스택</small>
	</div>

	<div class="heatmap-body" style={`--cell-size:${cellSize(totalMax)}px;`}>
		{#each stacks as stack (stack.name)}
			<div class="stack-row">
				<div class="stack-label" style={`--stack-color:${stack.color}`}>
					<strong>{stack.name}</strong>
					<small>{stack.containers.length}개</small>
				</div>
				<div class="metric-lane">
					{#each stack.containers as container (container.id)}
						<button
							type="button"
							class={`heat-cell ${container.state}`}
							style={`--v:${intensity(container, metric)}%;`}
							aria-label={`${container.name} ${metricLabels[metric]} ${formatValue(container, metric)}`}
							title={`${container.name}\n${metricLabels[metric]}: ${formatValue(container, metric)}`}
							onclick={() => onSelect(container.container)}
						></button>
					{/each}
				</div>
			</div>
		{/each}
		{#if stacks.length === 0}
			<div class="empty">표시할 스택이 없습니다.</div>
		{/if}
	</div>
</div>

<style>
	.heatmap {
		min-height: 0;
		height: 100%;
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 6px;
	}

	.heatmap-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 10px;
		flex-wrap: wrap;
	}

	.legend {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
	}

	.swatch {
		display: inline-block;
		width: 12px;
		height: 10px;
		border-radius: 2px;
		border: 1px solid rgba(148, 163, 184, 0.18);
	}

	.swatch.low {
		background: color-mix(in srgb, #f87171 8%, rgba(51, 65, 85, 0.7));
	}
	.swatch.mid {
		background: color-mix(in srgb, #f87171 50%, rgba(51, 65, 85, 0.7));
	}
	.swatch.high {
		background: color-mix(in srgb, #f87171 90%, rgba(51, 65, 85, 0.7));
	}

	.metric-switch {
		display: inline-flex;
		border: 1px solid rgba(100, 116, 139, 0.22);
		border-radius: 999px;
		padding: 2px;
		background: rgba(15, 23, 42, 0.55);
	}

	.metric-switch button {
		border: none;
		background: transparent;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		padding: 4px 10px;
		border-radius: 999px;
		cursor: pointer;
	}

	.metric-switch button.active {
		background: rgba(48, 213, 200, 0.18);
		color: #30d5c8;
	}

	.summary {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
	}

	.heatmap-body {
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
		overflow-y: auto;
		padding-right: 4px;
	}

	.heatmap-body::-webkit-scrollbar {
		width: 6px;
	}
	.heatmap-body::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.24);
		border-radius: 3px;
	}

	.stack-row {
		display: grid;
		grid-template-columns: 96px minmax(0, 1fr);
		gap: 6px;
		align-items: stretch;
	}

	.stack-label {
		display: grid;
		gap: 2px;
		padding: 5px 7px;
		border: 1px solid rgba(100, 116, 139, 0.14);
		border-left: 4px solid var(--stack-color);
		border-radius: 6px;
		background: rgba(15, 23, 42, 0.44);
		align-content: center;
		min-width: 0;
	}

	.stack-label strong,
	.stack-label small {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.stack-label strong {
		font-size: 10px;
	}

	.stack-label small {
		color: var(--text-muted);
		font-size: 9px;
	}

	.metric-lane {
		display: flex;
		flex-wrap: wrap;
		gap: 3px;
		padding: 4px;
		border: 1px solid rgba(100, 116, 139, 0.12);
		border-radius: 6px;
		background: rgba(15, 23, 42, 0.4);
		align-content: flex-start;
		min-height: calc(var(--cell-size, 14px) + 8px);
	}

	.heat-cell {
		width: var(--cell-size, 14px);
		height: var(--cell-size, 14px);
		border: 1px solid rgba(100, 116, 139, 0.14);
		border-radius: 3px;
		padding: 0;
		cursor: pointer;
		background:
			linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0)),
			color-mix(in srgb, #f87171 var(--v), rgba(51, 65, 85, 0.68));
		transition: transform 0.1s ease, box-shadow 0.1s ease;
		flex: 0 0 auto;
	}

	.heat-cell:hover {
		transform: scale(1.15);
		box-shadow: 0 0 0 2px rgba(48, 213, 200, 0.48);
		z-index: 1;
	}

	.heat-cell.running {
		box-shadow: inset 0 0 0 1px rgba(52, 211, 153, 0.22);
	}
	.heat-cell.paused {
		box-shadow: inset 0 0 0 1px rgba(251, 191, 36, 0.3);
	}
	.heat-cell.problem,
	.heat-cell.restarting,
	.heat-cell.dead {
		box-shadow: inset 0 0 0 1px rgba(248, 113, 113, 0.4);
	}
	.heat-cell.stopped,
	.heat-cell.exited {
		box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.22);
	}

	.empty {
		padding: 12px;
		border: 1px dashed rgba(100, 116, 139, 0.3);
		border-radius: 8px;
		color: var(--text-muted);
		font-size: 11px;
		text-align: center;
	}
</style>
