import { dev } from '$app/environment';
import type { Handle } from '@sveltejs/kit';

const API_TARGET = 'http://192.168.0.16:3334';

export const handle: Handle = async ({ event, resolve }) => {
	if (dev && event.url.pathname.startsWith('/api')) {
		const targetUrl = `${API_TARGET}${event.url.pathname}${event.url.search}`;
		const response = await fetch(targetUrl, {
			method: event.request.method,
			headers: event.request.headers,
			body: event.request.method !== 'GET' ? await event.request.text() : undefined,
		});

		return new Response(response.body, {
			status: response.status,
			headers: response.headers,
		});
	}

	return resolve(event);
};
