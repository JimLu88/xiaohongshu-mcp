from __future__ import annotations

import json

from build_xhs_full_context_owner_review_v3 import _render_html, build_owner


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
    assert manifest["r3_status"] == "awaiting_owner_review"


def test_owner_html_is_local_self_contained_and_exports_one_completed_json(tmp_path):
    packet, _, _ = build_owner()
    rendered = _render_html(packet, tmp_path / "owner.completed.json").decode("utf-8")
    assert "https://" not in rendered
    assert "http://" not in rendered
    assert "Owner 审核" in rendered
    assert "校验并导出" in rendered
    assert "owner.completed.json" in rendered
    assert "reviewer A" not in rendered
    assert "reviewer B" not in rendered


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
