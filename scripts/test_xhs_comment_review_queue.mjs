import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { COMMENT_MODES, buildReviewQueue } from "./build_xhs_comment_review_queue.mjs";

const fixturePath = path.resolve(
  "research",
  "panse_multi_direction",
  "comment_system_v1",
  "synthetic_candidates.json",
);

const fixture = JSON.parse(fs.readFileSync(fixturePath, "utf8"));
const preparedFixture = structuredClone(fixture);
for (const candidate of preparedFixture.candidates.slice(0, 11)) {
  candidate.proposed.interaction_intent = "peer_tip_invited";
  candidate.proposed.comment_direction_id = "invited_peer_tip";
  candidate.proposed.topic_ids = ["household_constraints"];
  candidate.proposed.topic_alignment_verified = true;
  candidate.proposed.source_context_complete = true;
}
const safeCollab = preparedFixture.candidates.find(
  (candidate) => candidate.candidate_id === "safe-collab",
);
safeCollab.proposed.official_reply_context = {
  policy_id: "panse-official-reply.v3",
  interaction_type: "reply_to_user",
  route_id: "product_fact_answer",
  visible_comment_context_read: true,
  facts_verified: true,
  cta_count: 0,
};
const safeBrandSearch = preparedFixture.candidates.find(
  (candidate) => candidate.candidate_id === "safe-brand-search",
);
safeBrandSearch.proposed.draft =
  "这是我们参与设计和制作的产品，小红书站内搜“畔色木作 + 产品名”就能找到。";
safeBrandSearch.proposed.official_reply_context = {
  policy_id: "panse-official-reply.v3",
  interaction_type: "reply_to_user",
  route_id: "purchase_channel_answer",
  visible_comment_context_read: true,
  facts_verified: true,
  third_party_target: true,
  affiliation_disclosure_present: true,
  cta_count: 1,
};
const queue = buildReviewQueue(preparedFixture, "2026-07-31T00:00:00.000Z");

assert.equal(queue.summary.input_candidates, 17);
assert.equal(queue.summary.unique_candidates, 17);
assert.equal(queue.summary.duplicates_removed, 0);
assert.equal(queue.summary.awaiting_style_generation, 11);
assert.equal(queue.summary.awaiting_human_review, 0);
assert.equal(queue.summary.rejected_by_gate, 6);
assert.deepEqual(
  [...queue.summary.modes_present].sort(),
  [...COMMENT_MODES].sort(),
);
assert.deepEqual(
  queue.records
    .filter((record) => record.eligible_for_style_generation)
    .map((record) => record.selected_mode)
    .sort(),
  [...COMMENT_MODES].sort(),
);
assert.equal(queue.publish_allowed, false);
assert.equal(queue.external_posting_enabled, false);
assert.equal(queue.network_access_performed, false);
assert.ok(queue.records.every((record) => record.publish_allowed === false));
assert.ok(
  queue.records
    .filter((record) => record.eligible_for_style_generation)
    .every((record) => record.human_review_required === true),
);
assert.ok(
  queue.records
    .filter((record) => record.eligible_for_style_generation)
    .every(
      (record) =>
        record.style_generation.required === true &&
        record.style_generation.required_model_id === "gpt-5.6-sol" &&
        record.style_generation.fallback_model_allowed === false &&
        record.style_generation.receipt_valid === false &&
        record.draft_status === "candidate_only_not_style_approved",
    ),
);

const rejectedById = Object.fromEntries(
  queue.records
    .filter((record) => !record.eligible_for_human_review)
    .map((record) => [record.candidate_id, record]),
);

assert.ok(
  rejectedById["reject-poaching"].failed_gates.includes("商业关系门"),
);
assert.ok(rejectedById["reject-offsite"].failed_gates.includes("平台门"));
assert.ok(
  rejectedById["reject-fake-experience"].failed_gates.includes("身份门"),
);
assert.ok(
  rejectedById["reject-unlabeled-mix"].failed_gates.includes("图片门"),
);
assert.ok(
  rejectedById["reject-unsupported-claim"].failed_gates.includes("证据门"),
);
assert.ok(
  rejectedById["reject-manipulative-debate"].failed_gates.includes(
    "争点门",
  ),
);
const safeDebate = queue.records.find(
  (record) => record.candidate_id === "safe-constructive-debate",
);
assert.equal(safeDebate.selected_mode, "建设性争点");
assert.equal(safeDebate.voice_route.account_id, "space_clinic");
assert.ok(safeDebate.human_review_reasons.includes("建设性争点与回复边界"));
assert.ok(
  queue.records.every(
    (record) =>
      Boolean(record.voice_route.voice_id) &&
      Boolean(record.voice_route.account_id),
  ),
);

const duplicateQueue = buildReviewQueue(
  {
    candidates: [preparedFixture.candidates[0], preparedFixture.candidates[0]],
  },
  "2026-07-31T00:00:00.000Z",
);
assert.equal(duplicateQueue.summary.input_candidates, 2);
assert.equal(duplicateQueue.summary.unique_candidates, 1);
assert.equal(duplicateQueue.summary.duplicates_removed, 1);

const baseStyledCandidate = structuredClone(preparedFixture.candidates[0]);
baseStyledCandidate.proposed.voice_id = "space_advisor";
baseStyledCandidate.proposed.account_id = "space_clinic";
baseStyledCandidate.proposed.interaction_intent = "peer_tip_invited";
const preStyleQueue = buildReviewQueue(
  { candidates: [baseStyledCandidate] },
  "2026-08-01T00:00:00.000Z",
);
const styleRoute = preStyleQueue.records[0].style_generation;
const syntheticBundleSha256 = "1".repeat(64);
baseStyledCandidate.proposed.style_lab_receipt = {
  contract_version: 2,
  intent_policy_version: "xhs-comment-intent.v4",
  interaction_intent: "peer_tip_invited",
  comment_direction_id: "invited_peer_tip",
  topic_ids: ["household_constraints"],
  voice_style_id: "everyday_space_questioner",
  interaction_mode: "soft_observation",
  candidate_id: baseStyledCandidate.candidate_id,
  candidate_input_sha256: styleRoute.candidate_input_sha256,
  style_profile_sha256: styleRoute.style_profile_sha256,
  catalog_version: styleRoute.style_lab_catalog_version,
  catalog_sha256: styleRoute.style_lab_catalog_sha256,
  approved_card_refs: styleRoute.approved_card_refs,
  taxonomy_ids: styleRoute.taxonomy_ids,
  requested_strength: styleRoute.requested_strength,
  bundle_id: `stylebundle_${syntheticBundleSha256.slice(0, 24)}`,
  bundle_sha256: syntheticBundleSha256,
  provider: "codex",
  model_id: "gpt-5.6-sol",
  model_verified: true,
  prompt_versions: {
    plan: "style-plan-v1",
    draft: "style-draft-v1",
    semantic_review: "style-semantic-review-v1",
  },
  observed_at: "2026-08-01T00:00:00.000Z",
  gate_tuple: [
    { name: "permission/source_rights", hard: true, status: "pass" },
    { name: "protected_fact_precision", hard: true, status: "pass" },
    { name: "protected_fact_recall", hard: true, status: "pass" },
    { name: "unsupported_claims", hard: true, status: "pass" },
    { name: "citation_coverage", hard: true, status: "pass" },
    { name: "near_copy", hard: true, status: "pass" },
  ],
  naturalness_status: "pass",
  delivery_ready_for_human_review: true,
  human_review_required: true,
  publish_allowed: false,
};
const styledQueue = buildReviewQueue(
  { candidates: [baseStyledCandidate] },
  "2026-08-01T00:00:00.000Z",
);
assert.equal(styledQueue.summary.awaiting_style_generation, 0);
assert.equal(styledQueue.summary.awaiting_human_review, 1);
assert.equal(styledQueue.records[0].style_generation.receipt_valid, true);
assert.equal(styledQueue.records[0].eligible_for_human_review, true);
assert.equal(styledQueue.records[0].publish_allowed, false);

const wrongModelCandidate = structuredClone(baseStyledCandidate);
wrongModelCandidate.proposed.style_lab_receipt.model_id = "gpt-5.6-terra";
const wrongModelQueue = buildReviewQueue(
  { candidates: [wrongModelCandidate] },
  "2026-08-01T00:00:00.000Z",
);
assert.equal(wrongModelQueue.summary.awaiting_style_generation, 1);
assert.equal(wrongModelQueue.summary.awaiting_human_review, 0);
assert.ok(
  wrongModelQueue.records[0].style_generation.receipt_failures.includes(
    "生成模型不是固定的 gpt-5.6-sol",
  ),
);

const changedAfterStyleCandidate = structuredClone(baseStyledCandidate);
changedAfterStyleCandidate.proposed.draft += " 又改了一句。";
const changedAfterStyleQueue = buildReviewQueue(
  { candidates: [changedAfterStyleCandidate] },
  "2026-08-01T00:00:00.000Z",
);
assert.equal(changedAfterStyleQueue.summary.awaiting_style_generation, 1);
assert.equal(changedAfterStyleQueue.summary.awaiting_human_review, 0);
assert.ok(
  changedAfterStyleQueue.records[0].style_generation.receipt_failures.includes(
    "候选内容已变化，风格回执需要重新生成",
  ),
);

const incompleteHardGatesCandidate = structuredClone(baseStyledCandidate);
incompleteHardGatesCandidate.proposed.style_lab_receipt.gate_tuple =
  incompleteHardGatesCandidate.proposed.style_lab_receipt.gate_tuple.filter(
    (item) => item.name !== "near_copy",
  );
const incompleteHardGatesQueue = buildReviewQueue(
  { candidates: [incompleteHardGatesCandidate] },
  "2026-08-01T00:00:00.000Z",
);
assert.equal(incompleteHardGatesQueue.summary.awaiting_style_generation, 1);
assert.equal(incompleteHardGatesQueue.summary.awaiting_human_review, 0);
assert.ok(
  incompleteHardGatesQueue.records[0].style_generation.receipt_failures.includes(
    "确定性硬门尚未全部通过",
  ),
);

process.stdout.write(
  `${JSON.stringify(
    {
      passed: true,
      tests: 45,
      summary: queue.summary,
    },
    null,
    2,
  )}\n`,
);
