import type { FleetAgentRow } from '$lib/stores/fleet-store';

type Health = FleetAgentRow['health'];

function randomBetween(min: number, max: number): number {
	return Math.random() * (max - min) + min;
}

function randomWalk(count: number, start: number, step = 4, min = 0, max = 100): number[] {
	const out: number[] = [];
	let current = start;
	for (let i = 0; i < count; i += 1) {
		current += randomBetween(-step, step);
		if (current < min) current = min;
		if (current > max) current = max;
		out.push(Math.round(current * 10) / 10);
	}
	return out;
}

function pickHealth(i: number, total: number): Health {
	// Distribute statuses: a few critical/warning/stale at start, rest healthy.
	if (total <= 3) return i === 0 ? 'critical' : 'healthy';
	const slot = i / Math.max(1, total);
	if (slot < 0.1) return 'critical';
	if (slot < 0.25) return 'warning';
	if (slot < 0.32) return 'stale';
	if (slot < 0.36) return 'offline';
	return 'healthy';
}

function metricsFor(health: Health): { cpu: number; mem: number; disk: number; gpu: number } {
	if (health === 'critical') {
		return {
			cpu: randomBetween(85, 99),
			mem: randomBetween(88, 99),
			disk: randomBetween(75, 96),
			gpu: randomBetween(70, 99),
		};
	}
	if (health === 'warning') {
		return {
			cpu: randomBetween(65, 82),
			mem: randomBetween(70, 84),
			disk: randomBetween(60, 82),
			gpu: randomBetween(55, 78),
		};
	}
	if (health === 'stale' || health === 'offline') {
		return {
			cpu: randomBetween(0, 30),
			mem: randomBetween(30, 55),
			disk: randomBetween(20, 60),
			gpu: randomBetween(0, 25),
		};
	}
	return {
		cpu: randomBetween(5, 55),
		mem: randomBetween(25, 70),
		disk: randomBetween(20, 65),
		gpu: randomBetween(0, 45),
	};
}

function containerDist(health: Health): Record<string, number> {
	const running = Math.round(randomBetween(3, 40));
	const stopped = Math.round(randomBetween(0, 8));
	const paused = Math.round(randomBetween(0, 2));
	const exited = Math.round(randomBetween(0, 5));
	const restarting = health === 'critical' || health === 'warning' ? Math.round(randomBetween(0, 2)) : 0;
	const dead = health === 'critical' ? Math.round(randomBetween(0, 1)) : 0;
	const total = running + stopped + paused + exited + restarting + dead;
	return {
		total,
		running,
		stopped,
		paused,
		exited,
		restarting,
		dead,
		created: 0,
		non_running: Math.max(0, total - running),
		problem: restarting + dead,
	};
}

function reasonsFor(health: Health, mem: number, cpu: number, disk: number): string[] {
	if (health === 'critical') {
		const out: string[] = [];
		if (cpu >= 90) out.push('CPU >= 90%');
		if (mem >= 90) out.push('Memory >= 90%');
		if (disk >= 90) out.push('Disk >= 90%');
		return out.length ? out : ['CPU >= 90%'];
	}
	if (health === 'warning') {
		const out: string[] = [];
		if (cpu >= 70) out.push('CPU >= 70%');
		if (mem >= 75) out.push('Memory >= 75%');
		return out.length ? out : ['CPU >= 70%'];
	}
	if (health === 'stale') return ['Metrics older than 60 seconds'];
	if (health === 'offline') return ['Agent is offline'];
	return [];
}

export function buildSimulatedAgents(count: number, offset = 0): FleetAgentRow[] {
	const out: FleetAgentRow[] = [];
	const sparkLength = 24;
	for (let i = 0; i < count; i += 1) {
		const health = pickHealth(i, count);
		const idx = i + offset + 1;
		const m = metricsFor(health);
		const containers = containerDist(health);
		const hasGpu = Math.random() > 0.6;
		const memoryTotal = Math.round(randomBetween(8, 128)) * 1024 * 1024 * 1024;
		const memoryUsed = Math.round((m.mem / 100) * memoryTotal);
		const rx = Math.round(randomBetween(0, 12)) * 1024 * 1024;
		const tx = Math.round(randomBetween(0, 8)) * 1024 * 1024;
		const processesTotal = Math.round(randomBetween(80, 420));
		const processesRunning = Math.max(1, Math.round(processesTotal * randomBetween(0.02, 0.15)));

		const row: FleetAgentRow = {
			agent: {
				id: `sim-${String(idx).padStart(3, '0')}`,
				hostname: `sim-node-${String(idx).padStart(2, '0')}`,
				ip_address: `10.20.${Math.floor(idx / 254)}.${(idx % 254) + 1}`,
				status: 'approved',
				is_active: health !== 'offline',
				last_seen_at: new Date(Date.now() - (health === 'offline' ? 120000 : 5000)).toISOString(),
			},
			health,
			health_reasons: reasonsFor(health, m.mem, m.cpu, m.disk),
			latest: health === 'offline'
				? null
				: {
						timestamp: new Date(Date.now() - (health === 'stale' ? 65000 : 8000)).toISOString(),
						cpu_usage: Math.round(m.cpu * 10) / 10,
						memory_usage: Math.round(m.mem * 10) / 10,
						memory_used: memoryUsed,
						memory_total: memoryTotal,
						disk_usage: Math.round(m.disk * 10) / 10,
						network_rx_rate: rx,
						network_tx_rate: tx,
						processes_total: processesTotal,
						processes_running: processesRunning,
						logins_total: Math.round(randomBetween(0, 6)),
						gpu_usage: hasGpu ? Math.round(m.gpu * 10) / 10 : 0,
						gpu_temperature: hasGpu ? Math.round(randomBetween(38, 82)) : null,
						gpu_count: hasGpu ? (Math.random() > 0.7 ? 2 : 1) : 0,
					},
			containers,
			sparkline: {
				cpu: randomWalk(sparkLength, m.cpu, 6),
				memory: randomWalk(sparkLength, m.mem, 3),
				disk: randomWalk(sparkLength, m.disk, 1.2),
				gpu: hasGpu ? randomWalk(sparkLength, m.gpu, 8) : Array(sparkLength).fill(0),
				rx: randomWalk(sparkLength, rx, Math.max(rx * 0.2, 1024 * 512), 0, rx * 2 + 1024 * 1024),
				tx: randomWalk(sparkLength, tx, Math.max(tx * 0.2, 1024 * 256), 0, tx * 2 + 1024 * 1024),
			},
		};
		out.push(row);
	}
	return out;
}
