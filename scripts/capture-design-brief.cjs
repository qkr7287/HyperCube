// Headless playwright capture for design-brief.
// Runs inside hc-frontend-dev container. Stores PNGs under /tmp/cap/.
// 1. fetch JWT via backend  2. localStorage seed  3. navigate + screenshot.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

// vite dev server 의 allowedHosts 가 internal 컨테이너 이름을 막아서 host IP 사용.
const FRONTEND = process.env.FRONTEND || 'http://192.168.0.63:33000';
const BACKEND = process.env.BACKEND || 'http://192.168.0.63:38000';
const USER = process.env.CAP_USER || 'admin';
const PASS = process.env.CAP_PASS || 'agics12!@';
const OUT = process.env.OUT_DIR || '/tmp/cap';
const VIEW = { width: 1480, height: 920 };

async function getToken() {
  const res = await fetch(`${BACKEND}/api/auth/token/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USER, password: PASS }),
  });
  if (!res.ok) throw new Error(`login failed ${res.status}: ${await res.text()}`);
  const body = await res.json();
  // EnvelopeJSONRenderer: { success, data: { access, refresh } } 또는 곧장 토큰.
  const data = body.data ?? body;
  const access = data.access ?? data.access_token ?? body.access;
  const refresh = data.refresh ?? data.refresh_token ?? body.refresh;
  if (!access) throw new Error('no access token in response: ' + JSON.stringify(body));
  return { access, refresh };
}

async function shoot(page, url, file, settleMs = 3500) {
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.waitForTimeout(settleMs);
  await page.screenshot({ path: path.join(OUT, file), clip: { x: 0, y: 0, ...VIEW } });
  console.log('saved', file);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const { access, refresh } = await getToken();
  console.log('got token');

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: VIEW, deviceScaleFactor: 1 });
  const page = await ctx.newPage();

  // localStorage 에 토큰 주입 — 같은 origin 의 빈 페이지 한번 들렀다가 set.
  await page.goto(`${FRONTEND}/favicon.ico`);
  await page.evaluate(([a, r]) => {
    localStorage.setItem('hc_access_token', a);
    if (r) localStorage.setItem('hc_refresh_token', r);
  }, [access, refresh]);

  await shoot(page, `${FRONTEND}/admin/marketplace`, 'marketplace.png');
  await shoot(page, `${FRONTEND}/gpu-hosting`, 'gpu-hosting.png');

  await browser.close();
})().catch((e) => { console.error('FAIL', e); process.exit(1); });
