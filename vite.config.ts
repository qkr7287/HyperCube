import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), '');
	const apiTarget = env.API_TARGET || 'http://192.168.0.16:3334';

	return {
		plugins: [sveltekit()],
		server: {
			host: true,
			proxy: {
				'/api': {
					target: apiTarget,
					changeOrigin: true,
				}
			}
		}
	};
});
