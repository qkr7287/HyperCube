import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import Docker from 'dockerode';

const docker = new Docker();

export const POST: RequestHandler = async ({ params, request }) => {
	try {
		const { action } = await request.json();
		const container = docker.getContainer(params.id);

		let result;
		switch (action) {
			case 'start':
				result = await container.start();
				break;
			case 'stop':
				result = await container.stop();
				break;
			case 'restart':
				result = await container.restart();
				break;
			case 'pause':
				result = await container.pause();
				break;
			case 'unpause':
				result = await container.unpause();
				break;
			case 'kill':
				result = await container.kill();
				break;
			case 'remove':
				result = await container.remove({ force: true });
				break;
			default:
				return json({
					success: false,
					error: '지원하지 않는 액션입니다.'
				}, { status: 400 });
		}

		return json({
			success: true,
			message: `컨테이너가 ${action}되었습니다.`,
			data: result
		});
	} catch (error) {
		console.error('Container Control API Error:', error);
		return json({
			success: false,
			error: `컨테이너 제어에 실패했습니다: ${error.message}`
		}, { status: 500 });
	}
};
