#!/usr/bin/env python3
"""Regression tests for the 600-comment production taxonomy and real-run gate."""

from __future__ import annotations

import pytest

from lib.xhs_comment_production_taxonomy import (
    apply_taxonomy_to_brief,
    validate_batch_mix,
    validate_production_context,
)
from run_xhs_style_lab import (
    OFFICIAL_GOVERNANCE_MARKER,
    PUBLIC_COMMENT_POLICY_MARKER,
    build_runtime_request_payload,
    validate_preflight_governance,
    verify_actual_run,
)


POLICY_ID = "panse-xhs-comment-production-taxonomy.v1"


def official_preflight() -> dict:
    return {
        "voice_id": "official_explanation",
        "production_taxonomy_verified": False,
        "production_contract": None,
        "official_topic_strategy_id": "panse-official-topic-strategy.v1",
        "official_topic_context": {
            "strategy_id": "panse-official-topic-strategy.v1",
            "topic_id": "maintenance_longevity",
            "panse_reply_right": "conditional_fact_only",
        },
        "official_professional_value_contract_id": (
            "panse-official-professional-value.v1"
        ),
        "official_professional_value_context": {
            "contract_id": "panse-official-professional-value.v1",
            "value_mode": "professional_observation",
            "professional_basis_text": "短期外观不能替代跨季节观察。",
        },
        "intent_policy_version": "xhs-comment-intent.v4",
        "topic_ids": ["maintenance_lifetime"],
        "interaction_intent": "request_more",
        "comment_direction_id": "request_more_evidence",
        "human_approved_example_set_version": "panse-xhs-human-approved-comments.v3",
        "direction_contract": {"character_range": {"minimum": 25, "maximum": 70}},
    }


def official_request() -> dict:
    return {
        "request_id": "synthetic-official-runner-regression",
        "brief_text": "这是不联网、不发布的官方号合成回归简报。",
        "style_requirement": "approved_required",
        "required_model_id": "gpt-5.6-sol",
        "fallback_model_allowed": False,
        "panse_intent_context": {"voice_id": "official_explanation"},
        "panse_official_topic_context": {"must_not_reach_runtime_schema": True},
        "panse_official_professional_value_context": {
            "must_not_reach_runtime_schema": True
        },
        "output": {"body_min_chars": 1, "body_max_chars": 200},
    }


def context(category_id: str, new_value_type: str, **extra: object) -> dict:
    value = {
        "production_taxonomy_version": POLICY_ID,
        "production_category_id": category_id,
        "speaker_motive": "我确实想回应这个具体点",
        "category_fit_reason": "正文提供了一个可以自然接话的具体落点",
        "new_value_type": new_value_type,
        "single_primary_speech_act": True,
        "source_restatement_avoided": True,
    }
    value.update(extra)
    return value


def test_preferred_category_binds_speaker_motive_into_transient_brief() -> None:
    contract = validate_production_context(
        context("C02_object_specific_preference", "preference"),
        "global_design_observer",
    )
    payload = apply_taxonomy_to_brief(
        {"brief_text": "这是一份完整的合成评论简报，不包含任何真实账号或外部动作。"},
        contract,
    )
    assert contract["account_slot"] == 5
    assert contract["production_status"] == "preferred"
    assert "<panse_production_speech_act>" in payload["brief_text"]
    assert "不得总结原帖后补一句空泛评价" in payload["brief_text"]


def test_editorial_summary_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="not eligible"):
        validate_production_context(
            context("C16_editorial_summary_or_aphorism", "summary"),
            "global_design_observer",
        )


def test_verified_experience_fails_without_current_account_evidence() -> None:
    with pytest.raises(ValueError, match="verified_firsthand_experience"):
        validate_production_context(
            context("C08_verified_experience_share", "verified_experience"),
            "evaluation_judgment",
        )


def test_category_must_match_the_account_voice() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        validate_production_context(
            context("C11_stance_or_disagreement", "respectful_stance", respectful_non_verdict_tone=True),
            "space_advisor",
        )


def test_batch_mix_rejects_conditional_dominance() -> None:
    items = [
        {"category_id": "C05_acquisition_price_channel_question"},
        {"category_id": "C05_acquisition_price_channel_question"},
        {"category_id": "C02_object_specific_preference"},
        {"category_id": "C03_dimension_layout_fit_question"},
    ]
    with pytest.raises(ValueError, match="conditional categories"):
        validate_batch_mix(items)


def test_official_runner_accepts_verified_official_contracts_without_category() -> None:
    preflight = official_preflight()
    assert validate_preflight_governance(preflight) == "official"
    payload = build_runtime_request_payload(official_request(), preflight)
    assert OFFICIAL_GOVERNANCE_MARKER in payload["brief_text"]
    assert PUBLIC_COMMENT_POLICY_MARKER in payload["brief_text"]
    assert "panse_official_topic_context" not in payload
    assert "panse_official_professional_value_context" not in payload
    assert "comment_intent_context" not in payload
    assert payload["required_model_id"] == "gpt-5.6-sol"
    assert payload["fallback_model_allowed"] is False


def test_nonofficial_runner_still_requires_production_category() -> None:
    preflight = official_preflight()
    preflight.update(
        {
            "voice_id": "global_design_observer",
            "official_topic_strategy_id": None,
            "official_topic_context": None,
            "official_professional_value_contract_id": None,
            "official_professional_value_context": None,
        }
    )
    with pytest.raises(RuntimeError, match="verified production_category_id"):
        validate_preflight_governance(preflight)


def test_real_run_gate_rejects_manually_labeled_stage_files() -> None:
    fake = {
        "provider_runs": [
            {"stage": stage, "ok": True, "provider": "codex.current_session", "model_id": "gpt-5.6-sol"}
            for stage in ("plan", "draft", "semantic_review")
        ],
        "delivery_ready_for_human_review": True,
        "publish_allowed": False,
        "side_effects": {},
    }
    with pytest.raises(ValueError, match="real Codex provider"):
        verify_actual_run(fake)


def test_real_run_gate_accepts_actual_provider_trace_only() -> None:
    result = {
        "provider_runs": [
            {
                "stage": stage,
                "ok": True,
                "provider": "tachikoma.codex_subscription",
                "model_id": "gpt-5.6-sol",
            }
            for stage in ("plan", "draft", "semantic_review")
        ],
        "delivery_ready_for_human_review": True,
        "publish_allowed": False,
        "provider_contract": {
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
        },
        "side_effects": {
            "style_card_write": False,
            "brief_persisted": False,
            "memory_write": False,
            "published": False,
        },
        "draft": {"draft_text": "桌腿和围板的连接细节讲清楚就够了。"},
    }
    verification = verify_actual_run(result)
    assert verification["actual_style_lab_run_verified"] is True
    assert verification["completed_stages"] == ["plan", "draft", "semantic_review"]
    assert verification["public_comment_text_policy"] == {
        "policy_id": "panse-xhs-public-comment-text.v1",
        "public_comment_text_policy_verified": True,
        "forbidden_literal_terms_absent": True,
        "template_opening_absent": True,
    }


def actual_result(draft_text: str) -> dict:
    return {
        "provider_runs": [
            {
                "stage": stage,
                "ok": True,
                "provider": "tachikoma.codex_subscription",
                "model_id": "gpt-5.6-sol",
            }
            for stage in ("plan", "draft", "semantic_review")
        ],
        "delivery_ready_for_human_review": True,
        "publish_allowed": False,
        "provider_contract": {
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
        },
        "side_effects": {
            "style_card_write": False,
            "brief_persisted": False,
            "memory_write": False,
            "published": False,
        },
        "draft": {"draft_text": draft_text},
    }


@pytest.mark.parametrize(
    "draft_text, expected_error",
    [
        ("畔色木作觉得这个连接方式更稳。", "literal brand name"),
        ("官方想追问一下，这里用的是什么木材？", "template opening"),
        ("官方补充一句：桌腿和围板之间还要看连接件。", "template opening"),
        ("提醒一句，潮湿环境下还要留意木材变化。", "template opening"),
    ],
)
def test_real_run_gate_rejects_brand_name_and_template_openings(
    draft_text: str,
    expected_error: str,
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        verify_actual_run(actual_result(draft_text))


def test_real_run_gate_keeps_affiliation_disclosure_without_brand_full_name() -> None:
    verification = verify_actual_run(
        actual_result("先说明，这个账号由品牌运营；这处连接还要结合安装图再判断。")
    )
    assert verification["public_comment_text_policy"][
        "public_comment_text_policy_verified"
    ] is True
