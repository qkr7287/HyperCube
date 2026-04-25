<script lang="ts" generics="T">
	import { onDestroy, onMount } from 'svelte';
	import type { Snippet } from 'svelte';

	let {
		items = [] as T[],
		pageSize = 8,
		intervalMs = 6500,
		paused = false,
		userPaused = false,
		onTogglePause,
		pauseLabel = '자동 슬라이드',
		hideBar = false,
		compactBar = false,
		resetSignal = 0,
		children,
	}: {
		items?: T[];
		pageSize?: number;
		intervalMs?: number;
		paused?: boolean;
		userPaused?: boolean;
		onTogglePause?: () => void;
		pauseLabel?: string;
		hideBar?: boolean;
		compactBar?: boolean;
		resetSignal?: number;
		children: Snippet<[T[], number, number]>;
	} = $props();

	const TICK_MS = 80;

	let pageIndex = $state(0);
	let hovered = $state(false);
	let progress = $state(0);
	let timer: ReturnType<typeof setInterval> | null = null;

	const pages = $derived.by(() => {
		if (items.length <= pageSize) return [items];
		const out: T[][] = [];
		for (let i = 0; i < items.length; i += pageSize) {
			out.push(items.slice(i, i + pageSize));
		}
		return out;
	});
	const pageCount = $derived(pages.length);
	const activeItems = $derived(pages[Math.min(pageIndex, pageCount - 1)] ?? []);
	const shouldRotate = $derived(!paused && !hovered && !userPaused && pageCount > 1);
	const showBar = $derived(!hideBar && (pageCount > 1 || Boolean(onTogglePause)));

	function advance() {
		if (pageCount <= 1) return;
		pageIndex = (pageIndex + 1) % pageCount;
		progress = 0;
	}

	function tick() {
		if (!shouldRotate) return;
		const steps = Math.max(1, Math.floor(intervalMs / TICK_MS));
		const next = progress + 100 / steps;
		if (next >= 100) {
			advance();
		} else {
			progress = next;
		}
	}

	function startTimer() {
		stopTimer();
		timer = setInterval(tick, TICK_MS);
	}

	function stopTimer() {
		if (timer) {
			clearInterval(timer);
			timer = null;
		}
	}

	function goto(index: number) {
		pageIndex = Math.max(0, Math.min(pageCount - 1, index));
		progress = 0;
	}

	$effect(() => {
		if (pageIndex >= pageCount) pageIndex = 0;
	});

	$effect(() => {
		resetSignal;
		pageIndex = 0;
		progress = 0;
	});

	$effect(() => {
		intervalMs;
		startTimer();
		return stopTimer;
	});

	$effect(() => {
		if (paused || hovered || userPaused) {
			progress = 0;
		}
	});

	onMount(startTimer);
	onDestroy(stopTimer);
</script>

<div
	class="carousel"
	role="group"
	aria-roledescription="carousel"
	onmouseenter={() => (hovered = true)}
	onmouseleave={() => (hovered = false)}
	onfocusin={() => (hovered = true)}
	onfocusout={() => (hovered = false)}
>
	<div class="carousel-page" data-page={pageIndex}>
		{@render children(activeItems, pageIndex, pageCount)}
	</div>

	{#if showBar}
		<div class="carousel-bar" class:is-paused={userPaused}>
			{#if onTogglePause}
				<button
					type="button"
					class="pause-btn"
					class:paused={userPaused}
					title={userPaused ? `${pauseLabel} 재개` : `${pauseLabel} 일시정지`}
					aria-label={userPaused ? '재개' : '일시정지'}
					onclick={onTogglePause}
				>
					{#if userPaused}
						<svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true">
							<polygon points="6,4 20,12 6,20" />
						</svg>
						<span>재생</span>
					{:else}
						<svg viewBox="0 0 24 24" width="11" height="11" fill="currentColor" aria-hidden="true">
							<rect x="6" y="4" width="4" height="16" rx="1" />
							<rect x="14" y="4" width="4" height="16" rx="1" />
						</svg>
						<span>정지</span>
					{/if}
				</button>
			{/if}
			{#if pageCount > 1}
				{#if !compactBar}
					<div class="dots" role="tablist" aria-label="페이지 선택">
						{#each Array(pageCount) as _, idx (idx)}
							<button
								type="button"
								role="tab"
								aria-selected={idx === pageIndex}
								class="dot"
								class:active={idx === pageIndex}
								onclick={() => goto(idx)}
							></button>
						{/each}
					</div>
				{/if}
				<div class="progress" aria-hidden="true" class:idle={!shouldRotate}>
					<i style={`width:${shouldRotate ? progress.toFixed(1) : userPaused ? 100 : 0}%`}></i>
				</div>
				{#if !compactBar}
					<small class="count">
						{pageIndex + 1} / {pageCount}
					</small>
				{/if}
			{:else if onTogglePause}
				<div class="status-text">
					{userPaused ? '일시정지됨' : '자동 재생 중'}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.carousel {
		display: grid;
		grid-template-rows: minmax(0, 1fr) auto;
		gap: 6px;
		min-height: 0;
		height: 100%;
	}

	.carousel-page {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-height: 0;
		overflow: hidden;
		animation: slideIn 360ms cubic-bezier(0.22, 1, 0.36, 1);
	}

	@keyframes slideIn {
		0% {
			opacity: 0;
			transform: translateY(12px);
		}
		100% {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.carousel-bar {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 2px 2px;
		border-top: 1px dashed rgba(100, 116, 139, 0.25);
		flex: 0 0 auto;
		background: inherit;
	}

	.carousel-bar.is-paused {
		border-top-color: rgba(251, 191, 36, 0.5);
	}

	.pause-btn {
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
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.02em;
		cursor: pointer;
		flex: 0 0 auto;
		white-space: nowrap;
		transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease, transform 0.12s ease, box-shadow 0.15s ease;
	}

	.pause-btn:hover {
		background: rgba(248, 113, 113, 0.26);
		transform: translateY(-1px);
	}

	.pause-btn.paused {
		background: rgba(52, 211, 153, 0.2);
		border-color: rgba(52, 211, 153, 0.6);
		color: #34d399;
		box-shadow: 0 0 12px rgba(52, 211, 153, 0.35);
		animation: paused-glow 1.6s ease-in-out infinite;
	}

	.pause-btn.paused:hover {
		background: rgba(52, 211, 153, 0.3);
	}

	@keyframes paused-glow {
		0%, 100% { box-shadow: 0 0 12px rgba(52, 211, 153, 0.3); }
		50% { box-shadow: 0 0 18px rgba(52, 211, 153, 0.55); }
	}

	.pause-btn span {
		line-height: 1;
	}

	.dots {
		display: inline-flex;
		gap: 4px;
		flex-wrap: wrap;
	}

	.dot {
		width: 10px;
		height: 6px;
		border-radius: 999px;
		background: rgba(100, 116, 139, 0.4);
		border: none;
		padding: 0;
		cursor: pointer;
		transition: background-color 0.18s ease, transform 0.18s ease, width 0.18s ease;
	}

	.dot:hover {
		background: rgba(48, 213, 200, 0.55);
	}

	.dot.active {
		width: 20px;
		background: #30d5c8;
		box-shadow: 0 0 8px rgba(48, 213, 200, 0.6);
	}

	.progress {
		flex: 1;
		height: 3px;
		background: rgba(30, 41, 59, 0.65);
		border-radius: 999px;
		overflow: hidden;
	}

	.progress i {
		display: block;
		height: 100%;
		background: linear-gradient(90deg, #30d5c8, #60a5fa);
		width: 0%;
		transition: width 80ms linear;
	}

	.progress.idle i {
		background: repeating-linear-gradient(
			-45deg,
			rgba(251, 191, 36, 0.4) 0,
			rgba(251, 191, 36, 0.4) 4px,
			rgba(251, 191, 36, 0.15) 4px,
			rgba(251, 191, 36, 0.15) 8px
		);
	}

	.count {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		min-width: 44px;
		text-align: right;
	}

	.status-text {
		flex: 1;
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		text-align: right;
		letter-spacing: 0.02em;
	}
</style>
