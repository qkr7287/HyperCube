import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

interface CoreUsage {
	core: number;
	usage: number;
}

export const GET: RequestHandler = async () => {
	try {
		const { stdout: statOutput } = await execAsync('cat /host/proc/stat');
		const { stdout: cpuInfoOutput } = await execAsync('cat /host/proc/cpuinfo');
		const { stdout: loadAvgOutput } = await execAsync('cat /host/proc/loadavg');

		const cores = parseCoreUsage(statOutput);
		const model = parseModel(cpuInfoOutput);
		const loadAvg = parseLoadAvg(loadAvgOutput);

		// Overall usage from first line (cpu)
		const overallLine = statOutput.split('\n').find(l => l.startsWith('cpu '));
		const overall = overallLine ? calcUsage(overallLine) : 0;

		return json({
			success: true,
			data: {
				model,
				cores: cores.length,
				overall,
				loadAvg,
				perCore: cores,
			}
		});
	} catch (error) {
		console.error('CPU API Error:', error);
		return json({
			success: false,
			error: 'CPU 정보를 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};

function calcUsage(line: string): number {
	const parts = line.trim().split(/\s+/).slice(1).map(Number);
	// user, nice, system, idle, iowait, irq, softirq, steal
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
			cores.push({
				core: parseInt(match[1]),
				usage: calcUsage(line),
			});
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
