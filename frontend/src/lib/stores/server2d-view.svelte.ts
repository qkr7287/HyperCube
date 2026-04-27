export type Server2dMetric = 'cpu' | 'memory' | 'network';
export type Server2dStateFilter = 'all' | 'running' | 'paused' | 'problem' | 'stopped';
export type Server2dSortMode = 'total' | 'name' | 'problem';
export type Server2dSortDir = 'desc' | 'asc';
export type Server2dContainerSort = 'default' | 'gpu' | 'memory' | 'cpu' | 'network' | 'total';

type Server2dView = {
	soloStack: string | null;
	selectedMetric: Server2dMetric;
	stateFilter: Server2dStateFilter;
	expandedStack: string | null;
	searchQuery: string;
	sortMode: Server2dSortMode;
	stackSortDir: Server2dSortDir;
	containerSort: Server2dContainerSort;
	containerSortDir: Server2dSortDir;
	matrixShowAll: boolean;
	containersPaused: boolean;
	stacksPaused: boolean;
	eventsPaused: boolean;
	stackFocusPaused: boolean;
};

export const view: Server2dView = $state({
	soloStack: null,
	selectedMetric: 'cpu',
	stateFilter: 'all',
	expandedStack: null,
	searchQuery: '',
	sortMode: 'total',
	stackSortDir: 'desc',
	containerSort: 'total',
	containerSortDir: 'desc',
	matrixShowAll: false,
	containersPaused: false,
	stacksPaused: false,
	eventsPaused: false,
	stackFocusPaused: true,
});

export function resetViewForServerChange(): void {
	view.soloStack = null;
	view.expandedStack = null;
	view.searchQuery = '';
	view.stateFilter = 'all';
	view.sortMode = 'total';
	view.stackSortDir = 'desc';
	view.containerSort = 'total';
	view.containerSortDir = 'desc';
	view.matrixShowAll = false;
	view.containersPaused = false;
	view.stacksPaused = false;
	view.eventsPaused = false;
	view.stackFocusPaused = true;
}

export function stateFilterLabel(value: Server2dStateFilter): string {
	if (value === 'running') return '실행';
	if (value === 'paused') return '일시정지';
	if (value === 'problem') return '문제';
	if (value === 'stopped') return '중지';
	return '전체';
}
