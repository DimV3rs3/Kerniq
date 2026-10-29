/* ---------- layout: editor + chat, or agent only (chats | conversation) ---------- */
// the default title is stored in English; show it in the interface language
function chatTitleText(c) { return (!c || !c.title || c.title === 'New chat') ? t('newChatLong') : c.title; }
function refreshChatHeading() {
  const el = document.getElementById('chat-heading');
  if (!el) return;
  if (layoutMode === 'agent') {
    const c = typeof currentChat === 'function' ? currentChat() : null;
    const title = chatTitleText(c);
    el.textContent = title; el.title = title; el.classList.add('is-title');
  } else {
    el.textContent = t('chat'); el.title = ''; el.classList.remove('is-title');
  }
}
/* the label is erased and typed again when the mode changes */
function typePillLabel(text) {
  const pill = document.getElementById('mode-pill');
  const el = pill && pill.querySelector('.mode-pill-label');
  if (!el) return Promise.resolve();
  const token = (el._tok = (el._tok || 0) + 1);
  if (!motionMs(1)) { el.textContent = text; el.classList.remove('typing'); return Promise.resolve(); }
  el.classList.add('typing');
  return (async () => {
    let cur = el.textContent;
    while (cur.length && el._tok === token) { cur = cur.slice(0, -1); el.textContent = cur; await wait(40); }
    for (let i = 1; i <= text.length && el._tok === token; i++) { el.textContent = text.slice(0, i); await wait(55); }
    if (el._tok === token) { el.textContent = text; el.classList.remove('typing'); }
  })();
}
function refreshLayoutLabels() {
  refreshChatHeading();
  const pill = document.getElementById('mode-pill');
  if (pill) {
    const label = pill.querySelector('.mode-pill-label');
    if (label && !label.classList.contains('typing')) label.textContent = t(layoutMode === 'agent' ? 'agentLabel' : 'editorLabel');
    const tip = t(layoutMode === 'agent' ? 'modeToEditor' : 'modeToAgent');
    pill.title = tip; pill.setAttribute('aria-label', tip);
  }
  const heading = document.querySelector('#explorer h3 .grow');
  if (heading && !document.getElementById('view-main').classList.contains('layout-anim')) {
    heading.textContent = t(layoutMode === 'agent' ? 'chats' : 'explorer');
  }
}
/* sets data-layout, labels and the switch state; does not touch panel sizes */
function applyLayoutAttrs(mode, persist) {
  layoutMode = mode === 'agent' ? 'agent' : 'editor';
  document.documentElement.dataset.layout = layoutMode;
  document.documentElement.dataset.tone = layoutMode;
  if (persist !== false) saveInterface({ layout: layoutMode });
  const sideBtn = document.getElementById('btn-toggle-explorer');
  if (sideBtn) { const lbl = t(layoutMode === 'agent' ? 'chats' : 'explorer'); sideBtn.title = lbl; sideBtn.setAttribute('aria-label', lbl); }
  document.querySelectorAll('#seg-layout button').forEach(b => {
    const on = b.dataset.v === layoutMode;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
  refreshLayoutLabels();
}
/* instant version: used on start-up and whenever motion is off */
function applyLayout(mode, persist) {
  applyLayoutAttrs(mode, persist);
  setExplorerCollapsed(!sideOpen[layoutMode], true);
  renderChatList();
  requestAnimationFrame(() => { if (typeof updateScrollBtn === 'function') updateScrollBtn(); });
}

/* animated switch.
   editor -> agent: side panels fold away, then the conversation takes the window.
   agent -> editor: close the chats sidebar if it is open, slide the chat off to the
   right without restyling it, reveal the editor already at full size, then open
   the editor side panels to the size they had last. */
let layoutBusy = false;
const LAYOUT_EASE = 'cubic-bezier(.65, 0, .35, 1)';
const wait = (ms) => new Promise(r => setTimeout(r, ms));
function motionMs(ms) {
  const m = document.documentElement.dataset.motion || 'on';
  if (m === 'off') return 0;
  if (m === 'auto' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return 0;
  return ms;
}
function layoutPanels() {
  return { ex: document.getElementById('explorer'), ed: document.getElementById('editor-panel'),
           ch: document.getElementById('chat-panel'), view: document.getElementById('view-main') };
}
function freezePanels(w) {
  const P = layoutPanels();
  [['ex', P.ex], ['ed', P.ed], ['ch', P.ch]].forEach(([k, el]) => {
    el.style.setProperty('transition', 'none', 'important');
    el.style.setProperty('width', w[k] + 'px', 'important');
    el.style.setProperty('flex', '0 0 auto', 'important');
  });
  void P.view.offsetWidth;             // commit the start widths before animating away from them
}
async function layoutPhase(target, ms, pins) {
  const P = layoutPanels();
  const dur = motionMs(ms);
  [['ex', P.ex], ['ed', P.ed], ['ch', P.ch]].forEach(([k, el]) => {
    if (pins && pins[k] != null) { el.classList.add('pin'); el.style.setProperty('--pin', pins[k] + 'px'); }
    else { el.classList.remove('pin'); el.style.removeProperty('--pin'); }
  });
  void P.view.offsetWidth;
  [['ex', P.ex], ['ed', P.ed], ['ch', P.ch]].forEach(([k, el]) => {
    el.style.setProperty('transition', dur ? 'width ' + dur + 'ms ' + LAYOUT_EASE : 'none', 'important');
    el.style.setProperty('width', Math.max(0, Math.round(target[k])) + 'px', 'important');
  });
  await wait(dur + 60);
}
function finishLayoutAnim() {
  const P = layoutPanels();
  P.view.classList.add('layout-settle');
  P.view.classList.remove('sheet-out', 'sheet-go', 'reveal-editor', 'keep-tree', 'keep-chats');
  [P.ex, P.ed, P.ch].forEach(el => {
    ['width', 'flex', 'transition', '--pin'].forEach(prop => el.style.removeProperty(prop));
    el.style.transform = '';
    el.classList.remove('pin');
  });
  P.view.classList.remove('layout-anim');
  applyStoredPanelSizes();
  setExplorerCollapsed(!sideOpen[layoutMode], true);
  setChatCollapsed(chatCollapsed, true);
  refreshLayoutLabels();
  renderChatList();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    P.view.classList.remove('layout-settle');
    if (typeof updateScrollBtn === 'function') updateScrollBtn();
    if (typeof renderCodeWindow === 'function') renderCodeWindow(true);
  }));
}
async function switchLayout(next) {
  next = next === 'agent' ? 'agent' : 'editor';
  if (document.documentElement.dataset.phone === '1') return;
  if (layoutBusy || next === layoutMode) return;
  if (!motionMs(1) || settingsOpen()) { applyLayout(next); return; }
  layoutBusy = true;
  const P = layoutPanels();
  try {
    const W = P.view.clientWidth;
    const sizes = storedPanelSizes();
    const S = Math.min(sizes.left, Math.floor(W * 0.5));
    const C = Math.min(sizes.right, Math.floor(W * 0.5));
    const start = { ex: P.ex.offsetWidth, ed: P.ed.offsetWidth, ch: P.ch.offsetWidth };
    P.view.classList.add('layout-anim');
    P.ex.classList.remove('collapsed'); P.ch.classList.remove('collapsed');
    freezePanels(start);
    if (next === 'agent') {
      document.documentElement.dataset.tone = 'agent';
      typePillLabel(t('agentLabel'));
      const editorW = start.ed + start.ex + start.ch;
      const pins = {};
      if (start.ch > 0) pins.ch = start.ch;
      if (start.ex > 0) { pins.ex = start.ex; P.view.classList.add('keep-tree'); }
      await layoutPhase({ ex: 0, ed: editorW, ch: 0 }, 420, pins);
      P.view.classList.remove('keep-tree');
      applyLayoutAttrs('agent');
      await layoutPhase({ ex: 0, ed: 0, ch: W }, 520, { ed: editorW });
      refreshLayoutLabels();
      renderChatList();
      if (sideOpen.agent) await layoutPhase({ ex: S, ed: 0, ch: W - S }, 380, { ex: S });
    } else {
      document.documentElement.dataset.tone = 'editor';
      typePillLabel(t('editorLabel'));
      const openPath = ((document.getElementById('open-path') || {}).textContent || '').trim();
      if (typeof setEditorMark === 'function') setEditorMark(!!openPath);
      const wantLeft = sideOpen.editor ? S : 0;
      const wantRight = chatCollapsed ? 0 : C;

      // 1. If the chats sidebar is open, fold it away. A closed one is skipped.
      //    The conversation keeps the agent style while this happens.
      if (start.ex > 8) {
        P.view.classList.add('keep-chats');
        await layoutPhase({ ex: 0, ed: 0, ch: W }, 360, { ex: start.ex });
        P.view.classList.remove('keep-chats');
      }

      // 2. Slide the chat off to the right without restyling it.
      //    The editor is already the full area underneath and does not resize.
      [P.ex, P.ed, P.ch].forEach(el => el.style.setProperty('transition', 'none', 'important'));
      P.ex.style.setProperty('width', '0px', 'important');
      P.ed.style.setProperty('width', W + 'px', 'important');
      P.ed.style.setProperty('flex', '1 1 auto', 'important');
      P.ch.style.setProperty('width', W + 'px', 'important');
      P.ch.style.transform = 'translateX(0)';
      P.view.classList.add('sheet-out');
      void P.view.offsetWidth;
      const slide = motionMs(520);
      P.ch.style.setProperty('transition', slide ? ('transform ' + slide + 'ms ' + LAYOUT_EASE) : 'none', 'important');
      P.view.classList.add('sheet-go');
      P.ch.style.transform = 'translateX(100%)';
      await wait(slide + 40);

      // 3. Chat is gone. Only now open the editor's side panels to their last size.
      P.ch.style.setProperty('transition', 'none', 'important');
      P.ch.style.transform = '';
      P.view.classList.remove('sheet-out', 'sheet-go');
      applyLayoutAttrs('editor');
      refreshLayoutLabels();
      renderChatList();
      freezePanels({ ex: 0, ed: W, ch: 0 });
      if (wantLeft > 0 || wantRight > 0) {
        await layoutPhase(
          { ex: wantLeft, ed: Math.max(0, W - wantLeft - wantRight), ch: wantRight },
          380,
          { ex: wantLeft || null, ch: wantRight || null },
        );
      }
    }
  } finally {
    finishLayoutAnim();
    layoutBusy = false;
  }
}
document.getElementById('mode-pill')?.addEventListener('click', () => switchLayout(layoutMode === 'agent' ? 'editor' : 'agent'));
document.querySelectorAll('#seg-layout button').forEach(b => b.addEventListener('click', () => {
  if (document.documentElement.dataset.phone === '1') {
    desktopLayout = b.dataset.v === 'agent' ? 'agent' : 'editor';
    saveInterface({ layout: desktopLayout });
    document.querySelectorAll('#seg-layout button').forEach(btn => {
      const on = btn.dataset.v === desktopLayout;
      btn.classList.toggle('on', on);
      btn.setAttribute('aria-checked', on ? 'true' : 'false');
    });
    return;
  }
  switchLayout(b.dataset.v);
}));
document.getElementById('side-new-chat')?.addEventListener('click', () => document.getElementById('btn-new-chat')?.click());



/* min / max / step for generated number fields: use the spec when it has them, sane defaults otherwise */
function numAttrs(f) {
  if (!(f.type === 'int' || f.type === 'float')) return '';
  const num = (v) => (v !== undefined && v !== null && v !== '' && isFinite(Number(v))) ? Number(v) : null;
  let min = num(f.minimum != null ? f.minimum : f.min), max = num(f.maximum != null ? f.maximum : f.max);
  const step = num(f.step) || (f.type === 'int' ? 1 : 0.01);
  if (f.key === 'port') { min = Math.max(min == null ? 1 : min, 1); max = Math.min(max == null ? 65535 : max, 65535); }
  if (f.type === 'int' && min == null && /(count|size|limit|retries|iterations|timeout|tokens)/i.test(f.key || '')) min = 0;
  return (min != null ? ' min="' + min + '"' : '') + (max != null ? ' max="' + max + '"' : '') + ' step="' + step + '"';
}

/* ---------- numeric limits for settings ---------- */
(function setupNumberLimits() {
  const root = document.getElementById('view-settings');
  if (!root) return;
  const LIMITS = { port: [1, 65535] };           // keys of generated plugin fields
  const decimals = (step) => { const s = String(step); return s.indexOf('.') >= 0 ? s.split('.')[1].length : 0; };
  function limitsFor(el) {
    let min = el.min !== '' ? Number(el.min) : -Infinity;
    let max = el.max !== '' ? Number(el.max) : Infinity;
    const key = el.dataset.fk || '';
    if (LIMITS[key]) { min = Math.max(min, LIMITS[key][0]); max = Math.min(max, LIMITS[key][1]); }
    if (el.id === 's-timeout') {
      const unit = (document.getElementById('s-timeout-unit') || {}).value;
      max = unit === 'h' ? 24 : unit === 'm' ? 1440 : 86400;
    }
    return [min, max];
  }
  function clamp(el) {
    if (!el || el.type !== 'number' || el.value === '') return;
    let v = Number(el.value);
    if (!isFinite(v)) { el.value = ''; return; }
    const [min, max] = limitsFor(el);
    const step = el.step && el.step !== 'any' ? Number(el.step) : 1;
    if (step > 0) v = Math.round(v / step) * step;
    v = Math.min(max, Math.max(min, v));
    const out = Number(v.toFixed(decimals(step)));
    if (String(out) !== el.value) {
      el.value = String(out);
      el.classList.remove('clamped');
      void el.offsetWidth;
      el.classList.add('clamped');                 // brief amber flash: "we corrected this"
      setTimeout(() => el.classList.remove('clamped'), 900);
    }
  }
  root.addEventListener('change', (ev) => {
    if (ev.target && ev.target.id === 's-timeout-unit') clamp(document.getElementById('s-timeout'));
    else clamp(ev.target);
  }, true);                                        // capture: runs before the dirty-tracking listener
})();

/* ---------- info tooltips ----------
   One floating element on <body>: it cannot be clipped by overflow containers and does not
   add scrollable width. Clicking the "i" shows/pins the tip and never reaches the control it labels. */
(function setupInfoTips() {
  let tip = null, owner = null, pinned = false;
  const ensure = () => {
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'tooltip';
      tip.setAttribute('role', 'tooltip');
      document.body.appendChild(tip);
    }
    return tip;
  };
  const find = (n) => (n && n.closest) ? n.closest('.info-tip') : null;
  function show(el) {
    const text = el.getAttribute('data-tip');
    if (!text) return;
    const t = ensure();
    t.textContent = text;
    t.style.left = '0px'; t.style.top = '0px';
    t.classList.add('on');
    owner = el;
    const r = el.getBoundingClientRect();
    const w = t.offsetWidth, h = t.offsetHeight;
    const left = Math.min(Math.max(8, r.left - 10), window.innerWidth - w - 8);
    let top = r.bottom + 8;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 8);
    t.style.left = left + 'px';
    t.style.top = top + 'px';
  }
  function hide() {
    if (tip) tip.classList.remove('on');
    owner = null; pinned = false;
  }
  document.addEventListener('mouseover', (e) => { const el = find(e.target); if (el && !pinned) show(el); });
  document.addEventListener('mouseout', (e) => {
    const el = find(e.target);
    if (el && !pinned && !(e.relatedTarget && el.contains(e.relatedTarget))) hide();
  });
  document.addEventListener('focusin', (e) => { const el = find(e.target); if (el) show(el); });
  document.addEventListener('focusout', (e) => { if (find(e.target) && !pinned) hide(); });
  document.addEventListener('click', (e) => {
    const el = find(e.target);
    if (el) {
      e.preventDefault();      // a <label> would otherwise toggle its checkbox
      e.stopPropagation();     // and row / panel click handlers must not fire
      if (owner === el && pinned) hide(); else { show(el); pinned = true; }
      return;
    }
    if (pinned) hide();
  }, true);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hide(); });
  window.addEventListener('scroll', () => { if (owner) hide(); }, true);
  window.addEventListener('resize', hide);
})();

/* the plan floats over the messages: keep its height reserved at the top of the list */
(function trackPlanHeight() {
  const box = document.getElementById('plan-float');
  const wrap = document.querySelector('.msgs-wrap');
  if (!box || !wrap) return;
  const update = () => wrap.style.setProperty('--plan-h', box.hidden ? '0px' : (box.offsetHeight + 10) + 'px');
  if (window.ResizeObserver) new ResizeObserver(update).observe(box);
  new MutationObserver(update).observe(box, { attributes: true, attributeFilter: ['hidden', 'class'] });
  update();
})();


