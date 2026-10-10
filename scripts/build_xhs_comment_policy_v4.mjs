import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  DIRECTIONS,
  POLICY_VERSION,
  ROLE_DIRECTIONS,
  TOPICS,
  publicPolicyShape,
} from "./lib/xhs_comment_direction_taxonomy_v4.mjs";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(SCRIPT_DIR, "..");
const RESEARCH = path.join(REPO, "research", "panse_multi_direction");
const parentPolicyPath = path.join(RESEARCH, "xhs_comment_intent_policy_v3.json");
const outputPath = path.join(RESEARCH, "xhs_comment_intent_policy_v4.json");

const parentPolicy = JSON.parse(fs.readFileSync(parentPolicyPath, "utf8"));
const taxonomy = publicPolicyShape();
const parentIntentIds = Object.keys(parentPolicy.tachikoma_interaction_mode_map);

const policy = {
  schema_version: 4,
  policy_version: POLICY_VERSION,
  created_at: "2026-08-09",
  supersedes: parentPolicy.policy_version,
  source_corpus: parentPolicy.source_corpus,
  source_analysis: parentPolicy.source_analysis,
  source_sample_count: parentPolicy.source_sample_count,
  architecture: {
    model: "topic -> voice -> detailed_direction -> parent_intent -> tachikoma_interaction_mode -> style_generation -> bound_receipt",
    parent_intent_count: parentIntentIds.length,
    detailed_direction_count: Object.keys(DIRECTIONS).length,
    topic_count: Object.keys(TOPICS).length,
    voice_style_count: Object.keys(ROLE_DIRECTIONS).length,
    rationale: "Ten parent intents remain for compatibility; twenty detailed directions are the executable unit. Topic and voice must both match before drafting.",
  },
  selection_rule: "Declare one recognized topic, one account voice and one compatible detailed direction before drafting. Derive the parent intent and Tachikoma interaction mode; never infer missing declarations at the generation gate.",
  parent_intents: Object.fromEntries(
    parentIntentIds.map((intent) => [
      intent,
      { tachikoma_interaction_mode: parentPolicy.tachikoma_interaction_mode_map[intent] },
    ]),
  ),
  hard_rules: {
    declared_topic_required_before_generation: true,
    declared_detailed_direction_required_before_generation: true,
    declared_parent_intent_required_before_generation: true,
    topic_direction_intersection_required: true,
    voice_direction_permission_required: true,
    source_grounded_praise_required: true,
    unanswered_question_required: true,
    teacher_or_judge_posture_forbidden: true,
    critique_first_forbidden: true,
    advice_requires_author_invitation: true,
    self_reference_requires_verified_firsthand: true,
    self_display_requires_verified_firsthand: true,
    contextual_difference_requires_verified_basis: true,
    one_comment_one_primary_speech_act: true,
    category_balancing_against_observed_corpus_forbidden: true,
    human_review_required: true,
    role_scoped_length_override_requires_verified_contracts: true,
  },
  topics: taxonomy.topics,
  directions: taxonomy.directions,
  roles: Object.fromEntries(
    Object.entries(taxonomy.roles).map(([voiceId, role]) => [
      voiceId,
      {
        ...role,
        observed_parent_intent_shares:
          parentPolicy.roles?.[voiceId]?.observed_intent_shares ?? {},
      },
    ]),
  ),
  receipt_binding: {
    required_fields: [
      "intent_policy_version",
      "comment_direction_id",
      "interaction_intent",
      "topic_ids",
      "voice_style_id",
      "interaction_mode",
    ],
  },
  human_approved_style_reference: {
    example_set_version: "panse-xhs-human-approved-comments.v3",
    path: "research/panse_multi_direction/comment_drafts_review_15_2026-08-10.json",
    approved_at: "2026-08-11",
    approved_count: 15,
    roles: [
      "stylist",
      "evaluation_judgment",
      "space_advisor",
      "global_design_observer",
    ],
    usage: "Calibrate voice, speech act and naturalness only. Current source context remains the sole content authority; copying facts or wording is forbidden.",
    inject_into_style_preflight: true,
  },
  publish_allowed: false,
  human_review_required: true,
};

if (policy.architecture.detailed_direction_count !== 20) {
  throw new Error(`Expected 20 detailed directions, got ${policy.architecture.detailed_direction_count}`);
}
if (policy.architecture.topic_count !== 14) {
  throw new Error(`Expected 14 topics, got ${policy.architecture.topic_count}`);
}
for (const [voiceId, role] of Object.entries(policy.roles)) {
  for (const directionId of role.allowed_direction_ids) {
    if (!policy.directions[directionId]) {
      throw new Error(`${voiceId} references unknown direction ${directionId}`);
    }
  }
  if (role.direction_sequence.some((id) => !role.allowed_direction_ids.includes(id))) {
    throw new Error(`${voiceId} sequence contains a forbidden direction`);
  }
  if (role.direction_sequence.length !== 20) {
    throw new Error(`${voiceId} must have a 20-step direction cycle`);
  }
  if (!role.voice_style_id || !role.voice_contract?.default_logic) {
    throw new Error(`${voiceId} is missing an enforceable voice contract`);
  }
  for (const [tierId, override] of Object.entries(role.length_tier_direction_overrides ?? {})) {
    const supportedContracts = {
      "official_explanation:very_short": {
        directionId: "light_social_response", minimum: 3, maximum: 5,
      },
      "stylist:very_short": {
        directionId: "light_social_response", minimum: 3, maximum: 5,
      },
      "evaluation_judgment:very_short": {
        directionId: "size_clearance_question", minimum: 3, maximum: 5,
      },
      "evaluation_judgment:short": {
        directionId: "size_clearance_question", minimum: 6, maximum: 16,
      },
      "space_advisor:very_short": {
        directionId: "layout_circulation_question", minimum: 3, maximum: 5,
      },
      "space_advisor:short": {
        directionId: "layout_circulation_question", minimum: 6, maximum: 16,
      },
      "global_design_observer:very_short": {
        directionId: "detail_grounded_praise", minimum: 3, maximum: 5,
      },
      "global_design_observer:short": {
        directionId: "detail_grounded_praise", minimum: 6, maximum: 16,
      },
    };
    const supportedContract = supportedContracts[`${voiceId}:${tierId}`];
    if (!supportedContract) {
      throw new Error(`${voiceId} has an unsupported role-scoped length override`);
    }
    const { directionId: supportedDirection, minimum, maximum } = supportedContract;
    if (
      JSON.stringify(override.allowed_direction_ids) !== JSON.stringify([supportedDirection]) ||
      override.direction_ranges?.[supportedDirection]?.minimum !== minimum ||
      override.direction_ranges?.[supportedDirection]?.maximum !== maximum
    ) {
      throw new Error(
        `${voiceId} ${tierId} override must remain ${supportedDirection} ${minimum}-${maximum} only`,
      );
    }
    const requiredContracts = voiceId === "official_explanation"
      ? [
          "official_topic_context_verified",
          "official_professional_value_context_verified",
          "source_context_complete",
        ]
      : [
          "production_taxonomy_verified",
          "single_primary_speech_act_verified",
          "source_context_complete",
        ];
    for (const required of requiredContracts) {
      if (!override.requires?.includes(required)) {
        throw new Error(`${voiceId} ${tierId} override is missing ${required}`);
      }
    }
    if (
      voiceId === "global_design_observer" &&
      !override.requires?.includes("global_case_boundary_verified")
    ) {
      throw new Error(
        `${voiceId} ${tierId} override is missing global_case_boundary_verified`,
      );
    }
  }
}
for (const [directionId, direction] of Object.entries(policy.directions)) {
  if (!parentIntentIds.includes(direction.parent_intent)) {
    throw new Error(`${directionId} references an unknown parent intent`);
  }
  if (
    direction.interaction_mode !==
    policy.parent_intents[direction.parent_intent].tachikoma_interaction_mode
  ) {
    throw new Error(`${directionId} interaction mode drifts from its parent intent`);
  }
  if (
    !direction.logic_shape ||
    !direction.tone ||
    !direction.character_range ||
    !direction.sentence_range
  ) {
    throw new Error(`${directionId} is missing a logic, tone or length contract`);
  }
  for (const topicId of direction.topic_ids) {
    if (topicId !== "*" && !policy.topics[topicId]) {
      throw new Error(`${directionId} references unknown topic ${topicId}`);
    }
  }
}

fs.writeFileSync(outputPath, `${JSON.stringify(policy, null, 2)}\n`, "utf8");
process.stdout.write(`${JSON.stringify({
  passed: true,
  output: path.relative(REPO, outputPath),
  policy_version: policy.policy_version,
  parent_intents: policy.architecture.parent_intent_count,
  detailed_directions: policy.architecture.detailed_direction_count,
  topics: policy.architecture.topic_count,
  voice_styles: policy.architecture.voice_style_count,
  publish_allowed: policy.publish_allowed,
}, null, 2)}\n`);
