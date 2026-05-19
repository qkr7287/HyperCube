import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E — dev 서버(192.168.0.63:3000) 대상 smoke 테스트.
 *
 * 실행: `npm run e2e`. 이 환경은 항상 떠 있어야 함. CI 에서 돌릴 거면 별도
 * baseURL / username / password 를 env 로 주입.
 *
 * `testIgnore` 로 unit test 파일은 vitest 가, e2e/ 는 playwright 가 책임.
 */
export default defineConfig({
	testDir: './e2e',
	timeout: 30_000,
	expect: { timeout: 8_000 },
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: 1,
	reporter: process.env.CI ? 'github' : 'list',
	use: {
		baseURL: process.env.E2E_BASE_URL || 'http://192.168.0.63:3000',
		trace: 'retain-on-failure',
		actionTimeout: 8_000,
		navigationTimeout: 15_000
	},
	projects: [
		{
			name: 'chromium',
			use: { ...devices['Desktop Chrome'], viewport: { width: 1920, height: 1080 } }
		}
	]
});
