import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
			// /api/* 요청을 192.168.0.16 서버의 DCMTool로 전달
			'/api': {
				target: 'http://192.168.0.16:3334',
				changeOrigin: true,
			}
		}
	}
});
