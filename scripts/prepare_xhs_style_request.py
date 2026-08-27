#!/usr/bin/env python3
"""Compile one pinned Tachikoma Style Lab request without generating text."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from lib.xhs_comment_production_taxonomy import (
    apply_taxonomy_to_brief,
    validate_production_context,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_reply_style_contract_v3.json"
)
INTENT_POLICY_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_comment_intent_policy_v4.json"
)
COLLOQUIAL_LEXICON_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_comment_colloquial_lexicon_v1.json"
)
OFFICIAL_TOPIC_STRATEGY_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "official_reply_research_v1"
    / "panse_official_topic_strategy_v1.json"
)
OFFICIAL_PROFESSIONAL_VALUE_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "official_reply_research_v1"
    / "panse_official_professional_value_v1.json"
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_official_topic_context(
    context: object,
    strategy: dict,
) -> dict:
    """Fail closed before Style Lab can style an official outbound comment."""
    if not isinstance(context, dict):
        raise ValueError(
            "panse_official_topic_context is required for official brand voice"
        )
    if context.get("strategy_id") != strategy.get("strategy_id"):
        raise ValueError("official topic strategy version mismatch")
    required = strategy.get("required_context_fields", [])
    missing = [field for field in required if field not in context]
    if missing:
        raise ValueError(
            "official topic context is missing: " + ", ".join(missing)
        )
    allowed_topics = {
        item.get("topic_id") for item in strategy.get("outbound_topic_pool", [])
    } | {
        item.get("topic_id") for item in strategy.get("event_driven_topics", [])
    }
    if context.get("topic_id") not in allowed_topics:
        raise ValueError("official outbound topic is not allowed by strategy")
    if context.get("visible_detail_grounded") is not True:
        raise ValueError("official outbound comment needs one visible grounded detail")
    if context.get("visible_comment_context_read") is not True:
        raise ValueError("visible comment context must be read before official generation")
    if context.get("question_answered_in_context") is True:
        raise ValueError("do not generate an official question already answered in context")
    if not str(context.get("panse_reply_right", "")).strip():
        raise ValueError("Panse reply right must be declared before official generation")
    if not str(context.get("target_relationship", "")).strip():
        raise ValueError("target relationship must be declared before official generation")
    return context


def validate_official_professional_value_context(
    context: object,
    contract: dict,
) -> dict:
    """Require a professional reason or bounded practical value before styling."""
    if not isinstance(context, dict):
        raise ValueError(
            "panse_official_professional_value_context is required for official brand voice"
        )
    if context.get("contract_id") != contract.get("contract_id"):
        raise ValueError("official professional value contract version mismatch")
    required = [
        "value_mode",
        "professional_basis_type",
        "professional_basis_text",
        "useful_takeaway_present",
        "fact_source_status",
    ]
    missing = [field for field in required if field not in context]
    if missing:
        raise ValueError(
            "official professional value context is missing: " + ", ".join(missing)
        )
    value_mode = context.get("value_mode")
    mode_policy = contract.get("value_modes", {}).get(value_mode)
    if not isinstance(mode_policy, dict):
        raise ValueError("unknown official professional value mode")
    if context.get("professional_basis_type") not in set(
        contract.get("professional_basis_types", [])
    ):
        raise ValueError("unknown official professional basis type")
    if not str(context.get("professional_basis_text", "")).strip():
        raise ValueError("official comment needs a concrete professional basis")
    if context.get("useful_takeaway_present") is not True:
        raise ValueError("official comment needs one useful judgment or takeaway")
    fact_source_status = context.get("fact_source_status")
    if fact_source_status not in set(contract.get("fact_source_statuses", [])):
        raise ValueError("unknown official fact source status")
    if value_mode == "professional_reasoned_praise" and (
        context.get("praise_reason_precedes_praise") is not True
    ):
        raise ValueError("professional reason must precede praise")
    if mode_policy.get("advice_allowed") is True:
        allowed_contexts = set(
            mode_policy.get("allowed_advice_context_statuses", [])
        )
        if context.get("advice_context_status") not in allowed_contexts:
            raise ValueError("professional advice lacks an invited or visible problem context")
        is_verified = fact_source_status in {
            "verified_panse",
            "verified_current_external",
        }
        if (
            mode_policy.get("requires_conditional_language_unless_verified") is True
            and not is_verified
            and context.get("conditional_language_present") is not True
        ):
            raise ValueError("unverified practical advice must use conditional language")
    return context


def select_human_approved_examples(
    intent_policy: dict,
    voice_id: str,
    comment_direction_id: str,
    topic_ids: list[str],
    limit: int = 3,
) -> tuple[dict, list[dict]]:
    reference = intent_policy.get("human_approved_style_reference")
    if not isinstance(reference, dict):
        raise ValueError("human-approved style reference is required")
    example_path = REPO_ROOT / str(reference.get("path", ""))
    corpus = load_json(example_path)
    if corpus.get("example_set_version") != reference.get("example_set_version"):
        raise ValueError("human-approved comment example version mismatch")
    if corpus.get("review_status") != "user_approved":
        raise ValueError("human-approved comment examples are not user approved")
    items = corpus.get("items")
    if not isinstance(items, list) or len(items) != reference.get("approved_count"):
        raise ValueError("human-approved comment example count mismatch")
    covered_roles = set(reference.get("roles", []))
    if voice_id not in covered_roles:
        return corpus, []
    topic_set = set(topic_ids)
    ranked = sorted(
        (item for item in items if item.get("voice_id") == voice_id),
        key=lambda item: (
            -(2 if item.get("comment_direction_id") == comment_direction_id else 0),
            -(1 if topic_set.intersection(item.get("topic_ids", [])) else 0),
            str(item.get("id", "")),
        ),
    )
    selected = [
        {
            "example_id": item["id"],
            "interaction_intent": item["interaction_intent"],
            "comment_direction_id": item["comment_direction_id"],
            "topic_ids": item["topic_ids"],
            "draft": item["draft"],
        }
        for item in ranked[:limit]
    ]
    if not selected:
        raise ValueError(f"no human-approved style examples for {voice_id}")
    return corpus, selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "request_path",
        help="Path to one request JSON, or '-' to read the transient request from stdin.",
    )
    args = parser.parse_args()

    contract = load_json(CONTRACT_PATH)
    intent_policy = load_json(INTENT_POLICY_PATH)
    colloquial_lexicon = load_json(COLLOQUIAL_LEXICON_PATH)
    official_topic_strategy = load_json(OFFICIAL_TOPIC_STRATEGY_PATH)
    official_professional_value = load_json(OFFICIAL_PROFESSIONAL_VALUE_PATH)
    tachikoma_root = Path(contract["style_lab"]["runtime_root"]).resolve()
    style_card_db = Path(contract["style_lab"]["style_card_db"]).resolve()
    if not style_card_db.is_file():
        raise FileNotFoundError(f"configured Style Card database not found: {style_card_db}")
    # Code may live in a clean release worktree while reviewed Style Cards stay
    # in the durable project data directory. Keep those two lifecycles explicit.
    os.environ["TK_STYLE_CARD_DB"] = str(style_card_db)
    sys.path.insert(0, str(tachikoma_root))

    from base.xiaohongshu_style import (  # pylint: disable=import-outside-toplevel
        StyleWritingRequest,
        prepare_style_bundle,
    )

    request_payload = (
        json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        if args.request_path == "-"
        else load_json(Path(args.request_path))
    )
    intent_context = request_payload.pop("panse_intent_context", None)
    if not isinstance(intent_context, dict):
        raise ValueError("panse_intent_context is required before Style Lab compilation")
    if intent_context.get("policy_version") != intent_policy["policy_version"]:
        raise ValueError("comment intent policy version mismatch")
    voice_id = str(intent_context.get("voice_id", "")).strip()
    production_contract = None
    if (
        intent_context.get("production_taxonomy_version") is not None
        or intent_context.get("production_category_id") is not None
    ):
        production_contract = validate_production_context(
            intent_context,
            voice_id,
        )
        request_payload = apply_taxonomy_to_brief(
            request_payload,
            production_contract,
        )
    official_topic_context = request_payload.pop(
        "panse_official_topic_context", None
    )
    official_professional_value_context = request_payload.pop(
        "panse_official_professional_value_context", None
    )
    if voice_id == "official_explanation":
        official_topic_context = validate_official_topic_context(
            official_topic_context,
            official_topic_strategy,
        )
        official_professional_value_context = (
            validate_official_professional_value_context(
                official_professional_value_context,
                official_professional_value,
            )
        )
    elif official_topic_context is not None:
        raise ValueError(
            "panse_official_topic_context is only valid for official brand voice"
        )
    elif official_professional_value_context is not None:
        raise ValueError(
            "panse_official_professional_value_context is only valid for official brand voice"
        )
    interaction_intent = str(
        intent_context.get("interaction_intent", "")
    ).strip()
    comment_direction_id = str(
        intent_context.get("comment_direction_id", "")
    ).strip()
    topic_ids = [
        str(value).strip()
        for value in intent_context.get("topic_ids", [])
        if str(value).strip()
    ]
    role_policy = intent_policy.get("roles", {}).get(voice_id)
    if not role_policy:
        raise ValueError(f"unknown comment voice: {voice_id}")
    direction_policy = intent_policy.get("directions", {}).get(
        comment_direction_id
    )
    if not direction_policy:
        raise ValueError("one of the 20 detailed comment directions is required")
    if direction_policy.get("parent_intent") != interaction_intent:
        raise ValueError("detailed direction and parent interaction intent mismatch")
    if comment_direction_id not in role_policy.get("allowed_direction_ids", []):
        raise ValueError(
            f"comment direction {comment_direction_id!r} is not allowed for {voice_id}"
        )
    if not topic_ids or any(
        topic_id not in intent_policy.get("topics", {}) for topic_id in topic_ids
    ):
        raise ValueError("one or more recognized topic_ids are required")
    direction_topics = direction_policy.get("topic_ids", [])
    if "*" not in direction_topics and not set(topic_ids).intersection(
        direction_topics
    ):
        raise ValueError("detailed direction does not match the declared topics")
    expected_interaction_mode = direction_policy.get("interaction_mode")
    if not expected_interaction_mode:
        raise ValueError(
            f"interaction intent {interaction_intent!r} has no Tachikoma interaction mode"
        )
    taxonomy_ids = request_payload.get("taxonomy_ids", [])
    controlled_home_comment_route = {
        "platform.xiaohongshu-comment",
        "persona.lifestyle-curator",
        "role.editor",
        "scene.social-comment",
    } <= set(taxonomy_ids)
    if controlled_home_comment_route:
        if request_payload.get("interaction_mode") != expected_interaction_mode:
            raise ValueError(
                "Style Lab interaction_mode must match the declared Panse interaction intent"
            )
    elif request_payload.get("interaction_mode") is not None:
        raise ValueError(
            "interaction_mode is only valid for the controlled home lifestyle route"
        )

    example_corpus, approved_examples = select_human_approved_examples(
        intent_policy,
        voice_id,
        comment_direction_id,
        topic_ids,
    )
    if controlled_home_comment_route:
        request_payload["comment_intent_context"] = {
            "intent_policy_version": intent_policy["policy_version"],
            "topic_ids": topic_ids,
            "interaction_intent": interaction_intent,
            "comment_direction_id": comment_direction_id,
            "voice_id": voice_id,
            "human_approved_example_set_version": (
                example_corpus["example_set_version"]
                if approved_examples
                else None
            ),
        }
    direction_range = direction_policy["character_range"]
    output_contract = request_payload.setdefault("output", {})
    output_contract["body_min_chars"] = max(
        int(output_contract.get("body_min_chars", 1)),
        int(direction_range["minimum"]),
    )
    output_contract["body_max_chars"] = min(
        int(output_contract.get("body_max_chars", 20_000)),
        int(direction_range["maximum"]),
    )
    if output_contract["body_min_chars"] > output_contract["body_max_chars"]:
        raise ValueError("request output range does not overlap the direction contract")

    request = StyleWritingRequest.model_validate(request_payload)
    bundle, _instruction = prepare_style_bundle(request)
    result = {
        "passed": True,
        "text_generated": False,
        "network_access_performed": False,
        "external_posting_performed": False,
        "request_id": request.request_id,
        "intent_policy_version": intent_policy["policy_version"],
        "voice_id": voice_id,
        "production_taxonomy_verified": production_contract is not None,
        "production_contract": production_contract,
        "interaction_intent": interaction_intent,
        "comment_direction_id": comment_direction_id,
        "topic_ids": topic_ids,
        "voice_style_id": role_policy["voice_style_id"],
        "official_topic_strategy_id": (
            official_topic_strategy["strategy_id"]
            if official_topic_context is not None
            else None
        ),
        "official_topic_context": official_topic_context,
        "official_professional_value_contract_id": (
            official_professional_value["contract_id"]
            if official_professional_value_context is not None
            else None
        ),
        "official_professional_value_context": official_professional_value_context,
        "voice_contract": role_policy["voice_contract"],
        "direction_contract": direction_policy,
        "colloquial_lexicon_contract": colloquial_lexicon,
        "human_approved_example_set_version": example_corpus[
            "example_set_version"
        ],
        "human_approved_example_ids": [
            item["example_id"] for item in approved_examples
        ],
        "interaction_mode": request.interaction_mode,
        "bundle_id": bundle["bundle_id"],
        "bundle_sha256": bundle["bundle_sha256"],
        "catalog_version": bundle["selection"]["taxonomy"]["catalog_version"],
        "catalog_sha256": bundle["selection"]["taxonomy"]["catalog_sha256"],
        "taxonomy_ids": bundle["selection"]["taxonomy"]["taxonomy_ids"],
        "approved_card_refs": bundle["selection"]["approved_card_refs"],
        "requested_strength": bundle["selection"]["strength"]["resolved"],
        "register_contract": bundle["style_instructions"]["register_contract"],
        "microgenre_contract": bundle["style_instructions"][
            "microgenre_contract"
        ],
        "provider_contract": bundle["provider_contract"],
        "publish_allowed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
