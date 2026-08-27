import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { validateOfficialReply } from "./lib/xhs_official_reply_policy.mjs";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(scriptDir, "..");
const runDir = path.join(
  repo,
  "research",
  "panse_multi_direction",
  "daily_runs",
  "2026-08-10",
);
const queue = JSON.parse(
  fs.readFileSync(path.join(runDir, "account_1_human_review_4.json"), "utf8"),
);
const requests = JSON.parse(
  fs.readFileSync(path.join(runDir, "account_1_style_requests_4.json"), "utf8"),
);

function camelProfessionalValue(context) {
  return {
    contractId: context.contract_id,
    valueMode: context.value_mode,
    professionalBasisType: context.professional_basis_type,
    professionalBasisText: context.professional_basis_text,
    usefulTakeawayPresent: context.useful_takeaway_present,
    factSourceStatus: context.fact_source_status,
    praiseReasonPrecedesPraise: context.praise_reason_precedes_praise,
    adviceContextStatus: context.advice_context_status,
    conditionalLanguagePresent: context.conditional_language_present,
  };
}

assert.equal(queue.items.length, 4);
for (const item of queue.items) {
  const request = requests.requests.find(
    (candidate) => candidate.style_request.request_id === item.request_id,
  );
  assert.ok(request, `missing style request for ${item.request_id}`);
  const payload = request.style_request;
  const topicContext = payload.panse_official_topic_context;
  const professionalContext = payload.panse_official_professional_value_context;
  const result = validateOfficialReply({
    draft: item.draft,
    routeId: item.route_id,
    interactionType: "outbound_comment",
    sourceContextComplete: true,
    visibleCommentContextRead: true,
    visibleDetailGrounded: true,
    factsVerified: item.route_id === "usage_fit_answer",
    topicStrategyContext: topicContext,
    professionalValueContext: camelProfessionalValue(professionalContext),
  });
  assert.equal(result.passed, true, `${item.request_id}: ${result.reasons.join("; ")}`);
}

const missingReason = validateOfficialReply({
  draft: "沙发这张太舒服了，审美真好👍",
  routeId: "creator_specific_praise",
  interactionType: "outbound_comment",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  visibleDetailGrounded: true,
  topicStrategyContext: {
    topic_id: "creator_ugc_aesthetic",
    target_relationship: "third_party_creator",
    panse_reply_right: "specific_creator_support",
    visible_detail_grounded: true,
    visible_comment_context_read: true,
    question_answered_in_context: false,
  },
});
assert.equal(missingReason.passed, false);
assert.ok(missingReason.reasons.includes("官方主动评论缺少专业价值前置上下文"));

process.stdout.write(
  `${JSON.stringify({ passed: true, queue_items: 4, negative_cases: 1 }, null, 2)}\n`,
);
