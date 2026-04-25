<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';

	type HotRow = {
		id: string;
		name: string;
		stack: string;
		cpu: number;
		memory: number;
		network: number;
		gpu?: number;
		state: string;
		container: any;
	};

	let {
		rows = [] as HotRow[],
		limit = 5,
		variant = 'horizontal' as 'vertical' | 'horizontal',
		title = '',
		subtitle = '',
		badge = '',
		helperText = 'CPU · 메모리 · 트래픽 사용량을 합산해 가장 바쁜 컨테이너부터 정렬합니다. 클릭하면 상세 모달이 열립니다.',
		panelClass = '',
		showRank = false,
		compactMetrics = false,
		onSelect = (_container: any) => {},
	}: {
		rows?: HotRow[];
		limit?: number;
		variant?: 'vertical' | 'horizontal';
		title?: string;
		subtitle?: string;
		badge?: string;
		helperText?: string;
		panelClass?: string;
		showRank?: boolean;
		compactMetrics?: boolean;
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

	function stateLabel(state: string): string {
		if (state === 'running') return '실행';
		if (state === 'paused') return '일시정지';
		if (state === 'dead') return '장애';
		if (state === 'restarting') return '재시작';
		if (state === 'exited' || state === 'stopped') return '중지';
		return state || '-';
	}

	function formatRateCompact(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0';
		const units = ['B', 'K', 'M', 'G'];
		let next = value;
		let index = 0;
		while (next >= 1024 && index < units.length - 1) {
			next /= 1024;
			index += 1;
		}
		return `${next.toFixed(next >= 100 ? 0 : next >= 10 ? 1 : 2)}${units[index]}`;
	}

	const top = $derived(rows.slice(0, limit));
</script>

<section class={`hot-panel ${variant} ${panelClass}`.trim()}>
	<div class="hot-head">
		<div class="title">
			<i class="flame" aria-hidden="true">🔥</i>
			<span class="title-text">{title || `Top ${limit} 뜨거운 컨테이너`}</span>
			<InfoTooltip text={helperText} placement={variant === 'horizontal' ? 'bottom-start' : 'bottom-end'} />
		</div>
		<small>{badge || `${rows.length}개 중 상위 ${Math.min(limit, rows.length)}개`}</small>
	</div>
	<div class="hot-list">
		{#each top as row, index (row.id)}
			<button type="button" class={`row ${stateClass(row.state)}`} onclick={() => onSelect(row.container)}>
				<header>
					{#if showRank}
						<span class={`rank rank-${index + 1}`}>#{index + 1}</span>
					{/if}
					<strong class="target" title={row.name}>{row.name}</strong>
					<span class={`state-tag ${stateClass(row.state)}`}>{stateLabel(row.state)}</span>
				</header>
				<div class="msg" title={row.stack}>
					<em class="stack-tag">{row.stack}</em>
				</div>
				<div class="metrics-grid">
					<em class="metric"><b>CPU</b><u>{row.cpu.toFixed(1)}%</u></em>
					<em class="metric"><b>MEM</b><u>{row.memory.toFixed(1)}%</u></em>
					<em class="metric" class:dim={!(row.gpu && row.gpu > 0)}><b>GPU</b><u>{row.gpu && row.gpu > 0 ? `${row.gpu.toFixed(1)}%` : '-'}</u></em>
					<em class="metric"><b>NET</b><u>{compactMetrics ? formatRateCompact(row.network) : formatRate(row.network)}</u></em>
				</div>
			</button>
		{/each}
		{#if top.length === 0}
			<div class="empty">표시할 컨테이너가 없습니다.</div>
		{/if}
	</div>
</section>

<style>
	.hot-panel {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 6px;
		min-height: 0;
		min-width: 0;
		height: 100%;
	}

	.hot-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		min-height: 22px;
	}

	.title {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 850;
		min-width: 0;
		overflow: hidden;
	}

	.flame {
		font-size: 12px;
		line-height: 1;
		flex: 0 0 auto;
	}

	.title-text {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.hot-head small {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		flex: 0 0 auto;
	}

	.hot-list {
		display: flex;
		flex-direction: column;
		gap: 5px;
		min-height: 0;
		overflow-y: auto;
		padding-right: 2px;
	}

	.hot-panel.horizontal .hot-list {
		display: grid;
		grid-auto-flow: column;
		grid-auto-columns: minmax(0, 1fr);
		gap: 6px;
		overflow: visible;
	}

	.hot-list::-webkit-scrollbar {
		width: 4px;
	}
	.hot-list::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.22);
		border-radius: 2px;
	}

	.row {
		display: grid;
		grid-template-rows: auto auto auto;
		gap: 4px;
		padding: 7px 10px 8px;
		border: 1px solid rgba(100, 116, 139, 0.18);
		border-left: 3px solid #94a3b8;
		border-radius: 7px;
		background: rgba(15, 23, 42, 0.55);
		text-align: left;
		cursor: pointer;
		min-width: 0;
		font-size: 11px;
		color: var(--text-primary);
		transition: border-color 0.12s ease, transform 0.12s ease, background-color 0.12s ease;
	}

	.row:hover {
		border-color: rgba(48, 213, 200, 0.45);
		transform: translateY(-1px);
	}

	.row.running { border-left-color: #34d399; background: rgba(52, 211, 153, 0.05); }
	.row.paused { border-left-color: #fbbf24; background: rgba(251, 191, 36, 0.06); }
	.row.problem { border-left-color: #f87171; background: rgba(248, 113, 113, 0.07); }
	.row.stopped { border-left-color: #94a3b8; }

	.row header {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.rank {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 22px;
		padding: 1px 6px;
		border-radius: 999px;
		font-size: 9px;
		font-weight: 900;
		letter-spacing: 0.04em;
		flex: 0 0 auto;
		line-height: 1;
		background: rgba(248, 113, 113, 0.18);
		color: #f87171;
		border: 1px solid rgba(248, 113, 113, 0.32);
	}

	.rank-1 {
		background: rgba(251, 191, 36, 0.22);
		color: #fbbf24;
		border-color: rgba(251, 191, 36, 0.45);
	}
	.rank-2 {
		background: rgba(148, 163, 184, 0.18);
		color: #cbd5e1;
		border-color: rgba(148, 163, 184, 0.4);
	}
	.rank-3 {
		background: rgba(217, 119, 6, 0.2);
		color: #f59e0b;
		border-color: rgba(217, 119, 6, 0.45);
	}

	.target {
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.state-tag {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 1px 6px;
		border-radius: 999px;
		font-size: 9px;
		font-weight: 800;
		flex: 0 0 auto;
	}

	.state-tag.running { background: rgba(52, 211, 153, 0.2); color: #34d399; }
	.state-tag.paused { background: rgba(251, 191, 36, 0.22); color: #fbbf24; }
	.state-tag.problem { background: rgba(248, 113, 113, 0.22); color: #f87171; }
	.state-tag.stopped { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }

	.msg {
		display: flex;
		gap: 6px;
		align-items: center;
		margin: 0;
		padding-left: 4px;
		min-width: 0;
		overflow: hidden;
	}

	.stack-tag {
		font-style: normal;
		color: #94a3b8;
		font-size: 9px;
		font-weight: 800;
		background: rgba(2, 6, 23, 0.45);
		padding: 1px 6px;
		border-radius: 999px;
		flex: 0 0 auto;
		line-height: 1;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.metrics-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 4px;
		min-width: 0;
	}

	.metric {
		font-style: normal;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1px;
		padding: 4px 4px 5px;
		border-radius: 5px;
		background: rgba(2, 6, 23, 0.5);
		min-width: 0;
		overflow: hidden;
		line-height: 1.05;
	}

	.metric b {
		color: var(--text-muted);
		font-size: 8px;
		font-weight: 800;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		line-height: 1;
	}

	.metric u {
		text-decoration: none;
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 900;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 100%;
		line-height: 1.05;
	}

	.metric.dim {
		opacity: 0.5;
	}

	.metric.dim u {
		color: var(--text-muted);
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
