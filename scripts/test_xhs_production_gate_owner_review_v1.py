from __future__ import annotations

import json

from build_xhs_production_gate_owner_review_v1 import (
    DIMENSIONS,
    render_html,
    select_additional,
)


def _record(index: int, role: str) -> dict:
    return {
        "sample_id": f"sample-{index}",
        "context_sha256": f"{index:064x}",
        "candidate": f"候选评论 {index}",
        "interaction_intent": "grounded_praise",
        "comment_direction_id": "detail_grounded_praise",
        "topic_ids": ["material_craft"],
        "interaction_mode": None,
        "role": role,
    }


def test_selection_excludes_existing_and_covers_official_role():
    records = []
    roles = [
        "official_explanation",
        "stylist",
        "evaluation_judgment",
        "space_advisor",
        "global_design_observer",
    ]
    for index in range(25):
        records.append(_record(index, roles[index % len(roles)]))
    policy = {
        "directions": {
            "detail_grounded_praise": {"interaction_mode": "support_only"}
        }
    }
    selected = select_additional(
        records,
        existing_hashes={records[0]["context_sha256"]},
        policy=policy,
    )
    assert len(selected) == 10
    assert len({item["context_sha256"] for item in selected}) == 10
    assert records[0]["context_sha256"] not in {
        item["context_sha256"] for item in selected
    }
    assert sum(item["role"] == "official_explanation" for item in selected) == 4
    assert all(item["interaction_mode"] == "support_only" for item in selected)


def test_private_html_is_chinese_self_contained_and_owner_gated(tmp_path):
    packet = {
        "items": [
            {
                "owner_item_id": "生产补充-31",
                "declared_role": "official_explanation",
                "declared_interaction_mode": "support_only",
                "comment_direction_id": "detail_grounded_praise",
                "context": {
                    "title": "测试标题",
                    "body": "测试正文",
                    "visible_comments": ["可见评论"],
                },
                "candidate": "这条补充一下。",
                "model_recommendation": {
                    "decision": "accept",
                    "reason_codes": [],
                    "review_dimensions": {name: "pass" for name in DIMENSIONS},
                },
                "owner_decision": None,
                "owner_review_dimensions": {name: None for name in DIMENSIONS},
                "owner_note": None,
                "reviewed_at": None,
            }
        ],
        "principal_sincere_signed_evidence": {},
        "production_switch": {},
    }
    rendered = render_html(packet, tmp_path / "completed.json")
    assert "小红书 40 条生产门补充审核" in rendered
    assert "全部采用模型建议" in rendered
    assert "负责人真实参与依据" in rendered
    assert "批准切换生产合同" in rendered
    assert "publish" not in rendered.lower()
    assert "https://" not in rendered
    assert "http://" not in rendered


def test_manifest_is_hash_only_after_real_build():
    manifest_path = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "research"
        / "panse_multi_direction"
        / "xhs_production_gate_owner_review_manifest_v1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["additional_context_count"] == 10
    assert manifest["combined_context_count_after_owner_approval"] == 40
    assert manifest["stores_source_text_or_candidate"] is False
    assert manifest["model_recommendations_are_owner_decisions"] is False
    assert manifest["production_contract_updated"] is False
    assert manifest["publication_executed"] is False
    assert not {"body", "candidate", "context", "visible_comments"}.intersection(
        manifest
    )
