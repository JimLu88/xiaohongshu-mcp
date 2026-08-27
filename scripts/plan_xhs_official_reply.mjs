import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import {
  classifyOfficialReplyRoute,
  loadOfficialReplyPolicy,
  officialReplyRoute,
} from "./lib/xhs_official_reply_policy.mjs";
import {
  evaluateOfficialTopicStrategy,
  loadOfficialTopicStrategy,
} from "./lib/xhs_official_topic_strategy.mjs";

export function planOfficialReply(
  payload,
  policy = loadOfficialReplyPolicy(),
  topicStrategyPolicy = loadOfficialTopicStrategy(),
) {
  const interactionType = String(payload?.interaction_type ?? "").trim();
  if (!policy.interaction_types[interactionType]) {
    throw new Error("Declare one valid official interaction_type before planning");
  }

  const topicStrategy = evaluateOfficialTopicStrategy(
    payload,
    topicStrategyPolicy,
  );

  const declaredRouteId = String(payload?.route_id ?? "").trim();
  if (
    declaredRouteId &&
    declaredRouteId !== "no_reply" &&
    topicStrategy.passed !== true
  ) {
    throw new Error(
      `Official topic strategy rejected this reply: ${topicStrategy.reasons.join("；")}`,
    );
  }
  const classification = declaredRouteId
    ? {
        route_id: declaredRouteId,
        confidence: 1,
        evidence_signals: ["explicit_route_declaration"],
        should_reply: declaredRouteId !== "no_reply",
      }
    : topicStrategy.passed
      ? classifyOfficialReplyRoute(payload, policy)
      : {
          route_id: "no_reply",
          confidence: 1,
          evidence_signals: topicStrategy.reasons.map(
            (reason) => `topic_strategy:${reason}`,
          ),
          should_reply: false,
        };
  const route = officialReplyRoute(classification.route_id, policy);
  if (!route) throw new Error(`Unknown official reply route: ${classification.route_id}`);
  if (!route.interaction_types.includes(interactionType)) {
    throw new Error("Selected official route is incompatible with interaction_type");
  }

  const noReply = route.family === "silence";
  return {
    passed: true,
    policy_id: policy.policy_id,
    account_id: policy.role.account_id,
    voice_id: payload?.voice_id || policy.role.voice_id,
    interaction_type: interactionType,
    route_id: classification.route_id,
    route_label: route.label,
    family: route.family,
    style_mode: route.style_mode,
    classification_confidence: classification.confidence,
    classification_evidence: classification.evidence_signals,
    topic_strategy: topicStrategy,
    should_reply: !noReply,
    character_range: route.character_range,
    sentence_range: route.sentence_range,
    structure: route.structure,
    requires: route.requires,
    forbids: route.forbids,
    generation_brief: noReply
      ? null
      : {
          response_goal: route.label,
          source_context_required: true,
          visible_comments_required: ["reply_to_user", "outbound_comment"].includes(
            interactionType,
          ),
          protected_facts: Array.isArray(payload?.protected_facts)
            ? payload.protected_facts
            : [],
          permitted_facts: Array.isArray(payload?.permitted_facts)
            ? payload.permitted_facts
            : [],
          unknowns: Array.isArray(payload?.unknowns) ? payload.unknowns : [],
          prohibited_claims: [
            "原帖、评论区或产品资料里没有的事实",
            "未经核实的购买、入住、检测、维修或长期使用经历",
            "老师、评委或验收者口吻",
            "空洞的第二句",
            "两个以上行动指令",
          ],
          desired_length: route.character_range,
          identity_relation: "畔色官方品牌账号",
          topic_id: topicStrategy.topic_id,
          panse_reply_right: topicStrategy.panse_reply_right,
          content_followup_signal: topicStrategy.content_followup_signal,
        },
    provider_contract: policy.provider_contract,
    semantic_review_gates: policy.semantic_review_gates,
    human_review_required: true,
    publish_allowed: false,
  };
}

function readPayload(argument) {
  if (argument === "-") return JSON.parse(fs.readFileSync(0, "utf8"));
  return JSON.parse(fs.readFileSync(path.resolve(argument), "utf8"));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const input = process.argv[2];
  if (!input) {
    throw new Error("Usage: node scripts/plan_xhs_official_reply.mjs <input.json|->");
  }
  process.stdout.write(`${JSON.stringify(planOfficialReply(readPayload(input)), null, 2)}\n`);
}
