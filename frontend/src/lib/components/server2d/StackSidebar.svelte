<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import SortDirToggle from './SortDirToggle.svelte';
	import { view, type Server2dSortDir } from '$lib/stores/server2d-view.svelte';

	type StackItem = {
		name: string;
		color: string;
		running: number;
		total: number;
		problem: number;
		cpuAvg: number;
		memoryAvg: number;
		networkAvg: number;
		gpuAvg: number | null;
	};

	let {
		stacks = [] as StackItem[],
		focusIntervalMs = 27000,
	}: {
		stacks?: StackItem[];
		focusIntervalMs?: number;
	} = $props();

	const FOCUS_TICK = 80;

	const soloed = $derived(view.soloStack);
	const sortDir = $derived(view.stackSortDir);
	const focusPaused = $derived(view.stackFocusPaused);

	let focusIndex = $state(0);
	let focusProgress = $state(0);
	let focusOwnedSolo = $state(false);
	let focusTimer: ReturnType<typeof setInterval> | null = null;
	let listEl: HTMLDivElement | null = null;
	let itemEls: (HTMLButtonElement | null)[] = [];

	const focusRunning = $derived(!focusPaused && stacks.length > 1);

	function setSortDir(next: Server2dSortDir) {
		view.stackSortDir = next;
	}

	function toggleFocus() {
		const wasPaused = view.stackFocusPaused;
		view.stackFocusPaused = !wasPaused;
		focusProgress = 0;
		if (wasPaused) {
			const target = sorted[focusIndex]?.name ?? null;
			if (target) {
				focusOwnedSolo = true;
				view.soloStack = target;
			}
		} else {
			focusOwnedSolo = false;
			view.soloStack = null;
		}
	}

	function toggleSolo(name: string) {
		focusOwnedSolo = false;
		if (!view.stackFocusPaused) view.stackFocusPaused = true;
		view.soloStack = view.soloStack === name ? null : name;
	}

	function networkPct(value: number, max: number): number {
		if (!Number.isFinite(value) || value <= 0 || max <= 0) return 0;
		return Math.min(100, (value / max) * 100);
	}

	function totalScore(stack: StackItem, networkMax: number): number {
		const net = networkPct(stack.networkAvg, networkMax);
		const gpu = typeof stack.gpuAvg === 'number' ? stack.gpuAvg : 0;
		return stack.cpuAvg + stack.memoryAvg + net + gpu;
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

	function formatPercent(value: number): string {
		if (!Number.isFinite(value)) return '0%';
		return `${Math.max(0, Math.min(999, value)).toFixed(0)}%`;
	}

	function levelOf(value: number): 'low' | 'mid' | 'high' {
		if (value >= 80) return 'high';
		if (value >= 50) return 'mid';
		return 'low';
	}

	const networkMax = $derived(Math.max(1, ...stacks.map((s) => s.networkAvg)));

	const sorted = $derived.by(() => {
		const list = [...stacks];
		const sign = sortDir === 'asc' ? 1 : -1;
		return list.sort((a, b) => sign * (totalScore(a, networkMax) - totalScore(b, networkMax)));
	});

	const total = $derived(stacks.reduce((sum, s) => sum + s.total, 0));
	const runningAll = $derived(stacks.reduce((sum, s) => sum + s.running, 0));
	const problemAll = $derived(stacks.reduce((sum, s) => sum + s.problem, 0));

	const focusedName = $derived.by(() => {
		if (sorted.length === 0) return null;
		const safeIdx = Math.max(0, Math.min(sorted.length - 1, focusIndex));
		return sorted[safeIdx]?.name ?? null;
	});

	function advanceFocus() {
		if (sorted.length === 0) {
			focusIndex = 0;
			return;
		}
		focusIndex = (focusIndex + 1) % sorted.length;
		focusProgress = 0;
		const next = sorted[focusIndex]?.name ?? null;
		if (next) {
			focusOwnedSolo = true;
			view.soloStack = next;
		}
	}

	function focusTick() {
		if (!focusRunning) return;
		const steps = Math.max(1, Math.floor(focusIntervalMs / FOCUS_TICK));
		const next = focusProgress + 100 / steps;
		if (next >= 100) advanceFocus();
		else focusProgress = next;
	}

	$effect(() => {
		focusIntervalMs;
		if (focusTimer) clearInterval(focusTimer);
		focusTimer = setInterval(focusTick, FOCUS_TICK);
		return () => {
			if (focusTimer) clearInterval(focusTimer);
		};
	});

	$effect(() => {
		if (!focusRunning) focusProgress = 0;
	});

	$effect(() => {
		if (focusIndex >= sorted.length) focusIndex = 0;
	});

	$effect(() => {
		if (!focusRunning || !focusedName) return;
		const idx = sorted.findIndex((s) => s.name === focusedName);
		const el = itemEls[idx];
		if (el && typeof el.scrollIntoView === 'function') {
			el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
		}
	});

	$effect(() => {
		if (!soloed) return;
		const idx = sorted.findIndex((s) => s.name === soloed);
		if (idx < 0) return;
		const el = itemEls[idx];
		if (el && typeof el.scrollIntoView === 'function') {
			el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
		}
	});

	$effect(() => {
		const current = view.soloStack;
		if (!focusOwnedSolo) return;
		const expected = sorted[focusIndex]?.name ?? null;
		if (current === expected) return;
		focusOwnedSolo = false;
		if (!view.stackFocusPaused) view.stackFocusPaused = true;
		focusProgress = 0;
		if (current) {
			const idx = sorted.findIndex((s) => s.name === current);
			if (idx >= 0) focusIndex = idx;
		}
	});

	onMount(() => {
		focusTimer = setInterval(focusTick, FOCUS_TICK);
	});

	onDestroy(() => {
		if (focusTimer) clearInterval(focusTimer);
	});
</script>

<aside class="sidebar">
	<div class="head">
		<div class="head-top">
			<div class="title">
				<span>스택 현황</span>
				<InfoTooltip text={`서버의 모든 Docker Compose 스택 목록입니다.\n\n• 종합 사용량(CPU+MEM+NET+GPU) 기준 정렬\n• 각 카드에 4개 자원 사용량 미니타일 표시\n• 클릭 = 해당 스택만 보는 Solo 모드\n• 하단 ▶︎ = 스택 포커스 애니메이션 (디폴트 OFF)`} placement="bottom-start" />
			</div>
			<small>{stacks.length}개 · 실행 {runningAll}/{total}{#if problemAll > 0} · <b class="warn">문제 {problemAll}</b>{/if}</small>
		</div>
		<div class="head-tools">
			<span class="sort-label">종합 사용량 정렬</span>
			<SortDirToggle value={sortDir} onChange={setSortDir} />
		</div>
	</div>

	<div class="body" bind:this={listEl} role="list">
		{#each sorted as stack, idx (stack.name)}
			{@const isFocused = focusedName === stack.name}
			{@const isSoloed = soloed === stack.name}
			{@const dimmed = soloed && !isSoloed}
			{@const hasGpu = typeof stack.gpuAvg === 'number'}
			<button
				type="button"
				role="listitem"
				class="item"
				class:active={isSoloed}
				class:dim={dimmed}
				class:focused={isFocused && focusRunning}
				class:problem={stack.problem > 0}
				class:has-gpu={hasGpu}
				style={`--stack-color:${stack.color};`}
				bind:this={itemEls[idx]}
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
				<div class="metric-tiles" class:has-gpu={hasGpu}>
					<div class="tile" data-level={levelOf(stack.cpuAvg)} data-kind="cpu">
						<span class="tile-label">CPU</span>
						<strong class="tile-value">{formatPercent(stack.cpuAvg)}</strong>
					</div>
					<div class="tile" data-level={levelOf(stack.memoryAvg)} data-kind="mem">
						<span class="tile-label">MEM</span>
						<strong class="tile-value">{formatPercent(stack.memoryAvg)}</strong>
					</div>
					<div class="tile" data-level={levelOf(networkPct(stack.networkAvg, networkMax))} data-kind="net">
						<span class="tile-label">NET</span>
						<strong class="tile-value">{formatRate(stack.networkAvg)}</strong>
					</div>
					{#if hasGpu}
						<div class="tile" data-level={levelOf(stack.gpuAvg as number)} data-kind="gpu">
							<span class="tile-label">GPU</span>
							<strong class="tile-value">{formatPercent(stack.gpuAvg as number)}</strong>
						</div>
					{/if}
				</div>
			</button>
		{/each}
		{#if sorted.length === 0}
			<div class="empty">스택 정보가 없습니다.</div>
		{/if}
	</div>

	<div class="focus-foot">
		<button
			type="button"
			class="focus-btn"
			class:paused={focusPaused}
			title={focusPaused ? '스택 포커스 애니메이션 재생' : '스택 포커스 애니메이션 정지'}
			aria-label={focusPaused ? '재생' : '정지'}
			onclick={toggleFocus}
		>
			{#if focusPaused}
				<svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor"><polygon points="6,4 20,12 6,20"/></svg>
				<span>재생</span>
			{:else}
				<svg viewBox="0 0 24 24" width="10" height="10" fill="currentColor"><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></svg>
				<span>정지</span>
			{/if}
		</button>
		<div class="focus-progress" class:idle={!focusRunning} aria-hidden="true">
			<i style={`width:${focusRunning ? focusProgress.toFixed(1) : focusPaused ? 0 : 100}%`}></i>
		</div>
		<small class="focus-count">
			{#if sorted.length > 0 && focusRunning}
				{Math.min(focusIndex + 1, sorted.length)} / {sorted.length}
			{:else if sorted.length > 0}
				{sorted.length}
			{/if}
		</small>
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
		gap: 8px;
		justify-content: space-between;
	}

	.sort-label {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 800;
		letter-spacing: 0.02em;
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

	.body {
		min-height: 0;
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 7px;
		overflow-y: auto;
		padding-right: 2px;
	}

	.body::-webkit-scrollbar {
		width: 4px;
	}

	.body::-webkit-scrollbar-thumb {
		background: rgba(148, 163, 184, 0.22);
		border-radius: 2px;
	}

	.item {
		display: grid;
		grid-template-rows: auto auto;
		gap: 6px;
		padding: 7px 10px 8px;
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

	.item.active,
	.item.focused {
		border-color: var(--stack-color);
		background: color-mix(in srgb, var(--stack-color) 15%, rgba(15, 23, 42, 0.65));
		transform: translateY(-1px) scale(1.01);
		box-shadow:
			0 0 0 1px var(--stack-color) inset,
			0 0 16px color-mix(in srgb, var(--stack-color) 60%, transparent),
			0 0 28px color-mix(in srgb, var(--stack-color) 35%, transparent);
		animation: focus-pulse 1.6s ease-in-out infinite;
	}

	@keyframes focus-pulse {
		0%, 100% {
			box-shadow:
				0 0 0 1px var(--stack-color) inset,
				0 0 12px color-mix(in srgb, var(--stack-color) 50%, transparent),
				0 0 22px color-mix(in srgb, var(--stack-color) 25%, transparent);
		}
		50% {
			box-shadow:
				0 0 0 1px var(--stack-color) inset,
				0 0 18px color-mix(in srgb, var(--stack-color) 70%, transparent),
				0 0 32px color-mix(in srgb, var(--stack-color) 45%, transparent);
		}
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

	.metric-tiles {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 4px;
	}

	.metric-tiles.has-gpu {
		grid-template-columns: repeat(4, minmax(0, 1fr));
	}

	.tile {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1px;
		padding: 4px 2px 5px;
		border-radius: 6px;
		border: 1px solid rgba(148, 163, 184, 0.2);
		background: rgba(2, 6, 23, 0.55);
		min-width: 0;
	}

	.tile-label {
		font-size: 9px;
		font-weight: 800;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--text-muted);
	}

	.tile-value {
		font-size: 11px;
		font-weight: 900;
		color: var(--text-primary);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 100%;
	}

	.tile[data-kind='cpu'] .tile-label { color: #30d5c8; }
	.tile[data-kind='mem'] .tile-label { color: #60a5fa; }
	.tile[data-kind='net'] .tile-label { color: #fbbf24; }
	.tile[data-kind='gpu'] .tile-label { color: #f472b6; }

	.tile[data-level='mid'] {
		border-color: rgba(251, 191, 36, 0.4);
		background: rgba(251, 191, 36, 0.08);
	}

	.tile[data-level='high'] {
		border-color: rgba(248, 113, 113, 0.5);
		background: rgba(248, 113, 113, 0.12);
	}

	.tile[data-level='high'] .tile-value {
		color: #fca5a5;
	}

	.empty {
		padding: 14px;
		border: 1px dashed rgba(100, 116, 139, 0.3);
		border-radius: 8px;
		color: var(--text-muted);
		font-size: 12px;
		text-align: center;
	}

	.focus-foot {
		flex: 0 0 auto;
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 8px;
		padding-top: 6px;
		border-top: 1px dashed rgba(100, 116, 139, 0.25);
	}

	.focus-btn {
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

	.focus-btn:hover {
		background: rgba(248, 113, 113, 0.26);
	}

	.focus-btn.paused {
		background: rgba(52, 211, 153, 0.2);
		border-color: rgba(52, 211, 153, 0.6);
		color: #34d399;
		box-shadow: 0 0 12px rgba(52, 211, 153, 0.35);
		animation: focus-btn-paused-glow 1.6s ease-in-out infinite;
	}

	.focus-btn.paused:hover {
		background: rgba(52, 211, 153, 0.3);
	}

	@keyframes focus-btn-paused-glow {
		0%, 100% { box-shadow: 0 0 12px rgba(52, 211, 153, 0.3); }
		50% { box-shadow: 0 0 18px rgba(52, 211, 153, 0.55); }
	}

	.focus-btn span {
		line-height: 1;
	}

	.focus-progress {
		flex: 1;
		height: 5px;
		border-radius: 999px;
		background: rgba(30, 41, 59, 0.65);
		overflow: hidden;
	}

	.focus-progress i {
		display: block;
		height: 100%;
		background: linear-gradient(90deg, #30d5c8, #60a5fa);
		width: 0%;
		transition: width 80ms linear;
	}

	.focus-progress.idle i {
		background: repeating-linear-gradient(
			-45deg,
			rgba(248, 113, 113, 0.4) 0,
			rgba(248, 113, 113, 0.4) 4px,
			rgba(248, 113, 113, 0.15) 4px,
			rgba(248, 113, 113, 0.15) 8px
		);
	}

	.focus-count {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		min-width: 38px;
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
</style>
