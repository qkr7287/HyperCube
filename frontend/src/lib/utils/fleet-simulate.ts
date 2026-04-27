// Fleet simulation utility — generate fake FleetAgentRow entries for visual testing.
//
// Activated via URL query on the root fleet dashboard:
//   ?sim=N        → N synthetic agents merged after real fleet
//   ?sim=each     → 5 agents, one per status (critical/warning/stale/offline/healthy)
//   ?only=sim     → hide real fleet, render only synthetic agents
//
// IDs are prefixed `sim-` so the page can no-op on click handlers that would
// otherwise try to navigate to a real /server-2d or /server-3d view.

import type { FleetAgentRow, FleetHealth, TimeRange } from '$lib/stores/fleet-store';

export const EACH_STATUS_ORDER: FleetHealth[] = ['critical', 'warning', 'stale', 'offline', 'healthy'];

const HOSTNAME_POOL = [
	'sim-edge', 'sim-core', 'sim-gpu', 'sim-batch', 'sim-cache',
	'sim-stream', 'sim-graph', 'sim-search', 'sim-ai', 'sim-vector',
	'sim-queue', 'sim-router', 'sim-broker', 'sim-warden', 'sim-vault',
];

// Deterministic PRNG so the same N produces the same agents within a session.
function mulberry32(seed: number): () => number {
	return function () {
		seed |= 0;
		seed = (seed + 0x6D2B79F5) | 0;
		let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
		t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

function pickHealth(rng: () => number): FleetHealth {
	// Bias toward healthy with occasional warnings/criticals.
	const r = rng();
	if (r < 0.65) return 'healthy';
	if (r < 0.82) return 'warning';
	if (r < 0.92) return 'critical';
	if (r < 0.97) return 'stale';
	return 'offline';
}

function metricsForHealth(health: FleetHealth, rng: () => number) {
	switch (health) {
		case 'critical':
			return {
				cpu: 88 + rng() * 11,
				memory: 90 + rng() * 9,
				disk: 80 + rng() * 18,
				gpu: 90 + rng() * 9,
				rx: 50_000_000 + rng() * 80_000_000,
				tx: 30_000_000 + rng() * 60_000_000,
			};
		case 'warning':
			return {
				cpu: 65 + rng() * 18,
				memory: 70 + rng() * 15,
				disk: 60 + rng() * 20,
				gpu: 60 + rng() * 25,
				rx: 8_000_000 + rng() * 30_000_000,
				tx: 4_000_000 + rng() * 20_000_000,
			};
		case 'stale':
			return {
				cpu: 30 + rng() * 25,
				memory: 40 + rng() * 25,
				disk: 50 + rng() * 25,
				gpu: 0,
				rx: 100_000 + rng() * 1_000_000,
				tx: 80_000 + rng() * 800_000,
			};
		case 'offline':
			return { cpu: 0, memory: 0, disk: 0, gpu: 0, rx: 0, tx: 0 };
		default: // healthy
			return {
				cpu: 5 + rng() * 35,
				memory: 25 + rng() * 35,
				disk: 30 + rng() * 35,
				gpu: rng() < 0.4 ? 5 + rng() * 30 : 0,
				rx: 500_000 + rng() * 8_000_000,
				tx: 300_000 + rng() * 5_000_000,
			};
	}
}

function makeSparkline(target: number, rng: () => number, points = 24): number[] {
	const out: number[] = [];
	let v = Math.max(0, target * (0.7 + rng() * 0.3));
	for (let i = 0; i < points; i++) {
		v += (target - v) * 0.18 + (rng() - 0.5) * Math.max(2, target * 0.08);
		out.push(Math.max(0, Math.min(100, v)));
	}
	out[out.length - 1] = Math.max(0, Math.min(100, target));
	return out;
}

function makeBytesSparkline(target: number, rng: () => number, points = 24): number[] {
	const out: number[] = [];
	for (let i = 0; i < points; i++) {
		out.push(Math.max(0, target * (0.4 + rng() * 1.2)));
	}
	return out;
}

function reasonsFor(health: FleetHealth): string[] {
	switch (health) {
		case 'critical': return ['CPU >= 90%', 'Memory >= 90%'];
		case 'warning': return ['CPU >= 70%'];
		case 'stale': return ['지난 60초 동안 메트릭 미수신'];
		case 'offline': return ['Agent 연결 없음'];
		default: return [];
	}
}

function buildRow(seed: number, health: FleetHealth, hostname: string, index: number): FleetAgentRow {
	const rng = mulberry32(seed);
	const m = metricsForHealth(health, rng);
	const id = `sim-${index.toString().padStart(3, '0')}`;
	const isOffline = health === 'offline';
	const lastSeenIso = isOffline
		? new Date(Date.now() - 10 * 60_000).toISOString()
		: health === 'stale'
			? new Date(Date.now() - 90_000).toISOString()
			: new Date().toISOString();

	const containerCount = isOffline ? 0 : Math.floor(2 + rng() * 18);
	const runningContainers = isOffline ? 0 : Math.max(0, Math.floor(containerCount * (0.6 + rng() * 0.4)));
	const stoppedContainers = Math.max(0, containerCount - runningContainers);

	return {
		agent: {
			id,
			hostname: `${hostname}-${index.toString().padStart(2, '0')}`,
			ip_address: `10.99.${(index % 200) + 1}.${(seed % 250) + 1}`,
			status: 'approved',
			is_active: !isOffline,
			last_seen_at: lastSeenIso,
		},
		health,
		health_reasons: reasonsFor(health),
		latest: isOffline ? null : {
			timestamp: lastSeenIso,
			cpu_usage: m.cpu,
			cpu_cores: 8 + Math.floor(rng() * 24),
			cpu_threads: 16 + Math.floor(rng() * 48),
			cpu_load_avg_1m: m.cpu / 100 * (8 + rng() * 8),
			memory_usage: m.memory,
			memory_used: Math.floor(m.memory / 100 * 64 * 1024 * 1024 * 1024),
			memory_total: 64 * 1024 * 1024 * 1024,
			disk_usage: m.disk,
			disk_used: Math.floor(m.disk / 100 * 1024 * 1024 * 1024 * 1024),
			disk_total: 1024 * 1024 * 1024 * 1024,
			network_rx_rate: m.rx,
			network_tx_rate: m.tx,
			processes_total: 80 + Math.floor(rng() * 320),
			processes_running: 1 + Math.floor(rng() * 8),
			logins_total: Math.floor(rng() * 4),
			gpu_usage: m.gpu,
			gpu_temperature: m.gpu > 0 ? 35 + rng() * 45 : null,
			gpu_memory_used: m.gpu > 0 ? Math.floor(m.gpu / 100 * 16 * 1024 * 1024 * 1024) : null,
			gpu_memory_total: m.gpu > 0 ? 16 * 1024 * 1024 * 1024 : null,
			gpu_count: m.gpu > 0 ? 1 + Math.floor(rng() * 3) : 0,
		},
		containers: isOffline ? {} : {
			running: runningContainers,
			stopped: stoppedContainers,
			total: containerCount,
		},
		sparkline: {
			cpu: makeSparkline(m.cpu, mulberry32(seed + 1)),
			memory: makeSparkline(m.memory, mulberry32(seed + 2)),
			disk: makeSparkline(m.disk, mulberry32(seed + 3)),
			gpu: makeSparkline(m.gpu, mulberry32(seed + 4)),
			rx: makeBytesSparkline(m.rx, mulberry32(seed + 5)),
			tx: makeBytesSparkline(m.tx, mulberry32(seed + 6)),
		},
	};
}

export function buildSimulatedAgents(
	count: number,
	seedBase = 0,
	forcedOrder?: FleetHealth[],
): FleetAgentRow[] {
	if (forcedOrder && forcedOrder.length > 0) {
		return forcedOrder.map((health, i) =>
			buildRow(seedBase + i * 1009, health, HOSTNAME_POOL[i % HOSTNAME_POOL.length], i + 1),
		);
	}
	const rows: FleetAgentRow[] = [];
	const rng = mulberry32(seedBase || 1);
	for (let i = 0; i < count; i++) {
		const health = pickHealth(rng);
		const seed = (seedBase || 1) + i * 1009;
		const hostname = HOSTNAME_POOL[i % HOSTNAME_POOL.length];
		rows.push(buildRow(seed, health, hostname, i + 1));
	}
	return rows;
}

// Used by callers that want to ignore the time range in their own fake data
// generation. Currently sparklines are length-fixed; this hook is a placeholder
// so the public signature can grow without churn at call sites.
export function isSimulatedAgentId(id: string | null | undefined): boolean {
	return Boolean(id && id.startsWith('sim-'));
}

// Currently unused but exported so the page can adapt sparkline length to the
// active range without recomputing the whole row.
export function _bucketsForRange(_range: TimeRange): number {
	return 24;
}
