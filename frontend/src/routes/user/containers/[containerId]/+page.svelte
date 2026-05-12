<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/stores';
	import InfoTooltip from '$lib/components/InfoTooltip.svelte';
	import UserMetricChart from '$lib/components/UserMetricChart.svelte';
	import ContainerActions from '$lib/components/ContainerActions.svelte';
	import ContainerKpiBar from '$lib/components/ContainerKpiBar.svelte';
	import InspectPanel from '$lib/components/InspectPanel.svelte';
	import EventList from '$lib/components/EventList.svelte';
	import LogTailPanel from '$lib/components/LogTailPanel.svelte';
	import ProcessTopPanel from '$lib/components/ProcessTopPanel.svelte';
	import ConsolePanel from '$lib/components/ConsolePanel.svelte';
	import StateBox from '$lib/components/StateBox.svelte';
	import AgentStatusIndicator from '$lib/components/AgentStatusIndicator.svelte';
	import ContainerLimitModal from '$lib/components/ContainerLimitModal.svelte';
	import { activeAgentIds } from '$lib/stores/global-events';
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
		agent?: string; // Agent UUID (FK)
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
	let actionMsgKind = $state<'info' | 'success' | 'error'>('info');
	let actionMsgTimer: ReturnType<typeof setTimeout> | null = null;
	let limitModalOpen = $state(false);

	// === 운영 인사이트 derived (hero meta 옆 chip) ===
	// 최근 5분 안의 die/restart 횟수 — "재시작 반복" 자동 탐지
	let recentRestarts = $derived.by(() => {
		const cutoff = Date.now() - 5 * 60 * 1000;
		return events.filter((e) => {
			if (e.kind !== 'die' && e.kind !== 'restart' && e.kind !== 'oom') return false;
			const ts = new Date(e.ts).getTime();
			return Number.isFinite(ts) && ts > cutoff;
		}).length;
	});
	// 가장 최근 die / kill 이벤트의 exit_code / signal — last exit reason
	let lastExit = $derived.by(() => {
		const dieOrKill = events
			.filter((e) => e.kind === 'die' || e.kind === 'kill')
			.sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime())[0];
		return dieOrKill || null;
	});
	// inspect 기반 OOM / health 신호
	let isOomKilled = $derived<boolean>(!!inspectData?.state?.oomKilled);
	let healthStatus = $derived<string | null>(inspectData?.state?.health?.status ?? null);
	let healthFailing = $derived(
		healthStatus === 'unhealthy' ||
			healthStatus === 'starting' ||
			(inspectData?.state?.health?.failingStreak ?? 0) > 0,
	);
	// ops-status: uptime (since startedAt), PID
	let uptimeText = $derived.by<string>(() => {
		const startedAt = inspectData?.state?.startedAt;
		if (!startedAt || !inspectData?.state?.running) return '-';
		const sec = Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
		if (sec < 60) return `${sec}초 가동`;
		if (sec < 3600) return `${Math.floor(sec / 60)}분 가동`;
		if (sec < 86400) {
			const h = Math.floor(sec / 3600);
			const m = Math.floor((sec % 3600) / 60);
			return m > 0 ? `${h}시간 ${m}분` : `${h}시간 가동`;
		}
		const d = Math.floor(sec / 86400);
		const h = Math.floor((sec % 86400) / 3600);
		return h > 0 ? `${d}일 ${h}시간` : `${d}일 가동`;
	});
	let containerPid = $derived<number | null>(inspectData?.state?.pid ?? null);
	let hasInsight = $derived(
		recentRestarts > 0 || isOomKilled || (healthStatus && healthStatus !== 'healthy'),
	);

	// agent online 판단: global event store 우선, 없으면 last_seen 2분 이내면 online 가정.
	// (사용자 페이지 globalWS 가 늦게 붙거나 backend 가 transition event 못 보낸 케이스,
	//  메트릭 폴링이 잠깐 지연되는 경우까지 흡수 — 120s 안전마진)
	let agentOnline = $derived.by<boolean>(() => {
		if (!container?.agent) return false;
		if ($activeAgentIds.has(container.agent)) return true;
		const lastIso = currentMetrics?.timestamp || container.last_seen;
		if (!lastIso) return false;
		const ts = new Date(lastIso).getTime();
		return Number.isFinite(ts) && Date.now() - ts < 120_000;
	});
	let events = $state<EventRow[]>([]);
	let eventsError = $state('');
	let eventsTimer: ReturnType<typeof setInterval> | null = null;
	// 누적 metric (network/disk) 차트 모드. cumulative = 원본, rate = bucket 간 delta/sec.
	let networkMode = $state<'cumulative' | 'rate'>('cumulative');
	let diskMode = $state<'cumulative' | 'rate'>('cumulative');
	// API 응답에 포함된 bucket 폭 (초) — rate 계산에 사용. fallback 으로 RANGE 매핑.
	let bucketSeconds = $state<number>(60);

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

	async function loadInspect({ silent = false } = {}) {
		// silent (=백그라운드 polling): loading bar / error 잠시 표시 모두 끔.
		//   - 이미 데이터 있으면 in-place 갱신만, 잠깐의 fetch 실패는 화면에 안 띄움.
		//   - 진짜 fail 이 지속되면 다음 fetch 도 안 들어와서 데이터는 stale 이지만
		//     UI 가 매 5초 깜빡이는 것보단 stale 상태로 두는 게 운영자 시야에 낫다.
		// 첫 fetch (또는 명시적 reload) 만 loading=true / error clear 동작.
		const showLoading = !silent || !inspectData;
		if (showLoading) {
			inspectLoading = true;
			inspectError = '';
		}
		try {
			inspectData = await api<any>(`/api/my-containers/${containerId}/inspect/`);
			// 성공 시는 silent 라도 stale error chip 은 지워준다.
			if (inspectError) inspectError = '';
		} catch (err: any) {
			if (showLoading) {
				inspectError = err?.message || 'inspect 조회 실패';
			}
			// silent 폴링 실패는 조용히 — 다음 cycle 에 다시 시도.
		} finally {
			if (showLoading) inspectLoading = false;
		}
	}

	function showActionMsg(text: string, kind: 'info' | 'success' | 'error', ttlMs: number) {
		actionMsg = text;
		actionMsgKind = kind;
		if (actionMsgTimer) clearTimeout(actionMsgTimer);
		actionMsgTimer = setTimeout(() => {
			actionMsg = '';
			actionMsgTimer = null;
		}, ttlMs);
	}

	function dismissActionMsg() {
		if (actionMsgTimer) clearTimeout(actionMsgTimer);
		actionMsgTimer = null;
		actionMsg = '';
	}

	async function handleControlDone(action: string) {
		showActionMsg(`'${action}' 명령 완료. 상태를 새로고침합니다.`, 'success', 3500);
		// 상태 변화는 즉시 반영되지 않을 수 있어 짧게 기다린 뒤 reload (silent — 이미 데이터 있으니 깜빡임 안 일으킴)
		setTimeout(() => {
			loadDashboard({ withDetail: true });
			loadInspect({ silent: true });
		}, 500);
	}

	function handleControlError(msg: string) {
		showActionMsg(msg, 'error', 8000);
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
		// rate 계산용 bucket 폭. 없으면 1 (분모 0 방지).
		bucketSeconds = Number(payload?.bucket_seconds) || 60;
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
			// inspect / events 는 실패해도 차트/메트릭 화면은 계속 보여야 하므로 별도 catch.
			// silent — polling 마다 loading bar / error chip 깜빡임 방지.
			loadInspect({ silent: true }).catch(() => {});
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

	function rateOf(values: number[], secs: number): number[] {
		// 누적값 → bucket 간 delta/초. 첫 점은 비교 대상 없으므로 0.
		// 컨테이너 재시작으로 카운터가 reset(음수) 되면 그 점은 0 으로 (hold).
		if (values.length === 0) return [];
		const out: number[] = [0];
		const denom = secs > 0 ? secs : 1;
		for (let i = 1; i < values.length; i++) {
			const diff = (values[i] ?? 0) - (values[i - 1] ?? 0);
			out.push(diff > 0 ? diff / denom : 0);
		}
		return out;
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
	let networkRx = $derived(history.map((row) => row.network_rx));
	let networkTx = $derived(history.map((row) => row.network_tx));
	let diskRead = $derived(history.map((row) => row.disk_read));
	let diskWrite = $derived(history.map((row) => row.disk_write));

	let networkFormat = $derived<'bytes' | 'bytes_per_sec'>(networkMode === 'rate' ? 'bytes_per_sec' : 'bytes');
	let diskFormat = $derived<'bytes' | 'bytes_per_sec'>(diskMode === 'rate' ? 'bytes_per_sec' : 'bytes');

	let networkDatasets = $derived([
		{
			label: '수신(RX)',
			color: '#30d5c8',
			values: networkMode === 'rate' ? rateOf(networkRx, bucketSeconds) : networkRx,
			format: networkFormat,
		},
		{
			label: '송신(TX)',
			color: '#f59e0b',
			values: networkMode === 'rate' ? rateOf(networkTx, bucketSeconds) : networkTx,
			format: networkFormat,
		},
	]);
	let diskDatasets = $derived([
		{
			label: '읽기(Read)',
			color: '#38bdf8',
			values: diskMode === 'rate' ? rateOf(diskRead, bucketSeconds) : diskRead,
			format: diskFormat,
		},
		{
			label: '쓰기(Write)',
			color: '#a78bfa',
			values: diskMode === 'rate' ? rateOf(diskWrite, bucketSeconds) : diskWrite,
			format: diskFormat,
		},
	]);

	// 임계 markLine 은 chartMarkLines 선언 후로 이동 (TDZ 방지).

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

	// 임계 markLine: CPU/Memory % 차트 위에 80% (warn) / 90% (danger) horizontal.
	const THRESHOLD_LINES: MarkLineEntry[] = [
		{ yAxis: 80, label: '경고 80%', color: '#eab308' },
		{ yAxis: 90, label: '위험 90%', color: '#ef4444' },
	];
	// CPU/Memory 차트 markLines = events vertical + thresholds horizontal 결합.
	let percentChartMarkLines = $derived<MarkLineEntry[]>([
		...chartMarkLines,
		...THRESHOLD_LINES,
	]);

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
		<div class="state-wrap"><StateBox kind="loading" message="대시보드 불러오는 중..." /></div>
	{:else if errorMsg}
		<div class="state-wrap">
			<StateBox
				kind="error"
				message={errorMsg}
				action={() => loadDashboard({ withDetail: true })}
				actionLabel="다시 시도"
			/>
		</div>
	{:else if container}
		<div class="topbar-sticky">
			<div class="unified-bar">
			<section class="hero">
				<span class="hero-caption">CONTAINER</span>
				<div class="hero-main">
					<div class="hero-titlebar">
						<h1>{container.name}</h1>
						<span class="status-pill" style="background: {statusTone(container.status)};">
							{statusLabel(container.status)}
						</span>
						<span class="hero-image" title="이미지">{container.selected_image || container.image}</span>
					</div>
					<div class="hero-meta">
						<AgentStatusIndicator
							agentId={container.agent}
							hostname={container.agent_hostname}
							lastSeen={currentMetrics?.timestamp || container.last_seen}
						/>
						<span class="mono-chip" title="컨테이너 ID">
							ID {container.container_id.slice(0, 12)}
						</span>
						{#if container.template_name}
							<span class="meta-chip" title="요청 템플릿">📦 {container.template_name}</span>
						{/if}

						<!-- 운영 인사이트 chip — 이상 신호 있을 때만 표시 -->
						{#if recentRestarts >= 2}
							<span class="insight-chip danger" title="최근 5분 안에 컨테이너가 {recentRestarts}회 die/restart/oom — 재시작 루프 의심">
								🔄 재시작 {recentRestarts}회 (5분)
							</span>
						{:else if recentRestarts === 1}
							<span class="insight-chip warn" title="최근 5분 안에 컨테이너가 1회 재시작 또는 종료됨">
								🔄 재시작 1회 (5분)
							</span>
						{/if}
						{#if isOomKilled}
							<span class="insight-chip danger" title="컨테이너가 OOM (Out of Memory) 으로 강제 종료된 적 있음">
								⚠ OOM Kill
							</span>
						{:else if lastExit && typeof lastExit.exit_code === 'number' && lastExit.exit_code !== 0}
							<span class="insight-chip warn" title="가장 최근 종료 exit code {lastExit.exit_code}">
								⚠ 최근 exit {lastExit.exit_code}
							</span>
						{/if}
						{#if healthStatus === 'unhealthy'}
							<span class="insight-chip danger" title="Docker healthcheck 결과 unhealthy">
								❤ Health: unhealthy
							</span>
						{:else if healthStatus === 'starting'}
							<span class="insight-chip warn" title="healthcheck 가 아직 starting 단계">
								❤ Health: starting
							</span>
						{:else if healthStatus === 'healthy'}
							<span class="insight-chip ok" title="healthcheck 통과">
								❤ Health: healthy
							</span>
						{/if}
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
						{refreshing ? '새로고침 중...' : '↻ 새로고침'}
					</button>
				</div>
			</section>

			<section class="kpi-row">
				<ContainerKpiBar
					{currentMetrics}
					{history}
					{rangeLabel}
					{cpuAvg}
					{cpuPeak}
					{memAvgPct}
					{memPeakPct}
					{netRxDelta}
					{netTxDelta}
					{diskReadDelta}
					{diskWriteDelta}
					hasGpu={hasGpuHistory || (currentGpuUsage !== null && currentGpuUsage !== undefined)}
					{currentGpuUsage}
					{gpuAvg}
					{gpuPeak}
					{cpuHelp}
					{memoryHelp}
					{networkHelp}
					{diskHelp}
				/>
			</section>

			<section class="ops-bar">
				<span class="ops-caption">CONTROL</span>
				<div class="ops-status" data-status={container.status}>
					<div class="status-orb">
						<span class="orb-core"></span>
						<span class="orb-pulse" aria-hidden="true"></span>
					</div>
					<div class="status-text">
						<span class="status-name">{statusLabel(container.status)}</span>
						<span class="status-meta">
							{uptimeText}{#if containerPid} · PID {containerPid}{/if}
						</span>
					</div>
				</div>
				<div class="ops-divider" aria-hidden="true"></div>
				<div class="ops-actions">
					<ContainerActions
						containerId={container.container_id}
						currentStatus={container.status}
						{agentOnline}
						onActionDone={handleControlDone}
						onError={handleControlError}
					/>
					<button
						class="limit-icon-btn"
						onclick={() => (limitModalOpen = true)}
						disabled={!agentOnline}
						title={agentOnline ? '메모리 / CPU / 재시작 정책 수정' : 'Agent 오프라인 — 수정 불가'}
						aria-label="자원 한도 수정"
					>⚙</button>
				</div>
				{#if actionMsg}
					<div class="ops-msg" data-kind={actionMsgKind} role="status">
						<span class="ops-msg-icon" aria-hidden="true">
							{actionMsgKind === 'error' ? '⚠' : actionMsgKind === 'success' ? '✓' : 'ℹ'}
						</span>
						<span class="ops-msg-text">{actionMsg}</span>
						<button class="ops-msg-close" onclick={dismissActionMsg} aria-label="닫기">✕</button>
					</div>
				{/if}
			</section>
			</div>
		</div>

		{#if !agentOnline}
			<div class="banner banner-error">
				<strong>Agent 오프라인</strong> — 이 컨테이너를 보고 있는 agent 가 응답하지 않습니다. 실시간 메트릭·로그·콘솔이 모두 멈춰 있을 수 있습니다.
			</div>
		{:else if container.status !== 'running'}
			<div class="banner banner-warn">
				컨테이너가 현재 <strong>{statusLabel(container.status)}</strong> 상태입니다. 다시 실행되기 전까지 실시간 메트릭이 비어 있거나 오래된 값일 수 있습니다.
			</div>
		{/if}

		<div class="bento">
		<section class="panel bento-area area-charts">
			<div class="panel-header compact">
				<h2>성능 지표 추이<InfoTooltip text={timeSeriesHelp + '\n\n차트 위에 마우스를 올리면 모든 차트의 같은 시각이 함께 표시됩니다. 휠/드래그로 줌.'} placement="bottom-start" /></h2>
				<span class="sync-chip" title="4개 차트가 함께 hover · zoom · marker 동기화됩니다">
					<span class="sync-icon" aria-hidden="true">⤬</span> 동기화
				</span>
				<div class="range-tools">
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

			<div class="chart-grid">
				<div class="chart-card">
					<div class="chart-head">
						<h3>CPU 사용률</h3>
					</div>
					<UserMetricChart labels={historyLabels} datasets={cpuDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={percentChartMarkLines} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>메모리 사용률</h3>
					</div>
					<UserMetricChart labels={historyLabels} datasets={memoryDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={percentChartMarkLines} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>네트워크 트래픽</h3>
						<div class="mode-toggle" role="group" aria-label="누적/속도 전환">
							<button class:active={networkMode === 'cumulative'} onclick={() => (networkMode = 'cumulative')}>누적</button>
							<button class:active={networkMode === 'rate'} onclick={() => (networkMode = 'rate')}>속도</button>
						</div>
					</div>
					<UserMetricChart labels={historyLabels} datasets={networkDatasets} yFormat={networkFormat} group={chartGroup} enableZoom markLines={chartMarkLines} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>디스크 처리량</h3>
						<div class="mode-toggle" role="group" aria-label="누적/속도 전환">
							<button class:active={diskMode === 'cumulative'} onclick={() => (diskMode = 'cumulative')}>누적</button>
							<button class:active={diskMode === 'rate'} onclick={() => (diskMode = 'rate')}>속도</button>
						</div>
					</div>
					<UserMetricChart labels={historyLabels} datasets={diskDatasets} yFormat={diskFormat} group={chartGroup} enableZoom markLines={chartMarkLines} />
				</div>
				{#if hasGpuHistory || (currentGpuUsage !== null && currentGpuUsage !== undefined)}
					<div class="chart-card">
						<div class="chart-head">
							<h3>GPU 사용률</h3>
						</div>
						<UserMetricChart labels={historyLabels} datasets={gpuDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={percentChartMarkLines} />
					</div>
				{/if}
			</div>
		</section>

		<div class="bento-area area-logs">
			<LogTailPanel agentId={container.agent ?? ''} {containerId} />
		</div>

		<div class="bento-area area-process">
			<ProcessTopPanel {containerId} {paused} />
		</div>

		<div class="bento-area area-events">
			<EventList {events} errorMsg={eventsError} />
		</div>

		<div class="bento-area area-inspect">
			<InspectPanel data={inspectData} loading={inspectLoading} errorMsg={inspectError} />
		</div>

		<div class="bento-area area-console">
			<ConsolePanel agentId={container.agent ?? ''} {containerId} startOpen={true} />
		</div>
		</div>

		<details class="details-accordion">
			<summary>
				<span class="details-title">런타임 정보 · 요청 시 설정</span>
				<span class="details-hint">컨테이너 ID / 요청 출처 / 포트·환경 변수</span>
				<span class="details-chevron" aria-hidden="true">▾</span>
			</summary>
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
		</details>

		<ContainerLimitModal
			open={limitModalOpen}
			containerId={container.container_id}
			{inspectData}
			onclose={() => (limitModalOpen = false)}
			onsaved={() => {
				showActionMsg('자원 한도 수정 완료', 'success', 3500);
				loadInspect({ silent: true });
			}}
		/>

	{/if}
</div>

<style>
	.page {
		/* full width, 자연 스크롤. user-body 가 스크롤 컨테이너 (overflow-y:auto) 라
		   .page 는 height 강제 없이 콘텐츠 만큼 늘어남. padding 은 시원하게. */
		max-width: none;
		margin: 0;
		padding: clamp(14px, 1.2vw, 24px) clamp(14px, 1.4vw, 28px) clamp(20px, 2vw, 32px);
		display: flex;
		flex-direction: column;
		gap: clamp(10px, 0.9vw, 16px);
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
		margin-bottom: clamp(4px, 0.3vw, 8px);
		align-self: flex-start;
		text-align: left;
	}

	.back-link:hover {
		color: var(--accent);
	}

	.banner {
		padding: 16px 18px;
		border-radius: 14px;
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
		color: var(--text-secondary);
	}

	/* StateBox wrapper — page-level loading/error 상태를 가운데 정렬 */
	.state-wrap {
		display: flex;
		justify-content: center;
		padding: clamp(40px, 6vh, 80px) clamp(16px, 2vw, 32px);
	}

	/* topbar-sticky — unified-bar (hero + KPI + ops 한 row) 를 묶어 스크롤 시에도 상단 고정.
	   z-index 10 으로 차트 hover tooltip(보통 z 5~9) 위. 배경 var(--bg-base). */
	.topbar-sticky {
		position: sticky;
		top: 0;
		z-index: 10;
		background: var(--bg-base);
		padding: 4px 0 8px;
		margin: -4px 0 0;
		display: flex;
		flex-direction: column;
		gap: clamp(8px, 0.7vw, 14px);
	}

	/* 한 row 안에 [hero | KPI | ops]. 좁아지면 wrap.
	   각 영역 자기 자연 height (align-items: stretch — KPI 가 가장 키 큰 cell 기준
	   stretch — KPI 가 4 pill 풀폭 fit 하도록 우선). */
	.unified-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: stretch;
		gap: clamp(8px, 0.7vw, 14px);
	}

	.hero {
		display: flex;
		justify-content: space-between;
		gap: clamp(12px, 0.9vw, 18px);
		padding: clamp(14px, 1vw, 18px) clamp(16px, 1.1vw, 20px);
		padding-top: clamp(18px, 1.3vw, 22px);
		border-radius: 14px;
		background:
			radial-gradient(ellipse at top left, rgba(48, 213, 200, 0.18), transparent 65%),
			linear-gradient(135deg, rgba(48, 213, 200, 0.08), rgba(9, 75, 102, 0.12)),
			rgba(18, 23, 32, 0.98);
		border: 1px solid rgba(48, 213, 200, 0.22);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
		align-items: center;
		flex: 1.5 1 525px;
		min-width: 420px;
		max-width: 680px;
		position: relative;
		overflow: hidden;
	}
	.hero::before {
		content: '';
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 3px;
		background: linear-gradient(180deg, var(--accent), rgba(48, 213, 200, 0.2));
		opacity: 0.7;
	}

	/* CONTAINER caption — ops-bar 의 CONTROL 캡션과 미러링 */
	.hero-caption {
		position: absolute;
		top: 5px;
		left: 14px;
		font-size: 9px;
		font-weight: 800;
		letter-spacing: 0.12em;
		color: var(--accent);
		opacity: 0.7;
		pointer-events: none;
	}

	.hero-main {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-width: 0;
		flex: 1 1 auto;
	}

	.hero-titlebar {
		display: inline-flex;
		align-items: center;
		gap: clamp(10px, 0.8vw, 14px);
		flex-wrap: wrap;
	}

	h1 {
		font-size: clamp(20px, 1.5vw, 28px);
		line-height: 1.05;
		font-weight: 800;
		letter-spacing: -0.018em;
		color: var(--text-primary);
		text-shadow: 0 0 28px rgba(48, 213, 200, 0.22);
	}

	.hero-image {
		display: inline-flex;
		align-items: center;
		padding: 3px 10px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.6);
		border: 1px solid rgba(48, 213, 200, 0.2);
		font-size: 12px;
		color: rgba(48, 213, 200, 0.95);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		word-break: break-all;
	}

	.meta-chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 3px 9px;
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.55);
		border: 1px solid rgba(31, 41, 55, 0.85);
		font-size: 11px;
		color: var(--text-secondary);
		font-weight: 600;
	}

	.hero-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		align-items: center;
	}

	/* AgentStatusIndicator (자체 .agent-indicator 클래스) 는 본인 스타일 유지하고
	   기존 chip 형태의 메타 span 만 잡는다 (:not 으로 격리). insight-chip / mono-chip
	   도 자체 스타일 가지므로 제외. */
	.hero-meta > span:not(.agent-indicator):not(.agent-indicator *):not(.insight-chip):not(.mono-chip) {
		padding: 3px 8px;
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.52);
		border: 1px solid rgba(31, 41, 55, 0.8);
		font-size: 11px;
		color: var(--text-secondary);
	}

	/* mono-chip — container ID 같은 hash 정보를 monospace 로. */
	.mono-chip {
		padding: 3px 8px;
		border-radius: 999px;
		background: rgba(13, 17, 23, 0.52);
		border: 1px solid rgba(31, 41, 55, 0.8);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
		color: var(--text-muted);
	}

	/* 운영 인사이트 chip — 이상 신호만 시각 강조. severity 색 한눈에. */
	.insight-chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 3px 9px;
		border-radius: 999px;
		font-size: 11px;
		font-weight: 800;
		letter-spacing: 0.02em;
		cursor: help;
		user-select: none;
		white-space: nowrap;
	}
	.insight-chip.warn {
		background: rgba(251, 191, 36, 0.14);
		border: 1px solid rgba(251, 191, 36, 0.4);
		color: #fde68a;
	}
	.insight-chip.danger {
		background: rgba(239, 68, 68, 0.16);
		border: 1px solid rgba(239, 68, 68, 0.45);
		color: #fca5a5;
		animation: insight-pulse 1.8s ease-in-out infinite;
	}
	.insight-chip.ok {
		background: rgba(16, 185, 129, 0.12);
		border: 1px solid rgba(16, 185, 129, 0.38);
		color: #6ee7b7;
	}
	@keyframes insight-pulse {
		0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.2); }
		50% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
	}

	.status-pill {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 4px 12px 4px 10px;
		border-radius: 999px;
		font-size: 12px;
		font-weight: 800;
		letter-spacing: 0.02em;
		color: white;
		box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.06) inset;
	}
	.status-pill::before {
		content: '';
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: currentColor;
		box-shadow: 0 0 8px currentColor;
	}

	.hero-actions {
		display: flex;
		flex-direction: column;
		align-items: stretch;
		gap: 6px;
		flex-shrink: 0;
		padding-left: clamp(12px, 0.9vw, 16px);
		border-left: 1px solid rgba(48, 213, 200, 0.2);
		align-self: stretch;
		justify-content: center;
	}

	.refresh-btn,
	.pause-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 5px;
		padding: 7px 14px;
		min-width: 110px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.7);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-secondary);
		font-size: 11.5px;
		font-weight: 700;
		font-family: inherit;
		cursor: pointer;
		white-space: nowrap;
		transition: background-color var(--ease-fast), border-color var(--ease-fast), color var(--ease-fast);
	}

	.refresh-btn:hover:not(:disabled),
	.pause-btn:hover:not(.active) {
		background: rgba(48, 213, 200, 0.1);
		border-color: rgba(48, 213, 200, 0.35);
		color: var(--accent);
	}

	.pause-btn.active {
		background: rgba(239, 68, 68, 0.14);
		border-color: rgba(239, 68, 68, 0.4);
		color: #fca5a5;
	}

	.refresh-btn:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}

	.banner {
		margin-top: 14px;
	}
	.banner-warn {
		background: rgba(251, 191, 36, 0.1);
		border-color: rgba(251, 191, 36, 0.32);
		color: #fde68a;
	}
	.banner-error {
		background: rgba(239, 68, 68, 0.12);
		border-color: rgba(239, 68, 68, 0.36);
		color: #fca5a5;
	}

	/* unified-bar 안에서 KPI 는 중간 1fr — 가능한 wide. KPI bar 컴포넌트가 자체적으로
	   auto-fit grid 라 4 pill 자동 분배. */
	.kpi-row {
		flex: 1 1 0;
		min-width: 320px;
		display: flex;
		align-items: stretch;
	}
	.kpi-row :global(.kpi-bar) {
		margin-top: 0;
		width: 100%;
	}

	/* ops-bar — unified-bar 우측. lifecycle 컨트롤 + 설정(한도수정) 두 그룹.
	   caption 라벨이 좌측 상단, 메인 영역은 단순 row. */
	.ops-bar {
		margin-top: 0;
		padding: clamp(10px, 0.8vw, 14px) clamp(12px, 0.9vw, 16px);
		padding-top: clamp(14px, 1vw, 18px);
		border-radius: 14px;
		background:
			linear-gradient(180deg, rgba(13, 17, 23, 0.55), rgba(18, 23, 32, 0.98)),
			rgba(18, 23, 32, 0.98);
		border: 1px solid var(--border);
		display: flex;
		flex-wrap: nowrap;
		align-items: center;
		gap: clamp(10px, 0.8vw, 14px);
		flex: 1 1 380px;
		min-width: 320px;
		max-width: 580px;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
		position: relative;
		overflow: hidden;
	}

	/* CONTROL caption — ops-bar 상단 좌측 작은 라벨 (overlay) */
	.ops-caption {
		position: absolute;
		top: 5px;
		left: 12px;
		font-size: 9px;
		font-weight: 800;
		letter-spacing: 0.12em;
		color: var(--accent);
		opacity: 0.7;
		pointer-events: none;
	}

	/* 좌측 상태 시각화 — orb (status color + pulse) + 텍스트 (상태명 + uptime/PID) */
	.ops-status {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-shrink: 0;
	}
	.status-orb {
		position: relative;
		width: 38px;
		height: 38px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	.orb-core {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--orb-color, #6b7280);
		box-shadow:
			0 0 0 4px rgba(255, 255, 255, 0.03),
			0 0 16px var(--orb-glow, rgba(107, 114, 128, 0.5));
		z-index: 1;
	}
	.orb-pulse {
		position: absolute;
		inset: 0;
		border-radius: 50%;
		background: var(--orb-color, transparent);
		opacity: 0.18;
		animation: orb-ping 2.2s ease-out infinite;
	}
	@keyframes orb-ping {
		0%   { transform: scale(0.6); opacity: 0.32; }
		70%  { transform: scale(1.2); opacity: 0;    }
		100% { transform: scale(1.2); opacity: 0;    }
	}
	/* status 별 색상 — orb 와 pulse 컬러 */
	.ops-status[data-status='running']    { --orb-color: #10b981; --orb-glow: rgba(16, 185, 129, 0.55); }
	.ops-status[data-status='paused']     { --orb-color: #fbbf24; --orb-glow: rgba(251, 191, 36, 0.55); }
	.ops-status[data-status='restarting'] { --orb-color: #60a5fa; --orb-glow: rgba(96, 165, 250, 0.55); }
	.ops-status[data-status='stopped'],
	.ops-status[data-status='exited'],
	.ops-status[data-status='dead']       { --orb-color: #ef4444; --orb-glow: rgba(239, 68, 68, 0.5); }
	.ops-status[data-status='created']    { --orb-color: #9ca3af; --orb-glow: rgba(156, 163, 175, 0.4); }
	/* paused 는 pulse 꺼서 시각적 정지감 */
	.ops-status[data-status='paused'] .orb-pulse,
	.ops-status[data-status='stopped'] .orb-pulse,
	.ops-status[data-status='exited'] .orb-pulse,
	.ops-status[data-status='dead'] .orb-pulse,
	.ops-status[data-status='created'] .orb-pulse { animation: none; opacity: 0; }

	.status-text {
		display: flex;
		flex-direction: column;
		gap: 1px;
		min-width: 0;
	}
	.status-name {
		font-size: 13px;
		font-weight: 800;
		color: var(--text-primary);
		letter-spacing: -0.005em;
		line-height: 1.1;
	}
	.status-meta {
		font-size: 10.5px;
		color: var(--text-muted);
		font-weight: 600;
		white-space: nowrap;
		line-height: 1.2;
	}

	.ops-divider {
		width: 1px;
		align-self: stretch;
		background: linear-gradient(180deg, transparent, rgba(48, 213, 200, 0.2), transparent);
		flex-shrink: 0;
		margin: 4px 0;
	}

	/* 우측 액션 영역 — ContainerActions + limit icon btn */
	.ops-actions {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: 1 1 auto;
		min-width: 0;
		justify-content: flex-end;
	}

	/* 한도수정 icon-only — secondary action 으로 visual weight 줄임 */
	.limit-icon-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		padding: 0;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.6);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-muted);
		font-family: inherit;
		font-size: 15px;
		cursor: pointer;
		flex-shrink: 0;
		transition: background-color var(--ease-fast), border-color var(--ease-fast), color var(--ease-fast);
	}
	.limit-icon-btn:hover:not(:disabled) {
		background: rgba(48, 213, 200, 0.14);
		border-color: rgba(48, 213, 200, 0.42);
		color: var(--accent);
	}
	.limit-icon-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.ops-left {
		display: flex;
		align-items: stretch;
		gap: clamp(4px, 0.35vw, 8px);
		flex-wrap: nowrap;
		flex: 1 1 auto;
		min-width: 0;
	}

	/* limit-btn — 설정 변경. lifecycle 그룹 박스와 동일 높이 유지. */
	.limit-btn {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 4px 9px;
		min-height: 54px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.7);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-secondary);
		font-family: inherit;
		font-size: 10.5px;
		font-weight: 700;
		cursor: pointer;
		white-space: nowrap;
		transition: background-color var(--ease-fast), border-color var(--ease-fast), color var(--ease-fast);
	}
	.limit-btn:hover:not(:disabled) {
		background: rgba(48, 213, 200, 0.12);
		border-color: rgba(48, 213, 200, 0.42);
		color: var(--accent);
	}
	.limit-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.ops-label {
		display: inline-flex;
		align-items: center;
		padding: 3px 7px;
		border-radius: 5px;
		background: rgba(48, 213, 200, 0.08);
		border: 1px solid rgba(48, 213, 200, 0.22);
		color: var(--accent);
		font-size: 9px;
		font-weight: 800;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		flex-shrink: 0;
	}

	.ops-msg {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
		font-weight: 700;
		padding: 6px 8px 6px 10px;
		border-radius: 8px;
		background: rgba(48, 213, 200, 0.1);
		border: 1px solid rgba(48, 213, 200, 0.3);
		color: var(--accent);
		max-width: 100%;
	}
	.ops-msg[data-kind='success'] {
		background: rgba(16, 185, 129, 0.14);
		border-color: rgba(16, 185, 129, 0.35);
		color: #34d399;
	}
	.ops-msg[data-kind='error'] {
		background: var(--state-error-bg);
		border-color: var(--state-error-border);
		color: var(--state-error-text);
	}
	.ops-msg-icon {
		font-size: 13px;
		line-height: 1;
	}
	.ops-msg-text {
		font-weight: 600;
	}
	.ops-msg-close {
		all: unset;
		cursor: pointer;
		padding: 2px 6px;
		font-size: 11px;
		font-weight: 800;
		color: inherit;
		opacity: 0.55;
		border-radius: 4px;
		transition: opacity var(--ease-fast), background-color var(--ease-fast);
	}
	.ops-msg-close:hover {
		opacity: 1;
		background: rgba(255, 255, 255, 0.08);
	}
	.ops-msg-close:focus-visible {
		outline: 2px solid currentColor;
		outline-offset: 2px;
	}

	.panel,
	.chart-card,
	.config-card {
		background: rgba(18, 23, 32, 0.96);
		border: 1px solid var(--border);
	}

	/* 12-col bento grid — 1440+: row1 charts(8) + logs(4), row2 process(5) + events(3) + inspect(4),
	   row3 console(12, full-width).
	   1280~1439: 차트/로그/하단 3분할/console 각각 1행씩 stack.
	   ≤980: 1열 stack (모바일 fallback).

	   row 는 자연 height (auto) — 각 cell 콘텐츠에 맞춰 늘어나고, grid 가 같은 row 내
	   cell 들을 가장 큰 cell 에 맞춰 stretch 시킨다. viewport-fit 강제 X. */
	.bento {
		display: grid;
		grid-template-columns: repeat(12, minmax(0, 1fr));
		grid-template-rows: auto auto auto;
		grid-template-areas:
			"charts charts charts charts charts charts charts charts logs logs logs logs"
			"process process process process events events events console console console console console"
			"inspect inspect inspect inspect inspect inspect inspect inspect inspect inspect inspect inspect";
		gap: clamp(10px, 0.9vw, 16px);
		margin-top: 0;
	}
	.bento-area {
		min-width: 0;
	}
	.area-charts {
		grid-area: charts;
	}
	.area-logs {
		grid-area: logs;
	}
	.area-process {
		grid-area: process;
	}
	.area-events {
		grid-area: events;
	}
	.area-inspect {
		grid-area: inspect;
	}
	.area-console {
		grid-area: console;
	}

	/* bento 안의 component panel 들은 grid item 자신이 자리 잡으므로 컴포넌트 내부의
	   margin-top 을 무력화 (관리자 일관성: 카드 간격은 grid gap 이 담당). */
	.bento :global(.panel) {
		margin-top: 0;
	}
	/* 차트 panel 도 bento 내부 grid item 으로 동작 — margin-top 제거. */
	.bento .panel {
		margin-top: 0;
	}

	/* 각 bento area 의 inner panel 은 자기 자연 height. grid row 가 가장 큰 cell
	   기준으로 stretch 되므로 panel 자체 stretch 는 height:100% 로 단순 처리.
	   (예전 flex:1 1 0 + min-height:0 패턴은 viewport-fit 강제 시 사용 — 자연
	   스크롤 환경에서는 panel 을 0 으로 collapse 시켜서 제거.) */
	.bento-area {
		display: flex;
		flex-direction: column;
	}
	.bento-area > :global(.panel) {
		width: 100%;
		height: 100%;
		margin-top: 0;
	}

	.panel {
		border-radius: var(--radius-panel, 14px);
		padding: clamp(16px, 1.2vw, 22px);
		margin-top: 14px;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: clamp(8px, 0.7vw, 14px);
		margin-bottom: clamp(8px, 0.6vw, 14px);
	}

	.panel-header.slim {
		margin-bottom: clamp(3px, 0.3vw, 8px);
	}

	/* compact = 차트 panel 처럼 dense workbench 헤더. 부제·hint 없이
	   h2 + 우측 range tabs 한 줄로. */
	.panel-header.compact {
		align-items: center;
		margin-bottom: 10px;
	}

	h2 {
		font-size: clamp(15px, 1.15vw, 19px);
		margin-bottom: 4px;
		font-weight: 700;
		letter-spacing: -0.005em;
	}

	.panel-header.compact h2 {
		margin-bottom: 0;
		font-size: clamp(12px, 0.9vw, 14px);
		font-weight: 800;
		letter-spacing: 0.02em;
		text-transform: uppercase;
		color: var(--text-secondary);
	}

	h2 + p,
	.panel-header p {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.sync-chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		margin-right: auto;
		padding: 3px 9px;
		border-radius: var(--radius-full);
		background: rgba(48, 213, 200, 0.1);
		border: 1px solid rgba(48, 213, 200, 0.28);
		color: var(--accent);
		font-size: 10px;
		font-weight: 800;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		cursor: help;
		user-select: none;
	}
	.sync-icon {
		font-size: 11px;
		line-height: 1;
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
		gap: 3px;
		flex-wrap: wrap;
		padding: 2px;
		background: rgba(13, 17, 23, 0.5);
		border: 1px solid rgba(31, 41, 55, 0.6);
		border-radius: 8px;
	}

	.range-btn {
		padding: 4px 10px;
		border-radius: 6px;
		background: transparent;
		color: var(--text-secondary);
		font-size: 11px;
		font-weight: 700;
		transition: background-color var(--ease-fast), color var(--ease-fast);
	}

	.range-btn:hover:not(.active) {
		background: rgba(48, 213, 200, 0.08);
		color: var(--text-primary);
	}

	.range-btn.active {
		background: rgba(48, 213, 200, 0.22);
		color: var(--accent);
		box-shadow: 0 0 0 1px rgba(48, 213, 200, 0.35) inset;
	}

	.chart-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		grid-template-rows: repeat(2, minmax(300px, 1fr));
		gap: clamp(10px, 0.8vw, 16px);
		flex: 1 1 auto;
		min-height: 0;
	}

	/* area-charts panel 자체가 flex column → chart-grid 가 자연 height 채움 */
	.area-charts {
		display: flex;
		flex-direction: column;
	}

	.chart-card {
		border-radius: var(--radius-panel);
		padding: clamp(10px, 0.8vw, 14px) clamp(12px, 0.9vw, 16px);
		transition: border-color var(--ease-fast);
		display: flex;
		flex-direction: column;
		min-height: 300px;
	}
	.chart-card:hover {
		border-color: rgba(48, 213, 200, 0.22);
	}

	.chart-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: clamp(6px, 0.6vw, 12px);
		margin-bottom: clamp(6px, 0.5vw, 10px);
		padding-bottom: clamp(5px, 0.4vw, 8px);
		border-bottom: 1px solid rgba(100, 116, 139, 0.14);
	}

	.chart-head h3 {
		font-size: clamp(13px, 0.95vw, 16px);
		font-weight: 700;
	}

	.chart-head span {
		font-size: 12px;
		color: var(--text-secondary);
	}

	.chart-head-right {
		display: inline-flex;
		align-items: center;
		gap: 12px;
	}

	.mode-toggle {
		display: inline-flex;
		gap: 0;
		border: 1px solid rgba(31, 41, 55, 0.9);
		border-radius: 8px;
		overflow: hidden;
	}

	.mode-toggle button {
		padding: 3px 9px;
		background: rgba(13, 17, 23, 0.86);
		border: none;
		color: var(--text-muted);
		font-family: inherit;
		font-size: 10px;
		font-weight: 700;
		cursor: pointer;
		transition: background-color var(--ease-fast), color var(--ease-fast);
	}

	.mode-toggle button:hover:not(.active) {
		background: rgba(48, 213, 200, 0.06);
		color: var(--text-primary);
	}

	.mode-toggle button + button {
		border-left: 1px solid rgba(31, 41, 55, 0.9);
	}

	.mode-toggle button.active {
		background: rgba(48, 213, 200, 0.22);
		color: var(--accent);
	}

	.details-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
		gap: clamp(10px, 0.8vw, 18px);
		margin-top: clamp(8px, 0.6vw, 14px);
	}

	/* 런타임/요청 설정 accordion — 기본 닫힘 (사용자가 펼쳐서 본다).
	   자연 스크롤 환경이라 모든 viewport 에서 표시. */
	.details-accordion {
		margin-top: clamp(8px, 0.6vw, 14px);
		border: 1px solid var(--border);
		border-radius: var(--radius-panel);
		background: rgba(18, 23, 32, 0.96);
		overflow: hidden;
	}
	.details-accordion > summary {
		list-style: none;
		cursor: pointer;
		padding: clamp(8px, 0.6vw, 12px) clamp(12px, 1vw, 18px);
		display: flex;
		align-items: center;
		gap: 10px;
		user-select: none;
		font-size: 12px;
		transition: background-color var(--ease-fast);
	}
	.details-accordion > summary::-webkit-details-marker { display: none; }
	.details-accordion > summary:hover {
		background: rgba(48, 213, 200, 0.06);
	}
	.details-title {
		font-weight: 800;
		color: var(--text-primary);
	}
	.details-hint {
		font-size: 11px;
		color: var(--text-muted);
	}
	.details-chevron {
		margin-left: auto;
		font-size: 14px;
		color: var(--text-secondary);
		transition: transform var(--ease-fast);
	}
	.details-accordion[open] > summary > .details-chevron {
		transform: rotate(180deg);
	}
	.details-accordion[open] > summary {
		border-bottom: 1px solid var(--border);
	}
	.details-accordion > .details-grid {
		padding: clamp(10px, 0.8vw, 16px);
		margin-top: 0;
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

	/* 1280~1439: 차트 풀폭 → 로그 풀폭 → 하단 process/events/console 가로 3분할 → inspect 풀폭 */
	@media (max-width: 1439px) {
		.bento {
			grid-template-areas:
				"charts charts charts charts charts charts charts charts charts charts charts charts"
				"logs logs logs logs logs logs logs logs logs logs logs logs"
				"process process process process events events events console console console console console"
				"inspect inspect inspect inspect inspect inspect inspect inspect inspect inspect inspect inspect";
		}
	}

	/* ≤980: 1열 stack (모바일) */
	@media (max-width: 980px) {
		.page {
			padding: 14px 12px 24px;
		}

		.hero,
		.panel-header,
		.chart-head,
		.env-row {
			flex-direction: column;
			align-items: stretch;
		}

		.bento {
			grid-template-columns: 1fr;
			grid-template-areas:
				'charts'
				'logs'
				'process'
				'events'
				'console'
				'inspect';
		}

		.chart-grid,
		.details-grid,
		.info-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
