<script lang="ts">
	let {
		text = '페이지 불러오는 중',
	}: {
		text?: string;
	} = $props();
</script>

<div class="nav-progress" aria-hidden="true">
	<div class="nav-progress-fill"></div>
</div>
<div class="loader-overlay" aria-live="polite" aria-busy="true">
	<div class="loader-bg"></div>
	<div class="loader-stage">
		<div class="orbit orbit-a"><i></i><i></i><i></i></div>
		<div class="orbit orbit-b"><i></i><i></i></div>
		<div class="orbit orbit-c"><i></i></div>
		<div class="cube-wrap">
			<div class="cube">
				<span class="face front"></span>
				<span class="face back"></span>
				<span class="face right"></span>
				<span class="face left"></span>
				<span class="face top"></span>
				<span class="face bottom"></span>
			</div>
			<div class="cube-glow"></div>
		</div>
	</div>
	<div class="loader-meta">
		<div class="brand">HYPER<span>CUBE</span></div>
		<div class="dots-line">
			<span></span><span></span><span></span>
		</div>
		<div class="status-text">{text}</div>
	</div>
</div>

<style>
	.nav-progress {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		height: 3px;
		z-index: 10001;
		background: rgba(15, 23, 42, 0.4);
		overflow: hidden;
		pointer-events: none;
	}
	.nav-progress-fill {
		position: absolute;
		left: 0;
		top: 0;
		height: 100%;
		width: 35%;
		background: linear-gradient(90deg,
			transparent,
			#30d5c8 20%,
			#60a5fa 50%,
			#a78bfa 80%,
			transparent);
		box-shadow: 0 0 12px rgba(48, 213, 200, 0.85), 0 0 22px rgba(96, 165, 250, 0.55);
		animation: progress-slide 1.2s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
	}
	@keyframes progress-slide {
		0%   { left: -40%; width: 35%; }
		60%  { width: 55%; }
		100% { left: 100%; width: 35%; }
	}

	.loader-overlay {
		position: fixed;
		inset: 0;
		z-index: 10000;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 36px;
		pointer-events: none;
		animation: overlay-in 0.34s ease-out both;
	}
	@keyframes overlay-in {
		from { opacity: 0; }
		to   { opacity: 1; }
	}

	.loader-bg {
		position: absolute;
		inset: 0;
		background:
			radial-gradient(ellipse 60% 60% at 50% 50%, rgba(48, 213, 200, 0.18), transparent 70%),
			radial-gradient(ellipse 80% 80% at 50% 50%, rgba(96, 165, 250, 0.10), transparent 75%),
			rgba(13, 17, 23, 0.78);
		backdrop-filter: blur(14px) saturate(140%);
		-webkit-backdrop-filter: blur(14px) saturate(140%);
		animation: bg-pulse 4s ease-in-out infinite;
	}
	@keyframes bg-pulse {
		0%, 100% { filter: brightness(1); }
		50%      { filter: brightness(1.18); }
	}

	.loader-stage {
		position: relative;
		width: 220px;
		height: 220px;
		display: grid;
		place-items: center;
		perspective: 800px;
	}

	.orbit {
		position: absolute;
		inset: 0;
		border-radius: 50%;
		border: 1px dashed rgba(148, 163, 184, 0.18);
	}
	.orbit i {
		position: absolute;
		left: 50%;
		top: 50%;
		width: 9px;
		height: 9px;
		margin-left: -4.5px;
		margin-top: -4.5px;
		border-radius: 50%;
		background: var(--p, #30d5c8);
		box-shadow: 0 0 14px var(--p, #30d5c8), 0 0 26px var(--p, #30d5c8);
	}
	.orbit-a { animation: orbit-spin 4s linear infinite; }
	.orbit-a i:nth-child(1) { --p: #30d5c8; transform: rotate(0deg)   translateY(-110px); }
	.orbit-a i:nth-child(2) { --p: #60a5fa; transform: rotate(120deg) translateY(-110px); }
	.orbit-a i:nth-child(3) { --p: #a78bfa; transform: rotate(240deg) translateY(-110px); }

	.orbit-b {
		inset: 28px;
		border-color: rgba(96, 165, 250, 0.18);
		animation: orbit-spin 2.6s linear infinite reverse;
	}
	.orbit-b i:nth-child(1) { --p: #fbbf24; width: 7px; height: 7px; transform: rotate(0deg)   translateY(-82px); }
	.orbit-b i:nth-child(2) { --p: #f472b6; width: 7px; height: 7px; transform: rotate(180deg) translateY(-82px); }

	.orbit-c {
		inset: 60px;
		border-color: rgba(167, 139, 250, 0.22);
		animation: orbit-spin 1.8s linear infinite;
	}
	.orbit-c i { --p: #34d399; width: 6px; height: 6px; transform: translateY(-50px); }

	@keyframes orbit-spin {
		from { transform: rotate(0deg); }
		to   { transform: rotate(360deg); }
	}

	.cube-wrap {
		position: relative;
		width: 70px;
		height: 70px;
		transform-style: preserve-3d;
	}
	.cube-glow {
		position: absolute;
		inset: -30px;
		border-radius: 50%;
		background: radial-gradient(circle, rgba(48, 213, 200, 0.5), transparent 65%);
		filter: blur(18px);
		animation: glow-pulse 1.6s ease-in-out infinite;
		pointer-events: none;
	}
	@keyframes glow-pulse {
		0%, 100% { opacity: 0.55; transform: scale(0.95); }
		50%      { opacity: 1;    transform: scale(1.15); }
	}

	.cube {
		position: relative;
		width: 70px;
		height: 70px;
		transform-style: preserve-3d;
		animation: cube-spin 3.2s cubic-bezier(0.45, 0, 0.55, 1) infinite;
	}
	@keyframes cube-spin {
		0%   { transform: rotateX(-25deg) rotateY(0deg); }
		100% { transform: rotateX(-25deg) rotateY(360deg); }
	}
	.face {
		position: absolute;
		width: 70px;
		height: 70px;
		border: 1.5px solid rgba(48, 213, 200, 0.85);
		background: linear-gradient(135deg, rgba(48, 213, 200, 0.18), rgba(96, 165, 250, 0.18));
		box-shadow: inset 0 0 18px rgba(48, 213, 200, 0.35);
	}
	.front  { transform: translateZ(35px); }
	.back   { transform: rotateY(180deg) translateZ(35px); }
	.right  { transform: rotateY( 90deg) translateZ(35px); }
	.left   { transform: rotateY(-90deg) translateZ(35px); }
	.top    { transform: rotateX( 90deg) translateZ(35px); }
	.bottom { transform: rotateX(-90deg) translateZ(35px); }

	.loader-meta {
		position: relative;
		display: grid;
		justify-items: center;
		gap: 14px;
	}
	.brand {
		font-size: 22px;
		font-weight: 900;
		letter-spacing: 0.32em;
		background: linear-gradient(90deg, #30d5c8, #60a5fa, #a78bfa, #30d5c8);
		background-size: 200% 100%;
		-webkit-background-clip: text;
		background-clip: text;
		-webkit-text-fill-color: transparent;
		animation: brand-shine 3s linear infinite;
	}
	.brand span {
		font-weight: 600;
		letter-spacing: 0.34em;
	}
	@keyframes brand-shine {
		0%   { background-position: 0% 50%; }
		100% { background-position: 200% 50%; }
	}

	.dots-line {
		display: inline-flex;
		gap: 7px;
	}
	.dots-line span {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: #30d5c8;
		box-shadow: 0 0 8px rgba(48, 213, 200, 0.85);
		animation: dot-bounce 1.05s ease-in-out infinite;
	}
	.dots-line span:nth-child(2) { background: #60a5fa; box-shadow: 0 0 8px rgba(96, 165, 250, 0.85); animation-delay: 0.16s; }
	.dots-line span:nth-child(3) { background: #a78bfa; box-shadow: 0 0 8px rgba(167, 139, 250, 0.85); animation-delay: 0.32s; }
	@keyframes dot-bounce {
		0%, 80%, 100% { transform: translateY(0)   scale(0.85); opacity: 0.55; }
		40%           { transform: translateY(-7px) scale(1.1); opacity: 1; }
	}

	.status-text {
		color: var(--text-muted);
		font-size: 12px;
		font-weight: 700;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		opacity: 0.85;
	}

	@media (prefers-reduced-motion: reduce) {
		.cube, .orbit-a, .orbit-b, .orbit-c, .cube-glow,
		.loader-bg, .brand, .dots-line span, .nav-progress-fill {
			animation: none !important;
		}
	}
</style>
