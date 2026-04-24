<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
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

	const TOP_LIMIT = 10;
	const showAll = $derived(view.matrixShowAll);

	const visibleColumns = $derived.by(() => {
		const nets = showAll ? networkUsage : networkUsage.slice(0, TOP_LIMIT);
		const vols = showAll ? volumeUsage : volumeUsage.slice(0, TOP_LIMIT);
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

	function toggleShowAll() {
		view.matrixShowAll = !view.matrixShowAll;
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
	const visibleNetworkCount = $derived(showAll ? totalNetworks : Math.min(TOP_LIMIT, totalNetworks));
	const visibleVolumeCount = $derived(showAll ? totalVolumes : Math.min(TOP_LIMIT, totalVolumes));
</script>

<section class="matrix">
	<div class="head">
		<div class="title">
			프레임 다이어그램 <small>· 스택 × 네트워크/볼륨 관계도</small>
			<InfoTooltip text="각 스택(가로 행)이 어떤 네트워크(파랑 열)·볼륨(주황 열)을 공유하는지 한눈에 보여줍니다. 셀의 숫자는 해당 스택에서 그 네트워크/볼륨에 붙은 컨테이너 개수, 색이 진할수록 많이 쓰입니다. 셀을 누르면 해당 컨테이너 목록이 열립니다." placement="bottom-start" />
		</div>
		<div class="meta">
			<span>네트워크 {totalNetworks}개 · 볼륨 {totalVolumes}개 (표시 중: 네트워크 {visibleNetworkCount} · 볼륨 {visibleVolumeCount})</span>
			{#if totalNetworks > TOP_LIMIT || totalVolumes > TOP_LIMIT}
				<button type="button" class="toggle" onclick={toggleShowAll}>
					{showAll ? '상위만 보기' : '전체 보기'}
				</button>
			{/if}
		</div>
	</div>

	{#if sortedStacks.length === 0 || visibleColumns.length === 0}
		<div class="empty">네트워크/볼륨 정보가 없습니다.</div>
	{:else}
		<div class="scroll">
			<table>
				<thead>
					<tr>
						<th class="stack-col">스택 \ 네트워크·볼륨</th>
						{#each visibleColumns as column (column.kind + ':' + column.name)}
							<th class={`col ${column.kind}`}>
								<span class="col-name" title={column.name}>{column.name}</span>
								<small>{column.kind === 'network' ? 'NET' : 'VOL'} · {column.usage}</small>
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each sortedStacks as stack (stack.name)}
						<tr>
							<th class="stack-label" style={`--stack-color:${stack.color}`}>
								<strong>{stack.name}</strong>
								<small>{stack.containers.length}개</small>
							</th>
							{#each visibleColumns as column (column.kind + ':' + column.name)}
								{@const key = `${stack.name}__${column.kind}:${column.name}`}
								{@const cell = cellByKey.get(key)}
								{#if cell}
									<td
										class={`cell ${column.kind}`}
										style={`--v:${cellIntensity(cell.count).toFixed(0)}%`}
										title={`${stack.name} · ${column.name}\n${cell.count}개 컨테이너`}
									>
										<button
											type="button"
											onclick={() => openCell(stack.name, column)}
										>
											{cell.count}
										</button>
									</td>
								{:else}
									<td class="cell empty"></td>
								{/if}
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
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
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
	}

	.head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
	}

	.title {
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 850;
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}

	.title small {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
	}

	.meta {
		display: flex;
		align-items: center;
		gap: 8px;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 700;
		flex-wrap: wrap;
	}

	.toggle {
		padding: 3px 10px;
		border: 1px solid rgba(48, 213, 200, 0.4);
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.12);
		color: #30d5c8;
		font-size: 10px;
		font-weight: 800;
		cursor: pointer;
	}

	.scroll {
		overflow: auto;
		max-height: 320px;
		border: 1px solid rgba(100, 116, 139, 0.14);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.42);
	}

	.scroll::-webkit-scrollbar {
		width: 6px;
		height: 6px;
	}
	.scroll::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.28);
		border-radius: 3px;
	}

	table {
		border-collapse: separate;
		border-spacing: 0;
		font-size: 11px;
	}

	thead th {
		position: sticky;
		top: 0;
		z-index: 3;
		background: rgba(13, 17, 23, 0.96);
		border-bottom: 1px solid rgba(100, 116, 139, 0.2);
		padding: 6px 8px;
		min-width: 74px;
		text-align: center;
		color: var(--text-primary);
		font-weight: 800;
		font-size: 10px;
	}

	th.stack-col {
		text-align: left;
		min-width: 130px;
		z-index: 4;
		left: 0;
		color: var(--text-muted);
		font-size: 10px;
	}

	th.col {
		vertical-align: bottom;
	}

	th.col .col-name {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 110px;
	}

	th.col small {
		display: block;
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 700;
		margin-top: 2px;
	}

	th.col.network {
		border-top: 2px solid rgba(34, 211, 238, 0.6);
	}

	th.col.volume {
		border-top: 2px solid rgba(251, 146, 60, 0.6);
	}

	tbody th.stack-label {
		position: sticky;
		left: 0;
		z-index: 2;
		background: rgba(13, 17, 23, 0.96);
		border-right: 1px solid rgba(100, 116, 139, 0.16);
		padding: 6px 8px;
		text-align: left;
		border-left: 3px solid var(--stack-color, #30d5c8);
	}

	tbody th.stack-label strong {
		display: block;
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 150px;
	}

	tbody th.stack-label small {
		color: var(--text-muted);
		font-size: 9px;
	}

	td.cell {
		padding: 0;
		text-align: center;
		border-right: 1px solid rgba(100, 116, 139, 0.08);
		border-bottom: 1px solid rgba(100, 116, 139, 0.08);
		position: relative;
	}

	td.cell button {
		width: 100%;
		height: 100%;
		min-height: 28px;
		padding: 4px 6px;
		border: none;
		background: color-mix(in srgb, #f87171 var(--v), rgba(51, 65, 85, 0.4));
		color: #f8fafc;
		font-weight: 800;
		font-size: 11px;
		cursor: pointer;
		transition: transform 0.1s ease, outline 0.1s ease;
	}

	td.cell.network button {
		background: color-mix(in srgb, #22d3ee var(--v), rgba(51, 65, 85, 0.4));
		color: #0b1320;
	}

	td.cell.volume button {
		background: color-mix(in srgb, #fb923c var(--v), rgba(51, 65, 85, 0.4));
		color: #0b1320;
	}

	td.cell button:hover {
		outline: 2px solid rgba(48, 213, 200, 0.55);
		outline-offset: -2px;
	}

	td.cell.empty {
		background: transparent;
		min-height: 28px;
	}

	.empty {
		padding: 18px;
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
