<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import UserMetricChart from '$lib/components/UserMetricChart.svelte';
	import ContainerActions from '$lib/components/ContainerActions.svelte';
	import InspectPanel from '$lib/components/InspectPanel.svelte';
	import EventList from '$lib/components/EventList.svelte';
	import { eventColor, eventLabel, type EventRow } from '$lib/utils/container-events';
	import type { MarkLineEntry } from '$lib/components/charts/types';
	import {
		formatBytesValue,
		formatDateTime,
		formatMemoryUsage,
		formatPercent,
		statusLabel,
		statusTone,
	} from '$lib/utils/container-dashboard';

	const cpuHelp = `이 컨테이너가 실제로 사용 중인 CPU 사용률(%)입니다.

여러 코어 환경이라도 0~100% 범위로 정규화돼 표시되므로, 100%에 가까울수록 컨테이너가 받은 CPU를 모두 쓰고 있다는 뜻입니다.

값은 약 10초마다 자동 갱신됩니다.`;

	const memoryHelp = `현재 메모리 사용량 / 컨테이너에 허용된 최대치입니다.

옆의 비율(%)은 (사용량 ÷ 한도)이며, 100%에 가까울수록 OOM(메모리 부족) 위험이 커집니다.

수치는 컨테이너 자체가 보고한 값으로, 호스트 전체 메모리와는 다릅니다.`;

	const networkHelp = `컨테이너가 시작된 시점부터 누적된 네트워크 송수신량입니다.

• RX: 외부에서 컨테이너로 들어온 누적 바이트
• TX: 컨테이너에서 외부로 나간 누적 바이트

순간 속도가 아닌 누적치라 시간이 지날수록 값은 점점 커집니다. 짧은 시간 동안의 변화량은 그래프 기울기로 확인할 수 있습니다.`;

	const diskHelp = `컨테이너가 시작된 시점부터 누적된 디스크 읽기/쓰기 양입니다.

• Read: 디스크에서 읽어 들인 누적 바이트
• Write: 디스크에 기록한 누적 바이트

순간 IOPS가 아닌 누적 바이트입니다. 마찬가지로 그래프 기울기가 가파를수록 그 시간대에 디스크 I/O가 많았다는 의미입니다.`;

	const timeSeriesHelp = `선택한 기간(1H/6H/24H/7D)에 해당하는 메트릭 변화 추이입니다.

• 1H: 최근 1시간 (가장 촘촘)
• 6H/24H/7D: 더 긴 기간 (자동 보간)

그래프 위에 마우스를 올리면 그 시각의 정확한 수치를 확인할 수 있습니다. y축 단위는 자동으로 데이터 범위에 맞춰 조정됩니다.`;

	const runtimeHelp = `이 컨테이너가 어느 요청으로부터 만들어졌는지, 마지막 동기화는 언제 일어났는지 등을 보여주는 메타정보입니다.

문제가 생겼을 때 운영자에게 Container ID나 Request ID를 함께 알려주면 빠르게 추적할 수 있습니다.`;

	const configHelp = `요청 시점에 적용된 포트 매핑과 환경 변수입니다.

• 포트 매핑: 외부에서 접속할 때 사용할 호스트 포트와 컨테이너 내부 포트의 연결
• 환경 변수: 컨테이너가 실행될 때 주입된 값 (비밀번호 등 민감 값이 보일 수 있으니 화면 공유에 유의)`;

	type ContainerDetail = {
		container_id: string;
		name: string;
		image: string;
		status: string;
		last_seen: string;
		agent_hostname?: string;
		template_name?: string | null;
		request_id?: string | null;
		requested_at?: string | null;
		request_status?: string | null;
		review_note?: string;
		custom_env?: Record<string, string>;
		custom_ports?: Array<{ host?: number; container?: number; protocol?: string }>;
		selected_image?: string;
	};

	type MetricsSnapshot = {
		timestamp?: string | null;
		containerId?: string;
		cpu?: { usage?: number };
		memory?: { usage?: number; limit?: number; percent?: number };
		network?: { rx?: number; tx?: number };
		disk?: { read?: number; write?: number };
		gpu?: Array<{ usage?: number | null }> | { usage?: number | null } | null;
	};

	type MetricsHistoryRow = {
		recorded_at: string;
		cpu_usage: number;
		memory_usage: number;
		memory_limit: number;
		memory_percent: number;
		network_rx: number;
		network_tx: number;
		disk_read: number;
		disk_write: number;
		gpu_usage: number | null;
	};

	const RANGE_OPTIONS = [
		{ key: '1m', label: '1분' },
		{ key: '5m', label: '5분' },
		{ key: '1h', label: '1시간' },
		{ key: '24h', label: '24시간' },
		{ key: '7d', label: '7일' },
	] as const;

	// range = 데이터 sample 간격(bucket). window는 그 단위에 맞게 적당한 양으로 자동.
	const RANGE_BUCKET_MAP: Record<(typeof RANGE_OPTIONS)[number]['key'], { window: string; bucket: string }> = {
		'1m': { window: '1h', bucket: '1m' },
		'5m': { window: '6h', bucket: '5m' },
		'1h': { window: '24h', bucket: '1h' },
		'24h': { window: '7d', bucket: '1d' },
		'7d': { window: '7d', bucket: '1d' },
	};

	let container = $state<ContainerDetail | null>(null);
	let currentMetrics = $state<MetricsSnapshot | null>(null);
	let history = $state<MetricsHistoryRow[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let errorMsg = $state('');
	let selectedRange = $state<(typeof RANGE_OPTIONS)[number]['key']>('1h');
	let refreshTimer: ReturnType<typeof setInterval> | null = null;
	let paused = $state(false);
	let inspectData = $state<any>(null);
	let inspectLoading = $state(false);
	let inspectError = $state('');
	let actionMsg = $state('');
	let events = $state<EventRow[]>([]);
	let eventsError = $state('');
	let eventsTimer: ReturnType<typeof setInterval> | null = null;

	let containerId = $derived($page.params.containerId);

	function token(): string | null {
		if (!browser) return null;
		return localStorage.getItem('hc_access_token');
	}

	async function api<T>(path: string): Promise<T> {
		const t = token();
		if (!t) throw new Error('Authentication required.');
		const response = await fetch(`${base}${path}`, {
			headers: { Authorization: `Bearer ${t}` },
		});
		const json = await response.json().catch(() => ({}));
		if (!response.ok) {
			throw new Error(json?.error?.detail || json?.detail || `HTTP ${response.status}`);
		}
		return json.data as T;
	}

	function snapshotGpu(snap: MetricsSnapshot | null): number | null {
		const list = snap?.gpu;
		if (Array.isArray(list)) return Number(list[0]?.usage ?? 0) || 0;
		if (list && typeof list === 'object') return Number((list as any).usage ?? 0) || 0;
		return null;
	}

	function normalizeHistory(rows: MetricsHistoryRow[], snapshot: MetricsSnapshot | null): MetricsHistoryRow[] {
		if (rows.length > 0 || !snapshot?.timestamp) return rows;
		return [
			{
				recorded_at: snapshot.timestamp,
				cpu_usage: snapshot.cpu?.usage ?? 0,
				memory_usage: snapshot.memory?.usage ?? 0,
				memory_limit: snapshot.memory?.limit ?? 0,
				memory_percent: snapshot.memory?.percent ?? 0,
				network_rx: snapshot.network?.rx ?? 0,
				network_tx: snapshot.network?.tx ?? 0,
				disk_read: snapshot.disk?.read ?? 0,
				disk_write: snapshot.disk?.write ?? 0,
				gpu_usage: snapshotGpu(snapshot),
			},
		];
	}

	async function loadDetail() {
		container = await api<ContainerDetail>(`/api/my-containers/${containerId}/`);
	}

	async function loadCurrentMetrics() {
		currentMetrics = await api<MetricsSnapshot>(`/api/my-containers/${containerId}/current-metrics/`);
	}

	async function loadEvents() {
		try {
			// limit 200 — 최대 보이는 이벤트 수. 시간 오름차순 응답.
			const rows = await api<EventRow[]>(`/api/my-containers/${containerId}/events/?limit=200`);
			events = rows ?? [];
			eventsError = '';
		} catch (err: any) {
			eventsError = err?.message || '이벤트 조회 실패';
		}
	}

	async function loadInspect() {
		inspectLoading = true;
		inspectError = '';
		try {
			inspectData = await api<any>(`/api/my-containers/${containerId}/inspect/`);
		} catch (err: any) {
			inspectError = err?.message || 'inspect 조회 실패';
			// agent_offline / timeout 은 차트/메트릭 갱신은 막지 않음
		} finally {
			inspectLoading = false;
		}
	}

	async function handleControlDone(action: string) {
		actionMsg = `'${action}' 명령 완료. 상태를 새로고침합니다.`;
		// 상태 변화는 즉시 반영되지 않을 수 있어 짧게 기다린 뒤 reload
		setTimeout(() => {
			loadDashboard({ withDetail: true });
			loadInspect();
		}, 500);
		setTimeout(() => (actionMsg = ''), 3000);
	}

	function handleControlError(msg: string) {
		actionMsg = msg;
		setTimeout(() => (actionMsg = ''), 6000);
	}

	async function loadHistory() {
		const map = RANGE_BUCKET_MAP[selectedRange];
		const cid = (container?.container_id ?? '').slice(0, 12);
		if (!cid) {
			history = [];
			return;
		}
		const url = `/api/metrics/containers/buckets/?range=${map.window}&bucket=${map.bucket}&container_id=${encodeURIComponent(cid)}`;
		const payload = await api<{ bucket_seconds: number; results: any[] }>(url);
		const rows = Array.isArray(payload?.results) ? payload.results : [];
		history = rows.map((r) => ({
			recorded_at: r.bucket_start,
			cpu_usage: Number(r.cpu_usage_pct_avg ?? r.cpu_avg ?? 0),
			memory_usage: Number(r.memory_avg ?? 0),
			memory_limit: 0,
			memory_percent: Number(r.memory_percent_avg ?? 0),
			network_rx: Number(r.network_rx_max ?? 0),
			network_tx: Number(r.network_tx_max ?? 0),
			disk_read: Number(r.disk_read_max ?? 0),
			disk_write: Number(r.disk_write_max ?? 0),
			gpu_usage: r.gpu_usage_avg !== undefined && r.gpu_usage_avg !== null ? Number(r.gpu_usage_avg) : null,
		}));
	}

	async function loadDashboard(options: { withDetail?: boolean } = {}) {
		const { withDetail = false } = options;
		if (!containerId) return;
		if (!container || withDetail) loading = true;
		else refreshing = true;
		errorMsg = '';
		try {
			// loadHistory가 container.container_id 필요 → detail 먼저 await
			if (withDetail || !container) await loadDetail();
			await Promise.all([loadCurrentMetrics(), loadHistory()]);
			history = normalizeHistory(history, currentMetrics);
			// inspect / events 는 실패해도 차트/메트릭 화면은 계속 보여야 하므로 별도 catch
			loadInspect().catch(() => {});
			loadEvents().catch(() => {});
		} catch (error: any) {
			errorMsg = error?.message || '대시보드를 불러오지 못했습니다.';
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	function handleRangeChange(rangeKey: (typeof RANGE_OPTIONS)[number]['key']) {
		selectedRange = rangeKey;
		loadDashboard();
	}

	function avgOf(values: number[]): number {
		const valid = values.filter((v) => Number.isFinite(v));
		if (valid.length === 0) return 0;
		let sum = 0;
		for (const v of valid) sum += v;
		return sum / valid.length;
	}

	function peakOf(values: number[]): number {
		let m = 0;
		for (const v of values) if (Number.isFinite(v) && v > m) m = v;
		return m;
	}

	function deltaOf(values: number[]): number {
		// 누적 metric (network/disk) 의 구간 증가량 = last - first.
		if (values.length < 2) return 0;
		const first = values[0] ?? 0;
		const last = values[values.length - 1] ?? 0;
		return Math.max(0, last - first);
	}

	let envEntries = $derived(Object.entries(container?.custom_env ?? {}));
	let portMappings = $derived(container?.custom_ports ?? []);
	let rangeLabel = $derived(RANGE_OPTIONS.find((o) => o.key === selectedRange)?.label ?? '');
	let chartGroup = $derived(`hc-container-${containerId}`);

	let cpuAvg = $derived(avgOf(history.map((r) => r.cpu_usage)));
	let cpuPeak = $derived(peakOf(history.map((r) => r.cpu_usage)));
	let memAvgPct = $derived(avgOf(history.map((r) => r.memory_percent)));
	let memPeakPct = $derived(peakOf(history.map((r) => r.memory_percent)));
	let netRxDelta = $derived(deltaOf(history.map((r) => r.network_rx)));
	let netTxDelta = $derived(deltaOf(history.map((r) => r.network_tx)));
	let diskReadDelta = $derived(deltaOf(history.map((r) => r.disk_read)));
	let diskWriteDelta = $derived(deltaOf(history.map((r) => r.disk_write)));
	let gpuValid = $derived(
		history
			.filter((r) => typeof r.gpu_usage === 'number')
			.map((r) => r.gpu_usage as number),
	);
	let gpuAvg = $derived(avgOf(gpuValid));
	let gpuPeak = $derived(peakOf(gpuValid));
	let historyLabels = $derived(
		history.map((row) =>
			new Date(row.recorded_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
		),
	);

	let cpuDatasets = $derived([
		{
			label: 'CPU 사용률',
			color: '#30d5c8',
			values: history.map((row) => row.cpu_usage),
			fill: true,
			format: 'percent' as const,
		},
	]);
	let memoryDatasets = $derived([
		{
			label: '메모리 사용률',
			color: '#4fc3f7',
			values: history.map((row) => row.memory_percent),
			fill: true,
			format: 'percent' as const,
		},
	]);
	let networkDatasets = $derived([
		{
			label: '수신(RX)',
			color: '#30d5c8',
			values: history.map((row) => row.network_rx),
			format: 'bytes' as const,
		},
		{
			label: '송신(TX)',
			color: '#f59e0b',
			values: history.map((row) => row.network_tx),
			format: 'bytes' as const,
		},
	]);
	let diskDatasets = $derived([
		{
			label: '읽기(Read)',
			color: '#38bdf8',
			values: history.map((row) => row.disk_read),
			format: 'bytes' as const,
		},
		{
			label: '쓰기(Write)',
			color: '#a78bfa',
			values: history.map((row) => row.disk_write),
			format: 'bytes' as const,
		},
	]);

	let chartMarkLines = $derived<MarkLineEntry[]>(buildChartMarkLines(events, history));

	function buildChartMarkLines(evs: EventRow[], hist: MetricsHistoryRow[]): MarkLineEntry[] {
		if (hist.length === 0 || evs.length === 0) return [];
		const bucketTs = hist.map((r) => new Date(r.recorded_at).getTime());
		const firstTs = bucketTs[0];
		const lastTs = bucketTs[bucketTs.length - 1];
		// 마지막 bucket 보다 약간 미래(+ 1 bucket 폭)까지는 표시. 그 이후는 차트 범위 밖.
		const bucketSpan = bucketTs.length >= 2 ? bucketTs[1] - bucketTs[0] : 60_000;
		const upper = lastTs + bucketSpan;

		const marks: MarkLineEntry[] = [];
		for (const ev of evs) {
			const t = new Date(ev.ts).getTime();
			if (Number.isNaN(t)) continue;
			if (t < firstTs - bucketSpan || t > upper) continue;
			// 가장 가까운 bucket index. 데이터 적어 linear OK.
			let idx = 0;
			let bestDiff = Infinity;
			for (let i = 0; i < bucketTs.length; i++) {
				const d = Math.abs(bucketTs[i] - t);
				if (d < bestDiff) {
					bestDiff = d;
					idx = i;
				}
			}
			marks.push({ index: idx, label: eventLabel(ev.kind), color: eventColor(ev.kind) });
		}
		return marks;
	}

	let hasGpuHistory = $derived(history.some((row) => typeof row.gpu_usage === 'number'));
	let gpuDatasets = $derived([
		{
			label: 'GPU 사용률',
			color: '#f472b6',
			values: history.map((row) => (typeof row.gpu_usage === 'number' ? row.gpu_usage : 0)),
			fill: true,
			format: 'percent' as const,
		},
	]);
	let currentGpuUsage = $derived(snapshotGpu(currentMetrics));

	onMount(() => {
		loadDashboard({ withDetail: true });
		refreshTimer = setInterval(() => {
			if (!paused) loadDashboard();
		}, 15000);
		// 이벤트는 metric 보다 짧은 주기로 폴링 — 발생이 드물어 부하 작음.
		eventsTimer = setInterval(() => {
			if (!paused) loadEvents();
		}, 10000);
		return () => {
			if (refreshTimer) clearInterval(refreshTimer);
			if (eventsTimer) clearInterval(eventsTimer);
		};
	});
</script>

<div class="page">
	<button class="back-link" onclick={() => goto(`${base}/user/containers`)}>← 내 컨테이너 목록으로</button>

	{#if loading}
		<div class="state-box">대시보드 불러오는 중...</div>
	{:else if errorMsg}
		<div class="state-box error">{errorMsg}</div>
	{:else if container}
		<section class="hero">
			<div class="hero-left">
				<div class="hero-title">
					<p class="eyebrow">2D 모니터링 대시보드</p>
					<div class="hero-name-row">
						<h1>{container.name}</h1>
						<span class="status-pill" style="background: {statusTone(container.status)};">
							{statusLabel(container.status)}
						</span>
					</div>
				</div>
				<p class="hero-subtitle">{container.selected_image || container.image}</p>
				<div class="hero-meta">
					<span>호스트 {container.agent_hostname ?? '-'}</span>
					<span>템플릿 {container.template_name ?? '-'}</span>
					<span>요청 시각 {formatDateTime(container.requested_at)}</span>
					<span>최근 샘플 {formatDateTime(currentMetrics?.timestamp || container.last_seen)}</span>
				</div>
			</div>
			<div class="hero-actions">
				<button
					class="pause-btn"
					class:active={paused}
					onclick={() => (paused = !paused)}
					title={paused ? '자동 새로고침 재개' : '자동 새로고침 일시정지'}
				>
					{paused ? '▶ 재개' : '❚❚ 일시정지'}
				</button>
				<button class="refresh-btn" onclick={() => loadDashboard({ withDetail: true })} disabled={refreshing}>
					{refreshing ? '새로고침 중...' : '지금 새로고침'}
				</button>
			</div>
		</section>

		{#if container.status !== 'running'}
			<div class="banner">
				컨테이너가 현재 <strong>{statusLabel(container.status)}</strong> 상태입니다. 다시 실행되기 전까지 실시간 메트릭이 비어 있거나 오래된 값일 수 있습니다.
			</div>
		{/if}

		<section class="ops-bar">
			<div class="ops-left">
				<span class="ops-label">컨테이너 컨트롤</span>
				<ContainerActions
					containerId={container.container_id}
					currentStatus={container.status}
					onActionDone={handleControlDone}
					onError={handleControlError}
				/>
			</div>
			{#if actionMsg}
				<div class="ops-msg">{actionMsg}</div>
			{/if}
		</section>

		<section class="stat-grid">
			<div class="stat-card">
				<span class="stat-label">CPU 사용률<InfoTooltip text={cpuHelp} placement="bottom-start" /></span>
				<strong>{formatPercent(currentMetrics?.cpu?.usage, 2)}</strong>
				<span class="stat-meta">최근 샘플 기준</span>
				<span class="stat-sub">{rangeLabel} 평균 {formatPercent(cpuAvg, 1)} · 피크 {formatPercent(cpuPeak, 1)}</span>
			</div>
			<div class="stat-card">
				<span class="stat-label">메모리 사용량<InfoTooltip text={memoryHelp} placement="bottom-start" /></span>
				<strong>{formatMemoryUsage(currentMetrics?.memory?.usage, currentMetrics?.memory?.limit)}</strong>
				<span class="stat-meta">전체 대비 {formatPercent(currentMetrics?.memory?.percent, 2)} 사용 중</span>
				<span class="stat-sub">{rangeLabel} 평균 {formatPercent(memAvgPct, 1)} · 피크 {formatPercent(memPeakPct, 1)}</span>
			</div>
			<div class="stat-card">
				<span class="stat-label">네트워크 누적<InfoTooltip text={networkHelp} placement="bottom-start" /></span>
				<strong>{formatBytesValue(currentMetrics?.network?.rx)} / {formatBytesValue(currentMetrics?.network?.tx)}</strong>
				<span class="stat-meta">RX(수신) / TX(송신) 누적</span>
				<span class="stat-sub">{rangeLabel} 증가 ↓ {formatBytesValue(netRxDelta)} · ↑ {formatBytesValue(netTxDelta)}</span>
			</div>
			<div class="stat-card">
				<span class="stat-label">디스크 누적<InfoTooltip text={diskHelp} placement="bottom-start" /></span>
				<strong>{formatBytesValue(currentMetrics?.disk?.read)} / {formatBytesValue(currentMetrics?.disk?.write)}</strong>
				<span class="stat-meta">Read(읽기) / Write(쓰기) 누적</span>
				<span class="stat-sub">{rangeLabel} 증가 R {formatBytesValue(diskReadDelta)} · W {formatBytesValue(diskWriteDelta)}</span>
			</div>
		</section>

		<section class="panel">
			<div class="panel-header">
				<div>
					<h2>성능 지표 추이<InfoTooltip text={timeSeriesHelp} placement="bottom-start" /></h2>
					<p>선택한 조회 단위마다 한 점씩 집계된 평균값을 보여줍니다.</p>
				</div>
				<div class="range-tools">
					<span class="range-label">조회 단위</span>
					<div class="range-tabs">
						{#each RANGE_OPTIONS as option}
							<button
								class="range-btn"
								class:active={selectedRange === option.key}
								onclick={() => handleRangeChange(option.key)}
							>{option.label}</button>
						{/each}
					</div>
				</div>
			</div>

			<p class="chart-hint">차트 위에 마우스를 올리면 모든 차트의 같은 시각이 함께 표시됩니다. 마우스 휠 / 드래그로 구간 확대 가능.</p>
			<div class="chart-grid">
				<div class="chart-card">
					<div class="chart-head">
						<h3>CPU 사용률</h3>
						<span>현재 {formatPercent(currentMetrics?.cpu?.usage, 2)}</span>
					</div>
					<UserMetricChart labels={historyLabels} datasets={cpuDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={chartMarkLines} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>메모리 사용률</h3>
						<span>현재 {formatPercent(currentMetrics?.memory?.percent, 2)}</span>
					</div>
					<UserMetricChart labels={historyLabels} datasets={memoryDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={chartMarkLines} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>네트워크 트래픽</h3>
						<span>수신 {formatBytesValue(currentMetrics?.network?.rx)} · 송신 {formatBytesValue(currentMetrics?.network?.tx)}</span>
					</div>
					<UserMetricChart labels={historyLabels} datasets={networkDatasets} yFormat="bytes" group={chartGroup} enableZoom markLines={chartMarkLines} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>디스크 처리량</h3>
						<span>읽기 {formatBytesValue(currentMetrics?.disk?.read)} · 쓰기 {formatBytesValue(currentMetrics?.disk?.write)}</span>
					</div>
					<UserMetricChart labels={historyLabels} datasets={diskDatasets} yFormat="bytes" group={chartGroup} enableZoom markLines={chartMarkLines} />
				</div>
				{#if hasGpuHistory || (currentGpuUsage !== null && currentGpuUsage !== undefined)}
					<div class="chart-card">
						<div class="chart-head">
							<h3>GPU 사용률</h3>
							<span>현재 {currentGpuUsage !== null ? formatPercent(currentGpuUsage, 2) : '-'}{#if gpuValid.length > 0} · {rangeLabel} 평균 {formatPercent(gpuAvg, 1)} · 피크 {formatPercent(gpuPeak, 1)}{/if}</span>
						</div>
						<UserMetricChart labels={historyLabels} datasets={gpuDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={chartMarkLines} />
					</div>
				{/if}
			</div>
		</section>

		<EventList {events} errorMsg={eventsError} />

		<InspectPanel data={inspectData} loading={inspectLoading} errorMsg={inspectError} />

		<section class="details-grid">
			<div class="panel">
				<div class="panel-header slim">
					<div>
						<h2>런타임 정보<InfoTooltip text={runtimeHelp} placement="bottom-start" /></h2>
						<p>이 컨테이너가 어느 요청에서 만들어졌고, 가장 최근에 언제 동기화됐는지를 보여줍니다.</p>
					</div>
				</div>
				<div class="info-grid">
					<div class="info-item">
						<span class="info-label">컨테이너 ID</span>
						<span class="info-value mono">{container.container_id}</span>
					</div>
					<div class="info-item">
						<span class="info-label">요청 ID</span>
						<span class="info-value mono">{container.request_id ?? '-'}</span>
					</div>
					<div class="info-item">
						<span class="info-label">요청 상태</span>
						<span class="info-value">{statusLabel(container.request_status)}</span>
					</div>
					<div class="info-item">
						<span class="info-label">최근 동기화</span>
						<span class="info-value">{formatDateTime(container.last_seen)}</span>
					</div>
				</div>
				{#if container.review_note}
					<div class="note-box">
						<span class="info-label">검토 메모</span>
						<p>{container.review_note}</p>
					</div>
				{/if}
			</div>

			<div class="panel">
				<div class="panel-header slim">
					<div>
						<h2>요청 시 설정<InfoTooltip text={configHelp} placement="bottom-start" /></h2>
						<p>요청을 만들 때 입력했던 포트 매핑과 환경 변수입니다.</p>
					</div>
				</div>
				<div class="config-split">
					<div class="config-card">
						<span class="config-title">포트 매핑</span>
						{#if portMappings.length > 0}
							<div class="tag-list">
								{#each portMappings as port}
									<span class="tag">호스트 {port.host ?? '-'} → 컨테이너 {port.container ?? '-'} ({port.protocol ?? 'tcp'})</span>
								{/each}
							</div>
						{:else}
							<p class="config-empty">별도로 지정한 포트 매핑이 없습니다.</p>
						{/if}
					</div>
					<div class="config-card">
						<span class="config-title">환경 변수</span>
						{#if envEntries.length > 0}
							<div class="env-list">
								{#each envEntries as [key, value]}
									<div class="env-row">
										<span>{key}</span>
										<span>{value}</span>
									</div>
								{/each}
							</div>
						{:else}
							<p class="config-empty">추가로 입력한 환경 변수가 없습니다.</p>
						{/if}
					</div>
				</div>
			</div>
		</section>
	{/if}
</div>

<style>
	.page {
		max-width: 1280px;
		margin: 0 auto;
		padding: 24px 32px 40px;
	}

	.back-link,
	.refresh-btn,
	.range-btn {
		border: none;
		font-family: inherit;
		cursor: pointer;
	}

	.back-link {
		padding: 0;
		background: transparent;
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 700;
		margin-bottom: 14px;
	}

	.back-link:hover {
		color: var(--accent);
	}

	.state-box,
	.banner {
		padding: 16px 18px;
		border-radius: 14px;
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		color: var(--text-secondary);
	}

	.state-box.error {
		color: #fecaca;
		border-color: rgba(239, 68, 68, 0.3);
		background: rgba(127, 29, 29, 0.18);
	}

	.hero {
		display: flex;
		justify-content: space-between;
		gap: 20px;
		padding: 24px 26px;
		border-radius: 20px;
		background:
			linear-gradient(140deg, rgba(48, 213, 200, 0.16), rgba(9, 75, 102, 0.18)),
			rgba(18, 23, 32, 0.98);
		border: 1px solid rgba(48, 213, 200, 0.18);
	}

	.hero-title {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 4px;
	}
	.hero-name-row {
		display: inline-flex;
		align-items: center;
		gap: 14px;
		flex-wrap: wrap;
	}

	.eyebrow {
		font-size: 11px;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 6px;
	}

	h1 {
		font-size: 32px;
		line-height: 1.1;
	}

	.hero-subtitle {
		margin-top: 8px;
		font-size: 14px;
		color: var(--text-secondary);
		word-break: break-all;
	}

	.hero-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin-top: 14px;
	}

	.hero-meta span {
		padding: 6px 10px;
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.52);
		border: 1px solid rgba(31, 41, 55, 0.8);
		font-size: 12px;
		color: var(--text-secondary);
	}

	.status-pill {
		padding: 5px 12px;
		border-radius: 999px;
		font-size: 12px;
		font-weight: 700;
		color: white;
	}

	.hero-actions {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		flex-wrap: wrap;
	}

	.refresh-btn,
	.pause-btn {
		padding: 10px 16px;
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.86);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 700;
	}

	.pause-btn {
		font-family: inherit;
		cursor: pointer;
	}

	.pause-btn.active {
		background: rgba(239, 68, 68, 0.16);
		border-color: rgba(239, 68, 68, 0.4);
		color: #fca5a5;
	}

	.banner {
		margin-top: 14px;
	}

	.ops-bar {
		margin-top: 14px;
		padding: 14px 16px;
		border-radius: 14px;
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
	}

	.ops-left {
		display: flex;
		align-items: center;
		gap: 14px;
		flex-wrap: wrap;
	}

	.ops-label {
		font-size: 11px;
		font-weight: 800;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--text-muted);
	}

	.ops-msg {
		font-size: 12px;
		color: var(--accent);
		padding: 6px 10px;
		border-radius: 8px;
		background: rgba(48, 213, 200, 0.1);
		border: 1px solid rgba(48, 213, 200, 0.3);
	}

	.stat-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 14px;
		margin-top: 18px;
	}

	.stat-card,
	.panel,
	.chart-card,
	.config-card {
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
	}

	.stat-card {
		padding: 18px 20px;
		border-radius: 16px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.stat-label {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.stat-card strong {
		font-size: 22px;
		color: var(--text-primary);
		word-break: break-word;
	}

	.stat-meta {
		font-size: 11px;
		color: var(--text-muted);
	}

	.stat-sub {
		font-size: 11px;
		color: var(--accent);
		opacity: 0.85;
		margin-top: 2px;
	}

	.chart-hint {
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 12px;
	}

	.panel {
		border-radius: 18px;
		padding: 20px;
		margin-top: 18px;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: 18px;
		margin-bottom: 18px;
	}

	.panel-header.slim {
		margin-bottom: 16px;
	}

	h2 {
		font-size: 20px;
		margin-bottom: 4px;
	}

	h2 + p,
	.panel-header p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.range-tools {
		display: inline-flex;
		align-items: center;
		gap: 10px;
	}
	.range-label {
		font-size: 12px;
		font-weight: 800;
		color: var(--text-muted);
		letter-spacing: 0.02em;
	}
	.range-tabs {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.range-btn {
		padding: 8px 12px;
		border-radius: 10px;
		background: rgba(13, 17, 23, 0.8);
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 700;
	}

	.range-btn.active {
		background: rgba(48, 213, 200, 0.18);
		color: var(--accent);
	}

	.chart-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
	}

	.chart-card {
		border-radius: 16px;
		padding: 16px;
	}

	.chart-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
		margin-bottom: 20px;
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.12);
	}

	.chart-head h3 {
		font-size: 15px;
	}

	.chart-head span {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.details-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
		gap: 18px;
	}

	.info-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}

	.info-item,
	.note-box,
	.config-card {
		padding: 14px;
		border-radius: 14px;
		background: rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
	}

	.info-label,
	.config-title {
		display: block;
		font-size: 11px;
		color: var(--text-muted);
		margin-bottom: 4px;
	}

	.info-value {
		font-size: 12px;
		color: var(--text-primary);
		word-break: break-word;
	}

	.info-value.mono {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.note-box {
		margin-top: 12px;
	}

	.note-box p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.config-split {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.tag-list {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.tag {
		padding: 6px 10px;
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.12);
		color: var(--accent);
		font-size: 11px;
		font-weight: 700;
	}

	.env-list {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.env-row {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		font-size: 12px;
		color: var(--text-primary);
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(31, 41, 55, 0.7);
	}

	.env-row:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.config-empty {
		font-size: 12px;
		color: var(--text-secondary);
	}

	@media (max-width: 980px) {
		.page {
			padding: 20px 16px 28px;
		}

		.hero,
		.panel-header,
		.chart-head,
		.env-row {
			flex-direction: column;
			align-items: stretch;
		}

		.stat-grid,
		.chart-grid,
		.details-grid,
		.info-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
