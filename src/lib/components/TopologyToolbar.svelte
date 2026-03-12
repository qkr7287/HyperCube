<script lang="ts">
	import iconScreenshot from '$lib/assets/icons/toolbar-screenshot.svg';
	import iconRotate from '$lib/assets/icons/toolbar-rotate.svg';
	import iconZoom from '$lib/assets/icons/toolbar-zoom.svg';

	let {
		onScreenshot = () => {},
		onRotate = () => {},
		onZoom = () => {},
		isRotating = false,
	}: {
		onScreenshot: () => void;
		onRotate: () => void;
		onZoom: () => void;
		isRotating: boolean;
	} = $props();
</script>

<div class="toolbar">
	<button class="toolbar-btn" onclick={onScreenshot}>
		<img src={iconScreenshot} alt="" class="toolbar-icon" />
		<span>Screenshot</span>
	</button>

	<div class="divider"></div>

	<button class="toolbar-btn" class:active={isRotating} onclick={onRotate}>
		<img src={iconRotate} alt="" class="toolbar-icon" class:spinning={isRotating} />
		<span>{isRotating ? 'Stop' : 'Rotate'}</span>
	</button>

	<div class="divider"></div>

	<button class="toolbar-btn" onclick={onZoom}>
		<img src={iconZoom} alt="" class="toolbar-icon" />
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

	.toolbar-btn.active {
		color: var(--accent);
	}

	.toolbar-icon {
		width: 14px;
		height: 14px;
		opacity: 0.7;
	}

	.toolbar-icon.spinning {
		opacity: 1;
		animation: spin 2s linear infinite;
	}

	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}

	.divider {
		width: 1px;
		height: 16px;
		background: rgba(255, 255, 255, 0.1);
	}
</style>
