import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  chooseDetailedDirection,
  classifyCommentTopics,
  humanApprovedExamplesForContext,
  loadCommentIntentPolicy,
} from "./lib/xhs_comment_intent_policy.mjs";

export function planCommentDirection(payload, policy = loadCommentIntentPolicy()) {
  const voiceId = String(payload?.voice_id ?? "").trim();
  const role = policy.roles?.[voiceId];
  if (!role) throw new Error(`Unknown Xiaohongshu comment voice: ${voiceId}`);

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

  const availableDirectionIds = role.allowed_direction_ids.filter((directionId) => {
    const direction = policy.directions[directionId];
    if (direction.requires.includes("firsthand_verified") && payload?.firsthand_verified !== true) return false;
    if (direction.requires.includes("advice_invited") && payload?.advice_invited !== true) return false;
    if (direction.requires.includes("difference_basis_verified") && payload?.difference_basis_verified !== true) return false;
    if (direction.requires.includes("visible_detail_grounded") && payload?.visible_detail_grounded !== true) return false;
    if (direction.speech_act === "question" && payload?.question_already_answered === true) return false;
    return true;
  });

  const directionId = chooseDetailedDirection({
    voiceId,
    sequenceIndex: payload?.sequence_index ?? 0,
    topicIds,
    availableDirectionIds,
    policy,
  });
  const direction = policy.directions[directionId];
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
    character_range: direction.character_range,
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
