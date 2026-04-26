<!--
  Simple area-style mini line chart for table cells.
  Shows values normalized over the series' own min/max so low-magnitude
  signals remain readable next to high-magnitude ones.
-->
<script lang="ts">
	let {
		values = [],
		color = '#30d5c8',
		label = '추이',
	}: {
		values?: number[];
		color?: string;
		label?: string;
	} = $props();

	const width = 110;
	const height = 30;

	let nums = $derived(values.filter((v) => typeof v === 'number' && Number.isFinite(v)));
	let max = $derived(nums.length ? Math.max(...nums, 1) : 1);
	let min = $derived(nums.length ? Math.min(...nums) : 0);
	let points = $derived.by(() => {
		const n = nums.length;
		if (n === 0) return '';
		const spread = max - min || 1;
		return nums
			.map((value, index) => {
				const x = n <= 1 ? width - 2 : 2 + (index / (n - 1)) * (width - 4);
				const y = height - 3 - ((value - min) / spread) * (height - 6);
				return `${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(' ');
	});
	let areaPath = $derived.by(() => {
		if (!points) return '';
		const lastPoint = points.split(' ').at(-1);
		const firstPoint = points.split(' ')[0];
		if (!lastPoint || !firstPoint) return '';
		const lastX = lastPoint.split(',')[0];
		const firstX = firstPoint.split(',')[0];
		return `M ${firstX},${height - 2} L ${points.replace(/ /g, ' L ')} L ${lastX},${height - 2} Z`;
	});
</script>

<svg class="mini-line" viewBox="0 0 {width} {height}" role="img" aria-label={label}>
	<line x1="0" y1={height - 2} x2={width} y2={height - 2} />
	{#if points}
		<path d={areaPath} style={`fill: ${color}; opacity: 0.12;`} />
		<polyline points={points} style={`stroke: ${color};`} />
	{:else}
		<text x={width / 2} y={height / 2 + 3} text-anchor="middle">데이터 없음</text>
	{/if}
</svg>

<style>
	.mini-line {
		display: block;
		width: 100%;
		max-width: 130px;
		height: 30px;
	}
	line {
		stroke: rgba(100, 116, 139, 0.2);
		stroke-width: 0.5;
	}
	polyline {
		fill: none;
		stroke-width: 1.6;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	text {
		fill: var(--text-muted);
		font-size: 8px;
	}
</style>
