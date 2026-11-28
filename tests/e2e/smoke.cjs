// Browser smoke test for CI: a teacher opens a lesson, a station joins with the code and works
// through to the recording, the teacher sees the station, and the lesson ends. No page errors.
// Run against a server in demo mode:  BASE=http://127.0.0.1:8000 node tests/e2e/smoke.cjs
const { chromium } = require('playwright');
const BASE = process.env.BASE || 'http://127.0.0.1:8000';

(async () => {
  const b = await chromium.launch();
  const errors = [];
  const page = async (w, h) => {
    const ctx = await b.newContext({ viewport: { width: w, height: h } });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => errors.push(String(e)));
    return p;
  };
  const t = await page(1440, 1000);
  await t.goto(`${BASE}/teacher`);
  await t.click('button.picker-item:has-text("תרגיל 1 ·")');
  await t.waitForURL(/teacher\/\w{32}$/);
  const code = (await t.textContent('.t-code-n')).trim();
  if (!/^\d{6}$/.test(code)) throw new Error(`bad lesson code ${code}`);

  const s = await page(1180, 820);                       // tablet
  await s.goto(`${BASE}/join?code=${code}`);
  await s.fill('#label', 'קבוצה 1');
  await s.click('.join-box button.primary');
  await s.waitForSelector('text=שאלת הבנה');
  await s.click('text=התחילו');
  await s.waitForSelector('.pred-row');
  await s.locator('.pred-row').nth(0).locator('text=יורד').click();
  await s.click('text=שמרו תחזית והתחילו את ההקלטה');
  await s.waitForSelector('text=ראיתי, בואו נסביר', { timeout: 30000 });

  await t.waitForSelector('.t-card:has-text("קבוצה 1")', { timeout: 10000 });
  t.once('dialog', (d) => d.accept());
  await t.click('button:has-text("סיום שיעור")');
  await t.waitForSelector('text=השיעור הסתיים', { timeout: 10000 });

  await b.close();
  if (errors.length) throw new Error(`page errors: ${errors.join(' | ')}`);
  console.log('smoke ok, lesson', code);
})().catch((e) => { console.error('SMOKE FAILED:', e.message); process.exit(1); });
