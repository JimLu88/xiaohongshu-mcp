#!/usr/bin/env node

import assert from "node:assert/strict";
import test from "node:test";

import {
  XHS_CAROUSEL_INTERACTION_CONTRACT,
  advanceXhsCarousel,
} from "./xhs_in_app_carousel.mjs";

const SAFE_OPTIONS = Object.freeze({
  settleMs: 100,
  preconditions: {
    account_identity_verified: true,
    target_identity_verified: true,
    risk_state_clear: true,
  },
});

function fakeTab({
  count = 1,
  visible = true,
  enabled = true,
  click = "advance",
  keyboard = "unchanged",
} = {}) {
  let state = 0;
  const calls = [];
  const next = {
    async count() {
      return count;
    },
    async isVisible() {
      return visible;
    },
    async isEnabled() {
      return enabled;
    },
    async click(options) {
      calls.push(["click", options]);
      if (click === "advance" || click === "advance_timeout") state += 1;
      if (click === "timeout" || click === "advance_timeout") {
        throw new Error("Timeout while clicking");
      }
      if (click === "error") throw new Error("click failed");
    },
  };
  const body = {
    async press(key, options) {
      calls.push(["press", key, options]);
      if (keyboard === "advance" || keyboard === "advance_timeout") state += 1;
      if (keyboard === "timeout" || keyboard === "advance_timeout") {
        throw new Error("Timeout while pressing");
      }
      if (keyboard === "error") throw new Error("press failed");
    },
  };
  return {
    calls,
    playwright: {
      locator(selector) {
        return selector === "body" ? body : next;
      },
      async evaluate() {
        return { active_index: state };
      },
      async waitForTimeout() {},
    },
  };
}

test("contract forbids coordinate fallback", () => {
  assert.equal(XHS_CAROUSEL_INTERACTION_CONTRACT.coordinate_click_allowed, false);
  assert.equal(XHS_CAROUSEL_INTERACTION_CONTRACT.maximum_actions_per_call, 2);
  assert.equal(XHS_CAROUSEL_INTERACTION_CONTRACT.required_preconditions.length, 3);
});

test("force semantic click advances one item and proves state change", async () => {
  const tab = fakeTab();
  const result = await advanceXhsCarousel(tab, SAFE_OPTIONS);
  assert.equal(result.status, "advanced");
  assert.equal(result.method, "force_semantic_click");
  assert.equal(result.actions_attempted, 1);
  assert.deepEqual(tab.calls, [["click", { force: true, timeoutMs: 3000 }]]);
});

test("ambiguous click timeout is accepted only when post-state changed", async () => {
  const tab = fakeTab({ click: "advance_timeout" });
  const result = await advanceXhsCarousel(tab, SAFE_OPTIONS);
  assert.equal(result.status, "advanced");
  assert.equal(result.click_result, "timeout");
  assert.equal(result.advanced_despite_ambiguous_timeout, true);
  assert.equal(result.actions_attempted, 1);
  assert.equal(tab.calls.length, 1);
});

test("unchanged click permits one verified keyboard fallback", async () => {
  const tab = fakeTab({ click: "timeout", keyboard: "advance" });
  const result = await advanceXhsCarousel(tab, SAFE_OPTIONS);
  assert.equal(result.status, "advanced");
  assert.equal(result.method, "keyboard_arrow_right");
  assert.equal(result.actions_attempted, 2);
  assert.equal(tab.calls[1][1], "ArrowRight");
});

test("unchanged state fails closed after two bounded semantic actions", async () => {
  const tab = fakeTab({ click: "timeout", keyboard: "timeout" });
  const result = await advanceXhsCarousel(tab, SAFE_OPTIONS);
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "media_state_unchanged_after_bounded_semantic_actions");
  assert.equal(result.coordinate_click_used, false);
  assert.equal(result.blind_retry_used, false);
  assert.equal(result.actions_attempted, 2);
});

test("missing, duplicate, hidden, and disabled controls fail before action", async () => {
  const cases = [
    [fakeTab({ count: 0 }), "next_control_missing"],
    [fakeTab({ count: 2 }), "next_control_not_unique"],
    [fakeTab({ visible: false }), "next_control_not_visible"],
    [fakeTab({ enabled: false }), "next_control_disabled_or_carousel_end"],
  ];
  for (const [tab, reason] of cases) {
    const result = await advanceXhsCarousel(tab, SAFE_OPTIONS);
    assert.equal(result.status, "blocked");
    assert.equal(result.reason, reason);
    assert.equal(tab.calls.length, 0);
  }
});

test("missing identity or risk preconditions blocks before browser action", async () => {
  const tab = fakeTab();
  const result = await advanceXhsCarousel(tab, {
    preconditions: { account_identity_verified: true },
  });
  assert.equal(result.status, "blocked");
  assert.equal(result.reason, "required_preconditions_not_verified");
  assert.deepEqual(result.missing_preconditions, [
    "target_identity_verified",
    "risk_state_clear",
  ]);
  assert.equal(tab.calls.length, 0);
});
