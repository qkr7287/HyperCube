<!--
  Small "?" help icon with a hover-triggered explanation bubble.

  The bubble is rendered into <body> via direct DOM manipulation so it
  cannot be clipped or restacked by any ancestor's overflow / transform /
  z-index. Position is calculated relative to the glyph and clamped to
  the viewport.
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
	let bubble: HTMLSpanElement | null = null;
	let open = false;

	const GAP = 8;

	function ensureBubble(): HTMLSpanElement | null {
		if (!browser) return null;
		if (bubble) return bubble;
		const node = document.createElement('span');
		node.className = 'info-bubble';
		node.setAttribute('role', 'tooltip');
		node.style.maxWidth = `${maxWidth}px`;
		node.textContent = text;
		document.body.appendChild(node);
		bubble = node;
		return node;
	}

	function destroyBubble() {
		if (bubble) {
			bubble.remove();
			bubble = null;
		}
	}

	function computePosition() {
		if (!glyph || !bubble) return;
		const anchor = glyph.getBoundingClientRect();
		const vw = window.innerWidth;
		const vh = window.innerHeight;

		const bubbleRect = bubble.getBoundingClientRect();
		const bw = Math.min(bubbleRect.width || maxWidth, maxWidth);
		const bh = bubbleRect.height || 80;

		let top = 0;
		let left = 0;
		let mode = placement;

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

		left = Math.max(8, Math.min(vw - bw - 8, left));
		top = Math.max(8, Math.min(vh - bh - 8, top));

		bubble.style.top = `${top}px`;
		bubble.style.left = `${left}px`;
		bubble.style.width = `${bw}px`;
		bubble.classList.add('positioned');
	}

	function handleEnter() {
		if (!browser) return;
		open = true;
		const node = ensureBubble();
		if (!node) return;
		node.textContent = text;
		node.classList.remove('positioned');
		// Compute position after the browser has had a chance to lay out the bubble
		// with its real dimensions. We don't gate on `open` here because we want the
		// position to land even if the user moves the mouse in the same frame.
		requestAnimationFrame(() => {
			requestAnimationFrame(() => computePosition());
		});
	}

	function handleLeave() {
		open = false;
		destroyBubble();
	}

	function handleScroll() {
		if (open) computePosition();
	}

	$effect(() => {
		if (!browser) return;
		window.addEventListener('scroll', handleScroll, true);
		window.addEventListener('resize', handleScroll);
		return () => {
			window.removeEventListener('scroll', handleScroll, true);
			window.removeEventListener('resize', handleScroll);
		};
	});

	onDestroy(() => {
		open = false;
		destroyBubble();
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
		pointer-events: auto;
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
		z-index: 99999;
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
