import assert from "node:assert/strict";
import { createHash } from "node:crypto";

import {
  ARTICLE_STYLE_CONTRACT,
  LAUNCH_CONFIG,
  buildArticlePreflightQueue,
} from "./build_xhs_article_preflight_queue.mjs";


const SHA_A = "a".repeat(64);
const SHA_B = "b".repeat(64);
const SHA_C = "c".repeat(64);
const LONG_BRIEF =
  "这是一份完整的来源文章简报，说明目标读者正在面对的家具或空间决策、文章准备回答的具体问题、允许使用的事实、仍然未知的部分、禁止写出的结论、图片计划、利益关系以及希望保留的适用边界。所有判断都要回到当前来源包，不用点赞量代替证据。";
const LONG_BRIEF_SHA256 = createHash("sha256").update(LONG_BRIEF).digest("hex");


function evidencePack() {
  return [
    {
      evidence_type: "platform_reference",
      source_locator: "local://source/platform-reference",
      content_sha256: SHA_A,
      rights_basis: "authorized research use",
      body_nonempty: true,
      claim_usage: "验证用户问题和表达方式，不作为事实结论",
      captured_at: "2026-08-01T00:00:00.000Z",
    },
    {
      evidence_type: "primary_document",
      source_locator: "local://source/primary-document",
      content_sha256: SHA_B,
      rights_basis: "public primary source",
      body_nonempty: true,
      claim_usage: "支持材料、工艺、标准或设计事实",
      captured_at: "2026-08-01T00:00:00.000Z",
    },
    {
      evidence_type: "case_or_comparison",
      source_locator: "local://source/case",
      content_sha256: SHA_C,
      rights_basis: "authorized research use",
      body_nonempty: true,
      claim_usage: "支持场景比较和适用边界",
      captured_at: "2026-08-01T00:00:00.000Z",
    },
  ];
}


function baseCandidate(direction, accountId) {
  return {
    candidate_id: `candidate-${direction}`,
    direction,
    account_id: accountId,
    topic_hierarchy: {
      macro_theme: "真实取舍",
      subtopic_family: "家具选择中的空间与使用条件",
      article_seed: `${direction} 的首篇验证选题`,
    },
    sourced_article_brief: LONG_BRIEF,
    source_contract: {
      source_locator: `local://brief/${direction}`,
      brief_sha256: LONG_BRIEF_SHA256,
      owner_or_rights_holder: "Panse project research team",
      rights_basis: "project-owned synthesized research brief",
      allowed_operations: ["generate"],
      language: "zh-CN",
      sensitivity: "internal",
      review_due_at: "2026-09-01T00:00:00.000Z",
    },
    evidence_pack: evidencePack(),
    fact_contract: {
      protected_facts: [],
      allowed_paraphrases: {},
      forbidden_inferences: ["不得虚构亲历或第三方背书"],
      citation_anchors: {},
      must_cover_fact_ids: [],
    },
    identity: {
      brand_involvement: false,
      fake_consumer_identity: false,
      firsthand_claims_unverified: false,
    },
    visuals: [],
    platform_risk: {},
  };
}


const validCandidates = [
  {
    ...baseCandidate(
      "furniture_configuration_observation",
      "furniture_decision_editor",
    ),
    decision_context: { room: "12 平方米客厅", budget: "未定", use_condition: "日常阅读和待客" },
  },
  {
    ...baseCandidate("wait_before_buy", "furniture_decision_editor"),
    decision_alternatives: ["delay_purchase", "no_purchase"],
  },
  {
    ...baseCandidate(
      "global_furniture_observation",
      "global_furniture_editor",
    ),
    claim_scope_refs: [
      { market: "日本住宅家具市场", year: "2025" },
      { brand: "example research case" },
    ],
  },
  {
    ...baseCandidate("image_mix_home", "mix_home_editor"),
    visuals: [
      {
        rights_status: "owned",
        synthetic: true,
        disclosure: "空间提案 / 场景合成",
        product_fidelity_reviewed: true,
      },
    ],
  },
  {
    ...baseCandidate("space_diagnosis", "space_clinic"),
    space_diagnosis: {
      dimensions: "客厅 3.2 米 × 4.1 米",
      circulation_constraints: "入口到阳台需要保留主通道",
      household_needs: "两人居住，偶尔四人用餐",
    },
  },
];


const queue = buildArticlePreflightQueue(
  { candidates: validCandidates },
  "2026-08-01T00:00:00.000Z",
);
assert.equal(queue.summary.input_candidates, 5);
assert.equal(queue.summary.preconditions_ready, 5);
assert.equal(queue.summary.ready_but_generation_disabled_during_warmup, 0);
assert.equal(queue.summary.awaiting_style_lab_generation, 5);
assert.equal(queue.summary.rejected_by_precondition, 0);
assert.equal(queue.text_generated, false);
assert.equal(queue.publish_allowed, false);
assert.ok(queue.records.every((record) => record.preconditions_ready));
assert.ok(
  queue.records.every(
    (record) =>
      record.style_generation.required_model_id === "gpt-5.6-sol" &&
      record.style_generation.fallback_model_allowed === false &&
      record.style_generation.generation_enabled === true &&
      record.eligible_for_style_generation === true &&
      record.publish_allowed === false,
  ),
);
assert.deepEqual(
  new Set(queue.records.map((record) => record.direction)),
  new Set(ARTICLE_STYLE_CONTRACT.direction_profiles.map((item) => item.direction)),
);


const invalidEvidence = structuredClone(validCandidates[0]);
invalidEvidence.candidate_id = "invalid-evidence";
invalidEvidence.evidence_pack = invalidEvidence.evidence_pack.slice(0, 2);
const invalidEvidenceQueue = buildArticlePreflightQueue([invalidEvidence]);
assert.equal(invalidEvidenceQueue.summary.rejected_by_precondition, 1);
assert.ok(
  invalidEvidenceQueue.records[0].failed_gates.includes("多类型来源包门"),
);


const wrongAccount = structuredClone(validCandidates[0]);
wrongAccount.candidate_id = "wrong-account";
wrongAccount.account_id = "mix_home_editor";
const wrongAccountQueue = buildArticlePreflightQueue([wrongAccount]);
assert.ok(wrongAccountQueue.records[0].failed_gates.includes("方向与账号门"));


const undisclosedMix = structuredClone(validCandidates[3]);
undisclosedMix.candidate_id = "undisclosed-mix";
undisclosedMix.visuals[0].disclosure = "";
const undisclosedMixQueue = buildArticlePreflightQueue([undisclosedMix]);
assert.ok(
  undisclosedMixQueue.records[0].failed_gates.includes("视觉授权与披露门"),
);
assert.ok(
  undisclosedMixQueue.records[0].failed_gates.includes("场景合成专属门"),
);


const broadGlobal = structuredClone(validCandidates[2]);
broadGlobal.candidate_id = "broad-global";
broadGlobal.claim_scope_refs = [{ conclusion: "国外家具都更好" }];
const broadGlobalQueue = buildArticlePreflightQueue([broadGlobal]);
assert.ok(
  broadGlobalQueue.records[0].failed_gates.includes("海外主张范围门"),
);


const riskyPlatform = structuredClone(validCandidates[4]);
riskyPlatform.candidate_id = "platform-warning";
riskyPlatform.platform_risk.frequency_warning = true;
const riskyPlatformQueue = buildArticlePreflightQueue([riskyPlatform]);
assert.ok(riskyPlatformQueue.records[0].failed_gates.includes("平台风险门"));


const changedBrief = structuredClone(validCandidates[0]);
changedBrief.sourced_article_brief += "补充一个新条件。";
const originalFingerprint = queue.records[0].article_input_sha256;
const changedFingerprint = buildArticlePreflightQueue([changedBrief]).records[0]
  .article_input_sha256;
assert.notEqual(originalFingerprint, changedFingerprint);
assert.ok(
  buildArticlePreflightQueue([changedBrief]).records[0].failed_gates.includes(
    "来源授权门",
  ),
);


const originalContractGeneration =
  ARTICLE_STYLE_CONTRACT.launch_policy.article_generation_enabled;
const originalContractWrite = ARTICLE_STYLE_CONTRACT.launch_policy.write_allowed;
const originalLaunchGeneration =
  LAUNCH_CONFIG.writing_runtime.article_generation_enabled;
ARTICLE_STYLE_CONTRACT.launch_policy.article_generation_enabled = false;
ARTICLE_STYLE_CONTRACT.launch_policy.write_allowed = false;
LAUNCH_CONFIG.writing_runtime.article_generation_enabled = false;
try {
  const disabledQueue = buildArticlePreflightQueue([validCandidates[0]]);
  assert.equal(disabledQueue.summary.ready_but_generation_disabled_during_warmup, 1);
  assert.equal(disabledQueue.records[0].eligible_for_style_generation, false);
  assert.equal(disabledQueue.records[0].publish_allowed, false);
} finally {
  ARTICLE_STYLE_CONTRACT.launch_policy.article_generation_enabled =
    originalContractGeneration;
  ARTICLE_STYLE_CONTRACT.launch_policy.write_allowed = originalContractWrite;
  LAUNCH_CONFIG.writing_runtime.article_generation_enabled =
    originalLaunchGeneration;
}


process.stdout.write(
  `${JSON.stringify(
    {
      passed: true,
      tests: 32,
      summary: queue.summary,
    },
    null,
    2,
  )}\n`,
);
