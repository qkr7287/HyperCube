<script lang="ts">
	import logoHypercube from '$lib/assets/logo_hypercube.png';

	let {
		text = '페이지 불러오는 중',
	}: {
		text?: string;
	} = $props();
</script>

<div class="loader-overlay" aria-live="polite" aria-busy="true">
	<div class="loader-bg"></div>
	<div class="loader-content">
		<div class="logo-wrap">
			<img src={logoHypercube} alt="HyperCube" />
			<div class="logo-glow"></div>
		</div>
		<div class="bar"><i></i></div>
		<div class="status-text">{text}</div>
	</div>
</div>

<style>
	.loader-overlay {
		position: fixed;
		inset: 0;
		z-index: 10000;
		display: flex;
		align-items: center;
		justify-content: center;
		pointer-events: none;
		animation: overlay-in 0.24s ease-out both;
	}
	@keyframes overlay-in {
		from { opacity: 0; }
		to   { opacity: 1; }
	}

	.loader-bg {
		position: absolute;
		inset: 0;
		background: rgba(13, 17, 23, 0.82);
		backdrop-filter: blur(10px) saturate(140%);
		-webkit-backdrop-filter: blur(10px) saturate(140%);
	}

	.loader-content {
		position: relative;
		display: grid;
		justify-items: center;
		gap: 24px;
	}

	.logo-wrap {
		position: relative;
		display: grid;
		place-items: center;
	}
	.logo-wrap img {
		height: 44px;
		width: auto;
		filter: drop-shadow(0 0 18px rgba(48, 213, 200, 0.45));
		animation: logo-pulse 2.2s ease-in-out infinite;
	}
	.logo-glow {
		position: absolute;
		inset: -28px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(48, 213, 200, 0.32), transparent 70%);
		filter: blur(20px);
		animation: logo-glow-pulse 2.2s ease-in-out infinite;
		pointer-events: none;
	}
	@keyframes logo-pulse {
		0%, 100% { opacity: 0.85; transform: scale(0.99); }
		50%      { opacity: 1;    transform: scale(1.02); }
	}
	@keyframes logo-glow-pulse {
		0%, 100% { opacity: 0.5; transform: scale(0.92); }
		50%      { opacity: 1;   transform: scale(1.08); }
	}

	.bar {
		width: 180px;
		height: 2px;
		border-radius: 999px;
		background: rgba(100, 116, 139, 0.18);
		overflow: hidden;
	}
	.bar i {
		display: block;
		width: 35%;
		height: 100%;
		background: linear-gradient(90deg, transparent, #30d5c8, #60a5fa, transparent);
		box-shadow: 0 0 10px rgba(48, 213, 200, 0.6);
		animation: bar-slide 1.2s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
	}
	@keyframes bar-slide {
		0%   { transform: translateX(-120%); }
		100% { transform: translateX(380%); }
	}

	.status-text {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		opacity: 0.8;
	}

	@media (prefers-reduced-motion: reduce) {
		.logo-wrap img, .logo-glow, .bar i {
			animation: none !important;
		}
	}
</style>
