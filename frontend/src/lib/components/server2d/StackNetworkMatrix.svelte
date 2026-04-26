<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import AutoSlideCarousel from './AutoSlideCarousel.svelte';
	import { view } from '$lib/stores/server2d-view.svelte';

	type MatrixContainer = {
		id: string;
		name: string;
		stack: string;
		state: string;
		networks: string[];
		volumes: string[];
		container: any;
	};

	type MatrixStack = {
		name: string;
		color: string;
		containers: MatrixContainer[];
	};

	let {
		stacks = [] as MatrixStack[],
		onSelectContainer = (_container: any) => {},
	}: {
		stacks?: MatrixStack[];
		onSelectContainer?: (container: any) => void;
	} = $props();

	type Column = {
		kind: 'network' | 'volume';
		name: string;
		usage: number;
	};

	type Cell = {
		stack: string;
		column: Column;
		count: number;
		containers: MatrixContainer[];
	};

	type ModalState = {
		open: boolean;
		stack: string;
		column: Column | null;
		containers: MatrixContainer[];
	};

	let modalState = $state<ModalState>({ open: false, stack: '', column: null, containers: [] });

	const networkUsage = $derived.by(() => {
		const counts = new Map<string, number>();
		for (const stack of stacks) {
			for (const container of stack.containers) {
				for (const name of container.networks ?? []) {
					counts.set(name, (counts.get(name) ?? 0) + 1);
				}
			}
		}
		return [...counts.entries()]
			.map(([name, usage]) => ({ kind: 'network' as const, name, usage }))
			.sort((a, b) => b.usage - a.usage);
	});

	const volumeUsage = $derived.by(() => {
		const counts = new Map<string, number>();
		for (const stack of stacks) {
			for (const container of stack.containers) {
				for (const name of container.volumes ?? []) {
					counts.set(name, (counts.get(name) ?? 0) + 1);
				}
			}
		}
		return [...counts.entries()]
			.map(([name, usage]) => ({ kind: 'volume' as const, name, usage }))
			.sort((a, b) => b.usage - a.usage);
	});

	const NET_COLS = 6;
	const VOL_COLS = 4;
	const ROWS_PER_PAGE = 5;

	const visibleColumns = $derived.by(() => {
		const nets = networkUsage.slice(0, NET_COLS);
		const vols = volumeUsage.slice(0, VOL_COLS);
		return [...nets, ...vols];
	});

	const sortedStacks = $derived.by(() =>
		[...stacks].sort((a, b) => b.containers.length - a.containers.length),
	);

	const cellByKey = $derived.by(() => {
		const map = new Map<string, Cell>();
		for (const stack of sortedStacks) {
			for (const column of visibleColumns) {
				const matches = stack.containers.filter((container) => {
					const list = column.kind === 'network' ? container.networks : container.volumes;
					return (list ?? []).includes(column.name);
				});
				if (matches.length) {
					map.set(`${stack.name}__${column.kind}:${column.name}`, {
						stack: stack.name,
						column,
						count: matches.length,
						containers: matches,
					});
				}
			}
		}
		return map;
	});

	const maxCellCount = $derived.by(() => {
		let max = 1;
		for (const cell of cellByKey.values()) {
			if (cell.count > max) max = cell.count;
		}
		return max;
	});

	function cellIntensity(count: number): number {
		if (count <= 0) return 0;
		return Math.max(18, Math.min(100, (count / maxCellCount) * 100));
	}

	function openCell(stackName: string, column: Column) {
		const key = `${stackName}__${column.kind}:${column.name}`;
		const cell = cellByKey.get(key);
		if (!cell) return;
		modalState = {
			open: true,
			stack: stackName,
			column,
			containers: cell.containers,
		};
	}

	function closeModal() {
		modalState = { open: false, stack: '', column: null, containers: [] };
	}

	function stateLabel(state: string): string {
		if (state === 'running') return '실행';
		if (state === 'exited' || state === 'stopped') return '중지';
		if (state === 'paused') return '일시정지';
		if (state === 'restarting') return '재시작';
		if (state === 'dead') return '장애';
		return state || '-';
	}

	const totalNetworks = $derived(networkUsage.length);
	const totalVolumes = $derived(volumeUsage.length);
	const paused = $derived(modalState.open);
</script>

<section class="matrix">
	<div class="head">
		<div class="title">
			프레임 다이어그램
			<InfoTooltip text={`스택과 네트워크/볼륨의 공유 관계도.\n\n• 가로 행 = 스택\n• 파랑 열 = 네트워크 (사용 많은 ${NET_COLS}개)\n• 주황 열 = 볼륨 (사용 많은 ${VOL_COLS}개)\n• 셀 숫자 = 그 스택의 멤버 수\n• 색 진할수록 많이 사용\n• 셀 클릭 = 멤버 컨테이너 목록`} placement="bottom-start" />
		</div>
		<small class="meta">{totalNetworks} 네트워크 · {totalVolumes} 볼륨 · {sortedStacks.length} 스택</small>
	</div>

	{#if sortedStacks.length === 0 || visibleColumns.length === 0}
		<div class="empty">네트워크/볼륨 정보가 없습니다.</div>
	{:else}
		<div class="layout">
			<div class="header-row" style={`--cols:${visibleColumns.length}`}>
				<div class="corner"></div>
				{#each visibleColumns as column (column.kind + ':' + column.name)}
					<div class={`col-head ${column.kind}`} title={`${column.kind === 'network' ? '네트워크' : '볼륨'}: ${column.name}\n사용: ${column.usage}개 컨테이너`}>
						<span class="col-name">{column.name}</span>
						<small>{column.kind === 'network' ? 'NET' : 'VOL'}·{column.usage}</small>
					</div>
				{/each}
			</div>

			<div class="rows-host">
				<AutoSlideCarousel items={sortedStacks} pageSize={ROWS_PER_PAGE} intervalMs={7500} {paused}>
					{#snippet children(pageItems: MatrixStack[])}
						<div class="rows" style={`--cols:${visibleColumns.length}; --rows:${pageItems.length};`}>
							{#each pageItems as stack (stack.name)}
								<div class="row" style={`--stack-color:${stack.color}`}>
									<div class="row-label" title={`${stack.name} (${stack.containers.length}개)`}>
										<i class="stripe"></i>
										<strong>{stack.name}</strong>
										<small>{stack.containers.length}</small>
									</div>
									{#each visibleColumns as column (column.kind + ':' + column.name)}
										{@const key = `${stack.name}__${column.kind}:${column.name}`}
										{@const cell = cellByKey.get(key)}
										{#if cell}
											<button
												type="button"
												class={`cell ${column.kind}`}
												style={`--v:${cellIntensity(cell.count).toFixed(0)}%`}
												title={`${stack.name} · ${column.name}\n${cell.count}개 컨테이너`}
												onclick={() => openCell(stack.name, column)}
											>{cell.count}</button>
										{:else}
											<div class="cell empty"></div>
										{/if}
									{/each}
								</div>
							{/each}
						</div>
					{/snippet}
				</AutoSlideCarousel>
			</div>
		</div>
	{/if}
</section>

{#if modalState.open && modalState.column}
	<div class="modal-backdrop" onclick={closeModal} role="presentation">
		<div class="modal-card" role="dialog" aria-modal="true" onclick={(event) => event.stopPropagation()}>
			<header>
				<div>
					<strong>{modalState.stack}</strong> ·
					<em class={modalState.column.kind}>{modalState.column.kind === 'network' ? '네트워크' : '볼륨'}</em>
					<code>{modalState.column.name}</code>
				</div>
				<button type="button" class="close" onclick={closeModal} aria-label="닫기">✕</button>
			</header>
			<div class="modal-body">
				{#each modalState.containers as container (container.id)}
					<button
						type="button"
						class="member"
						onclick={() => { onSelectContainer(container.container); closeModal(); }}
					>
						<div>
							<strong>{container.name}</strong>
							<small>{stateLabel(container.state)}</small>
						</div>
						<span class="arrow">열기 →</span>
					</button>
				{:else}
					<div class="modal-empty">멤버 컨테이너 없음</div>
				{/each}
			</div>
		</div>
	</div>
{/if}

<style>
	.matrix {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 6px;
		min-height: 0;
		min-width: 0;
		height: 100%;
		overflow: hidden;
	}

	.head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 8px;
		min-height: 22px;
	}

	.title {
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 850;
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	.meta {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		flex: 0 1 auto;
	}

	.layout {
		display: grid;
		grid-template-rows: auto minmax(0, 1fr);
		gap: 4px;
		min-height: 0;
		overflow: hidden;
	}

	.header-row {
		display: grid;
		grid-template-columns: minmax(80px, 1fr) repeat(var(--cols), minmax(0, 1fr));
		gap: 3px;
		align-items: end;
	}

	.corner {
		min-height: 28px;
	}

	.col-head {
		display: grid;
		gap: 1px;
		padding: 4px 5px;
		border-radius: 5px;
		background: rgba(15, 23, 42, 0.7);
		text-align: center;
		min-width: 0;
	}

	.col-head.network {
		border-top: 2px solid rgba(34, 211, 238, 0.7);
	}

	.col-head.volume {
		border-top: 2px solid rgba(251, 146, 60, 0.7);
	}

	.col-head .col-name {
		display: block;
		color: var(--text-primary);
		font-size: 9px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.col-head small {
		color: var(--text-muted);
		font-size: 8px;
		font-weight: 700;
	}

	.rows-host {
		min-height: 0;
		min-width: 0;
		overflow: hidden;
	}

	.rows {
		display: grid;
		grid-auto-flow: row;
		grid-auto-rows: minmax(0, 1fr);
		gap: 3px;
		min-height: 0;
		height: 100%;
	}

	.row {
		display: grid;
		grid-template-columns: minmax(80px, 1fr) repeat(var(--cols), minmax(0, 1fr));
		gap: 3px;
		min-width: 0;
		min-height: 0;
		align-items: stretch;
	}

	.row-label {
		display: grid;
		grid-template-columns: 4px minmax(0, 1fr) auto;
		align-items: center;
		gap: 5px;
		padding: 4px 6px;
		border-radius: 5px;
		background: rgba(15, 23, 42, 0.6);
		min-width: 0;
		overflow: hidden;
	}

	.stripe {
		width: 4px;
		height: 16px;
		background: var(--stack-color, #30d5c8);
		border-radius: 2px;
	}

	.row-label strong {
		color: var(--text-primary);
		font-size: 10px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}

	.row-label small {
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 800;
	}

	.cell {
		display: flex;
		align-items: center;
		justify-content: center;
		border: none;
		padding: 0;
		font-weight: 800;
		font-size: 11px;
		cursor: pointer;
		border-radius: 4px;
		min-width: 0;
		min-height: 22px;
		transition: outline 0.1s ease;
	}

	.cell.network {
		background: color-mix(in srgb, #22d3ee var(--v), rgba(15, 23, 42, 0.55));
		color: #0b1320;
	}

	.cell.volume {
		background: color-mix(in srgb, #fb923c var(--v), rgba(15, 23, 42, 0.55));
		color: #0b1320;
	}

	.cell:hover {
		outline: 2px solid rgba(48, 213, 200, 0.65);
		outline-offset: -2px;
	}

	.cell.empty {
		cursor: default;
		background: rgba(15, 23, 42, 0.4);
		min-height: 22px;
	}

	.empty {
		padding: 14px;
		border: 1px dashed rgba(100, 116, 139, 0.3);
		border-radius: 8px;
		color: var(--text-muted);
		text-align: center;
		font-size: 11px;
	}

	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 2000;
		background: rgba(2, 6, 23, 0.7);
		display: grid;
		place-items: center;
		padding: 24px;
	}

	.modal-card {
		width: min(520px, 100%);
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		border: 1px solid rgba(48, 213, 200, 0.28);
		border-radius: 12px;
		background: var(--bg-card);
		overflow: hidden;
		box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6);
	}

	.modal-card header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		padding: 12px 16px;
		border-bottom: 1px solid var(--border);
		color: var(--text-primary);
		font-size: 13px;
	}

	.modal-card code {
		font-family: 'JetBrains Mono', 'Consolas', monospace;
		background: rgba(2, 6, 23, 0.4);
		padding: 2px 6px;
		border-radius: 4px;
		font-size: 12px;
	}

	.modal-card em.network { color: #22d3ee; font-style: normal; font-weight: 800; }
	.modal-card em.volume { color: #fb923c; font-style: normal; font-weight: 800; }

	.close {
		background: transparent;
		border: none;
		color: var(--text-muted);
		font-size: 16px;
		cursor: pointer;
		padding: 0 6px;
	}

	.modal-body {
		padding: 10px 12px 14px;
		overflow-y: auto;
		display: grid;
		gap: 6px;
	}

	.member {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 8px 10px;
		border: 1px solid var(--border);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.55);
		color: var(--text-primary);
		cursor: pointer;
	}

	.member:hover {
		border-color: rgba(48, 213, 200, 0.35);
	}

	.member strong {
		display: block;
		font-size: 12px;
		font-weight: 800;
	}

	.member small {
		color: var(--text-muted);
		font-size: 10px;
	}

	.arrow {
		color: #30d5c8;
		font-size: 11px;
		font-weight: 800;
	}

	.modal-empty {
		padding: 16px;
		text-align: center;
		color: var(--text-muted);
		font-size: 11px;
	}
</style>
