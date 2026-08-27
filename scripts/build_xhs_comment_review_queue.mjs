import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { fileURLToPath, pathToFileURL } from "node:url";
import {
  DEFAULT_POLICY_PATH,
  INTENT_POLICY_VERSION,
  loadCommentIntentPolicy,
  validateCommentDirection,
} from "./lib/xhs_comment_intent_policy.mjs";
import {
  DEFAULT_OFFICIAL_REPLY_POLICY_PATH,
  OFFICIAL_REPLY_POLICY_ID,
  loadOfficialReplyPolicy,
  validateOfficialReply,
} from "./lib/xhs_official_reply_policy.mjs";
import {
  DEFAULT_OFFICIAL_TOPIC_STRATEGY_PATH,
  OFFICIAL_TOPIC_STRATEGY_ID,
} from "./lib/xhs_official_topic_strategy.mjs";

export const COMMENT_MODES = [
  "参数补充",
  "户型问诊",
  "报告翻译",
  "适用边界",
  "低成本替代",
  "征集晒图",
  "结构草图",
  "合作联合答疑",
  "被问后搜索词",
  "热问回收",
  "建设性争点",
];

const OFFSITE_OR_ENGAGEMENT_PATTERNS = [
  /看(我)?主页/u,
  /看(我)?置顶/u,
  /\bdd\b/iu,
  /加(我)?微(信)?/u,
  /微信|VX|V信/iu,
  /扫码|二维码/u,
  /求关注|点个赞|帮顶|互赞|互关/u,
];

const PRIVATE_MESSAGE_PATTERN = /私信/u;

const FIRST_HAND_PATTERNS = [
  /我(家|自己)?(买|入|用|住)过/u,
  /亲测/u,
  /自用.{0,8}(天|月|年)/u,
  /用了.{0,8}(天|月|年)/u,
  /入住.{0,8}(天|月|年)/u,
];

const UNSUPPORTED_NEGATIVE_PATTERNS = [
  /偷工减料/u,
  /质量(很差|不行|有问题)/u,
  /不牢|不安全|有毒/u,
  /甲醛(超标|爆表)/u,
  /肯定会(坏|塌|裂)/u,
];

const IDENTITY_SUPERIORITY_PATTERNS = [
  /(外国人|中国人|国人|某国人).{0,12}(天生|就是|都|更高级|更文明|不如|没素质)/u,
  /(男人|女人|南方人|北方人).{0,12}(天生|就是|都|更高级|更文明|不如|没素质)/u,
];

const MANIPULATIVE_DEBATE_PATTERNS = [
  /故意.{0,8}(制造|挑起|引发).{0,8}(争议|矛盾|吵架)/u,
  /带节奏|引战|吵起来|拱火/u,
  /其他网友怎么看/u,
];

const DEBATE_BASES = new Set([
  "real_tradeoff",
  "context_difference",
  "preference_split",
  "craft_process_difference",
  "material_aesthetic_difference",
  "market_preference_difference",
  "local_adaptation_tradeoff",
]);

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));
export const STYLE_REPLY_CONTRACT_PATH = path.resolve(
  MODULE_DIR,
  "..",
  "research",
  "panse_multi_direction",
    "xhs_reply_style_contract_v3.json",
);
export const STYLE_REPLY_CONTRACT = readJson(STYLE_REPLY_CONTRACT_PATH);
export const COMMENT_INTENT_POLICY = loadCommentIntentPolicy();
export const OFFICIAL_REPLY_POLICY = loadOfficialReplyPolicy();

export const PUBLIC_VOICES = [
  {
    voice_id: "principal_sincere_signed",
    account_id: "panse_official",
    pattern: /主理人|负责人|设计取舍|失败复盘|为什么这样做/u,
  },
  {
    voice_id: "official_explanation",
    account_id: "panse_official",
    pattern: /畔色|官方|版本|订单|售后|价格|链接|哪里买/u,
  },
  {
    voice_id: "space_advisor",
    account_id: "space_clinic",
    pattern: /户型|动线|开间|进深|墙宽|门宽|放得下|通道|尺寸/u,
  },
  {
    voice_id: "stylist",
    account_id: "mix_home_editor",
    pattern: /搭配|光线|颜色|软装|小屋|氛围|晒图|场景合成/u,
  },
  {
    voice_id: "global_design_observer",
    account_id: "global_furniture_editor",
    pattern: /国外|海外|北欧|日本|经典家具|设计史|展会|中国户型适配/u,
  },
  {
    voice_id: "evaluation_judgment",
    account_id: "furniture_decision_editor",
    pattern: /材料|结构|检测|报告|选购|先不买|替代|参数/u,
  },
];

const MODE_HINTS = [
  ["被问后搜索词", /品牌|链接|哪里买|店铺|型号/u],
  ["征集晒图", /晒图|晒家具|发图|产品图/u],
  ["报告翻译", /检测|报告|标准|认证|甲醛/u],
  ["户型问诊", /户型|动线|开间|进深|墙宽|门宽|放得下/u],
  ["结构草图", /结构|连接|五金|榫|安装图|受力/u],
  ["合作联合答疑", /合作|联合答疑|授权博主/u],
  ["低成本替代", /先不买|替代|要不要买|预算|省钱/u],
  ["适用边界", /适合|不适合|照抄|边界|条件/u],
  ["热问回收", /高频|很多人问|反复问|热问/u],
  ["建设性争点", /取舍|两种做法|你们那里|更在意|选哪种|分歧/u],
  ["参数补充", /尺寸|参数|高度|深度|宽度|材质/u],
];

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function normalizeText(value = "") {
  return String(value)
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim();
}

function includesAny(text, patterns) {
  return patterns.some((pattern) => pattern.test(text));
}

function styleProfileForVoice(voice) {
  return STYLE_REPLY_CONTRACT.voice_preflights.find(
    (profile) => profile.voice_id === voice.voice_id,
  );
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function candidateInputFingerprint(candidate) {
  const proposed = candidate?.proposed ?? {};
  const { style_lab_receipt: ignoredReceipt, ...proposedWithoutReceipt } =
    proposed;
  void ignoredReceipt;
  return sha256(
    canonicalJson({
      ...candidate,
      proposed: proposedWithoutReceipt,
    }),
  );
}

function sameCanonicalValue(left, right) {
  return canonicalJson(left) === canonicalJson(right);
}

function evaluateStyleReceipt(
  proposed,
  profile,
  candidateId,
  candidateInputSha256,
  expectedInteractionIntent,
  expectedDetailedDirection,
  expectedTopicIds,
  expectedVoiceStyleId,
  expectedInteractionMode,
) {
  const receipt = proposed?.style_lab_receipt ?? {};
  const gateTuple = Array.isArray(receipt?.gate_tuple)
    ? receipt.gate_tuple
    : [];
  const requiredHardGates =
    STYLE_REPLY_CONTRACT.receipt_contract.required_hard_gates;
  const gateByName = new Map(
    gateTuple.map((item) => [normalizeText(item?.name), item]),
  );
  const hardGatesPass =
    requiredHardGates.every((name) => {
      const item = gateByName.get(name);
      return item?.hard === true && item?.status === "pass";
    }) &&
    gateTuple.every((item) => item?.hard !== true || item?.status === "pass");
  const naturalnessPass =
    receipt?.naturalness_status === "pass" ||
    receipt?.naturalness_checks?.repair_required === false;
  const reasons = [];

  if (!profile) reasons.push("没有匹配的风格角色配置");
  if (receipt?.contract_version !== STYLE_REPLY_CONTRACT.schema_version) {
    reasons.push("缺少当前版本的风格实验室回执");
  }
  if (receipt?.intent_policy_version !== INTENT_POLICY_VERSION) {
    reasons.push("缺少当前版本的评论方向策略回执");
  }
  if (!expectedInteractionIntent) {
    reasons.push("风格生成前没有声明评论方向");
  } else if (receipt?.interaction_intent !== expectedInteractionIntent) {
    reasons.push("风格回执没有绑定当前评论方向");
  }
  if (!expectedDetailedDirection) {
    reasons.push("风格生成前没有声明20类评论细方向之一");
  } else if (receipt?.comment_direction_id !== expectedDetailedDirection) {
    reasons.push("风格回执没有绑定当前评论细方向");
  }
  if (!sameCanonicalValue(receipt?.topic_ids, expectedTopicIds)) {
    reasons.push("风格回执没有绑定当前原帖主题");
  }
  if (receipt?.voice_style_id !== expectedVoiceStyleId) {
    reasons.push("风格回执没有绑定当前账号语气层");
  }
  if (receipt?.interaction_mode !== expectedInteractionMode) {
    reasons.push("风格回执的互动模式与评论细方向不一致");
  }
  if (receipt?.candidate_id !== candidateId) {
    reasons.push("风格回执未绑定当前候选内容");
  }
  if (receipt?.candidate_input_sha256 !== candidateInputSha256) {
    reasons.push("候选内容已变化，风格回执需要重新生成");
  }
  if (
    profile &&
    receipt?.style_profile_sha256 !== profile.style_profile_sha256
  ) {
    reasons.push("风格角色指纹与当前声音不一致");
  }
  if (
    receipt?.catalog_version !== STYLE_REPLY_CONTRACT.style_lab.catalog_version ||
    receipt?.catalog_sha256 !== STYLE_REPLY_CONTRACT.style_lab.catalog_sha256
  ) {
    reasons.push("风格目录版本或 SHA-256 不是当前锁定版本");
  }
  if (
    profile &&
    !sameCanonicalValue(receipt?.approved_card_refs, profile.approved_card_refs)
  ) {
    reasons.push("已批准风格卡或卡片版本与当前角色不一致");
  }
  if (
    profile &&
    !sameCanonicalValue(receipt?.taxonomy_ids, profile.taxonomy_ids)
  ) {
    reasons.push("风格分类与当前角色不一致");
  }
  if (profile && receipt?.requested_strength !== profile.requested_strength) {
    reasons.push("风格强度与当前角色不一致");
  }
  const bundleSha256 = normalizeText(receipt?.bundle_sha256);
  const bundleId = normalizeText(receipt?.bundle_id);
  if (
    !/^[0-9a-f]{64}$/u.test(bundleSha256) ||
    bundleId !== `stylebundle_${bundleSha256.slice(0, 24)}`
  ) {
    reasons.push("动态 Style Bundle 标识与 SHA-256 不一致");
  }
  if (
    receipt?.model_id !==
    STYLE_REPLY_CONTRACT.provider_contract.required_model_id
  ) {
    reasons.push("生成模型不是固定的 gpt-5.6-sol");
  }
  if (receipt?.model_verified !== true) {
    reasons.push("生成模型元数据尚未验证");
  }
  if (!normalizeText(receipt?.provider)) {
    reasons.push("缺少生成服务提供方元数据");
  }
  const promptVersionsPresent = Array.isArray(receipt?.prompt_versions)
    ? receipt.prompt_versions.length > 0
    : receipt?.prompt_versions &&
      typeof receipt.prompt_versions === "object" &&
      Object.keys(receipt.prompt_versions).length > 0;
  if (!promptVersionsPresent) {
    reasons.push("缺少各生成阶段的提示词版本");
  }
  if (Number.isNaN(Date.parse(normalizeText(receipt?.observed_at)))) {
    reasons.push("缺少有效的模型观测时间");
  }
  if (!hardGatesPass) reasons.push("确定性硬门尚未全部通过");
  if (!naturalnessPass) reasons.push("评论自然度检查尚未通过");
  if (receipt?.delivery_ready_for_human_review !== true) {
    reasons.push("风格实验室尚未放行到人工复核阶段");
  }
  if (receipt?.human_review_required !== true) {
    reasons.push("回执没有保留人工复核要求");
  }
  if (receipt?.publish_allowed !== false) {
    reasons.push("回执必须明确 publish_allowed=false");
  }

  return {
    valid: reasons.length === 0,
    reasons,
    receipt_present: Object.keys(receipt).length > 0,
  };
}

function inferMode(candidate) {
  const requested = normalizeText(candidate?.proposed?.mode);
  if (COMMENT_MODES.includes(requested)) {
    return requested;
  }

  const combined = normalizeText(
    [
      candidate?.target_note?.topic,
      candidate?.question_summary,
      candidate?.proposed?.draft,
    ]
      .filter(Boolean)
      .join(" "),
  );

  return MODE_HINTS.find(([, pattern]) => pattern.test(combined))?.[0] ??
    "参数补充";
}

function gate(name, passed, reason) {
  return { name, passed: Boolean(passed), reason };
}

function inferVoice(candidate, mode) {
  const proposed = candidate?.proposed ?? {};
  const requested = normalizeText(proposed?.voice_id);
  const declared = PUBLIC_VOICES.find((voice) => voice.voice_id === requested);
  if (declared) {
    return declared;
  }

  const combined = normalizeText(
    [
      candidate?.target_note?.topic,
      candidate?.question_summary,
      proposed?.draft,
      mode,
    ]
      .filter(Boolean)
      .join(" "),
  );
  return (
    PUBLIC_VOICES.find((voice) => voice.pattern.test(combined)) ??
    PUBLIC_VOICES.find(
      (voice) => voice.voice_id === "evaluation_judgment",
    )
  );
}

function evaluateCandidate(candidate) {
  const note = candidate?.target_note ?? {};
  const proposed = candidate?.proposed ?? {};
  const candidateId = normalizeText(candidate?.candidate_id);
  const candidateInputSha256 = candidateInputFingerprint(candidate);
  const image = proposed?.image ?? {};
  const draft = normalizeText(proposed?.draft);
  const mode = inferMode(candidate);
  const voice = inferVoice(candidate, mode);
  const declaredInteractionIntent = normalizeText(
    proposed?.interaction_intent,
  );
  const declaredDetailedDirection = normalizeText(
    proposed?.comment_direction_id,
  );
  const declaredTopicIds = Array.isArray(proposed?.topic_ids)
    ? proposed.topic_ids.map((value) => normalizeText(value)).filter(Boolean)
    : [];
  const styleProfile = styleProfileForVoice(voice);
  const directionReview = validateCommentDirection({
    text: draft,
    voiceId: voice.voice_id,
    declaredIntent: declaredInteractionIntent,
    declaredDirection: declaredDetailedDirection,
    topicContext: [
      note?.topic,
      candidate?.question_summary,
      proposed?.source_context?.body,
    ].filter(Boolean).join(" "),
    declaredTopicIds,
    topicAlignmentVerified: proposed?.topic_alignment_verified === true,
    sourceContextComplete: proposed?.source_context_complete === true,
    visibleDetailGrounded: proposed?.visible_detail_grounded === true,
    firsthandVerified: proposed?.firsthand_experience_verified === true,
    adviceInvited:
      note?.explicitly_invites_advice === true || note?.allows_advice === true,
    questionAlreadyAnswered:
      proposed?.question_answered_in_context === true,
    differenceBasisVerified:
      proposed?.contextual_difference_basis_verified === true,
    policy: COMMENT_INTENT_POLICY,
  });
  const styleReceipt = evaluateStyleReceipt(
    proposed,
    styleProfile,
    candidateId,
    candidateInputSha256,
    declaredInteractionIntent,
    declaredDetailedDirection,
    directionReview.topic_ids,
    directionReview.voice_style_id,
    directionReview.interaction_mode,
  );
  const isOfficialVoice = voice.account_id === "panse_official";
  const officialReplyContext = proposed?.official_reply_context ?? {};
  const officialTopicStrategyContext =
    officialReplyContext?.topic_strategy ?? {};
  const officialRouteId = normalizeText(officialReplyContext?.route_id);
  const sources = Array.isArray(proposed?.fact_sources)
    ? proposed.fact_sources.filter(Boolean)
    : [];

  const relevancePassed =
    Boolean(normalizeText(note?.topic)) &&
    Boolean(normalizeText(candidate?.question_summary)) &&
    Boolean(draft) &&
    note?.allows_advice !== false &&
    note?.minor_or_sensitive !== true;

  const minimumValuePassed =
    draft.length >= 12 &&
    (Boolean(normalizeText(proposed?.value_added)) ||
      sources.length > 0 ||
      mode === "户型问诊" ||
      mode === "低成本替代" ||
      mode === "热问回收") ||
    (isOfficialVoice &&
      [
        "micro_acknowledgement",
        "product_desire_response",
        "brand_peer_response",
      ].includes(officialRouteId) &&
      draft.length > 0);

  const claimsFirstHand =
    proposed?.claims_firsthand_experience === true ||
    includesAny(draft, FIRST_HAND_PATTERNS);
  const identityPassed =
    !claimsFirstHand || proposed?.firsthand_experience_verified === true;

  const requiresEvidence =
    proposed?.requires_evidence === true ||
    proposed?.named_competitor_comparison === true ||
    includesAny(draft, UNSUPPORTED_NEGATIVE_PATTERNS);
  const evidencePassed = !requiresEvidence || sources.length > 0;

  const hasImage = image?.attached === true;
  const hasImageRights =
    !hasImage || ["owned", "authorized"].includes(image?.rights_status);
  const syntheticDisclosed =
    image?.synthetic !== true ||
    /空间提案|场景合成/u.test(normalizeText(image?.disclosure));
  const imageInvitationValid =
    mode !== "征集晒图" || note?.explicitly_invites_product_images === true;
  const imagePassed =
    hasImageRights && syntheticDisclosed && imageInvitationValid;

  const mentionsPanse =
    proposed?.mentions_panse === true || /畔色/u.test(draft);
  const hasAffiliationDisclosure =
    /利益相关|这是我们|我们参与|畔色官方/u.test(draft) &&
    Boolean(normalizeText(proposed?.affiliation_disclosure));
  const competitorPoaching =
    note?.competitor_commercial === true && mentionsPanse;
  const collaborationContextValid =
    mode !== "合作联合答疑" || proposed?.collaboration_authorized === true;
  const brandSearchContextValid =
    mode !== "被问后搜索词" || note?.user_requested_brand_or_link === true;
  const commercialPassed =
    !competitorPoaching &&
    collaborationContextValid &&
    brandSearchContextValid &&
    (!mentionsPanse || hasAffiliationDisclosure);

  const requestedAccountId = normalizeText(proposed?.account_id);
  const accountMatchesVoice =
    !requestedAccountId || requestedAccountId === voice.account_id;
  const principalIdentityValid =
    voice.voice_id !== "principal_sincere_signed" ||
    (proposed?.real_decision_participant_verified === true &&
      Boolean(normalizeText(proposed?.principal_signature)));
  const voicePassed = accountMatchesVoice && principalIdentityValid;

  const debate = proposed?.debate ?? {};
  const debatePrompt = normalizeText(debate?.prompt || draft);
  const debateBasisValid =
    mode !== "建设性争点" || DEBATE_BASES.has(normalizeText(debate?.basis));
  const debateTruthful =
    mode !== "建设性争点" ||
    (debate?.truthful_tradeoff === true &&
      debate?.fabricated_disagreement !== true);
  const debateIdentitySafe =
    mode !== "建设性争点" ||
    !includesAny(debatePrompt, IDENTITY_SUPERIORITY_PATTERNS);
  const debateNotManipulative =
    mode !== "建设性争点" ||
    (!includesAny(debatePrompt, MANIPULATIVE_DEBATE_PATTERNS) &&
      debate?.bait_only !== true);
  const debatePassed =
    debateBasisValid &&
    debateTruthful &&
    debateIdentitySafe &&
    debateNotManipulative;

  const officialPrivateHandoffAllowed =
    isOfficialVoice &&
    [
      "complaint_acknowledgement",
      "service_progress_update",
      "campaign_fulfillment_notice",
    ].includes(officialRouteId);
  const privateMessagePassed =
    !PRIVATE_MESSAGE_PATTERN.test(draft) || officialPrivateHandoffAllowed;
  const platformPassed =
    !includesAny(draft, OFFSITE_OR_ENGAGEMENT_PATTERNS) &&
    privateMessagePassed &&
    proposed?.coordinated_account_action !== true &&
    proposed?.automatic_private_message !== true &&
    note?.platform_warning_present !== true;

  const officialReplyReview = isOfficialVoice
    ? validateOfficialReply({
        draft,
        routeId: officialRouteId,
        interactionType: officialReplyContext?.interaction_type,
        sourceContextComplete: proposed?.source_context_complete === true,
        visibleCommentContextRead:
          officialReplyContext?.visible_comment_context_read === true,
        visibleDetailGrounded: proposed?.visible_detail_grounded === true,
        factsVerified:
          officialReplyContext?.facts_verified === true || sources.length > 0,
        unknownsDeclared: officialReplyContext?.unknowns_declared === true,
        collaborationVerified:
          proposed?.collaboration_authorized === true ||
          officialReplyContext?.collaboration_verified === true,
        campaignFactsVerified:
          officialReplyContext?.campaign_facts_verified === true,
        fulfillmentActionPresent:
          officialReplyContext?.fulfillment_action_present === true,
        issueSpecificityPresent:
          officialReplyContext?.issue_specificity_present === true,
        nextActionPresent: officialReplyContext?.next_action_present === true,
        serviceStatusVerified:
          officialReplyContext?.service_status_verified === true,
        evidenceOrInvestigationStatusPresent:
          officialReplyContext?.evidence_or_investigation_status_present === true ||
          sources.length > 0,
        firsthandExperienceVerified:
          proposed?.firsthand_experience_verified === true,
        mentionsPanse,
        thirdPartyTarget:
          officialReplyContext?.third_party_target === true ||
          officialReplyContext?.interaction_type === "outbound_comment",
        affiliationDisclosurePresent:
          Boolean(normalizeText(proposed?.affiliation_disclosure)) ||
          officialReplyContext?.affiliation_disclosure_present === true,
        selfCommentAuthorized:
          officialReplyContext?.self_comment_authorized === true,
        noReplyReason: officialReplyContext?.no_reply_reason,
        platformSafe: platformPassed,
        classifiedInput: officialReplyContext?.classified_input ?? null,
        topicStrategyContext: {
          ...officialTopicStrategyContext,
          post_context:
            officialTopicStrategyContext?.post_context ??
            proposed?.source_context?.body ??
            note?.topic,
          user_text:
            officialTopicStrategyContext?.user_text ??
            candidate?.question_summary,
          visible_detail_grounded:
            officialTopicStrategyContext?.visible_detail_grounded ??
            proposed?.visible_detail_grounded === true,
          visible_comment_context_read:
            officialTopicStrategyContext?.visible_comment_context_read ??
            officialReplyContext?.visible_comment_context_read === true,
          facts_verified:
            officialTopicStrategyContext?.facts_verified ??
            (officialReplyContext?.facts_verified === true || sources.length > 0),
          mentions_panse:
            officialTopicStrategyContext?.mentions_panse ?? mentionsPanse,
        },
        ctaCount: Number.isInteger(officialReplyContext?.cta_count)
          ? officialReplyContext.cta_count
          : null,
        policy: OFFICIAL_REPLY_POLICY,
      })
    : {
        passed: true,
        policy_id: OFFICIAL_REPLY_POLICY_ID,
        route_id: null,
        family: null,
        style_mode: null,
        reasons: [],
      };

  const gates = [
    gate(
      "评论方向门",
      directionReview.passed,
      directionReview.passed
        ? `先选${directionReview.intent}方向，再进入风格生成`
        : directionReview.reasons.join("；"),
    ),
    gate(
      "官方回复路由门",
      officialReplyReview.passed,
      isOfficialVoice
        ? officialReplyReview.passed
          ? `官方号按${officialReplyReview.route_id}方向生成并复核`
          : officialReplyReview.reasons.join("；")
        : "非官方号不适用官方回复路由",
    ),
    gate(
      "官方话题发言权门",
      !isOfficialVoice || officialReplyReview.topic_strategy?.passed === true,
      !isOfficialVoice
        ? "非官方号不适用官方话题发言权门"
        : officialReplyReview.topic_strategy?.passed
          ? `话题${officialReplyReview.topic_strategy.topic_id}及畔色发言权已声明`
          : (officialReplyReview.topic_strategy?.reasons ?? []).join("；"),
    ),
    gate(
      "相关性门",
      relevancePassed,
      relevancePassed
        ? "回应了允许参与的具体家具或空间问题"
        : "缺少具体问题、主题、草稿，或目标不适合参与",
    ),
    gate(
      "新增价值门",
      minimumValuePassed,
      minimumValuePassed
        ? "包含具体条件、参数、来源或可执行判断"
        : "内容过短或没有新增信息",
    ),
    gate(
      "身份门",
      identityPassed,
      identityPassed
        ? "没有未核实的消费者或长期使用身份"
        : "出现未核实的购买、入住或使用经历",
    ),
    gate(
      "证据门",
      evidencePassed,
      evidencePassed
        ? "需要证据的主张已有来源，或本条不作事实性强断言"
        : "事实、竞品或安全主张缺少可追溯来源",
    ),
    gate(
      "图片门",
      imagePassed,
      imagePassed
        ? "图片授权、合成标识和晒图邀请条件通过"
        : "图片授权、合成标识或晒图邀请条件不满足",
    ),
    gate(
      "商业关系门",
      commercialPassed,
      commercialPassed
        ? "未截流竞品；合作已授权；品牌提及发生在主动询问后并已说明关系"
        : "存在竞品截流、合作未授权、非主动品牌承接或利益关系未说明",
    ),
    gate(
      "角色门",
      voicePassed,
      voicePassed
        ? `由${voice.voice_id}对应账号承接，身份条件完整`
        : "指定账号与公开声音不匹配，或负责人署名缺少真实参与验证",
    ),
    gate(
      "争点门",
      debatePassed,
      debatePassed
        ? "争点来自真实取舍或差异，没有虚构对立和身份优越判断"
        : "争点缺少真实依据、含虚构对立、身份优越判断或煽动性表达",
    ),
    gate(
      "平台门",
      platformPassed,
      platformPassed
        ? "没有站外导流、诱导互动、多账号协同或平台警告"
        : "含站外导流、诱导互动、多账号协同或平台风险信号",
    ),
  ];

  const failedGates = gates.filter((item) => !item.passed);
  const contentGatesPassed = failedGates.length === 0;
  const humanReviewReasons = [];
  if (mentionsPanse) humanReviewReasons.push("品牌提及");
  if (proposed?.named_competitor_comparison === true) {
    humanReviewReasons.push("具名竞品比较");
  }
  if (hasImage) humanReviewReasons.push("产品或空间图片");
  if (mode === "被问后搜索词") humanReviewReasons.push("站内搜索词承接");
  if (mode === "合作联合答疑") humanReviewReasons.push("合作授权状态");
  if (mode === "建设性争点") {
    humanReviewReasons.push("建设性争点与回复边界");
  }
  if (voice.voice_id === "principal_sincere_signed") {
    humanReviewReasons.push("真实负责人署名");
  }
  if (isOfficialVoice) {
    humanReviewReasons.push(`官方回复细方向：${officialReplyReview.route_id || "未声明"}`);
  }

  const idempotencyKey = [
    normalizeText(note?.note_id),
    mode,
    draft.toLowerCase(),
  ].join("::");

  return {
    candidate_id: candidateId,
    idempotency_key: idempotencyKey,
    target_note: {
      note_id: normalizeText(note?.note_id),
      url: normalizeText(note?.url),
      author: normalizeText(note?.author),
      topic: normalizeText(note?.topic),
      competitor_commercial: note?.competitor_commercial === true,
    },
    selected_mode: mode,
    interaction_direction: directionReview,
    official_reply_route: isOfficialVoice
      ? officialReplyReview
      : { applicable: false, policy_id: OFFICIAL_REPLY_POLICY_ID },
    official_topic_strategy: isOfficialVoice
      ? officialReplyReview.topic_strategy
      : { applicable: false, strategy_id: OFFICIAL_TOPIC_STRATEGY_ID },
    voice_route: {
      voice_id: voice.voice_id,
      account_id: voice.account_id,
    },
    question_summary: normalizeText(candidate?.question_summary),
    draft,
    fact_sources: sources,
    image: {
      attached: hasImage,
      rights_status: normalizeText(image?.rights_status),
      synthetic: image?.synthetic === true,
      disclosure: normalizeText(image?.disclosure),
    },
    mentions_panse: mentionsPanse,
    affiliation_disclosure: normalizeText(
      proposed?.affiliation_disclosure,
    ),
    draft_status: styleReceipt.valid
      ? "style_lab_generated"
      : "candidate_only_not_style_approved",
    style_generation: {
      required: true,
      contract_schema_version: STYLE_REPLY_CONTRACT.schema_version,
      contract_path: STYLE_REPLY_CONTRACT_PATH,
      intent_policy_version: INTENT_POLICY_VERSION,
      intent_policy_path: DEFAULT_POLICY_PATH,
      official_reply_policy_id: isOfficialVoice
        ? OFFICIAL_REPLY_POLICY_ID
        : null,
      official_reply_policy_path: isOfficialVoice
        ? DEFAULT_OFFICIAL_REPLY_POLICY_PATH
        : null,
      official_reply_route_id: isOfficialVoice
        ? officialReplyReview.route_id
        : null,
      official_reply_style_mode: isOfficialVoice
        ? officialReplyReview.style_mode
        : null,
      official_topic_strategy_id: isOfficialVoice
        ? OFFICIAL_TOPIC_STRATEGY_ID
        : null,
      official_topic_strategy_path: isOfficialVoice
        ? DEFAULT_OFFICIAL_TOPIC_STRATEGY_PATH
        : null,
      official_topic_id: isOfficialVoice
        ? officialReplyReview.topic_strategy?.topic_id ?? null
        : null,
      official_panse_reply_right: isOfficialVoice
        ? officialReplyReview.topic_strategy?.panse_reply_right ?? null
        : null,
      interaction_intent: directionReview.intent,
      comment_direction_id: directionReview.direction_id,
      topic_ids: directionReview.topic_ids,
      voice_style_id: directionReview.voice_style_id,
      voice_contract: directionReview.voice_contract,
      direction_contract: directionReview.direction_contract,
      interaction_mode: directionReview.interaction_mode,
      explicit_intent_required_before_receipt: true,
      style_lab_catalog_version:
        STYLE_REPLY_CONTRACT.style_lab.catalog_version,
      style_lab_catalog_sha256:
        STYLE_REPLY_CONTRACT.style_lab.catalog_sha256,
      required_model_id:
        STYLE_REPLY_CONTRACT.provider_contract.required_model_id,
      fallback_model_allowed:
        STYLE_REPLY_CONTRACT.provider_contract.fallback_model_allowed,
      voice_id: voice.voice_id,
      account_id: voice.account_id,
      artifact_type: styleProfile?.artifact_type ?? "",
      taxonomy_ids: styleProfile?.taxonomy_ids ?? [],
      requested_strength: styleProfile?.requested_strength ?? null,
      style_profile_sha256: styleProfile?.style_profile_sha256 ?? "",
      preflight_bundle_id: styleProfile?.preflight_bundle_id ?? "",
      preflight_bundle_sha256:
        styleProfile?.preflight_bundle_sha256 ?? "",
      approved_card_refs: styleProfile?.approved_card_refs ?? [],
      candidate_input_sha256: candidateInputSha256,
      preconditions: STYLE_REPLY_CONTRACT.preconditions.map((item) => item.id),
      receipt_present: styleReceipt.receipt_present,
      receipt_valid: styleReceipt.valid,
      receipt_failures: styleReceipt.reasons,
      status: !contentGatesPassed
        ? "blocked_by_content_gate"
        : styleReceipt.valid
          ? "ready_for_human_review"
          : "awaiting_style_lab_generation",
      publish_allowed: false,
    },
    gates,
    failed_gates: failedGates.map((item) => item.name),
    queue_status:
      !contentGatesPassed
        ? "rejected_by_gate"
        : styleReceipt.valid
          ? "awaiting_human_review"
          : "awaiting_style_lab_generation",
    eligible_for_style_generation:
      contentGatesPassed && !styleReceipt.valid,
    eligible_for_human_review:
      contentGatesPassed && styleReceipt.valid,
    human_review_required: contentGatesPassed,
    human_review_reasons:
      humanReviewReasons.length > 0
        ? humanReviewReasons
        : ["所有外部评论都必须人工复核"],
    publish_allowed: false,
  };
}

export function buildReviewQueue(payload, generatedAt = new Date().toISOString()) {
  const candidates = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.candidates)
      ? payload.candidates
      : [];

  const seen = new Set();
  const duplicateCandidates = [];
  const records = [];

  for (const candidate of candidates) {
    const evaluated = evaluateCandidate(candidate);
    if (seen.has(evaluated.idempotency_key)) {
      duplicateCandidates.push({
        candidate_id: evaluated.candidate_id,
        idempotency_key: evaluated.idempotency_key,
        reason: "同一目标笔记、模式和标准化草稿已存在",
      });
      continue;
    }
    seen.add(evaluated.idempotency_key);
    records.push(evaluated);
  }

  const eligible = records.filter((item) => item.eligible_for_human_review);
  const awaitingStyle = records.filter(
    (item) => item.eligible_for_style_generation,
  );

  return {
    schema_version: 2,
    generated_at: generatedAt,
    system: "panse_xiaohongshu_comment_review_queue",
    execution_scope: "local_analysis_only",
    network_access_performed: false,
    external_posting_enabled: false,
    publish_allowed: false,
    summary: {
      input_candidates: candidates.length,
      unique_candidates: records.length,
      duplicates_removed: duplicateCandidates.length,
      awaiting_style_generation: awaitingStyle.length,
      awaiting_human_review: eligible.length,
      rejected_by_gate: records.filter(
        (item) => item.queue_status === "rejected_by_gate",
      ).length,
      modes_present: [...new Set(records.map((item) => item.selected_mode))],
    },
    duplicates: duplicateCandidates,
    records,
  };
}

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (current === "--input" || current === "--output") {
      result[current.slice(2)] = argv[index + 1];
      index += 1;
    } else if (current === "--compact") {
      result.compact = true;
    } else {
      throw new Error(`Unknown argument: ${current}`);
    }
  }
  return result;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) {
    throw new Error(
      "Usage: node scripts/build_xhs_comment_review_queue.mjs --input <candidates.json> [--output <queue.json>] [--compact]",
    );
  }

  const inputPath = path.resolve(args.input);
  const queue = buildReviewQueue(readJson(inputPath));
  const serialized = `${JSON.stringify(queue, null, args.compact ? 0 : 2)}\n`;

  if (args.output) {
    const outputPath = path.resolve(args.output);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, serialized, "utf8");
    process.stdout.write(
      `${JSON.stringify({ output: outputPath, ...queue.summary }, null, 2)}\n`,
    );
    return;
  }

  process.stdout.write(serialized);
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  try {
    main();
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : error}\n`);
    process.exitCode = 1;
  }
}
