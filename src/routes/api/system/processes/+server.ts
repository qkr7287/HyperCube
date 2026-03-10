import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const GET: RequestHandler = async () => {
	try {
		// 호스트 네임스페이스 직접 사용 - 정확한 프로세스 정보 가져오기
		const [totalResult, runningResult, psOutput] = await Promise.all([
			execAsync('ps aux | wc -l'),
			execAsync('ps aux | grep -v grep | wc -l'),
			execAsync('ps aux')
		]);
		
		const totalProcesses = Math.max(0, (parseInt(totalResult.stdout.trim()) || 0) - 1); // 헤더 제외
		const runningProcesses = Math.max(0, (parseInt(runningResult.stdout.trim()) || 0) - 1); // 헤더 제외
		const processes = parsePsOutput(psOutput.stdout);

		// 프로세스 통계 계산
		const sleepingProcesses = processes.filter(p => p.status === 'S').length;
		const zombieProcesses = processes.filter(p => p.status === 'Z').length;

		// CPU 사용률로 정렬하고 상위 20개 프로세스만 반환
		const sortedProcesses = processes.sort((a, b) => b.cpu - a.cpu);
		const topProcesses = sortedProcesses.slice(0, 20);

		return json({
			success: true,
			data: {
				processes: topProcesses,
				totalProcesses,
				runningProcesses,
				sleepingProcesses,
				zombieProcesses
			}
		});
	} catch (error) {
		console.error('Processes API Error:', error);
		return json({
			success: false,
			error: '프로세스 정보를 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};

function parsePsOutput(output: string) {
	const lines = output.split('\n').filter(line => line.trim());
	const processes: any[] = [];

	// 헤더 제거
	const dataLines = lines.slice(1);

	dataLines.forEach(line => {
		const parts = line.trim().split(/\s+/);
		if (parts.length >= 11) {
			const user = parts[0];
			const pid = parseInt(parts[1]);
			const cpu = parseFloat(parts[2]);
			const memory = parseFloat(parts[3]);
			const vsz = parseInt(parts[4]);
			const rss = parseInt(parts[5]);
			const tty = parts[6];
			const status = parts[7];
			const start = parts[8];
			const time = parts[9];
			const command = parts.slice(10).join(' ');

			// 프로세스명 추출 (명령어의 첫 번째 부분)
			const name = command.split(' ')[0].split('/').pop() || command;

			processes.push({
				pid,
				name,
				user,
				cpu,
				memory,
				vsz,
				rss,
				tty,
				status,
				start,
				time,
				command
			});
		}
	});

	return processes;
}

