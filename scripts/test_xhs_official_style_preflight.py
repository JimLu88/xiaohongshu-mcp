#!/usr/bin/env python3
"""Unit checks for the official topic gate in Style Lab preflight."""

from __future__ import annotations

import copy
import json

from prepare_xhs_style_request import (
    OFFICIAL_PROFESSIONAL_VALUE_PATH,
    OFFICIAL_TOPIC_STRATEGY_PATH,
    validate_official_professional_value_context,
    validate_official_topic_context,
)


def expect_failure(context: object, policy: dict, validator=validate_official_topic_context) -> None:
    try:
        validator(context, policy)
    except ValueError:
        return
    raise AssertionError("expected official topic preflight to fail")


def main() -> int:
    strategy = json.loads(OFFICIAL_TOPIC_STRATEGY_PATH.read_text(encoding="utf-8"))
    professional_value = json.loads(
        OFFICIAL_PROFESSIONAL_VALUE_PATH.read_text(encoding="utf-8")
    )
    valid = {
        "strategy_id": "panse-official-topic-strategy.v1",
        "topic_id": "real_space_use",
        "source_author_intent": "share_real_home_use",
        "target_relationship": "third_party_creator",
        "visible_detail_grounded": True,
        "visible_comment_context_read": True,
        "question_answered_in_context": False,
        "panse_reply_right": "peer_observation",
    }
    assert validate_official_topic_context(valid, strategy) == valid
    expect_failure(None, strategy)
    missing_right = copy.deepcopy(valid)
    missing_right.pop("panse_reply_right")
    expect_failure(missing_right, strategy)
    answered = copy.deepcopy(valid)
    answered["question_answered_in_context"] = True
    expect_failure(answered, strategy)
    unknown_topic = copy.deepcopy(valid)
    unknown_topic["topic_id"] = "unrelated_hotspot"
    expect_failure(unknown_topic, strategy)

    reasoned_praise = {
        "contract_id": "panse-official-professional-value.v1",
        "value_mode": "professional_reasoned_praise",
        "professional_basis_type": "visible_measurement_relation",
        "professional_basis_text": "正文写明2.5米开间和80厘米沙发侧宽",
        "useful_takeaway_present": True,
        "fact_source_status": "source_visible",
        "praise_reason_precedes_praise": True,
    }
    assert (
        validate_official_professional_value_context(
            reasoned_praise, professional_value
        )
        == reasoned_praise
    )
    empty_basis = copy.deepcopy(reasoned_praise)
    empty_basis["professional_basis_text"] = ""
    expect_failure(
        empty_basis, professional_value, validate_official_professional_value_context
    )
    generic_praise = copy.deepcopy(reasoned_praise)
    generic_praise["praise_reason_precedes_praise"] = False
    expect_failure(
        generic_praise, professional_value, validate_official_professional_value_context
    )

    safe_advice = {
        "contract_id": "panse-official-professional-value.v1",
        "value_mode": "conditional_practical_advice",
        "professional_basis_type": "conditional_domain_practice",
        "professional_basis_text": "作者展示了局部维修后仍有明显色差",
        "useful_takeaway_present": True,
        "fact_source_status": "conditional_no_external_claim",
        "advice_context_status": "visible_problem_present",
        "conditional_language_present": True,
    }
    assert (
        validate_official_professional_value_context(safe_advice, professional_value)
        == safe_advice
    )
    hard_unverified_advice = copy.deepcopy(safe_advice)
    hard_unverified_advice["conditional_language_present"] = False
    expect_failure(
        hard_unverified_advice,
        professional_value,
        validate_official_professional_value_context,
    )
    uninvited_advice = copy.deepcopy(safe_advice)
    uninvited_advice["advice_context_status"] = "uninvited_critique"
    expect_failure(
        uninvited_advice,
        professional_value,
        validate_official_professional_value_context,
    )

    print(json.dumps({"passed": True, "assertions": 11}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
