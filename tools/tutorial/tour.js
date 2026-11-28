// End-to-end tutorial recording of the real system (no narration: cursor + written captions).
// Usage: node tour.js <base-url> <out-dir>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const BASE = process.argv[2] || 'http://127.0.0.1:8003';
const OUT = process.argv[3] || path.join(__dirname, 'out');
const W = 1280, H = 800;
const CLASS = 'י׳2 (הדגמה)';
const READ = 1.0;   // caption reading-time multiplier

let p, cur = { x: W / 2, y: H / 2 };
const sleep = (ms) => p.waitForTimeout(ms);
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);

async function moveTo(x, y, ms = 650) {
  const steps = Math.max(8, Math.round(ms / 16));
  const from = { ...cur };
  for (let i = 1; i <= steps; i++) {
    const k = ease(i / steps);
    await p.mouse.move(from.x + (x - from.x) * k, from.y + (y - from.y) * k);
    await p.waitForTimeout(16);
  }
  cur = { x, y };
}
async function target(loc) {
  loc = typeof loc === 'string' ? p.locator(loc).first() : loc;
  await loc.waitFor({ state: 'visible', timeout: 30000 });
  await loc.evaluate((el) => {
    const r = el.getBoundingClientRect();
    if (r.top < 70 || r.bottom > innerHeight - 150) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
  await sleep(450);
  const bb = await loc.boundingBox();
  return { loc, x: bb.x + bb.width / 2, y: bb.y + bb.height / 2, bb };
}
async function click(loc, pause = 450) {
  const t = await target(loc);
  await moveTo(t.x, t.y);
  await sleep(120);
  await p.mouse.down(); await sleep(90); await p.mouse.up();
  await sleep(pause);
}
async function clickXY(x, y, pause = 450) { await moveTo(x, y); await sleep(100); await p.mouse.down(); await sleep(80); await p.mouse.up(); await sleep(pause); }
async function type(loc, text, delay = 55) {
  await click(loc, 150);
  const l = typeof loc === 'string' ? p.locator(loc).first() : loc;
  await l.pressSequentially(text, { delay });
  await sleep(300);
}
async function hover(loc) { const t = await target(loc); await moveTo(t.x, t.y); }
// Caption with optional highlight. Reading time grows with text length.
async function say(kicker, text, opts = {}) {
  const ms = opts.ms ?? Math.round((1700 + text.length * 48) * READ);
  if (opts.ring) {
    const l = typeof opts.ring === 'string' ? p.locator(opts.ring).first() : opts.ring;
    await l.waitFor({ state: 'visible', timeout: 30000 });
    await l.evaluate((el) => { const r = el.getBoundingClientRect(); if (r.top < 60 || r.bottom > innerHeight - 190) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); });
    await sleep(500);
    await l.evaluate((el, pad) => window.__tour.ring(el, pad), opts.pad ?? 8);
    if (opts.point !== false) { const bb = await l.boundingBox(); await moveTo(bb.x + Math.min(bb.width - 12, 30), bb.y + Math.min(bb.height / 2, 24), 500); }
  }
  await p.evaluate(([k, t, top]) => window.__tour.caption(k, t, top), [kicker, text, !!opts.top]);
  await sleep(ms);
  await p.evaluate(() => window.__tour.hide());
  await sleep(350);
}
async function chapter(n, h, s, ms = 3000) {
  await p.evaluate(([a, b, c]) => window.__tour.card(a, b, c), [n, h, s]);
  await sleep(ms);
  await p.evaluate(() => window.__tour.uncard());
  await sleep(600);
}
async function go(url) { await p.goto(BASE + url); await p.evaluate(() => window.__tour && window.__tour.mount()); await sleep(700); }
async function smoothScroll(y, ms = 900) { await p.evaluate((yy) => window.scrollTo({ top: yy, behavior: 'smooth' }), y); await sleep(ms); }
async function scrollBy(dy, ms = 900) { await p.evaluate((d) => window.scrollBy({ top: d, behavior: 'smooth' }), dy); await sleep(ms); }

// ---------- background groups through the student API (no browser) ----------
// Each group keeps its own token cookie (the server binds a session to the tablet that joined).
const jar = {};
async function api(method, url, body) {
  const m = url.match(/^\/sessions\/([0-9a-f]+)/);
  const headers = { 'content-type': 'application/json' };
  if (m && jar[m[1]]) headers.cookie = jar[m[1]];
  const r = await fetch(BASE + '/api' + url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const sc = r.headers.get('set-cookie');
  if (sc) { const pm = sc.match(/Path=\/api\/sessions\/([0-9a-f]+)/i); if (pm) jar[pm[1]] = sc.split(';')[0]; }
  if (!r.ok) throw new Error(`${method} ${url} ${r.status} ${await r.text()}`);
  return r.json();
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function toHypothesis(sid) {
  await api('POST', `/sessions/${sid}/theory`, { choice: 0 });
  await api('POST', `/sessions/${sid}/advance`);
  await api('POST', `/sessions/${sid}/prediction`, { directions: { speed_rpm: 'down' } });
  await api('POST', `/sessions/${sid}/advance`);
  for (let i = 0; i < 40; i++) { try { await api('POST', `/sessions/${sid}/advance`); return; } catch (e) { await wait(500); } }
}
async function backgroundGroups(code) {
  const roster = (await api('GET', `/join/${code}`)).roster;
  const ids = (names) => roster.filter((r) => names.includes(r.name)).map((r) => r.id);
  // Group B: chooses "frequency changed" and argues from speed alone -> misconception alert.
  const gb = (async () => {
    const s = await api('POST', '/join', { code, label: 'קבוצה ב', members: ids(['יואב מ.', 'מאיה ר.', 'איתי ב.']) });
    await wait(4000); await toHypothesis(s.id);
    await wait(6000); await api('POST', `/sessions/${s.id}/hypothesis`, { code: 'H-FREQ' }); await api('POST', `/sessions/${s.id}/advance`);
    const a = await api('POST', `/sessions/${s.id}/readings`, { channel: 'speed_rpm', t: 5 });
    const b = await api('POST', `/sessions/${s.id}/readings`, { channel: 'speed_rpm', t: 20 });
    await wait(5000); await api('POST', `/sessions/${s.id}/advance`);
    await api('POST', `/sessions/${s.id}/reason`, { text: 'המהירות ירדה כי התדר ירד', cited: b.readings.map((r) => r.id) });
    await api('POST', `/sessions/${s.id}/hints`);
  })();
  // Group C: stays on the hypothesis step until it counts as stuck.
  const gc = (async () => {
    const s = await api('POST', '/join', { code, label: 'קבוצה ג', members: ids(['שירה ג.', 'אדם ח.', 'תמר פ.']) });
    await wait(7000); await toHypothesis(s.id);
  })();
  // Group D: solves it with one hint and finishes.
  const gd = (async () => {
    const s = await api('POST', '/join', { code, label: 'קבוצה ד', members: ids(['רון ז.', 'ליה ע.', 'גיא נ.']) });
    await wait(10000); await toHypothesis(s.id);
    await wait(8000); await api('POST', `/sessions/${s.id}/hypothesis`, { code: 'H-LOAD' }); await api('POST', `/sessions/${s.id}/advance`);
    await api('POST', `/sessions/${s.id}/hints`);
    await api('POST', `/sessions/${s.id}/channels/f_drive_hz/open`, { expectation: 'same' });
    await api('POST', `/sessions/${s.id}/channels/torque_nm/open`, { expectation: 'up' });
    await api('POST', `/sessions/${s.id}/readings`, { channel: 'f_drive_hz', t: 5 });
    await api('POST', `/sessions/${s.id}/readings`, { channel: 'f_drive_hz', t: 20 });
    const v = await api('POST', `/sessions/${s.id}/readings`, { channel: 'torque_nm', t: 20 });
    await wait(9000); await api('POST', `/sessions/${s.id}/advance`);
    await api('POST', `/sessions/${s.id}/reason`, { text: 'התדר נשאר 50 והמומנט עלה', cited: v.readings.map((r) => r.id) });
    await wait(4000);
    await api('POST', `/sessions/${s.id}/readings`, { channel: 'torque_nm', t: 30 });
    await api('POST', `/sessions/${s.id}/advance`);
    await api('POST', `/sessions/${s.id}/exit`, { text: 'כן, כשהעומס עולה ההחלקה גדלה.' });
  })();
  return Promise.allSettled([gb, gc, gd]);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, recordVideo: { dir: OUT, size: { width: W, height: H } }, locale: 'he-IL' });
  await ctx.addInitScript({ path: path.join(__dirname, 'overlay.js') });
  p = await ctx.newPage();
  const errors = [];
  p.on('pageerror', (e) => errors.push(String(e)));

  // ================= Opening =================
  await go('/teacher/login');
  await chapter('סרטון הדרכה', 'מנטור מעבדה', 'מסלול מלא: המורה מכינה שיעור, קבוצת תלמידים פותרת תרגיל בעמדה, והמורה עוקבת ומסכמת.', 4500);

  // ================= Part 1: teacher prepares =================
  await chapter('חלק 1', 'המורה מכינה שיעור', 'כניסה, בחירת תרגיל, תצוגה מקדימה, הגדרת העמדה ובדיקת בטיחות');
  await say('כניסה', 'כל מורה נכנסת עם שם משתמש וסיסמה. הסיסמה נשמרת רק כגיבוב מוצפן.', { ring: '.join-box' });
  await type('#u', 'rita', 90);
  await type('#p', 'demo-password', 40);
  await click('button[type=submit]', 1200);
  await say('מסך הבית', 'כאן רואים את השיעורים הפתוחים והמתוכננים. בראש המסך חמש לשוניות: שיעור חי, הכנת שיעור, תלמידים, כיתה ותוכן.', { ring: '.t-tabs' });
  await click('text=הכנת שיעור חדש', 1000);

  await say('אשף בחמישה צעדים', 'האשף מוביל מבחירת כיתה ועד פתיחת השיעור. עם ברירות המחדל זה לוקח פחות משתי דקות.', { ring: '.stepper', point: false });
  await type('input[placeholder="למשל י׳2"]', CLASS, 70);
  const n = p.locator('input[type=number]');
  await click(n, 150); await p.keyboard.press('Control+A'); await p.keyboard.type('4', { delay: 80 });
  await say('צעד 1 · כיתה ועמדות', 'בוחרים כיתה, תאריך ומספר קבוצות. העמדה מוצגת עם הרכיבים שלה. כרגע היא עובדת עם הקלטות.', { ring: '.picker-list' });
  await click('.prep-nav .primary', 800);

  await say('צעד 2 · תרגיל', 'רשימת התרגילים, עם סימון אם התוכן מאושר או עדיין בטיוטה.', { ring: '.picker-list' });
  await click('button.picker-item:has-text("תרגיל 1 ·")', 500);
  await click('.prep-nav .primary', 900);

  await say('צעד 3 · תצוגה מקדימה', 'מה התלמידים יעברו, שלב אחר שלב. אצל התלמיד הכותרת היא רק „תרגיל 1“, בלי שם, כדי לא לחשוף את התשובה.', { ring: '.pv-flow' });
  await click('.pv-stage:has-text("השערה")', 900);
  await click('.pv-stage:has-text("נימוק")', 1200);
  await say('סולם רמזים', 'שלושה רמזים מדורגים. כל רמז הוא שאלה שמכוונת לבדיקה, לא תשובה.', { ring: '.pv-detail' });
  await click('.pv-keytoggle input', 600);
  await click('.pv-stage:has-text("ראיות")', 900);
  await say('המפתח למורה בלבד', 'המורה יכולה לפתוח את המפתח: הסיבה, הראיות הנדרשות והמסקנה. התלמידים אף פעם לא מקבלים את המידע הזה.', { ring: '.pv-detail' });
  await say('ציר הזמן של ההקלטה', 'עד איפה התלמיד צופה, חלונות „לפני“ ו„אחרי“, והפס הכתום: הרגע שבו משהו משתנה בעמדה.', { ring: '.tl' });
  await click('.prep-nav .primary', 900);

  await say('צעד 4 · הגדרת העמדה', 'מצב ההתחלה של כל רכיב, לפי מסלול האנרגיה מהרשת עד הבלם: תדר בווסת, מומנט בבלם, חיבור המנוע ועוד.', { ring: '.ss-path' });
  await say('קריאות צפויות', 'מה אמורים לראות לפני שמתחילים. כך בודקים שהעמדה מכוונת נכון.', { ring: '.ss-expect' });
  await say('מה משתנה בזמן ההרצה', 'למורה בלבד: מתי ובאיזה רכיב קורה השינוי, ואם אפשר לשחזר אותו בעמדה חיה.', { ring: '.sc' });
  await say('בדיקת בטיחות', 'המערכת בודקת את ההקלטה מול מעטפת הבטיחות של המנוע. בתרגיל הזה הכול בתוך המעטפת.', { ring: '.env' });
  await click('.prep-check input', 600);
  await click('.prep-nav .primary', 900);

  await say('צעד 5 · עזרה וציון', 'כמה רמזים מותר, האם מותר לשאול שאלה פתוחה, והאם מורידים נקודה על רמז. ההגדרות עוברות לכל קבוצה שמצטרפת.', { ring: '.t-section' });
  await click('text=פתיחת השיעור עכשיו', 1500);

  await say('שיעור פתוח', 'המערכת יצרה קוד בן 6 ספרות. הקבוצות מקלידות אותו בעמדה כדי להצטרף.', { ring: '.t-code' });
  const code = (await p.textContent('.t-code-n')).trim();
  const lessonUrl = new URL(p.url()).pathname;
  const bg = backgroundGroups(code);

  // ================= Part 2: students =================
  await chapter('חלק 2', 'קבוצה פותרת תרגיל', 'מסך העמדה: הצטרפות, רקע, תחזית, צפייה, השערה, ראיות, נימוק ובדיקה חוזרת');
  await go('/join');
  await say('הצטרפות', 'בעמדה מקלידים את קוד השיעור ואת שם הקבוצה.', { ring: '.join-box' });
  await type('#code', code, 120);
  await type('#label', 'קבוצה א', 70);
  await p.waitForSelector('.join-members');
  await say('מי בקבוצה', 'כל תלמיד מסמן את השם שלו. כך המורה יכולה לעקוב אחרי כל תלמיד גם כשהרכב הקבוצות משתנה.', { ring: '.join-members' });
  for (const nm of ['נועה כ.', 'עומר ל.', 'דנה ש.']) await click(`.join-members >> text=${nm}`, 250);
  await click('.join-box .primary', 1500);

  await say('רקע', 'התרגיל מתחיל בכרטיסי ידע קצרים ובשאלת הבנה.', { ring: '.check' });
  await click('.check button:has-text("1,500")', 900);
  await say('משוב בלי לתת תשובה', 'תשובה שגויה מקבלת הכוונה למושג הרלוונטי, לא את התשובה הנכונה.', { ring: '.check' });
  await click('.check button:has-text("750")', 1000);
  await click('text=התחילו', 1000);

  await say('תחזית', 'לפני שרואים נתונים, הקבוצה מחליטה מה לדעתה יקרה לכל ערוץ.', { ring: '.pred-row' });
  const rows = p.locator('.pred-row');
  await click(rows.nth(0).locator('text=יורד'), 400);
  await click(rows.nth(1).locator('text=לא משתנה'), 400);
  await click('text=שמרו תחזית והתחילו את ההקלטה', 600);
  await say('צפייה', 'ההקלטה מתנגנת ונעצרת בדיוק ברגע השינוי. מה שאחרי העצירה עוד לא נשלח לעמדה.', { ms: 4200 });
  await p.waitForSelector('text=ראיתי, בואו נסביר', { timeout: 30000 });
  await sleep(800);
  await click('text=ראיתי, בואו נסביר', 900);

  await say('השערה', 'הקבוצה בוחרת הסבר. נניח שבחרו „תדר היציאה השתנה“, טעות נפוצה.', {});
  await click('text=תדר היציאה השתנה', 500);
  await click('text=המשיכו לבדיקת ראיות', 1000);

  await say('ראיות', 'בהתחלה רואים רק את מהירות הציר. כל ערוץ נוסף נפתח רק אחרי שהקבוצה כותבת מה היא מצפה לראות בו.', { ring: '.channels', point: false });
  await click('button.ch:has-text("תדר יציאה")', 400);
  await click('.expect >> text=לא ישתנה', 900);
  await click('button.ch:has-text("מומנט")', 400);
  await click('.expect >> text=יעלה', 1100);
  await click('text=רמז · נותרו 3', 1000);
  await say('רמז מהמנטור', 'הרמז הוא שאלה שמכוונת לבדיקה הבאה. אם הוגדר מפתח API, Claude מנסח אותו. בלי מפתח, מוצג הטקסט המאושר.', { ring: '.mentor' });
  const svgs = p.locator('.strip svg');
  const at = async (i, sec) => { const bb = await svgs.nth(i).boundingBox(); await clickXY(bb.x + ((8 + (sec / 39) * 664) / 680) * bb.width, bb.y + bb.height / 2, 350); };
  await say('שמירת קריאות', 'לוחצים על הגרף כדי לשמור קריאה: לפני השינוי ואחריו, בכל ערוץ.', {});
  await svgs.nth(1).scrollIntoViewIfNeeded();
  await at(1, 5); await at(1, 20); await at(2, 5); await at(2, 20);
  await sleep(600);
  await click('text=עברו לנימוק', 900);

  await say('נימוק', 'כותבים נימוק ומסמנים על אילו קריאות הוא מבוסס.', { ring: '#reason' });
  for (const c of await p.locator('.cite input').all()) await click(c, 200);
  await type('#reason', 'המהירות ירדה כי התדר ירד', 45);
  await click('text=שלחו נימוק', 1300);
  await say('הכוונה, לא תשובה', 'מנוע האבחון מזהה שהקריאות לא תומכות בנימוק, ומחזיר את הקבוצה לבדוק. המורה תראה במסך שלה את התפיסה השגויה.', { ring: '.note.warn' });
  await click('text=עברו לנימוק', 900);
  await click('.mentor >> text=מומנט העומס השתנה', 600);
  for (const c of await p.locator('.cite input').all()) { if (!(await c.isChecked())) await click(c, 200); }
  await type('#reason', 'תדר היציאה נשאר 50 Hz והמומנט עלה מ־0.65 ל־1.55', 35);
  await click('text=שלחו נימוק', 1400);
  await say('בדיקה חוזרת', 'נימוק נכון לא מסיים את התרגיל. ההקלטה ממשיכה, והקבוצה בודקת שהמסקנה מחזיקה גם בחלון חדש.', {});
  await p.waitForSelector('text=בדקתי, המשך');
  await sleep(3500);
  await at(2, 30);
  await click('text=בדקתי, המשך', 900);
  await type('#exit', 'כן. כשהעומס עולה ההחלקה גדלה, ולכן המהירות יורדת גם בתדר קבוע.', 30);
  await click('text=שלחו וסיימו', 1500);
  await say('סיום', 'הקבוצה סיימה. עכשיו חוזרים למסך המורה.', { ms: 3000 });
  await bg;

  // ================= Part 3: teacher live =================
  await chapter('חלק 3', 'המורה עוקבת בזמן אמת', 'כרטיס לכל קבוצה, התראות עם הצעת התערבות, יומן ואישור ציון');
  await go(lessonUrl);
  await p.waitForSelector('.t-card');
  await sleep(1500);
  await say('כרטיסי הקבוצות', 'כרטיס לכל קבוצה, עם שמות התלמידים, השלב והזמן בו, והשערה אחרונה. הכרטיסים ממוינים לפי דחיפות.', { ring: '.t-cards' });
  await say('התראות', 'קבוצה תקועה, תפיסה שגויה או מכסת רמזים שנגמרה. ליד כל התראה מופיעה שאלה שהמורה יכולה לשאול בעל פה.', { ring: '.t-alerts' });
  await click(p.locator('.t-card', { hasText: 'קבוצה א' }).locator('text=פתח יומן'), 1300);
  await say('יומן קבוצה', 'כל מה שהקבוצה עשתה: תחזית, השערה, קריאות, נימוקים ורמזים. בראש היומן מופיעה המסקנה המצופה, למורה בלבד.', { ring: '.t-drawer', point: false });
  await click('.t-drawer >> text=אשר ציון', 1000);
  await say('ציון', 'המערכת מציעה ציון לפי המחוון, והמורה מאשרת או משנה אותו. ייצוא הציונים יוצא לאקסל.', { ring: '.t-rubric' });
  await click('.t-drawer .x.big', 800);

  // ================= Part 4: class and students =================
  await chapter('חלק 4', 'סיכום לאורך זמן', 'כיתה, תלמידים ותוכן');
  await click('.t-tabs >> text=כיתה', 1500);
  await say('כיתה לאורך זמן', 'כל השיעורים של הכיתה, כולל השיעור של היום. אפשר לבחור תקופה.', { ring: '.cv-lessons' });
  await say('מפת מחוון', 'כל קבוצה מול ארבעת היבטי המחוון. ירוק פירושו שליטה, צהוב פירושו שליטה חלקית.', { ring: '.cv-heat' });
  await say('תפיסות שגויות', 'כמה קבוצות הראו כל תפיסה, ואיך זה השתנה משיעור לשיעור.', { ring: '.cv-mis' });
  await say('איפה נתקעים', 'זמן חציוני בכל שלב. באדום: שלבים שבהם קבוצות עברו את סף ה״תקוע״.', { ring: '.cv-stages' });

  await click('.t-tabs >> text=תלמידים', 1500);
  await say('תלמידים', 'כל תלמיד בנפרד, גם כשהרכב הקבוצות מתחלף: ממוצע מחוון, מגמה ותפיסות שגויות.', { ring: '.st-table' });
  await click('.st-table tbody tr:has-text("נועה כ.")', 1300);
  await say('פירוט תלמיד', 'כל השיעורים של התלמידה, עם מי עבדה בכל שיעור, הציון, ושליטה בכל כרטיס ידע.', { ring: '.t-drawer', point: false });
  await p.locator('.t-drawer').evaluate((el) => el.scrollTo({ top: 420, behavior: 'smooth' }));
  await sleep(2000);
  await click('.t-drawer .x.big', 800);

  await click('.t-tabs >> text=תוכן', 1500);
  await click('.ct-item:has-text("תרגיל 4")', 1300);
  await say('עריכת תוכן', 'המורה עורכת ומאשרת תרגילים במסך. שדה שצריך לתקן מסומן באדום, ואי אפשר לאשר עד שמתקנים.', { ring: '.ct-field.bad' });
  const goal = p.locator('.ct-field:has(.ct-label:text-is("מטרה")) textarea');
  await click(goal, 200);
  await p.keyboard.press('End');
  await goal.pressSequentially(' עומס יתר', { delay: 80 });
  await say('חומת התשובה', 'מילה שחושפת את התשובה בטקסט לתלמיד נחסמת מיד, כבר בזמן ההקלדה.', { ring: p.locator('.ct-field:has(.ct-label:text-is("מטרה"))') });
  await click('.ct-savebar >> text=ביטול', 900);

  await p.evaluate(() => window.scrollTo({ top: 0 }));
  await chapter('סוף', 'מנטור מעבדה', 'הכנה ← ביצוע בעמדה ← מעקב חי ← סיכום לאורך זמן', 4500);

  await ctx.close();
  await browser.close();
  console.log('errors:', JSON.stringify(errors));
})().catch((e) => { console.error('FAIL', e.message); process.exit(1); });
