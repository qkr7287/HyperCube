<script lang="ts">
	import { healthColor } from '$lib/utils/health-color';

	interface Container {
		id: string;
		shortId: string;
		names: string[];
		image: string;
		state: string;
		status: string;
		labels: any;
	}

	interface Project {
		name: string;
		containers: Container[];
		color: string;
		stats: { total: number; running: number; stopped: number; paused: number };
	}

	const MAX_VISIBLE_CELLS = 9;
	const LABEL_MAX_CHARS = 14;

	let {
		project,
		selected = false,
		selectedContainerId = null,
		onclick = () => {},
		onContainerClick = (container: Container) => {},
	}: {
		project: Project;
		selected: boolean;
		selectedContainerId?: string | null;
		onclick: () => void;
		onContainerClick: (container: Container) => void;
	} = $props();

	function getContainerName(container: Container): string {
		return container.names?.[0]?.replace('/', '') || container.shortId;
	}

	function getContainerLabel(container: Container): string {
		const name = getContainerName(container);
		return name.length > LABEL_MAX_CHARS ? `${name.slice(0, LABEL_MAX_CHARS)}…` : name;
	}

	function getContainerStateTone(container: Container): 'running' | 'paused' | 'stopped' {
		if (container.state === 'running') return 'running';
		if (container.state === 'paused') return 'paused';
		return 'stopped';
	}

	const healthHex = $derived(healthColor(project.stats.running, project.stats.total).hex);
	const visibleContainers = $derived(project.containers.slice(0, MAX_VISIBLE_CELLS));
	const hiddenCount = $derived(Math.max(project.containers.length - MAX_VISIBLE_CELLS, 0));
</script>

<div
	class="card"
	class:selected
	onclick={onclick}
	onkeydown={(event) => {
		if (event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			onclick();
		}
	}}
	role="button"
	tabindex="0"
	style="--health-color: {healthHex};"
>
	<span class="health-bar" aria-hidden="true"></span>

	<div class="card-header">
		<div class="heading-block">
			<span class="project-name" class:accent={selected}>{project.name.toUpperCase()}</span>
			<span class="project-meta">{project.stats.total} containers</span>
		</div>

		<div class="counts">
			<span class="count running">{project.stats.running} running</span>
			<span class="count stopped" class:muted={project.stats.stopped === 0}>
				{project.stats.stopped} stopped
			</span>
		</div>
	</div>

	<div class="hex-grid">
		{#each visibleContainers as container}
			<button
				type="button"
				class="hex-cell"
				class:cell-active={selectedContainerId === container.id}
				class:cell-running={getContainerStateTone(container) === 'running'}
				class:cell-paused={getContainerStateTone(container) === 'paused'}
				class:cell-stopped={getContainerStateTone(container) === 'stopped'}
				title={getContainerName(container)}
				onclick={(event) => {
					event.stopPropagation();
					onContainerClick(container);
				}}
			>
				<span class="hex-wrap">
					<svg class="hex-shape" viewBox="0 0 24 28" width="30" height="34" aria-hidden="true">
						<path class="hex-body" d="M12 0 L24 7 L24 21 L12 28 L0 21 L0 7 Z" />
						<path class="hex-wire" d="M12 14 L12 28 M12 14 L24 7 M12 14 L0 7" />
					</svg>
				</span>
				<span class="hex-label">{getContainerLabel(container)}</span>
			</button>
		{/each}

		{#if hiddenCount > 0}
			<div class="hex-cell hex-more" title={`${hiddenCount} more containers`}>
				<span class="hex-wrap">
					<svg class="hex-shape" viewBox="0 0 24 28" width="30" height="34" aria-hidden="true">
						<path class="hex-body" d="M12 0 L24 7 L24 21 L12 28 L0 21 L0 7 Z" />
						<path class="hex-wire" d="M12 14 L12 28 M12 14 L24 7 M12 14 L0 7" />
					</svg>
				</span>
				<span class="hex-label">+{hiddenCount}</span>
			</div>
		{/if}
	</div>
</div>

<style>
	.card {
		position: relative;
		width: 100%;
		text-align: left;
		background: linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(13, 17, 23, 0.98));
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 18px 20px 18px 22px;
		cursor: pointer;
		transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
		color: inherit;
		font-family: inherit;
		display: flex;
		flex-direction: column;
		gap: 16px;
		overflow: hidden;
		flex: 0 0 auto;
	}

	.card:hover {
		background: linear-gradient(180deg, rgba(19, 29, 44, 0.98), rgba(14, 20, 29, 1));
		transform: translateY(-1px);
	}

	.card.selected {
		border-color: var(--accent);
		box-shadow: 0 0 0 1px rgba(48, 213, 200, 0.16), 0 12px 28px rgba(3, 10, 20, 0.24);
	}

	.health-bar {
		position: absolute;
		top: 10px;
		bottom: 10px;
		left: 4px;
		width: 4px;
		border-radius: 2px;
		background: var(--health-color, var(--text-secondary));
		box-shadow: 0 0 10px color-mix(in srgb, var(--health-color, transparent) 55%, transparent);
		transition: background-color 0.3s ease, box-shadow 0.3s ease;
	}

	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 16px;
	}

	.heading-block {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}

	.project-name {
		font-size: 13px;
		font-weight: 700;
		color: #d9d9d9;
		letter-spacing: 0.02em;
	}

	.project-name.accent {
		color: var(--accent);
	}

	.project-meta {
		font-size: 11px;
		color: var(--text-muted);
	}

	.counts {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 10px;
	}

	.count {
		font-size: 12px;
		font-weight: 600;
		white-space: nowrap;
	}

	.count.running {
		color: var(--accent);
	}

	.count.stopped {
		color: var(--error-soft);
	}

	.count.muted {
		color: var(--text-secondary);
	}

	.hex-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 12px 10px;
		justify-content: flex-start;
	}

	.hex-cell {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 6px;
		padding: 6px 4px 4px;
		width: 76px;
		min-width: 0;
		border: 0;
		background: transparent;
		color: var(--text-primary);
		font-family: inherit;
		cursor: pointer;
		border-radius: 6px;
		transition: background-color 0.18s ease, transform 0.18s ease;
	}

	.hex-cell:hover {
		background: rgba(148, 163, 184, 0.06);
		transform: translateY(-1px);
	}

	.hex-cell.hex-more {
		cursor: default;
	}

	.hex-cell.hex-more:hover {
		background: transparent;
		transform: none;
	}

	.hex-wrap {
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}

	.hex-shape {
		transition: filter 0.2s ease, transform 0.18s ease;
		overflow: visible;
	}

	.hex-body {
		transition: fill 0.2s ease;
	}

	.hex-wire {
		fill: none;
		stroke: rgba(10, 18, 28, 0.75);
		stroke-width: 1.1;
		stroke-linecap: round;
		stroke-linejoin: round;
		pointer-events: none;
	}

	.cell-running .hex-body {
		fill: #4ade80;
	}
	.cell-running .hex-shape {
		filter: drop-shadow(0 0 8px rgba(74, 222, 128, 0.42));
	}

	.cell-paused .hex-body {
		fill: #facc15;
	}
	.cell-paused .hex-shape {
		filter: drop-shadow(0 0 8px rgba(250, 204, 21, 0.42));
	}

	.cell-stopped .hex-body {
		fill: #f87171;
	}
	.cell-stopped .hex-shape {
		filter: drop-shadow(0 0 6px rgba(248, 113, 113, 0.35));
		opacity: 0.9;
	}

	.hex-more .hex-body {
		fill: rgba(148, 163, 184, 0.18);
		stroke: rgba(148, 163, 184, 0.38);
		stroke-width: 0.6;
	}

	.hex-more .hex-wire {
		stroke: rgba(148, 163, 184, 0.45);
	}

	.cell-active .hex-shape {
		filter: drop-shadow(0 0 12px rgba(48, 213, 200, 0.8));
		transform: scale(1.1);
	}

	.cell-active {
		background: rgba(48, 213, 200, 0.08);
	}

	.hex-cell:hover .hex-shape {
		transform: translateY(-1px);
	}

	.cell-active:hover .hex-shape {
		transform: scale(1.1) translateY(-1px);
	}

	.hex-label {
		display: block;
		max-width: 100%;
		font-size: 11px;
		font-weight: 600;
		color: var(--text-primary);
		text-align: center;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		letter-spacing: 0.01em;
	}

	.cell-active .hex-label {
		color: var(--accent);
	}

	.cell-stopped .hex-label {
		color: var(--text-secondary);
	}

	.hex-more .hex-label {
		color: var(--text-secondary);
		font-weight: 700;
	}
</style>
