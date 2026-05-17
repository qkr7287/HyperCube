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
		formatRelativeTime,
		statusLabel,
		statusTone,
	} from '$lib/utils/container-dashboard';

	const cpuHelp = `이 컨테이너가 실제로 사용 중인 CPU 사용률(%)입니다.

여러 코어 환경이라도 0~100% 범위로 정규화돼 표시되므로, 100%에 가까울수록 컨테이너가 받은 CPU를 모두 쓰고 있다는 뜻입니다.

값은 선택한 자동 새로고침 주기에 맞춰 갱신됩니다.`;

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
		allocated_gpu_slice_ids?: (string | number)[];
		cpu_percent_limit?: number | null;
		memory_mb_limit?: number | null;
		workspace_gb_limit?: number | null;
		workspace_device?: string | null;
	};

	type MetricsSnapshot = {
		timestamp?: string | null;
		containerId?: string;
		cpu?: { usage?: number };
		memory?: { usage?: number; limit?: number; percent?: number };
		network?: { rx?: number; tx?: number };
		disk?: { read?: number; write?: number };
		workspace?: {
			path?: string;
			device?: string;
			projectId?: number;
			hardGb?: number;
			sizeGb?: number;
			usedGb?: number;
			availableGb?: number;
			usedPct?: number;
		} | null;
		gpu?:
			| Array<{ usage?: number | null; memoryUsed?: number | null; memoryTotal?: number | null }>
			| { usage?: number | null; memoryUsed?: number | null; memoryTotal?: number | null }
			| null;
	};

	type MetricsHistoryRow = {
		recorded_at: string;
		cpu_usage: number;
		cpu_usage_max: number;
		memory_usage: number;
		memory_limit: number;
		memory_percent: number;
		memory_percent_max: number;
		network_rx: number;
		network_tx: number;
		disk_read: number;
		disk_write: number;
		gpu_usage: number | null;
		gpu_usage_max: number | null;
		gpu_memory_used?: number | null;
		gpu_memory_used_max?: number | null;
		gpu_memory_total?: number | null;
		gpu_memory_total_max?: number | null;
	};

	const RANGE_OPTIONS = [
		{ key: '30s', label: '30초' },
		{ key: '1m', label: '1분' },
		{ key: '5m', label: '5분' },
		{ key: '1h', label: '1시간' },
		{ key: '24h', label: '24시간' },
	] as const;

	// range = 데이터 sample 간격(bucket). window는 그 단위에 맞게 적당한 양으로 자동.
	const RANGE_BUCKET_MAP: Record<(typeof RANGE_OPTIONS)[number]['key'], { window: string; bucket: string }> = {
		'30s': { window: '5m', bucket: '30s' },
		'1m': { window: '1h', bucket: '1m' },
		'5m': { window: '6h', bucket: '5m' },
		'1h': { window: '24h', bucket: '1h' },
		'24h': { window: '7d', bucket: '1d' },
	};

	// 자동 새로고침 주기 — 차트 range 옵션과 같은 label set 으로 sync.
	const REFRESH_INTERVAL_OPTIONS = [
		{ value: 30_000, label: '30초' },
		{ value: 60_000, label: '1분' },
		{ value: 300_000, label: '5분' },
		{ value: 3_600_000, label: '1시간' },
		{ value: 86_400_000, label: '24시간' },
	] as const;

	let container = $state<ContainerDetail | null>(null);
	let currentMetrics = $state<MetricsSnapshot | null>(null);
	let history = $state<MetricsHistoryRow[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let errorMsg = $state('');
	let selectedRange = $state<(typeof RANGE_OPTIONS)[number]['key']>('1h');
	let refreshIntervalMs = $state(60_000);
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
	// 마지막 동기화 신선도 — meta-chip 색상 분기용. 30초 이내 fresh, 2분 이내 default,
	// 그 이상이면 stale 색으로 운영자가 즉시 인지하도록.
	let syncFreshness = $derived.by<'fresh' | 'ok' | 'stale' | 'cold'>(() => {
		const iso = currentMetrics?.timestamp || container?.last_seen;
		if (!iso) return 'cold';
		const ts = new Date(iso).getTime();
		if (!Number.isFinite(ts)) return 'cold';
		const ageSec = (Date.now() - ts) / 1000;
		if (ageSec < 30) return 'fresh';
		if (ageSec < 120) return 'ok';
		if (ageSec < 600) return 'stale';
		return 'cold';
	});
	let runtimeRestartCount = $derived(Number(inspectData?.restartCount ?? 0));
	// healthcheck 정의된 컨테이너 → Healthy/Unhealthy/Starting.
	// healthcheck 없으면 status pill 과 단어 중복("실행 중") 을 피해 더 운영적 문구로.
	let runtimeHealthText = $derived.by<string>(() => {
		if (isOomKilled) return 'OOM Killed';
		if (healthStatus === 'healthy') return 'Healthy';
		if (healthStatus === 'unhealthy') return 'Unhealthy';
		if (healthStatus === 'starting') return 'Starting';
		if (inspectData?.state?.dead) return '종료';
		if (inspectData?.state?.paused) return '일시정지';
		if (inspectData?.state?.restarting) return '재시작 중';
		if (inspectData?.state?.running) return '정상';
		return inspectData?.state?.status || '정보 없음';
	});
	// healthcheck 가 정의되어 있을 때만 "Health" 라벨, 아니면 "런타임" 으로 분리.
	let runtimeHealthLabel = $derived<string>(healthStatus ? 'Health' : '런타임');
	let runtimeHealthTone = $derived.by<string>(() => {
		if (isOomKilled || healthStatus === 'unhealthy' || inspectData?.state?.dead) return 'danger';
		if (healthStatus === 'starting' || inspectData?.state?.restarting || inspectData?.state?.paused) return 'warn';
		if (healthStatus === 'healthy' || inspectData?.state?.running) return 'success';
		return 'muted';
	});
	let runtimeExitText = $derived.by<string>(() => {
		const code = inspectData?.state?.exitCode;
		if (typeof code === 'number') return code === 0 ? '정상 종료' : `Exit ${code}`;
		if (lastExit && typeof lastExit.exit_code === 'number') return `Exit ${lastExit.exit_code}`;
		return '기록 없음';
	});
	let runtimeOomText = $derived(isOomKilled ? '발생' : '없음');
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
	// 누적 metric (network/disk) 차트 모드. cumulative = 원본, rate = bucket 간 delta/sec.
	let networkMode = $state<'cumulative' | 'rate'>('cumulative');
	let diskMode = $state<'cumulative' | 'rate'>('cumulative');
	// API 응답에 포함된 bucket 폭 (초) — rate 계산에 사용. fallback 으로 RANGE 매핑.
	let bucketSeconds = $state<number>(60);

	let containerId = $derived($page.params.containerId ?? '');

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
			const err: Error & { status?: number } = new Error(
				json?.error?.detail || json?.detail || `HTTP ${response.status}`,
			);
			err.status = response.status;
			throw err;
		}
		return json.data as T;
	}

	// inspect 폴링 backoff (loadInspect 전용). agent_offline 503 가 길어질 때
	// 매 refresh tick 마다 또 503 을 받지 않게 lockout 시간을 둔다.
	const INSPECT_BACKOFF_THRESHOLD = 3;
	const INSPECT_BACKOFF_BASE_MS = 30_000;
	const INSPECT_BACKOFF_MAX_MS = 300_000;
	let inspect5xx = 0;
	let inspectBackoffUntil = 0;

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
				cpu_usage_max: snapshot.cpu?.usage ?? 0,
				memory_usage: snapshot.memory?.usage ?? 0,
				memory_limit: snapshot.memory?.limit ?? 0,
				memory_percent: snapshot.memory?.percent ?? 0,
				memory_percent_max: snapshot.memory?.percent ?? 0,
				network_rx: snapshot.network?.rx ?? 0,
				network_tx: snapshot.network?.tx ?? 0,
				disk_read: snapshot.disk?.read ?? 0,
				disk_write: snapshot.disk?.write ?? 0,
				gpu_usage: snapshotGpu(snapshot),
				gpu_usage_max: snapshotGpu(snapshot),
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
		// silent polling 은 5xx 연속 시 backoff window 동안 호출 자체를 skip.
		if (silent && inspectBackoffUntil > Date.now()) return;
		const showLoading = !silent || !inspectData;
		if (showLoading) {
			inspectLoading = true;
			inspectError = '';
		}
		try {
			inspectData = await api<any>(`/api/my-containers/${containerId}/inspect/`);
			// 성공 시는 silent 라도 stale error chip 은 지워준다.
			if (inspectError) inspectError = '';
			inspect5xx = 0;
			inspectBackoffUntil = 0;
		} catch (err: any) {
			if (err?.status >= 500) {
				inspect5xx += 1;
				if (inspect5xx >= INSPECT_BACKOFF_THRESHOLD) {
					const step = inspect5xx - INSPECT_BACKOFF_THRESHOLD;
					const delay = Math.min(INSPECT_BACKOFF_MAX_MS, INSPECT_BACKOFF_BASE_MS * 2 ** step);
					inspectBackoffUntil = Date.now() + delay;
				}
			} else {
				inspect5xx = 0;
				inspectBackoffUntil = 0;
			}
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
			cpu_usage_max: Number(r.cpu_max ?? r.cpu_avg ?? 0),
			memory_usage: Number(r.memory_avg ?? 0),
			memory_limit: 0,
			memory_percent: Number(r.memory_percent_avg ?? 0),
			memory_percent_max: Number(r.memory_percent_max ?? r.memory_percent_avg ?? 0),
			network_rx: Number(r.network_rx_max ?? 0),
			network_tx: Number(r.network_tx_max ?? 0),
			disk_read: Number(r.disk_read_max ?? 0),
			disk_write: Number(r.disk_write_max ?? 0),
			gpu_usage: r.gpu_usage_avg !== undefined && r.gpu_usage_avg !== null ? Number(r.gpu_usage_avg) : null,
			gpu_usage_max: r.gpu_usage_max !== undefined && r.gpu_usage_max !== null ? Number(r.gpu_usage_max) : null,
			gpu_memory_used: r.gpu_memory_used_avg !== undefined && r.gpu_memory_used_avg !== null ? Number(r.gpu_memory_used_avg) : (r.gpu_memory_used_max !== undefined && r.gpu_memory_used_max !== null ? Number(r.gpu_memory_used_max) : null),
			gpu_memory_used_max: r.gpu_memory_used_max !== undefined && r.gpu_memory_used_max !== null ? Number(r.gpu_memory_used_max) : null,
			gpu_memory_total: r.gpu_memory_total_avg !== undefined && r.gpu_memory_total_avg !== null ? Number(r.gpu_memory_total_avg) : (r.gpu_memory_total_max !== undefined && r.gpu_memory_total_max !== null ? Number(r.gpu_memory_total_max) : null),
			gpu_memory_total_max: r.gpu_memory_total_max !== undefined && r.gpu_memory_total_max !== null ? Number(r.gpu_memory_total_max) : null,
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

	function refreshIntervalLabel(ms = refreshIntervalMs): string {
		return REFRESH_INTERVAL_OPTIONS.find((option) => option.value === ms)?.label ?? `${Math.round(ms / 1000)}초`;
	}

	function startRefreshTimer() {
		if (refreshTimer) clearInterval(refreshTimer);
		refreshTimer = setInterval(() => {
			if (!paused) loadDashboard();
		}, refreshIntervalMs);
	}

	// 두 selector 가 같은 label set 을 공유하므로, 한쪽이 바뀌면 다른 쪽도
	// 같은 시간 단위로 sync 해서 UI 가 어긋나 보이지 않게 한다.
	const RANGE_KEY_TO_MS: Record<(typeof RANGE_OPTIONS)[number]['key'], number> = {
		'30s': 30_000,
		'1m': 60_000,
		'5m': 300_000,
		'1h': 3_600_000,
		'24h': 86_400_000,
	};
	const MS_TO_RANGE_KEY = Object.fromEntries(
		Object.entries(RANGE_KEY_TO_MS).map(([k, v]) => [v, k]),
	) as Record<number, (typeof RANGE_OPTIONS)[number]['key']>;

	function handleRefreshIntervalChange(event: Event) {
		const next = Number((event.currentTarget as HTMLSelectElement).value);
		if (!Number.isFinite(next) || next <= 0) return;
		refreshIntervalMs = next;
		startRefreshTimer();
		const matchKey = MS_TO_RANGE_KEY[next];
		if (matchKey && selectedRange !== matchKey) {
			selectedRange = matchKey;
			loadDashboard();
		}
	}

	function handleRangeChange(rangeKey: (typeof RANGE_OPTIONS)[number]['key']) {
		selectedRange = rangeKey;
		const matchMs = RANGE_KEY_TO_MS[rangeKey];
		if (matchMs && refreshIntervalMs !== matchMs) {
			refreshIntervalMs = matchMs;
			startRefreshTimer();
		}
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

	function pad2(value: number): string {
		return String(value).padStart(2, '0');
	}

	function localDateKey(date: Date): string {
		return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
	}

	function formatHistoryTime(value: string, includeDate: boolean): string {
		const date = new Date(value);
		if (Number.isNaN(date.getTime())) return '';
		const time = `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
		if (!includeDate) return time;
		return `${pad2(date.getMonth() + 1)}/${pad2(date.getDate())} ${time}`;
	}

	function shouldShowDateOnAxis(rows: MetricsHistoryRow[]): boolean {
		if (rows.length === 0) return false;
		if (selectedRange === '24h') return true;

		const first = new Date(rows[0].recorded_at);
		const last = new Date(rows[rows.length - 1].recorded_at);
		if (Number.isNaN(first.getTime()) || Number.isNaN(last.getTime())) return false;
		return localDateKey(first) !== localDateKey(last);
	}

	let envEntries = $derived(Object.entries(container?.custom_env ?? {}));
	let portMappings = $derived(container?.custom_ports ?? []);
	let hasRequestConfig = $derived(portMappings.length > 0 || envEntries.length > 0);
	let requestConfigMode = $derived(hasRequestConfig ? '사용자 지정' : '기본값');
	let requestConfigSource = $derived(
		container?.template_name || container?.selected_image || container?.image || '요청 이미지',
	);
	let rangeLabel = $derived(RANGE_OPTIONS.find((o) => o.key === selectedRange)?.label ?? '');
	let chartGroup = $derived(`hc-container-${containerId}`);
	let cpuQuotaCores = $derived(container?.cpu_percent_limit ? container.cpu_percent_limit / 100 : null);
	let cpuAxisLabel = $derived(cpuQuotaCores ? `CPU % (of ${formatCoreLimit(cpuQuotaCores)} quota)` : 'CPU % (of host 전체)');
	let cpuDenominatorText = $derived(
		cpuQuotaCores
			? `분모: cpu_quota = ${container?.cpu_percent_limit} (= ${formatCoreLimit(cpuQuotaCores)})`
			: '분모: host 전체',
	);
	let memoryQuotaGb = $derived(container?.memory_mb_limit ? container.memory_mb_limit / 1024 : null);
	let memoryAxisLabel = $derived(memoryQuotaGb ? `Memory % (of ${formatGb(memoryQuotaGb)} GB quota)` : 'Memory % (of host 전체)');
	let memoryDenominatorText = $derived(memoryQuotaGb ? `분모: memory_limit = ${formatGb(memoryQuotaGb)} GB` : '분모: host 전체');

	function formatCoreLimit(value: number): string {
		return Number.isInteger(value) ? `${value} cores` : `${value.toFixed(1)} cores`;
	}

	function formatGb(value: number): string {
		return Number.isInteger(value) ? String(value) : value.toFixed(1);
	}

	function maskEnvValue(value: string): string {
		if (!value) return '-';
		return `•••• ${value.length}자`;
	}

	let cpuAvg = $derived(avgOf(history.map((r) => r.cpu_usage)));
	let cpuPeak = $derived(peakOf(history.map((r) => r.cpu_usage_max)));
	let memAvgPct = $derived(avgOf(history.map((r) => r.memory_percent)));
	let memPeakPct = $derived(peakOf(history.map((r) => r.memory_percent_max)));
	let netRxDelta = $derived(deltaOf(history.map((r) => r.network_rx)));
	let netTxDelta = $derived(deltaOf(history.map((r) => r.network_tx)));
	let diskReadDelta = $derived(deltaOf(history.map((r) => r.disk_read)));
	let diskWriteDelta = $derived(deltaOf(history.map((r) => r.disk_write)));
	let gpuValid = $derived(
		history
			.filter((r) => typeof r.gpu_usage === 'number')
			.map((r) => r.gpu_usage as number),
	);
	let gpuMaxValid = $derived(
		history
			.filter((r) => typeof r.gpu_usage_max === 'number')
			.map((r) => r.gpu_usage_max as number),
	);
	let gpuAvg = $derived(avgOf(gpuValid));
	let gpuPeak = $derived(peakOf(gpuMaxValid.length > 0 ? gpuMaxValid : gpuValid));
	let gpuMemPctSeries = $derived(
		history.map((r) => {
			const u = Number(r.gpu_memory_used ?? 0);
			const t = Number(r.gpu_memory_total ?? 0);
			return t > 0 ? (u / t) * 100 : 0;
		}),
	);
	let gpuMemPctMaxSeries = $derived(
		history.map((r) => {
			const u = Number(r.gpu_memory_used_max ?? r.gpu_memory_used ?? 0);
			const t = Number(r.gpu_memory_total_max ?? r.gpu_memory_total ?? 0);
			return t > 0 ? (u / t) * 100 : 0;
		}),
	);
	let gpuMemValid = $derived(gpuMemPctSeries.filter((v) => v > 0));
	let gpuMemMaxValid = $derived(gpuMemPctMaxSeries.filter((v) => v > 0));
	let gpuMemAvg = $derived(avgOf(gpuMemValid));
	let gpuMemPeak = $derived(peakOf(gpuMemMaxValid.length > 0 ? gpuMemMaxValid : gpuMemValid));
	let currentGpuMemPct = $derived.by(() => {
		const last = gpuMemPctSeries.length ? gpuMemPctSeries[gpuMemPctSeries.length - 1] : 0;
		return last > 0 ? last : null;
	});
	let hasGpuAllocated = $derived((container?.allocated_gpu_slice_ids?.length ?? 0) > 0);
	let hasGpuMemHistory = $derived(hasGpuAllocated || gpuMemValid.length > 0);
	let historyShowsDateOnAxis = $derived(shouldShowDateOnAxis(history));
	let historyLabels = $derived(
		history.map((row) => formatHistoryTime(row.recorded_at, historyShowsDateOnAxis)),
	);
	let historyTooltipLabels = $derived(
		history.map((row) => formatHistoryTime(row.recorded_at, true)),
	);

	// 본문 차트는 dual series:
	//   1) main = bucket 평균 (부드러운 평균 부하 trend)
	//   2) max = bucket 최댓값 (짧은 spike 시각화) — 옅은 색, dashed
	// 둘 다 같은 bucket 단위라 spike 와 trend 를 동시에 비교 가능.
	let cpuDatasets = $derived([
		{
			label: 'CPU 평균',
			color: '#30d5c8',
			values: history.map((row) => row.cpu_usage),
			fill: true,
			format: 'percent' as const,
		},
		{
			label: 'CPU 최댓값',
			color: '#30d5c8',
			values: history.map((row) => row.cpu_usage_max),
			fill: false,
			dashed: true,
			format: 'percent' as const,
		},
	]);
	let memoryDatasets = $derived([
		{
			label: '메모리 평균',
			color: '#4fc3f7',
			values: history.map((row) => row.memory_percent),
			fill: true,
			format: 'percent' as const,
		},
		{
			label: '메모리 최댓값',
			color: '#4fc3f7',
			values: history.map((row) => row.memory_percent_max),
			fill: false,
			dashed: true,
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

	let hasGpuHistory = $derived(
		hasGpuAllocated || history.some((row) => typeof row.gpu_usage === 'number'),
	);
	let gpuDatasets = $derived([
		{
			label: 'GPU 코어 평균',
			color: '#f472b6',
			values: history.map((row) => (typeof row.gpu_usage === 'number' ? row.gpu_usage : 0)),
			fill: true,
			format: 'percent' as const,
		},
		{
			label: 'GPU 코어 최댓값',
			color: '#f472b6',
			values: history.map((row) =>
				typeof row.gpu_usage_max === 'number'
					? row.gpu_usage_max
					: typeof row.gpu_usage === 'number'
						? row.gpu_usage
						: 0,
			),
			fill: false,
			dashed: true,
			format: 'percent' as const,
		},
	]);
	let gpuMemDatasets = $derived([
		{
			label: 'GPU 메모리 평균',
			color: '#a087d9',
			values: gpuMemPctSeries,
			fill: true,
			format: 'percent' as const,
		},
		{
			label: 'GPU 메모리 최댓값',
			color: '#a087d9',
			values: gpuMemPctMaxSeries,
			fill: false,
			dashed: true,
			format: 'percent' as const,
		},
	]);
	let currentGpuUsage = $derived(snapshotGpu(currentMetrics));

	onMount(() => {
		loadDashboard({ withDetail: true });
		startRefreshTimer();
		return () => {
			if (refreshTimer) clearInterval(refreshTimer);
		};
	});
</script>

<div class="page">
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
			<section class="hero" data-status={container.status}>
				<div class="hero-main">
					<div class="hero-titlebar">
						<button
							type="button"
							class="back-link"
							onclick={() => goto(`${base}/user/containers`)}
							aria-label="컨테이너 목록으로 돌아가기"
							title="컨테이너 목록으로 돌아가기"
						>
							<span aria-hidden="true">←</span>
						</button>
						<div class="container-heading">
							<div class="container-name-line">
								<h1 title={container.name}>{container.name}</h1>
								<span class="status-pill" style="background: {statusTone(container.status)};">
									{statusLabel(container.status)}
								</span>
							</div>
							<div class="hero-subline">
								<span class="hero-image-text" title={container.selected_image || container.image}>
									{container.selected_image || container.image}
								</span>
								<span class="hero-divider" aria-hidden="true">•</span>
								<code class="hero-id" title="컨테이너 ID">{container.container_id.slice(0, 12)}</code>
							</div>
						</div>
					</div>
					<div class="hero-meta">
						<AgentStatusIndicator
							agentId={container.agent}
							hostname={container.agent_hostname}
							lastSeen={currentMetrics?.timestamp || container.last_seen}
						/>
						{#if container.template_name}
							<span class="meta-chip" title="요청 템플릿">
								<b>템플릿</b>
								<strong>{container.template_name}</strong>
							</span>
						{/if}
						<span class="meta-chip" title="요청 처리 상태">
							<b>요청</b>
							<strong>{statusLabel(container.request_status)}</strong>
						</span>
						<span class="meta-chip sync" data-fresh={syncFreshness} title="마지막 동기화">
							<b>동기화</b>
							<strong>{formatRelativeTime(currentMetrics?.timestamp || container.last_seen)}</strong>
						</span>
					</div>
					<div class="hero-vitals" aria-label="컨테이너 핵심 상태">
						<span class="vital-chip" title="컨테이너 가동 시간">
							<i class="vital-icon" aria-hidden="true">⏱</i>
							<span class="vital-body">
								<b>가동</b>
								<strong>{uptimeText || '—'}</strong>
							</span>
						</span>
						<span class="vital-chip" data-tone={runtimeRestartCount >= 3 ? 'danger' : runtimeRestartCount >= 1 ? 'warn' : 'ok'} title="누적 재시작 횟수 (inspect.restartCount)">
							<i class="vital-icon" aria-hidden="true">↻</i>
							<span class="vital-body">
								<b>재시작</b>
								<strong>{runtimeRestartCount}회</strong>
							</span>
						</span>
						<span class="vital-chip" data-tone={runtimeHealthTone} title={healthStatus ? 'Docker healthcheck 결과' : '컨테이너 런타임 상태'}>
							<i class="vital-icon" aria-hidden="true">♥</i>
							<span class="vital-body">
								<b>{runtimeHealthLabel}</b>
								<strong>{runtimeHealthText}</strong>
							</span>
						</span>
					</div>
					{#if recentRestarts >= 1 || isOomKilled || (lastExit && typeof lastExit?.exit_code === 'number' && lastExit.exit_code !== 0) || healthStatus}
						<div class="hero-insights">
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
					{/if}
				</div>
				<div class="hero-actions">
					<button
						class="pause-btn"
						class:active={paused}
						onclick={() => (paused = !paused)}
						title={paused ? '자동 새로고침 재개' : '자동 새로고침 일시정지'}
					>
						{paused ? '▶ 재개' : '⏸ 일시정지'}
					</button>
					<button class="refresh-btn" onclick={() => loadDashboard({ withDetail: true })} disabled={refreshing}>
						{refreshing ? '새로고침 중...' : '↻ 새로고침'}
					</button>
					<label class="refresh-interval" title="자동 새로고침 주기">
						<span>주기</span>
						<select bind:value={refreshIntervalMs} onchange={handleRefreshIntervalChange} aria-label="자동 새로고침 주기">
							{#each REFRESH_INTERVAL_OPTIONS as option}
								<option value={option.value}>{option.label}</option>
							{/each}
						</select>
					</label>
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
					hasGpuMem={hasGpuMemHistory || (currentGpuMemPct !== null && currentGpuMemPct !== undefined)}
					{currentGpuMemPct}
					{gpuMemAvg}
					{gpuMemPeak}
					{cpuHelp}
					{memoryHelp}
					{networkHelp}
					{diskHelp}
					workspaceHelp="컨테이너별 /workspace XFS project quota 사용량입니다. 분모는 요청 시 승인된 workspace quota(hard limit)입니다."
					cpuPercentLimit={container.cpu_percent_limit}
					memoryMbLimit={container.memory_mb_limit}
					workspaceGbLimit={container.workspace_gb_limit}
				/>
			</section>

			<section class="ops-bar">
				<div class="ops-head">
					<span class="ops-caption">CONTROL</span>
					<div class="ops-status" data-status={container.status}>
						<div class="status-orb">
							<span class="orb-core"></span>
							<span class="orb-pulse" aria-hidden="true"></span>
						</div>
						<div class="status-text">
							<span class="status-name">{statusLabel(container.status)}</span>
							<span class="status-meta">{uptimeText}</span>
						</div>
					</div>
				</div>
				<div class="ops-quick" aria-label="컨트롤 상태 요약">
					<span class:ok={agentOnline} class:bad={!agentOnline}>
						<b>명령 상태</b>
						<strong>{agentOnline ? '발송 가능' : '대기 중'}</strong>
						<em>{agentOnline ? '에이전트 온라인' : '에이전트 오프라인'}</em>
					</span>
					<span class:paused>
						<b>갱신 상태</b>
						<strong>{paused ? '일시정지' : '자동'}</strong>
						<em>{paused ? '수동 확인 모드' : '주기 폴링 중'}</em>
					</span>
					<span>
						<b>프로세스</b>
						<strong>{containerPid ?? '-'}</strong>
						<em>{containerPid ? '호스트 PID' : '미확인'}</em>
					</span>
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
					>
						<span aria-hidden="true">⚙</span>
						<span>설정</span>
					</button>
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
					<UserMetricChart labels={historyLabels} tooltipLabels={historyTooltipLabels} datasets={cpuDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={percentChartMarkLines} yAxisLabel={cpuAxisLabel} denominatorText={cpuDenominatorText} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>메모리 사용률</h3>
					</div>
					<UserMetricChart labels={historyLabels} tooltipLabels={historyTooltipLabels} datasets={memoryDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={percentChartMarkLines} yAxisLabel={memoryAxisLabel} denominatorText={memoryDenominatorText} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>네트워크 트래픽</h3>
						<div class="mode-toggle" role="group" aria-label="누적/속도 전환">
							<button class:active={networkMode === 'cumulative'} onclick={() => (networkMode = 'cumulative')}>누적</button>
							<button class:active={networkMode === 'rate'} onclick={() => (networkMode = 'rate')}>속도</button>
						</div>
					</div>
					<UserMetricChart labels={historyLabels} tooltipLabels={historyTooltipLabels} datasets={networkDatasets} yFormat={networkFormat} group={chartGroup} enableZoom markLines={chartMarkLines} />
				</div>
				<div class="chart-card">
					<div class="chart-head">
						<h3>디스크 처리량</h3>
						<div class="mode-toggle" role="group" aria-label="누적/속도 전환">
							<button class:active={diskMode === 'cumulative'} onclick={() => (diskMode = 'cumulative')}>누적</button>
							<button class:active={diskMode === 'rate'} onclick={() => (diskMode = 'rate')}>속도</button>
						</div>
					</div>
					<UserMetricChart labels={historyLabels} tooltipLabels={historyTooltipLabels} datasets={diskDatasets} yFormat={diskFormat} group={chartGroup} enableZoom markLines={chartMarkLines} />
				</div>
				{#if hasGpuHistory || (currentGpuUsage !== null && currentGpuUsage !== undefined)}
					<div class="chart-card">
						<div class="chart-head">
							<h3>GPU 코어 사용률</h3>
						</div>
						<UserMetricChart labels={historyLabels} tooltipLabels={historyTooltipLabels} datasets={gpuDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={percentChartMarkLines} />
					</div>
				{/if}
				{#if hasGpuMemHistory || (currentGpuMemPct !== null && currentGpuMemPct !== undefined)}
					<div class="chart-card">
						<div class="chart-head">
							<h3>GPU 메모리 (VRAM)</h3>
						</div>
						<UserMetricChart labels={historyLabels} tooltipLabels={historyTooltipLabels} datasets={gpuMemDatasets} yFormat="percent" group={chartGroup} enableZoom markLines={percentChartMarkLines} />
					</div>
				{/if}
			</div>
		</section>

		<div class="bento-area area-live">
			<div class="live-stack">
				<LogTailPanel agentId={container.agent ?? ''} {containerId} startOpen={true} />
				<ConsolePanel agentId={container.agent ?? ''} {containerId} startOpen={true} />
			</div>
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

		<div class="bento-area area-context">
			<section class="details-grid context-grid" aria-label="런타임 정보 및 요청 시 설정">
			<div class="panel runtime-panel">
				<div class="panel-header slim">
					<div>
						<h2>런타임 정보<InfoTooltip text={runtimeHelp} placement="bottom-start" /></h2>
						<p>이 컨테이너가 어느 요청에서 만들어졌고, 가장 최근에 언제 동기화됐는지를 보여줍니다. (상태·Health·재시작은 상단 hero 영역 참조)</p>
					</div>
				</div>
				<div class="runtime-timeline" aria-label="런타임 타임라인">
					<div>
						<span>시작</span>
						<strong>{formatDateTime(inspectData?.state?.startedAt)}</strong>
					</div>
					<div>
						<span>최근 동기화</span>
						<strong>{formatDateTime(container.last_seen)}</strong>
					</div>
				</div>
				<div class="info-grid">
					<div class="info-item">
						<span class="info-label">컨테이너 ID</span>
						<span class="info-value mono" title={container.container_id}>{container.container_id}</span>
					</div>
					<div class="info-item info-item-stacked">
						<span class="info-label">요청</span>
						<span class="info-value">{statusLabel(container.request_status)}</span>
						<span class="info-meta mono" title={container.request_id ?? '-'}>{container.request_id ?? '-'}</span>
					</div>
				</div>
				{#if container.review_note}
					<div class="note-box">
						<span class="info-label">검토 메모</span>
						<p>{container.review_note}</p>
					</div>
				{/if}
				<div class="runtime-footprint" aria-label="런타임 운영 상태">
					<div>
						<span>호스트 PID</span>
						<strong>{containerPid ?? '-'}</strong>
						<em>{containerPid ? '프로세스 추적 가능' : 'inspect 대기'}</em>
					</div>
					<div data-tone={agentOnline ? 'success' : 'danger'}>
						<span>Agent</span>
						<strong>{agentOnline ? '온라인' : '오프라인'}</strong>
						<em title={container.agent ?? '-'}>{container.agent ?? '-'}</em>
					</div>
				</div>
			</div>

			<div class="panel config-panel">
				<div class="panel-header slim">
					<div>
						<h2>요청 시 설정<InfoTooltip text={configHelp} placement="bottom-start" /></h2>
						<p>요청을 만들 때 입력했던 포트 매핑과 환경 변수입니다.</p>
					</div>
				</div>
				<div class="config-summary" aria-label="요청 설정 요약">
					<div class="config-summary-card">
						<span>포트</span>
						<strong>{portMappings.length}개</strong>
						<em>{portMappings.length > 0 ? '외부 연결 있음' : '기본 네트워크'}</em>
					</div>
					<div class="config-summary-card">
						<span>환경 변수</span>
						<strong>{envEntries.length}개</strong>
						<em>{envEntries.length > 0 ? '주입 값 있음' : '추가 값 없음'}</em>
					</div>
					<div class="config-summary-card">
						<span>실행 설정</span>
						<strong>{requestConfigMode}</strong>
						<em title={requestConfigSource}>{requestConfigSource}</em>
					</div>
				</div>

				{#if hasRequestConfig}
					<div class="config-detail-grid">
						{#if portMappings.length > 0}
							<div class="config-card">
								<span class="config-title">포트 매핑</span>
								<div class="port-flow-list">
									{#each portMappings as port}
										<div class="port-flow">
											<span class="flow-end">
												<b>HOST</b>
												<strong>{port.host ?? '-'}</strong>
											</span>
											<span class="flow-arrow">→</span>
											<span class="flow-end">
												<b>CONTAINER</b>
												<strong>{port.container ?? '-'}</strong>
											</span>
											<em>{port.protocol ?? 'tcp'}</em>
										</div>
									{/each}
								</div>
							</div>
						{/if}
						{#if envEntries.length > 0}
							<div class="config-card">
								<span class="config-title">환경 변수</span>
								<div class="env-list">
									{#each envEntries as [key, value]}
										<div class="env-row">
											<span class="env-key">{key}</span>
											<span class="env-mask" title="민감 값 보호를 위해 마스킹됩니다.">{maskEnvValue(value)}</span>
										</div>
									{/each}
								</div>
							</div>
						{/if}
					</div>
				{:else}
					<div class="config-empty-state">
						<strong>추가 설정 없음</strong>
						<span>별도 포트 매핑이나 환경 변수 없이 요청 이미지/템플릿 기본값으로 실행 중입니다.</span>
					</div>
				{/if}
			</div>
			</section>
		</div>

		</div>

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
		max-width: none;
		margin: 0;
		padding: clamp(6px, 0.55vw, 10px) clamp(8px, 0.8vw, 16px);
		height: 100%;
		display: flex;
		flex-direction: column;
		gap: clamp(5px, 0.45vw, 8px);
		min-height: 0;
		overflow: hidden;
	}

	.back-link,
	.refresh-btn,
	.range-btn {
		border: none;
		font-family: inherit;
		cursor: pointer;
	}

	.back-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 30px;
		height: 30px;
		padding: 0;
		background: rgba(13, 17, 23, 0.55);
		border: 1px solid rgba(48, 213, 200, 0.26);
		border-radius: 8px;
		color: var(--accent);
		font-size: 16px;
		font-weight: 900;
		line-height: 1;
		align-self: center;
		white-space: nowrap;
		flex: 0 0 auto;
		transition:
			background-color var(--ease-fast),
			border-color var(--ease-fast),
			color var(--ease-fast);
	}

	.back-link:hover {
		background: rgba(48, 213, 200, 0.14);
		border-color: rgba(48, 213, 200, 0.45);
		color: #6ee7e0;
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
		position: static;
		z-index: 10;
		background: var(--bg-base);
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: clamp(4px, 0.35vw, 8px);
		flex: 0 0 auto;
	}

	/* 한 row 안에 [hero | KPI | ops]. 좁아지면 wrap.
	   stretch — 같은 row 안 세 영역 높이 통일 (가장 키 큰 영역 기준).
	   min-height — hero-insights chip(재시작/OOM/health) 이 polling 마다 나타났다
	   사라지며 hero 자연 높이가 변동하는 걸 흡수. 하한을 잠가 화면이 출렁이지 않게.
	   ops-bar 가 자연 가장 키 크므로 그 컴팩트 높이(~170) 기준으로 잠금. */
	.unified-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: stretch;
		gap: clamp(5px, 0.45vw, 9px);
		min-height: clamp(160px, 15vh, 180px);
	}

	/* hero accent stripe (data-status) — 좌측 4px 컬러 바로 컨테이너 정체성 강화.
	   기본은 accent teal, running → green, paused/restarting → amber, exited/dead → red. */
	.hero {
		--hero-accent: rgba(48, 213, 200, 0.7);
		--hero-glow: rgba(48, 213, 200, 0.45);
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		gap: 8px;
		padding: 10px 14px 10px 18px;
		border-radius: 12px;
		background:
			radial-gradient(ellipse at top left, rgba(48, 213, 200, 0.10), transparent 60%),
			rgba(18, 23, 32, 0.98);
		border: 1px solid rgba(48, 213, 200, 0.22);
		box-shadow:
			0 10px 32px rgba(0, 0, 0, 0.18),
			inset 0 1px 0 rgba(255, 255, 255, 0.03);
		align-items: stretch;
		flex: 0.9 1 360px;
		min-width: 320px;
		max-width: 450px;
		position: relative;
		overflow: hidden;
	}
	.hero::before {
		content: '';
		position: absolute;
		left: 0;
		top: 8px;
		bottom: 8px;
		width: 4px;
		border-radius: 0 4px 4px 0;
		background: var(--hero-accent);
		box-shadow: 0 0 14px var(--hero-glow);
	}
	.hero[data-status='running'] {
		--hero-accent: #34d399;
		--hero-glow: rgba(52, 211, 153, 0.5);
	}
	.hero[data-status='paused'],
	.hero[data-status='restarting'] {
		--hero-accent: #fbbf24;
		--hero-glow: rgba(251, 191, 36, 0.45);
	}
	.hero[data-status='exited'],
	.hero[data-status='dead'],
	.hero[data-status='oom_killed'] {
		--hero-accent: #f87171;
		--hero-glow: rgba(248, 113, 113, 0.5);
	}

	.hero-main {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
		flex: 1 1 auto;
	}

	.hero-titlebar {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: center;
		gap: 10px;
		min-width: 0;
		width: 100%;
	}

	.container-heading {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.container-name-line {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	h1 {
		min-width: 0;
		font-size: clamp(21px, 1.55vw, 27px);
		line-height: 1.02;
		font-weight: 900;
		letter-spacing: -0.018em;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		/* 컨테이너 정체성 — 밝은-회색 톤 다운 그라데이션 + 미세한 글로우. */
		background: linear-gradient(180deg, #fafcff 0%, #c9d2e0 100%);
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
		filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.45));
	}

	.hero-subline {
		display: flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		max-width: 100%;
		font-size: 11.5px;
		color: var(--text-muted);
	}

	.hero-image-text {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: rgba(48, 213, 200, 0.88);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-weight: 700;
		flex: 0 1 auto;
	}

	.hero-divider {
		color: var(--text-muted);
		opacity: 0.5;
		flex: 0 0 auto;
	}

	.hero-id {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 11px;
		color: var(--text-muted);
		flex: 0 0 auto;
	}

	.meta-chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		max-width: 100%;
		min-height: 22px;
		padding: 2px 8px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.48);
		border: 1px solid rgba(100, 116, 139, 0.16);
		font-size: 11.5px;
		color: var(--text-secondary);
		font-weight: 700;
		min-width: 0;
	}

	.meta-chip b {
		color: var(--text-muted);
		font-size: 9.5px;
		font-weight: 900;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		flex: 0 0 auto;
	}

	.meta-chip strong {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--text-primary);
		font-size: 11.5px;
		font-weight: 800;
	}

	/* 동기화 신선도 — 30s/2m/10m 임계로 색 분기. fresh = 정상, stale/cold = 운영자 주의 */
	.meta-chip.sync[data-fresh='fresh'] {
		border-color: rgba(16, 185, 129, 0.32);
		background: rgba(16, 185, 129, 0.06);
	}
	.meta-chip.sync[data-fresh='fresh'] strong { color: #6ee7b7; }
	.meta-chip.sync[data-fresh='stale'] {
		border-color: rgba(251, 191, 36, 0.34);
		background: rgba(251, 191, 36, 0.06);
	}
	.meta-chip.sync[data-fresh='stale'] strong { color: #fde68a; }
	.meta-chip.sync[data-fresh='cold'] {
		border-color: rgba(239, 68, 68, 0.34);
		background: rgba(239, 68, 68, 0.06);
	}
	.meta-chip.sync[data-fresh='cold'] strong { color: #fca5a5; }

	.hero-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		align-items: center;
		min-width: 0;
	}

	.hero-insights {
		display: flex;
		flex-wrap: wrap;
		gap: 5px;
		align-items: center;
		min-width: 0;
	}

	/* hero vitals — 가동 / 재시작 / health 항상 표시. hero 중앙 공백 채움 +
	   "이 컨테이너가 지금 어떤 상태인가" 한 줄 요약. tone 별로 좌측 dot 색. */
	.hero-vitals {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 5px;
		min-width: 0;
	}
	.vital-chip {
		min-width: 0;
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: center;
		gap: 8px;
		padding: 6px 9px 6px 11px;
		border-radius: 9px;
		background: linear-gradient(180deg, rgba(13, 17, 23, 0.55), rgba(2, 6, 12, 0.45));
		border: 1px solid rgba(100, 116, 139, 0.2);
		position: relative;
		overflow: hidden;
		transition: border-color var(--ease-fast), background-color var(--ease-fast);
	}
	.vital-chip:hover {
		border-color: rgba(48, 213, 200, 0.32);
	}
	.vital-chip::before {
		content: '';
		position: absolute;
		left: 0;
		top: 6px;
		bottom: 6px;
		width: 2px;
		border-radius: 2px;
		background: rgba(148, 163, 184, 0.55);
	}
	.vital-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		border-radius: 7px;
		background: rgba(13, 17, 23, 0.5);
		color: rgba(148, 163, 184, 0.85);
		font-size: 13px;
		font-style: normal;
		line-height: 1;
		flex: 0 0 auto;
	}
	.vital-body {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 1px;
	}
	.vital-chip b {
		color: var(--text-muted);
		font-size: 9.5px;
		font-weight: 900;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		line-height: 1;
	}
	.vital-chip strong {
		min-width: 0;
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 850;
		line-height: 1.15;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
	}
	.vital-chip[data-tone='success'] .vital-icon,
	.vital-chip[data-tone='ok'] .vital-icon {
		background: rgba(16, 185, 129, 0.12);
		color: #6ee7b7;
	}
	.vital-chip[data-tone='warn'] .vital-icon {
		background: rgba(251, 191, 36, 0.12);
		color: #fde68a;
	}
	.vital-chip[data-tone='danger'] .vital-icon {
		background: rgba(239, 68, 68, 0.14);
		color: #fca5a5;
	}
	.vital-chip[data-tone='success']::before,
	.vital-chip[data-tone='ok']::before {
		background: #34d399;
		box-shadow: 0 0 6px rgba(52, 211, 153, 0.45);
	}
	.vital-chip[data-tone='success'] strong,
	.vital-chip[data-tone='ok'] strong { color: #6ee7b7; }
	.vital-chip[data-tone='warn']::before {
		background: #fbbf24;
		box-shadow: 0 0 6px rgba(251, 191, 36, 0.45);
	}
	.vital-chip[data-tone='warn'] strong { color: #fde68a; }
	.vital-chip[data-tone='danger']::before {
		background: #f87171;
		box-shadow: 0 0 6px rgba(248, 113, 113, 0.5);
	}
	.vital-chip[data-tone='danger'] strong { color: #fca5a5; }

	/* 운영 인사이트 chip — 이상 신호만 시각 강조. severity 색 한눈에. */
	.insight-chip {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		padding: 2px 7px;
		border-radius: 999px;
		font-size: 11.5px;
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
		gap: 7px;
		padding: 4px 11px 4px 10px;
		border-radius: 999px;
		font-size: 12px;
		font-weight: 850;
		letter-spacing: 0.04em;
		color: white;
		box-shadow:
			0 0 0 1px rgba(255, 255, 255, 0.08) inset,
			0 2px 10px rgba(0, 0, 0, 0.18);
		text-shadow: 0 1px 1px rgba(0, 0, 0, 0.32);
	}
	.status-pill::before {
		content: '';
		display: inline-block;
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: currentColor;
		box-shadow: 0 0 10px currentColor;
	}
	/* running 상태는 살아 있다는 신호로 dot 부드러운 펄스. 다른 상태는 정적. */
	.hero[data-status='running'] .status-pill::before {
		animation: pulse-running 1.8s ease-in-out infinite;
	}
	@keyframes pulse-running {
		0%, 100% { opacity: 1; transform: scale(1); }
		50% { opacity: 0.65; transform: scale(0.86); }
	}

	/* hero 운영 utility 묶음 — 일시정지·새로고침·주기. 외곽 pill 로 그룹감을 주고
	   내부 버튼은 teal hint border + subtle gradient 로 hero 본체 색조와 맞춤. */
	.hero-actions {
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 4px;
		flex-wrap: wrap;
		flex-shrink: 0;
		align-self: stretch;
		padding: 3px 5px;
		border-radius: 10px;
		background: rgba(2, 6, 12, 0.34);
		border: 1px solid rgba(48, 213, 200, 0.1);
		justify-content: flex-start;
	}

	.refresh-btn,
	.pause-btn,
	.refresh-interval {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 5px;
		padding: 0 9px;
		min-width: 0;
		min-height: 24px;
		border-radius: 6px;
		background:
			linear-gradient(180deg, rgba(20, 27, 38, 0.85), rgba(11, 16, 24, 0.92));
		border: 1px solid rgba(48, 213, 200, 0.16);
		color: var(--text-primary);
		font-size: 11.5px;
		font-weight: 750;
		font-family: inherit;
		cursor: pointer;
		white-space: nowrap;
		transition: background-color var(--ease-fast), border-color var(--ease-fast), color var(--ease-fast);
	}

	.refresh-interval {
		gap: 4px;
		cursor: default;
	}

	.refresh-interval span {
		color: var(--text-muted);
		font-size: 10px;
		font-weight: 850;
	}

	.refresh-interval select {
		min-width: 52px;
		border: 0;
		outline: none;
		background: transparent;
		color: var(--text-primary);
		font-family: inherit;
		font-size: 11.5px;
		font-weight: 800;
		cursor: pointer;
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
		margin-top: 0;
		padding: 8px 12px;
		border-radius: 10px;
		font-size: 12px;
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
		flex: 1.35 1 500px;
		min-width: 500px;
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
		padding: clamp(7px, 0.5vw, 9px) clamp(8px, 0.6vw, 11px);
		border-radius: 10px;
		background:
			linear-gradient(135deg, rgba(48, 213, 200, 0.09), transparent 38%),
			linear-gradient(180deg, rgba(13, 17, 23, 0.55), rgba(18, 23, 32, 0.98)),
			rgba(18, 23, 32, 0.98);
		border: 1px solid var(--border);
		display: grid;
		grid-template-rows: auto auto auto;
		align-content: space-between;
		gap: 6px;
		flex: 0.78 1 340px;
		min-width: 320px;
		max-width: 430px;
		box-shadow:
			0 10px 30px rgba(0, 0, 0, 0.16),
			inset 0 1px 0 rgba(255, 255, 255, 0.03);
		position: relative;
		overflow: hidden;
	}

	.ops-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		min-width: 0;
		padding-bottom: 5px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.14);
	}

	.ops-caption {
		display: inline-flex;
		align-items: center;
		padding: 4px 8px;
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.1);
		border: 1px solid rgba(48, 213, 200, 0.22);
		font-size: 11px;
		font-weight: 900;
		letter-spacing: 0.08em;
		color: var(--accent);
		flex: 0 0 auto;
	}

	.ops-status {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 8px;
		flex: 0 0 auto;
		min-width: 0;
	}
	.status-orb {
		position: relative;
		width: 32px;
		height: 32px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	.orb-core {
		width: 10px;
		height: 10px;
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
		gap: 2px;
		min-width: 0;
		text-align: right;
	}
	.status-name {
		font-size: 15px;
		font-weight: 900;
		color: var(--text-primary);
		letter-spacing: -0.005em;
		line-height: 1.1;
	}
	.status-meta {
		font-size: 12px;
		color: var(--text-muted);
		font-weight: 700;
		white-space: nowrap;
		line-height: 1.2;
	}

	.ops-quick {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 6px;
		width: 100%;
	}
	.ops-quick span {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 3px;
		min-width: 0;
		min-height: 46px;
		padding: 5px 8px;
		border-radius: 8px;
		background: rgba(2, 6, 12, 0.3);
		border: 1px solid rgba(100, 116, 139, 0.14);
		color: var(--text-secondary);
		font-size: 12px;
		font-weight: 800;
		line-height: 1.1;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		font-variant-numeric: tabular-nums;
	}
	.ops-quick b {
		display: block;
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 900;
		letter-spacing: 0;
	}
	.ops-quick strong,
	.ops-quick em {
		display: block;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.ops-quick strong {
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 900;
	}
	.ops-quick em {
		color: rgba(148, 163, 184, 0.62);
		font-size: 10.5px;
		font-style: normal;
		font-weight: 700;
		letter-spacing: 0.01em;
	}
	/* 상태 색은 좌측 stripe 와 strong 텍스트 컬러로만 표시 — 배경 oversaturation 방지. */
	.ops-quick span.ok,
	.ops-quick span.bad,
	.ops-quick span.paused {
		position: relative;
	}
	.ops-quick span.ok::before,
	.ops-quick span.bad::before,
	.ops-quick span.paused::before {
		content: '';
		position: absolute;
		left: 0;
		top: 6px;
		bottom: 6px;
		width: 2px;
		border-radius: 2px;
	}
	.ops-quick span.ok {
		border-color: rgba(16, 185, 129, 0.3);
		background: rgba(16, 185, 129, 0.04);
	}
	.ops-quick span.ok::before { background: #34d399; box-shadow: 0 0 6px rgba(52, 211, 153, 0.45); }
	.ops-quick span.ok strong { color: #6ee7b7; }
	.ops-quick span.bad {
		border-color: rgba(239, 68, 68, 0.34);
		background: rgba(239, 68, 68, 0.05);
	}
	.ops-quick span.bad::before { background: #f87171; box-shadow: 0 0 6px rgba(248, 113, 113, 0.45); }
	.ops-quick span.bad strong { color: #fca5a5; }
	.ops-quick span.paused {
		border-color: rgba(251, 191, 36, 0.34);
		background: rgba(251, 191, 36, 0.05);
	}
	.ops-quick span.paused::before { background: #fbbf24; box-shadow: 0 0 6px rgba(251, 191, 36, 0.4); }
	.ops-quick span.paused strong { color: #fde68a; }

	.ops-divider {
		display: none;
	}

	/* 우측 액션 영역 — ContainerActions + limit icon btn */
	.ops-actions {
		display: flex;
		align-items: stretch;
		gap: 5px;
		flex: 0 0 auto;
		min-width: 0;
		width: 100%;
		justify-content: stretch;
	}
	.ops-actions :global(.actions) {
		flex: 1 1 auto;
		width: 100%;
		min-width: 0;
	}

	/* 한도수정 — lifecycle 버튼 옆에서 같은 밀도로 보이게 맞춤 */
	.limit-icon-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 4px;
		min-width: 68px;
		height: 40px;
		padding: 0 11px;
		border-radius: 8px;
		background: rgba(13, 17, 23, 0.6);
		border: 1px solid rgba(31, 41, 55, 0.9);
		color: var(--text-muted);
		font-family: inherit;
		font-size: 12px;
		font-weight: 800;
		cursor: pointer;
		flex-shrink: 0;
		white-space: nowrap;
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
		font-size: 11.5px;
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
		font-size: 10px;
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
		background:
			linear-gradient(180deg, rgba(21, 27, 38, 0.98), rgba(15, 20, 29, 0.98)),
			rgba(18, 23, 32, 0.96);
		border: 1px solid rgba(100, 116, 139, 0.18);
		box-shadow:
			0 8px 24px rgba(0, 0, 0, 0.16),
			inset 0 1px 0 rgba(255, 255, 255, 0.025);
	}

	/* Desktop layout: charts stay compact, events/status sit directly below them. */
	.bento {
		display: grid;
		grid-template-columns: repeat(12, minmax(0, 1fr));
		grid-template-rows: minmax(0, 1.05fr) minmax(0, 0.76fr) minmax(0, 0.67fr);
		grid-template-areas:
			"charts charts charts charts charts live live live live process process process"
			"charts charts charts charts charts live live live live context context context"
			"events events inspect inspect inspect live live live live context context context";
		gap: clamp(5px, 0.45vw, 9px);
		margin-top: 0;
		flex: 1 1 0;
		min-height: 0;
		overflow: hidden;
	}
	.bento-area {
		min-width: 0;
		min-height: 0;
	}
	.area-charts {
		grid-area: charts;
	}
	.area-live {
		grid-area: live;
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
	.area-context {
		grid-area: context;
	}
	.area-context > .context-grid {
		flex: 1 1 0;
		width: 100%;
	}

	.live-stack {
		display: grid;
		grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
		gap: clamp(5px, 0.45vw, 9px);
		height: 100%;
		min-height: 0;
		min-width: 0;
		width: 100%;
		max-width: 100%;
		overflow: hidden;
	}

	.live-stack :global(.panel) {
		display: flex;
		flex-direction: column;
		min-height: 0;
		min-width: 0;
		height: 100%;
		width: 100%;
		max-width: 100%;
		margin-top: 0;
		box-sizing: border-box;
		overflow: hidden;
	}

	.live-stack :global(.toolbar) {
		flex: 0 0 auto;
		min-width: 0;
		max-width: 100%;
		box-sizing: border-box;
	}

	.live-stack :global(.logbox),
	.live-stack :global(.termbox) {
		flex: 1 1 0;
		min-height: 0;
		min-width: 0;
		height: auto;
		width: 100%;
		max-width: 100%;
		box-sizing: border-box;
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
		min-height: 0;
	}

	.panel {
		border-radius: 10px;
		padding: clamp(8px, 0.7vw, 12px);
		margin-top: 0;
		min-height: 0;
	}

	.panel-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-end;
		gap: clamp(5px, 0.45vw, 10px);
		margin-bottom: clamp(5px, 0.45vw, 8px);
	}

	.panel-header.slim {
		margin-bottom: clamp(3px, 0.3vw, 8px);
	}

	/* compact = 차트 panel 처럼 dense workbench 헤더. 부제·hint 없이
	   h2 + 우측 range tabs 한 줄로. */
	.panel-header.compact {
		align-items: center;
		margin-bottom: 8px;
		padding-bottom: 6px;
		border-bottom: 1px solid rgba(100, 116, 139, 0.14);
	}

	h2 {
		font-size: clamp(13px, 0.95vw, 16px);
		margin-bottom: 2px;
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
		padding: 2px 7px;
		border-radius: var(--radius-full);
		background: rgba(48, 213, 200, 0.1);
		border: 1px solid rgba(48, 213, 200, 0.28);
		color: var(--accent);
		font-size: 10.5px;
		font-weight: 800;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		cursor: help;
		user-select: none;
	}
	.sync-icon {
		font-size: 12px;
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
		padding: 1px;
		background: rgba(13, 17, 23, 0.5);
		border: 1px solid rgba(31, 41, 55, 0.6);
		border-radius: 8px;
	}

	.range-btn {
		padding: 3px 7px;
		border-radius: 5px;
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
		grid-template-rows: repeat(2, minmax(0, 1fr));
		grid-auto-rows: minmax(0, 1fr);
		gap: clamp(5px, 0.45vw, 8px);
		flex: 1 1 0;
		min-height: 0;
	}

	/* area-charts panel 자체가 flex column → chart-grid 가 자연 height 채움 */
	.area-charts {
		display: flex;
		flex-direction: column;
		min-height: 0;
	}

	.chart-card {
		border-radius: 9px;
		padding: clamp(6px, 0.5vw, 9px);
		transition: border-color var(--ease-fast);
		display: flex;
		flex-direction: column;
		min-height: 0;
		position: relative;
	}
	.chart-card::before {
		content: '';
		position: absolute;
		top: 0;
		left: 10px;
		right: 10px;
		height: 2px;
		border-radius: 999px;
		background: linear-gradient(90deg, rgba(48, 213, 200, 0.65), rgba(96, 165, 250, 0.16));
		opacity: 0.45;
	}
	.chart-card:hover {
		border-color: rgba(48, 213, 200, 0.22);
	}

	.chart-head {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: clamp(4px, 0.35vw, 8px);
		margin-bottom: clamp(3px, 0.25vw, 5px);
		padding-bottom: clamp(3px, 0.25vw, 5px);
		border-bottom: 1px solid rgba(100, 116, 139, 0.14);
	}

	.chart-head h3 {
		font-size: clamp(12px, 0.82vw, 14px);
		font-weight: 700;
	}

	.chart-head span {
		font-size: 12.5px;
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
		padding: 2px 7px;
		background: rgba(13, 17, 23, 0.86);
		border: none;
		color: var(--text-muted);
		font-family: inherit;
		font-size: 10.5px;
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
		gap: clamp(6px, 0.5vw, 10px);
		margin-top: clamp(5px, 0.4vw, 8px);
	}

	.context-grid {
		grid-template-columns: 1fr;
		grid-template-rows: minmax(0, 1fr) minmax(0, 0.86fr);
		height: 100%;
		min-height: 0;
		margin-top: 0;
	}
	.context-grid > .panel {
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
		padding: 8px;
	}
	.context-grid > .runtime-panel {
		overflow: auto;
		gap: 5px;
		scrollbar-gutter: stable;
	}
	.context-grid > .config-panel {
		gap: 7px;
	}
	.context-grid .panel-header.slim {
		margin-bottom: 4px;
		padding-bottom: 4px;
	}
	.context-grid .panel-header.slim p {
		display: none;
	}
	.context-grid .runtime-panel .info-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 6px;
	}
	.context-grid .runtime-timeline > div {
		padding: 5px 6px;
		border-radius: 9px;
	}
	.context-grid .runtime-timeline span {
		font-size: 10px;
	}
	.context-grid .runtime-timeline strong {
		font-size: 13px;
	}
	.context-grid .runtime-timeline {
		gap: 5px;
	}
	.context-grid .runtime-timeline > div {
		gap: 2px;
	}
	.context-grid .runtime-panel .info-item {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 3px;
		min-height: 40px;
		padding: 6px 8px;
	}
	.context-grid .runtime-panel .info-label {
		margin-bottom: 0;
	}
	.context-grid .runtime-panel .info-value {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		line-height: 1.25;
	}
	.context-grid .runtime-panel .info-value.mono {
		font-size: 12px;
	}
	.context-grid .info-item,
	.context-grid .note-box,
	.context-grid .config-card,
	.context-grid .config-summary-card,
	.context-grid .config-empty-state {
		padding: 8px;
		border-radius: 9px;
	}
	.context-grid .note-box {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: center;
		gap: 8px;
		flex: 0 0 auto;
		margin-top: 4px;
		min-height: 28px;
		max-height: none;
		overflow: hidden;
		padding: 4px 8px;
	}
	.context-grid .note-box .info-label {
		margin-bottom: 0;
		white-space: nowrap;
	}
	.context-grid .note-box p {
		margin: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.context-grid .runtime-footprint {
		margin-top: auto;
	}
	.context-grid .config-detail-grid {
		gap: 7px;
		min-height: 0;
		overflow: auto;
	}
	.context-grid .tag-list,
	.context-grid .port-flow-list,
	.context-grid .env-list {
		max-height: 86px;
		overflow: auto;
	}

	/* 런타임/요청 설정 accordion — 기본 닫힘 (사용자가 펼쳐서 본다).
	   자연 스크롤 환경이라 모든 viewport 에서 표시. */
	.details-accordion {
		margin-top: 0;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: rgba(18, 23, 32, 0.96);
		overflow: hidden;
		flex: 0 0 auto;
	}
	.details-accordion > summary {
		list-style: none;
		cursor: pointer;
		padding: 6px 10px;
		display: flex;
		align-items: center;
		gap: 10px;
		user-select: none;
		font-size: 11px;
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
		padding: clamp(6px, 0.5vw, 10px);
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
		font-size: 12px;
		color: var(--text-muted);
		margin-bottom: 4px;
	}

	.info-value {
		font-size: 13px;
		color: var(--text-primary);
		word-break: break-word;
	}

	.info-value.mono {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.info-meta {
		display: block;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--text-muted);
		font-size: 11px;
		line-height: 1.2;
	}

	.info-meta.mono {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
	}

	.runtime-timeline > div {
		background:
			linear-gradient(180deg, rgba(13, 17, 23, 0.82), rgba(8, 12, 19, 0.72)),
			rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
		min-width: 0;
	}

	.runtime-timeline span {
		color: var(--text-muted);
		font-size: 10.5px;
		font-weight: 800;
	}

	.runtime-timeline strong {
		color: var(--text-primary);
		font-size: 14px;
		font-weight: 900;
		line-height: 1.05;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.runtime-timeline {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 6px;
		flex: 0 0 auto;
	}

	.runtime-timeline > div {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.runtime-footprint {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 6px;
		flex: 0 0 auto;
		min-width: 0;
	}

	.runtime-footprint > div {
		position: relative;
		min-width: 0;
		min-height: 46px;
		padding: 5px 8px 5px 10px;
		border-radius: 9px;
		background:
			linear-gradient(180deg, rgba(13, 17, 23, 0.76), rgba(8, 12, 19, 0.68)),
			rgba(13, 17, 23, 0.72);
		border: 1px solid rgba(100, 116, 139, 0.15);
		display: grid;
		grid-template-columns: minmax(0, 1fr);
		align-content: center;
		align-items: center;
		gap: 2px;
		overflow: hidden;
	}

	.runtime-footprint > div::before {
		content: '';
		position: absolute;
		inset: 7px auto 7px 0;
		width: 3px;
		border-radius: 999px;
		background: rgba(100, 116, 139, 0.62);
	}

	.runtime-footprint > div[data-tone='success']::before {
		background: #10b981;
	}

	.runtime-footprint > div[data-tone='warn']::before {
		background: #fbbf24;
	}

	.runtime-footprint > div[data-tone='danger']::before {
		background: #ef4444;
	}

	.runtime-footprint span {
		color: var(--text-muted);
		font-size: 9.5px;
		font-weight: 850;
		line-height: 1;
		white-space: nowrap;
	}

	.runtime-footprint strong {
		color: var(--text-primary);
		font-size: 12px;
		font-weight: 900;
		line-height: 1.05;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-variant-numeric: tabular-nums;
		text-align: left;
	}

	.runtime-footprint em {
		color: var(--text-secondary);
		font-size: 9.5px;
		font-style: normal;
		font-weight: 650;
		line-height: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.note-box {
		margin-top: 12px;
	}

	.note-box p {
		font-size: 13px;
		color: var(--text-secondary);
	}

	.config-summary {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 7px;
		flex: 0 0 auto;
	}

	.config-summary-card,
	.config-empty-state {
		background:
			linear-gradient(180deg, rgba(13, 17, 23, 0.84), rgba(8, 12, 19, 0.78)),
			rgba(13, 17, 23, 0.76);
		border: 1px solid rgba(31, 41, 55, 0.86);
	}

	.config-summary-card {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 3px;
		min-width: 0;
		min-height: 62px;
	}

	.config-summary-card span {
		color: var(--text-muted);
		font-size: 11px;
		font-weight: 800;
	}

	.config-summary-card strong {
		color: var(--text-primary);
		font-size: 15px;
		font-weight: 900;
		line-height: 1.05;
		font-variant-numeric: tabular-nums;
	}

	.config-summary-card em {
		color: var(--text-secondary);
		font-size: 11px;
		font-style: normal;
		font-weight: 650;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.config-detail-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(128px, 1fr));
		gap: 12px;
		min-height: 0;
		overflow: auto;
	}

	.config-empty-state {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 4px;
		min-height: 70px;
		color: var(--text-secondary);
	}

	.config-empty-state strong {
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 850;
	}

	.config-empty-state span {
		font-size: 12px;
		line-height: 1.35;
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
		font-size: 12px;
		font-weight: 700;
	}

	.port-flow-list {
		display: flex;
		flex-direction: column;
		gap: 7px;
	}

	.port-flow {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto;
		align-items: center;
		gap: 6px;
		padding: 7px;
		border-radius: 8px;
		background: rgba(2, 6, 12, 0.34);
		border: 1px solid rgba(100, 116, 139, 0.14);
	}

	.flow-end {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.flow-end b {
		color: var(--text-muted);
		font-size: 9px;
		font-weight: 900;
		letter-spacing: 0.04em;
	}

	.flow-end strong {
		color: var(--text-primary);
		font-size: 13px;
		font-weight: 900;
		font-variant-numeric: tabular-nums;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.flow-arrow {
		color: var(--accent);
		font-size: 13px;
		font-weight: 900;
	}

	.port-flow em {
		padding: 2px 5px;
		border-radius: 999px;
		background: rgba(48, 213, 200, 0.1);
		color: var(--accent);
		font-size: 10px;
		font-style: normal;
		font-weight: 800;
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
		font-size: 13px;
		color: var(--text-primary);
		padding-bottom: 8px;
		border-bottom: 1px solid rgba(31, 41, 55, 0.7);
	}

	.env-key,
	.env-mask {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.env-key {
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		color: var(--text-primary);
	}

	.env-mask {
		color: var(--text-muted);
		font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
		font-size: 12px;
	}

	.env-row:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.config-empty {
		font-size: 13px;
		color: var(--text-secondary);
	}

	/* 1280~1439: 차트와 라이브 패널을 위에 두고 보조 패널은 한 줄로 압축. */
	@media (max-width: 1439px) {
		.bento {
			grid-template-rows: minmax(0, 1.08fr) minmax(0, 0.73fr) minmax(0, 0.61fr);
			grid-template-areas:
				"charts charts charts charts charts live live live live process process process"
				"charts charts charts charts charts live live live live context context context"
				"events events inspect inspect inspect live live live live context context context";
		}
	}

	/* viewport 세로가 짧으면 zero-scroll 정책을 해제하고 page 자체를 스크롤 가능.
	   한 화면에 모두 담으려면 6 차트 카드(GPU 컨테이너)가 1/3씩 분할되어 찌부됨.
	   세로 ≤ 900 환경(노트북 1366×768, 1600×900 등)은 scroll 허용 + 차트 카드
	   floor 보장으로 가독성 회복. */
	@media (max-height: 900px) {
		.page {
			overflow-y: auto;
		}
		.bento {
			overflow: visible;
			grid-template-rows: minmax(220px, auto) minmax(180px, auto) minmax(180px, auto);
		}
		.chart-card {
			min-height: 150px;
		}
		.area-charts {
			min-height: 0;
		}
	}

	/* ≤980: 1열 stack (모바일) */
	@media (max-width: 980px) {
		.page {
			padding: 14px 12px 24px;
			height: auto;
			min-height: 100%;
			overflow: visible;
		}

		.unified-bar {
			display: grid;
			grid-template-columns: 1fr;
		}

		.hero,
		.kpi-row,
		.ops-bar {
			width: 100%;
			min-width: 0;
			max-width: none;
		}

		.kpi-row {
			flex-basis: auto;
		}

		.kpi-row :global(.kpi-bar) {
			grid-template-columns: repeat(2, minmax(0, 1fr));
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
			grid-template-rows: none;
			grid-auto-rows: auto;
			grid-template-areas:
				'charts'
				'events'
				'inspect'
				'live'
				'process'
				'context';
			overflow: visible;
			flex: 0 0 auto;
		}
		.bento-area > :global(.panel) {
			height: auto;
		}
		.chart-grid {
			grid-template-columns: 1fr;
			grid-template-rows: none;
			grid-auto-rows: minmax(180px, auto);
			flex: 0 0 auto;
		}
		.chart-card {
			min-height: 180px;
		}
		.context-grid {
			grid-template-rows: none;
			height: auto;
		}
		.area-context > .context-grid {
			flex: 0 0 auto;
		}
		.context-grid > .panel {
			overflow: visible;
		}
		.context-grid .runtime-panel .info-grid,
		.context-grid .runtime-panel .info-item {
			grid-template-columns: 1fr;
		}
		.context-grid .runtime-panel .info-value {
			text-align: left;
		}
		.chart-grid,
		.details-grid,
		.info-grid,
		.config-summary,
		.runtime-timeline {
			grid-template-columns: 1fr;
		}

		.context-grid .runtime-timeline,
		.context-grid .runtime-footprint {
			grid-template-columns: 1fr;
		}

		.context-grid .runtime-timeline span {
			font-size: 10.5px;
		}

		.context-grid .runtime-timeline strong {
			font-size: 14px;
		}

		.port-flow {
			grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
		}

		.port-flow em {
			grid-column: 1 / -1;
			justify-self: start;
		}

		.live-stack {
			grid-template-rows: minmax(260px, auto) minmax(260px, auto);
		}
	}
</style>
