import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MODULE_DIR = path.dirname(fileURLToPath(import.meta.url));

export const DEFAULT_POLICY_PATH = path.resolve(
  MODULE_DIR,
  "..",
  "..",
  "research",
  "panse_multi_direction",
  "xhs_comment_intent_policy_v4.json",
);

export const INTENT_POLICY_VERSION = "xhs-comment-intent.v4";

export const DEFAULT_HUMAN_APPROVED_EXAMPLES_PATH = path.resolve(
  MODULE_DIR,
  "..",
  "..",
  "research",
  "panse_multi_direction",
  "comment_drafts_review_15_2026-08-10.json",
);

const SIGNALS = {
  acquisition_where: /哪里买|哪买|怎么买|求链接|有链接|链接吗|店铺|门店|地址|哪家|什么牌子|哪个品牌|型号|色号|淘宝|官网/iu,
  price_budget: /多少钱|什么价|价格|报价|预算|花了多少|贵不贵|买不起|费用|价位/iu,
  utility_fit: /尺寸|多大|多宽|多高|多深|开间|进深|过道|通道|放得下|适合|承重|稳不稳|实用|好用|收纳|清洁|打理|耐用|舒服|遮光|采光|安装|怎么用|有什么用/iu,
  question: /[?？]|请问|想问|求问|怎么|哪里|哪儿|多少|多大|是不是|有没有|能不能|会不会|什么/iu,
  praise: /好看|漂亮|喜欢|温馨|舒服|氛围|治愈|厉害|绝了|太美|高级|可爱|羡慕|心动|爱了|有生活|真棒|真好|审美|大气|有质感|不错|真美|养眼|有品|有感觉|挺特别|有意思|赞/iu,
  self_reference: /我家|我们家|我也|我买|我用|我住|我装|同款|正在装修|准备装修|打算|我的|我这边|我之前|我现在/iu,
  self_display: /我家.{0,16}(更|也有|早就|同款)|我(买|装|做)的.{0,16}(更|才|就是)|比我家|我家比|我这个更/iu,
  request_more: /求图|求教程|想看|蹲后续|求清单|尺寸图|户型图|展开讲|出一期|多分享|继续更/iu,
  peer_tip: /建议|可以试|可以先|最好|注意|记得|不如|换成|尽量|实在不行|可以把|要一起|先从/iu,
  critique: /不好看|丑|不实用|翻车|智商税|没必要|踩雷|不喜欢|不可取|不合理|浪费|有问题/iu,
  humor: /哈哈|笑死|搬出去|让我住|给我住|我来住|请离开|打劫|偷走|梦里|排队|夺舍|hhh/iu,
  teacher_posture: /真正|关键|本质|更值得参考|主要还得看|必须|一定要|才是|正确做法|应该先|听我的|照着做|别硬|根本不懂/iu,
  critique_first: /^(但是|不过|其实|说句不好听|恕我直言|这不就是|不好看|不实用|没必要|智商税|翻车|不可取|不合理)/iu,
};

const INTENT_ORDER = [
  "acquisition_question",
  "utility_fit_question",
  "request_more",
  "grounded_praise",
  "self_display_verified",
  "self_reference_verified",
  "peer_tip_invited",
  "contextual_disagreement",
  "light_humor",
  "neutral_social",
];

export function normalizeCommentText(value = "") {
  return String(value).normalize("NFKC").replace(/\s+/gu, " ").trim();
}

export function classifyCommentIntent(value) {
  const text = normalizeCommentText(value);
  const signals = Object.fromEntries(
    Object.entries(SIGNALS).map(([name, pattern]) => [name, pattern.test(text)]),
  );
  const labels = Object.entries(signals)
    .filter(([, present]) => present)
    .map(([name]) => name);

  let primary_intent = "neutral_social";
  if (signals.acquisition_where || signals.price_budget) {
    primary_intent = "acquisition_question";
  } else if (signals.question && signals.utility_fit) {
    primary_intent = "utility_fit_question";
  } else if (signals.request_more) {
    primary_intent = "request_more";
  } else if (signals.praise) {
    primary_intent = "grounded_praise";
  } else if (signals.self_display) {
    primary_intent = "self_display_verified";
  } else if (signals.self_reference) {
    primary_intent = "self_reference_verified";
  } else if (signals.peer_tip) {
    primary_intent = "peer_tip_invited";
  } else if (signals.critique) {
    primary_intent = "contextual_disagreement";
  } else if (signals.humor) {
    primary_intent = "light_humor";
  } else if (signals.question) {
    primary_intent = "utility_fit_question";
  }

  return {
    text,
    primary_intent,
    labels,
    pragmatic:
      signals.acquisition_where ||
      signals.price_budget ||
      signals.utility_fit ||
      signals.request_more,
    teacher_posture: signals.teacher_posture,
    critique_first: signals.critique_first,
  };
}

export function loadCommentIntentPolicy(policyPath = DEFAULT_POLICY_PATH) {
  const policy = JSON.parse(fs.readFileSync(policyPath, "utf8"));
  if (policy.policy_version !== INTENT_POLICY_VERSION) {
    throw new Error(`Unexpected comment intent policy version: ${policy.policy_version}`);
  }
  return policy;
}

export function loadHumanApprovedCommentExamples(
  examplesPath = DEFAULT_HUMAN_APPROVED_EXAMPLES_PATH,
) {
  const corpus = JSON.parse(fs.readFileSync(examplesPath, "utf8"));
  if (corpus.intent_policy_version !== INTENT_POLICY_VERSION) {
    throw new Error(
      `Unexpected human-approved example policy version: ${corpus.intent_policy_version}`,
    );
  }
  if (corpus.review_status !== "user_approved") {
    throw new Error("Human-approved comment examples are not marked user_approved");
  }
  if (!Array.isArray(corpus.items) || corpus.items.length === 0) {
    throw new Error("Human-approved comment example corpus is empty");
  }
  return corpus;
}

export function humanApprovedExamplesForContext(
  {
    voiceId,
    directionId = "",
    topicIds = [],
    limit = 3,
  },
  corpus = loadHumanApprovedCommentExamples(),
) {
  const normalizedTopics = new Set(
    (Array.isArray(topicIds) ? topicIds : []).map(normalizeCommentText).filter(Boolean),
  );
  return corpus.items
    .filter((item) => item.voice_id === voiceId)
    .map((item) => ({
      item,
      score:
        (item.comment_direction_id === directionId ? 2 : 0) +
        ((item.topic_ids ?? []).some((topicId) => normalizedTopics.has(topicId)) ? 1 : 0),
    }))
    .sort((left, right) => right.score - left.score || left.item.id.localeCompare(right.item.id))
    .slice(0, Math.max(0, Number(limit) || 0))
    .map(({ item }) => ({
      example_id: item.id,
      voice_id: item.voice_id,
      interaction_intent: item.interaction_intent,
      comment_direction_id: item.comment_direction_id,
      topic_ids: item.topic_ids,
      draft: item.draft,
    }));
}

export function tachikomaInteractionModeForIntent(
  intent,
  policy = loadCommentIntentPolicy(),
) {
  const mode = policy.parent_intents?.[intent]?.tachikoma_interaction_mode;
  if (!mode) throw new Error(`Missing Tachikoma interaction mode for intent: ${intent}`);
  return mode;
}

export function classifyCommentTopics(value, policy = loadCommentIntentPolicy()) {
  const text = normalizeCommentText(value).toLowerCase();
  return Object.entries(policy.topics ?? {})
    .filter(([, topic]) =>
      (topic.keywords ?? []).some((keyword) =>
        text.includes(String(keyword).toLowerCase()),
      ),
    )
    .map(([topicId]) => topicId);
}

export function detailedDirection(directionId, policy = loadCommentIntentPolicy()) {
  return policy.directions?.[directionId] ?? null;
}

export function tachikomaInteractionModeForDirection(
  directionId,
  policy = loadCommentIntentPolicy(),
) {
  const direction = detailedDirection(directionId, policy);
  if (!direction) throw new Error(`Unknown detailed comment direction: ${directionId}`);
  return direction.interaction_mode;
}

function rolePolicy(policy, voiceId) {
  const role = policy.roles?.[voiceId];
  if (!role) throw new Error(`Missing comment intent role policy: ${voiceId}`);
  return role;
}

export function validateCommentDirection({
  text,
  voiceId,
  declaredIntent = "",
  declaredDirection = "",
  topicContext = "",
  declaredTopicIds = [],
  topicAlignmentVerified = false,
  sourceContextComplete = false,
  visibleDetailGrounded = false,
  firsthandVerified = false,
  adviceInvited = false,
  questionAlreadyAnswered = false,
  differenceBasisVerified = false,
  policy = loadCommentIntentPolicy(),
}) {
  const observed = classifyCommentIntent(text);
  const role = rolePolicy(policy, voiceId);
  const intent = normalizeCommentText(declaredIntent);
  const directionId = normalizeCommentText(declaredDirection);
  const direction = detailedDirection(directionId, policy);
  const inferredTopicIds = classifyCommentTopics(topicContext, policy);
  const normalizedDeclaredTopics = [...new Set(
    (Array.isArray(declaredTopicIds) ? declaredTopicIds : [])
      .map((value) => normalizeCommentText(value))
      .filter(Boolean),
  )];
  const topicIds = normalizedDeclaredTopics.length
    ? normalizedDeclaredTopics
    : inferredTopicIds;
  const reasons = [];

  if (!intent) reasons.push("生成前没有显式声明上位互动意图");
  else if (!INTENT_ORDER.includes(intent)) reasons.push("声明了不受支持的上位互动意图");
  if (!directionId) reasons.push("生成前没有显式声明20类细方向之一");
  else if (!direction) reasons.push("声明了未知的评论细方向");
  if (direction && direction.parent_intent !== intent) {
    reasons.push("细方向与上位互动意图不一致");
  }
  if (direction && !role.allowed_direction_ids.includes(directionId)) {
    reasons.push("该细方向不适合当前账号角色");
  }
  const unknownTopics = topicIds.filter((topicId) => !policy.topics?.[topicId]);
  if (!topicIds.length) reasons.push("没有识别或声明评论所对应的内容主题");
  if (unknownTopics.length) reasons.push("声明了未知的内容主题");
  if (
    normalizedDeclaredTopics.length &&
    inferredTopicIds.length &&
    !topicAlignmentVerified &&
    !normalizedDeclaredTopics.some((topicId) => inferredTopicIds.includes(topicId))
  ) {
    reasons.push("声明主题与原帖上下文不一致");
  }
  if (
    direction &&
    !direction.topic_ids.includes("*") &&
    !direction.topic_ids.some((topicId) => topicIds.includes(topicId))
  ) {
    reasons.push("评论细方向与原帖主题没有交集");
  }
  if (observed.teacher_posture) reasons.push("出现老师或评委式判卷口吻");
  if (observed.critique_first) reasons.push("以反驳、纠正或否定开头");
  if (
    ["self_reference_verified", "self_display_verified"].includes(intent) &&
    !firsthandVerified
  ) {
    reasons.push("自述或展示方向缺少真实经历验证");
  }
  if (intent === "peer_tip_invited" && !adviceInvited) {
    reasons.push("作者未征求建议，不应主动指导");
  }
  if (
    ["acquisition_question", "utility_fit_question", "request_more"].includes(intent) &&
    questionAlreadyAnswered
  ) {
    reasons.push("正文或可见评论已经回答，不能重复提问");
  }
  if (
    direction?.speech_act === "question" &&
    !observed.labels.includes("question") &&
    observed.primary_intent !== "request_more"
  ) {
    reasons.push("声明为提问方向，但草稿没有形成一个自然问题");
  }
  if (direction?.speech_act === "praise") {
    if (!visibleDetailGrounded) reasons.push("夸奖没有绑定原帖可见细节");
    if (!observed.labels.includes("praise")) {
      reasons.push("声明为夸奖方向，但草稿没有表达明确正向感受");
    }
  }
  if (direction?.requires?.includes("source_context_complete") && !sourceContextComplete) {
    reasons.push("该方向缺少完整正文和可见评论上下文");
  }
  if (directionId === "contextual_difference" && !differenceBasisVerified) {
    reasons.push("条件差异方向缺少真实依据");
  }

  return {
    passed: reasons.length === 0,
    intent,
    direction_id: directionId,
    direction_label: direction?.label ?? "",
    inferred_intent: observed.primary_intent,
    declared_intent: declaredIntent,
    topic_ids: topicIds,
    inferred_topic_ids: inferredTopicIds,
    voice_style_id: role.voice_style_id,
    voice_contract: role.voice_contract,
    direction_contract: direction,
    pragmatic: observed.pragmatic,
    labels: observed.labels,
    reasons,
    policy_version: policy.policy_version,
    interaction_mode: direction?.interaction_mode ?? null,
  };
}

export function chooseCommentIntent({
  voiceId,
  sequenceIndex = 0,
  availableIntents = [],
  policy = loadCommentIntentPolicy(),
}) {
  const role = rolePolicy(policy, voiceId);
  const sequence = role.direction_sequence.map(
    (directionId) => policy.directions[directionId].parent_intent,
  );
  const allowed = availableIntents.length
    ? sequence.filter((intent) => availableIntents.includes(intent))
    : sequence;
  if (!allowed.length) throw new Error(`No available comment intent for ${voiceId}`);
  return allowed[Math.abs(Number(sequenceIndex) || 0) % allowed.length];
}

export function chooseDetailedDirection({
  voiceId,
  sequenceIndex = 0,
  topicIds = [],
  availableDirectionIds = [],
  policy = loadCommentIntentPolicy(),
}) {
  const role = rolePolicy(policy, voiceId);
  const topics = new Set(topicIds);
  const candidates = role.direction_sequence.filter((directionId) => {
    const direction = detailedDirection(directionId, policy);
    if (!direction) return false;
    if (availableDirectionIds.length && !availableDirectionIds.includes(directionId)) return false;
    return direction.topic_ids.includes("*") || direction.topic_ids.some((id) => topics.has(id));
  });
  if (!candidates.length) {
    throw new Error(`No topic-compatible detailed direction for ${voiceId}`);
  }
  return candidates[Math.abs(Number(sequenceIndex) || 0) % candidates.length];
}
