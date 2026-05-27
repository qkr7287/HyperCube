/** 템플릿 등록 모달 캡처. */
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
	await page.locator('#login-user').fill('admin');
	await page.locator('#login-pass').fill('agics12!@');
	await page.locator('button.auth-btn[type="submit"]').click();
	await page.waitForFunction(() => Boolean(localStorage.getItem('hc_access_token')), null, {
		timeout: 20000
	});
	await page.waitForTimeout(2500);

	await page.goto(BASE + '/admin/catalog?tab=templates', { waitUntil: 'networkidle' });
	await page.waitForTimeout(2500);
	await page.locator('button.create-btn').first().click();
	await page.waitForSelector('.overlay', { timeout: 8000 });
	await page.waitForTimeout(1500);
	await page.screenshot({ path: path.join(OUT, 'm5-template-editor.png'), fullPage: false });
	console.log('shot -> m5-template-editor');

	await browser.close();
})().catch((e) => {
	console.error('FAILED:', e.message);
	process.exit(1);
});
