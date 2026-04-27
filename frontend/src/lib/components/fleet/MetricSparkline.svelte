<script lang="ts">
	let {
		values = [],
		color = '#30d5c8',
		label = 'Trend',
		loading = false,
	}: {
		values?: number[];
		color?: string;
		label?: string;
		loading?: boolean;
	} = $props();

	const width = 92;
	const height = 26;
	let nums = $derived(values.filter((v) => typeof v === 'number' && Number.isFinite(v)));
	let min = $derived(nums.length ? Math.min(...nums) : 0);
	let max = $derived(nums.length ? Math.max(...nums) : 0);
	let points = $derived(nums
		.map((value, index) => {
			const x = nums.length <= 1 ? width : (index / (nums.length - 1)) * width;
			const spread = max - min || 1;
			const y = height - ((value - min) / spread) * (height - 4) - 2;
			return `${x.toFixed(1)},${y.toFixed(1)}`;
		})
		.join(' '));
</script>

<div class="spark-wrap">
	<svg class="spark" viewBox="0 0 {width} {height}" role="img" aria-label={label}>
		<line x1="0" y1={height - 2} x2={width} y2={height - 2} />
		{#if points}
			<polyline points={points} style="stroke: {color};" class:dim={loading} />
		{:else}
			<text x="46" y="16" text-anchor="middle">No data</text>
		{/if}
	</svg>
	{#if loading}
		<span class="spinner" aria-label="갱신 중"></span>
	{/if}
</div>

<style>
	/* 부모가 height 를 명시했을 때(SVG height:100% 가 의미를 갖도록) 같이 stretch.
	   wrap 자체에 height 가 없으면 svg height:100% 가 0 으로 collapse 해서
	   FleetStatusBar 의 CPU/메모리 KPI 스파크라인이 안 보이게 된다. */
	.spark-wrap {
		position: relative;
		display: flex;
		align-items: center;
		width: 100%;
		height: 100%;
		min-width: 0;
	}
	.spark {
		display: block;
		width: 100%;
		max-width: 140px;
		min-width: 0;
		height: 26px;
	}
	line {
		stroke: rgba(100, 116, 139, 0.22);
		stroke-width: 1;
	}
	polyline {
		fill: none;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
		transition: opacity 0.18s ease;
	}
	polyline.dim {
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
		to { transform: rotate(360deg); }
	}
</style>
