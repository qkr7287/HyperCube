import Docker from 'dockerode';
import { exec } from 'child_process';
import { promisify } from 'util';

const docker = new Docker();
const execAsync = promisify(exec);

// ─── Types ───

interface CoreUsage {
	core: number;
	usage: number;
}

export interface SystemInfo {
	hostname: string;
	os: string;
	cpu: { cores: number; model: string; usage: number };
	memory: { total: string; used: string; free: string; usage: number };
	disk: { total: string; used: string; free: string; usage: number };
	network: { connections: number; interfaces: string[] };
	logins: { total: number; active: number };
	processes: { total: number; running: number };
	docker: { version: string; containers: number; images: number; driver: string; storage: any };
}

export interface CpuDetail {
	model: string;
	cores: number;
	overall: number;
	loadAvg: { avg1: number; avg5: number; avg15: number };
	perCore: CoreUsage[];
}

export interface ContainerInfo {
	id: string;
	shortId: string;
	names: string[];
	image: string;
	imageId: string;
	command: string;
	created: number;
	state: string;
	status: string;
	ports: any;
	labels: any;
	sizeRw: number;
	sizeRootFs: number;
	hostConfig: any;
	networkSettings: any;
	mounts: any;
}

// ─── System Info ───

export async function getSystemInfo(): Promise<SystemInfo> {
	const dockerInfo = await docker.info();

	const [hostname, os, cpuInfo, memoryInfo, diskInfo, networkInfo, loginInfo, processInfo] = await Promise.all([
		getHostname(),
		getOSInfo(),
		getCPUInfo(),
		getMemoryInfo(),
		getDiskInfo(),
		getNetworkInfo(),
		getLoginInfo(),
		getProcessInfo()
	]);

	return {
		hostname,
		os,
		cpu: {
			cores: cpuInfo.cores,
			model: cpuInfo.model,
			usage: cpuInfo.usage
		},
		memory: {
			total: memoryInfo.total,
			used: memoryInfo.used,
			free: memoryInfo.free,
			usage: memoryInfo.usage
		},
		disk: {
			total: diskInfo.total,
			used: diskInfo.used,
			free: diskInfo.free,
			usage: diskInfo.usage
		},
		network: {
			connections: networkInfo.connections,
			interfaces: networkInfo.interfaces
		},
		logins: {
			total: loginInfo.totalUsers,
			active: loginInfo.activeUsers
		},
		processes: {
			total: processInfo.totalProcesses,
			running: processInfo.runningProcesses
		},
		docker: {
			version: dockerInfo.ServerVersion,
			containers: dockerInfo.Containers,
			images: dockerInfo.Images,
			driver: dockerInfo.Driver,
			storage: dockerInfo.DriverStatus
		}
	};
}

// ─── CPU Detail ───

export async function getCpuDetail(): Promise<CpuDetail> {
	const { stdout: statOutput } = await execAsync('cat /host/proc/stat');
	const { stdout: cpuInfoOutput } = await execAsync('cat /host/proc/cpuinfo');
	const { stdout: loadAvgOutput } = await execAsync('cat /host/proc/loadavg');

	const cores = parseCoreUsage(statOutput);
	const model = parseModel(cpuInfoOutput);
	const loadAvg = parseLoadAvg(loadAvgOutput);

	const overallLine = statOutput.split('\n').find(l => l.startsWith('cpu '));
	const overall = overallLine ? calcUsage(overallLine) : 0;

	return { model, cores: cores.length, overall, loadAvg, perCore: cores };
}

// ─── Container List ───

export async function getContainerList(): Promise<ContainerInfo[]> {
	const containers = await docker.listContainers({ all: true });

	return containers.map(container => ({
		id: container.Id,
		shortId: container.Id.substring(0, 12),
		names: container.Names,
		image: container.Image,
		imageId: container.ImageID,
		command: container.Command,
		created: container.Created,
		state: container.State,
		status: container.Status,
		ports: container.Ports,
		labels: container.Labels,
		sizeRw: (container as any).SizeRw,
		sizeRootFs: (container as any).SizeRootFs,
		hostConfig: container.HostConfig,
		networkSettings: container.NetworkSettings,
		mounts: container.Mounts
	}));
}

// ─── Internal helpers ───

function calcUsage(line: string): number {
	const parts = line.trim().split(/\s+/).slice(1).map(Number);
	const idle = parts[3] + (parts[4] || 0);
	const total = parts.reduce((a, b) => a + b, 0);
	if (total === 0) return 0;
	return Math.round(((total - idle) / total) * 10000) / 100;
}

function parseCoreUsage(stat: string): CoreUsage[] {
	const lines = stat.split('\n');
	const cores: CoreUsage[] = [];
	for (const line of lines) {
		const match = line.match(/^cpu(\d+)\s/);
		if (match) {
			cores.push({ core: parseInt(match[1]), usage: calcUsage(line) });
		}
	}
	return cores;
}

function parseModel(cpuinfo: string): string {
	const match = cpuinfo.match(/model name\s*:\s*(.+)/);
	return match ? match[1].trim() : 'Unknown';
}

function parseLoadAvg(loadavg: string): { avg1: number; avg5: number; avg15: number } {
	const parts = loadavg.trim().split(/\s+/);
	return {
		avg1: parseFloat(parts[0]) || 0,
		avg5: parseFloat(parts[1]) || 0,
		avg15: parseFloat(parts[2]) || 0,
	};
}

async function getHostname(): Promise<string> {
	try {
		const { stdout } = await execAsync('cat /host/etc/hostname');
		return stdout.trim();
	} catch {
		try {
			const { stdout } = await execAsync('hostname');
			return stdout.trim();
		} catch {
			return 'Unknown';
		}
	}
}

async function getOSInfo(): Promise<string> {
	try {
		const { stdout } = await execAsync('nsenter -t 1 -m -u -i -n -p lsb_release -d | cut -d ":" -f 2 | xargs');
		return stdout.trim();
	} catch {
		try {
			const { stdout } = await execAsync('nsenter -t 1 -m cat /etc/os-release | grep PRETTY_NAME | cut -d "=" -f 2 | tr -d \'"\'');
			return stdout.trim();
		} catch {
			try {
				const { stdout } = await execAsync('nsenter -t 1 -u uname -a');
				const parts = stdout.trim().split(' ');
				if (parts.length >= 3) return `${parts[0]} ${parts[2]}`;
				return stdout.trim();
			} catch {
				return 'Unknown';
			}
		}
	}
}

async function getCPUInfo(): Promise<{ cores: number; model: string; usage: number }> {
	try {
		const [coresResult, modelResult, usageResult] = await Promise.all([
			execAsync('nproc'),
			execAsync('lscpu | grep "Model name" | cut -d ":" -f 2 | xargs'),
			execAsync('cat /host/proc/stat | head -1 | awk \'{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}\'')
		]);
		return {
			cores: parseInt(coresResult.stdout.trim()),
			model: modelResult.stdout.trim(),
			usage: parseFloat(usageResult.stdout.trim()) || 0
		};
	} catch {
		return { cores: 0, model: 'Unknown', usage: 0 };
	}
}

async function getMemoryInfo(): Promise<{ total: string; used: string; free: string; usage: number }> {
	try {
		const { stdout } = await execAsync('cat /host/proc/meminfo');
		const lines = stdout.split('\n');
		let totalKB = 0, availableKB = 0;
		for (const line of lines) {
			if (line.startsWith('MemTotal:')) totalKB = parseInt(line.split(/\s+/)[1]);
			else if (line.startsWith('MemAvailable:')) availableKB = parseInt(line.split(/\s+/)[1]);
		}
		const usedKB = totalKB - availableKB;
		const totalGB = (totalKB / 1024 / 1024).toFixed(1);
		const usedGB = (usedKB / 1024 / 1024).toFixed(1);
		const freeGB = (availableKB / 1024 / 1024).toFixed(1);
		const usage = totalKB > 0 ? Math.round((usedKB / totalKB) * 100) : 0;
		return { total: `${totalGB}G`, used: `${usedGB}G`, free: `${freeGB}G`, usage };
	} catch {
		try {
			const { stdout } = await execAsync('free -h');
			const lines = stdout.split('\n');
			const memLine = lines[1].split(/\s+/);
			const total = memLine[1];
			const used = memLine[2];
			const free = memLine[3];
			const totalMB = parseInt(memLine[1]) * 1024;
			const usedMB = parseInt(memLine[2]) * 1024;
			const usage = (usedMB / totalMB) * 100;
			return { total, used, free, usage: Math.round(usage) };
		} catch {
			return { total: '0G', used: '0G', free: '0G', usage: 0 };
		}
	}
}

async function getDiskInfo(): Promise<{ total: string; used: string; free: string; usage: number }> {
	try {
		const { stdout } = await execAsync('df -h / | tail -1');
		const parts = stdout.split(/\s+/);
		return {
			total: parts[1],
			used: parts[2],
			free: parts[3],
			usage: parseInt(parts[4].replace('%', ''))
		};
	} catch {
		return { total: '0G', used: '0G', free: '0G', usage: 0 };
	}
}

async function getNetworkInfo(): Promise<{ connections: number; interfaces: string[] }> {
	try {
		const [connectionsResult, interfacesResult] = await Promise.all([
			execAsync('nsenter -t 1 -n ss -tuln 2>/dev/null || ss -tuln'),
			execAsync('ip addr show | grep -E "^[0-9]+:" | cut -d: -f2 | tr -d " "')
		]);
		const lines = connectionsResult.stdout.split('\n').filter(line => line.trim());
		const connections = lines.filter(line => !line.startsWith('Netid')).length;
		return {
			connections: Math.max(0, connections),
			interfaces: interfacesResult.stdout.trim().split('\n').filter(i => i)
		};
	} catch {
		try {
			const [tcpResult, udpResult, interfacesResult] = await Promise.all([
				execAsync('cat /host/proc/net/tcp'),
				execAsync('cat /host/proc/net/udp'),
				execAsync('cat /host/proc/net/dev | grep -v "lo:" | awk -F: \'{print $1}\' | grep -v "^$"')
			]);
			const tcpLines = tcpResult.stdout.split('\n').filter(line => {
				const trimmed = line.trim();
				return trimmed && !trimmed.startsWith('sl') && !trimmed.startsWith('local_address') && trimmed.includes(':');
			});
			const udpLines = udpResult.stdout.split('\n').filter(line => {
				const trimmed = line.trim();
				return trimmed && !trimmed.startsWith('sl') && !trimmed.startsWith('local_address') && trimmed.includes(':');
			});
			return {
				connections: Math.max(0, tcpLines.length + udpLines.length),
				interfaces: interfacesResult.stdout.trim().split('\n').filter(i => i)
			};
		} catch {
			return { connections: 0, interfaces: [] };
		}
	}
}

async function getLoginInfo(): Promise<{ totalUsers: number; activeUsers: number }> {
	try {
		const { stdout } = await execAsync('nsenter -t 1 -m -u who 2>/dev/null || who');
		const lines = stdout.split('\n').filter(line => line.trim());
		return {
			totalUsers: Math.max(0, lines.length),
			activeUsers: Math.max(0, lines.filter(line => line.includes('pts/')).length)
		};
	} catch {
		return { totalUsers: 0, activeUsers: 0 };
	}
}

async function getProcessInfo(): Promise<{ totalProcesses: number; runningProcesses: number }> {
	try {
		const { stdout } = await execAsync('ps aux');
		const lines = stdout.split('\n').filter(line => line.trim());
		const processes = lines.slice(1);
		const runningProcesses = processes.filter(line => {
			const parts = line.trim().split(/\s+/);
			return parts[7] === 'R';
		}).length;
		return { totalProcesses: processes.length, runningProcesses };
	} catch {
		return { totalProcesses: 0, runningProcesses: 0 };
	}
}
