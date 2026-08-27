#!/usr/bin/env node

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  XHS_SEARCH_NAVIGATION_CONTRACT,
  acquireXhsSearchWorkspace,
  inspectXhsSearchInputSurface,
  openXhsSearchResults,
  rebindXhsSearchWorkspaceCandidate,
  recoverXhsSearchPage,
  verifyXhsSearchWorkspaceCandidate,
  verifyXhsSearchPage,
} from "./xhs_in_app_search_navigation.mjs";

const QUERY = "实木家具 开裂 修复 保养";
const PROFILE_ID = "6465fa8000000000290160bd";
const SAFE_SEARCH = Object.freeze({
  query: QUERY,
  settleMs: 100,
  preconditions: {
    account_identity_verified: true,
    workspace_verified: true,
    risk_state_clear: true,
  },
});

function fakeEnvironment({
  initialTabs = [],
  goto = "home",
  search = "results",
  searchInputCount = 1,
  visibleSearchInputCount = 1,
  operableSearchInputCount = 1,
  operableSearchInputIndex = 0,
  operableSearchInputId = "primary-search",
  exactOperableIdUnique = true,
  locatorCountError = false,
  listAfterGoto = undefined,
  browserDisconnected = false,
  userTabs = [],
  userTabsAfterGoto = undefined,
  userTabsUnavailable = false,
  newTabPending = false,
  visibleDomSnapshot = undefined,
  visibleDomError = false,
} = {}) {
  let state = initialTabs[0]?.state ?? "blank";
  let tabs = initialTabs.map((item, index) => ({
    id: item.id ?? `existing-${index}`,
    url: item.url,
  }));
  let listCalls = 0;
  let openTabsCalls = 0;
  const calls = [];
  const tab = {
    id: "task-tab-1",
    async goto(url) {
      calls.push(["goto", url]);
      if (goto === "home" || goto === "home_timeout") state = "home";
      if (goto === "pending") return new Promise(() => {});
      if (goto === "reset") tabs = [];
      if (goto === "home_timeout") throw new Error("Timeout during Page.navigate");
      if (goto === "reset") throw new Error("browser control session reset");
    },
    playwright: {
      locator(selector) {
        calls.push(["locator", selector]);
        let selectedIndex =
          selector === `#${operableSearchInputId}` ? operableSearchInputIndex : null;
        return {
          filter(options) {
            calls.push(["filter", options]);
            return this;
          },
          nth(index) {
            selectedIndex = index;
            calls.push(["nth", index]);
            return this;
          },
          async count() {
            if (locatorCountError) throw new Error("locator count failed");
            if (selectedIndex === null) return searchInputCount;
            return selectedIndex >= 0 && selectedIndex < searchInputCount ? 1 : 0;
          },
          async isVisible() {
            return selectedIndex === operableSearchInputIndex;
          },
          async isEnabled() {
            return selectedIndex === operableSearchInputIndex;
          },
          async getAttribute(name) {
            const attrs = {
              id:
                selectedIndex === operableSearchInputIndex
                  ? operableSearchInputId
                  : "",
              name: "",
              placeholder: "搜索",
              "aria-label": "",
              class: "textarea",
            };
            return attrs[name] ?? null;
          },
          async fill(value, options) {
            calls.push(["fill", value, options]);
            if (search === "fill_reset") throw new Error("browser control session reset");
          },
          async press(key, options) {
            calls.push(["press", key, options]);
            if (search === "results" || search === "results_timeout") state = "search";
            if (search === "reset") {
              state = "reset";
              tabs = [];
            }
            if (search === "results_timeout") throw new Error("Timeout while pressing Enter");
            if (search === "reset") throw new Error("browser control session reset");
          },
        };
      },
      async evaluate() {
        calls.push(["evaluate"]);
        if (state === "reset") throw new Error("browser control session reset");
        if (state === "search") {
          return {
            current_path: "/search_result",
            search_route: true,
            query_matched: true,
            visible_search_input_count: visibleSearchInputCount,
            operable_search_input_count: operableSearchInputCount,
            search_input_candidates: [],
            operable_search_input:
              operableSearchInputCount === 1
                ? {
                    dom_index: operableSearchInputIndex,
                    id: operableSearchInputId,
                    exact_id_unique: exactOperableIdUnique,
                    name: "",
                    placeholder: "搜索",
                    aria_label: "",
                    class_name: "textarea",
                  }
                : null,
            visible_result_link_count: 20,
            explicit_empty_result: false,
            risk_signal_observed: false,
            search_page_verified: true,
          };
        }
        return {
          current_origin: state === "home" ? "https://www.xiaohongshu.com" : "null",
          current_path: state === "home" ? "/" : "about:blank",
          visible_search_input_count:
            state === "home" ? visibleSearchInputCount : 0,
          operable_search_input_count:
            state === "home" ? operableSearchInputCount : 0,
          search_input_candidates: [],
          operable_search_input:
            state === "home" && operableSearchInputCount === 1
              ? {
                  dom_index: operableSearchInputIndex,
                  id: operableSearchInputId,
                  exact_id_unique: exactOperableIdUnique,
                  name: "",
                  placeholder: "搜索",
                  aria_label: "",
                  class_name: "textarea",
                }
              : null,
          risk_signal_observed: false,
          workspace_verified:
            state === "home" && operableSearchInputCount === 1,
          search_page_verified: false,
        };
      },
      async waitForTimeout() {
        if (state === "reset") throw new Error("browser control session reset");
      },
    },
    dom_cua: {
      async get_visible_dom() {
        calls.push(["get_visible_dom"]);
        if (visibleDomError) throw new Error("visible DOM control unavailable");
        if (visibleDomSnapshot !== undefined) return visibleDomSnapshot;
        return {
          nodes: [
            ...Array.from({ length: operableSearchInputCount }, (_, index) => ({
              node_id: `visible-node-${index}`,
              node_name: "TEXTAREA",
              attributes: {
                id:
                  index === operableSearchInputIndex
                    ? operableSearchInputId
                    : `secondary-search-${index}`,
                name: index === operableSearchInputIndex ? "aiSearchTextarea" : "",
                placeholder: "搜索",
                class: "textarea",
              },
            })),
            {
              node_id: "self-profile-node",
              node_name: "A",
              attributes: { href: `/user/profile/${PROFILE_ID}` },
              children: [{ node_name: "#text", node_value: "我" }],
            },
          ],
          body_text: "小红书",
        };
      },
    },
  };
  const browser = {
    tabs: {
      async list() {
        listCalls += 1;
        calls.push(["list", listCalls]);
        if (browserDisconnected) throw new Error("browser disconnected");
        if (listCalls > 1 && listAfterGoto !== undefined) return listAfterGoto;
        return tabs;
      },
      async new() {
        calls.push(["new"]);
        tabs = [{ id: tab.id, url: "about:blank" }];
        if (newTabPending) return new Promise(() => {});
        return tab;
      },
      async get(id) {
        calls.push(["get", id]);
        tab.id = id;
        return tab;
      },
    },
    user: {
      async openTabs() {
        openTabsCalls += 1;
        calls.push(["openTabs"]);
        if (userTabsUnavailable) throw new Error("browser control session reset");
        if (openTabsCalls > 1 && userTabsAfterGoto !== undefined) {
          return userTabsAfterGoto;
        }
        return userTabs;
      },
      async claimTab(info) {
        calls.push(["claimTab", info]);
        const url = new URL(info.url);
        state = /\/search_result(?:\/|$)/.test(url.pathname) ? "search" : "home";
        tabs = [{ id: tab.id, url: info.url }];
        return tab;
      },
    },
  };
  return { browser, tab, calls };
}

test("contract treats an empty tab list as recoverable and remains IAB-only", () => {
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.empty_tab_list_invalidates_browser_binding, false);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.maximum_new_tabs_per_acquire_call, 1);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.maximum_user_tab_claims_per_recovery, 1);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.maximum_homepage_navigations_per_acquire_call, 1);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.homepage_navigation_soft_deadline_ms, 8_000);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.acquire_result_soft_deadline_ms, 12_000);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.existing_workspace_staged_verification, true);
  assert.equal(
    XHS_SEARCH_NAVIGATION_CONTRACT.existing_workspace_verification_surface,
    "documented_dom_cua_visible_dom_single_rpc",
  );
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.maximum_existing_workspace_verification_rpcs, 1);
  assert.equal(
    XHS_SEARCH_NAVIGATION_CONTRACT.existing_workspace_verification_includes_identity_and_risk,
    true,
  );
  assert.equal(
    XHS_SEARCH_NAVIGATION_CONTRACT.additional_identity_dom_rpc_allowed_after_workspace_verification,
    false,
  );
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.local_timer_claims_external_rpc_preemption, false);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.maximum_search_submissions_per_call, 1);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.direct_search_url_allowed, false);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.alternate_browser_allowed, false);
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.released_user_tab_claim_allowed, true);
  assert.equal(
    XHS_SEARCH_NAVIGATION_CONTRACT.browser_binding_verification,
    "documented_iab_capability_surface_plus_successful_task_tab_list",
  );
  assert.equal(XHS_SEARCH_NAVIGATION_CONTRACT.unique_exact_id_locator_preferred, true);
  assert.equal(
    XHS_SEARCH_NAVIGATION_CONTRACT.proven_operable_dom_index_fallback_allowed,
    true,
  );
});

test("documented IAB binding is verified by a successful zero-action tab list", async () => {
  const env = fakeEnvironment();
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "workspace_ready");
  assert.equal(result.browser_binding_verified, true);
  assert.equal(
    result.browser_binding_verification_method,
    "documented_iab_capability_surface_plus_successful_task_tab_list",
  );
  assert.equal(env.calls.filter((call) => call[0] === "list").length >= 1, true);
  assert.equal(env.calls.filter((call) => call[0] === "new").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "goto").length, 1);
});

test("missing documented task-tab capabilities is rejected before any acquire action", async () => {
  let listCalled = false;
  const incompleteBinding = {
    tabs: {
      async list() {
        listCalled = true;
        return [];
      },
    },
  };
  await assert.rejects(
    acquireXhsSearchWorkspace(incompleteBinding),
    /documented Codex in-app Browser binding is required/,
  );
  assert.equal(listCalled, false);
});

test("empty tab list creates one task tab and loads homepage only", async () => {
  const env = fakeEnvironment();
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "workspace_ready");
  assert.equal(result.method, "create_one_tab_then_homepage");
  assert.equal(result.new_tabs_created, 1);
  assert.equal(result.homepage_navigations_attempted, 1);
  assert.deepEqual(env.calls.filter((call) => call[0] === "goto"), [
    ["goto", "https://www.xiaohongshu.com/"],
  ]);
});

test("two visually visible responsive inputs pass only when one is operable", async () => {
  const env = fakeEnvironment({
    searchInputCount: 2,
    visibleSearchInputCount: 2,
    operableSearchInputCount: 1,
    operableSearchInputIndex: 1,
  });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "workspace_ready");
  assert.equal(result.workspace_state.visible_search_input_count, 2);
  assert.equal(result.workspace_state.operable_search_input_count, 1);
  assert.equal(result.workspace_state.operable_search_input.dom_index, 1);
});

test("existing workspace acquire returns an exact staged candidate after task list only", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ id: "existing", url: "https://www.xiaohongshu.com/", state: "home" }],
  });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "workspace_candidate_ready");
  assert.equal(result.method, "list_exact_existing_workspace_candidate");
  assert.equal(result.workspace_candidate.id, "existing");
  assert.equal(result.new_tabs_created, 0);
  assert.equal(env.calls.some((call) => call[0] === "get"), false);
  assert.equal(env.calls.some((call) => call[0] === "evaluate"), false);
  assert.equal(env.calls.some((call) => call[0] === "new"), false);
  assert.equal(env.calls.some((call) => call[0] === "goto"), false);
});

test("existing explore checkpoint wins over an unrelated blank task tab", async () => {
  const env = fakeEnvironment({
    initialTabs: [
      {
        id: "8",
        url: "https://www.xiaohongshu.com/explore",
        state: "home",
      },
      { id: "9", url: "about:blank" },
    ],
  });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "workspace_candidate_ready");
  assert.equal(result.workspace_candidate.id, "8");
  assert.equal(env.calls.some((call) => call[0] === "get"), false);
  assert.equal(env.calls.some((call) => call[0] === "evaluate"), false);
  assert.equal(env.calls.some((call) => call[0] === "new"), false);
  assert.equal(env.calls.some((call) => call[0] === "goto"), false);

  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, {
    candidate: result.workspace_candidate,
  });
  assert.equal(rebound.status, "workspace_tab_rebound");
  assert.deepEqual(env.calls.filter((call) => call[0] === "get"), [["get", "8"]]);

  const verified = await verifyXhsSearchWorkspaceCandidate(rebound.tab, {
    candidate: rebound.workspace_candidate,
    requiredProfileId: PROFILE_ID,
  });
  assert.equal(verified.status, "workspace_ready");
  assert.equal(verified.workspace_state.workspace_verified, true);
  assert.equal(verified.workspace_state.operable_search_input.node_id, "visible-node-0");
  assert.equal(verified.identity_state.identity_verified, true);
  assert.equal(verified.identity_state.required_profile_id, PROFILE_ID);
  assert.equal(verified.identity_verification_rpcs_attempted, 0);
  assert.equal(env.calls.filter((call) => call[0] === "get_visible_dom").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "evaluate").length, 0);
});

test("existing workspace visible DOM verification requires exact candidate context before RPC", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ id: "8", url: "https://www.xiaohongshu.com/explore", state: "home" }],
  });
  const result = await verifyXhsSearchWorkspaceCandidate(env.tab);
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "workspace_candidate_context_not_verified");
  assert.equal(result.workspace_verification_rpcs_attempted, 0);
  assert.equal(env.calls.some((call) => call[0] === "get_visible_dom"), false);
});

test("existing workspace verification requires the current profile id before its only DOM RPC", async () => {
  const candidate = { id: "8", url: "https://www.xiaohongshu.com/explore" };
  const env = fakeEnvironment({
    initialTabs: [{ ...candidate, state: "home" }],
  });
  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, { candidate });
  const result = await verifyXhsSearchWorkspaceCandidate(rebound.tab, { candidate });
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "workspace_candidate_context_not_verified");
  assert.equal(result.required_profile_context_verified, false);
  assert.equal(result.workspace_verification_rpcs_attempted, 0);
  assert.equal(env.calls.some((call) => call[0] === "get_visible_dom"), false);
});

test("existing workspace visible DOM verification fails closed on ambiguous search targets", async () => {
  const candidate = { id: "8", url: "https://www.xiaohongshu.com/explore" };
  const env = fakeEnvironment({
    initialTabs: [{ ...candidate, state: "home" }],
    visibleDomSnapshot: {
      nodes: [0, 1].map((index) => ({
        node_id: `node-${index}`,
        tagName: "textarea",
        attributes: {
          id: index === 0 ? "search-input-in-feeds" : "secondary-search-input",
          placeholder: "搜索",
        },
      })),
    },
  });
  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, { candidate });
  const result = await verifyXhsSearchWorkspaceCandidate(rebound.tab, {
    candidate,
    requiredProfileId: PROFILE_ID,
  });
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "existing_workspace_tab_not_verified");
  assert.equal(result.workspace_state.operable_search_input_count, 2);
  assert.equal(result.workspace_verification_rpcs_attempted, 1);
});

test("existing workspace visible DOM verification fails closed on risk text", async () => {
  const candidate = { id: "8", url: "https://www.xiaohongshu.com/explore" };
  const env = fakeEnvironment({
    initialTabs: [{ ...candidate, state: "home" }],
    visibleDomSnapshot: {
      nodes: [{
        node_id: "search-node",
        tagName: "textarea",
        attributes: { id: "search-input-in-feeds", name: "aiSearchTextarea" },
      }],
      body_text: "请完成安全验证",
    },
  });
  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, { candidate });
  const result = await verifyXhsSearchWorkspaceCandidate(rebound.tab, {
    candidate,
    requiredProfileId: PROFILE_ID,
  });
  assert.equal(result.status, "blocked");
  assert.equal(result.workspace_state.risk_signal_observed, true);
  assert.equal(result.workspace_state.workspace_verified, false);
});

test("existing workspace visible DOM verification requires an interactable node id", async () => {
  const candidate = { id: "8", url: "https://www.xiaohongshu.com/explore" };
  const env = fakeEnvironment({
    initialTabs: [{ ...candidate, state: "home" }],
    visibleDomSnapshot:
      '<textarea id="search-input-in-feeds" name="aiSearchTextarea"></textarea>',
  });
  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, { candidate });
  const result = await verifyXhsSearchWorkspaceCandidate(rebound.tab, {
    candidate,
    requiredProfileId: PROFILE_ID,
  });
  assert.equal(result.status, "blocked");
  assert.equal(result.workspace_state.operable_search_input_count, 1);
  assert.equal(result.workspace_state.operable_search_input.node_id, "");
});

test("existing workspace visible DOM RPC failure is structured and not retried", async () => {
  const candidate = { id: "8", url: "https://www.xiaohongshu.com/explore" };
  const env = fakeEnvironment({
    initialTabs: [{ ...candidate, state: "home" }],
    visibleDomError: true,
  });
  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, { candidate });
  const result = await verifyXhsSearchWorkspaceCandidate(rebound.tab, {
    candidate,
    requiredProfileId: PROFILE_ID,
  });
  assert.equal(result.status, "blocked_external_runtime");
  assert.equal(result.reason, "browser_control_unavailable_during_workspace_verification");
  assert.equal(result.workspace_verification_rpcs_attempted, 1);
  assert.equal(env.calls.filter((call) => call[0] === "get_visible_dom").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "evaluate").length, 0);
});

test("existing workspace identity is bound from the same visible DOM RPC and full DOM is not returned", async () => {
  const candidate = { id: "8", url: "https://www.xiaohongshu.com/explore" };
  const env = fakeEnvironment({
    initialTabs: [{ ...candidate, state: "home" }],
    visibleDomSnapshot: {
      nodes: [
        {
          node_id: "23",
          node_name: "TEXTAREA",
          attributes: { id: "search-input-in-feeds", name: "aiSearchTextarea" },
        },
        {
          node_id: "7",
          node_name: "A",
          attributes: { href: `/user/profile/${PROFILE_ID}` },
          children: [{ node_name: "#text", node_value: "我" }],
        },
      ],
      non_persistable_marker: "FULL_DOM_MUST_NOT_ESCAPE",
    },
  });
  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, { candidate });
  const result = await verifyXhsSearchWorkspaceCandidate(rebound.tab, {
    candidate,
    requiredProfileId: PROFILE_ID,
  });
  assert.equal(result.status, "workspace_ready");
  assert.equal(result.identity_state.identity_verified, true);
  assert.equal(result.identity_state.bound_to_workspace_snapshot, true);
  assert.equal(result.identity_state.additional_browser_rpc_required, false);
  assert.equal(result.identity_state.required_profile_self_link_match_count, 1);
  assert.equal(result.identity_state.login_prompt_observed, false);
  assert.equal(result.identity_state.risk_signal_observed, false);
  assert.equal(result.workspace_verification_rpcs_attempted, 1);
  assert.equal(result.identity_verification_rpcs_attempted, 0);
  assert.equal(env.calls.filter((call) => call[0] === "get_visible_dom").length, 1);
  assert.equal(JSON.stringify(result).includes("FULL_DOM_MUST_NOT_ESCAPE"), false);
});

test("existing workspace identity fails closed when the fresh DOM lacks the required self profile", async () => {
  const candidate = { id: "8", url: "https://www.xiaohongshu.com/explore" };
  const env = fakeEnvironment({
    initialTabs: [{ ...candidate, state: "home" }],
    visibleDomSnapshot: {
      nodes: [
        {
          node_id: "23",
          node_name: "TEXTAREA",
          attributes: { id: "search-input-in-feeds", name: "aiSearchTextarea" },
        },
        {
          node_id: "7",
          node_name: "A",
          attributes: { href: "/user/profile/111111111111111111111111" },
          children: [{ node_name: "#text", node_value: "我" }],
        },
      ],
    },
  });
  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, { candidate });
  const result = await verifyXhsSearchWorkspaceCandidate(rebound.tab, {
    candidate,
    requiredProfileId: PROFILE_ID,
  });
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "existing_workspace_identity_not_verified");
  assert.equal(result.workspace_state.workspace_verified, true);
  assert.equal(result.identity_state.identity_verified, false);
  assert.equal(result.identity_state.required_profile_self_link_match_count, 0);
  assert.equal(env.calls.filter((call) => call[0] === "get_visible_dom").length, 1);
});

test("existing workspace identity fails closed on a login prompt from the same snapshot", async () => {
  const candidate = { id: "8", url: "https://www.xiaohongshu.com/explore" };
  const env = fakeEnvironment({
    initialTabs: [{ ...candidate, state: "home" }],
    visibleDomSnapshot: {
      nodes: [
        {
          node_id: "23",
          node_name: "TEXTAREA",
          attributes: { id: "search-input-in-feeds", name: "aiSearchTextarea" },
        },
        {
          node_id: "7",
          node_name: "A",
          attributes: { href: `/user/profile/${PROFILE_ID}` },
          children: [{ node_name: "#text", node_value: "我" }],
        },
      ],
      modal_text: "请先登录",
    },
  });
  const rebound = await rebindXhsSearchWorkspaceCandidate(env.browser, { candidate });
  const result = await verifyXhsSearchWorkspaceCandidate(rebound.tab, {
    candidate,
    requiredProfileId: PROFILE_ID,
  });
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "existing_workspace_identity_not_verified");
  assert.equal(result.identity_state.login_prompt_observed, true);
  assert.equal(result.identity_state.identity_verified, false);
});

test("released visible homepage tab is claimed before creating a duplicate", async () => {
  const env = fakeEnvironment({
    userTabs: [
      {
        id: "claim-home",
        title: "小红书",
        url: "https://www.xiaohongshu.com/",
      },
    ],
  });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "workspace_ready");
  assert.equal(result.method, "claim_existing_visible_user_workspace_tab");
  assert.equal(result.user_tab_claims_attempted, 1);
  assert.equal(result.new_tabs_created, 0);
  assert.equal(env.calls.filter((call) => call[0] === "claimTab").length, 1);
  assert.equal(env.calls.some((call) => call[0] === "new"), false);
  assert.equal(env.calls.some((call) => call[0] === "goto"), false);
});

test("multiple visible workspace candidates fail closed before claim or creation", async () => {
  const env = fakeEnvironment({
    userTabs: [
      { id: "home-1", title: "小红书 1", url: "https://www.xiaohongshu.com/" },
      { id: "home-2", title: "小红书 2", url: "https://www.xiaohongshu.com/" },
    ],
  });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "visible_user_workspace_tab_not_unique");
  assert.equal(result.user_workspace_candidates_found, 2);
  assert.equal(env.calls.some((call) => call[0] === "claimTab"), false);
  assert.equal(env.calls.some((call) => call[0] === "new"), false);
});

test("homepage timeout is accepted only when the created tab proves workspace state", async () => {
  const env = fakeEnvironment({ goto: "home_timeout" });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "workspace_ready");
  assert.equal(result.homepage_navigation_result, "timeout");
  assert.equal(result.workspace_state.workspace_verified, true);
  assert.equal(env.calls.filter((call) => call[0] === "goto").length, 1);
});

test("pending homepage navigation returns structured indeterminate result before caller timeout", async () => {
  const env = fakeEnvironment({ goto: "pending" });
  const startedAt = Date.now();
  const result = await acquireXhsSearchWorkspace(env.browser, {
    navigationSoftDeadlineMs: 20,
  });
  assert.equal(result.status, "blocked_external_runtime");
  assert.equal(
    result.reason,
    "homepage_navigation_indeterminate_before_acquire_deadline",
  );
  assert.equal(result.homepage_navigation_result, "soft_deadline_indeterminate");
  assert.equal(result.browser_binding_verified, true);
  assert.equal(result.new_tabs_created, 1);
  assert.equal(result.homepage_navigations_attempted, 1);
  assert.equal(Date.now() - startedAt < 250, true);
  assert.equal(env.calls.filter((call) => call[0] === "new").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "goto").length, 1);
  assert.equal(env.calls.some((call) => call[0] === "press"), false);
});

test("pending tab creation returns structured indeterminate result before any navigation", async () => {
  const env = fakeEnvironment({ newTabPending: true });
  const startedAt = Date.now();
  const result = await acquireXhsSearchWorkspace(env.browser, {
    acquireResultSoftDeadlineMs: 30,
  });
  assert.equal(result.status, "blocked_external_runtime");
  assert.equal(
    result.reason,
    "task_tab_creation_indeterminate_before_acquire_deadline",
  );
  assert.equal(result.acquire_deadline_stage, "task_tab_creation");
  assert.equal(result.new_tab_creation_attempts, 1);
  assert.equal(result.new_tabs_created, null);
  assert.equal(result.homepage_navigations_attempted, 0);
  assert.equal(Date.now() - startedAt < 250, true);
  assert.equal(env.calls.filter((call) => call[0] === "new").length, 1);
  assert.equal(env.calls.some((call) => call[0] === "goto"), false);
});

test("session reset with no remaining tab is classified as blocked_external_runtime", async () => {
  const env = fakeEnvironment({ goto: "reset", listAfterGoto: [] });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "blocked_external_runtime");
  assert.equal(result.reason, "no_rebindable_tab_after_homepage_navigation");
  assert.equal(result.rebindable_tabs_found, 0);
  assert.equal(env.calls.filter((call) => call[0] === "goto").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "new").length, 1);
});

test("homepage navigation reset claims the released visible homepage tab", async () => {
  const env = fakeEnvironment({
    goto: "reset",
    listAfterGoto: [],
    userTabsAfterGoto: [
      {
        id: "released-home",
        title: "小红书",
        url: "https://www.xiaohongshu.com/",
      },
    ],
  });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "workspace_ready");
  assert.equal(
    result.method,
    "claim_released_user_workspace_after_homepage_navigation",
  );
  assert.equal(result.user_tab_claims_attempted, 1);
  assert.equal(env.calls.filter((call) => call[0] === "goto").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "claimTab").length, 1);
});

test("explicit browser disconnect is classified before any tab creation", async () => {
  const env = fakeEnvironment({ browserDisconnected: true });
  const result = await acquireXhsSearchWorkspace(env.browser);
  assert.equal(result.status, "blocked_external_runtime");
  assert.equal(result.reason, "browser_binding_unavailable_before_workspace_acquire");
  assert.equal(result.browser_binding_verified, false);
  assert.equal(
    result.browser_binding_verification_method,
    "documented_iab_capability_surface_plus_successful_task_tab_list",
  );
  assert.equal(env.calls.some((call) => call[0] === "new"), false);
});

test("missing search preconditions block before input discovery", async () => {
  const env = fakeEnvironment({ initialTabs: [{ state: "home" }] });
  const result = await openXhsSearchResults(env.tab, {
    query: QUERY,
    preconditions: { workspace_verified: true },
  });
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "required_search_preconditions_not_verified");
  assert.deepEqual(result.missing_preconditions, [
    "account_identity_verified",
    "risk_state_clear",
  ]);
  assert.equal(env.calls.length, 0);
});

test("same-tab visible search input submits once and proves results", async () => {
  const env = fakeEnvironment({ initialTabs: [{ state: "home" }] });
  const result = await openXhsSearchResults(env.tab, SAFE_SEARCH);
  assert.equal(result.status, "opened");
  assert.equal(result.method, "same_tab_visible_search_input_enter");
  assert.equal(result.search_submissions_attempted, 1);
  assert.equal(result.search_state.search_page_verified, true);
  assert.equal(env.calls.filter((call) => call[0] === "press").length, 1);
});

test("search prefers the unique exact id of the proven operable responsive input", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    searchInputCount: 2,
    visibleSearchInputCount: 2,
    operableSearchInputCount: 1,
    operableSearchInputIndex: 1,
  });
  const result = await openXhsSearchResults(env.tab, SAFE_SEARCH);
  assert.equal(result.status, "opened");
  assert.equal(result.locator_strategy, "unique_exact_id");
  assert.deepEqual(env.calls.filter((call) => call[0] === "locator"), [
    ["locator", "#primary-search"],
  ]);
  assert.equal(env.calls.some((call) => call[0] === "nth"), false);
  assert.equal(env.calls.filter((call) => call[0] === "fill").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "press").length, 1);
});

test("live responsive surface targets unique search-input-in-feeds without arbitrary choice", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    searchInputCount: 3,
    visibleSearchInputCount: 2,
    operableSearchInputCount: 1,
    operableSearchInputIndex: 2,
    operableSearchInputId: "search-input-in-feeds",
  });
  const result = await openXhsSearchResults(env.tab, SAFE_SEARCH);
  assert.equal(result.status, "opened");
  assert.equal(result.locator_strategy, "unique_exact_id");
  assert.deepEqual(env.calls.filter((call) => call[0] === "locator"), [
    ["locator", "#search-input-in-feeds"],
  ]);
  assert.equal(env.calls.some((call) => call[0] === "nth"), false);
  assert.equal(env.calls.filter((call) => call[0] === "fill").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "press").length, 1);
});

test("non-unique exact id falls back only to the already proven operable DOM index", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    searchInputCount: 3,
    visibleSearchInputCount: 2,
    operableSearchInputCount: 1,
    operableSearchInputIndex: 2,
    exactOperableIdUnique: false,
  });
  const result = await openXhsSearchResults(env.tab, SAFE_SEARCH);
  assert.equal(result.status, "opened");
  assert.equal(result.locator_strategy, "proven_operable_dom_index");
  assert.deepEqual(env.calls.filter((call) => call[0] === "nth"), [["nth", 2]]);
});

test("locator count failure reports the exact preflight stage and never fills", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    locatorCountError: true,
  });
  const result = await openXhsSearchResults(env.tab, SAFE_SEARCH);
  assert.equal(result.status, "blocked_external_runtime");
  assert.equal(result.reason, "browser_control_unavailable_during_search_preflight");
  assert.equal(result.preflight_stage, "locator_count");
  assert.equal(result.locator_strategy, "unique_exact_id");
  assert.equal(result.search_submissions_attempted, 0);
  assert.equal(env.calls.some((call) => call[0] === "fill"), false);
  assert.equal(env.calls.some((call) => call[0] === "press"), false);
});

test("two truly operable search inputs remain blocked before fill", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    searchInputCount: 2,
    visibleSearchInputCount: 2,
    operableSearchInputCount: 2,
  });
  const result = await openXhsSearchResults(env.tab, SAFE_SEARCH);
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "search_input_not_unique");
  assert.equal(result.visible_search_input_count, 2);
  assert.equal(result.operable_search_input_count, 2);
  assert.equal(env.calls.some((call) => call[0] === "fill"), false);
  assert.equal(env.calls.some((call) => call[0] === "press"), false);
});

test("ambiguous Enter timeout is accepted only when search results are proven", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    search: "results_timeout",
  });
  const result = await openXhsSearchResults(env.tab, SAFE_SEARCH);
  assert.equal(result.status, "opened");
  assert.equal(result.submit_result, "timeout");
  assert.equal(result.opened_despite_ambiguous_timeout, true);
  assert.equal(env.calls.filter((call) => call[0] === "press").length, 1);
});

test("search control reset blocks externally without a second submission", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    search: "reset",
  });
  const result = await openXhsSearchResults(env.tab, SAFE_SEARCH);
  assert.equal(result.status, "blocked_external_runtime");
  assert.equal(result.reason, "browser_control_unavailable_after_search_submit");
  assert.equal(result.search_submissions_attempted, 1);
  assert.equal(result.blind_retry_used, false);
  assert.equal(env.calls.filter((call) => call[0] === "press").length, 1);
});

test("search control reset claims and verifies the released result tab", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    search: "reset",
    userTabs: [
      {
        id: "released-search",
        title: QUERY,
        url: "https://www.xiaohongshu.com/search_result",
      },
    ],
  });
  const result = await openXhsSearchResults(env.tab, {
    ...SAFE_SEARCH,
    browser: env.browser,
  });
  assert.equal(result.status, "opened");
  assert.equal(result.method, "claim_released_user_search_tab_after_control_reset");
  assert.equal(result.recovered_after_control_reset, true);
  assert.equal(result.user_tab_claims_attempted, 1);
  assert.equal(env.calls.filter((call) => call[0] === "press").length, 1);
  assert.equal(env.calls.filter((call) => call[0] === "claimTab").length, 1);
});

test("read-only search recovery claims once and never submits", async () => {
  const env = fakeEnvironment({
    userTabs: [
      {
        id: "released-search",
        title: QUERY,
        url: "https://www.xiaohongshu.com/search_result",
      },
    ],
  });
  const result = await recoverXhsSearchPage(env.browser, { query: QUERY });
  assert.equal(result.status, "verified");
  assert.equal(result.method, "claim_released_user_search_tab_after_control_reset");
  assert.equal(result.search_submissions_attempted, 0);
  assert.equal(result.user_tab_claims_attempted, 1);
  assert.equal(env.calls.some((call) => call[0] === "press"), false);
});

test("read-only search verifier performs zero submissions", async () => {
  const env = fakeEnvironment({ initialTabs: [{ state: "search" }] });
  const result = await verifyXhsSearchPage(env.tab, { query: QUERY });
  assert.equal(result.status, "verified");
  assert.equal(result.search_submissions_attempted, 0);
  assert.equal(env.calls.some((call) => call[0] === "press"), false);
});

test("read-only surface inspector preserves visible versus operable counts", async () => {
  const env = fakeEnvironment({
    initialTabs: [{ state: "home" }],
    visibleSearchInputCount: 2,
    operableSearchInputCount: 1,
    operableSearchInputIndex: 1,
  });
  const result = await inspectXhsSearchInputSurface(env.tab);
  assert.equal(result.status, "inspected");
  assert.equal(result.surface_state.visible_search_input_count, 2);
  assert.equal(result.surface_state.operable_search_input_count, 1);
  assert.equal(result.search_submissions_attempted, 0);
  assert.equal(env.calls.some((call) => call[0] === "fill"), false);
  assert.equal(env.calls.some((call) => call[0] === "press"), false);
});

test("implementation has no browser substitution, direct search URL, coordinate, or DOM CUA action path", async () => {
  const source = await readFile(
    new URL("./xhs_in_app_search_navigation.mjs", import.meta.url),
    "utf8",
  );
  assert.equal(/browser-client|agent\.browsers|getForUrl|getDefault/.test(source), false);
  assert.equal(/search_result\?keyword=/.test(source), false);
  assert.equal(/\.cua\.|\.dom_cua\.(?:click|double_click|type|keypress|scroll)|\bchrome\b|\bedge\b/.test(source), false);
  assert.equal((source.match(/\.dom_cua\.get_visible_dom\s*\(/g) ?? []).length, 1);
  assert.equal((source.match(/\.goto\s*\(/g) ?? []).length, 1);
  assert.equal((source.match(/tabs\.new\s*\(/g) ?? []).length, 1);
  assert.match(source, /elementFromPoint/);
  assert.match(source, /aria-hidden='true'/);
  assert.match(source, /\[inert\]/);
  assert.match(source, /readOnly/);
  assert.equal(/\.first\s*\(/.test(source), false);
});
