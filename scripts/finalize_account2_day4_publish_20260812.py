#!/usr/bin/env python3
"""Record verified slot-2 publication receipts for 2026-08-12."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-12"


def load(name: str) -> dict:
    return json.loads((RUN_DIR / name).read_text(encoding="utf-8"))


def save(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipts = [
        {"note_id":"692d7bb1000000001e009f36","title":"装了个44平的老破小，入住一年依旧很满意！","exact_text":"小空间没有硬塞功能，住了一年还能觉得顺手，这个真的很厉害。","count_before":433,"count_after":434,"count_change":1,"exact_text_publicly_visible":True,"account_nickname_publicly_visible":True,"editor_cleared":True,"account_profile_id":"634c02a1000000001901c0e6","submit_method":"xhs-comment-submit.enter-v1","verified":True},
        {"note_id":"6a6eac4e000000003300d929","title":"小众红棕背景墙，到底是高级还是压抑？","exact_text":"红棕色真挺挑光线的，不过只刷一面就没那么压，晚上开灯应该会更有感觉。","count_before":1,"count_after":2,"count_change":1,"exact_text_publicly_visible":True,"account_nickname_publicly_visible":True,"editor_cleared":True,"account_profile_id":"634c02a1000000001901c0e6","submit_method":"xhs-comment-submit.enter-v1","verified":True},
        {"note_id":"6a13f47b000000003601ac01","title":"采光一般的客厅里，白色沙发像块天然反光板","exact_text":"沙发套按季节换颜色这个挺妙，夏天用白色清爽，冬天换深色又会暖很多。","count_before":73,"count_after":74,"count_change":1,"exact_text_publicly_visible":True,"account_nickname_publicly_visible":True,"editor_cleared":True,"account_profile_id":"634c02a1000000001901c0e6","submit_method":"xhs-comment-submit.enter-v1","verified":True},
        {"note_id":"6a75e2ee000000003302d571","title":"小户型餐厅这么装，真的是显大又实用🏠","exact_text":"平时四个人用圆桌不占地方，来人再拉开，比一直摆张大桌子轻松多了。","count_before":23,"count_after":24,"count_change":1,"exact_text_publicly_visible":True,"account_nickname_publicly_visible":True,"editor_cleared":True,"account_profile_id":"634c02a1000000001901c0e6","submit_method":"xhs-comment-submit.enter-v1","verified":True},
    ]
    save("account_2_comment_publish_receipts_4.json",{"schema_version":1,"date":"2026-08-12","account_slot":2,"account_nickname":"🦀","published_at":stamp,"user_approval":"发全部","published_count":4,"public_visible_count":4,"all_verified":True,"safety_warning_observed":False,"items":receipts})

    review = load("account_2_human_review_4.json")
    review.update({"send_allowed":True,"user_approval_received":True,"user_approval_text":"发全部","published_count":4,"public_visible_count":4,"completed_at":stamp})
    by_note = {item["note_id"]: item for item in receipts}
    for item in review["items"]:
        receipt = by_note[item["note_id"]]
        item.update({"queue_status":"published_public_visible","published":True,"public_visible":True,"count_before":receipt["count_before"],"count_after":receipt["count_after"],"editor_cleared":True,"published_at":stamp})
    save("account_2_human_review_4.json", review)

    plan = load("account_2_daily_plan.json")
    plan.update({"status":"completed_with_unverified_follow","public_visible_comments":4,"unsent_review_items":0,"verified_follows":0,"follow_attempted":1,"follow_status":"unverified_stopped_without_retry","user_approval_received":True,"completed_at":stamp})
    save("account_2_daily_plan.json", plan)

    status = load("five_account_daily_status.json")
    for account in status["accounts"]:
        if account["account_slot"] == 2:
            account.update({"status":"completed_with_unverified_follow","public_visible_comments":4,"unsent":0,"verified_follows":0,"follow_attempted":1,"follow_status":"unverified_stopped_without_retry","user_approval_received":True})
    status["overall_status"] = "in_progress"
    save("five_account_daily_status.json", status)
    print(json.dumps({"published":4,"public_visible":4,"verified_follows":0,"slot2_status":"completed_with_unverified_follow","overall_status":"in_progress"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
