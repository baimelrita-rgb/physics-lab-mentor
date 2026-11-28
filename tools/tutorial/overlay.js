// Injected into every page of the tutorial recording: a visible mouse cursor, click ripples,
// caption box, highlight ring and chapter cards. Pointer-events are off, so it never blocks the app.
(() => {
  if (window.__tour) return;
  const css = `
  #tour-cursor{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;
    transform:translate(-3px,-2px);transition:none;filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
  .tour-ripple{position:fixed;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;z-index:2147483646;
    pointer-events:none;border:3px solid #F59E0B;animation:tourRipple .55s ease-out forwards}
  @keyframes tourRipple{from{transform:scale(.6);opacity:1}to{transform:scale(3.2);opacity:0}}
  #tour-cap{position:fixed;left:50%;bottom:28px;transform:translateX(-50%) translateY(20px);max-width:820px;width:calc(100% - 80px);
    z-index:2147483645;pointer-events:none;background:rgba(17,24,39,.94);color:#fff;border-radius:16px;padding:18px 24px;
    font-family:Heebo,system-ui,sans-serif;direction:rtl;box-shadow:0 12px 40px rgba(0,0,0,.35);opacity:0;
    transition:opacity .35s, transform .35s;border-inline-start:6px solid #F59E0B}
  #tour-cap.on{opacity:1;transform:translateX(-50%) translateY(0)}
  #tour-cap.top{bottom:auto;top:24px}
  #tour-cap .k{font-size:14px;color:#FCD34D;font-weight:700;margin-bottom:4px;letter-spacing:.2px}
  #tour-cap .t{font-size:21px;line-height:1.5;font-weight:500}
  #tour-ring{position:fixed;z-index:2147483644;pointer-events:none;border:3px solid #F59E0B;border-radius:12px;
    box-shadow:0 0 0 9999px rgba(15,23,42,.38);opacity:0;transition:all .35s ease}
  #tour-ring.on{opacity:1}
  #tour-card{position:fixed;inset:0;z-index:2147483646;pointer-events:none;display:flex;flex-direction:column;
    align-items:center;justify-content:center;gap:14px;background:linear-gradient(135deg,#1E3A8A,#0F172A);color:#fff;
    font-family:Heebo,system-ui,sans-serif;direction:rtl;opacity:0;transition:opacity .5s}
  #tour-card.on{opacity:1}
  #tour-card .n{font-size:18px;color:#FCD34D;font-weight:700}
  #tour-card .h{font-size:46px;font-weight:700}
  #tour-card .s{font-size:22px;color:#CBD5E1;max-width:760px;text-align:center;line-height:1.5}`;
  const arrow = `<svg viewBox="0 0 24 24" width="26" height="26"><path d="M3 2 L3 20 L8 15.5 L11.5 22.5 L14.5 21 L11 14 L18 14 Z"
    fill="#111827" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  const mount = () => {
    if (document.getElementById('tour-cursor')) return;
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    const c = document.createElement('div'); c.id = 'tour-cursor'; c.innerHTML = arrow; document.body.appendChild(c);
    const cap = document.createElement('div'); cap.id = 'tour-cap'; cap.innerHTML = '<div class="k"></div><div class="t"></div>'; document.body.appendChild(cap);
    const ring = document.createElement('div'); ring.id = 'tour-ring'; document.body.appendChild(ring);
    const card = document.createElement('div'); card.id = 'tour-card'; card.innerHTML = '<div class="n"></div><div class="h"></div><div class="s"></div>'; document.body.appendChild(card);
    let pos = { x: 640, y: 400 };
    try { pos = JSON.parse(sessionStorage.getItem('tour-pos')) || pos; } catch (e) {}
    c.style.left = pos.x + 'px'; c.style.top = pos.y + 'px';
  };
  document.addEventListener('mousemove', (e) => {
    const c = document.getElementById('tour-cursor'); if (!c) return;
    c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
    try { sessionStorage.setItem('tour-pos', JSON.stringify({ x: e.clientX, y: e.clientY })); } catch (err) {}
  }, true);
  document.addEventListener('mousedown', (e) => {
    const r = document.createElement('div'); r.className = 'tour-ripple';
    r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    document.body.appendChild(r); setTimeout(() => r.remove(), 600);
  }, true);
  window.__tour = {
    mount,
    caption(kicker, text, top) {
      mount(); const cap = document.getElementById('tour-cap');
      cap.querySelector('.k').textContent = kicker || ''; cap.querySelector('.t').textContent = text;
      cap.classList.toggle('top', !!top); cap.classList.add('on');
    },
    hide() { const cap = document.getElementById('tour-cap'); if (cap) cap.classList.remove('on'); this.unring(); },
    ring(sel, pad) {
      mount(); const el = typeof sel === 'string' ? document.querySelector(sel) : sel; const ring = document.getElementById('tour-ring');
      if (!el) return false; const r = el.getBoundingClientRect(); pad = pad ?? 8;
      Object.assign(ring.style, { left: r.left - pad + 'px', top: r.top - pad + 'px', width: r.width + 2 * pad + 'px', height: r.height + 2 * pad + 'px' });
      ring.classList.add('on'); return true;
    },
    unring() { const ring = document.getElementById('tour-ring'); if (ring) ring.classList.remove('on'); },
    card(n, h, s) {
      mount(); const card = document.getElementById('tour-card');
      card.querySelector('.n').textContent = n; card.querySelector('.h').textContent = h; card.querySelector('.s').textContent = s || '';
      card.classList.add('on');
    },
    uncard() { const card = document.getElementById('tour-card'); if (card) card.classList.remove('on'); },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
