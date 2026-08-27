#!/usr/bin/env python3
"""Record verified slot-1 comment publication receipts for 2026-08-12."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-12"


def load(name: str) -> dict:
    return json.loads((RUN_DIR / name).read_text(encoding="utf-8"))


def save(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    stamp = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    receipts = [
        {
            "note_id": "69a9428700000000280225a7",
            "title": "求助椅子裂开了怎么修补",
            "exact_text": "问题可能不只在裂缝，榫口松动也要一起看，不然补好裂缝凳脚还是会晃。",
            "count_before": 100,
            "count_after": 101,
            "count_change": 1,
            "exact_text_publicly_visible": True,
            "account_nickname_publicly_visible": True,
            "editor_cleared": True,
            "account_profile_id": "6465fa8000000000290160bd",
            "submit_method": "xhs-comment-submit.enter-v1",
            "verified": True,
        },
        {
            "note_id": "69d205f5000000002102d9fb",
            "title": "建模代做✨布艺沙发全流程✨犀牛建模",
            "exact_text": "犀牛先把尺寸和基础面定好，软包褶皱再放到 Blender 里收，会自然很多。",
            "count_before": 5,
            "count_after": 6,
            "count_change": 1,
            "exact_text_publicly_visible": True,
            "account_nickname_publicly_visible": True,
            "editor_cleared": True,
            "account_profile_id": "6465fa8000000000290160bd",
            "submit_method": "xhs-comment-submit.enter-v1",
            "verified": True,
        },
        {
            "note_id": "69a4aaec000000001d012079",
            "title": "换桌子？不存在的！木桌去白印亲测有用！",
            "exact_text": "酒精这一步得看涂层，油蜡面和漆面的反应可能不一样，先从小范围试会更稳。",
            "count_before": 100,
            "count_after": 101,
            "count_change": 1,
            "exact_text_publicly_visible": True,
            "account_nickname_publicly_visible": True,
            "editor_cleared": True,
            "account_profile_id": "6465fa8000000000290160bd",
            "submit_method": "xhs-comment-submit.enter-v1",
            "verified": True,
        },
        {
            "note_id": "69666408000000002203ac48",
            "title": "烫黑碳化的木桌，自己在家也能修！",
            "exact_text": "木纹补得挺细，最后那层502如果以后发白会比较难返修，换成和原桌面同体系的透明面漆会稳一点。",
            "count_before": 233,
            "count_after": 234,
            "count_change": 1,
            "exact_text_publicly_visible": True,
            "account_nickname_publicly_visible": True,
            "editor_cleared": True,
            "account_profile_id": "6465fa8000000000290160bd",
            "submit_method": "xhs-comment-submit.enter-v1",
            "verified": True,
        },
    ]
    save(
        "account_1_comment_publish_receipts_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "account_slot": 1,
            "account_nickname": "畔色木作",
            "published_at": stamp,
            "user_approval": "发全部",
            "published_count": 4,
            "public_visible_count": 4,
            "all_verified": True,
            "safety_warning_observed": False,
            "items": receipts,
        },
    )

    review = load("account_1_human_review_4.json")
    review.update(
        {
            "send_allowed": True,
            "user_approval_received": True,
            "user_approval_text": "发全部",
            "published_count": 4,
            "public_visible_count": 4,
            "completed_at": stamp,
        }
    )
    by_note = {item["note_id"]: item for item in receipts}
    for item in review["items"]:
        receipt = by_note[item["note_id"]]
        item.update(
            {
                "queue_status": "published_public_visible",
                "published": True,
                "public_visible": True,
                "count_before": receipt["count_before"],
                "count_after": receipt["count_after"],
                "editor_cleared": True,
                "published_at": stamp,
            }
        )
    save("account_1_human_review_4.json", review)

    plan = load("account_1_daily_plan.json")
    plan.update(
        {
            "status": "completed",
            "public_visible_comments": 4,
            "unsent_review_items": 0,
            "user_approval_received": True,
            "completed_at": stamp,
        }
    )
    save("account_1_daily_plan.json", plan)

    status = load("five_account_daily_status.json")
    for account in status["accounts"]:
        if account["account_slot"] == 1:
            account.update(
                {
                    "status": "completed",
                    "public_visible_comments": 4,
                    "unsent": 0,
                    "user_approval_received": True,
                }
            )
    status["overall_status"] = "in_progress"
    save("five_account_daily_status.json", status)
    print(
        json.dumps(
            {
                "published": 4,
                "public_visible": 4,
                "slot1_status": "completed",
                "overall_status": "in_progress",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
