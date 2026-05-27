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

	// 7d 는 ContainerDetailModal 의 metricsRange ('7d' 포함) 호환용 — UI selector
	// (RANGE_OPTIONS) 에선 노출 안 함, defaultRange 로만 들어옴.
	type RangeKey = '30s' | '1m' | '5m' | '1h' | '24h' | '7d';
	type Unit = 'percent' | 'count' | 'bytes' | 'rate';

	const CHART_POINTS = 20;
	const RANGE_KEY_TO_MS: Record<RangeKey, number> = {
		'30s': 30_000,
		'1m': 60_000,
		'5m': 300_000,
		'1h': 3_600_000,
		'24h': 86_400_000,
		'7d': 7 * 86_400_000,
	};

	// 짧은 tick (1분 등) 으로 backend raw API 만 부르면 1m 안 raw rows ~1-2 개라
	// 차트가 거의 비어 보임. tick × CHART_POINTS 만큼 window 잡아 bucket
	// aggregation 받으면 정확히 N 개 점.
	const AUTO_BUCKET: Record<RangeKey, { window: string; bucket: string }> = {
		'30s': { window: '10m', bucket: '30' },
		'1m':  { window: '1h',  bucket: '60' },
		'5m':  { window: '6h',  bucket: '300' },
		'1h':  { window: '24h', bucket: '3600' },
		'24h': { window: '7d',  bucket: '86400' },
		'7d':  { window: '7d',  bucket: '86400' },
	};

	// metricField → bucket aggregation field 자동 매핑 (system buckets endpoint 기준).
	// caller 가 bucketField 를 명시하면 그쪽이 우선.
	const FIELD_TO_BUCKET: Record<string, string> = {
		'cpu_usage': 'cpu_avg',
		'memory_usage': 'memory_avg',
		'memory_percent': 'memory_avg',
		'disk_usage': 'disk_avg',
		'gpu_usage': 'gpu_avg',
		'gpu_temperature_max': 'gpu_temperature_max',
	};

	let {
		agentId,
		metricField,
		metricExtractor = null,
		liveValue,
		label,
		color = '#30d5c8',
		unit = 'percent',
		defaultRange = '5m' as RangeKey,
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
		{ key: '30s', label: '30초' },
		{ key: '1m', label: '1분' },
		{ key: '5m', label: '5분' },
		{ key: '1h', label: '1시간' },
		{ key: '24h', label: '24시간' },
	];

	let range = $state<RangeKey>(defaultRange);
	let labels = $state<string[]>([]);
	let timestamps = $state<number[]>([]);
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
			// caller 가 명시 안 했으면 자동 BUCKET_MAP 으로 fetch — tick × N 만큼
			// window 잡고 backend bucket aggregation. 짧은 tick (1m 등) 으로 raw
			// API 만 호출하면 1 분 안 raw rows 1-2 개라 차트가 비어 보임.
			const auto = AUTO_BUCKET[forRange];
			const effWindow = windowRange || auto.window;
			const effBucket = bucket || auto.bucket;
			const effBucketField = bucketField || FIELD_TO_BUCKET[metricField] || '';
			// metricExtractor 는 raw row 에서 per-index 값을 뽑는 용도라 bucket 응답
			// (fleet-aggregate 만 있음) 에는 매칭되는 컬럼이 없다. 명시적인 bucketField
			// 매핑이 없는데 extractor 만 있으면 raw rows 로 강제 fallback — 그래야
			// per-GPU 사용률/VRAM/온도 차트가 "데이터 없음" 으로 안 죽는다.
			const useBuckets = Boolean(effBucket && effWindow)
				&& (effBucketField !== '' || !metricExtractor);
			const limit = forRange === '7d' || forRange === '24h' ? 500 : 240;
			const extra = extraQuery ? `&${extraQuery}` : '';
			const url = useBuckets
				? `${base}${endpoint}buckets/?agent=${encodeURIComponent(agentId)}&range=${effWindow}&bucket=${effBucket}${extra}`
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
			const useBucketsParse = useBuckets;
			const tsField = useBucketsParse ? 'bucket_start' : 'recorded_at';
			const kept = downsample(rows);
			const read = useBucketsParse && effBucketField
				? (r: any) => Number(r?.[effBucketField] ?? 0)
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
				const rateTs: number[] = [];
				for (let i = 1; i < paired.length; i += 1) {
					const [v0, , t0] = paired[i - 1];
					const [v1, l1, t1] = paired[i];
					const dt = (t1 - t0) / 1000;
					if (dt > 0) {
						rateValues.push(Math.max(0, ((v1 as number) - (v0 as number)) / dt));
						rateLabels.push(l1);
						rateTs.push(t1 as number);
					}
				}
				values = rateValues;
				labels = rateLabels;
				timestamps = rateTs;
			} else {
				values = paired.map(([v]) => v as number);
				labels = paired.map(([, l]) => l);
				timestamps = paired.map(([, , t]) => t as number);
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
			range === '24h'
				? `${pad(now.getMonth() + 1)}/${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`
				: `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
		const cap = range === '24h' ? 500 : 240;
		values = [...values, v].slice(-cap);
		labels = [...labels, lbl].slice(-cap);
		timestamps = [...timestamps, now.getTime()].slice(-cap);
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

	function pad2(n: number): string {
		return n < 10 ? `0${n}` : `${n}`;
	}

	function formatAxisTime(value: number, intervalMs: number): string {
		const d = new Date(value);
		const DAY = 86_400_000;
		const HOUR = 3600_000;
		if (intervalMs < 60_000) {
			return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
		}
		if (intervalMs < HOUR) {
			return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
		}
		if (intervalMs < DAY) {
			return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
		}
		return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}`;
	}

	function formatTooltipTime(value: number): string {
		const d = new Date(value);
		return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
	}

	function buildOption(
		lbls: string[],
		ts: number[],
		vals: number[],
		u: Unit,
		seriesLabel: string,
		seriesColor: string,
		intervalMs: number,
	): EChartsOption {
		const bounds = computeYBounds(vals, u);
		const useTimeAxis = ts.length > 0;
		// percent 모드 stepSize: 항상 5~7 ticks 가 되도록 max 별로 조정.
		// ECharts 5.5 는 11 ticks (max=100, step=10) 같은 dense layout 을 modal
		// 처럼 짧은 chart 에서 가독성 부족이라 판단해 alignTicks 경고를 띄움.
		const percentStep =
			u === 'percent'
				? bounds.max <= 2
					? 0.5
					: bounds.max <= 5
						? 1
						: bounds.max <= 15
							? 3
							: bounds.max <= 30
								? 5
								: bounds.max <= 50
									? 10
									: 20
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
				appendToBody: true,
				trigger: 'axis',
				backgroundColor: 'rgba(13, 17, 23, 0.95)',
				borderColor: 'rgba(48, 213, 200, 0.4)',
				borderWidth: 1,
				padding: 10,
				textStyle: { color: '#cbd5e1', fontSize: 11 },
				axisPointer: { type: 'line', lineStyle: { color: 'rgba(148, 163, 184, 0.3)' }, snap: false },
				formatter: (params: any) => {
					const arr = Array.isArray(params) ? params : [params];
					if (arr.length === 0) return '';
					let title = '';
					if (useTimeAxis) {
						const tsValue = Number(arr[0]?.axisValue);
						title = Number.isFinite(tsValue) ? formatTooltipTime(tsValue) : '';
					} else {
						title = arr[0].axisValueLabel ?? '';
					}
					const lines = arr.map((p: any) => {
						const rawVal = Array.isArray(p.value) ? p.value[1] : p.value;
						const v = Number(rawVal ?? 0);
						return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${p.seriesName}: <strong>${formatValue(v, u)}</strong>`;
					});
					return `<div style="color:#e2e8f0;font-weight:700;margin-bottom:4px">${title}</div>${lines.join('<br/>')}`;
				},
			},
			legend: { show: false },
			xAxis: useTimeAxis
				? {
						type: 'time',
						interval: intervalMs,
						minInterval: intervalMs,
						axisTick: { show: false },
						axisLine: { show: false },
						axisLabel: {
							color: '#64748b',
							hideOverlap: true,
							fontSize: 10,
							formatter: (value: number) => formatAxisTime(value, intervalMs),
						},
						splitLine: { show: false },
					}
				: {
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
				// compact (110px) 차트는 ECharts 기본 5~6 ticks 가 라벨끼리
				// 세로로 겹쳐 가독성 저하 — non-percent 는 3 분할로 제한.
				// "0 / 중간 / 최대" 패턴이라 한눈에 들어오고 라벨 간격이
				// 약 35px 확보돼 겹침이 사라진다.
				splitNumber: u === 'percent' ? undefined : compact ? 3 : 4,
				axisTick: { show: false },
				axisLine: { show: false },
				axisLabel: {
					color: '#64748b',
					fontSize: 10,
					hideOverlap: true,
					formatter: (v: number) => formatValue(v, u),
				},
				splitLine: { lineStyle: { color: 'rgba(100, 116, 139, 0.12)' } },
			},
			series: [
				{
					id: 'main',
					type: 'line',
					name: seriesLabel,
					data: useTimeAxis ? vals.map((v, i) => [ts[i], v] as [number, number]) : vals,
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

	// 차트엔 마지막 N(=CHART_POINTS) 개 점만 — tick × N 이 가시 범위.
	let chartLabels = $derived(labels.slice(-CHART_POINTS));
	let chartValues = $derived(values.slice(-CHART_POINTS));
	let chartTimestamps = $derived(timestamps.slice(-CHART_POINTS));
	let tickIntervalMs = $derived(RANGE_KEY_TO_MS[range]);
	let option = $derived<EChartsOption>(
		buildOption(chartLabels, chartTimestamps, chartValues, unit, label, color, tickIntervalMs),
	);

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
		<div class="tabs" role="tablist" title={`갱신 주기 — polling + 차트 x축 tick 간격 + 표시 단위(모두 같음). 항상 마지막 ${CHART_POINTS}개 점 = 갱신 주기 × ${CHART_POINTS} 범위.`}>
			<span class="tick-label">갱신 주기</span>
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
		<EChartBase {option} ariaLabel={label} dataOnly />
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
		cursor: help;
	}

	.tick-label {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.08em;
		color: var(--text-muted);
		text-transform: uppercase;
		padding: 3px 7px;
		border-radius: 5px;
		background: rgba(48, 213, 200, 0.1);
		border: 1px solid rgba(48, 213, 200, 0.25);
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
	/* compact: 최소 110px 를 보장하되, 부모가 높이를 주면(flex 컨테이너 안)
	   그만큼 늘어나 빈 공간 없이 채운다. */
	.canvas-wrap.compact {
		flex: 1 1 0;
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
