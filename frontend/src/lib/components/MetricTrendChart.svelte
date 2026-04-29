<!--
  MetricTrendChart — sidebar detail modal 의 reusable 시계열.

  - Range tabs (1m / 10m / 1h / 6h / 24h / 7d)
  - mount + range 변경마다 /api/metrics/system/?... 또는 buckets/?... 호출
  - WS liveValue 변동마다 append (cap 240/500)
  - derivative 모드: 누적 카운터 (network bytes 등) 의 per-second slope
  - bucket 모드: 서버측 bucket aggregation 사용
  - chart 렌더링은 ECharts (EChartBase) 위임. setOption notMerge:true 로
    chart.js 시절의 destroy + recreate / lastYMax 추적 / toChartPayload 우회
    모두 폐기.
-->
<script lang="ts">
	import { untrack } from 'svelte';
	import { base } from '$app/paths';
	import EChartBase from '$lib/components/charts/EChartBase.svelte';
	import type { EChartsOption } from '$lib/components/charts/echart-registry';

	type RangeKey = '1m' | '10m' | '1h' | '6h' | '24h' | '7d';
	type Unit = 'percent' | 'count' | 'bytes' | 'rate';

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
		hideRangeTabs = false,
		compact = false,
		derivative = false,
		bucket = '',
		windowRange = '',
		bucketField = '',
	}: {
		agentId: string;
		metricField: string;
		metricExtractor?: ((row: any) => number | null | undefined) | null;
		liveValue: number;
		label: string;
		color?: string;
		unit?: Unit;
		defaultRange?: RangeKey;
		accessToken?: string;
		endpoint?: string;
		extraQuery?: string;
		hideRangeTabs?: boolean;
		compact?: boolean;
		derivative?: boolean;
		bucket?: string;
		windowRange?: string;
		bucketField?: string;
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
	let loadedKey = '';
	let lastLive: number | undefined;

	function downsample<T>(arr: T[], keepAtMost = 120): T[] {
		if (arr.length <= keepAtMost) return arr;
		const stride = Math.ceil(arr.length / keepAtMost);
		return arr.filter((_, i) => i % stride === 0);
	}

	function formatClockLabel(iso: string, forRange: RangeKey): string {
		const d = new Date(iso);
		const pad = (n: number) => n.toString().padStart(2, '0');
		if (forRange === '24h' || forRange === '7d') {
			return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
		}
		return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
	}

	async function loadHistory(forRange: RangeKey) {
		if (!agentId || !accessToken) return;
		loading = true;
		try {
			const useBuckets = Boolean(bucket && (windowRange || forRange));
			const limit = forRange === '7d' || forRange === '24h' ? 500 : 240;
			const extra = extraQuery ? `&${extraQuery}` : '';
			const url = useBuckets
				? `${base}${endpoint}buckets/?agent=${encodeURIComponent(agentId)}&range=${windowRange || forRange}&bucket=${bucket}${extra}`
				: `${base}${endpoint}?agent=${encodeURIComponent(agentId)}&range=${forRange}&limit=${limit}&ordering=recorded_at${extra}`;
			const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
			if (!res.ok) return;
			const payload = await res.json();
			const rows: any[] = Array.isArray(payload?.data?.results)
				? payload.data.results
				: Array.isArray(payload?.data)
					? payload.data
					: Array.isArray(payload?.results)
						? payload.results
						: Array.isArray(payload)
							? payload
							: [];
			const useBucketsParse = Boolean(bucket && (windowRange || forRange));
			const tsField = useBucketsParse ? 'bucket_start' : 'recorded_at';
			const kept = downsample(rows);
			const read = useBucketsParse && bucketField
				? (r: any) => Number(r?.[bucketField] ?? 0)
				: metricExtractor
					? (r: any) => {
						const v = metricExtractor(r);
						return typeof v === 'number' && !Number.isNaN(v) ? v : NaN;
					}
					: (r: any) => Number(r?.[metricField] ?? 0);
			const paired = kept
				.map((r) => [read(r), formatClockLabel(r?.[tsField], forRange), new Date(r?.[tsField]).getTime()] as const)
				.filter(([v, , t]) => !Number.isNaN(v) && Number.isFinite(t));
			if (derivative) {
				const rateValues: number[] = [];
				const rateLabels: string[] = [];
				for (let i = 1; i < paired.length; i += 1) {
					const [v0, , t0] = paired[i - 1];
					const [v1, l1, t1] = paired[i];
					const dt = (t1 - t0) / 1000;
					if (dt > 0) {
						rateValues.push(Math.max(0, ((v1 as number) - (v0 as number)) / dt));
						rateLabels.push(l1);
					}
				}
				values = rateValues;
				labels = rateLabels;
			} else {
				values = paired.map(([v]) => v as number);
				labels = paired.map(([, l]) => l);
			}
			loadedKey = `${agentId}|${forRange}`;
		} catch (err) {
			console.error('[MetricTrendChart] history fetch failed', err);
		} finally {
			loading = false;
		}
	}

	function appendLive(v: number | undefined) {
		// derivative 모드: 누적 카운터 그대로 받으면 기울기 표현이 안 되니 skip.
		// loadHistory periodic refresh 가 derivative 라인을 갱신.
		if (derivative) return;
		if (typeof v !== 'number' || Number.isNaN(v)) return;
		// "데이터 없음" stub (systemInfo.memory.usage 첫 WS tick 전 0) 무시.
		if (unit === 'percent' && v === 0 && values.length === 0) return;
		if (v === lastLive && values.length > 0) return;
		lastLive = v;
		const now = new Date();
		const pad = (n: number) => n.toString().padStart(2, '0');
		const lbl =
			range === '24h' || range === '7d'
				? `${pad(now.getMonth() + 1)}/${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`
				: `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
		const cap = range === '7d' || range === '24h' ? 500 : 240;
		values = [...values, v].slice(-cap);
		labels = [...labels, lbl].slice(-cap);
	}

	function computeYBounds(nums: number[], u: Unit): { min: number; max: number } {
		const finite = nums.filter((v) => typeof v === 'number' && !Number.isNaN(v));
		if (u === 'percent') {
			if (finite.length === 0) return { min: 0, max: 1 };
			const dmax = Math.max(...finite);
			if (dmax <= 0) return { min: 0, max: 1 };
			const padded = dmax * 1.25;
			const stops = [1, 2, 3, 5, 7, 10, 15, 20, 30, 50, 75, 100];
			for (const s of stops) {
				if (padded <= s) return { min: 0, max: s };
			}
			return { min: 0, max: 100 };
		}
		if (u === 'rate' || u === 'bytes') {
			if (finite.length === 0) return { min: 0, max: 1024 };
			const dmax = Math.max(...finite);
			if (dmax <= 0) return { min: 0, max: 1024 };
			const padded = dmax * 1.25;
			const pow = Math.pow(1024, Math.floor(Math.log(padded) / Math.log(1024)));
			const ceiled = Math.ceil(padded / pow) * pow;
			return { min: 0, max: ceiled };
		}
		// count: 0~max+10% rounded up
		if (finite.length === 0) return { min: 0, max: 1 };
		const dmax = Math.max(...finite);
		if (dmax <= 0) return { min: 0, max: 1 };
		const ceiled = Math.ceil(dmax * 1.2);
		return { min: 0, max: ceiled };
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

	function formatRate(bps: number): string {
		if (!bps) return '0 B/s';
		const units = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
		const idx = Math.min(
			Math.floor(Math.log(Math.abs(bps)) / Math.log(1024)),
			units.length - 1,
		);
		return `${(bps / Math.pow(1024, idx)).toFixed(1)} ${units[idx]}`;
	}

	function formatValue(v: number, u: Unit): string {
		if (u === 'percent') return `${v.toFixed(1)}%`;
		if (u === 'bytes') return formatBytes(v);
		if (u === 'rate') return formatRate(v);
		return v.toFixed(0);
	}

	function buildOption(
		lbls: string[],
		vals: number[],
		u: Unit,
		seriesLabel: string,
		seriesColor: string,
	): EChartsOption {
		const bounds = computeYBounds(vals, u);
		// percent 의 stepSize 계산: chart.js 시절 로직과 동등
		const percentStep =
			u === 'percent'
				? bounds.max <= 2
					? 0.5
					: bounds.max <= 5
						? 1
						: bounds.max <= 15
							? 2
							: bounds.max <= 30
								? 5
								: 10
				: undefined;
		return {
			animationDuration: 250,
			animationDurationUpdate: 600,
			animationEasingUpdate: 'cubicInOut',
			grid: {
				top: 8,
				left: 8,
				right: 8,
				bottom: 22,
				containLabel: true,
			},
			tooltip: {
				trigger: 'axis',
				backgroundColor: 'rgba(13, 17, 23, 0.95)',
				borderColor: 'rgba(48, 213, 200, 0.4)',
				borderWidth: 1,
				padding: 10,
				textStyle: { color: '#cbd5e1', fontSize: 11 },
				axisPointer: { type: 'line', lineStyle: { color: 'rgba(148, 163, 184, 0.3)' } },
				formatter: (params: any) => {
					const arr = Array.isArray(params) ? params : [params];
					if (arr.length === 0) return '';
					const title = arr[0].axisValueLabel ?? '';
					const lines = arr.map((p: any) => {
						const v = Number(p.value ?? 0);
						return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <strong>${formatValue(v, u)}</strong>`;
					});
					return `<div style="color:#e2e8f0;font-weight:700;margin-bottom:4px">${title}</div>${lines.join('<br/>')}`;
				},
			},
			legend: { show: false },
			xAxis: {
				type: 'category',
				data: lbls,
				boundaryGap: false,
				axisTick: { show: false },
				axisLine: { show: false },
				axisLabel: {
					color: '#64748b',
					hideOverlap: true,
					fontSize: 10,
				},
				splitLine: { show: false },
			},
			yAxis: {
				type: 'value',
				min: bounds.min,
				max: bounds.max,
				interval: percentStep,
				axisTick: { show: false },
				axisLine: { show: false },
				axisLabel: {
					color: '#64748b',
					fontSize: 10,
					formatter: (v: number) => formatValue(v, u),
				},
				splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.12)' } },
			},
			series: [
				{
					type: 'line',
					name: seriesLabel,
					data: vals,
					smooth: 0.35,
					symbol: 'none',
					lineStyle: { color: seriesColor, width: 2 },
					itemStyle: { color: seriesColor },
					areaStyle: { color: `${seriesColor}2a` },
					emphasis: { focus: 'series' },
				},
			],
		};
	}

	let option = $derived<EChartsOption>(buildOption(labels, values, unit, label, color));

	// agent / range 변경 시 history 재요청.
	$effect(() => {
		const key = `${agentId}|${range}`;
		if (key === loadedKey) return;
		untrack(() => loadHistory(range));
	});

	// WS tick append.
	$effect(() => {
		const v = liveValue;
		untrack(() => appendLive(v));
	});
</script>

<div class="trend">
	{#if !hideRangeTabs}
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
	{/if}
	<div class="canvas-wrap" class:compact>
		<EChartBase {option} ariaLabel={label} />
		{#if loading}
			<div class="chart-loading" role="status" aria-live="polite">
				<span class="chart-spinner"></span>
				<span>데이터 불러오는 중…</span>
			</div>
		{:else if values.length === 0}
			<div class="chart-loading muted" role="status">
				<span>이 구간에 기록된 데이터 없음</span>
			</div>
		{/if}
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

	.chart-loading {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 6px;
		background: rgba(13, 17, 23, 0.6);
		backdrop-filter: blur(2px);
		color: var(--text-secondary);
		font-size: 11px;
		font-weight: 700;
		pointer-events: none;
		z-index: 2;
	}
	.chart-loading.muted {
		background: rgba(13, 17, 23, 0.35);
		color: var(--text-muted);
	}
	.chart-spinner {
		width: 18px;
		height: 18px;
		border: 2px solid rgba(48, 213, 200, 0.18);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: chart-spin 0.85s linear infinite;
	}
	@keyframes chart-spin { to { transform: rotate(360deg); } }
	.canvas-wrap.compact {
		height: 110px;
		min-height: 110px;
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
</style>
