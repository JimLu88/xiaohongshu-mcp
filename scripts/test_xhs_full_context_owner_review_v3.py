from __future__ import annotations

import json

import pytest

from build_xhs_full_context_owner_review_v3 import (
    DIMENSION_LABELS,
    _apply_recovered_notes,
    _apply_owner_adjudication,
    _render_html,
    build_owner,
)


def test_owner_packet_is_single_reviewer_and_has_30_pending_items(tmp_path):
    packet, provenance, manifest = build_owner()
    assert packet["review_policy"]["reviewer_role"] == "owner"
    assert packet["review_policy"]["required_reviewer_count"] == 1
    assert packet["review_policy"]["independent_review_required"] is False
    assert packet["review_policy"]["does_not_modify_other_contract_approval_rules"] is True
    assert len(packet["items"]) == 30
    assert len(provenance["records"]) == 30
    assert all(item["decision"] is None for item in packet["items"])
    assert all("blind_id" not in item for item in packet["items"])
    assert all(item["owner_item_id"].startswith("审核项-") for item in packet["items"])
    assert set(DIMENSION_LABELS) == set(packet["items"][0]["review_dimensions"])
    assert manifest["r3_status"] == "awaiting_owner_review"


def test_owner_html_is_local_self_contained_and_exports_one_completed_json(tmp_path):
    packet, _, _ = build_owner()
    rendered = _render_html(packet, tmp_path / "owner.completed.json").decode("utf-8")
    assert "https://" not in rendered
    assert "http://" not in rendered
    assert "负责人审核" in rendered
    assert "项目负责人" in rendered
    assert "负责人决定" in rendered
    assert "保存当前进度" in rendered
    assert "未选完下拉框也可以保存当前进度" in rendered
    assert "xhs-full-context-owner-review-v3.in-progress.json" in rendered
    assert "校验并导出审核结果" in rendered
    assert "内容有上下文依据" in rendered
    assert "语序和逻辑自然" in rendered
    assert "published=true" not in rendered
    assert "Owner 审核" not in rendered
    assert "Owner 决定" not in rendered
    assert "reviewer A" not in rendered
    assert "reviewer B" not in rendered


def test_recovered_notes_are_candidate_bound_and_do_not_infer_decisions():
    packet, _, _ = build_owner()
    item = packet["items"][0]
    recovery = {
        "schema_version": "xhs-owner-review-note-recovery/v1",
        "recovered_at": "2026-08-14T11:50:43+08:00",
        "source": "user_supplied_screenshots",
        "note_count": 1,
        "items": [
            {
                "owner_item_id": item["owner_item_id"],
                "candidate": item["candidate"],
                "reviewer_note": "这是一条恢复备注。",
            }
        ],
    }
    assert _apply_recovered_notes(packet, recovery) == 1
    assert item["reviewer_note"] == "这是一条恢复备注。"
    assert item["decision"] is None
    assert all(value is None for value in item["review_dimensions"].values())
    recovery["items"][0]["candidate"] = "错误候选文本"
    with pytest.raises(ValueError, match="candidate mismatch"):
        _apply_recovered_notes(build_owner()[0], recovery)


def test_owner_adjudication_fills_every_dimension_and_preserves_hard_gate():
    packet, _, _ = build_owner()
    rows = []
    for item in packet["items"]:
        rows.append(
            {
                "owner_item_id": item["owner_item_id"],
                "decision": "accept",
                "question_applicable": False,
                "protected_spans_applicable": False,
                "fail_dimensions": [],
                "reason_codes": [],
            }
        )
    rows[0].update(
        decision="revise",
        fail_dimensions=["ordinary_order_and_logic"],
        reason_codes=["ordinary_word_order_awkward"],
    )
    rows[1].update(
        decision="reject",
        fail_dimensions=["source_grounded"],
        reason_codes=["unsupported_absolute_generalization"],
    )
    adjudication = {
        "schema_version": "xhs-owner-review-adjudication/v1",
        "authorized_at": "2026-08-14T12:16:14+08:00",
        "authorization_source": "current_user_instruction",
        "inference_basis": "ten_owner_notes_apply_to_all_thirty_items",
        "human_note_count": 10,
        "item_count": 30,
        "completion_mode": "owner_authorized_model_inference_from_human_notes",
        "requires_owner_readback_before_r4_approval": True,
        "items": rows,
    }
    counts = _apply_owner_adjudication(packet, adjudication)
    assert counts == {"accept": 28, "revise": 1, "reject": 1}
    assert packet["owner_review_completed"] is True
    assert packet["r3_status"] == (
        "owner_review_completed_pending_acceptance_analysis"
    )
    assert all(
        value in {"pass", "fail", "not_applicable"}
        for item in packet["items"]
        for value in item["review_dimensions"].values()
    )
    assert packet["items"][1]["review_dimensions"]["source_grounded"] == "fail"
    adjudication["items"][1]["decision"] = "accept"
    with pytest.raises(ValueError, match="accepted item has failures"):
        _apply_owner_adjudication(build_owner()[0], adjudication)


def test_owner_manifest_is_hash_only_and_has_no_private_context():
    packet, provenance, manifest = build_owner()
    manifest_text = json.dumps(manifest, ensure_ascii=False)
    private_values = {
        value
        for item in packet["items"]
        for value in (
            item["context"]["body"],
            item["candidate"],
            *item["context"]["visible_comments"],
        )
        if isinstance(value, str) and value
    }
    private_values.update(row["note_id"] for row in provenance["records"])
    assert not any(value in manifest_text for value in private_values)
    assert manifest["stores_note_id_body_comments_images_or_draft"] is False
    assert manifest["generation_executed"] is False
    assert manifest["network_executed"] is False
    assert manifest["publication_executed"] is False
    assert manifest["publish_allowed"] is False
