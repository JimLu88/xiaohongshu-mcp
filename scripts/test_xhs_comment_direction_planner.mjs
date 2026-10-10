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

const slot2Assignments = Array.from({ length: 15 }, (_, index) => {
  const itemIndex = index + 1;
  const tierId = itemIndex <= 3
    ? "very_short"
    : itemIndex <= 5
      ? "short"
      : itemIndex <= 10
        ? "medium"
        : "long";
  const ranges = {
    very_short: [3, 5],
    short: [6, 16],
    medium: [17, 30],
    long: [31, 45],
  };
  return {
    policy_id: "panse-xhs-comment-length-mix.v1",
    batch_id: "slot-2-synthetic-15",
    batch_size: 15,
    item_index: itemIndex,
    tier_id: tierId,
    minimum_chars: ranges[tierId][0],
    maximum_chars: ranges[tierId][1],
  };
});
const slot2Plans = slot2Assignments.map((assignment, index) =>
  planCommentDirection({
    voice_id: "stylist",
    topic_context: "白墙、木色和下午采光",
    sequence_index: index,
    visible_detail_grounded: true,
    comment_length_assignment: assignment,
  }));
assert.ok(slot2Plans.slice(0, 3).every((plan) =>
  plan.comment_direction_id === "light_social_response" &&
  plan.length_tier_override_applied === true &&
  plan.character_range.minimum === 3 &&
  plan.character_range.maximum === 5));
assert.ok(slot2Plans.every((plan, index) =>
  plan.character_range.minimum <= slot2Assignments[index].maximum_chars &&
  plan.character_range.maximum >= slot2Assignments[index].minimum_chars));

const slot4Assignments = Array.from({ length: 14 }, (_, index) => {
  const itemIndex = index + 1;
  const tierId = itemIndex <= 2
    ? "very_short"
    : itemIndex <= 4
      ? "short"
      : itemIndex <= 9
        ? "medium"
        : "long";
  const ranges = {
    very_short: [3, 5],
    short: [6, 16],
    medium: [17, 30],
    long: [31, 45],
  };
  return {
    policy_id: "panse-xhs-comment-length-mix.v1",
    batch_id: "slot4-14",
    batch_size: 14,
    item_index: itemIndex,
    tier_id: tierId,
    minimum_chars: ranges[tierId][0],
    maximum_chars: ranges[tierId][1],
  };
});
const slot4Plans = slot4Assignments.map((assignment, index) =>
  planCommentDirection({
    voice_id: "space_advisor",
    topic_ids: ["layout_circulation"],
    sequence_index: index,
    question_already_answered: false,
    comment_length_assignment: assignment,
  }));
assert.ok(slot4Plans.slice(0, 2).every((plan) =>
  plan.comment_direction_id === "layout_circulation_question" &&
  plan.length_tier_override_applied === true &&
  plan.character_range.minimum === 3 &&
  plan.character_range.maximum === 5));
assert.ok(slot4Plans.slice(2, 4).every((plan) =>
  plan.comment_direction_id === "layout_circulation_question" &&
  plan.length_tier_override_applied === true &&
  plan.character_range.minimum === 6 &&
  plan.character_range.maximum === 16));
assert.ok(slot4Plans.every((plan, index) =>
  plan.character_range.minimum <= slot4Assignments[index].maximum_chars &&
  plan.character_range.maximum >= slot4Assignments[index].minimum_chars));
assert.deepEqual(
  slot4Assignments.reduce((counts, item) => {
    counts[item.tier_id] += 1;
    return counts;
  }, { very_short: 0, short: 0, medium: 0, long: 0 }),
  { very_short: 2, short: 2, medium: 5, long: 5 },
);

const buyer = planCommentDirection({
  voice_id: "evaluation_judgment",
  topic_context: "这款柜子的价格和预算",
  sequence_index: 0,
});
assert.equal(buyer.comment_direction_id, "price_budget_question");
const slot3VeryShort = planCommentDirection({
  voice_id: "evaluation_judgment",
  topic_ids: ["dimensions_fit"],
  sequence_index: 0,
  question_already_answered: false,
  comment_length_assignment: {
    policy_id: "panse-xhs-comment-length-mix.v1",
    batch_id: "slot3-7",
    batch_size: 7,
    item_index: 1,
    tier_id: "very_short",
    minimum_chars: 3,
    maximum_chars: 5,
  },
});
assert.equal(slot3VeryShort.comment_direction_id, "size_clearance_question");
assert.deepEqual(slot3VeryShort.character_range, { minimum: 3, maximum: 5 });
assert.equal(slot3VeryShort.length_tier_override_applied, true);
const slot3Short = planCommentDirection({
  voice_id: "evaluation_judgment",
  topic_ids: ["dimensions_fit"],
  sequence_index: 0,
  question_already_answered: false,
  comment_length_assignment: {
    policy_id: "panse-xhs-comment-length-mix.v1",
    batch_id: "slot3-7",
    batch_size: 7,
    item_index: 2,
    tier_id: "short",
    minimum_chars: 6,
    maximum_chars: 16,
  },
});
assert.equal(slot3Short.comment_direction_id, "size_clearance_question");
assert.deepEqual(slot3Short.character_range, { minimum: 6, maximum: 16 });
assert.equal(slot3Short.length_tier_override_applied, true);
assert.throws(
  () => planCommentDirection({
    voice_id: "evaluation_judgment",
    topic_ids: ["budget_value"],
    sequence_index: 0,
    comment_length_assignment: slot4Assignments[0],
  }),
  /No topic-compatible detailed direction/,
);

const global = planCommentDirection({
  voice_id: "global_design_observer",
  topic_context: "海外家具放到国内湿度和户型怎么适配",
  sequence_index: 0,
});
assert.equal(global.comment_direction_id, "global_localization_question");

const slot5Assignments = Array.from({ length: 10 }, (_, index) => {
  const itemIndex = index + 1;
  const tierId = itemIndex <= 2
    ? "very_short"
    : itemIndex <= 4
      ? "short"
      : itemIndex <= 7
        ? "medium"
        : "long";
  const ranges = {
    very_short: [3, 5],
    short: [6, 16],
    medium: [17, 30],
    long: [31, 45],
  };
  return {
    policy_id: "panse-xhs-comment-length-mix.v1",
    batch_id: "slot5-10",
    batch_size: 10,
    item_index: itemIndex,
    tier_id: tierId,
    minimum_chars: ranges[tierId][0],
    maximum_chars: ranges[tierId][1],
  };
});
const slot5Plans = slot5Assignments.map((assignment, index) =>
  planCommentDirection({
    voice_id: "global_design_observer",
    topic_ids: ["dimensions_fit"],
    sequence_index: index,
    visible_detail_grounded: true,
    comment_length_assignment: assignment,
  }));
assert.ok(slot5Plans.slice(0, 2).every((plan) =>
  plan.comment_direction_id === "detail_grounded_praise" &&
  plan.length_tier_override_applied === true &&
  plan.character_range.minimum === 3 &&
  plan.character_range.maximum === 5));
assert.ok(slot5Plans.slice(2, 4).every((plan) =>
  plan.comment_direction_id === "detail_grounded_praise" &&
  plan.length_tier_override_applied === true &&
  plan.character_range.minimum === 6 &&
  plan.character_range.maximum === 16));
assert.ok(slot5Plans.every((plan, index) =>
  plan.character_range.minimum <= slot5Assignments[index].maximum_chars &&
  plan.character_range.maximum >= slot5Assignments[index].minimum_chars));
assert.deepEqual(
  slot5Assignments.reduce((counts, item) => {
    counts[item.tier_id] += 1;
    return counts;
  }, { very_short: 0, short: 0, medium: 0, long: 0 }),
  { very_short: 2, short: 2, medium: 3, long: 3 },
);

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

process.stdout.write(`${JSON.stringify({ passed: true, tests: 25 }, null, 2)}\n`);
