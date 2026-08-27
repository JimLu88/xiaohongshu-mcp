#!/usr/bin/env python3
"""Recompile every pinned Xiaohongshu reply style without generating text."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_reply_style_contract_v3.json"
)
OUTPUT_KEYS = (
    "title_candidates",
    "title_max_chars",
    "body_min_chars",
    "body_max_chars",
    "tag_min",
    "tag_max",
)
REQUIRED_PRECONDITIONS = {
    "target_context_complete",
    "interaction_intent_fixed",
    "speaking_identity_fixed",
    "complete_brief",
    "source_and_rights",
    "fact_contract",
    "identity_and_affiliation",
    "platform_risk_clear",
    "approved_style_bundle",
    "quality_and_naturalness",
    "human_and_platform_review",
}
REQUIRED_RECEIPT_FIELDS = {
    "intent_policy_version",
    "interaction_intent",
    "comment_direction_id",
    "topic_ids",
    "voice_style_id",
    "interaction_mode",
    "candidate_id",
    "candidate_input_sha256",
    "style_profile_sha256",
    "catalog_version",
    "catalog_sha256",
    "approved_card_refs",
    "taxonomy_ids",
    "requested_strength",
    "bundle_id",
    "bundle_sha256",
    "provider",
    "model_id",
    "model_verified",
    "prompt_versions",
    "observed_at",
    "gate_tuple",
}
REQUIRED_HARD_GATES = {
    "permission/source_rights",
    "protected_fact_precision",
    "protected_fact_recall",
    "unsupported_claims",
    "citation_coverage",
    "near_copy",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def profile_fingerprint(contract: dict[str, Any], profile: dict[str, Any]) -> str:
    output = contract["output_contract"]
    payload = {
        "account_id": profile["account_id"],
        "voice_id": profile["voice_id"],
        "artifact_type": profile["artifact_type"],
        "taxonomy_ids": profile["taxonomy_ids"],
        "requested_strength": profile["requested_strength"],
        "preflight_interaction_mode": profile.get("preflight_interaction_mode"),
        "approved_card_refs": profile["approved_card_refs"],
        "catalog_version": contract["style_lab"]["catalog_version"],
        "catalog_sha256": contract["style_lab"]["catalog_sha256"],
        "output": {key: output[key] for key in OUTPUT_KEYS},
    }
    return sha256_json(payload)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(contract_path: Path, *, emit_refresh_values: bool = False) -> dict[str, Any]:
    contract = load_json(contract_path)
    style_lab = contract["style_lab"]
    tachikoma_root = Path(style_lab["runtime_root"]).resolve()
    require(tachikoma_root.is_dir(), f"Tachikoma root not found: {tachikoma_root}")
    configured_card_db = Path(style_lab["style_card_db"]).resolve()
    require(configured_card_db.is_file(), f"Style Card database not found: {configured_card_db}")
    os.environ["TK_STYLE_CARD_DB"] = str(configured_card_db)
    sys.path.insert(0, str(tachikoma_root))

    from base.xiaohongshu_style import (  # pylint: disable=import-outside-toplevel
        StyleWritingRequest,
        prepare_style_bundle,
    )
    from chatgpt_mcp import style_taxonomy  # pylint: disable=import-outside-toplevel
    from chatgpt_mcp.style_cards import DEFAULT_DB_PATH  # pylint: disable=import-outside-toplevel

    require(contract.get("schema_version") == 2, "contract schema_version must be 2")
    intent_policy = contract.get("intent_policy", {})
    require(
        intent_policy.get("policy_version") == "xhs-comment-intent.v4",
        "comment intent policy version must be v4",
    )
    intent_policy_path = REPO_ROOT / intent_policy.get("path", "")
    require(intent_policy_path.is_file(), "comment intent policy file is missing")
    live_intent_policy = load_json(intent_policy_path)
    require(
        live_intent_policy.get("source_sample_count") == 600,
        "comment intent corpus must contain 600 samples",
    )
    require(
        len(live_intent_policy.get("directions", {})) == 20,
        "comment policy must contain exactly 20 detailed directions",
    )
    require(
        len(live_intent_policy.get("topics", {})) == 14,
        "comment policy must contain exactly 14 topics",
    )
    require(style_lab.get("runtime_entrypoint") == "base.xiaohongshu_style.prepare_style_bundle", "unexpected Style Lab entrypoint")
    require(
        style_lab.get("project_direction_planner")
        == "scripts/plan_xhs_comment_direction.mjs",
        "comment direction planner must be the project entry gate",
    )
    require(
        style_lab.get("project_preflight_entrypoint")
        == "scripts/prepare_xhs_style_request.py",
        "Style Lab requests must pass the project preflight wrapper",
    )
    require(
        (REPO_ROOT / style_lab["project_direction_planner"]).is_file(),
        "comment direction planner is missing",
    )
    require(
        (REPO_ROOT / style_lab["project_preflight_entrypoint"]).is_file(),
        "project Style Lab preflight wrapper is missing",
    )
    approved_examples = style_lab.get("human_approved_comment_examples", {})
    approved_examples_path = REPO_ROOT / approved_examples.get("path", "")
    require(
        approved_examples.get("example_set_version")
        == "panse-xhs-human-approved-comments.v3",
        "human-approved comment example version must be v3",
    )
    require(approved_examples_path.is_file(), "human-approved example file is missing")
    approved_example_corpus = load_json(approved_examples_path)
    require(
        approved_example_corpus.get("review_status") == "user_approved",
        "human-approved comment examples must be user approved",
    )
    require(
        len(approved_example_corpus.get("items", []))
        == approved_examples.get("approved_count")
        == 15,
        "human-approved comment example count must be 15",
    )
    require(
        approved_examples.get("content_authority")
        == "current_complete_source_context",
        "current source context must remain the content authority",
    )
    require(
        approved_examples.get("near_copy_forbidden") is True,
        "near-copy of human-approved examples must stay forbidden",
    )
    require(style_lab.get("style_requirement") == "approved_required", "approved Style Cards must be required")
    require(style_lab.get("pin_card_versions") is True, "Style Card versions must be pinned")
    require(style_lab.get("taxonomy_fallback_allowed") is False, "taxonomy fallback must stay disabled")
    require(style_lab.get("publish_allowed") is False, "Style Lab must not publish")

    provider = contract["provider_contract"]
    require(provider.get("required_model_id") == "gpt-5.6-sol", "required model must be exactly gpt-5.6-sol")
    require(provider.get("required_model_match") == "exact", "model matching must be exact")
    require(provider.get("fallback_model_allowed") is False, "model fallback must stay disabled")
    require(provider.get("model_mismatch_action") == "fail_closed_before_human_review", "model mismatch must fail closed")

    precondition_ids = {
        item["id"] for item in contract.get("preconditions", []) if item.get("required") is True
    }
    require(REQUIRED_PRECONDITIONS <= precondition_ids, "one or more required preconditions are missing")
    receipt_fields = set(contract["receipt_contract"].get("required_fields", []))
    require(REQUIRED_RECEIPT_FIELDS <= receipt_fields, "receipt cannot bind the style run to its content and model")
    hard_gates = set(contract["receipt_contract"].get("required_hard_gates", []))
    require(hard_gates == REQUIRED_HARD_GATES, "receipt must require the exact six deterministic hard gates")
    require(contract.get("external_posting_enabled") is False, "external posting must stay disabled")
    require(contract.get("publish_allowed") is False, "publish_allowed must stay false")

    catalog = style_taxonomy.load_taxonomy()
    catalog_sha256 = style_taxonomy.taxonomy_sha256()
    require(catalog.catalog_version == style_lab["catalog_version"], "live taxonomy catalog version drifted")
    require(catalog_sha256 == style_lab["catalog_sha256"], "live taxonomy SHA-256 drifted")
    require(len(catalog.entries) == style_lab["declared_taxonomy_count"], "live taxonomy entry count drifted")

    card_db_path = Path(os.getenv("TK_STYLE_CARD_DB") or DEFAULT_DB_PATH).resolve()
    with sqlite3.connect(f"file:{card_db_path.as_posix()}?mode=ro", uri=True) as connection:
        approved_card_rows = connection.execute(
                """
                SELECT v.allowed_operations_json
                FROM style_card_versions v
                JOIN (
                    SELECT card_id, MAX(card_version) AS approved_version
                    FROM style_card_versions
                    WHERE status='approved'
                    GROUP BY card_id
                ) approved
                  ON approved.card_id=v.card_id
                 AND approved.approved_version=v.card_version
                JOIN (
                    SELECT card_id, MAX(card_version) AS latest_version
                    FROM style_card_versions
                    GROUP BY card_id
                ) latest ON latest.card_id=v.card_id
                JOIN style_card_versions current
                  ON current.card_id=latest.card_id
                 AND current.card_version=latest.latest_version
                WHERE v.status='approved' AND current.status<>'deprecated'
                """
            ).fetchall()
        approved_card_count = sum(
            "generate" in json.loads(row[0]) for row in approved_card_rows
        )
    require(approved_card_count == style_lab["approved_card_count"], "live approved Style Card count drifted")

    output = {key: contract["output_contract"][key] for key in OUTPUT_KEYS}
    validated_profiles: list[dict[str, Any]] = []
    seen_voices: set[str] = set()

    for profile in contract.get("voice_preflights", []):
        voice_id = profile["voice_id"]
        require(voice_id not in seen_voices, f"duplicate voice_id: {voice_id}")
        seen_voices.add(voice_id)
        expected_profile_sha256 = profile_fingerprint(contract, profile)
        if not emit_refresh_values:
            require(
                profile.get("style_profile_sha256") == expected_profile_sha256,
                f"style profile fingerprint drifted: {voice_id}",
            )
        require(profile["artifact_type"] in {"comment", "reply"}, f"invalid reply artifact: {voice_id}")
        require(profile["taxonomy_ids"].count("platform.xiaohongshu-comment") == 1, f"wrong platform taxonomy: {voice_id}")
        require(all(ref.get("card_version") for ref in profile["approved_card_refs"]), f"unpinned card version: {voice_id}")

        if not emit_refresh_values:
            preflight_sha256 = profile["preflight_bundle_sha256"]
            require(re.fullmatch(r"[0-9a-f]{64}", preflight_sha256) is not None, f"bad preflight bundle SHA-256: {voice_id}")
            require(profile["preflight_bundle_id"] == f"stylebundle_{preflight_sha256[:24]}", f"bad preflight bundle ID: {voice_id}")

        request = StyleWritingRequest(
            request_id=f"panse.style-contract.{voice_id}",
            idempotency_key=f"panse:style-contract:{voice_id}:v2",
            brief_text=(
                "这是畔色小红书项目的本地风格契约复验占位 brief；"
                "仅验证已批准卡片、分类、体裁和质量合同，不生成或发布内容。"
            ),
            source_locator=f"local://panse/style-contract/{voice_id}",
            rights_basis="project-owned contract validation fixture",
            sensitivity="internal",
            audience="小红书家具家居内容读者",
            use_case="评论或品牌回复风格预检",
            artifact_type=profile["artifact_type"],
            interaction_mode=profile.get("preflight_interaction_mode"),
            source_context=(
                {
                    "body": "本地风格契约复验使用的完整目标正文占位内容。",
                    "visible_comments": [],
                    "body_complete": True,
                    "visible_comments_complete": True,
                    "expected_visible_comment_count": 0,
                    "image_observations": [],
                    "images_complete": True,
                    "expected_image_count": 0,
                }
                if profile.get("preflight_interaction_mode")
                else None
            ),
            comment_intent_context=(
                {
                    "intent_policy_version": "xhs-comment-intent.v4",
                    "topic_ids": ["color_light_atmosphere"],
                    "interaction_intent": "utility_fit_question",
                    "comment_direction_id": "color_light_fit_question",
                    "voice_id": profile["voice_id"],
                    "human_approved_example_set_version": (
                        "panse-xhs-human-approved-comments.v3"
                    ),
                }
                if profile.get("preflight_interaction_mode")
                else None
            ),
            taxonomy_ids=profile["taxonomy_ids"],
            style_card_refs=profile["approved_card_refs"],
            requested_strength=profile["requested_strength"],
            style_requirement="approved_required",
            pin_card_versions=True,
            required_model_id=provider["required_model_id"],
            fallback_model_allowed=False,
            content_contract={
                "protected_facts": [],
                "allowed_paraphrases": {},
                "forbidden_inferences": [
                    "不得虚构购买、使用或入住经历",
                    "不得把品牌、员工或模型伪装成独立消费者",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            output=output,
        )
        bundle, _instruction = prepare_style_bundle(request)
        selection = bundle["selection"]
        resolved_refs = [
            {"card_id": item["card_id"], "card_version": item["card_version"]}
            for item in selection["approved_card_refs"]
        ]
        register = bundle["style_instructions"]["register_contract"]

        require(selection["mode"] == "approved_cards+taxonomy", f"approved-card mode not used: {voice_id}")
        require(resolved_refs == profile["approved_card_refs"], f"resolved Style Cards drifted: {voice_id}")
        require(selection["taxonomy"]["taxonomy_ids"] == profile["taxonomy_ids"], f"resolved taxonomy drifted: {voice_id}")
        require(selection["taxonomy"]["catalog_sha256"] == style_lab["catalog_sha256"], f"compiled catalog drifted: {voice_id}")
        require(selection["strength"]["resolved"] == profile["requested_strength"], f"resolved strength drifted: {voice_id}")
        require(register["register_id"] == profile["register_id"], f"register drifted: {voice_id}")
        require(register["rhetorical_device_budget"] == profile["rhetorical_device_budget"], f"rhetorical budget drifted: {voice_id}")
        require(bundle["provider_contract"]["human_review_path_required"] is True, f"human review path missing: {voice_id}")

        validated_profiles.append(
            {
                "voice_id": voice_id,
                "style_profile_sha256": expected_profile_sha256,
                "compiled_bundle_id": bundle["bundle_id"],
                "compiled_bundle_sha256": bundle["bundle_sha256"],
                "register_id": register["register_id"],
            }
        )

    require(len(validated_profiles) == 7, "expected seven reply voice preflights")
    return {
        "passed": True,
        "execution_scope": "local_style_compilation_only",
        "text_generated": False,
        "network_access_performed": False,
        "external_posting_performed": False,
        "catalog_version": catalog.catalog_version,
        "catalog_sha256": catalog_sha256,
        "taxonomy_count": len(catalog.entries),
        "approved_card_count": approved_card_count,
        "required_model_id": provider["required_model_id"],
        "fallback_model_allowed": provider["fallback_model_allowed"],
        "profiles": validated_profiles,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--emit-refresh-values",
        action="store_true",
        help="Compile against the live approved catalog and print replacement fingerprints without trusting stale stored values.",
    )
    args = parser.parse_args()
    try:
        result = validate(
            args.contract.resolve(), emit_refresh_values=args.emit_refresh_values
        )
    except Exception as exc:  # fail closed with a machine-readable error
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
