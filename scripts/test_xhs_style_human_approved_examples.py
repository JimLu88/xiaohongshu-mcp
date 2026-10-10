#!/usr/bin/env python3
"""Verify that Style Lab preflight can load role-matched approved examples."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from prepare_xhs_style_request import select_human_approved_examples
from run_xhs_style_lab import build_runtime_request_payload, load_runtime


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_comment_intent_policy_v4.json"
)


def main() -> int:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    cases = [
        ("stylist", "atmosphere_grounded_praise", ["color_light_atmosphere"]),
        ("evaluation_judgment", "maintenance_durability_question", ["maintenance_lifetime"]),
        ("space_advisor", "size_clearance_question", ["dimensions_fit"]),
        ("global_design_observer", "global_localization_question", ["global_localization"]),
    ]
    results = []
    for voice_id, direction_id, topic_ids in cases:
        corpus, selected = select_human_approved_examples(
            policy,
            voice_id,
            direction_id,
            topic_ids,
        )
        assert corpus["review_status"] == "user_approved"
        assert len(selected) == 3
        assert all(
            item["example_id"].startswith(("review12-", "feedback15-"))
            for item in selected
        )
        results.append(
            {
                "voice_id": voice_id,
                "selected_example_ids": [item["example_id"] for item in selected],
            }
        )
    _corpus, uncovered = select_human_approved_examples(
        policy,
        "official_explanation",
        "detail_grounded_praise",
        ["material_craft"],
    )
    assert uncovered == []
    synthetic = {
        "request_id": "xhs-wrapper-bom-synthetic-001",
        "idempotency_key": "xhs-wrapper-bom-synthetic-001-v1",
        "brief_text": (
            "这是完全合成的家居评论联调简报，只承接可见白墙和浅木色，"
            "不得虚构购买、入住或长期使用经历。"
        ),
        "source_locator": "inline-job://synthetic/wrapper-bom-001",
        "rights_basis": "用户创建的无版权风险合成测试简报",
        "sensitivity": "internal",
        "language": "zh-CN",
        "channel": "小红书",
        "scenario": "家居空间讨论评论",
        "audience": "关注家居配色的普通用户",
        "use_case": "具体支持",
        "artifact_type": "comment",
        "interaction_mode": "support_only",
        "panse_intent_context": {
            "policy_version": "xhs-comment-intent.v4",
            "topic_ids": ["color_light_atmosphere"],
            "interaction_intent": "grounded_praise",
            "comment_direction_id": "atmosphere_grounded_praise",
            "voice_id": "stylist",
            "production_taxonomy_version": "panse-xhs-comment-production-taxonomy.v1",
            "production_category_id": "C02_object_specific_preference",
            "speaker_motive": "我对浅木色边柜这个具体对象确实有偏好",
            "category_fit_reason": "用具体对象偏好回应，不总结整篇内容",
            "new_value_type": "preference",
            "single_primary_speech_act": True,
            "source_restatement_avoided": True,
        },
        "panse_comment_length_context": {
            "policy_id": "panse-xhs-comment-length-mix.v1",
            "batch_id": "synthetic-stylist-15",
            "batch_size": 15,
            "item_index": 6,
            "eligible_tiers": ["very_short", "short", "medium", "long"],
        },
        "source_context": {
            "body": "白墙旁边放了一张浅木色边柜。",
            "visible_comments": [],
            "image_observations": [
                {
                    "locator": "image[0]#reviewed",
                    "observation": "画面里浅木色边柜靠着白墙。",
                    "observation_basis": "caller_reviewed",
                }
            ],
            "body_complete": True,
            "visible_comments_complete": True,
            "images_complete": True,
            "expected_visible_comment_count": 0,
            "expected_image_count": 1,
        },
        "taxonomy_ids": [
            "platform.xiaohongshu-comment",
            "persona.lifestyle-curator",
            "role.editor",
            "scene.social-comment",
        ],
        "requested_strength": 0.5,
        "style_requirement": "taxonomy_fallback_allowed",
        "required_model_id": "gpt-5.6-sol",
        "fallback_model_allowed": False,
        "content_contract": {
            "protected_facts": [],
            "allowed_paraphrases": {},
            "forbidden_inferences": ["我家", "我买过"],
            "citation_anchors": {},
            "must_cover_fact_ids": [],
        },
        "output": {
            "title_candidates": 0,
            "title_max_chars": 0,
            "body_min_chars": 12,
            "body_max_chars": 38,
            "tag_min": 0,
            "tag_max": 0,
        },
        "max_authorized_excerpt_chars": 0,
    }
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("prepare_xhs_style_request.py")), "-"],
        input=b"\xef\xbb\xbf" + json.dumps(synthetic, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    receipt = json.loads(completed.stdout.decode("utf-8"))
    assert receipt["production_taxonomy_verified"] is True
    assert receipt["production_contract"]["category_id"] == (
        "C02_object_specific_preference"
    )
    assert receipt["microgenre_contract"]["comment_direction_id"] == (
        "atmosphere_grounded_praise"
    )
    assert receipt["microgenre_contract"]["current_source_is_only_fact_authority"] is True
    assert receipt["publish_allowed"] is False

    very_short = json.loads(json.dumps(synthetic, ensure_ascii=False))
    very_short["request_id"] = "xhs-wrapper-bom-synthetic-slot2-very-short-001"
    very_short["idempotency_key"] = "xhs-wrapper-bom-synthetic-slot2-very-short-001-v1"
    very_short["interaction_mode"] = "light_humor_or_neutral"
    very_short["panse_intent_context"].update(
        {
            "interaction_intent": "neutral_social",
            "comment_direction_id": "light_social_response",
        }
    )
    very_short["panse_comment_length_context"]["item_index"] = 1
    very_short["output"]["body_min_chars"] = 1
    very_short["output"]["body_max_chars"] = 200
    very_short["style_requirement"] = "approved_required"
    very_short_completed = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("prepare_xhs_style_request.py")), "-"],
        input=b"\xef\xbb\xbf" + json.dumps(very_short, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert very_short_completed.returncode == 0, very_short_completed.stderr.decode(
        "utf-8", errors="replace"
    )
    very_short_receipt = json.loads(very_short_completed.stdout.decode("utf-8"))
    assert very_short_receipt["voice_id"] == "stylist"
    assert very_short_receipt["comment_direction_id"] == "light_social_response"
    assert very_short_receipt["direction_contract"]["character_range"] == {
        "minimum": 3,
        "maximum": 5,
    }
    assert very_short_receipt["direction_contract"][
        "length_tier_override_applied"
    ] is True
    assert very_short_receipt["comment_length_mix"]["allocation"] == {
        "very_short": 3,
        "short": 2,
        "medium": 5,
        "long": 5,
    }
    assert very_short_receipt["text_generated"] is False
    assert very_short_receipt["external_posting_performed"] is False
    runtime_payload = build_runtime_request_payload(
        very_short,
        very_short_receipt,
    )
    request_model, _generate_style_content, _runtime_root = load_runtime()
    runtime_request = request_model.model_validate(runtime_payload)
    assert runtime_request.output.body_min_chars == 3
    assert runtime_request.output.body_max_chars == 5
    assert runtime_request.comment_intent_context.length_tier_id == "very_short"
    assert runtime_request.comment_intent_context.length_override_contract_id == (
        "panse-xhs-role-scoped-comment-length.v1"
    )
    print(
        json.dumps(
            {
                "passed": True,
                "example_set_version": "panse-xhs-human-approved-comments.v3",
                "roles": len(results),
                "selected_per_role": 3,
                "uncovered_roles_keep_existing_style_cards": True,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
