#!/usr/bin/env python3
"""Record verified partial slot-1 publication after the browser became unstable."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-13"


def load(name: str) -> dict:
    return json.loads((RUN_DIR / name).read_text(encoding="utf-8"))


def save(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipts = [
        ("698061d3000000001a0249c7", "我的书桌撞烂了😭 又修好了😁", "凹痕别急着直接泡水，先看木种、表面涂层和伤得多深，找师傅判断一下更稳。", 32, 33),
        ("69b2cb4e000000000600ca74", "定制柜落地，终于明白了定制柜的售后服务", "柜子装完先把抽屉、门缝、划痕和保护膜一起过一遍，能当天修的尽量当天修。", 9, 10),
        ("6933fbf8000000001e030eac", "还没住进去，我的柜子？开裂了？", "还没入住就开裂，先看门板有没有留伸缩余量，别只把缝补上，不然换个季节还可能再裂。", 235, 236),
    ]
    items = [
        {
            "note_id": note_id, "title": title, "exact_text": text,
            "count_before": before, "count_after": after, "count_change": 1,
            "exact_text_publicly_visible": True, "account_nickname_publicly_visible": True,
            "editor_cleared": True, "account_profile_id": "6465fa8000000000290160bd",
            "submit_method": "xhs-comment-submit.enter-v1", "verified": True,
        }
        for note_id, title, text, before, after in receipts
    ]
    save("account_1_comment_publish_receipts_partial_3.json", {
        "schema_version": 1, "date": "2026-08-13", "account_slot": 1,
        "account_nickname": "畔色木作", "recorded_at": stamp,
        "user_approval": "发全部", "published_count": 3, "public_visible_count": 3,
        "all_recorded_items_verified": True, "safety_warning_observed": False,
        "stop_reason": "in_app_browser_repeated_dom_timeout_on_note_4_before_input",
        "unsent_note_ids": ["68c5712d000000001b01ea42", "69ee12b80000000035026415"],
        "items": items,
    })

    review = load("account_1_human_review_5.json")
    review.update({
        "send_allowed": True, "user_approval_received": True, "user_approval_text": "发全部",
        "published_count": 3, "public_visible_count": 3,
        "queue_status": "partially_published_browser_blocked", "last_updated_at": stamp,
    })
    by_note = {item["note_id"]: item for item in items}
    for item in review["items"]:
        if item["note_id"] in by_note:
            receipt = by_note[item["note_id"]]
            item.update({
                "queue_status": "published_public_visible", "published": True,
                "public_visible": True, "count_before": receipt["count_before"],
                "count_after": receipt["count_after"], "editor_cleared": True,
                "published_at": stamp,
            })
        else:
            item.update({
                "queue_status": "approved_unsent_browser_blocked", "published": False,
                "public_visible": False, "stop_reason": "in_app_browser_repeated_dom_timeout_before_input",
            })
    save("account_1_human_review_5.json", review)

    plan = load("account_1_daily_plan.json")
    plan.update({
        "status": "blocked_partial_publish_browser_timeout", "public_visible_comments": 3,
        "unsent_review_items": 2, "user_approval_received": True,
        "stop_reason": "in_app_browser_repeated_dom_timeout_on_note_4_before_input",
        "last_updated_at": stamp,
    })
    save("account_1_daily_plan.json", plan)

    status = load("five_account_daily_status.json")
    for account in status["accounts"]:
        if account["account_slot"] == 1:
            account.update({
                "status": "blocked_partial_publish_browser_timeout",
                "public_visible_comments": 3, "unsent": 2,
                "user_approval_received": True,
                "stop_reason": "in_app_browser_repeated_dom_timeout_on_note_4_before_input",
            })
    status["totals_verified"]["public_visible_comments"] = 3
    status["overall_status"] = "in_progress_with_slot1_browser_block"
    save("five_account_daily_status.json", status)
    print(json.dumps({"verified_published": 3, "unsent": 2, "slot1_status": "blocked_partial_publish_browser_timeout"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
