export type Server2dMetric = 'cpu' | 'memory' | 'network';
export type Server2dStateFilter = 'all' | 'running' | 'paused' | 'problem' | 'stopped';
export type Server2dSortMode = 'load' | 'name' | 'problem';

type Server2dView = {
	soloStack: string | null;
	selectedMetric: Server2dMetric;
	stateFilter: Server2dStateFilter;
	expandedStack: string | null;
	searchQuery: string;
	sortMode: Server2dSortMode;
	matrixShowAll: boolean;
};

export const view: Server2dView = $state({
	soloStack: null,
	selectedMetric: 'cpu',
	stateFilter: 'all',
	expandedStack: null,
	searchQuery: '',
	sortMode: 'load',
	matrixShowAll: false,
});

export function resetViewForServerChange(): void {
	view.soloStack = null;
	view.expandedStack = null;
	view.searchQuery = '';
	view.stateFilter = 'all';
	view.sortMode = 'load';
	view.matrixShowAll = false;
}

export function stateFilterLabel(value: Server2dStateFilter): string {
	if (value === 'running') return '실행';
	if (value === 'paused') return '일시정지';
	if (value === 'problem') return '문제';
	if (value === 'stopped') return '중지';
	return '전체';
}
