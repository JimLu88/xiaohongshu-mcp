#!/usr/bin/env node
/**
 * Bounded same-tab detail navigation for the Codex in-app browser.
 *
 * This adapter starts from an already verified Xiaohongshu search page. It
 * never creates a tab, calls goto/back, logs in, or performs an account or
 * publishing action. A navigation attempt is accepted only when a read-only
 * probe proves that the expected note detail is visible.
 */

export const XHS_DETAIL_NAVIGATION_CONTRACT = Object.freeze({
  contract_id: "panse-xhs-iab-detail-navigation.v2",
  maximum_navigation_actions_per_call: 1,
  maximum_user_tab_claims_per_recovery: 1,
  action: "same_tab_exact_target_semantic_click",
  required_preconditions: [
    "account_identity_verified",
    "search_page_verified",
    "target_identity_verified",
    "risk_state_clear",
  ],
  new_tab_allowed: false,
  goto_allowed: false,
  history_navigation_allowed: false,
  coordinate_click_allowed: false,
  blind_retry_allowed: false,
  post_timeout_read_only_verification_required: true,
  released_user_tab_claim_allowed: true,
});

function detailStateProbe(target) {
  const normalize = (value) =>
    String(value ?? "")
      .replace(/\s+/g, " ")
      .replace(/\|/g, "｜")
      .trim();
  const visible = (element) => {
    if (!(element instanceof Element)) return false;
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity || "1") !== 0 &&
      rect.width > 0 &&
      rect.height > 0
    );
  };

  const bodyText = normalize(document.body?.innerText);
  const expectedTitle = normalize(target.expected_title);
  const url = String(location.href);
  const path = String(location.pathname);
  const noteIdInLocation = url.includes(target.note_id);
  const titleVisible = expectedTitle.length > 0 && bodyText.includes(expectedTitle);
  const visibleEditors = Array.from(
    document.querySelectorAll("[contenteditable='true']"),
  ).filter(visible).length;
  const visibleDetailRoots = Array.from(
    document.querySelectorAll(
      "[class*='note-detail'], [class*='detail-mask'], [class*='note-container'], [class*='comments-container']",
    ),
  ).filter(visible).length;
  const searchRoute = /\/search_result(?:\/|$)/.test(path);
  const detailSurfacePresent =
    visibleEditors > 0 ||
    visibleDetailRoots > 0 ||
    (noteIdInLocation && !searchRoute);

  return {
    current_path: path,
    note_id_in_location: noteIdInLocation,
    expected_title_visible: titleVisible,
    visible_editor_count: visibleEditors,
    visible_detail_root_count: visibleDetailRoots,
    search_route: searchRoute,
    detail_surface_present: detailSurfacePresent,
    target_confirmed:
      noteIdInLocation && titleVisible && detailSurfacePresent,
  };
}

function classifyError(error) {
  const text = `${error?.name ?? ""} ${error?.message ?? ""}`;
  if (/disconnected|session.*(?:reset|closed)|target.*closed|tab.*(?:missing|closed)/i.test(text)) {
    return "control_session_unavailable";
  }
  if (/timeout/i.test(text)) return "timeout";
  return "error";
}

function validateTarget(options) {
  const noteId = String(options.noteId ?? "").trim();
  const expectedTitle = String(options.expectedTitle ?? "").trim();
  if (!/^[0-9a-z]+$/i.test(noteId)) {
    throw new TypeError("noteId must be a non-empty alphanumeric Xiaohongshu note id");
  }
  if (!expectedTitle) {
    throw new TypeError("expectedTitle is required");
  }
  return { note_id: noteId, expected_title: expectedTitle };
}

async function safeProbe(tab, target, timeoutMs) {
  try {
    const state = await tab.playwright.evaluate(detailStateProbe, target, {
      timeoutMs,
    });
    return { ok: true, state };
  } catch (error) {
    return { ok: false, error_kind: classifyError(error) };
  }
}

async function safeValue(action) {
  try {
    return { ok: true, value: await action() };
  } catch (error) {
    return { ok: false, error_kind: classifyError(error) };
  }
}

function blocked(reason, target, extra = {}) {
  return {
    contract_id: XHS_DETAIL_NAVIGATION_CONTRACT.contract_id,
    status: "blocked",
    reason,
    note_id: target?.note_id,
    coordinate_click_used: false,
    new_tab_used: false,
    goto_used: false,
    history_navigation_used: false,
    blind_retry_used: false,
    ...extra,
  };
}

function externalBlocked(reason, target, extra = {}) {
  return {
    ...blocked(reason, target, extra),
    status: "blocked_external_runtime",
  };
}

function isExactDetailInfo(info, target) {
  try {
    const url = new URL(String(info?.url ?? ""));
    return (
      url.origin === "https://www.xiaohongshu.com" &&
      url.href.includes(target.note_id) &&
      !/\/search_result(?:\/|$)/.test(url.pathname)
    );
  } catch {
    return false;
  }
}

export async function verifyXhsDetailTarget(tab, options = {}) {
  if (!tab?.playwright?.evaluate) {
    throw new TypeError("a documented in-app Browser Tab is required");
  }
  const target = validateTarget(options);
  const probeTimeoutMs = Math.min(
    Math.max(Number(options.probeTimeoutMs ?? 3_000), 500),
    5_000,
  );
  const proof = await safeProbe(tab, target, probeTimeoutMs);
  if (!proof.ok) {
    return blocked("browser_control_unavailable_during_read_only_verification", target, {
      probe_error_kind: proof.error_kind,
      navigation_actions_attempted: 0,
    });
  }
  return {
    contract_id: XHS_DETAIL_NAVIGATION_CONTRACT.contract_id,
    status: proof.state.target_confirmed ? "verified" : "not_verified",
    note_id: target.note_id,
    detail_state: proof.state,
    navigation_actions_attempted: 0,
    coordinate_click_used: false,
    new_tab_used: false,
    goto_used: false,
    history_navigation_used: false,
    blind_retry_used: false,
  };
}

export async function recoverXhsDetailTarget(browser, options = {}) {
  if (!browser?.tabs?.list || !browser?.tabs?.get) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const target = validateTarget(options);
  const probeTimeoutMs = Math.min(
    Math.max(Number(options.probeTimeoutMs ?? 3_000), 500),
    5_000,
  );
  const verify = async (tab) => safeProbe(tab, target, probeTimeoutMs);
  const listResult = await safeValue(() => browser.tabs.list());
  const infos = listResult.ok ? listResult.value ?? [] : [];
  const candidates = infos.filter((info) => isExactDetailInfo(info, target));
  if (candidates.length > 1) {
    return blocked("rebindable_detail_tab_not_unique", target, {
      detail_candidates_found: candidates.length,
      navigation_actions_attempted: 0,
      user_tab_claims_attempted: 0,
    });
  }
  if (candidates.length === 1) {
    const tabResult = await safeValue(() => browser.tabs.get(candidates[0].id));
    if (tabResult.ok) {
      const proof = await verify(tabResult.value);
      if (proof.ok && proof.state.target_confirmed) {
        return {
          contract_id: XHS_DETAIL_NAVIGATION_CONTRACT.contract_id,
          status: "verified",
          method: "rebind_existing_detail_tab_after_control_reset",
          tab: tabResult.value,
          note_id: target.note_id,
          detail_state: proof.state,
          navigation_actions_attempted: 0,
          user_tab_claims_attempted: 0,
          coordinate_click_used: false,
          new_tab_used: false,
          goto_used: false,
          history_navigation_used: false,
          blind_retry_used: false,
        };
      }
      if (proof.ok) {
        return blocked("rebound_detail_target_not_verified", target, {
          detail_state: proof.state,
          navigation_actions_attempted: 0,
          user_tab_claims_attempted: 0,
        });
      }
    }
  }

  if (!browser?.user?.openTabs || !browser?.user?.claimTab) {
    return externalBlocked("visible_user_tab_recovery_api_unavailable", target, {
      browser_error_kind: listResult.ok ? undefined : listResult.error_kind,
      navigation_actions_attempted: 0,
      user_tabs_inspected: 0,
      user_tab_claims_attempted: 0,
    });
  }
  const openTabsResult = await safeValue(() => browser.user.openTabs());
  if (!openTabsResult.ok) {
    return externalBlocked("visible_user_tabs_unavailable_during_detail_recovery", target, {
      browser_error_kind: listResult.ok ? undefined : listResult.error_kind,
      user_tabs_error_kind: openTabsResult.error_kind,
      navigation_actions_attempted: 0,
      user_tabs_inspected: 0,
      user_tab_claims_attempted: 0,
    });
  }
  const openTabs = openTabsResult.value ?? [];
  const visibleCandidates = openTabs.filter((info) => isExactDetailInfo(info, target));
  if (visibleCandidates.length > 1) {
    return blocked("visible_user_detail_tab_not_unique", target, {
      detail_candidates_found: visibleCandidates.length,
      navigation_actions_attempted: 0,
      user_tabs_inspected: openTabs.length,
      user_tab_claims_attempted: 0,
    });
  }
  if (visibleCandidates.length === 0) {
    return externalBlocked("no_rebindable_detail_tab_after_control_reset", target, {
      browser_error_kind: listResult.ok ? undefined : listResult.error_kind,
      rebindable_tabs_found: infos.length,
      navigation_actions_attempted: 0,
      user_tabs_inspected: openTabs.length,
      user_tab_claims_attempted: 0,
    });
  }
  const claimResult = await safeValue(() =>
    browser.user.claimTab(visibleCandidates[0]),
  );
  if (!claimResult.ok) {
    return externalBlocked("visible_user_detail_tab_claim_failed", target, {
      claim_error_kind: claimResult.error_kind,
      navigation_actions_attempted: 0,
      user_tabs_inspected: openTabs.length,
      user_tab_claims_attempted: 1,
    });
  }
  const proof = await verify(claimResult.value);
  if (!proof.ok) {
    return externalBlocked("browser_control_unavailable_after_detail_tab_claim", target, {
      probe_error_kind: proof.error_kind,
      navigation_actions_attempted: 0,
      user_tabs_inspected: openTabs.length,
      user_tab_claims_attempted: 1,
    });
  }
  if (!proof.state.target_confirmed) {
    return blocked("claimed_user_detail_target_not_verified", target, {
      detail_state: proof.state,
      navigation_actions_attempted: 0,
      user_tabs_inspected: openTabs.length,
      user_tab_claims_attempted: 1,
    });
  }
  return {
    contract_id: XHS_DETAIL_NAVIGATION_CONTRACT.contract_id,
    status: "verified",
    method: "claim_released_user_detail_tab_after_control_reset",
    tab: claimResult.value,
    note_id: target.note_id,
    detail_state: proof.state,
    navigation_actions_attempted: 0,
    user_tabs_inspected: openTabs.length,
    user_tab_claims_attempted: 1,
    coordinate_click_used: false,
    new_tab_used: false,
    goto_used: false,
    history_navigation_used: false,
    blind_retry_used: false,
  };
}

export async function openXhsDetailFromSearch(tab, options = {}) {
  if (
    !tab?.playwright?.locator ||
    !tab?.playwright?.evaluate ||
    !tab?.playwright?.waitForTimeout
  ) {
    throw new TypeError("a documented in-app Browser Tab is required");
  }
  const target = validateTarget(options);
  const preconditions = options.preconditions ?? {};
  const missingPreconditions =
    XHS_DETAIL_NAVIGATION_CONTRACT.required_preconditions.filter(
      (name) => preconditions[name] !== true,
    );
  if (missingPreconditions.length > 0) {
    return blocked("required_preconditions_not_verified", target, {
      missing_preconditions: missingPreconditions,
      navigation_actions_attempted: 0,
    });
  }

  const actionTimeoutMs = Math.min(
    Math.max(Number(options.actionTimeoutMs ?? 5_000), 500),
    8_000,
  );
  const probeTimeoutMs = Math.min(
    Math.max(Number(options.probeTimeoutMs ?? 3_000), 500),
    5_000,
  );
  const settleMs = Math.min(
    Math.max(Number(options.settleMs ?? 700), 100),
    2_000,
  );
  const selector = `a[href*="${target.note_id}"]`;
  let link;
  try {
    link = tab.playwright
      .locator(selector)
      .filter({ hasText: target.expected_title, visible: true });
  } catch (error) {
    return blocked("browser_control_unavailable_during_target_preflight", target, {
      selector,
      preflight_error_kind: classifyError(error),
      navigation_actions_attempted: 0,
    });
  }
  const countResult = await safeValue(() => link.count());
  if (!countResult.ok) {
    return blocked("browser_control_unavailable_during_target_preflight", target, {
      selector,
      preflight_error_kind: countResult.error_kind,
      navigation_actions_attempted: 0,
    });
  }
  const count = countResult.value;
  if (count !== 1) {
    return blocked(
      count === 0 ? "exact_target_link_missing" : "exact_target_link_not_unique",
      target,
      {
        selector,
        matched_controls: count,
        navigation_actions_attempted: 0,
      },
    );
  }
  const visibleResult = await safeValue(() => link.isVisible());
  if (!visibleResult.ok) {
    return blocked("browser_control_unavailable_during_target_preflight", target, {
      selector,
      preflight_error_kind: visibleResult.error_kind,
      navigation_actions_attempted: 0,
    });
  }
  if (!visibleResult.value) {
    return blocked("exact_target_link_not_visible", target, {
      selector,
      navigation_actions_attempted: 0,
    });
  }
  const hrefResult = await safeValue(() =>
    link.getAttribute("href", { timeoutMs: probeTimeoutMs }),
  );
  if (!hrefResult.ok) {
    return blocked("browser_control_unavailable_during_target_preflight", target, {
      selector,
      preflight_error_kind: hrefResult.error_kind,
      navigation_actions_attempted: 0,
    });
  }
  const href = hrefResult.value;
  if (!String(href ?? "").includes(target.note_id)) {
    return blocked("exact_target_link_href_mismatch", target, {
      selector,
      navigation_actions_attempted: 0,
    });
  }

  let clickResult = "ok";
  try {
    await link.click({ force: true, timeoutMs: actionTimeoutMs });
  } catch (error) {
    clickResult = classifyError(error);
  }
  const settleResult = await safeValue(() =>
    tab.playwright.waitForTimeout(settleMs),
  );
  const proof = await safeProbe(tab, target, probeTimeoutMs);
  if (!proof.ok) {
    if (options.browser) {
      const recovery = await recoverXhsDetailTarget(options.browser, {
        noteId: target.note_id,
        expectedTitle: target.expected_title,
        probeTimeoutMs,
      });
      if (recovery.status === "verified") {
        return {
          contract_id: XHS_DETAIL_NAVIGATION_CONTRACT.contract_id,
          status: "opened",
          method: recovery.method,
          tab: recovery.tab,
          note_id: target.note_id,
          click_result: clickResult,
          recovered_after_control_reset: true,
          detail_state: recovery.detail_state,
          navigation_actions_attempted: 1,
          user_tab_claims_attempted: recovery.user_tab_claims_attempted,
          coordinate_click_used: false,
          new_tab_used: false,
          goto_used: false,
          history_navigation_used: false,
          blind_retry_used: false,
        };
      }
      return externalBlocked("browser_control_unavailable_after_navigation", target, {
        selector,
        click_result: clickResult,
        settle_error_kind: settleResult.ok ? undefined : settleResult.error_kind,
        post_navigation_probe_error_kind: proof.error_kind,
        recovery_status: recovery.status,
        recovery_reason: recovery.reason,
        navigation_actions_attempted: 1,
        user_tab_claims_attempted: recovery.user_tab_claims_attempted ?? 0,
        resume_contract: "stop without a second navigation when neither a controlled tab nor one exact visible user detail tab can be verified",
      });
    }
    return blocked("browser_control_unavailable_after_navigation", target, {
      selector,
      click_result: clickResult,
      settle_error_kind: settleResult.ok ? undefined : settleResult.error_kind,
      post_navigation_probe_error_kind: proof.error_kind,
      navigation_actions_attempted: 1,
      resume_contract: "rebind the existing in-app browser tab, then call verifyXhsDetailTarget before considering any fresh navigation",
    });
  }
  if (!proof.state.target_confirmed) {
    return blocked("target_detail_not_confirmed_after_single_semantic_click", target, {
      selector,
      click_result: clickResult,
      detail_state: proof.state,
      navigation_actions_attempted: 1,
    });
  }

  return {
    contract_id: XHS_DETAIL_NAVIGATION_CONTRACT.contract_id,
    status: "opened",
    method: "same_tab_exact_target_semantic_click",
    note_id: target.note_id,
    click_result: clickResult,
    opened_despite_ambiguous_timeout: clickResult === "timeout",
    detail_state: proof.state,
    navigation_actions_attempted: 1,
    coordinate_click_used: false,
    new_tab_used: false,
    goto_used: false,
    history_navigation_used: false,
    blind_retry_used: false,
  };
}
