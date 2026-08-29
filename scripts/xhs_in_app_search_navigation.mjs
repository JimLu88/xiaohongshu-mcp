#!/usr/bin/env node
/**
 * Bounded Xiaohongshu search workspace acquisition and search submission for
 * the Codex in-app browser.
 *
 * A browser binding can remain valid after its task tabs are cleaned up. This
 * module therefore treats an empty task-tab list as recoverable. Workspace
 * bootstrap is deliberately split into one documented Browser RPC per public
 * stage so a control reset cannot hide whether a visible-tab inspection, tab
 * claim, tab creation, or homepage navigation was attempted. A query is still
 * submitted only after the caller has independently verified account identity
 * and risk state.
 */

const XHS_ORIGIN = "https://www.xiaohongshu.com";
const XHS_HOME_URL = `${XHS_ORIGIN}/`;
const SEARCH_INPUT_SELECTOR =
  "textarea.textarea, input[placeholder*='搜索'], textarea[placeholder*='搜索']";

export const XHS_SEARCH_NAVIGATION_CONTRACT = Object.freeze({
  contract_id: "panse-xhs-iab-search-navigation.v13",
  browser_family: "iab",
  maximum_control_rpcs_per_workspace_stage: 1,
  empty_workspace_staged_bootstrap: true,
  maximum_new_tabs_per_acquire_call: 0,
  maximum_user_tab_claims_per_acquire_call: 0,
  maximum_homepage_navigations_per_acquire_call: 0,
  maximum_new_tabs_per_bootstrap_create_stage: 1,
  maximum_homepage_navigations_per_bootstrap_navigation_stage: 1,
  bootstrap_creation_requires_visible_absence_proof: true,
  indeterminate_navigation_zero_action_recovery: true,
  maximum_post_indeterminate_navigation_recovery_rpcs: 1,
  navigation_replay_after_indeterminate_result_allowed: false,
  released_workspace_recovery_after_task_candidate_loss: true,
  maximum_released_workspace_list_rpcs: 1,
  maximum_released_workspace_claim_rpcs: 1,
  lost_task_id_reused_as_current_id: false,
  maximum_user_tab_claims_per_recovery: 1,
  homepage_navigation_soft_deadline_ms: 8_000,
  acquire_result_soft_deadline_ms: 12_000,
  existing_workspace_staged_verification: true,
  existing_workspace_verification_surface:
    "documented_dom_cua_visible_dom_single_rpc",
  maximum_existing_workspace_verification_rpcs: 1,
  existing_workspace_verification_includes_identity_and_risk: true,
  additional_identity_dom_rpc_allowed_after_workspace_verification: false,
  local_timer_claims_external_rpc_preemption: false,
  maximum_search_submissions_per_call: 1,
  required_search_preconditions: [
    "account_identity_verified",
    "workspace_verified",
    "risk_state_clear",
  ],
  direct_search_url_allowed: false,
  alternate_browser_allowed: false,
  coordinate_action_allowed: false,
  blind_retry_allowed: false,
  unique_exact_id_locator_preferred: true,
  proven_operable_dom_index_fallback_allowed: true,
  empty_tab_list_invalidates_browser_binding: false,
  released_user_tab_claim_allowed: true,
  browser_binding_verification:
    "documented_iab_capability_surface_plus_successful_task_tab_list",
});

function classifyError(error) {
  const text = `${error?.name ?? ""} ${error?.message ?? ""}`;
  if (/disconnected|session.*(?:reset|closed)|target.*closed|tab.*(?:missing|closed)/i.test(text)) {
    return "control_session_unavailable";
  }
  if (/timeout/i.test(text)) return "timeout";
  return "error";
}

async function safeValue(action) {
  try {
    return { ok: true, value: await action() };
  } catch (error) {
    return { ok: false, error_kind: classifyError(error) };
  }
}

async function safeValueBeforeDeadline(action, timeoutMs) {
  let timer;
  const actionResult = Promise.resolve()
    .then(action)
    .then(
      (value) => ({ ok: true, value }),
      (error) => ({ ok: false, error_kind: classifyError(error) }),
    );
  const deadlineResult = new Promise((resolve) => {
    timer = setTimeout(
      () => resolve({ ok: false, error_kind: "soft_deadline" }),
      timeoutMs,
    );
  });
  const result = await Promise.race([actionResult, deadlineResult]);
  if (timer !== undefined) clearTimeout(timer);
  return result;
}

function remainingDeadlineMs(deadlineAt, capMs = Number.POSITIVE_INFINITY) {
  return Math.max(10, Math.min(capMs, deadlineAt - Date.now()));
}

function workspaceStateProbe(input = {}) {
  const normalize = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
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
  const selector = String(input.selector ?? "");
  const query = normalize(input.query);
  const bodyText = normalize(document.body?.innerText);
  const title = normalize(document.title);
  const searchInputs = Array.from(document.querySelectorAll(selector));
  const idCounts = new Map();
  for (const element of document.querySelectorAll("[id]")) {
    const id = String(element.id ?? "");
    if (id) idCounts.set(id, (idCounts.get(id) ?? 0) + 1);
  }
  const candidates = searchInputs.map((element, domIndex) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const viewportLeft = Math.max(0, rect.left);
    const viewportTop = Math.max(0, rect.top);
    const viewportRight = Math.min(window.innerWidth, rect.right);
    const viewportBottom = Math.min(window.innerHeight, rect.bottom);
    const inViewport =
      viewportRight > viewportLeft && viewportBottom > viewportTop;
    const probeX = inViewport ? (viewportLeft + viewportRight) / 2 : -1;
    const probeY = inViewport ? (viewportTop + viewportBottom) / 2 : -1;
    const topElement = inViewport ? document.elementFromPoint(probeX, probeY) : null;
    const topmost = Boolean(
      topElement &&
        (topElement === element ||
          element.contains(topElement) ||
          topElement.contains(element)),
    );
    const visuallyVisible = visible(element);
    const hiddenBySemanticAncestor = Boolean(
      element.closest("[aria-hidden='true'], [inert]"),
    );
    const disabled =
      element.matches(":disabled") ||
      element.getAttribute("aria-disabled") === "true";
    const readOnly = Boolean(element.readOnly);
    const operable =
      visuallyVisible &&
      inViewport &&
      topmost &&
      !hiddenBySemanticAncestor &&
      !disabled &&
      !readOnly &&
      style.pointerEvents !== "none";
    return {
      dom_index: domIndex,
      tag_name: element.tagName.toLowerCase(),
      id: String(element.id ?? ""),
      exact_id_unique:
        String(element.id ?? "").length > 0 && idCounts.get(String(element.id)) === 1,
      name: String(element.getAttribute("name") ?? ""),
      placeholder: String(element.getAttribute("placeholder") ?? ""),
      aria_label: String(element.getAttribute("aria-label") ?? ""),
      class_name: String(element.className ?? ""),
      visually_visible: visuallyVisible,
      in_viewport: inViewport,
      topmost,
      hidden_by_semantic_ancestor: hiddenBySemanticAncestor,
      disabled,
      read_only: readOnly,
      pointer_events: String(style.pointerEvents),
      operable,
      value_matches_query: query.length > 0 && normalize(element.value) === query,
      rect: {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
    };
  });
  const visibleCandidates = candidates.filter((candidate) => candidate.visually_visible);
  const operableCandidates = candidates.filter((candidate) => candidate.operable);
  const riskSignalObserved =
    /验证码|安全验证|访问频繁|账号异常|登录异常/.test(bodyText);
  const resultLinks = Array.from(
    document.querySelectorAll(
      "a[href*='/search_result/'], a[href*='/explore/'], a[href*='/discovery/item/']",
    ),
  ).filter(visible);
  const explicitEmpty = /暂无(?:相关)?结果|没有找到|无搜索结果/.test(bodyText);
  const queryMatched =
    operableCandidates.some((candidate) => candidate.value_matches_query) ||
    title.includes(query) ||
    bodyText.includes(query);
  const searchRoute = /\/search_result(?:\/|$)/.test(location.pathname);
  return {
    current_origin: String(location.origin),
    current_path: String(location.pathname),
    visible_search_input_count: visibleCandidates.length,
    operable_search_input_count: operableCandidates.length,
    search_input_candidates: candidates,
    operable_search_input:
      operableCandidates.length === 1 ? operableCandidates[0] : null,
    risk_signal_observed: riskSignalObserved,
    workspace_verified:
      location.origin === "https://www.xiaohongshu.com" &&
      operableCandidates.length === 1 &&
      !riskSignalObserved,
    search_route: searchRoute,
    query_matched: queryMatched,
    visible_result_link_count: resultLinks.length,
    explicit_empty_result: explicitEmpty,
    search_page_verified:
      searchRoute &&
      operableCandidates.length === 1 &&
      queryMatched &&
      (resultLinks.length > 0 || explicitEmpty) &&
      !riskSignalObserved,
  };
}

function exactIdSelectorForTarget(target) {
  const id = String(target?.id ?? "");
  if (target?.exact_id_unique !== true) return null;
  if (!/^[A-Za-z_][A-Za-z0-9_-]*$/.test(id)) return null;
  return `#${id}`;
}

function scalarObjectText(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";
  const direct = Object.entries(value)
    .filter(([, item]) => item === null || ["string", "number", "boolean"].includes(typeof item))
    .map(([key, item]) => `${key}=${String(item ?? "")}`)
    .join(" ");
  const attributes = [value.attributes, value.attrs, value.properties]
    .filter((item) => item && typeof item === "object" && !Array.isArray(item))
    .flatMap((item) =>
      Object.entries(item)
        .filter(([, field]) =>
          field === null || ["string", "number", "boolean"].includes(typeof field),
        )
        .map(([key, field]) => `${key}=${String(field ?? "")}`),
    )
    .join(" ");
  return `${direct} ${attributes}`.trim();
}

function collectVisibleDomSegments(snapshot) {
  const segments = [];
  const seen = new Set();
  const add = (value) => {
    const text = String(value ?? "").replace(/\s+/g, " ").trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    segments.push(text);
  };
  const visit = (value) => {
    if (typeof value === "string") {
      for (const match of value.matchAll(/<(?:input|textarea)\b[^>]*>/gi)) add(match[0]);
      for (const match of value.matchAll(/<a\b[^>]*>(?:[^<]{0,160})/gi)) add(match[0]);
      if (!/[<>]/.test(value)) add(value);
      return;
    }
    if (Array.isArray(value)) {
      for (const item of value) visit(item);
      return;
    }
    if (!value || typeof value !== "object") return;
    const direct = scalarObjectText(value);
    add(direct);
    if (
      /(?:tag(?:_name|Name)?|node(?:_name|Name)|role)\s*[=:]\s*["']?(?:a|link)\b/i.test(
        direct,
      )
    ) {
      const descendantScalars = [];
      const collectDescendants = (item, depth) => {
        if (depth > 3 || item === null || item === undefined) return;
        if (["string", "number", "boolean"].includes(typeof item)) {
          descendantScalars.push(String(item));
          return;
        }
        if (Array.isArray(item)) {
          for (const child of item) collectDescendants(child, depth + 1);
          return;
        }
        if (typeof item === "object") {
          for (const child of Object.values(item)) collectDescendants(child, depth + 1);
        }
      };
      for (const [key, item] of Object.entries(value)) {
        if (!["attributes", "attrs", "properties"].includes(key)) {
          collectDescendants(item, 0);
        }
      }
      add(`${direct} descendant_text=${descendantScalars.join(" ")}`);
    }
    for (const item of Object.values(value)) {
      if (item && typeof item === "object") visit(item);
      else if (typeof item === "string" && /<(?:input|textarea)\b/i.test(item)) visit(item);
    }
  };
  visit(snapshot);
  return segments;
}

function extractVisibleDomField(segment, names) {
  for (const name of names) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const patterns = [
      new RegExp(`(?:^|[\\s,{])${escaped}\\s*[=:]\\s*["']([^"']*)["']`, "i"),
      new RegExp(`(?:^|[\\s,{])${escaped}\\s*[=:]\\s*([^\\s,}]+)`, "i"),
      new RegExp(`\\b${escaped}\\s*=\\s*["']([^"']*)["']`, "i"),
    ];
    for (const pattern of patterns) {
      const match = segment.match(pattern);
      if (match) return String(match[1] ?? "");
    }
  }
  return "";
}

function analyzeVisibleDomWorkspace(snapshot, candidate) {
  let serialized;
  try {
    serialized = typeof snapshot === "string" ? snapshot : JSON.stringify(snapshot);
  } catch {
    serialized = "";
  }
  const normalized = String(serialized ?? "").replace(/\s+/g, " ").trim();
  const riskSignalObserved =
    /验证码|安全验证|访问频繁|账号异常|登录异常/.test(normalized);
  const loginPromptObserved =
    /(?:^|[\s>"'=])(?:请先登录|登录后|手机号登录|扫码登录|密码登录|注册\/登录|登录\/注册)(?:$|[\s<"'])/.test(
      normalized,
    );
  const candidates = collectVisibleDomSegments(snapshot)
    .filter((segment) => {
      const control =
        /<(?:input|textarea)\b/i.test(segment) ||
        /(?:tag(?:_name|Name)?|node(?:_name|Name)|role)\s*[=:]\s*["']?(?:input|textarea|textbox|searchbox)\b/i.test(
          segment,
        );
      const searchMarker =
        /search-input-in-feeds|aiSearchTextarea/i.test(segment) ||
        /(?:id|name)\s*[=:]\s*["']?[^\s,"'}]*(?:search[^\s,"'}]*input|input[^\s,"'}]*search)/i.test(
          segment,
        ) ||
        /placeholder\s*[=:]\s*["']?[^"'}]*(?:搜索|search)/i.test(segment) ||
        /class(?:Name|_name)?\s*[=:]\s*["']?[^"'}]*\btextarea\b/i.test(segment);
      const explicitlyUnavailable =
        /\bdisabled\s*[=:]\s*(?:true|["']disabled["'])\b/i.test(segment) ||
        /\breadonly\s*[=:]\s*(?:true|["']readonly["'])\b/i.test(segment) ||
        /<(?:input|textarea)\b[^>]*\sdisabled(?:\s|>)/i.test(segment) ||
        /<(?:input|textarea)\b[^>]*\sreadonly(?:\s|>)/i.test(segment) ||
        /aria-hidden\s*=\s*["']?true/i.test(segment) ||
        /\binert\b/i.test(segment);
      return control && searchMarker && !explicitlyUnavailable;
    })
    .map((segment, visibleDomIndex) => ({
      visible_dom_index: visibleDomIndex,
      node_id: extractVisibleDomField(segment, ["node_id", "nodeId"]),
      tag_name:
        segment.match(/<(input|textarea)\b/i)?.[1]?.toLowerCase() ??
        extractVisibleDomField(segment, ["tag_name", "tagName", "node_name", "nodeName"]),
      id: extractVisibleDomField(segment, ["id"]),
      name: extractVisibleDomField(segment, ["name"]),
      placeholder: extractVisibleDomField(segment, ["placeholder"]),
      aria_label: extractVisibleDomField(segment, ["aria-label", "aria_label", "ariaLabel"]),
      class_name: extractVisibleDomField(segment, ["class", "class_name", "className"]),
    }));
  const uniqueCandidates = [];
  const fingerprints = new Set();
  for (const item of candidates) {
    const fingerprint = [
      item.node_id,
      item.id,
      item.name,
      item.placeholder,
      item.aria_label,
      item.class_name,
    ].join("|");
    if (fingerprints.has(fingerprint)) continue;
    fingerprints.add(fingerprint);
    uniqueCandidates.push(item);
  }
  const exactCandidateVerified = Boolean(
    candidate?.id && isReusableWorkspaceInfo(candidate),
  );
  const operable = uniqueCandidates.length === 1 ? uniqueCandidates[0] : null;
  return {
    current_origin: exactCandidateVerified ? XHS_ORIGIN : null,
    current_path: exactCandidateVerified
      ? new URL(String(candidate.url)).pathname
      : null,
    verification_surface: "dom_cua_visible_dom",
    visible_dom_snapshot_received: normalized.length > 0,
    visible_dom_search_input_count: uniqueCandidates.length,
    operable_search_input_count: uniqueCandidates.length,
    operable_search_input: operable,
    risk_signal_observed: riskSignalObserved,
    login_prompt_observed: loginPromptObserved,
    exact_candidate_verified: exactCandidateVerified,
    workspace_verified:
      exactCandidateVerified &&
      normalized.length > 0 &&
      uniqueCandidates.length === 1 &&
      Boolean(operable?.node_id) &&
      !riskSignalObserved,
  };
}

function analyzeVisibleDomIdentity(snapshot, requiredProfileId, riskSignalObserved) {
  let serialized;
  try {
    serialized = typeof snapshot === "string" ? snapshot : JSON.stringify(snapshot);
  } catch {
    serialized = "";
  }
  const normalized = String(serialized ?? "").replace(/\s+/g, " ").trim();
  const loginPromptObserved =
    /(?:^|[\s>"'=])(?:请先登录|登录后|手机号登录|扫码登录|密码登录|注册\/登录|登录\/注册)(?:$|[\s<"'])/.test(
      normalized,
    );
  const profilePattern = /\/user\/profile\/([0-9a-f]{24})(?:[/?#\s"']|$)/i;
  const selfProfileLinks = collectVisibleDomSegments(snapshot)
    .filter((segment) => {
      const link =
        /<a\b/i.test(segment) ||
        /(?:tag(?:_name|Name)?|node(?:_name|Name)|role)\s*[=:]\s*["']?(?:a|link)\b/i.test(
          segment,
        );
      const href = extractVisibleDomField(segment, ["href"]);
      const label = extractVisibleDomField(segment, [
        "inner_text",
        "innerText",
        "text",
        "name",
        "aria-label",
        "aria_label",
        "ariaLabel",
        "node_value",
        "nodeValue",
      ]);
      const selfLabel =
        /(?:^|[\s>"'=])我(?:$|[\s<"'])/.test(segment) ||
        /^我$/.test(String(label).trim());
      return link && profilePattern.test(href || segment) && selfLabel;
    })
    .map((segment) => {
      const href = extractVisibleDomField(segment, ["href"]);
      const match = (href || segment).match(profilePattern);
      return {
        node_id: extractVisibleDomField(segment, ["node_id", "nodeId"]),
        profile_id: String(match?.[1] ?? "").toLowerCase(),
        href: href || (match ? `/user/profile/${match[1]}` : ""),
      };
    });
  const uniqueSelfLinks = [];
  const fingerprints = new Set();
  for (const link of selfProfileLinks) {
    const fingerprint = `${link.node_id}|${link.profile_id}|${link.href}`;
    if (fingerprints.has(fingerprint)) continue;
    fingerprints.add(fingerprint);
    uniqueSelfLinks.push(link);
  }
  const requiredMatches = uniqueSelfLinks.filter(
    (link) =>
      link.profile_id === requiredProfileId.toLowerCase() &&
      Boolean(link.node_id),
  );
  const verified =
    requiredMatches.length === 1 &&
    !loginPromptObserved &&
    !riskSignalObserved;
  return {
    verification_surface: "same_dom_cua_visible_dom_snapshot",
    bound_to_workspace_snapshot: true,
    additional_browser_rpc_required: false,
    required_profile_id: requiredProfileId,
    required_profile_href: `/user/profile/${requiredProfileId}`,
    visible_self_profile_link_count: uniqueSelfLinks.length,
    required_profile_self_link_match_count: requiredMatches.length,
    self_profile_node_id_present:
      requiredMatches.length === 1 && Boolean(requiredMatches[0].node_id),
    login_prompt_observed: loginPromptObserved,
    risk_signal_observed: riskSignalObserved,
    identity_verified: verified,
  };
}

async function safeProbe(tab, pageFunction, arg, timeoutMs) {
  try {
    const state = await tab.playwright.evaluate(pageFunction, arg, { timeoutMs });
    return { ok: true, state };
  } catch (error) {
    return { ok: false, error_kind: classifyError(error) };
  }
}

async function safeProbeBeforeDeadline(
  tab,
  pageFunction,
  arg,
  timeoutMs,
  deadlineMs,
) {
  const result = await safeValueBeforeDeadline(
    () => tab.playwright.evaluate(pageFunction, arg, { timeoutMs }),
    deadlineMs,
  );
  return result.ok
    ? { ok: true, state: result.value }
    : { ok: false, error_kind: result.error_kind };
}

function blocked(reason, extra = {}) {
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "blocked",
    reason,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
    ...extra,
  };
}

function externalBlocked(reason, extra = {}) {
  return {
    ...blocked(reason, extra),
    status: "blocked_external_runtime",
  };
}

function isReusableWorkspaceInfo(info) {
  try {
    const url = new URL(String(info?.url ?? ""));
    return (
      url.origin === XHS_ORIGIN &&
      (url.pathname === "/" ||
        /\/explore(?:\/|$)/.test(url.pathname) ||
        /\/search_result(?:\/|$)/.test(url.pathname))
    );
  } catch {
    return false;
  }
}

function isBlankTaskTabInfo(info) {
  return Boolean(info?.id) && String(info?.url ?? "") === "about:blank";
}

function limitedCandidate(info) {
  return {
    id: info?.id,
    title: String(info?.title ?? ""),
    url: String(info?.url ?? ""),
  };
}

function isSearchPageInfo(info) {
  try {
    const url = new URL(String(info?.url ?? ""));
    return (
      url.origin === XHS_ORIGIN &&
      /\/search_result(?:\/|$)/.test(url.pathname)
    );
  } catch {
    return false;
  }
}

async function verifyWorkspace(tab, timeoutMs, deadlineMs) {
  const probe = Number.isFinite(deadlineMs)
    ? safeProbeBeforeDeadline
    : safeProbe;
  return probe(
    tab,
    workspaceStateProbe,
    { selector: SEARCH_INPUT_SELECTOR },
    timeoutMs,
    deadlineMs,
  );
}

export async function inspectXhsSearchInputSurface(tab, options = {}) {
  if (!tab?.playwright?.evaluate) {
    throw new TypeError("a documented in-app Browser Tab is required");
  }
  const timeoutMs = Math.min(
    Math.max(Number(options.probeTimeoutMs ?? 3_000), 500),
    5_000,
  );
  const proof = await safeProbe(
    tab,
    workspaceStateProbe,
    {
      query: String(options.query ?? "").replace(/\s+/g, " ").trim(),
      selector: SEARCH_INPUT_SELECTOR,
    },
    timeoutMs,
  );
  if (!proof.ok) {
    return externalBlocked("browser_control_unavailable_during_search_surface_inspection", {
      probe_error_kind: proof.error_kind,
      search_submissions_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "inspected",
    surface_state: proof.state,
    search_submissions_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function rebindXhsSearchWorkspaceCandidate(browser, options = {}) {
  if (!browser?.tabs?.get) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const candidate = options.candidate;
  if (!candidate?.id || !isReusableWorkspaceInfo(candidate)) {
    return blocked("workspace_candidate_not_verified_for_rebind", {
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const tabResult = await safeValue(() => browser.tabs.get(candidate.id));
  if (!tabResult.ok) {
    return externalBlocked("existing_workspace_tab_rebind_failed", {
      browser_error_kind: tabResult.error_kind,
      workspace_candidate: candidate,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "workspace_tab_rebound",
    method: "rebind_exact_existing_workspace_candidate",
    tab: tabResult.value,
    workspace_candidate: candidate,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function inspectXhsVisibleWorkspaceCandidates(browser) {
  if (!browser?.user?.openTabs) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const openTabsResult = await safeValue(() => browser.user.openTabs());
  if (!openTabsResult.ok) {
    return externalBlocked("visible_user_tabs_unavailable_during_workspace_bootstrap", {
      browser_error_kind: openTabsResult.error_kind,
      workspace_stage: "visible_user_tab_list",
      workspace_stage_rpcs_attempted: 1,
      user_tabs_inspected: 0,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const openTabs = openTabsResult.value ?? [];
  const candidates = openTabs.filter(isReusableWorkspaceInfo);
  if (candidates.length > 1) {
    return blocked("visible_user_workspace_tab_not_unique", {
      workspace_stage: "visible_user_tab_list",
      workspace_stage_rpcs_attempted: 1,
      user_tabs_inspected: openTabs.length,
      user_workspace_candidates_found: candidates.length,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  if (candidates.length === 1) {
    return {
      contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
      status: "visible_workspace_candidate_ready",
      method: "list_exact_visible_user_workspace_candidate",
      // claimTab requires the exact object returned by the current openTabs call.
      visible_workspace_candidate: candidates[0],
      continuation_contract: [
        "call claimXhsVisibleWorkspaceCandidate exactly once with this candidate",
        "then verify the returned exact task candidate with one fresh visible DOM RPC",
      ],
      workspace_stage: "visible_user_tab_list",
      workspace_stage_rpcs_attempted: 1,
      user_tabs_inspected: openTabs.length,
      user_workspace_candidates_found: 1,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
      alternate_browser_used: false,
      coordinate_action_used: false,
      blind_retry_used: false,
    };
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "workspace_creation_required",
    method: "visible_user_workspace_absence_verified",
    continuation_contract: [
      "call createXhsSearchWorkspaceBlankCandidate exactly once",
      "do not create a tab when any exact task or visible workspace candidate exists",
    ],
    workspace_stage: "visible_user_tab_list",
    workspace_stage_rpcs_attempted: 1,
    user_tabs_inspected: openTabs.length,
    user_workspace_candidates_found: 0,
    user_tab_claims_attempted: 0,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function claimXhsVisibleWorkspaceCandidate(browser, options = {}) {
  if (!browser?.user?.claimTab) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const candidate = options.candidate;
  if (!candidate?.id || !isReusableWorkspaceInfo(candidate)) {
    return blocked("visible_workspace_candidate_not_verified_for_claim", {
      workspace_stage_rpcs_attempted: 0,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const claimResult = await safeValue(() => browser.user.claimTab(candidate));
  if (!claimResult.ok) {
    return externalBlocked("visible_user_workspace_tab_claim_failed", {
      browser_error_kind: claimResult.error_kind,
      workspace_stage: "visible_user_tab_claim",
      workspace_stage_rpcs_attempted: 1,
      user_tab_claims_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const tab = claimResult.value;
  const workspaceCandidate = {
    id: tab.id,
    title: String(candidate.title ?? ""),
    url: String(candidate.url ?? ""),
  };
  if (!workspaceCandidate.id || !isReusableWorkspaceInfo(workspaceCandidate)) {
    return blocked("claimed_workspace_candidate_not_exact", {
      workspace_stage: "visible_user_tab_claim",
      workspace_stage_rpcs_attempted: 1,
      user_tab_claims_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "workspace_tab_claimed",
    method: "claim_exact_visible_user_workspace_candidate",
    tab,
    workspace_candidate: workspaceCandidate,
    workspace_stage: "visible_user_tab_claim",
    workspace_stage_rpcs_attempted: 1,
    user_tab_claims_attempted: 1,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function rebindXhsBlankWorkspaceCandidate(browser, options = {}) {
  if (!browser?.tabs?.get) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const candidate = options.candidate;
  if (!isBlankTaskTabInfo(candidate)) {
    return blocked("blank_workspace_candidate_not_verified_for_rebind", {
      workspace_stage_rpcs_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const tabResult = await safeValue(() => browser.tabs.get(candidate.id));
  if (!tabResult.ok) {
    return externalBlocked("blank_workspace_tab_rebind_failed", {
      browser_error_kind: tabResult.error_kind,
      workspace_stage: "blank_task_tab_rebind",
      workspace_stage_rpcs_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  if (String(tabResult.value?.id ?? "") !== String(candidate.id)) {
    return blocked("blank_workspace_tab_rebind_identity_mismatch", {
      workspace_stage: "blank_task_tab_rebind",
      workspace_stage_rpcs_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "blank_workspace_tab_rebound",
    method: "rebind_exact_blank_workspace_candidate",
    tab: tabResult.value,
    workspace_candidate: limitedCandidate(candidate),
    workspace_stage: "blank_task_tab_rebind",
    workspace_stage_rpcs_attempted: 1,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function createXhsSearchWorkspaceBlankCandidate(browser, options = {}) {
  if (!browser?.tabs?.new) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const discovery = options.discovery;
  if (
    discovery?.contract_id !== XHS_SEARCH_NAVIGATION_CONTRACT.contract_id ||
    discovery?.status !== "workspace_creation_required" ||
    discovery?.workspace_stage !== "visible_user_tab_list" ||
    discovery?.workspace_stage_rpcs_attempted !== 1 ||
    discovery?.user_workspace_candidates_found !== 0
  ) {
    return blocked("visible_workspace_absence_proof_required_before_tab_creation", {
      workspace_stage_rpcs_attempted: 0,
      new_tab_creation_attempts: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const newTabResult = await safeValue(() => browser.tabs.new());
  if (!newTabResult.ok) {
    return externalBlocked("task_tab_creation_result_unavailable", {
      browser_error_kind: newTabResult.error_kind,
      workspace_stage: "task_tab_creation",
      workspace_stage_rpcs_attempted: 1,
      new_tab_creation_attempts: 1,
      new_tabs_created: null,
      homepage_navigations_attempted: 0,
    });
  }
  const tab = newTabResult.value;
  if (!tab?.id) {
    return blocked("created_blank_workspace_candidate_missing_exact_id", {
      workspace_stage: "task_tab_creation",
      workspace_stage_rpcs_attempted: 1,
      new_tab_creation_attempts: 1,
      new_tabs_created: 1,
      homepage_navigations_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "blank_workspace_candidate_created",
    method: "create_one_exact_blank_task_tab",
    tab,
    workspace_candidate: { id: tab.id, title: "", url: "about:blank" },
    workspace_stage: "task_tab_creation",
    workspace_stage_rpcs_attempted: 1,
    new_tab_creation_attempts: 1,
    new_tabs_created: 1,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function navigateXhsBlankWorkspaceCandidate(tab, options = {}) {
  if (!tab?.goto) {
    throw new TypeError("a documented in-app Browser Tab is required");
  }
  const candidate = options.candidate;
  if (
    !isBlankTaskTabInfo(candidate) ||
    (tab.id !== undefined && String(tab.id) !== String(candidate.id))
  ) {
    return blocked("blank_workspace_candidate_context_not_verified", {
      workspace_stage_rpcs_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const gotoResult = await safeValue(() => tab.goto(XHS_HOME_URL));
  if (!gotoResult.ok) {
    return externalBlocked("homepage_navigation_result_unavailable", {
      browser_error_kind: gotoResult.error_kind,
      workspace_stage: "homepage_navigation",
      workspace_stage_rpcs_attempted: 1,
      workspace_candidate_id: candidate.id,
      new_tabs_created: 0,
      homepage_navigations_attempted: 1,
      resume_contract:
        "do not navigate again; after browser control is stable, call inspectXhsWorkspaceAfterNavigation once for this exact candidate id",
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "homepage_navigation_completed",
    method: "navigate_exact_blank_candidate_to_xhs_homepage",
    workspace_candidate_id: candidate.id,
    workspace_stage: "homepage_navigation",
    workspace_stage_rpcs_attempted: 1,
    new_tabs_created: 0,
    homepage_navigations_attempted: 1,
    continuation_contract:
      "call inspectXhsWorkspaceAfterNavigation exactly once; do not infer the final URL from goto completion",
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function inspectXhsWorkspaceAfterNavigation(browser, options = {}) {
  if (!browser?.tabs?.list) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const candidateId = String(options.candidateId ?? "");
  if (!candidateId) {
    return blocked("navigated_workspace_candidate_id_missing", {
      workspace_stage_rpcs_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const listResult = await safeValue(() => browser.tabs.list());
  if (!listResult.ok) {
    return externalBlocked("task_tabs_unavailable_after_homepage_navigation", {
      browser_error_kind: listResult.error_kind,
      workspace_stage: "post_navigation_task_tab_list",
      workspace_stage_rpcs_attempted: 1,
      workspace_candidate_id: candidateId,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const infos = listResult.value ?? [];
  const exactMatches = infos.filter(
    (info) => String(info?.id ?? "") === candidateId,
  );
  if (exactMatches.length !== 1) {
    return externalBlocked("navigated_workspace_candidate_not_rebindable", {
      workspace_stage: "post_navigation_task_tab_list",
      workspace_stage_rpcs_attempted: 1,
      workspace_candidate_id: candidateId,
      exact_candidate_matches: exactMatches.length,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  if (!isReusableWorkspaceInfo(exactMatches[0])) {
    return blocked("homepage_navigation_not_verified_by_exact_task_tab", {
      workspace_stage: "post_navigation_task_tab_list",
      workspace_stage_rpcs_attempted: 1,
      workspace_candidate: limitedCandidate(exactMatches[0]),
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "workspace_candidate_ready",
    method: "list_exact_workspace_candidate_after_navigation",
    workspace_candidate: limitedCandidate(exactMatches[0]),
    workspace_stage: "post_navigation_task_tab_list",
    workspace_stage_rpcs_attempted: 1,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function recoverXhsWorkspaceAfterIndeterminateNavigation(
  browser,
  options = {},
) {
  const attempt = options.navigationAttempt;
  const candidateId = String(attempt?.workspace_candidate_id ?? "");
  if (
    !candidateId ||
    attempt?.browser_rpc !== "tab.goto" ||
    attempt?.called_exactly_once !== true ||
    attempt?.result_received !== false ||
    attempt?.homepage_navigations_attempted !== 1 ||
    attempt?.retry_performed !== false
  ) {
    return blocked("indeterminate_navigation_attempt_proof_required", {
      workspace_stage: "post_indeterminate_navigation_recovery",
      workspace_stage_rpcs_attempted: 0,
      navigation_replayed: false,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const inspected = await inspectXhsWorkspaceAfterNavigation(browser, {
    candidateId,
  });
  return {
    ...inspected,
    method:
      inspected.status === "workspace_candidate_ready"
        ? "recover_exact_workspace_after_indeterminate_navigation_via_single_task_list"
        : inspected.method,
    workspace_stage: "post_indeterminate_navigation_recovery",
    navigation_result_received: false,
    navigation_outcome_inferred: false,
    navigation_replayed: false,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    recovery_rpcs_attempted: 1,
    continuation_contract:
      inspected.status === "workspace_candidate_ready"
        ? [
            "call rebindXhsSearchWorkspaceCandidate exactly once with this verified candidate",
            "then call verifyXhsSearchWorkspaceCandidate exactly once with the current required profile id",
          ]
        : "stop without another navigation, tab creation, task-list recovery, DOM read, or search action",
  };
}

export async function recoverXhsReleasedWorkspaceAfterTaskCandidateLoss(
  browser,
  options = {},
) {
  if (!browser?.user?.openTabs) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const lossProof = options.lossProof;
  const lostCandidateId = String(lossProof?.workspace_candidate_id ?? "");
  if (
    !lostCandidateId ||
    lossProof?.status !== "blocked_external_runtime" ||
    lossProof?.reason !== "navigated_workspace_candidate_not_rebindable" ||
    lossProof?.exact_candidate_matches !== 0 ||
    lossProof?.recovery_rpcs_attempted !== 1 ||
    lossProof?.navigation_replayed !== false ||
    lossProof?.additional_browser_actions_after_recovery !== 0
  ) {
    return blocked("task_candidate_loss_proof_required_before_visible_recovery", {
      workspace_stage: "released_workspace_visible_list",
      workspace_stage_rpcs_attempted: 0,
      visible_workspace_recovery_rpcs_attempted: 0,
      user_tabs_inspected: 0,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const openTabsResult = await safeValue(() => browser.user.openTabs());
  if (!openTabsResult.ok) {
    return externalBlocked("visible_user_tabs_unavailable_after_task_candidate_loss", {
      browser_error_kind: openTabsResult.error_kind,
      workspace_stage: "released_workspace_visible_list",
      workspace_stage_rpcs_attempted: 1,
      visible_workspace_recovery_rpcs_attempted: 1,
      lost_workspace_candidate_id: lostCandidateId,
      user_tabs_inspected: 0,
      user_workspace_candidates_found: 0,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const openTabs = openTabsResult.value ?? [];
  const candidates = openTabs.filter(isReusableWorkspaceInfo);
  if (candidates.length > 1) {
    return blocked("released_visible_workspace_candidate_not_unique", {
      workspace_stage: "released_workspace_visible_list",
      workspace_stage_rpcs_attempted: 1,
      visible_workspace_recovery_rpcs_attempted: 1,
      lost_workspace_candidate_id: lostCandidateId,
      user_tabs_inspected: openTabs.length,
      user_workspace_candidates_found: candidates.length,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  if (candidates.length === 0) {
    return externalBlocked("released_visible_workspace_candidate_not_found", {
      workspace_stage: "released_workspace_visible_list",
      workspace_stage_rpcs_attempted: 1,
      visible_workspace_recovery_rpcs_attempted: 1,
      lost_workspace_candidate_id: lostCandidateId,
      user_tabs_inspected: openTabs.length,
      user_workspace_candidates_found: 0,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "released_workspace_candidate_ready",
    method: "list_one_exact_visible_workspace_after_task_candidate_loss",
    released_workspace_candidate: candidates[0],
    lost_workspace_candidate_id: lostCandidateId,
    continuity_to_lost_task_id_inferred: false,
    continuation_contract:
      "call claimXhsReleasedWorkspaceCandidate exactly once with this complete discovery result; treat the claimed tab id as a new current identity",
    workspace_stage: "released_workspace_visible_list",
    workspace_stage_rpcs_attempted: 1,
    visible_workspace_recovery_rpcs_attempted: 1,
    user_tabs_inspected: openTabs.length,
    user_workspace_candidates_found: 1,
    user_tab_claims_attempted: 0,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function claimXhsReleasedWorkspaceCandidate(browser, options = {}) {
  if (!browser?.user?.claimTab) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const discovery = options.discovery;
  const candidate = discovery?.released_workspace_candidate;
  if (
    discovery?.contract_id !== XHS_SEARCH_NAVIGATION_CONTRACT.contract_id ||
    discovery?.status !== "released_workspace_candidate_ready" ||
    discovery?.workspace_stage !== "released_workspace_visible_list" ||
    discovery?.visible_workspace_recovery_rpcs_attempted !== 1 ||
    discovery?.user_workspace_candidates_found !== 1 ||
    !discovery?.lost_workspace_candidate_id ||
    !candidate?.id ||
    !isReusableWorkspaceInfo(candidate)
  ) {
    return blocked("released_workspace_discovery_proof_required_before_claim", {
      workspace_stage: "released_workspace_exact_claim",
      workspace_stage_rpcs_attempted: 0,
      user_tab_claims_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const claimResult = await safeValue(() => browser.user.claimTab(candidate));
  if (!claimResult.ok) {
    return externalBlocked("released_workspace_exact_claim_failed", {
      browser_error_kind: claimResult.error_kind,
      workspace_stage: "released_workspace_exact_claim",
      workspace_stage_rpcs_attempted: 1,
      lost_workspace_candidate_id: discovery.lost_workspace_candidate_id,
      user_tab_claims_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const tab = claimResult.value;
  const workspaceCandidate = {
    id: tab?.id,
    title: String(candidate.title ?? ""),
    url: String(candidate.url ?? ""),
  };
  if (!workspaceCandidate.id || !isReusableWorkspaceInfo(workspaceCandidate)) {
    return blocked("claimed_released_workspace_missing_new_exact_task_id", {
      workspace_stage: "released_workspace_exact_claim",
      workspace_stage_rpcs_attempted: 1,
      lost_workspace_candidate_id: discovery.lost_workspace_candidate_id,
      user_tab_claims_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "released_workspace_tab_claimed",
    method: "claim_one_exact_released_workspace_after_task_candidate_loss",
    tab,
    workspace_candidate: workspaceCandidate,
    lost_workspace_candidate_id: discovery.lost_workspace_candidate_id,
    current_workspace_candidate_id: workspaceCandidate.id,
    lost_task_id_reused_as_current_id: false,
    continuity_to_lost_task_id_inferred: false,
    continuation_contract: [
      "use the newly returned task id as the only current workspace identity",
      "call verifyXhsSearchWorkspaceCandidate exactly once with this new candidate and the current required profile id",
    ],
    workspace_stage: "released_workspace_exact_claim",
    workspace_stage_rpcs_attempted: 1,
    user_tab_claims_attempted: 1,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function verifyXhsSearchWorkspaceCandidate(tab, options = {}) {
  if (!tab?.dom_cua?.get_visible_dom) {
    throw new TypeError("a documented in-app Browser Tab is required");
  }
  const candidate = options.candidate;
  const requiredProfileId = String(options.requiredProfileId ?? "").trim().toLowerCase();
  if (
    !candidate?.id ||
    !isReusableWorkspaceInfo(candidate) ||
    (tab.id !== undefined && String(tab.id) !== String(candidate.id)) ||
    !/^[0-9a-f]{24}$/.test(requiredProfileId)
  ) {
    return blocked("workspace_candidate_context_not_verified", {
      required_profile_context_verified: /^[0-9a-f]{24}$/.test(requiredProfileId),
      workspace_verification_rpcs_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const proof = await safeValue(() => tab.dom_cua.get_visible_dom());
  if (!proof.ok) {
    return externalBlocked("browser_control_unavailable_during_workspace_verification", {
      probe_error_kind: proof.error_kind,
      verification_surface: "dom_cua_visible_dom",
      workspace_verification_rpcs_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const state = analyzeVisibleDomWorkspace(proof.value, candidate);
  const identityState = analyzeVisibleDomIdentity(
    proof.value,
    requiredProfileId,
    state.risk_signal_observed,
  );
  if (!state.workspace_verified) {
    return blocked("existing_workspace_tab_not_verified", {
      workspace_state: state,
      workspace_verification_rpcs_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  if (!identityState.identity_verified) {
    return blocked("existing_workspace_identity_not_verified", {
      workspace_state: state,
      identity_state: identityState,
      workspace_verification_rpcs_attempted: 1,
      identity_verification_rpcs_attempted: 0,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "workspace_ready",
    method: "verify_rebound_workspace_and_identity_via_single_visible_dom",
    tab,
    workspace_state: state,
    identity_state: identityState,
    workspace_verification_rpcs_attempted: 1,
    identity_verification_rpcs_attempted: 0,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

async function claimVisibleUserTab(browser, options) {
  const {
    predicate,
    verify,
    method,
    notUniqueReason,
    notVerifiedReason,
    required,
    counters,
    deadlineAt,
  } = options;
  if (!browser?.user?.openTabs || !browser?.user?.claimTab) {
    if (!required) return { kind: "none" };
    return {
      kind: "result",
      result: externalBlocked("visible_user_tab_recovery_api_unavailable", {
        ...counters,
        user_tabs_inspected: 0,
        user_tab_claims_attempted: 0,
      }),
    };
  }
  const openTabsResult = Number.isFinite(deadlineAt)
    ? await safeValueBeforeDeadline(
        () => browser.user.openTabs(),
        remainingDeadlineMs(deadlineAt),
      )
    : await safeValue(() => browser.user.openTabs());
  if (!openTabsResult.ok) {
    if (!required && openTabsResult.error_kind !== "soft_deadline") {
      return { kind: "none" };
    }
    return {
      kind: "result",
      result: externalBlocked("visible_user_tabs_unavailable_during_recovery", {
        ...counters,
        user_tabs_error_kind: openTabsResult.error_kind,
        acquire_deadline_stage: "visible_user_tab_list",
        user_tabs_inspected: 0,
        user_tab_claims_attempted: 0,
      }),
    };
  }
  const openTabs = openTabsResult.value ?? [];
  const candidates = openTabs.filter(predicate);
  if (candidates.length === 0) return { kind: "none", inspected: openTabs.length };
  if (candidates.length !== 1) {
    return {
      kind: "result",
      result: blocked(notUniqueReason, {
        ...counters,
        user_tabs_inspected: openTabs.length,
        user_workspace_candidates_found: candidates.length,
        user_tab_claims_attempted: 0,
      }),
    };
  }
  const claimResult = Number.isFinite(deadlineAt)
    ? await safeValueBeforeDeadline(
        () => browser.user.claimTab(candidates[0]),
        remainingDeadlineMs(deadlineAt),
      )
    : await safeValue(() => browser.user.claimTab(candidates[0]));
  if (!claimResult.ok) {
    return {
      kind: "result",
      result: externalBlocked("visible_user_workspace_tab_claim_failed", {
        ...counters,
        claim_error_kind: claimResult.error_kind,
        acquire_deadline_stage: "visible_user_tab_claim",
        user_tabs_inspected: openTabs.length,
        user_workspace_candidates_found: 1,
        user_tab_claims_attempted: 1,
      }),
    };
  }
  const proof = await verify(claimResult.value);
  if (!proof.ok) {
    return {
      kind: "result",
      result: externalBlocked("browser_control_unavailable_after_user_tab_claim", {
        ...counters,
        probe_error_kind: proof.error_kind,
        user_tabs_inspected: openTabs.length,
        user_workspace_candidates_found: 1,
        user_tab_claims_attempted: 1,
      }),
    };
  }
  if (!proof.verified) {
    return {
      kind: "result",
      result: blocked(notVerifiedReason, {
        ...counters,
        claimed_state: proof.state,
        user_tabs_inspected: openTabs.length,
        user_workspace_candidates_found: 1,
        user_tab_claims_attempted: 1,
      }),
    };
  }
  return {
    kind: "result",
    result: {
      contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
      status: proof.successStatus,
      method,
      tab: claimResult.value,
      ...proof.resultFields,
      ...counters,
      user_tabs_inspected: openTabs.length,
      user_workspace_candidates_found: 1,
      user_tab_claims_attempted: 1,
      alternate_browser_used: false,
      coordinate_action_used: false,
      blind_retry_used: false,
    },
  };
}

async function claimVisibleUserWorkspace(browser, timeoutMs, options = {}) {
  return claimVisibleUserTab(browser, {
    predicate: isReusableWorkspaceInfo,
    verify: async (tab) => {
      const proof = await verifyWorkspace(
        tab,
        timeoutMs,
        Number.isFinite(options.deadlineAt)
          ? remainingDeadlineMs(options.deadlineAt)
          : undefined,
      );
      return proof.ok
        ? {
            ok: true,
            verified: proof.state.workspace_verified,
            state: proof.state,
            successStatus: "workspace_ready",
            resultFields: { workspace_state: proof.state },
          }
        : proof;
    },
    method: options.method ?? "claim_existing_visible_user_workspace_tab",
    notUniqueReason: "visible_user_workspace_tab_not_unique",
    notVerifiedReason: "claimed_user_workspace_tab_not_verified",
    required: options.required === true,
    deadlineAt: options.deadlineAt,
    counters: options.counters ?? {
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    },
  });
}

async function recoverCreatedTab(browser, createdTabId, timeoutMs, deadlineAt) {
  const listResult = Number.isFinite(deadlineAt)
    ? await safeValueBeforeDeadline(
        () => browser.tabs.list(),
        remainingDeadlineMs(deadlineAt),
      )
    : await safeValue(() => browser.tabs.list());
  const counters = {
    new_tabs_created: 1,
    homepage_navigations_attempted: 1,
  };
  const infos = listResult.ok ? listResult.value ?? [] : [];
  const candidates = infos.filter(
    (info) => info.id === createdTabId || isReusableWorkspaceInfo(info),
  );
  if (candidates.length > 1) {
    return blocked("rebindable_workspace_tab_not_unique", {
      ...counters,
      rebindable_tabs_found: infos.length,
      workspace_candidates_found: candidates.length,
    });
  }
  if (candidates.length === 1) {
    const tabResult = Number.isFinite(deadlineAt)
      ? await safeValueBeforeDeadline(
          () => browser.tabs.get(candidates[0].id),
          remainingDeadlineMs(deadlineAt),
        )
      : await safeValue(() => browser.tabs.get(candidates[0].id));
    if (tabResult.ok) {
      const proof = await verifyWorkspace(
        tabResult.value,
        timeoutMs,
        Number.isFinite(deadlineAt)
          ? remainingDeadlineMs(deadlineAt)
          : undefined,
      );
      if (proof.ok && proof.state.workspace_verified) {
        return {
          contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
          status: "workspace_ready",
          method: "rebind_after_ambiguous_homepage_navigation",
          tab: tabResult.value,
          workspace_state: proof.state,
          ...counters,
          user_tab_claims_attempted: 0,
          alternate_browser_used: false,
          coordinate_action_used: false,
          blind_retry_used: false,
        };
      }
      if (proof.ok) {
        return blocked("homepage_workspace_not_verified_after_single_navigation", {
          ...counters,
          workspace_state: proof.state,
          user_tab_claims_attempted: 0,
        });
      }
    }
  }
  const claimed = await claimVisibleUserWorkspace(browser, timeoutMs, {
    required: true,
    method: "claim_released_user_workspace_after_homepage_navigation",
    counters,
    deadlineAt,
  });
  if (claimed.kind === "result") return claimed.result;
  return externalBlocked("no_rebindable_tab_after_homepage_navigation", {
    ...counters,
    browser_error_kind: listResult.ok ? undefined : listResult.error_kind,
    rebindable_tabs_found: infos.length,
    user_tabs_inspected: claimed.inspected ?? 0,
    user_tab_claims_attempted: 0,
  });
}

export async function acquireXhsSearchWorkspace(browser, options = {}) {
  if (!browser?.tabs?.list) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const acquireResultSoftDeadlineMs = Math.min(
    Math.max(
      Number(
        options.acquireResultSoftDeadlineMs ??
          XHS_SEARCH_NAVIGATION_CONTRACT.acquire_result_soft_deadline_ms,
      ),
      50,
    ),
    15_000,
  );
  const deadlineAt = Date.now() + acquireResultSoftDeadlineMs;
  const listResult = await safeValueBeforeDeadline(
    () => browser.tabs.list(),
    remainingDeadlineMs(deadlineAt),
  );
  if (!listResult.ok) {
    return externalBlocked("browser_binding_unavailable_before_workspace_acquire", {
      browser_binding_verified: false,
      browser_binding_verification_method:
        XHS_SEARCH_NAVIGATION_CONTRACT.browser_binding_verification,
      browser_error_kind: listResult.error_kind,
      acquire_deadline_stage: "task_tab_list",
      acquire_result_soft_deadline_ms: acquireResultSoftDeadlineMs,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    });
  }
  const withBindingEvidence = (result) => ({
    ...result,
    browser_binding_verified: true,
    browser_binding_verification_method:
      XHS_SEARCH_NAVIGATION_CONTRACT.browser_binding_verification,
  });
  const infos = listResult.value ?? [];
  const reusable = infos.filter(isReusableWorkspaceInfo);
  if (reusable.length > 1 && !options.preferredTabId) {
    return withBindingEvidence(blocked("existing_workspace_tab_not_unique", {
      workspace_candidates_found: reusable.length,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    }));
  }
  const selectedInfo = options.preferredTabId
    ? reusable.find((info) => info.id === options.preferredTabId)
    : reusable[0];
  if (selectedInfo) {
    return withBindingEvidence({
      contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
      status: "workspace_candidate_ready",
      method: "list_exact_existing_workspace_candidate",
      workspace_candidate: selectedInfo,
      continuation_contract: [
        "call rebindXhsSearchWorkspaceCandidate exactly once with this candidate",
        "then call verifyXhsSearchWorkspaceCandidate exactly once with the rebound tab",
        "do not create or navigate while this exact candidate remains available",
      ],
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
      alternate_browser_used: false,
      coordinate_action_used: false,
      blind_retry_used: false,
    });
  }
  const blankCandidates = infos.filter(isBlankTaskTabInfo);
  if (blankCandidates.length > 1 && !options.preferredBlankTabId) {
    return withBindingEvidence(blocked("blank_workspace_candidate_not_unique", {
      task_tabs_inspected: infos.length,
      blank_workspace_candidates_found: blankCandidates.length,
      workspace_stage: "task_tab_list",
      workspace_stage_rpcs_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
    }));
  }
  const selectedBlank = options.preferredBlankTabId
    ? blankCandidates.find(
        (info) => String(info.id) === String(options.preferredBlankTabId),
      )
    : blankCandidates[0];
  if (selectedBlank) {
    return withBindingEvidence({
      contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
      status: "workspace_bootstrap_candidate_ready",
      method: "list_exact_existing_blank_workspace_candidate",
      workspace_candidate: limitedCandidate(selectedBlank),
      continuation_contract: [
        "call rebindXhsBlankWorkspaceCandidate exactly once with this candidate",
        "then call navigateXhsBlankWorkspaceCandidate exactly once with the rebound tab",
        "after navigation settles, call inspectXhsWorkspaceAfterNavigation exactly once for the same candidate id",
      ],
      task_tabs_inspected: infos.length,
      blank_workspace_candidates_found: 1,
      workspace_stage: "task_tab_list",
      workspace_stage_rpcs_attempted: 1,
      new_tabs_created: 0,
      homepage_navigations_attempted: 0,
      alternate_browser_used: false,
      coordinate_action_used: false,
      blind_retry_used: false,
    });
  }
  return withBindingEvidence({
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "workspace_bootstrap_discovery_required",
    method: "task_workspace_absence_verified_after_single_list",
    continuation_contract: [
      "call inspectXhsVisibleWorkspaceCandidates exactly once",
      "claim only one exact visible Xiaohongshu workspace candidate",
      "create a blank task tab only after visible workspace absence is verified",
    ],
    task_tabs_inspected: infos.length,
    blank_workspace_candidates_found: 0,
    workspace_stage: "task_tab_list",
    workspace_stage_rpcs_attempted: 1,
    new_tabs_created: 0,
    homepage_navigations_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  });
}

export async function recoverXhsSearchPage(browser, options = {}) {
  if (!browser?.tabs?.list || !browser?.tabs?.get) {
    throw new TypeError("a documented Codex in-app Browser binding is required");
  }
  const query = String(options.query ?? "").replace(/\s+/g, " ").trim();
  if (!query) throw new TypeError("query is required");
  const timeoutMs = Math.min(
    Math.max(Number(options.probeTimeoutMs ?? 3_000), 500),
    5_000,
  );
  const verify = async (tab) => {
    const proof = await safeProbe(
      tab,
      workspaceStateProbe,
      { query, selector: SEARCH_INPUT_SELECTOR },
      timeoutMs,
    );
    return proof.ok
      ? {
          ok: true,
          verified: proof.state.search_page_verified,
          state: proof.state,
          successStatus: "verified",
          resultFields: {
            query,
            search_state: proof.state,
            search_submissions_attempted: 0,
          },
        }
      : proof;
  };
  const listResult = await safeValue(() => browser.tabs.list());
  const infos = listResult.ok ? listResult.value ?? [] : [];
  const candidates = infos.filter(isSearchPageInfo);
  if (candidates.length > 1) {
    return blocked("rebindable_search_tab_not_unique", {
      query,
      search_candidates_found: candidates.length,
      search_submissions_attempted: 0,
      user_tab_claims_attempted: 0,
    });
  }
  if (candidates.length === 1) {
    const tabResult = await safeValue(() => browser.tabs.get(candidates[0].id));
    if (tabResult.ok) {
      const proof = await verify(tabResult.value);
      if (proof.ok && proof.verified) {
        return {
          contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
          status: "verified",
          method: "rebind_existing_search_tab_after_control_reset",
          tab: tabResult.value,
          ...proof.resultFields,
          user_tab_claims_attempted: 0,
          alternate_browser_used: false,
          coordinate_action_used: false,
          blind_retry_used: false,
        };
      }
      if (proof.ok) {
        return blocked("rebound_search_page_not_verified", {
          query,
          search_state: proof.state,
          search_submissions_attempted: 0,
          user_tab_claims_attempted: 0,
        });
      }
    }
  }
  const claimed = await claimVisibleUserTab(browser, {
    predicate: isSearchPageInfo,
    verify,
    method: "claim_released_user_search_tab_after_control_reset",
    notUniqueReason: "visible_user_search_tab_not_unique",
    notVerifiedReason: "claimed_user_search_page_not_verified",
    required: true,
    counters: { query, search_submissions_attempted: 0 },
  });
  if (claimed.kind === "result") return claimed.result;
  return externalBlocked("no_rebindable_search_tab_after_control_reset", {
    query,
    browser_error_kind: listResult.ok ? undefined : listResult.error_kind,
    rebindable_tabs_found: infos.length,
    user_tabs_inspected: claimed.inspected ?? 0,
    user_tab_claims_attempted: 0,
    search_submissions_attempted: 0,
  });
}

export async function verifyXhsSearchPage(tab, options = {}) {
  if (!tab?.playwright?.evaluate) {
    throw new TypeError("a documented in-app Browser Tab is required");
  }
  const query = String(options.query ?? "").replace(/\s+/g, " ").trim();
  if (!query) throw new TypeError("query is required");
  const timeoutMs = Math.min(
    Math.max(Number(options.probeTimeoutMs ?? 3_000), 500),
    5_000,
  );
  const proof = await safeProbe(
    tab,
    workspaceStateProbe,
    { query, selector: SEARCH_INPUT_SELECTOR },
    timeoutMs,
  );
  if (!proof.ok) {
    return externalBlocked("browser_control_unavailable_during_search_verification", {
      probe_error_kind: proof.error_kind,
      search_submissions_attempted: 0,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: proof.state.search_page_verified ? "verified" : "not_verified",
    query,
    search_state: proof.state,
    search_submissions_attempted: 0,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}

export async function openXhsSearchResults(tab, options = {}) {
  if (
    !tab?.playwright?.locator ||
    !tab?.playwright?.evaluate ||
    !tab?.playwright?.waitForTimeout
  ) {
    throw new TypeError("a documented in-app Browser Tab is required");
  }
  const query = String(options.query ?? "").replace(/\s+/g, " ").trim();
  if (!query) throw new TypeError("query is required");
  const preconditions = options.preconditions ?? {};
  const missingPreconditions =
    XHS_SEARCH_NAVIGATION_CONTRACT.required_search_preconditions.filter(
      (name) => preconditions[name] !== true,
    );
  if (missingPreconditions.length > 0) {
    return blocked("required_search_preconditions_not_verified", {
      query,
      missing_preconditions: missingPreconditions,
      search_submissions_attempted: 0,
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
  const selector = SEARCH_INPUT_SELECTOR;
  const surfaceProof = await safeProbe(
    tab,
    workspaceStateProbe,
    { selector },
    probeTimeoutMs,
  );
  if (!surfaceProof.ok) {
    return externalBlocked("browser_control_unavailable_during_search_preflight", {
      query,
      preflight_stage: "surface_probe",
      preflight_error_kind: surfaceProof.error_kind,
      search_submissions_attempted: 0,
    });
  }
  const target = surfaceProof.state.operable_search_input;
  if (surfaceProof.state.operable_search_input_count !== 1 || !target) {
    return blocked(
      surfaceProof.state.operable_search_input_count === 0
        ? "search_input_missing"
        : "search_input_not_unique",
      {
        query,
        visible_search_input_count:
          surfaceProof.state.visible_search_input_count,
        operable_search_input_count:
          surfaceProof.state.operable_search_input_count,
        search_input_candidates: surfaceProof.state.search_input_candidates,
        search_submissions_attempted: 0,
      },
    );
  }
  const exactIdSelector = exactIdSelectorForTarget(target);
  const locatorStrategy = exactIdSelector
    ? "unique_exact_id"
    : "proven_operable_dom_index";
  let input;
  try {
    input = exactIdSelector
      ? tab.playwright.locator(exactIdSelector)
      : tab.playwright.locator(selector).nth(target.dom_index);
  } catch (error) {
    return externalBlocked("browser_control_unavailable_during_search_preflight", {
      query,
      preflight_stage: "locator_construction",
      locator_strategy: locatorStrategy,
      preflight_error_kind: classifyError(error),
      search_submissions_attempted: 0,
    });
  }
  const countResult = await safeValue(() => input.count());
  if (!countResult.ok) {
    return externalBlocked("browser_control_unavailable_during_search_preflight", {
      query,
      preflight_stage: "locator_count",
      locator_strategy: locatorStrategy,
      preflight_error_kind: countResult.error_kind,
      search_submissions_attempted: 0,
    });
  }
  if (countResult.value !== 1) {
    return blocked(
      countResult.value === 0 ? "search_input_missing" : "search_input_not_unique",
      {
        query,
        matched_inputs: countResult.value,
        locator_strategy: locatorStrategy,
        search_submissions_attempted: 0,
      },
    );
  }
  const targetCheck = await safeValue(async () => ({
    visible: await input.isVisible(),
    enabled: await input.isEnabled(),
    id: String((await input.getAttribute("id")) ?? ""),
    name: String((await input.getAttribute("name")) ?? ""),
    placeholder: String((await input.getAttribute("placeholder")) ?? ""),
    aria_label: String((await input.getAttribute("aria-label")) ?? ""),
    class_name: String((await input.getAttribute("class")) ?? ""),
  }));
  if (!targetCheck.ok) {
    return externalBlocked("browser_control_unavailable_during_search_preflight", {
      query,
      preflight_stage: "locator_state_and_fingerprint",
      locator_strategy: locatorStrategy,
      preflight_error_kind: targetCheck.error_kind,
      search_submissions_attempted: 0,
    });
  }
  const fingerprintMatches =
    targetCheck.value.id === target.id &&
    targetCheck.value.name === target.name &&
    targetCheck.value.placeholder === target.placeholder &&
    targetCheck.value.aria_label === target.aria_label &&
    targetCheck.value.class_name === target.class_name;
  if (
    !targetCheck.value.visible ||
    !targetCheck.value.enabled ||
    !fingerprintMatches
  ) {
    return blocked("search_input_changed_after_unique_operability_probe", {
      query,
      target_dom_index: target.dom_index,
      locator_strategy: locatorStrategy,
      target_fingerprint_matches: fingerprintMatches,
      target_visible: targetCheck.value.visible,
      target_enabled: targetCheck.value.enabled,
      search_submissions_attempted: 0,
    });
  }
  const fillResult = await safeValue(() =>
    input.fill(query, { timeoutMs: actionTimeoutMs }),
  );
  if (!fillResult.ok) {
    return externalBlocked("browser_control_unavailable_during_search_fill", {
      query,
      locator_strategy: locatorStrategy,
      fill_error_kind: fillResult.error_kind,
      search_submissions_attempted: 0,
    });
  }
  let submitResult = "ok";
  try {
    await input.press("Enter", { timeoutMs: actionTimeoutMs });
  } catch (error) {
    submitResult = classifyError(error);
  }
  const settleResult = await safeValue(() =>
    tab.playwright.waitForTimeout(settleMs),
  );
  const proof = await safeProbe(
    tab,
    workspaceStateProbe,
    { query, selector: SEARCH_INPUT_SELECTOR },
    probeTimeoutMs,
  );
  if (!proof.ok) {
    if (options.browser) {
      const recovery = await recoverXhsSearchPage(options.browser, {
        query,
        probeTimeoutMs,
      });
      if (recovery.status === "verified") {
        return {
          contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
          status: "opened",
          method: recovery.method,
          tab: recovery.tab,
          query,
          locator_strategy: locatorStrategy,
          submit_result: submitResult,
          recovered_after_control_reset: true,
          search_state: recovery.search_state,
          search_submissions_attempted: 1,
          user_tab_claims_attempted: recovery.user_tab_claims_attempted,
          alternate_browser_used: false,
          coordinate_action_used: false,
          blind_retry_used: false,
        };
      }
      return externalBlocked("browser_control_unavailable_after_search_submit", {
        query,
        locator_strategy: locatorStrategy,
        submit_result: submitResult,
        settle_error_kind: settleResult.ok ? undefined : settleResult.error_kind,
        probe_error_kind: proof.error_kind,
        recovery_status: recovery.status,
        recovery_reason: recovery.reason,
        search_submissions_attempted: 1,
        user_tab_claims_attempted: recovery.user_tab_claims_attempted ?? 0,
        resume_contract: "stop without a second submission when neither a controlled tab nor one exact visible user search tab can be verified",
      });
    }
    return externalBlocked("browser_control_unavailable_after_search_submit", {
      query,
      locator_strategy: locatorStrategy,
      submit_result: submitResult,
      settle_error_kind: settleResult.ok ? undefined : settleResult.error_kind,
      probe_error_kind: proof.error_kind,
      search_submissions_attempted: 1,
      resume_contract: "reuse the existing in-app browser binding, acquire or rebind one workspace tab, then call verifyXhsSearchPage before any fresh query submission",
    });
  }
  if (!proof.state.search_page_verified) {
    return blocked("search_page_not_verified_after_single_submit", {
      query,
      locator_strategy: locatorStrategy,
      submit_result: submitResult,
      search_state: proof.state,
      search_submissions_attempted: 1,
    });
  }
  return {
    contract_id: XHS_SEARCH_NAVIGATION_CONTRACT.contract_id,
    status: "opened",
    method: "same_tab_visible_search_input_enter",
    query,
    locator_strategy: locatorStrategy,
    submit_result: submitResult,
    opened_despite_ambiguous_timeout: submitResult === "timeout",
    search_state: proof.state,
    search_submissions_attempted: 1,
    alternate_browser_used: false,
    coordinate_action_used: false,
    blind_retry_used: false,
  };
}
