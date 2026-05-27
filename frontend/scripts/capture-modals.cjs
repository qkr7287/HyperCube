/** 요청/승인 모달 4종 캡처 — 디자인 브리프 보강용. */
const { chromium } = require('@playwright/test');
const path = require('path');

const BASE = 'http://192.168.0.63:33000';
const OUT = path.join(__dirname, '..', '..', 'docs', 'design-redesign-brief', 'screenshots');

async function login(page, user, pass) {
	await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
	await page.waitForSelector('#login-user', { timeout: 20000 });
	await page.locator('#login-user').fill(user);
	await page.locator('#login-pass').fill(pass);
	await page.locator('button.auth-btn[type="submit"]').click();
	await page.waitForFunction(() => Boolean(localStorage.getItem('hc_access_token')), null, {
		timeout: 20000
	});
	await page.waitForTimeout(2500);
}

async function snap(page, name) {
	await page.waitForTimeout(1500);
	await page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: false });
	console.log('  shot ->', name);
}

(async () => {
	const browser = await chromium.launch();
	const ctx = await browser.newContext({ viewport: { width: 1680, height: 1050 } });
	const page = await ctx.newPage();

	// === 사용자 모달 2종 ===
	console.log('user login...');
	await login(page, 'user1', 'agics12!@');
	await page.goto(BASE + '/user', { waitUntil: 'networkidle' });
	await page.waitForTimeout(3000);

	// m1: 컨테이너 생성 요청
	await page.getByRole('button', { name: '+ 새 요청', exact: true }).first().click();
	await page.waitForSelector('.overlay', { timeout: 8000 });
	await snap(page, 'm1-container-request');
	await page.keyboard.press('Escape').catch(() => {});
	await page.waitForTimeout(800);

	// m2: 모델 등록 요청
	await page.getByRole('button', { name: '모델 등록 요청' }).first().click();
	await page.waitForSelector('.overlay', { timeout: 8000 });
	await snap(page, 'm2-model-request');
	await page.keyboard.press('Escape').catch(() => {});
	await page.waitForTimeout(800);

	// === 관리자 모달 2종 ===
	console.log('admin login...');
	await page.evaluate(() => localStorage.clear());
	await login(page, 'admin', 'agics12!@');

	// m3: 컨테이너 요청 승인
	await page.goto(BASE + '/admin/approvals?tab=container', { waitUntil: 'networkidle' });
	await page.waitForTimeout(2500);
	await page.getByRole('button', { name: '전체' }).first().click().catch(() => {});
	await page.waitForTimeout(2000);
	const cBtn = page.locator('button.detail-btn').first();
	if (await cBtn.count()) {
		await cBtn.click();
		await page.waitForSelector('.overlay', { timeout: 8000 });
		await snap(page, 'm3-container-approval');
		await page.keyboard.press('Escape').catch(() => {});
	} else {
		console.log('  !! no container request rows');
	}
	await page.waitForTimeout(800);

	// m4: 모델 등록 요청 승인
	await page.goto(BASE + '/admin/approvals?tab=model', { waitUntil: 'networkidle' });
	await page.waitForTimeout(2500);
	await page.getByRole('button', { name: '전체' }).first().click().catch(() => {});
	await page.waitForTimeout(2000);
	const mBtn = page.locator('button.detail-btn').first();
	if (await mBtn.count()) {
		await mBtn.click();
		await page.waitForSelector('.overlay', { timeout: 8000 });
		await snap(page, 'm4-model-approval');
	} else {
		console.log('  !! no model request rows');
	}

	await browser.close();
	console.log('done.');
})().catch((e) => {
	console.error('FAILED:', e.message);
	process.exit(1);
});
