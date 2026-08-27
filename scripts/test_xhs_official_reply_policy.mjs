import assert from "node:assert/strict";
import {
  classifyOfficialReplyRoute,
  loadOfficialProfessionalValueContract,
  loadOfficialReplyPolicy,
  validateOfficialReply,
  validateOfficialProfessionalValueContext,
} from "./lib/xhs_official_reply_policy.mjs";
import {
  evaluateOfficialTopicStrategy,
  loadOfficialTopicStrategy,
} from "./lib/xhs_official_topic_strategy.mjs";
import { planOfficialReply } from "./plan_xhs_official_reply.mjs";

const policy = loadOfficialReplyPolicy();
const topicStrategy = loadOfficialTopicStrategy();
const professionalValueContract = loadOfficialProfessionalValueContract();
assert.equal(policy.policy_id, "panse-official-reply.v3");
assert.equal(topicStrategy.strategy_id, "panse-official-topic-strategy.v1");
assert.equal(Object.keys(policy.routes).length, 18);
assert.equal(Object.keys(policy.families).length, 7);
assert.equal(policy.provider_contract.required_model_id, "gpt-5.6-sol");
assert.equal(policy.provider_contract.fallback_model_allowed, false);
assert.equal(policy.provider_contract.publish_allowed, false);
assert.equal(
  professionalValueContract.contract_id,
  "panse-official-professional-value.v1",
);

const reasonedPraiseContext = {
  contractId: "panse-official-professional-value.v1",
  valueMode: "professional_reasoned_praise",
  professionalBasisType: "visible_structure_or_process",
  professionalBasisText: "拆解图可见连接件和受力关系",
  usefulTakeawayPresent: true,
  factSourceStatus: "source_visible",
  praiseReasonPrecedesPraise: true,
};

assert.equal(
  classifyOfficialReplyRoute({
    interaction_type: "reply_to_user",
    user_text: "这款餐桌哪里买呀？",
  }).route_id,
  "purchase_channel_answer",
);
assert.equal(
  classifyOfficialReplyRoute({
    interaction_type: "reply_to_user",
    user_text: "延期两个月还没人处理",
  }).route_id,
  "complaint_acknowledgement",
);
assert.equal(
  classifyOfficialReplyRoute({
    interaction_type: "reply_to_user",
    user_text: "这款有没有甲醛检测？",
  }).route_id,
  "quality_safety_clarification",
);
assert.equal(
  classifyOfficialReplyRoute({
    interaction_type: "outbound_comment",
    post_context: "这张图在讨论家具甲醛检测争议",
    visible_detail_grounded: true,
  }).route_id,
  "quality_safety_clarification",
);
assert.equal(
  classifyOfficialReplyRoute({
    interaction_type: "reply_to_brand",
    post_context: "联合发布",
  }).route_id,
  "brand_peer_response",
);
assert.equal(
  classifyOfficialReplyRoute({
    interaction_type: "reply_to_user",
    platform_safe: false,
    no_reply_reason: "出现安全验证",
  }).route_id,
  "no_reply",
);

const micro = validateOfficialReply({
  draft: "谢谢喜欢😊",
  routeId: "micro_acknowledgement",
  interactionType: "reply_to_user",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  policy,
});
assert.equal(micro.passed, true);

const creatorPraise = validateOfficialReply({
  draft: "连接件和受力关系都画出来了，这张拆解图确实专业。",
  routeId: "creator_specific_praise",
  interactionType: "outbound_comment",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  visibleDetailGrounded: true,
  topicStrategyContext: {
    topic_id: "craft_material_process",
    target_relationship: "third_party_creator",
    panse_reply_right: "specific_creator_support",
    visible_detail_grounded: true,
    visible_comment_context_read: true,
    question_answered_in_context: false,
  },
  professionalValueContext: reasonedPraiseContext,
  policy,
});
assert.equal(creatorPraise.passed, true);

const purchase = validateOfficialReply({
  draft: "目前在小红书店铺可以买到，搜“畔色木作”就能找到。",
  routeId: "purchase_channel_answer",
  interactionType: "reply_to_user",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  factsVerified: true,
  ctaCount: 1,
  policy,
});
assert.equal(purchase.passed, true);

const complaint = validateOfficialReply({
  draft:
    "看到你说餐桌延期两周还没发出，抱歉。我们现在核对订单进度，麻烦私信订单号，售后同事会继续跟进。",
  routeId: "complaint_acknowledgement",
  interactionType: "reply_to_user",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  issueSpecificityPresent: true,
  nextActionPresent: true,
  ctaCount: 1,
  policy,
});
assert.equal(complaint.passed, true);

const noReply = validateOfficialReply({
  draft: "",
  routeId: "no_reply",
  interactionType: "reply_to_user",
  noReplyReason: "出现安全验证",
  platformSafe: false,
  policy,
});
assert.equal(noReply.passed, true);

const teacher = validateOfficialReply({
  draft: "真正关键的是通道尺寸，你应该先量完再发。",
  routeId: "usage_fit_answer",
  interactionType: "outbound_comment",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  factsVerified: true,
  policy,
});
assert.equal(teacher.passed, false);
assert.ok(teacher.reasons.includes("出现老师或评委式口吻"));

const emptyEnding = validateOfficialReply({
  draft: "工坊里大家围着椅子看结构那张很喜欢。很值得参考。",
  routeId: "creator_specific_praise",
  interactionType: "outbound_comment",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  visibleDetailGrounded: true,
  topicStrategyContext: {
    topic_id: "craft_material_process",
    target_relationship: "third_party_creator",
    panse_reply_right: "specific_creator_support",
    visible_detail_grounded: true,
    visible_comment_context_read: true,
    question_answered_in_context: false,
  },
  professionalValueContext: reasonedPraiseContext,
  policy,
});
assert.equal(emptyEnding.passed, false);
assert.ok(emptyEnding.reasons.includes("结尾是可以直接删除的空洞第二句"));

const publicPrivacy = validateOfficialReply({
  draft: "麻烦在评论区留下完整手机号和订单号，我们安排处理。",
  routeId: "complaint_acknowledgement",
  interactionType: "reply_to_user",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  issueSpecificityPresent: true,
  nextActionPresent: true,
  policy,
});
assert.equal(publicPrivacy.passed, false);
assert.ok(publicPrivacy.reasons.includes("要求用户在公开评论区提供隐私信息"));

const wrongPriority = validateOfficialReply({
  draft: "谢谢关注。",
  routeId: "micro_acknowledgement",
  interactionType: "reply_to_user",
  sourceContextComplete: true,
  visibleCommentContextRead: true,
  classifiedInput: {
    interaction_type: "reply_to_user",
    user_text: "餐桌延期两个月还没有发货",
  },
  policy,
});
assert.equal(wrongPriority.passed, false);
assert.ok(
  wrongPriority.reasons.includes(
    "高优先级场景应先走complaint_acknowledgement",
  ),
);

const unauthorizedSelfComment = validateOfficialReply({
  draft: "获奖名单见正文，请在五个工作日内私信收货信息。",
  routeId: "campaign_fulfillment_notice",
  interactionType: "brand_self_comment",
  sourceContextComplete: true,
  campaignFactsVerified: true,
  fulfillmentActionPresent: true,
  ctaCount: 1,
  policy,
});
assert.equal(unauthorizedSelfComment.passed, false);
assert.ok(unauthorizedSelfComment.reasons.includes("官方自评或置顶评论缺少当前任务授权"));

const planned = planOfficialReply({
  interaction_type: "outbound_comment",
  post_context: "工坊里围着椅子看结构的制作过程",
  visible_detail_grounded: true,
  visible_comment_context_read: true,
  target_relationship: "third_party_creator",
  panse_reply_right: "specific_creator_support",
  question_answered_in_context: false,
  protected_facts: ["椅子结构"],
});
assert.equal(planned.route_id, "creator_specific_praise");
assert.equal(planned.style_mode, "warm_specific");
assert.equal(planned.provider_contract.required_model_id, "gpt-5.6-sol");
assert.equal(planned.publish_allowed, false);

const competitorPurchase = evaluateOfficialTopicStrategy({
  interaction_type: "outbound_comment",
  topic_id: "explicit_panse_product_service",
  target_relationship: "competitor_commercial",
  panse_reply_right: "peer_observation",
  visible_detail_grounded: true,
  visible_comment_context_read: true,
  third_party_purchase_question: true,
});
assert.equal(competitorPurchase.passed, false);
assert.ok(
  competitorPurchase.reasons.includes(
    "其他品牌的购买渠道问题不属于畔色官方回答范围",
  ),
);

const exhibitionObservation = evaluateOfficialTopicStrategy({
  interaction_type: "outbound_comment",
  topic_id: "design_culture_exhibition",
  target_relationship: "third_party_creator",
  panse_reply_right: "specific_design_observation",
  visible_detail_grounded: true,
  visible_comment_context_read: true,
  question_answered_in_context: false,
});
assert.equal(exhibitionObservation.passed, true);
assert.equal(exhibitionObservation.route_hint, "creator_specific_praise");

const unverifiedMaintenance = evaluateOfficialTopicStrategy({
  interaction_type: "outbound_comment",
  topic_id: "maintenance_longevity",
  target_relationship: "third_party_creator",
  panse_reply_right: "conditional_fact_only",
  visible_detail_grounded: true,
  visible_comment_context_read: true,
  facts_verified: false,
});
assert.equal(unverifiedMaintenance.passed, false);

const genericOutbound = validateOfficialReply({
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
  policy,
});
assert.equal(genericOutbound.passed, false);
assert.ok(genericOutbound.reasons.includes("官方主动评论缺少专业价值前置上下文"));

const safeAdviceContext = {
  contractId: "panse-official-professional-value.v1",
  valueMode: "conditional_practical_advice",
  professionalBasisType: "conditional_domain_practice",
  professionalBasisText: "作者展示局部维修后仍有明显色差",
  usefulTakeawayPresent: true,
  factSourceStatus: "conditional_no_external_claim",
  adviceContextStatus: "visible_problem_present",
  conditionalLanguagePresent: true,
};
assert.equal(
  validateOfficialProfessionalValueContext(safeAdviceContext).passed,
  true,
);
const hardAdviceContext = {
  ...safeAdviceContext,
  conditionalLanguagePresent: false,
};
const hardAdvice = validateOfficialProfessionalValueContext(hardAdviceContext);
assert.equal(hardAdvice.passed, false);
assert.ok(hardAdvice.reasons.includes("未经核实的实用建议没有使用条件化表达"));

const competitorPlan = planOfficialReply({
  interaction_type: "outbound_comment",
  topic_id: "explicit_panse_product_service",
  target_relationship: "competitor_commercial",
  panse_reply_right: "peer_observation",
  visible_detail_grounded: true,
  visible_comment_context_read: true,
  third_party_purchase_question: true,
});
assert.equal(competitorPlan.route_id, "no_reply");
assert.equal(competitorPlan.should_reply, false);

process.stdout.write(`${JSON.stringify({ passed: true, tests: 41 }, null, 2)}\n`);
