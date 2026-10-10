/** Four existing tabs, one account, prepare only. No navigation or submission. */
export async function prepareCommentBatch(page, batch) {
  const version = 'panse-xhs-comment-batch-handoff.v1';
  const allowedOrigin = 'https://www.xiaohongshu.com';
  const context = page.context();
  const result = {contract_id: version, batch_id: batch.batch_id, status: 'preparing',
    ready_count: 0, notify_user: false, automatic_submission_performed: false,
    platform_publication_verified: false, items: []};
  const owned = [];
  let stopped = false;
  const fail = code => { const error = new Error(code); error.safeCode = code; throw error; };
  const now = () => Date.now();
  const date = () => new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Shanghai',
    year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const validTime = () => batch.date === date() && now() < Date.parse(batch.expires_at);
  const noteOf = value => {
    try { const url = new URL(value); return url.origin === allowedOrigin
      ? /^\/(?:explore|discovery\/item)\/([a-f0-9]{24})\/?$/.exec(url.pathname)?.[1] : null; }
    catch { return null; }
  };
  async function pause(code) {
    stopped = true;
    result.status = 'paused'; result.reason = code; result.notify_user = false;
    for (const row of owned) {
      try { await row.page.evaluate(() => {
        if (window.__panseBatchGuard) window.__panseBatchGuard.phase = 'paused';
      }); } catch {}
    }
  }
  // Local page observations never leave the page as body text, URLs or credentials.
  async function inspect(tab, item, expectedText) {
    if (!validTime()) fail('batch_expired');
    if (noteOf(tab.url()) !== item.note_id) fail('target_changed');
    const observed = await tab.evaluate(({item, profile, expectedText}) => {
      const visible = el => !!el && el.getClientRects().length > 0 &&
        getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none';
      const all = selector => [...document.querySelectorAll(selector)].filter(visible);
      const self = [...document.querySelectorAll('a[href]')].filter(el => visible(el) && el.textContent.trim() === '我');
      const identity = self.length === 1 && new URL(self[0].href).pathname === `/user/profile/${profile}`;
      const body = document.body.innerText;
      const risk = /安全验证|安全校验|访问过于频繁|操作过于频繁|请求频繁|账号异常|登录异常|滑块验证|人机验证|请完成验证/.test(body);
      const login = /登录后查看|扫码登录|手机号登录/.test(body);
      const editors = all(item.selectors.editor), titles = all(item.selectors.title);
      const comments = all(item.selectors.comments), sends = all(item.selectors.send);
      const editor = editors[0];
      const editable = !!editor && (editor.matches('textarea,input:not([type]),input[type="text"]') || editor.isContentEditable);
      const text = editor ? ('value' in editor ? editor.value : editor.innerText) : null;
      const disabled = !editor || editor.disabled || editor.readOnly || editor.closest('[inert],[aria-hidden="true"]');
      const duplicate = comments.length === 1 && [...comments[0].querySelectorAll('*')]
        .some(el => visible(el) && el.textContent.trim() === item.text);
      return {identity, risk, login, unique: editors.length === 1 && titles.length === 1 &&
        comments.length === 1 && sends.length === 1, editable: editable && !disabled,
        title_match: titles.length === 1 && titles[0].textContent.trim() === item.title,
        send_ready: expectedText === '' || (sends.length === 1 && !sends[0].disabled && sends[0].getAttribute('aria-disabled') !== 'true'),
        text_match: text === expectedText, duplicate};
    }, {item, profile: batch.expected_profile_id, expectedText});
    if (observed.risk) fail('risk_signal');
    if (observed.login) fail('login_required');
    if (!observed.identity) fail('identity_mismatch_or_unknown');
    if (!observed.unique || !observed.editable) fail('ambiguous_or_uneditable_page');
    if (!observed.title_match) fail('title_changed');
    if (!observed.text_match) fail('editor_not_empty_or_text_changed');
    if (!observed.send_ready) fail('send_button_not_ready');
    if (observed.duplicate) fail('duplicate_comment');
  }
  try {
    if (!/^[a-zA-Z0-9._-]{1,80}$/.test(batch.batch_id || '') || batch.contract_id !== version ||
      !Number.isInteger(batch.account_slot) || batch.account_slot < 1 || batch.account_slot > 5 ||
      !/^[a-f0-9]{24}$/.test(batch.expected_profile_id || '') || batch.human_final_submission_required !== true ||
      !Array.isArray(batch.items) || batch.items.length !== 4 || !validTime() ||
      Date.parse(batch.expires_at) > Date.parse(batch.date + 'T23:59:59.999+08:00') ||
      Date.parse(batch.expires_at) - now() > 10 * 60 * 1000) fail('invalid_batch_contract');
    const ids = new Set(), texts = new Set();
    for (const item of batch.items) {
      if (!/^[a-f0-9]{24}$/.test(item.note_id || '') || typeof item.text !== 'string' ||
        !item.text.trim() || item.text.length > 500 || /[\r\n]/.test(item.text) ||
        ids.has(item.note_id) || texts.has(item.text.normalize('NFKC').replace(/\s/g,''))) fail('duplicate_or_invalid_item');
      ids.add(item.note_id); texts.add(item.text.normalize('NFKC').replace(/\s/g,''));
      for (const key of ['editor','title','comments','send']) {
        if (typeof item.selectors?.[key] !== 'string' || !item.selectors[key] || item.selectors[key].length > 300)
          fail('missing_observed_selector');
      }
      const matches = context.pages().filter(tab => noteOf(tab.url()) === item.note_id);
      if (matches.length !== 1) fail('target_tab_missing_or_ambiguous');
      owned.push({page:matches[0], item});
    }
    // Entire batch preflight before changing any editor.
    for (const row of owned) await inspect(row.page, row.item, '');
    const binding = '__panseBatchPause_' + batch.batch_id.replace(/[^a-zA-Z0-9]/g,'_');
    for (const row of owned) {
      if (await row.page.evaluate(() => !!window.__panseBatchGuard)) fail('page_has_existing_batch');
      await row.page.exposeBinding(binding, async () => { await pause('waiting_page_changed'); });
      row.route = async route => {
        if (row.phase !== 'ready' && !['GET','HEAD','OPTIONS'].includes(route.request().method())) {
          stopped = true; result.reason = 'unexpected_write_during_preparation'; await route.abort();
        } else await route.fallback();
      };
      await row.page.route('**/*', row.route);
      await row.page.evaluate(({item, profile, expiresAt, binding}) => {
        const editor = document.querySelector(item.selectors.editor);
        const send = document.querySelector(item.selectors.send);
        const original = {editor, send};
        const guard = window.__panseBatchGuard = {phase:'preparing', expiresAt};
        const currentText = () => 'value' in editor ? editor.value : editor.innerText;
        const valid = (checkEditable = true) => {
          const self = [...document.querySelectorAll('a[href]')].filter(el =>
            el.getClientRects().length && el.textContent.trim() === '我');
          return Date.now() < expiresAt && self.length === 1 &&
            new URL(self[0].href).pathname === `/user/profile/${profile}` &&
            document.querySelector(item.selectors.editor) === original.editor &&
            document.querySelector(item.selectors.send) === original.send &&
            document.querySelectorAll(item.selectors.editor).length === 1 &&
            document.querySelector(item.selectors.title)?.textContent.trim() === item.title &&
            (!checkEditable || (!editor.disabled && !editor.readOnly && !send.disabled)) &&
            new URL(location.href).pathname.replace(/\/$/,'').endsWith('/' + item.note_id) &&
            !/安全验证|安全校验|访问过于频繁|操作过于频繁|请求频繁|账号异常|登录异常|滑块验证|人机验证|请完成验证|扫码登录|登录后查看/.test(document.body.innerText);
        };
        const stop = () => { if (guard.phase !== 'paused') {
          guard.phase = 'paused'; window[binding]().catch(() => {});
        }};
        const listener = event => {
          const sending = event.type === 'submit' || (event.type === 'click' && send.contains(event.target)) ||
            (event.type === 'keydown' && event.key === 'Enter' && editor.contains(event.target));
          if (!sending) return;
          if (event.type === 'submit' && event.isTrusted && guard.phase === 'user_action_pending' && guard.nativeSubmitPending) {
            guard.nativeSubmitPending = false; return;
          }
          if (guard.phase !== 'ready' || !event.isTrusted || !valid() || currentText() !== item.text) {
            event.preventDefault(); event.stopImmediatePropagation();
            if (guard.phase === 'ready') stop();
          } else {
            guard.phase = 'user_action_pending';
            guard.nativeSubmitPending = event.type !== 'submit';
          }
          // Never click, dispatch, or submit. A permitted native user action continues unchanged.
        };
        for (const event of ['submit','click','keydown']) document.addEventListener(event,listener,true);
        let queued = false;
        const observer = new MutationObserver(() => {
          if (queued || !['ready','user_action_pending'].includes(guard.phase)) return;
          queued = true; queueMicrotask(() => { queued = false; if (!valid(guard.phase === 'ready')) stop(); });
        });
        observer.observe(document.body,{subtree:true,childList:true,attributes:true,characterData:true});
        window.addEventListener('pagehide',stop,{once:true});
        window.addEventListener('focus',() => { if (!valid(guard.phase === 'ready')) stop(); });
        setTimeout(stop,Math.max(0,expiresAt-Date.now()));
      }, {item:row.item, profile:batch.expected_profile_id, expiresAt:Date.parse(batch.expires_at), binding});
    }
    for (const row of owned) {
      if (stopped) fail(result.reason || 'batch_stopped');
      await inspect(row.page,row.item,'');
      await row.page.locator(row.item.selectors.editor).fill(row.item.text,{timeout:5000});
      if (stopped) fail(result.reason || 'batch_stopped');
      await inspect(row.page,row.item,row.item.text);
      result.items.push({note_id:row.item.note_id,status:'prefilled',submission_status:'not_submitted'});
    }
    for (const row of owned) await inspect(row.page,row.item,row.item.text);
    if (stopped) fail(result.reason || 'batch_stopped');
    // Browser-internal visibility only; never operate OS windows or everyday profiles.
    const cdp = await context.newCDPSession(owned[0].page);
    try {
      const {windowId} = await cdp.send('Browser.getWindowForTarget');
      await cdp.send('Browser.setWindowBounds',{windowId,bounds:{windowState:'normal'}});
      await cdp.send('Browser.setWindowBounds',{windowId,bounds:{left:80,top:80,width:1280,height:900}});
      const {bounds} = await cdp.send('Browser.getWindowBounds',{windowId});
      if (bounds.windowState !== 'normal' || bounds.left < 0 || bounds.top < 0) fail('visibility_not_verified');
      result.browser_window_bounds_verified = true;
    } finally { await cdp.detach(); }
    if (stopped || !validTime()) fail('batch_stopped_or_expired');
    for (const row of owned) {
      await inspect(row.page,row.item,row.item.text);
      row.phase = 'ready';
      await row.page.unroute('**/*',row.route);
      await row.page.evaluate(() => { window.__panseBatchGuard.phase = 'ready'; });
    }
    // A bounded human handoff is the only exception to immediate tab cleanup.
    // Close only these four owned tabs at expiry; never clear drafts or other tabs.
    const expiry = setTimeout(async () => {
      await pause('batch_expired');
      for (const row of owned) { try { await row.page.close(); } catch {} }
    },Math.max(0,Date.parse(batch.expires_at)-now()));
    expiry.unref?.();
    result.status = 'ready_for_human_batch'; result.ready_count = 4; result.notify_user = true;
    result.expires_at = batch.expires_at;
    result.browser_handoff = 'four_tabs_in_same_dedicated_browser';
    result.expires_action = 'pause_and_close_only_the_four_batch_tabs';
    return result;
  } catch (error) {
    await pause(error.safeCode || 'browser_runtime_error');
    result.ready_count = 0;
    // Keep partial drafts intact. Never erase user content or retry an uncertain fill.
    return result;
  }
}
