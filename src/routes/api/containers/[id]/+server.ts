import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import Docker from 'dockerode';

const docker = new Docker();

export const GET: RequestHandler = async ({ params }) => {
	try {
		const container = docker.getContainer(params.id);
		const [inspect, stats] = await Promise.all([
			container.inspect(),
			container.stats({ stream: false })
		]);

		return json({
			success: true,
			data: {
				inspect,
				stats
			}
		});
	} catch (error) {
		console.error('Container API Error:', error);
		return json({
			success: false,
			error: '컨테이너 정보를 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};
