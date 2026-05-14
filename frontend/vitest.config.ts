import { defineConfig } from 'vitest/config';

/**
 * Vitest 단위 테스트 전용 설정 — vite.config.ts 의 sveltekit() 플러그인은
 * dev 서버용이라 분리. 현재 테스트 범위: $lib/utils/* 의 pure helper.
 *
 * 컴포넌트(.svelte) 테스트가 필요해지면 @testing-library/svelte +
 * jsdom 환경 추가하면 됨.
 */
export default defineConfig({
	test: {
		include: ['src/**/*.{test,spec}.ts'],
		environment: 'node',
		globals: false,
	},
	resolve: {
		alias: {
			$lib: new URL('./src/lib', import.meta.url).pathname,
		},
	},
});
