/**
 * 디자인 리뉴얼 브리프용 — 모든 페이지 스크린샷 캡처.
 * 실행: cd frontend && node scripts/capture-screenshots.cjs
 * 출력: docs/design-redesign-brief/screenshots/*.png
 */
const { chromium } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE = process.env.CAP_BASE || 'http://192.168.0.63:33000';
const OUT = path.join(__dirname, '..', '..', 'docs', 'design-redesign-brief', 'screenshots');

async function login(page, user, pass) {
	await page.evaluate(() => localStorage.clear()).catch(() => {});
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

async function shoot(page, url, name, wait = 3000) {
	await page.goto(BASE + url, { waitUntil: 'networkidle' }).catch(() => {});
	await page.waitForTimeout(wait);
	const file = path.join(OUT, name + '.png');
	await page.screenshot({ path: file, fullPage: true });
	console.log('  shot ->', name);
}

(async () => {
	fs.mkdirSync(OUT, { recursive: true });
	const browser = await chromium.launch();
	const ctx = await browser.newContext({ viewport: { width: 1680, height: 1050 } });
	const page = await ctx.newPage();

	// 0. 로그인 페이지 (인증 전)
	console.log('login page...');
	await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
	await page.waitForSelector('#login-user', { timeout: 20000 });
	await page.waitForTimeout(1200);
	await page.screenshot({ path: path.join(OUT, '00-login.png'), fullPage: true });
	console.log('  shot -> 00-login');

	// === 관리자 ===
	console.log('admin login...');
	await login(page, process.env.CAP_ADMIN_USER || 'admin', process.env.CAP_ADMIN_PASS || 'agics12!@');
	await shoot(page, '/', '01-admin-dashboard', 3500);
	await shoot(page, '/server-2d', '02-server-2d', 4500);
	await shoot(page, '/server-3d', '03-server-3d', 6000);
	await shoot(page, '/admin/approvals', '04-admin-approvals', 3000);
	await shoot(page, '/admin/catalog', '05-admin-catalog', 3000);
	await shoot(page, '/admin/marketplace', '06-admin-marketplace', 3000);

	// === 일반 사용자 ===
	console.log('user login...');
	await login(page, process.env.CAP_USER_USER || 'user1', process.env.CAP_USER_PASS || 'agics12!@');
	await shoot(page, '/user', '07-user-dashboard', 3500);
	const cid = process.env.CAP_CONTAINER_ID || '05eddec05865';
	await shoot(page, '/user/containers/' + cid, '08-container-detail', 5000);

	await browser.close();
	console.log('done. output:', OUT);
})().catch((e) => {
	console.error('CAPTURE FAILED:', e.message);
	process.exit(1);
});
