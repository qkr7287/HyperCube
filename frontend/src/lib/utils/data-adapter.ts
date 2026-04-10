/**
 * Agent WebSocket 데이터 → Frontend 인터페이스 변환
 *
 * Agent가 보내는 원시 데이터(bytes 단위)를 Frontend가 기대하는
 * 형태(human-readable 문자열)로 변환한다.
 */

// ----- Helpers -----

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB'];

export function formatBytes(bytes: number | undefined | null): string {
	if (bytes == null || bytes === 0) return '0 B';
	const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(1024));
	const idx = Math.min(i, UNITS.length - 1);
	const value = bytes / Math.pow(1024, idx);
	return `${value.toFixed(1)} ${UNITS[idx]}`;
}

// ----- System Metrics -----

export interface SystemInfo {
	hostname: string;
	os: string;
	cpu: { cores: number; model: string; usage: number };
	memory: { total: string; used: string; free: string; usage: number };
	disk: { total: string; used: string; free: string; usage: number };
	network: { connections: number; interfaces: string[] };
	logins: { total: number; active: number };
	processes: { total: number; running: number };
	docker: { version: string; containers: number; images: number; driver?: string; storage?: any };
}

export function transformSystemMetrics(msg: any): SystemInfo {
	const d = msg?.data ?? msg ?? {};

	const cpu = d.cpu ?? {};
	const mem = d.memory ?? {};
	const disk = d.disk ?? {};
	const net = d.network ?? {};
	const docker = d.docker ?? {};
	const logins = d.logins ?? {};
	const procs = d.processes ?? {};

	const memTotal = typeof mem.total === 'number' ? mem.total : 0;
	const memUsed = typeof mem.used === 'number' ? mem.used : 0;
	const memFree = typeof mem.free === 'number' ? mem.free : memTotal - memUsed;

	const diskTotal = typeof disk.total === 'number' ? disk.total : 0;
	const diskUsed = typeof disk.used === 'number' ? disk.used : 0;
	const diskFree = typeof disk.free === 'number' ? disk.free : diskTotal - diskUsed;

	return {
		hostname: d.hostname ?? '',
		os: d.os ?? '',
		cpu: {
			cores: cpu.cores ?? 0,
			model: cpu.model ?? '',
			usage: cpu.usage ?? 0,
		},
		memory: {
			total: formatBytes(memTotal),
			used: formatBytes(memUsed),
			free: formatBytes(memFree),
			usage: typeof mem.usage === 'number' ? mem.usage : 0,
		},
		disk: {
			total: formatBytes(diskTotal),
			used: formatBytes(diskUsed),
			free: formatBytes(diskFree),
			usage: typeof disk.usage === 'number' ? disk.usage : 0,
		},
		network: {
			connections: net.connections ?? 0,
			interfaces: net.interfaces ?? [],
		},
		logins: {
			total: logins.total ?? 0,
			active: logins.active ?? 0,
		},
		processes: {
			total: procs.total ?? 0,
			running: procs.running ?? 0,
		},
		docker: {
			version: docker.version ?? '',
			containers: docker.containers ?? 0,
			images: docker.images ?? 0,
			driver: docker.driver,
			storage: docker.storage,
		},
	};
}

/**
 * 기존 SystemInfo와 새 delta를 merge. 새 값이 유효(non-zero/non-empty)할 때만 덮어쓴다.
 */
export function mergeSystemInfo(prev: SystemInfo, incoming: SystemInfo): SystemInfo {
	return {
		hostname: incoming.hostname || prev.hostname,
		os: incoming.os || prev.os,
		cpu: {
			cores: incoming.cpu.cores || prev.cpu.cores,
			model: incoming.cpu.model || prev.cpu.model,
			usage: incoming.cpu.usage || prev.cpu.usage,
		},
		memory: {
			total: incoming.memory.total !== '0 B' ? incoming.memory.total : prev.memory.total,
			used: incoming.memory.used !== '0 B' ? incoming.memory.used : prev.memory.used,
			free: incoming.memory.free !== '0 B' ? incoming.memory.free : prev.memory.free,
			usage: incoming.memory.usage || prev.memory.usage,
		},
		disk: {
			total: incoming.disk.total !== '0 B' ? incoming.disk.total : prev.disk.total,
			used: incoming.disk.used !== '0 B' ? incoming.disk.used : prev.disk.used,
			free: incoming.disk.free !== '0 B' ? incoming.disk.free : prev.disk.free,
			usage: incoming.disk.usage || prev.disk.usage,
		},
		network: {
			connections: incoming.network.connections || prev.network.connections,
			interfaces: incoming.network.interfaces.length > 0 ? incoming.network.interfaces : prev.network.interfaces,
		},
		logins: {
			total: incoming.logins.total || prev.logins.total,
			active: incoming.logins.active || prev.logins.active,
		},
		processes: {
			total: incoming.processes.total || prev.processes.total,
			running: incoming.processes.running || prev.processes.running,
		},
		docker: {
			version: incoming.docker.version || prev.docker.version,
			containers: incoming.docker.containers || prev.docker.containers,
			images: incoming.docker.images || prev.docker.images,
			driver: incoming.docker.driver || prev.docker.driver,
			storage: incoming.docker.storage || prev.docker.storage,
		},
	};
}

// ----- Containers -----

export interface ContainerInfo {
	id: string;
	shortId: string;
	names: string[];
	image: string;
	state: string;
	status: string;
	labels: Record<string, string>;
	ports?: any;
	created?: number;
}

export function transformContainers(msg: any): ContainerInfo[] {
	const containers = msg?.data?.containers ?? msg?.containers ?? [];
	if (!Array.isArray(containers)) return [];

	return containers.map((c: any) => ({
		id: c.id ?? '',
		shortId: (c.id ?? '').substring(0, 12),
		names: c.names ?? (c.name ? [`/${c.name}`] : []),
		image: c.image ?? '',
		state: c.state ?? 'created',
		status: c.status ?? '',
		labels: c.labels ?? {},
		ports: c.ports,
		created: c.created,
	}));
}
