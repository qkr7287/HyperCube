<!--
  Reusable time-series chart for sidebar detail modals.

  - Range tabs (1m / 10m / 1h / 6h / 24h / 7d).
  - Loads recent history from /api/metrics/system/?agent=<id>&range=<r>&limit=N
    on mount + on range change, so the chart is never blank on first open.
  - Appends live samples on every agentMetric prop tick.
  - Chart.js under the hood for axes/tooltip/anti-aliasing; overflow fixed
    via an explicit wrap height + maintainAspectRatio=false.
  - Percent series snap to 0/10/20/…/100 grid (fixed Y-axis), non-percent
    series let Chart.js auto-pick a rounded scale.
-->
<script lang="ts">
	import { untrack } from 'svelte';
	import {
		CategoryScale,
		Chart,
		Filler,
		LineController,
		LineElement,
		LinearScale,
		PointElement,
		Tooltip,
	} from 'chart.js';
	import { base } from '$app/paths';

	Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip);

	type RangeKey = '1m' | '10m' | '1h' | '6h' | '24h' | '7d';
	type Unit = 'percent' | 'count' | 'bytes';

	let {
		agentId,
		metricField,
		metricExtractor = null,
		liveValue,
		label,
		color = '#30d5c8',
		unit = 'percent',
		defaultRange = '10m',
		accessToken = '',
		endpoint = '/api/metrics/system/',
		extraQuery = '',
	}: {
		agentId: string;
		/** field name in the backend metrics response (cpu_usage, memory_usage, etc.).
		 *  Ignored when `metricExtractor` is provided. */
		metricField: string;
		/** Extract a scalar out of a row when the data isn't a flat column —
		 *  e.g. GPU charts pull `row.gpu[index].usage`. Return null/NaN to
		 *  skip that row. */
		metricExtractor?: ((row: any) => number | null | undefined) | null;
		/** current live value from WS systemInfo. Each change appends to the chart. */
		liveValue: number;
		label: string;
		color?: string;
		unit?: Unit;
		defaultRange?: RangeKey;
		accessToken?: string;
		endpoint?: string;
		/** extra query string fragment (no leading &) — e.g. "container_id=abc" */
		extraQuery?: string;
	} = $props();

	const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
		{ key: '1m', label: '1분' },
		{ key: '10m', label: '10분' },
		{ key: '1h', label: '1시간' },
		{ key: '6h', label: '6시간' },
		{ key: '24h', label: '24시간' },
		{ key: '7d', label: '7일' },
	];

	let range = $state<RangeKey>(defaultRange);
	let labels = $state<string[]>([]);
	let values = $state<number[]>([]);
	let loading = $state(false);
	let loadedKey = ''; // agentId+range we last fetched for
	let canvasEl: HTMLCanvasElement | null = null;
	let chart: Chart | null = null;
	let lastLive: number | undefined;

	/**
	 * For long ranges the point count can be huge. Client-side bucket down to
	 * ~120 points for readability; browser handles the rest.
	 */
	function downsample<T>(arr: T[], keepAtMost = 120): T[] {
		if (arr.length <= keepAtMost) return arr;
		const stride = Math.ceil(arr.length / keepAtMost);
		return arr.filter((_, i) => i % stride === 0);
	}

	function formatClockLabel(iso: string, forRange: RangeKey): string {
		const d = new Date(iso);
		const pad = (n: number) => n.toString().padStart(2, '0');
		// For multi-day windows, show date; otherwise hh:mm.
		if (forRange === '24h' || forRange === '7d') {
			return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
		}
		return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
	}

	async function loadHistory(forRange: RangeKey) {
		if (!agentId || !accessToken) return;
		loading = true;
		try {
			const limit = forRange === '7d' || forRange === '24h' ? 500 : 240;
			const extra = extraQuery ? `&${extraQuery}` : '';
			const res = await fetch(
				`${base}${endpoint}?agent=${encodeURIComponent(agentId)}&range=${forRange}&limit=${limit}&ordering=recorded_at${extra}`,
				{ headers: { Authorization: `Bearer ${accessToken}` } },
			);
			if (!res.ok) return;
			const payload = await res.json();
			const rows: any[] = payload?.data ?? payload?.results ?? payload ?? [];
			// Backend returns oldest→newest when limit is set (see paginate override).
			const kept = downsample(rows);
			const read = metricExtractor
				? (r: any) => {
					const v = metricExtractor(r);
					return typeof v === 'number' && !Number.isNaN(v) ? v : NaN;
				}
				: (r: any) => Number(r?.[metricField] ?? 0);
			const paired = kept
				.map((r) => [read(r), formatClockLabel(r?.recorded_at, forRange)] as const)
				.filter(([v]) => !Number.isNaN(v));
			values = paired.map(([v]) => v as number);
			labels = paired.map(([, l]) => l);
			loadedKey = `${agentId}|${forRange}`;
		} catch (err) {
			console.error('[MetricTrendChart] history fetch failed', err);
		} finally {
			loading = false;
		}
	}

	function appendLive(v: number | undefined) {
		if (typeof v !== 'number' || Number.isNaN(v)) return;
		// Skip the "no data yet" stub (e.g. systemInfo.memory.usage before the
		// first WS tick). Without this, a leading 0 drags the Y-axis floor down
		// and the chart zooms out to 0–100% even when the real series sits at 94%.
		if (unit === 'percent' && v === 0 && values.length === 0) return;
		if (v === lastLive && values.length > 0) return;
		lastLive = v;
		const now = new Date();
		const pad = (n: number) => n.toString().padStart(2, '0');
		const label =
			range === '24h' || range === '7d'
				? `${pad(now.getMonth() + 1)}/${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`
				: `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;

		// Append and soft-cap: keep ~240 visible points for short ranges,
		// more for long ranges (backend already paginated).
		const cap = range === '7d' || range === '24h' ? 500 : 240;
		values = [...values, v].slice(-cap);
		labels = [...labels, label].slice(-cap);
	}

	function rebuildChart() {
		if (!canvasEl) return;
		// Chart.js mutates its config/data objects, so we must always hand it
		// plain copies. Passing $state arrays directly trips Svelte 5's
		// descriptor guard (state_descriptors_fixed).
		const labelsCopy = [...labels];
		const valuesCopy = [...values];
		const bounds = computeYBounds(valuesCopy, unit);
		// Destroy + recreate every time. Chart.js's in-place option mutation
		// is unreliable for re-applying scale bounds (beginAtZero / min / max /
		// stepSize all interact in surprising ways), so we just throw away the
		// instance on each data change. The dataset is small, redraws are cheap.
		if (chart) {
			chart.destroy();
			chart = null;
		}
		chart = new Chart(canvasEl, {
			type: 'line',
			data: {
				labels: labelsCopy,
				datasets: [
					{
						label,
						data: valuesCopy,
						borderColor: color,
						backgroundColor: `${color}2a`, // color + ~16% alpha
						fill: true,
						tension: 0.35,
						borderWidth: 2,
						pointRadius: 0,
						pointHoverRadius: 4,
					},
				],
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 600 },
				interaction: { mode: 'index', intersect: false },
				plugins: {
					tooltip: {
						backgroundColor: 'rgba(13,17,23,0.95)',
						borderColor: 'rgba(48,213,200,0.4)',
						borderWidth: 1,
						padding: 10,
						callbacks: {
							label: (ctx) => {
								const v = Number(ctx.parsed.y ?? 0);
								if (unit === 'percent') return `${ctx.dataset.label}: ${v.toFixed(1)}%`;
								if (unit === 'bytes') return `${ctx.dataset.label}: ${formatBytes(v)}`;
								return `${ctx.dataset.label}: ${v.toFixed(0)}`;
							},
						},
					},
					legend: { display: false },
				},
				scales: {
					x: {
						ticks: {
							color: '#64748b',
							maxRotation: 0,
							autoSkipPadding: 16,
							font: { size: 10 },
						},
						grid: { color: 'rgba(100,116,139,0.08)' },
					},
					y: {
						type: 'linear',
						beginAtZero: false,
						min: bounds.min,
						max: bounds.max,
						suggestedMin: bounds.min,
						suggestedMax: bounds.max,
						ticks: {
							color: '#64748b',
							font: { size: 10 },
							stepSize: unit === 'percent' ? 10 : undefined,
							autoSkip: false,
							callback: (v) => {
								if (unit === 'percent') return `${v}%`;
								if (unit === 'bytes') return formatBytes(Number(v));
								return v;
							},
						},
						grid: { color: 'rgba(100,116,139,0.12)' },
					},
				},
			},
		});
	}

	/**
	 * Choose Y-axis bounds that actually focus on the data.
	 *
	 * - Percent series snap to 10-unit grid lines, stay pinned at [0, 100]
	 *   limits, and expand to show ±10pt of padding around the live range.
	 *   So quiet CPU stays zoomed to 0–30%, but a spike to 92% still reads
	 *   against a 70–100% backdrop.
	 * - Non-percent series (counts / bytes) let Chart.js auto-pick.
	 */
	function computeYBounds(values: number[], u: Unit): { min?: number; max?: number } {
		if (u !== 'percent') return {};
		const nums = values.filter((v) => typeof v === 'number' && !Number.isNaN(v));
		if (nums.length === 0) return { min: 0, max: 10 };
		let dmin = Math.min(...nums);
		let dmax = Math.max(...nums);
		// Padding: ±10 percentage points, rounded to the nearest 10.
		const pad = 10;
		let lo = Math.max(0, Math.floor((dmin - pad) / 10) * 10);
		let hi = Math.min(100, Math.ceil((dmax + pad) / 10) * 10);
		// Always show at least a 20-point window so tiny variation stays legible.
		if (hi - lo < 20) hi = Math.min(100, lo + 20);
		if (hi - lo < 20) lo = Math.max(0, hi - 20);
		return { min: lo, max: hi };
	}

	function formatBytes(bytes: number): string {
		if (!bytes) return '0 B';
		const units = ['B', 'KB', 'MB', 'GB', 'TB'];
		const idx = Math.min(
			Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024)),
			units.length - 1,
		);
		return `${(bytes / Math.pow(1024, idx)).toFixed(1)} ${units[idx]}`;
	}

	// Fetch history when agent/range changes.
	$effect(() => {
		const key = `${agentId}|${range}`;
		if (key === loadedKey) return;
		untrack(() => loadHistory(range));
	});

	// Append each fresh WS tick.
	$effect(() => {
		appendLive(liveValue);
	});

	// Render / refresh Chart.js.
	$effect(() => {
		// trigger on labels/values change
		labels;
		values;
		untrack(() => rebuildChart());
	});

	$effect(() => {
		return () => {
			chart?.destroy();
			chart = null;
		};
	});
</script>

<div class="trend">
	<div class="tabs" role="tablist">
		{#each RANGE_OPTIONS as opt}
			<button
				type="button"
				role="tab"
				aria-selected={range === opt.key}
				class="tab"
				class:active={range === opt.key}
				onclick={() => (range = opt.key)}
			>
				{opt.label}
			</button>
		{/each}
		{#if loading}
			<span class="loading-mark">로딩…</span>
		{:else if values.length === 0}
			<span class="loading-mark muted">이 구간에 기록된 데이터 없음</span>
		{/if}
	</div>
	<div class="canvas-wrap">
		<canvas bind:this={canvasEl}></canvas>
	</div>
</div>

<style>
	.trend {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
	}

	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		align-items: center;
	}

	.tab {
		background: transparent;
		border: 1px solid rgba(148, 163, 184, 0.14);
		color: #94a3b8;
		font-family: inherit;
		font-size: 11px;
		font-weight: 600;
		padding: 4px 10px;
		border-radius: 999px;
		cursor: pointer;
		transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
	}
	.tab:hover {
		background: rgba(48, 213, 200, 0.08);
		color: #cbd5e1;
	}
	.tab.active {
		background: rgba(48, 213, 200, 0.18);
		border-color: rgba(48, 213, 200, 0.55);
		color: #30d5c8;
	}

	.loading-mark {
		margin-left: auto;
		font-size: 11px;
		color: #30d5c8;
	}
	.loading-mark.muted {
		color: #475569;
	}

	.canvas-wrap {
		position: relative;
		width: 100%;
		height: 220px;
		min-height: 220px;
		background: #0f172a;
		border: 1px solid rgba(148, 163, 184, 0.12);
		border-radius: 12px;
		padding: 12px 14px;
		box-sizing: border-box;
	}
	.canvas-wrap canvas {
		position: absolute;
		inset: 12px 14px;
		width: calc(100% - 28px) !important;
		height: calc(100% - 24px) !important;
	}
</style>
