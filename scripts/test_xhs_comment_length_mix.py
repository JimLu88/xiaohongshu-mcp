#!/usr/bin/env python3
"""Regression tests for the governed Xiaohongshu comment length mix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.xhs_comment_length_mix import (
    LENGTH_MIX_MARKER,
    allocate_length_tiers,
    apply_length_assignment_to_request,
    build_length_assignment,
    load_length_mix_policy,
    validate_comment_batch,
    validate_generated_comment_length,
)
from prepare_xhs_style_request import resolve_direction_length_contract


POLICY_ID = "panse-xhs-comment-length-mix.v1"
ALL_TIERS = ["very_short", "short", "medium", "long"]
INTENT_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "panse_multi_direction"
    / "xhs_comment_intent_policy_v4.json"
)


def load_intent_policy() -> dict:
    return json.loads(INTENT_POLICY_PATH.read_text(encoding="utf-8"))


def context(batch_size: int, item_index: int, **extra: object) -> dict:
    value = {
        "policy_id": POLICY_ID,
        "batch_id": f"synthetic-{batch_size}",
        "batch_size": batch_size,
        "item_index": item_index,
        "eligible_tiers": list(ALL_TIERS),
    }
    value.update(extra)
    return value


def test_single_policy_source_has_exact_ranges_weights_and_constraints() -> None:
    policy = load_length_mix_policy()
    assert [
        (item["minimum_chars"], item["maximum_chars"])
        for item in policy["tiers"]
    ] == [(3, 5), (6, 16), (17, 30), (31, 45)]
    assert [item["default_weight"] for item in policy["tiers"]] == [
        0.15,
        0.15,
        0.35,
        0.35,
    ]
    assert policy["batch_constraints"] == {
        "very_short_min_share": 0.1,
        "very_short_max_share": 0.2,
        "medium_and_long_min_share": 0.6,
    }


@pytest.mark.parametrize(
    "batch_size, expected",
    [
        (5, {"very_short": 1, "short": 1, "medium": 2, "long": 1}),
        (12, {"very_short": 2, "short": 2, "medium": 4, "long": 4}),
        (14, {"very_short": 2, "short": 2, "medium": 5, "long": 5}),
        (15, {"very_short": 3, "short": 2, "medium": 5, "long": 5}),
    ],
)
def test_common_batch_allocations_are_deterministic(
    batch_size: int,
    expected: dict[str, int],
) -> None:
    assert allocate_length_tiers(batch_size) == expected
    assert allocate_length_tiers(batch_size) == expected


def test_four_item_boundary_is_rejected_as_integer_infeasible() -> None:
    with pytest.raises(ValueError, match="minimum is 5"):
        allocate_length_tiers(4)


def test_rounding_adjustment_keeps_nine_item_very_short_share_under_twenty() -> None:
    assert allocate_length_tiers(9) == {
        "very_short": 1,
        "short": 2,
        "medium": 3,
        "long": 3,
    }


@pytest.mark.parametrize("batch_size", range(5, 101))
def test_every_supported_batch_obeys_share_invariants(batch_size: int) -> None:
    allocation = allocate_length_tiers(batch_size)
    assert 0.10 <= allocation["very_short"] / batch_size <= 0.20
    assert (allocation["medium"] + allocation["long"]) / batch_size >= 0.60
    assert sum(allocation.values()) == batch_size


def test_fourteen_item_assignment_is_exact_two_two_five_five() -> None:
    assignments = [build_length_assignment(context(14, index)) for index in range(1, 15)]
    observed = {tier_id: 0 for tier_id in ALL_TIERS}
    for assignment in assignments:
        observed[assignment["tier_id"]] += 1
        assert assignment["allocation"] == {
            "very_short": 2,
            "short": 2,
            "medium": 5,
            "long": 5,
        }
    assert observed == {"very_short": 2, "short": 2, "medium": 5, "long": 5}


def test_content_ineligible_assignment_blocks_instead_of_padding_facts() -> None:
    with pytest.raises(ValueError, match="not content-relevant"):
        build_length_assignment(
            context(14, 1, eligible_tiers=["medium", "long"])
        )


def test_generation_constraint_uses_assigned_range_and_policy_marker() -> None:
    assignment = build_length_assignment(context(14, 5))
    payload = apply_length_assignment_to_request(
        {
            "brief_text": "只使用给定内容依据，不补事实。",
            "output": {"body_min_chars": 1, "body_max_chars": 200},
        },
        assignment,
    )
    assert LENGTH_MIX_MARKER in payload["brief_text"]
    assert payload["output"] == {"body_min_chars": 17, "body_max_chars": 30}


def test_generation_constraint_preserves_stricter_direction_range() -> None:
    assignment = build_length_assignment(context(14, 5))
    payload = apply_length_assignment_to_request(
        {
            "brief_text": "只使用给定内容依据，不补事实。",
            "output": {"body_min_chars": 25, "body_max_chars": 70},
        },
        assignment,
    )
    assert payload["output"] == {"body_min_chars": 25, "body_max_chars": 30}


def test_nonoverlapping_direction_and_length_tier_blocks() -> None:
    assignment = build_length_assignment(context(14, 1))
    with pytest.raises(ValueError, match="does not overlap"):
        apply_length_assignment_to_request(
            {
                "brief_text": "只使用给定内容依据，不补事实。",
                "output": {"body_min_chars": 25, "body_max_chars": 70},
            },
            assignment,
        )


def test_official_light_response_has_verified_very_short_override() -> None:
    policy = load_intent_policy()
    role = policy["roles"]["official_explanation"]
    direction = policy["directions"]["light_social_response"]
    assignment = build_length_assignment(context(12, 1))
    contract = resolve_direction_length_contract(
        voice_id="official_explanation",
        role_policy=role,
        comment_direction_id="light_social_response",
        direction_policy=direction,
        length_assignment=assignment,
        official_contracts_verified=True,
    )
    assert contract["character_range"] == {"minimum": 3, "maximum": 5}
    assert contract["length_tier_override_applied"] is True


def test_official_twelve_item_batch_keeps_two_two_four_four() -> None:
    policy = load_intent_policy()
    role = policy["roles"]["official_explanation"]
    direction = policy["directions"]["light_social_response"]
    observed = {tier_id: 0 for tier_id in ALL_TIERS}
    for item_index in range(1, 13):
        assignment = build_length_assignment(context(12, item_index))
        observed[assignment["tier_id"]] += 1
        contract = resolve_direction_length_contract(
            voice_id="official_explanation",
            role_policy=role,
            comment_direction_id="light_social_response",
            direction_policy=direction,
            length_assignment=assignment,
            official_contracts_verified=True,
        )
        payload = apply_length_assignment_to_request(
            {
                "brief_text": "只回应一个已核实的可见点。",
                "output": {
                    "body_min_chars": contract["character_range"]["minimum"],
                    "body_max_chars": contract["character_range"]["maximum"],
                },
            },
            assignment,
        )
        assert payload["output"]["body_min_chars"] <= payload["output"]["body_max_chars"]
    assert observed == {"very_short": 2, "short": 2, "medium": 4, "long": 4}


def test_slot2_stylist_very_short_override_requires_nonofficial_contracts() -> None:
    policy = load_intent_policy()
    assignment = build_length_assignment(context(15, 1))
    contract = resolve_direction_length_contract(
        voice_id="stylist",
        role_policy=policy["roles"]["stylist"],
        comment_direction_id="light_social_response",
        direction_policy=policy["directions"]["light_social_response"],
        length_assignment=assignment,
        official_contracts_verified=False,
        nonofficial_contracts_verified=True,
    )
    assert contract["character_range"] == {"minimum": 3, "maximum": 5}
    assert contract["length_tier_override_applied"] is True
    assert contract["length_tier_override"]["voice_id"] == "stylist"


def test_slot2_fifteen_item_light_response_contract_keeps_three_two_five_five() -> None:
    policy = load_intent_policy()
    observed = {tier_id: 0 for tier_id in ALL_TIERS}
    for item_index in range(1, 16):
        assignment = build_length_assignment(context(15, item_index))
        observed[assignment["tier_id"]] += 1
        contract = resolve_direction_length_contract(
            voice_id="stylist",
            role_policy=policy["roles"]["stylist"],
            comment_direction_id="light_social_response",
            direction_policy=policy["directions"]["light_social_response"],
            length_assignment=assignment,
            official_contracts_verified=False,
            nonofficial_contracts_verified=True,
        )
        payload = apply_length_assignment_to_request(
            {
                "brief_text": "只顺着一个已核实的具体点自然接一句。",
                "output": {
                    "body_min_chars": contract["character_range"]["minimum"],
                    "body_max_chars": contract["character_range"]["maximum"],
                },
            },
            assignment,
        )
        assert payload["output"]["body_min_chars"] <= payload["output"]["body_max_chars"]
    assert observed == {"very_short": 3, "short": 2, "medium": 5, "long": 5}


def test_slot2_stylist_override_fails_without_verified_nonofficial_contracts() -> None:
    policy = load_intent_policy()
    with pytest.raises(ValueError, match="requires verified nonofficial contracts"):
        resolve_direction_length_contract(
            voice_id="stylist",
            role_policy=policy["roles"]["stylist"],
            comment_direction_id="light_social_response",
            direction_policy=policy["directions"]["light_social_response"],
            length_assignment=build_length_assignment(context(15, 1)),
            official_contracts_verified=False,
            nonofficial_contracts_verified=False,
        )


def test_slot3_seven_item_allocation_is_one_one_three_two() -> None:
    assert allocate_length_tiers(7) == {
        "very_short": 1,
        "short": 1,
        "medium": 3,
        "long": 2,
    }


@pytest.mark.parametrize("batch_size", range(5, 16))
def test_slot3_all_supported_daily_batch_sizes_have_safe_length_routes(
    batch_size: int,
) -> None:
    policy = load_intent_policy()
    role = policy["roles"]["evaluation_judgment"]
    direction = policy["directions"]["size_clearance_question"]
    for item_index in range(1, batch_size + 1):
        assignment = build_length_assignment(context(batch_size, item_index))
        contract = resolve_direction_length_contract(
            voice_id="evaluation_judgment",
            role_policy=role,
            comment_direction_id="size_clearance_question",
            direction_policy=direction,
            length_assignment=assignment,
            official_contracts_verified=False,
            nonofficial_contracts_verified=True,
        )
        effective = apply_length_assignment_to_request(
            {
                "brief_text": "只问一个尚未回答、直接影响购买适配的尺寸问题。",
                "output": {
                    "body_min_chars": contract["character_range"]["minimum"],
                    "body_max_chars": contract["character_range"]["maximum"],
                },
            },
            assignment,
        )["output"]
        minimum = effective["body_min_chars"]
        maximum = effective["body_max_chars"]
        assert contract["base_character_range"] == {"minimum": 18, "maximum": 55}
        assert minimum <= maximum
        assert validate_generated_comment_length(
            "界" * minimum, assignment, effective
        )["assigned_range_verified"] is True
        assert validate_generated_comment_length(
            "界" * maximum, assignment, effective
        )["assigned_range_verified"] is True
        with pytest.raises(ValueError, match="length-mix gate rejected"):
            validate_generated_comment_length("界" * (minimum - 1), assignment, effective)
        with pytest.raises(ValueError, match="length-mix gate rejected"):
            validate_generated_comment_length("界" * (maximum + 1), assignment, effective)
        if assignment["tier_id"] in {"very_short", "short"}:
            assert contract["length_tier_override_applied"] is True
            assert contract["length_tier_override"]["comment_direction_id"] == (
                "size_clearance_question"
            )
        else:
            assert contract["length_tier_override_applied"] is False


def test_slot3_short_routes_require_verified_taxonomy_and_single_speech_act() -> None:
    policy = load_intent_policy()
    with pytest.raises(ValueError, match="requires verified nonofficial contracts"):
        resolve_direction_length_contract(
            voice_id="evaluation_judgment",
            role_policy=policy["roles"]["evaluation_judgment"],
            comment_direction_id="size_clearance_question",
            direction_policy=policy["directions"]["size_clearance_question"],
            length_assignment=build_length_assignment(context(7, 1)),
            official_contracts_verified=False,
            nonofficial_contracts_verified=False,
        )


def test_slot4_space_advisor_layout_question_has_verified_very_short_override() -> None:
    policy = load_intent_policy()
    assignment = build_length_assignment(context(14, 1))
    contract = resolve_direction_length_contract(
        voice_id="space_advisor",
        role_policy=policy["roles"]["space_advisor"],
        comment_direction_id="layout_circulation_question",
        direction_policy=policy["directions"]["layout_circulation_question"],
        length_assignment=assignment,
        official_contracts_verified=False,
        nonofficial_contracts_verified=True,
    )
    assert contract["character_range"] == {"minimum": 3, "maximum": 5}
    assert contract["base_character_range"] == {"minimum": 18, "maximum": 55}
    assert contract["length_tier_override_applied"] is True
    assert contract["length_tier_override"]["voice_id"] == "space_advisor"


def test_slot4_space_advisor_layout_question_has_verified_short_override() -> None:
    policy = load_intent_policy()
    assignment = build_length_assignment(context(14, 3))
    contract = resolve_direction_length_contract(
        voice_id="space_advisor",
        role_policy=policy["roles"]["space_advisor"],
        comment_direction_id="layout_circulation_question",
        direction_policy=policy["directions"]["layout_circulation_question"],
        length_assignment=assignment,
        official_contracts_verified=False,
        nonofficial_contracts_verified=True,
    )
    assert contract["character_range"] == {"minimum": 6, "maximum": 16}
    assert contract["base_character_range"] == {"minimum": 18, "maximum": 55}
    assert contract["length_tier_override_applied"] is True
    assert contract["length_tier_override"] == {
        "voice_id": "space_advisor",
        "tier_id": "short",
        "comment_direction_id": "layout_circulation_question",
        "requires": [
            "production_taxonomy_verified",
            "single_primary_speech_act_verified",
            "source_context_complete",
        ],
        "generation_instruction": (
            "只问一个原帖和当前评论未回答的日常动作问题；保留问号，"
            "控制在6—16字，不得补事实、下诊断或写空泛套话。"
        ),
    }


def test_slot4_space_advisor_override_fails_without_verified_nonofficial_contracts() -> None:
    policy = load_intent_policy()
    with pytest.raises(ValueError, match="requires verified nonofficial contracts"):
        resolve_direction_length_contract(
            voice_id="space_advisor",
            role_policy=policy["roles"]["space_advisor"],
            comment_direction_id="layout_circulation_question",
            direction_policy=policy["directions"]["layout_circulation_question"],
            length_assignment=build_length_assignment(context(14, 1)),
            official_contracts_verified=False,
            nonofficial_contracts_verified=False,
        )


def test_official_very_short_override_fails_without_verified_contracts() -> None:
    policy = load_intent_policy()
    with pytest.raises(ValueError, match="requires verified official contracts"):
        resolve_direction_length_contract(
            voice_id="official_explanation",
            role_policy=policy["roles"]["official_explanation"],
            comment_direction_id="light_social_response",
            direction_policy=policy["directions"]["light_social_response"],
            length_assignment=build_length_assignment(context(12, 1)),
            official_contracts_verified=False,
        )


def test_nonofficial_voice_cannot_inherit_the_official_override() -> None:
    policy = load_intent_policy()
    contract = resolve_direction_length_contract(
        voice_id="principal_sincere_signed",
        role_policy=policy["roles"]["principal_sincere_signed"],
        comment_direction_id="light_social_response",
        direction_policy=policy["directions"]["light_social_response"],
        length_assignment=build_length_assignment(context(12, 1)),
        official_contracts_verified=True,
    )
    assert contract["character_range"] == {"minimum": 8, "maximum": 32}
    assert contract["length_tier_override_applied"] is False


def test_generated_item_outside_assigned_tier_is_rejected() -> None:
    assignment = build_length_assignment(context(14, 1))
    with pytest.raises(ValueError, match="observed 6 chars"):
        validate_generated_comment_length("短短短短短短", assignment)


def test_generated_item_must_also_meet_stricter_effective_range() -> None:
    assignment = build_length_assignment(context(14, 5))
    with pytest.raises(ValueError, match="observed 20 chars"):
        validate_generated_comment_length(
            "中" * 20,
            assignment,
            {"body_min_chars": 25, "body_max_chars": 30},
        )


def test_complete_fourteen_item_batch_passes_sendable_length_gate() -> None:
    comments = (
        ["极" * 3] * 2
        + ["短" * 6] * 2
        + ["中" * 17] * 5
        + ["长" * 31] * 5
    )
    result = validate_comment_batch(comments)
    assert result["length_mix_gate_passed"] is True
    assert result["batch_may_enter_sendable_state"] is True
    assert result["observed_distribution"] == {
        "very_short": 2,
        "short": 2,
        "medium": 5,
        "long": 5,
    }
    assert 0.10 <= result["very_short_share"] <= 0.20
    assert result["medium_and_long_share"] >= 0.60


def test_shortened_batch_is_explicitly_blocked_from_sendable_state() -> None:
    result = validate_comment_batch(["短" * 6] * 14)
    assert result["status"] == "blocked"
    assert result["length_mix_gate_passed"] is False
    assert result["batch_may_enter_sendable_state"] is False
    assert any("medium-plus-long" in reason for reason in result["reasons"])
