/** 08 컨테이너 상세만 재캡처 — user1 의 실제 컨테이너 id 를 API 로 조회. */
const { chromium } = require('@playwright/test');
const path = require('path');

const BASE = 'http://192.168.0.63:33000';
const OUT = path.join(__dirname, '..', '..', 'docs', 'design-redesign-brief', 'screenshots');

(async () => {
	const browser = await chromium.launch();
	const ctx = await browser.newContext({ viewport: { width: 1680, height: 1050 } });
	const page = await ctx.newPage();

	await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
	await page.waitForSelector('#login-user', { timeout: 20000 });
	await page.locator('#login-user').fill('user1');
	await page.locator('#login-pass').fill('agics12!@');
	await page.locator('button.auth-btn[type="submit"]').click();
	await page.waitForFunction(() => Boolean(localStorage.getItem('hc_access_token')), null, {
		timeout: 20000
	});

	const token = await page.evaluate(() => localStorage.getItem('hc_access_token'));
	const resp = await page.request.get(BASE + '/api/my-containers/', {
		headers: { Authorization: 'Bearer ' + token }
	});
	const json = await resp.json();
	const root = json && json.data ? json.data : json;
	const list = Array.isArray(root) ? root : root && root.results ? root.results : [];
	console.log('containers:', list.map((c) => c.container_id + ' ' + (c.name || '')).join(' | '));

	// 실행 중인 컨테이너 우선
	const running = list.find((c) => /run/i.test(c.status || '')) || list[0];
	if (!running) {
		console.error('no container');
		process.exit(1);
	}
	const cid = running.container_id;
	console.log('using:', cid, running.name);

	await page.goto(BASE + '/user/containers/' + cid, { waitUntil: 'networkidle' });
	await page.waitForTimeout(6000);
	await page.screenshot({ path: path.join(OUT, '08-container-detail.png'), fullPage: true });
	console.log('shot -> 08-container-detail');

	await browser.close();
})().catch((e) => {
	console.error('FAILED:', e.message);
	process.exit(1);
});
