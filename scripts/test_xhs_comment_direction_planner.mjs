import assert from "node:assert/strict";
import { planCommentDirection } from "./plan_xhs_comment_direction.mjs";

const space = planCommentDirection({
  voice_id: "space_advisor",
  topic_context: "餐边柜尺寸和过道净宽",
  sequence_index: 0,
});
assert.equal(space.comment_direction_id, "size_clearance_question");
assert.equal(space.interaction_intent, "utility_fit_question");
assert.equal(space.human_approved_example_set_version, "panse-xhs-human-approved-comments.v3");
assert.equal(space.human_approved_style_examples.length, 3);
assert.ok(space.human_approved_style_examples.every((item) => item.voice_id === "space_advisor"));

const stylist = planCommentDirection({
  voice_id: "stylist",
  topic_context: "白墙、木色和下午采光",
  sequence_index: 0,
});
assert.equal(stylist.comment_direction_id, "color_light_fit_question");
assert.equal(stylist.voice_style_id, "warm_home_companion");

const buyer = planCommentDirection({
  voice_id: "evaluation_judgment",
  topic_context: "这款柜子的价格和预算",
  sequence_index: 0,
});
assert.equal(buyer.comment_direction_id, "price_budget_question");

const global = planCommentDirection({
  voice_id: "global_design_observer",
  topic_context: "海外家具放到国内湿度和户型怎么适配",
  sequence_index: 0,
});
assert.equal(global.comment_direction_id, "global_localization_question");

const noFirsthand = planCommentDirection({
  voice_id: "stylist",
  topic_ids: ["household_constraints"],
  sequence_index: 15,
  firsthand_verified: false,
});
assert.notEqual(noFirsthand.comment_direction_id, "verified_same_situation");
assert.notEqual(noFirsthand.comment_direction_id, "verified_self_display");

assert.throws(
  () => planCommentDirection({ voice_id: "space_advisor", topic_context: "完全无关文本" }),
  /No recognized topic/,
);
assert.equal(space.publish_allowed, false);
assert.equal(space.human_review_required, true);

process.stdout.write(`${JSON.stringify({ passed: true, tests: 13 }, null, 2)}\n`);
