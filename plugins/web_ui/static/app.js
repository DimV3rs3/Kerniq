
const UI_I18N = {
  en: {
    explorer: 'Explorer', chat: 'Chat', newChat: 'New', settings: 'Settings',
    save: 'Save', saved: 'Saved', cancel: 'Cancel', send: 'Send', stop: 'Stop',
    openFile: 'Open a file…', ready: 'Ready', done: 'Done', error: 'Error',
    stopping: 'Stopping…', stopped: 'Stopped',
    processing: 'Processing prompt…', thinking: 'Thinking…', generating: 'Generating…',
    aggHint: 'Merge consecutive collapsible tool calls into one chat block',
    aggLabel: 'Merge tool calls when possible',
    autoApprove: 'Auto-approve risk up to',
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
    notLoaded: 'not loaded', loaded: 'loaded', loading: 'loading…', offline: 'offline',
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
    planTitle: 'Plan',
    planArchive: 'Archive',
    modePlan: 'Plan',
    modeAct: 'Act',
    autoAct: 'After Plan, run Act automatically',
    modeAuto: 'Auto Plan / Act',
    planCompleted: 'Completed',
    actDivider: 'Act',
    contextCompacted: 'Context compacted. Older turns were replaced by a memory note.',
    contextTrimmed: 'Context trimmed. Older turns were dropped. The latest turns were kept.',
    splitModels: 'Different model for Act',
    actModel: 'Act model',
    composePlan: 'Build a plan',
    loopRetries: 'Loop retries',
    providerDesc: 'Description',
    packAuto: 'Auto-accept every tool in this pack',
    packMerge: 'Merge calls for every tool in this pack',
    fromProject: 'From the project',
    fromOutside: 'From outside',
    scrollDown: 'Scroll to bottom',
    tempTip: 'Higher temperature makes replies more varied and less predictable. Lower keeps them closer to the most likely wording. 0.7 is the default.',
    providersEmpty: 'Provider list did not load.',
    toolsEmpty: 'No tools discovered.',
    pluginsEmpty: 'No plugins discovered.',
    attachBlocked: 'Photos, video, audio, and archives cannot be attached.',
    fileDialogFailed: 'File dialog failed.',
    settingsFailed: 'Settings did not load.',

    selectTool: 'Select a tool', selectPlugin: 'Select a plugin',
    noMatches: 'No matches', typeToSearch: 'Type to search project files',
    seconds: 'seconds', minutes: 'minutes', hours: 'hours',
    groupOutput: 'Reply',
    groupSend: 'Sending',
    groupChatTools: 'Chat tools',
    groupPlan: 'Plan and Act',
    groupSafety: 'Safety and language',
    approveAll: 'all — no prompts',
    pluginOn: 'on',
    pluginOff: 'off',
    pluginHidden: 'hidden',
    showHiddenPlugins: 'Show hidden plugins',
    langPacks: 'Language packs',
    fromProjectHint: 'Search files in the workspace',
    fromOutsideHint: 'Pick files from your computer',
    tabInterface: 'Interface',
    interfaceSettings: 'Interface settings',
    prefsLocal: 'These options apply immediately and are stored in this browser.',
    groupMotion: 'Motion',
    animations: 'Animations',
    animationsTip: 'Transitions and motion effects. "Follow system" respects the reduce-motion setting of your operating system.',
    motionOn: 'On',
    motionAuto: 'Follow system',
    motionOff: 'Off',
    groupEditor: 'Editor',
    syntaxHl: 'Syntax highlighting',
    syntaxHlTip: 'Colour code in the editor. Turn it off for very large files.',
    runNote: 'The agent is running. Settings are read-only until it finishes.',
    stopAgent: 'Stop agent',
    groupReasoning: 'Reasoning',
    autoThink: 'Auto-expand reasoning',
    autoThinkTip: 'Open the reasoning block while the model is thinking and fold it again when it finishes. A block you open or close yourself is left alone.',
    groupLanguage: 'Language',
    uiLanguage: 'Interface language',
    langPacksBtn: 'Language packs…',
    groupStatus: 'Status bar',
    showFooter: 'Show status footer',
    agentLabel: 'Agent',
    chats: 'Chats',
    newChatLong: 'New chat',
    editorLabel: 'Editor',
    modeToAgent: 'Switch to agent mode',
    modeToEditor: 'Switch to editor mode',
    groupLayout: 'Layout',
    workspaceLayout: 'Workspace layout',
    layoutTip: 'Agent only hides the editor: chats on the left, the conversation in the centre.',
    layoutEditorOpt: 'Editor + chat',
    layoutAgentOpt: 'Agent only',
  },
};
let autoThink = false;     // open reasoning while the model thinks, fold it when it is done
try { autoThink = localStorage.getItem('kerniq_auto_think') === '1'; } catch (e) {}
let layoutMode = 'editor';
try { layoutMode = localStorage.getItem('kerniq_layout') === 'agent' ? 'agent' : 'editor'; } catch (e) {}
let uiLocale = 'en';
let langPacks = {};
/* Counted phrases: a pack may give one form per plural category, separated by "|"
   ("файл прочитан|файла прочитано|файлов прочитано"). The form is chosen with Intl.PluralRules
   for the pack's language; a translation without "|" is used as is. */
let _pluralRules = null, _pluralLocale = '';
function pluralFormIndex(n, count) {
  try {
    if (!_pluralRules || _pluralLocale !== uiLocale) { _pluralRules = new Intl.PluralRules(uiLocale); _pluralLocale = uiLocale; }
  } catch (_) {
    _pluralRules = new Intl.PluralRules('en'); _pluralLocale = uiLocale;
  }
  const used = _pluralRules.resolvedOptions().pluralCategories;
  const order = ['zero', 'one', 'two', 'few', 'many', 'other'].filter(c => used.indexOf(c) >= 0);
  return Math.min(Math.max(order.indexOf(_pluralRules.select(n)), 0), count - 1);
}
function translatePlural(one, other, n) {
  const base = translate(n === 1 ? one : other);
  if (typeof base !== 'string' || base.indexOf('|') < 0) return base;
  const forms = base.split('|').map(s => s.trim());
  return forms[pluralFormIndex(n, forms.length)];
}
function translate(text) {
  const source = String(text == null ? '' : text);
  if (!source || uiLocale === 'en') return source;
  const pack = langPacks[uiLocale];
  const table = pack && pack.strings;
  if (table && table[source]) return table[source];
  return source;
}
function t(key) {
  return translate((UI_I18N.en && UI_I18N.en[key]) || key);
}
let providerCatalog = [];
let agentMode = 'act';
let modeAuto = true;
let liveModel = '';
let runSawPlan = false;
try { agentMode = localStorage.getItem('kerniq_agent_mode') || 'act'; } catch (e) { agentMode = 'act'; }
if (agentMode !== 'plan' && agentMode !== 'act') agentMode = 'act';
function applyUiLocale(locale) {
  uiLocale = (locale && locale !== 'en' && langPacks[locale]) ? locale : 'en';
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
  document.querySelectorAll('[data-i18n-tip]').forEach(el => {
    const k = el.getAttribute('data-i18n-tip');
    if (k) el.setAttribute('data-tip', t(k));
  });
  // settings tabs
  const tabMap = {
    agent: 'tabAgent', api: 'tabApi', prompt: 'tabPrompt', chat: 'tabChat',
    tools: 'tabTools', plugins: 'tabPlugins', reset: 'tabReset', interface: 'tabInterface',
  };
  document.querySelectorAll('.stab').forEach(el => {
    const k = tabMap[el.dataset.tab];
    if (k) el.textContent = t(k);
  });
  const ex = document.querySelector('#explorer h3 .grow');
  if (ex) ex.textContent = t(layoutMode === 'agent' ? 'chats' : 'explorer');
  if (typeof refreshLayoutLabels === 'function') refreshLayoutLabels();
  if (typeof refreshInterfaceControls === 'function') refreshInterfaceControls();
  refreshChatHeading();
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
  if (und) { und.title = t('undo'); und.setAttribute('aria-label', t('undo')); }
  const red = document.getElementById('btn-redo');
  if (red) { red.title = t('redo'); red.setAttribute('aria-label', t('redo')); }
  const clo = document.getElementById('btn-close-tab');
  if (clo) clo.textContent = t('close');
  const sav = document.getElementById('btn-save');
  if (sav) { sav.title = t('save'); sav.setAttribute('aria-label', t('save')); }
  const br = document.getElementById('btn-pick-ws');
  if (br) br.textContent = t('browse');
  const rm = document.getElementById('btn-refresh-models');
  if (rm) rm.textContent = t('refresh');
  const fr = document.getElementById('btn-factory-reset');
  if (fr) fr.textContent = t('factoryReset');
  const su = document.getElementById('btn-stop-ui');
  if (su) su.textContent = '⏹ ' + t('stopUi');
  const mp = document.getElementById('mode-plan');
  if (mp) mp.textContent = t('modePlan');
  const ma = document.getElementById('mode-act');
  if (ma) ma.textContent = t('modeAct');
  if (typeof renderProviderFields === 'function' && providerCatalog.length) {
    renderProviderFields(collectProviderDraft());
  }
  if (typeof renderPlan === 'function') renderPlan();
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
let sendLock = false;
let sendAbort = false;
function setRunLock(on) {
  document.body.classList.toggle('run-locked', !!on);
  if (typeof applyModeSwitch === 'function') applyModeSwitch();
  document.querySelectorAll('#view-settings input, #view-settings select, #view-settings textarea, #view-settings button').forEach(el => {
    if (el.id === 'btn-stop-ui' || el.closest('nav') || el.hasAttribute('data-keep-unlocked') ||
        el.classList.contains('twist') || el.closest('#tab-interface')) return;
    if (on) {
      if (el.dataset.lockPrev == null) el.dataset.lockPrev = el.disabled ? '1' : '0';
      el.disabled = true;
    } else if (el.dataset.lockPrev != null) {
      el.disabled = el.dataset.lockPrev === '1';
      delete el.dataset.lockPrev;
    }
  });
  if (!on && typeof syncSettingLocks === 'function') syncSettingLocks();
}
let currentRunId = null;
let streamingEnabled = true;
let generatingTokens = false;
let treeData = [];
let expanded = new Set(['']);
let settingsDirty = false;
let settingsHydrating = false;
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
let chatAttachments = [];
let mentionOpen = false;
let mentionStart = -1;


async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const t = await r.text();
  try { return JSON.parse(t); } catch { return { error: t }; }
}
function uid() { return Math.random().toString(36).slice(2) + Date.now().toString(36); }
function encodePath(p) {
  return String(p).split('/').map(encodeURIComponent).join('/');
}
/* ---------- markdown ----------
   Block parser + inline parser. Everything user-visible goes through esc(),
   links are scheme-checked, and renderMarkdown() never throws: on any
   internal error it falls back to escaped plain text. */
const MD_MAX_DEPTH = 6;
const MD_BULLET = '[-*+•·▪◦\\u2010-\\u2015\\u2212]';
const MD_LIST_RE = new RegExp('^(\\s*)(' + MD_BULLET + '|\\d{1,9}[.)])\\s+(.*)$');
const MD_HR_RE = /^\s{0,3}([-*_\u2010-\u2015\u2212])(?:\s*\1){2,}\s*$/;
const MD_HEAD_RE = /^\s{0,3}(#{1,6})\s+(.*?)(?:\s+#+)?\s*$/;
const MD_FENCE_RE = /^(\s{0,3})(`{3,}|~{3,})\s*([^\s`]*)[^`]*$/;
const MD_TSEP_RE = /^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$/;
const MD_QUOTE_RE = /^\s{0,3}>/;

function mdSafeUrl(u) {
  const s = String(u || '').trim();
  return /^(?:https?:\/\/|mailto:|#|\/|\.\.?\/)/i.test(s) ? s : '';
}

const PRISM_ALIAS = {
  js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript', node: 'javascript',
  ts: 'typescript', tsx: 'typescript',
  py: 'python', python3: 'python',
  sh: 'bash', shell: 'bash', zsh: 'bash', console: 'bash',
  ps1: 'powershell', pwsh: 'powershell',
  html: 'markup', xml: 'markup', svg: 'markup', vue: 'markup',
  yml: 'yaml', md: 'markdown', jsonc: 'json', json5: 'json',
  'c++': 'cpp', cxx: 'cpp', cc: 'cpp', 'c#': 'csharp', cs: 'csharp',
  rs: 'rust', golang: 'go', scss: 'css', less: 'css',
};
function highlightCode(text, lang) {
  const src = String(text == null ? '' : text);
  let l = String(lang || '').toLowerCase();
  l = PRISM_ALIAS[l] || l;
  try {
    const P = window.Prism;
    if (P && P.languages && P.languages[l] && src.length < 200000 && !/[^\n]{4000}/.test(src)) {
      return P.highlight(src, P.languages[l], l);
    }
  } catch (_) { /* fall through to plain text */ }
  return esc(src);
}

function mdInlineEmph(s) {
  s = s.replace(/\*\*\*(?=\S)([\s\S]*?\S)\*\*\*/g, '<strong><em>$1</em></strong>');
  s = s.replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(^|[^\w])__(?=\S)([\s\S]*?\S)__(?!\w)/g, '$1<strong>$2</strong>');
  s = s.replace(/~~(?=\S)([\s\S]*?\S)~~/g, '<del>$1</del>');
  s = s.replace(/(^|[^\w*])\*(?=[^\s*])([^*\n]*?[^\s*])\*(?!\*)/g, '$1<em>$2</em>');
  s = s.replace(/(^|[^\w])_(?=[^\s_])([^_\n]*?[^\s_])_(?!\w)/g, '$1<em>$2</em>');
  return s;
}
function mdFileRef(p) {
  const path = String(p).trim();
  return '<a href="#" class="file-ref" data-path="' + esc(path) + '">' + esc(path) + '</a>';
}
function inlineMd(src) {
  const stash = [];
  const keep = (html) => '\u0000' + (stash.push(html) - 1) + '\u0001';
  let s = String(src == null ? '' : src).replace(/[\u0000\u0001]/g, '');
  // 1. things that must not be touched by emphasis: code spans, file refs
  s = s.replace(/(`+)([\s\S]*?[^`])\1(?!`)/g, (m, ticks, body) =>
    keep('<code>' + esc(body.replace(/^ (.*) $/, '$1')) + '</code>'));
  s = s.replace(/\[\[file:([^\]]+)\]\]/g, (m, p) => keep(mdFileRef(p)));
  s = esc(s);
  // 2. links, images (shown as links), autolinks, bare urls
  s = s.replace(/!?\[([^\]\n]+)\]\(([^)\s]+)(?:\s+&quot;[^)]*&quot;)?\)/g, (m, text, url) => {
    const u = mdSafeUrl(url);
    const inner = mdInlineEmph(text);
    if (!u) return inner;
    return keep('<a href="' + u + '" target="_blank" rel="noopener noreferrer">' + inner + '</a>');
  });
  s = s.replace(/&lt;(https?:\/\/(?:(?!&gt;)\S)+)&gt;/g, (m, url) =>
    keep('<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + '</a>'));
  s = s.replace(/(^|[\s(])(https?:\/\/[^\s<]+)/g, (m, pre, url) => {
    let tail = '';
    const tm = url.match(/(?:[.,;:!?)\]]|&quot;|&#39;|&gt;|&lt;)+$/);
    if (tm) { tail = tm[0]; url = url.slice(0, url.length - tail.length); }
    if (!url) return m;
    return pre + keep('<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + '</a>') + tail;
  });
  // 3. emphasis
  s = mdInlineEmph(s);
  // 4. restore
  for (let n = 0; n < 4 && s.indexOf('\u0000') >= 0; n++) {
    s = s.replace(/\u0000(\d+)\u0001/g, (m, i) => stash[+i] != null ? stash[+i] : '');
  }
  return s;
}

function mdSplitRow(row) {
  let s = row.trim();
  if (s.startsWith('|')) s = s.slice(1);
  if (s.endsWith('|') && !s.endsWith('\\|')) s = s.slice(0, -1);
  const cells = [];
  let cur = '', inCode = false;
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (ch === '\\' && s[i + 1] === '|') { cur += '|'; i++; }
    else if (ch === '`') { inCode = !inCode; cur += ch; }
    else if (ch === '|' && !inCode) { cells.push(cur.trim()); cur = ''; }
    else cur += ch;
  }
  cells.push(cur.trim());
  return cells;
}
function mdTable(rows) {
  const list = rows.filter(r => r.trim());
  if (!list.length) return '';
  const hasSep = list.length > 1 && MD_TSEP_RE.test(list[1]) && /-/.test(list[1]);
  const align = hasSep ? mdSplitRow(list[1]).map(c => {
    const l = c.startsWith(':'), r = c.endsWith(':');
    return l && r ? 'center' : r ? 'right' : l ? 'left' : '';
  }) : [];
  const cols = Math.max.apply(null, list.map(r => mdSplitRow(r).length));
  const cell = (tag, text, idx) => {
    const a = align[idx] ? ' style="text-align:' + align[idx] + '"' : '';
    return '<' + tag + a + '>' + inlineMd(text || '') + '</' + tag + '>';
  };
  const row = (tag, r) => {
    const cells = mdSplitRow(r);
    while (cells.length < cols) cells.push('');
    return '<tr>' + cells.slice(0, cols).map((c, i) => cell(tag, c, i)).join('') + '</tr>';
  };
  let html = '<div class="table-wrap"><table class="md-table">';
  let bodyRows = list;
  if (hasSep) {
    html += '<thead>' + row('th', list[0]) + '</thead>';
    bodyRows = list.slice(2);
  }
  html += '<tbody>' + bodyRows.filter(r => !(MD_TSEP_RE.test(r) && /-/.test(r))).map(r => row('td', r)).join('') + '</tbody></table></div>';
  return html;
}
function parseFileLinks(html) {
  return html.replace(/\[\[file:([^\]]+)\]\]/g, (_, p) => mdFileRef(p));
}

function mdCodeBlock(body, lang) {
  const l = String(lang || '').toLowerCase();
  const lines = body.split('\n');
  // models often wrap a plain table in a code fence: render it as a table
  if ((!l || l === 'md' || l === 'markdown' || l === 'text' || l === 'table') &&
      lines.some(x => MD_TSEP_RE.test(x) && /-/.test(x) && x.indexOf('|') >= 0) &&
      lines.every(x => !x.trim() || /^\s*\|.*\|\s*$/.test(x))) {
    return mdTable(lines);
  }
  return '<div class="code-block"><div class="code-head"><span class="code-lang">' + esc(lang || '') + '</span>' +
    '<button type="button" class="copy-btn" data-copy>' + esc(translate('Copy')) + '</button></div>' +
    '<pre class="md-code"><code>' + highlightCode(body, lang) + '</code></pre></div>';
}

function mdIsBlockStart(L) {
  return MD_FENCE_RE.test(L) || MD_HEAD_RE.test(L) || MD_HR_RE.test(L) ||
    MD_QUOTE_RE.test(L) || MD_LIST_RE.test(L) || /^\s*\|.+\|/.test(L);
}
const mdTabs = (L) => L.replace(/^\t+/, (m) => '    '.repeat(m.length));
function mdMinIndent(lines) {
  let min = Infinity;
  for (const L of lines) {
    if (!L.trim()) continue;
    const n = L.match(/^ */)[0].length;
    if (n < min) min = n;
  }
  return min === Infinity ? 0 : min;
}

function mdList(lines, start, depth) {
  const first = mdTabs(lines[start]).match(MD_LIST_RE);
  const base = first[1].length;
  const ordered = /\d/.test(first[2][0]);
  const startNum = ordered ? parseInt(first[2], 10) : 1;
  const items = [];
  let cur = null, inFence = false, fenceCh = '', fenceLen = 0;
  let j = start;
  while (j < lines.length) {
    const L = mdTabs(lines[j]);
    if (inFence) {
      cur.body.push(L);
      const cm = L.match(/^\s*(`{3,}|~{3,})\s*$/);
      if (cm && cm[1][0] === fenceCh && cm[1].length >= fenceLen) inFence = false;
      j++; continue;
    }
    if (!L.trim()) {
      let k = j + 1;
      while (k < lines.length && !lines[k].trim()) k++;
      if (k >= lines.length) break;
      const N = mdTabs(lines[k]);
      const nm = N.match(MD_LIST_RE);
      const nIndent = N.match(/^ */)[0].length;
      const sameKind = nm && (/\d/.test(nm[2][0]) === ordered);
      if (nIndent > base + 1 || (sameKind && nIndent <= base + 1 && nIndent >= base)) {
        if (cur) cur.body.push('');
        j++; continue;
      }
      break;
    }
    const m = L.match(MD_LIST_RE);
    const indent = L.match(/^ */)[0].length;
    if (m && indent <= base + 1) {
      if (/\d/.test(m[2][0]) !== ordered) break;
      cur = { text: m[3], body: [] };
      items.push(cur);
      j++; continue;
    }
    if (!cur) break;
    if (indent > base + 1) {
      const fm = L.match(/^\s*(`{3,}|~{3,})/);
      if (fm) { inFence = true; fenceCh = fm[1][0]; fenceLen = fm[1].length; }
      cur.body.push(L);
      j++; continue;
    }
    // un-indented, non-item line: lazy continuation unless it starts a block
    const prevBlank = cur.body.length && !cur.body[cur.body.length - 1].trim();
    if (prevBlank || mdIsBlockStart(L)) break;
    cur.body.push('  ' + L.trim());
    j++;
  }
  const tag = ordered ? 'ol' : 'ul';
  let html = '<' + tag + (ordered && startNum !== 1 ? ' start="' + startNum + '"' : '') + '>';
  for (const it of items) {
    let text = it.text, cls = '';
    const task = text.match(/^\[( |x|X)\]\s+/);
    if (task) {
      cls = ' class="task"';
      text = '\u0003' + (task[1] === ' ' ? 'todo' : 'done') + '\u0003' + text.slice(task[0].length);
    }
    const bodyLines = it.body.slice();
    const cut = mdMinIndent(bodyLines);
    const dedented = bodyLines.map(x => x.slice(Math.min(cut, x.match(/^ */)[0].length)));
    let inner = mdBlocks([text].concat(dedented), depth + 1);
    inner = inner.replace(/^<p>([\s\S]*?)<\/p>/, '$1');
    inner = inner.replace(/\u0003(todo|done)\u0003/, '<span class="task-box $1" aria-hidden="true"></span>');
    html += '<li' + cls + '>' + inner + '</li>';
  }
  return { html: html + '</' + tag + '>', next: j };
}

function mdBlocks(lines, depth) {
  if (depth > MD_MAX_DEPTH) {
    return '<p>' + lines.map(inlineMd).join('<br/>') + '</p>';
  }
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    // fenced code (unclosed fences run to the end: friendly to streaming)
    const fm = line.match(MD_FENCE_RE);
    if (fm) {
      const indent = fm[1].length, ch = fm[2][0], len = fm[2].length, lang = fm[3] || '';
      const buf = [];
      i++;
      while (i < lines.length) {
        const cm = lines[i].match(/^\s{0,3}(`{3,}|~{3,})\s*$/);
        if (cm && cm[1][0] === ch && cm[1].length >= len) { i++; break; }
        buf.push(indent ? lines[i].replace(new RegExp('^ {0,' + indent + '}'), '') : lines[i]);
        i++;
      }
      out.push(mdCodeBlock(buf.join('\n'), lang));
      continue;
    }
    // horizontal rule (before lists: "- - -", "***")
    if (MD_HR_RE.test(line)) { out.push('<hr/>'); i++; continue; }
    // heading
    const hm = line.match(MD_HEAD_RE);
    if (hm) {
      const lvl = Math.min(hm[1].length + 2, 6);
      out.push('<h' + lvl + '>' + inlineMd(hm[2]) + '</h' + lvl + '>');
      i++; continue;
    }
    // table
    const next = lines[i + 1];
    if (line.indexOf('|') >= 0 && next !== undefined && MD_TSEP_RE.test(next) && /-/.test(next) && next.indexOf('|') >= 0 ||
        /^\s*\|.+\|/.test(line)) {
      const buf = [];
      while (i < lines.length && lines[i].trim() && lines[i].indexOf('|') >= 0) { buf.push(lines[i]); i++; }
      out.push(mdTable(buf));
      continue;
    }
    // blockquote
    if (MD_QUOTE_RE.test(line)) {
      const buf = [];
      while (i < lines.length && MD_QUOTE_RE.test(lines[i])) { buf.push(lines[i].replace(/^\s{0,3}>\s?/, '')); i++; }
      out.push('<blockquote>' + mdBlocks(buf, depth + 1) + '</blockquote>');
      continue;
    }
    // lists (nested, ordered, tasks)
    if (MD_LIST_RE.test(mdTabs(line))) {
      const r = mdList(lines, i, depth);
      out.push(r.html);
      i = Math.max(r.next, i + 1);
      continue;
    }
    // paragraph
    const para = [lines[i]];
    i++;
    while (i < lines.length && lines[i].trim() && !mdIsBlockStart(lines[i])) { para.push(lines[i]); i++; }
    out.push('<p>' + para.map(l => inlineMd(l.replace(/\s+$/, ''))).join('<br/>') + '</p>');
  }
  return out.join('\n');
}

function renderMarkdown(text) {
  const src = String(text == null ? '' : text);
  try {
    const raw = src.replace(/\r\n?/g, '\n').replace(/\u00a0/g, ' ');
    return mdBlocks(raw.split('\n'), 0);
  } catch (err) {
    try { console.error('markdown render failed:', err); } catch (_) {}
    return '<p style="white-space:pre-wrap">' + esc(src) + '</p>';
  }
}


/* ---------- syntax highlight (Prism) ---------- */
function langFromPath(path) {
  const name = String(path || '').split(/[\\/]/).pop().toLowerCase();
  if (name === '.env' || name.startsWith('.env.')) return 'bash';
  if (name === 'dockerfile' || name === 'makefile') return 'bash';
  const ext = name.indexOf('.') >= 0 ? name.split('.').pop() : '';
  const map = {
    py: 'python', pyw: 'python',
    js: 'javascript', mjs: 'javascript', cjs: 'javascript', jsx: 'javascript',
    ts: 'typescript', tsx: 'typescript',
    json: 'json', jsonc: 'json',
    sh: 'bash', bash: 'bash', zsh: 'bash', env: 'bash',
    ps1: 'powershell', psm1: 'powershell',
    html: 'markup', htm: 'markup', xml: 'markup', svg: 'markup', vue: 'markup',
    css: 'css', scss: 'css', less: 'css',
    md: 'markdown', markdown: 'markdown',
    yml: 'yaml', yaml: 'yaml',
    rs: 'rust', go: 'go', java: 'java',
    c: 'c', h: 'c', cpp: 'cpp', cc: 'cpp', cxx: 'cpp', hpp: 'cpp',
    cs: 'csharp', sql: 'sql',
  };
  return map[ext] || 'none';
}

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
}

function settingsOpen() { return document.body.classList.contains('settings-mode'); }
function showView(n) {
  const open = n === 'settings';
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
  if (data.workspace) document.getElementById('top-workspace').textContent = data.workspace;
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
  html += `<button data-a="reveal">${t('reveal')}</button>`;
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
function hideCtx() {
  mentionOpen = false;
  const ctx = document.getElementById('ctx');
  if (ctx) ctx.style.display = 'none';
}
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
    d.innerHTML = `<span class="dirty">${t.dirty ? '•' : ''}</span><span class="name"></span><span class="x">×</span>`;
    d.querySelector('.name').textContent = name;
    d.title = t.path;
    d.onclick = () => openFile(t.path);
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
  const c = currentChat(); if (!c) return;
  const prevTop = el.scrollTop;
  // every rebuild creates new elements; starting their animations at the shared clock's phase keeps
  // the shimmer / pulse running instead of restarting on each update
  const clock = (document.timeline && document.timeline.currentTime != null) ? document.timeline.currentTime : performance.now();
  el.style.setProperty('--shimmer-delay', '-' + ((clock % 1900) / 1000).toFixed(3) + 's');
  el.style.setProperty('--pulse-delay', '-' + ((clock % 1200) / 1000).toFixed(3) + 's');
  el.innerHTML = '';
  aggregateMessages(c.messages).filter(m => !(m.kind === 'think_collapsed' && !(m.text || '').trim())).forEach(m => {
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
  const max = 1.4 * 13 * 15 + 12;
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
  const prov = (settings && settings.api && settings.api.provider) || 'lm_studio';
  if (prov !== 'lm_studio') return true;
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

  setFooterActivity('loading');
  setFooterModelStatus('', null);
  setStatus(t('loading'), true);
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
    modelLoaded = !(l && l.error);
    settleFooter();
    setStatus(t('ready'), false);
    if (l && l.error) {
      toast('Load failed: ' + l.error, true);
      return false;
    }
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
    const ok = await ensureModelReady();
    if (sendAbort || !ok) {
      if (!ok && !sendAbort) toast(translate('Model not ready — send cancelled'), true);
      running = false;
      updateActionBtn();
      return;
    }
    if (!activeChatId) newChat(true);
    const c = currentChat();
    if (!c) {
      toast('No active chat', true);
      running = false;
      updateActionBtn();
      return;
    }
    let taskToSend = text.trim();
    if (chatAttachments.length) {
      taskToSend = text.trim() + '\n\nAttached files (use these paths):\n' + chatAttachments.map(a => a.path).join('\n');
    }
    c.messages.push({ role: 'user', content: text.trim(), attachments: chatAttachments.slice() });
    if (c.title === 'New chat' || c.title === 'Chat') {
      c.title = chatTitleFromPrompt(text);
      api('/api/chat/title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text.trim() }),
      }).then(r => {
        if (r && r.title) { c.title = r.title; saveChats(); renderChatList(); }
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
        compose_plan: document.getElementById('s-compose-plan')
          ? document.getElementById('s-compose-plan').checked
          : !(settings && settings.chat && settings.chat.compose_plan === false),
        auto_act: document.getElementById('s-auto-act')
          ? document.getElementById('s-auto-act').checked
          : !(settings && settings.chat && settings.chat.auto_act_after_plan === false),
        plan: (chat && chat.plan) || [],
        archive: (chat && chat.planArchive) || [],
        attachments: (chat && chat.messages || []).slice().reverse().find(m => m.role === 'user')?.attachments || chatAttachments,
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
    if (e.model) liveModel = String(e.model);
    const limit = Number(e.context_limit || 0);
    if (limit) {
      _modelContextLimit = limit;
      const ch = currentChat();
      if (ch) ch.context_limit = limit;
    }
    _lastPromptTokens = null;
    setFooterContext(null, _modelContextLimit);
    if (liveModel) setFooterModelStatus(t('model') + ': ' + liveModel, true);
    modelLoaded = !!liveModel;
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
        saveChats();
        renderPlan();
        return;
      }
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
      if (c) {
        c.messages.push({ role: 'system', content: e.text || 'Model finished (empty response)', kind: 'empty_done' });
        renderMessages();
      }
    } else if (st === 'done' || st === 'cancelled') {
      generatingTokens = false;
      settleFooter();
      setStatus(statusLabel(st, e.text), false);
    } else if (st === 'error') {
      generatingTokens = false;
      setFooterActivity('err');
      setStatus(statusLabel(st, e.text || 'Error'), false);
    } else if (st === 'loading_model') {
      setFooterActivity('loading');
      if (e.text) {
        liveModel = String(e.text);
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
      renderMessages();
      return;
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
        foldFinishedThink(m);
        break;
      }
    }
    c.messages = retainOnlyLatestThought(c.messages);
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


function normPlanStatus(s) {
  const v = String(s || 'pending').toLowerCase().replace(/ /g, '_');
  if (['done', 'complete', 'completed', 'x', 'finished'].includes(v)) return 'done';
  if (['skipped', 'skip', 'cancelled', 'canceled', 'wont_do'].includes(v)) return 'skipped';
  if (['frozen', 'freeze', 'paused', 'pause', 'hold', 'on_hold'].includes(v)) return 'frozen';
  if (['failed', 'fail', 'failure'].includes(v)) return 'failed';
  if (['active', 'doing', 'in_progress', 'current', 'progress', 'wip'].includes(v)) return 'active';
  return 'pending';
}
function planCollapsed() {
  try { return localStorage.getItem('kerniq_plan_collapsed') === '1'; } catch (e) { return false; }
}
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
function rememberMode(mode) {
  if (mode !== 'plan' && mode !== 'act') return;
  agentMode = mode;
  try { localStorage.setItem('kerniq_agent_mode', mode); } catch (e) {}
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
  const next = !planCollapsed();
  try { localStorage.setItem('kerniq_plan_collapsed', next ? '1' : '0'); } catch (e) {}
  renderPlan();
});
applyModeSwitch();

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
      input.value = stored || f.default || '';
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
  sel.onchange = async () => {
    const spec = providerCatalog.find(p => p.id === sel.value);
    const draft = collectProviderDraft();
    if (spec) {
      const keys = new Set((spec.fields || []).map(f => f.key));
      if (keys.has('base_url')) {
        const field = (spec.fields || []).find(f => f.key === 'base_url');
        draft.base_url = (field && field.default) || draft.base_url;
      }
      if (keys.has('binary_path')) {
        const field = (spec.fields || []).find(f => f.key === 'binary_path');
        draft.binary_path = draft.binary_path || (field && field.default) || 'claude';
      }
    }
    renderProviderFields(draft);
    markSettingsDirty();
    await refreshModelsSelect(draft.model || '');
  };
  renderProviderFields();
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
    const selectedRow = rows.find(m => {
      const mid = String(m.id || m.name || '');
      return selected && (mid === selected || mid.indexOf(selected) >= 0 || selected.indexOf(mid) >= 0);
    });
    const reportsLoad = rows.some(m => m && (Array.isArray(m.loaded_instances) || m.loaded_context_length));
    const loadedRow = rows.find(m => m && ((m.loaded_instances || []).length || m.loaded_context_length));
    const loadedId = loadedRow ? String(loadedRow.id || loadedRow.name || '') : '';
    if (prov === 'mock') modelLoaded = true;
    else if (!reachable) modelLoaded = false;
    else if (reportsLoad) {
      const row = loadedRow || selectedRow || null;
      modelLoaded = !!(row && ((row.loaded_instances || []).length || row.loaded_context_length));
      if (!selected && !loadedId) modelLoaded = false;
    } else {
      modelLoaded = !!(selected || rows.length);
    }
    setFooterProvider(prov, providerReachable);
    const label = loadedId || liveModel || selected || (prov === 'mock' ? 'mock' : 'auto');
    if (loadedId) liveModel = loadedId;
    if (!reachable && prov !== 'mock') {
      setFooterModelStatus(t('model') + ': ' + label, false);
    } else {
      setFooterModelStatus(t('model') + ': ' + label, modelLoaded || prov === 'mock' ? true : null);
    }
    let limit = null;
    const limitRow = loadedRow || rows.find(m => {
      const mid = String(m.id || m.name || '');
      return label && (mid === label || mid.indexOf(label) >= 0 || label.indexOf(mid) >= 0);
    });
    if (limitRow) {
      const lim = limitRow.loaded_context_length || limitRow.context_length || limitRow.max_context_length || limitRow.context || null;
      if (lim) limit = Number(lim);
    }
    if (limit) _modelContextLimit = limit;
    setFooterContext(_lastPromptTokens, _modelContextLimit);
  } catch (e) {
    if (!running) setFooterModelStatus(t('model') + ': ' + t('offline'), false);
  }
}

/* settings */
function markSettingsDirty() {
  if (settingsHydrating || document.body.classList.contains('run-locked')) return;
  settingsDirty = true;
  const save = document.getElementById('btn-settings-save');
  const cancel = document.getElementById('btn-settings-cancel');
  if (!save || !cancel) return;
  save.disabled = false; cancel.disabled = false;
  save.className = 'save-active';
  cancel.className = 'cancel-active';
}
function syncSettingLocks() {
  const streaming = document.getElementById('s-chat-streaming');
  const reasoning = document.getElementById('s-chat-reasoning');
  const streamOn = !streaming || streaming.checked;
  const runLocked = document.body.classList.contains('run-locked');
  if (reasoning) {
    const line = reasoning.closest('.check-line');
    if (!streamOn) {
      reasoning.checked = false;
      reasoning.disabled = true;
      if (line) line.classList.add('locked');
    } else if (!runLocked) {
      reasoning.disabled = false;
      if (line) line.classList.remove('locked');
    }
  }
  streamingEnabled = streamOn;
  if (typeof resetTps === 'function') resetTps(!streamOn);
  const modeAutoEl = document.getElementById('s-mode-auto');
  const autoAct = document.getElementById('s-auto-act');
  const autoOn = !!(modeAutoEl && modeAutoEl.checked);
  modeAuto = modeAutoEl ? autoOn : modeAuto;
  if (autoAct) {
    const line = autoAct.closest('.check-line');
    if (autoOn) {
      autoAct.checked = true;
      autoAct.disabled = true;
      if (line) line.classList.add('locked');
    } else if (!runLocked) {
      autoAct.disabled = false;
      if (line) line.classList.remove('locked');
    }
  }
  const debugEl = document.getElementById('s-chat-debug');
  const approve = document.getElementById('s-auto-approve');
  if (approve) {
    const allOpt = approve.querySelector('option[value="all"]');
    const devOn = !!(debugEl && debugEl.checked);
    if (allOpt) {
      allOpt.hidden = !devOn;
      allOpt.disabled = !devOn;
    }
    if (!devOn && approve.value === 'all') approve.value = 'high';
  }
  if (typeof applyModeSwitch === 'function') applyModeSwitch();
}
function bindSettingsDirty() {
  const root = document.getElementById('view-settings');
  if (!root || root.dataset.dirtyDelegated) return;
  root.dataset.dirtyDelegated = '1';
  const onEdit = (ev) => {
    if (ev.target && ev.target.closest && ev.target.closest('#tab-interface')) return;   // local prefs, not part of Save
    if (settingsHydrating || document.body.classList.contains('run-locked')) {
      ev.preventDefault();
      ev.stopPropagation();
      return;
    }
    const node = ev.target;
    if (!node || !node.closest) return;
    if (node.id === 's-show-hidden-plugins') return;
    if (node.closest('.settings-actions') || node.closest('#tab-reset')) return;
    syncSettingLocks();
    markSettingsDirty();
  };
  root.addEventListener('input', onEdit);
  root.addEventListener('change', onEdit);
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
  settingsHydrating = true;
  try {
  const loaded = await api('/api/settings');
  if (!loaded || loaded.error || !loaded.agent) {
    toast((loaded && loaded.error) || t('settingsFailed'), true);
  }
  settings = (loaded && loaded.agent) ? loaded : (settings || {});
  settingsSnapshot = JSON.stringify(settings);
  const a = settings.agent || {}, apiS = settings.api || {}, p = settings.prompt || {};
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
  const loopEl = document.getElementById('s-loop-retries');
  if (loopEl) loopEl.value = a.loop_retries ?? 4;
  undoLimit = a.undo_history_size ?? 100;
  document.getElementById('s-api-max-tokens').value = apiS.max_tokens != null ? apiS.max_tokens : '';
  document.getElementById('s-api-temp').value = apiS.temperature ?? 0.7;
  await loadProviderCatalog(apiS.provider || 'lm_studio');
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
  const ap = document.getElementById('s-auto-approve');
  if (ap) ap.value = ch.auto_approve_up_to || 'low';
  const autoAct = document.getElementById('s-auto-act');
  if (autoAct) autoAct.checked = ch.auto_act_after_plan !== false;
  const modeAutoEl = document.getElementById('s-mode-auto');
  if (modeAutoEl) modeAutoEl.checked = ch.mode_auto !== false;
  modeAuto = ch.mode_auto !== false;
  const composeEl = document.getElementById('s-compose-plan');
  if (composeEl) composeEl.checked = ch.compose_plan !== false;
  applyModeSwitch();
  const splitEl = document.getElementById('s-split-models');
  const actField = document.getElementById('act-model-field');
  const actInput = document.getElementById('s-act-model');
  const apiCfg = settings.api || {};
  if (splitEl) splitEl.checked = !!apiCfg.split_models;
  if (actField) actField.hidden = !(apiCfg.split_models);
  if (actInput && !actInput.value) actInput.value = apiCfg.act_model || apiCfg.model || '';
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
  draftTools = {}; draftPlugins = {};
  await Promise.all([
    loadProviderCatalog(apiS.provider || 'lm_studio').catch((e) => toast(String(e), true)),
    loadComponents().catch((e) => toast(String(e), true)),
  ]);
  syncSettingLocks();
  clearSettingsDirty();
  bindSettingsDirty();
  refreshModelsSelect(apiS.model).catch(() => {});
  } catch (e) {
    toast(t('settingsFailed') + ' ' + (e && e.message ? e.message : e), true);
    loadProviderCatalog('lm_studio').catch(() => {});
    loadComponents().catch(() => {});
  } finally {
    settingsHydrating = false;
    bindSettingsDirty();
    syncSettingLocks();
  }
}

let modelsInflight = null;
let modelsCache = null;
let modelsCacheAt = 0;
let modelChoices = [];
async function fetchModels() {
  const now = Date.now();
  if (modelsCache && now - modelsCacheAt < 1500) return modelsCache;
  if (modelsInflight) return modelsInflight;
  modelsInflight = fetch('/api/models', { signal: AbortSignal.timeout(8000) })
    .then(r => r.text())
    .then(text => {
      try { return JSON.parse(text); } catch { return { models: [], reachable: false, error: text }; }
    })
    .catch(() => ({ models: [], reachable: false, error: 'timed out' }))
    .then(data => {
      modelsCache = data;
      modelsCacheAt = Date.now();
      return data;
    }).finally(() => { modelsInflight = null; });
  return modelsInflight;
}
function fillModelMenu(filter) {
  const menu = document.getElementById('model-menu');
  const input = document.getElementById('s-model');
  if (!menu) return;
  const q = String(filter || '').trim().toLowerCase();
  menu.innerHTML = '';
  const rows = modelChoices.filter(m => !q || String(m.id || '').toLowerCase().includes(q) || String(m.name || '').toLowerCase().includes(q));
  if (!rows.length) {
    const empty = document.createElement('div');
    empty.className = 'hint';
    empty.style.padding = '8px';
    empty.textContent = t('noMatches');
    menu.appendChild(empty);
    return;
  }
  rows.forEach(m => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = m.name && m.name !== m.id ? (m.name + ' — ' + m.id) : (m.id || '');
    b.onclick = (ev) => {
      ev.preventDefault();
      if (input) input.value = m.id || '';
      menu.hidden = true;
      if (typeof markSettingsDirty === 'function') markSettingsDirty();
    };
    menu.appendChild(b);
  });
}
function fillActMenu(filter) {
  const menu = document.getElementById('act-model-menu');
  const input = document.getElementById('s-act-model');
  if (!menu) return;
  const q = String(filter || '').trim().toLowerCase();
  menu.innerHTML = '';
  modelChoices.filter(m => !q || String(m.id || '').toLowerCase().includes(q)).forEach(m => {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = m.id || '';
    b.onclick = (ev) => {
      ev.preventDefault();
      if (input) input.value = m.id || '';
      menu.hidden = true;
      markSettingsDirty();
    };
    menu.appendChild(b);
  });
}
document.getElementById('s-split-models')?.addEventListener('change', (ev) => {
  const on = !!ev.target.checked;
  const field = document.getElementById('act-model-field');
  if (field) field.hidden = !on;
  const act = document.getElementById('s-act-model');
  const plan = document.getElementById('s-model');
  if (on && act && !act.value && plan) act.value = plan.value || '';
  markSettingsDirty();
});
document.getElementById('act-model-arrow')?.addEventListener('click', (ev) => {
  ev.preventDefault();
  const menu = document.getElementById('act-model-menu');
  if (!menu) return;
  menu.hidden = !menu.hidden;
  if (!menu.hidden) fillActMenu(document.getElementById('s-act-model')?.value || '');
});
document.getElementById('s-act-model')?.addEventListener('input', () => {
  const menu = document.getElementById('act-model-menu');
  if (menu) { menu.hidden = false; fillActMenu(document.getElementById('s-act-model').value); }
  markSettingsDirty();
});
async function refreshModelsSelect(selected) {
  const sel = document.getElementById('s-model');
  if (!sel) return;
  const prev = selected != null ? selected : sel.value;
  if (prev != null) sel.value = prev;
  const prov = (document.getElementById('s-provider') || {}).value || ((settings && settings.api && settings.api.provider) || 'lm_studio');
  const data = await fetchModels();
  modelChoices = data.models || [];
  fillModelMenu(sel.value || '');
  if (data.error || data.reachable === false) setFooterProvider(prov, false);
  else setFooterProvider(prov, true);
  const modelLabel = sel.value || '(auto)';
  if (data.error || data.reachable === false) setFooterModelStatus(t('model') + ': ' + (data.error || t('offline')), false);
  else if (modelLabel && modelLabel !== '(auto)') setFooterModelStatus(t('model') + ': ' + modelLabel, null);
  const selM = sel.value || '';
  for (const m of (data.models || [])) {
    const lim = m.loaded_context_length || m.context_length || m.max_context_length || m.context;
    if (!lim) continue;
    if (selM && (m.id === selM || String(m.id||'').includes(selM))) { _modelContextLimit = Number(lim); break; }
    if (_modelContextLimit == null) _modelContextLimit = Number(lim);
  }
  setFooterContext(_lastPromptTokens, _modelContextLimit);
  sel.oninput = () => {
    markSettingsDirty();
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
  }  refreshInterfaceControls();
}

let expandedPacks = {};
let selectedPack = null;
function renderToolsList() {
  const by = {};
  (componentsCache.tools || []).forEach(t => { const c = t.category || 'other'; (by[c] = by[c] || []).push(t); });
  const order = ['filesystem', 'terminal', 'web', 'fetch', 'plan', 'other'];
  const labels = { filesystem: 'Filesystem', terminal: 'Terminal', web: 'Web', fetch: 'Fetch', plan: 'Plan', other: 'Other' };
  Object.keys(by).forEach(k => { if (!order.includes(k)) order.push(k); });
  const cats = document.getElementById('s-cats');
  if (cats) cats.innerHTML = '';
  const el = document.getElementById('s-tools-list');
  if (!el) return;
  el.innerHTML = '';
  if (!(componentsCache.tools || []).length) {
    el.innerHTML = '<div class="empty"></div>';
    el.querySelector('.empty').textContent = t('toolsEmpty');
    return;
  }
  order.forEach(k => {
    if (!by[k]?.length) return;
    const pack = document.createElement('div');
    pack.className = 'pack';
    const head = document.createElement('div');
    head.className = 'pack-row' + (selectedPack === k && !selectedToolId ? ' selected' : '');
    const anyOn = by[k].some(t => (draftTools[t.id] || {}).enabled !== false);
    const open = !!expandedPacks[k];
    head.innerHTML = `<input type="checkbox" class="soft-check" ${anyOn ? 'checked' : ''}/><button type="button" class="twist">${open ? '▾' : '▸'}</button><span class="pname"></span>`;
    head.querySelector('.pname').textContent = labels[k] || k;
    const cb = head.querySelector('input');
    cb.onclick = e => e.stopPropagation();
    cb.onchange = e => {
      by[k].forEach(t => {
        draftTools[t.id] = draftTools[t.id] || { enabled: true, values: {} };
        draftTools[t.id].enabled = e.target.checked;
      });
      markSettingsDirty();
      renderToolsList();
    };
    head.querySelector('.twist').onclick = e => {
      e.stopPropagation();
      expandedPacks[k] = !expandedPacks[k];
      renderToolsList();
    };
    head.querySelector('.pname').onclick = () => {
      selectedPack = k;
      selectedToolId = null;
      renderToolsList();
      renderPackDetail(k, by[k]);
    };
    pack.appendChild(head);
    if (open) {
      by[k].forEach(t => {
        const d = draftTools[t.id] || { enabled: true, values: {} };
        const row = document.createElement('div');
        row.className = 'tool-sub' + (selectedToolId === t.id ? ' selected' : '');
        row.innerHTML = `<input type="checkbox" class="soft-check" ${d.enabled !== false ? 'checked' : ''}/><span class="tname"></span>`;
        row.querySelector('.tname').textContent = t.name;
        const tcb = row.querySelector('input');
        tcb.onclick = e => e.stopPropagation();
        tcb.onchange = e => {
          draftTools[t.id] = draftTools[t.id] || { enabled: true, values: {} };
          draftTools[t.id].enabled = e.target.checked;
          markSettingsDirty();
          renderToolsList();
        };
        row.querySelector('.tname').onclick = () => {
          selectedToolId = t.id;
          selectedPack = k;
          renderToolsList();
          renderToolDetail(t.id);
        };
        pack.appendChild(row);
      });
    }
    el.appendChild(pack);
  });
}
function renderPackDetail(cat, tools) {
  const panel = document.getElementById('s-tool-detail');
  if (!panel) return;
  const list = tools || [];
  const allAccept = list.length && list.every(t => (draftTools[t.id]?.values || {}).auto_accept);
  const allMerge = list.length && list.every(t => (draftTools[t.id]?.values || {}).collapsible !== false);
  panel.innerHTML = `<h3>${esc(cat)}</h3><div class="hint">${list.length}</div>`
    + `<label class="field-row-check"><input type="checkbox" class="soft-check" id="pack-auto" ${allAccept ? 'checked' : ''}/><span>${esc(t('packAuto'))}</span></label>`
    + `<label class="field-row-check"><input type="checkbox" class="soft-check" id="pack-merge" ${allMerge ? 'checked' : ''}/><span>${esc(t('packMerge'))}</span></label>`;
  const apply = (key, value) => {
    list.forEach(tool => {
      draftTools[tool.id] = draftTools[tool.id] || { enabled: true, values: {} };
      draftTools[tool.id].values[key] = value;
    });
    markSettingsDirty();
  };
  panel.querySelector('#pack-auto').onchange = e => apply('auto_accept', e.target.checked);
  panel.querySelector('#pack-merge').onchange = e => apply('collapsible', e.target.checked);
}
function renderToolDetail(id) {
  const panel = document.getElementById('s-tool-detail');
  const t = (componentsCache.tools || []).find(x => x.id === id);
  if (!panel || !t) return;
  const draft = draftTools[id] || { enabled: true, values: {} };
  let html = `<h3>${esc(t.name)}</h3><div class="hint">risk: ${esc(t.risk_level || 'medium')} · ${esc(t.description || '')}</div>`;
  const fields = (t.schema && t.schema.fields) || [];
  if (!fields.length) html += '<div class="empty">No extra settings</div>';
  else fields.forEach(f => {
    const val = draft.values[f.key] !== undefined ? draft.values[f.key] : f.default;
    if (f.type === 'bool') {
      html += `<label class="field-row-check"><input type="checkbox" class="soft-check" data-fk="${esc(f.key)}" ${val ? 'checked' : ''}/><span>${esc(f.label)}</span></label>`;
    } else {
      html += `<div class="field"><label class="lbl">${esc(f.label)}</label>`;
      html += `<input type="${f.type === 'int' || f.type === 'float' ? 'number' : 'text'}"${numAttrs(f)} data-fk="${esc(f.key)}" value="${esc(val ?? '')}"/>`;
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
let showHiddenPlugins = false;
function renderPluginsList() {
  const el = document.getElementById('s-plugins-list');
  if (!el) return;
  el.innerHTML = '';
  const rows = (componentsCache.plugins || []).filter(p => {
    const vals = (draftPlugins[p.id] && draftPlugins[p.id].values) || p.values || {};
    const listed = vals.listed !== false;
    return showHiddenPlugins || listed;
  });
  if (!rows.length) {
    el.innerHTML = '<div class="empty"></div>';
    el.querySelector('.empty').textContent = t('pluginsEmpty');
    return;
  }
  rows.forEach(p => {
    const vals = (draftPlugins[p.id] && draftPlugins[p.id].values) || p.values || {};
    const enabled = vals.enabled !== false;
    const listed = vals.listed !== false;
    const row = document.createElement('div');
    row.className = 'tool-row' + (selectedPluginId === p.id ? ' selected' : '');
    const badges = document.createElement('span');
    badges.className = 'plugin-badges';
    const on = document.createElement('span');
    on.className = 'plugin-badge ' + (enabled ? 'on' : 'off');
    on.textContent = enabled ? t('pluginOn') : t('pluginOff');
    badges.appendChild(on);
    if (!listed) {
      const hid = document.createElement('span');
      hid.className = 'plugin-badge hide';
      hid.textContent = t('pluginHidden');
      badges.appendChild(hid);
    }
    if (p.status && p.status !== 'available') {
      const st = document.createElement('span');
      st.className = 'plugin-badge err';
      st.textContent = p.status;
      badges.appendChild(st);
    }
    const name = document.createElement('span');
    name.className = 'tname';
    name.textContent = p.name || p.id;
    row.appendChild(name);
    row.appendChild(badges);
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
    if (f.key === 'ui_locale') {
      const opts = [{ value: 'en', label: 'English' }];
      Object.keys(langPacks).forEach(pid => {
        const pack = langPacks[pid];
        opts.push({ value: pid, label: (pack && (pack.name_native || pack.name_en)) || pid });
      });
      f = Object.assign({}, f, { options: opts });
    }
    const val = draft.values[f.key] !== undefined ? draft.values[f.key] : f.default;
    const label = translate(f.label || '');
    const tip = translate(f.description || '');
    if (f.type === 'bool') {
      html += `<div class="field field-check"><label class="check-line"><input type="checkbox" class="soft-check" data-fk="${esc(f.key)}" ${val ? 'checked' : ''}/><span>${esc(label)}</span>`;
      if (tip) html += `<span class="info-tip" tabindex="0" data-tip="${esc(tip)}">i</span>`;
      html += `</label></div>`;
    } else if (f.type === 'select' && f.options && f.options.length) {
      html += `<div class="field"><label class="lbl">${esc(label)}`;
      if (tip) html += `<span class="info-tip" tabindex="0" data-tip="${esc(tip)}">i</span>`;
      html += `</label><select data-fk="${esc(f.key)}" class="input-std">`;
      f.options.forEach(o => {
        const ov = o.value != null ? o.value : o;
        const ol = translate(o.label != null ? o.label : String(ov));
        html += `<option value="${esc(ov)}" ${String(val) === String(ov) ? 'selected' : ''}>${esc(ol)}</option>`;
      });
      html += `</select></div>`;
    } else {
      html += `<div class="field"><label class="lbl">${esc(label)}`;
      if (tip) html += `<span class="info-tip" tabindex="0" data-tip="${esc(tip)}">i</span>`;
      html += `</label>`;
      html += `<input class="input-std" type="${f.type === 'int' || f.type === 'float' ? 'number' : 'text'}"${numAttrs(f)} data-fk="${esc(f.key)}" value="${esc(val ?? '')}"/>`;
      html += `</div>`;
    }
  });
  if (id === 'plugin_web_ui') {
    html += '<div class="set-group"><h3>' + esc(translate('Language packs')) + '</h3><div class="row">';
    html += '<button type="button" id="btn-lang-import">' + esc(translate('Import')) + '</button>';
    html += '<button type="button" class="ghost" id="btn-lang-remove">' + esc(translate('Remove')) + '</button>';
    html += '</div></div>';
  }
  panel.innerHTML = html;
  syncCompactLimit(panel);
  if (!draftPlugins[id]) draftPlugins[id] = { values: {} };
  panel.querySelectorAll('[data-fk]').forEach(inp => {
    const ev = (inp.type === 'checkbox' || inp.tagName === 'SELECT') ? 'change' : 'input';
    inp.addEventListener(ev, () => {
      let v;
      if (inp.type === 'checkbox') v = inp.checked;
      else if (inp.type === 'number') v = Number(inp.value);
      else v = inp.value;
      draftPlugins[id].values[inp.dataset.fk] = v;
      if (inp.dataset.fk === 'target_mode' || inp.dataset.fk === 'trigger_percent' || inp.dataset.fk === 'target_percent') syncCompactLimit(panel);
      if (inp.dataset.fk === 'enabled' || inp.dataset.fk === 'listed') renderPluginsList();
      markSettingsDirty();
    });
  });
  const importBtn = document.getElementById('btn-lang-import');
  const removeBtn = document.getElementById('btn-lang-remove');
  if (importBtn) importBtn.onclick = () => document.getElementById('lang-pack-file').click();
  if (removeBtn) removeBtn.onclick = () => openLangModal();
}
function syncCompactLimit(panel) {
  if (!panel) return;
  const mode = panel.querySelector('[data-fk="target_mode"]');
  const trigger = panel.querySelector('[data-fk="trigger_percent"]');
  const pctInput = panel.querySelector('[data-fk="target_percent"]');
  const tokenInput = panel.querySelector('[data-fk="target_tokens"]');
  const pctField = pctInput && pctInput.closest('.field');
  const tokenField = tokenInput && tokenInput.closest('.field');
  const tokens = !mode || mode.value === 'tokens';
  if (pctField) pctField.style.display = tokens ? 'none' : '';
  if (tokenField) tokenField.style.display = tokens ? '' : 'none';
  if (trigger && pctInput) {
    const cap = Math.max(5, Number(trigger.value || 75) - 1);
    if (Number(pctInput.value) >= Number(trigger.value || 75)) pctInput.value = String(cap);
    pctInput.max = String(cap);
  }
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
    loop_retries: Number(document.getElementById('s-loop-retries')?.value) || 4,
  };
  undoLimit = agent.undo_history_size;
  const apiBody = {
    provider: document.getElementById('s-provider').value,
    base_url: document.getElementById('s-base-url')
      ? document.getElementById('s-base-url').value
      : ((settings && settings.api && settings.api.base_url) || ''),
    api_token: document.getElementById('s-api-token')
      ? document.getElementById('s-api-token').value
      : ((settings && settings.api && settings.api.api_token) || ''),
    binary_path: document.getElementById('s-binary-path')
      ? document.getElementById('s-binary-path').value
      : ((settings && settings.api && settings.api.binary_path) || ''),
    model: document.getElementById('s-model')?.value || '',
    split_models: !!document.getElementById('s-split-models')?.checked,
    act_model: document.getElementById('s-act-model')?.value || document.getElementById('s-model')?.value || '',
    temperature: Number(document.getElementById('s-api-temp').value),
    max_tokens: emptyNum('s-api-max-tokens'),
    provider_descriptions: (settings && settings.api && settings.api.provider_descriptions) || {},
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
    auto_approve_up_to: document.getElementById('s-auto-approve')?.value || 'low',
    auto_act_after_plan: document.getElementById('s-auto-act')?.checked !== false,
    mode_auto: document.getElementById('s-mode-auto')?.checked !== false,
    compose_plan: document.getElementById('s-compose-plan')?.checked !== false,
    response_language: document.getElementById('s-chat-lang')?.value || 'auto',
  };
  modeAuto = chat.mode_auto;
  applyModeSwitch();
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
  settings = settings || {};
  settings.agent = Object.assign({}, settings.agent || {}, agent);
  settings.api = Object.assign({}, settings.api || {}, apiBody);
  settings.prompt = Object.assign({}, settings.prompt || {}, prompt);
  settings.chat = Object.assign({}, settings.chat || {}, chat);
  streamingEnabled = chat.streaming !== false;
  resetTps(!streamingEnabled);
  syncSettingLocks();
  const uiDraft = draftPlugins['plugin_web_ui'];
  if (uiDraft && uiDraft.values && uiDraft.values.show_footer === false) {
    document.getElementById('app-footer').classList.add('hidden');
  } else {
    document.getElementById('app-footer').classList.remove('hidden');
  }
  clearSettingsDirty();
  const loc = draftPlugins['plugin_web_ui']?.values?.ui_locale || 'en';
  applyUiLocale(loc);
  toast(t('saved'));
  await refreshTree();
  await refreshModelFooter();
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

function flashSetting(el) {
  if (!el) return;
  const target = el.closest('.field, .field-row-check, .model-combo') || el;
  target.classList.remove('settings-flash');
  void target.offsetWidth;
  try { target.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (_) {}
  target.classList.add('settings-flash');
  window.setTimeout(() => target.classList.remove('settings-flash'), 1600);
}
async function openSettingsAt(tab, focusId) {
  const view = document.getElementById('view-settings');
  const btn = document.getElementById('nav-settings');
  const already = settingsOpen();
  showView('settings');
  if (btn) {
    btn.classList.add('active-settings');
    btn.textContent = '✕';
    btn.title = 'Close settings';
  }
  const prov = document.getElementById('s-provider');
  if (!already && (!prov || !prov.options.length)) {
    try { await loadSettings(); } catch (_) {}
  }
  const stab = document.querySelector('.stab[data-tab="' + tab + '"]');
  if (stab) stab.click();
  if (focusId) window.setTimeout(() => flashSetting(document.getElementById(focusId)), 40);
}
async function openContextSettings() {
  await openSettingsAt('plugins', null);
  if (!(componentsCache.plugins || []).length) {
    try { await loadComponents(); } catch (_) {}
  }
  const plugins = componentsCache.plugins || [];
  const plug = plugins.find(p => p.id === 'plugin_context_compact')
    || plugins.find(p => /compact|context/i.test(String(p.id || '') + String(p.name || '')));
  if (!plug) return;
  selectedPluginId = plug.id;
  renderPluginsList();
  renderPluginDetail(plug.id);
  flashSetting(document.querySelector('#s-plugin-detail [data-fk="trigger_percent"]') || document.getElementById('s-plugin-detail'));
}

/* nav */
document.getElementById('nav-logo').onclick = () => {
  if (settingsDirty && !confirm('Settings are not saved. Leave anyway?')) return;
  showView('main');
};
document.getElementById('nav-settings').onclick = () => {
  const btn = document.getElementById('nav-settings');
  const open = settingsOpen();
  if (open) {
    showView('main');
    btn.classList.remove('active-settings');
    btn.textContent = '⚙';
    btn.title = 'Settings';
    renderMessages();
  } else {
    showView('settings');
    btn.classList.add('active-settings');
    btn.textContent = '✕';
    btn.title = 'Close settings';
    loadSettings();
  }
};
document.getElementById('footer-provider').onclick = () => { openSettingsAt('api', 's-provider'); };
document.getElementById('footer-model').onclick = () => { openSettingsAt('api', 's-model'); };
document.getElementById('footer-ctx').onclick = () => { openContextSettings(); };
document.getElementById('top-workspace').onclick = () => { openSettingsAt('agent', 's-workspace'); };
document.getElementById('btn-toggle-explorer').onclick = () => { if (!layoutBusy) setExplorerCollapsed(!explorerCollapsed); };
document.getElementById('btn-toggle-chat').onclick = () => setChatCollapsed(!chatCollapsed);
const refreshTreeBtn = document.getElementById('btn-refresh-tree');
if (refreshTreeBtn) refreshTreeBtn.onclick = () => refreshTree();
document.getElementById('btn-new-chat').onclick = () => newChat(false);
const _refreshModelsBtn = document.getElementById('btn-refresh-models');
if (_refreshModelsBtn) _refreshModelsBtn.onclick = () => refreshModelsSelect(document.getElementById('s-model').value);

document.getElementById('s-show-hidden-plugins')?.addEventListener('change', (ev) => {
  showHiddenPlugins = !!ev.target.checked;
  renderPluginsList();
});
document.querySelectorAll('.stab').forEach(s => {
  s.onclick = () => {
    document.querySelectorAll('.stab').forEach(x => x.classList.remove('active'));
    s.classList.add('active');
    document.querySelectorAll('.tabp').forEach(p => p.style.display = 'none');
    document.getElementById('tab-' + s.dataset.tab).style.display = 'block';
  };
});

async function resumeServerChat() {
  const c = currentChat();
  if (!c) return;
  let snap;
  try {
    snap = await api('/api/chat/snapshot?chat_id=' + encodeURIComponent(c.id));
  } catch (_) {
    return;
  }
  if (!snap || snap.error && !(snap.messages || []).length) return;
  const localLen = (c.messages || []).length;
  const serverLen = (snap.messages || []).length;
  if (!snap.active && serverLen <= localLen) return;
  if (snap.active && serverLen) {
    let lastUser = -1;
    c.messages.forEach((m, i) => { if (m.role === 'user') lastUser = i; });
    const prefix = lastUser > 0 ? c.messages.slice(0, lastUser) : [];
    c.messages = prefix.concat(snap.messages);
  } else if (serverLen) {
    c.messages = snap.messages;
  }
  saveChats();
  renderMessages();
  (snap.pending_approvals || []).forEach(showApproval);
  if (snap.active && snap.run_id) {
    running = true;
    setRunLock(true);
    currentRunId = snap.run_id;
    updateActionBtn();
    setStatus(statusLabel('processing'), true);
    await pollRun(snap.run_id, snap.cursor || 0);
    finalizeLiveMessages();
    running = false;
    setRunLock(false);
    currentRunId = null;
    updateActionBtn();
    saveChats();
    renderMessages();
  }
}

/* init */
loadPanelWidths();
bindResizer('resizer-left', 'left');
bindResizer('resizer-right', 'right');
loadChats();
try { applyChatContextFooter(); } catch (_) {}
if (!chats.length) newChat(true);
else { activeChatId = chats[chats.length - 1].id; renderChatList(); renderMessages(); }
applyStoredMode();
resumeServerChat();
clearEditor();
refreshTree();
bindSettingsDirty();
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
  if (persist !== false) { try { localStorage.setItem('kerniq_layout', layoutMode); } catch (e) {} }
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
   editor -> agent: the chat grows leftwards over the explorer and editor (they squeeze, contents do not
                    re-wrap); when it fills the window the chat list slides in if it was open.
   agent -> editor: the chat list folds away, the chat shrinks to the right while the editor takes the whole
                    window; then the explorer and the chat slide in if they were open. */
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
  [P.ex, P.ed, P.ch].forEach(el => {
    ['width', 'flex', 'transition', '--pin'].forEach(prop => el.style.removeProperty(prop));
    el.classList.remove('pin');
  });
  P.view.classList.remove('layout-anim', 'keep-tree', 'keep-chats');
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
      typePillLabel(t('agentLabel'));                            // "Editor" is erased, "Agent" is typed
      // 1. the chat folds away to the right; the editor takes its place
      if (start.ch > 0) await layoutPhase({ ex: start.ex, ed: start.ed + start.ch, ch: 0 }, 340, { ch: start.ch });
      // 2. now invisible, the chat switches to the agent styling, then grows over everything
      P.view.classList.add('keep-tree');                         // the explorer keeps its tree while it squeezes
      applyLayoutAttrs('agent');
      await layoutPhase({ ex: 0, ed: 0, ch: W }, 520, { ex: S, ed: start.ed + start.ch });
      P.view.classList.remove('keep-tree');
      refreshLayoutLabels();
      renderChatList();
      // 3. the chat list slides in if it was open
      if (sideOpen.agent) await layoutPhase({ ex: S, ed: 0, ch: W - S }, 380, { ex: S });
    } else {
      typePillLabel(t('editorLabel'));
      P.view.classList.add('keep-chats');                        // the chat list folds away with its contents
      if (start.ex > 0) await layoutPhase({ ex: 0, ed: 0, ch: W }, 380, { ex: start.ex });
      await layoutPhase({ ex: 0, ed: W, ch: 0 }, 560, { ch: W });  // chat leaves to the right, editor fills the window
      P.view.classList.remove('keep-chats');
      applyLayoutAttrs('editor');
      const E = sideOpen.editor ? S : 0;
      const Cw = chatCollapsed ? 0 : C;
      if (E || Cw) await layoutPhase({ ex: E, ed: W - E - Cw, ch: Cw }, 420, { ex: E || null, ch: Cw || null });
    }
  } finally {
    finishLayoutAnim();
    layoutBusy = false;
  }
}
document.getElementById('mode-pill')?.addEventListener('click', () => switchLayout(layoutMode === 'agent' ? 'editor' : 'agent'));
document.querySelectorAll('#seg-layout button').forEach(b => b.addEventListener('click', () => switchLayout(b.dataset.v)));
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


/* ---------- interface language + status footer (kept in the Web UI plugin settings) ---------- */
function webUiSaved() {
  const p = (componentsCache.plugins || []).find(x => x.id === 'plugin_web_ui');
  return (p && p.values) || {};
}
async function setWebUiValue(key, value) {
  const draft = draftPlugins['plugin_web_ui'] || (draftPlugins['plugin_web_ui'] = { values: {} });
  draft.values[key] = value;                                   // Save in the Plugins tab must not undo this
  const merged = Object.assign({}, webUiSaved(), { [key]: value });
  const p = (componentsCache.plugins || []).find(x => x.id === 'plugin_web_ui');
  if (p) p.values = merged;
  const r = await api('/api/component/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ kind: 'plugin', id: 'plugin_web_ui', values: merged }),
  });
  if (r && r.error) toast(String(r.error), true);
  if (typeof selectedPluginId !== 'undefined' && selectedPluginId === 'plugin_web_ui') renderPluginDetail('plugin_web_ui');
}
function refreshInterfaceControls() {
  const sel = document.getElementById('ui-lang');
  if (sel) {
    sel.innerHTML = '';
    const add = (v, label) => { const o = document.createElement('option'); o.value = v; o.textContent = label; sel.appendChild(o); };
    add('en', 'English');
    Object.keys(langPacks).forEach(id => {
      const pk = langPacks[id];
      if (pk && pk.valid !== false) add(id, pk.name_native || pk.name_en || id);
    });
    sel.value = [...sel.options].some(o => o.value === uiLocale) ? uiLocale : 'en';
  }
  const f = document.getElementById('ui-footer');
  const foot = document.getElementById('app-footer');
  if (f && foot) f.checked = !foot.classList.contains('hidden');
}
document.getElementById('ui-lang')?.addEventListener('change', async (e) => {
  const v = e.target.value;
  applyUiLocale(v);
  await setWebUiValue('ui_locale', v);
});
document.getElementById('ui-footer')?.addEventListener('change', async (e) => {
  footerEnabled = !!e.target.checked;
  document.getElementById('app-footer').classList.toggle('hidden', !e.target.checked);
  await setWebUiValue('show_footer', !!e.target.checked);
});
document.getElementById('ui-auto-think')?.addEventListener('change', (e) => {
  autoThink = !!e.target.checked;
  try { localStorage.setItem('kerniq_auto_think', autoThink ? '1' : '0'); } catch (_) {}
});
(function () { const b = document.getElementById('ui-auto-think'); if (b) b.checked = autoThink; })();
document.getElementById('btn-lang-packs')?.addEventListener('click', () => openLangModal());
document.getElementById('lang-modal-import')?.addEventListener('click', () => document.getElementById('lang-pack-file')?.click());
refreshInterfaceControls();

/* interface preferences: applied at once, stored in this browser only */
applyLayout(layoutMode, false);
(function setupInterfacePrefs() {
  const root = document.documentElement;
  const seg = document.getElementById('seg-motion');
  const hlBox = document.getElementById('ui-hl');
  const syncMotion = () => {
    const cur = root.dataset.motion || 'on';
    if (!seg) return;
    seg.querySelectorAll('button').forEach(b => {
      const on = b.dataset.v === cur;
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
  };
  if (seg) {
    seg.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      root.dataset.motion = b.dataset.v;
      try { localStorage.setItem('kerniq_motion', b.dataset.v); } catch (_) {}
      syncMotion();
    }));
    syncMotion();
  }
  if (hlBox) {
    hlBox.checked = ED.hl;
    hlBox.addEventListener('change', () => {
      ED.hl = hlBox.checked;
      try { localStorage.setItem('kerniq_hl', ED.hl ? '1' : '0'); } catch (_) {}
      updateLineNumbers();
    });
  }
  const stop = document.getElementById('btn-run-stop');
  if (stop) stop.addEventListener('click', () => {
    const b = document.getElementById('btn-action');
    if (b && !b.disabled) b.click();
  });
})();

document.getElementById('msgs')?.addEventListener('click', (e) => {
  const b = e.target.closest('.copy-btn');
  if (!b) return;
  const code = b.closest('.code-block') && b.closest('.code-block').querySelector('pre code');
  if (!code) return;
  const text = code.textContent;
  const done = () => {
    b.textContent = translate('Copied');
    b.classList.add('done');
    setTimeout(() => { b.textContent = translate('Copy'); b.classList.remove('done'); }, 1400);
  };
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.cssText = 'position:fixed;opacity:0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (_) {}
    ta.remove(); done();
  };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback);
  else fallback();
});
document.getElementById('msgs')?.addEventListener('click', async (e) => {
  const a = e.target.closest('a.file-ref');
  if (!a) return;
  e.preventDefault();
  const path = a.dataset.path;
  if (!path) return;
  if (layoutMode === 'agent') await switchLayout('editor');   // the file opens in the editor
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

const BLOCKED_ATTACH = new Set(['png','jpg','jpeg','gif','webp','bmp','svg','ico','heic','heif','tif','tiff','mp4','mov','mkv','webm','avi','wmv','m4v','mpg','mpeg','mp3','wav','ogg','flac','aac','m4a','wma','opus','exe','dll','bin','iso','dmg','msi','zip','7z','rar','gz','tar','bz2','xz']);
function attachBlocked(name) {
  const raw = String(name || '');
  const dot = raw.lastIndexOf('.');
  if (dot < 0) return false;
  return BLOCKED_ATTACH.has(raw.slice(dot + 1).toLowerCase());
}
const CTX_ICON = {
  folder: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
  upload: '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 16V4M7 9l5-5 5 5M5 20h14"/></svg>',
  search: '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>',
  chev: '<svg class="ci-chev" viewBox="0 0 12 12" width="10" height="10" aria-hidden="true"><path d="M4 2.5 7.5 6 4 9.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
};
function placeCtx(anchor, opts) {
  const ctx = document.getElementById('ctx');
  if (!ctx || !anchor) return ctx;
  const above = !!(opts && opts.above);
  const r = anchor.getBoundingClientRect();
  const gap = 8, edge = 8;
  ctx.style.display = 'block';
  ctx.style.visibility = 'hidden';
  ctx.style.maxHeight = '';
  ctx.style.top = '0px';
  ctx.style.bottom = 'auto';
  ctx.style.left = '0px';
  const width = ctx.offsetWidth, height = ctx.offsetHeight;
  let left = r.left;
  if (left + width > window.innerWidth - edge) left = Math.max(edge, window.innerWidth - width - edge);
  const spaceAbove = r.top - gap - edge;
  const spaceBelow = window.innerHeight - r.bottom - gap - edge;
  if (above || (height > spaceBelow && spaceAbove > spaceBelow)) {
    // pinned by its bottom edge: results that arrive later grow upwards instead of over the anchor
    ctx.style.top = 'auto';
    ctx.style.bottom = (window.innerHeight - r.top + gap) + 'px';
    ctx.style.maxHeight = Math.max(120, spaceAbove) + 'px';
  } else {
    ctx.style.top = (r.bottom + gap) + 'px';
    ctx.style.maxHeight = Math.max(120, spaceBelow) + 'px';
  }
  ctx.style.left = left + 'px';
  ctx.style.visibility = '';
  return ctx;
}
function bindCtxHide(anchor) {
  const ctx = document.getElementById('ctx');
  const hide = (ev) => {
    if (ctx.contains(ev.target) || (anchor && anchor.contains && anchor.contains(ev.target))) return;
    hideCtx();
    document.removeEventListener('click', hide);
  };
  setTimeout(() => document.addEventListener('click', hide), 0);
}
(function setupAttach() {
  const btn = document.getElementById('btn-attach');
  if (!btn) return;
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
        if (attachBlocked(f.name)) { toast(t('attachBlocked'), true); continue; }
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
        if (r.path) addAttachment(r.path, true, false);
        else if (r.error) toast(r.error, true);
      }
    });
  }
  const outside = document.getElementById('outside-picker');
  if (outside) {
    outside.addEventListener('change', async () => {
      const files = [...(outside.files || [])];
      outside.value = '';
      for (const f of files) {
        if (attachBlocked(f.name)) { toast(t('attachBlocked'), true); continue; }
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
        if (r.path) addAttachment(r.path, true, false);
        else if (r.error) toast(r.error, true);
      }
    });
  }
})();
function addAttachment(path, exists, external) {
  if (chatAttachments.some(a => a.path === path)) return;
  chatAttachments.push({ path, exists: exists !== false, external: !!external });
  renderAttachChips();
}
function renderAttachChips() {
  const el = document.getElementById('attach-chips');
  if (!el) return;
  el.innerHTML = '';
  chatAttachments.forEach((a, i) => {
    const d = document.createElement('span');
    d.className = 'attach-chip ' + (a.exists ? 'ok' : 'bad');
    d.appendChild(document.createTextNode((a.external ? '↗ ' : '') + a.path + ' '));
    const x = document.createElement('b');
    x.textContent = '×';
    x.onclick = () => { chatAttachments.splice(i, 1); renderAttachChips(); };
    d.appendChild(x);
    el.appendChild(d);
  });
}
function hitMarkup(path) {
  const norm = String(path).replace(/\\/g, '/');
  const i = norm.lastIndexOf('/');
  const name = i >= 0 ? norm.slice(i + 1) : norm;
  const dir = i >= 0 ? norm.slice(0, i + 1) : '';
  return fileSvg(name) + '<span class="hit-name">' + esc(name) + '</span>' +
    (dir ? '<span class="hit-dir">' + esc(dir) + '</span>' : '');
}
function fillFileHits(hits, onPick) {
  hits.innerHTML = '';
  let seq = 0;
  return async (query) => {
    const mine = ++seq;
    const data = await api('/api/fs/search?q=' + encodeURIComponent(query || ''));
    if (mine !== seq) return;              // a newer query is already on its way
    hits.innerHTML = '';
    const list = (data.hits || []).filter(h => !attachBlocked(h.path));
    let shown = 0;
    const CHUNK = 120;                       // no cap on results: they are added as the list is scrolled
    const more = () => {
      const frag = document.createDocumentFragment();
      list.slice(shown, shown + CHUNK).forEach(h => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'hit';
        b.title = h.path;
        b.innerHTML = hitMarkup(h.path);
        b.onclick = (ev) => { ev.preventDefault(); ev.stopPropagation(); onPick(h.path); };
        frag.appendChild(b);
      });
      shown = Math.min(list.length, shown + CHUNK);
      hits.appendChild(frag);
    };
    hits.onscroll = () => {
      if (shown < list.length && hits.scrollTop + hits.clientHeight >= hits.scrollHeight - 60) more();
    };
    more();
    if (!list.length) {
      const empty = document.createElement('div');
      empty.className = 'attach-empty';
      empty.textContent = (query || '').trim() ? t('noMatches') : t('typeToSearch');
      hits.appendChild(empty);
    } else {
      hits.firstElementChild.classList.add('active');
    }
  };
}
function bindHitKeys(input, hits) {
  input.onkeydown = (ev) => {
    const items = [...hits.querySelectorAll('.hit')];
    const cur = items.findIndex(x => x.classList.contains('active'));
    if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
      ev.preventDefault();
      if (!items.length) return;
      const n = (cur + (ev.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
      items.forEach(x => x.classList.remove('active'));
      items[n].classList.add('active');
      items[n].scrollIntoView({ block: 'nearest' });
    } else if (ev.key === 'Enter') {
      ev.preventDefault();
      const target = items[cur >= 0 ? cur : 0];
      if (target) target.click();
    } else if (ev.key === 'Escape') {
      ev.preventDefault();
      hideCtx();
      const pr = document.getElementById('prompt');
      if (pr) pr.focus();
    }
  };
}
function showAttachMenu(anchor) {
  const ctx = document.getElementById('ctx');
  if (!ctx) return;
  mentionOpen = false;
  ctx.className = 'ctx ctx-attach';
  const item = (id, icon, chev) => '<button type="button" class="ctx-item" id="' + id + '"><span class="ci-ico">' + icon +
    '</span><span class="ci-text"><span class="ci-label"></span><span class="ci-hint"></span></span>' + (chev || '') + '</button>';
  ctx.innerHTML = item('attach-project', CTX_ICON.folder, CTX_ICON.chev) +
    '<div id="attach-project-box" hidden><div class="ctx-search">' + CTX_ICON.search +
    '<input id="attach-q" autocomplete="off" spellcheck="false"/></div><div id="attach-hits" class="attach-hits"></div></div>' +
    item('attach-outside', CTX_ICON.upload, '');
  const setText = (id, label, hint) => {
    const el = document.getElementById(id);
    el.querySelector('.ci-label').textContent = label;
    el.querySelector('.ci-hint').textContent = hint;
  };
  setText('attach-project', t('fromProject'), t('fromProjectHint'));
  setText('attach-outside', t('fromOutside'), t('fromOutsideHint'));
  const box = document.getElementById('attach-project-box');
  const q = document.getElementById('attach-q');
  const hits = document.getElementById('attach-hits');
  q.placeholder = t('attachSearch');
  const search = fillFileHits(hits, (path) => { addAttachment(path, true, false); hideCtx(); });
  bindHitKeys(q, hits);
  const reposition = () => placeCtx(anchor, { above: true });
  document.getElementById('attach-project').onclick = (ev) => {
    ev.stopPropagation();
    box.hidden = !box.hidden;
    document.getElementById('attach-project').classList.toggle('open', !box.hidden);
    reposition();
    if (!box.hidden) { q.focus(); search(q.value || ''); }
  };
  document.getElementById('attach-outside').onclick = async (ev) => {
    ev.stopPropagation();
    hideCtx();
    const r = await api('/api/fs/pick_files', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    if (r && r.error) {
      toast(t('fileDialogFailed'), true);
      const input = document.getElementById('outside-picker');
      if (input) input.click();
      return;
    }
    (r.paths || []).forEach(p => addAttachment(p, true, true));
    if (r && r.blocked && r.blocked.length) toast(t('attachBlocked'), true);
  };
  q.oninput = () => { clearTimeout(q._t); q._t = setTimeout(() => search(q.value || ''), 160); };
  q.onclick = (ev) => ev.stopPropagation();
  reposition();
  bindCtxHide(anchor);
}
function trackMention() {
  const pos = promptEl.selectionStart || 0;
  const before = promptEl.value.slice(0, pos);
  const m = before.match(/(^|\s)@([^\s@]*)$/);
  if (!m) {
    if (mentionOpen) hideCtx();
    return;
  }
  mentionStart = pos - m[2].length - 1;
  showMentionMenu(m[2] || '');
}
function insertMention(path) {
  const pos = promptEl.selectionStart || 0;
  const start = mentionStart >= 0 ? mentionStart : pos;
  const token = '@' + path + ' ';
  promptEl.value = promptEl.value.slice(0, start) + token + promptEl.value.slice(pos);
  const caret = start + token.length;
  hideCtx();
  promptEl.focus();
  promptEl.setSelectionRange(caret, caret);
  autoGrow();
  updateActionBtn();
}
function showMentionMenu(query) {
  const fresh = !mentionOpen;
  const ctx = document.getElementById('ctx');
  if (!ctx) return;
  mentionOpen = true;
  if (!document.getElementById('attach-hits') || !fresh) {
    ctx.className = 'ctx ctx-attach';
    ctx.innerHTML = '<div class="ctx-search">' + CTX_ICON.search + '<input id="attach-q" autocomplete="off" spellcheck="false"/></div><div id="attach-hits" class="attach-hits"></div>';
  }
  placeCtx(promptEl, { above: true });
  const q = document.getElementById('attach-q');
  q.placeholder = t('attachSearch');
  if (document.activeElement !== q) q.value = query || '';
  const hits = document.getElementById('attach-hits');
  const search = fillFileHits(hits, insertMention);
  q.oninput = () => { clearTimeout(q._t); q._t = setTimeout(() => search(q.value || ''), 200); };
  q.onclick = (ev) => ev.stopPropagation();
  search(query || '');
  if (fresh) bindCtxHide(promptEl);
}

const msgsBox = document.getElementById('msgs');
if (msgsBox) {
  msgsBox.addEventListener('scroll', () => {
    if (programmaticScroll) return;
    stickToBottom = nearBottom(msgsBox);
    updateScrollBtn();
  });
}
const scrollBtn = document.getElementById('btn-scroll-bottom');
if (scrollBtn) {
  scrollBtn.onclick = () => {
    const el = document.getElementById('msgs');
    if (!el) return;
    stickToBottom = true;
    updateScrollBtn();
    programmaticScroll = true;
    const top = el.scrollHeight;
    try { el.scrollTo({ top: top, behavior: 'smooth' }); }
    catch (_) { el.scrollTop = top; }
    const finish = () => {
      if (!nearBottom(el)) return;
      programmaticScroll = false;
      stickToBottom = true;
      updateScrollBtn();
      el.removeEventListener('scroll', finish);
    };
    el.addEventListener('scroll', finish);
    setTimeout(() => {
      el.removeEventListener('scroll', finish);
      programmaticScroll = false;
      stickToBottom = nearBottom(el);
      updateScrollBtn();
    }, 900);
  };
}

// Model loaded indicator in footer
startTpsTimer();
setInterval(() => { if (!running) refreshModelFooter().catch(() => {}); }, 8000);
setInterval(() => { setFooterContext(_lastPromptTokens, _modelContextLimit); }, 5000);
document.addEventListener('DOMContentLoaded', () => { setTimeout(() => refreshModelFooter().catch(() => {}), 500); });


async function loadLangPacks() {
  const data = await api('/api/ui/languages').catch(() => ({ packs: [] }));
  langPacks = {};
  (data.packs || []).forEach(pack => {
    if (pack && pack.id) langPacks[pack.id] = pack;
  });
  const loc = (draftPlugins['plugin_web_ui'] && draftPlugins['plugin_web_ui'].values && draftPlugins['plugin_web_ui'].values.ui_locale)
    || (settings && settings.plugins && settings.plugins.ui_locale)
    || uiLocale;
  applyUiLocale(loc);
}
function openLangModal() {
  const modal = document.getElementById('lang-modal');
  const list = document.getElementById('lang-list');
  if (!modal || !list) return;
  const imp = document.getElementById('lang-modal-import');
  if (imp) imp.textContent = translate('Import');
  list.innerHTML = '';
  const ids = Object.keys(langPacks);
  if (!ids.length) {
    list.innerHTML = '<div class="empty">' + esc(translate('No language packs installed.')) + '</div>';
  }
  ids.forEach(id => {
    const pack = langPacks[id];
    const row = document.createElement('div');
    row.className = 'lang-row';
    const name = document.createElement('span');
    const broken = pack.valid === false;
    name.textContent = broken
      ? ((pack.name_en || id) + ' — ' + ((pack.errors && pack.errors[0]) || 'Invalid'))
      : ((pack.name_native || pack.name_en || id) + ' · ' + (pack.name_en || id));
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'lang-x';
    btn.setAttribute('aria-label', translate('Remove'));
    btn.textContent = '×';
    btn.title = translate('Remove');
    btn.onclick = async () => {
      await api('/api/ui/languages/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: id }),
      });
      const draft = draftPlugins['plugin_web_ui'];
      if (draft && draft.values && draft.values.ui_locale === id) {
        draft.values.ui_locale = 'en';
        await api('/api/component/settings', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ kind: 'plugin', id: 'plugin_web_ui', values: draft.values }),
        });
      }
      if (uiLocale === id) uiLocale = 'en';
      await loadLangPacks();
      if (selectedPluginId) renderPluginDetail(selectedPluginId);
      openLangModal();
    };
    row.appendChild(name);
    row.appendChild(btn);
    list.appendChild(row);
  });
  modal.classList.add('on');
  document.body.classList.add('modal-open');
}
function closeLangModal() {
  const modal = document.getElementById('lang-modal');
  if (modal) modal.classList.remove('on');
  document.body.classList.remove('modal-open');
}
document.getElementById('lang-modal-close')?.addEventListener('click', closeLangModal);
document.getElementById('lang-modal')?.addEventListener('click', (ev) => {
  if (ev.target && ev.target.id === 'lang-modal') closeLangModal();
});
document.getElementById('lang-pack-file')?.addEventListener('change', async (ev) => {
  const file = ev.target.files && ev.target.files[0];
  ev.target.value = '';
  if (!file) return;
  let pack;
  try { pack = JSON.parse(await file.text()); }
  catch (_) { toast(translate('Language pack is not valid JSON.'), true); return; }
  const res = await api('/api/ui/languages/import', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pack: pack }),
  });
  if (res && res.error) { toast(res.error, true); return; }
  await loadLangPacks();
  if (selectedPluginId) renderPluginDetail(selectedPluginId);
  if (res && res.warnings && res.warnings.length) toast(res.warnings.join(' '));
  else toast(translate('Language pack imported.'));
});
loadLangPacks();

async function shutdownUi() {
  if (!confirm(translate('Stop the Web UI and close this page?'))) return;
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
