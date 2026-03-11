<script lang="ts">
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

	let {
		project,
		selected = false,
		onclick = () => {},
	}: {
		project: Project;
		selected: boolean;
		onclick: () => void;
	} = $props();
</script>

<button
	class="card"
	class:selected
	onclick={onclick}
>
	<div class="card-header">
		<span class="project-name" class:accent={selected}>{project.name.toUpperCase()}</span>
		<div class="counts">
			<span class="count running">{project.stats.running} 실행중</span>
			<span class="count stopped" class:muted={project.stats.stopped === 0}>
				{project.stats.stopped} 정지중
			</span>
		</div>
	</div>
	<div class="container-dots">
		{#each project.containers as container}
			<div class="dot-wrapper">
				<svg width="28" height="24" viewBox="0 0 28 24" fill="none">
					<path d="M7 0h14l7 12-7 12H7L0 12 7 0Z"
						fill={container.state === 'running' ? 'var(--accent)' : 'var(--error)'}
						opacity={container.state === 'running' ? 1 : 0.8}
					/>
				</svg>
			</div>
		{/each}
	</div>
</button>

<style>
	.card {
		width: 100%;
		text-align: left;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-md);
		padding: 20px;
		cursor: pointer;
		transition: all 0.2s ease;
		color: inherit;
		font-family: inherit;
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.card:hover {
		background: var(--bg-card-hover);
	}

	.card.selected {
		border-color: var(--accent);
	}

	.card-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.project-name {
		font-size: 13px;
		font-weight: 700;
		color: #d9d9d9;
	}

	.project-name.accent {
		color: var(--accent);
	}

	.counts {
		display: flex;
		gap: 12px;
	}

	.count {
		font-size: 13px;
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

	.container-dots {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.dot-wrapper {
		display: flex;
		align-items: center;
		justify-content: center;
	}
</style>
