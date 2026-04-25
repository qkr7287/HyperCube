<script lang="ts" generics="T">
	import { onDestroy, onMount } from 'svelte';
	import type { Snippet } from 'svelte';

	let {
		items = [] as T[],
		pageSize = 8,
		intervalMs = 6500,
		paused = false,
		children,
	}: {
		items?: T[];
		pageSize?: number;
		intervalMs?: number;
		paused?: boolean;
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
	const shouldRotate = $derived(!paused && !hovered && pageCount > 1);

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
		intervalMs;
		startTimer();
		return stopTimer;
	});

	$effect(() => {
		if (paused || hovered) {
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

	{#if pageCount > 1}
		<div class="carousel-bar">
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
			<div class="progress" aria-hidden="true">
				<i style={`width:${shouldRotate ? progress.toFixed(1) : 0}%`}></i>
			</div>
			<small class="count">
				{pageIndex + 1} / {pageCount}
			</small>
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

	.count {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 800;
		min-width: 44px;
		text-align: right;
	}
</style>
