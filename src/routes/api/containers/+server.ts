import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getContainerList } from '$lib/server/services/system-service';

export const GET: RequestHandler = async () => {
	try {
		const containerData = await getContainerList();
		return json({ success: true, data: containerData });
	} catch (error) {
		console.error('Docker API Error:', error);
		return json({
			success: false,
			error: 'Docker API 연결에 실패했습니다.'
		}, { status: 500 });
	}
};
