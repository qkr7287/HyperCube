<script lang="ts">
	import StatCard from './StatCard.svelte';
	import ProjectCard from './ProjectCard.svelte';

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
		projects = [],
		containers = [],
		selectedProject = null,
		onSelectProject = (name: string | null) => {},
		viewMode = 'group',
		onViewModeChange = (mode: string) => {},
	}: {
		projects: Project[];
		containers: Container[];
		selectedProject: string | null;
		onSelectProject: (name: string | null) => void;
		viewMode: string;
		onViewModeChange: (mode: string) => void;
	} = $props();

	let runningCount = $derived(containers.filter(c => c.state === 'running').length);
	let stoppedCount = $derived(containers.filter(c => c.state === 'exited').length);
	let waitingCount = $derived(containers.length - runningCount - stoppedCount);

	let alertingProjects = $derived(projects.filter(p => p.stats.stopped > 0));
</script>

<aside class="sidebar">
	<!-- Header -->
	<div class="sidebar-header">
		<span class="heading">컨테이너 정보</span>
		<div class="view-tabs">
			<button
				class="tab"
				class:active={viewMode === 'group'}
				onclick={() => onViewModeChange('group')}
			>GROUP</button>
			<button
				class="tab"
				class:active={viewMode === 'grid'}
				onclick={() => onViewModeChange('grid')}
			>GRID</button>
			<button
				class="tab"
				class:active={viewMode === 'list'}
				onclick={() => onViewModeChange('list')}
			>LIST</button>
		</div>
	</div>

	<!-- Stat Cards -->
	<div class="stats-row">
		<StatCard count={runningCount} label="실행중" type="running" />
		<StatCard count={waitingCount} label="대기중" type="waiting" />
		<StatCard count={stoppedCount} label="정지중" type="stopped" />
	</div>

	<!-- Project List -->
	<div class="project-list">
		{#if alertingProjects.length > 0}
			<div class="alert-badge">
				{alertingProjects.length} ALERTING OPS
			</div>
		{/if}

		{#each projects as project}
			<ProjectCard
				{project}
				selected={selectedProject === project.name}
				onclick={() => onSelectProject(selectedProject === project.name ? null : project.name)}
			/>
		{/each}
	</div>

	<!-- Show All Button -->
	<button class="show-all-btn">
		<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
			<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
			<rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
		</svg>
		<span>SHOW ALL {projects.length} CONTAINER GROUPS</span>
	</button>
</aside>

<style>
	.sidebar {
		width: 480px;
		min-width: 480px;
		background: var(--bg-base);
		border-left: 1px solid var(--border);
		padding: 24px;
		display: flex;
		flex-direction: column;
		gap: 0;
		overflow: hidden;
	}

	.sidebar-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-bottom: 32px;
		flex-shrink: 0;
	}

	.heading {
		font-size: 13px;
		font-weight: 700;
		color: var(--text-secondary);
	}

	.view-tabs {
		display: flex;
		background: var(--bg-tab);
		border-radius: var(--radius-sm);
		padding: 4px;
	}

	.tab {
		padding: 4px 12px;
		border: none;
		background: none;
		color: var(--text-muted);
		font-size: 13px;
		font-weight: 400;
		cursor: pointer;
		border-radius: var(--radius-sm);
		transition: all 0.2s;
	}

	.tab.active {
		background: var(--accent);
		color: var(--accent-dark);
		font-weight: 700;
	}

	.stats-row {
		display: flex;
		gap: 16px;
		padding-bottom: 40px;
		flex-shrink: 0;
	}

	.project-list {
		display: flex;
		flex-direction: column;
		gap: 16px;
		overflow-y: auto;
		flex: 1;
		min-height: 0;
		padding-bottom: 16px;
	}

	.alert-badge {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 6px 12px;
		background: rgba(239, 62, 94, 0.1);
		border: 1px solid rgba(239, 62, 94, 0.3);
		border-radius: var(--radius-sm);
		color: var(--error-soft);
		font-size: 12px;
		font-weight: 700;
		width: fit-content;
	}

	.show-all-btn {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		width: 100%;
		padding: 16px;
		background: transparent;
		border: 1px solid var(--accent);
		border-radius: var(--radius-md);
		color: var(--accent);
		font-size: 11px;
		font-weight: 700;
		cursor: pointer;
		transition: all 0.2s;
		margin-top: 8px;
	}

	.show-all-btn:hover {
		background: rgba(48, 213, 200, 0.1);
	}
</style>
