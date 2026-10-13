
const UI_I18N = {
  en: {
    explorer: 'Explorer', chat: 'Chat', newChat: 'New', settings: 'Settings',
    save: 'Save', cancel: 'Cancel', send: 'Send', stop: 'Stop',
    openFile: 'Open a file…', ready: 'Готово', done: 'Done', error: 'Error',
    stopping: 'Stopping…', stopped: 'Stopped',
    processing: 'Processing prompt…', thinking: 'Thinking…', generating: 'Generating…',
    aggHint: 'Merge consecutive collapsible tool calls into one chat block',
    aggLabel: 'Merge tool calls when possible',
    attach: 'Attach', attachSearch: 'Search project files…',
    createFile: 'New file', createDir: 'New folder', reveal: 'Show in explorer',
    delete: 'Delete', rename: 'Rename', promptPh: 'Message agent…',
    serverMode: 'Server mode',
    chatSettings: 'Chat settings', agentSettings: 'Agent settings',
    apiModel: 'API & model', systemPrompt: 'System prompt',
    tools: 'Tools', plugins: 'Plugins', resetSettings: 'Reset settings',
    streamResponses: 'Stream responses', showReasoning: 'Show reasoning',
    emptyStatus: 'Status on empty response', developerMode: 'Developer mode',
    sendMessage: 'Send message',
    sendEnter: 'Enter — send, Shift+Enter — new line',
    sendShift: 'Shift+Enter — send, Enter — new line',
    fileOpsOnly: 'File ops: names only', responseLang: 'Response language',
    baseUrl: 'Base URL', workspace: 'Workspace', undo: 'Undo', redo: 'Redo',
    close: 'Close', refresh: 'Refresh', provider: 'provider', model: 'model',
    notLoaded: 'not loaded', loaded: 'loaded', offline: 'offline',
    available: 'available', ctx: 'ctx',
    tabAgent: 'Agent', tabApi: 'API & model', tabPrompt: 'System prompt',
    tabChat: 'Chat', tabTools: 'Tools', tabPlugins: 'Plugins', tabReset: 'Reset settings',
    workspace: 'Workspace', browse: 'Browse…', maxIterations: 'Max iterations',
    modelTimeout: 'Model response timeout', undoSize: 'Undo history size',
    provider: 'provider', model: 'model', temperature: 'Temperature',
    maxTokens: 'Max tokens', apiToken: 'API token', refresh: 'Refresh',
    includeTools: 'Include tool catalog in context',
    factoryReset: 'Reset everything to factory defaults',
    requiresDouble: 'Requires double confirmation',
    toolsHeading: 'Tools',
    pluginsHeading: 'Plugins',
    stopUi: 'Stop UI',

    selectTool: 'Select a tool', selectPlugin: 'Select a plugin',
    noMatches: 'No matches', typeToSearch: 'Type to search project files',
    seconds: 'seconds', minutes: 'minutes', hours: 'hours',
  },
  ru: {
    explorer: 'Проводник', chat: 'Чат', newChat: 'Новый', settings: 'Настройки',
    save: 'Сохранить', cancel: 'Отмена', send: 'Отправить', stop: 'Стоп',
    openFile: 'Откройте файл…', ready: 'Готово', done: 'Готово', error: 'Ошибка',
    stopping: 'Остановка…', stopped: 'Остановлено',
    processing: 'Обработка промпта…', thinking: 'Обдумывание…', generating: 'Генерация…',
    aggHint: 'Объединять подряд идущие вызовы tools в один блок',
    aggLabel: 'Объединять вызовы инструментов',
    attach: 'Вложение', attachSearch: 'Поиск файлов проекта…',
    createFile: 'Новый файл', createDir: 'Новая папка', reveal: 'Показать в проводнике',
    delete: 'Удалить', rename: 'Переименовать', promptPh: 'Сообщение агенту…',
    serverMode: 'Серверный режим',
    chatSettings: 'Настройки чата', agentSettings: 'Настройки агента',
    apiModel: 'API и модель', systemPrompt: 'Системный промпт',
    tools: 'Инструменты', plugins: 'Плагины', resetSettings: 'Сброс настроек',
    streamResponses: 'Поток ответа', showReasoning: 'Показывать рассуждения',
    emptyStatus: 'Статус при пустом ответе', developerMode: 'Режим разработчика',
    sendMessage: 'Отправка сообщения',
    sendEnter: 'Enter — отправить, Shift+Enter — новая строка',
    sendShift: 'Shift+Enter — отправить, Enter — новая строка',
    fileOpsOnly: 'Только имена файловых операций', responseLang: 'Язык ответа',
    baseUrl: 'Base URL', workspace: 'Workspace', undo: 'Отменить', redo: 'Повторить',
    close: 'Закрыть', refresh: 'Обновить', provider: 'Провайдер', model: 'модель',
    notLoaded: 'не загружена', loaded: 'загружена', offline: 'офлайн',
    available: 'доступно', ctx: 'контекст',
    tabAgent: 'Агент', tabApi: 'API и модель', tabPrompt: 'Системный промпт',
    tabChat: 'Чат', tabTools: 'Инструменты', tabPlugins: 'Плагины', tabReset: 'Сброс',
    workspace: 'Workspace', browse: 'Обзор…', maxIterations: 'Макс. итераций',
    modelTimeout: 'Таймаут ответа модели', undoSize: 'Размер истории отмены',
    provider: 'Провайдер', model: 'модель', temperature: 'Temperature',
    maxTokens: 'Макс. токенов', apiToken: 'API token', refresh: 'Обновить',
    includeTools: 'Добавлять каталог tools в контекст',
    factoryReset: 'Сбросить всё к заводским настройкам',
    requiresDouble: 'Требуется двойное подтверждение',
    toolsHeading: 'Инструменты',
    pluginsHeading: 'Плагины',
    stopUi: 'Выключить UI',

    selectTool: 'Выберите инструмент', selectPlugin: 'Выберите плагин',
    noMatches: 'Нет совпадений', typeToSearch: 'Введите запрос для поиска файлов',
    seconds: 'сек', minutes: 'мин', hours: 'ч',
  },
};
let uiLocale = 'en';
function t(key) {
  return (UI_I18N[uiLocale] && UI_I18N[uiLocale][key]) || (UI_I18N.en[key] || key);
}
function applyUiLocale(locale) {
  uiLocale = (locale === 'ru') ? 'ru' : 'en';
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const k = el.getAttribute('data-i18n');
    if (k) el.textContent = t(k);
  });
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const k = el.getAttribute('data-i18n-title');
    if (k) el.title = t(k);
  });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const k = el.getAttribute('data-i18n-placeholder');
    if (k) el.placeholder = t(k);
  });
  // settings tabs
  const tabMap = {
    agent: 'tabAgent', api: 'tabApi', prompt: 'tabPrompt', chat: 'tabChat',
    tools: 'tabTools', plugins: 'tabPlugins', reset: 'tabReset',
  };
  document.querySelectorAll('.stab').forEach(el => {
    const k = tabMap[el.dataset.tab];
    if (k) el.textContent = t(k);
  });
  const ex = document.querySelector('#explorer h3 .grow');
  if (ex) ex.textContent = t('explorer');
  const ch = document.querySelector('#chat-panel h3 .grow');
  if (ch) ch.textContent = t('chat');
  const nc = document.getElementById('btn-new-chat');
  if (nc) nc.textContent = '+ ' + t('newChat');
  const pr = document.getElementById('prompt');
  if (pr) pr.placeholder = t('promptPh');
  const ed = document.getElementById('editor');
  if (ed) ed.placeholder = t('openFile');
  const save = document.getElementById('btn-settings-save');
  if (save) save.textContent = t('save');
  const cancel = document.getElementById('btn-settings-cancel');
  if (cancel) cancel.textContent = t('cancel');
  const und = document.getElementById('btn-undo');
  if (und) und.textContent = t('undo');
  const red = document.getElementById('btn-redo');
  if (red) red.textContent = t('redo');
  const clo = document.getElementById('btn-close-tab');
  if (clo) clo.textContent = t('close');
  const sav = document.getElementById('btn-save');
  if (sav) sav.textContent = t('save');
  const br = document.getElementById('btn-pick-ws');
  if (br) br.textContent = t('browse');
  const rm = document.getElementById('btn-refresh-models');
  if (rm) rm.textContent = t('refresh');
  const fr = document.getElementById('btn-factory-reset');
  if (fr) fr.textContent = t('factoryReset');
  const su = document.getElementById('btn-stop-ui');
  if (su) su.textContent = '⏹ ' + t('stopUi');
  const mmc = document.getElementById('mm-cancel');
  if (mmc) mmc.textContent = t('cancel');
  const st = document.getElementById('agent-status');
  if (st && !running) st.textContent = t('ready');
  const unit = document.getElementById('s-timeout-unit');
  if (unit) {
    [...unit.options].forEach(o => {
      if (o.value === 's') o.textContent = t('seconds');
      if (o.value === 'm') o.textContent = t('minutes');
      if (o.value === 'h') o.textContent = t('hours');
    });
  }
  // Labels: only elements with data-i18n (no DOM surgery that duplicates text)
  document.querySelectorAll('.field > .lbl').forEach(lbl => {
    // If label has leftover duplicate text nodes from older builds, normalize once
    const tips = [...lbl.querySelectorAll('.info-tip')];
    const i18nSpans = [...lbl.querySelectorAll('[data-i18n]')];
    if (i18nSpans.length) {
      const key = i18nSpans[0].getAttribute('data-i18n');
      lbl.innerHTML = '';
      const span = document.createElement('span');
      span.setAttribute('data-i18n', key);
      span.textContent = t(key);
      lbl.appendChild(span);
      tips.forEach(tip => lbl.appendChild(tip));
    }
  });
  document.documentElement.lang = uiLocale;
  updateActionBtn();
  if (!running) setStatus(t('ready'), false);
  setFooterContext(null, _modelContextLimit);
}
const LS_CHATS = 'kerniq_chats_v1';
const LS_PANEL = 'kerniq_panels_v1';

let settings = null;
let openTabs = [];
let activeTab = null;
let chats = [];
let activeChatId = null;
const MAX_CHATS = 3;
let running = false;
let currentRunId = null;
let streamingEnabled = true;
let generatingTokens = false;
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
let chatAttachments = []; // {path, exists, external}


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
function parseFileLinks(html) {
  return html.replace(/\[\[file:([^\]]+)\]\]/g, (_, p) => {
    const path = p.trim();
    return `<a href="#" class="file-ref" data-path="${esc(path)}">${esc(path)}</a>`;
  });
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
  return parseFileLinks(out.join('\n') || '');
}


/* ---------- syntax highlight (Prism) ---------- */
function langFromPath(path) {
  const ext = (path || '').split('.').pop().toLowerCase();
  const map = {
    py: 'python', pyw: 'python',
    js: 'javascript', mjs: 'javascript', cjs: 'javascript',
    ts: 'typescript', tsx: 'typescript',
    json: 'json', jsonc: 'json',
    sh: 'bash', bash: 'bash', zsh: 'bash',
    ps1: 'powershell', psm1: 'powershell',
    html: 'markup', htm: 'markup', xml: 'markup', svg: 'markup',
    css: 'css', scss: 'css',
    md: 'markdown', markdown: 'markdown',
    yml: 'yaml', yaml: 'yaml',
    toml: 'markup', ini: 'markup',
    rs: 'rust', go: 'go', java: 'java',
    c: 'c', h: 'c', cpp: 'cpp', cc: 'cpp', hpp: 'cpp',
    cs: 'csharp', sql: 'sql',
  };
  return map[ext] || 'none';
}
function updateHighlight() {
  const ed = document.getElementById('editor');
  const code = document.getElementById('hl-code');
  if (ed) ed.classList.add('no-hl');
  if (code) { code.textContent = ''; code.className = 'language-none'; }
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
  try {
    let raw = localStorage.getItem(LS_CHATS);
    // migrate from older keys that saveChats accidentally used
    if (!raw) raw = localStorage.getItem('kerniq_chats');
    chats = JSON.parse(raw || '[]');
    if (!Array.isArray(chats)) chats = [];
    // normalize per-chat context fields
    chats.forEach(c => {
      if (c.prompt_tokens == null) c.prompt_tokens = null;
      if (c.context_limit == null) c.context_limit = null;
    });
    if (chats.length > MAX_CHATS) chats = chats.slice(-MAX_CHATS);
  } catch {
    chats = [];
  }
}
function saveChats() {
  if (chats.length > MAX_CHATS) {
    chats = chats.slice(-MAX_CHATS);
    if (!chats.find(c => c.id === activeChatId)) {
      activeChatId = chats.length ? chats[chats.length - 1].id : null;
    }
  }
  try {
    localStorage.setItem(LS_CHATS, JSON.stringify(chats));
    // remove legacy key so deleted chats cannot resurrect
    localStorage.removeItem('kerniq_chats');
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


function setFooterState(mode) {
  const dot = document.getElementById('footer-dot');
  if (!dot) return;
  dot.className = 'dot ' + (mode || 'idle');
}
function setFooterProvider(name, ok) {
  const el = document.getElementById('footer-provider');
  if (el) el.textContent = t('provider') + ': ' + (name || '—');
  if (ok === false) setFooterState('err');
  else if (!running) setFooterState('idle');
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
  el.textContent = text || '';
  el.classList.toggle('bad', ok === false);
  el.classList.toggle('ok', ok === true);
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
    updateHighlight();
    return;
  }
  const text = ed.value || '';
  const n = text.length === 0 ? 1 : text.split('\n').length;
  const parts = [];
  for (let i = 1; i <= n; i++) parts.push(String(i));
  ln.textContent = parts.join('\n');
  ln.scrollTop = ed.scrollTop;
  updateHighlight();
}
document.getElementById('editor').addEventListener('scroll', () => {
  const ed = document.getElementById('editor');
  document.getElementById('line-nums').scrollTop = ed.scrollTop;
  const pre = document.querySelector('.hl-pre');
  if (pre) { pre.scrollTop = ed.scrollTop; pre.scrollLeft = ed.scrollLeft; }
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
        node.children[part] = { name: part, path: parts.slice(0, i + 1).join('/'), type: isLast ? e.type : 'dir', hidden: isLast ? !!e.hidden : (part.startsWith('.')), children: {} };
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
        row.innerHTML = `<span class="twist">${open ? '▼' : '▶'}</span><span style="opacity:${ch.hidden?0.45:1}">📁</span><span style="opacity:${ch.hidden?0.55:1}">${esc(ch.name)}</span>`;
        row.onclick = () => { if (expanded.has(ch.path)) expanded.delete(ch.path); else expanded.add(ch.path); renderTree(); };
        row.oncontextmenu = ev => { ev.preventDefault(); showCtx(ev, ch.path, true); };
        el.appendChild(row);
        if (open) walk(ch, depth + 1);
      } else {
        row.innerHTML = `<span class="twist"></span><span style="opacity:${ch.hidden?0.45:1}">${ch.type==='dir'?'📁':'📄'}</span><span style="opacity:${ch.hidden?0.55:1}">${esc(ch.name)}</span>`;
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
  ctx.style.display = 'block';
  ctx.style.left = ev.clientX + 'px';
  ctx.style.top = ev.clientY + 'px';
  const parent = isDir ? path : (path ? path.split('/').slice(0, -1).join('/') : '');
  let html = '';
  if (!isRoot && !isDir) html += `<button data-a="open">${'Open'}</button>`;
  html += `<button data-a="newfile">${t('createFile')}</button>`;
  html += `<button data-a="newdir">${t('createDir')}</button>`;
  html += `<button data-a="reveal">${t('reveal')}</button>`;
  if (!isRoot && path) {
    html += `<button data-a="rename">${t('rename')}</button>`;
    html += `<button data-a="delete" style="color:var(--err)">${t('delete')}</button>`;
  }
  ctx.innerHTML = html;
  ctx.querySelectorAll('button').forEach(b => {
    b.onclick = async () => {
      hideCtx();
      const a = b.dataset.a;
      if (a === 'open') openFile(path);
      else if (a === 'newfile' || a === 'newdir') {
        const name = prompt(a === 'newdir' ? t('createDir') : t('createFile'));
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
      } else if (a === 'reveal') {
        const r = await api('/api/fs/reveal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: path || '.' }) });
        if (r.error) toast(r.error, true); else toast('Opened');
      } else if (a === 'rename') {
        const base = path.split('/').pop();
        const nn = prompt(t('rename'), base);
        if (!nn || nn === base) return;
        const r = await api('/api/fs/rename', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path, new_name: nn }) });
        if (r.error) toast(r.error, true);
        else { toast('Renamed'); await refreshTree(); }
      } else if (a === 'delete') {
        if (!confirm('Delete ' + path + '?')) return;
        const r = await api('/api/fs/file?path=' + encodePath(path), { method: 'DELETE' });
        if (r.error) toast(r.error, true);
        else { toast('Deleted'); openTabs = openTabs.filter(t => t.path !== path); if (activeTab === path) clearEditor(); await refreshTree(); renderTabs(); }
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
    if (!confirm('File has changes. Close without saving?')) return;
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
  else { t.dirty = false; document.getElementById('btn-save').disabled = true; renderTabs(); toast(t('save')); await refreshTree(); }
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
  return out.join(' ') || 'Chat';
}
function renderChatList() {
  const el = document.getElementById('chat-hist');
  if (!el) return;
  // Enforce max chats in memory
  if (chats.length > MAX_CHATS) {
    chats = chats.slice(-MAX_CHATS);
    saveChats();
  }
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
function toolIcon(name) {
  const t = (componentsCache.tools || []).find(x => x.name === name || x.id === name);
  if (t && t.ui_icon) return t.ui_icon;
  return TOOL_ICON[name] || '⚙';
}
function toolAggLabel(name, count) {
  const t = (componentsCache.tools || []).find(x => x.name === name || x.id === name);
  if (t && count > 1) {
    // prefer dynamic plural from tool if available via simple pattern
  }
  const base = AGG_LABEL[name] || name;
  return count + ' ' + base;
}
const MERGEABLE = new Set(['web_search','fetch_url','search_code','read_file','list_directory','file_exists','get_file_info']);
const TOOL_ICON = {
  web_search: '🔍', fetch_url: '🔗', search_code: '🔎',
  list_directory: '📁', read_file: '📄', write_file: '✍️',
  create_file: '＋', edit_file: '✎', delete_file: '🗑',
  create_directory: '📂', run_command: '💻',
};
const AGG_LABEL = {
  web_search: 'searches', fetch_url: 'fetches', search_code: 'code searches',
  read_file: 'files read', list_directory: 'dirs listed',
  file_exists: 'checks', get_file_info: 'info',
};

function aggregateMessages(msgs) {
  const aggOn = !(settings && settings.chat && settings.chat.aggregate_tools === false);
  const fileOnly = !!(settings && settings.chat && settings.chat.file_ops_only);
  const debug = !!(settings && settings.chat && settings.chat.developer_mode);
  const out = [];
  for (const m of msgs) {
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
      out.push({ ...m, summary: '', args: undefined });
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
      d.className = 'msg system'; d.innerHTML = '<span style="color:var(--think)">▸ Thought</span>';
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
        web_search: 'searches',
        fetch_url: 'links',
        search_code: 'code searches',
        read_file: 'files read',
        list_directory: 'folder views',
        file_exists: 'file checks',
        get_file_info: 'file info',
      };
      const label = labels[m.name] || m.name;
      d.className = 'msg tool ' + (m.errors ? 'err' : 'ok');
      d.innerHTML = '<b>⚙ ' + esc(m.name) + '</b> — ' + m.count + ' ' + label
        + (m.errors ? ' <span class="muted">(' + m.errors + ' failed)</span>' : '');
    } else if (m.kind === 'tool') {
      const ok = m.success !== false && m.status !== 'error';
      const pending = m.status === 'pending';
      d.className = 'msg tool ' + (pending ? '' : (ok ? 'ok' : 'err'));
      const debug = !!(settings && settings.chat && settings.chat.developer_mode);
      let body = '<b>⚙ ' + esc(m.name) + '</b> — ' + (pending ? '…' : (ok ? 'ok' : 'error'));
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
promptEl.addEventListener('input', () => { autoGrow(); updateActionBtn(); });
function _modelMatch(a, b) {
  if (!a || !b) return false;
  a = String(a); b = String(b);
  if (a === b) return true;
  if (a.includes(b) || b.includes(a)) return true;
  const ta = a.split(/[\\/]/).pop();
  const tb = b.split(/[\\/]/).pop();
  return !!(ta && tb && (ta === tb || ta.includes(tb) || tb.includes(ta)));
}

/** Ensure a usable model is loaded. Never hangs on a modal. */
async function ensureModelReady() {
  let info;
  try {
    info = await api('/api/lms/loaded');
  } catch (e) {
    toast('Cannot reach LM Studio status: ' + e, true);
    return true; // still try /api/chat/run — provider may work
  }
  if (info && info.error) {
    toast('LM Studio: ' + info.error, true);
    return true;
  }
  const selected = String((info && info.selected_model) || '').trim();
  const loaded = (info && info.loaded) || [];
  const loadedIds = loaded.map(x => x.model || x.id || x.key || '').filter(Boolean);
  const selectedLoaded = selected && loadedIds.some(id => _modelMatch(id, selected));

  // auto or already loaded
  if (!selected || selectedLoaded) return true;

  setStatus('Loading model…', true);
  try {
    if (loadedIds.length) {
      const u = await api('/api/lms/unload_all', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
      });
      if (u && u.error) {
        toast('Unload failed: ' + u.error, true);
        // continue try load anyway
      }
    }
    const l = await api('/api/lms/load', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: selected, alongside: false }),
    });
    setStatus(t('ready'), false);
    if (l && l.error) {
      toast('Load failed: ' + l.error, true);
      return false;
    }
    await refreshModelFooter().catch(() => {});
    return true;
  } catch (e) {
    setStatus(t('ready'), false);
    toast('Model load error: ' + e, true);
    return false;
  }
}



actionBtn.onclick = async () => {
  if (running) {
    setStatus(t('stopping') || 'Stopping…', true);
    updateActionBtn();
    const rid = currentRunId;
    if (rid) {
      try {
        await api('/api/chat/cancel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ run_id: rid }),
        });
      } catch (e) { /* ignore */ }
    }
    return;
  }
  try {
    const text = promptEl.value;
    if (!hasMeaningfulText(text)) return;
    const ok = await ensureModelReady();
    if (!ok) {
      toast(uiLocale === 'ru' ? 'Модель не готова — отправка отменена' : 'Model not ready — send cancelled', true);
      return;
    }
    if (!activeChatId) newChat(true);
    const c = currentChat();
    if (!c) {
      toast('No active chat', true);
      return;
    }
    let taskToSend = text.trim();
    if (chatAttachments.length) {
      taskToSend = text.trim() + '\n\nAttached files (use these paths):\n' + chatAttachments.map(a => a.path).join('\n');
    }
    c.messages.push({ role: 'user', content: text.trim(), attachments: chatAttachments.slice() });
    if (c.title === 'New chat') c.title = chatTitleFromPrompt(text);
    chatAttachments = [];
    renderAttachChips();
    promptEl.value = ''; autoGrow(); updateActionBtn();
    saveChats(); renderChatList(); renderMessages();
    setStatus(statusLabel('processing'), true);
    await runAgent(taskToSend);
  } catch (err) {
    console.error('send failed', err);
    toast('Send failed: ' + (err && err.message ? err.message : err), true);
    running = false;
    setStatus(t('error') || 'Error', false);
    updateActionBtn();
  }
};
async function runAgent(task) {
  running = true;
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
      if (m.kind) continue;
      if (m.role === 'user' && m.content) hist.push({ role: 'user', content: String(m.content) });
      if (m.role === 'assistant' && m.content) hist.push({ role: 'assistant', content: String(m.content) });
    }
    if (hist.length && hist[hist.length - 1].role === 'user') hist.pop();
  }
  try {
    const r = await api('/api/chat/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, chat_id: activeChatId, history: hist }),
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
    currentChat().messages.push({ role: 'assistant', content: 'Error: ' + msg });
    saveChats(); renderMessages(); setStatus('Error', false);
  }
  finalizeLiveMessages();
  generatingTokens = false;
  stopTpsTimer();
  resetTps(!streamingEnabled);
  currentRunId = null;
  running = false;
  updateActionBtn();
  try { await refreshModelFooter(); } catch (_) {}
}
async function pollRun(runId) {
  let done = false;
  let idleTicks = 0;
  let networkFails = 0;
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
      ev = await api('/api/chat/events?run_id=' + encodeURIComponent(runId));
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
function statusLabel(st, fallback) {
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
    }
  }
  saveChats();
  renderMessages();
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
  if (e.type === 'heartbeat') {
    // keep poll alive during long prefill / thinking with no tokens yet
    setStatus(e.text || statusLabel('processing'), true);
    return;
  }
  if (e.type === 'status') {
    const st = e.status || '';
    if (st === 'empty_done') {
      generatingTokens = false;
      setStatus(statusLabel(st, e.text), false);
      if (c) {
        c.messages.push({ role: 'system', content: e.text || 'Model finished (empty response)', kind: 'empty_done' });
        renderMessages();
      }
    } else if (st === 'done' || st === 'cancelled') {
      generatingTokens = false;
      setStatus(statusLabel(st, e.text), false);
    } else if (st === 'error') {
      generatingTokens = false;
      setStatus(statusLabel(st, e.text || 'Error'), false);
    } else if (st === 'generating') {
      generatingTokens = true;
      setStatus(statusLabel(st, e.text), true);
    } else if (st === 'thinking' || st === 'processing' || st === 'loading_model') {
      generatingTokens = false;
      setStatus(statusLabel(st, e.text), true);
    } else if (st === 'tool' || st === 'waiting_tool') {
      generatingTokens = false;
      setStatus(statusLabel(st, e.text), true);
    } else {
      setStatus(e.text || statusLabel(st), true);
    }
  } else if (e.type === 'reasoning_delta') {
    // Reasoning streams tokens too — count for tok/s while thinking
    noteGeneratedText(e.text || '');
    setStatus(statusLabel('thinking'), true);
    let live = c.messages.find(m => m.kind === 'think_live');
    if (!live) { live = { kind: 'think_live', text: '' }; c.messages.push(live); }
    live.text = (live.text || '') + (e.text || '');
    scheduleRender();
  } else if (e.type === 'content_delta') {
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
      if (text) { tl.kind = 'think_collapsed'; tl.text = text; }
      else c.messages = c.messages.filter(m => m !== tl);
    } else if (text) {
      c.messages.push({ kind: 'think_collapsed', text });
    }
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
    if (liveIdx >= 0) {
      const live = c.messages[liveIdx];
      live.kind = undefined;
      live.role = 'assistant';
      live.content = content || live.content || '';
      live.completed = !!e.completed;
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
        break;
      }
    }
    c.messages.push({
      kind: 'tool', name: e.name, status: e.status, success: e.success,
      stop_reason: e.stop_reason, summary: e.summary, args: e.args,
    });
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


async function refreshModelFooter() {
  try {
    const s = settings || {};
    const prov = (s.api && s.api.provider) || 'lm_studio';
    setFooterProvider(prov);
    streamingEnabled = !(s.chat && s.chat.streaming === false);
    if (prov === 'mock') {
      setFooterModelStatus(t('model') + ': mock', true);
      setFooterContext(_lastPromptTokens, null);
      const fe = document.getElementById('footer-extra');
      if (fe) fe.textContent = '';
      return;
    }
    const selected = (s.api && s.api.model) || '';
    const info = await api('/api/lms/loaded');
    const modelsData = await api('/api/models').catch(() => ({}));
    // context limit from first matching model if available
    _modelContextLimit = null;
    for (const m of (modelsData.models || [])) {
      // Prefer actual loaded window, then max capability
      const lim = m.loaded_context_length || m.context_length || m.max_context_length || m.context || null;
      if (!lim) continue;
      const mid = m.id || m.name || '';
      if (selected && (mid === selected || String(mid).includes(selected) || selected.includes(String(mid)))) {
        _modelContextLimit = Number(lim);
        break;
      }
      if (_modelContextLimit == null) _modelContextLimit = Number(lim);
    }
    if (info && info.error) {
      setFooterModelStatus(t('model') + ': ' + t('offline'), false);
      setFooterContext(_lastPromptTokens, _modelContextLimit);
      return;
    }
    const loaded = (info && (info.loaded || info.models || info.instances)) || [];
    const names = Array.isArray(loaded)
      ? loaded.map(x => (typeof x === 'string' ? x : (x.model || x.id || x.key || ''))).filter(Boolean)
      : [];
    const selectedFromApi = (info && info.selected_model) || selected;
    const sel = selectedFromApi || selected || (names[0] || '');
    const match = !sel || names.some(n => n === sel || n.includes(sel) || sel.includes(n));
    if (!sel) {
      setFooterModelStatus(t('model') + ': —', false);
    } else if (!names.length) {
      setFooterModelStatus(t('model') + ': ' + sel + ' (' + t('notLoaded') + ')', false);
    } else {
      setFooterModelStatus(t('model') + ': ' + sel + ' (' + (match ? t('loaded') : t('notLoaded')) + ')', !!match);
    }
    const fe = document.getElementById('footer-extra');
    if (fe) {
      const n = (modelsData.models || []).length;
      fe.textContent = n ? (n + ' ' + t('available')) : '';
    }
    setFooterContext(_lastPromptTokens, _modelContextLimit);
  } catch (e) {
    setFooterModelStatus(t('model') + ': ?', false);
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
  streamingEnabled = ch.streaming !== false;
  if (!streamingEnabled) resetTps(true);
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
  if (langSel) {
    const langs = window.__RESPONSE_LANGS || {};
    if (Object.keys(langs).length && langSel.options.length < 3) {
      langSel.innerHTML = '';
      Object.keys(langs).forEach(k => {
        const o = document.createElement('option');
        o.value = k; o.textContent = langs[k];
        langSel.appendChild(o);
      });
    }
    langSel.value = ch.response_language || 'en';
    if (![...langSel.options].some(o => o.value === langSel.value)) langSel.value = 'en';
  }
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
  if (data.error || !data.reachable) setFooterModelStatus(t('model') + ': ' + (data.error || t('offline')), false);
  else if (modelLabel && modelLabel !== '(auto)') setFooterModelStatus(t('model') + ': ' + modelLabel, null);
  const extra = document.getElementById('footer-extra');
  if (extra) {
    const n = (data.models || []).length;
    extra.textContent = (data.reachable && n) ? (n + ' ' + t('available')) : '';
  }
  const selM = (document.getElementById('s-model') || {}).value || '';
  for (const m of (data.models || [])) {
    const lim = m.loaded_context_length || m.context_length || m.max_context_length || m.context;
    if (!lim) continue;
    if (selM && (m.id === selM || String(m.id||'').includes(selM))) { _modelContextLimit = Number(lim); break; }
    if (_modelContextLimit == null) _modelContextLimit = Number(lim);
  }
  setFooterContext(_lastPromptTokens, _modelContextLimit);
  sel.onchange = () => {
    markSettingsDirty();
    const fe = document.getElementById('footer-extra');
    if (fe) fe.textContent = 'model: ' + (sel.value || '(auto)');
  };
}

async function loadComponents() {
  const data = await api('/api/components');
  if (data.error) { toast('Components: ' + data.error, true); console.error(data); }
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
  if (ui && ui.values && ui.values.ui_locale) applyUiLocale(ui.values.ui_locale);
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
  if (!fields.length) html += '<div class="empty">No extra settings</div>';
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
  if (!fields.length) html += '<div class="empty">No settings</div>';
  else fields.forEach(f => {
    const val = draft.values[f.key] !== undefined ? draft.values[f.key] : f.default;
    if (f.type === 'bool') {
      html += `<div class="field field-check"><label class="check-line"><input type="checkbox" class="soft-check" data-fk="${esc(f.key)}" ${val ? 'checked' : ''}/><span>${esc(f.label)}</span>`;
      if (f.description) html += `<span class="info-tip" tabindex="0" data-tip="${esc(f.description)}">i</span>`;
      html += `</label></div>`;
    } else if (f.type === 'select' && f.options && f.options.length) {
      html += `<div class="field"><label class="lbl">${esc(f.label)}`;
      if (f.description) html += `<span class="info-tip" tabindex="0" data-tip="${esc(f.description)}">i</span>`;
      html += `</label><select data-fk="${esc(f.key)}" class="input-std">`;
      f.options.forEach(o => {
        const ov = o.value != null ? o.value : o;
        const ol = o.label != null ? o.label : String(ov);
        html += `<option value="${esc(ov)}" ${String(val) === String(ov) ? 'selected' : ''}>${esc(ol)}</option>`;
      });
      html += `</select></div>`;
    } else {
      html += `<div class="field"><label class="lbl">${esc(f.label)}`;
      if (f.description) html += `<span class="info-tip" tabindex="0" data-tip="${esc(f.description)}">i</span>`;
      html += `</label>`;
      html += `<input class="input-std" type="${f.type === 'int' || f.type === 'float' ? 'number' : 'text'}" data-fk="${esc(f.key)}" value="${esc(val ?? '')}"/>`;
      html += `</div>`;
    }
  });
  panel.innerHTML = html;
  if (!draftPlugins[id]) draftPlugins[id] = { values: {} };
  panel.querySelectorAll('[data-fk]').forEach(inp => {
    const ev = (inp.type === 'checkbox' || inp.tagName === 'SELECT') ? 'change' : 'input';
    inp.addEventListener(ev, () => {
      let v;
      if (inp.type === 'checkbox') v = inp.checked;
      else if (inp.type === 'number') v = Number(inp.value);
      else v = inp.value;
      draftPlugins[id].values[inp.dataset.fk] = v;
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
      d.innerHTML = `<span>${esc(t.name)}</span><button class="secondary" data-id="${esc(t.id)}">Reset</button>`;
      d.querySelector('button').onclick = async () => {
        if (!confirm('Reset settings for ' + t.name + '?')) return;
        await api('/api/settings/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'tool', id: t.id }) });
        draftTools[t.id] = undefined;
        await loadComponents();
        toast('Reset: ' + t.name);
      };
      tl.appendChild(d);
    });
  }
  if (pl) {
    pl.innerHTML = '';
    (componentsCache.plugins || []).forEach(p => {
      const d = document.createElement('div');
      d.className = 'reset-item';
      d.innerHTML = `<span>${esc(p.name)}</span><button class="secondary" data-id="${esc(p.id)}">Reset</button>`;
      d.querySelector('button').onclick = async () => {
        if (!confirm('Reset settings for ' + p.name + '?')) return;
        await api('/api/settings/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plugin', id: p.id }) });
        draftPlugins[p.id] = undefined;
        await loadComponents();
        toast('Reset: ' + p.name);
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
  setFooterModelStatus(t('model') + ': ' + modelName, null); const _fe=document.getElementById('footer-extra'); if(_fe && !(_fe.textContent||'').includes('available')) {/* keep available count from refresh */} 
  // apply plugin footer visibility immediately
  const uiDraft = draftPlugins['plugin_web_ui'];
  if (uiDraft && uiDraft.values && uiDraft.values.show_footer === false) {
    document.getElementById('app-footer').classList.add('hidden');
  } else {
    document.getElementById('app-footer').classList.remove('hidden');
  }
  clearSettingsDirty();
  const loc = draftPlugins['plugin_web_ui']?.values?.ui_locale || 'en';
  applyUiLocale(loc);
  toast(t('save'));
  await refreshTree();
  await refreshModelsSelect(apiBody.model);
}

document.getElementById('btn-settings-save').onclick = saveAllSettings;
document.getElementById('btn-settings-cancel').onclick = async () => {
  if (!settingsDirty) return;
  if (!confirm('Discard unsaved changes?')) return;
  draftTools = {}; draftPlugins = {};
  await loadSettings();
(async () => {
  try {
    const d = await api('/api/languages');
    if (d && d.languages) {
      window.__RESPONSE_LANGS = d.languages;
      const langSel = document.getElementById('s-chat-lang');
      if (langSel && langSel.options.length < 5) {
        const cur = langSel.value || 'en';
        langSel.innerHTML = '';
        Object.keys(d.languages).forEach(k => {
          const o = document.createElement('option');
          o.value = k; o.textContent = d.languages[k];
          langSel.appendChild(o);
        });
        langSel.value = cur;
      }
    }
  } catch (e) {}
})();

(async () => {
  try {
    const info = await api('/api/server/info');
    window.__SERVER_INFO = info;
    if (info && info.server_mode) {
      const top = document.getElementById('top-workspace');
      if (top && !document.getElementById('server-badge')) {
        const b = document.createElement('span');
        b.id = 'server-badge';
        b.className = 'server-badge';
        b.textContent = 'SERVER · ' + (info.lan_ip || '');
        top.parentElement && top.parentElement.appendChild(b);
      }
      const pick = document.getElementById('btn-pick-ws');
      if (pick) {
        pick.title = 'In server mode, enter the host path manually';
      }
    }
  } catch (e) {}
})();
  toast('Changes discarded');
};
document.getElementById('btn-factory-reset').onclick = async () => {
  if (!confirm('Reset ALL settings to factory defaults?')) return;
  if (!confirm('Are you sure? This cannot be undone for local JSON settings.')) return;
  await api('/api/settings/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scope: 'all' }) });
  draftTools = {}; draftPlugins = {};
  await loadSettings();
(async () => {
  try {
    const d = await api('/api/languages');
    if (d && d.languages) {
      window.__RESPONSE_LANGS = d.languages;
      const langSel = document.getElementById('s-chat-lang');
      if (langSel && langSel.options.length < 5) {
        const cur = langSel.value || 'en';
        langSel.innerHTML = '';
        Object.keys(d.languages).forEach(k => {
          const o = document.createElement('option');
          o.value = k; o.textContent = d.languages[k];
          langSel.appendChild(o);
        });
        langSel.value = cur;
      }
    }
  } catch (e) {}
})();

(async () => {
  try {
    const info = await api('/api/server/info');
    window.__SERVER_INFO = info;
    if (info && info.server_mode) {
      const top = document.getElementById('top-workspace');
      if (top && !document.getElementById('server-badge')) {
        const b = document.createElement('span');
        b.id = 'server-badge';
        b.className = 'server-badge';
        b.textContent = 'SERVER · ' + (info.lan_ip || '');
        top.parentElement && top.parentElement.appendChild(b);
      }
      const pick = document.getElementById('btn-pick-ws');
      if (pick) {
        pick.title = 'In server mode, enter the host path manually';
      }
    }
  } catch (e) {}
})();
  toast('Factory defaults applied');
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
  if (settingsDirty && !confirm('Settings are not saved. Leave anyway?')) return;
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
(async () => {
  try {
    const d = await api('/api/languages');
    if (d && d.languages) {
      window.__RESPONSE_LANGS = d.languages;
      const langSel = document.getElementById('s-chat-lang');
      if (langSel && langSel.options.length < 5) {
        const cur = langSel.value || 'en';
        langSel.innerHTML = '';
        Object.keys(d.languages).forEach(k => {
          const o = document.createElement('option');
          o.value = k; o.textContent = d.languages[k];
          langSel.appendChild(o);
        });
        langSel.value = cur;
      }
    }
  } catch (e) {}
})();

(async () => {
  try {
    const info = await api('/api/server/info');
    window.__SERVER_INFO = info;
    if (info && info.server_mode) {
      const top = document.getElementById('top-workspace');
      if (top && !document.getElementById('server-badge')) {
        const b = document.createElement('span');
        b.id = 'server-badge';
        b.className = 'server-badge';
        b.textContent = 'SERVER · ' + (info.lan_ip || '');
        top.parentElement && top.parentElement.appendChild(b);
      }
      const pick = document.getElementById('btn-pick-ws');
      if (pick) {
        pick.title = 'In server mode, enter the host path manually';
      }
    }
  } catch (e) {}
})();
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
try { applyChatContextFooter(); } catch (_) {}
if (!chats.length) newChat(true);
else { activeChatId = chats[chats.length - 1].id; renderChatList(); renderMessages(); }
clearEditor();
refreshTree();
loadSettings();
(async () => {
  try {
    const d = await api('/api/languages');
    if (d && d.languages) {
      window.__RESPONSE_LANGS = d.languages;
      const langSel = document.getElementById('s-chat-lang');
      if (langSel && langSel.options.length < 5) {
        const cur = langSel.value || 'en';
        langSel.innerHTML = '';
        Object.keys(d.languages).forEach(k => {
          const o = document.createElement('option');
          o.value = k; o.textContent = d.languages[k];
          langSel.appendChild(o);
        });
        langSel.value = cur;
      }
    }
  } catch (e) {}
})();

(async () => {
  try {
    const info = await api('/api/server/info');
    window.__SERVER_INFO = info;
    if (info && info.server_mode) {
      const top = document.getElementById('top-workspace');
      if (top && !document.getElementById('server-badge')) {
        const b = document.createElement('span');
        b.id = 'server-badge';
        b.className = 'server-badge';
        b.textContent = 'SERVER · ' + (info.lan_ip || '');
        top.parentElement && top.parentElement.appendChild(b);
      }
      const pick = document.getElementById('btn-pick-ws');
      if (pick) {
        pick.title = 'In server mode, enter the host path manually';
      }
    }
  } catch (e) {}
})();
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

document.getElementById('msgs')?.addEventListener('click', (e) => {
  const a = e.target.closest('a.file-ref');
  if (!a) return;
  e.preventDefault();
  const path = a.dataset.path;
  if (!path) return;
  // expand tree to path
  const parts = path.split('/');
  let acc = '';
  parts.forEach((p, i) => {
    if (i < parts.length - 1) {
      acc = acc ? acc + '/' + p : p;
      expanded.add(acc);
    }
  });
  renderTree();
  openFile(path);
});

(function setupAttach() {
  const btn = document.getElementById('btn-attach');
  const chips = document.getElementById('attach-chips');
  if (!btn) return;
  // remove any duplicate inject near New chat
  document.querySelectorAll('#chat-panel h3 #btn-attach').forEach(el => {
    if (el !== btn) el.remove();
  });
  btn.onclick = (e) => {
    e.stopPropagation();
    showAttachMenu(btn);
  };
  const panel = document.getElementById('chat-panel');
  if (panel && !panel.dataset.dropBound) {
    panel.dataset.dropBound = '1';
    panel.addEventListener('dragover', (ev) => { ev.preventDefault(); panel.classList.add('drag-over'); });
    panel.addEventListener('dragleave', () => panel.classList.remove('drag-over'));
    panel.addEventListener('drop', async (ev) => {
      ev.preventDefault();
      panel.classList.remove('drag-over');
      const files = [...(ev.dataTransfer.files || [])];
      for (const f of files) {
        const dataUrl = await new Promise((res) => {
          const r = new FileReader();
          r.onload = () => res(r.result);
          r.readAsDataURL(f);
        });
        const raw = (dataUrl || '').split(',')[1] || '';
        const r = await api('/api/attachments/import', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: f.name, content_base64: raw }),
        });
        if (r.path) addAttachment(r.path, true);
        else if (r.error) toast(r.error, true);
      }
    });
  }
})();
function addAttachment(path, exists) {
  if (chatAttachments.some(a => a.path === path)) return;
  chatAttachments.push({ path, exists: exists !== false });
  renderAttachChips();
}
function renderAttachChips() {
  const el = document.getElementById('attach-chips');
  if (!el) return;
  el.innerHTML = '';
  chatAttachments.forEach((a, i) => {
    const d = document.createElement('span');
    d.className = 'attach-chip ' + (a.exists ? 'ok' : 'bad');
    d.innerHTML = esc(a.path) + ' <b data-i="'+i+'">×</b>';
    d.querySelector('b').onclick = () => { chatAttachments.splice(i, 1); renderAttachChips(); };
    el.appendChild(d);
  });
}
function showAttachMenu(anchor) {
  const ctx = document.getElementById('ctx');
  if (!ctx) return;
  const r = anchor.getBoundingClientRect();
  ctx.style.display = 'block';
  ctx.style.minWidth = Math.max(280, r.width + 120) + 'px';
  ctx.style.maxWidth = Math.min(420, window.innerWidth - 16) + 'px';
  ctx.innerHTML = '<input id="attach-q" placeholder="'+t('attachSearch')+'" style="width:100%;margin-bottom:4px;box-sizing:border-box"/><div id="attach-hits" class="attach-hits"></div>';
  // position after content so we can open upward if near bottom
  const menuH = Math.min(320, window.innerHeight * 0.45);
  let left = r.left;
  let top = r.bottom + 4;
  // prefer open upward from composer
  if (r.bottom + menuH + 8 > window.innerHeight) {
    top = Math.max(8, r.top - menuH - 4);
  }
  if (left + 300 > window.innerWidth) left = Math.max(8, window.innerWidth - 308);
  ctx.style.left = left + 'px';
  ctx.style.top = top + 'px';
  ctx.style.maxHeight = menuH + 'px';
  ctx.style.overflow = 'hidden';
  const q = document.getElementById('attach-q');
  const hits = document.getElementById('attach-hits');
  hits.style.maxHeight = (menuH - 40) + 'px';
  hits.style.overflowY = 'auto';
  const search = async () => {
    const data = await api('/api/fs/search?q=' + encodeURIComponent(q.value || ''));
    hits.innerHTML = '';
    (data.hits || []).forEach(h => {
      const b = document.createElement('button');
      b.textContent = h.path;
      b.title = h.path;
      b.onclick = () => { addAttachment(h.path, true); ctx.style.display = 'none'; };
      hits.appendChild(b);
    });
    if (!(data.hits || []).length) {
      const empty = document.createElement('div');
      empty.style.cssText = 'padding:8px 12px;color:var(--muted);font-size:12px';
      empty.textContent = (q.value || '').trim() ? t('noMatches') : t('typeToSearch');
      hits.appendChild(empty);
    }
  };
  q.oninput = () => { clearTimeout(q._t); q._t = setTimeout(search, 200); };
  q.onclick = (ev) => ev.stopPropagation();
  hits.onclick = (ev) => ev.stopPropagation();
  q.focus();
  search();
  const hide = (ev) => {
    if (ctx.contains(ev.target) || anchor.contains(ev.target)) return;
    ctx.style.display = 'none';
    document.removeEventListener('click', hide);
  };
  setTimeout(() => document.addEventListener('click', hide), 0);
}

// Model loaded indicator in footer
startTpsTimer();
setInterval(() => { if (!running) refreshModelFooter().catch(() => {}); }, 8000);
setInterval(() => { setFooterContext(_lastPromptTokens, _modelContextLimit); }, 5000);
document.addEventListener('DOMContentLoaded', () => { setTimeout(() => refreshModelFooter().catch(() => {}), 500); });


async function shutdownUi() {
  if (!confirm(uiLocale === 'ru' ? 'Остановить Web UI и закрыть страницу?' : 'Stop Web UI server and close this page?')) return;
  try {
    await api('/api/shutdown', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  } catch (_) {}
  try { window.close(); } catch (_) {}
  document.body.innerHTML = '<div style="padding:40px;font-family:system-ui;color:#c9d1d9;background:#0d1117;min-height:100vh">Kerniq UI stopped. You can close this tab.</div>';
}

document.addEventListener('DOMContentLoaded', () => {
  const stop = document.getElementById('btn-stop-ui');
  if (stop) stop.onclick = () => shutdownUi();
});
