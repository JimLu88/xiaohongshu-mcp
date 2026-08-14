from __future__ import annotations

import json

from build_xhs_full_context_blind_pilot_v2 import (
    TARGET_REAL_CONTEXTS,
    _verified_publication,
    audit_local_contexts,
    build,
    load_published_note_ids,
)


def test_verified_publication_requires_full_receipt_evidence():
    assert _verified_publication({}, {"published": True}) is False
    assert _verified_publication({}, {"sent": True, "verified": True}) is False
    assert _verified_publication(
        {},
        {
            "exact_text_visible": True,
            "current_account_context_visible": True,
            "editor_cleared": True,
            "comment_count_increment_verified": True,
        },
    ) is True
    assert _verified_publication(
        {"all_publicly_verified": True, "profile_id": "public-profile"},
        {
            "exact_text_visible": True,
            "editor_cleared": True,
            "comment_count_before": 3,
            "comment_count_after": 4,
        },
    ) is True
    assert _verified_publication(
        {"all_publicly_verified": True, "profile_id": "public-profile"},
        {
            "exact_text_visible": True,
            "editor_cleared": True,
            "comment_count_before": 3,
            "comment_count_after": 3,
        },
    ) is False


def test_v2_reads_nested_contexts_and_reaches_target_when_local_evidence_allows():
    packet_a, packet_b, queue, provenance, manifest = build()
    assert manifest["eligible_real_contexts"] >= len(packet_a["items"])
    assert len(packet_a["items"]) == len(packet_b["items"])
    assert len(packet_a["items"]) == manifest["selected_real_contexts"]
    assert len(packet_a["items"]) <= TARGET_REAL_CONTEXTS
    assert manifest["remaining_real_context_gap"] == max(
        0, TARGET_REAL_CONTEXTS - len(packet_a["items"])
    )
    assert queue["private_local_only"] is True
    assert provenance["private_local_only"] is True
    assert len(provenance["records"]) == len(packet_a["items"])
    assert manifest["independent_reviews_completed"] == 0


def test_selected_contexts_are_complete_and_published_notes_are_excluded():
    packet_a, _, _, provenance, _ = build()
    eligible, _, _ = audit_local_contexts()
    published = load_published_note_ids()
    selected_hashes = {item["context_sha256"] for item in packet_a["items"]}
    selected = [item for item in eligible if item["context_sha256"] in selected_hashes]
    assert len(selected) == len(packet_a["items"])
    for item in selected:
        assert item["body"]
        assert item["visible_comments"]
        assert item["image_observation"]["images_complete"] is True
        assert item["candidate"]
        assert item["missing_reasons"] == []
    for row in provenance["records"]:
        if row["review_stratum"] == "retrospective_verified_publication":
            assert row["note_id"] in published
            assert row["publication_receipt_path"]
            assert row["candidate_origin"].startswith("verified_publication_text_")
        elif row["review_stratum"] == "retrospective_candidate_publication_unverified":
            assert row["note_id"] in published
            assert row["publication_receipt_path"] is None
            assert row["publication_status_path"]
            assert row["candidate_origin"] == "historical_human_review_candidate"
        else:
            assert row["note_id"] not in published
            assert row["candidate_origin"] == "pending_human_review_packet"


def test_reviewer_packets_use_same_set_different_order_and_pending_decisions():
    packet_a, packet_b, _, _, _ = build()
    hashes_a = [item["context_sha256"] for item in packet_a["items"]]
    hashes_b = [item["context_sha256"] for item in packet_b["items"]]
    assert set(hashes_a) == set(hashes_b)
    if len(hashes_a) > 1:
        assert hashes_a != hashes_b
    assert all(item["decision"] is None for item in packet_a["items"] + packet_b["items"])
    assert packet_a["reviewer_identity_in_other_packet_hidden"] is True
    assert packet_b["model_or_provider_review_counts_as_human"] is False


def test_manifest_contains_no_private_context_or_note_ids():
    packet_a, packet_b, queue, provenance, manifest = build()
    manifest_text = json.dumps(manifest, ensure_ascii=False)
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
    private_values.update(
        row["note_id"] for row in queue["records"] if row.get("note_id")
    )
    private_values.update(queue["verified_published_note_ids_observed"])
    private_values.update(row["note_id"] for row in provenance["records"])
    assert not any(value in manifest_text for value in private_values)
    assert manifest["stores_note_id_body_comments_images_or_draft"] is False
    assert manifest["generation_executed"] is False
    assert manifest["network_executed"] is False
    assert manifest["publication_executed"] is False
    assert manifest["publish_allowed"] is False
    assert manifest["retrospective_publication_is_style_approval"] is False
    assert manifest["status_flag_only_is_verified_publication"] is False
    assert manifest["historical_candidate_is_style_approval"] is False


def test_prospective_only_mode_still_excludes_published_notes():
    packet_a, _, _, provenance, manifest = build(include_verified_published=False)
    published = load_published_note_ids()
    assert all(row["note_id"] not in published for row in provenance["records"])
    assert manifest["selected_strata"].get("retrospective_verified_publication", 0) == 0
    assert len(packet_a["items"]) < TARGET_REAL_CONTEXTS
