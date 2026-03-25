import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { getSystemInfo } from '$lib/server/services/system-service';

export const GET: RequestHandler = async () => {
	try {
		const systemInfo = await getSystemInfo();
		return json({ success: true, data: systemInfo });
	} catch (error) {
		console.error('System API Error:', error);
		return json({
			success: false,
			error: '시스템 정보를 가져오는데 실패했습니다.'
		}, { status: 500 });
	}
};
