/* ---------- editor: one scroll container + windowed syntax highlight ----------
   .code-wrap is the only scroller. The gutter is sticky inside it, the textarea
   is sized to its content and shows through a transparent text layer, and a <pre>
   behind it paints Prism-highlighted HTML for the visible lines only. Nothing is
   synchronised from scroll events, so the gutter cannot lag behind the text. */
const ED = {
  lineH: 20, padY: 12, padX: 12, gutter: 56,
  lines: 1, maxCols: 0, offsets: [0], charW: 7.8,
  lang: 'none', path: null, hl: true, hlActive: true,
  winFrom: -1, winTo: -1, scrollByPath: {},
};
try { ED.hl = localStorage.getItem('kerniq_hl') !== '0'; } catch (_) {}

function measureEditorChar() {
  const ed = document.getElementById('editor');
  if (!ed) return;
  const cs = getComputedStyle(ed);
  const ctx = measureEditorChar._c || (measureEditorChar._c = document.createElement('canvas').getContext('2d'));
  ctx.font = cs.fontStyle + ' ' + cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
  const w = ctx.measureText('0'.repeat(64)).width / 64;
  if (w > 0) ED.charW = w;
}
function layoutEditor() {
  const wrap = document.getElementById('code-wrap');
  if (!wrap) return;
  wrap.style.setProperty('--code-h', (ED.lines * ED.lineH + ED.padY * 2 + ED.lineH) + 'px');
  wrap.style.setProperty('--code-w', Math.ceil(ED.maxCols * ED.charW + ED.padX + 56) + 'px');
}
function renderCodeWindow(force) {
  const ed = document.getElementById('editor');
  const wrap = document.getElementById('code-wrap');
  const pre = document.querySelector('.hl-pre');
  const code = document.getElementById('hl-code');
  if (!ed || !wrap || !pre || !code) return;
  if (ed.disabled || !activeTab) { code.innerHTML = ''; ED.winFrom = -1; return; }
  const total = ED.lines;
  const first = Math.max(0, Math.floor((wrap.scrollTop - ED.padY) / ED.lineH));
  const last = Math.min(total - 1, first + Math.ceil((wrap.clientHeight || 700) / ED.lineH) + 1);
  const margin = 24;
  if (!force && ED.winFrom >= 0 &&
      (ED.winFrom === 0 || first >= ED.winFrom + margin) &&
      (ED.winTo >= total - 1 || last <= ED.winTo - margin)) return;
  const BUF = 90;
  const from = Math.max(0, first - BUF);
  const to = Math.min(total - 1, last + BUF);
  const text = ed.value;
  const a = ED.offsets[from];
  const b = to + 1 < total ? ED.offsets[to + 1] - 1 : text.length;
  const slice = text.slice(a, b);
  code.innerHTML = ED.hlActive ? highlightCode(slice, ED.lang) : esc(slice);
  pre.style.top = (ED.padY + from * ED.lineH) + 'px';
  ED.winFrom = from; ED.winTo = to;
}
function updateHighlight() { renderCodeWindow(true); }

function updateLineNumbers() {
  const ed = document.getElementById('editor');
  const ln = document.getElementById('line-nums');
  const wrap = document.getElementById('code-wrap');
  if (!ed || !ln || !wrap) return;
  if (ed.disabled || !activeTab) {
    ln.textContent = ''; ln.dataset.n = '';
    ED.lines = 1; ED.path = null; ED.winFrom = -1;
    renderCodeWindow(true);
    wrap.style.setProperty('--code-h', '0px');
    wrap.style.setProperty('--code-w', '0px');
    return;
  }
  const text = ed.value || '';
  // one pass: line starts + widest line (tabs counted as 4 columns)
  const offs = [0];
  let cur = 0, max = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i);
    if (c === 10) { offs.push(i + 1); if (cur > max) max = cur; cur = 0; }
    else if (c === 9) cur += 4;
    else cur++;
  }
  if (cur > max) max = cur;
  ED.offsets = offs; ED.maxCols = max;
  ED.lines = offs.length;
  if (ln.dataset.n !== String(ED.lines)) {          // rebuild gutter only when the line count changes
    const parts = new Array(ED.lines);
    for (let i = 0; i < ED.lines; i++) parts[i] = i + 1;
    ln.textContent = parts.join('\n');
    ln.dataset.n = String(ED.lines);
  }
  ED.lang = langFromPath(activeTab);
  ED.hlActive = ED.hl && ED.lang !== 'none' && text.length < 1500000;
  measureEditorChar();
  layoutEditor();
  if (ED.path !== activeTab) {                      // another file: restore its scroll position
    ED.path = activeTab;
    const sp = ED.scrollByPath[activeTab];
    wrap.scrollTop = sp ? sp.top : 0;
    wrap.scrollLeft = sp ? sp.left : 0;
    ED.winFrom = -1;
  }
  renderCodeWindow(true);
}

function ensureCaretVisible() {
  const ed = document.getElementById('editor');
  const wrap = document.getElementById('code-wrap');
  if (!ed || !wrap || document.activeElement !== ed) return;
  const pos = ed.selectionEnd;
  let lo = 0, hi = ED.offsets.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (ED.offsets[mid] <= pos) lo = mid; else hi = mid - 1; }
  const lineText = ed.value.slice(ED.offsets[lo], pos);
  const cols = lineText.length + (lineText.split('\t').length - 1) * 3;
  const top = ED.padY + lo * ED.lineH, bottom = top + ED.lineH;
  const viewH = wrap.clientHeight, viewW = wrap.clientWidth;
  if (top < wrap.scrollTop) wrap.scrollTop = Math.max(0, top - ED.lineH);
  else if (bottom > wrap.scrollTop + viewH - 14) wrap.scrollTop = bottom - viewH + ED.lineH * 2;
  const x = ED.gutter + ED.padX + cols * ED.charW;
  if (x < wrap.scrollLeft + ED.gutter + 8) wrap.scrollLeft = Math.max(0, x - ED.gutter - 40);
  else if (x > wrap.scrollLeft + viewW - 24) wrap.scrollLeft = x - viewW + 48;
}

(function setupEditor() {
  const ed = document.getElementById('editor');
  const wrap = document.getElementById('code-wrap');
  if (!ed || !wrap) return;
  wrap.addEventListener('scroll', () => {
    if (activeTab) ED.scrollByPath[activeTab] = { top: wrap.scrollTop, left: wrap.scrollLeft };
    renderCodeWindow(false);
  }, { passive: true });
  // the textarea itself must never scroll: that would detach it from the highlight layer
  ed.addEventListener('scroll', () => { if (ed.scrollTop || ed.scrollLeft) { ed.scrollTop = 0; ed.scrollLeft = 0; } });
  ed.addEventListener('keyup', (e) => {
    if (/^(Arrow|Page|Home|End)/.test(e.key)) ensureCaretVisible();
  });
  if (window.ResizeObserver) {
    let raf = 0;
    new ResizeObserver(() => {
      if (raf) return;
      raf = requestAnimationFrame(() => { raf = 0; renderCodeWindow(true); });
    }).observe(wrap);
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { measureEditorChar(); layoutEditor(); });

  // Tab / Shift+Tab indent, Enter keeps indentation
  const IND = '    ';
  const fire = () => ed.dispatchEvent(new Event('input', { bubbles: true }));
  ed.addEventListener('keydown', (e) => {
    if (ed.disabled || e.isComposing || e.ctrlKey || e.metaKey || e.altKey) return;
    const v = ed.value, s = ed.selectionStart, en = ed.selectionEnd;
    if (e.key === 'Tab') {
      e.preventDefault();
      if (s === en && !e.shiftKey) { ed.setRangeText(IND, s, en, 'end'); fire(); return; }
      const ls = v.lastIndexOf('\n', s - 1) + 1;
      const endAdj = (en > s && v[en - 1] === '\n') ? en - 1 : en;
      let le = v.indexOf('\n', endAdj); if (le < 0) le = v.length;
      const out = v.slice(ls, le).split('\n')
        .map(l => e.shiftKey ? l.replace(/^( {1,4}|\t)/, '') : IND + l).join('\n');
      ed.setRangeText(out, ls, le, 'select');
      fire();
    } else if (e.key === 'Enter' && !e.shiftKey && s === en) {
      const ls = v.lastIndexOf('\n', s - 1) + 1;
      const indent = v.slice(ls, s).match(/^[ \t]*/)[0];
      const prev = v[s - 1], nextCh = v[s];
      const codey = ED.lang !== 'none' && ED.lang !== 'markdown';
      const colon = ED.lang === 'python' || ED.lang === 'yaml';
      const opens = prev !== undefined && ((codey && '{(['.indexOf(prev) >= 0) || (colon && prev === ':'));
      e.preventDefault();
      if (opens && prev !== ':' && nextCh !== undefined && '})]'.indexOf(nextCh) >= 0) {
        ed.setRangeText('\n' + indent + IND + '\n' + indent, s, en, 'preserve');
        const caret = s + 1 + indent.length + IND.length;
        ed.setSelectionRange(caret, caret);
      } else {
        ed.setRangeText('\n' + indent + (opens ? IND : ''), s, en, 'end');
      }
      fire();
    }
  });
})();

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function developerOn() {
  const box = document.getElementById('s-chat-debug');
  if (box) return !!box.checked;
  return !!(settings && settings.chat && settings.chat.developer_mode);
}
function motionOff() {
  const mode = document.documentElement.dataset.motion || 'on';
  if (mode === 'off') return true;
  if (mode === 'auto') {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (_) { return false; }
  }
  return false;
}
let showNotifications = true;
let autoDismissToasts = true;
function explainStatus(text) {
  const raw = String(text || '');
  const known = {
    empty_response: 'Empty response',
    provider_error: 'Provider error',
    no_plan: 'The model did not write a plan',
    max_iterations: 'Iteration limit reached',
    content_loop: 'The model repeated itself',
    tool_loop: 'The model repeated a tool',
    verification_failed: 'Verification failed',
  };
  return translate(known[raw] || raw);
}
function toast(msg, err, detail, sticky) {
  if (!showNotifications) return;
  let stack = document.getElementById('toast-stack');
  if (!stack) {
    stack = document.createElement('div');
    stack.id = 'toast-stack';
    stack.className = 'toast-stack';
    document.body.appendChild(stack);
  }
  const el = document.createElement('div');
  el.className = 'toast' + (err ? ' err' : '');
  const text = document.createElement('span');
  text.className = 'toast-text';
  text.textContent = msg == null ? '' : String(msg);
  el.appendChild(text);
  const extra = detail == null ? '' : String(detail).trim();
  if (extra && extra !== String(msg || '').trim() && (err || developerOn())) {
    const more = document.createElement('span');
    more.className = 'toast-detail';
    more.textContent = extra.length > 900 ? extra.slice(0, 900) + '…' : extra;
    text.appendChild(document.createElement('br'));
    text.appendChild(more);
  }
  if (sticky || !autoDismissToasts) {
    el.classList.add('sticky');
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'toast-x';
    close.setAttribute('aria-label', 'Close');
    close.textContent = '×';
    close.onclick = (ev) => { ev.stopPropagation(); dismissToast(el); };
    el.appendChild(close);
  }
  stack.appendChild(el);
  const reveal = () => el.classList.add('show');
  if (motionOff()) reveal();
  else requestAnimationFrame(() => requestAnimationFrame(reveal));
  if (!sticky && autoDismissToasts) {
    const life = err ? 4200 : 2400;
    el._timer = setTimeout(() => dismissToast(el), life);
  }
}
function dismissToast(el) {
  if (!el || !el.parentNode || el.classList.contains('leave')) return;
  clearTimeout(el._timer);
  el.classList.remove('show');
  el.classList.add('leave');
  const drop = () => { if (el.parentNode) el.parentNode.removeChild(el); };
  if (motionOff()) drop();
  else el.addEventListener('transitionend', drop, { once: true });
  setTimeout(drop, motionOff() ? 0 : 400);
}

function setStatus(text, spinning) {
  const st = document.getElementById('agent-status');
  const spin = document.getElementById('agent-spin');
  if (st) st.textContent = text == null ? '' : String(text);
  if (spin) {
    if (spinning) spin.classList.add('on');
    else spin.classList.remove('on');
  }
  // keep footer state in sync lightly
  try {
    if (spinning) setFooterState('run');
    else if (String(text || '').toLowerCase().includes('error')) setFooterState('err');
    else setFooterState('idle');
  } catch (_) {}
}
function loadChats() {
  chats = [];
}
function saveChats() {
  if (chats.length > MAX_CHATS) {
    chats = chats.slice(-MAX_CHATS);
    if (!chats.find(c => c.id === activeChatId)) {
      activeChatId = chats.length ? chats[chats.length - 1].id : null;
    }
  }
  clearTimeout(saveChats._t);
  saveChats._t = setTimeout(() => {
    api('/api/ui/chats', {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chats }),
    }).catch(() => {});
  }, 250);
}
async function loadChatsFromServer() {
  dropBrowserState();
  try {
    const data = await api('/api/ui/chats');
    chats = Array.isArray(data && data.chats) ? data.chats : [];
  } catch (_) { chats = []; }
  if (chats.length > MAX_CHATS) chats = chats.slice(-MAX_CHATS);
  chats.forEach(c => {
    if (c.prompt_tokens == null) c.prompt_tokens = null;
    if (c.context_limit == null) c.context_limit = null;
    if (!Array.isArray(c.messages)) c.messages = [];
  });
  if (!chats.find(c => c.id === activeChatId)) activeChatId = chats.length ? chats[chats.length - 1].id : null;
}
function dropBrowserState() {
  try {
    ['kerniq_chats_v1', 'kerniq_chats', 'kerniq_layout', 'kerniq_motion', 'kerniq_hl',
     'kerniq_auto_think', 'kerniq_agent_mode', 'kerniq_plan_collapsed', 'kerniq_panels_v1',
     'kerniq_side_open'].forEach(key => localStorage.removeItem(key));
  } catch (_) {}
}


function fmtTokens(n) {
  if (n == null || isNaN(n)) return '—';
  n = Number(n);
  if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, '') + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, '') + 'K';
  return String(Math.round(n));
}

function estimateChatTokens() {
  // Heuristic only when server usage is unknown.
  // ~4 chars/token is the common Latin estimate (OpenAI tokenizer ≈ 4 chars/token on English).
  // For Cyrillic/CJK use ~2 chars/token. Mixed: per-message.
  const c = currentChat();
  let charsLat = 0, charsCjk = 0;
  const add = (s) => {
    s = String(s || '');
    for (const ch of s) {
      const code = ch.codePointAt(0);
      // CJK + Cyrillic denser tokens
      if ((code >= 0x0400 && code <= 0x04FF) || (code >= 0x3040 && code <= 0x30FF) ||
          (code >= 0x3400 && code <= 0x9FFF) || (code >= 0xAC00 && code <= 0xD7AF)) {
        charsCjk += 1;
      } else {
        charsLat += 1;
      }
    }
  };
  if (c) {
    for (const m of (c.messages || [])) {
      add(m.content); add(m.text); add(m.summary);
      if (m.args) add(JSON.stringify(m.args));
      if (m.name) add(m.name);
      // tool results stored in content for role tool
    }
  }
  // System prompt + tool schemas also go into the real model request
  try {
    if (settings && settings.prompt && settings.prompt.system_prompt) add(settings.prompt.system_prompt);
  } catch (_) {}
  try {
    // Approximate tool catalog: ~400 tokens base + names
    if (settings && settings.prompt && settings.prompt.include_tool_catalog !== false) {
      charsLat += 1600; // ~400 tokens of tool JSON schemas
    }
  } catch (_) {}
  const est = Math.round(charsLat / 4 + charsCjk / 2);
  return Math.max(0, est);
}

let _modelContextLimit = null; // tokens — loaded window when known
let _lastPromptTokens = null; // from provider usage (real)
let _lastCompletionTokens = null;
let _toolsSchemaTokens = 400; // approx when tool catalog enabled


let footerActivity = 'idle';
let modelLoaded = false;
let providerReachable = null;
function setFooterActivity(mode) {
  footerActivity = mode || 'idle';
  const dot = document.getElementById('footer-dot');
  if (!dot) return;
  const cls = footerActivity === 'err' ? 'err'
    : footerActivity === 'work' || footerActivity === 'wait' ? 'work'
    : footerActivity === 'loaded' ? 'loaded'
    : footerActivity === 'loading' ? 'loading'
    : 'idle';
  dot.className = 'dot ' + cls;
}
function settleFooter() {
  if (running) return;
  if (providerReachable === false) setFooterActivity('err');
  else if (modelLoaded) setFooterActivity('loaded');
  else setFooterActivity('idle');
}
function setFooterState(mode) {
  setFooterActivity(mode);
}
function setFooterProvider(name, ok) {
  const el = document.getElementById('footer-provider');
  if (el) el.textContent = t('provider') + ': ' + (name || '—');
  if (ok === false) providerReachable = false;
  else if (ok === true) providerReachable = true;
  if (!running) settleFooter();
}

function setFooterContext(used, limit) {
  const el = document.getElementById('footer-ctx');
  if (!el) return;
  if (limit == null) limit = _modelContextLimit;
  if (used == null) used = _lastPromptTokens;
  // Sticky: do not clear a good value with null (stops 17K <-> — flicker)
  if (used == null && el.dataset.lastUsed) used = Number(el.dataset.lastUsed);
  if ((limit == null || !(limit > 0)) && el.dataset.lastLimit) limit = Number(el.dataset.lastLimit);
  if (used != null && used >= 0) el.dataset.lastUsed = String(used);
  if (limit != null && limit > 0) el.dataset.lastLimit = String(limit);
  if (limit && limit > 0) {
    if (used != null && used >= 0) {
      const pct = Math.min(100, (used / limit) * 100);
      const pctStr = pct >= 10 ? String(Math.round(pct)) : pct.toFixed(1);
      el.textContent = t('ctx') + ': ' + fmtTokens(used) + '/' + fmtTokens(limit) + ' (' + pctStr + '%)';
    } else {
      el.textContent = t('ctx') + ': —/' + fmtTokens(limit);
    }
  } else if (used != null && used >= 0) {
    el.textContent = t('ctx') + ': ' + fmtTokens(used) + '/—';
  } else {
    el.textContent = t('ctx') + ': —';
  }
}
// Rolling tok/s: 4 one-second buckets (3 past + current). Only while streaming generation.
let tpsBuckets = []; // [{sec: number, tokens: number}]
let tpsTimer = null;
let tokensThisSecond = 0;
let currentSec = 0;

function _estimateTokens(text) {
  const s = String(text || '');
  if (!s) return 0;
  // rough: ~4 chars per token for latin, ~2 for denser scripts
  return Math.max(1, Math.round(s.length / 4));
}

function _tpsTick() {
  const el = document.getElementById('footer-tps');
  if (!el) return;
  if (!streamingEnabled) {
    el.style.display = 'none';
    el.textContent = '';
    return;
  }
  el.style.display = '';
  const sec = Math.floor(Date.now() / 1000);
  if (sec !== currentSec) {
    if (currentSec) tpsBuckets.push({ sec: currentSec, tokens: tokensThisSecond });
    currentSec = sec;
    tokensThisSecond = 0;
  }
  tpsBuckets = tpsBuckets.filter(b => sec - b.sec < 4);
  const all = tpsBuckets.slice();
  if (generatingTokens) all.push({ sec, tokens: tokensThisSecond });
  const sum = all.reduce((a, b) => a + (b.tokens || 0), 0);
  const avg = generatingTokens ? (sum / 4) : 0;
  el.textContent = avg.toFixed(1) + ' tok/s';
}

function noteGeneratedText(text) {
  if (!text) return;
  generatingTokens = true;
  const sec = Math.floor(Date.now() / 1000);
  if (sec !== currentSec) {
    if (currentSec) tpsBuckets.push({ sec: currentSec, tokens: tokensThisSecond });
    currentSec = sec;
    tokensThisSecond = 0;
  }
  tokensThisSecond += _estimateTokens(text);
  _tpsTick();
}

function resetTps(hide) {
  generatingTokens = false;
  tokensThisSecond = 0;
  currentSec = 0;
  tpsBuckets = [];
  const el = document.getElementById('footer-tps');
  if (!el) return;
  if (!streamingEnabled || hide) {
    el.style.display = 'none';
    el.textContent = '';
    return;
  }
  el.style.display = '';
  el.textContent = '0.0 tok/s';
}

function startTpsTimer() {
  if (tpsTimer) return;
  tpsTimer = setInterval(_tpsTick, 1000);
}
function stopTpsTimer() {
  if (tpsTimer) { clearInterval(tpsTimer); tpsTimer = null; }
}

function setFooterTps(n) {
  // legacy single-shot: treat as instantaneous rate sample into current bucket
  if (!streamingEnabled) return;
  if (n == null || n === 0) {
    if (!generatingTokens) resetTps(false);
    return;
  }
  generatingTokens = true;
  const sec = Math.floor(Date.now() / 1000);
  if (sec !== currentSec) {
    if (currentSec) tpsBuckets.push({ sec: currentSec, tokens: tokensThisSecond });
    currentSec = sec;
    tokensThisSecond = 0;
  }
  tokensThisSecond += Number(n);
  _tpsTick();
}

function setFooterModelStatus(text, ok) {
  const el = document.getElementById('footer-model');
  if (!el) return;
  if (footerActivity === 'loading') {
    text = t('model') + ': ' + t('loading');
    ok = null;
  }
  el.textContent = text || '';
  el.classList.toggle('bad', ok === false);
  el.classList.toggle('ok', ok === true);
  el.classList.toggle('foreign', ok === 'foreign');
}

function settingsOpen() { return document.body.classList.contains('settings-mode'); }
function showView(n) {
  const open = n === 'settings';
  if (open) {
    document.documentElement.classList.remove('chats-open');
    document.body.classList.remove('chats-open');
  }
  const bar = document.querySelector('.settings-actions');
  if (open) bar.style.display = 'flex';
  else setTimeout(() => { if (!settingsOpen()) bar.style.display = 'none'; }, 420);   // after the slide-up
  document.body.classList.toggle('settings-mode', open);
  const mainView = document.getElementById('view-main');
  if (mainView) mainView.inert = open;
  const btn = document.getElementById('nav-settings');
  if (btn && n === 'main') {
    btn.classList.remove('active-settings');
    btn.textContent = '⚙';
    btn.title = 'Settings';
  }
  if (n === 'main') {
    window._renderPaused = false;
    renderMessages();
  }
}

/* panels */
function setPanelContentWidth(panel, w) {
  if (panel) panel.style.setProperty('--panel-w', w + 'px');
}
function loadPanelWidths() {
  try {
    applyStoredPanelSizes();
    const p = readPanelStore();
    if (p.explorerCollapsed) setExplorerCollapsed(true, true);
    if (p.chatCollapsed) setChatCollapsed(true, true);
  } catch {}
}
const LS_SIDE = 'kerniq_side_open';
const sideOpen = { editor: true, agent: true };
function loadSideOpen() {
  try {
    const s = JSON.parse(localStorage.getItem(LS_SIDE) || 'null');
    if (s && typeof s === 'object') { sideOpen.editor = s.editor !== false; sideOpen.agent = s.agent !== false; return; }
    const p = JSON.parse(localStorage.getItem(LS_PANEL) || '{}');
    sideOpen.editor = !p.explorerCollapsed;
  } catch (_) {}
}
function saveSideOpen() { try { localStorage.setItem(LS_SIDE, JSON.stringify(sideOpen)); } catch (_) {} }
loadSideOpen();
function clampPanelSize(side, v) {
  const n = Number(v);
  if (!isFinite(n) || n <= 0 || n > window.innerWidth * 0.8) return side === 'left' ? 280 : 380;   // absurd value: start over
  const max = Math.floor(window.innerWidth * 0.5);
  return Math.max(side === 'left' ? 250 : 280, Math.min(max, Math.round(n)));
}
function readPanelStore() {
  try { return JSON.parse(localStorage.getItem(LS_PANEL) || '{}') || {}; } catch (_) { return {}; }
}
function storedPanelSizes() {
  const p = readPanelStore();
  return { left: clampPanelSize('left', p.left), right: clampPanelSize('right', p.right) };
}
function applyStoredPanelSizes() {
  const s = storedPanelSizes();
  const ex = document.getElementById('explorer'), ch = document.getElementById('chat-panel');
  ex.style.width = s.left + 'px'; ex.style.minWidth = 'min(' + s.left + 'px, 50%)'; setPanelContentWidth(ex, s.left);
  ch.style.width = s.right + 'px'; ch.style.minWidth = 'min(' + s.right + 'px, 50%)'; setPanelContentWidth(ch, s.right);
}
function savePanelWidths() {
  const prev = readPanelStore();
  const animating = document.getElementById('view-main').classList.contains('layout-anim');
  const exW = document.getElementById('explorer').offsetWidth;
  const chW = document.getElementById('chat-panel').offsetWidth;
  // the chat only has "its own" width in the editor layout; in agent mode it spans the window
  const left = (explorerCollapsed || animating) ? prev.left : exW;
  const right = (chatCollapsed || animating || layoutMode === 'agent') ? prev.right : chW;
  localStorage.setItem(LS_PANEL, JSON.stringify({
    left: clampPanelSize('left', left), right: clampPanelSize('right', right),
    explorerCollapsed, chatCollapsed,
  }));
}
function setExplorerCollapsed(v, skipSave) {
  explorerCollapsed = v;
  document.getElementById('explorer').classList.toggle('collapsed', v);
  document.getElementById('btn-toggle-explorer').classList.toggle('on', !v);
  if (!skipSave) { sideOpen[layoutMode] = !v; saveSideOpen(); savePanelWidths(); }
}
function setChatCollapsed(v, skipSave) {
  chatCollapsed = v;
  document.getElementById('chat-panel').classList.toggle('collapsed', v);
  document.getElementById('btn-toggle-chat').classList.toggle('on', !v);
  if (!skipSave) savePanelWidths();
}
function bindResizer(id, side) {
  const el = document.getElementById(id);
  if (!el) return;
  let drag = null;                       // { startX, startW, panel, pointerId }

  const stop = () => {
    if (!drag) return;
    const pid = drag.pointerId;
    drag = null;
    document.body.classList.remove('resizing-panels');
    el.classList.remove('active', 'at-limit');
    try { if (el.hasPointerCapture(pid)) el.releasePointerCapture(pid); } catch (_) {}
    savePanelWidths();
  };
  el.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || layoutBusy) return;
    e.preventDefault();
    e.stopPropagation();
    const panel = document.getElementById(side === 'left' ? 'explorer' : 'chat-panel');
    if (side === 'left' && explorerCollapsed) setExplorerCollapsed(false, true);
    if (side === 'right' && chatCollapsed) setChatCollapsed(false, true);
    // capture: moves and the release keep coming to this element even outside the window
    try { el.setPointerCapture(e.pointerId); } catch (_) {}
    drag = { startX: e.clientX, startW: panel.getBoundingClientRect().width || (side === 'left' ? 280 : 380), panel, pointerId: e.pointerId };
    document.body.classList.add('resizing-panels');
    el.classList.add('active');
  });
  el.addEventListener('pointermove', (e) => {
    if (!drag) return;
    if (e.buttons === 0) { stop(); return; }          // the release was lost somewhere: end the drag
    e.preventDefault();
    const max = Math.floor(window.innerWidth * 0.5);
    const min = side === 'left' ? 250 : 280;
    const raw = side === 'left' ? drag.startW + (e.clientX - drag.startX) : drag.startW - (e.clientX - drag.startX);
    if (raw < 40) {
      if (side === 'left') setExplorerCollapsed(true); else setChatCollapsed(true);
      el.classList.add('at-limit');
      return;
    }
    if (side === 'left' && explorerCollapsed) setExplorerCollapsed(false, true);
    if (side === 'right' && chatCollapsed) setChatCollapsed(false, true);
    const w = Math.max(min, Math.min(max, raw));
    el.classList.toggle('at-limit', w !== raw);       // the line turns amber at the size limit
    drag.panel.style.width = w + 'px';
    drag.panel.style.minWidth = w + 'px';
    setPanelContentWidth(drag.panel, w);
  });
  el.addEventListener('pointerup', stop);
  el.addEventListener('pointercancel', stop);
  el.addEventListener('lostpointercapture', stop);
  window.addEventListener('blur', stop);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
}

/* undo/redo */
function pushUndo(entry) {
  undoStack.push(entry);
  if (undoStack.length > undoLimit) undoStack.shift();
  redoStack = [];
  updateUndoBtns();
}
function updateUndoBtns() {
  document.getElementById('btn-undo').disabled = !undoStack.length;
  document.getElementById('btn-redo').disabled = !redoStack.length;
}
function doUndo() {
  const e = undoStack.pop();
  if (!e) return;
  applyInverse(e);
  redoStack.push(e);
  updateUndoBtns();
}
function doRedo() {
  const e = redoStack.pop();
  if (!e) return;
  applyAction(e);
  undoStack.push(e);
  updateUndoBtns();
}
function applyAction(e) {
  if (e.type === 'edit') {
    const t = openTabs.find(x => x.path === e.path);
    if (t) { t.content = e.after; t.dirty = e.dirtyAfter; if (activeTab === e.path) document.getElementById('editor').value = e.after; updateLineNumbers(); }
  } else if (e.type === 'open') {
    openFile(e.path, true);
  } else if (e.type === 'close') {
    closeTab(e.path, true, true);
  }
}
function applyInverse(e) {
  if (e.type === 'edit') {
    const t = openTabs.find(x => x.path === e.path);
    if (t) { t.content = e.before; t.dirty = e.dirtyBefore; if (activeTab === e.path) document.getElementById('editor').value = e.before; updateLineNumbers(); }
  } else if (e.type === 'open') {
    closeTab(e.path, true, true);
  } else if (e.type === 'close') {
    // reopen
    if (!openTabs.find(x => x.path === e.path)) {
      openTabs.push({ path: e.path, content: e.content || '', dirty: !!e.dirty });
    }
    activeTab = e.path;
    renderTabs();
    const t = openTabs.find(x => x.path === e.path);
    document.getElementById('editor').value = t.content;
    document.getElementById('editor').disabled = false;
    document.getElementById('open-path').textContent = e.path;
    updateLineNumbers();
  }
}

/* tree */
function buildTree(entries) {
  const root = { name: '', path: '', type: 'dir', children: {} };
  for (const e of entries) {
    const parts = e.path.replace(/\\/g, '/').split('/').filter(Boolean);
    let node = root;
    parts.forEach((part, i) => {
      const isLast = i === parts.length - 1;
      if (!node.children[part]) {
        node.children[part] = { name: part, path: parts.slice(0, i + 1).join('/'), type: isLast ? e.type : 'dir', hidden: isLast ? !!e.hidden : (part.startsWith('.')), children: {} };
      } else if (!isLast) node.children[part].type = 'dir';
      node = node.children[part];
    });
  }
  return root;
}
async function refreshTree(silent) {
  const data = await api('/api/fs/tree' + (silent ? '' : '?fresh=1'));   // the poll may be served from a short server cache
  if (data.error) { if (!silent) document.getElementById('tree').textContent = data.error; return; }
  const key = JSON.stringify(data.entries || []);
  if (silent && key === refreshTree._last) return;
  refreshTree._last = key;
  treeData = data.entries || [];
  paintWorkspaceLabel(data.workspace);
  renderTree();
}
const TWIST_SVG = '<svg viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"><path d="M4 2.5 7.5 6 4 9.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const DIR_SVG = '<svg class="fi dir" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.5h7.5A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/></svg>';
function fileSvg(name) {
  const ext = (String(name).split('.').pop() || '').toLowerCase();
  return '<svg class="fi" data-ext="' + esc(ext) + '" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/></svg>';
}
function renderTree() {
  const root = buildTree(treeData);
  const el = document.getElementById('tree');
  el.innerHTML = '';
  el.oncontextmenu = (ev) => {
    if (ev.target !== el && !ev.target.classList.contains('tree')) return;
    ev.preventDefault();
    showCtx(ev, '', true, true);
  };

  const walk = (node, depth) => {
    const kids = Object.values(node.children).sort((a, b) => {
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const ch of kids) {
      const row = document.createElement('div');
      row.className = 'row' + (ch.path === activeTab ? ' active' : '');
      row.style.paddingLeft = (4 + depth * 14) + 'px';
      const open = expanded.has(ch.path);
      if (ch.type === 'dir') {
        row.innerHTML = `<span class="twist${open ? ' open' : ''}">${TWIST_SVG}</span>${DIR_SVG}<span class="fname">${esc(ch.name)}</span>`;
        if (ch.hidden) row.classList.add('hidden-entry');
        row.onclick = () => { if (expanded.has(ch.path)) expanded.delete(ch.path); else expanded.add(ch.path); renderTree(); };
        row.oncontextmenu = ev => { ev.preventDefault(); showCtx(ev, ch.path, true); };
        el.appendChild(row);
        if (open) walk(ch, depth + 1);
      } else {
        row.innerHTML = `<span class="twist"></span>${fileSvg(ch.name)}<span class="fname">${esc(ch.name)}</span>`;
        if (ch.hidden) row.classList.add('hidden-entry');
        row.onclick = () => openFile(ch.path);
        row.oncontextmenu = ev => { ev.preventDefault(); showCtx(ev, ch.path, false); };
        el.appendChild(row);
      }
    }
  };
  walk(root, 0);
}
let treePoll = null;
function startTreePoll() { stopTreePoll(); treePoll = setInterval(() => refreshTree(true), 2500); }
function stopTreePoll() { if (treePoll) clearInterval(treePoll); treePoll = null; }

function showCtx(ev, path, isDir, isRoot) {
  const ctx = document.getElementById('ctx');
  ctx.className = 'ctx';
  ctx.style.display = 'block';
  ctx.style.bottom = 'auto';
  ctx.style.maxHeight = '';
  ctx.style.left = ev.clientX + 'px';
  ctx.style.top = ev.clientY + 'px';
  const parent = isDir ? path : (path ? path.split('/').slice(0, -1).join('/') : '');
  let html = '';
  if (!isRoot && !isDir) html += `<button data-a="open">${'Open'}</button>`;
  html += `<button data-a="newfile">${t('createFile')}</button>`;
  html += `<button data-a="newdir">${t('createDir')}</button>`;
  if (serverModeOn()) html += `<button data-a="download">${t('download')}</button>`;
  if (!serverModeOn()) html += `<button data-a="reveal">${t('reveal')}</button>`;
  if (!isRoot && path) {
    html += `<button data-a="rename">${t('rename')}</button>`;
    html += `<button data-a="delete" style="color:var(--err)">${t('delete')}</button>`;
  }
  ctx.innerHTML = html;
  // keep the menu inside the window (right-click near an edge used to clip it)
  ctx.style.left = Math.max(8, Math.min(ev.clientX, window.innerWidth - ctx.offsetWidth - 8)) + 'px';
  ctx.style.top = Math.max(8, Math.min(ev.clientY, window.innerHeight - ctx.offsetHeight - 8)) + 'px';
  ctx.querySelectorAll('button').forEach(b => {
    b.onclick = async () => {
      hideCtx();
      const a = b.dataset.a;
      if (a === 'open') openFile(path);
      else if (a === 'newfile' || a === 'newdir') {
        const name = await askName(a === 'newdir' ? t('createDir') : t('createFile'), '');
        if (!name) return;
        const full = parent ? (parent + '/' + name) : name;
        const r = await api('/api/fs/create', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: full, kind: a === 'newdir' ? 'dir' : 'file' }),
        });
        if (r.error) toast(r.error, true);
        else {
          if (parent) expanded.add(parent);
          await refreshTree();
          if (a === 'newfile') openFile(full);
          toast('Created');
        }
      } else if (a === 'download') {
        await downloadWorkspacePath(isRoot ? '' : path);
      } else if (a === 'reveal') {
        const r = await api('/api/fs/reveal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: path || '.' }) });
        if (r.error) toast(r.error, true); else toast('Opened');
      } else if (a === 'rename') {
        const base = path.split('/').pop();
        const nn = await askName(t('rename'), base);
        if (!nn || nn === base) return;
        const r = await api('/api/fs/rename', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, new_name: nn }) });
        if (r.error) toast(r.error, true);
        else { toast('Renamed'); await refreshTree(); }
      } else if (a === 'delete') {
        if (!await askConfirm(translate('Delete this path?') + '\n' + path, { danger: true, ok: translate('Delete') })) return;
        const r = await api('/api/fs/file?path=' + encodePath(path), { method: 'DELETE' });
        if (r.error) toast(r.error, true);
        else { toast('Deleted'); openTabs = openTabs.filter(t => t.path !== path); if (activeTab === path) clearEditor(); await refreshTree(); renderTabs(); }
      }
    };
  });
}
function hideCtx() {
  mentionOpen = false;
  const ctx = document.getElementById('ctx');
  if (ctx) ctx.style.display = 'none';
}
let confirmChain = Promise.resolve();
function askConfirm(message, opts) {
  const run = () => new Promise(resolve => {
    const bg = document.getElementById('confirm-modal');
    const text = document.getElementById('confirm-text');
    const title = document.getElementById('confirm-title');
    const okBtn = document.getElementById('confirm-ok');
    const cancelBtn = document.getElementById('confirm-cancel');
    if (!bg || !okBtn || !cancelBtn) { resolve(window.confirm(message)); return; }
    if (title) title.textContent = (opts && opts.title) || translate('Confirm');
    if (text) text.textContent = message || '';
    okBtn.textContent = (opts && opts.ok) || translate('Confirm');
    cancelBtn.textContent = (opts && opts.cancel) || translate('Cancel');
    okBtn.classList.toggle('danger', !!(opts && opts.danger));
    okBtn.classList.toggle('save-active', !(opts && opts.danger));
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      bg.classList.remove('on');
      if (!document.querySelector('.modal-bg.on')) document.body.classList.remove('modal-open');
      document.removeEventListener('keydown', onKey);
      resolve(!!value);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); finish(false); }
      else if (e.key === 'Enter') { e.preventDefault(); finish(true); }
    };
    okBtn.onclick = () => finish(true);
    cancelBtn.onclick = () => finish(false);
    bg.onclick = (e) => { if (e.target === bg) finish(false); };
    document.addEventListener('keydown', onKey);
    bg.classList.add('on');
    document.body.classList.add('modal-open');
    okBtn.focus();
  });
  const next = confirmChain.then(run, run);
  confirmChain = next.then(() => {}, () => {});
  return next;
}
function askName(title, initial) {
  return new Promise(resolve => {
    const bg = document.getElementById('name-modal');
    const input = document.getElementById('name-input');
    const heading = document.getElementById('name-title');
    const okBtn = document.getElementById('name-ok');
    const cancelBtn = document.getElementById('name-cancel');
    if (!bg || !input || !okBtn || !cancelBtn) { resolve(null); return; }
    if (heading) heading.textContent = title || t('nameTitle');
    input.value = initial || '';
    okBtn.textContent = translate('OK');
    cancelBtn.textContent = translate('Cancel');
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      bg.classList.remove('on');
      if (!document.querySelector('.modal-bg.on')) document.body.classList.remove('modal-open');
      document.removeEventListener('keydown', onKey);
      resolve(value);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); finish(null); }
      else if (e.key === 'Enter') { e.preventDefault(); finish(String(input.value || '').trim() || null); }
    };
    okBtn.onclick = () => finish(String(input.value || '').trim() || null);
    cancelBtn.onclick = () => finish(null);
    bg.onclick = (e) => { if (e.target === bg) finish(null); };
    document.addEventListener('keydown', onKey);
    bg.classList.add('on');
    document.body.classList.add('modal-open');
    setTimeout(() => { input.focus(); input.select(); }, 30);
  });
}
async function downloadWorkspacePath(path) {
  try {
    const response = await fetch('/api/fs/download?path=' + encodeURIComponent(path || ''), { credentials: 'same-origin' });
    const type = response.headers.get('content-type') || '';
    if (!response.ok || type.indexOf('application/json') >= 0) {
      let msg = t('downloadFailed');
      try {
        const body = await response.json();
        if (body && body.error) msg = body.error;
      } catch (_) {}
      toast(msg, true);
      return;
    }
    const blob = await response.blob();
    const disp = response.headers.get('content-disposition') || '';
    const match = /filename="([^"]+)"/.exec(disp);
    const name = match ? match[1] : 'download';
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (_) {
    toast(t('downloadFailed'), true);
  }
}
document.addEventListener('click', hideCtx);

/* editor */
function clearEditor() {
  activeTab = null;
  document.getElementById('editor').value = '';
  document.getElementById('editor').disabled = true;
  document.getElementById('open-path').textContent = '';
  document.getElementById('btn-save').disabled = true;
  setEditorMark(false);
  updateLineNumbers();
}
async function openFile(path, skipUndo) {
  let tab = openTabs.find(t => t.path === path);
  const wasOpen = !!tab;
  if (!tab) {
    const data = await api('/api/fs/file?path=' + encodePath(path));
    if (data.error) { toast(data.error, true); return; }
    tab = { path, content: data.content || '', dirty: false };
    openTabs.push(tab);
    if (!skipUndo) pushUndo({ type: 'open', path });
  }
  activeTab = path;
  renderTabs();
  const ed = document.getElementById('editor');
  ed.disabled = false;
  ed.value = tab.content;
  document.getElementById('open-path').textContent = path;
  document.getElementById('btn-save').disabled = !tab.dirty;
  setEditorMark(true);
  updateLineNumbers();
  renderTree();
}
function renderTabs() {
  const el = document.getElementById('tabs');
  el.innerHTML = '';
  openTabs.forEach(t => {
    const d = document.createElement('div');
    d.className = 'tab' + (t.path === activeTab ? ' active' : '');
    const name = t.path.split(/[/\\]/).pop();
    d.innerHTML = `<span class="dirty">${t.dirty ? '•' : ''}</span><span class="name"></span><span class="x">×</span>`;
    d.querySelector('.name').textContent = name;
    d.title = t.path;
    d.onclick = () => openFile(t.path);
    d.querySelector('.x').onclick = ev => { ev.stopPropagation(); closeTab(t.path, false); };
    el.appendChild(d);
  });
}
function closeTab(path, force, skipUndo) {
  const tab = openTabs.find(x => x.path === path);
  if (!tab) return;
  if (tab.dirty && !force) {
    askConfirm(translate('File has changes. Close without saving?')).then(ok => {
      if (ok) closeTab(path, true, skipUndo);
    });
    return;
  }
  if (!skipUndo) pushUndo({ type: 'close', path, content: tab.content, dirty: tab.dirty });
  openTabs = openTabs.filter(x => x.path !== path);
  if (activeTab === path) {
    activeTab = openTabs.length ? openTabs[openTabs.length - 1].path : null;
    if (activeTab) openFile(activeTab, true);
    else clearEditor();
  }
  renderTabs();
  renderTree();
}
async function saveActive() {
  const t = openTabs.find(x => x.path === activeTab);
  if (!t) return;
  const r = await api('/api/fs/file', {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path: t.path, content: t.content }),
  });
  if (r.error) toast(r.error, true);
  else { t.dirty = false; document.getElementById('btn-save').disabled = true; renderTabs(); toast(t('saved')); await refreshTree(); }
}

let editTimer = null;
let editBefore = null;
document.getElementById('editor').addEventListener('input', () => {
  const t = openTabs.find(x => x.path === activeTab);
  if (!t || document.getElementById('editor').disabled) return;
  if (editBefore === null) editBefore = t.content;
  t.content = document.getElementById('editor').value;
  const wasDirty = t.dirty;
  t.dirty = true;
  document.getElementById('btn-save').disabled = false;
  if (!wasDirty) renderTabs();
  updateLineNumbers();
  ensureCaretVisible();
  clearTimeout(editTimer);
  editTimer = setTimeout(() => {
    if (editBefore !== null && editBefore !== t.content) {
      pushUndo({ type: 'edit', path: t.path, before: editBefore, after: t.content, dirtyBefore: false, dirtyAfter: true });
    }
    editBefore = null;
  }, 400);
});

/* keyboard */
function handleAppShortcut(e) {
  const mod = e.ctrlKey || e.metaKey;
  if (!mod) return false;
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key.toLowerCase();
  // code-based for layout independence
  const code = e.code;
  if (code === 'KeyS' || k === 's') {
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    saveActive();
    return true;
  }
  if ((code === 'KeyZ' || k === 'z') && !e.shiftKey) {
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    doUndo();
    return true;
  }
  if (code === 'KeyY' || k === 'y' || ((code === 'KeyZ' || k === 'z') && e.shiftKey)) {
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    doRedo();
    return true;
  }
  if (code === 'KeyW' || k === 'w') {
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    if (activeTab) closeTab(activeTab, false);
    return true;
  }
  return false;
}
document.addEventListener('keydown', handleAppShortcut, true);
window.addEventListener('keydown', handleAppShortcut, true);
document.getElementById('editor').addEventListener('keydown', handleAppShortcut, true);

document.getElementById('btn-save').onclick = saveActive;
document.getElementById('btn-undo').onclick = doUndo;
document.getElementById('btn-redo').onclick = doRedo;

