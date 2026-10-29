/* ---------- interface language + status footer (kept in the Web UI plugin settings) ---------- */
function webUiSaved() {
  const p = (componentsCache.plugins || []).find(x => x.id === 'plugin_web_ui');
  return (p && p.values) || {};
}
async function saveInterface(patch) {
  settings = settings || {};
  settings.interface = Object.assign({
    layout: 'editor', motion: 'on', blur: true, highlight: true, auto_think: false,
    show_notifications: true, auto_dismiss_notifications: true,
    theme: document.documentElement.dataset.themeChoice || 'dark',
  }, settings.interface || {}, patch || {});
  if (serverModeOn()) {
    writeBrowserSettings({
      agent: settings.agent || {},
      api: settings.api || {},
      prompt: settings.prompt || {},
      chat: settings.chat || {},
      interface: settings.interface,
    }).catch(() => {});
    return;
  }
  api('/api/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interface: settings.interface }),
  }).catch(() => {});
}
function applyTheme(pref) {
  const choice = pref === 'light' || pref === 'dark' || pref === 'system' ? pref : 'dark';
  let resolved = choice;
  if (choice === 'system') {
    let light = false;
    try { light = window.matchMedia('(prefers-color-scheme: light)').matches; } catch (_) {}
    resolved = light ? 'light' : 'dark';
  }
  document.documentElement.dataset.themeChoice = choice;
  document.documentElement.dataset.theme = resolved;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', resolved === 'light' ? '#e7eaee' : '#1e2128');
  const scheme = document.querySelector('meta[name="color-scheme"]');
  if (scheme) scheme.setAttribute('content', resolved);
  try { localStorage.setItem('kerniq.theme', choice); } catch (_) {}
  document.querySelectorAll('#seg-theme button').forEach(b => {
    const on = b.dataset.v === choice;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
}
try {
  const schemeMq = window.matchMedia('(prefers-color-scheme: light)');
  const onScheme = () => {
    if (document.documentElement.dataset.themeChoice === 'system') applyTheme('system');
  };
  if (schemeMq.addEventListener) schemeMq.addEventListener('change', onScheme);
} catch (_) {}
function applyInterface(row) {
  const data = row || {};
  const saved = data.layout === 'agent' ? 'agent' : 'editor';
  desktopLayout = saved;
  const phone = document.documentElement.dataset.phone === '1';
  layoutMode = phone ? 'agent' : saved;
  document.documentElement.dataset.layout = layoutMode;
  document.documentElement.dataset.tone = layoutMode;
  const motion = ['on', 'off', 'auto'].indexOf(data.motion) >= 0 ? data.motion : 'on';
  document.documentElement.dataset.motion = motion;
  document.documentElement.dataset.blur = data.blur === false ? 'off' : 'on';
  const theme = data.theme === 'light' || data.theme === 'dark' || data.theme === 'system'
    ? data.theme
    : (document.documentElement.dataset.themeChoice || 'dark');
  applyTheme(theme);
  autoThink = !!data.auto_think;
  showNotifications = data.show_notifications !== false;
  autoDismissToasts = data.auto_dismiss_notifications !== false;
  ED.hl = data.highlight !== false;
  const think = document.getElementById('ui-auto-think');
  if (think) think.checked = autoThink;
  const showToasts = document.getElementById('ui-show-toasts');
  if (showToasts) showToasts.checked = showNotifications;
  const dismiss = document.getElementById('ui-auto-dismiss');
  if (dismiss) dismiss.checked = autoDismissToasts;
  const hl = document.getElementById('ui-hl');
  if (hl) hl.checked = ED.hl;
  const blurBox = document.getElementById('ui-blur');
  if (blurBox) blurBox.checked = data.blur !== false;
  document.querySelectorAll('#seg-motion button').forEach(b => {
    const on = b.dataset.v === motion;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
  document.querySelectorAll('#seg-layout button').forEach(b => {
    const shown = phone ? saved : layoutMode;
    const on = b.dataset.v === shown;
    b.classList.toggle('on', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
  });
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
    const want = uiLocaleWanted || uiLocale;
    sel.value = [...sel.options].some(o => o.value === want) ? want : 'en';
  }
  const f = document.getElementById('ui-footer');
  const foot = document.getElementById('app-footer');
  if (f && foot) f.checked = !foot.classList.contains('hidden');
  const saved = webUiSaved();
  const host = document.getElementById('ui-host');
  if (host && document.activeElement !== host) host.value = saved.host || '127.0.0.1';
  const port = document.getElementById('ui-port');
  if (port && document.activeElement !== port) port.value = saved.port != null ? saved.port : 8765;
  const server = document.getElementById('ui-server');
  if (server) server.checked = !!saved.server_mode;
  const lan = document.getElementById('ui-lan');
  if (lan) lan.checked = !!saved.lan_access;
  const log = document.getElementById('ui-log');
  if (log) {
    log.querySelectorAll('option').forEach(o => {
      const src = o.getAttribute('data-en');
      if (src) o.textContent = translate(src);
    });
    if ([...log.options].some(o => o.value === (saved.log_level || 'warning'))) log.value = saved.log_level || 'warning';
  }
  refreshAutostart();
}
async function refreshAutostart() {
  const box = document.getElementById('ui-autostart');
  if (!box) return;
  const data = await api('/api/ui/autostart').catch(() => null);
  if (!data || document.activeElement === box) return;
  box.checked = !!data.enabled;
  const note = document.getElementById('ui-autostart-note');
  if (note) note.textContent = data.message || '';
}
document.getElementById('ui-lang')?.addEventListener('change', async (e) => {
  const v = e.target.value || 'en';
  try { localStorage.setItem('kerniq.ui_locale', v); } catch (_) {}
  applyUiLocale(v);
  if (serverModeOn()) {
    if (typeof refreshInterfaceControls === 'function') refreshInterfaceControls();
    return;
  }
  await setWebUiValue('ui_locale', v);
});
document.getElementById('s-model-sort')?.addEventListener('change', () => {
  settings = settings || {};
  settings.api = settings.api || {};
  settings.api.model_sort = document.getElementById('s-model-sort').value;
  fillModelMenu(document.getElementById('s-model')?.value || '');
  markSettingsDirty();
});
document.getElementById('s-model-sort-dir')?.addEventListener('change', () => {
  settings = settings || {};
  settings.api = settings.api || {};
  settings.api.model_sort_dir = document.getElementById('s-model-sort-dir').value;
  fillModelMenu(document.getElementById('s-model')?.value || '');
  markSettingsDirty();
});
document.getElementById('s-api-max-tokens')?.addEventListener('input', () => clampMaxTokensField());
document.getElementById('ui-footer')?.addEventListener('change', async (e) => {
  footerEnabled = !!e.target.checked;
  document.getElementById('app-footer').classList.toggle('hidden', !e.target.checked);
  await setWebUiValue('show_footer', !!e.target.checked);
});
document.getElementById('ui-host')?.addEventListener('change', (e) => setWebUiValue('host', e.target.value.trim() || '127.0.0.1'));
document.getElementById('ui-port')?.addEventListener('change', (e) => setWebUiValue('port', Number(e.target.value) || 8765));
document.getElementById('ui-server')?.addEventListener('change', (e) => setWebUiValue('server_mode', !!e.target.checked));
document.getElementById('ui-lan')?.addEventListener('change', (e) => setWebUiValue('lan_access', !!e.target.checked));
document.getElementById('ui-log')?.addEventListener('change', (e) => setWebUiValue('log_level', e.target.value));
document.getElementById('ui-autostart')?.addEventListener('change', async (e) => {
  const on = !!e.target.checked;
  const r = await api('/api/ui/autostart', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: on }),
  });
  const note = document.getElementById('ui-autostart-note');
  if (r && r.error) {
    e.target.checked = !on;
    toast(String(r.error), true);
    return;
  }
  if (note && r && r.message) note.textContent = r.message;
  if (r && r.message) toast(r.message);
});
document.getElementById('ui-auto-think')?.addEventListener('change', (e) => {
  autoThink = !!e.target.checked;
  saveInterface({ auto_think: autoThink });
});
document.getElementById('ui-show-toasts')?.addEventListener('change', (e) => {
  showNotifications = !!e.target.checked;
  saveInterface({ show_notifications: showNotifications });
});
document.getElementById('ui-auto-dismiss')?.addEventListener('change', (e) => {
  autoDismissToasts = !!e.target.checked;
  saveInterface({ auto_dismiss_notifications: autoDismissToasts });
});
document.getElementById('plugin-modal-close')?.addEventListener('click', closePluginModal);
document.getElementById('plugin-modal')?.addEventListener('click', (e) => {
  if (e.target && e.target.id === 'plugin-modal') closePluginModal();
});
document.getElementById('btn-lang-packs')?.addEventListener('click', () => openLangModal());
document.getElementById('lang-modal-import')?.addEventListener('click', () => document.getElementById('lang-pack-file')?.click());
refreshInterfaceControls();

/* interface preferences live in the project settings, not in the browser */
if (document.documentElement.dataset.phone === '1') applyLayout('agent', false);
else applyLayout(layoutMode, false);
watchBenchmark();
(function setupPhone() {
  const mq = window.matchMedia('(orientation: portrait) and (max-width: 820px)');
  const apply = () => {
    const on = mq.matches;
    document.documentElement.dataset.phone = on ? '1' : '0';
    if (on) {
      if (layoutMode !== 'agent') applyLayout('agent', false);
      else {
        document.documentElement.dataset.layout = 'agent';
        document.documentElement.dataset.tone = 'agent';
      }
    } else {
      document.documentElement.classList.remove('chats-open');
      document.body.classList.remove('chats-open');
      const back = desktopLayout === 'agent' ? 'agent' : 'editor';
      if (back !== layoutMode) applyLayout(back, false);
    }
  };
  if (mq.addEventListener) mq.addEventListener('change', apply);
  apply();
  const closeChats = () => {
    document.documentElement.classList.remove('chats-open');
    document.body.classList.remove('chats-open');
  };
  const freshChat = () => {
    closeChats();
    document.getElementById('btn-new-chat')?.click();
  };
  document.getElementById('btn-mobile-new')?.addEventListener('click', freshChat);
  document.getElementById('drawer-new')?.addEventListener('click', freshChat);
  document.getElementById('drawer-settings')?.addEventListener('click', () => {
    closeChats();
    document.getElementById('nav-settings')?.click();
  });
  document.getElementById('chat-panel')?.addEventListener('click', (ev) => {
    if (document.documentElement.dataset.phone !== '1') return;
    if (!document.documentElement.classList.contains('chats-open')) return;
    if (ev.target.closest && ev.target.closest('#explorer')) return;
    closeChats();
  });

  const root = document.documentElement;
  const explorer = document.getElementById('explorer');
  const chat = document.getElementById('chat-panel');
  const settingsView = document.getElementById('view-settings');
  const phoneOn = () => root.dataset.phone === '1';
  const setChats = (on) => {
    root.classList.toggle('chats-open', on);
    document.body.classList.toggle('chats-open', on);
  };
  const blockedGesture = (node) => !!(node && node.closest && node.closest('textarea, input, select, button, a, .modal, .modal-bg, #ext-sheet'));
  let drawerDrag = null;
  let settingsDrag = null;
  let swallowChatClick = false;

  function paintDrawer(p) {
    const clamped = Math.max(0, Math.min(1, p));
    root.style.setProperty('--phone-dim', String(clamped));
    if (explorer) explorer.style.transform = 'translateX(' + (-105 * (1 - clamped)) + '%)';
    if (chat) chat.style.transform = 'translateX(' + (30 * clamped) + '%)';
    return clamped;
  }
  function clearDrawerInline() {
    root.classList.remove('phone-drag');
    root.style.removeProperty('--phone-dim');
    if (explorer) explorer.style.transform = '';
    if (chat) chat.style.transform = '';
  }
  function settleDrawer(open) {
    root.classList.remove('phone-drag');
    if (explorer) void explorer.offsetWidth;
    setChats(open);
    paintDrawer(open ? 1 : 0);
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      clearDrawerInline();
      setChats(open);
    };
    if (explorer) explorer.addEventListener('transitionend', finish, { once: true });
    setTimeout(finish, 420);
  }

  chat?.addEventListener('click', (ev) => {
    if (!swallowChatClick) return;
    swallowChatClick = false;
    ev.preventDefault();
    ev.stopPropagation();
  }, true);

  chat?.addEventListener('touchstart', (ev) => {
    if (!phoneOn() || settingsOpen() || document.body.classList.contains('modal-open')) return;
    if (!ev.touches || ev.touches.length !== 1) return;
    if (blockedGesture(ev.target)) return;
    if (ev.target.closest && ev.target.closest('#explorer')) return;
    const t = ev.touches[0];
    drawerDrag = {
      x: t.clientX,
      y: t.clientY,
      lastX: t.clientX,
      lastT: Date.now(),
      vx: 0,
      p0: root.classList.contains('chats-open') ? 1 : 0,
      p: root.classList.contains('chats-open') ? 1 : 0,
      active: false,
    };
  }, { passive: true });

  chat?.addEventListener('touchmove', (ev) => {
    if (!drawerDrag || !ev.touches || !ev.touches.length) return;
    const t = ev.touches[0];
    const dx = t.clientX - drawerDrag.x;
    const dy = t.clientY - drawerDrag.y;
    const now = Date.now();
    drawerDrag.vx = (t.clientX - drawerDrag.lastX) / Math.max(1, now - drawerDrag.lastT);
    drawerDrag.lastX = t.clientX;
    drawerDrag.lastT = now;
    if (!drawerDrag.active) {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      if (Math.abs(dx) < Math.abs(dy) * 1.2) { drawerDrag = null; return; }
      if (drawerDrag.p0 === 0 && dx <= 0) { drawerDrag = null; return; }
      drawerDrag.active = true;
      root.classList.add('phone-drag');
    }
    const width = Math.max(1, window.innerWidth * 0.6);
    drawerDrag.p = paintDrawer(drawerDrag.p0 + dx / width);
    if (ev.cancelable) ev.preventDefault();
  }, { passive: false });

  const endDrawer = () => {
    if (!drawerDrag) return;
    const drag = drawerDrag;
    drawerDrag = null;
    if (!drag.active) return;
    swallowChatClick = true;
    const flickOpen = drag.vx > 0.4;
    const flickClose = drag.vx < -0.4;
    const open = flickClose ? false : (flickOpen || drag.p > 0.34);
    settleDrawer(open);
  };
  chat?.addEventListener('touchend', endDrawer);
  chat?.addEventListener('touchcancel', endDrawer);

  document.getElementById('btn-settings-back')?.addEventListener('click', () => {
    if (!phoneOn()) return;
    setChats(true);
    showView('main');
  });

  function clearSettingsInline() {
    root.classList.remove('phone-drag');
    if (settingsView) settingsView.style.transform = '';
  }
  settingsView?.addEventListener('touchstart', (ev) => {
    if (!phoneOn() || !settingsOpen() || document.body.classList.contains('modal-open')) return;
    if (!ev.touches || ev.touches.length !== 1) return;
    if (blockedGesture(ev.target)) return;
    const t = ev.touches[0];
    const nav = ev.target.closest && ev.target.closest('#settings-nav');
    const main = document.querySelector('.settings-main');
    const fromLeft = t.clientX <= 28;
    const fromRight = t.clientX >= window.innerWidth - 28;
    if (!fromLeft && !fromRight && !nav) return;
    settingsDrag = {
      x: t.clientX,
      y: t.clientY,
      fromLeft,
      fromRight,
      fromNav: !!nav && !fromLeft && !fromRight,
      scrollTop: main ? main.scrollTop : 0,
      active: false,
      axis: '',
      p: 0,
    };
  }, { passive: true });

  settingsView?.addEventListener('touchmove', (ev) => {
    if (!settingsDrag || !settingsView || !ev.touches || !ev.touches.length) return;
    const t = ev.touches[0];
    const dx = t.clientX - settingsDrag.x;
    const dy = t.clientY - settingsDrag.y;
    if (!settingsDrag.active) {
      if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
      const horizontal = Math.abs(dx) > Math.abs(dy);
      if ((settingsDrag.fromLeft && horizontal && dx > 0) || (settingsDrag.fromRight && horizontal && dx < 0)) {
        settingsDrag.axis = 'x';
      } else if (settingsDrag.fromNav && !horizontal && dy > 0 && settingsDrag.scrollTop <= 1) {
        settingsDrag.axis = 'y';
      } else {
        settingsDrag = null;
        return;
      }
      settingsDrag.active = true;
      root.classList.add('phone-drag');
      setChats(true);
    }
    if (settingsDrag.axis === 'x') {
      const travel = settingsDrag.fromRight ? Math.max(0, -dx) : Math.max(0, dx);
      settingsDrag.p = Math.max(0, Math.min(1, travel / Math.max(1, window.innerWidth)));
      const signed = settingsDrag.fromRight ? -settingsDrag.p : settingsDrag.p;
      settingsView.style.transform = 'translateX(' + (signed * 100) + '%)';
    } else {
      settingsDrag.p = Math.max(0, Math.min(1, dy / Math.max(1, window.innerHeight * 0.42)));
      settingsView.style.transform = 'translateY(' + (settingsDrag.p * 100) + '%)';
    }
    if (ev.cancelable) ev.preventDefault();
  }, { passive: false });

  const endSettings = () => {
    if (!settingsDrag || !settingsView) { settingsDrag = null; return; }
    const drag = settingsDrag;
    settingsDrag = null;
    if (!drag.active) return;
    const commit = drag.p > 0.28;
    root.classList.remove('phone-drag');
    void settingsView.offsetWidth;
    if (!commit) {
      setChats(false);
      settingsView.style.transform = 'none';
      const back = () => { clearSettingsInline(); };
      settingsView.addEventListener('transitionend', back, { once: true });
      setTimeout(back, 480);
      return;
    }
    settingsView.style.transform = drag.axis === 'y'
      ? 'translateY(110%)'
      : (drag.fromRight ? 'translateX(-104%)' : 'translateX(104%)');
    let closed = false;
    const finish = () => {
      if (closed) return;
      closed = true;
      settingsView.style.transition = 'none';
      settingsView.style.transform = 'translateY(-101%)';
      showView('main');
      setChats(true);
      requestAnimationFrame(() => {
        settingsView.style.transition = '';
        settingsView.style.transform = '';
      });
    };
    settingsView.addEventListener('transitionend', finish, { once: true });
    setTimeout(finish, 480);
  };
  settingsView?.addEventListener('touchend', endSettings);
  settingsView?.addEventListener('touchcancel', endSettings);
})();
(function setupExtensions() {
  const sheet = document.getElementById('ext-sheet');
  const body = document.getElementById('ext-sheet-body');
  const title = document.getElementById('ext-sheet-title');
  const nav = document.getElementById('settings-nav');
  const main = document.querySelector('.settings-main');
  function openSheet(ext) {
    if (!sheet || !body) return;
    if (title) title.textContent = ext.label || 'Extension';
    const stateText = (document.getElementById('bench-note-text') || {}).textContent || '';
    body.innerHTML = '';
    const status = document.createElement('p');
    status.className = 'ext-metric';
    status.textContent = stateText || translate('No benchmark is running.');
    body.appendChild(status);
    const actions = document.createElement('div');
    actions.className = 'ext-actions';
    const run = document.createElement('button');
    run.type = 'button';
    run.className = 'save-active';
    run.textContent = translate('Run benchmark');
    run.addEventListener('click', () => runPluginAction(ext.plugin_id, 'run', run));
    const settingsBtn = document.createElement('button');
    settingsBtn.type = 'button';
    settingsBtn.className = 'ghost';
    settingsBtn.textContent = translate('Open settings');
    settingsBtn.addEventListener('click', () => {
      sheet.hidden = true;
      const stab = document.querySelector('.stab[data-tab="ext-' + ext.id + '"]');
      document.getElementById('nav-settings')?.click();
      if (stab) stab.click();
    });
    actions.appendChild(run);
    actions.appendChild(settingsBtn);
    body.appendChild(actions);
    sheet.hidden = false;
  }
  document.getElementById('ext-sheet-close')?.addEventListener('click', () => { if (sheet) sheet.hidden = true; });
  document.getElementById('drawer-ext')?.addEventListener('click', () => {
    document.documentElement.classList.remove('chats-open');
    document.body.classList.remove('chats-open');
    const ext = document.getElementById('drawer-ext')._ext;
    if (ext) openSheet(ext);
  });
  (async () => {
    try { await loadComponents(); } catch (_) {}
    let data = null;
    try { data = await api('/api/extensions'); } catch (_) { data = null; }
    const rows = (data && data.extensions) || [];
    rows.forEach(ext => {
      if (ext.slot === 'panel') {
        const btn = document.getElementById('drawer-ext');
        if (btn) { btn.hidden = false; btn.title = ext.label || 'Benchmark'; btn._ext = ext; }
      }
      if (ext.slot !== 'settings' || !nav || !main) return;
      const stab = document.createElement('div');
      stab.className = 'stab';
      stab.dataset.tab = 'ext-' + ext.id;
      stab.innerHTML = '<i class="stab-ico" data-i="' + (ext.icon === 'chart' ? 'chart' : 'plugins') + '"></i><span class="stab-tx"></span>';
      stab.querySelector('.stab-tx').textContent = ext.label || ext.id;
      nav.appendChild(stab);
      const panel = document.createElement('div');
      panel.className = 'scard tabp';
      panel.id = 'tab-ext-' + ext.id;
      panel.style.display = 'none';
      panel.innerHTML = '<h2></h2><div class="ext-host"></div>';
      panel.querySelector('h2').textContent = ext.label || ext.id;
      main.appendChild(panel);
      const host = panel.querySelector('.ext-host');
      const plug = (componentsCache.plugins || []).find(p => p.id === ext.plugin_id);
      if (plug && host) {
        host.innerHTML = pluginFormHtml(plug);
        bindPluginForm(host, plug);
      } else if (host) {
        host.textContent = translate('Open Plugins once so this section can load its settings.');
      }
      const open = document.createElement('button');
      open.type = 'button';
      open.className = 'ghost';
      open.textContent = translate('Open benchmark window');
      open.addEventListener('click', () => openSheet(ext));
      panel.appendChild(open);
    });
  })().catch(() => {});
})();
(function setupInterfacePrefs() {
  const seg = document.getElementById('seg-motion');
  const hlBox = document.getElementById('ui-hl');
  if (seg) {
    seg.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      document.documentElement.dataset.motion = b.dataset.v;
      saveInterface({ motion: b.dataset.v });
      document.querySelectorAll('#seg-motion button').forEach(btn => {
        const on = btn.dataset.v === b.dataset.v;
        btn.classList.toggle('on', on);
        btn.setAttribute('aria-checked', on ? 'true' : 'false');
      });
    }));
  }
  if (hlBox) {
    hlBox.addEventListener('change', () => {
      ED.hl = hlBox.checked;
      saveInterface({ highlight: ED.hl });
      updateLineNumbers();
    });
  }
  const blurBox = document.getElementById('ui-blur');
  if (blurBox) {
    blurBox.addEventListener('change', () => {
      document.documentElement.dataset.blur = blurBox.checked ? 'on' : 'off';
      saveInterface({ blur: blurBox.checked });
    });
  }
  const themeSeg = document.getElementById('seg-theme');
  if (themeSeg) {
    themeSeg.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
      applyTheme(b.dataset.v);
      saveInterface({ theme: b.dataset.v });
    }));
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

function readDroppedEntry(entry, rel) {
  return new Promise((resolve) => {
    if (!entry) { resolve([]); return; }
    if (entry.isFile) {
      entry.file((file) => { file._rel = rel; resolve([file]); }, () => resolve([]));
      return;
    }
    if (!entry.isDirectory || !entry.createReader) { resolve([]); return; }
    const reader = entry.createReader();
    const acc = [];
    const pump = () => {
      reader.readEntries(async (entries) => {
        if (!entries.length) { resolve(acc); return; }
        for (const child of entries) {
          const next = rel ? rel + '/' + child.name : child.name;
          acc.push(...await readDroppedEntry(child, next));
        }
        pump();
      }, () => resolve(acc));
    };
    pump();
  });
}
async function fileToBase64(file) {
  const dataUrl = await new Promise((res) => {
    const reader = new FileReader();
    reader.onload = () => res(reader.result);
    reader.readAsDataURL(file);
  });
  return String(dataUrl || '').split(',')[1] || '';
}
async function importBrowserFiles(files, asFolder) {
  let folderPath = '';
  for (const file of files) {
    if (attachBlocked(file.name)) {
      toast(isImagePath(file.name) ? t('modelNoVision') : t('attachBlocked'), true);
      continue;
    }
    const raw = await fileToBase64(file);
    const relative = file._rel || file.webkitRelativePath || file.name;
    const imported = await api('/api/attachments/import', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: file.name, relative: asFolder ? relative : file.name, content_base64: raw }),
    });
    if (imported && imported.error) { toast(imported.error, true); continue; }
    if (asFolder) {
      if (imported.folder) folderPath = imported.folder;
    } else if (imported && imported.path) {
      addAttachment(imported.path, true, false);
    }
  }
  if (asFolder && folderPath) addAttachment(folderPath, true, false, { directory: true });
}
const IMAGE_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']);
const BLOCKED_ATTACH = new Set(['svg','ico','heic','heif','tif','tiff','mp4','mov','mkv','webm','avi','wmv','m4v','mpg','mpeg','mp3','wav','ogg','flac','aac','m4a','wma','opus','exe','dll','bin','iso','dmg','msi','zip','7z','rar','gz','tar','bz2','xz']);
function fileExt(name) {
  const raw = String(name || '');
  const dot = raw.lastIndexOf('.');
  return dot < 0 ? '' : raw.slice(dot + 1).toLowerCase();
}
function isImagePath(name) { return IMAGE_EXT.has(fileExt(name)); }
function attachBlocked(name) {
  const ext = fileExt(name);
  if (IMAGE_EXT.has(ext)) return !activeVision();
  return BLOCKED_ATTACH.has(ext);
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
      const items = [...(ev.dataTransfer.items || [])];
      const folders = [];
      const loose = [];
      let usedEntries = false;
      for (const item of items) {
        const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
        if (!entry) continue;
        usedEntries = true;
        if (entry.isDirectory) {
          const grouped = await readDroppedEntry(entry, entry.name);
          if (grouped.length) folders.push(grouped);
        } else if (entry.isFile) {
          loose.push(...await readDroppedEntry(entry, entry.name));
        }
      }
      if (!usedEntries) {
        await importBrowserFiles([...(ev.dataTransfer.files || [])], false);
        return;
      }
      for (const group of folders) await importBrowserFiles(group, true);
      if (loose.length) await importBrowserFiles(loose, false);
    });
  }
  const photo = document.getElementById('photo-picker');
  if (photo) {
    photo.addEventListener('change', async () => {
      const files = [...(photo.files || [])];
      photo.value = '';
      if (!activeVision()) { toast(t('modelNoVision'), true); return; }
      await importBrowserFiles(files, false);
    });
  }
  const outside = document.getElementById('outside-picker');
  if (outside) {
    outside.addEventListener('change', async () => {
      const files = [...(outside.files || [])];
      outside.value = '';
      await importBrowserFiles(files, false);
    });
  }
  const folder = document.getElementById('folder-picker');
  if (folder) {
    folder.addEventListener('change', async () => {
      const files = [...(folder.files || [])];
      folder.value = '';
      await importBrowserFiles(files, true);
    });
  }
})();
function addAttachment(path, exists, external, extra) {
  if (isImagePath(path) && !activeVision()) { toast(t('modelNoVision'), true); return; }
  if (chatAttachments.some(a => a.path === path)) return;
  chatAttachments.push({
    path,
    exists: exists !== false,
    external: !!external,
    directory: !!(extra && extra.directory),
  });
  renderAttachChips();
}
function renderAttachChips() {
  const el = document.getElementById('attach-chips');
  if (!el) return;
  el.innerHTML = '';
  chatAttachments.forEach((a, i) => {
    const d = document.createElement('span');
    d.className = 'attach-chip ' + (a.exists ? 'ok' : 'bad');
    const label = a.directory ? String(a.path).replace(/\/$/, '') + '/' : a.path;
    d.appendChild(document.createTextNode((a.external ? '↗ ' : '') + label + ' '));
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
    (activeVision() ? item('attach-photo', CTX_ICON.upload, '') : '') +
    item('attach-outside', CTX_ICON.upload, '') +
    item('attach-folder', CTX_ICON.folder, '');
  const setText = (id, label, hint) => {
    const el = document.getElementById(id);
    el.querySelector('.ci-label').textContent = label;
    el.querySelector('.ci-hint').textContent = hint;
  };
  setText('attach-project', t('fromProject'), t('fromProjectHint'));
  const photoBtn = document.getElementById('attach-photo');
  if (photoBtn) setText('attach-photo', t('photo'), t('photoHint'));
  setText('attach-outside', t('fromOutside'), t('fromOutsideHint'));
  setText('attach-folder', t('attachFolder'), t('attachFolderHint'));
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
  document.getElementById('attach-photo')?.addEventListener('click', (ev) => {
    ev.stopPropagation();
    hideCtx();
    if (!activeVision()) { toast(t('modelNoVision'), true); return; }
    const input = document.getElementById('photo-picker');
    if (input) input.click();
  });
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
  document.getElementById('attach-folder').onclick = async (ev) => {
    ev.stopPropagation();
    hideCtx();
    if (serverModeOn()) {
      const input = document.getElementById('folder-picker');
      if (input) input.click();
      return;
    }
    const r = await api('/api/fs/pick_attach_folder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    if (r && r.path) addAttachment(r.path, true, true, { directory: !!r.directory });
    else if (r && r.error) {
      toast(r.error, true);
      const input = document.getElementById('folder-picker');
      if (input) input.click();
    }
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
  const fromPlugin = serverModeOn() ? '' : (
    (draftPlugins['plugin_web_ui'] && draftPlugins['plugin_web_ui'].values && draftPlugins['plugin_web_ui'].values.ui_locale)
    || ''
  );
  let stored = '';
  try { stored = localStorage.getItem('kerniq.ui_locale') || ''; } catch (_) {}
  applyUiLocale(preferredLocale(fromPlugin || stored));
  if (typeof refreshInterfaceControls === 'function') refreshInterfaceControls();
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
      refreshOpenPlugin();
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
  refreshOpenPlugin();
  if (res && res.warnings && res.warnings.length) toast(res.warnings.join(' '));
  else toast(translate('Language pack imported.'));
});
loadLangPacks();

async function shutdownUi() {
  if (!await askConfirm(translate('Stop the Web UI and close this page?'), { danger: true })) return;
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
