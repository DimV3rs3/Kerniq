/* chat (compact) */
function chatTitleFromPrompt(text) {
  const words = text.trim().split(/\s+/).filter(Boolean);
  let out = [], chars = 0;
  for (const w of words) {
    if (out.length >= 4) break;
    if (out.length >= 2 && chars + w.length > 28) break;
    out.push(w); chars += w.length + 1;
  }
  return out.join(' ') || 'Chat';
}
const SIDE_ICON = {
  chat: '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M5 4h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9l-4 3.5V6a2 2 0 0 1 2-2z"/></svg>',
  trash: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>',
};
function renderSideChats() {
  const el = document.getElementById('side-list');
  if (!el) return;
  el.innerHTML = '';
  chats.slice().reverse().forEach(c => {
    const locked = !!running && c.id !== activeChatId;     // no chat switching mid-run
    const d = document.createElement('div');
    d.className = 'side-item' + (c.id === activeChatId ? ' active' : '') + (locked ? ' disabled' : '');
    d.innerHTML = '<span class="side-ico">' + SIDE_ICON.chat + '</span><span class="title"></span>' +
      '<button type="button" class="x" aria-label="Delete">' + SIDE_ICON.trash + '</button>';
    const title = d.querySelector('.title');
    title.textContent = chatTitleText(c);
    d.title = chatTitleText(c);
    d.addEventListener('click', () => {
      if (locked || c.id === activeChatId) return;
      activeChatId = c.id;
      applyStoredMode();
      applyChatContextFooter();
      renderChatList(); renderMessages();
    });
    d.querySelector('.x').addEventListener('click', (e) => {
      e.stopPropagation();
      if (running) return;
      chats = chats.filter(x => x.id !== c.id);
      if (activeChatId === c.id) activeChatId = chats.length ? chats[chats.length - 1].id : null;
      saveChats(); applyChatContextFooter(); renderChatList(); renderMessages();
    });
    el.appendChild(d);
  });
}
function renderChatList() {
  const el = document.getElementById('chat-hist');
  if (!el) return;
  // Enforce max chats in memory
  if (chats.length > MAX_CHATS) {
    chats = chats.slice(-MAX_CHATS);
    saveChats();
  }
  renderSideChats();
  refreshChatHeading();
  // Collapse strip when 0 or 1 chat
  if (chats.length <= 1) {
    el.classList.add('hidden-hist');
    el.innerHTML = '';
    return;
  }
  el.classList.remove('hidden-hist');
  const list = running
    ? chats.filter(c => c.id === activeChatId)
    : chats.slice().reverse();
  el.innerHTML = '';
  list.forEach(c => {
    const d = document.createElement('div');
    d.className = 'h' + (c.id === activeChatId ? ' active' : '');
    d.innerHTML = '<span class="title"></span><button class="x" title="×">×</button>';
    d.querySelector('.title').textContent = c.title || 'Chat';
    d.querySelector('.title').onclick = () => {
      activeChatId = c.id;
      applyStoredMode();
      applyChatContextFooter();
      renderChatList(); renderMessages();
    };
    d.querySelector('.x').onclick = (e) => {
      e.stopPropagation();
      chats = chats.filter(x => x.id !== c.id);
      if (activeChatId === c.id) activeChatId = chats.length ? chats[chats.length - 1].id : null;
      saveChats(); applyChatContextFooter(); renderChatList(); renderMessages();
    };
    el.appendChild(d);
  });
}

function currentChat() { return chats.find(c => c.id === activeChatId); }
function applyChatContextFooter() {
  const ch = currentChat();
  _lastPromptTokens = (ch && ch.prompt_tokens != null) ? ch.prompt_tokens : null;
  const lim = (ch && ch.context_limit != null) ? ch.context_limit : _modelContextLimit;
  // reset sticky dataset so we don't show previous chat's numbers
  const el = document.getElementById('footer-ctx');
  if (el) {
    if (_lastPromptTokens != null) el.dataset.lastUsed = String(_lastPromptTokens);
    else delete el.dataset.lastUsed;
    if (lim != null) el.dataset.lastLimit = String(lim);
  }
  setFooterContext(_lastPromptTokens, lim);
}

function newChat(force) {
  const empty = chats.find(c => !c.messages.length);
  if (!force && empty) { activeChatId = empty.id; renderChatList(); renderMessages(); toast('An empty chat already exists'); return; }
  const c = { id: uid(), title: 'New chat', messages: [], created: Date.now() };
  chats.push(c); if (chats.length > MAX_CHATS) chats = chats.slice(-MAX_CHATS); activeChatId = c.id; saveChats(); applyChatContextFooter(); renderChatList(); renderMessages();
}

function isToolCollapsible(name) {
  const t = (componentsCache.tools || []).find(x => x.name === name || x.id === name);
  if (t && t.collapsible != null) return !!t.collapsible;
  return MERGEABLE.has(name);
}
const HAMMER_SVG = '<svg class="ico" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M14.2 2.4l1.6 1.6-2.2 2.2 2.5 2.5 2.2-2.2 1.6 1.6-4.7 4.7-6.3-6.3 4.7-4.1zM3 17.2l3.6-3.6 2.8 2.8-3.6 3.6H3v-2.8z"/></svg>';
function toolIcon(name) {
  const t = (componentsCache.tools || []).find(x => x.name === name || x.id === name);
  if (t && t.ui_icon && t.ui_icon !== '⚙' && t.ui_icon !== 'tool') return t.ui_icon;
  return HAMMER_SVG;
}
function toolStatePhrase(name, count) {
  const tool = (componentsCache.tools || []).find(x => x.name === name || x.id === name);
  let phrase = String((tool && tool.display_phrase) || '').trim();
  if (!phrase) return count + ' ' + translatePlural('call', 'calls', count);
  return count + ' ' + translatePlural(phrase, phrase, count);
}
function toolAggLabel(name, count) {
  return toolStatePhrase(name, count);
}
const MERGEABLE = new Set(['web_search','fetch_url','search_code','read_file','list_directory','file_exists','get_file_info']);

function retainOnlyLatestThought(messages) {
  let last = -1;
  messages.forEach((m, i) => {
    if (m.kind === 'think_collapsed' || m.kind === 'think_live') last = i;
  });
  if (last < 0) return messages;
  return messages.filter((m, i) => {
    if (m.kind === 'think_collapsed' || m.kind === 'think_live') return i === last;
    return true;
  });
}
function aggregateMessages(msgs) {
  const aggOn = !(settings && settings.chat && settings.chat.aggregate_tools === false);
  const fileOnly = !!(settings && settings.chat && settings.chat.file_ops_only);
  const debug = !!(settings && settings.chat && settings.chat.developer_mode);
  const out = [];
  const source = retainOnlyLatestThought(msgs);
  for (const m of source) {
    if (m.kind === 'think_collapsed' && !(m.text || '').trim()) continue;
    if (m.kind === 'tool' && m.status === 'pending') continue;
    if (m.kind === 'file_op' && fileOnly) { out.push(m); continue; }
    if (aggOn && m.kind === 'tool' && isToolCollapsible(m.name)) {
      const prev = out[out.length - 1];
      if (prev && prev.kind === 'tool_agg' && prev.name === m.name) {
        prev.count += 1;
        if (m.status === 'error' || m.success === false) prev.errors += 1;
        continue;
      }
      out.push({
        kind: 'tool_agg', name: m.name, count: 1,
        errors: (m.status === 'error' || m.success === false) ? 1 : 0,
      });
      continue;
    }
    if (fileOnly && m.kind === 'tool') continue;
    if (m.kind === 'tool' && !debug) {
      const summary = (m.success === false || m.status === 'error') ? (m.summary || '') : '';
      out.push({ ...m, summary, args: undefined });
      continue;
    }
    out.push(m);
  }
  return out;
}

let _renderTimer = null;
let _streamChars = 0;
let _streamStarted = 0;
function scheduleRender() {
  if (document.body.classList.contains('settings-mode')) {
    window._renderPaused = true;
    saveChats();
    return;
  }
  if (_renderTimer) return;
  _renderTimer = setTimeout(() => {
    _renderTimer = null;
    renderMessages();
    saveChats();
  }, 80);
}
let stickToBottom = true;
let programmaticScroll = false;
function nearBottom(node) {
  if (!node) return true;
  return (node.scrollHeight - node.scrollTop - node.clientHeight) < 64;
}
function updateScrollBtn() {
  const btn = document.getElementById('btn-scroll-bottom');
  if (!btn) return;
  btn.hidden = !!stickToBottom;
  btn.title = t('scrollDown');
}
// Streaming fires an update per token; rebuilding the whole chat each time is what made it stutter.
// Calls are coalesced so the DOM is rebuilt at most once per frame.
let _renderRaf = 0;
function renderMessages() {
  if (_renderRaf) return;
  _renderRaf = requestAnimationFrame(() => {
    _renderRaf = 0;
    try { renderMessagesNow(); } catch (err) { console.error('renderMessages failed:', err); }
  });
}

/* ---------- message actions: copy raw text, collapsible prompts and reasoning ---------- */
const MSG_ICON = {
  copy: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/></svg>',
  check: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
  chev: '<svg class="think-chev" viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"><path d="M4 2.5 7.5 6 4 9.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};
async function copyPlainText(text) {
  const value = String(text == null ? '' : text);
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) { await navigator.clipboard.writeText(value); return true; }
  } catch (_) { /* fall back below */ }
  const ta = document.createElement('textarea');
  ta.value = value; ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
  document.body.appendChild(ta); ta.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (_) {}
  ta.remove();
  return ok;
}
function makeCopyButton(getText) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'msg-copy';
  b.title = translate('Copy');
  b.setAttribute('aria-label', translate('Copy'));
  b.innerHTML = MSG_ICON.copy;
  b.addEventListener('click', async (ev) => {
    ev.stopPropagation();
    const ok = await copyPlainText(getText());
    b.classList.toggle('done', ok);
    b.innerHTML = ok ? MSG_ICON.check : MSG_ICON.copy;
    b.title = translate(ok ? 'Copied' : 'Copy');
    clearTimeout(b._t);
    b._t = setTimeout(() => { b.classList.remove('done'); b.innerHTML = MSG_ICON.copy; b.title = translate('Copy'); }, 1400);
  });
  return b;
}
const THINK_TAIL_LINES = 6;      // how many reasoning lines stay visible
const USER_HEAD_LINES = 4;       // how many lines of a long prompt stay visible
// bottom row of a finished assistant message: "done" tick + copy (raw markdown source, not rendered HTML)
function appendBotTools(d, m, done) {
  const row = document.createElement('div');
  row.className = 'msg-tools';
  if (done) {
    const ok = document.createElement('span');
    ok.className = 'msg-done';
    ok.innerHTML = MSG_ICON.check;
    row.appendChild(ok);
  }
  row.appendChild(makeCopyButton(() => m.content || ''));
  d.appendChild(row);
}
function buildUserMessage(d, m) {
  d.className = 'msg user';
  const text = m.content || '';
  const bubble = document.createElement('div');
  bubble.className = 'user-bubble';
  const body = document.createElement('div');
  body.className = 'user-body';
  body.textContent = text;
  bubble.appendChild(body);
  if (m._expanded) d.classList.add('expanded');
  const more = document.createElement('button');
  more.type = 'button';
  more.className = 'expand-btn';
  more.textContent = translate(m._expanded ? 'Show less' : 'Show more');
  more.addEventListener('click', (ev) => {
    ev.stopPropagation();
    m._expanded = !m._expanded;
    d.classList.toggle('expanded', !!m._expanded);
    more.textContent = translate(m._expanded ? 'Show less' : 'Show more');
    updateScrollBtn();
  });
  bubble.appendChild(more);
  d.appendChild(bubble);
  const row = document.createElement('div');
  row.className = 'msg-tools';
  row.appendChild(makeCopyButton(() => text));
  d.appendChild(row);
  d.dataset.clamp = '1';
}
// with auto-expand on, a finished block folds itself unless the user touched it
function foldFinishedThink(m) {
  if (autoThink && !m._userToggled) { m.open = false; m.full = false; }
}
function buildThinkBlock(d, m) {
  const live = m.kind === 'think_live';
  const text = String(m.text || '');
  d.className = 'msg think' + (live ? ' live' : '') + (m.open ? ' open' : '');
  const head = document.createElement('button');
  head.type = 'button';
  head.className = 'think-head';
  head.setAttribute('aria-expanded', m.open ? 'true' : 'false');
  const lines = text.split('\n').filter(l => l.trim()).length;
  head.innerHTML = MSG_ICON.chev + '<span class="think-title"></span><span class="think-meta"></span>';
  head.querySelector('.think-title').textContent = translate(live ? 'Thinking…' : 'Thought');
  head.querySelector('.think-meta').textContent = lines > 0 ? lines + ' ' + translatePlural('line', 'lines', lines) : '';
  head.addEventListener('click', () => {
    m.open = !m.open;
    m._userToggled = true;
    renderMessages();
  });
  d.appendChild(head);
  if (m.open) {
    const body = document.createElement('div');
    body.className = 'think-body' + (m.full ? ' full' : '') + (live ? ' live-body' : '');
    body.textContent = text.replace(/\n{3,}/g, '\n\n').trim() || '…';
    if (!live) {
      body.title = translate(m.full ? 'Show less' : 'Show all');
      body.addEventListener('click', () => { m.full = !m.full; renderMessages(); });
    }
    const box = document.createElement('div');
    box.className = 'think-box';
    const ell = document.createElement('span');
    ell.className = 'think-ellipsis';
    ell.textContent = '…';
    ell.setAttribute('aria-hidden', 'true');
    box.appendChild(ell);
    box.appendChild(body);
    d.appendChild(box);
    d.dataset.thinkTail = '1';
  }
}
// run after the messages are attached: layout is needed to know what overflows
function settleMessageClamps(root) {
  root.querySelectorAll('.msg.user[data-clamp]').forEach(d => {
    const body = d.querySelector('.user-body');
    const more = d.querySelector('.expand-btn');
    if (!body || !more) return;
    const was = d.classList.contains('expanded');
    d.classList.remove('expanded');
    const clipped = body.scrollHeight > body.clientHeight + 2;
    if (was) d.classList.add('expanded');
    d.classList.toggle('clippable', clipped);
    more.hidden = !clipped;
  });
  root.querySelectorAll('.msg.think[data-think-tail]').forEach(d => {
    const body = d.querySelector('.think-body');
    const box = d.querySelector('.think-box');
    if (!body || !box) return;
    if (body.classList.contains('full')) { box.classList.remove('clipped'); return; }
    box.classList.toggle('clipped', body.scrollHeight > body.clientHeight + 2);
    body.scrollTop = body.scrollHeight;          // newest lines stay at the bottom
  });
}

function renderMessagesNow() {
  if (document.body.classList.contains('settings-mode')) {
    window._renderPaused = true;
    return;
  }
  const el = document.getElementById('msgs');
  if (!el) return;
  const c = currentChat();
  if (!c) { el.innerHTML = ''; refreshChatHeading(); return; }
  const prevTop = el.scrollTop;
  // every rebuild creates new elements; starting their animations at the shared clock's phase keeps
  // the shimmer / pulse running instead of restarting on each update
  const clock = (document.timeline && document.timeline.currentTime != null) ? document.timeline.currentTime : performance.now();
  el.style.setProperty('--shimmer-delay', '-' + ((clock % 1900) / 1000).toFixed(3) + 's');
  el.style.setProperty('--pulse-delay', '-' + ((clock % 1200) / 1000).toFixed(3) + 's');
  el.innerHTML = '';
  const rows = aggregateMessages(c.messages).filter(m => !(m.kind === 'think_collapsed' && !(m.text || '').trim()));
  if (!rows.length) {
    el.innerHTML = '<div class="empty-chat"><strong></strong><span></span></div>';
    el.querySelector('strong').textContent = t('emptyChatTitle');
    el.querySelector('span').textContent = t('emptyChatBody');
    refreshChatHeading();
    return;
  }
  rows.forEach(m => {
    const d = document.createElement('div');
    try {
    if (m.kind === 'think_collapsed' || m.kind === 'think_live') {
      buildThinkBlock(d, m);
    } else if (m.kind === 'assistant_live') {
      d.className = 'msg bot assistant'; d.innerHTML = renderMarkdown(m.content || '');
    } else if (m.role === 'user') {
      buildUserMessage(d, m);
    } else if (m.role === 'assistant' && (m.kind === 'error' || m.error)) {
      d.className = 'msg error-card';
      const debug = !!(settings && settings.chat && settings.chat.developer_mode);
      let html = '<div class="err-title"></div>';
      d.innerHTML = html;
      d.querySelector('.err-title').textContent = m.content || 'Error';
      if (debug && m.detail) {
        const pre = document.createElement('pre');
        pre.className = 'err-detail';
        pre.textContent = m.detail;
        d.appendChild(pre);
      }
      const next = document.createElement('p');
      next.className = 'err-next';
      next.textContent = t('errorNext');
      d.appendChild(next);
    } else if (m.role === 'assistant') {
      d.className = 'msg bot assistant' + (m.completed ? ' completed' : '');
      d.innerHTML = renderMarkdown(m.content || '');
      appendBotTools(d, m, !!m.completed);
    } else if (m.kind === 'tool_agg') {
      const failed = m.errors || 0;
      d.className = 'msg tool ' + (failed ? 'err' : 'ok');
      d.innerHTML = '<span class="tool-ico">' + HAMMER_SVG + '</span><span class="tool-name">' + esc(m.name) + '</span>'
        + '<span class="tool-state">' + esc(toolStatePhrase(m.name, m.count)) + '</span>'
        + (failed ? '<span class="muted">(' + failed + ' ' + esc(translate('failed')) + ')</span>' : '');
    } else if (m.kind === 'tool') {
      const ok = m.success !== false && m.status !== 'error';
      const pending = m.status === 'pending';
      d.className = 'msg tool ' + (pending ? '' : (ok ? 'ok' : 'err'));
      const debug = !!(settings && settings.chat && settings.chat.developer_mode);
      let body = '<span class="tool-ico">' + HAMMER_SVG + '</span><span class="tool-name">' + esc(m.name) + '</span>'
        + '<span class="tool-state">' + (pending ? '…' : (ok ? esc(toolStatePhrase(m.name, 1)) : 'error')) + '</span>';
      if (!pending && m.stop_reason && m.stop_reason !== 'completed') body += '<span class="muted">(' + esc(m.stop_reason) + ')</span>';
      if (debug && m.args && !pending) body += '<span class="tool-detail">' + esc(typeof m.args === 'string' ? m.args : JSON.stringify(m.args)) + '</span>';
      if (!pending && m.summary) body += '<span class="tool-detail">' + esc(m.summary) + '</span>';
      d.innerHTML = body;
    } else if (m.kind === 'file_op') {
      const col = m.op === 'create' ? 'var(--ok)' : m.op === 'delete' ? 'var(--err)' : 'var(--warn)';
      d.className = 'msg system';
      d.innerHTML = `<span style="color:${col}">${m.op === 'create' ? '＋' : m.op === 'delete' ? '✕' : '✎'} ${esc(m.path || '')}${m.added != null ? ` (+${m.added}/-${m.removed || 0})` : ''}</span>`;
    } else if (m.kind === 'divider') {
      d.className = 'msg divider';
      d.textContent = m.content || t('actDivider');
    } else if (m.kind === 'notice') {
      d.className = 'msg notice';
      d.textContent = m.content || '';
    } else { d.className = 'msg system'; d.textContent = m.content || ''; }
    } catch (err) {
      console.error('message render failed:', err, m);
      d.className = 'msg system';
      d.textContent = String(m && (m.content || m.text) || '');
    }
    el.appendChild(d);
  });
  settleMessageClamps(el);
  if (stickToBottom) {
    programmaticScroll = true;
    el.scrollTop = el.scrollHeight;
    setTimeout(() => { programmaticScroll = false; }, 40);
  } else {
    el.scrollTop = prevTop;   // a rebuild must not throw the reader back to the top
  }
  updateScrollBtn();
  renderPlan();
}

const promptEl = document.getElementById('prompt');
let sendKeyMode = 'enter'; // 'enter' | 'shift_enter'
function getSendKeyMode() {
  try {
    if (settings && settings.chat && settings.chat.send_key) return settings.chat.send_key;
  } catch {}
  return sendKeyMode || 'enter';
}
promptEl.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && mentionOpen) {
    e.preventDefault();
    hideCtx();
    return;
  }
  if (e.key === 'Enter' && mentionOpen) {
    const first = document.querySelector('#ctx #attach-hits button');
    if (first) { e.preventDefault(); first.click(); return; }
  }
  if (e.key !== 'Enter') return;
  const mode = getSendKeyMode();
  const sendNow = mode === 'enter' ? !e.shiftKey : e.shiftKey;
  if (sendNow) {
    e.preventDefault();
    if (!actionBtn.disabled && !running) actionBtn.click();
  }
});
const actionBtn = document.getElementById('btn-action');
function hasMeaningfulText(s) { return /[^\s\u200b]/.test(s || ''); }
function autoGrow() {
  promptEl.style.height = 'auto';
  const phone = document.documentElement.dataset.phone === '1';
  const lines = phone ? 5 : 15;
  const max = 1.4 * 13 * lines + 12;
  const h = Math.min(promptEl.scrollHeight, max);
  promptEl.style.height = h + 'px';
  promptEl.style.overflowY = promptEl.scrollHeight > max ? 'auto' : 'hidden';
}
function updateActionBtn() {
  if (typeof applyModeSwitch === 'function') applyModeSwitch();
  const btn = document.getElementById('btn-action');
  if (!btn) return;
  btn.classList.toggle('is-stop', !!running);
  btn.classList.toggle('is-send', !running);
  btn.disabled = false;
  btn.textContent = '';
  if (running) {
    btn.innerHTML = '<span class="stop-ico" aria-hidden="true"></span>';
    btn.title = t('stop');
    btn.setAttribute('aria-label', t('stop'));
  } else {
    btn.innerHTML = '<span class="send-ico" aria-hidden="true">↑</span>';
    btn.title = t('send');
    btn.setAttribute('aria-label', t('send'));
    const pr = document.getElementById('prompt');
    if (pr && !(pr.value || '').trim()) btn.disabled = true;
  }
}
promptEl.addEventListener('input', () => { autoGrow(); updateActionBtn(); trackMention(); });
function _modelMatch(a, b) {
  a = String(a || '').trim();
  b = String(b || '').trim();
  return !!a && a === b;
}

function syncAutoLoad() {
  const on = !!document.getElementById('s-auto-load')?.checked;
  const sel = document.getElementById('s-load-action');
  if (sel) sel.disabled = !on;
}
function savedLoadAction() {
  const api = (settings && settings.api) || {};
  const allowed = { alongside: 1, unload_idle: 1, unload_busy: 1, notify: 1 };
  const action = String(api.model_load_action || 'notify');
  return allowed[action] ? action : 'notify';
}
/** Load the selected model using the plan the server computed. */
async function ensureModelReady(override) {
  const prov = (settings && settings.api && settings.api.provider) || 'lm_studio';
  if (prov !== 'lm_studio') return true;
  const forced = override != null && String(override).trim();
  const selected = forced
    ? String(override).trim()
    : String((settings && settings.api && settings.api.model) || '').trim();
  if (!selected) return true;
  let plan;
  try {
    plan = await api('/api/models/load-plan?model=' + encodeURIComponent(selected));
  } catch (e) {
    toast('Cannot reach LM Studio status: ' + e, true);
    return true;
  }
  if (plan && plan.error && plan.status !== 'foreign') {
    toast('LM Studio: ' + plan.error, true);
    return true;
  }
  if (plan && (plan.status === 'ready' || plan.selected_loaded)) return true;
  const auto = !!(settings && settings.api && settings.api.auto_model_load);
  let choice = '';
  if (plan && plan.status === 'foreign') {
    if (auto) choice = autoLoadChoice(plan, savedLoadAction());
    else choice = await askLoadChoice(plan);
  }
  if (choice === 'cancel' || choice === 'notify') {
    if (choice === 'notify') toast(translate(busyNotice(plan)), true);
    return false;
  }
  if (choice === '' && plan && plan.status === 'foreign') return false;
  setFooterActivity('loading');
  setFooterModelStatus('', null);
  setStatus(t('loading'), true);
  try {
    const l = await api('/api/lms/load', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: selected, choice: choice || 'alongside' }),
    });
    if (l && l.needs_choice && l.plan) {
      const again = auto ? autoLoadChoice(l.plan, savedLoadAction()) : await askLoadChoice(l.plan);
      if (!again || again === 'cancel' || again === 'notify') {
        if (again === 'notify') toast(translate(busyNotice(l.plan)), true);
        settleFooter();
        return false;
      }
      return ensureModelReady(selected);
    }
    modelLoaded = !(l && l.error);
    settleFooter();
    setStatus(t('ready'), false);
    if (l && l.error) { toast('Load failed: ' + l.error, true); return false; }
    await refreshModelFooter().catch(() => {});
    return true;
  } catch (e) {
    modelLoaded = false;
    settleFooter();
    setStatus(t('ready'), false);
    toast('Model load error: ' + e, true);
    return false;
  }
}
function autoLoadChoice(plan, action) {
  if (!plan || plan.status !== 'foreign') return 'alongside';
  if (action === 'notify') return 'notify';
  if (action === 'unload_busy') return 'unload_busy';
  if (action === 'unload_idle') return plan.busy ? 'alongside' : 'unload';
  return 'alongside';
}
function busyNotice(plan) {
  if (plan && plan.busy) return 'A model is working. It was left loaded.';
  return 'Another model is loaded. This one was not loaded.';
}
function askLoadChoice(plan) {
  return new Promise(resolve => {
    const bg = document.getElementById('model-modal');
    const text = document.getElementById('model-modal-text');
    const box = document.getElementById('model-modal-actions');
    if (!bg || !box) { resolve('cancel'); return; }
    if (text) text.textContent = translate(plan.prompt || '');
    box.innerHTML = '';
    (plan.choices || []).forEach(choice => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = translate(choice.label || choice.id);
      b.className = choice.id === 'cancel' ? 'cancel-active' : (choice.id === 'unload' ? 'save-active' : '');
      b.onclick = () => { bg.classList.remove('on'); resolve(choice.id); };
      box.appendChild(b);
    });
    if (!(plan.choices || []).length) { resolve(''); return; }
    bg.classList.add('on');
  });
}



actionBtn.onclick = async () => {
  if (running) {
    if (sendLock && !currentRunId) {
      sendAbort = true;
      setStatus(t('stopping') || 'Stopping…', true);
      return;
    }
    setStatus(t('stopping') || 'Stopping…', true);
    updateActionBtn();
    approvalQueue = [];
    const approval = document.getElementById('approval-modal');
    if (approval) approval.style.display = 'none';
    const rid = currentRunId;
    try {
      await api('/api/chat/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: rid || '', chat_id: activeChatId || '' }),
      });
    } catch (e) { /* ignore */ }
    return;
  }
  if (sendLock) return;
  const text = promptEl.value;
  if (!hasMeaningfulText(text)) return;
  sendLock = true;
  sendAbort = false;
  running = true;
  updateActionBtn();
  try {
    const savedModel = String((settings && settings.api && settings.api.model) || '').trim();
    let readyFor = savedModel;
    if (!savedModel) {
      const listed = await fetchModels().catch(() => ({ models: [] }));
      readyFor = pickAutoModel((listed && listed.models) || modelChoices || []);
      autoFooterModel = readyFor;
      if (readyFor) paintModelFooter(readyFor, (listed && listed.models) || modelChoices, true);
    }
    const ok = await ensureModelReady(readyFor);
    if (sendAbort || !ok) {
      autoFooterModel = '';
      if (!ok && !sendAbort) toast(translate('Model not ready — send cancelled'), true);
      running = false;
      updateActionBtn();
      refreshModelFooter().catch(() => {});
      return;
    }
    if (!activeChatId) newChat(true);
    const c = currentChat();
    if (!c) {
      autoFooterModel = '';
      toast('No active chat', true);
      running = false;
      updateActionBtn();
      refreshModelFooter().catch(() => {});
      return;
    }
    let taskToSend = text.trim();
    if (chatAttachments.length) {
      const pictures = chatAttachments.filter(a => isImagePath(a.path));
      const files = chatAttachments.filter(a => !isImagePath(a.path));
      const notes = [];
      if (files.length) notes.push('Attached files (use these paths):\n' + files.map(a => a.path).join('\n'));
      if (pictures.length) notes.push('Attached pictures are included in this message for you to see:\n' + pictures.map(a => a.path).join('\n'));
      if (notes.length) taskToSend = text.trim() + '\n\n' + notes.join('\n\n');
    }
    c.messages.push({ role: 'user', content: text.trim(), attachments: chatAttachments.slice() });
    if (c.title === 'New chat' || c.title === 'Chat') {
      c.title = chatTitleFromPrompt(text);
      api('/api/chat/title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.trim() }),
      }).then(r => {
        if (r && r.title) { c.title = r.title; saveChats(); renderChatList(); refreshChatHeading(); }
      }).catch(() => {});
    }
    chatAttachments = [];
    renderAttachChips();
    promptEl.value = ''; autoGrow(); updateActionBtn();
    saveChats(); renderChatList(); renderMessages();
    setStatus(statusLabel('processing'), true);
    await runAgent(taskToSend);
  } catch (err) {
    console.error('send failed', err);
    autoFooterModel = '';
    toast('Send failed: ' + (err && err.message ? err.message : err), true);
    running = false;
    setRunLock(false);
    setStatus(t('error') || 'Error', false);
    updateActionBtn();
  } finally {
    sendLock = false;
    sendAbort = false;
  }
};
async function runAgent(task) {
  running = true;
  setRunLock(true);
  setFooterActivity('work');
  runSawPlan = false;
  currentRunId = null;
  updateActionBtn();
  streamingEnabled = !(settings && settings.chat && settings.chat.streaming === false);
  resetTps(!streamingEnabled);
  if (streamingEnabled) startTpsTimer();
  setStatus(statusLabel('processing'), true);
  const hist = [];
  const chat = currentChat();
  if (chat) {
    for (const m of chat.messages) {
      if (!m || m.kind === 'status' || m.kind === 'notice' || m.kind === 'divider') continue;
      if (m.kind === 'think_live' || m.kind === 'think_collapsed') continue;
      if (m.kind === 'tool' || m.kind === 'tool_agg' || m.kind === 'file_op') continue;
      if (m.role === 'user' && m.content) hist.push({ role: 'user', content: String(m.content) });
      if (m.role === 'assistant' && m.content) hist.push({ role: 'assistant', content: String(m.content) });
    }
    if (hist.length && hist[hist.length - 1].role === 'user') hist.pop();
  }
  try {
    const r = await api('/api/chat/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task,
        chat_id: activeChatId,
        history: hist,
        mode: (modeAuto ? 'auto' : (typeof agentMode === 'string' ? agentMode : 'act')),
        mode_auto: !!modeAuto,
        compose_plan: planComposeAvailable() && !!document.getElementById('s-compose-plan')?.checked,
        auto_act: document.getElementById('s-auto-act')
          ? document.getElementById('s-auto-act').checked
          : !(settings && settings.chat && settings.chat.auto_act_after_plan === false),
        plan: (chat && chat.plan) || [],
        archive: (chat && chat.planArchive) || [],
        attachments: (chat && chat.messages || []).slice().reverse().find(m => m.role === 'user')?.attachments || chatAttachments,
        client_settings: Object.assign({
          api: liveApiSettings(),
        }, serverModeOn() ? {
          chat: Object.assign({}, (settings && settings.chat) || {}, {
            read_only_external_attachments: document.getElementById('s-external-ro')
              ? document.getElementById('s-external-ro').checked
              : !((settings && settings.chat && settings.chat.read_only_external_attachments) === false),
          }),
          agent: (settings && settings.agent) || {},
          prompt: (settings && settings.prompt) || {},
          interface: (settings && settings.interface) || {},
        } : {}),
      }),
    });
    if (r.error) {
      currentChat().messages.push({ role: 'assistant', content: 'Error: ' + r.error });
      saveChats(); renderMessages(); setStatus('Error', false);
    } else {
      currentRunId = r.run_id;
      await pollRun(r.run_id);
    }
  } catch (e) {
    const msg = (e && e.message) ? e.message : String(e);
    currentChat().messages.push({ role: 'assistant', kind: 'error', error: true, content: 'The request failed.', detail: msg });
    saveChats(); renderMessages(); setStatus('Error', false);
  }
  finalizeLiveMessages();
  generatingTokens = false;
  stopTpsTimer();
  resetTps(!streamingEnabled);
  currentRunId = null;
  running = false;
  autoFooterModel = '';
  runModel = '';
  settlePlan();
  setRunLock(false);
  settleFooter();
  updateActionBtn();
  try { await refreshModelFooter(); } catch (_) {}
}
async function pollRun(runId, startCursor) {
  let done = false;
  let idleTicks = 0;
  let networkFails = 0;
  let cursor = Number(startCursor || 0);
  // Match agent timeout (seconds) — long prompt prefill must not kill the UI
  const timeoutSec = Math.max(
    120,
    Number((settings && settings.agent && settings.agent.timeout_seconds) || 600)
  );
  // idle ticks of 350ms; allow full timeout + 2 min slack with no events
  const maxIdleTicks = Math.ceil((timeoutSec + 120) / 0.35);
  while (!done) {
    await new Promise(r => setTimeout(r, 350));
    let ev;
    try {
      ev = await api('/api/chat/events?run_id=' + encodeURIComponent(runId) + '&cursor=' + cursor);
      networkFails = 0;
    } catch (e) {
      networkFails++;
      if (networkFails > 60) { // ~21s of pure network failure
        setStatus('Error', false);
        const c = currentChat();
        if (c) {
          c.messages.push({ role: 'assistant', content: 'Error: lost connection to Kerniq UI server while waiting for the model.' });
          saveChats(); renderMessages();
        }
        break;
      }
      continue;
    }
    if (ev.error) {
      const msg = ev.error === 'unknown run' ? 'Error: run not found on server' : String(ev.error);
      setStatus(msg, false);
      const c = currentChat();
      if (c && !c.messages.some(m => m.role === 'assistant' && String(m.content||'').startsWith('Error'))) {
        c.messages.push({ role: 'assistant', content: msg });
        saveChats(); renderMessages();
      }
      break;
    }
    const events = ev.events || [];
    if (ev.cursor != null) cursor = Number(ev.cursor);
    else cursor += events.length;
    if (events.length) idleTicks = 0;
    else idleTicks++;
    for (const e of events) handleEvent(e);
    if (ev.done) {
      done = true;
      const lastStatus = (events.filter(x => x.type === 'status').pop() || {}).status;
      const lastText = (events.filter(x => x.type === 'status').pop() || {}).text;
      if (lastStatus === 'cancelled') setStatus('Stopped', false);
      else if (lastStatus === 'error') setStatus(lastText || 'Error', false);
      else setStatus('Done', false);
      generatingTokens = false;
    }
    // Only bail on idle after agent timeout window (not ~2 min)
    if (!done && idleTicks > maxIdleTicks) {
      const msg = 'Error: no events from agent for ' + timeoutSec + 's+ (timeout). Model may still be running in LM Studio.';
      setStatus(msg, false);
      const c = currentChat();
      if (c) {
        c.messages.push({ role: 'assistant', content: msg });
        saveChats(); renderMessages();
      }
      break;
    }
  }
  finalizeLiveMessages();
  saveChats();
  renderMessages();
  try { await refreshTree(); } catch (_) {}
}

const STATUS_KEYS = {
  loading_model: 'processing',
  processing: 'processing',
  thinking: 'thinking',
  generating: 'generating',
  tool: 'processing',
  waiting_tool: 'processing',
  cancelled: 'stopped',
  done: 'done',
  error: 'error',
  empty_done: 'done',
};
function quietThinking() {
  const ch = settings && settings.chat;
  const stream = !ch || ch.streaming !== false;
  const reason = !ch || ch.show_reasoning_live !== false;
  return !stream && !reason;
}
function statusLabel(st, fallback) {
  if (quietThinking() && ['processing', 'thinking', 'loading_model', 'generating', 'tool', 'waiting_tool'].includes(st)) {
    return t('thinking');
  }
  const k = STATUS_KEYS[st];
  if (k) return t(k);
  return fallback || st || '…';
}

function finalizeLiveMessages() {
  const c = currentChat();
  if (!c) return;
  for (const m of c.messages) {
    if (m.kind === 'assistant_live') {
      m.kind = undefined;
      m.role = 'assistant';
      m.content = m.content || '';
    }
    if (m.kind === 'think_live') {
      m.kind = 'think_collapsed';
      foldFinishedThink(m);
    }
  }
  saveChats();
  renderMessages();
}

let approvalQueue = [];
function showApproval(req) {
  if (!req || !req.request_id) return;
  if (approvalQueue.some(item => item.request_id === req.request_id)) return;
  approvalQueue.push(req);
  renderApproval();
}
function renderApproval() {
  const modal = document.getElementById('approval-modal');
  if (!modal) return;
  if (!approvalQueue.length) {
    modal.style.display = 'none';
    return;
  }
  const req = approvalQueue[0];
  const text = document.getElementById('approval-text');
  const args = document.getElementById('approval-args');
  if (text) {
    text.textContent = (req.tool_id || 'tool') + ' · risk ' + (req.risk_level || '')
      + '\n' + (req.consequences || req.description || '');
  }
  if (args) args.textContent = JSON.stringify(req.arguments || {}, null, 2);
  modal.style.display = 'flex';
}
async function decideApproval(decision) {
  const req = approvalQueue.shift();
  renderApproval();
  if (!req) return;
  try {
    await api('/api/approvals/decide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: req.request_id, decision }),
    });
  } catch (err) {
    toast(String(err), true);
  }
}
document.addEventListener('DOMContentLoaded', () => {
  const allow = document.getElementById('approval-allow');
  const deny = document.getElementById('approval-deny');
  if (allow) allow.addEventListener('click', () => decideApproval('allow'));
  if (deny) deny.addEventListener('click', () => decideApproval('deny'));
});

function handleEvent(e) {
  if (e.type === 'approval' && e.request) {
    showApproval(e.request);
    return;
  }
  if (e.type === 'mode' && (e.mode === 'plan' || e.mode === 'act')) {
    if (e.mode === 'plan') runSawPlan = true;
    if (e.mode === 'act' && runSawPlan) {
      const c = currentChat();
      if (c) c.messages.push({ kind: 'divider', content: t('actDivider') });
      runSawPlan = false;
      saveChats();
      renderMessages();
    }
    rememberMode(e.mode);
    return;
  }
  if (e.type === 'model') {
    if (e.model) {
      liveModel = String(e.model);
      runModel = liveModel;
    }
    const limit = Number(e.context_limit || 0);
    if (limit) {
      _modelContextLimit = limit;
      const ch = currentChat();
      if (ch) ch.context_limit = limit;
    }
    _lastPromptTokens = null;
    setFooterContext(null, _modelContextLimit);
    if (runModel) setFooterModelStatus(t('model') + ': ' + runModel, true);
    modelLoaded = !!runModel;
    setFooterActivity(modelLoaded ? 'loaded' : 'err');
    saveChats();
    return;
  }
  if (e.type === 'notice') {
    const c = currentChat();
    if (!c) return;
    const label = e.kind === 'compacted'
      ? t('contextCompacted')
      : e.kind === 'trimmed'
        ? t('contextTrimmed')
        : (e.text || '');
    c.messages.push({ kind: 'notice', content: label });
    saveChats();
    renderMessages();
    return;
  }
  if (e.type === 'plan') {
    const chat = currentChat();
    if (chat) {
      if (e.reset) {
        chat.plan = [];
        chat.planArchive = [];
        chat.planDismissed = false;
        saveChats();
        renderPlan();
        return;
      }
      chat.planDismissed = false;
      chat.plan = Array.isArray(e.items) ? e.items : [];
      if (Array.isArray(e.archive)) chat.planArchive = e.archive;
      saveChats();
    }
    renderPlan();
    return;
  }
  if (e.type === 'cleanup_think') {
    const c = currentChat(); if (!c) return;
    c.messages = c.messages.filter(m => !(m.kind === 'think_collapsed' || m.kind === 'think_live') || (m.text || '').trim());
    // drop trailing empty thinks
    while (c.messages.length) {
      const last = c.messages[c.messages.length - 1];
      if (last.kind === 'think_collapsed' || last.kind === 'think_live') c.messages.pop();
      else break;
    }
    renderMessages();
    return;
  }

  const c = currentChat(); if (!c) return;
  if (e.type === 'heartbeat') {
    // keep poll alive during long prefill / thinking with no tokens yet
    setStatus(quietThinking() ? t('thinking') : (e.text || statusLabel('processing')), true);
    return;
  }
  if (e.type === 'status') {
    const st = e.status || '';
    if (st === 'empty_done') {
      generatingTokens = false;
      setStatus(statusLabel(st, e.text), false);
      toast(translate(e.text || 'Empty reply, retrying…'), true, e.detail || '');
      if (c) {
        c.messages.push({ role: 'system', content: e.text || 'Model finished (empty response)', kind: 'empty_done' });
        renderMessages();
      }
    } else if (st === 'done' || st === 'cancelled' || st === 'error') {
      generatingTokens = false;
      if (st === 'error') {
        setFooterActivity('err');
        toast(explainStatus(e.text || 'Error'), true, e.detail || e.error || '');
      } else {
        settleFooter();
        if (st === 'done') toast(translate('Model finished the reply'));
      }
      settlePlan();
      setStatus(statusLabel(st, e.text || (st === 'error' ? 'Error' : '')), false);
    } else if (st === 'loading_model') {
      setFooterActivity('loading');
      if (e.text) {
        liveModel = String(e.text);
        runModel = liveModel;
        setFooterModelStatus(t('model') + ': ' + liveModel, null);
      }
      generatingTokens = false;
      setStatus(statusLabel(st, e.text), true);
    } else if (st === 'generating' || st === 'thinking' || st === 'processing') {
      setFooterActivity('work');
      generatingTokens = st === 'generating';
      setStatus(statusLabel(st, e.text), true);
    } else if (st === 'tool' || st === 'waiting_tool') {
      generatingTokens = false;
      setFooterActivity('work');
      setStatus(statusLabel(st, e.text), true);
    } else {
      setStatus(e.text || statusLabel(st), true);
    }
  } else if (e.type === 'reasoning_delta') {
    // Reasoning streams tokens too — count for tok/s while thinking
    noteGeneratedText(e.text || '');
    setFooterActivity('work');
    setStatus(statusLabel('thinking'), true);
    c.messages = c.messages.filter(m => m.kind !== 'think_collapsed');
    let live = c.messages.find(m => m.kind === 'think_live');
    if (!live) { live = { kind: 'think_live', text: '', open: autoThink }; c.messages.push(live); }
    live.text = (live.text || '') + (e.text || '');
    scheduleRender();
  } else if (e.type === 'content_delta') {
    setFooterActivity('work');
    setStatus(statusLabel('generating'), true);
    noteGeneratedText(e.text || '');
    // New live block only after the last tool (or at end). Never reuse pre-tool text.
    let liveIdx = -1;
    for (let i = c.messages.length - 1; i >= 0; i--) {
      const m = c.messages[i];
      if (m.kind === 'tool' || m.kind === 'tool_agg' || m.kind === 'file_op') break;
      if (m.kind === 'assistant_live') { liveIdx = i; break; }
    }
    if (liveIdx < 0) {
      c.messages.push({ kind: 'assistant_live', role: 'assistant', content: e.text || '' });
    } else {
      c.messages[liveIdx].content = (c.messages[liveIdx].content || '') + (e.text || '');
    }
    scheduleRender();
  } else if (e.type === 'think_done') {
    const text = (e.text || '').trim();
    const tl = c.messages.find(m => m.kind === 'think_live');
    if (tl) {
      if (text) { tl.kind = 'think_collapsed'; tl.text = text; foldFinishedThink(tl); }
      else c.messages = c.messages.filter(m => m !== tl);
    } else if (text) {
      c.messages.push({ kind: 'think_collapsed', text });
    }
    c.messages = retainOnlyLatestThought(c.messages);
    renderMessages();
  } else if (e.type === 'assistant') {
    let content = (e.content || '').replace(/TASK_COMPLETED/g, '').trim();
    // Finalize only the latest assistant_live AFTER last tool
    let liveIdx = -1;
    for (let i = c.messages.length - 1; i >= 0; i--) {
      const m = c.messages[i];
      if (m.kind === 'tool' || m.kind === 'tool_agg' || m.kind === 'file_op') break;
      if (m.kind === 'assistant_live') { liveIdx = i; break; }
    }
    if (e.error) {
      c.messages.push({
        role: 'assistant',
        kind: 'error',
        error: true,
        content: content || 'Error',
        detail: e.detail || '',
        completed: false,
      });
      toast(translate(content || 'Error'), true, e.detail || '');
      renderMessages();
      return;
    }
    if (liveIdx >= 0) {
      const live = c.messages[liveIdx];
      const streamed = String(live.content || '').replace(/TASK_COMPLETED/g, '').trim();
      const next = content || streamed;
      if (!next) {
        c.messages.splice(liveIdx, 1);
      } else {
        live.kind = undefined;
        live.role = 'assistant';
        live.content = next;
        live.completed = !!e.completed;
      }
    } else if (content) {
      c.messages.push({ role: 'assistant', content, completed: !!e.completed });
    }
    // drop empty trailing think_collapsed
    while (c.messages.length) {
      const last = c.messages[c.messages.length - 1];
      if (last.kind === 'think_collapsed' && !(last.text || '').trim()) c.messages.pop();
      else break;
    }
    renderMessages();
  } else if (e.type === 'tool') {
    // Text before tools becomes "thought" → collapse
    for (let i = c.messages.length - 1; i >= 0; i--) {
      const m = c.messages[i];
      if (m.kind === 'tool' || m.kind === 'tool_agg' || m.kind === 'file_op') break;
      if (m.kind === 'assistant_live') {
        const txt = (m.content || '').trim();
        if (txt) {
          m.kind = 'think_collapsed';
          m.text = txt;
          delete m.role;
          delete m.content;
        } else {
          c.messages.splice(i, 1);
        }
        break;
      }
      if (m.kind === 'think_live') {
        m.kind = 'think_collapsed';
        foldFinishedThink(m);
        break;
      }
    }
    c.messages = retainOnlyLatestThought(c.messages);
    c.messages.push({
      kind: 'tool', name: e.name, status: e.status, success: e.success,
      stop_reason: e.stop_reason, summary: e.summary, args: e.args,
    });
    if (e.status === 'error' || e.success === false) {
      const brief = translate(e.summary || e.name || 'Error');
      const detail = developerOn()
        ? [e.stop_reason, e.args ? JSON.stringify(e.args) : ''].filter(Boolean).join('\n')
        : '';
      toast(brief, true, detail);
    }
    renderMessages();
  } else if (e.type === 'file_op') {
    c.messages.push({ kind: 'file_op', op: e.op, path: e.path, added: e.added, removed: e.removed }); renderMessages();
  } else if (e.type === 'tps') {
    // Provider instantaneous rate → feed as tokens into current second bucket
    if (e.value) {
      generatingTokens = true;
      const sec = Math.floor(Date.now() / 1000);
      if (sec !== currentSec) {
        if (currentSec) tpsBuckets.push({ sec: currentSec, tokens: tokensThisSecond });
        currentSec = sec; tokensThisSecond = 0;
      }
      // value is tok/s — approximate tokens for this tick
      tokensThisSecond += Math.max(1, Number(e.value) * 0.35);
      _tpsTick();
    }
  } else if (e.type === 'usage') {
    if (e.prompt_tokens != null) _lastPromptTokens = Number(e.prompt_tokens);
    if (e.completion_tokens != null) _lastCompletionTokens = Number(e.completion_tokens);
    const ch = currentChat();
    if (ch) {
      if (_lastPromptTokens != null) ch.prompt_tokens = _lastPromptTokens;
      if (_modelContextLimit != null) ch.context_limit = _modelContextLimit;
      if (e.completion_tokens != null) ch.completion_tokens = Number(e.completion_tokens);
      saveChats();
    }
    setFooterContext(_lastPromptTokens, ch && ch.context_limit != null ? ch.context_limit : _modelContextLimit);
  }
}


function normPlanStatus(s) {
  const v = String(s || 'pending').toLowerCase().replace(/ /g, '_');
  if (['done', 'complete', 'completed', 'x', 'finished'].includes(v)) return 'done';
  if (['skipped', 'skip', 'cancelled', 'canceled', 'wont_do'].includes(v)) return 'skipped';
  if (['frozen', 'freeze', 'paused', 'pause', 'hold', 'on_hold'].includes(v)) return 'frozen';
  if (['failed', 'fail', 'failure'].includes(v)) return 'failed';
  if (['active', 'doing', 'in_progress', 'current', 'progress', 'wip'].includes(v)) return 'active';
  return 'pending';
}
function planCollapsed() { return false; }
function coercePlan(items) {
  const list = (items || []).map(raw => ({
    id: raw && raw.id,
    title: (raw && (raw.title || raw.text)) || '',
    status: normPlanStatus(raw && raw.status),
  }));
  let seenActive = false;
  list.forEach(item => {
    if (item.status !== 'active') return;
    if (seenActive) item.status = 'pending';
    else seenActive = true;
  });
  return list;
}
function renderPlan() {
  const box = document.getElementById('plan-float');
  const body = document.getElementById('plan-body');
  const chev = document.getElementById('plan-chevron');
  if (!box || !body) return;
  const chat = typeof currentChat === 'function' ? currentChat() : null;
  if (chat && chat.planDismissed) {
    box.hidden = true;
    box.classList.remove('all-done');
    return;
  }
  const shown = coercePlan((chat && Array.isArray(chat.plan)) ? chat.plan : []);
  const liveIds = new Set(shown.map(item => String(item.id || '')));
  const archived = coercePlan((chat && Array.isArray(chat.planArchive)) ? chat.planArchive : [])
    .filter(item => item.title && item.id && !liveIds.has(String(item.id)))
    .map(item => ({
      id: item.id,
      title: item.title,
      status: item.status === 'skipped' ? 'skipped' : 'done',
    }));
  const open = shown.filter(item => item.status !== 'done' && item.status !== 'skipped');
  const finished = shown.length > 0 && open.length === 0;
  if (!shown.length && !archived.length) {
    box.hidden = true;
    box.classList.remove('all-done');
    return;
  }
  box.hidden = false;
  box.classList.toggle('all-done', finished || !shown.length);
  const title = document.getElementById('plan-title');
  if (title) {
    title.textContent = !shown.length ? t('planArchive') : (finished ? t('planCompleted') : t('planTitle'));
  }
  const collapsed = planCollapsed();
  box.classList.toggle('collapsed', collapsed);
  if (chev) chev.textContent = '';
  body.innerHTML = '';
  shown.forEach(raw => {
    const row = document.createElement('div');
    row.className = 'plan-item ' + raw.status;
    row.innerHTML = '<span class="plan-dot"></span><span class="plan-title"></span>';
    row.querySelector('.plan-title').textContent = raw.title;
    body.appendChild(row);
  });
  if (archived.length && shown.length) {
    const label = document.createElement('div');
    label.className = 'plan-archive-label';
    label.textContent = t('planArchive');
    body.appendChild(label);
  }
  archived.forEach(raw => {
    const row = document.createElement('div');
    row.className = 'plan-item ' + raw.status + ' archived';
    row.innerHTML = '<span class="plan-dot"></span><span class="plan-title"></span>';
    row.querySelector('.plan-title').textContent = raw.title;
    body.appendChild(row);
  });
}
function planVerdict(items) {
  const rows = coercePlan(items || []);
  if (!rows.length) return '';
  const open = rows.filter(item => item.status === 'pending' || item.status === 'active' || item.status === 'frozen');
  const failed = rows.filter(item => item.status === 'failed');
  const done = rows.filter(item => item.status === 'done' || item.status === 'skipped');
  if (!open.length && !failed.length) return t('planCompleted');
  if (done.length) return t('planPartial');
  return t('planFailed');
}
function settlePlan() {
  const chat = typeof currentChat === 'function' ? currentChat() : null;
  const box = document.getElementById('plan-float');
  if (!chat || chat.planDismissed) {
    if (box) box.hidden = true;
    return;
  }
  const verdict = planVerdict(chat.plan);
  if (!verdict) return;
  chat.planDismissed = true;
  chat.messages.push({ kind: 'notice', content: verdict });
  saveChats();
  renderMessages();
  if (box) {
    box.hidden = true;
    box.classList.remove('all-done');
  }
}
function rememberMode(mode) {
  if (mode !== 'plan' && mode !== 'act') return;
  agentMode = mode;
  const c = currentChat();
  if (c && c.mode !== mode) {
    c.mode = mode;
    saveChats();
  }
  applyModeSwitch();
}
function applyStoredMode() {
  const c = currentChat();
  if (c && (c.mode === 'plan' || c.mode === 'act')) agentMode = c.mode;
  applyModeSwitch();
}
function applyModeSwitch() {
  const plan = document.getElementById('mode-plan');
  const act = document.getElementById('mode-act');
  const busy = !!running;
  const locked = !!modeAuto || busy;
  if (plan) {
    plan.classList.toggle('on', agentMode === 'plan');
    plan.disabled = locked;
    plan.tabIndex = locked ? -1 : 0;
  }
  if (act) {
    act.classList.toggle('on', agentMode === 'act');
    act.disabled = locked;
    act.tabIndex = locked ? -1 : 0;
  }
  const box = document.getElementById('mode-switch');
  if (box) {
    box.classList.toggle('locked', locked);
    box.classList.toggle('busy', busy);
    box.title = busy ? translate('Mode cannot be changed while the agent is working') : '';
  }
}
document.getElementById('mode-switch')?.addEventListener('click', (ev) => {
  if (modeAuto || running) return;
  const btn = ev.target.closest('button');
  if (!btn || !btn.dataset.mode || btn.disabled) return;
  agentMode = btn.dataset.mode === 'plan' ? 'plan' : 'act';
  rememberMode(agentMode);
});
document.getElementById('plan-toggle')?.addEventListener('click', () => {
  renderPlan();
});
applyModeSwitch();

const providerDrafts = {};
function rememberProviderDraft(id, draft) {
  if (!id || !draft) return;
  providerDrafts[id] = {
    base_url: draft.base_url || '',
    api_token: draft.api_token || '',
    model: draft.model || '',
    binary_path: draft.binary_path || '',
  };
  try { localStorage.setItem('kerniq.provider.drafts', JSON.stringify(providerDrafts)); } catch (_) {}
}
function loadProviderDrafts() {
  try {
    const raw = JSON.parse(localStorage.getItem('kerniq.provider.drafts') || '{}');
    if (raw && typeof raw === 'object') Object.assign(providerDrafts, raw);
  } catch (_) {}
}
function collectProviderDraft() {
  const apiS = (settings && settings.api) || {};
  return {
    base_url: document.getElementById('s-base-url')?.value ?? apiS.base_url ?? '',
    api_token: document.getElementById('s-api-token')?.value ?? apiS.api_token ?? '',
    model: document.getElementById('s-model')?.value ?? apiS.model ?? '',
    binary_path: document.getElementById('s-binary-path')?.value ?? apiS.binary_path ?? '',
  };
}
function fieldText(f, key) {
  if (key === 'help') return translate(f.help || '');
  return translate(f[key] || '');
}
function renderProviderFields(draft) {
  const sel = document.getElementById('s-provider');
  const box = document.getElementById('provider-fields');
  const blurb = document.getElementById('provider-blurb');
  if (!sel || !box) return;
  const spec = providerCatalog.find(p => p.id === sel.value) || null;
  if (blurb) {
    blurb.textContent = spec ? translate(spec.blurb || '') : '';
  }
  const values = draft || collectProviderDraft();
  box.innerHTML = '';
  (spec?.fields || []).forEach(f => {
    const wrap = document.createElement('div');
    wrap.className = 'field';
    const label = document.createElement('label');
    label.className = 'lbl';
    label.textContent = fieldText(f, 'label');
    wrap.appendChild(label);
    let input;
    if (f.type === 'model' || f.key === 'model') {
      const row = document.createElement('div');
      row.className = 'row';
      const combo = document.createElement('div');
      combo.className = 'model-combo';
      input = document.createElement('input');
      input.id = 's-model';
      input.placeholder = f.placeholder || '(auto)';
      input.autocomplete = 'off';
      input.value = values.model || '';
      const arrow = document.createElement('button');
      arrow.type = 'button';
      arrow.className = 'combo-arrow';
      arrow.id = 'model-arrow';
      arrow.textContent = '▾';
      const menu = document.createElement('div');
      menu.className = 'combo-menu';
      menu.id = 'model-menu';
      menu.hidden = true;
      combo.appendChild(input);
      combo.appendChild(arrow);
      combo.appendChild(menu);
      const refresh = document.createElement('button');
      refresh.type = 'button';
      refresh.className = 'ghost';
      refresh.id = 'btn-refresh-models';
      refresh.textContent = t('refresh');
      refresh.onclick = () => refreshModelsSelect(input.value);
      row.appendChild(combo);
      row.appendChild(refresh);
      wrap.appendChild(row);
      arrow.onclick = (ev) => {
        ev.preventDefault();
        menu.hidden = !menu.hidden;
        if (!menu.hidden) fillModelMenu('');
      };
      input.addEventListener('focus', () => { menu.hidden = false; fillModelMenu(input.value); });
      input.addEventListener('input', () => { menu.hidden = false; fillModelMenu(input.value); });
      document.addEventListener('click', (ev) => {
        if (!combo.contains(ev.target)) menu.hidden = true;
      });
    } else {
      input = document.createElement('input');
      if (f.key === 'api_token') input.id = 's-api-token';
      else if (f.key === 'base_url') input.id = 's-base-url';
      else if (f.key === 'binary_path') input.id = 's-binary-path';
      else input.id = 's-field-' + f.key;
      input.type = f.type === 'secret' ? 'password' : 'text';
      input.placeholder = f.placeholder || '';
      const stored = values[f.key] || '';
      input.value = stored || (f.key === 'api_token' ? '' : (f.default || ''));
      wrap.appendChild(input);
    }
    const help = fieldText(f, 'help');
    if (help) {
      const hint = document.createElement('div');
      hint.className = 'hint';
      hint.textContent = help;
      wrap.appendChild(hint);
    }
    if (input) {
      input.addEventListener('input', () => { if (typeof markSettingsDirty === 'function') markSettingsDirty(); });
    }
    box.appendChild(wrap);
  });
}
async function loadProviderCatalog(selectedId) {
  loadProviderDrafts();
  const data = await api('/api/providers').catch(() => ({ providers: [] }));
  providerCatalog = data.providers || [];
  const sel = document.getElementById('s-provider');
  if (!sel) return;
  const current = selectedId || sel.value || 'lm_studio';
  sel.innerHTML = '';
  if (!providerCatalog.length) {
    const why = (data && data.error) ? String(data.error).slice(0, 180) : t('providersEmpty');
    const note = document.getElementById('provider-blurb');
    if (note) note.textContent = why;
    toast(why, true);
  }
  providerCatalog.forEach(p => {
    const o = document.createElement('option');
    o.value = p.id;
    o.textContent = p.label || p.id;
    sel.appendChild(o);
  });
  if ([...sel.options].some(o => o.value === current)) sel.value = current;
  else if (sel.options.length) sel.selectedIndex = 0;
  let providerShown = sel.value;
  sel.onchange = async () => {
    const nextId = sel.value;
    const leaving = providerShown;
    const draft = collectProviderDraft();
    rememberProviderDraft(leaving, draft);
    const spec = providerCatalog.find(p => p.id === nextId);
    const remembered = providerDrafts[nextId];
    if (remembered) {
      draft.base_url = remembered.base_url;
      draft.api_token = remembered.api_token;
      draft.model = remembered.model || '';
      draft.binary_path = remembered.binary_path || draft.binary_path;
    } else if (spec) {
      const prev = providerCatalog.find(p => p.id === leaving);
      const prevField = ((prev && prev.fields) || []).find(f => f.key === 'base_url');
      const prevDefault = (prevField && prevField.default) || '';
      const nextField = (spec.fields || []).find(f => f.key === 'base_url');
      if (!draft.base_url || draft.base_url === prevDefault) {
        draft.base_url = (nextField && nextField.default) || '';
      }
      if ((spec.fields || []).some(f => f.key === 'api_token')) draft.api_token = '';
    }
    providerShown = nextId;
    renderProviderFields(draft);
    markSettingsDirty();
    modelsCache = null;
    modelsCacheKey = '';
    await refreshModelsSelect(draft.model || '');
  };
  renderProviderFields();
  providerShown = sel.value;
  rememberProviderDraft(sel.value, collectProviderDraft());
}

let autoFooterModel = '';
function isChatModelRow(m) {
  if (!m) return false;
  const kind = String(m.type || '').toLowerCase();
  if (kind === 'embedding' || kind === 'embeddings' || kind === 'reranker') return false;
  const name = String(m.id || m.name || '').toLowerCase();
  return !!name && name.indexOf('embed') < 0 && name.indexOf('rerank') < 0;
}
function pickAutoModel(rows) {
  const chat = (rows || []).filter(isChatModelRow);
  const loaded = chat.filter(m => (m.loaded_instances || []).length || m.loaded_context_length);
  const row = loaded[0] || chat[0];
  return row ? String(row.id || row.name || '') : '';
}
function activeVision() {
  const rows = modelChoices || [];
  const picked = String(footerModelId() || '').trim();
  const id = picked || pickAutoModel(rows);
  const row = id ? modelRow(id, rows) : null;
  return !!(row && row.vision === true);
}
function modelRow(id, rows) {
  return (rows || modelChoices || []).find(m => _modelMatch(m.id || m.name || '', id)) || null;
}
function contextOfRow(row) {
  if (!row) return null;
  const n = Number(row.loaded_context_length || row.context_length || row.max_context_length || row.context || 0);
  return n > 0 ? n : null;
}
function footerModelId() {
  if (autoFooterModel) return autoFooterModel;
  const input = document.getElementById('s-model');
  if (input && settingsOpen()) return String(input.value || '').trim();
  return String((settings && settings.api && settings.api.model) || '').trim();
}
function paintModelFooter(id, rows, reachable) {
  const label = (id || '').trim() || translate('auto');
  const row = id ? modelRow(id, rows) : null;
  _modelContextLimit = contextOfRow(row);
  const loaded = !!(row && ((row.loaded_instances || []).length || row.loaded_context_length));
  const others = (rows || []).filter(m => isChatModelRow(m) && ((m.loaded_instances || []).length || m.loaded_context_length) && !_modelMatch(m.id || m.name, id));
  if (reachable === false) setFooterModelStatus(t('model') + ': ' + label, false);
  else if (id && others.length && !loaded) setFooterModelStatus(t('model') + ': ' + label, 'foreign');
  else setFooterModelStatus(t('model') + ': ' + label, id ? (loaded ? true : null) : null);
  setFooterContext(_lastPromptTokens, _modelContextLimit);
  if (typeof clampMaxTokensField === 'function') clampMaxTokensField();
}

async function refreshModelFooter() {
  try {
    const s = settings || {};
    const prov = (s.api && s.api.provider) || 'lm_studio';
    const selected = (s.api && s.api.model) || '';
    streamingEnabled = !(s.chat && s.chat.streaming === false);
    resetTps(!streamingEnabled);
    const modelsData = await fetchModels().catch(() => ({}));
    const reachable = !(modelsData && modelsData.error) && modelsData.reachable !== false;
    providerReachable = prov === 'mock' ? true : reachable;
    const rows = modelsData.models || [];
    const selectedRow = rows.find(m => _modelMatch(m.id || m.name || '', selected));
    const reportsLoad = rows.some(m => m && (Array.isArray(m.loaded_instances) || m.loaded_context_length));
    const loadedRows = rows.filter(m => m && ((m.loaded_instances || []).length || m.loaded_context_length));
    const loadedIds = loadedRows.map(m => String(m.id || m.name || '')).filter(Boolean);
    const selectedLoaded = !!(selected && loadedIds.some(id => _modelMatch(id, selected)));
    const foreign = loadedIds.filter(id => !_modelMatch(id, selected));
    if (prov === 'mock') modelLoaded = true;
    else if (!reachable) modelLoaded = false;
    else if (reportsLoad) modelLoaded = selectedLoaded;
    else modelLoaded = !!(selected || rows.length);
    setFooterProvider(prov, providerReachable);
    const labelId = (running && runModel) ? runModel : footerModelId();
    if (!(running && runModel) && labelId) liveModel = labelId;
    paintModelFooter(labelId, rows, reachable && prov !== 'mock' ? true : (prov === 'mock' ? true : false));
    if (prov === 'mock') setFooterModelStatus(t('model') + ': ' + (labelId || 'mock'), true);
  } catch (e) {
    if (!running) setFooterModelStatus(t('model') + ': ' + t('offline'), false);
  }
}

