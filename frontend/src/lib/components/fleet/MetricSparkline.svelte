<script module lang="ts">
	let __sparkCounter = 0;
</script>

<script lang="ts">
	let {
		values = [],
		color = '#30d5c8',
		label = 'Trend',
		loading = false,
		stretch = false,
	}: {
		values?: number[];
		color?: string;
		label?: string;
		loading?: boolean;
		stretch?: boolean;
	} = $props();

	const width = 100;
	const height = 32;
	const padTop = 3;
	const padBottom = 3;
	// 점·tip-halo 가 viewBox 가장자리에서 반쪽만 보여 "<" 모양으로 잘리는 걸 막기 위한 좌우 inset.
	const padX = 3.5;

	const uid = ++__sparkCounter;
	const gradId = `spark-grad-${uid}`;
	const glowId = `spark-glow-${uid}`;

	let nums = $derived(values.filter((v) => typeof v === 'number' && Number.isFinite(v)));
	let min = $derived(nums.length ? Math.min(...nums) : 0);
	let max = $derived(nums.length ? Math.max(...nums) : 0);

	let pts = $derived(
		nums.map((value, index) => {
			const x =
				nums.length <= 1
					? width / 2
					: padX + (index / (nums.length - 1)) * (width - padX * 2);
			const spread = max - min || 1;
			const y = height - padBottom - ((value - min) / spread) * (height - padTop - padBottom);
			return { x, y };
		})
	);

	function smoothPath(points: { x: number; y: number }[]): string {
		if (points.length === 0) return '';
		if (points.length === 1) return `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
		let d = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
		// 마지막 spike 가 있을 때 인접 segment 의 Bezier cp 가 chart 밖으로
		// 빠져나가 V 자 dip 을 만드는 걸 막기 위해, cp y 좌표를 chart 영역
		// 안으로 clamp 한다.
		const yMin = padTop;
		const yMax = height - padBottom;
		const lastIdx = points.length - 2;
		for (let i = 0; i < points.length - 1; i++) {
			// 마지막 segment 는 직선(L) — Catmull-Rom 끝점 휨 완전 제거.
			if (i === lastIdx) {
				d += ` L ${points[i + 1].x.toFixed(2)} ${points[i + 1].y.toFixed(2)}`;
				continue;
			}
			const p0 = points[i - 1] ?? points[i];
			const p1 = points[i];
			const p2 = points[i + 1];
			const p3 = points[i + 2] ?? p2;
			const cp1x = p1.x + (p2.x - p0.x) / 6;
			let cp1y = p1.y + (p2.y - p0.y) / 6;
			const cp2x = p2.x - (p3.x - p1.x) / 6;
			let cp2y = p2.y - (p3.y - p1.y) / 6;
			cp1y = Math.max(yMin, Math.min(yMax, cp1y));
			cp2y = Math.max(yMin, Math.min(yMax, cp2y));
			d += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
		}
		return d;
	}

	let linePath = $derived(smoothPath(pts));
	let areaPath = $derived(
		pts.length >= 1
			? `${linePath} L ${pts[pts.length - 1].x.toFixed(2)} ${height} L ${pts[0].x.toFixed(2)} ${height} Z`
			: ''
	);
</script>

<div class="spark-wrap">
	<svg
		class="spark"
		viewBox="0 0 {width} {height}"
		preserveAspectRatio={stretch ? 'none' : 'xMidYMid meet'}
		role="img"
		aria-label={label}
	>
		<defs>
			<linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
				<stop offset="0%" stop-color={color} stop-opacity="0.42" />
				<stop offset="60%" stop-color={color} stop-opacity="0.12" />
				<stop offset="100%" stop-color={color} stop-opacity="0" />
			</linearGradient>
			<filter id={glowId} x="-10%" y="-30%" width="120%" height="160%">
				<feGaussianBlur stdDeviation="0.6" result="blur" />
				<feMerge>
					<feMergeNode in="blur" />
					<feMergeNode in="SourceGraphic" />
				</feMerge>
			</filter>
		</defs>
		<line class="baseline" x1="0" y1={height - 1} x2={width} y2={height - 1} />
		{#if pts.length}
			<path d={areaPath} fill="url(#{gradId})" class:dim={loading} vector-effect="non-scaling-stroke" />
			<path
				d={linePath}
				fill="none"
				stroke={color}
				class="line"
				class:dim={loading}
				filter="url(#{glowId})"
				vector-effect="non-scaling-stroke"
			/>
		{:else}
			<text x={width / 2} y={height / 2 + 3} text-anchor="middle">No data</text>
		{/if}
	</svg>
	{#if loading}
		<span class="spinner" aria-label="갱신 중"></span>
	{/if}
</div>

<style>
	.spark-wrap {
		position: relative;
		display: flex;
		align-items: stretch;
		width: 100%;
		height: 100%;
		min-width: 0;
	}
	.spark {
		display: block;
		width: 100%;
		min-width: 0;
		height: 100%;
	}
	/* stretch 모드가 아닐 때만 좁은 max-width 유지 — 좁은 list cell 같이
	   "옆에 정보 텍스트가 같이 있고 스파크는 작은 보조" 케이스 보호. */
	.spark:not([preserveAspectRatio='none']) {
		max-width: 140px;
	}
	.baseline {
		stroke: rgba(100, 116, 139, 0.18);
		stroke-width: 1;
		stroke-dasharray: 2 3;
	}
	.line {
		stroke-width: 1.6;
		stroke-linecap: round;
		stroke-linejoin: round;
		transition: opacity 0.18s ease;
	}
	.line.dim,
	path.dim {
		opacity: 0.32;
	}
	text {
		fill: var(--text-muted);
		font-size: 8px;
	}
	.spinner {
		position: absolute;
		left: 50%;
		top: 50%;
		width: 12px;
		height: 12px;
		margin: -6px 0 0 -6px;
		border: 1.5px solid rgba(48, 213, 200, 0.25);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: spark-spin 0.8s linear infinite;
		pointer-events: none;
	}
	@keyframes spark-spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
