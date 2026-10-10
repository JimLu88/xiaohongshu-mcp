import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  chooseDetailedDirection,
  classifyCommentTopics,
  humanApprovedExamplesForContext,
  loadCommentIntentPolicy,
} from "./lib/xhs_comment_intent_policy.mjs";

const LENGTH_POLICY_ID = "panse-xhs-comment-length-mix.v1";
const LENGTH_TIERS = {
  very_short: { minimum: 3, maximum: 5 },
  short: { minimum: 6, maximum: 16 },
  medium: { minimum: 17, maximum: 30 },
  long: { minimum: 31, maximum: 45 },
};

function normalizeLengthAssignment(value) {
  if (value == null) return null;
  if (typeof value !== "object" || Array.isArray(value)) {
    throw new Error("comment_length_assignment must be a governed assignment object");
  }
  if (value.policy_id !== LENGTH_POLICY_ID) {
    throw new Error("comment length assignment policy mismatch");
  }
  const tierId = String(value.tier_id ?? "").trim();
  const tier = LENGTH_TIERS[tierId];
  if (!tier) throw new Error("comment length assignment has an unknown tier");
  if (
    Number(value.minimum_chars) !== tier.minimum ||
    Number(value.maximum_chars) !== tier.maximum
  ) {
    throw new Error("comment length assignment range drifted from the active policy");
  }
  return { ...value, tier_id: tierId };
}

function directionLengthContract(role, directionId, policy, lengthAssignment) {
  const direction = policy.directions[directionId];
  const baseRange = direction.character_range;
  if (!lengthAssignment) {
    return { character_range: baseRange, length_tier_override_applied: false };
  }
  const tier = LENGTH_TIERS[lengthAssignment.tier_id];
  const override = role.length_tier_direction_overrides?.[lengthAssignment.tier_id];
  if (override && !override.allowed_direction_ids?.includes(directionId)) {
    return null;
  }
  const overrideRange = override?.allowed_direction_ids?.includes(directionId)
    ? override.direction_ranges?.[directionId]
    : null;
  const effectiveRange = overrideRange ?? baseRange;
  const overlaps =
    Number(effectiveRange.minimum) <= tier.maximum &&
    Number(effectiveRange.maximum) >= tier.minimum;
  if (!overlaps) return null;
  return {
    character_range: effectiveRange,
    base_character_range: baseRange,
    length_tier_override_applied: Boolean(overrideRange),
    length_tier_override: overrideRange
      ? {
          tier_id: lengthAssignment.tier_id,
          direction_id: directionId,
          requires: override.requires,
          generation_instruction: override.generation_instruction,
        }
      : null,
  };
}

export function planCommentDirection(payload, policy = loadCommentIntentPolicy()) {
  const voiceId = String(payload?.voice_id ?? "").trim();
  const role = policy.roles?.[voiceId];
  if (!role) throw new Error(`Unknown Xiaohongshu comment voice: ${voiceId}`);
  const lengthAssignment = normalizeLengthAssignment(payload?.comment_length_assignment);

  const declaredTopicIds = Array.isArray(payload?.topic_ids)
    ? [...new Set(payload.topic_ids.map(String).map((value) => value.trim()).filter(Boolean))]
    : [];
  const topicIds = declaredTopicIds.length
    ? declaredTopicIds
    : classifyCommentTopics(payload?.topic_context ?? "", policy);
  if (!topicIds.length) {
    throw new Error("No recognized topic; read more of the note before choosing a direction");
  }
  if (topicIds.some((topicId) => !policy.topics[topicId])) {
    throw new Error("One or more topic_ids are unknown");
  }

  const lengthContracts = new Map();
  const availableDirectionIds = role.allowed_direction_ids.filter((directionId) => {
    const direction = policy.directions[directionId];
    if (direction.requires.includes("firsthand_verified") && payload?.firsthand_verified !== true) return false;
    if (direction.requires.includes("advice_invited") && payload?.advice_invited !== true) return false;
    if (direction.requires.includes("difference_basis_verified") && payload?.difference_basis_verified !== true) return false;
    if (direction.requires.includes("visible_detail_grounded") && payload?.visible_detail_grounded !== true) return false;
    if (direction.speech_act === "question" && payload?.question_already_answered === true) return false;
    const lengthContract = directionLengthContract(
      role,
      directionId,
      policy,
      lengthAssignment,
    );
    if (!lengthContract) return false;
    lengthContracts.set(directionId, lengthContract);
    return true;
  });
  if (lengthAssignment && !availableDirectionIds.length) {
    throw new Error(
      `No length-compatible detailed direction for ${voiceId} and ${lengthAssignment.tier_id}`,
    );
  }

  const directionId = chooseDetailedDirection({
    voiceId,
    sequenceIndex: payload?.sequence_index ?? 0,
    topicIds,
    availableDirectionIds,
    policy,
  });
  const direction = policy.directions[directionId];
  const lengthContract = lengthContracts.get(directionId) ?? directionLengthContract(
    role,
    directionId,
    policy,
    lengthAssignment,
  );
  const humanApprovedStyleExamples = humanApprovedExamplesForContext({
    voiceId,
    directionId,
    topicIds,
    limit: 3,
  });
  return {
    passed: true,
    policy_version: policy.policy_version,
    voice_id: voiceId,
    voice_style_id: role.voice_style_id,
    topic_ids: topicIds,
    comment_direction_id: directionId,
    interaction_intent: direction.parent_intent,
    interaction_mode: direction.interaction_mode,
    logic_shape: direction.logic_shape,
    tone: direction.tone,
    character_range: lengthContract.character_range,
    base_character_range: lengthContract.base_character_range ?? direction.character_range,
    length_tier_override_applied: lengthContract.length_tier_override_applied,
    length_tier_override: lengthContract.length_tier_override,
    comment_length_assignment: lengthAssignment,
    sentence_range: direction.sentence_range,
    human_approved_example_set_version:
      policy.human_approved_style_reference?.example_set_version ?? null,
    human_approved_style_examples: humanApprovedStyleExamples,
    human_approved_examples_usage:
      "只校准语气和互动方式；不得复制样本事实或措辞，当前原帖仍是唯一内容依据。",
    panse_intent_context: {
      policy_version: policy.policy_version,
      voice_id: voiceId,
      interaction_intent: direction.parent_intent,
      comment_direction_id: directionId,
      topic_ids: topicIds,
    },
    publish_allowed: false,
    human_review_required: true,
  };
}

function readPayload(arg) {
  if (arg === "-") return JSON.parse(fs.readFileSync(0, "utf8"));
  return JSON.parse(fs.readFileSync(path.resolve(arg), "utf8"));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const input = process.argv[2];
  if (!input) throw new Error("Usage: node plan_xhs_comment_direction.mjs <input.json|->");
  process.stdout.write(`${JSON.stringify(planCommentDirection(readPayload(input)), null, 2)}\n`);
}
