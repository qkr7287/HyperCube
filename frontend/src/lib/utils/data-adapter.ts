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
	uptime: number;  // seconds
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
		uptime: typeof d.uptime === 'number' ? d.uptime : 0,
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
		uptime: incoming.uptime || prev.uptime,
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
	networks?: string[];
	mounts?: { name: string; type: 'volume' }[];
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
		networks: Array.isArray(c.networks) ? c.networks : undefined,
		mounts: Array.isArray(c.mounts) ? c.mounts : undefined,
	}));
}

// ----- On-demand system_info adapters -----
// Agent 응답 shape를 각 모달이 기대하는 형식으로 정규화.
// Agent가 제공하지 않는 필드는 기본값(0/빈 배열)으로 채운다 — 모달이 `?? 0`로
// 처리하도록 되어있어 누락 필드는 자연스럽게 표시 안 됨.

export function adaptCpuDetail(d: any): any {
	if (!d) return null;
	return {
		overall: d.usage ?? d.overall ?? 0,
		cores: d.cores ?? 0,
		model: d.model ?? '',
		speed: d.speed ?? 0,
		loadAvg: d.loadAvg ?? { avg1: 0, avg5: 0, avg15: 0 },
		perCore: (d.perCore ?? []).map((c: any) => ({
			core: c.core,
			usage: c.load ?? c.usage ?? 0,
		})),
		temperature: d.temperature,
	};
}

export function adaptNetworkDetail(d: any): any {
	if (!d) return null;
	const stats = d.stats ?? {};
	return {
		connections: d.connections ?? 0,
		stats: {
			rx_bytes: stats.rx_bytes ?? stats.rxBytes ?? 0,
			tx_bytes: stats.tx_bytes ?? stats.txBytes ?? 0,
			rx_packets: stats.rx_packets ?? stats.rxPackets ?? 0,
			tx_packets: stats.tx_packets ?? stats.txPackets ?? 0,
			rx_errors: stats.rx_errors ?? stats.rxErrors ?? 0,
			tx_errors: stats.tx_errors ?? stats.txErrors ?? 0,
		},
		interfaces: (d.interfaces ?? []).map((i: any) => ({
			iface: i.iface ?? i.name,
			mac: i.mac,
			addresses: [
				i.ip4 ? { address: i.ip4, family: 'IPv4' } : null,
				i.ip6 ? { address: i.ip6, family: 'IPv6' } : null,
			].filter(Boolean),
			speed: i.speed,
			mtu: i.mtu,
			up: i.up ?? (i.operstate === 'up'),
		})),
	};
}

export function adaptProcessDetail(d: any): any {
	if (!d) return null;
	const list = d.list ?? d.processes ?? [];
	const total = d.total ?? 0;
	const running = d.running ?? 0;
	const blocked = d.blocked ?? 0;
	return {
		totalProcesses: total,
		runningProcesses: running,
		// Agent가 sleeping/zombie를 구분해 주지 않으면 파생: total - running - blocked
		sleepingProcesses: d.sleeping ?? Math.max(0, total - running - blocked),
		zombieProcesses: d.zombie ?? 0,
		processes: list.map((p: any) => ({
			pid: p.pid,
			name: p.name,
			command: p.command,
			cpu: p.cpu ?? 0,
			// Agent는 mem을 RSS MB 단위로 보냄. 모달이 MB로 직접 표시.
			memoryMB: p.mem ?? p.memory ?? 0,
			// 호환 유지: 기존 `memory` 필드도 MB로 노출 (모달 업데이트 시 제거 가능)
			memory: p.mem ?? p.memory ?? 0,
			// Agent는 state에 "running/sleeping/stopped/zombie" 등 전체 단어 사용
			status: p.state ?? p.status ?? '',
			user: p.user,
		})),
	};
}

/**
 * Agent `inspect` 응답(camelCase) → 기존 Mock Docker inspect 스키마(PascalCase)로 변환.
 * 모달이 details.inspect.{Id,Created,State.Status,Config.Cmd,...} 형태로 읽고 있어서
 * 형태를 유지한 채 값만 교체.
 */
export function adaptContainerInspect(d: any): any {
	if (!d) return null;
	const state = d.state ?? {};
	const config = d.config ?? {};
	const netSettings = d.networkSettings ?? {};

	return {
		inspect: {
			Id: d.id,
			Name: d.name ? `/${String(d.name).replace(/^\//, '')}` : undefined,
			Created: d.created,
			Image: d.image,
			RestartCount: d.restartCount,
			State: {
				Status: state.status,
				Running: state.running,
				Paused: state.paused,
				Restarting: state.restarting,
				OOMKilled: state.oomKilled,
				Dead: state.dead,
				Pid: state.pid,
				ExitCode: state.exitCode,
				StartedAt: state.startedAt,
				FinishedAt: state.finishedAt,
				Health: state.health,
			},
			Config: {
				Hostname: config.hostname,
				Env: config.env ?? [],
				Cmd: config.cmd ?? [],
				Entrypoint: config.entrypoint ?? [],
				Labels: config.labels ?? {},
				WorkingDir: config.workingDir ?? '',
			},
			NetworkSettings: {
				Ports: netSettings.ports ?? {},
				Networks: netSettings.networks ?? {},
			},
			Mounts: d.mounts ?? [],
		},
		// stats는 더 이상 inspect 응답에 포함 안 됨. 모달은 containerMetricsStore에서 실시간 값 사용.
		stats: null,
	};
}

export function adaptLoginDetail(d: any): any {
	if (!d) return null;
	const users = d.users ?? [];
	return {
		totalUsers: users.length,
		// Agent protocol doesn't flag active/inactive — treat all utmp entries as active.
		activeUsers: users.length,
		uptime: d.uptime ?? 0,
		users: users.map((u: any) => ({
			user: u.user ?? u.name ?? u.username,
			terminal: u.terminal ?? u.tty,
			host: u.ip ?? u.host,
			loginTime: [u.date, u.time].filter(Boolean).join(' ') || u.loginTime || '',
			active: true,
		})),
	};
}
