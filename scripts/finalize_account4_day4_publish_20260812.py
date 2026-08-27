#!/usr/bin/env python3
"""Record verified slot-4 comment publication receipts for 2026-08-12."""

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
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipts = [
        {
            "note_id": "6a682e4c000000000903510e",
            "title": "客厅开间3.5m｜小户型这样装真的显大",
            "exact_text": "鞋柜和餐边柜中间接个斜边挺顺，进门不会突然鼓出来一块。",
            "count_before": 15,
            "count_after": 16,
            "count_change": 1,
            "exact_text_publicly_visible": True,
            "editor_cleared": True,
            "account_profile_id": "6a684f14000000001400c004",
            "submit_method": "enter_once",
            "verified": True,
        },
        {
            "note_id": "6a799509000000002701fa44",
            "title": "68㎡小户型｜客餐厅尺寸大公开，直接抄作业📏",
            "exact_text": "这个位置摆得挺舒服",
            "count_before": 6,
            "count_after": 7,
            "count_change": 1,
            "exact_text_publicly_visible": True,
            "editor_cleared": True,
            "account_profile_id": "6a684f14000000001400c004",
            "submit_method": "enter_once",
            "verified": True,
        },
        {
            "note_id": "6a755b4200000000250134c9",
            "title": "讲真，小户型一定要试试餐厨一体，附尺寸图❗️",
            "exact_text": "餐边柜前面那把椅子坐下以后，后面的柜门还能正常打开吗？",
            "count_before": 0,
            "count_after": 1,
            "count_change": 1,
            "count_verification": "empty_state_before_then_exact_count_after_refresh",
            "exact_text_publicly_visible": True,
            "editor_cleared": True,
            "account_profile_id": "6a684f14000000001400c004",
            "submit_method": "enter_once",
            "verified": True,
        },
        {
            "note_id": "696cb831000000000b00989d",
            "title": "小户型U型厨房尺寸分享～谁说80cm过道窄",
            "exact_text": "配上这个窄柜挺顺眼，厨房小也没显得挤。",
            "count_before": 39,
            "count_after": 40,
            "count_change": 1,
            "exact_text_publicly_visible": True,
            "editor_cleared": True,
            "account_profile_id": "6a684f14000000001400c004",
            "submit_method": "enter_once",
            "verified": True,
        },
    ]
    save(
        "account_4_comment_publish_receipts_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "account_slot": 4,
            "account_nickname": "小红薯6A68E133",
            "published_at": stamp,
            "user_approval": "发全部",
            "published_count": 4,
            "public_visible_count": 4,
            "all_verified": True,
            "safety_warning_observed": False,
            "items": receipts,
        },
    )

    review = load("account_4_human_review_4.json")
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
    save("account_4_human_review_4.json", review)

    plan = load("account_4_daily_plan.json")
    plan.update(
        {
            "status": "completed",
            "public_visible_comments": 4,
            "unsent_review_items": 0,
            "user_approval_received": True,
            "completed_at": stamp,
        }
    )
    save("account_4_daily_plan.json", plan)

    status = load("five_account_daily_status.json")
    for account in status["accounts"]:
        if account["account_slot"] == 4:
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
    print(json.dumps({"published": 4, "public_visible": 4, "slot4_status": "completed"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
