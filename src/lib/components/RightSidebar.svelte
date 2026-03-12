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
		onSelectContainer = (container: Container) => {},
		viewMode = 'group',
		onViewModeChange = (mode: string) => {},
	}: {
		projects: Project[];
		containers: Container[];
		selectedProject: string | null;
		onSelectProject: (name: string | null) => void;
		onSelectContainer: (container: Container) => void;
		viewMode: string;
		onViewModeChange: (mode: string) => void;
	} = $props();

	let runningCount = $derived(containers.filter(c => c.state === 'running').length);
	let stoppedCount = $derived(containers.filter(c => c.state === 'exited').length);
	let waitingCount = $derived(containers.length - runningCount - stoppedCount);

	let alertingProjects = $derived(projects.filter(p => p.stats.stopped > 0));

	// List view state
	let searchQuery = $state('');
	let sortColumn = $state<string>('state');
	let sortDirection = $state<'asc' | 'desc'>('asc');

	function getContainerName(container: Container): string {
		return container.names?.[0]?.replace('/', '') || container.shortId;
	}

	function getContainerNameDisplay(container: Container): string {
		const name = getContainerName(container);
		return name.length > 14 ? name.substring(0, 14) + '...' : name;
	}

	function getContainerImage(container: Container): string {
		return container.image.length > 14 ? container.image.substring(0, 14) + '...' : container.image;
	}

	function getContainerProject(container: Container): string {
		return container.labels?.['com.docker.compose.project'] || 'default';
	}

	function getLastActivity(container: Container): string {
		const status = container.status || '';
		// "Up 2 days" -> running for 2 days
		// "Up 12 hours" -> running for 12 hours
		// "Exited (0) 3 hours ago" -> stopped 3 hours ago
		const upMatch = status.match(/Up\s+(.+)/);
		if (upMatch) return upMatch[1].replace(/\s*\(.*\)/, '').trim();
		const exitMatch = status.match(/Exited.*?\)\s+(.+)\s+ago/);
		if (exitMatch) return exitMatch[1] + ' ago';
		return status || '-';
	}

	function getStateLabel(state: string): string {
		return state === 'running' ? 'Running' : state === 'exited' ? 'Stopped' : 'Waiting';
	}

	function getStateSortOrder(state: string): number {
		if (state === 'running') return 0;
		if (state === 'exited') return 2;
		return 1;
	}

	let filteredContainers = $derived.by(() => {
		let result = containers;
		if (searchQuery.trim()) {
			const q = searchQuery.trim().toLowerCase();
			result = result.filter(c =>
				getContainerName(c).toLowerCase().includes(q) ||
				getContainerProject(c).toLowerCase().includes(q)
			);
		}
		return result;
	});

	let sortedContainers = $derived.by(() => {
		const list = [...filteredContainers];
		const dir = sortDirection === 'asc' ? 1 : -1;

		list.sort((a, b) => {
			let cmp = 0;
			switch (sortColumn) {
				case 'state':
					cmp = getStateSortOrder(a.state) - getStateSortOrder(b.state);
					break;
				case 'name':
					cmp = getContainerName(a).localeCompare(getContainerName(b));
					break;
				case 'image':
					cmp = a.image.localeCompare(b.image);
					break;
				case 'project':
					cmp = getContainerProject(a).localeCompare(getContainerProject(b));
					break;
				case 'activity':
					cmp = getLastActivity(a).localeCompare(getLastActivity(b));
					break;
				default:
					cmp = 0;
			}
			return cmp * dir;
		});
		return list;
	});

	function toggleSort(column: string) {
		if (sortColumn === column) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortColumn = column;
			sortDirection = 'asc';
		}
	}
</script>

<aside class="sidebar" class:wide={viewMode === 'list'}>
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
				class:active={viewMode === 'list'}
				onclick={() => onViewModeChange('list')}
			>LIST</button>
		</div>
	</div>

	{#if viewMode === 'group'}
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
					onContainerClick={onSelectContainer}
				/>
			{/each}
		</div>

	{:else}
		<!-- List View: Stat Cards (Figma) -->
		<div class="list-stats">
			<div class="list-stat-card active">
				<span class="list-stat-label-en">Total</span>
				<span class="list-stat-value total">전체: {containers.length}</span>
			</div>
			<div class="list-stat-card">
				<span class="list-stat-label-en muted">Running</span>
				<span class="list-stat-value running">실행중: {runningCount}</span>
			</div>
			<div class="list-stat-card">
				<span class="list-stat-label-en muted">Waiting</span>
				<span class="list-stat-value waiting">대기중: {waitingCount}</span>
			</div>
			<div class="list-stat-card">
				<span class="list-stat-label-en muted">Stopped</span>
				<span class="list-stat-value stopped">중지됨: {stoppedCount}</span>
			</div>
		</div>

		<!-- Search -->
		<div class="search-bar">
			<svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
			</svg>
			<input
				type="text"
				class="search-input"
				placeholder="컨테이너명, 프로젝트명 검색..."
				bind:value={searchQuery}
			/>
			{#if searchQuery}
				<button class="search-clear" onclick={() => searchQuery = ''}>
					<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
						<path d="M18 6L6 18M6 6l12 12"/>
					</svg>
				</button>
			{/if}
		</div>

		<!-- List View: Table -->
		<div class="table-wrapper">
			<table class="container-table">
				<thead>
					<tr>
						<th class="sortable" onclick={() => toggleSort('state')}>
							상태
							{#if sortColumn === 'state'}
								<span class="sort-arrow">{sortDirection === 'asc' ? '\u25B2' : '\u25BC'}</span>
							{/if}
						</th>
						<th class="sortable" onclick={() => toggleSort('name')}>
							컨테이너명
							{#if sortColumn === 'name'}
								<span class="sort-arrow">{sortDirection === 'asc' ? '\u25B2' : '\u25BC'}</span>
							{/if}
						</th>
						<th class="sortable" onclick={() => toggleSort('image')}>
							이미지
							{#if sortColumn === 'image'}
								<span class="sort-arrow">{sortDirection === 'asc' ? '\u25B2' : '\u25BC'}</span>
							{/if}
						</th>
						<th class="sortable" onclick={() => toggleSort('project')}>
							프로젝트
							{#if sortColumn === 'project'}
								<span class="sort-arrow">{sortDirection === 'asc' ? '\u25B2' : '\u25BC'}</span>
							{/if}
						</th>
						<th class="sortable" onclick={() => toggleSort('activity')}>
							마지막 활동
							{#if sortColumn === 'activity'}
								<span class="sort-arrow">{sortDirection === 'asc' ? '\u25B2' : '\u25BC'}</span>
							{/if}
						</th>
						<th>동작</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedContainers as container}
						<tr>
							<td>
								<span class="status-text" class:status-running={container.state === 'running'} class:status-stopped={container.state === 'exited'}>
									{getStateLabel(container.state)}
								</span>
							</td>
							<td class="cell-name" title={getContainerName(container)}>{getContainerNameDisplay(container)}</td>
							<td class="cell-image" title={container.image}>{getContainerImage(container)}</td>
							<td class="cell-project">{getContainerProject(container)}</td>
							<td class="cell-activity">{getLastActivity(container)}</td>
							<td><button class="detail-btn" onclick={() => onSelectContainer(container)}>상세보기</button></td>
						</tr>
					{/each}
					{#if sortedContainers.length === 0}
						<tr>
							<td colspan="6" class="empty-row">검색 결과가 없습니다</td>
						</tr>
					{/if}
				</tbody>
			</table>
		</div>

		<!-- Show All Footer -->
		<div class="show-all-footer">
			<span class="show-all-text">SHOW ALL {containers.length} CONTAINERS</span>
		</div>
	{/if}
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
		transition: width 0.3s ease, min-width 0.3s ease;
	}

	.sidebar.wide {
		width: 678px;
		min-width: 678px;
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

	/* List View Styles */
	.list-stats {
		display: flex;
		gap: 12px;
		padding-bottom: 24px;
		flex-shrink: 0;
	}

	.list-stat-card {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 16px;
		border-radius: 8px;
		background: #121720;
		border: 1px solid #1f2937;
		height: 53px;
		box-sizing: border-box;
	}

	.list-stat-card.active {
		background: rgba(48, 213, 200, 0.1);
		border-color: #30d5c8;
		height: 54px;
		padding: 0;
	}

	.list-stat-label-en {
		font-size: 9px;
		font-weight: 700;
		color: var(--accent);
		text-align: center;
		line-height: 13.5px;
	}

	.list-stat-label-en.muted {
		color: #94a3b8;
	}

	.list-stat-value {
		font-size: 13px;
		font-weight: 700;
		line-height: 19.5px;
		text-align: center;
	}

	.list-stat-value.total {
		color: var(--accent);
	}

	.list-stat-value.running {
		font-weight: 500;
		font-size: 15px;
		line-height: 22.5px;
		color: var(--accent);
	}

	.list-stat-value.waiting {
		font-weight: 500;
		font-size: 15px;
		line-height: 22.5px;
		color: #f79009;
	}

	.list-stat-value.stopped {
		font-weight: 500;
		font-size: 15px;
		line-height: 22.5px;
		color: #64748b;
	}

	.table-wrapper {
		flex: 1;
		overflow-y: auto;
		min-height: 0;
	}

	.container-table {
		width: 100%;
		border-collapse: collapse;
	}

	.container-table thead {
		position: sticky;
		top: 0;
		z-index: 1;
		background: var(--bg-base);
	}

	.container-table th {
		font-size: 13px;
		font-weight: 400;
		color: var(--text-secondary);
		text-align: left;
		padding: 8px 8px 12px;
		border-bottom: 1px solid var(--border);
		white-space: nowrap;
	}

	.container-table td {
		font-size: 11px;
		color: var(--text-primary);
		padding: 10px 8px;
		border-bottom: 1px solid rgba(31, 41, 55, 0.4);
		white-space: nowrap;
	}

	.container-table tbody tr:hover {
		background: rgba(48, 213, 200, 0.03);
	}

	.status-text {
		font-size: 14px;
		font-weight: 500;
		color: var(--text-muted);
	}

	.status-text.status-running {
		color: var(--accent);
	}

	.status-text.status-stopped {
		color: var(--text-muted);
	}

	.cell-name {
		font-weight: 500;
	}

	.cell-image {
		color: var(--text-primary);
	}

	.cell-project {
		font-size: 10px;
	}

	.cell-activity {
		color: var(--text-primary);
		font-size: 11px;
	}

	.detail-btn {
		background: #30d5c8;
		border: none;
		color: #094b66;
		font-size: 10px;
		font-weight: 700;
		cursor: pointer;
		padding: 4px 8px;
		border-radius: 8px;
		transition: opacity 0.2s;
	}

	.detail-btn:hover {
		opacity: 0.85;
	}

	.sortable {
		cursor: pointer;
		user-select: none;
	}

	.sortable:hover {
		color: var(--text-primary);
	}

	.sort-arrow {
		font-size: 8px;
		margin-left: 4px;
		color: var(--accent);
	}

	.empty-row {
		text-align: center;
		color: var(--text-muted);
		padding: 24px 8px !important;
	}

	/* Search */
	.search-bar {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 12px;
		background: var(--bg-card);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		margin-bottom: 16px;
		flex-shrink: 0;
	}

	.search-icon {
		color: var(--text-muted);
		flex-shrink: 0;
	}

	.search-input {
		flex: 1;
		background: none;
		border: none;
		outline: none;
		color: var(--text-primary);
		font-size: 12px;
	}

	.search-input::placeholder {
		color: var(--text-muted);
	}

	.search-clear {
		background: none;
		border: none;
		color: var(--text-muted);
		cursor: pointer;
		padding: 2px;
		display: flex;
		align-items: center;
	}

	.search-clear:hover {
		color: var(--text-primary);
	}

	/* Show All Footer (Figma style) */
	.show-all-footer {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 20px 16px;
		background: #0f172a;
		border-radius: 0 0 var(--radius-md) var(--radius-md);
		margin: 0 -24px -24px;
	}

	.show-all-text {
		font-size: 11px;
		font-weight: 700;
		color: var(--accent);
		letter-spacing: 0.02em;
	}
</style>
