<!--
  Circular health score gauge. Value 0-100.
  Color follows the usual severity ladder.
-->
<script lang="ts">
	let {
		value = 100,
		size = 40,
		stroke = 4,
	}: {
		value?: number;
		size?: number;
		stroke?: number;
	} = $props();

	let clamped = $derived(Math.max(0, Math.min(100, Number(value) || 0)));
	let radius = $derived((size - stroke) / 2);
	let circumference = $derived(2 * Math.PI * radius);
	let dashOffset = $derived(circumference * (1 - clamped / 100));
	let color = $derived.by(() => {
		if (clamped >= 85) return '#34d399'; // green
		if (clamped >= 65) return '#fbbf24'; // amber
		if (clamped >= 40) return '#fb923c'; // orange
		return '#ef4444'; // red
	});
</script>

<svg class="gauge" width={size} height={size} viewBox="0 0 {size} {size}" role="img" aria-label={`부하 점수 ${clamped}`}>
	<circle
		class="bg"
		cx={size / 2}
		cy={size / 2}
		r={radius}
		stroke-width={stroke}
	/>
	<circle
		class="fg"
		cx={size / 2}
		cy={size / 2}
		r={radius}
		stroke-width={stroke}
		stroke-dasharray={circumference}
		stroke-dashoffset={dashOffset}
		style={`stroke: ${color};`}
		transform={`rotate(-90 ${size / 2} ${size / 2})`}
	/>
	<text x={size / 2} y={size / 2} dominant-baseline="central" text-anchor="middle" style={`fill: ${color};`}>
		{clamped}
	</text>
</svg>

<style>
	.gauge {
		display: block;
	}
	.bg {
		fill: none;
		stroke: rgba(100, 116, 139, 0.2);
	}
	.fg {
		fill: none;
		stroke-linecap: round;
		transition: stroke-dashoffset 0.5s ease, stroke 0.3s ease;
	}
	text {
		font-size: 12px;
		font-weight: 800;
		font-variant-numeric: tabular-nums;
	}
</style>
