<script lang="ts">
	import { onDestroy, untrack } from 'svelte';
	import type { FleetAgentRow } from '$lib/stores/fleet-store';
	import FleetAgentCard from './FleetAgentCard.svelte';

	let {
		agents = [],
		selectedId = null,
		range = '1h',
		onSelect = () => {},
		onOpen3d,
	}: {
		agents?: FleetAgentRow[];
		selectedId?: string | null;
		range?: '1m' | '5m' | '1h' | '24h' | '7d';
		onSelect?: (agentId: string) => void;
		onOpen3d?: (agentId: string) => void;
	} = $props();

	const INTERVAL_OPTIONS = [
		{ value: 5000, label: '5초' },
		{ value: 10000, label: '10초' },
		{ value: 30000, label: '30초' },
		{ value: 60000, label: '1분' },
	];
	const PAGE_SIZE = 10;

	let rotateInterval = $state(10000);
	let currentPage = $state(0);
	let autoRotate = $state(true);
	let hovering = $state(false);
	let rotateTimer: ReturnType<typeof setInterval> | null = null;

	let pagesCount = $derived(Math.max(1, Math.ceil(agents.length / PAGE_SIZE)));
	let safePage = $derived(Math.min(currentPage, pagesCount - 1));
	let pageIndexes = $derived(Array.from({ length: pagesCount }, (_, i) => i));
	let showRotation = $derived(pagesCount > 1);
	let showDots = $derived(pagesCount <= 8);

	let pages = $derived.by(() => {
		const out: FleetAgentRow[][] = [];
		for (let i = 0; i < pagesCount; i += 1) {
			out.push(agents.slice(i * PAGE_SIZE, i * PAGE_SIZE + PAGE_SIZE));
		}
		return out;
	});

	type Variant = 'full' | 'medium' | 'compact';
	type GridLayout = {
		cols: number;
		rows: number;
		firstSpans: boolean;
		variants: Variant[];
	};

	function calcGrid(count: number): GridLayout {
		// firstSpans 가 true 인 경우 첫 카드는 row 2개 차지 → 세로로 긴 공간 확보 →
		// full variant 로 승격. 그래야 "2대일 때와 같은 느낌"으로 metrics + extra 섹션
		// (컨테이너 분포 · 피크값 · 프로세스/네트워크/에이전트) 모두 노출.
		if (count <= 0) return { cols: 1, rows: 1, firstSpans: false, variants: ['full'] };
		if (count === 1) return { cols: 1, rows: 1, firstSpans: false, variants: ['full'] };
		if (count === 2) return { cols: 2, rows: 1, firstSpans: false, variants: ['full', 'full'] };
		if (count === 3) return { cols: 2, rows: 2, firstSpans: true, variants: ['full', 'medium', 'medium'] };
		if (count === 4) return { cols: 2, rows: 2, firstSpans: false, variants: ['medium', 'medium', 'medium', 'medium'] };
		if (count === 5) return {
			cols: 3,
			rows: 2,
			firstSpans: true,
			variants: ['full', 'medium', 'medium', 'medium', 'medium'],
		};
		if (count === 6) return {
			cols: 3,
			rows: 2,
			firstSpans: false,
			variants: Array(6).fill('compact') as Variant[],
		};
		// count 7, 9 는 cols=4/5 라 span 카드가 너무 좁아(~460/365px) full/medium
		// 의 multi-col extras 가 쪼개져 글자·chip 이 깨짐. span 대신 전부 compact
		// 균등 배치 — 빈 cell 1개는 감수.
		if (count === 7) return {
			cols: 4,
			rows: 2,
			firstSpans: false,
			variants: Array(7).fill('compact') as Variant[],
		};
		if (count === 8) return {
			cols: 4,
			rows: 2,
			firstSpans: false,
			variants: Array(8).fill('compact') as Variant[],
		};
		if (count === 9) return {
			cols: 5,
			rows: 2,
			firstSpans: false,
			variants: Array(9).fill('compact') as Variant[],
		};
		return {
			cols: 5,
			rows: 2,
			firstSpans: false,
			variants: Array(count).fill('compact') as Variant[],
		};
	}

	function clampPage(p: number): number {
		if (p < 0) return pagesCount - 1;
		if (p >= pagesCount) return 0;
		return p;
	}

	function goToPage(index: number) {
		currentPage = clampPage(index);
	}

	function nextPage() {
		goToPage(safePage + 1);
	}
	function prevPage() {
		goToPage(safePage - 1);
	}
	function toggleAuto() {
		autoRotate = !autoRotate;
	}

	function startTimer() {
		stopTimer();
		if (!autoRotate || !showRotation || hovering) return;
		rotateTimer = setInterval(() => {
			goToPage(safePage + 1);
		}, rotateInterval);
	}
	function stopTimer() {
		if (rotateTimer) {
			clearInterval(rotateTimer);
			rotateTimer = null;
		}
	}

	$effect(() => {
		autoRotate;
		hovering;
		showRotation;
		pagesCount;
		rotateInterval;
		startTimer();
	});

	// Keep selected server's page in view — only when selectedId itself changes,
	// not when parent re-renders the agents array (which would fight user navigation).
	$effect(() => {
		const id = selectedId;
		if (!id) return;
		untrack(() => {
			const idx = agents.findIndex((row) => row.agent.id === id);
			if (idx < 0) return;
			const page = Math.floor(idx / PAGE_SIZE);
			if (page !== currentPage) goToPage(page);
		});
	});


	onDestroy(stopTimer);
</script>

<section
	class="rotator"
	onmouseenter={() => (hovering = true)}
	onmouseleave={() => (hovering = false)}
	aria-label="전체 서버 카드"
>
	{#if agents.length === 0}
		<div class="empty">연결된 서버가 없습니다.</div>
	{:else}
		<div class="pages-wrapper">
			<div
				class="pages"
				style={`--pages-count: ${pagesCount}; width: ${pagesCount * 100}%; transform: translateX(-${pagesCount > 0 ? (100 / pagesCount) * safePage : 0}%);`}
			>
				{#each pages as pageAgents, pageIdx (pageIdx)}
					{@const layout = calcGrid(pageAgents.length)}
					<div class="page">
						<div
							class="grid"
							class:first-span={layout.firstSpans}
							style={`--cols: ${layout.cols}; --rows: ${layout.rows};`}
						>
							{#each pageAgents as agent, idx (agent.agent.id)}
								<FleetAgentCard
									{agent}
									variant={layout.variants[idx] ?? 'compact'}
									selected={selectedId === agent.agent.id}
									{range}
									{onSelect}
									{onOpen3d}
								/>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		</div>

		{#if showRotation}
			<div class="controls">
				<div class="controls-side controls-left">
					<span class="count">서버 {agents.length}대 · 페이지당 {PAGE_SIZE}대</span>
				</div>

				<div class="controls-center">
					<button type="button" class="nav" onclick={prevPage} title="이전 페이지">◀</button>
					{#if showDots}
						<div class="dots">
							{#each pageIndexes as i (i)}
								<button
									type="button"
									class="dot"
									class:active={i === safePage}
									onclick={() => goToPage(i)}
									title={`${i + 1} / ${pagesCount} 페이지`}
									aria-label={`${i + 1}페이지로 이동`}
								></button>
							{/each}
						</div>
					{:else}
						<span class="pages-count">{safePage + 1} / {pagesCount}</span>
					{/if}
					<button type="button" class="nav" onclick={nextPage} title="다음 페이지">▶</button>
				</div>

				<div class="controls-side controls-right">
					<span class="ctrl-label">회전 주기</span>
					<div class="interval-picker">
						{#each INTERVAL_OPTIONS as option}
							<button
								type="button"
								class="pill"
								class:active={rotateInterval === option.value}
								onclick={() => (rotateInterval = option.value)}
								aria-pressed={rotateInterval === option.value}
							>{option.label}</button>
						{/each}
					</div>

					<div class="auto-block">
						<span class="auto-state" class:on={autoRotate}>
							{#if autoRotate}
								<span class="auto-pulse"></span> 자동 회전 중
							{:else}
								<span class="auto-pulse off"></span> 회전 정지됨
							{/if}
						</span>
						<button
							type="button"
							class="switch"
							class:on={autoRotate}
							onclick={toggleAuto}
							role="switch"
							aria-checked={autoRotate}
							aria-label={autoRotate ? '자동 회전 끄기' : '자동 회전 켜기'}
							title={autoRotate ? '자동 회전 정지하기' : '자동 회전 시작하기'}
						>
							<span class="switch-thumb"></span>
						</button>
					</div>
				</div>
			</div>
		{/if}
	{/if}
</section>

<style>
	.rotator {
		min-height: 0;
		min-width: 0;
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: clamp(6px, 0.5vw, 12px);
		height: 100%;
	}
	.pages-wrapper {
		flex: 1;
		min-height: 0;
		min-width: 0;
		width: 100%;
		overflow: hidden;
	}
	.pages {
		width: 100%;
		height: 100%;
		display: flex;
		will-change: transform;
		transition: transform 0.55s cubic-bezier(0.22, 0.61, 0.36, 1);
	}
	.page {
		flex: 0 0 calc(100% / var(--pages-count, 1));
		width: calc(100% / var(--pages-count, 1));
		min-width: 0;
		height: 100%;
	}
	.grid {
		height: 100%;
		display: grid;
		grid-template-columns: repeat(var(--cols, 1), minmax(0, 1fr));
		grid-template-rows: repeat(var(--rows, 1), minmax(0, 1fr));
		gap: clamp(8px, 0.6vw, 14px);
	}
	.grid.first-span > :global(:first-child) {
		grid-row: span 2;
	}
	.empty {
		flex: 1;
		display: grid;
		place-items: center;
		color: var(--text-muted);
		background: var(--bg-card);
		border: 1px dashed var(--border);
		border-radius: var(--radius-md);
		font-size: clamp(12px, 0.85vw, 16px);
	}
	.controls {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		gap: clamp(10px, 0.8vw, 18px);
		padding: clamp(4px, 0.35vw, 10px) clamp(4px, 0.4vw, 10px);
		color: var(--text-muted);
		font-size: clamp(10px, 0.7vw, 13px);
		font-weight: 700;
	}
	.controls-side {
		display: inline-flex;
		align-items: center;
		gap: clamp(6px, 0.5vw, 10px);
	}
	.controls-left {
		justify-self: start;
	}
	.controls-right {
		justify-self: end;
	}
	.controls-center {
		display: inline-flex;
		align-items: center;
		gap: clamp(6px, 0.55vw, 12px);
		justify-self: center;
	}
	.ctrl-label {
		color: var(--text-muted);
		font-size: clamp(10px, 0.68vw, 12px);
		font-weight: 800;
		letter-spacing: 0.3px;
	}
	.interval-picker {
		display: inline-flex;
		gap: 2px;
		padding: 3px;
		border: 1px solid var(--border);
		background: var(--bg-card);
		border-radius: var(--radius-sm);
	}
	.pill {
		min-width: clamp(28px, 2vw, 40px);
		height: clamp(22px, 1.8vw, 28px);
		padding: 0 clamp(7px, 0.55vw, 12px);
		border: 0;
		border-radius: calc(var(--radius-sm) - 2px);
		background: transparent;
		color: var(--text-secondary);
		font-family: inherit;
		font-size: clamp(10px, 0.68vw, 12px);
		font-weight: 700;
		cursor: pointer;
	}
	.pill:hover {
		color: var(--text-primary);
		background: var(--bg-tab);
	}
	.pill.active {
		color: var(--bg-base);
		background: var(--accent);
	}
	.nav {
		width: clamp(26px, 2vw, 34px);
		height: clamp(26px, 2vw, 34px);
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--bg-card);
		color: var(--text-secondary);
		cursor: pointer;
		font-size: clamp(11px, 0.75vw, 14px);
	}
	.nav:hover {
		border-color: var(--accent);
		color: var(--accent);
	}
	.dots {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}
	.dot {
		width: clamp(7px, 0.55vw, 11px);
		height: clamp(7px, 0.55vw, 11px);
		border-radius: 50%;
		border: 0;
		background: rgba(100, 116, 139, 0.4);
		cursor: pointer;
		padding: 0;
		transition: background 0.12s ease, transform 0.12s ease;
	}
	.dot:hover {
		background: rgba(48, 213, 200, 0.6);
	}
	.dot.active {
		background: var(--accent);
		transform: scale(1.35);
	}
	.pages-count {
		min-width: 48px;
		text-align: center;
		color: var(--text-primary);
		font-variant-numeric: tabular-nums;
	}
	.auto-block {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 0 4px 0 8px;
		border-left: 1px solid var(--border);
	}
	.auto-state {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		font-size: clamp(10px, 0.7vw, 12px);
		font-weight: 800;
		color: var(--text-muted);
		white-space: nowrap;
	}
	.auto-state.on {
		color: #34d399;
	}
	.auto-pulse {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: #34d399;
		box-shadow: 0 0 6px rgba(52, 211, 153, 0.6);
		animation: auto-pulse 1.8s ease-in-out infinite;
	}
	.auto-pulse.off {
		background: #64748b;
		box-shadow: none;
		animation: none;
	}
	@keyframes auto-pulse {
		0%, 100% { opacity: 1; transform: scale(1); }
		50% { opacity: 0.5; transform: scale(0.75); }
	}
	.switch {
		position: relative;
		display: inline-block;
		width: 38px;
		height: 22px;
		border: 0;
		padding: 0;
		border-radius: 11px;
		background: rgba(100, 116, 139, 0.4);
		cursor: pointer;
		transition: background 0.18s ease;
	}
	.switch.on {
		background: var(--accent);
	}
	.switch-thumb {
		position: absolute;
		top: 2px;
		left: 2px;
		width: 18px;
		height: 18px;
		border-radius: 50%;
		background: #fff;
		transition: transform 0.18s ease;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
	}
	.switch.on .switch-thumb {
		transform: translateX(16px);
	}
	.count {
		color: var(--text-muted);
	}
</style>
