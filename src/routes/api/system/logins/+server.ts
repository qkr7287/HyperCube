import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export const GET: RequestHandler = async () => {
	try {
		// 호스트 네임스페이스 직접 사용 - 정확한 로그인 정보 가져오기
		const [whoOutput, uptimeOutput, lastBootOutput] = await Promise.all([
			execAsync('nsenter -t 1 -m -u who 2>/dev/null || who'),
			execAsync('cat /host/proc/uptime'),
			execAsync('cat /host/proc/stat | grep btime')
		]);
		
		const users = parseWhoOutput(whoOutput.stdout);
		const uptime = parseUptimeFromProc(uptimeOutput.stdout);
		const lastBoot = parseBootTime(lastBootOutput.stdout);

		// 활성 사용자 수
		const activeUsers = users.filter(user => user.active).length;

		return json({
			success: true,
			data: {
				users,
				totalUsers: users.length,
				activeUsers,
				uptime,
				lastBoot: lastBoot || 'N/A'
			}
		});
	} catch (error) {
		console.error('Logins API Error:', error);
		return json({
			success: false,
			error: '로그인 정보를 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};

function parseWhoOutput(output: string) {
	const lines = output.split('\n').filter(line => line.trim());
	
	return lines.map(line => {
		const parts = line.trim().split(/\s+/);
		const user = parts[0];
		const terminal = parts[1];
		const loginTime = parts[2] + ' ' + parts[3];
		const host = parts[4] || 'N/A';
		
		// 터미널이 pts인 경우 활성으로 간주
		const active = terminal && terminal.startsWith('pts');
		
		return {
			user,
			terminal,
			host,
			loginTime,
			lastActivity: 'N/A', // who 명령어로는 마지막 활동 시간을 알 수 없음
			active,
			process: active ? 'bash' : 'N/A'
		};
	});
}

function parseUptimeFromProc(output: string) {
	// /proc/uptime에서 첫 번째 값이 시스템 가동시간(초)
	const uptimeSeconds = parseFloat(output.split(' ')[0]);
	return Math.floor(uptimeSeconds);
}

function parseBootTime(output: string) {
	// btime 1234567890 형태에서 타임스탬프 추출
	const match = output.match(/btime\s+(\d+)/);
	if (match) {
		const timestamp = parseInt(match[1]);
		const bootDate = new Date(timestamp * 1000);
		return bootDate.toLocaleString();
	}
	return 'N/A';
}

