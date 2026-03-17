import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getCpuDetail } from '$lib/server/services/system-service';

export const GET: RequestHandler = async () => {
	try {
		const data = await getCpuDetail();
		return json({ success: true, data });
	} catch (error) {
		console.error('CPU API Error:', error);
		return json({
			success: false,
			error: 'CPU 정보를 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};
