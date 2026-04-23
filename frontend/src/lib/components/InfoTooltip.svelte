<!--
  Small "?" help icon with a hover-triggered explanation bubble.
  Drops in next to any label. Text is short, plain-language, and
  appears without a click so the layout stays clean.

  Default placement is `bottom-start` — bubble drops below the glyph
  and anchors at its left edge. That keeps the bubble inside modals
  whose header is near the top of the viewport (where `top` would
  clip the bubble off-screen) and dodges the right-edge clip too.
-->
<script lang="ts">
	let {
		text,
		label = '설명',
		placement = 'bottom-start',
	}: {
		text: string;
		label?: string;
		placement?: 'top' | 'bottom' | 'left' | 'right' | 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end';
	} = $props();
</script>

<span class="info-tip" tabindex="0" aria-label={label}>
	<span class="info-glyph" aria-hidden="true">?</span>
	<span class="info-bubble" data-placement={placement} role="tooltip">{text}</span>
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
	}

	.info-glyph {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 14px;
		height: 14px;
		border-radius: 50%;
		font-size: 10px;
		font-weight: 700;
		line-height: 1;
		color: rgba(203, 213, 225, 0.85);
		background: rgba(148, 163, 184, 0.18);
		border: 1px solid rgba(148, 163, 184, 0.28);
		transition: color 0.15s, background-color 0.15s, border-color 0.15s;
	}

	.info-tip:hover .info-glyph,
	.info-tip:focus-visible .info-glyph {
		color: #0b1320;
		background: #30d5c8;
		border-color: #30d5c8;
	}

	.info-bubble {
		position: absolute;
		z-index: 60;
		max-width: 300px;
		min-width: 220px;
		padding: 10px 12px;
		font-size: 12px;
		line-height: 1.55;
		color: #e2e8f0;
		background: rgba(13, 17, 23, 0.98);
		border: 1px solid rgba(48, 213, 200, 0.35);
		border-radius: 8px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
		opacity: 0;
		pointer-events: none;
		transform: translateY(-2px);
		transition: opacity 0.15s ease, transform 0.15s ease;
		white-space: pre-line;
		text-align: left;
		font-weight: 400;
		letter-spacing: 0.01em;
	}

	.info-bubble[data-placement='top'] {
		bottom: calc(100% + 8px);
		left: 50%;
		transform: translate(-50%, -2px);
	}
	.info-bubble[data-placement='top-start'] {
		bottom: calc(100% + 8px);
		left: 0;
		transform: translate(0, -2px);
	}
	.info-bubble[data-placement='top-end'] {
		bottom: calc(100% + 8px);
		right: 0;
		transform: translate(0, -2px);
	}
	.info-bubble[data-placement='bottom'] {
		top: calc(100% + 8px);
		left: 50%;
		transform: translate(-50%, 2px);
	}
	.info-bubble[data-placement='bottom-start'] {
		top: calc(100% + 8px);
		left: 0;
		transform: translate(0, 2px);
	}
	.info-bubble[data-placement='bottom-end'] {
		top: calc(100% + 8px);
		right: 0;
		transform: translate(0, 2px);
	}
	.info-bubble[data-placement='left'] {
		right: calc(100% + 10px);
		top: 50%;
		transform: translate(-2px, -50%);
	}
	.info-bubble[data-placement='right'] {
		left: calc(100% + 10px);
		top: 50%;
		transform: translate(2px, -50%);
	}

	.info-tip:hover .info-bubble,
	.info-tip:focus-visible .info-bubble {
		opacity: 1;
		pointer-events: auto;
	}
	.info-tip:hover .info-bubble[data-placement='top'],
	.info-tip:focus-visible .info-bubble[data-placement='top'] {
		transform: translate(-50%, 0);
	}
	.info-tip:hover .info-bubble[data-placement='top-start'],
	.info-tip:focus-visible .info-bubble[data-placement='top-start'],
	.info-tip:hover .info-bubble[data-placement='top-end'],
	.info-tip:focus-visible .info-bubble[data-placement='top-end'] {
		transform: translate(0, 0);
	}
	.info-tip:hover .info-bubble[data-placement='bottom'],
	.info-tip:focus-visible .info-bubble[data-placement='bottom'] {
		transform: translate(-50%, 0);
	}
	.info-tip:hover .info-bubble[data-placement='bottom-start'],
	.info-tip:focus-visible .info-bubble[data-placement='bottom-start'],
	.info-tip:hover .info-bubble[data-placement='bottom-end'],
	.info-tip:focus-visible .info-bubble[data-placement='bottom-end'] {
		transform: translate(0, 0);
	}
	.info-tip:hover .info-bubble[data-placement='left'],
	.info-tip:focus-visible .info-bubble[data-placement='left'] {
		transform: translate(0, -50%);
	}
	.info-tip:hover .info-bubble[data-placement='right'],
	.info-tip:focus-visible .info-bubble[data-placement='right'] {
		transform: translate(0, -50%);
	}
</style>
