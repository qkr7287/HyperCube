<script lang="ts">
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import AutoSlideCarousel from './AutoSlideCarousel.svelte';
	import { view, type Server2dMetric } from '$lib/stores/server2d-view.svelte';

	type StackItem = {
		name: string;
		color: string;
		running: number;
		total: number;
		problem: number;
		cpuAvg: number;
		memoryAvg: number;
		networkAvg: number;
	};

	let {
		stacks = [] as StackItem[],
		pageSize = 10,
		intervalMs = 6000,
	}: {
		stacks?: StackItem[];
		pageSize?: number;
		intervalMs?: number;
	} = $props();

	const metric = $derived(view.selectedMetric);
	const soloed = $derived(view.soloStack);
	const paused = $derived(Boolean(view.soloStack));

	function setMetric(next: Server2dMetric) {
		view.selectedMetric = next;
	}

	function toggleSolo(name: string) {
		view.soloStack = view.soloStack === name ? null : name;
	}

	function valueFor(stack: StackItem): number {
		if (metric === 'memory') return stack.memoryAvg;
		if (metric === 'network') return stack.networkAvg;
		return stack.cpuAvg;
	}

	function intensityStyle(stack: StackItem, networkMax: number): string {
		const raw = valueFor(stack);
		let pct = 0;
		if (metric === 'network') {
			pct = networkMax > 0 ? Math.min(100, (raw / networkMax) * 100) : 0;
		} else {
			pct = Math.min(100, Math.max(0, raw));
		}
		return `--intensity:${pct.toFixed(0)}%`;
	}

	function formatValue(stack: StackItem): string {
		const raw = valueFor(stack);
		if (metric === 'network') return formatRate(raw);
		return `${raw.toFixed(1)}%`;
	}

	function formatRate(value: number): string {
		if (!Number.isFinite(value) || value <= 0) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let idx = 0;
		while (next >= 1024 && idx < units.length - 1) {
			next /= 1024;
			idx += 1;
		}
		return `${next.toFixed(next >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
	}

	const sorted = $derived.by(() =>
		[...stacks].sort((a, b) => valueFor(b) - valueFor(a)),
	);
	const networkMax = $derived(Math.max(1, ...stacks.map((s) => s.networkAvg)));
	const total = $derived(stacks.reduce((sum, s) => sum + s.total, 0));
	const runningAll = $derived(stacks.reduce((sum, s) => sum + s.running, 0));
	const problemAll = $derived(stacks.reduce((sum, s) => sum + s.problem, 0));
</script>

<aside class="sidebar">
	<div class="head">
		<div class="title">
			<span>스택 현황</span>
			<InfoTooltip text="서버의 모든 Docker Compose 스택입니다. 많으면 자동 슬라이드로 순환 노출됩니다. 스택을 마우스로 올리거나 클릭하면 Solo 모드로 전환되고, 클릭 시 순환이 멈춥니다." placement="bottom-start" />
		</div>
		<small>{stacks.length}개 · 실행 {runningAll}/{total}{#if problemAll > 0} · <b class="warn">문제 {problemAll}</b>{/if}</small>
	</div>

	<div class="metric-switch" role="tablist" aria-label="사이드바 지표">
		{#each ['cpu', 'memory', 'network'] as key (key)}
			<button
				type="button"
				role="tab"
				aria-selected={metric === key}
				class:active={metric === key}
				onclick={() => setMetric(key as Server2dMetric)}
			>
				{key === 'cpu' ? 'CPU' : key === 'memory' ? '메모리' : '트래픽'}
			</button>
		{/each}
	</div>

	<div class="body">
		<AutoSlideCarousel items={sorted} pageSize={pageSize} intervalMs={intervalMs} paused={paused}>
			{#snippet children(pageItems: StackItem[])}
				<div class="list" role="list">
					{#each pageItems as stack (stack.name)}
						<button
							type="button"
							role="listitem"
							class="item"
							class:active={soloed === stack.name}
							class:dim={soloed && soloed !== stack.name}
							class:problem={stack.problem > 0}
							style={`--stack-color:${stack.color}; ${intensityStyle(stack, networkMax)}`}
							onclick={() => toggleSolo(stack.name)}
						>
							<div class="head-row">
								<i class="stripe"></i>
								<strong class="name">{stack.name}</strong>
								<span class="count">
									<em class="running">{stack.running}/{stack.total}</em>
									{#if stack.problem > 0}<em class="problem-badge">!{stack.problem}</em>{/if}
								</span>
							</div>
							<div class="metric-row">
								<i class="bar"><u></u></i>
								<small class="value">{formatValue(stack)}</small>
							</div>
						</button>
					{/each}
					{#if pageItems.length === 0}
						<div class="empty">스택 정보가 없습니다.</div>
					{/if}
				</div>
			{/snippet}
		</AutoSlideCarousel>
	</div>
</aside>

<style>
	.sidebar {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
		min-width: 0;
		height: 100%;
	}

	.head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 6px;
	}

	.title {
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 900;
		display: inline-flex;
		align-items: center;
		letter-spacing: 0.02em;
	}

	.head small {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
	}

	.head small b.warn {
		color: #f87171;
		font-weight: 800;
	}

	.metric-switch {
		display: inline-flex;
		border: 1px solid rgba(100, 116, 139, 0.24);
		border-radius: 999px;
		padding: 2px;
		background: rgba(15, 23, 42, 0.65);
		align-self: flex-start;
	}

	.metric-switch button {
		border: none;
		background: transparent;
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 800;
		padding: 4px 11px;
		border-radius: 999px;
		cursor: pointer;
	}

	.metric-switch button.active {
		background: rgba(48, 213, 200, 0.22);
		color: #30d5c8;
	}

	.body {
		min-height: 0;
		flex: 1;
		display: flex;
		flex-direction: column;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 7px;
	}

	.item {
		display: grid;
		grid-template-rows: auto auto;
		gap: 4px;
		padding: 7px 11px 8px;
		border: 1px solid rgba(100, 116, 139, 0.2);
		border-radius: 8px;
		background: rgba(15, 23, 42, 0.58);
		color: var(--text-primary);
		text-align: left;
		cursor: pointer;
		transition: border-color 0.14s ease, background-color 0.14s ease, transform 0.14s ease, opacity 0.14s ease, box-shadow 0.14s ease;
	}

	.item:hover {
		border-color: color-mix(in srgb, var(--stack-color) 60%, rgba(48, 213, 200, 0.55));
		transform: translateY(-1px);
	}

	.item.active {
		border-color: var(--stack-color);
		background: color-mix(in srgb, var(--stack-color) 15%, rgba(15, 23, 42, 0.65));
		box-shadow: 0 0 0 1px var(--stack-color) inset, 0 0 12px color-mix(in srgb, var(--stack-color) 45%, transparent);
	}

	.item.dim {
		opacity: 0.4;
	}

	.item.problem {
		border-color: rgba(248, 113, 113, 0.5);
	}

	.head-row {
		display: grid;
		grid-template-columns: 5px minmax(0, 1fr) auto;
		gap: 7px;
		align-items: center;
	}

	.stripe {
		width: 5px;
		height: 18px;
		background: var(--stack-color, #30d5c8);
		border-radius: 3px;
		box-shadow: 0 0 10px color-mix(in srgb, var(--stack-color, #30d5c8) 55%, transparent);
	}

	.name {
		font-size: 13px;
		font-weight: 800;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		letter-spacing: 0.01em;
	}

	.count {
		display: inline-flex;
		gap: 4px;
	}

	.count em {
		font-style: normal;
		padding: 2px 7px;
		border-radius: 999px;
		background: rgba(2, 6, 23, 0.55);
		font-size: 10px;
		font-weight: 800;
	}

	.count em.running {
		color: #34d399;
	}

	.count em.problem-badge {
		background: rgba(248, 113, 113, 0.18);
		color: #f87171;
	}

	.metric-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 8px;
		align-items: center;
	}

	.bar {
		display: block;
		height: 8px;
		border-radius: 999px;
		background: rgba(30, 41, 59, 0.92);
		overflow: hidden;
		position: relative;
	}

	.bar u {
		display: block;
		height: 100%;
		width: var(--intensity, 0%);
		text-decoration: none;
		background: linear-gradient(90deg, color-mix(in srgb, var(--stack-color) 70%, #30d5c8), var(--stack-color));
		transition: width 0.2s ease;
		box-shadow: 0 0 6px color-mix(in srgb, var(--stack-color) 45%, transparent);
	}

	.value {
		font-size: 13px;
		font-weight: 900;
		color: var(--text-primary);
		min-width: 62px;
		text-align: right;
	}

	.all-metrics {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 4px;
	}

	.all-metrics span {
		display: inline-flex;
		gap: 4px;
		padding: 3px 6px;
		border-radius: 5px;
		background: rgba(2, 6, 23, 0.45);
		color: var(--text-secondary);
		font-size: 10px;
		font-weight: 800;
	}

	.all-metrics b {
		color: var(--text-muted);
		font-weight: 800;
	}

	.empty {
		padding: 14px;
		border: 1px dashed rgba(100, 116, 139, 0.3);
		border-radius: 8px;
		color: var(--text-muted);
		font-size: 12px;
		text-align: center;
	}
</style>
