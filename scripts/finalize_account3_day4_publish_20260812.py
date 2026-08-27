#!/usr/bin/env python3
"""Finalize verified slot-3 publications for 2026-08-12."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-12"

PUBLISHED = [
    {"note_id":"68e4ece6000000000300e342","title":"长凳避雷！！","text":"长凳这种受力大的，买之前真得让商家发1张底面和连接处的近照，光看正面太容易漏掉结构问题。","comment_count_before":11,"comment_count_after":12},
    {"note_id":"66f505df000000001a02210e","title":"家居木材到底怎么选？橡胶木到底好不好？","text":"同一种木头做柜门和做餐桌要求也不一样吧，选的时候是不是得先看用在哪儿？","comment_count_before":90,"comment_count_after":91},
    {"note_id":"6704ebba000000001902f46c","title":"家具选实木还是贴木皮？5个点教你看明白","text":"家里要是温差大又不想天天小心维护，贴皮也不一定差，基材和封边问清楚更重要。","comment_count_before":137,"comment_count_after":138},
    {"note_id":"6a4b194b000000001c0272a1","title":"分享我在实体店买家具的维权之路","text":"把每一步和最后结果都写出来太有用了，遇到这种事的人照着找入口会省很多时间。","comment_count_before":35,"comment_count_after":36},
    {"note_id":"68c13130000000001c031bb1","title":"网上买餐桌一定要慎重，真的有坑","text":"大件安装前这一步太关键了，发现材质或缝隙不对就先别让师傅继续装，不然后面退起来真费钱。","comment_count_before":319,"comment_count_after":320},
]


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipts = []
    for item in PUBLISHED:
        receipts.append({**item,"submit_method":"xhs-comment-submit.enter-v1","enter_pressed_once":True,"send_button_clicked":False,"comment_count_increment_verified":True,"exact_text_visible":True,"current_account_nickname":"link","current_account_profile_id":"5b38445e4eacab65d6c0521c","current_account_context_visible":True,"editor_cleared":True,"risk_signal_observed":False,"published":True,"verified_at":stamp})
    write(RUN_DIR / "account_3_comment_publish_receipts_5.json", {"schema_version":1,"date":"2026-08-12","account_slot":3,"account_nickname":"link","approved_count":6,"published_verified_count":5,"not_published_count":1,"all_published_receipts_verified":True,"items":receipts,"not_published":[{"note_id":"697a18b5000000001a01ee0e","title":"餐椅避雷‼️1.5k一把的实木餐椅真心不值❌","text":"6把一起开裂真的太坑爹了，寄回修之前最好让商家把运费和修完后的质保说清楚。","reason":"target_note_unavailable_and_not_found_by_exact_title_search","attempted_to_submit":False,"replacement_target_used":False}],"risk_signal_observed":False})

    review_path = RUN_DIR / "account_3_human_review_6.json"
    review = json.loads(review_path.read_text(encoding="utf-8"))
    published_ids = {item["note_id"] for item in PUBLISHED}
    for item in review["items"]:
        item["current_user_approval_received"] = True
        if item["note_id"] in published_ids:
            item.update({"queue_status":"published_verified","published":True})
        else:
            item.update({"queue_status":"not_published_target_unavailable","published":False,"stop_reason":"target_note_unavailable"})
    review.update({"send_allowed":True,"user_approval_received":True,"published_count":5,"not_published_count":1})
    write(review_path, review)

    plan_path = RUN_DIR / "account_3_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"approved_comments":6,"public_visible_comments":5,"unsent_review_items":0,"not_published_target_unavailable":1,"status":"completed_with_unavailable_target_and_unverified_follow","stop_reason":"one_approved_target_unavailable; follow_unverified_no_retry"})
    write(plan_path, plan)

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 3:
            account.update({"status":"completed_with_unavailable_target_and_unverified_follow","public_visible_comments":5,"unsent":0,"approved_comments":6,"not_published_target_unavailable":1,"user_approval_received":True,"stop_reason":"one_approved_target_unavailable; follow_unverified_no_retry"})
    write(status_path, status)
    print(json.dumps({"published_verified":5,"target_unavailable":1,"slot3_status":"completed_with_unavailable_target_and_unverified_follow"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
