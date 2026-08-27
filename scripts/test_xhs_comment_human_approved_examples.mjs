import assert from "node:assert/strict";
import {
  humanApprovedExamplesForContext,
  loadCommentIntentPolicy,
  loadHumanApprovedCommentExamples,
  validateCommentDirection,
} from "./lib/xhs_comment_intent_policy.mjs";

const policy = loadCommentIntentPolicy();
const corpus = loadHumanApprovedCommentExamples();
const expectedRoles = [
  "stylist",
  "evaluation_judgment",
  "space_advisor",
  "global_design_observer",
];
const forbiddenNaturalnessFragments = [
  "\u90a3\u7ec4",
  "\u5c24\u5176",
  "真正",
  "关键是",
  "你应该",
  "必须",
  "建议你",
  "值得参考",
  "更值得参考",
  "我家也",
  "我买过",
  "我用过",
  "亲测",
  "畔色",
  "私信",
  "关注",
  "主页",
];

assert.equal(corpus.example_set_version, "panse-xhs-human-approved-comments.v3");
assert.equal(corpus.review_status, "user_approved");
assert.equal(corpus.publish_allowed, false);
assert.equal(corpus.items.length, 15);

const expectedRoleCounts = {
  stylist: 3,
  evaluation_judgment: 3,
  space_advisor: 3,
  global_design_observer: 6,
};

for (const role of expectedRoles) {
  const roleItems = corpus.items.filter((item) => item.voice_id === role);
  assert.equal(
    roleItems.length,
    expectedRoleCounts[role],
    `${role} has an unexpected approved example count`,
  );
  const selected = humanApprovedExamplesForContext({
    voiceId: role,
    directionId: roleItems[0].comment_direction_id,
    topicIds: roleItems[0].topic_ids,
    limit: 3,
  }, corpus);
  assert.equal(selected.length, 3);
  assert.equal(selected[0].example_id, roleItems[0].id);
}

for (const item of corpus.items) {
  const result = validateCommentDirection({
    text: item.draft,
    voiceId: item.voice_id,
    declaredIntent: item.interaction_intent,
    declaredDirection: item.comment_direction_id,
    topicContext: `${item.title} ${(item.topic_ids ?? []).join(" ")}`,
    declaredTopicIds: item.topic_ids,
    topicAlignmentVerified: true,
    sourceContextComplete: item.source_context_complete === true,
    visibleDetailGrounded: item.visible_detail_grounded === true,
    questionAlreadyAnswered: item.question_already_answered === true,
    policy,
  });
  assert.equal(result.passed, true, `${item.id}: ${result.reasons.join("; ")}`);
  const range = policy.directions[item.comment_direction_id].character_range;
  assert.ok(item.draft.length >= range.minimum, `${item.id} is too short`);
  assert.ok(item.draft.length <= range.maximum, `${item.id} is too long`);
  assert.ok(
    forbiddenNaturalnessFragments.every((fragment) => !item.draft.includes(fragment)),
    `${item.id} contains a forbidden naturalness fragment`,
  );
}

process.stdout.write(`${JSON.stringify({
  passed: true,
  example_set_version: corpus.example_set_version,
  examples: corpus.items.length,
  roles: expectedRoles.length,
  publish_allowed: corpus.publish_allowed,
}, null, 2)}\n`);
