<script lang="ts">
	let {
		values = [],
		color = '#30d5c8',
		label = 'Trend',
	}: {
		values?: number[];
		color?: string;
		label?: string;
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

<svg class="spark" viewBox="0 0 {width} {height}" role="img" aria-label={label}>
	<line x1="0" y1={height - 2} x2={width} y2={height - 2} />
	{#if points}
		<polyline points={points} style="stroke: {color};" />
	{:else}
		<text x="46" y="16" text-anchor="middle">No data</text>
	{/if}
</svg>

<style>
	.spark {
		display: block;
		width: 100%;
		max-width: 140px;
		min-width: 80px;
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
	}
	text {
		fill: var(--text-muted);
		font-size: 8px;
	}
</style>
