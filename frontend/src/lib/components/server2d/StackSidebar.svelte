<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import AutoSlideCarousel from './AutoSlideCarousel.svelte';
	import SortDirToggle from './SortDirToggle.svelte';
	import { view, type Server2dMetric, type Server2dSortDir } from '$lib/stores/server2d-view.svelte';

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
		intervalMs = 12000,
		metricRotateMs = 18000,
	}: {
		stacks?: StackItem[];
		pageSize?: number;
		intervalMs?: number;
		metricRotateMs?: number;
	} = $props();

	const metric = $derived(view.selectedMetric);
	const soloed = $derived(view.soloStack);
	const externalPaused = $derived(Boolean(view.soloStack));
	const sortDir = $derived(view.stackSortDir);

	const METRIC_CYCLE: Server2dMetric[] = ['cpu', 'memory', 'network'];
	const METRIC_TICK = 80;

	let metricProgress = $state(0);
	let metricTimer: ReturnType<typeof setInterval> | null = null;
	const metricAutoPaused = $derived(view.metricAutoPaused);
	const metricRotating = $derived(!metricAutoPaused && !externalPaused);

	function setMetric(next: Server2dMetric) {
		view.selectedMetric = next;
		view.metricAutoPaused = true;
		metricProgress = 0;
	}

	function toggleMetricAutoRotate() {
		view.metricAutoPaused = !view.metricAutoPaused;
		metricProgress = 0;
	}

	function setSortDir(next: Server2dSortDir) {
		view.stackSortDir = next;
	}

	function advanceMetric() {
		const idx = METRIC_CYCLE.indexOf(view.selectedMetric);
		const next = METRIC_CYCLE[(idx + 1) % METRIC_CYCLE.length];
		view.selectedMetric = next;
		metricProgress = 0;
	}

	function metricTick() {
		if (!metricRotating) return;
		const steps = Math.max(1, Math.floor(metricRotateMs / METRIC_TICK));
		const next = metricProgress + 100 / steps;
		if (next >= 100) advanceMetric();
		else metricProgress = next;
	}

	$effect(() => {
		metricRotateMs;
		if (metricTimer) clearInterval(metricTimer);
		metricTimer = setInterval(metricTick, METRIC_TICK);
		return () => {
			if (metricTimer) clearInterval(metricTimer);
		};
	});

	onMount(() => {
		metricTimer = setInterval(metricTick, METRIC_TICK);
	});

	onDestroy(() => {
		if (metricTimer) clearInterval(metricTimer);
	});

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

	const sorted = $derived.by(() => {
		const list = [...stacks];
		const sign = sortDir === 'asc' ? 1 : -1;
		return list.sort((a, b) => sign * (valueFor(a) - valueFor(b)));
	});
	const networkMax = $derived(Math.max(1, ...stacks.map((s) => s.networkAvg)));
	const total = $derived(stacks.reduce((sum, s) => sum + s.total, 0));
	const runningAll = $derived(stacks.reduce((sum, s) => sum + s.running, 0));
	const problemAll = $derived(stacks.reduce((sum, s) => sum + s.problem, 0));
</script>

<aside class="sidebar">
	<div class="head">
		<div class="head-top">
			<div class="title">
				<span>스택 현황</span>
				<InfoTooltip text={`서버의 모든 Docker Compose 스택 목록입니다.\n\n• 부하 큰 스택 순으로 정렬\n• 스택이 많으면 자동 슬라이드 순환\n• 클릭 = 해당 스택만 보는 Solo 모드\n• Solo 모드일 때 자동 순환 정지`} placement="bottom-start" />
			</div>
			<small>{stacks.length}개 · 실행 {runningAll}/{total}{#if problemAll > 0} · <b class="warn">문제 {problemAll}</b>{/if}</small>
		</div>
		<div class="head-tools">
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
			<SortDirToggle value={sortDir} onChange={setSortDir} />
		</div>
	</div>

	<div class="body">
		<AutoSlideCarousel
			items={sorted}
			pageSize={pageSize}
			intervalMs={intervalMs}
			paused={externalPaused}
			userPaused={view.stacksPaused}
			hideBar={true}
			pauseLabel="스택 슬라이드"
		>
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

	<div class="metric-foot">
		<button
			type="button"
			class="metric-pause"
			class:paused={metricAutoPaused}
			title={metricAutoPaused ? '지표 자동 전환 재개' : '지표 자동 전환 일시정지'}
			aria-label={metricAutoPaused ? '재개' : '일시정지'}
			onclick={toggleMetricAutoRotate}
		>
			{#if metricAutoPaused}
				<svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor"><polygon points="6,4 20,12 6,20"/></svg>
				<span>재생</span>
			{:else}
				<svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>
				<span>정지</span>
			{/if}
		</button>
		<div class="metric-progress" class:idle={!metricRotating} aria-hidden="true">
			<i style={`width:${metricRotating ? metricProgress.toFixed(1) : metricAutoPaused ? 100 : 0}%`}></i>
		</div>
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
		flex-direction: column;
		gap: 6px;
	}

	.head-top {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 6px;
	}

	.head-tools {
		display: flex;
		align-items: center;
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

	.head-top small {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
	}

	.head-top small b.warn {
		color: #f87171;
		font-weight: 800;
	}

	.metric-foot {
		flex: 0 0 auto;
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 8px;
		padding-top: 6px;
		border-top: 1px dashed rgba(100, 116, 139, 0.25);
	}

	.metric-pause {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 5px;
		height: 22px;
		padding: 0 9px 0 8px;
		border: 1px solid rgba(248, 113, 113, 0.5);
		border-radius: 999px;
		background: rgba(248, 113, 113, 0.16);
		color: #f87171;
		cursor: pointer;
		flex: 0 0 auto;
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.02em;
		transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
	}

	.metric-pause:hover {
		background: rgba(248, 113, 113, 0.26);
	}

	.metric-pause.paused {
		background: rgba(52, 211, 153, 0.2);
		border-color: rgba(52, 211, 153, 0.6);
		color: #34d399;
		box-shadow: 0 0 12px rgba(52, 211, 153, 0.35);
		animation: metric-paused-glow 1.6s ease-in-out infinite;
	}

	.metric-pause.paused:hover {
		background: rgba(52, 211, 153, 0.3);
	}

	@keyframes metric-paused-glow {
		0%, 100% { box-shadow: 0 0 12px rgba(52, 211, 153, 0.3); }
		50% { box-shadow: 0 0 18px rgba(52, 211, 153, 0.55); }
	}

	.metric-pause span {
		line-height: 1;
	}

	.metric-progress {
		flex: 1;
		height: 5px;
		border-radius: 999px;
		background: rgba(30, 41, 59, 0.65);
		overflow: hidden;
	}

	.metric-progress i {
		display: block;
		height: 100%;
		background: linear-gradient(90deg, #30d5c8, #60a5fa);
		width: 0%;
		transition: width 80ms linear;
	}

	.metric-progress.idle i {
		background: repeating-linear-gradient(
			-45deg,
			rgba(52, 211, 153, 0.4) 0,
			rgba(52, 211, 153, 0.4) 4px,
			rgba(52, 211, 153, 0.15) 4px,
			rgba(52, 211, 153, 0.15) 8px
		);
	}

	.metric-switch {
		display: inline-flex;
		border: 1px solid rgba(100, 116, 139, 0.24);
		border-radius: 999px;
		padding: 2px;
		background: rgba(15, 23, 42, 0.65);
		flex: 1;
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
		flex: 1;
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
		overflow: hidden;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 7px;
		overflow-y: auto;
		padding-right: 2px;
		min-height: 0;
		flex: 1;
	}

	.list::-webkit-scrollbar {
		width: 4px;
	}

	.list::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.22);
		border-radius: 2px;
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

	.empty {
		padding: 14px;
		border: 1px dashed rgba(100, 116, 139, 0.3);
		border-radius: 8px;
		color: var(--text-muted);
		font-size: 12px;
		text-align: center;
	}
</style>
