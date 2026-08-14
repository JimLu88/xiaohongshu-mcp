from __future__ import annotations

import json

from build_xhs_full_context_blind_pilot import build, reversal_cases


def test_real_pilot_has_exact_five_unique_full_context_items():
    packet_a, packet_b, manifest = build()
    assert len(packet_a["items"]) == len(packet_b["items"]) == 5
    assert len({item["context_sha256"] for item in packet_a["items"]}) == 5
    assert {item["context_sha256"] for item in packet_a["items"]} == {
        item["context_sha256"] for item in packet_b["items"]
    }
    assert [item["context_sha256"] for item in packet_a["items"]] != [
        item["context_sha256"] for item in packet_b["items"]
    ]
    for item in packet_a["items"]:
        assert item["context"]["body"]
        assert item["context"]["visible_comments"]
        image = item["context"]["image_observation"]
        assert image["image_count"] == 0 or image["images_viewed"] >= min(image["image_count"], 6)
        assert item["candidate"]
        assert item["decision"] is None
    assert manifest["remaining_real_context_gap"] == 25
    assert manifest["independent_reviews_completed"] == 0


def test_reversals_target_structure_not_only_banned_words():
    controls = reversal_cases()
    families = {item["problem_family"] for item in controls}
    assert len(controls) == 12
    assert {
        "teacher_posture",
        "judge_posture",
        "advice_first",
        "source_restatement",
        "fabricated_firsthand",
        "answered_question",
        "narrator_inflation",
        "fake_colloquial",
        "complete_editor_logic",
        "uniform_polish",
    } <= families
    assert all(item["expected_decision"] == "reject" for item in controls)
    assert all(item["synthetic_control"] for item in controls)
    assert all(item["publish_allowed"] is False for item in controls)


def test_manifest_has_hashes_only_not_private_context():
    packet_a, packet_b, manifest = build()
    text = json.dumps(manifest, ensure_ascii=False)
    private_values = {
        value
        for packet in (packet_a, packet_b)
        for item in packet["items"]
        for value in (
            item["context"]["body"],
            item["candidate"],
            *item["context"]["visible_comments"],
        )
        if isinstance(value, str) and value
    }
    assert not any(value in text for value in private_values)
    assert manifest["stores_note_body_comments_images_or_draft"] is False
    assert manifest["generation_executed"] is False
    assert manifest["network_executed"] is False
    assert manifest["publication_executed"] is False
