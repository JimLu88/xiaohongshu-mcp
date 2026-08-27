import assert from "node:assert/strict";
import {
  chooseDetailedDirection,
  classifyCommentIntent,
  classifyCommentTopics,
  loadCommentIntentPolicy,
  tachikomaInteractionModeForDirection,
  tachikomaInteractionModeForIntent,
  validateCommentDirection,
} from "./lib/xhs_comment_intent_policy.mjs";

const policy = loadCommentIntentPolicy();
assert.equal(policy.source_sample_count, 600);
assert.equal(policy.architecture.parent_intent_count, 10);
assert.equal(Object.keys(policy.directions).length, 20);
assert.equal(Object.keys(policy.topics).length, 14);
assert.equal(policy.architecture.voice_style_count, 6);
assert.equal(
  tachikomaInteractionModeForIntent("acquisition_question", policy),
  "curiosity_question",
);
assert.equal(
  tachikomaInteractionModeForDirection("detail_grounded_praise", policy),
  "support_only",
);

assert.ok(classifyCommentTopics("餐桌旁边只剩85厘米过道").includes("layout_circulation"));
assert.ok(classifyCommentTopics("白墙和木色在朝北房间里").includes("color_light_atmosphere"));
assert.equal(
  classifyCommentIntent("这款餐桌哪里买呀，多少钱？").primary_intent,
  "acquisition_question",
);

const purchaseQuestion = validateCommentDirection({
  text: "这张桌子是哪个型号呀，线上能买到吗？",
  voiceId: "evaluation_judgment",
  declaredIntent: "acquisition_question",
  declaredDirection: "acquisition_channel_question",
  topicContext: "实木餐桌购买渠道和型号",
  declaredTopicIds: ["purchase_service"],
  sourceContextComplete: true,
  policy,
});
assert.equal(purchaseQuestion.passed, true);
assert.equal(purchaseQuestion.voice_style_id, "practical_purchase_peer");

const spaceQuestion = validateCommentDirection({
  text: "柜门全打开以后，过道还能剩多少厘米呀？",
  voiceId: "space_advisor",
  declaredIntent: "utility_fit_question",
  declaredDirection: "size_clearance_question",
  topicContext: "餐边柜尺寸、柜深和过道净宽",
  declaredTopicIds: ["dimensions_fit"],
  sourceContextComplete: true,
  policy,
});
assert.equal(spaceQuestion.passed, true);
assert.equal(spaceQuestion.interaction_mode, "curiosity_question");

const praise = validateCommentDirection({
  text: "窗边这块木色被下午光照得真好看。",
  voiceId: "stylist",
  declaredIntent: "grounded_praise",
  declaredDirection: "atmosphere_grounded_praise",
  topicContext: "白墙、木色、窗边采光和空间氛围",
  declaredTopicIds: ["color_light_atmosphere"],
  visibleDetailGrounded: true,
  sourceContextComplete: true,
  policy,
});
assert.equal(praise.passed, true);
assert.equal(praise.interaction_mode, "support_only");

const wrongRole = validateCommentDirection({
  text: "这个榫接具体是什么结构呀？",
  voiceId: "stylist",
  declaredIntent: "utility_fit_question",
  declaredDirection: "product_identity_material_question",
  topicContext: "木作榫接结构",
  declaredTopicIds: ["material_craft"],
  sourceContextComplete: true,
  policy,
});
assert.equal(wrongRole.passed, false);
assert.ok(wrongRole.reasons.includes("该细方向不适合当前账号角色"));

const wrongTopic = validateCommentDirection({
  text: "柜门全打开后过道还剩多少呀？",
  voiceId: "space_advisor",
  declaredIntent: "utility_fit_question",
  declaredDirection: "size_clearance_question",
  topicContext: "白墙和木色搭配",
  declaredTopicIds: ["color_light_atmosphere"],
  sourceContextComplete: true,
  policy,
});
assert.equal(wrongTopic.passed, false);
assert.ok(wrongTopic.reasons.includes("评论细方向与原帖主题没有交集"));

const missingDeclarations = validateCommentDirection({
  text: "挺好看的。",
  voiceId: "stylist",
  topicContext: "客厅木色搭配",
  visibleDetailGrounded: true,
  sourceContextComplete: true,
  policy,
});
assert.equal(missingDeclarations.passed, false);
assert.ok(missingDeclarations.reasons.includes("生成前没有显式声明20类细方向之一"));

const teacher = validateCommentDirection({
  text: "真正关键的是通道尺寸，你应该先量完再发。",
  voiceId: "space_advisor",
  declaredIntent: "peer_tip_invited",
  declaredDirection: "invited_peer_tip",
  topicContext: "小户型通道尺寸求助",
  declaredTopicIds: ["layout_circulation"],
  topicAlignmentVerified: true,
  adviceInvited: true,
  sourceContextComplete: true,
  policy,
});
assert.equal(teacher.passed, false);
assert.ok(teacher.reasons.includes("出现老师或评委式判卷口吻"));

const fakeExperience = validateCommentDirection({
  text: "我家也买了同款，确实比这个更实用。",
  voiceId: "stylist",
  declaredIntent: "self_display_verified",
  declaredDirection: "verified_self_display",
  topicContext: "小户型家具使用",
  declaredTopicIds: ["household_constraints"],
  firsthandVerified: false,
  sourceContextComplete: true,
  policy,
});
assert.equal(fakeExperience.passed, false);
assert.ok(fakeExperience.reasons.includes("自述或展示方向缺少真实经历验证"));

const repeatedQuestion = validateCommentDirection({
  text: "这款椅子哪里买呀？",
  voiceId: "global_design_observer",
  declaredIntent: "acquisition_question",
  declaredDirection: "acquisition_channel_question",
  topicContext: "国外经典椅子的品牌和购买渠道",
  declaredTopicIds: ["purchase_service", "global_localization"],
  questionAlreadyAnswered: true,
  sourceContextComplete: true,
  policy,
});
assert.equal(repeatedQuestion.passed, false);

const unsolicitedTip = validateCommentDirection({
  text: "可以先把茶几撤掉试一周。",
  voiceId: "evaluation_judgment",
  declaredIntent: "peer_tip_invited",
  declaredDirection: "invited_peer_tip",
  topicContext: "客厅家具取舍",
  declaredTopicIds: ["layout_circulation"],
  adviceInvited: false,
  sourceContextComplete: true,
  policy,
});
assert.equal(unsolicitedTip.passed, false);

const unsupportedDifference = validateCommentDirection({
  text: "这个做法很好看，不过放到潮湿地区可能要换一种维护方式。",
  voiceId: "global_design_observer",
  declaredIntent: "contextual_disagreement",
  declaredDirection: "contextual_difference",
  topicContext: "海外木家具在不同气候的适配",
  declaredTopicIds: ["global_localization", "maintenance_lifetime"],
  differenceBasisVerified: false,
  sourceContextComplete: true,
  policy,
});
assert.equal(unsupportedDifference.passed, false);

const selected = chooseDetailedDirection({
  voiceId: "space_advisor",
  topicIds: ["dimensions_fit"],
  sequenceIndex: 0,
  policy,
});
assert.equal(selected, "size_clearance_question");
assert.notEqual(
  policy.roles.stylist.voice_style_id,
  policy.roles.evaluation_judgment.voice_style_id,
);
assert.notDeepEqual(
  policy.roles.stylist.voice_contract,
  policy.roles.global_design_observer.voice_contract,
);
assert.ok(
  Object.values(policy.directions).every(
    (direction) => direction.logic_shape && direction.tone && direction.interaction_mode,
  ),
);

process.stdout.write(`${JSON.stringify({ passed: true, tests: 29 }, null, 2)}\n`);
