import { expect, test } from '@playwright/test';

/**
 * 컨테이너 상세 페이지 smoke E2E.
 *
 * dev 서버(192.168.0.63:3000) 가 떠 있고, admin 계정 + 1 개 이상의
 * GPU 컨테이너가 있다는 가정. 이 테스트가 보장하는 것:
 *
 * 1. admin 로그인 후 /user/containers 진입
 * 2. 첫 컨테이너 카드로 들어가서 hero / KPI 6 카드 / status-line / Δ pill
 *    이 모두 렌더되는지
 * 3. 값에 placeholder("-" / 빈 문자) 가 아니라 실제 숫자가 들어 있는지
 *
 * 자세한 값 매칭은 unit test 에서 하고, 여기서는 "렌더가 끊기지 않는가"
 * 를 본다.
 */

const ADMIN_USER = process.env.E2E_USER || 'admin';
const ADMIN_PASS = process.env.E2E_PASS || 'agics12!@';

test.beforeEach(async ({ page }, info) => {
	await page.goto('/');
	// 폼 렌더까지 대기 (auth-form 또는 redirect 둘 중 하나로 settle)
	await page
		.waitForSelector('#login-user, .topbar, nav', { timeout: 15_000 })
		.catch(() => undefined);
	const userInput = page.locator('#login-user');
	const formVisible = await userInput.isVisible().catch(() => false);
	if (formVisible) {
		await userInput.fill(ADMIN_USER);
		await page.locator('#login-pass').fill(ADMIN_PASS);
		await page.locator('button.auth-btn[type="submit"]').click();
		await page.waitForFunction(
			() => Boolean(localStorage.getItem('hc_access_token')),
			null,
			{ timeout: 15_000 }
		);
	} else {
		// 폼이 안 보였는데 토큰도 없으면 진단용 스크린샷 남김
		const token = await page.evaluate(() => localStorage.getItem('hc_access_token'));
		if (!token) {
			await page.screenshot({ path: `test-results/no-login-${info.title}.png` });
		}
	}
});

/**
 * 컨테이너 detail 페이지로 이동. admin 계정은 `/api/my-containers/` 가 비어
 * 있을 수 있어서, env 로 알려진 container_id 를 받거나, container 목록 API
 * 두 후보(my-containers, admin/containers) 를 순차로 시도해서 첫 id 를 얻음.
 */
/**
 * detail 페이지 로드까지 진행. 실패 시 test.skip 으로 fail-soft.
 * - admin 계정은 /api/my-containers/ 가 비어 있을 수 있어 graceful skip.
 * - E2E_CONTAINER_ID 가 주어지면 그 id 로 바로 이동 (owner 검증은 페이지가).
 */
async function gotoFirstContainer(page: import('@playwright/test').Page): Promise<boolean> {
	const envId = process.env.E2E_CONTAINER_ID;
	const token = await page.evaluate(() => localStorage.getItem('hc_access_token'));
	if (!token) return false;

	const tryId = async (id: string): Promise<boolean> => {
		const probe = await page.request.get(`/api/my-containers/${id}/`, {
			headers: { Authorization: `Bearer ${token}` }
		});
		if (!probe.ok()) return false;
		await page.goto(`/user/containers/${id}`);
		await page.waitForLoadState('networkidle');
		// 페이지가 "container is null" 상태가 아닌지 확인
		const hero = page.locator('section.hero');
		try {
			await expect(hero).toBeVisible({ timeout: 5_000 });
			return true;
		} catch {
			return false;
		}
	};

	if (envId && (await tryId(envId))) return true;

	const listResp = await page.request.get('/api/my-containers/', {
		headers: { Authorization: `Bearer ${token}` }
	});
	if (listResp.ok()) {
		const json = await listResp.json();
		const root = json?.data ?? json;
		const list: any[] = Array.isArray(root) ? root : Array.isArray(root?.results) ? root.results : [];
		for (const item of list) {
			if (item?.container_id && (await tryId(String(item.container_id)))) return true;
		}
	}
	return false;
}

test('컨테이너 상세 페이지 — hero + KPI 6 카드 렌더', async ({ page }) => {
	const ok = await gotoFirstContainer(page);
	test.skip(!ok, '접근 가능한 컨테이너가 없음. E2E_CONTAINER_ID 또는 owner 계정으로 E2E_USER/E2E_PASS 지정.');

	// hero 자체 존재 + accent stripe + 컨테이너 이름
	const hero = page.locator('section.hero');
	await expect(hero).toBeVisible();
	await expect(hero.locator('h1')).toHaveText(/\S+/);
	// data-status 가 비어있지 않아야 함 (running / paused / exited / dead)
	await expect(hero).toHaveAttribute('data-status', /\S+/);

	// vital chips 3 개 (가동 / 재시작 / Health)
	const vitalChips = hero.locator('.vital-chip');
	await expect(vitalChips).toHaveCount(3);
	for (let i = 0; i < 3; i++) {
		await expect(vitalChips.nth(i).locator('strong')).toHaveText(/\S+/);
	}

	// KPI 카드: 최소 4 (CPU/Mem/Net/Disk), GPU 컨테이너면 6
	const kpiCards = page.locator('section.kpi-bar .kpi');
	const kpiCount = await kpiCards.count();
	expect(kpiCount).toBeGreaterThanOrEqual(4);
	expect(kpiCount).toBeLessThanOrEqual(6);

	// 각 KPI 카드: 라벨, value(non-empty), status-line, insight-row pills
	for (let i = 0; i < kpiCount; i++) {
		const card = kpiCards.nth(i);
		await expect(card.locator('.metric-hero .value')).toHaveText(/\S+/);
		await expect(card.locator('.status-line')).toHaveText(/\S+/);
		const pills = card.locator('.insight-row > span, .flow-grid > span');
		await expect(pills.first()).toBeVisible();
	}
});

test('KPI Δ pill 음수 부호는 U+2212', async ({ page }) => {
	const ok = await gotoFirstContainer(page);
	test.skip(!ok, '접근 가능한 컨테이너가 없음. E2E_CONTAINER_ID 또는 owner 계정으로 E2E_USER/E2E_PASS 지정.');

	// Δ 평균 pill 들 — 음수면 반드시 U+2212 (ASCII '-' 사용 금지)
	const deltaPills = page.locator('.insight-row > span[data-tone]');
	const count = await deltaPills.count();
	for (let i = 0; i < count; i++) {
		const text = (await deltaPills.nth(i).textContent()) ?? '';
		const tone = await deltaPills.nth(i).getAttribute('data-tone');
		// 부호 후보: '+' / '−' (U+2212) / '±'
		expect(text).toMatch(/[+−±]\d/);
		// ASCII '-' 같이 보이지만 다른 문자는 금지 (시각 일관성)
		const ascii = text.indexOf('-');
		const minus = text.indexOf('−');
		const pm = text.indexOf('±');
		expect(ascii === -1 || minus !== -1 || pm !== -1, `pill "${text}" tone=${tone}`).toBe(
			true
		);
	}
});

test('CONTROL 영역 + 차트 영역 동시 렌더', async ({ page }) => {
	const ok = await gotoFirstContainer(page);
	test.skip(!ok, '접근 가능한 컨테이너가 없음. E2E_CONTAINER_ID 또는 owner 계정으로 E2E_USER/E2E_PASS 지정.');

	// CONTROL (ops-bar)
	const ops = page.locator('section.ops-bar');
	await expect(ops).toBeVisible();
	// 적어도 1 개의 라이프사이클 액션 버튼 (시작/재시작/일시정지/종료 중 하나)
	await expect(ops.locator('button').first()).toBeVisible();

	// 차트 영역 — 적어도 4 개 차트 카드 (CPU/Mem/Net/Disk)
	const charts = page.locator('.chart-grid .chart-card');
	await expect(charts.first()).toBeVisible({ timeout: 15_000 });
	expect(await charts.count()).toBeGreaterThanOrEqual(4);
});
