import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

/**
 * Vitest 설정 — 두 종류 테스트가 같은 러너 안에서 돈다.
 *
 * - *.test.ts (node 환경) — pure helper 단위 테스트. 빠르고 외부 의존 없음.
 * - *.svelte.test.ts (jsdom 환경) — Svelte 컴포넌트 렌더 테스트.
 *
 * 환경 분기는 `test.environmentMatchGlobs` 로 파일명 패턴별로 자동 적용.
 */
export default defineConfig({
	plugins: [sveltekit(), svelteTesting()],
	test: {
		include: ['src/**/*.{test,spec}.ts'],
		environmentMatchGlobs: [
			['src/**/*.svelte.test.ts', 'jsdom'],
			['src/**/*.test.ts', 'node'],
		],
		globals: false,
		setupFiles: ['./src/lib/test/setup.ts'],
	},
});
