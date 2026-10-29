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

function serverModeOn() {
  return !!(window.__SERVER_INFO && window.__SERVER_INFO.server_mode);
}
function debugUnlocked() {
  return !!(window.__SERVER_INFO && window.__SERVER_INFO.debug_unlocked);
}
function applyServerChrome() {
  const server = serverModeOn();
  const debug = debugUnlocked();
  document.documentElement.dataset.server = server ? '1' : '0';
  document.documentElement.dataset.debug = debug ? '1' : '0';
  const dev = document.getElementById('developer-mode-field');
  if (dev) dev.hidden = server && !debug;
  const wsField = document.getElementById('workspace-field');
  if (wsField) wsField.hidden = server && !debug;
  const top = document.getElementById('top-workspace');
  const input = document.getElementById('s-workspace');
  const pick = document.getElementById('btn-pick-ws');
  if (server && !debug) {
    if (top) { top.hidden = true; top.textContent = ''; top.title = ''; }
    if (input) { input.value = ''; input.readOnly = true; }
    if (pick) pick.hidden = true;
    const box = document.getElementById('s-chat-debug');
    if (box) box.checked = false;
    return;
  }
  if (top) top.hidden = false;
  if (pick) pick.hidden = server;
  if (server && debug) {
    const real = String((window.__SERVER_INFO && window.__SERVER_INFO.workspace_real) || '');
    if (input) { input.value = real; input.readOnly = true; }
    if (top) { top.textContent = real || 'debug'; top.title = real; }
  }
}
function applyServerWorkspace() {
  applyServerChrome();
}
function paintWorkspaceLabel(fromServer) {
  if (serverModeOn()) {
    applyServerChrome();
    return;
  }
  const top = document.getElementById('top-workspace');
  const input = document.getElementById('s-workspace');
  if (!top) return;
  const typed = input && input.value ? String(input.value) : '';
  let text = fromServer || typed || './workspace';
  const absolute = text.startsWith('/') || /^[A-Za-z]:[\\/]/.test(text);
  const typedAbsolute = typed.startsWith('/') || /^[A-Za-z]:[\\/]/.test(typed);
  if (absolute && !typedAbsolute) text = typed || './workspace';
  top.textContent = text;
  top.title = text;
}
function lockServerModelField() {
  const input = document.getElementById('s-base-url');
  if (!input) return;
  if (input.readOnly) {
    input.readOnly = false;
    input.title = '';
  }
}
function setEditorMark(fileOpen) {
  const mark = document.getElementById('editor-mark');
  if (mark) mark.hidden = !!fileOpen;
}
function announceServer(info) {
  window.__SERVER_INFO = info || window.__SERVER_INFO || {};
  applyServerWorkspace();
  lockServerModelField();
  if (!info) return;
  let seen = false;
  try { seen = sessionStorage.getItem('kerniq-lan-note') === '1'; } catch (_) {}
  if (seen) return;
  try { sessionStorage.setItem('kerniq-lan-note', '1'); } catch (_) {}
  const publicBind = !!(info.server_mode || info.bind_host === '0.0.0.0' || info.bind_host === '::');
  if (publicBind && (info.urls || []).length) {
    const urls = (info.urls || []).filter(url => String(url).indexOf('127.0.0.1') < 0);
    const shown = (urls.length ? urls : info.urls).join('   ');
    const extra = info.firewall_note ? (' ' + info.firewall_note) : '';
    toast(t('windowsOpen') + ' ' + shown + extra + ' ' + t('proxyBypass'), false, '', true);
  }
  if (info.storage_warning) toast(t('storageJson'), false, '', true);
  if (info.disk && info.disk.message && (info.disk.near || info.disk.full)) {
    toast(info.disk.message, !!info.disk.full, '', true);
  }
}
function _cookieMap() {
  const map = {};
  String(document.cookie || '').split(';').forEach(part => {
    const idx = part.indexOf('=');
    if (idx < 0) return;
    map[part.slice(0, idx).trim()] = part.slice(idx + 1).trim();
  });
  return map;
}
function writeSettingsCookie(text) {
  const size = 900;
  const parts = [];
  for (let i = 0; i < text.length; i += size) parts.push(text.slice(i, i + size));
  const clear = (name) => { document.cookie = name + '=; Path=/; Max-Age=0; SameSite=Lax'; };
  if (parts.length > 6) {
    for (let i = 0; i < 8; i++) clear('kerniq_s' + i);
    document.cookie = 'kerniq_sn=local; Path=/; Max-Age=31536000; SameSite=Lax';
    return;
  }
  for (let i = 0; i < 8; i++) {
    if (i < parts.length) {
      document.cookie = 'kerniq_s' + i + '=' + encodeURIComponent(parts[i]) + '; Path=/; Max-Age=31536000; SameSite=Lax';
    } else {
      clear('kerniq_s' + i);
    }
  }
  document.cookie = 'kerniq_sn=' + parts.length + '; Path=/; Max-Age=31536000; SameSite=Lax';
}
function readSettingsCookie() {
  const map = _cookieMap();
  if (map.kerniq_sn === 'local') return null;
  const n = Number(map.kerniq_sn || 0);
  if (!n) return null;
  let text = '';
  for (let i = 0; i < n; i++) {
    if (!map['kerniq_s' + i]) return null;
    try { text += decodeURIComponent(map['kerniq_s' + i]); }
    catch (_) { return null; }
  }
  try { return JSON.parse(text); } catch (_) { return null; }
}
async function settingsCryptoKey() {
  const name = 'kerniq.settings.key';
  let raw = '';
  try { raw = localStorage.getItem(name) || ''; } catch (_) { raw = ''; }
  if (!raw) {
    const bytes = crypto.getRandomValues(new Uint8Array(32));
    raw = btoa(String.fromCharCode.apply(null, bytes));
    try { localStorage.setItem(name, raw); } catch (_) {}
  }
  const bin = Uint8Array.from(atob(raw), c => c.charCodeAt(0));
  return crypto.subtle.importKey('raw', bin, 'AES-GCM', false, ['encrypt', 'decrypt']);
}
async function sealToken(plain) {
  if (!plain || !window.crypto || !crypto.subtle) return '';
  const key = await settingsCryptoKey();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const enc = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, new TextEncoder().encode(plain));
  const blob = new Uint8Array(iv.length + enc.byteLength);
  blob.set(iv, 0);
  blob.set(new Uint8Array(enc), iv.length);
  let text = '';
  blob.forEach(b => { text += String.fromCharCode(b); });
  return btoa(text);
}
async function openToken(sealed) {
  if (!sealed || !window.crypto || !crypto.subtle) return '';
  try {
    const key = await settingsCryptoKey();
    const blob = Uint8Array.from(atob(sealed), c => c.charCodeAt(0));
    const dec = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: blob.slice(0, 12) }, key, blob.slice(12));
    return new TextDecoder().decode(dec);
  } catch (_) {
    return '';
  }
}
async function writeBrowserSettings(parts) {
  const apiCopy = Object.assign({}, parts.api || {});
  const plain = apiCopy.api_token || '';
  delete apiCopy.api_token_sealed;
  const sealed = plain ? await sealToken(plain) : '';
  apiCopy.api_token = '';
  apiCopy.api_token_sealed = sealed || '';
  const blob = {
    agent: parts.agent || {},
    api: apiCopy,
    prompt: parts.prompt || {},
    chat: parts.chat || {},
    interface: parts.interface || {},
  };
  const text = JSON.stringify(blob);
  try { localStorage.setItem('kerniq.settings.blob', text); } catch (_) {}
  try {
    if (plain && !sealed) localStorage.setItem('kerniq.settings.token', plain);
    else localStorage.removeItem('kerniq.settings.token');
  } catch (_) {}
  writeSettingsCookie(text);
}
async function readBrowserSettings() {
  const cookieBlob = readSettingsCookie();
  let localBlob = null;
  try { localBlob = JSON.parse(localStorage.getItem('kerniq.settings.blob') || 'null'); } catch (_) { localBlob = null; }
  const blob = (cookieBlob && typeof cookieBlob === 'object') ? cookieBlob : localBlob;
  if (!blob || typeof blob !== 'object') return null;
  const localApi = (localBlob && localBlob.api) || {};
  blob.api = Object.assign({}, blob.api || {});
  if (!blob.api.api_token_sealed && localApi.api_token_sealed) {
    blob.api.api_token_sealed = localApi.api_token_sealed;
  }
  if (blob.api.api_token_sealed) blob.api.api_token = await openToken(blob.api.api_token_sealed);
  if (!blob.api.api_token) {
    try { blob.api.api_token = localStorage.getItem('kerniq.settings.token') || ''; } catch (_) {}
  }
  if (!blob.api.base_url && localApi.base_url) blob.api.base_url = localApi.base_url;
  return blob;
}
function askExternalWrite() {
  return new Promise(resolve => {
    const bg = document.getElementById('external-modal');
    const ok = document.getElementById('external-ok');
    const cancel = document.getElementById('external-cancel');
    if (!bg || !ok || !cancel) { resolve(false); return; }
    const title = document.getElementById('external-title');
    const text = document.getElementById('external-text');
    if (title) title.textContent = t('externalTitle');
    if (text) text.textContent = t('externalBody');
    cancel.textContent = translate('Cancel');
    let left = 3;
    let settled = false;
    let timer = null;
    const paint = () => {
      ok.disabled = left > 0;
      ok.textContent = left > 0 ? String(left) : t('externalAllow');
    };
    const finish = (yes) => {
      if (settled) return;
      settled = true;
      if (timer) clearInterval(timer);
      bg.classList.remove('on');
      if (!document.querySelector('.modal-bg.on')) document.body.classList.remove('modal-open');
      document.removeEventListener('keydown', onKey, true);
      resolve(!!yes);
    };
    const onKey = (e) => {
      if (e.key === 'Escape' || e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); finish(false); }
    };
    ok.onclick = (e) => { e.preventDefault(); e.stopPropagation(); if (!ok.disabled) finish(true); };
    cancel.onclick = (e) => { e.preventDefault(); finish(false); };
    bg.onclick = (e) => { if (e.target === bg) finish(false); };
    document.addEventListener('keydown', onKey, true);
    bg.classList.add('on');
    document.body.classList.add('modal-open');
    paint();
    timer = setInterval(() => {
      left -= 1;
      if (left <= 0) { clearInterval(timer); left = 0; }
      paint();
    }, 1000);
  });
}

async function loadSettings() {
  settingsHydrating = true;
  try {
  const loaded = await api('/api/settings');
  if (!window.__SERVER_INFO) {
    try { window.__SERVER_INFO = await api('/api/server/info'); } catch (_) {}
  }
  if (!loaded || loaded.error || !loaded.agent) {
    toast((loaded && loaded.error) || t('settingsFailed'), true);
  }
  settings = (loaded && loaded.agent) ? loaded : (settings || {});
  if (serverModeOn()) {
    const local = await readBrowserSettings();
    if (local) {
      ['chat', 'agent', 'api', 'prompt', 'interface'].forEach(section => {
        if (local[section] && typeof local[section] === 'object') {
          settings[section] = Object.assign({}, settings[section] || {}, local[section]);
        }
      });
    }
    if (settings.api) settings.api.api_token = (settings.api.api_token || '');
  }
  settingsSnapshot = JSON.stringify(settings);
  applyInterface(settings.interface || {});
  const a = settings.agent || {}, apiS = settings.api || {}, p = settings.prompt || {};
  document.getElementById('s-workspace').value = serverModeOn() ? '' : (a.workspace || './workspace');
  document.getElementById('top-workspace').textContent = serverModeOn() ? '' : (a.workspace || './workspace');
  applyServerChrome();
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
  if (window.KerniqHostFreedom) {
    KerniqHostFreedom.sync({ server: serverModeOn(), enabled: !serverModeOn() && !!a.host_freedom });
  }
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
  const extRo = document.getElementById('s-external-ro');
  if (extRo) extRo.checked = ch.read_only_external_attachments !== false;
  const autoAct = document.getElementById('s-auto-act');
  if (autoAct) autoAct.checked = ch.auto_act_after_plan !== false;
  const modeAutoEl = document.getElementById('s-mode-auto');
  if (modeAutoEl) modeAutoEl.checked = ch.mode_auto !== false;
  modeAuto = ch.mode_auto !== false;
  const composeEl = document.getElementById('s-compose-plan');
  if (composeEl) composeEl.checked = ch.compose_plan !== false;
  syncComposePlanLock();
  applyModeSwitch();
  const splitEl = document.getElementById('s-split-models');
  const actField = document.getElementById('act-model-field');
  const actInput = document.getElementById('s-act-model');
  const apiCfg = settings.api || {};
  if (splitEl) splitEl.checked = !!apiCfg.split_models;
  if (actField) actField.hidden = !(apiCfg.split_models);
  if (actInput && !actInput.value) actInput.value = apiCfg.act_model || apiCfg.model || '';
  const sortEl = document.getElementById('s-model-sort');
  const sortDirEl = document.getElementById('s-model-sort-dir');
  if (sortEl) sortEl.value = apiCfg.model_sort || 'name';
  if (sortDirEl) sortDirEl.value = apiCfg.model_sort_dir || 'asc';
  const autoLoad = document.getElementById('s-auto-load');
  const loadAction = document.getElementById('s-load-action');
  if (autoLoad) autoLoad.checked = !!apiCfg.auto_model_load;
  if (loadAction) loadAction.value = savedLoadAction();
  syncAutoLoad();
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
let modelsInflightKey = '';
let modelsCache = null;
let modelsCacheAt = 0;
let modelsCacheKey = '';
let modelChoices = [];
function liveApiSettings() {
  const apiS = Object.assign({}, (settings && settings.api) || {});
  const providerEl = document.getElementById('s-provider');
  const urlEl = document.getElementById('s-base-url');
  const tokenEl = document.getElementById('s-api-token');
  const modelEl = document.getElementById('s-model');
  if (providerEl && providerEl.value) apiS.provider = providerEl.value;
  if (urlEl) apiS.base_url = urlEl.value;
  if (tokenEl) apiS.api_token = tokenEl.value;
  if (modelEl) apiS.model = modelEl.value;
  delete apiS.api_token_sealed;
  return apiS;
}
function modelProbe() {
  const probe = liveApiSettings();
  const body = { provider: probe.provider || '' };
  const spec = providerCatalog.find(p => p.id === body.provider);
  const keys = new Set(((spec && spec.fields) || []).map(f => f.key));
  const urlEl = document.getElementById('s-base-url');
  const tokenEl = document.getElementById('s-api-token');
  if (!spec) {
    if (probe.base_url) body.base_url = probe.base_url;
    if (probe.api_token) body.api_token = probe.api_token;
    return body;
  }
  if (keys.has('base_url')) body.base_url = urlEl ? (urlEl.value || '') : (probe.base_url || '');
  if (keys.has('api_token')) body.api_token = tokenEl ? (tokenEl.value || '') : (probe.api_token || '');
  return body;
}
async function fetchModels() {
  const body = modelProbe();
  const key = [body.provider || '', body.base_url || '', body.api_token || ''].join('\n');
  const now = Date.now();
  if (modelsCache && modelsCacheKey === key && now - modelsCacheAt < 1500) return modelsCache;
  if (modelsInflight && modelsInflightKey === key) return modelsInflight;
  modelsInflightKey = key;
  modelsInflight = fetch('/api/models', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(8000),
  })
    .then(r => r.text())
    .then(text => {
      try { return JSON.parse(text); } catch { return { models: [], reachable: false, error: text }; }
    })
    .catch(() => ({ models: [], reachable: false, error: 'timed out' }))
    .then(data => {
      modelsCache = data;
      modelsCacheKey = key;
      modelsCacheAt = Date.now();
      return data;
    }).finally(() => { modelsInflight = null; modelsInflightKey = ''; });
  return modelsInflight;
}
function modelParamCount(row) {
  const text = String((row && (row.id || row.name)) || '').toLowerCase();
  const moe = text.match(/(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*b/);
  if (moe) return parseFloat(moe[1]) * parseFloat(moe[2]);
  const hit = text.match(/(\d+(?:\.\d+)?)\s*b\b/);
  return hit ? parseFloat(hit[1]) : -1;
}
function modelSortValue() {
  const el = document.getElementById('s-model-sort');
  const saved = (settings && settings.api && settings.api.model_sort) || 'name';
  const value = el && el.value ? el.value : saved;
  return value === 'params' || value === 'context' ? value : 'name';
}
function modelSortDir() {
  const el = document.getElementById('s-model-sort-dir');
  const saved = (settings && settings.api && settings.api.model_sort_dir) || 'asc';
  const value = el && el.value ? el.value : saved;
  return value === 'desc' ? 'desc' : 'asc';
}
function sortModelRows(rows) {
  const key = modelSortValue();
  const dir = modelSortDir() === 'desc' ? -1 : 1;
  return rows.slice().sort((a, b) => {
    let cmp = 0;
    if (key === 'params') cmp = modelParamCount(a) - modelParamCount(b);
    else if (key === 'context') cmp = (contextOfRow(a) || 0) - (contextOfRow(b) || 0);
    else cmp = String(a.id || a.name || '').localeCompare(String(b.id || b.name || ''));
    if (cmp === 0) cmp = String(a.id || '').localeCompare(String(b.id || ''));
    return cmp * dir;
  });
}
function activeContextLimit() {
  const picked = String(footerModelId() || '').trim();
  const row = picked ? modelRow(picked, modelChoices) : null;
  if (row && contextOfRow(row)) return contextOfRow(row);
  const auto = pickAutoModel(modelChoices);
  const autoRow = auto ? modelRow(auto, modelChoices) : null;
  return contextOfRow(autoRow);
}
function clampMaxTokensField() {
  const input = document.getElementById('s-api-max-tokens');
  if (!input) return;
  const limit = activeContextLimit();
  if (!limit) return;
  input.max = String(limit);
  input.placeholder = 'auto (' + limit + ')';
  if (input.value !== '' && Number(input.value) > limit) {
    input.value = String(limit);
    input.classList.add('clamped');
    setTimeout(() => input.classList.remove('clamped'), 900);
  }
}
function fillModelMenu(filter) {
  const menu = document.getElementById('model-menu');
  const input = document.getElementById('s-model');
  if (!menu) return;
  const q = String(filter || '').trim().toLowerCase();
  menu.innerHTML = '';
  const rows = sortModelRows(modelChoices.filter(m => !q || String(m.id || '').toLowerCase().includes(q) || String(m.name || '').toLowerCase().includes(q)));
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
      if (typeof paintModelFooter === 'function') paintModelFooter(m.id || '', modelChoices, true);
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
document.getElementById('s-auto-load')?.addEventListener('change', () => {
  syncAutoLoad();
  markSettingsDirty();
});
document.getElementById('s-load-action')?.addEventListener('change', () => markSettingsDirty());
document.getElementById('s-external-ro')?.addEventListener('change', async (ev) => {
  const box = ev.target;
  if (box.checked) { markSettingsDirty(); return; }
  const ok = await askExternalWrite();
  if (!ok) { box.checked = true; return; }
  markSettingsDirty();
});
document.getElementById('btn-db-save')?.addEventListener('click', async () => {
  const host = document.getElementById('db-host')?.value || '';
  if (!host.trim()) { toast(t('dbTip'), true); return; }
  const r = await api('/api/server/database', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      host: host.trim(),
      port: Number(document.getElementById('db-port')?.value || 3306),
      user: document.getElementById('db-user')?.value || '',
      password: document.getElementById('db-pass')?.value || '',
      name: document.getElementById('db-name')?.value || 'kerniq',
    }),
  });
  const pass = document.getElementById('db-pass');
  if (pass) pass.value = '';
  if (!r || r.error) { toast((r && r.error) || t('settingsFailed'), true); return; }
  toast(t('dbReady'));
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
  paintModelFooter(footerModelId(), modelChoices, !(data.error || data.reachable === false));
  sel.oninput = () => {
    markSettingsDirty();
    paintModelFooter(sel.value.trim(), modelChoices, !(data.error || data.reachable === false));
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
  if (!serverModeOn() && ui && ui.values && ui.values.ui_locale != null) applyUiLocale(preferredLocale(ui.values.ui_locale));
  if (ui && ui.values && ui.values.show_footer === false) {
    footerEnabled = false;
    document.getElementById('app-footer').classList.add('hidden');
  }  refreshInterfaceControls();
  syncComposePlanLock();
}

let expandedPacks = {};
let selectedPack = null;
let draftPacks = {};
function planComposeAvailable() {
  const tools = componentsCache.tools || [];
  if (!tools.length) return true;
  const plan = tools.find(t => t.name === 'update_plan');
  if (!plan) return false;
  const draft = draftTools[plan.id] || { enabled: plan.enabled !== false, values: { ...(plan.values || {}) } };
  if (draft.enabled === false) return false;
  if (draft.values && Object.prototype.hasOwnProperty.call(draft.values, 'include_in_plan')) {
    return !!draft.values.include_in_plan;
  }
  return plan.include_in_plan !== false;
}
const COMPOSE_PLAN_TIP = 'When this is on, the first model turn can only edit the TODO. It is forced off when the plan tool is missing, disabled, or not included in Plan mode.';
const COMPOSE_PLAN_LOCK = 'Build a plan is unavailable because the plan tool is missing, disabled, or not included in Plan mode.';
function syncComposePlanLock() {
  const el = document.getElementById('s-compose-plan');
  if (!el) return;
  const ok = planComposeAvailable();
  el.disabled = !ok;
  if (!ok) el.checked = false;
  const line = el.closest('.check-line');
  if (line) line.classList.toggle('is-locked', !ok);
  const tip = document.getElementById('compose-plan-tip');
  const text = translate(ok ? COMPOSE_PLAN_TIP : COMPOSE_PLAN_LOCK);
  el.title = ok ? '' : text;
  if (tip) tip.setAttribute('data-tip', text);
}
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
      draftPacks[k] = { forceEnabled: !!e.target.checked };
      by[k].forEach(t => {
        draftTools[t.id] = draftTools[t.id] || { enabled: true, values: {} };
        draftTools[t.id].enabled = e.target.checked;
      });
      markSettingsDirty();
      syncComposePlanLock();
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
          if (draftPacks[k]) draftPacks[k].forceEnabled = null;
          markSettingsDirty();
          syncComposePlanLock();
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
  const pack = (componentsCache.packs || []).find(p => p.id === cat);
  const fields = (pack && pack.schema && pack.schema.fields) || [];
  let html = `<h3>${esc((pack && pack.name) || cat)}</h3><div class="hint">${list.length}</div>`;
  if (!fields.length) html += '<div class="empty">No pack settings</div>';
  fields.forEach(f => {
    const vals = list.map(tool => {
      const draft = draftTools[tool.id] || { values: {} };
      if (draft.values && draft.values[f.key] !== undefined) return draft.values[f.key];
      return f.default;
    });
    const mixed = vals.length > 1 && vals.some(v => v !== vals[0]);
    const val = mixed ? '' : vals[0];
    const label = translate(f.label || f.key);
    if (f.type === 'bool') {
      html += `<label class="field-row-check"><input type="checkbox" class="soft-check" data-pk="${esc(f.key)}" ${!mixed && val ? 'checked' : ''}/><span>${esc(label)}</span></label>`;
    } else {
      html += `<div class="field"><label class="lbl">${esc(label)}</label>`;
      html += `<input type="${f.type === 'int' || f.type === 'float' ? 'number' : 'text'}" data-pk="${esc(f.key)}" value="${esc(val ?? '')}"/>`;
      html += `</div>`;
    }
  });
  panel.innerHTML = html;
  fields.forEach(f => {
    if (f.type !== 'bool') return;
    const inp = panel.querySelector(`[data-pk="${f.key}"]`);
    if (!inp) return;
    const vals = list.map(tool => {
      const draft = draftTools[tool.id] || { values: {} };
      if (draft.values && draft.values[f.key] !== undefined) return !!draft.values[f.key];
      return !!f.default;
    });
    if (vals.length > 1 && vals.some(v => v !== vals[0])) inp.indeterminate = true;
  });
  panel.querySelectorAll('[data-pk]').forEach(inp => {
    inp.addEventListener(inp.type === 'checkbox' ? 'change' : 'input', () => {
      const value = inp.type === 'checkbox' ? inp.checked : (inp.type === 'number' ? Number(inp.value) : inp.value);
      if (inp.type === 'checkbox') inp.indeterminate = false;
      list.forEach(tool => {
        draftTools[tool.id] = draftTools[tool.id] || { enabled: true, values: {} };
        draftTools[tool.id].values = draftTools[tool.id].values || {};
        draftTools[tool.id].values[inp.dataset.pk] = value;
      });
      if (inp.dataset.pk === 'include_in_plan') syncComposePlanLock();
      markSettingsDirty();
    });
  });
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
    const label = translate(f.label || '');
    if (f.type === 'bool') {
      html += `<label class="field-row-check"><input type="checkbox" class="soft-check" data-fk="${esc(f.key)}" ${val ? 'checked' : ''}/><span>${esc(label)}</span></label>`;
    } else if (f.type === 'path') {
      html += `<div class="field"><label class="lbl">${esc(label)}</label><div class="path-pick"><input class="input-std" data-fk="${esc(f.key)}" value="${esc(val ?? '')}"/><button type="button" class="ghost" data-pick="${esc(f.key)}">${esc(translate('Browse…'))}</button></div></div>`;
    } else {
      html += `<div class="field"><label class="lbl">${esc(label)}</label>`;
      html += `<input type="${f.type === 'int' || f.type === 'float' ? 'number' : 'text'}"${numAttrs(f)} data-fk="${esc(f.key)}" value="${esc(val ?? '')}"/>`;
      html += `</div>`;
    }
  });
  panel.innerHTML = html;
  panel.querySelectorAll('[data-fk]').forEach(inp => {
    inp.addEventListener(inp.type === 'checkbox' ? 'change' : 'input', () => {
      draftTools[id].values[inp.dataset.fk] = inp.type === 'checkbox' ? inp.checked : (inp.type === 'number' ? Number(inp.value) : inp.value);
      if (inp.dataset.fk === 'include_in_plan') syncComposePlanLock();
      markSettingsDirty();
    });
  });
  panel.querySelectorAll('[data-pick]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const picked = await api('/api/fs/pick_folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!picked || picked.cancelled) return;
      if (picked.error) { toast(String(picked.error), true); return; }
      const input = panel.querySelector('[data-fk="' + btn.dataset.pick + '"]');
      if (input && picked.path) {
        input.value = picked.path;
        draftTools[id] = draftTools[id] || { enabled: true, values: {} };
        draftTools[id].values[btn.dataset.pick] = picked.path;
        markSettingsDirty();
      }
    });
  });
}
let showHiddenPlugins = false;
let pluginUpdateMap = {};
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
    const news = pluginUpdateMap[p.id];
    if (news && news.update) {
      const up = document.createElement('span');
      up.className = 'plugin-badge hide';
      up.textContent = t('pluginUpdateReady');
      badges.appendChild(up);
    }
    const name = document.createElement('span');
    name.className = 'tname';
    name.textContent = p.name || p.id;
    row.appendChild(name);
    row.appendChild(badges);
    row.onclick = () => openPlugin(p.id);
    el.appendChild(row);
  });
}
function fieldVisible(field, values, fields) {
  if (field.slot == null) return true;
  const counter = (fields || []).find(item => item.key === 'slot_count');
  const raw = values && values.slot_count != null ? values.slot_count : (counter && counter.default);
  const count = Math.max(1, Math.min(3, Number(raw || 1)));
  return Number(field.slot) <= count;
}
function openPlugin(id) {
  if (id === 'plugin_web_ui') {
    selectedPluginId = null;
    renderPluginsList();
    closePluginModal();
    openSettingsAt('interface', null);
    return;
  }
  selectedPluginId = id;
  renderPluginsList();
  const p = (componentsCache.plugins || []).find(x => x.id === id);
  const bg = document.getElementById('plugin-modal');
  const title = document.getElementById('plugin-modal-title');
  const body = document.getElementById('plugin-modal-body');
  if (!p || !bg || !body) return;
  if (title) title.textContent = p.name || p.id;
  body.innerHTML = pluginFormHtml(p);
  bindPluginForm(body, p);
  bg.classList.add('on');
  document.body.classList.add('modal-open');
}
function closePluginModal() {
  const bg = document.getElementById('plugin-modal');
  if (bg) bg.classList.remove('on');
  document.body.classList.remove('modal-open');
  if (selectedPluginId) {
    selectedPluginId = null;
    renderPluginsList();
  }
}
function refreshOpenPlugin() {
  const bg = document.getElementById('plugin-modal');
  if (selectedPluginId && bg && bg.classList.contains('on')) openPlugin(selectedPluginId);
}
function fieldBlock(f, draft) {
  const val = draft.values[f.key] !== undefined ? draft.values[f.key] : f.default;
  const label = translate(f.label || '');
  const tip = translate(f.description || '');
  const tipHtml = tip ? '<span class="info-tip" tabindex="0" data-tip="' + esc(tip) + '">i</span>' : '';
  if (f.type === 'bool') {
    return '<div class="field field-check"><label class="check-line"><input type="checkbox" class="soft-check" data-fk="' + esc(f.key) + '"' + (val ? ' checked' : '') + '/><span>' + esc(label) + '</span>' + tipHtml + '</label></div>';
  }
  let control = '';
  if (f.type === 'select' && f.options && f.options.length) {
    control = '<select data-fk="' + esc(f.key) + '" class="input-std">';
    f.options.forEach(o => {
      const ov = o.value != null ? o.value : o;
      const ol = translate(o.label != null ? o.label : String(ov));
      control += '<option value="' + esc(ov) + '"' + (String(val) === String(ov) ? ' selected' : '') + '>' + esc(ol) + '</option>';
    });
    control += '</select>';
  } else if (f.type === 'text') {
    control = '<textarea class="input-std" data-fk="' + esc(f.key) + '">' + esc(val ?? '') + '</textarea>';
  } else if (f.type === 'path') {
    control = '<div class="path-pick"><input class="input-std" data-fk="' + esc(f.key) + '" value="' + esc(val ?? '') + '"/><button type="button" class="ghost" data-pick="' + esc(f.key) + '">' + esc(translate('Browse…')) + '</button></div>';
  } else {
    control = '<input class="input-std" type="' + (f.type === 'int' || f.type === 'float' ? 'number' : 'text') + '"' + numAttrs(f) + ' data-fk="' + esc(f.key) + '" value="' + esc(val ?? '') + '"/>';
  }
  return '<div class="field"><label class="lbl">' + esc(label) + tipHtml + '</label>' + control + '</div>';
}
function pluginFormHtml(p) {
  const draft = draftPlugins[p.id] || { values: Object.assign({}, p.values || {}) };
  const fields = ((p.schema && p.schema.fields) || []).filter(f => fieldVisible(f, draft.values, p.schema && p.schema.fields));
  let html = '';
  const actions = p.actions || [];
  if (actions.length) {
    html += '<div class="plugin-actions">';
    actions.forEach(action => {
      html += '<button type="button" class="save-active" data-action="' + esc(action.id) + '">' + esc(translate(action.label || action.id)) + '</button>';
    });
    html += '</div>';
  }
  const groups = [];
  fields.forEach(f => {
    const key = f.group || 'general';
    let group = groups.find(item => item.key === key);
    if (!group) { group = { key: key, fields: [] }; groups.push(group); }
    group.fields.push(f);
  });
  if (groups.length) html += '<div class="set-cols">';
  groups.forEach(group => {
    const texts = group.fields.filter(f => f.type === 'text');
    const shorts = group.fields.filter(f => f.type !== 'text');
    const wide = texts.length > 0 || shorts.length > 1;
    html += '<div class="set-group' + (wide ? ' span-2' : '') + '">';
    if (group.key !== 'general') {
      const title = group.key.replace(/_/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase());
      html += '<h3>' + esc(translate(title)) + '</h3>';
    }
    if (shorts.length > 1) html += '<div class="field-grid">';
    shorts.forEach(f => { html += fieldBlock(f, draft); });
    if (shorts.length > 1) html += '</div>';
    texts.forEach(f => { html += fieldBlock(f, draft); });
    html += '</div>';
  });
  if (groups.length) html += '</div>';
  if (!fields.length && !actions.length) html += '<div class="empty">No settings</div>';
  if (!p.source || p.source.kind !== 'kit') {
    html += '<div class="plugin-actions"><button type="button" class="ghost" data-plugin-remove="' + esc(p.id) + '">' + esc(t('pluginRemove')) + '</button></div>';
  }
  return html;
}
function bindPluginForm(panel, p) {
  const id = p.id;
  if (!draftPlugins[id]) draftPlugins[id] = { values: Object.assign({}, p.values || {}) };
  const redraw = () => { panel.innerHTML = pluginFormHtml(p); bindPluginForm(panel, p); };
  panel.querySelectorAll('[data-fk]').forEach(inp => {
    const ev = (inp.type === 'checkbox' || inp.tagName === 'SELECT') ? 'change' : 'input';
    inp.addEventListener(ev, () => {
      let v;
      if (inp.type === 'checkbox') v = inp.checked;
      else if (inp.type === 'number') v = Number(inp.value);
      else v = inp.value;
      draftPlugins[id].values[inp.dataset.fk] = v;
      if (inp.dataset.fk === 'slot_count') redraw();
      else {
        if (inp.dataset.fk === 'target_mode' || inp.dataset.fk === 'trigger_percent' || inp.dataset.fk === 'target_percent') syncCompactLimit(panel);
        markSettingsDirty();
      }
    });
  });
  panel.querySelectorAll('[data-pick]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const picked = await api('/api/fs/pick_folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      if (!picked || picked.cancelled) return;
      if (picked.error) { toast(String(picked.error), true); return; }
      const input = panel.querySelector('[data-fk="' + btn.dataset.pick + '"]');
      if (input && picked.path) {
        input.value = picked.path;
        draftPlugins[id].values[btn.dataset.pick] = picked.path;
        markSettingsDirty();
      }
    });
  });
  panel.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', () => runPluginAction(id, btn.dataset.action, btn));
  });
  syncCompactLimit(panel);
}
function liveKerniqSettings() {
  const snap = {
    api: (typeof liveApiSettings === 'function') ? liveApiSettings() : Object.assign({}, (settings && settings.api) || {}),
    agent: Object.assign({}, (settings && settings.agent) || {}),
    chat: Object.assign({}, (settings && settings.chat) || {}),
    prompt: Object.assign({}, (settings && settings.prompt) || {}),
  };
  const num = (id) => {
    const el = document.getElementById(id);
    if (!el || el.value === '') return null;
    const n = Number(el.value);
    return isFinite(n) ? n : null;
  };
  const iter = num('s-max-iter');
  if (iter != null) snap.agent.max_iterations = iter;
  const timeout = document.getElementById('s-timeout');
  const unit = document.getElementById('s-timeout-unit');
  if (timeout && timeout.value !== '' && unit) {
    const n = Number(timeout.value) || 0;
    snap.agent.timeout_seconds = unit.value === 'm' ? n * 60 : unit.value === 'h' ? n * 3600 : n;
  }
  const retries = num('s-loop-retries');
  if (retries != null) snap.agent.loop_retries = retries;
  const temp = num('s-api-temp');
  if (temp != null) snap.api.temperature = temp;
  const maxTok = document.getElementById('s-api-max-tokens');
  if (maxTok) snap.api.max_tokens = maxTok.value === '' ? null : Number(maxTok.value);
  const split = document.getElementById('s-split-models');
  if (split) snap.api.split_models = !!split.checked;
  const act = document.getElementById('s-act-model');
  if (act) snap.api.act_model = act.value || '';
  const bin = document.getElementById('s-binary-path');
  if (bin) snap.api.binary_path = bin.value || '';
  const modeAutoEl = document.getElementById('s-mode-auto');
  if (modeAutoEl) snap.chat.mode_auto = !!modeAutoEl.checked;
  const compose = document.getElementById('s-compose-plan');
  if (compose) snap.chat.compose_plan = !!compose.checked && (typeof planComposeAvailable !== 'function' || planComposeAvailable());
  const autoAct = document.getElementById('s-auto-act');
  if (autoAct) snap.chat.auto_act_after_plan = !!autoAct.checked;
  const lang = document.getElementById('s-chat-lang');
  if (lang && lang.value) snap.chat.response_language = lang.value;
  const streaming = document.getElementById('s-chat-streaming');
  if (streaming) snap.chat.streaming = !!streaming.checked;
  return snap;
}
let benchHiddenKey = '';
let benchLastKey = '';
function benchKey(state) {
  if (!state || !state.status || state.status === 'idle') return '';
  return [state.status, state.index || '', state.model || '', state.slot || '', state.error || ''].join('|');
}
function benchNote(state) {
  const el = document.getElementById('bench-note');
  const text = document.getElementById('bench-note-text');
  if (!el || !text) return;
  const status = state && state.status;
  const key = benchKey(state);
  benchLastKey = key;
  if (!status || status === 'idle') { el.hidden = true; el.className = 'bench-note'; benchHiddenKey = ''; return; }
  if (benchHiddenKey && benchHiddenKey === key) { el.hidden = true; return; }
  if (benchHiddenKey && benchHiddenKey !== key) benchHiddenKey = '';
  el.hidden = false;
  el.className = 'bench-note on' + (status === 'done' ? ' done' : status === 'failed' ? ' failed' : '');
  if (status === 'running') {
    const model = state.model ? ' · ' + state.model : '';
    const slot = state.slot ? ' · ' + translate('task') + ' ' + state.slot + '/' + (state.slots || '') : '';
    const index = state.total ? ' (' + (state.index || 0) + '/' + state.total + ')' : '';
    text.textContent = translate('Benchmark is running in the background.') + index + model + slot;
  } else if (status === 'done') {
    text.textContent = translate('Benchmark finished') + (state.folder ? ' · ' + state.folder : '');
  } else {
    text.textContent = translate('Benchmark failed') + (state.error ? ': ' + state.error : '');
  }
}
document.getElementById('bench-note-hide')?.addEventListener('click', () => {
  benchHiddenKey = benchLastKey || 'hidden';
  const el = document.getElementById('bench-note');
  if (el) { el.hidden = true; el.className = 'bench-note'; }
});
let benchWatchTimer = 0;
async function watchBenchmark() {
  if (benchWatchTimer) { clearTimeout(benchWatchTimer); benchWatchTimer = 0; }
  const tick = async () => {
    let state = null;
    try { state = await api('/api/benchmark/active'); } catch (e) { state = null; }
    let id = '';
    try { id = sessionStorage.getItem('kerniq_benchmark_job') || ''; } catch (_) {}
    if (id) {
      try {
        const job = await api('/api/plugins/job?id=' + encodeURIComponent(id));
        if (job && job.status && job.status !== 'running' && (!state || state.status === 'running' || state.status === 'idle')) {
          state = { status: job.status === 'done' ? 'done' : 'failed', error: job.error || '', folder: (job.result && job.result.folder) || '' };
        }
      } catch (_) {}
    }
    benchNote(state);
    const running = state && state.status === 'running';
    if (!running) {
      try { sessionStorage.removeItem('kerniq_benchmark_job'); } catch (_) {}
      if (state && (state.status === 'done' || state.status === 'failed')) {
        benchWatchTimer = setTimeout(() => benchNote(null), 12000);
      }
      return;
    }
    benchWatchTimer = setTimeout(tick, 2000);
  };
  tick();
}
async function runPluginAction(pluginId, actionId, button) {
  if (button) button.disabled = true;
  const draft = draftPlugins[pluginId];
  if (draft) {
    await api('/api/component/settings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'plugin', id: pluginId, values: draft.values }),
    });
  }
  const started = await api('/api/plugins/action', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      plugin_id: pluginId,
      action_id: actionId,
      client_settings: settings ? liveKerniqSettings() : null,
    }),
  });
  if (!started || started.error || !started.job_id) {
    toast((started && started.error) || translate('Could not start'), true);
    if (button) button.disabled = false;
    return;
  }
  try { sessionStorage.setItem('kerniq_benchmark_job', started.job_id); } catch (_) {}
  toast(translate('Benchmark started'));
  watchBenchmark();
  if (button) button.disabled = false;
}
function renderPluginDetail(id) { openPlugin(id); }
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
        if (!await askConfirm(translate('Reset settings for this item?') + '\n' + t.name)) return;
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
        if (!await askConfirm(translate('Reset settings for this item?') + '\n' + p.name)) return;
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
    host_freedom: window.KerniqHostFreedom ? KerniqHostFreedom.checked() : false,
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
    auto_model_load: !!document.getElementById('s-auto-load')?.checked,
    model_load_action: document.getElementById('s-load-action')?.value || 'notify',
    model_sort: document.getElementById('s-model-sort')?.value || 'name',
    model_sort_dir: document.getElementById('s-model-sort-dir')?.value || 'asc',
    provider_descriptions: (settings && settings.api && settings.api.provider_descriptions) || {},
  };
  rememberProviderDraft(apiBody.provider, {
    base_url: apiBody.base_url,
    api_token: apiBody.api_token,
    model: apiBody.model,
    binary_path: apiBody.binary_path,
  });
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
    compose_plan: planComposeAvailable() && !!document.getElementById('s-compose-plan')?.checked,
    response_language: document.getElementById('s-chat-lang')?.value || 'auto',
    read_only_external_attachments: document.getElementById('s-external-ro')?.checked !== false,
  };
  modeAuto = chat.mode_auto;
  applyModeSwitch();
  sendKeyMode = chat.send_key;
  const interfaceNow = (settings && settings.interface) || {};
  if (serverModeOn()) {
    await writeBrowserSettings({ agent, api: apiBody, prompt, chat, interface: interfaceNow });
  } else {
    await api('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ agent, api: apiBody, prompt, chat }) });
  }
  for (const t of (componentsCache.tools || [])) {
    const d = draftTools[t.id];
    if (!d) continue;
    await api('/api/component/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'tool', id: t.id, values: d.values, enabled: d.enabled }) });
  }
  for (const pack of (componentsCache.packs || [])) {
    const intent = draftPacks[pack.id];
    if (!intent || typeof intent.forceEnabled !== 'boolean') continue;
    await api('/api/component/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'pack', id: pack.id, values: {}, enabled: intent.forceEnabled }) });
  }
  for (const p of (componentsCache.plugins || [])) {
    const d = draftPlugins[p.id];
    if (!d) continue;
    await api('/api/component/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ kind: 'plugin', id: p.id, values: d.values }) });
  }
  document.getElementById('top-workspace').textContent = serverModeOn() ? '' : agent.workspace;
  applyServerChrome();
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
  if (!serverModeOn()) {
    const loc = preferredLocale(draftPlugins['plugin_web_ui']?.values?.ui_locale || '');
    applyUiLocale(loc);
  }
  toast(t('saved'));
  await refreshTree();
  await refreshModelFooter();
}

document.getElementById('btn-settings-save').onclick = saveAllSettings;
document.getElementById('btn-settings-cancel').onclick = async () => {
  if (!settingsDirty) return;
  if (!await askConfirm(translate('Discard unsaved changes?'))) return;
  draftTools = {}; draftPlugins = {};
  await loadSettings();
  toast('Changes discarded');
  refreshModelFooter().catch(() => {});
};

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

/* server notice is a toast, not a bar */
document.getElementById('btn-factory-reset').onclick = async () => {
  if (!await askConfirm(translate('Reset every setting to the factory defaults?'), { danger: true, ok: translate('Reset everything'), title: translate('Reset settings') })) return;
  if (!await askConfirm(translate('This clears local settings and cannot be undone.'), { danger: true, ok: translate('Reset everything'), title: translate('Reset settings') })) return;
  await api('/api/settings/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scope: 'all' }) });
  draftTools = {}; draftPlugins = {};
  await loadSettings();
  toast('Factory defaults applied');
};

/* workspace folder picker (best-effort) */
document.getElementById('btn-pick-ws').onclick = async () => {
  if (serverModeOn()) {
    toast('Each user stays in /workspace.', true);
    return;
  }
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
  const field = el.closest ? el.closest('.field') : null;
  const target = (field && field.querySelector('input, select, textarea')) || el;
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
  openPlugin(plug.id);
  setTimeout(() => flashSetting(document.querySelector('#plugin-modal [data-fk="trigger_percent"]')), 40);
}

/* nav */
document.getElementById('nav-logo').onclick = async () => {
  if (document.documentElement.dataset.phone === '1') {
    const open = !document.documentElement.classList.contains('chats-open');
    document.documentElement.classList.toggle('chats-open', open);
    document.body.classList.toggle('chats-open', open);
    return;
  }
  if (settingsDirty && !await askConfirm(translate('Settings are not saved. Leave anyway?'))) return;
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
function pluginResult(result) {
  if (!result || result.ok === false || result.error) {
    toast((result && (result.error || result.message)) || t('error'), true);
    return;
  }
  toast(result.message || t('done'));
  if (result.restart) toast(t('pluginRestart'));
  loadComponents().catch(() => {});
}
document.getElementById('plugin-search')?.addEventListener('click', async () => {
  const q = document.getElementById('plugin-repo');
  const hits = document.getElementById('plugin-search-hits');
  if (!hits) return;
  hits.innerHTML = '';
  const found = await api('/api/plugins/search', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: (q && q.value) || '' }),
  });
  if (!found || found.ok === false) { toast((found && found.error) || t('error'), true); return; }
  const repos = found.repos || [];
  if (!repos.length) { hits.textContent = t('pluginNoMatches'); return; }
  repos.forEach(repo => {
    const row = document.createElement('button');
    row.type = 'button';
    row.className = 'ghost plugin-hit';
    row.textContent = repo.full_name + (repo.description ? ' — ' + repo.description : '');
    row.addEventListener('click', () => { if (q) q.value = repo.full_name; });
    hits.appendChild(row);
  });
});
document.getElementById('plugin-install')?.addEventListener('click', async () => {
  const q = document.getElementById('plugin-repo');
  const repo = (q && q.value || '').trim();
  if (!repo) return;
  const result = await api('/api/plugins/install', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo: repo }),
  });
  pluginResult(result);
});
document.getElementById('plugin-updates')?.addEventListener('click', async () => {
  const box = document.getElementById('plugin-update-list');
  const data = await api('/api/plugins/updates', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  pluginUpdateMap = {};
  (data.updates || []).forEach(row => { pluginUpdateMap[row.plugin_id] = row; });
  renderPluginsList();
  if (!box) return;
  box.innerHTML = '';
  (data.updates || []).filter(row => row.kind !== 'kit').forEach(row => {
    const line = document.createElement('div');
    line.className = 'plugin-hit';
    line.textContent = (row.name || row.plugin_id) + ' — ' + (row.note || row.error || '');
    if (row.update && row.repo) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = t('pluginUpdateReady');
      btn.addEventListener('click', async () => {
        const body = row.kind === 'path' ? { path: row.repo, force: true } : { repo: row.repo, force: true };
        pluginResult(await api('/api/plugins/install', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }));
      });
      line.appendChild(btn);
    }
    box.appendChild(line);
  });
});
document.getElementById('plugin-modal-body')?.addEventListener('click', async (ev) => {
  const btn = ev.target.closest && ev.target.closest('[data-plugin-remove]');
  if (!btn) return;
  const result = await api('/api/plugins/remove', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: btn.getAttribute('data-plugin-remove') }),
  });
  if (result && result.ok) closePluginModal();
  pluginResult(result);
});
document.getElementById('settings-nav')?.addEventListener('click', (ev) => {
  const s = ev.target.closest && ev.target.closest('.stab');
  if (!s || !s.dataset.tab) return;
  document.querySelectorAll('.stab').forEach(x => x.classList.remove('active'));
  s.classList.add('active');
  document.querySelectorAll('.tabp').forEach(p => p.style.display = 'none');
  const panel = document.getElementById('tab-' + s.dataset.tab);
  if (panel) panel.style.display = 'block';
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
    autoFooterModel = '';
    runModel = '';
    settlePlan();
    setRunLock(false);
    currentRunId = null;
    updateActionBtn();
    saveChats();
    renderMessages();
    refreshModelFooter().catch(() => {});
  }
}

/* init */
loadPanelWidths();
bindResizer('resizer-left', 'left');
bindResizer('resizer-right', 'right');
(async function bootChats() {
  await loadChatsFromServer();
  try { applyChatContextFooter(); } catch (_) {}
  if (!chats.length) newChat(true);
  else { activeChatId = chats[chats.length - 1].id; renderChatList(); renderMessages(); }
  applyStoredMode();
})();
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

/* server notice is a toast, not a bar */
updateActionBtn();
autoGrow();
startTreePoll();
(async () => {
  try { announceServer(await api('/api/server/info')); } catch (e) {}
})();
document.querySelector('.settings-actions').style.display = 'none';



