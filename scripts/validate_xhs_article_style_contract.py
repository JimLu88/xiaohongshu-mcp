#!/usr/bin/env python3
"""Recompile the five pinned Xiaohongshu article styles without generating text."""

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
    / "xhs_article_style_contract_v2.json"
)
LAUNCH_CONFIG = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "five_direction_launch_config.json"
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
    "direction_and_account_fixed",
    "topic_hierarchy_complete",
    "complete_brief",
    "source_package",
    "source_and_rights",
    "fact_contract",
    "identity_and_affiliation",
    "visual_rights_and_disclosure",
    "platform_risk_clear",
    "approved_style_bundle",
    "quality_and_originality",
    "human_and_platform_review",
}
REQUIRED_RECEIPT_FIELDS = {
    "contract_version",
    "candidate_id",
    "article_input_sha256",
    "direction_profile_sha256",
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
    "delivery_ready_for_human_review",
    "human_review_required",
    "publish_allowed",
}
REQUIRED_HARD_GATES = {
    "permission/source_rights",
    "protected_fact_precision",
    "protected_fact_recall",
    "unsupported_claims",
    "citation_coverage",
    "near_copy",
}
REQUIRED_SOFT_GATES = {
    "style_adherence",
    "discourse_coherence",
    "fluency/readability",
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
    payload = {
        "direction": profile["direction"],
        "account_id": profile["account_id"],
        "artifact_type": profile["artifact_type"],
        "taxonomy_ids": profile["taxonomy_ids"],
        "requested_strength": profile["requested_strength"],
        "approved_card_refs": profile["approved_card_refs"],
        "catalog_version": contract["style_lab"]["catalog_version"],
        "catalog_sha256": contract["style_lab"]["catalog_sha256"],
        "output": {key: profile["output"][key] for key in OUTPUT_KEYS},
    }
    return sha256_json(payload)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def current_generate_card_count(card_db_path: Path) -> int:
    with sqlite3.connect(f"file:{card_db_path.as_posix()}?mode=ro", uri=True) as connection:
        rows = connection.execute(
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
    return sum("generate" in json.loads(row[0]) for row in rows)


def validate(contract_path: Path) -> dict[str, Any]:
    contract = load_json(contract_path)
    launch = load_json(LAUNCH_CONFIG)
    style_lab = contract["style_lab"]
    tachikoma_root = Path(style_lab["runtime_root"]).resolve()
    require(tachikoma_root.is_dir(), f"Tachikoma root not found: {tachikoma_root}")
    if style_lab.get("style_card_db"):
        configured_db = Path(style_lab["style_card_db"]).resolve()
        require(configured_db.is_file(), f"Style Card database not found: {configured_db}")
        os.environ["TK_STYLE_CARD_DB"] = str(configured_db)
    sys.path.insert(0, str(tachikoma_root))

    from base.xiaohongshu_style import (  # pylint: disable=import-outside-toplevel
        StyleWritingRequest,
        prepare_style_bundle,
    )
    from chatgpt_mcp import style_taxonomy  # pylint: disable=import-outside-toplevel
    from chatgpt_mcp.style_cards import DEFAULT_DB_PATH  # pylint: disable=import-outside-toplevel

    require(contract.get("schema_version") == 2, "contract schema_version must be 2")
    require(style_lab.get("runtime_entrypoint") == "base.xiaohongshu_style.prepare_style_bundle", "unexpected Style Lab entrypoint")
    require(style_lab.get("style_requirement") == "approved_required", "approved Style Cards must be required")
    require(style_lab.get("pin_card_versions") is True, "Style Card versions must be pinned")
    require(style_lab.get("taxonomy_fallback_allowed") is False, "taxonomy fallback must stay disabled")
    require(style_lab.get("named_author_imitation_allowed") is False, "named-author imitation must stay disabled")

    provider = contract["provider_contract"]
    require(provider.get("required_model_id") == "gpt-5.6-sol", "required model must be exactly gpt-5.6-sol")
    require(provider.get("required_model_match") == "exact", "model matching must be exact")
    require(provider.get("fallback_model_allowed") is False, "model fallback must stay disabled")
    require(provider.get("model_mismatch_action") == "fail_closed_before_human_review", "model mismatch must fail closed")

    policy = contract["launch_policy"]
    require(policy.get("account_warmup_active") is True, "account warmup status drifted")
    require(policy.get("article_generation_enabled") is True, "offline article generation must be enabled")
    require(policy.get("write_allowed") is True, "offline article writing must be allowed")
    require(policy.get("external_posting_enabled") is False, "external posting must stay disabled")
    require(policy.get("publish_allowed") is False, "publish_allowed must stay false")
    writing_runtime = launch["writing_runtime"]
    require(writing_runtime.get("article_generation_enabled") is True, "launch config must enable offline article generation")
    require(
        writing_runtime.get("article_style_contract_path")
        == "research/panse_multi_direction/xhs_article_style_contract_v2.json",
        "launch config points to the wrong article style contract",
    )
    require(writing_runtime.get("article_preflight_required") is True, "launch config must require article preflight")
    require(writing_runtime.get("legacy_article_preflight_executable") is False, "legacy v7 preflight must remain non-executable")
    require(writing_runtime.get("required_generation_model_id") == provider["required_model_id"], "launch config model drifted")

    hierarchy = contract["topic_hierarchy_contract"]
    require(
        hierarchy.get("required_order")
        == ["macro_theme", "subtopic_family", "article_seed", "sourced_article_brief"],
        "topic hierarchy drifted",
    )
    require(hierarchy.get("minimum_evidence_types", 0) >= 3, "source package needs at least three evidence types")
    require(hierarchy.get("nonempty_source_body_required") is True, "nonempty source bodies must be required")
    require(hierarchy.get("likes_are_not_evidence") is True, "likes cannot substitute for evidence")

    precondition_ids = {
        item["id"] for item in contract.get("preconditions", []) if item.get("required") is True
    }
    require(REQUIRED_PRECONDITIONS <= precondition_ids, "one or more required article preconditions are missing")
    receipt = contract["receipt_contract"]
    require(REQUIRED_RECEIPT_FIELDS <= set(receipt.get("required_fields", [])), "article receipt cannot bind content, style and model")
    require(set(receipt.get("required_hard_gates", [])) == REQUIRED_HARD_GATES, "article receipt must require the exact six hard gates")
    require(set(receipt.get("required_soft_review_gates", [])) == REQUIRED_SOFT_GATES, "article receipt must require the exact three soft review gates")
    require(receipt.get("aggregate_score_allowed") is False, "aggregate quality scores must stay disabled")

    catalog = style_taxonomy.load_taxonomy()
    catalog_sha256 = style_taxonomy.taxonomy_sha256()
    require(catalog.catalog_version == style_lab["catalog_version"], "live taxonomy catalog version drifted")
    require(catalog_sha256 == style_lab["catalog_sha256"], "live taxonomy SHA-256 drifted")
    require(len(catalog.entries) == style_lab["declared_taxonomy_count"], "live taxonomy entry count drifted")
    card_db_path = Path(os.getenv("TK_STYLE_CARD_DB") or DEFAULT_DB_PATH).resolve()
    generate_card_count = current_generate_card_count(card_db_path)
    require(generate_card_count == style_lab["approved_generate_card_count"], "live approved generate-card count drifted")

    expected_directions = set(launch["directions"])
    configured_accounts = {
        item["account_id"]: item for item in launch.get("accounts", [])
    }
    profiles = contract.get("direction_profiles", [])
    require({item["direction"] for item in profiles} == expected_directions, "article profiles do not match launch directions")
    require(len(profiles) == 5, "expected exactly five article direction profiles")

    validated_profiles: list[dict[str, Any]] = []
    for index, profile in enumerate(profiles):
        direction = profile["direction"]
        account_id = profile["account_id"]
        account = configured_accounts.get(account_id)
        require(account is not None, f"unknown account for {direction}")
        require(direction in account.get("directions", []), f"direction is not assigned to account: {direction}")
        require(profile.get("artifact_type") == "article", f"wrong artifact type: {direction}")
        require(profile["taxonomy_ids"].count("platform.xiaohongshu-note") == 1, f"wrong platform taxonomy: {direction}")
        require(len(profile.get("direction_gates", [])) >= 3, f"direction-specific gates missing: {direction}")
        require(all(ref.get("card_version") for ref in profile["approved_card_refs"]), f"unpinned Style Card: {direction}")

        expected_profile_sha256 = profile_fingerprint(contract, profile)
        require(profile.get("direction_profile_sha256") == expected_profile_sha256, f"direction fingerprint drifted: {direction}")
        preflight_sha256 = profile["preflight_bundle_sha256"]
        require(re.fullmatch(r"[0-9a-f]{64}", preflight_sha256) is not None, f"bad preflight bundle SHA-256: {direction}")
        require(profile["preflight_bundle_id"] == f"stylebundle_{preflight_sha256[:24]}", f"bad preflight bundle ID: {direction}")

        request = StyleWritingRequest(
            request_id=f"panse.article-contract.{index}",
            idempotency_key=f"panse:article-contract:{direction}:v2",
            brief_text=(
                f"这是畔色小红书正文方向 {direction} 的本地风格契约复验 brief；"
                "只验证已批准风格卡、事实合同、体裁和质量流程，不生成或发布正文。"
            ),
            source_locator=f"local://panse/article-contract/{direction}",
            rights_basis="project-owned contract validation fixture",
            sensitivity="internal",
            audience="正在做家具购买、家居布置或空间决策的小红书读者",
            use_case="小红书家具家居正文风格预检",
            artifact_type="article",
            taxonomy_ids=profile["taxonomy_ids"],
            style_card_refs=profile["approved_card_refs"],
            requested_strength=profile["requested_strength"],
            style_requirement="approved_required",
            pin_card_versions=True,
            content_contract={
                "protected_facts": [],
                "allowed_paraphrases": {},
                "forbidden_inferences": [
                    "不得虚构产品测试、消费者体验或第三方背书",
                    "不得把 AI 合成图描述为真实空间或产品实拍",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            output={key: profile["output"][key] for key in OUTPUT_KEYS},
        )
        bundle, _instruction = prepare_style_bundle(request)
        selection = bundle["selection"]
        resolved_refs = [
            {"card_id": item["card_id"], "card_version": item["card_version"]}
            for item in selection["approved_card_refs"]
        ]
        register = bundle["style_instructions"]["register_contract"]

        require(selection["mode"] == "approved_cards+taxonomy", f"approved-card mode not used: {direction}")
        require(resolved_refs == profile["approved_card_refs"], f"resolved Style Cards drifted: {direction}")
        require(selection["taxonomy"]["taxonomy_ids"] == profile["taxonomy_ids"], f"resolved taxonomy drifted: {direction}")
        require(selection["taxonomy"]["catalog_sha256"] == style_lab["catalog_sha256"], f"compiled catalog drifted: {direction}")
        require(selection["strength"]["resolved"] == profile["requested_strength"], f"resolved strength drifted: {direction}")
        require(register["register_id"] == profile["register_id"], f"register drifted: {direction}")
        require(register["rhetorical_device_budget"] == profile["rhetorical_device_budget"], f"rhetorical budget drifted: {direction}")
        require(bundle["provider_contract"]["human_review_path_required"] is True, f"human review path missing: {direction}")

        validated_profiles.append(
            {
                "direction": direction,
                "account_id": account_id,
                "direction_profile_sha256": expected_profile_sha256,
                "compiled_bundle_id": bundle["bundle_id"],
                "register_id": register["register_id"],
            }
        )

    return {
        "passed": True,
        "execution_scope": "local_article_style_compilation_only",
        "text_generated": False,
        "network_access_performed": False,
        "external_posting_performed": False,
        "article_generation_enabled": policy["article_generation_enabled"],
        "write_allowed": policy["write_allowed"],
        "publish_allowed": policy["publish_allowed"],
        "catalog_version": catalog.catalog_version,
        "catalog_sha256": catalog_sha256,
        "taxonomy_count": len(catalog.entries),
        "approved_generate_card_count": generate_card_count,
        "required_model_id": provider["required_model_id"],
        "fallback_model_allowed": provider["fallback_model_allowed"],
        "profiles": validated_profiles,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    args = parser.parse_args()
    try:
        result = validate(args.contract.resolve())
    except Exception as exc:  # fail closed with a machine-readable error
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
