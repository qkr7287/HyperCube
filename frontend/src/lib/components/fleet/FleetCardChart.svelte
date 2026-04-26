<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import {
		CategoryScale,
		Chart,
		Filler,
		Legend,
		LineController,
		LineElement,
		LinearScale,
		PointElement,
		Tooltip,
	} from 'chart.js';

	Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Tooltip, Filler, Legend);

	type Series = { values: number[]; color: string; label?: string };

	type RangeKey = '1m' | '5m' | '1h' | '24h' | '7d';

	let {
		series,
		unit = 'percent',
		maxY,
		showLegend = false,
		range = '1h',
		showAxes = true,
	}: {
		series: Series | Series[];
		unit?: 'percent' | 'rate';
		maxY?: number;
		showLegend?: boolean;
		range?: RangeKey;
		showAxes?: boolean;
	} = $props();

	// Bucket size in seconds — fleet-store의 BUCKET_SECONDS와 반드시 일치해야
	// label 시점이 실제 데이터와 맞는다.
	const BUCKET_SEC: Record<RangeKey, number> = { '1m': 60, '5m': 300, '1h': 3600, '24h': 86400, '7d': 604800 };

	function pad(n: number): string {
		return String(n).padStart(2, '0');
	}

	function buildTimeLabels(count: number): string[] {
		if (count === 0) return [];
		const interval = BUCKET_SEC[range] * 1000;
		const now = Date.now();
		const latestBucketStart = Math.floor(now / interval) * interval;
		const labels: string[] = [];
		for (let i = 0; i < count; i += 1) {
			const at = latestBucketStart - (count - 1 - i) * interval;
			const d = new Date(at);
			if (range === '7d' || range === '24h') {
				// 1d / 1주 bucket — MM/DD
				labels.push(`${pad(d.getMonth() + 1)}/${pad(d.getDate())}`);
			} else {
				// 1m / 5m / 1h — HH:MM
				labels.push(`${pad(d.getHours())}:${pad(d.getMinutes())}`);
			}
		}
		return labels;
	}

	let canvas: HTMLCanvasElement | null = null;
	let chart: Chart | null = null;
	let seriesList = $derived(Array.isArray(series) ? series : [series]);

	function formatValue(value: number): string {
		if (unit === 'percent') return `${value.toFixed(1)}%`;
		if (value < 1) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		let next = value;
		let idx = 0;
		while (next >= 1000 && idx < units.length - 1) {
			next /= 1024;
			idx += 1;
		}
		const digits = next >= 10 ? 0 : 1;
		return `${next.toFixed(digits)} ${units[idx]}`;
	}

	function peakValue(list: Series[]): number {
		let peak = 0;
		for (const item of list) {
			for (const value of item.values) if (value > peak) peak = value;
		}
		return peak;
	}

	function buildGradient(ctx: CanvasRenderingContext2D, color: string): CanvasGradient {
		const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.clientHeight || 100);
		gradient.addColorStop(0, `${color}60`);
		gradient.addColorStop(0.6, `${color}18`);
		gradient.addColorStop(1, `${color}00`);
		return gradient;
	}

	function buildDatasets(list: Series[]) {
		if (!canvas) return [];
		const ctx = canvas.getContext('2d');
		return list.map((item) => ({
			label: item.label ?? '',
			data: [...item.values],
			borderColor: item.color,
			backgroundColor: ctx ? buildGradient(ctx, item.color) : `${item.color}30`,
			borderWidth: 2,
			pointRadius: 0,
			pointHoverRadius: 4,
			pointBackgroundColor: item.color,
			pointBorderColor: 'rgba(11, 15, 24, 0.9)',
			pointBorderWidth: 1,
			pointHitRadius: 12,
			tension: 0.35,
			fill: list.length === 1 ? 'origin' : false,
			cubicInterpolationMode: 'monotone' as const,
		}));
	}

	function maxLabels(list: Series[]): number {
		let n = 0;
		for (const item of list) if (item.values.length > n) n = item.values.length;
		return n;
	}

	function render() {
		if (!canvas) return;
		const list = seriesList;
		const n = maxLabels(list);
		const suggestedMax = unit === 'percent' ? 100 : Math.max(peakValue(list) * 1.15, 1024);
		chart = new Chart(canvas, {
			type: 'line',
			data: {
				labels: buildTimeLabels(n),
				datasets: buildDatasets(list),
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				// 첫 렌더는 덜 튀게 (400ms), 이후 streaming update는 transitions.active로 처리.
				animation: { duration: 400, easing: 'easeOutQuart' },
				// 같은 index의 값이 animated 될 때 — 이 설정이 물 흐르듯 느낌의 핵심.
				// 각 bucket point가 이전 poll 때의 값에서 새 값으로 부드럽게 이어진다.
				animations: {
					y: { duration: 900, easing: 'easeInOutCubic' },
					// x는 고정 label slot이라 애니메이션 불필요.
					x: { duration: 0 },
					numbers: { duration: 900, easing: 'easeInOutCubic' },
				},
				transitions: {
					active: { animation: { duration: 900, easing: 'easeInOutCubic' } },
				},
				interaction: { mode: 'index', intersect: false },
				plugins: {
					legend: {
						display: showLegend || list.length > 1,
						position: 'top' as const,
						align: 'end' as const,
						labels: {
							color: 'rgba(203,213,225,0.85)',
							boxWidth: 8,
							boxHeight: 8,
							padding: 8,
							font: { size: 10, weight: 700 },
							usePointStyle: true,
							pointStyle: 'rectRounded' as const,
						},
					},
					tooltip: {
						backgroundColor: 'rgba(13,17,23,0.96)',
						borderColor: 'rgba(48,213,200,0.35)',
						borderWidth: 1,
						padding: 8,
						displayColors: true,
						callbacks: {
							title: (items) => (items?.[0]?.label ? String(items[0].label) : ''),
							label: (ctx) => {
								const label = ctx.dataset.label ? `${ctx.dataset.label}: ` : '';
								return `${label}${formatValue(Number(ctx.parsed.y ?? 0))}`;
							},
						},
					},
				},
				scales: {
					x: {
						display: showAxes,
						grid: { display: false },
						border: { display: false },
						ticks: {
							color: '#64748b',
							font: { size: 9 },
							maxTicksLimit: 4,
							maxRotation: 0,
							autoSkip: true,
							autoSkipPadding: 12,
						},
					},
					y: {
						display: showAxes,
						beginAtZero: true,
						min: 0,
						max: unit === 'percent' ? (maxY ?? 100) : undefined,
						suggestedMax: unit === 'rate' ? suggestedMax : undefined,
						grid: { color: 'rgba(100,116,139,0.08)' },
						border: { display: false },
						ticks: {
							color: '#64748b',
							font: { size: 9 },
							maxTicksLimit: 4,
							callback: (v) => formatValue(Number(v)),
						},
					},
				},
			},
		});
	}

	function streamUpdate(list: Series[]) {
		if (!chart) return;
		const datasets = chart.data.datasets;
		const targetLength = maxLabels(list);
		// Label count는 stable 하게 유지 — fleet-store의 bucketSparkline이 항상
		// 같은 크기의 배열을 뱉으므로, 시간이 흐르면 "oldest bucket이 떨어지고
		// 새 bucket이 오른쪽에 붙는" 슬라이드 효과가 자연스럽게 생긴다.
		chart.data.labels = buildTimeLabels(targetLength);

		for (let i = 0; i < list.length; i += 1) {
			const item = list[i];
			if (!datasets[i]) continue;
			const current = (datasets[i].data as number[]) ?? [];
			const incoming = item.values;
			// 같은 참조를 유지한 채 길이 맞추고 값만 바꾼다 — Chart.js가 index 기준
			// y값 전이 애니메이션(transitions.active)을 걸어줌.
			if (current.length !== incoming.length) {
				current.length = incoming.length;
			}
			for (let j = 0; j < incoming.length; j += 1) current[j] = incoming[j];
			datasets[i].data = current;
		}
	}

	function sync() {
		if (!canvas) return;
		if (!chart) {
			render();
			return;
		}
		const list = seriesList;
		const structureChanged = chart.data.datasets.length !== list.length;

		if (structureChanged) {
			chart.data.labels = buildTimeLabels(maxLabels(list));
			chart.data.datasets = buildDatasets(list);
		} else {
			streamUpdate(list);
		}

		if (unit === 'rate' && chart.options.scales?.y) {
			(chart.options.scales.y as any).suggestedMax = Math.max(peakValue(list) * 1.15, 1024);
		}
		chart.update(structureChanged ? 'none' : 'active');
	}

	$effect(() => {
		seriesList;
		range;
		sync();
	});

	onMount(sync);
	onDestroy(() => {
		chart?.destroy();
		chart = null;
	});
</script>

<div class="wrap">
	<canvas bind:this={canvas}></canvas>
</div>

<style>
	.wrap {
		width: 100%;
		height: 100%;
		min-height: 0;
		min-width: 0;
	}
	canvas {
		width: 100% !important;
		height: 100% !important;
	}
</style>
