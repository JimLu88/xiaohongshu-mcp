#!/usr/bin/env node
/**
 * Deterministic one-step carousel adapter for the Codex in-app browser.
 *
 * The caller passes a documented Browser Tab object. This module never opens
 * a page, never logs in, and never loops through media. It advances at most
 * one item and proves the change from a read-only structural state probe.
 */

import { createHash } from "node:crypto";

export const XHS_CAROUSEL_INTERACTION_CONTRACT = Object.freeze({
  contract_id: "panse-xhs-iab-carousel.v1",
  next_selector: ".arrow-controller.right",
  maximum_actions_per_call: 2,
  action_order: ["force_semantic_click", "keyboard_arrow_right"],
  required_preconditions: [
    "account_identity_verified",
    "target_identity_verified",
    "risk_state_clear",
  ],
  coordinate_click_allowed: false,
  state_change_required: true,
  timeout_is_success_without_state_change: false,
});

function carouselStateProbe() {
  const next = document.querySelector(".arrow-controller.right");
  let root = next?.parentElement ?? document.body;
  for (let depth = 0; depth < 6 && root?.parentElement; depth += 1) {
    const mediaCount = root.querySelectorAll("img, video").length;
    const slideCount = root.querySelectorAll(
      "[class*='slide'], [class*='swiper'], [class*='carousel']",
    ).length;
    if (mediaCount > 1 || slideCount > 1) break;
    root = root.parentElement;
  }

  const structuralSelectors = [
    ".swiper-slide-active",
    ".swiper-slide",
    "[class*='carousel']",
    "[class*='indicator']",
    "[aria-current]",
    "[aria-hidden]",
  ].join(", ");
  const structural = Array.from(root?.querySelectorAll(structuralSelectors) ?? [])
    .slice(0, 80)
    .map((element) => ({
      tag: element.tagName,
      class_name: String(element.className ?? ""),
      data_index:
        element.getAttribute("data-swiper-slide-index") ??
        element.getAttribute("data-index"),
      aria_current: element.getAttribute("aria-current"),
      aria_hidden: element.getAttribute("aria-hidden"),
      transform: element.style?.transform ?? "",
      display: element.style?.display ?? "",
      opacity: element.style?.opacity ?? "",
    }));
  const media = Array.from(root?.querySelectorAll("img, video") ?? [])
    .slice(0, 30)
    .map((element) => ({
      tag: element.tagName,
      source:
        element.currentSrc ||
        element.getAttribute("src") ||
        element.getAttribute("poster") ||
        "",
      aria_hidden: element.getAttribute("aria-hidden"),
      parent_class: String(element.parentElement?.className ?? ""),
    }));

  return {
    next_present: Boolean(next),
    next_class: String(next?.className ?? ""),
    next_disabled:
      next?.getAttribute("aria-disabled") ??
      (next?.hasAttribute("disabled") ? "true" : null),
    structural,
    media,
  };
}

function stateHash(value) {
  const proofState =
    Array.isArray(value?.structural) || Array.isArray(value?.media)
      ? { structural: value.structural ?? [], media: value.media ?? [] }
      : value;
  return createHash("sha256").update(JSON.stringify(proofState)).digest("hex");
}

function classifyError(error) {
  const text = `${error?.name ?? ""} ${error?.message ?? ""}`;
  return /timeout/i.test(text) ? "timeout" : "error";
}

async function probe(tab) {
  const state = await tab.playwright.evaluate(carouselStateProbe, undefined, {
    timeoutMs: 3_000,
  });
  return { hash: stateHash(state), state };
}

async function waitForSettle(tab, settleMs) {
  await tab.playwright.waitForTimeout(settleMs);
}

async function attempt(action) {
  try {
    await action();
    return "ok";
  } catch (error) {
    return classifyError(error);
  }
}

function resultBase(before, selector) {
  return {
    contract_id: XHS_CAROUSEL_INTERACTION_CONTRACT.contract_id,
    selector,
    before_state_sha256: before.hash,
    coordinate_click_used: false,
    blind_retry_used: false,
  };
}

export async function advanceXhsCarousel(tab, options = {}) {
  if (!tab?.playwright?.locator || !tab?.playwright?.evaluate) {
    throw new TypeError("a documented in-app Browser Tab is required");
  }
  const selector = options.selector ?? XHS_CAROUSEL_INTERACTION_CONTRACT.next_selector;
  const preconditions = options.preconditions ?? {};
  const missingPreconditions =
    XHS_CAROUSEL_INTERACTION_CONTRACT.required_preconditions.filter(
      (name) => preconditions[name] !== true,
    );
  if (missingPreconditions.length > 0) {
    return {
      contract_id: XHS_CAROUSEL_INTERACTION_CONTRACT.contract_id,
      status: "blocked",
      reason: "required_preconditions_not_verified",
      missing_preconditions: missingPreconditions,
      selector,
      coordinate_click_used: false,
      blind_retry_used: false,
    };
  }
  const timeoutMs = Math.min(Math.max(Number(options.timeoutMs ?? 3_000), 500), 5_000);
  const settleMs = Math.min(Math.max(Number(options.settleMs ?? 450), 100), 2_000);
  const next = tab.playwright.locator(selector);
  const count = await next.count();
  if (count !== 1) {
    return {
      contract_id: XHS_CAROUSEL_INTERACTION_CONTRACT.contract_id,
      status: "blocked",
      reason: count === 0 ? "next_control_missing" : "next_control_not_unique",
      selector,
      matched_controls: count,
      coordinate_click_used: false,
      blind_retry_used: false,
    };
  }
  if (!(await next.isVisible())) {
    return {
      contract_id: XHS_CAROUSEL_INTERACTION_CONTRACT.contract_id,
      status: "blocked",
      reason: "next_control_not_visible",
      selector,
      matched_controls: count,
      coordinate_click_used: false,
      blind_retry_used: false,
    };
  }
  if (!(await next.isEnabled())) {
    return {
      contract_id: XHS_CAROUSEL_INTERACTION_CONTRACT.contract_id,
      status: "blocked",
      reason: "next_control_disabled_or_carousel_end",
      selector,
      matched_controls: count,
      coordinate_click_used: false,
      blind_retry_used: false,
    };
  }

  const before = await probe(tab);
  const clickResult = await attempt(() =>
    next.click({ force: true, timeoutMs }),
  );
  await waitForSettle(tab, settleMs);
  const afterClick = await probe(tab);
  if (afterClick.hash !== before.hash) {
    return {
      ...resultBase(before, selector),
      status: "advanced",
      method: "force_semantic_click",
      click_result: clickResult,
      advanced_despite_ambiguous_timeout: clickResult === "timeout",
      after_state_sha256: afterClick.hash,
      actions_attempted: 1,
    };
  }

  const keyboardResult = await attempt(() =>
    tab.playwright.locator("body").press("ArrowRight", { timeoutMs }),
  );
  await waitForSettle(tab, settleMs);
  const afterKeyboard = await probe(tab);
  if (afterKeyboard.hash !== before.hash) {
    return {
      ...resultBase(before, selector),
      status: "advanced",
      method: "keyboard_arrow_right",
      click_result: clickResult,
      keyboard_result: keyboardResult,
      advanced_despite_ambiguous_timeout: keyboardResult === "timeout",
      after_state_sha256: afterKeyboard.hash,
      actions_attempted: 2,
    };
  }

  return {
    ...resultBase(before, selector),
    status: "blocked",
    reason: "media_state_unchanged_after_bounded_semantic_actions",
    click_result: clickResult,
    keyboard_result: keyboardResult,
    after_state_sha256: afterKeyboard.hash,
    actions_attempted: 2,
  };
}
