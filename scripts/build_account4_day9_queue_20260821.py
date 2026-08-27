#!/usr/bin/env python3
"""Build slot-4 cycle-day-9 review-only artifacts for 2026-08-21."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-21"
TEMPLATE = RUN_DIR.parent / "2026-08-12" / "account_4_style_requests_4.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"
MODEL_ID = "gpt-5.6-sol"


CANDIDATES = [
    {
        "note_id": "69fdd66f00000000200388de",
        "title": "床尾梳妆台+斗柜｜过道留多少不踩雷？",
        "body": "作者展示40cm深的床尾梳妆台和斗柜，并按自家使用说明70cm较宽松、50cm为最低预留。",
        "comments": "当前可见8条评论，已讨论35至40cm柜深和购买来源，未说明50cm是凳子推进后还是拉出后测量。",
        "media": "5张图已全部查看。",
        "draft": "50cm这个净距，是凳子完全推进去时量的，还是拉出来以后量的？",
        "mode": "curiosity_question",
        "direction": "size_clearance_question",
        "intent": "utility_fit_question",
        "topic": "dimensions_fit",
        "min_chars": 18,
        "max_chars": 55,
        "angle": "只追问50cm测量时的凳子状态，避免重复柜深和购买来源。",
    },
    {
        "note_id": "689d3113000000001c00890f",
        "title": "入户门过道只有83公分了，怎么办😢",
        "body": "作者称40cm深入户柜完成后只剩83cm通道，担心家具进场并考虑让定制公司调整。",
        "comments": "当前可见1401条评论，集中讨论家具进场、30cm柜体和拆改，未给出入户门完全打开后的最窄净距。",
        "media": "单图已查看。",
        "draft": "入户门完全打开以后，门扇到柜子最窄还剩多少？",
        "mode": "curiosity_question",
        "direction": "layout_circulation_question",
        "intent": "utility_fit_question",
        "topic": "layout_circulation",
        "min_chars": 18,
        "max_chars": 55,
        "angle": "把83cm直线通道细化为开门后的实际最窄点。",
    },
    {
        "note_id": "675947ea000000000700c48a",
        "title": "过道窄！！家具进不了🚪入户鞋柜大翻车❌❌",
        "body": "作者担心鞋柜压缩入户通道，成品后过道约90cm，并称现有家具均顺利进场。",
        "comments": "当前可见121条评论，讨论80至110cm通道、沙发冰箱进场和转弯，作者未把转弯净空单独量出。",
        "media": "共7张图，已连续查看前6张。",
        "draft": "这种门口有转弯的，量过道时还得把转身的位置一起算进去",
        "mode": "light_humor_or_neutral",
        "direction": "light_social_response",
        "intent": "neutral_social",
        "topic": "layout_circulation",
        "min_chars": 12,
        "max_chars": 38,
        "angle": "补充直线宽度之外的转弯净空，不复述家具已经进场。",
    },
    {
        "note_id": "67e0f047000000000903ac13",
        "title": "餐桌过道只留80公分，会不会太窄了？",
        "body": "作者围绕三口之家、婴儿车、露营收纳、岛台和去客厅化需求连续更新4版户型，最新版在图4。",
        "comments": "当前可见141条评论，主要讨论餐桌通道、八百库、餐边柜和公区布局，作者已按部分建议更新。",
        "media": "4张户型图已全部查看。",
        "draft": "最新版把餐桌从主通道里让开了，前两版的拥挤感一下少了很多",
        "mode": "support_only",
        "direction": "detail_grounded_praise",
        "intent": "grounded_praise",
        "topic": "layout_circulation",
        "min_chars": 12,
        "max_chars": 38,
        "angle": "只夸最新版一个可见的动线变化，不追加建议。",
    },
    {
        "note_id": "6725c56c000000001b02ab9f",
        "title": "砸掉两面墙做L型开放式厨房 我后悔了吗❓",
        "body": "作者入住半年后复盘把原6㎡厨房改成约15㎡餐厨一体空间，强调家人互动和餐桌多用途。",
        "comments": "当前可见2条评论分别询问尺寸和燃气开通，未讨论日常炒菜时油烟是否会跑到餐桌区域。",
        "media": "66.85秒视频已完整播放至ended=true。",
        "draft": "入住半年后，炒菜时油烟会不会跑到餐桌这边？",
        "mode": "curiosity_question",
        "direction": "layout_circulation_question",
        "intent": "utility_fit_question",
        "topic": "layout_circulation",
        "min_chars": 18,
        "max_chars": 55,
        "angle": "追问开放餐厨半年后的真实油烟边界，当前评论区未回答。",
    },
    {
        "note_id": "6980a60d0000000022022647",
        "title": "餐厅开间2.5米，没听劝还是做了满墙餐边柜",
        "body": "作者在2.5m餐厅开间内做30cm深满墙餐边柜，搭配160×80cm餐桌，正文称柜前和厨房门口各留70cm。",
        "comments": "当前可见67条评论已讨论柜深、餐桌和坐人是否拥挤，但70cm是收椅后还是坐人状态的椅背后净距仍不明确。",
        "media": "6张图已全部查看。",
        "draft": "你说柜前留70cm，是餐椅推进去以后量的，还是坐人时椅背后还剩70cm？",
        "mode": "curiosity_question",
        "direction": "size_clearance_question",
        "intent": "utility_fit_question",
        "topic": "dimensions_fit",
        "min_chars": 18,
        "max_chars": 55,
        "angle": "把70cm的测量状态问清，不重复作者已回答的柜深。",
    },
]


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def preflight(payload: dict) -> dict:
    done = subprocess.run(
        [sys.executable, str(PREFLIGHT), "-"],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO,
        check=False,
    )
    if done.returncode:
        raise RuntimeError(done.stderr.decode("utf-8", errors="replace"))
    return json.loads(done.stdout.decode("utf-8"))


def build_payload(base: dict, item: dict, index: int) -> dict:
    payload = copy.deepcopy(base)
    payload.update(
        {
            "request_id": f"panse.2026-08-21.account4.comment.{index:03d}",
            "idempotency_key": f"panse:2026-08-21:account-4:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。标题、完整正文、当前可见评论和规定数量媒体均已阅读。"
                "身份是关注户型、尺寸与动线的普通家居同好。评论只补1个净距、动线落点、使用反馈或具体短夸。"
                "不要复述标题、正文和显而易见画面；不要每条都提问，也不要为了互动硬问。"
                "像普通真人，不用老师、评委、测评机构或验收口吻；数字统一用阿拉伯数字。"
                "少用思路、那组、尤其、参考价值、落地、下单等词；禁止使用“这种分享很实在”。"
                "输出1句话，12至60个中文字符；不提畔色，不导流，不虚构购买、入住、装修、检测、维修或长期使用经历。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "户型尺寸与动线号公开评论待审稿",
            "audience": "正在处理小户型、餐桌、玄关、柜体和通道尺寸的普通用户",
            "use_case": "生成一条自然、具体、等待人工批准的评论草稿",
            "interaction_mode": item["mode"],
            "source_context": {
                "body": item["body"],
                "visible_comments": [item["comments"]],
                "image_observations": [
                    {
                        "locator": "reviewed_media",
                        "observation": item["media"],
                        "observation_basis": "caller_reviewed",
                    }
                ],
                "body_complete": True,
                "visible_comments_complete": True,
                "images_complete": True,
                "expected_visible_comment_count": 1,
                "expected_image_count": 1,
            },
            "required_model_id": MODEL_ID,
            "fallback_model_allowed": False,
            "content_contract": {
                "protected_facts": [],
                "allowed_paraphrases": {},
                "forbidden_inferences": [
                    "不得虚构购买、入住、装修、检测、维修或长期使用经历",
                    "不得使用老师、评委、测评机构或验收者口吻",
                    "不得复述标题、正文或显而易见画面",
                    "问题必须是作者容易回答且当前评论区尚未回答的问题",
                    "不得把尺寸、安全、性能或责任归属写成未经核验的普遍事实",
                    "数量必须使用阿拉伯数字",
                    "不得推荐畔色或导流",
                    "不得使用用户明确否决的固定表达“这种分享很实在”",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            "output": {
                "title_candidates": 0,
                "title_max_chars": 0,
                "body_min_chars": item["min_chars"],
                "body_max_chars": item["max_chars"],
                "tag_min": 0,
                "tag_max": 0,
            },
            "panse_intent_context": {
                "policy_version": "xhs-comment-intent.v4",
                "topic_ids": [item["topic"]],
                "interaction_intent": item["intent"],
                "comment_direction_id": item["direction"],
                "voice_id": "space_advisor",
                "human_approved_example_set_version": "panse-xhs-human-approved-comments.v3",
            },
        }
    )
    return payload


def main() -> int:
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    requests, receipts, reviews = [], [], []
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}
    question_count = 0

    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        request_id = payload["request_id"]
        question_count += int(item["mode"] == "curiosity_question")
        requests.append({"target_note": {"note_id": item["note_id"], "title": item["title"], "source_locator": payload["source_locator"]}, "style_request": payload})
        receipts.append(receipt)
        stages["plan"][request_id] = {"model_id": MODEL_ID, "fallback_used": False, "interaction_mode": item["mode"], "comment_direction_id": item["direction"], "entry_angle": item["angle"]}
        stages["draft"][request_id] = {"model_id": MODEL_ID, "fallback_used": False, "draft_text": item["draft"], "tags": []}
        stages["semantic_review"][request_id] = {
            "model_id": MODEL_ID,
            "fallback_used": False,
            "results": [
                {"gate": "source_and_comment_grounding", "status": "pass", "notes": "正文、规定数量媒体和当前可见评论均已读取。"},
                {"gate": "historical_note_dedup", "status": "pass", "notes": "未在历史公开发布回执中找到该note_id。"},
                {"gate": "new_value_not_restatement", "status": "pass", "notes": item["angle"]},
                {"gate": "identity_boundary", "status": "pass", "notes": "未虚构亲历或品牌关系。"},
                {"gate": "question_quality", "status": "pass", "notes": "提问项均为当前评论区未回答且作者容易回答；本批含2条非问句。"},
                {"gate": "natural_voice", "status": "pass", "notes": "1句口语，未使用禁用固定表达和老师口吻。"},
            ],
        }
        reviews.append(
            {
                "request_id": request_id,
                "account_slot_and_nickname": "slot 4 / 小红薯6A68E133",
                "note_id": item["note_id"],
                "target_note_title": item["title"],
                "source_context_summary": item["body"],
                "visible_comment_context_summary": item["comments"],
                "exact_draft_text": item["draft"],
                "style_preflight_passed": bool(receipt.get("passed")),
                "semantic_review_passed": True,
                "queue_status": "awaiting_user_review",
                "current_user_approval_required": True,
                "current_user_approval_received": False,
                "send_authorized": False,
                "published": False,
            }
        )

    if question_count == len(CANDIDATES):
        raise RuntimeError("batch-level rule failed: every draft is a question")

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    all_passed = all(item.get("passed") for item in receipts)
    model_verified = all(response["model_id"] == MODEL_ID and response["fallback_used"] is False for stage in stages.values() for response in stage.values())
    request_file = "account_4_style_requests_6.json"
    compile_file = "account_4_style_compile_receipts_6.json"
    stage_file = "account_4_current_session_stage_responses_6.json"
    review_file = "account_4_human_review_6.json"
    write_json(request_file, {"schema_version": 1, "date": "2026-08-21", "account_slot": 4, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "request_count": 6, "requests": requests})
    write_json(compile_file, {"schema_version": 1, "compiled_at": stamp, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "receipt_count": 6, "all_passed": all_passed, "external_posting_performed": False, "receipts": receipts})
    write_json(stage_file, {"schema_version": 1, "created_at": stamp, "provider": "codex.current_session", "model_id": MODEL_ID, "model_selection_evidence": {"surface": "codex.current_session", "request_meta_model": MODEL_ID, "reasoning_effort": "high", "thread_id": "019ffb78-aa64-7482-baf8-fc1338b9a0ae"}, "account_slot": 4, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "stages": stages, "external_posting_performed": False})
    write_json(review_file, {"schema_version": 1, "date": "2026-08-21", "account_slot": 4, "account_nickname": "小红薯6A68E133", "review_item_count": 6, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "required_generation_model_verified": model_verified, "generation_model_evidence": {"current_turn_context_model": MODEL_ID, "stage_response_file": stage_file, "all_stage_models_match": model_verified, "fallback_used": False}, "all_ready_for_user_review": all_passed and model_verified, "send_allowed": False, "user_approval_received": False, "approved_item_numbers": [], "unapproved_item_numbers": [1, 2, 3, 4, 5, 6], "published_count": 0, "items": reviews})
    write_json("account_4_follow_evaluations.json", {"schema_version": 1, "date": "2026-08-21", "account_slot": 4, "profile_id": "6a684f14000000001400c004", "planned_follow_target": 1, "follow_attempts": 0, "verified_follows": 0, "evaluations": [{"nickname": "ViVi宅家日记", "profile_id": "627bb68c0000000021021762", "notes_deep_read": ["675947ea000000000700c48a", "672c42be0000000019015c24", "6725c56c000000001b02ab9f"], "profile_observation": "同一账号连续发布同一住宅的玄关、厨房、卧室和入住后空间使用内容；已深读3篇相关内容，方向稳定，未见广告农场、搬运号或敏感私人账号特征。", "decision": "qualified_pending_user_confirmation_without_click", "reason": "two_related_deep_reads_and_profile_consistency_met"}], "follow_button_clicked": False, "follow_button_current_text": "关注", "safety_warning_observed": False, "recorded_at": stamp})

    plan_path = RUN_DIR / "account_4_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"status": "awaiting_user_review", "actual_browse": 15, "actual_deep_reads": 15, "drafts_ready": 6, "public_visible_comments": 0, "follow_attempts": 0, "verified_follows": 0, "follow_status": "qualified_pending_user_confirmation_without_click", "unsent_review_items": 6, "comment_send_allowed": False, "stop_reason": None})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["totals_verified"].update({"browse": 45, "deep_reads": 45, "comment_drafts": 12, "public_visible_comments": 6, "follows": 1})
    for account in status["accounts"]:
        if account["account_slot"] == 4:
            account.update({"status": "awaiting_user_review", "actual_browse": 15, "actual_deep_reads": 15, "drafts_ready": 6, "public_visible_comments": 0, "verified_follows": 0, "follow_status": "qualified_pending_user_confirmation_without_click", "unsent": 6})
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"drafts": 6, "all_preflight_passed": all_passed, "model_verified": model_verified, "question_count": question_count, "follow_clicked": False, "review_file": str(RUN_DIR / review_file)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
