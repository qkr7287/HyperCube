<!--
  Small "?" help icon with a hover-triggered explanation bubble.

  The bubble is rendered with `position: fixed` and positioned via JS so it
  can escape panels that clip with `overflow: hidden`. Flips placement
  automatically when near viewport edges.
-->
<script lang="ts">
	import { onDestroy } from 'svelte';
	import { browser } from '$app/environment';

	let {
		text,
		label = '설명',
		placement = 'bottom-start',
		maxWidth = 340,
	}: {
		text: string;
		label?: string;
		placement?: 'top' | 'bottom' | 'left' | 'right' | 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end';
		maxWidth?: number;
	} = $props();

	let glyph = $state<HTMLSpanElement | null>(null);
	let bubble = $state<HTMLSpanElement | null>(null);
	let open = $state(false);
	let positioned = $state(false);
	let style = $state('');

	const GAP = 8;

	function computePosition() {
		if (!glyph || !bubble) return;
		const anchor = glyph.getBoundingClientRect();
		const vw = window.innerWidth;
		const vh = window.innerHeight;

		// Measure bubble natural size
		const bubbleRect = bubble.getBoundingClientRect();
		const bw = Math.min(bubbleRect.width || maxWidth, maxWidth);
		const bh = bubbleRect.height || 80;

		let top = 0;
		let left = 0;
		let mode = placement;

		// Decide vertical: prefer bottom; flip to top if no room
		const wantsTop = mode.startsWith('top');
		const spaceBelow = vh - anchor.bottom - GAP;
		const spaceAbove = anchor.top - GAP;
		const placeAbove = wantsTop
			? spaceAbove >= bh || spaceAbove >= spaceBelow
			: spaceBelow < bh && spaceAbove > spaceBelow;

		if (placeAbove) {
			top = anchor.top - GAP - bh;
			mode = mode.replace('bottom', 'top') as typeof mode;
		} else {
			top = anchor.bottom + GAP;
			mode = mode.replace('top', 'bottom') as typeof mode;
		}

		// Decide horizontal
		if (mode.endsWith('-end')) {
			left = anchor.right - bw;
		} else if (mode.endsWith('-start')) {
			left = anchor.left;
		} else if (mode === 'left') {
			left = anchor.left - bw - GAP;
			top = anchor.top + anchor.height / 2 - bh / 2;
		} else if (mode === 'right') {
			left = anchor.right + GAP;
			top = anchor.top + anchor.height / 2 - bh / 2;
		} else {
			left = anchor.left + anchor.width / 2 - bw / 2;
		}

		// Clamp to viewport
		left = Math.max(8, Math.min(vw - bw - 8, left));
		top = Math.max(8, Math.min(vh - bh - 8, top));

		style = `top: ${top}px; left: ${left}px; width: ${bw}px;`;
		positioned = true;
	}

	function handleEnter() {
		open = true;
		positioned = false;
		// Wait two animation frames so the bubble is in the DOM with its
		// final width measurable, then compute position. Setting
		// positioned=true reveals it via CSS to avoid a flash at (0,0).
		if (browser) {
			requestAnimationFrame(() => requestAnimationFrame(() => computePosition()));
		}
	}

	function handleLeave() {
		open = false;
		positioned = false;
	}

	function handleScroll() {
		if (open) computePosition();
	}

	$effect(() => {
		if (!browser || !open) return;
		window.addEventListener('scroll', handleScroll, true);
		window.addEventListener('resize', handleScroll);
		return () => {
			window.removeEventListener('scroll', handleScroll, true);
			window.removeEventListener('resize', handleScroll);
		};
	});

	onDestroy(() => {
		open = false;
	});
</script>

<span
	class="info-tip"
	tabindex="0"
	aria-label={label}
	bind:this={glyph}
	onmouseenter={handleEnter}
	onmouseleave={handleLeave}
	onfocus={handleEnter}
	onblur={handleLeave}
>
	<span class="info-glyph" aria-hidden="true">?</span>
</span>
{#if open}
	<span
		class="info-bubble"
		class:positioned
		role="tooltip"
		bind:this={bubble}
		style={style}
		style:max-width="{maxWidth}px"
	>{text}</span>
{/if}

<style>
	.info-tip {
		position: relative;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 16px;
		height: 16px;
		margin-left: 6px;
		cursor: help;
		outline: none;
	}

	.info-glyph {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 15px;
		height: 15px;
		border-radius: 50%;
		font-size: 10px;
		font-weight: 800;
		line-height: 1;
		color: rgba(203, 213, 225, 0.95);
		background: rgba(148, 163, 184, 0.22);
		border: 1px solid rgba(148, 163, 184, 0.34);
		transition: color 0.15s, background-color 0.15s, border-color 0.15s;
	}

	.info-tip:hover .info-glyph,
	.info-tip:focus-visible .info-glyph {
		color: #0b1320;
		background: #30d5c8;
		border-color: #30d5c8;
	}

	:global(.info-bubble) {
		position: fixed;
		top: -9999px;
		left: -9999px;
		z-index: 2000;
		padding: 12px 14px;
		font-size: 12.5px;
		line-height: 1.65;
		color: #e2e8f0;
		background: rgba(11, 15, 24, 0.98);
		border: 1px solid rgba(48, 213, 200, 0.42);
		border-radius: 10px;
		box-shadow: 0 14px 40px rgba(0, 0, 0, 0.55);
		white-space: pre-line;
		text-align: left;
		font-weight: 400;
		letter-spacing: 0.01em;
		pointer-events: none;
		opacity: 0;
		transition: opacity 0.12s ease-out;
	}

	:global(.info-bubble.positioned) {
		opacity: 1;
	}
</style>
