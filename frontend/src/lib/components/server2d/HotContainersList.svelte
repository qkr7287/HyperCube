<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';

	type HotRow = {
		id: string;
		name: string;
		stack: string;
		cpu: number;
		memory: number;
		network: number;
		state: string;
		container: any;
	};

	let {
		rows = [] as HotRow[],
		limit = 5,
		variant = 'horizontal' as 'vertical' | 'horizontal',
		onSelect = (_container: any) => {},
	}: {
		rows?: HotRow[];
		limit?: number;
		variant?: 'vertical' | 'horizontal';
		onSelect?: (container: any) => void;
	} = $props();

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

	const top = $derived(rows.slice(0, limit));
</script>

<div class={`hot-panel ${variant}`}>
	<div class="hot-head">
		<span class="title">Top {limit} 뜨거운 컨테이너 <InfoTooltip text="CPU · 메모리 · 트래픽 사용량을 합산해 가장 바쁜 컨테이너부터 정렬합니다. 클릭하면 상세 모달이 열립니다." placement={variant === 'horizontal' ? 'bottom-start' : 'bottom-end'} /></span>
		<small>{rows.length}개 중 상위 {Math.min(limit, rows.length)}개</small>
	</div>
	<div class="hot-list">
		{#each top as row (row.id)}
			<button type="button" class={`hot-item ${stateClass(row.state)}`} onclick={() => onSelect(row.container)}>
				<div class="meta">
					<i class={`dot ${stateClass(row.state)}`}></i>
					<div class="text">
						<b>{row.name}</b>
						<small>{row.stack}</small>
					</div>
				</div>
				<div class="metrics">
					<em><b>CPU</b>{row.cpu.toFixed(1)}%</em>
					<em><b>MEM</b>{row.memory.toFixed(1)}%</em>
					<em><b>NET</b>{formatRate(row.network)}</em>
				</div>
			</button>
		{/each}
		{#if top.length === 0}
			<div class="empty">표시할 컨테이너가 없습니다.</div>
		{/if}
	</div>
</div>

<style>
	.hot-panel {
		display: flex;
		flex-direction: column;
		gap: 5px;
		min-height: 0;
		min-width: 0;
	}

	.hot-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 8px;
	}

	.title {
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 850;
		display: inline-flex;
		align-items: center;
	}

	.hot-head small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
	}

	.hot-panel.vertical .hot-list {
		display: flex;
		flex-direction: column;
		gap: 5px;
		overflow-y: auto;
		min-height: 0;
		padding-right: 2px;
	}

	.hot-panel.horizontal .hot-list {
		display: grid;
		grid-auto-flow: column;
		grid-auto-columns: minmax(0, 1fr);
		gap: 6px;
		min-height: 0;
	}

	.hot-list::-webkit-scrollbar {
		width: 5px;
	}
	.hot-list::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.24);
		border-radius: 3px;
	}

	.hot-item {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		border: 1px solid rgba(100, 116, 139, 0.16);
		border-left: 3px solid #94a3b8;
		border-radius: 7px;
		background: rgba(15, 23, 42, 0.55);
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
		min-width: 0;
		transition: border-color 0.12s ease;
	}

	.hot-panel.horizontal .hot-item {
		grid-template-columns: minmax(0, 1fr);
		grid-template-rows: auto auto;
		gap: 4px;
	}

	.hot-item:hover {
		border-color: rgba(48, 213, 200, 0.45);
	}

	.hot-item.running { border-left-color: #34d399; }
	.hot-item.paused { border-left-color: #fbbf24; }
	.hot-item.problem { border-left-color: #f87171; }
	.hot-item.stopped { border-left-color: #94a3b8; }

	.meta {
		display: flex;
		align-items: center;
		gap: 7px;
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

	.text {
		display: grid;
		min-width: 0;
	}

	.text b {
		font-size: 11px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.text small {
		color: var(--text-muted);
		font-size: 9px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.metrics {
		display: inline-flex;
		gap: 3px;
		flex-shrink: 0;
	}

	.metrics em {
		font-style: normal;
		display: inline-flex;
		gap: 3px;
		align-items: baseline;
		padding: 2px 5px;
		background: rgba(2, 6, 23, 0.5);
		border-radius: 999px;
		font-size: 9px;
		color: var(--text-primary);
		font-weight: 800;
	}

	.metrics em b {
		color: var(--text-muted);
		font-size: 8px;
		font-weight: 800;
	}

	.empty {
		padding: 10px;
		border: 1px dashed rgba(100, 116, 139, 0.28);
		border-radius: 8px;
		color: var(--text-muted);
		font-size: 11px;
		text-align: center;
	}
</style>
