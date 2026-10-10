"""Deterministic Xiaohongshu comment length-mix policy and gates."""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = (
    REPO_ROOT / "configs" / "panse" / "xhs_comment_length_mix_policy_v1.json"
)
LENGTH_MIX_MARKER = "<panse_comment_length_mix>"


def load_length_mix_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected one length-mix policy object: {path}")
    validate_length_mix_policy(value)
    return value


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _ceil_share(batch_size: int, share: object) -> int:
    return int(
        (Decimal(batch_size) * _decimal(share)).to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def _floor_share(batch_size: int, share: object) -> int:
    return int(
        (Decimal(batch_size) * _decimal(share)).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )


def validate_length_mix_policy(policy: dict[str, Any]) -> None:
    if policy.get("policy_id") != "panse-xhs-comment-length-mix.v1":
        raise ValueError("unexpected Xiaohongshu comment length-mix policy id")
    tiers = policy.get("tiers")
    if not isinstance(tiers, list) or len(tiers) != 4:
        raise ValueError("length-mix policy must define exactly four tiers")
    expected_ids = ["very_short", "short", "medium", "long"]
    tier_ids = [str(item.get("tier_id", "")) for item in tiers]
    if tier_ids != expected_ids:
        raise ValueError("length-mix tiers must use the canonical order")
    expected_ranges = [(3, 5), (6, 16), (17, 30), (31, 45)]
    observed_ranges = [
        (int(item.get("minimum_chars", -1)), int(item.get("maximum_chars", -1)))
        for item in tiers
    ]
    if observed_ranges != expected_ranges:
        raise ValueError("length-mix tier ranges do not match the governed contract")
    weights = [_decimal(item.get("default_weight")) for item in tiers]
    if weights != [Decimal("0.15"), Decimal("0.15"), Decimal("0.35"), Decimal("0.35")]:
        raise ValueError("length-mix default weights must be 15/15/35/35")
    if sum(weights) != Decimal("1.00"):
        raise ValueError("length-mix default weights must sum to one")
    constraints = policy.get("batch_constraints", {})
    if (
        _decimal(constraints.get("very_short_min_share")) != Decimal("0.1")
        or _decimal(constraints.get("very_short_max_share")) != Decimal("0.2")
        or _decimal(constraints.get("medium_and_long_min_share"))
        != Decimal("0.6")
    ):
        raise ValueError("length-mix share constraints drifted")
    allocation = policy.get("allocation", {})
    if allocation.get("method") != "constrained_largest_remainder":
        raise ValueError("unsupported length-mix allocation method")
    if allocation.get("tie_break_order") != expected_ids:
        raise ValueError("length-mix tie-break order drifted")


def allocate_length_tiers(
    batch_size: int,
    policy: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Allocate one batch using constrained largest remainder, deterministically."""
    policy = policy or load_length_mix_policy()
    validate_length_mix_policy(policy)
    if not isinstance(batch_size, int) or isinstance(batch_size, bool):
        raise ValueError("comment length-mix batch_size must be an integer")
    minimum = int(policy["minimum_supported_batch_size"])
    if batch_size < minimum:
        raise ValueError(
            f"comment length-mix batch_size={batch_size} is unsupported; "
            f"minimum is {minimum} because the 10%-20% very-short share has no "
            "stable integer allocation below that boundary"
        )

    tiers = policy["tiers"]
    tier_ids = [item["tier_id"] for item in tiers]
    raw = {
        item["tier_id"]: Decimal(batch_size) * _decimal(item["default_weight"])
        for item in tiers
    }
    counts = {
        tier_id: int(raw[tier_id].to_integral_value(rounding=ROUND_FLOOR))
        for tier_id in tier_ids
    }
    remaining = batch_size - sum(counts.values())
    ranked = sorted(
        tier_ids,
        key=lambda tier_id: (
            -(raw[tier_id] - Decimal(counts[tier_id])),
            tier_ids.index(tier_id),
        ),
    )
    for tier_id in ranked[:remaining]:
        counts[tier_id] += 1

    constraints = policy["batch_constraints"]
    very_short_min = _ceil_share(
        batch_size, constraints["very_short_min_share"]
    )
    very_short_max = _floor_share(
        batch_size, constraints["very_short_max_share"]
    )
    medium_long_min = _ceil_share(
        batch_size, constraints["medium_and_long_min_share"]
    )
    if very_short_min > very_short_max:
        raise ValueError(
            f"batch_size={batch_size} cannot satisfy the 10%-20% very-short share"
        )

    def choose_target(candidates: Iterable[str]) -> str:
        return max(
            candidates,
            key=lambda tier_id: (
                raw[tier_id] - Decimal(counts[tier_id]),
                -tier_ids.index(tier_id),
            ),
        )

    def choose_donor(candidates: Iterable[str]) -> str:
        available = [tier_id for tier_id in candidates if counts[tier_id] > 0]
        if not available:
            raise ValueError("length-mix constraints have no valid donor tier")
        return max(
            available,
            key=lambda tier_id: (
                Decimal(counts[tier_id]) - raw[tier_id],
                -tier_ids.index(tier_id),
            ),
        )

    while counts["very_short"] > very_short_max:
        counts["very_short"] -= 1
        counts[choose_target(["short", "medium", "long"])] += 1
    while counts["very_short"] < very_short_min:
        donor = choose_donor(["short", "medium", "long"])
        counts[donor] -= 1
        counts["very_short"] += 1
    while counts["medium"] + counts["long"] < medium_long_min:
        donors = ["short"]
        if counts["very_short"] > very_short_min:
            donors.append("very_short")
        donor = choose_donor(donors)
        target = choose_target(["medium", "long"])
        counts[donor] -= 1
        counts[target] += 1

    _validate_allocation(batch_size, counts, policy)
    return {tier_id: counts[tier_id] for tier_id in tier_ids}


def _validate_allocation(
    batch_size: int,
    counts: dict[str, int],
    policy: dict[str, Any],
) -> None:
    if sum(counts.values()) != batch_size or any(value < 0 for value in counts.values()):
        raise ValueError("length-mix allocation does not sum to the batch size")
    constraints = policy["batch_constraints"]
    very_short = Decimal(counts["very_short"]) / Decimal(batch_size)
    medium_long = Decimal(counts["medium"] + counts["long"]) / Decimal(batch_size)
    if very_short < _decimal(constraints["very_short_min_share"]):
        raise ValueError("very-short allocation is below 10%")
    if very_short > _decimal(constraints["very_short_max_share"]):
        raise ValueError("very-short allocation is above 20%")
    if medium_long < _decimal(constraints["medium_and_long_min_share"]):
        raise ValueError("medium-plus-long allocation is below 60%")


def build_length_assignment(
    context: object,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a request batch context and return its deterministic tier."""
    policy = policy or load_length_mix_policy()
    if not isinstance(context, dict):
        raise ValueError("panse_comment_length_context is required")
    if context.get("policy_id") != policy["policy_id"]:
        raise ValueError("comment length context policy_id does not match the active policy")
    batch_id = str(context.get("batch_id", "")).strip()
    if not batch_id:
        raise ValueError("comment length context requires a non-empty batch_id")
    batch_size = context.get("batch_size")
    item_index = context.get("item_index")
    if not isinstance(batch_size, int) or isinstance(batch_size, bool):
        raise ValueError("comment length context batch_size must be an integer")
    if not isinstance(item_index, int) or isinstance(item_index, bool):
        raise ValueError("comment length context item_index must be an integer")
    if item_index < 1 or item_index > batch_size:
        raise ValueError("comment length context item_index is outside the batch")
    eligible_tiers = context.get("eligible_tiers")
    if not isinstance(eligible_tiers, list) or not eligible_tiers:
        raise ValueError(
            "comment length context requires eligible_tiers so length cannot override relevance"
        )

    known_tiers = {item["tier_id"] for item in policy["tiers"]}
    if any(value not in known_tiers for value in eligible_tiers):
        raise ValueError("comment length context contains an unknown eligible tier")
    human_batch = context.get("delivery_mode") == "human_final_batch"
    if context.get("delivery_mode") not in (None, "human_final_batch"):
        raise ValueError("unknown comment delivery mode")
    if human_batch:
        if not 1 <= batch_size <= 4 or context.get("human_final_submission_required") is not True:
            raise ValueError("human-final small batch requires 1-4 items and manual submission")
        tier_id = context.get("assigned_tier")
        if tier_id not in known_tiers:
            raise ValueError("human-final small batch requires an explicit content-relevant tier")
        allocation = None  # A 4-item batch cannot satisfy a 10%-20% integer share.
    else:
        allocation = allocate_length_tiers(batch_size, policy)
        sequence: list[str] = []
        for item in policy["tiers"]:
            sequence.extend([item["tier_id"]] * allocation[item["tier_id"]])
        tier_id = sequence[item_index - 1]
    if tier_id not in eligible_tiers:
        raise ValueError(
            f"assigned length tier {tier_id!r} is not content-relevant for item "
            f"{item_index}; reorder or replace the batch item instead of padding facts"
        )
    declared_tier = context.get("assigned_tier")
    if declared_tier is not None and declared_tier != tier_id:
        raise ValueError("declared assigned_tier does not match deterministic allocation")
    declared_allocation = context.get("allocation")
    if declared_allocation is not None and declared_allocation != allocation:
        raise ValueError("declared length allocation does not match deterministic allocation")

    tier = next(item for item in policy["tiers"] if item["tier_id"] == tier_id)
    assignment = {
        "policy_id": policy["policy_id"],
        "batch_id": batch_id,
        "batch_size": batch_size,
        "item_index": item_index,
        "tier_id": tier_id,
        "tier_label": tier["label"],
        "minimum_chars": int(tier["minimum_chars"]),
        "maximum_chars": int(tier["maximum_chars"]),
        "allocation": allocation,
        "eligible_tiers": list(eligible_tiers),
    }
    if human_batch:
        assignment.update(delivery_mode="human_final_batch", human_final_submission_required=True,
                          batch_percentage_quota_applied=False)
    return assignment


def apply_length_assignment_to_request(
    request_payload: dict[str, Any],
    assignment: dict[str, Any],
) -> dict[str, Any]:
    """Inject the assigned tier into both the prompt and runtime output bounds."""
    payload = dict(request_payload)
    brief = str(payload.get("brief_text", ""))
    if LENGTH_MIX_MARKER in brief:
        raise ValueError("comment length-mix contract was already injected")
    block = {
        **assignment,
        "generation_instruction": (
            f"本条必须保持在{assignment['minimum_chars']}–"
            f"{assignment['maximum_chars']}字；优先保留与当前内容直接相关的落点。"
            "若可靠内容无法在该档位表达，必须失败，不得补写、虚构或改变事实来凑长度。"
        ),
    }
    payload["brief_text"] = (
        brief.rstrip()
        + "\n\n"
        + LENGTH_MIX_MARKER
        + json.dumps(block, ensure_ascii=False, sort_keys=True)
        + "</panse_comment_length_mix>"
    )
    output = dict(payload.get("output") or {})
    output["body_min_chars"] = max(
        int(output.get("body_min_chars", 1)),
        assignment["minimum_chars"],
    )
    output["body_max_chars"] = min(
        int(output.get("body_max_chars", 20_000)),
        assignment["maximum_chars"],
    )
    if output["body_min_chars"] > output["body_max_chars"]:
        raise ValueError(
            "assigned length tier does not overlap the active comment-direction range; "
            "reorder or replace the batch item instead of weakening either contract"
        )
    payload["output"] = output
    return payload


def count_comment_chars(text: str) -> int:
    if not isinstance(text, str):
        raise ValueError("comment text must be a string")
    return len(text.strip())


def classify_comment_length(
    text: str,
    policy: dict[str, Any] | None = None,
) -> str:
    policy = policy or load_length_mix_policy()
    length = count_comment_chars(text)
    for tier in policy["tiers"]:
        if int(tier["minimum_chars"]) <= length <= int(tier["maximum_chars"]):
            return str(tier["tier_id"])
    raise ValueError(f"comment length {length} is outside the governed 3-45 range")


def validate_generated_comment_length(
    text: str,
    assignment: dict[str, Any],
    effective_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    length = count_comment_chars(text)
    minimum = int(
        (effective_output or {}).get("body_min_chars", assignment["minimum_chars"])
    )
    maximum = int(
        (effective_output or {}).get("body_max_chars", assignment["maximum_chars"])
    )
    if minimum < assignment["minimum_chars"] or maximum > assignment["maximum_chars"]:
        raise ValueError("effective output range escapes the assigned length tier")
    if minimum > maximum:
        raise ValueError("effective output range is invalid")
    if length < minimum or length > maximum:
        raise ValueError(
            "comment length-mix gate rejected generated draft: "
            f"item {assignment['item_index']} requires tier {assignment['tier_id']} "
            f"({minimum}-{maximum} effective chars), "
            f"observed {length} chars"
        )
    return {
        "policy_id": assignment["policy_id"],
        "batch_id": assignment["batch_id"],
        "batch_size": assignment["batch_size"],
        "item_index": assignment["item_index"],
        "tier_id": assignment["tier_id"],
        "observed_chars": length,
        "effective_minimum_chars": minimum,
        "effective_maximum_chars": maximum,
        "assigned_range_verified": True,
    }


def _extract_comment_text(item: object) -> str:
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        raise ValueError("each comment must be a string or object")
    for key in ("text", "draft_text", "exact_draft_text"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    draft = item.get("draft")
    if isinstance(draft, dict) and isinstance(draft.get("draft_text"), str):
        return draft["draft_text"]
    raise ValueError("comment object has no supported text field")


def validate_comment_batch(
    comments: object,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an explicit blocking result for any invalid or drifted batch."""
    policy = policy or load_length_mix_policy()
    if not isinstance(comments, list):
        raise ValueError("comment batch must be a list")
    batch_size = len(comments)
    reasons: list[str] = []
    try:
        expected = allocate_length_tiers(batch_size, policy)
    except ValueError as exc:
        return {
            "policy_id": policy["policy_id"],
            "status": "blocked",
            "length_mix_gate_passed": False,
            "batch_may_enter_sendable_state": False,
            "batch_size": batch_size,
            "reasons": [str(exc)],
        }

    actual = {item["tier_id"]: 0 for item in policy["tiers"]}
    item_results: list[dict[str, Any]] = []
    for index, item in enumerate(comments, 1):
        try:
            text = _extract_comment_text(item)
            tier_id = classify_comment_length(text, policy)
            length = count_comment_chars(text)
            actual[tier_id] += 1
            item_results.append(
                {"item_index": index, "tier_id": tier_id, "observed_chars": length}
            )
        except ValueError as exc:
            reasons.append(f"item {index}: {exc}")

    for tier_id, expected_count in expected.items():
        if actual[tier_id] != expected_count:
            reasons.append(
                f"tier {tier_id} expected {expected_count}, observed {actual[tier_id]}"
            )
    very_short_share = Decimal(actual["very_short"]) / Decimal(batch_size)
    medium_long_share = Decimal(actual["medium"] + actual["long"]) / Decimal(
        batch_size
    )
    constraints = policy["batch_constraints"]
    if very_short_share < _decimal(constraints["very_short_min_share"]):
        reasons.append("very-short comments are below 10%")
    if very_short_share > _decimal(constraints["very_short_max_share"]):
        reasons.append("very-short comments are above 20%")
    if medium_long_share < _decimal(constraints["medium_and_long_min_share"]):
        reasons.append("medium-plus-long comments are below 60%")

    passed = not reasons
    return {
        "policy_id": policy["policy_id"],
        "status": "passed" if passed else "blocked",
        "length_mix_gate_passed": passed,
        "batch_may_enter_sendable_state": passed,
        "batch_size": batch_size,
        "expected_distribution": expected,
        "observed_distribution": actual,
        "very_short_share": float(very_short_share),
        "medium_and_long_share": float(medium_long_share),
        "items": item_results,
        "reasons": reasons,
    }
