import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));

export const DEFAULT_OFFICIAL_TOPIC_STRATEGY_PATH = path.resolve(
  MODULE_DIR,
  "..",
  "..",
  "research",
  "panse_multi_direction",
  "official_reply_research_v1",
  "panse_official_topic_strategy_v1.json",
);

export const OFFICIAL_TOPIC_STRATEGY_ID = "panse-official-topic-strategy.v1";

const TOPIC_SIGNALS = [
  ["ai_render_design_process", /\bAI\b|建模|渲染|效果图|实物对比|设计过程|模型|生成图/iu],
  ["maintenance_longevity", /保养|维修|发霉|开裂|清洁|长期使用|耐用|修复|划痕|补漆|老化/u],
  ["craft_material_process", /工坊|制作|木材|木种|结构|工艺|打磨|榫卯|材料|拆解|实验|检测|承重/u],
  ["real_space_use", /户型|小户型|空间|动线|收纳|家里|客厅|卧室|餐厅|入住|尺寸|通道|采光|光线|窗帘|摆放/u],
  ["design_culture_exhibition", /设计展|米兰|Arper|Artek|国外|海外|家具史|设计师|展览|博物馆/iu],
  ["creator_ugc_aesthetic", /买家秀|晒家|改造|搭配|配色|照片|创作者|真实小屋|家居博主|工作室/u],
];

const ALLOWED_OUTBOUND_RIGHTS = new Set([
  "peer_observation",
  "specific_creator_support",
  "process_peer_observation",
  "conditional_fact_only",
  "specific_design_observation",
  "owned_factual_answer",
  "service_responsibility",
  "partner_peer",
]);

function normalize(value = "") {
  return String(value).normalize("NFKC").replace(/\s+/gu, " ").trim();
}

export function loadOfficialTopicStrategy(
  strategyPath = DEFAULT_OFFICIAL_TOPIC_STRATEGY_PATH,
) {
  const strategy = JSON.parse(fs.readFileSync(strategyPath, "utf8"));
  if (strategy.strategy_id !== OFFICIAL_TOPIC_STRATEGY_ID) {
    throw new Error(
      `Expected ${OFFICIAL_TOPIC_STRATEGY_ID}, received ${strategy.strategy_id}`,
    );
  }
  return strategy;
}

export function classifyOfficialTopic(input = {}) {
  const declared = normalize(input.topic_id);
  if (declared) return declared;

  const relationship = normalize(input.target_relationship);
  const text = normalize(
    [input.post_context, input.user_text, input.visible_comments_summary]
      .filter(Boolean)
      .join(" "),
  );

  if (
    input.mentions_panse === true ||
    input.direct_panse_question === true ||
    ["own_post", "panse_mention", "panse_ugc"].includes(relationship) ||
    /畔色/u.test(text)
  ) {
    return "explicit_panse_product_service";
  }
  for (const [topicId, pattern] of TOPIC_SIGNALS) {
    if (pattern.test(text)) return topicId;
  }
  return "unclassified_or_unrelated";
}

function routeHint(topicId, input) {
  if (topicId === "real_space_use") return "lifestyle_resonance";
  if (topicId === "maintenance_longevity") {
    const adviceContextAllowed =
      input.advice_invited === true ||
      ["author_asked", "visible_problem_present", "direct_service_question"].includes(
        normalize(input.advice_context_status),
      );
    const factBoundaryAllowed =
      input.facts_verified === true ||
      (normalize(input.fact_source_status) === "conditional_no_external_claim" &&
        input.conditional_language_present === true);
    return adviceContextAllowed && factBoundaryAllowed
      ? "usage_fit_answer"
      : "creator_specific_praise";
  }
  if (
    [
      "craft_material_process",
      "ai_render_design_process",
      "creator_ugc_aesthetic",
      "design_culture_exhibition",
    ].includes(topicId)
  ) {
    return "creator_specific_praise";
  }
  return null;
}

export function evaluateOfficialTopicStrategy(
  input = {},
  strategy = loadOfficialTopicStrategy(),
) {
  const interactionType = normalize(input.interaction_type);
  const topicId = classifyOfficialTopic(input);
  const relationship = normalize(input.target_relationship);
  const replyRight = normalize(input.panse_reply_right);
  const reasons = [];

  if (!strategy.interaction_boundaries?.[interactionType]) {
    reasons.push("未声明有效的官方互动类型");
  }

  if (interactionType === "outbound_comment") {
    if (input.visible_detail_grounded !== true) {
      reasons.push("官方主动评论缺少原帖可见细节落点");
    }
    if (input.visible_comment_context_read !== true) {
      reasons.push("官方主动评论尚未读取当前可见评论上下文");
    }
    if (input.question_answered_in_context === true) {
      reasons.push("拟提问题已被正文或可见评论回答");
    }
    if (!replyRight || !ALLOWED_OUTBOUND_RIGHTS.has(replyRight)) {
      reasons.push("没有声明有效的畔色官方发言权");
    }
    if (
      relationship === "competitor_commercial" &&
      (input.third_party_purchase_question === true ||
        input.complaint_about_other_brand === true)
    ) {
      reasons.push("竞品购买或投诉话题不用于畔色主动截流");
    }
    if (input.complaint_about_other_brand === true) {
      reasons.push("不利用其他品牌的投诉获取曝光");
    }
    if (input.third_party_purchase_question === true) {
      reasons.push("其他品牌的购买渠道问题不属于畔色官方回答范围");
    }
    if (
      topicId === "maintenance_longevity" &&
      replyRight === "conditional_fact_only" &&
      input.facts_verified !== true &&
      !(
        normalize(input.fact_source_status) === "conditional_no_external_claim" &&
        input.conditional_language_present === true &&
        ["author_asked", "visible_problem_present", "direct_service_question"].includes(
          normalize(input.advice_context_status),
        )
      )
    ) {
      reasons.push("维护或质量事实尚未核验，不能以官方身份作答");
    }
    if (topicId === "unclassified_or_unrelated") {
      reasons.push("话题与畔色已批准的家具、空间或设计主题不匹配");
    }
  }

  if (interactionType === "reply_to_brand" && input.collaboration_verified !== true) {
    reasons.push("品牌间互动缺少真实合作或自然关系依据");
  }

  if (
    interactionType === "reply_to_user" &&
    ["third_party_creator", "competitor_commercial"].includes(relationship) &&
    input.direct_panse_question !== true &&
    input.mentions_panse !== true
  ) {
    reasons.push("第三方讨论未直接询问畔色，官方没有被动答复权");
  }

  const allowed = reasons.length === 0;
  return {
    passed: allowed,
    strategy_id: strategy.strategy_id,
    interaction_type: interactionType,
    topic_id: topicId,
    target_relationship: relationship || null,
    panse_reply_right: replyRight || null,
    route_hint: allowed ? routeHint(topicId, input) : "no_reply",
    should_reply: allowed,
    reasons,
    content_followup_signal: normalize(input.content_followup_signal) || null,
  };
}
