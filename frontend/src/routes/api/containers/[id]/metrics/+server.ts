import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import Docker from 'dockerode';

const docker = new Docker();

export const GET: RequestHandler = async ({ params }) => {
	try {
		const container = docker.getContainer(params.id);
		const stats = await container.stats({ stream: false });

		// CPU 사용률 계산
		const cpuDelta = stats.cpu_stats.cpu_usage.total_usage - stats.precpu_stats.cpu_usage.total_usage;
		const systemDelta = stats.cpu_stats.system_cpu_usage - stats.precpu_stats.system_cpu_usage;
		const cpuPercent = (cpuDelta / systemDelta) * stats.cpu_stats.online_cpus * 100.0;

		// 메모리 사용량 계산
		const memoryUsage = stats.memory_stats.usage || 0;
		const memoryLimit = stats.memory_stats.limit || 1;
		const memoryPercent = (memoryUsage / memoryLimit) * 100;

		// 네트워크 통계
		const networks = stats.networks || {};
		let networkRx = 0;
		let networkTx = 0;
		
		Object.values(networks).forEach((network: any) => {
			networkRx += network.rx_bytes || 0;
			networkTx += network.tx_bytes || 0;
		});

		// 디스크 I/O 통계
		const blkioStats = stats.blkio_stats || {};
		let diskRead = 0;
		let diskWrite = 0;
		
		if (blkioStats.io_service_bytes_recursive) {
			blkioStats.io_service_bytes_recursive.forEach((entry: any) => {
				if (entry.op === 'Read') diskRead += entry.value || 0;
				if (entry.op === 'Write') diskWrite += entry.value || 0;
			});
		}

		const metrics = {
			timestamp: new Date().toISOString(),
			cpu: {
				usage: Math.round(cpuPercent * 100) / 100,
				cores: stats.cpu_stats.online_cpus
			},
			memory: {
				usage: memoryUsage,
				limit: memoryLimit,
				percent: Math.round(memoryPercent * 100) / 100
			},
			network: {
				rx: networkRx,
				tx: networkTx
			},
			disk: {
				read: diskRead,
				write: diskWrite
			}
		};

		return json({
			success: true,
			data: metrics
		});
	} catch (error) {
		console.error('Container Metrics API Error:', error);
		return json({
			success: false,
			error: '컨테이너 메트릭을 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};

