import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import Docker from 'dockerode';
import { exec } from 'child_process';
import { promisify } from 'util';

const docker = new Docker();
const execAsync = promisify(exec);

export const GET: RequestHandler = async () => {
	try {
		// Docker 시스템 정보
		const dockerInfo = await docker.info();
		
		// 시스템 정보 수집
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

		const systemInfo = {
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

		return json({
			success: true,
			data: systemInfo
		});
	} catch (error) {
		console.error('System API Error:', error);
		return json({
			success: false,
			error: '시스템 정보를 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};

async function getHostname(): Promise<string> {
	try {
		// 호스트 시스템의 hostname 읽기
		const { stdout } = await execAsync('cat /host/etc/hostname');
		return stdout.trim();
	} catch {
		try {
			// fallback: 컨테이너 내부 hostname
			const { stdout } = await execAsync('hostname');
			return stdout.trim();
		} catch {
			return 'Unknown';
		}
	}
}

async function getOSInfo(): Promise<string> {
	try {
		// 호스트 시스템의 OS 정보 읽기 - 호스트의 lsb_release 사용
		const { stdout } = await execAsync('nsenter -t 1 -m -u -i -n -p lsb_release -d | cut -d ":" -f 2 | xargs');
		return stdout.trim();
	} catch {
		try {
			// fallback: 호스트의 /etc/os-release 직접 읽기
			const { stdout } = await execAsync('nsenter -t 1 -m cat /etc/os-release | grep PRETTY_NAME | cut -d "=" -f 2 | tr -d \'"\'');
			return stdout.trim();
		} catch {
			try {
				// fallback: 호스트의 uname 사용
				const { stdout } = await execAsync('nsenter -t 1 -u uname -a');
				const parts = stdout.trim().split(' ');
				if (parts.length >= 3) {
					return `${parts[0]} ${parts[2]}`;
				}
				return stdout.trim();
			} catch {
				return 'Unknown';
			}
		}
	}
}

async function getCPUInfo(): Promise<{cores: number, model: string, usage: number}> {
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

async function getMemoryInfo(): Promise<{total: string, used: string, free: string, usage: number}> {
	try {
		// 호스트 시스템의 메모리 정보 읽기
		const { stdout } = await execAsync('cat /host/proc/meminfo');
		const lines = stdout.split('\n');
		
		let totalKB = 0, availableKB = 0;
		for (const line of lines) {
			if (line.startsWith('MemTotal:')) {
				totalKB = parseInt(line.split(/\s+/)[1]);
			} else if (line.startsWith('MemAvailable:')) {
				availableKB = parseInt(line.split(/\s+/)[1]);
			}
		}
		
		const usedKB = totalKB - availableKB;
		const totalGB = (totalKB / 1024 / 1024).toFixed(1);
		const usedGB = (usedKB / 1024 / 1024).toFixed(1);
		const freeGB = (availableKB / 1024 / 1024).toFixed(1);
		const usage = totalKB > 0 ? Math.round((usedKB / totalKB) * 100) : 0;
		
		return { 
			total: `${totalGB}G`, 
			used: `${usedGB}G`, 
			free: `${freeGB}G`, 
			usage 
		};
	} catch {
		try {
			// fallback: 컨테이너 내부 메모리 정보
			const { stdout } = await execAsync('free -h');
			const lines = stdout.split('\n');
			const memLine = lines[1].split(/\s+/);
			
			const total = memLine[1];
			const used = memLine[2];
			const free = memLine[3];
			const totalMB = parseInt(memLine[1]) * 1024; // GB to MB
			const usedMB = parseInt(memLine[2]) * 1024;
			const usage = (usedMB / totalMB) * 100;
			
			return { total, used, free, usage: Math.round(usage) };
		} catch {
			return { total: '0G', used: '0G', free: '0G', usage: 0 };
		}
	}
}

async function getDiskInfo(): Promise<{total: string, used: string, free: string, usage: number}> {
	try {
		const { stdout } = await execAsync('df -h / | tail -1');
		const parts = stdout.split(/\s+/);
		
		const total = parts[1];
		const used = parts[2];
		const free = parts[3];
		const usage = parseInt(parts[4].replace('%', ''));
		
		return { total, used, free, usage };
	} catch {
		return { total: '0G', used: '0G', free: '0G', usage: 0 };
	}
}

async function getNetworkInfo(): Promise<{connections: number, interfaces: string[]}> {
	try {
		// 호스트 네임스페이스 직접 사용 - ss 명령어로 정확한 연결 수 가져오기
		const [connectionsResult, interfacesResult] = await Promise.all([
			execAsync('nsenter -t 1 -n ss -tuln 2>/dev/null || ss -tuln'),
			execAsync('ip addr show | grep -E "^[0-9]+:" | cut -d: -f2 | tr -d " "')
		]);
		
		// 네트워크 연결 수 계산 (헤더 제외)
		const lines = connectionsResult.stdout.split('\n').filter(line => line.trim());
		const connections = lines.filter(line => !line.startsWith('Netid')).length;
		
		return {
			connections: Math.max(0, connections),
			interfaces: interfacesResult.stdout.trim().split('\n').filter(i => i)
		};
	} catch {
		try {
			// fallback: /host/proc/net/tcp와 /host/proc/net/udp 직접 읽기
			const [tcpResult, udpResult, interfacesResult] = await Promise.all([
				execAsync('cat /host/proc/net/tcp'),
				execAsync('cat /host/proc/net/udp'),
				execAsync('cat /host/proc/net/dev | grep -v "lo:" | awk -F: \'{print $1}\' | grep -v "^$"')
			]);
			
			// TCP와 UDP 연결 수 계산 (헤더 제외, 실제 연결만 계산)
			const tcpLines = tcpResult.stdout.split('\n').filter(line => {
				const trimmed = line.trim();
				return trimmed && !trimmed.startsWith('sl') && !trimmed.startsWith('local_address') && trimmed.includes(':');
			});
			const udpLines = udpResult.stdout.split('\n').filter(line => {
				const trimmed = line.trim();
				return trimmed && !trimmed.startsWith('sl') && !trimmed.startsWith('local_address') && trimmed.includes(':');
			});
			const connections = tcpLines.length + udpLines.length;
			
			return {
				connections: Math.max(0, connections),
				interfaces: interfacesResult.stdout.trim().split('\n').filter(i => i)
			};
		} catch {
			return { connections: 0, interfaces: [] };
		}
	}
}

async function getLoginInfo(): Promise<{totalUsers: number, activeUsers: number}> {
	try {
		const { stdout } = await execAsync('nsenter -t 1 -m -u who 2>/dev/null || who');
		const lines = stdout.split('\n').filter(line => line.trim());
		const totalUsers = lines.length;
		const activeUsers = lines.filter(line => line.includes('pts/')).length;

		return {
			totalUsers: Math.max(0, totalUsers),
			activeUsers: Math.max(0, activeUsers)
		};
	} catch {
		return { totalUsers: 0, activeUsers: 0 };
	}
}

async function getProcessInfo(): Promise<{totalProcesses: number, runningProcesses: number}> {
	try {
		// 호스트 네임스페이스 직접 사용 - ps 명령어로 정확한 프로세스 정보 가져오기
		const { stdout } = await execAsync('ps aux');
		const lines = stdout.split('\n').filter(line => line.trim());
		const processes = lines.slice(1); // 헤더 제거
		const runningProcesses = processes.filter(line => {
			const parts = line.trim().split(/\s+/);
			return parts[7] === 'R'; // 상태가 R (Running)인 프로세스
		}).length;
		
		return {
			totalProcesses: processes.length,
			runningProcesses: runningProcesses
		};
	} catch {
		try {
			// fallback: 컨테이너 내부 프로세스 정보
			const { stdout } = await execAsync('ps aux');
			const lines = stdout.split('\n').filter(line => line.trim());
			const processes = lines.slice(1); // 헤더 제거
			const runningProcesses = processes.filter(line => {
				const parts = line.trim().split(/\s+/);
				return parts[7] === 'R'; // 상태가 R (Running)인 프로세스
			}).length;
			
			return {
				totalProcesses: processes.length,
				runningProcesses
			};
		} catch {
			return { totalProcesses: 0, runningProcesses: 0 };
		}
	}
}
