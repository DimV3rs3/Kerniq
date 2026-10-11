const LS_CHATS = 'ap_chats_v1';
const LS_PANEL = 'ap_panel_w_v1';

let settings = null;
let openTabs = [];
let activeTab = null;
let chats = [];
let activeChatId = null;
let running = false;
let treeData = [];
let expanded = new Set(['']);
let settingsDirty = false;
let settingsBaseline = "";
function snapshotSettingsForm() {
  const ids = ['s-workspace','s-timeout','s-timeout-unit','s-undo-size','s-provider','s-base-url','s-api-token','s-api-temp','s-system','s-max-iter','s-api-max-tokens','s-model','s-include-tools','s-chat-streaming','s-chat-reasoning','s-chat-empty','s-chat-debug'];
  const o = {};
  ids.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    o[id] = el.type === 'checkbox' ? el.checked : el.value;
  });
  // component drafts
  o._tools = JSON.stringify(draftTools || {});
  o._plugins = JSON.stringify(draftPlugins || {});
  return JSON.stringify(o);
}
function recomputeSettingsDirty() {
  const cur = snapshotSettingsForm();
  settingsDirty = cur !== settingsBaseline;
  updateSettingsButtons();
}

let settingsSnapshot = null;
let undoStack = [];
let redoStack = [];
let undoLimit = 100;
let explorerCollapsed = false;
let chatCollapsed = false;
let componentsCache = { tools: [], plugins: [] };
let selectedToolId = null;
let selectedPluginId = null;
let draftTools = {};
let draftPlugins = {};
let footerEnabled = true;

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const t = await r.text();
  try { return JSON.parse(t); } catch { return { error: t }; }
}
function uid() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }
function encodePath(p) {
  return String(p).split('/').map(encodeURIComponent).join('/');
}
function inlineMd(s) {
  s = esc(String(s || ''));
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^\*])\*([^*]+)\*(?!\*)/g, '$1<em>$2</em>');
  s = s.replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/&lt;(https?:[^&\s]+)&gt;/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  return s;
}
function mdTable(rows) {
  if (!rows.length) return '';
  const parse = (r) => r.replace(/^\||\|$/g, '').split('|').map(c => c.trim());
  let html = '<table class="md-table"><tbody>';
  let isHeader = true;
  for (const r of rows) {
    if (/^\s*\|?[\s|:.-]+\|?\s*$/.test(r)) { isHeader = false; continue; }
    const cells = parse(r);
    if (!cells.some(c => c)) continue;
    const tag = isHeader ? 'th' : 'td';
    html += '<tr>' + cells.map(c => '<' + tag + '>' + inlineMd(c) + '</' + tag + '>').join('') + '</tr>';
    isHeader = false;
  }
  return html + '</tbody></table>';
}
function renderMarkdown(text) {
  let raw = String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  raw = raw.replace(/[\u2010-\u2015\u2212]/g, '-').replace(/\u00a0/g, ' ');
  const lines = raw.split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    // fenced code
    const fence = line.match(/^```([\w-]*)\s*$/);
    if (fence) {
      const buf = [];
      i++;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) { buf.push(lines[i]); i++; }
      i++; // closing fence
      const body = buf.join('\n');
      if (buf.some(l => /^\s*\|.+\|/.test(l))) out.push(mdTable(buf));
      else out.push('<pre class="md-code"><code>' + esc(body) + '</code></pre>');
      continue;
    }
    // table block
    if (/^\s*\|.+\|/.test(line)) {
      const buf = [];
      while (i < lines.length && (/^\s*\|/.test(lines[i]) || /^\s*\|?[\s|:.-]+\|?\s*$/.test(lines[i]))) {
        buf.push(lines[i]); i++;
      }
      out.push(mdTable(buf));
      continue;
    }
    // hr
    if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) { out.push('<hr/>'); i++; continue; }
    // headings
    let hm = line.match(/^(#{1,4})\s+(.+)$/);
    if (hm) {
      const lvl = Math.min(hm[1].length + 2, 5); // h3-h5 visual
      out.push('<h' + lvl + '>' + inlineMd(hm[2]) + '</h' + lvl + '>');
      i++; continue;
    }
    // ul
    if (/^\s*[-*•]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*[-*•]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*[-*•]\s+/, ''));
        i++;
      }
      out.push('<ul>' + items.map(t => '<li>' + inlineMd(t) + '</li>').join('') + '</ul>');
      continue;
    }
    // ol
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*\d+\.\s+/, ''));
        i++;
      }
      out.push('<ol>' + items.map(t => '<li>' + inlineMd(t) + '</li>').join('') + '</ol>');
      continue;
    }
    // blank
    if (!line.trim()) { i++; continue; }
    // paragraph: merge consecutive plain lines
    const para = [];
    while (i < lines.length) {
      const L = lines[i];
      if (!L.trim()) break;
      if (/^```/.test(L) || /^\s*\|/.test(L) || /^\s*#{1,4}\s/.test(L) ||
          /^\s*[-*•]\s+/.test(L) || /^\s*\d+\.\s+/.test(L) ||
          /^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(L)) break;
      para.push(L);
      i++;
    }
    out.push('<p>' + para.map(inlineMd).join('<br/>') + '</p>');
  }
  return out.join('\n') || '';
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}
function toast(msg, err) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show' + (err ? ' err' : '');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.className = 'toast'; }, 2200);
}
function loadChats() {
  try { chats = JSON.parse(localStorage.getItem(LS_CHATS) || '[]'); } catch { chats = []; }
}
function saveChats() { localStorage.setItem(LS_CHATS, JSON.stringify(chats)); }

function setStatus(t, busy) {
  document.getElementById('agent-status').textContent = t;
  const sp = document.getElementById('agent-spin');
  if (sp) {
    if (busy === undefined) busy = !/^(Готов|готово|ошибка|остановка)/i.test(t || '');
    sp.classList.toggle('on', !!busy);
  }
  setFooterState(busy ? 'work' : (t && /ошибка/i.test(t) ? 'err' : 'idle'));
}

function setFooterState(mode) {
  const dot = document.getElementById('footer-dot');
  if (!dot) return;
  dot.className = 'dot ' + (mode || 'idle');
}
function setFooterProvider(name, ok) {
  document.getElementById('footer-provider').textContent = 'provider: ' + (name || '—');
  if (ok === false) setFooterState('err');
  else if (!running) setFooterState('idle');
}
let tpsWindow = [];
function setFooterTps(n) {
  const el = document.getElementById('footer-tps');
  if (!el) return;
  if (n == null || n === 0) {
    if (!running) el.textContent = '0.0 tok/s';
    return;
  }
  const now = Date.now();
  tpsWindow.push({ t: now, v: Number(n) });
  tpsWindow = tpsWindow.filter(x => now - x.t < 5000);
  const avg = tpsWindow.reduce((a, b) => a + b.v, 0) / tpsWindow.length;
  el.textContent = avg.toFixed(1) + ' tok/s';
}

function showView(n) {
  document.getElementById('view-main').style.display = n === 'main' ? 'flex' : 'none';
  document.getElementById('view-settings').style.display = n === 'settings' ? 'block' : 'none';
  document.querySelector('.settings-actions').style.display = n === 'settings' ? 'flex' : 'none';
  document.body.classList.toggle('settings-mode', n === 'settings');
  const btn = document.getElementById('nav-settings');
  if (btn && n === 'main') {
    btn.classList.remove('active-settings');
    btn.textContent = '⚙';
    btn.title = 'Settings';
  }
  if (n === 'main') startTreePoll(); else stopTreePoll();
}

/* panels */
function setPanelContentWidth(panel, w) {
  if (panel) panel.style.setProperty('--panel-w', w + 'px');
}
function loadPanelWidths() {
  try {
    const p = JSON.parse(localStorage.getItem(LS_PANEL) || '{}');
    const ex = document.getElementById('explorer');
    const ch = document.getElementById('chat-panel');
    if (p.left) {
      ex.style.width = p.left + 'px';
      ex.style.minWidth = p.left + 'px';
      setPanelContentWidth(ex, p.left);
    } else setPanelContentWidth(ex, 280);
    if (p.right) {
      ch.style.width = p.right + 'px';
      ch.style.minWidth = p.right + 'px';
      setPanelContentWidth(ch, p.right);
    } else setPanelContentWidth(ch, 360);
    if (p.explorerCollapsed) setExplorerCollapsed(true, true);
    if (p.chatCollapsed) setChatCollapsed(true, true);
  } catch {}
}
function savePanelWidths() {
  const left = document.getElementById('explorer').offsetWidth;
  const right = document.getElementById('chat-panel').offsetWidth;
  localStorage.setItem(LS_PANEL, JSON.stringify({
    left: explorerCollapsed ? (JSON.parse(localStorage.getItem(LS_PANEL) || '{}').left || 280) : left,
    right: chatCollapsed ? (JSON.parse(localStorage.getItem(LS_PANEL) || '{}').right || 360) : right,
    explorerCollapsed, chatCollapsed,
  }));
}
function setExplorerCollapsed(v, skipSave) {
  explorerCollapsed = v;
  document.getElementById('explorer').classList.toggle('collapsed', v);
  document.getElementById('btn-toggle-explorer').classList.toggle('on', !v);
  if (!skipSave) savePanelWidths();
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
  let dragging = false;
  let startX = 0;
  let startW = 0;
  let panel = null;

  const onMove = (ev) => {
    if (!dragging || !panel) return;
    ev.preventDefault();
    const max = Math.floor(window.innerWidth * 0.5);
    let w = side === 'left' ? startW + (ev.clientX - startX) : startW - (ev.clientX - startX);
    if (w < 40) {
      if (side === 'left') setExplorerCollapsed(true);
      else setChatCollapsed(true);
      return;
    }
    if (side === 'left' && explorerCollapsed) setExplorerCollapsed(false, true);
    if (side === 'right' && chatCollapsed) setChatCollapsed(false, true);
    const min = window.innerWidth > 900 ? 350 : 200;
    w = Math.max(min, Math.min(max, w));
    panel.style.width = w + 'px';
    panel.style.minWidth = w + 'px';
    setPanelContentWidth(panel, w);
  };

  const endDrag = () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove('resizing-panels');
    el.classList.remove('active');
    window.removeEventListener('mousemove', onMove, true);
    window.removeEventListener('mouseup', endDrag, true);
    window.removeEventListener('blur', endDrag);
    document.removeEventListener('mouseleave', endDrag);
    savePanelWidths();
  };

  el.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    panel = side === 'left' ? document.getElementById('explorer') : document.getElementById('chat-panel');
    if (side === 'left' && explorerCollapsed) setExplorerCollapsed(false, true);
    if (side === 'right' && chatCollapsed) setChatCollapsed(false, true);
    dragging = true;
    document.body.classList.add('resizing-panels');
    el.classList.add('active');
    startX = e.clientX;
    startW = panel.getBoundingClientRect().width || (side === 'left' ? 280 : 360);
    window.addEventListener('mousemove', onMove, true);
    window.addEventListener('mouseup', endDrag, true);
    window.addEventListener('blur', endDrag);
  });
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

/* line numbers */
function updateLineNumbers() {
  const ed = document.getElementById('editor');
  const ln = document.getElementById('line-nums');
  if (!ln) return;
  if (ed.disabled || !activeTab) {
    ln.textContent = '';
    return;
  }
  const text = ed.value || '';
  // count lines: trailing newline still counts as next empty line for caret UX
  const n = text.length === 0 ? 1 : text.split('\n').length;
  const parts = [];
  for (let i = 1; i <= n; i++) parts.push(String(i));
  ln.textContent = parts.join('\n');
  ln.scrollTop = ed.scrollTop;
}
document.getElementById('editor').addEventListener('scroll', () => {
  document.getElementById('line-nums').scrollTop = document.getElementById('editor').scrollTop;
});

/* tree */
function buildTree(entries) {
  const root = { name: '', path: '', type: 'dir', children: {} };
  for (const e of entries) {
    const parts = e.path.replace(/\\/g, '/').split('/').filter(Boolean);
    let node = root;
    parts.forEach((part, i) => {
      const isLast = i === parts.length - 1;
      if (!node.children[part]) {
        node.children[part] = { name: part, path: parts.slice(0, i + 1).join('/'), type: isLast ? e.type : 'dir', children: {} };
      } else if (!isLast) node.children[part].type = 'dir';
      node = node.children[part];
    });
  }
  return root;
}
async function refreshTree(silent) {
  const data = await api('/api/fs/tree');
  if (data.error) { if (!silent) document.getElementById('tree').textContent = data.error; return; }
  const key = JSON.stringify(data.entries || []);
  if (silent && key === refreshTree._last) return;
  refreshTree._last = key;
  treeData = data.entries || [];
  if (data.workspace) document.getElementById('top-workspace').textContent = data.workspace;
  renderTree();
}
function renderTree() {
  const root = buildTree(treeData);
  const el = document.getElementById('tree');
  el.innerHTML = '';
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
        row.innerHTML = `<span class="twist">${open ? '▼' : '▶'}</span><span>📁</span><span>${esc(ch.name)}</span>`;
        row.onclick = () => { if (expanded.has(ch.path)) expanded.delete(ch.path); else expanded.add(ch.path); renderTree(); };
        row.oncontextmenu = ev => { ev.preventDefault(); showCtx(ev, ch.path, true); };
        el.appendChild(row);
        if (open) walk(ch, depth + 1);
      } else {
        row.innerHTML = `<span class="twist"></span><span>📄</span><span>${esc(ch.name)}</span>`;
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

function showCtx(ev, path, isDir) {
  const ctx = document.getElementById('ctx');
  ctx.style.display = 'block';
  ctx.style.left = ev.clientX + 'px';
  ctx.style.top = ev.clientY + 'px';
  let html = '';
  if (!isDir) html += `<button data-a="open">Открыть</button>`;
  html += `<button data-a="reveal">Показать в проводнике</button>`;
  html += `<button data-a="rename">Переименовать</button>`;
  html += `<button data-a="delete" style="color:var(--err)">Удалить</button>`;
  ctx.innerHTML = html;
  ctx.querySelectorAll('button').forEach(b => {
    b.onclick = async () => {
      hideCtx();
      const a = b.dataset.a;
      if (a === 'open') openFile(path);
      else if (a === 'reveal') {
        const r = await api('/api/fs/reveal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) });
        if (r.error) toast(r.error, true); else toast('Открыто');
      } else if (a === 'rename') {
        const base = path.split('/').pop();
        const nn = prompt('Новое имя', base);
        if (!nn || nn === base) return;
        const r = await api('/api/fs/rename', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, new_name: nn }) });
        if (r.error) toast(r.error, true);
        else { toast('Переименовано'); await refreshTree(); }
      } else if (a === 'delete') {
        if (!confirm('Удалить ' + path + '?')) return;
        const r = await api('/api/fs/file?path=' + encodePath(path), { method: 'DELETE' });
        if (r.error) toast(r.error, true);
        else { toast('Удалено'); openTabs = openTabs.filter(t => t.path !== path); if (activeTab === path) clearEditor(); await refreshTree(); renderTabs(); }
      }
    };
  });
}
function hideCtx() { document.getElementById('ctx').style.display = 'none'; }
document.addEventListener('click', hideCtx);

/* editor */
function clearEditor() {
  activeTab = null;
  document.getElementById('editor').value = '';
  document.getElementById('editor').disabled = true;
  document.getElementById('open-path').textContent = '';
  document.getElementById('btn-save').disabled = true;
  document.getElementById('btn-close-tab').disabled = true;
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
  document.getElementById('btn-close-tab').disabled = false;
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
    d.innerHTML = `<span>${t.dirty ? '• ' : ''}${esc(name)}</span><span class="x">×</span>`;
    d.querySelector('span').onclick = () => openFile(t.path);
    d.querySelector('.x').onclick = ev => { ev.stopPropagation(); closeTab(t.path, false); };
    el.appendChild(d);
  });
}
function closeTab(path, force, skipUndo) {
  const t = openTabs.find(x => x.path === path);
  if (!t) return;
  if (t.dirty && !force) {
    if (!confirm('Файл изменён. Закрыть без сохранения?')) return;
  }
  if (!skipUndo) pushUndo({ type: 'close', path, content: t.content, dirty: t.dirty });
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
  else { t.dirty = false; document.getElementById('btn-save').disabled = true; renderTabs(); toast('Сохранено'); await refreshTree(); }
}

let editTimer = null;
let editBefore = null;
document.getElementById('editor').addEventListener('input', () => {
  const t = openTabs.find(x => x.path === activeTab);
  if (!t || document.getElementById('editor').disabled) return;
  if (editBefore === null) editBefore = t.content;
  t.content = document.getElementById('editor').value;
  t.dirty = true;
  document.getElementById('btn-save').disabled = false;
  renderTabs();
  updateLineNumbers();
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
document.getElementById('btn-close-tab').onclick = () => { if (activeTab) closeTab(activeTab, false); };
document.getElementById('btn-undo').onclick = doUndo;
document.getElementById('btn-redo').onclick = doRedo;

/* chat (compact) */
function chatTitleFromPrompt(text) {
  const words = text.trim().split(/\s+/).filter(Boolean);
  let out = [], chars = 0;
  for (const w of words) {
    if (out.length >= 4) break;
    if (out.length >= 2 && chars + w.length > 28) break;
    out.push(w); chars += w.length + 1;
  }
  return out.join(' ') || 'Чат';
}
function renderChatList() {
  const el = document.getElementById('chat-hist');
  el.innerHTML = '';
  const list = running
    ? chats.filter(c => c.id === activeChatId)
    : chats.slice().reverse();
  list.forEach(c => {
    const d = document.createElement('div');
    d.className = 'h' + (c.id === activeChatId ? ' active' : '');
    d.innerHTML = `<span class="title">${esc(c.title || 'Chat')}</span><span class="del">×</span>`;
    d.querySelector('.title').onclick = () => { activeChatId = c.id; renderChatList(); renderMessages(); };
    d.querySelector('.del').onclick = ev => {
      ev.stopPropagation();
      chats = chats.filter(x => x.id !== c.id);
      if (activeChatId === c.id) {
        if (chats.length) activeChatId = chats[chats.length - 1].id;
        else newChat(true);
      }
      saveChats(); renderChatList(); renderMessages();
    };
    el.appendChild(d);
  });
}
function currentChat() { return chats.find(c => c.id === activeChatId); }
function newChat(force) {
  const empty = chats.find(c => !c.messages.length);
  if (!force && empty) { activeChatId = empty.id; renderChatList(); renderMessages(); toast('Уже есть пустой чат'); return; }
  const c = { id: uid(), title: 'Новый чат', messages: [], created: Date.now() };
  chats.push(c); activeChatId = c.id; saveChats(); renderChatList(); renderMessages();
}

function aggregateMessages(msgs) {
  const aggOn = !(settings && settings.chat && settings.chat.aggregate_tools === false);
  const fileOnly = !!(settings && settings.chat && settings.chat.file_ops_only);
  const MERGEABLE = new Set(['web_search','fetch_url','search_code','read_file','list_directory','file_exists','get_file_info']);
  const out = [];
  for (const m of msgs) {
    if (m.kind === 'file_op' && fileOnly) {
      out.push(m);
      continue;
    }
    if (m.kind === 'tool' && m.status === 'pending') continue; // hide pending noise
    if (aggOn && m.kind === 'tool' && m.status !== 'pending' && MERGEABLE.has(m.name)) {
      const prev = out[out.length - 1];
      if (prev && prev.kind === 'tool_agg' && prev.name === m.name) {
        prev.count += 1;
        if (m.status === 'error' || m.success === false) prev.errors += 1;
        continue;
      }
      out.push({
        kind: 'tool_agg',
        name: m.name,
        count: 1,
        errors: (m.status === 'error' || m.success === false) ? 1 : 0,
      });
      continue;
    }
    if (fileOnly && m.kind === 'tool') continue;
    out.push(m);
  }
  return out;
}

let _renderTimer = null;
let _streamChars = 0;
let _streamStarted = 0;
function scheduleRender() {
  if (_renderTimer) return;
  _renderTimer = setTimeout(() => {
    _renderTimer = null;
    renderMessages();
  }, 80); // ~12 fps max during stream
}
function renderMessages() {

  const el = document.getElementById('msgs');
  el.innerHTML = '';
  const c = currentChat(); if (!c) return;
  aggregateMessages(c.messages).filter(m => !(m.kind === 'think_collapsed' && !(m.text || '').trim())).forEach(m => {
    const d = document.createElement('div');
    if (m.kind === 'think_collapsed') {
      d.className = 'msg system'; d.innerHTML = '<span style="color:var(--think)">▸ Обдумано</span>';
    } else if (m.kind === 'think_live') {
      d.className = 'msg system'; d.innerHTML = '<span style="color:var(--muted);font-size:12px">' + esc(m.text || '…') + '</span>';
    } else if (m.kind === 'assistant_live') {
      d.className = 'msg bot assistant'; d.innerHTML = renderMarkdown(m.content || '');
    } else if (m.role === 'user') {
      d.className = 'msg user'; d.textContent = m.content || '';
    } else if (m.role === 'assistant') {
      d.className = 'msg bot assistant' + (m.completed ? ' completed' : '');
      d.innerHTML = renderMarkdown(m.content || '');
    } else if (m.kind === 'tool_agg') {
      const labels = {
        web_search: 'поисков',
        fetch_url: 'ссылок',
        search_code: 'поисков по коду',
        read_file: 'файлов прочитано',
        list_directory: 'просмотров папок',
        file_exists: 'проверок файлов',
        get_file_info: 'info файлов',
      };
      const label = labels[m.name] || m.name;
      d.className = 'msg tool ' + (m.errors ? 'err' : 'ok');
      d.innerHTML = '<b>⚙ ' + esc(m.name) + '</b> — ' + m.count + ' ' + label
        + (m.errors ? ' <span class="muted">(' + m.errors + ' с ошибкой)</span>' : '');
    } else if (m.kind === 'tool') {
      const ok = m.success !== false && m.status !== 'error';
      const pending = m.status === 'pending';
      d.className = 'msg tool ' + (pending ? '' : (ok ? 'ok' : 'err'));
      const debug = !!(settings && settings.chat && settings.chat.developer_mode);
      let body = '<b>⚙ ' + esc(m.name) + '</b> — ' + (pending ? '…' : (ok ? 'успешно' : 'ошибка'));
      if (!pending && m.stop_reason && m.stop_reason !== 'completed') body += ' <span class="muted">(' + esc(m.stop_reason) + ')</span>';
      if (debug && m.args && !pending) body += '<br/><span class="muted">' + esc(typeof m.args === 'string' ? m.args : JSON.stringify(m.args)) + '</span>';
      if (!pending && m.summary) body += '<br/><span class="muted">' + esc(m.summary) + '</span>';
      d.innerHTML = body;
    } else if (m.kind === 'file_op') {
      const col = m.op === 'create' ? 'var(--ok)' : m.op === 'delete' ? 'var(--err)' : 'var(--warn)';
      d.className = 'msg system';
      d.innerHTML = `<span style="color:${col}">${m.op === 'create' ? '＋' : m.op === 'delete' ? '✕' : '✎'} ${esc(m.path || '')}${m.added != null ? ` (+${m.added}/-${m.removed || 0})` : ''}</span>`;
    } else { d.className = 'msg system'; d.textContent = m.content || ''; }
    el.appendChild(d);
  });
  el.scrollTop = el.scrollHeight;
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
  if (e.key !== 'Enter') return;
  const mode = getSendKeyMode();
  const sendNow = mode === 'enter' ? !e.shiftKey : e.shiftKey;
  if (sendNow) {
    e.preventDefault();
    if (!actionBtn.disabled && !running) actionBtn.click();
  }
  // else: allow newline
});
const actionBtn = document.getElementById('btn-action');
function hasMeaningfulText(s) { return /[^\s\u200b]/.test(s || ''); }
function autoGrow() {
  promptEl.style.height = 'auto';
  const max = 1.4 * 13 * 15 + 12;
  const h = Math.min(promptEl.scrollHeight, max);
  promptEl.style.height = h + 'px';
  promptEl.style.overflowY = promptEl.scrollHeight > max ? 'auto' : 'hidden';
}
function updateActionBtn() {
  if (running) { actionBtn.disabled = false; actionBtn.textContent = 'Stop'; actionBtn.className = 'stop'; return; }
  actionBtn.className = ''; actionBtn.textContent = 'Send';
  actionBtn.disabled = !hasMeaningfulText(promptEl.value);
}
promptEl.addEventListener('input', () => { autoGrow(); updateActionBtn(); });
async function ensureModelReady() {
  const info = await api('/api/lms/loaded');
  if (info.error || !info.conflict) return true;
  const loadedNames = (info.loaded || []).map(x => x.model || x.instance_id).join(', ');
  document.getElementById('model-modal-text').textContent =
    'Сейчас загружено: ' + loadedNames + '. Выбрано в настройках: ' + (info.selected_model || '(auto)') + '.';
  document.getElementById('model-modal').classList.add('on');
  return await new Promise(resolve => {
    const done = async (action) => {
      document.getElementById('model-modal').classList.remove('on');
      if (action === 'cancel') { resolve(false); return; }
      setStatus('загрузка модели…', true);
      if (action === 'replace') {
        const u = await api('/api/lms/unload_all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        if (u.error) { toast(u.error, true); resolve(false); return; }
        const l = await api('/api/lms/load', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: info.selected_model, alongside: false }) });
        if (l.error) { toast(l.error, true); resolve(false); return; }
      } else if (action === 'alongside') {
        const l = await api('/api/lms/load', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: info.selected_model, alongside: true }) });
        if (l.error) { toast(l.error, true); resolve(false); return; }
      }
      setStatus('Готов', false);
      resolve(true);
    };
    document.getElementById('mm-cancel').onclick = () => done('cancel');
    document.getElementById('mm-alongside').onclick = () => done('alongside');
    document.getElementById('mm-replace').onclick = () => done('replace');
  });
}

actionBtn.onclick = async () => {
  if (running) { running = false; setStatus('остановка…', true); updateActionBtn(); return; }
  const text = promptEl.value;
  if (!hasMeaningfulText(text)) return;
  const apiTok = (settings && settings.api && settings.api.api_token) || '';
  // optional warning only if provider errors previously required auth — skip hard block for local LMS
  const ok = await ensureModelReady();
  if (!ok) return;
  if (!activeChatId) newChat(true);
  const c = currentChat();
  c.messages.push({ role: 'user', content: text.trim() });
  if (c.title === 'Новый чат') c.title = chatTitleFromPrompt(text);
  promptEl.value = ''; autoGrow();
  saveChats(); renderChatList(); renderMessages();
  setStatus('обработка промпта…', true);
  await runAgent(text.trim());
};
async function runAgent(task) {
  running = true; updateActionBtn(); setStatus('обработка промпта…', true); setFooterTps(0);
  const hist = [];
  const chat = currentChat();
  if (chat) {
    for (const m of chat.messages) {
      if (m.kind) continue;
      if (m.role === 'user' && m.content) hist.push({ role: 'user', content: String(m.content) });
      if (m.role === 'assistant' && m.content) hist.push({ role: 'assistant', content: String(m.content) });
    }
    if (hist.length && hist[hist.length - 1].role === 'user') hist.pop();
  }
  const r = await api('/api/chat/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ task, chat_id: activeChatId, history: hist }) });
  if (r.error) {
    currentChat().messages.push({ role: 'assistant', content: 'Ошибка: ' + r.error });
    saveChats(); renderMessages(); setStatus('ошибка', false);
  } else await pollRun(r.run_id);
  running = false; updateActionBtn();
}
async function pollRun(runId) {
  let done = false;
  while (!done && running) {
    await new Promise(r => setTimeout(r, 400));
    const ev = await api('/api/chat/events?run_id=' + encodeURIComponent(runId));
    if (ev.error) { setStatus(ev.error, false); break; }
    for (const e of (ev.events || [])) handleEvent(e);
    if (ev.done) { done = true; setStatus('готово', false); tpsWindow = []; setFooterTps(0); }
  }
  saveChats(); renderMessages(); await refreshTree();
}
function handleEvent(e) {
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
  if (e.type === 'status') {
    if (e.status === 'thinking') setStatus('обдумывание…', true);
    else if (e.status === 'tool') setStatus('вызов инструмента…', true);
    else if (e.status === 'processing') setStatus('обработка промпта…', true);
    else if (e.status === 'empty_done') {
      setStatus(e.text || 'Модель завершила ответ', false);
      const c = currentChat();
      if (c) {
        c.messages.push({ role: 'system', content: e.text || 'Модель завершила ответ (пусто)', kind: 'empty_done' });
        renderMessages();
      }
    }
    else setStatus(e.text || '…', true);
  } else if (e.type === 'reasoning_delta') {
    setStatus('обдумывание…', true);
    let live = c.messages.find(m => m.kind === 'think_live');
    if (!live) { live = { kind: 'think_live', text: '' }; c.messages.push(live); }
    live.text = (live.text || '') + (e.text || '');
    scheduleRender();
  } else if (e.type === 'content_delta') {
    setStatus('генерация ответа…', true);
    let live = c.messages.find(m => m.kind === 'assistant_live');
    if (!live) {
      const tl = c.messages.find(m => m.kind === 'think_live');
      if (tl) { tl.kind = 'think_collapsed'; }
      live = { kind: 'assistant_live', role: 'assistant', content: '' };
      c.messages.push(live);
    }
    live.content = (live.content || '') + (e.text || '');
    scheduleRender();
  } else if (e.type === 'think_done') {
    const text = (e.text || '').trim();
    const tl = c.messages.find(m => m.kind === 'think_live');
    if (tl) {
      if (text) { tl.kind = 'think_collapsed'; tl.text = text; }
      else { c.messages = c.messages.filter(m => m !== tl); }
    } else if (text) {
      c.messages.push({ kind: 'think_collapsed', text });
    }
    // never leave empty "Обдумано" as last bubble after a completed answer
    const last = c.messages[c.messages.length - 1];
    if (last && last.kind === 'think_collapsed' && !(last.text || '').trim()) {
      c.messages.pop();
    }
    renderMessages();
  } else if (e.type === 'assistant') {
    let content = e.content || '';
    if (content.includes('TASK_COMPLETED')) {
      content = content.replace(/TASK_COMPLETED/g, '').trim();
      e.completed = true;
    }
    const live = c.messages.find(m => m.kind === 'assistant_live');
    if (live) {
      live.kind = undefined;
      live.role = 'assistant';
      live.content = content || live.content || '';
      live.completed = !!e.completed;
    } else {
      c.messages.push({ role: 'assistant', content: content, completed: !!e.completed });
    }
    // drop trailing empty think after final answer
    if (e.completed) {
      while (c.messages.length && c.messages[c.messages.length-1].kind === 'think_collapsed' && !(c.messages[c.messages.length-1].text)) {
        c.messages.pop();
      }
    }
    renderMessages();
  } else if (e.type === 'tool') {
    c.messages.push({ kind: 'tool', name: e.name, status: e.status, success: e.success, stop_reason: e.stop_reason, summary: e.summary, args: e.args }); renderMessages();
  } else if (e.type === 'file_op') {
    c.messages.push({ kind: 'file_op', op: e.op, path: e.path, added: e.added, removed: e.removed }); renderMessages();
  } else if (e.type === 'tps') {
    setFooterTps(e.value || 0);
  }
}

/* settings */
function markSettingsDirty() {
  settingsDirty = true;
  const save = document.getElementById('btn-settings-save');
  const cancel = document.getElementById('btn-settings-cancel');
  save.disabled = false; cancel.disabled = false;
  save.className = 'save-active';
  cancel.className = 'cancel-active';
}
function bindLangDirty() {
  const langSel = document.getElementById('s-chat-lang');
  if (langSel && !langSel.dataset.dirtyBound) {
    langSel.dataset.dirtyBound = '1';
    langSel.addEventListener('change', () => markSettingsDirty());
  }
}
function clearSettingsDirty() {
  settingsDirty = false;
  const save = document.getElementById('btn-settings-save');
  const cancel = document.getElementById('btn-settings-cancel');
  save.disabled = true; cancel.disabled = true;
  save.className = ''; cancel.className = '';
}
function bindNullMax(numId, chkId, val) {
  const num = document.getElementById(numId), chk = document.getElementById(chkId);
  const isNull = val === null || val === undefined;
  chk.checked = isNull; num.disabled = isNull; if (!isNull) num.value = val;
  chk.onchange = () => { num.disabled = chk.checked; markSettingsDirty(); };
  num.oninput = () => markSettingsDirty();
}
function readNullMax(numId, chkId) {
  if (document.getElementById(chkId).checked) return null;
  const v = document.getElementById(numId).value;
  return v === '' ? null : Number(v);
}

async function loadSettings() {
  settings = await api('/api/settings');
  if (settings.error) return;
  settingsSnapshot = JSON.stringify(settings);
  const a = settings.agent, apiS = settings.api, p = settings.prompt;
  document.getElementById('s-workspace').value = a.workspace || './workspace';
  document.getElementById('top-workspace').textContent = a.workspace || './workspace';
  document.getElementById('s-max-iter').value = a.max_iterations != null ? a.max_iterations : '';
  // timeout with unit
  let ts = a.timeout_seconds ?? 120;
  let unit = 's';
  if (ts >= 3600 && ts % 3600 === 0) { unit = 'h'; ts = ts / 3600; }
  else if (ts >= 60 && ts % 60 === 0) { unit = 'm'; ts = ts / 60; }
  document.getElementById('s-timeout').value = ts;
  document.getElementById('s-timeout-unit').value = unit;
  document.getElementById('s-undo-size').value = a.undo_history_size ?? 100;
  undoLimit = a.undo_history_size ?? 100;
  document.getElementById('s-provider').value = apiS.provider || 'lm_studio';
  document.getElementById('s-base-url').value = apiS.base_url || 'http://localhost:1234';
  document.getElementById('s-api-token').value = apiS.api_token || '';
  document.getElementById('s-api-max-tokens').value = apiS.max_tokens != null ? apiS.max_tokens : '';
  document.getElementById('s-api-temp').value = apiS.temperature ?? 0.7;
  document.getElementById('s-system').value = p.system_prompt || '';
  document.getElementById('s-include-tools').checked = !!p.include_tool_catalog;
  const ch = settings.chat || {};
  const elS = document.getElementById('s-chat-streaming');
  if (elS) elS.checked = ch.streaming !== false;
  const elR = document.getElementById('s-chat-reasoning');
  if (elR) elR.checked = ch.show_reasoning_live !== false;
  const elE = document.getElementById('s-chat-empty');
  if (elE) elE.checked = ch.empty_response_status !== false;
  const elD = document.getElementById('s-chat-debug');
  if (elD) elD.checked = !!ch.developer_mode;
  const elF = document.getElementById('s-chat-fileops');
  if (elF) elF.checked = !!ch.file_ops_only;
  const elA = document.getElementById('s-chat-agg');
  if (elA) elA.checked = ch.aggregate_tools !== false;
  const langSel = document.getElementById('s-chat-lang');
  if (langSel && !langSel.dataset.filled) {
    const langs = window.__RESPONSE_LANGS || {};
    langSel.innerHTML = '';
    Object.keys(langs).forEach(k => {
      const o = document.createElement('option');
      o.value = k; o.textContent = langs[k];
      langSel.appendChild(o);
    });
    langSel.dataset.filled = '1';
  }
  if (langSel) langSel.value = ch.response_language || 'auto';
  const sk = ch.send_key || 'enter';
  sendKeyMode = sk;
  const se = document.getElementById('s-send-enter');
  const ss = document.getElementById('s-send-shift-enter');
  if (se && ss) {
    se.checked = sk !== 'shift_enter';
    ss.checked = sk === 'shift_enter';
  }
  setFooterProvider(apiS.provider || 'lm_studio');
  await refreshModelsSelect(apiS.model);
  draftTools = {}; draftPlugins = {};
  await loadComponents();
  clearSettingsDirty();
  // dirty listeners
  ['s-workspace','s-timeout','s-timeout-unit','s-undo-size','s-provider','s-base-url','s-api-token','s-api-temp','s-system','s-max-iter','s-api-max-tokens','s-chat-streaming','s-chat-reasoning','s-chat-empty','s-chat-debug','s-send-enter','s-send-shift-enter','s-chat-fileops','s-chat-agg','s-chat-lang'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.oninput = () => markSettingsDirty();
    if (el && el.tagName === 'SELECT') el.onchange = () => markSettingsDirty();
  });
  document.getElementById('s-include-tools').onchange = () => markSettingsDirty();
}

async function refreshModelsSelect(selected) {
  const sel = document.getElementById('s-model');
  if (!sel) return;
  const prev = selected != null ? selected : sel.value;
  sel.innerHTML = '<option value="">(auto)</option>';
  const data = await api('/api/models');
  (data.models || []).forEach(m => {
    const o = document.createElement('option');
    o.value = m.id; o.textContent = m.name || m.id;
    if (prev && prev === m.id) o.selected = true;
    sel.appendChild(o);
  });
  if (data.error || !data.reachable) setFooterProvider('lm_studio', false);
  else setFooterProvider('lm_studio', true);
  const modelLabel = sel.value || '(auto)';
  const extra = document.getElementById('footer-extra');
  if (extra) {
    const n = (data.models || []).length;
    extra.textContent = data.reachable
      ? (`model: ${modelLabel}` + (n ? ` · ${n} available` : ''))
      : (data.error || 'offline');
  }
  sel.onchange = () => {
    markSettingsDirty();
    const fe = document.getElementById('footer-extra');
    if (fe) fe.textContent = 'model: ' + (sel.value || '(auto)');
  };
}

async function loadComponents() {
  const data = await api('/api/components');
  if (data.error) { toast('Компоненты: ' + data.error, true); console.error(data); }
  componentsCache = data || { tools: [], plugins: [] };
  if (!(componentsCache.tools || []).length) {
    console.warn('empty tools', data);
  }
  (data.tools || []).forEach(t => {
    if (!draftTools[t.id]) draftTools[t.id] = { enabled: t.enabled !== false, values: { ...(t.values || {}) } };
  });
  (data.plugins || []).forEach(p => {
    if (!draftPlugins[p.id]) draftPlugins[p.id] = { values: { ...(p.values || {}) } };
  });
  renderToolsList();
  renderPluginsList();
  renderResetLists();
  // footer from plugin settings
  const ui = (data.plugins || []).find(p => p.id === 'plugin_web_ui');
  if (ui && ui.values && ui.values.show_footer === false) {
    footerEnabled = false;
    document.getElementById('app-footer').classList.add('hidden');
  }
}

function renderToolsList() {
  const by = {};
  (componentsCache.tools || []).forEach(t => { const c = t.category || 'other'; (by[c] = by[c] || []).push(t); });
  const order = ['filesystem', 'terminal', 'web', 'fetch', 'other'];
  const labels = { filesystem: 'Filesystem', terminal: 'Terminal', web: 'Web search', fetch: 'Fetch URL', other: 'Other' };
  const cats = document.getElementById('s-cats');
  if (cats) {
    cats.innerHTML = '';
    order.forEach(k => {
      if (!by[k]?.length) return;
      const anyOn = by[k].some(t => draftTools[t.id]?.enabled !== false);
      const lab = document.createElement('label');
      lab.innerHTML = `<input type="checkbox" data-cat="${k}" ${anyOn ? 'checked' : ''}/> ${labels[k]}`;
      lab.querySelector('input').onchange = e => {
        by[k].forEach(t => { draftTools[t.id] = draftTools[t.id] || { enabled: true, values: {} }; draftTools[t.id].enabled = e.target.checked; });
        markSettingsDirty(); renderToolsList();
      };
      cats.appendChild(lab);
    });
  }
  const el = document.getElementById('s-tools-list');
  if (!el) return;
  el.innerHTML = '';
  order.forEach(k => {
    if (!by[k]?.length) return;
    const box = document.createElement('div');
    box.className = 'tool-group';
    box.innerHTML = `<h4>${labels[k]}</h4>`;
    by[k].forEach(t => {
      const d = draftTools[t.id] || { enabled: true, values: {} };
      const row = document.createElement('div');
      row.className = 'tool-row' + (selectedToolId === t.id ? ' selected' : '');
      row.innerHTML = `<input type="checkbox" class="soft-check" ${d.enabled !== false ? 'checked' : ''}/><span class="tname">${esc(t.name)}</span><span class="tdesc">${esc(t.description || '')}</span>`;
      const cb = row.querySelector('input');
      cb.onclick = e => e.stopPropagation();
      cb.onchange = e => { draftTools[t.id].enabled = e.target.checked; markSettingsDirty(); renderToolsList(); };
      row.onclick = () => { selectedToolId = t.id; renderToolsList(); renderToolDetail(t.id); };
      box.appendChild(row);
    });
    el.appendChild(box);
  });
}
function renderToolDetail(id) {
  const panel = document.getElementById('s-tool-detail');
  const t = (componentsCache.tools || []).find(x => x.id === id);
  if (!panel || !t) return;
  const draft = draftTools[id] || { enabled: true, values: {} };
  let html = `<h3>${esc(t.name)}</h3><div class="hint">${esc(t.description || '')}</div>`;
  const fields = (t.schema && t.schema.fields) || [];
  if (!fields.length) html += '<div class="empty">Нет доп. настроек</div>';
  else fields.forEach(f => {
    const val = draft.values[f.key] !== undefined ? draft.values[f.key] : f.default;
    if (f.type === 'bool') {
      html += `<label class="field-row-check"><input type="checkbox" class="soft-check" data-fk="${esc(f.key)}" ${val ? 'checked' : ''}/><span>${esc(f.label)}</span></label>`;
    } else {
      html += `<div class="field"><label class="lbl">${esc(f.label)}</label>`;
      html += `<input type="${f.type === 'int' || f.type === 'float' ? 'number' : 'text'}" data-fk="${esc(f.key)}" value="${esc(val ?? '')}"/>`;
      html += `</div>`;
    }
  });
  panel.innerHTML = html;
  panel.querySelectorAll('[data-fk]').forEach(inp => {
    inp.addEventListener(inp.type === 'checkbox' ? 'change' : 'input', () => {
      draftTools[id].values[inp.dataset.fk] = inp.type === 'checkbox' ? inp.checked : (inp.type === 'number' ? Number(inp.value) : inp.value);
      markSettingsDirty();
    });
  });
}
function renderPluginsList() {
  const el = document.getElementById('s-plugins-list');
  if (!el) return;
  el.innerHTML = '';
  (componentsCache.plugins || []).forEach(p => {
    const row = document.createElement('div');
    row.className = 'tool-row' + (selectedPluginId === p.id ? ' selected' : '');
    row.innerHTML = `<span class="tname">${esc(p.name || p.id)}</span><span class="tdesc">${esc(p.status || '')}</span>`;
    row.onclick = () => { selectedPluginId = p.id; renderPluginsList(); renderPluginDetail(p.id); };
    el.appendChild(row);
  });
}
function renderPluginDetail(id) {
  const panel = document.getElementById('s-plugin-detail');
  const p = (componentsCache.plugins || []).find(x => x.id === id);
  if (!panel || !p) return;
  const draft = draftPlugins[id] || { values: {} };
  let html = `<h3>${esc(p.name)}</h3>`;
  const fields = (p.schema && p.schema.fields) || [];
  if (!fields.length) html += '<div class="empty">Нет настроек</div>';
  else fields.forEach(f => {
    const val = draft.values[f.key] !== undefined ? draft.values[f.key] : f.default;
    if (f.type === 'bool') {
      html += `<label class="field-row-check"><input type="checkbox" class="soft-check" data-fk="${esc(f.key)}" ${val ? 'checked' : ''}/><span>${esc(f.label)}</span></label>`;
      if (f.description) html += `<div class="hint">${esc(f.description)}</div>`;
    } else {
      html += `<div class="field"><label class="lbl">${esc(f.label)}</label>`;
      html += `<input type="${f.type === 'int' || f.type === 'float' ? 'number' : 'text'}" data-fk="${esc(f.key)}" value="${esc(val ?? '')}"/>`;
      if (f.description) html += `<div class="hint">${esc(f.description)}</div>`;
      html += `</div>`;
    }
  });
  panel.innerHTML = html;
  panel.querySelectorAll('[data-fk]').forEach(inp => {
    inp.addEventListener(inp.type === 'checkbox' ? 'change' : 'input', () => {
      draftPlugins[id].values[inp.dataset.fk] = inp.type === 'checkbox' ? inp.checked : (inp.type === 'number' ? Number(inp.value) : inp.value);
      markSettingsDirty();
    });
  });
}
function renderResetLists() {
  const tl = document.getElementById('reset-tools-list');
  const pl = document.getElementById('reset-plugins-list');
  if (tl) {
    tl.innerHTML = '';
    (componentsCache.tools || []).forEach(t => {
      const d = document.createElement('div');
      d.className = 'reset-item';
      d.innerHTML = `<span>${esc(t.name)}</span><button class="secondary" data-id="${esc(t.id)}">Сбросить</button>`;
      d.querySelector('button').onclick = async () => {
        if (!confirm('Сбросить настройки ' + t.name + '?')) return;
        await api('/api/settings/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'tool', id: t.id }) });
        draftTools[t.id] = undefined;
        await loadComponents();
        toast('Сброшено: ' + t.name);
      };
      tl.appendChild(d);
    });
  }
  if (pl) {
    pl.innerHTML = '';
    (componentsCache.plugins || []).forEach(p => {
      const d = document.createElement('div');
      d.className = 'reset-item';
      d.innerHTML = `<span>${esc(p.name)}</span><button class="secondary" data-id="${esc(p.id)}">Сбросить</button>`;
      d.querySelector('button').onclick = async () => {
        if (!confirm('Сбросить настройки ' + p.name + '?')) return;
        await api('/api/settings/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plugin', id: p.id }) });
        draftPlugins[p.id] = undefined;
        await loadComponents();
        toast('Сброшено: ' + p.name);
      };
      pl.appendChild(d);
    });
  }
}

async function saveAllSettings() {
  const toSec = () => {
    const n = Number(document.getElementById('s-timeout').value) || 120;
    const u = document.getElementById('s-timeout-unit').value;
    if (u === 'm') return n * 60;
    if (u === 'h') return n * 3600;
    return n;
  };
  const emptyNum = (id) => {
    const v = document.getElementById(id).value;
    if (v === '' || v == null) return null;
    return Number(v);
  };
  const agent = {
    workspace: document.getElementById('s-workspace').value,
    max_iterations: emptyNum('s-max-iter'),
    timeout_seconds: toSec(),
    undo_history_size: Number(document.getElementById('s-undo-size').value) || 100,
  };
  undoLimit = agent.undo_history_size;
  const apiBody = {
    provider: document.getElementById('s-provider').value,
    base_url: document.getElementById('s-base-url').value,
    api_token: document.getElementById('s-api-token').value,
    model: document.getElementById('s-model').value,
    temperature: Number(document.getElementById('s-api-temp').value),
    max_tokens: emptyNum('s-api-max-tokens'),
  };
  const prompt = {
    system_prompt: document.getElementById('s-system').value,
    include_tool_catalog: document.getElementById('s-include-tools').checked,
  };
  const chat = {
    streaming: document.getElementById('s-chat-streaming')?.checked !== false,
    show_reasoning_live: document.getElementById('s-chat-reasoning')?.checked !== false,
    empty_response_status: document.getElementById('s-chat-empty')?.checked !== false,
    developer_mode: !!document.getElementById('s-chat-debug')?.checked,
    send_key: document.getElementById('s-send-shift-enter')?.checked ? 'shift_enter' : 'enter',
    file_ops_only: !!document.getElementById('s-chat-fileops')?.checked,
    aggregate_tools: document.getElementById('s-chat-agg')?.checked !== false,
    response_language: document.getElementById('s-chat-lang')?.value || 'auto',
  };
  sendKeyMode = chat.send_key;
  await api('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ agent, api: apiBody, prompt, chat }) });
  for (const t of (componentsCache.tools || [])) {
    const d = draftTools[t.id];
    if (!d) continue;
    await api('/api/component/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'tool', id: t.id, values: d.values, enabled: d.enabled }) });
  }
  for (const p of (componentsCache.plugins || [])) {
    const d = draftPlugins[p.id];
    if (!d) continue;
    await api('/api/component/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plugin', id: p.id, values: d.values }) });
  }
  document.getElementById('top-workspace').textContent = agent.workspace;
  setFooterProvider(apiBody.provider);
  const modelName = apiBody.model || '(auto)';
  document.getElementById('footer-extra').textContent = 'model: ' + modelName;
  // apply plugin footer visibility immediately
  const uiDraft = draftPlugins['plugin_web_ui'];
  if (uiDraft && uiDraft.values && uiDraft.values.show_footer === false) {
    document.getElementById('app-footer').classList.add('hidden');
  } else {
    document.getElementById('app-footer').classList.remove('hidden');
  }
  clearSettingsDirty();
  toast('Сохранено');
  await refreshTree();
  await refreshModelsSelect(apiBody.model);
}

document.getElementById('btn-settings-save').onclick = saveAllSettings;
document.getElementById('btn-settings-cancel').onclick = async () => {
  if (!settingsDirty) return;
  if (!confirm('Отменить несохранённые изменения?')) return;
  draftTools = {}; draftPlugins = {};
  await loadSettings();
  toast('Изменения отменены');
};
document.getElementById('btn-factory-reset').onclick = async () => {
  if (!confirm('Сбросить ВСЕ настройки к заводским?')) return;
  if (!confirm('Точно? Это необратимо для локальных JSON настроек.')) return;
  await api('/api/settings/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scope: 'all' }) });
  draftTools = {}; draftPlugins = {};
  await loadSettings();
  toast('Заводские настройки');
};

/* workspace folder picker (best-effort) */
document.getElementById('btn-pick-ws').onclick = async () => {
  const r = await api('/api/fs/pick_folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  if (r.error) { toast(r.error, true); return; }
  if (r.cancelled) return;
  if (r.path) {
    document.getElementById('s-workspace').value = r.path;
    markSettingsDirty();
  }
};

/* nav */
document.getElementById('nav-logo').onclick = () => {
  if (settingsDirty && !confirm('Настройки не сохранены. Уйти?')) return;
  showView('main');
};
document.getElementById('nav-settings').onclick = () => {
  const btn = document.getElementById('nav-settings');
  const open = document.getElementById('view-settings').style.display === 'block';
  if (open) {
    showView('main');
    btn.classList.remove('active-settings');
    btn.textContent = '⚙';
    btn.title = 'Settings';
  } else {
    showView('settings');
    btn.classList.add('active-settings');
    btn.textContent = '✕';
    btn.title = 'Close settings';
    loadSettings();
  }
};
document.getElementById('btn-toggle-explorer').onclick = () => setExplorerCollapsed(!explorerCollapsed);
document.getElementById('btn-toggle-chat').onclick = () => setChatCollapsed(!chatCollapsed);
document.getElementById('btn-refresh-tree').onclick = () => refreshTree();
document.getElementById('btn-new-chat').onclick = () => newChat(false);
document.getElementById('btn-refresh-models').onclick = () => refreshModelsSelect(document.getElementById('s-model').value);

document.querySelectorAll('.stab').forEach(s => {
  s.onclick = () => {
    document.querySelectorAll('.stab').forEach(x => x.classList.remove('active'));
    s.classList.add('active');
    document.querySelectorAll('.tabp').forEach(p => p.style.display = 'none');
    document.getElementById('tab-' + s.dataset.tab).style.display = 'block';
  };
});

/* init */
loadPanelWidths();
bindResizer('resizer-left', 'left');
bindResizer('resizer-right', 'right');
loadChats();
if (!chats.length) newChat(true);
else { activeChatId = chats[chats.length - 1].id; renderChatList(); renderMessages(); }
clearEditor();
refreshTree();
loadSettings();
updateActionBtn();
autoGrow();
startTreePoll();
document.querySelector('.settings-actions').style.display = 'none';

/* editor scrollbar: default cursor when over scrollbar */
(function() {
  const ed = document.getElementById('editor');
  if (!ed) return;
  ed.addEventListener('mousemove', (e) => {
    const r = ed.getBoundingClientRect();
    const bar = 14; // approx scrollbar width
    const onV = e.clientX >= r.right - bar;
    const onH = e.clientY >= r.bottom - bar;
    ed.style.cursor = (onV || onH) ? 'default' : 'text';
  });
  ed.addEventListener('mouseleave', () => { ed.style.cursor = 'text'; });
})();
