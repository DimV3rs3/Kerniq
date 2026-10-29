
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
    download: 'Download',
    delete: 'Delete', rename: 'Rename', promptPh: 'Ask to edit a file, explain code, or plan the next change…',
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
    sortModels: 'Sort models', sortByName: 'Name', sortByParams: 'Parameters',
    sortByContext: 'Context length', sortAsc: 'Ascending', sortDesc: 'Descending',
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
    planFailed: 'Failed',
    planPartial: 'Partially completed',
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
    photo: 'Photo',
    photoHint: 'The current model can look at it',
    modelNoVision: 'This model cannot view images.',
    hide: 'Hide',
    back: 'Back',
    pluginRepoPh: 'owner/repo or words to search',
    pluginSearch: 'Search',
    pluginInstall: 'Install',
    pluginCheckUpdates: 'Check updates',
    pluginRestart: 'Restart Kerniq to load it.',
    pluginKit: 'Included with Kerniq',
    pluginUpdateReady: 'Update available',
    pluginRemove: 'Remove',
    pluginNoMatches: 'No plugins found.',
    scrollDown: 'Scroll to bottom',
    tempTip: 'Higher temperature makes replies more varied and less predictable. Lower keeps them closer to the most likely wording. 0.7 is the default.',
    providersEmpty: 'No providers yet. Check the base URL under API & model, then refresh.',
    toolsEmpty: 'No tools showed up. If you just added one, restart Kerniq and open this tab again.',
    pluginsEmpty: 'No plugins showed up. Put a plugin folder in plugins/ and it will appear here.',
    attachBlocked: 'Video, audio, and archives cannot be attached. Pick a text or source file instead.',
    fileDialogFailed: 'The folder picker did not open. Type the path in the field instead.',
    settingsFailed: 'Settings did not load. Kerniq may still be starting — wait a moment and open Settings again.',
    downloadFailed: 'That download did not start. Try again, or download a smaller folder.',
    nameTitle: 'Name',

    selectTool: 'Pick a tool on the left.\nIts options show up here.', selectPlugin: 'Pick a plugin to change its options.',
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
    attachFolder: 'Attach a folder',
    attachFolderHint: 'A whole directory, not one file at a time',
    externalRo: 'Attached folders and files are read-only',
    externalRoTip: 'On: the agent can read folders and files attached from outside the workspace, and cannot change them. Off: it can change those attachments. Turning this off asks you to wait 3 seconds.',
    externalTitle: 'Allow changes outside the workspace',
    externalBody: 'Attached folders and files will no longer be read-only. The agent can change them. Wait 3 seconds, then confirm. Anything else keeps them read-only.',
    externalAllow: 'Allow changes',
    dbHost: 'Database host',
    dbPort: 'Database port',
    dbUser: 'Database user',
    dbPassword: 'Database password',
    dbName: 'Database name',
    dbSave: 'Create database and connect',
    dbTip: 'Kerniq creates the MySQL database. You do not create it first. Leave this empty to keep JSON files.',
    dbReady: 'Database is ready. Restart Kerniq so new chats use it.',
    browserSettings: 'These options stay in this browser. The API key is encrypted here and is not saved on the server.',
    windowsOpen: 'From another computer, open one of these addresses. 127.0.0.1 is only this machine.',
    proxyBypass: 'If this PC uses a proxy (for example 127.0.0.1:10809), add the server address to the proxy bypass list. The browser otherwise sends the page to the proxy, so it never arrives. A port test can still succeed.',
    tabInterface: 'Interface',
    interfaceSettings: 'Interface settings',
    prefsLocal: 'These options apply immediately and are stored in this project\'s settings.',
    groupMotion: 'Motion',
    animations: 'Animations',
    animationsTip: 'Transitions and motion effects. "Follow system" respects the reduce-motion setting of your operating system.',
    motionOn: 'On',
    motionAuto: 'Follow system',
    motionOff: 'Off',
    backgroundBlur: 'Background blur',
    backgroundBlurTip: 'On: dialogs blur the page and dim it slightly. Off: the page only dims, with no blur.',
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
    groupStartup: 'Startup',
    uiAutostart: 'Start the UI when you sign in',
    uiAutostartTip: 'The Web UI starts in the background the next time you sign in on this computer. Nothing is sent off the machine. A second copy is not started while this page is open. Windows, Linux, and macOS each get their own sign-in entry. Turn it off here or with kerniq autostart off.',
    groupNotifications: 'Notifications',
    showNotifications: 'Show notifications',
    autoDismissNotifications: 'Automatically dismiss notifications',
    autoDismissTip: 'On: notifications leave on their own. Off: they stay until you close them.',
    agentLabel: 'Agent',
    chats: 'Chats',
    newChatLong: 'New chat',
    editorLabel: 'Editor',
    modeToAgent: 'Switch to agent mode',
    modeToEditor: 'Switch to editor mode',
    groupAppearance: 'Appearance',
    colorTheme: 'Colour theme',
    colorThemeTip: 'Dark keeps colour quiet. Light uses stronger colour. System follows this computer.',
    themeDark: 'Dark',
    themeLight: 'Light',
    themeSystem: 'System',
    emptyChatTitle: 'Nothing in this chat yet',
    emptyChatBody: 'Ask the agent to edit a file, explain the code, or sketch the next change.',
    errorNext: 'You can send the request again. If the provider did not answer, open API & model and check the address.',
    groupLayout: 'Layout',
    workspaceLayout: 'Workspace layout',
    layoutTip: 'Agent only hides the editor: chats on the left, the conversation in the centre.',
    layoutEditorOpt: 'Editor + chat',
    layoutAgentOpt: 'Agent only',
    groupServer: 'Server',
    bindHost: 'Bind host',
    bindHostTip: '127.0.0.1 = only this computer; 0.0.0.0 = every interface. Applied when Kerniq starts.',
    port: 'Port',
    serverMode: 'Server mode',
    serverModeTip: 'One Kerniq for every client. Chats are separated by a cookie. Models stay loaded and new work waits. Listens on 0.0.0.0 after a restart.',
    lanAccess: 'Allow LAN access',
    lanAccessTip: 'Bind 0.0.0.0 for LAN (also enabled by server mode)',
    logLevel: 'Console log level',
    logLevelTip: 'How much the terminal prints while UI runs',
    autoModelLoad: 'Decide load and unload automatically',
    autoModelLoadTip: 'Off: ask when another model is already loaded. On: apply the action below without asking.',
    modelLoadAction: 'When another model is loaded',
    loadAlongsideWorking: 'Load alongside the working model',
    unloadIdleAndLoad: 'Unload the idle model and load',
    unloadWorkingAndLoad: 'Unload the working model and load',
    notifyModelBusy: 'Show a busy notification',
    modelBusyNotice: 'Another model is loaded. This one was not loaded.',
    modelBusyWorking: 'A model is working. It was left loaded.',
    modelBusyIdle: 'An idle model is loaded. This one was not loaded.',
    storageJson: 'No database is connected. Chats and replies are stored in JSON.',
    queuedWork: 'Queued until the working model finishes.',
  },
};
let autoThink = false;     // open reasoning while the model thinks, fold it when it is done
let layoutMode = 'editor';
let desktopLayout = 'editor';
let uiLocale = 'en';
let uiLocaleWanted = 'en';
try { uiLocaleWanted = localStorage.getItem('kerniq.ui_locale') || 'en'; } catch (_) {}
function preferredLocale(explicit) {
  const want = String(explicit == null ? '' : explicit).trim();
  if (want) return want;
  let stored = '';
  try { stored = localStorage.getItem('kerniq.ui_locale') || ''; } catch (_) {}
  return stored || uiLocaleWanted || 'en';
}
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
let runModel = '';
let runSawPlan = false;
if (agentMode !== 'plan' && agentMode !== 'act') agentMode = 'act';
function applyUiLocale(locale) {
  const requested = String(locale || 'en').trim() || 'en';
  uiLocaleWanted = requested;
  uiLocale = (requested !== 'en' && langPacks[requested]) ? requested : 'en';
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
    if (!k) return;
    const label = el.querySelector('.stab-tx');
    if (label) { label.textContent = t(k); el.title = label.textContent; }
    else el.textContent = t(k);
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
  if (ed) ed.placeholder = '';
  const save = document.getElementById('btn-settings-save');
  if (save) save.textContent = t('save');
  const cancel = document.getElementById('btn-settings-cancel');
  if (cancel) cancel.textContent = t('cancel');
  const backBtn = document.getElementById('btn-settings-back');
  if (backBtn) { backBtn.title = t('back'); backBtn.setAttribute('aria-label', t('back')); }
  const benchHide = document.getElementById('bench-note-hide');
  if (benchHide) { benchHide.title = t('hide'); benchHide.setAttribute('aria-label', t('hide')); }
  const und = document.getElementById('btn-undo');
  if (und) { und.title = t('undo'); und.setAttribute('aria-label', t('undo')); }
  const red = document.getElementById('btn-redo');
  if (red) { red.title = t('redo'); red.setAttribute('aria-label', t('redo')); }
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
  if (typeof syncComposePlanLock === 'function') syncComposePlanLock();
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

