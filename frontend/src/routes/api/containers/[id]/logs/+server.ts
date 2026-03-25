import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import Docker from 'dockerode';

const docker = new Docker();

export const GET: RequestHandler = async ({ params, url }) => {
	try {
		const container = docker.getContainer(params.id);
		const tail = url.searchParams.get('tail') || '100';

		// 컨테이너가 존재하는지 확인
		const containerInfo = await container.inspect();
		if (!containerInfo) {
			return json({
				success: false,
				error: '컨테이너를 찾을 수 없습니다.'
			}, { status: 404 });
		}

		// 간단한 로그 옵션
		const options = {
			tail: parseInt(tail),
			stdout: true,
			stderr: true,
			timestamps: false
		};

		console.log('Fetching logs for container:', params.id, 'with options:', options);

		// 스트림 대신 버퍼로 로그 가져오기
		const logs = await container.logs(options);
		const logString = logs.toString();
		
		// Docker 로그 스트림 타입 처리 (8바이트 헤더 제거)
		const cleanLogs = logString
			.split('\n')
			.map(line => {
				// Docker 로그 스트림 헤더 제거 (첫 8바이트)
				if (line.length > 8) {
					return line.substring(8);
				}
				return line;
			})
			.filter(line => line.trim());

		console.log('Successfully fetched', cleanLogs.length, 'log lines');

		return json({
			success: true,
			data: {
				logs: cleanLogs,
				containerId: params.id
			}
		});

	} catch (error) {
		console.error('Container Logs API Error:', error);
		return json({
			success: false,
			error: `컨테이너 로그를 가져오는데 실패했습니다: ${error instanceof Error ? error.message : '알 수 없는 오류'}`
		}, { status: 500 });
	}
};
