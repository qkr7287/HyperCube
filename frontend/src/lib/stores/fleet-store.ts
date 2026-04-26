import { browser } from '$app/environment';
import { base } from '$app/paths';
import { writable, get } from 'svelte/store';

export type TimeRange = '1m' | '5m' | '1h' | '24h' | '7d';
export type FleetHealth = 'healthy' | 'warning' | 'critical' | 'offline' | 'stale';

type AgentApiRow = {
	id: string;
	hostname: string;
	ip_address: string;
	status: string;
	is_active: boolean;
	last_seen_at: string | null;
};

type ContainerApiRow = {
	container_id: string;
	agent: string;
	status: string;
};

type GpuMetric = {
	index?: number;
	vendor?: string;
	model?: string;
	usage?: number;
	temperature?: number;
	memoryTotal?: number;
	memoryUsed?: number;
};

type SystemMetricRow = {
	agent: string;
	agent_hostname: string;
	cpu_usage: number;
	cpu_cores?: number | null;
	cpu_threads?: number | null;
	cpu_load_avg_1m?: number | null;
	memory_usage: number;
	memory_used: number;
	memory_total: number;
	disk_usage: number;
	disk_used?: number | null;
	disk_total?: number | null;
	network_rx: number;
	network_tx: number;
	processes_total?: number | null;
	processes_running?: number | null;
	logins_total?: number | null;
	gpu?: GpuMetric[];
	recorded_at: string;
};

export type FleetSummary = {
	generated_at: string;
	agent_counts: Record<string, number>;
	metric_summary: {
		cpu_avg: number;
		cpu_max: number;
		memory_avg: number;
		memory_max: number;
		disk_avg: number;
		disk_max: number;
		network_rx_rate: number;
		network_tx_rate: number;
		gpu_avg: number;
		gpu_max: number;
	};
	operations_summary: {
		processes_total: number;
		processes_avg: number;
		logins_total: number;
		logins_avg: number;
		fresh_agents: number;
		warm_agents: number;
		stale_agents: number;
		expired_agents: number;
	};
	container_summary: Record<string, number>;
	top_risks: FleetRisk[];
};

export type FleetRisk = {
	agent_id: string;
	hostname: string;
	health: FleetHealth;
	reason: string;
	cpu_usage: number;
	memory_usage: number;
	disk_usage: number;
	gpu_usage: number;
	last_seen_at: string | null;
	metric_timestamp: string | null;
};

export type FleetAgentRow = {
	agent: AgentApiRow;
	health: FleetHealth;
	health_reasons: string[];
	latest: {
		timestamp: string | null;
		cpu_usage: number;
		cpu_cores: number | null;
		cpu_threads: number | null;
		cpu_load_avg_1m: number | null;
		memory_usage: number;
		memory_used: number;
		memory_total: number;
		disk_usage: number;
		disk_used: number | null;
		disk_total: number | null;
		network_rx_rate: number;
		network_tx_rate: number;
		processes_total: number | null;
		processes_running: number | null;
		logins_total: number | null;
		gpu_usage: number;
		gpu_temperature: number | null;
		gpu_memory_used: number | null;
		gpu_memory_total: number | null;
		gpu_count: number;
	} | null;
	containers: Record<string, number>;
	sparkline: {
		cpu: number[];
		memory: number[];
		disk: number[];
		gpu: number[];
		rx: number[];
		tx: number[];
	};
};

export type FleetHistoryPoint = {
	timestamp: string;
	agent_count: number;
	cpu_avg: number;
	cpu_max: number;
	memory_avg: number;
	memory_max: number;
	disk_avg: number;
	disk_max: number;
	network_rx_rate: number;
	network_tx_rate: number;
	gpu_avg: number;
	gpu_max: number;
};

export type FleetAgentSeries = {
	agent_id: string;
	hostname: string;
	color: string;
	cpu: number[];
	memory: number[];
	disk: number[];
	network: number[];
	gpu: number[];
};

export type AgentHistoryPoint = {
	timestamp: string;
	cpu_usage: number;
	memory_usage: number;
	disk_usage: number;
	network_rx_rate: number;
	network_tx_rate: number;
	processes_total: number | null;
	processes_running: number | null;
	logins_total: number | null;
	gpu_usage: number;
	gpu_temperature: number | null;
};

export const fleetSummary = writable<FleetSummary | null>(null);
export const fleetAgents = writable<FleetAgentRow[]>([]);
export const fleetHistory = writable<FleetHistoryPoint[]>([]);
export const fleetAgentSeries = writable<FleetAgentSeries[]>([]);
export const selectedAgentHistory = writable<AgentHistoryPoint[]>([]);
export const fleetLoading = writable(false);
export const fleetError = writable('');
export const fleetConnected = writable(false);
export const lastFleetUpdate = writable<Date | null>(null);

// Bucket size — 조회 단위 그대로 사용. range 라벨이 곧 bucket 크기.
// 1m = 1분 단위, 5m = 5분 단위, 1h = 1시간 단위, 24h = 1일 단위, 7d = 1주일 단위.
const BUCKET_SECONDS: Record<TimeRange, number> = {
	'1m': 60,        // 1분 bucket
	'5m': 300,       // 5분 bucket
	'1h': 3600,      // 1시간 bucket
	'24h': 86400,    // 1일 bucket
	'7d': 604800,    // 1주일 bucket
};
// 차트에 표시할 bucket 개수. raw row 부담을 고려해 24h/7d는 더 적게.
export const SPARKLINE_POINTS: Record<TimeRange, number> = {
	'1m': 10,   // 1분 × 10 = 10분 창
	'5m': 10,   // 5분 × 10 = 50분 창
	'1h': 12,   // 1시간 × 12 = 12시간 창
	'24h': 7,   // 1일 × 7 = 7일 창
	'7d': 4,    // 1주일 × 4 = 4주 창
};
// Backend retention에 맞춘 raw data 요청 범위. bucket × points 보다 조금 더 넉넉히.
const API_RANGE: Record<TimeRange, string> = {
	'1m': '30m',
	'5m': '6h',
	'1h': '24h',
	'24h': '7d',
	'7d': '7d',
};
// raw row 상한. backend `limit` 한도(2000)에 맞춰 모두 2000으로 클램프.
const RANGE_LIMITS: Record<TimeRange, number> = { '1m': 500, '5m': 2000, '1h': 2000, '24h': 2000, '7d': 2000 };
// Per-agent 상세 history에서 사용할 bucket 개수.
const HISTORY_LIMITS: Record<TimeRange, number> = { '1m': 30, '5m': 24, '1h': 24, '24h': 7, '7d': 4 };
// Poll 주기 — bucket 크기에 맞춰 점점 느리게. 너무 자주 polling 하면 백엔드 부담.
const POLL_INTERVAL_MS: Record<TimeRange, number> = {
	'1m': 10000,     // 10s
	'5m': 30000,     // 30s
	'1h': 60000,     // 1 min
	'24h': 600000,   // 10 min
	'7d': 3600000,   // 1 hr
};
const AGENT_COLORS = ['#30d5c8', '#f87171', '#60a5fa', '#fbbf24', '#a78bfa', '#34d399', '#fb7185', '#38bdf8', '#c084fc', '#2dd4bf'];
const HEALTH_ORDER: Record<FleetHealth, number> = {
	critical: 0,
	warning: 1,
	stale: 2,
	offline: 3,
	healthy: 4,
};

let token = '';
let range: TimeRange = '1h';
let pollTimer: ReturnType<typeof setInterval> | null = null;
let selectedAgentId: string | null = null;

function unwrap<T>(payload: any): T {
	return (payload?.data ?? payload) as T;
}

async function api<T>(path: string): Promise<T> {
	const res = await fetch(`${base}${path}`, {
		headers: { Authorization: `Bearer ${token}` },
	});
	const json = await res.json().catch(() => ({}));
	if (!res.ok) {
		const detail = json?.error?.detail ?? json?.detail ?? json?.error ?? `HTTP ${res.status}`;
		throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
	}
	return unwrap<T>(json);
}

type SystemBucketRow = {
	agent: string;
	bucket_epoch: number;
	bucket_start: string;
	cpu_avg: number;
	cpu_max: number;
	memory_avg: number;
	memory_max: number;
	disk_avg: number;
	disk_max: number;
	network_rx_max: number;
	network_tx_max: number;
	sample_count: number;
};

export async function refreshFleet() {
	if (!browser || !token) return;
	fleetLoading.set(true);
	fleetError.set('');

	try {
		const bucketSec = BUCKET_SECONDS[range];
		const points = SPARKLINE_POINTS[range];
		// bucket × points 만큼의 윈도우를 from_time/to_time으로 보내야 점이
		// 충분히 채워진다. ?range=만 보내면 backend가 최근 한 bucket만 반환해
		// 점이 1개로 평탄해진다.
		const now = Date.now();
		const fromTime = new Date(now - bucketSec * points * 1000).toISOString();
		const toTime = new Date(now).toISOString();
		const [agentsPayload, containersPayload, latestPayload, bucketsPayload] = await Promise.all([
			api<{ results: AgentApiRow[] }>('/api/agents/?status=approved&page_size=200&ordering=hostname'),
			api<{ results: ContainerApiRow[] }>('/api/containers/?page_size=1000&ordering=agent'),
			// 카드의 "latest" 값(현재 CPU/메모리 % 등)은 raw row에서 가장 최근 1건으로 추출.
			api<SystemMetricRow[]>(`/api/metrics/system/?limit=200&ordering=recorded_at`),
			api<{ bucket_seconds: number; results: SystemBucketRow[] }>(
				`/api/metrics/system/buckets/?from_time=${encodeURIComponent(fromTime)}&to_time=${encodeURIComponent(toTime)}&bucket=${bucketSec}`,
			),
		]);

		const agents = agentsPayload.results ?? [];
		const containers = containersPayload.results ?? [];
		const latestRaw = Array.isArray(latestPayload) ? latestPayload : [];
		const buckets = bucketsPayload?.results ?? [];
		const rows = buildRows(agents, containers, latestRaw, buckets, range);
		const history = buildHistoryFromBuckets(buckets, range);

		fleetAgents.set(rows);
		fleetHistory.set(history);
		fleetAgentSeries.set(buildAgentSeriesFromBuckets(agents, buckets, range));
		fleetSummary.set(buildSummary(rows));
		fleetConnected.set(true);
		lastFleetUpdate.set(new Date());

		if (selectedAgentId) await loadSelectedAgent(selectedAgentId);
	} catch (err: any) {
		fleetConnected.set(false);
		fleetError.set(err?.message || 'Failed to refresh the fleet dashboard.');
	} finally {
		fleetLoading.set(false);
	}
}

export async function loadSelectedAgent(agentId: string) {
	if (!browser || !token || !agentId) return;
	selectedAgentId = agentId;
	try {
		const bucketSec = BUCKET_SECONDS[range];
		const points = SPARKLINE_POINTS[range];
		const now = Date.now();
		const fromTime = new Date(now - bucketSec * points * 1000).toISOString();
		const toTime = new Date(now).toISOString();
		const payload = await api<{ bucket_seconds: number; results: SystemBucketRow[] }>(
			`/api/metrics/system/buckets/?agent=${encodeURIComponent(agentId)}&from_time=${encodeURIComponent(fromTime)}&to_time=${encodeURIComponent(toTime)}&bucket=${bucketSec}`,
		);
		const buckets = payload?.results ?? [];
		const history: AgentHistoryPoint[] = buckets.map((b) => ({
			timestamp: b.bucket_start,
			cpu_usage: b.cpu_avg,
			memory_usage: b.memory_avg,
			disk_usage: b.disk_avg,
			network_rx_rate: 0,
			network_tx_rate: 0,
			processes_total: null,
			processes_running: null,
			logins_total: null,
			gpu_usage: 0,
			gpu_temperature: null,
		}));
		selectedAgentHistory.set(history);
	} catch {
		selectedAgentHistory.set([]);
	}
}

function startPollTimer() {
	if (pollTimer) clearInterval(pollTimer);
	pollTimer = setInterval(refreshFleet, POLL_INTERVAL_MS[range]);
}

export function startFleetMonitoring(accessToken: string, initialRange: TimeRange = '1h') {
	stopFleetMonitoring();
	token = accessToken;
	range = initialRange;
	refreshFleet();
	startPollTimer();
}

export function stopFleetMonitoring() {
	if (pollTimer) {
		clearInterval(pollTimer);
		pollTimer = null;
	}
	token = '';
	selectedAgentId = null;
	fleetConnected.set(false);
	fleetAgentSeries.set([]);
	selectedAgentHistory.set([]);
}

export async function setFleetRange(nextRange: TimeRange) {
	range = nextRange;
	await refreshFleet();
	startPollTimer();
}

export function currentAgents(): FleetAgentRow[] {
	return get(fleetAgents);
}

function buildRows(
	agents: AgentApiRow[],
	containers: ContainerApiRow[],
	metrics: SystemMetricRow[],
	buckets: SystemBucketRow[],
	rangeKey: TimeRange,
): FleetAgentRow[] {
	const containersByAgent = groupContainers(containers);
	const metricsByAgent = groupMetrics(metrics);
	// 카드 sparkline 은 raw `/metrics/system/?limit=200` 가 아니라 buckets 엔드포인트
	// 데이터로 생성한다. raw 200 row 는 ~8 분 분량이라 24h/7d 는 물론 1h sparkline
	// 도 평탄해진다. buckets 는 from_time/to_time + bucket=range 단위로 받아 필요한
	// 점 개수가 항상 채워짐.
	const bucketsByAgent = new Map<string, SystemBucketRow[]>();
	for (const r of buckets) {
		const list = bucketsByAgent.get(r.agent) ?? [];
		list.push(r);
		bucketsByAgent.set(r.agent, list);
	}

	return agents
		.map((agent) => {
			const agentMetrics = metricsByAgent.get(agent.id) ?? [];
			const latest = latestFromHistory(agentMetrics);
			const containerSummary = containersByAgent.get(agent.id) ?? emptyContainerSummary();
			const [health, reasons] = classifyHealth(agent, latest, containerSummary);

			const agentBuckets = bucketsByAgent.get(agent.id) ?? [];
			return {
				agent,
				health,
				health_reasons: reasons,
				latest,
				containers: containerSummary,
				sparkline: {
					cpu: bucketsToSparkline(agentBuckets, rangeKey, (b) => b.cpu_avg),
					memory: bucketsToSparkline(agentBuckets, rangeKey, (b) => b.memory_avg),
					disk: bucketsToSparkline(agentBuckets, rangeKey, (b) => b.disk_avg),
					// GPU 는 system buckets 에 없어 0 fallback. agent series 의 gpu 도 동일.
					gpu: bucketsToSparkline(agentBuckets, rangeKey, () => 0),
					// network_rx_max / tx_max 는 boot 이후 누적 바이트. sparkline 은 rate 이므로
					// bucket 간 delta / bucket 길이로 변환.
					rx: bucketsToRateSparkline(agentBuckets, rangeKey, (b) => b.network_rx_max),
					tx: bucketsToRateSparkline(agentBuckets, rangeKey, (b) => b.network_tx_max),
				},
			};
		})
		.sort((a, b) => {
			const pressureA = maxUsage(a);
			const pressureB = maxUsage(b);
			return HEALTH_ORDER[a.health] - HEALTH_ORDER[b.health] || pressureB - pressureA || a.agent.hostname.localeCompare(b.agent.hostname);
		});
}

function groupContainers(containers: ContainerApiRow[]): Map<string, Record<string, number>> {
	const map = new Map<string, Record<string, number>>();
	for (const container of containers) {
		const summary = map.get(container.agent) ?? emptyContainerSummary();
		const status = normalizeStatus(container.status);
		summary.total += 1;
		summary[status] = (summary[status] ?? 0) + 1;
		summary.non_running = Math.max(0, summary.total - (summary.running ?? 0));
		summary.problem = (summary.restarting ?? 0) + (summary.dead ?? 0);
		map.set(container.agent, summary);
	}
	return map;
}

function groupMetrics(metrics: SystemMetricRow[]): Map<string, SystemMetricRow[]> {
	const map = new Map<string, SystemMetricRow[]>();
	for (const row of metrics) {
		const list = map.get(row.agent) ?? [];
		list.push(row);
		map.set(row.agent, list);
	}
	for (const list of map.values()) {
		list.sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());
	}
	return map;
}

function latestFromHistory(rows: SystemMetricRow[]): FleetAgentRow['latest'] {
	const latest = rows.at(-1);
	if (!latest) return null;
	// "갑자기 0" 버그 원인: 직전 row의 network_rx가 우연히 0이면 networkRate의
	// zero-guard가 발동해 rate=0을 반환함. 최근 N개 row를 거꾸로 훑어 prev/curr 둘
	// 다 유효한 delta를 찾으면 그 rate를 latest로 사용 — 한 포인트의 노이즈에
	// 카드 전체가 0으로 보이는 상황을 방지.
	const [rx, tx] = resolveLatestNetworkRate(rows);
	const gpuStats = gpuSummary(latest.gpu);

	return {
		timestamp: latest.recorded_at,
		cpu_usage: num(latest.cpu_usage),
		cpu_cores: latest.cpu_cores ?? null,
		cpu_threads: latest.cpu_threads ?? null,
		cpu_load_avg_1m: latest.cpu_load_avg_1m ?? null,
		memory_usage: num(latest.memory_usage),
		memory_used: num(latest.memory_used),
		memory_total: num(latest.memory_total),
		disk_usage: num(latest.disk_usage),
		disk_used: latest.disk_used ?? null,
		disk_total: latest.disk_total ?? null,
		network_rx_rate: rx,
		network_tx_rate: tx,
		processes_total: latest.processes_total ?? null,
		processes_running: latest.processes_running ?? null,
		logins_total: latest.logins_total ?? null,
		gpu_usage: gpuStats.usage,
		gpu_temperature: gpuStats.temperature,
		gpu_memory_used: gpuStats.memoryUsed,
		gpu_memory_total: gpuStats.memoryTotal,
		gpu_count: gpuStats.count,
	};
}

function classifyHealth(
	agent: AgentApiRow,
	latest: FleetAgentRow['latest'],
	containers: Record<string, number>,
): [FleetHealth, string[]] {
	if (!agent.is_active) return ['offline', ['Agent is offline']];
	if (!latest) return ['stale', ['No recent metrics']];

	const age = metricAge(latest.timestamp);
	if (age == null || age > 60) return ['stale', ['Metrics older than 60 seconds']];

	const criticalReasons: string[] = [];
	if (latest.cpu_usage >= 90) criticalReasons.push('CPU >= 90%');
	if (latest.memory_usage >= 90) criticalReasons.push('Memory >= 90%');
	if (latest.disk_usage >= 90) criticalReasons.push('Disk >= 90%');
	if (latest.gpu_usage >= 95) criticalReasons.push('GPU >= 95%');
	if ((containers.dead ?? 0) > 0) criticalReasons.push('Dead container detected');
	if (criticalReasons.length) return ['critical', criticalReasons];

	const warningReasons: string[] = [];
	if (age > 30) warningReasons.push('Metrics older than 30 seconds');
	if (latest.cpu_usage >= 70) warningReasons.push('CPU >= 70%');
	if (latest.memory_usage >= 75) warningReasons.push('Memory >= 75%');
	if (latest.disk_usage >= 80) warningReasons.push('Disk >= 80%');
	if (latest.gpu_usage >= 80) warningReasons.push('GPU >= 80%');
	if ((containers.restarting ?? 0) > 0) warningReasons.push('Restarting container detected');
	return warningReasons.length ? ['warning', warningReasons] : ['healthy', []];
}

function buildSummary(rows: FleetAgentRow[]): FleetSummary {
	const counts = { total: rows.length, online: 0, offline: 0, warning: 0, critical: 0, stale: 0, healthy: 0 };
	const containerSummary = emptyContainerSummary();
	const cpu: number[] = [];
	const memory: number[] = [];
	const disk: number[] = [];
	const gpu: number[] = [];
	const processes: number[] = [];
	const logins: number[] = [];
	const freshness = { fresh_agents: 0, warm_agents: 0, stale_agents: 0, expired_agents: 0 };
	let rx = 0;
	let tx = 0;

	for (const row of rows) {
		counts[row.health] += 1;
		if (row.agent.is_active) counts.online += 1;

		for (const key of Object.keys(containerSummary)) {
			containerSummary[key] += row.containers[key] ?? 0;
		}

		if (row.latest) {
			cpu.push(row.latest.cpu_usage);
			memory.push(row.latest.memory_usage);
			disk.push(row.latest.disk_usage);
			if (row.latest.gpu_count > 0) gpu.push(row.latest.gpu_usage);
			rx += row.latest.network_rx_rate;
			tx += row.latest.network_tx_rate;
			if (typeof row.latest.processes_total === 'number') processes.push(row.latest.processes_total);
			if (typeof row.latest.logins_total === 'number') logins.push(row.latest.logins_total);

			const age = metricAge(row.latest.timestamp);
			if (age == null || age > 60) freshness.expired_agents += 1;
			else if (age > 30) freshness.stale_agents += 1;
			else if (age > 15) freshness.warm_agents += 1;
			else freshness.fresh_agents += 1;
		} else {
			freshness.expired_agents += 1;
		}
	}

	return {
		generated_at: new Date().toISOString(),
		agent_counts: counts,
		metric_summary: {
			cpu_avg: avg(cpu),
			cpu_max: max(cpu),
			memory_avg: avg(memory),
			memory_max: max(memory),
			disk_avg: avg(disk),
			disk_max: max(disk),
			network_rx_rate: rx,
			network_tx_rate: tx,
			gpu_avg: avg(gpu),
			gpu_max: max(gpu),
		},
		operations_summary: {
			processes_total: sum(processes),
			processes_avg: avg(processes),
			logins_total: sum(logins),
			logins_avg: avg(logins),
			...freshness,
		},
		container_summary: containerSummary,
		top_risks: rows
			.filter((row) => row.health !== 'healthy')
			.slice(0, 8)
			.map((row) => ({
				agent_id: row.agent.id,
				hostname: row.agent.hostname,
				health: row.health,
				reason: row.health_reasons.slice(0, 2).join(', ') || row.health,
				cpu_usage: row.latest?.cpu_usage ?? 0,
				memory_usage: row.latest?.memory_usage ?? 0,
				disk_usage: row.latest?.disk_usage ?? 0,
				gpu_usage: row.latest?.gpu_usage ?? 0,
				last_seen_at: row.agent.last_seen_at,
				metric_timestamp: row.latest?.timestamp ?? null,
			})),
	};
}

function bucketSlots(rangeKey: TimeRange): number[] {
	const sec = BUCKET_SECONDS[rangeKey];
	const points = SPARKLINE_POINTS[rangeKey];
	const now = Math.floor(Date.now() / 1000 / sec) * sec;
	const out: number[] = [];
	for (let i = points - 1; i >= 0; i -= 1) out.push(now - i * sec);
	return out;
}

function buildHistoryFromBuckets(rows: SystemBucketRow[], rangeKey: TimeRange): FleetHistoryPoint[] {
	const slots = bucketSlots(rangeKey);
	const bucketSec = BUCKET_SECONDS[rangeKey];
	// Group rows by bucket_epoch — fleet-wide aggregation across agents.
	const byBucket = new Map<number, SystemBucketRow[]>();
	for (const r of rows) {
		const arr = byBucket.get(r.bucket_epoch) ?? [];
		arr.push(r);
		byBucket.set(r.bucket_epoch, arr);
	}
	// Per-agent cumulative byte counters per bucket — fleet rate 는 agent 별 delta 합산.
	// network_rx_max 는 boot 이후 누적이므로 같은 agent 의 직전 bucket 과 비교해야 의미.
	const cumulativeByAgent = new Map<string, Map<number, { rx: number; tx: number }>>();
	for (const r of rows) {
		const m = cumulativeByAgent.get(r.agent) ?? new Map();
		m.set(r.bucket_epoch, { rx: r.network_rx_max ?? 0, tx: r.network_tx_max ?? 0 });
		cumulativeByAgent.set(r.agent, m);
	}

	const series: FleetHistoryPoint[] = [];
	type Snapshot = { cpuAvg: number; cpuMax: number; memAvg: number; memMax: number; diskAvg: number; diskMax: number; gpuAvg: number; gpuMax: number; agents: number };
	let lastReal: Snapshot | null = null;
	let firstRealIdx = -1;

	const clampPct = (v: number) => Math.max(0, Math.min(100, Number.isFinite(v) ? v : 0));
	for (let i = 0; i < slots.length; i += 1) {
		const slot = slots[i];
		const prevSlot = i > 0 ? slots[i - 1] : null;
		// Sum rx/tx rate across all agents that have both this slot and previous slot data.
		let rxRate = 0;
		let txRate = 0;
		if (prevSlot != null) {
			for (const m of cumulativeByAgent.values()) {
				const cur = m.get(slot);
				const prev = m.get(prevSlot);
				if (cur && prev && cur.rx >= prev.rx) rxRate += (cur.rx - prev.rx) / bucketSec;
				if (cur && prev && cur.tx >= prev.tx) txRate += (cur.tx - prev.tx) / bucketSec;
			}
		}
		const items = byBucket.get(slot);
		if (items && items.length) {
			const cpuAvg = clampPct(avg(items.map((it) => it.cpu_avg)));
			const cpuMax = clampPct(max(items.map((it) => it.cpu_max)));
			const memAvg = clampPct(avg(items.map((it) => it.memory_avg)));
			const memMax = clampPct(max(items.map((it) => it.memory_max)));
			const diskAvg = clampPct(avg(items.map((it) => it.disk_avg)));
			const diskMax = clampPct(max(items.map((it) => it.disk_max)));
			// GPU 는 system_metrics 에 별도 컬럼이 없어 buckets 응답에도 없음 → 0.
			// 정확한 fleet GPU trend 가 필요하면 backend 에 gpu_usage 컬럼 추가 후 buckets 에 포함시켜야 함.
			const gpuAvg = 0;
			const gpuMax = 0;
			lastReal = { cpuAvg, cpuMax, memAvg, memMax, diskAvg, diskMax, gpuAvg, gpuMax, agents: items.length };
			if (firstRealIdx < 0) firstRealIdx = i;
			series.push({
				timestamp: new Date(slot * 1000).toISOString(),
				agent_count: items.length,
				cpu_avg: cpuAvg,
				cpu_max: cpuMax,
				memory_avg: memAvg,
				memory_max: memMax,
				disk_avg: diskAvg,
				disk_max: diskMax,
				network_rx_rate: rxRate,
				network_tx_rate: txRate,
				gpu_avg: gpuAvg,
				gpu_max: gpuMax,
			});
		} else {
			series.push({
				timestamp: new Date(slot * 1000).toISOString(),
				agent_count: lastReal?.agents ?? 0,
				cpu_avg: lastReal?.cpuAvg ?? 0,
				cpu_max: lastReal?.cpuMax ?? 0,
				memory_avg: lastReal?.memAvg ?? 0,
				memory_max: lastReal?.memMax ?? 0,
				disk_avg: lastReal?.diskAvg ?? 0,
				disk_max: lastReal?.diskMax ?? 0,
				network_rx_rate: rxRate,
				network_tx_rate: txRate,
				gpu_avg: lastReal?.gpuAvg ?? 0,
				gpu_max: lastReal?.gpuMax ?? 0,
			});
		}
	}

	// backward-fill: 첫 real value 이전 슬롯을 첫 값으로 평탄화
	if (firstRealIdx > 0) {
		const first = series[firstRealIdx];
		for (let i = 0; i < firstRealIdx; i += 1) {
			series[i] = {
				...series[i],
				cpu_avg: first.cpu_avg, cpu_max: first.cpu_max,
				memory_avg: first.memory_avg, memory_max: first.memory_max,
				disk_avg: first.disk_avg, disk_max: first.disk_max,
				gpu_avg: first.gpu_avg, gpu_max: first.gpu_max,
				agent_count: first.agent_count,
			};
		}
	}

	return series;
}

function buildAgentSeriesFromBuckets(
	agents: AgentApiRow[],
	rows: SystemBucketRow[],
	rangeKey: TimeRange,
): FleetAgentSeries[] {
	const slots = bucketSlots(rangeKey);
	const slotIndex = new Map(slots.map((s, i) => [s, i]));
	const byAgent = new Map<string, Map<number, SystemBucketRow>>();
	for (const r of rows) {
		const m = byAgent.get(r.agent) ?? new Map<number, SystemBucketRow>();
		m.set(r.bucket_epoch, r);
		byAgent.set(r.agent, m);
	}

	function fillSeries(values: (number | null)[]): number[] {
		// forward fill from the first real value
		let last: number | null = null;
		const out = values.slice();
		for (let i = 0; i < out.length; i += 1) {
			if (out[i] !== null) last = out[i];
			else if (last !== null) out[i] = last;
		}
		// backward fill leading nulls with first real value
		let first: number | null = null;
		for (const v of out) if (v !== null) { first = v; break; }
		if (first !== null) {
			for (let i = 0; i < out.length; i += 1) if (out[i] === null) out[i] = first;
		} else {
			for (let i = 0; i < out.length; i += 1) out[i] = 0;
		}
		return out as number[];
	}

	return agents.map((agent, index) => {
		const m = byAgent.get(agent.id) ?? new Map<number, SystemBucketRow>();
		const cpu: (number | null)[] = new Array(slots.length).fill(null);
		const mem: (number | null)[] = new Array(slots.length).fill(null);
		const disk: (number | null)[] = new Array(slots.length).fill(null);
		const gpu: (number | null)[] = new Array(slots.length).fill(null);
		const net: (number | null)[] = new Array(slots.length).fill(null);
		for (const [bucket, row] of m) {
			const idx = slotIndex.get(bucket);
			if (idx === undefined) continue;
			cpu[idx] = row.cpu_avg;
			mem[idx] = row.memory_avg;
			disk[idx] = row.disk_avg;
			gpu[idx] = 0;
			net[idx] = 0;
		}
		return {
			agent_id: agent.id,
			hostname: agent.hostname,
			color: AGENT_COLORS[index % AGENT_COLORS.length],
			cpu: fillSeries(cpu),
			memory: fillSeries(mem),
			disk: fillSeries(disk),
			gpu: fillSeries(gpu),
			network: fillSeries(net),
		};
	});
}

function buildHistory(metrics: SystemMetricRow[], rangeKey: TimeRange): FleetHistoryPoint[] {
	const buckets = new Map<number, { rows: SystemMetricRow[]; rx: number; tx: number; agents: Set<string> }>();
	const previousByAgent = new Map<string, SystemMetricRow>();
	const sorted = [...metrics].sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());

	for (const row of sorted) {
		const bucket = bucketEpoch(row.recorded_at, BUCKET_SECONDS[rangeKey]);
		const item = buckets.get(bucket) ?? { rows: [], rx: 0, tx: 0, agents: new Set<string>() };
		const previous = previousByAgent.get(row.agent);
		const [rx, tx] = networkRate(previous, row);
		item.rows.push(row);
		item.rx += rx;
		item.tx += tx;
		item.agents.add(row.agent);
		buckets.set(bucket, item);
		previousByAgent.set(row.agent, row);
	}

	// 카드의 SPARKLINE_POINTS와 동일한 점 개수만큼 슬롯을 만들어 빈 bucket을 채운다.
	// 데이터가 1개 bucket밖에 없으면 24h/7d range에서 그래프가 한 점만 그려져
	// "선이 안 보이는" 문제가 됨. backward/forward-fill로 평탄선이라도 그리도록.
	const bucketSec = BUCKET_SECONDS[rangeKey];
	const points = SPARKLINE_POINTS[rangeKey];
	const nowBucket = Math.floor(Date.now() / 1000 / bucketSec) * bucketSec;
	const slots: number[] = [];
	for (let i = points - 1; i >= 0; i -= 1) slots.push(nowBucket - i * bucketSec);

	const realByBucket = buckets;
	const series: FleetHistoryPoint[] = [];
	let lastReal: { rx: number; tx: number; cpuAvg: number; cpuMax: number; memAvg: number; memMax: number; diskAvg: number; diskMax: number; gpuAvg: number; gpuMax: number; agents: number } | null = null;

	const computed = new Map<number, FleetHistoryPoint>();
	for (const [bucket, item] of realByBucket) {
		const cpu = item.rows.map((row) => num(row.cpu_usage));
		const memory = item.rows.map((row) => num(row.memory_usage));
		const disk = item.rows.map((row) => num(row.disk_usage));
		const gpu = item.rows.map((row) => gpuUsage(row.gpu)).filter((value) => value > 0);
		computed.set(bucket, {
			timestamp: new Date(bucket * 1000).toISOString(),
			agent_count: item.agents.size,
			cpu_avg: avg(cpu),
			cpu_max: max(cpu),
			memory_avg: avg(memory),
			memory_max: max(memory),
			disk_avg: avg(disk),
			disk_max: max(disk),
			network_rx_rate: item.rx,
			network_tx_rate: item.tx,
			gpu_avg: avg(gpu),
			gpu_max: max(gpu),
		});
	}

	for (const slot of slots) {
		const real = computed.get(slot);
		if (real) {
			series.push(real);
			lastReal = {
				rx: real.network_rx_rate,
				tx: real.network_tx_rate,
				cpuAvg: real.cpu_avg, cpuMax: real.cpu_max,
				memAvg: real.memory_avg, memMax: real.memory_max,
				diskAvg: real.disk_avg, diskMax: real.disk_max,
				gpuAvg: real.gpu_avg, gpuMax: real.gpu_max,
				agents: real.agent_count,
			};
		} else {
			series.push({
				timestamp: new Date(slot * 1000).toISOString(),
				agent_count: lastReal?.agents ?? 0,
				cpu_avg: lastReal?.cpuAvg ?? 0,
				cpu_max: lastReal?.cpuMax ?? 0,
				memory_avg: lastReal?.memAvg ?? 0,
				memory_max: lastReal?.memMax ?? 0,
				disk_avg: lastReal?.diskAvg ?? 0,
				disk_max: lastReal?.diskMax ?? 0,
				network_rx_rate: 0,
				network_tx_rate: 0,
				gpu_avg: lastReal?.gpuAvg ?? 0,
				gpu_max: lastReal?.gpuMax ?? 0,
			});
		}
	}

	// backward-fill: 처음 몇 개 슬롯이 비어 0/0인 경우 첫 실제 값으로 덮어쓴다.
	let firstRealIdx = -1;
	for (let i = 0; i < series.length; i += 1) {
		if (computed.has(slots[i])) { firstRealIdx = i; break; }
	}
	if (firstRealIdx > 0) {
		const firstReal = series[firstRealIdx];
		for (let i = 0; i < firstRealIdx; i += 1) {
			series[i] = {
				...series[i],
				cpu_avg: firstReal.cpu_avg, cpu_max: firstReal.cpu_max,
				memory_avg: firstReal.memory_avg, memory_max: firstReal.memory_max,
				disk_avg: firstReal.disk_avg, disk_max: firstReal.disk_max,
				gpu_avg: firstReal.gpu_avg, gpu_max: firstReal.gpu_max,
				agent_count: firstReal.agent_count,
			};
		}
	}

	return series;
}

function buildAgentSeries(
	agents: AgentApiRow[],
	metrics: SystemMetricRow[],
	timestamps: string[],
	rangeKey: TimeRange,
): FleetAgentSeries[] {
	const timestampToIndex = new Map(timestamps.map((timestamp, index) => [timestamp, index]));
	const previousByAgent = new Map<string, SystemMetricRow>();
	const valuesByAgent = new Map<string, Map<string, { cpu: number[]; memory: number[]; disk: number[]; network: number[]; gpu: number[] }>>();
	const sorted = [...metrics].sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime());

	for (const row of sorted) {
		const bucket = new Date(bucketEpoch(row.recorded_at, BUCKET_SECONDS[rangeKey]) * 1000).toISOString();
		if (!timestampToIndex.has(bucket)) continue;
		const previous = previousByAgent.get(row.agent);
		const [rx, tx] = networkRate(previous, row);
		const bucketMap = valuesByAgent.get(row.agent) ?? new Map();
		const item = bucketMap.get(bucket) ?? { cpu: [], memory: [], disk: [], network: [], gpu: [] };
		item.cpu.push(num(row.cpu_usage));
		item.memory.push(num(row.memory_usage));
		item.disk.push(num(row.disk_usage));
		item.network.push(rx + tx);
		const gpuValue = gpuUsage(row.gpu);
		if (gpuValue > 0) item.gpu.push(gpuValue);
		bucketMap.set(bucket, item);
		valuesByAgent.set(row.agent, bucketMap);
		previousByAgent.set(row.agent, row);
	}

	return agents.map((agent, index) => {
		const bucketMap = valuesByAgent.get(agent.id) ?? new Map();
		return {
			agent_id: agent.id,
			hostname: agent.hostname,
			color: AGENT_COLORS[index % AGENT_COLORS.length],
			cpu: timestamps.map((timestamp) => avg(bucketMap.get(timestamp)?.cpu ?? [])),
			memory: timestamps.map((timestamp) => avg(bucketMap.get(timestamp)?.memory ?? [])),
			disk: timestamps.map((timestamp) => avg(bucketMap.get(timestamp)?.disk ?? [])),
			network: timestamps.map((timestamp) => avg(bucketMap.get(timestamp)?.network ?? [])),
			gpu: timestamps.map((timestamp) => avg(bucketMap.get(timestamp)?.gpu ?? [])),
		};
	});
}

function buildAgentHistory(rows: SystemMetricRow[]): AgentHistoryPoint[] {
	let previous: SystemMetricRow | undefined;
	return [...rows]
		.sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime())
		.map((row) => {
			const [rx, tx] = networkRate(previous, row);
			previous = row;
			const gpuStats = gpuSummary(row.gpu);
			return {
				timestamp: row.recorded_at,
				cpu_usage: num(row.cpu_usage),
				memory_usage: num(row.memory_usage),
				disk_usage: num(row.disk_usage),
				network_rx_rate: rx,
				network_tx_rate: tx,
				processes_total: row.processes_total ?? null,
				processes_running: row.processes_running ?? null,
				logins_total: row.logins_total ?? null,
				gpu_usage: gpuStats.usage,
				gpu_temperature: gpuStats.temperature,
			};
		});
}

function emptyContainerSummary(): Record<string, number> {
	return {
		total: 0,
		running: 0,
		stopped: 0,
		paused: 0,
		exited: 0,
		created: 0,
		restarting: 0,
		dead: 0,
		non_running: 0,
		problem: 0,
	};
}

function networkRate(previous: SystemMetricRow | undefined, current: SystemMetricRow): [number, number] {
	if (!previous) return [0, 0];
	const seconds = Math.max(1, (new Date(current.recorded_at).getTime() - new Date(previous.recorded_at).getTime()) / 1000);
	const prevRx = num(previous.network_rx);
	const prevTx = num(previous.network_tx);
	const currRx = num(current.network_rx);
	const currTx = num(current.network_tx);
	// Agent 재시작 / 카운터 리셋 시 curr < prev 가 되면 Math.max로 0 반환.
	// 이전 샘플이 0이고 현재가 크게 뛰면 "첫 누적치 박제" 의심 — 해당 구간만 0.
	const rx = prevRx === 0 && currRx > 0 ? 0 : Math.max(0, currRx - prevRx) / seconds;
	const tx = prevTx === 0 && currTx > 0 ? 0 : Math.max(0, currTx - prevTx) / seconds;
	return [rx, tx];
}

// 카드에 표시할 "현재 rate"는 마지막 한 pair가 아니라 최근 N개 row 중 유효한 delta를
// 찾아서 쓴다. 이유: Backend의 한 row가 rx=0으로 기록되면 networkRate의 zero-guard
// 가 발동해 0이 반환됨 → UI가 "갑자기 0"으로 깜박이는 문제. 뒤에서부터 훑어 첫
// 양수 rate pair를 만나면 그 값을 써, 단발성 노이즈에 영향받지 않게 함.
function resolveLatestNetworkRate(rows: SystemMetricRow[]): [number, number] {
	if (rows.length < 2) return [0, 0];
	// Backend가 DB/Redis merge 타이밍 때문에 완전히 같은 recorded_at 을 가진 중복 row
	// 를 반환하는 경우가 있음 (16번 서버 관찰됨). 중복 pair는 delta 계산이 무의미하므로
	// 시간차와 byte 진전 모두 있는 pair를 뒤에서부터 찾는다.
	const curr = rows.at(-1)!;
	const currRx = num(curr.network_rx);
	const currTx = num(curr.network_tx);
	const currT = new Date(curr.recorded_at).getTime();
	for (let i = rows.length - 2; i >= 0; i -= 1) {
		const prev = rows[i];
		const prevT = new Date(prev.recorded_at).getTime();
		if (currT - prevT < 1000) continue; // 동일 timestamp 중복 skip
		const prevRx = num(prev.network_rx);
		const prevTx = num(prev.network_tx);
		if (prevRx > 0 && currRx >= prevRx && prevTx > 0 && currTx >= prevTx) {
			return networkRate(prev, curr);
		}
		// 카운터 리셋 감지 — 더 거슬러 올라가도 유효한 pair 없을 확률 높음. 중단.
		if (currRx < prevRx || currTx < prevTx) break;
	}
	return [0, 0];
}

function metricAge(timestamp?: string | null): number | null {
	if (!timestamp) return null;
	const at = new Date(timestamp).getTime();
	if (Number.isNaN(at)) return null;
	return Math.max(0, Math.floor((Date.now() - at) / 1000));
}

function bucketEpoch(iso: string, seconds: number): number {
	const epoch = Math.floor(new Date(iso).getTime() / 1000);
	return epoch - (epoch % seconds);
}

function maxUsage(row: FleetAgentRow): number {
	return Math.max(
		row.latest?.cpu_usage ?? 0,
		row.latest?.memory_usage ?? 0,
		row.latest?.disk_usage ?? 0,
		row.latest?.gpu_usage ?? 0,
	);
}

function normalizeStatus(status?: string | null): string {
	const next = (status || 'created').toLowerCase();
	const valid = new Set(['running', 'stopped', 'paused', 'exited', 'created', 'restarting', 'dead']);
	return valid.has(next) ? next : 'created';
}

function gpuUsage(gpu?: GpuMetric[] | null): number {
	return gpuSummary(gpu).usage;
}

function gpuSummary(gpu?: GpuMetric[] | null): {
	usage: number;
	temperature: number | null;
	memoryUsed: number | null;
	memoryTotal: number | null;
	count: number;
} {
	const rows = Array.isArray(gpu) ? gpu : [];
	const usages = rows.map((item) => num(item.usage)).filter((value) => value > 0);
	const temps = rows.map((item) => num(item.temperature)).filter((value) => value > 0);
	// GPU 메모리는 전체 장치 합계로 집계 (사용자는 서버 전체 VRAM 관점으로 보고 싶어함).
	const memUsed = rows.reduce((sum, item) => sum + num(item.memoryUsed), 0);
	const memTotal = rows.reduce((sum, item) => sum + num(item.memoryTotal), 0);
	return {
		usage: avg(usages),
		temperature: temps.length ? max(temps) : null,
		memoryUsed: memTotal > 0 ? memUsed : null,
		memoryTotal: memTotal > 0 ? memTotal : null,
		count: rows.length,
	};
}

/**
 * 고정 크기 슬라이딩 윈도우 sparkline 생성.
 *
 * 시계열을 `bucketSec` 단위로 묶어 `pointCount` 개수의 버킷 배열을 만든다.
 * - 배열 인덱스는 현재 시각에 정렬됨 (마지막 요소 = 최신 버킷).
 * - 시간이 한 bucket만큼 흐르면 다음 poll 때 배열이 한 칸 왼쪽으로 slide.
 *   (oldest 떨어져나가고 새 bucket이 오른쪽에 추가)
 *
 * Chart.js는 같은 인덱스의 값 변화를 애니메이션하므로, 이 방식이 "물 흐르듯"
 * 이어지는 streaming 효과의 핵심이다. 각 poll 마다 downsample로 재샘플링하면
 * 인덱스 ↔ 시각 정합이 깨져서 통째로 redraw되는 느낌이 남.
 */
/**
 * Cumulative counter buckets → rate sparkline.
 *
 * network_rx_max / tx_max 는 boot 이후 누적 바이트라 그대로 sparkline 에 넣으면
 * 단조 증가 직선이 된다. bucket-to-bucket delta 를 bucket 길이로 나눠 평균 rate
 * (B/s) 를 만든다. 첫 bucket 은 직전이 없으니 0.
 */
function bucketsToRateSparkline(
	rows: SystemBucketRow[],
	rangeKey: TimeRange,
	cumulativeFn: (row: SystemBucketRow) => number,
): number[] {
	const bucketSec = BUCKET_SECONDS[rangeKey];
	const points = SPARKLINE_POINTS[rangeKey];
	const now = Math.floor(Date.now() / 1000);
	const latestBucket = Math.floor(now / bucketSec) * bucketSec;
	// slot index → cumulative bytes 매핑
	const cumulative = new Array<number | null>(points).fill(null);
	for (const r of rows) {
		const offset = (latestBucket - r.bucket_epoch) / bucketSec;
		const idx = points - 1 - offset;
		if (idx < 0 || idx >= points) continue;
		const v = cumulativeFn(r);
		if (Number.isFinite(v)) cumulative[idx] = v;
	}
	// rate[i] = (cumulative[i] - cumulative[i-1]) / bucketSec. 둘 중 하나라도 null 이면 0.
	const out = new Array(points).fill(0);
	for (let i = 1; i < points; i += 1) {
		const cur = cumulative[i];
		const prev = cumulative[i - 1];
		if (cur != null && prev != null && cur >= prev) {
			out[i] = (cur - prev) / bucketSec;
		}
	}
	return out;
}

/**
 * SystemBucketRow → fixed-length sparkline 배열.
 *
 * buildRows 카드용. SPARKLINE_POINTS 길이의 배열을 만들고 각 bucket 을
 * (현재 시각 기준 offset) 자리에 배치 — 마지막 슬롯이 최신.
 * forward/backward fill 로 빈 칸은 직전·직후 값으로 메워서 평평한 baseline 회피.
 */
function bucketsToSparkline(
	rows: SystemBucketRow[],
	rangeKey: TimeRange,
	valueFn: (row: SystemBucketRow) => number,
): number[] {
	const bucketSec = BUCKET_SECONDS[rangeKey];
	const points = SPARKLINE_POINTS[rangeKey];
	const now = Math.floor(Date.now() / 1000);
	const latestBucket = Math.floor(now / bucketSec) * bucketSec;
	const out: (number | null)[] = new Array(points).fill(null);
	for (const r of rows) {
		const offset = (latestBucket - r.bucket_epoch) / bucketSec;
		const idx = points - 1 - offset;
		if (idx < 0 || idx >= points) continue;
		const v = valueFn(r);
		if (Number.isFinite(v)) out[idx] = v;
	}
	let lastKnown: number | null = null;
	for (let i = 0; i < points; i += 1) {
		if (out[i] !== null) lastKnown = out[i] as number;
		else if (lastKnown !== null) out[i] = lastKnown;
	}
	let firstReal: number | null = null;
	for (const v of out) if (v !== null) { firstReal = v; break; }
	if (firstReal !== null) {
		for (let i = 0; i < points; i += 1) if (out[i] === null) out[i] = firstReal;
	} else {
		for (let i = 0; i < points; i += 1) out[i] = 0;
	}
	return out as number[];
}

function bucketSparkline(
	rows: SystemMetricRow[],
	bucketSec: number,
	pointCount: number,
	valueFn: (row: SystemMetricRow) => number,
): number[] {
	const now = Math.floor(Date.now() / 1000);
	const latestBucket = Math.floor(now / bucketSec) * bucketSec;
	const sums = new Array(pointCount).fill(0);
	const counts = new Array(pointCount).fill(0);

	for (const row of rows) {
		const t = Math.floor(new Date(row.recorded_at).getTime() / 1000);
		const bucket = Math.floor(t / bucketSec) * bucketSec;
		const offset = (latestBucket - bucket) / bucketSec;
		const index = pointCount - 1 - offset;
		if (index < 0 || index >= pointCount) continue;
		const v = valueFn(row);
		if (!Number.isFinite(v)) continue;
		sums[index] += v;
		counts[index] += 1;
	}

	const out: (number | null)[] = new Array(pointCount).fill(null);
	// 1단계: 실제 값이 있는 bucket 채움. forward-fill 은 직전 값 이어받되,
	// 초기값 0 으로 시작하면 Agent 가 최근에만 데이터를 보낼 때 과거 bucket 이
	// 모두 0 으로 깔리는 문제 → 초기엔 null 유지.
	let lastKnown: number | null = null;
	for (let i = 0; i < pointCount; i += 1) {
		if (counts[i] > 0) {
			out[i] = sums[i] / counts[i];
			lastKnown = out[i] as number;
		} else if (lastKnown !== null) {
			out[i] = lastKnown;
		}
	}
	// 2단계: 앞쪽 null (첫 실제 값 이전 bucket) 은 첫 실제 값으로 backward-fill.
	// 이래야 "데이터 없음" 을 0 이 아닌 현재값 수평선 으로 그려서 오인을 방지.
	let firstReal: number | null = null;
	for (const v of out) if (v !== null) { firstReal = v; break; }
	if (firstReal !== null) {
		for (let i = 0; i < pointCount; i += 1) if (out[i] === null) out[i] = firstReal;
	} else {
		// 아예 데이터 없는 에이전트 → 전부 0 (차트가 평평한 baseline).
		for (let i = 0; i < pointCount; i += 1) out[i] = 0;
	}
	return out as number[];
}

function downsample<T>(values: T[], keep: number): T[] {
	if (values.length <= keep) return values;
	const stride = Math.ceil(values.length / keep);
	return values.filter((_, idx) => idx % stride === 0).slice(-keep);
}

function avg(values: number[]): number {
	return values.length ? Math.round((sum(values) / values.length) * 100) / 100 : 0;
}

function sum(values: number[]): number {
	return values.reduce((total, value) => total + value, 0);
}

function max(values: number[]): number {
	return values.length ? Math.max(...values) : 0;
}

function num(value: unknown): number {
	const next = Number(value ?? 0);
	return Number.isFinite(next) ? next : 0;
}
