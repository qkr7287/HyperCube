<script lang="ts">
	type ContainerNodeRef = {
		id: string;
		name: string;
		state: string;
		cpu: number;
		memory: number;
		container: any;
	};

	type StackFrame = {
		name: string;
		color: string;
		containers: ContainerNodeRef[];
	};

	let {
		stacks = [],
		onSelect = (_container: any) => {},
	}: {
		stacks?: StackFrame[];
		onSelect?: (container: any) => void;
	} = $props();

	type TreemapTile = {
		stack: StackFrame;
		x: number;
		y: number;
		width: number;
		height: number;
		weight: number;
	};

	const PAD = 4;

	function computeWeights(): { stack: StackFrame; weight: number }[] {
		return stacks
			.map((stack) => ({
				stack,
				weight: Math.max(1, stack.containers.length),
			}))
			.sort((a, b) => b.weight - a.weight);
	}

	function squarify(
		items: { stack: StackFrame; weight: number }[],
		x: number,
		y: number,
		width: number,
		height: number,
	): TreemapTile[] {
		if (items.length === 0 || width <= 0 || height <= 0) return [];
		const tiles: TreemapTile[] = [];
		const totalWeight = items.reduce((sum, item) => sum + item.weight, 0);
		let available = items.slice();
		let ox = x;
		let oy = y;
		let ow = width;
		let oh = height;

		while (available.length) {
			const remainingWeight = available.reduce((sum, item) => sum + item.weight, 0);
			const shorter = Math.min(ow, oh);
			const row: typeof available = [];
			let rowWeight = 0;
			let bestRatio = Infinity;

			while (available.length) {
				const candidate = available[0];
				const testRow = [...row, candidate];
				const testWeight = rowWeight + candidate.weight;
				const ratio = worstRatio(testRow, testWeight, shorter, ow, oh, remainingWeight);
				if (ratio <= bestRatio) {
					row.push(available.shift()!);
					rowWeight = testWeight;
					bestRatio = ratio;
				} else {
					break;
				}
			}

			if (!row.length) {
				row.push(available.shift()!);
				rowWeight = row[0].weight;
			}

			const rowArea = (rowWeight / totalWeight) * width * height;
			if (ow <= oh) {
				const rowHeight = rowArea / ow;
				let rx = ox;
				for (const item of row) {
					const itemWidth = (item.weight / rowWeight) * ow;
					tiles.push({
						stack: item.stack,
						x: rx,
						y: oy,
						width: itemWidth,
						height: rowHeight,
						weight: item.weight,
					});
					rx += itemWidth;
				}
				oy += rowHeight;
				oh -= rowHeight;
			} else {
				const rowWidth = rowArea / oh;
				let ry = oy;
				for (const item of row) {
					const itemHeight = (item.weight / rowWeight) * oh;
					tiles.push({
						stack: item.stack,
						x: ox,
						y: ry,
						width: rowWidth,
						height: itemHeight,
						weight: item.weight,
					});
					ry += itemHeight;
				}
				ox += rowWidth;
				ow -= rowWidth;
			}
		}

		return tiles;
	}

	function worstRatio(
		row: { stack: StackFrame; weight: number }[],
		weightSum: number,
		shorter: number,
		totalW: number,
		totalH: number,
		totalWeight: number,
	): number {
		if (!row.length || weightSum === 0) return Infinity;
		const rowArea = (weightSum / totalWeight) * totalW * totalH;
		let minWeight = Infinity;
		let maxWeight = -Infinity;
		for (const item of row) {
			if (item.weight < minWeight) minWeight = item.weight;
			if (item.weight > maxWeight) maxWeight = item.weight;
		}
		const s2 = shorter * shorter;
		const maxArea = (maxWeight / totalWeight) * totalW * totalH;
		const minArea = (minWeight / totalWeight) * totalW * totalH;
		return Math.max((s2 * maxArea) / (rowArea * rowArea), (rowArea * rowArea) / (s2 * minArea));
	}

	function gridFor(count: number, width: number, height: number): { cols: number; rows: number } {
		if (count <= 0) return { cols: 1, rows: 1 };
		const ratio = Math.max(width, 1) / Math.max(height, 1);
		const cols = Math.max(1, Math.round(Math.sqrt(count * ratio)));
		const rows = Math.ceil(count / cols);
		return { cols, rows };
	}

	function stateColor(state: string): string {
		if (state === 'running') return '#34d399';
		if (state === 'paused') return '#fbbf24';
		if (state === 'restarting' || state === 'dead') return '#f87171';
		if (state === 'exited' || state === 'stopped') return '#64748b';
		return '#94a3b8';
	}

	function heatColor(cpu: number, memory: number): string {
		const value = Math.max(0, Math.min(100, Math.max(cpu, memory)));
		const alpha = 0.15 + (value / 100) * 0.75;
		return `rgba(248, 113, 113, ${alpha.toFixed(2)})`;
	}

	let containerBox = $state<HTMLDivElement | null>(null);
	let width = $state(560);
	let height = $state(240);

	function measure() {
		if (!containerBox) return;
		const rect = containerBox.getBoundingClientRect();
		width = Math.max(120, rect.width);
		height = Math.max(120, rect.height);
	}

	$effect(() => {
		if (!containerBox) return;
		const observer = new ResizeObserver(() => measure());
		observer.observe(containerBox);
		measure();
		return () => observer.disconnect();
	});

	let weights = $derived(computeWeights());
	let tiles = $derived(squarify(weights, 0, 0, width, height));
</script>

<div class="frame" bind:this={containerBox}>
	<svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" width={width} height={height}>
		<defs>
			<pattern id="rack-grid" width="8" height="8" patternUnits="userSpaceOnUse">
				<path d="M0 0 L8 0 M0 0 L0 8" stroke="rgba(100,116,139,0.1)" stroke-width="0.5" />
			</pattern>
		</defs>
		<rect x="0" y="0" width={width} height={height} fill="url(#rack-grid)" />

		{#each tiles as tile (tile.stack.name)}
			{@const stackContainers = tile.stack.containers}
			{@const innerX = tile.x + PAD}
			{@const innerY = tile.y + PAD + 14}
			{@const innerW = Math.max(0, tile.width - PAD * 2)}
			{@const innerH = Math.max(0, tile.height - PAD * 2 - 14)}
			{@const grid = gridFor(stackContainers.length, innerW, innerH)}
			{@const cellW = innerW / Math.max(1, grid.cols)}
			{@const cellH = innerH / Math.max(1, grid.rows)}

			<g class="tile-group">
				<rect
					x={tile.x + 1}
					y={tile.y + 1}
					width={Math.max(0, tile.width - 2)}
					height={Math.max(0, tile.height - 2)}
					rx="5"
					fill="rgba(15, 23, 42, 0.82)"
					stroke={tile.stack.color}
					stroke-width="1.2"
				/>
				<rect
					x={tile.x + 1}
					y={tile.y + 1}
					width={Math.max(0, tile.width - 2)}
					height="14"
					rx="5"
					fill={`${tile.stack.color}22`}
				/>
				<text
					x={tile.x + 7}
					y={tile.y + 11}
					class="tile-title"
					style={`--tile-color:${tile.stack.color}`}
				>
					{tile.stack.name}
				</text>
				<text x={tile.x + tile.width - 7} y={tile.y + 11} class="tile-count" text-anchor="end">
					{stackContainers.length}개
				</text>

				{#each stackContainers as container, index (container.id)}
					{@const col = index % grid.cols}
					{@const row = Math.floor(index / grid.cols)}
					{@const cx = innerX + col * cellW}
					{@const cy = innerY + row * cellH}
					{@const fillColor = container.state === 'running' ? heatColor(container.cpu, container.memory) : 'rgba(51,65,85,0.55)'}
					<g
						role="button"
						tabindex="0"
						onclick={() => onSelect(container.container)}
						onkeydown={(event) => {
							if (event.key === 'Enter' || event.key === ' ') {
								event.preventDefault();
								onSelect(container.container);
							}
						}}
					>
						<title>
							{container.name} / {container.state} / CPU {container.cpu.toFixed(
								1,
							)}% / MEM {container.memory.toFixed(1)}%
						</title>
						<rect
							x={cx + 0.8}
							y={cy + 0.8}
							width={Math.max(0.5, cellW - 1.6)}
							height={Math.max(0.5, cellH - 1.6)}
							rx="2"
							fill={fillColor}
							stroke={stateColor(container.state)}
							stroke-width="0.6"
						/>
					</g>
				{/each}
			</g>
		{/each}
	</svg>
</div>

<style>
	.frame {
		position: relative;
		width: 100%;
		height: 100%;
		min-height: 0;
		background:
			linear-gradient(180deg, rgba(10, 14, 23, 0.98), rgba(15, 23, 42, 0.88)),
			radial-gradient(circle at 15% 15%, rgba(48, 213, 200, 0.1), transparent 60%);
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: 8px;
		overflow: hidden;
	}

	svg {
		display: block;
	}

	:global(.tile-group rect) {
		transition: stroke-width 0.15s ease;
	}

	:global(.tile-group g:hover rect) {
		stroke-width: 1.6;
	}

	:global(.tile-title) {
		fill: #e2e8f0;
		font-size: 9px;
		font-weight: 800;
		letter-spacing: 0.02em;
	}

	:global(.tile-count) {
		fill: #94a3b8;
		font-size: 8px;
		font-weight: 700;
	}
</style>
