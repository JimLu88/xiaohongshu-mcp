#!/usr/bin/env node

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  XHS_DETAIL_NAVIGATION_CONTRACT,
  openXhsDetailFromSearch,
  recoverXhsDetailTarget,
  verifyXhsDetailTarget,
} from "./xhs_in_app_detail_navigation.mjs";

const TARGET = Object.freeze({
  noteId: "6934ebd1000000001e02f8e9",
  expectedTitle: "还没入住家具已经开始变形的变形开裂的开裂",
});

const SAFE_OPTIONS = Object.freeze({
  ...TARGET,
  settleMs: 100,
  preconditions: {
    account_identity_verified: true,
    search_page_verified: true,
    target_identity_verified: true,
    risk_state_clear: true,
  },
});

function fakeTab({
  count = 1,
  visible = true,
  href = `/explore/${TARGET.noteId}`,
  click = "open",
  probeAfter = "available",
  initialState = "search",
  preflightError = false,
  settleError = false,
} = {}) {
  let state = initialState;
  let probeCount = 0;
  const calls = [];
  const link = {
    filter(options) {
      calls.push(["filter", options]);
      return this;
    },
    async count() {
      if (preflightError) throw new Error("browser control session reset");
      return count;
    },
    async isVisible() {
      return visible;
    },
    async getAttribute(name, options) {
      calls.push(["getAttribute", name, options]);
      return href;
    },
    async click(options) {
      calls.push(["click", options]);
      if (click === "open" || click === "open_timeout" || click === "open_reset") {
        state = "detail";
      }
      if (click === "timeout" || click === "open_timeout") {
        throw new Error("Timeout while clicking exact result link");
      }
      if (click === "reset" || click === "open_reset") {
        throw new Error("browser control session reset");
      }
      if (click === "error") throw new Error("click failed");
    },
  };
  return {
    calls,
    playwright: {
      locator(selector) {
        calls.push(["locator", selector]);
        return link;
      },
      async evaluate() {
        probeCount += 1;
        if (probeAfter === "reset" && probeCount >= 1) {
          throw new Error("browser control session reset");
        }
        const detail = state === "detail";
        return {
          current_path: detail ? `/explore/${TARGET.noteId}` : "/search_result",
          note_id_in_location: detail,
          expected_title_visible: true,
          visible_editor_count: detail ? 1 : 0,
          visible_detail_root_count: detail ? 1 : 0,
          search_route: !detail,
          detail_surface_present: detail,
          target_confirmed: detail,
        };
      },
      async waitForTimeout() {
        if (settleError) throw new Error("browser control session reset");
      },
    },
  };
}

function fakeRecoveryBrowser({ userTabs = [], claimedTab, taskTabs = [] } = {}) {
  const calls = [];
  return {
    calls,
    tabs: {
      async list() {
        calls.push(["list"]);
        return taskTabs;
      },
      async get(id) {
        calls.push(["get", id]);
        return claimedTab;
      },
    },
    user: {
      async openTabs() {
        calls.push(["openTabs"]);
        return userTabs;
      },
      async claimTab(info) {
        calls.push(["claimTab", info]);
        return claimedTab;
      },
    },
  };
}

test("contract restricts navigation to one same-tab semantic action", () => {
  assert.equal(XHS_DETAIL_NAVIGATION_CONTRACT.maximum_navigation_actions_per_call, 1);
  assert.equal(XHS_DETAIL_NAVIGATION_CONTRACT.maximum_user_tab_claims_per_recovery, 1);
  assert.equal(XHS_DETAIL_NAVIGATION_CONTRACT.new_tab_allowed, false);
  assert.equal(XHS_DETAIL_NAVIGATION_CONTRACT.goto_allowed, false);
  assert.equal(XHS_DETAIL_NAVIGATION_CONTRACT.history_navigation_allowed, false);
  assert.equal(XHS_DETAIL_NAVIGATION_CONTRACT.coordinate_click_allowed, false);
  assert.equal(XHS_DETAIL_NAVIGATION_CONTRACT.blind_retry_allowed, false);
  assert.equal(XHS_DETAIL_NAVIGATION_CONTRACT.released_user_tab_claim_allowed, true);
});

test("missing preconditions block before locating or clicking", async () => {
  const tab = fakeTab();
  const result = await openXhsDetailFromSearch(tab, {
    ...TARGET,
    preconditions: { account_identity_verified: true },
  });
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "required_preconditions_not_verified");
  assert.deepEqual(result.missing_preconditions, [
    "search_page_verified",
    "target_identity_verified",
    "risk_state_clear",
  ]);
  assert.equal(tab.calls.length, 0);
});

test("missing, duplicate, hidden, and mismatched links fail before action", async () => {
  const cases = [
    [fakeTab({ count: 0 }), "exact_target_link_missing"],
    [fakeTab({ count: 2 }), "exact_target_link_not_unique"],
    [fakeTab({ visible: false }), "exact_target_link_not_visible"],
    [fakeTab({ href: "/explore/not-the-target" }), "exact_target_link_href_mismatch"],
  ];
  for (const [tab, reason] of cases) {
    const result = await openXhsDetailFromSearch(tab, SAFE_OPTIONS);
    assert.equal(result.status, "blocked");
    assert.equal(result.reason, reason);
    assert.equal(tab.calls.some((call) => call[0] === "click"), false);
  }
});

test("same-tab exact target click opens only after target proof", async () => {
  const tab = fakeTab();
  const result = await openXhsDetailFromSearch(tab, SAFE_OPTIONS);
  assert.equal(result.status, "opened");
  assert.equal(result.method, "same_tab_exact_target_semantic_click");
  assert.equal(result.navigation_actions_attempted, 1);
  assert.equal(result.detail_state.target_confirmed, true);
  assert.equal(result.new_tab_used, false);
  assert.equal(result.goto_used, false);
  assert.equal(result.history_navigation_used, false);
  assert.equal(tab.calls.filter((call) => call[0] === "click").length, 1);
});

test("ambiguous click timeout is accepted only when the target detail is proven", async () => {
  const tab = fakeTab({ click: "open_timeout" });
  const result = await openXhsDetailFromSearch(tab, SAFE_OPTIONS);
  assert.equal(result.status, "opened");
  assert.equal(result.click_result, "timeout");
  assert.equal(result.opened_despite_ambiguous_timeout, true);
  assert.equal(result.detail_state.target_confirmed, true);
  assert.equal(tab.calls.filter((call) => call[0] === "click").length, 1);
});

test("unchanged state after timeout blocks without a second navigation", async () => {
  const tab = fakeTab({ click: "timeout" });
  const result = await openXhsDetailFromSearch(tab, SAFE_OPTIONS);
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "target_detail_not_confirmed_after_single_semantic_click");
  assert.equal(result.click_result, "timeout");
  assert.equal(result.navigation_actions_attempted, 1);
  assert.equal(result.blind_retry_used, false);
  assert.equal(tab.calls.filter((call) => call[0] === "click").length, 1);
});

test("control reset after navigation returns a rebind-only stop result", async () => {
  const tab = fakeTab({
    click: "reset",
    settleError: true,
    probeAfter: "reset",
  });
  const result = await openXhsDetailFromSearch(tab, SAFE_OPTIONS);
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "browser_control_unavailable_after_navigation");
  assert.equal(result.post_navigation_probe_error_kind, "control_session_unavailable");
  assert.equal(result.settle_error_kind, "control_session_unavailable");
  assert.match(result.resume_contract, /rebind/);
  assert.equal(result.navigation_actions_attempted, 1);
  assert.equal(result.blind_retry_used, false);
});

test("control reset after navigation claims and verifies the released detail tab", async () => {
  const sourceTab = fakeTab({
    click: "reset",
    settleError: true,
    probeAfter: "reset",
  });
  const claimedTab = fakeTab({ initialState: "detail" });
  const browser = fakeRecoveryBrowser({
    userTabs: [
      {
        id: "released-detail",
        title: TARGET.expectedTitle,
        url: `https://www.xiaohongshu.com/explore/${TARGET.noteId}`,
      },
    ],
    claimedTab,
  });
  const result = await openXhsDetailFromSearch(sourceTab, {
    ...SAFE_OPTIONS,
    browser,
  });
  assert.equal(result.status, "opened");
  assert.equal(result.method, "claim_released_user_detail_tab_after_control_reset");
  assert.equal(result.recovered_after_control_reset, true);
  assert.equal(result.user_tab_claims_attempted, 1);
  assert.equal(sourceTab.calls.filter((call) => call[0] === "click").length, 1);
  assert.equal(browser.calls.filter((call) => call[0] === "claimTab").length, 1);
});

test("control reset during target preflight blocks before navigation", async () => {
  const tab = fakeTab({ preflightError: true });
  const result = await openXhsDetailFromSearch(tab, SAFE_OPTIONS);
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "browser_control_unavailable_during_target_preflight");
  assert.equal(result.preflight_error_kind, "control_session_unavailable");
  assert.equal(result.navigation_actions_attempted, 0);
  assert.equal(tab.calls.some((call) => call[0] === "click"), false);
});

test("read-only verifier confirms an already open target after tab rebind", async () => {
  const tab = fakeTab({ initialState: "detail" });
  const result = await verifyXhsDetailTarget(tab, TARGET);
  assert.equal(result.status, "verified");
  assert.equal(result.navigation_actions_attempted, 0);
  assert.equal(result.detail_state.target_confirmed, true);
  assert.equal(tab.calls.some((call) => call[0] === "click"), false);
});

test("read-only verifier never upgrades an unconfirmed search page", async () => {
  const tab = fakeTab({ initialState: "search" });
  const result = await verifyXhsDetailTarget(tab, TARGET);
  assert.equal(result.status, "not_verified");
  assert.equal(result.navigation_actions_attempted, 0);
  assert.equal(result.detail_state.target_confirmed, false);
});

test("read-only detail recovery claims exactly one released target without navigation", async () => {
  const claimedTab = fakeTab({ initialState: "detail" });
  const browser = fakeRecoveryBrowser({
    userTabs: [
      {
        id: "released-detail",
        title: TARGET.expectedTitle,
        url: `https://www.xiaohongshu.com/explore/${TARGET.noteId}`,
      },
    ],
    claimedTab,
  });
  const result = await recoverXhsDetailTarget(browser, TARGET);
  assert.equal(result.status, "verified");
  assert.equal(result.method, "claim_released_user_detail_tab_after_control_reset");
  assert.equal(result.navigation_actions_attempted, 0);
  assert.equal(result.user_tab_claims_attempted, 1);
  assert.equal(claimedTab.calls.some((call) => call[0] === "click"), false);
});

test("read-only detail recovery blocks on multiple released target tabs", async () => {
  const claimedTab = fakeTab({ initialState: "detail" });
  const url = `https://www.xiaohongshu.com/explore/${TARGET.noteId}`;
  const browser = fakeRecoveryBrowser({
    userTabs: [
      { id: "released-detail-1", title: TARGET.expectedTitle, url },
      { id: "released-detail-2", title: TARGET.expectedTitle, url },
    ],
    claimedTab,
  });
  const result = await recoverXhsDetailTarget(browser, TARGET);
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "visible_user_detail_tab_not_unique");
  assert.equal(result.detail_candidates_found, 2);
  assert.equal(browser.calls.some((call) => call[0] === "claimTab"), false);
  assert.equal(claimedTab.calls.some((call) => call[0] === "click"), false);
});

test("implementation contains no direct tab creation, goto, back, or coordinate action", async () => {
  const source = await readFile(
    new URL("./xhs_in_app_detail_navigation.mjs", import.meta.url),
    "utf8",
  );
  for (const forbidden of [/\.goto\s*\(/, /\.back\s*\(/, /tabs\.new\s*\(/, /\.cua\./, /\.dom_cua\./]) {
    assert.equal(forbidden.test(source), false, `forbidden navigation surface: ${forbidden}`);
  }
});
