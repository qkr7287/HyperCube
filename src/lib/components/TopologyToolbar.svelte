<script lang="ts">
	let {
		onScreenshot = () => {},
		onRotate = () => {},
		onZoom = () => {},
	}: {
		onScreenshot: () => void;
		onRotate: () => void;
		onZoom: () => void;
	} = $props();
</script>

<div class="toolbar">
	<button class="toolbar-btn" onclick={onScreenshot}>
		<svg width="12" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="3"/><path d="M3 9h1M20 9h1"/>
		</svg>
		<span>Screenshot</span>
	</button>

	<div class="divider"></div>

	<button class="toolbar-btn" onclick={onRotate}>
		<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0115-6.7L21 8"/>
			<path d="M3 22v-6h6"/><path d="M21 12a9 9 0 01-15 6.7L3 16"/>
		</svg>
		<span>Rotate</span>
	</button>

	<div class="divider"></div>

	<button class="toolbar-btn" onclick={onZoom}>
		<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><path d="M11 8v6M8 11h6"/>
		</svg>
		<span>Zoom</span>
	</button>
</div>

<style>
	.toolbar {
		position: absolute;
		bottom: 24px;
		left: 50%;
		transform: translateX(-50%);
		z-index: 10;
		display: flex;
		align-items: center;
		gap: 24px;
		padding: 10px 24px;
		background: rgba(22, 27, 34, 0.7);
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: var(--radius-full);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
	}

	.toolbar-btn {
		display: flex;
		align-items: center;
		gap: 8px;
		background: none;
		border: none;
		color: var(--text-primary);
		font-size: 11px;
		font-weight: 700;
		cursor: pointer;
		padding: 0;
		transition: color 0.2s;
	}

	.toolbar-btn:hover {
		color: var(--accent);
	}

	.toolbar-btn svg {
		opacity: 0.7;
	}

	.divider {
		width: 1px;
		height: 16px;
		background: rgba(255, 255, 255, 0.1);
	}
</style>
