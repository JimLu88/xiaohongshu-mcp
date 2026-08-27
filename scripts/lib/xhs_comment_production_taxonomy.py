#!/usr/bin/env python3
"""Validate the user-approved production speech-act taxonomy for XHS comments."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_comment_production_taxonomy_v1.json"
)


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require_truthy(context: dict[str, Any], field: str) -> None:
    value = context.get(field)
    if value is True:
        return
    if isinstance(value, str) and value.strip():
        return
    raise ValueError(f"production category requires {field}")


def validate_production_context(
    context: object,
    voice_id: str,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fail closed when a nonofficial draft lacks an approved reason to speak."""
    if not isinstance(context, dict):
        raise ValueError("panse_intent_context is required")
    selected_policy = policy or load_policy()
    if context.get("production_taxonomy_version") != selected_policy.get("policy_id"):
        raise ValueError("production comment taxonomy version mismatch")

    category_id = str(context.get("production_category_id", "")).strip()
    category = selected_policy.get("categories", {}).get(category_id)
    if not isinstance(category, dict):
        raise ValueError("recognized production_category_id is required")
    status = category.get("production_status")
    if status in {"observe_only", "reject"}:
        raise ValueError(
            f"production category {category_id} is not eligible: {status}"
        )

    voice_policy = selected_policy.get("voice_category_matrix", {}).get(voice_id)
    if not isinstance(voice_policy, dict):
        raise ValueError(f"production taxonomy does not govern voice {voice_id!r}")
    allowed = {
        category
        for bucket in ("preferred", "limited", "conditional")
        for category in voice_policy.get(bucket, [])
    }
    if category_id not in allowed:
        raise ValueError(
            f"production category {category_id!r} is not allowed for {voice_id}"
        )

    for field in selected_policy.get("required_request_fields", []):
        _require_truthy(context, field)
    if context.get("single_primary_speech_act") is not True:
        raise ValueError("one primary speech act is required")
    if context.get("source_restatement_avoided") is not True:
        raise ValueError("source restatement must be removed before generation")

    new_value_type = str(context.get("new_value_type", "")).strip()
    if new_value_type not in set(category.get("new_value_types", [])):
        raise ValueError(
            f"new_value_type {new_value_type!r} does not match {category_id}"
        )
    for field in category.get("required_evidence", []):
        _require_truthy(context, field)
    if category_id == "C10_peer_tip_or_suggestion" and context.get(
        "advice_context_status"
    ) not in {"author_invited", "clear_visible_problem"}:
        raise ValueError("advice requires author invitation or a clear visible problem")

    return {
        "policy_id": selected_policy["policy_id"],
        "category_id": category_id,
        "category_label": category["label"],
        "production_status": status,
        "account_slot": voice_policy["account_slot"],
        "voice_id": voice_id,
        "speaker_motive": str(context["speaker_motive"]).strip(),
        "category_fit_reason": str(context["category_fit_reason"]).strip(),
        "new_value_type": new_value_type,
        "single_primary_speech_act": True,
        "source_restatement_avoided": True,
        "rule": category["rule"],
    }


def apply_taxonomy_to_brief(
    request_payload: dict[str, Any],
    production_contract: dict[str, Any],
) -> dict[str, Any]:
    """Bind the selected speech act into the transient provider brief."""
    payload = deepcopy(request_payload)
    marker = "<panse_production_speech_act>"
    brief = str(payload.get("brief_text", ""))
    if marker in brief:
        raise ValueError("production speech-act contract was already injected")
    block = {
        "policy_id": production_contract["policy_id"],
        "category_id": production_contract["category_id"],
        "category_label": production_contract["category_label"],
        "speaker_motive": production_contract["speaker_motive"],
        "new_value_type": production_contract["new_value_type"],
        "single_primary_speech_act": True,
        "source_restatement_avoided": True,
        "rule": production_contract["rule"],
        "generation_instruction": (
            "先按这个真实发言动机决定说什么，再应用风格；不得总结原帖后补一句空泛评价。"
        ),
    }
    payload["brief_text"] = (
        brief.rstrip()
        + "\n\n"
        + marker
        + json.dumps(block, ensure_ascii=False, sort_keys=True)
        + "</panse_production_speech_act>"
    )
    return payload


def validate_batch_mix(
    production_contracts: list[dict[str, Any]],
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply batch diversity caps without forcing a category onto a poor source fit."""
    selected_policy = policy or load_policy()
    count = len(production_contracts)
    if not count:
        raise ValueError("at least one production contract is required")
    categories = selected_policy["categories"]
    counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for item in production_contracts:
        category_id = item["category_id"]
        counts[category_id] = counts.get(category_id, 0) + 1
        status = categories[category_id]["production_status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    mix = selected_policy["batch_mix"]
    conditional_share = status_counts.get("conditional", 0) / count
    if conditional_share > float(mix["conditional_categories_max_share"]):
        raise ValueError("conditional categories exceed the approved batch share")
    limited_count = status_counts.get("limited", 0)
    limited_cap = max(
        1,
        round(
            count
            * int(mix["limited_categories_combined_max_per_batch_of_6"])
            / 6
        ),
    )
    if limited_count > limited_cap:
        raise ValueError("limited categories exceed the approved batch cap")
    same_category_cap = max(
        1,
        int(count * float(mix["same_category_default_max_share"]) + 0.999999),
    )
    if any(value > same_category_cap for value in counts.values()):
        raise ValueError("one production category dominates the batch")
    return {
        "passed": True,
        "item_count": count,
        "category_counts": counts,
        "status_counts": status_counts,
        "forced_category_balancing": False,
    }
