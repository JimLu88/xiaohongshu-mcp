import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  evaluateOfficialTopicStrategy,
  loadOfficialTopicStrategy,
} from "./xhs_official_topic_strategy.mjs";

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));

export const DEFAULT_OFFICIAL_REPLY_POLICY_PATH = path.resolve(
  MODULE_DIR,
  "..",
  "..",
  "research",
  "panse_multi_direction",
  "official_reply_research_v1",
  "panse_official_reply_policy_v3.json",
);

export const DEFAULT_OFFICIAL_PROFESSIONAL_VALUE_PATH = path.resolve(
  MODULE_DIR,
  "..",
  "..",
  "research",
  "panse_multi_direction",
  "official_reply_research_v1",
  "panse_official_professional_value_v1.json",
);

export const OFFICIAL_REPLY_POLICY_ID = "panse-official-reply.v3";
export const OFFICIAL_PROFESSIONAL_VALUE_ID = "panse-official-professional-value.v1";

const ROUTE_SIGNALS = [
  ["quality_safety_clarification", /安全|甲醛|承重|断裂|开裂|有毒|检测|质量问题|质量不行/u],
  ["misinformation_correction", /说错|误传|不是.{0,8}(这个|这款|这个版本)|假消息|辟谣|更正/u],
  ["complaint_acknowledgement", /投诉|欺骗|破损|色差|异味|延期|不发货|没发货|联系不上|没人管|维权|漏发|错发/u],
  ["service_progress_update", /已经受理|正在核实|处理进度|退款进度|补件|已安排|专人跟进/u],
  ["campaign_fulfillment_notice", /获奖|开奖|中奖|领奖|补地址|收货信息|奖品|发奖/u],
  ["campaign_participation_answer", /怎么参加|参与条件|活动入口|截止时间|还能参加|资格/u],
  ["purchase_channel_answer", /哪里买|怎么买|购买链接|购买入口|哪家店|门店|线上能买|什么型号/u],
  ["price_stock_answer", /多少钱|价格|有货|库存|补货|活动价|优惠/u],
  ["product_fact_answer", /什么木|木种|材质|材料|结构|工艺|尺寸|多高|多宽|多深|哪个版本/u],
  ["usage_fit_answer", /怎么保养|好打理|耐用|舒服|舒适|户型|动线|放得下|安装|入户|维修/u],
  ["boundary_unknown", /看不清|无法判断|不能确认|不确定|暂不提供|需要现场|信息不足/u],
  ["ugc_customer_response", /开箱|入住|用了.{0,6}(天|月|年)|使用反馈|买家秀|晒家|搭配展示/u],
  ["product_desire_response", /想买|想搬回家|想要|种草|想体验|搬我家/u],
  ["lifestyle_resonance", /我家|周末|下班|孩子|宠物|爸妈|咖啡|做饭|吃饭|睡觉/u],
  ["creator_specific_praise", /工坊|过程|改造|照片|拆解图|设计展|细节|光线|配色/u],
];

const TEACHER_PATTERNS = [
  /你(应该|必须|最好先)/u,
  /真正关键的是/u,
  /正确做法是/u,
  /显然|一看就知道/u,
  /建议你先.{0,20}再/u,
  /这样才(对|合理|专业)/u,
];

const FAKE_FIRSTHAND_PATTERNS = [
  /我(家|自己)?(买|入|用|住)过/u,
  /亲测/u,
  /用了.{0,8}(天|月|年)/u,
  /入住.{0,8}(天|月|年)/u,
];

const PUBLIC_PRIVACY_PATTERNS = [
  /在(评论区|下面).{0,12}(留|发|写).{0,8}(完整)?(手机号|地址|订单号|身份证)/u,
  /公开.{0,8}(手机号|地址|订单号|身份证)/u,
];

const CTA_PATTERNS = [
  /私信/u,
  /点击|点开/u,
  /到店|进店/u,
  /搜索|搜“|搜"/u,
  /填写|提交/u,
  /回复/u,
  /下单|购买/u,
];

const EMPTY_SECOND_SENTENCES = new Set([
  "这个真的很实用",
  "这点很值得参考",
  "很值得参考",
  "学到了",
  "确实很有意义",
  "期待更多分享",
  "期待后续",
  "一般家里有点难实现",
]);

function normalize(value = "") {
  return String(value).normalize("NFKC").replace(/\s+/gu, " ").trim();
}

function codePointLength(value) {
  return Array.from(normalize(value)).length;
}

function splitSentences(value) {
  return normalize(value)
    .split(/[。！？!?；;\n]+/u)
    .map((item) => item.trim())
    .filter(Boolean);
}

function countPatternGroups(value, patterns) {
  return patterns.reduce((count, pattern) => count + (pattern.test(value) ? 1 : 0), 0);
}

export function loadOfficialReplyPolicy(policyPath = DEFAULT_OFFICIAL_REPLY_POLICY_PATH) {
  const policy = JSON.parse(fs.readFileSync(policyPath, "utf8"));
  if (policy.policy_id !== OFFICIAL_REPLY_POLICY_ID) {
    throw new Error(`Expected ${OFFICIAL_REPLY_POLICY_ID}, received ${policy.policy_id}`);
  }
  return policy;
}

export function loadOfficialProfessionalValueContract(
  contractPath = DEFAULT_OFFICIAL_PROFESSIONAL_VALUE_PATH,
) {
  const contract = JSON.parse(fs.readFileSync(contractPath, "utf8"));
  if (contract.contract_id !== OFFICIAL_PROFESSIONAL_VALUE_ID) {
    throw new Error(
      `Expected ${OFFICIAL_PROFESSIONAL_VALUE_ID}, received ${contract.contract_id}`,
    );
  }
  return contract;
}

export function validateOfficialProfessionalValueContext(
  context,
  contract = loadOfficialProfessionalValueContract(),
) {
  const reasons = [];
  if (!context || typeof context !== "object" || Array.isArray(context)) {
    return {
      passed: false,
      contract_id: contract.contract_id,
      reasons: ["官方主动评论缺少专业价值前置上下文"],
    };
  }
  if (normalize(context.contractId) !== contract.contract_id) {
    reasons.push("官方专业价值规则版本不匹配");
  }
  const valueMode = normalize(context.valueMode);
  const modePolicy = contract.value_modes?.[valueMode];
  if (!modePolicy) reasons.push("没有声明有效的官方专业价值模式");
  if (!contract.professional_basis_types?.includes(normalize(context.professionalBasisType))) {
    reasons.push("没有声明有效的专业依据类型");
  }
  if (!normalize(context.professionalBasisText)) {
    reasons.push("没有写明可核对的专业依据");
  }
  if (context.usefulTakeawayPresent !== true) {
    reasons.push("没有提供与专业依据直接相关的判断或建议");
  }
  const factSourceStatus = normalize(context.factSourceStatus);
  if (!contract.fact_source_statuses?.includes(factSourceStatus)) {
    reasons.push("没有声明有效的事实来源状态");
  }
  if (
    valueMode === "professional_reasoned_praise" &&
    context.praiseReasonPrecedesPraise !== true
  ) {
    reasons.push("夸奖前没有先写专业理由");
  }
  if (modePolicy?.advice_allowed === true) {
    if (
      !modePolicy.allowed_advice_context_statuses?.includes(
        normalize(context.adviceContextStatus),
      )
    ) {
      reasons.push("建议没有回应作者提问、可见故障或直接服务问题");
    }
    const verified = ["verified_panse", "verified_current_external"].includes(
      factSourceStatus,
    );
    if (
      modePolicy.requires_conditional_language_unless_verified === true &&
      !verified &&
      context.conditionalLanguagePresent !== true
    ) {
      reasons.push("未经核实的实用建议没有使用条件化表达");
    }
  }
  return {
    passed: reasons.length === 0,
    contract_id: contract.contract_id,
    value_mode: valueMode,
    reasons,
  };
}

export function officialReplyRoute(routeId, policy = loadOfficialReplyPolicy()) {
  return policy.routes?.[normalize(routeId)] ?? null;
}

export function classifyOfficialReplyRoute(input, policy = loadOfficialReplyPolicy()) {
  const interactionType = normalize(input?.interaction_type || "reply_to_user");
  const combined = normalize(
    [input?.user_text, input?.post_context, input?.visible_comments_summary]
      .filter(Boolean)
      .join(" "),
  );
  const evidenceSignals = [];

  if (
    input?.platform_safe === false ||
    input?.duplicate_target === true ||
    input?.spam_or_abuse === true ||
    normalize(input?.no_reply_reason)
  ) {
    evidenceSignals.push("explicit_no_reply_condition");
    return buildClassification("no_reply", interactionType, 1, evidenceSignals, policy);
  }

  if (interactionType === "reply_to_brand") {
    evidenceSignals.push("reply_to_brand");
    return buildClassification("brand_peer_response", interactionType, 0.98, evidenceSignals, policy);
  }

  if (input?.facts_correction_required === true) {
    evidenceSignals.push("facts_correction_required");
    return buildClassification("misinformation_correction", interactionType, 1, evidenceSignals, policy);
  }
  if (input?.service_status_update === true) {
    evidenceSignals.push("service_status_update");
    return buildClassification("service_progress_update", interactionType, 1, evidenceSignals, policy);
  }
  if (input?.campaign_fulfillment === true) {
    evidenceSignals.push("campaign_fulfillment");
    return buildClassification("campaign_fulfillment_notice", interactionType, 1, evidenceSignals, policy);
  }

  for (const [routeId, pattern] of ROUTE_SIGNALS.slice(0, 4)) {
    if (pattern.test(combined)) {
      evidenceSignals.push(`high_priority_text_signal:${routeId}`);
      return buildClassification(routeId, interactionType, 0.94, evidenceSignals, policy);
    }
  }
  if (input?.unknown_or_insufficient === true) {
    evidenceSignals.push("unknown_or_insufficient");
    return buildClassification("boundary_unknown", interactionType, 1, evidenceSignals, policy);
  }
  if (input?.ugc_customer_content === true) {
    evidenceSignals.push("ugc_customer_content");
    return buildClassification("ugc_customer_response", interactionType, 0.98, evidenceSignals, policy);
  }
  if (
    interactionType === "outbound_comment" &&
    input?.visible_detail_grounded === true
  ) {
    evidenceSignals.push("outbound_visible_detail_grounded");
    return buildClassification("creator_specific_praise", interactionType, 0.94, evidenceSignals, policy);
  }

  for (const [routeId, pattern] of ROUTE_SIGNALS.slice(4)) {
    if (pattern.test(combined)) {
      evidenceSignals.push(`text_signal:${routeId}`);
      return buildClassification(routeId, interactionType, 0.9, evidenceSignals, policy);
    }
  }

  if (input?.visible_detail_grounded === true) {
    evidenceSignals.push("visible_detail_grounded");
    return buildClassification("creator_specific_praise", interactionType, 0.72, evidenceSignals, policy);
  }

  evidenceSignals.push("low_information_social_default");
  return buildClassification("micro_acknowledgement", interactionType, 0.55, evidenceSignals, policy);
}

function buildClassification(routeId, interactionType, confidence, evidenceSignals, policy) {
  const route = officialReplyRoute(routeId, policy);
  return {
    policy_id: policy.policy_id,
    route_id: routeId,
    family: route?.family ?? null,
    style_mode: route?.style_mode ?? null,
    interaction_type: interactionType,
    confidence,
    evidence_signals: evidenceSignals,
    should_reply: routeId !== "no_reply",
  };
}

function requiredFlagValue(context, requirement) {
  const mapping = {
    source_context_complete: context.sourceContextComplete,
    visible_detail_grounded: context.visibleDetailGrounded,
    facts_verified: context.factsVerified,
    unknowns_declared: context.unknownsDeclared,
    collaboration_verified: context.collaborationVerified,
    campaign_facts_verified: context.campaignFactsVerified,
    fulfillment_action_present: context.fulfillmentActionPresent,
    issue_specificity_present: context.issueSpecificityPresent,
    next_action_present: context.nextActionPresent,
    service_status_verified: context.serviceStatusVerified,
    evidence_or_investigation_status_present:
      context.evidenceOrInvestigationStatusPresent,
    no_reply_reason_present: Boolean(normalize(context.noReplyReason)),
  };
  return mapping[requirement] === true;
}

export function validateOfficialReply({
  draft = "",
  routeId = "",
  interactionType = "",
  sourceContextComplete = false,
  visibleCommentContextRead = false,
  visibleDetailGrounded = false,
  factsVerified = false,
  unknownsDeclared = false,
  collaborationVerified = false,
  campaignFactsVerified = false,
  fulfillmentActionPresent = false,
  issueSpecificityPresent = false,
  nextActionPresent = false,
  serviceStatusVerified = false,
  evidenceOrInvestigationStatusPresent = false,
  firsthandExperienceVerified = false,
  mentionsPanse = false,
  thirdPartyTarget = false,
  affiliationDisclosurePresent = false,
  selfCommentAuthorized = false,
  noReplyReason = "",
  platformSafe = true,
  classifiedInput = null,
  topicStrategyContext = null,
  professionalValueContext = null,
  ctaCount = null,
  policy = loadOfficialReplyPolicy(),
  topicStrategyPolicy = loadOfficialTopicStrategy(),
  professionalValueContract = loadOfficialProfessionalValueContract(),
} = {}) {
  const normalizedDraft = normalize(draft);
  const normalizedRouteId = normalize(routeId);
  const normalizedInteractionType = normalize(interactionType);
  const route = officialReplyRoute(normalizedRouteId, policy);
  const reasons = [];
  const topicStrategyReview = evaluateOfficialTopicStrategy(
    {
      interaction_type: normalizedInteractionType,
      ...(topicStrategyContext ?? {}),
      visible_detail_grounded:
        topicStrategyContext?.visible_detail_grounded ?? visibleDetailGrounded,
      visible_comment_context_read:
        topicStrategyContext?.visible_comment_context_read ??
        visibleCommentContextRead,
      facts_verified:
        topicStrategyContext?.facts_verified ?? factsVerified,
      collaboration_verified:
        topicStrategyContext?.collaboration_verified ??
        collaborationVerified,
      mentions_panse:
        topicStrategyContext?.mentions_panse ?? mentionsPanse,
    },
    topicStrategyPolicy,
  );
  const professionalValueReview =
    normalizedRouteId !== "no_reply" && normalizedInteractionType === "outbound_comment"
      ? validateOfficialProfessionalValueContext(
          professionalValueContext,
          professionalValueContract,
        )
      : null;

  if (!route) reasons.push("生成前没有声明有效的官方回复细方向");
  if (!policy.interaction_types?.[normalizedInteractionType]) {
    reasons.push("生成前没有声明有效的官方互动类型");
  }
  if (route && !route.interaction_types.includes(normalizedInteractionType)) {
    reasons.push("该官方回复细方向不适合当前互动类型");
  }
  if (platformSafe !== true && normalizedRouteId !== "no_reply") {
    reasons.push("平台或账号安全状态不允许外部互动");
  }
  if (
    normalizedRouteId !== "no_reply" &&
    normalizedInteractionType === "outbound_comment" &&
    topicStrategyReview.passed !== true
  ) {
    reasons.push(...topicStrategyReview.reasons);
  }
  if (professionalValueReview && professionalValueReview.passed !== true) {
    reasons.push(...professionalValueReview.reasons);
  }
  if (
    normalizedRouteId !== "no_reply" &&
    ["reply_to_user", "outbound_comment"].includes(normalizedInteractionType) &&
    visibleCommentContextRead !== true
  ) {
    reasons.push("尚未读取当前可见评论上下文");
  }
  if (normalizedInteractionType === "brand_self_comment" && selfCommentAuthorized !== true) {
    reasons.push("官方自评或置顶评论缺少当前任务授权");
  }

  if (normalizedRouteId !== "no_reply") {
    if (!normalizedDraft) reasons.push("官方回复草稿为空");
    const length = codePointLength(normalizedDraft);
    if (route && (length < route.character_range[0] || length > route.character_range[1])) {
      reasons.push(`草稿长度不在${route.character_range[0]}-${route.character_range[1]}字范围内`);
    }
    const sentenceCount = splitSentences(normalizedDraft).length;
    if (
      route &&
      (sentenceCount < route.sentence_range[0] || sentenceCount > route.sentence_range[1])
    ) {
      reasons.push(`句子数量不在${route.sentence_range[0]}-${route.sentence_range[1]}句范围内`);
    }
  } else if (normalizedDraft) {
    reasons.push("不回复方向不得生成草稿");
  }

  const requirementContext = {
    sourceContextComplete,
    visibleDetailGrounded,
    factsVerified,
    unknownsDeclared,
    collaborationVerified,
    campaignFactsVerified,
    fulfillmentActionPresent,
    issueSpecificityPresent,
    nextActionPresent,
    serviceStatusVerified,
    evidenceOrInvestigationStatusPresent,
    noReplyReason,
  };
  for (const requirement of route?.requires ?? []) {
    if (!requiredFlagValue(requirementContext, requirement)) {
      reasons.push(`官方回复方向缺少前置条件：${requirement}`);
    }
  }

  if (TEACHER_PATTERNS.some((pattern) => pattern.test(normalizedDraft))) {
    reasons.push("出现老师或评委式口吻");
  }
  if (PUBLIC_PRIVACY_PATTERNS.some((pattern) => pattern.test(normalizedDraft))) {
    reasons.push("要求用户在公开评论区提供隐私信息");
  }
  if (
    FAKE_FIRSTHAND_PATTERNS.some((pattern) => pattern.test(normalizedDraft)) &&
    firsthandExperienceVerified !== true
  ) {
    reasons.push("出现未经核实的购买、入住或长期使用经历");
  }
  if (
    mentionsPanse === true &&
    thirdPartyTarget === true &&
    affiliationDisclosurePresent !== true
  ) {
    reasons.push("第三方内容中涉及畔色产品或推荐，但没有说明官方关系");
  }
  const resolvedCtaCount = Number.isInteger(ctaCount)
    ? ctaCount
    : countPatternGroups(normalizedDraft, CTA_PATTERNS);
  if (resolvedCtaCount > 1) reasons.push("一个回复包含两个以上行动指令");

  const sentences = splitSentences(normalizedDraft);
  if (sentences.length > 1 && EMPTY_SECOND_SENTENCES.has(sentences.at(-1))) {
    reasons.push("结尾是可以直接删除的空洞第二句");
  }

  const classification = classifiedInput
    ? classifyOfficialReplyRoute(classifiedInput, policy)
    : null;
  if (
    classification &&
    classification.confidence >= 0.85 &&
    classification.route_id !== normalizedRouteId
  ) {
    const expectedPriority = policy.route_priority.indexOf(classification.route_id);
    const declaredPriority = policy.route_priority.indexOf(normalizedRouteId);
    if (expectedPriority >= 0 && (declaredPriority < 0 || expectedPriority < declaredPriority)) {
      reasons.push(`高优先级场景应先走${classification.route_id}`);
    }
  }

  return {
    passed: reasons.length === 0,
    policy_id: policy.policy_id,
    route_id: normalizedRouteId,
    route_label: route?.label ?? null,
    family: route?.family ?? null,
    style_mode: route?.style_mode ?? null,
    interaction_type: normalizedInteractionType,
    character_count: codePointLength(normalizedDraft),
    sentence_count: splitSentences(normalizedDraft).length,
    cta_count: resolvedCtaCount,
    classified_route: classification,
    topic_strategy: topicStrategyReview,
    professional_value: professionalValueReview,
    reasons,
  };
}
