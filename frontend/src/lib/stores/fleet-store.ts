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
	memory_usage: number;
	memory_used: number;
	memory_total: number;
	disk_usage: number;
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
		memory_usage: number;
		memory_used: number;
		memory_total: number;
		disk_usage: number;
		network_rx_rate: number;
		network_tx_rate: number;
		processes_total: number | null;
		processes_running: number | null;
		logins_total: number | null;
		gpu_usage: number;
		gpu_temperature: number | null;
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

const RANGE_LIMITS: Record<TimeRange, number> = { '1m': 200, '5m': 800, '1h': 2000, '24h': 4000, '7d': 8000 };
const HISTORY_LIMITS: Record<TimeRange, number> = { '1m': 30, '5m': 60, '1h': 240, '24h': 500, '7d': 600 };
const BUCKET_SECONDS: Record<TimeRange, number> = { '1m': 5, '5m': 15, '1h': 60, '24h': 300, '7d': 1800 };
const POLL_INTERVAL_MS: Record<TimeRange, number> = {
	'1m': 10000,
	'5m': 30000,
	'1h': 60000,
	'24h': 300000,
	'7d': 1800000,
};
// Backend only exposes 5m / 1h / 24h ranges; map new ranges to closest supported.
const API_RANGE: Record<TimeRange, string> = { '1m': '5m', '5m': '5m', '1h': '1h', '24h': '24h', '7d': '24h' };
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

export async function refreshFleet() {
	if (!browser || !token) return;
	fleetLoading.set(true);
	fleetError.set('');

	try {
		const [agentsPayload, containersPayload, metricsPayload] = await Promise.all([
			api<{ results: AgentApiRow[] }>('/api/agents/?status=approved&page_size=200&ordering=hostname'),
			api<{ results: ContainerApiRow[] }>('/api/containers/?page_size=1000&ordering=agent'),
			api<SystemMetricRow[]>(`/api/metrics/system/?range=${API_RANGE[range]}&limit=${RANGE_LIMITS[range]}&ordering=recorded_at`),
		]);

		const agents = agentsPayload.results ?? [];
		const containers = containersPayload.results ?? [];
		const metrics = Array.isArray(metricsPayload) ? metricsPayload : [];
		const rows = buildRows(agents, containers, metrics);
		const history = buildHistory(metrics, range);

		fleetAgents.set(rows);
		fleetHistory.set(history);
		fleetAgentSeries.set(buildAgentSeries(agents, metrics, history.map((point) => point.timestamp), range));
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
		const rows = await api<SystemMetricRow[]>(
			`/api/metrics/system/?agent=${encodeURIComponent(agentId)}&range=${API_RANGE[range]}&limit=${HISTORY_LIMITS[range]}&ordering=recorded_at`,
		);
		selectedAgentHistory.set(buildAgentHistory(Array.isArray(rows) ? rows : []));
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

function buildRows(agents: AgentApiRow[], containers: ContainerApiRow[], metrics: SystemMetricRow[]): FleetAgentRow[] {
	const containersByAgent = groupContainers(containers);
	const metricsByAgent = groupMetrics(metrics);

	return agents
		.map((agent) => {
			const agentMetrics = metricsByAgent.get(agent.id) ?? [];
			const latest = latestFromHistory(agentMetrics);
			const containerSummary = containersByAgent.get(agent.id) ?? emptyContainerSummary();
			const [health, reasons] = classifyHealth(agent, latest, containerSummary);

			const rxSeries = agentMetrics.map((row, idx, arr) => {
				if (idx === 0) return 0;
				const [rx] = networkRate(arr[idx - 1], row);
				return rx;
			});
			const txSeries = agentMetrics.map((row, idx, arr) => {
				if (idx === 0) return 0;
				const [, tx] = networkRate(arr[idx - 1], row);
				return tx;
			});
			return {
				agent,
				health,
				health_reasons: reasons,
				latest,
				containers: containerSummary,
				sparkline: {
					cpu: downsample(agentMetrics.map((m) => num(m.cpu_usage)), 24),
					memory: downsample(agentMetrics.map((m) => num(m.memory_usage)), 24),
					disk: downsample(agentMetrics.map((m) => num(m.disk_usage)), 24),
					gpu: downsample(agentMetrics.map((m) => gpuUsage(m.gpu)), 24),
					rx: downsample(rxSeries, 24),
					tx: downsample(txSeries, 24),
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
	const previous = rows.at(-2);
	const [rx, tx] = networkRate(previous, latest);
	const gpuStats = gpuSummary(latest.gpu);

	return {
		timestamp: latest.recorded_at,
		cpu_usage: num(latest.cpu_usage),
		memory_usage: num(latest.memory_usage),
		memory_used: num(latest.memory_used),
		memory_total: num(latest.memory_total),
		disk_usage: num(latest.disk_usage),
		network_rx_rate: rx,
		network_tx_rate: tx,
		processes_total: latest.processes_total ?? null,
		processes_running: latest.processes_running ?? null,
		logins_total: latest.logins_total ?? null,
		gpu_usage: gpuStats.usage,
		gpu_temperature: gpuStats.temperature,
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

	return Array.from(buckets.entries())
		.sort(([a], [b]) => a - b)
		.map(([timestamp, item]) => {
			const cpu = item.rows.map((row) => num(row.cpu_usage));
			const memory = item.rows.map((row) => num(row.memory_usage));
			const disk = item.rows.map((row) => num(row.disk_usage));
			const gpu = item.rows.map((row) => gpuUsage(row.gpu)).filter((value) => value > 0);
			return {
				timestamp: new Date(timestamp * 1000).toISOString(),
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
			};
		});
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
	const rx = Math.max(0, num(current.network_rx) - num(previous.network_rx)) / seconds;
	const tx = Math.max(0, num(current.network_tx) - num(previous.network_tx)) / seconds;
	return [rx, tx];
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

function gpuSummary(gpu?: GpuMetric[] | null): { usage: number; temperature: number | null; count: number } {
	const rows = Array.isArray(gpu) ? gpu : [];
	const usages = rows.map((item) => num(item.usage)).filter((value) => value > 0);
	const temps = rows.map((item) => num(item.temperature)).filter((value) => value > 0);
	return {
		usage: avg(usages),
		temperature: temps.length ? max(temps) : null,
		count: rows.length,
	};
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
