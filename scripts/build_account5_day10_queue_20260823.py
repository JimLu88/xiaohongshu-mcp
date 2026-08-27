#!/usr/bin/env python3
"""Archived unsafe builder for the 2026-08-23 slot-5 queue.

This historical script hard-coded draft and stage-result content. It is kept as
evidence only and must not be used to create or refresh a review queue.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-23"
TEMPLATE = RUN_DIR.parent / "2026-08-12" / "account_5_style_requests_4.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"
MODEL_ID = "gpt-5.6-sol"


CANDIDATES = [
    {
        "note_id": "69a3c99c00000000150219e9",
        "title": "修复，是另一种创造",
        "body": "旧椅破损位置用藤条重新编织，修复不隐藏缺口，而是把新材料变成新的视觉部分。",
        "comments": "当前可见评论为空。",
        "media": "5张图片全部查看，含破损、编织过程与修复结果。",
        "draft": "藤条没在遮破损，反而把缺口变成了整把椅子的重点，挺妙的。",
        "topic": "maintenance_lifetime",
        "direction": "detail_grounded_praise",
        "angle": "落在藤条把破损转成视觉重点，不空泛夸修复。",
    },
    {
        "note_id": "6a41ecf50000000008003b6a",
        "title": "让经典再续，品牌家具修复服务",
        "body": "品牌展示纸绳座面拆除、木面清洁处理和重新编织等家具修复过程。",
        "comments": "当前可见8条评论，主要围绕修复渠道和家具品牌；未见与草稿相同表述。",
        "media": "10张中已查看6张，含旧纸绳、拆除、木面处理和重编工序。",
        "draft": "纸绳座面能在国内找到熟悉原结构的师傅重编，对老椅子太重要了。",
        "topic": "maintenance_lifetime",
        "direction": "detail_grounded_praise",
        "angle": "强调原结构修复渠道的意义，不把工艺结论扩大成普遍事实。",
    },
    {
        "note_id": "67954720000000002902e1b0",
        "title": "Furniture Restoration：修复家具",
        "body": "家具从拆解软包和表层开始，逐步露出内部结构，再完成清洁、修补和复原。",
        "comments": "当前可见评论已读，讨论集中在家具修复过程和完成效果；未见相同表述。",
        "media": "7张中已查看6张，覆盖拆解、内部结构和复原过程。",
        "draft": "一件家具拆开再复原，能看见藏在软包和表面下面的结构，这个过程确实很迷人。",
        "topic": "material_craft",
        "direction": "detail_grounded_praise",
        "angle": "落在拆解后可见的内部结构，不只说成品好看。",
    },
    {
        "note_id": "6a8952020000000033019e72",
        "title": "法国小家不大，但终于越住越顺眼了",
        "body": "法国小公寓用圆桌连接开放餐厨，灰蓝餐椅、木柜、黑色吊灯和地毯划出餐区。",
        "comments": "当前可见1条评论，询问能否看看家里其他区域；尚未提到灯与桌腿的颜色呼应。",
        "media": "1张图片已查看。",
        "draft": "黑色吊灯和桌腿一上一下呼应，灰蓝餐椅就不会显得突然了。",
        "topic": "global_localization",
        "direction": "detail_grounded_praise",
        "angle": "指出上下两处黑色形成呼应，不复述作者的小户型结论。",
    },
    {
        "note_id": "6a7b42d0000000002500d95d",
        "title": "Study 001｜研究100个世界各地的小户型",
        "body": "纽约Studio用整排浅柜、椭圆家具和多功能家具压缩体量；评论区对21㎡标注有质疑。",
        "comments": "当前可见58条评论，讨论面积、开放厨房和Studio生活；未见对整排浅柜组合方式的相同表述。",
        "media": "10张中已查看前6张，含平面图、全景、浅柜、厨房和窗边工作区。",
        "draft": "一排浅柜把电视、收纳和台面合在一起，比零散摆几个小柜子利落多了。",
        "topic": "dimensions_fit",
        "direction": "detail_grounded_praise",
        "angle": "只评价浅柜的复合用途，避开评论区有争议的面积数字。",
    },
    {
        "note_id": "6a8413e1000000003302ccf0",
        "title": "Study 002｜研究100个世界各地的小户型",
        "body": "波兰38㎡Studio用半开放书架代墙、统一胶合板串联区域，并通过镜面和玻璃砖借光。",
        "comments": "当前可见46条评论，讨论户型、采光和继续更新；未见对书架隔断轻巧感的相同表述。",
        "media": "13张中已查看6张，含平面图、厨房客厅、书架隔断与窗边工作区。",
        "draft": "书架既挡住床，又让窗边的光穿过去，这种隔断比实墙轻巧多了。",
        "topic": "dimensions_fit",
        "direction": "detail_grounded_praise",
        "angle": "把书架的遮挡与透光作用放在同一句，不空泛夸小户型。",
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
            "request_id": f"panse.2026-08-23.account5.comment.{index:03d}",
            "idempotency_key": f"panse:2026-08-23:account-5:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。标题、完整正文、当前可见评论和规定数量媒体均已阅读。"
                "身份是关注全球家具工艺和居住偏好的普通同好，不装专家。"
                "只写1个具体观察或直接判断；不要复述标题、正文和图里显而易见的内容，不为了互动硬提问。"
                "像普通真人，不用老师、评委、测评机构或验收口吻；数字统一用阿拉伯数字。"
                "少用思路、那组、尤其、参考价值、落地、下单等词；禁止使用‘这种分享很实在’。"
                "输出1句话，说完就停；不提畔色，不导流，不虚构购买、入住、装修、检测、维修或长期使用经历。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "全球家具工艺与居住偏好账号公开评论待审稿",
            "audience": "关注海外家具工艺、修复与小户型居住案例的普通用户",
            "use_case": "生成一条自然、具体、等待人工批准的评论草稿",
            "interaction_mode": "support_only",
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
                    "不得把材料、结构、安全、性能或责任归属写成未经核验的普遍事实",
                    "不得推荐畔色或导流",
                    "不得使用固定表达‘这种分享很实在’",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            "output": {
                "title_candidates": 0,
                "title_max_chars": 0,
                "body_min_chars": 8,
                "body_max_chars": 70,
                "tag_min": 0,
                "tag_max": 0,
            },
            "panse_intent_context": {
                "policy_version": "xhs-comment-intent.v4",
                "topic_ids": [item["topic"]],
                "interaction_intent": "grounded_praise",
                "comment_direction_id": item["direction"],
                "voice_id": "global_design_observer",
                "human_approved_example_set_version": "panse-xhs-human-approved-comments.v3",
            },
        }
    )
    return payload


def main() -> int:
    raise RuntimeError(
        "archived hard-coded queue builder; use scripts/run_xhs_style_lab.py "
        "with a governed request and real plan/draft/semantic_review provider runs"
    )
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    requests, receipts, reviews = [], [], []
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}

    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        request_id = payload["request_id"]
        requests.append(
            {
                "target_note": {
                    "note_id": item["note_id"],
                    "title": item["title"],
                    "source_locator": payload["source_locator"],
                },
                "style_request": payload,
            }
        )
        receipts.append(receipt)
        stages["plan"][request_id] = {
            "model_id": MODEL_ID,
            "fallback_used": False,
            "interaction_mode": "support_only",
            "comment_direction_id": item["direction"],
            "entry_angle": item["angle"],
        }
        stages["draft"][request_id] = {
            "model_id": MODEL_ID,
            "fallback_used": False,
            "draft_text": item["draft"],
            "tags": [],
        }
        stages["semantic_review"][request_id] = {
            "model_id": MODEL_ID,
            "fallback_used": False,
            "results": [
                {"gate": "source_and_comment_grounding", "status": "pass", "notes": "正文、规定数量媒体和当前可见评论均已读取。"},
                {"gate": "historical_note_dedup", "status": "pass", "notes": "未在历史发布回执中找到该note_id。"},
                {"gate": "new_value_not_restatement", "status": "pass", "notes": item["angle"]},
                {"gate": "identity_boundary", "status": "pass", "notes": "未虚构亲历、购买或品牌关系。"},
                {"gate": "question_quality", "status": "not_applicable", "notes": "本批不为了互动硬提问。"},
                {"gate": "natural_voice", "status": "pass", "notes": "单句口语，未使用禁用固定表达和老师口吻。"},
            ],
        }
        reviews.append(
            {
                "request_id": request_id,
                "account_slot_and_nickname": "slot 5 / 是阿宝啊",
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

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    all_passed = all(item.get("passed") for item in receipts)
    model_verified = all(
        response["model_id"] == MODEL_ID and response["fallback_used"] is False
        for stage in stages.values()
        for response in stage.values()
    )
    write_json(
        "account_5_style_requests_6.json",
        {"schema_version": 1, "date": "2026-08-23", "account_slot": 5, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "request_count": 6, "requests": requests},
    )
    write_json(
        "account_5_style_compile_receipts_6.json",
        {"schema_version": 1, "compiled_at": stamp, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "receipt_count": 6, "all_passed": all_passed, "external_posting_performed": False, "receipts": receipts},
    )
    write_json(
        "account_5_current_session_stage_responses_6.json",
        {"schema_version": 1, "created_at": stamp, "provider": "codex.current_session", "model_id": MODEL_ID, "account_slot": 5, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "stages": stages, "external_posting_performed": False},
    )
    write_json(
        "account_5_human_review_6.json",
        {"schema_version": 1, "date": "2026-08-23", "account_slot": 5, "account_nickname": "是阿宝啊", "review_item_count": 6, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "required_generation_model_verified": model_verified, "all_ready_for_user_review": all_passed and model_verified, "send_allowed": False, "user_approval_received": False, "approved_item_numbers": [], "unapproved_item_numbers": [1, 2, 3, 4, 5, 6], "published_count": 0, "approval_rule": "Only explicit current-batch approval of the exact displayed drafts permits sending.", "items": reviews},
    )
    write_json(
        "account_5_follow_evaluations.json",
        {"schema_version": 1, "date": "2026-08-23", "account_slot": 5, "profile_id": "6347830c0000000012027db3", "planned_follow_target": 1, "follow_attempts": 0, "verified_follows": 0, "evaluations": [{"nickname": "Muffins", "profile_id": "5be2e74ec9f9e90001b392b7", "notes_deep_read": ["6a7b42d0000000002500d95d", "6a8413e1000000003302ccf0"], "profile_observation": "主页简介明确持续研究100个世界各地的小户型；现有3篇笔记均围绕20至38㎡Studio和小户型居住，方向稳定，未见广告农场、搬运号或敏感私人账号特征。", "decision": "qualified_pending_user_confirmation_without_click", "reason": "two_related_deep_reads_and_profile_consistency_met"}], "follow_button_clicked": False, "follow_button_current_text": "关注", "safety_warning_observed": False, "recorded_at": stamp},
    )

    plan_path = RUN_DIR / "account_5_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"status": "awaiting_user_review", "actual_browse": 12, "actual_deep_reads": 12, "drafts_ready": 6, "public_visible_comments": 0, "follow_attempts": 0, "verified_follows": 0, "follow_status": "qualified_pending_user_confirmation_without_click", "unsent_review_items": 6, "comment_send_allowed": False, "stop_reason": None})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["totals_verified"].update({"browse": 12, "deep_reads": 12, "comment_drafts": 6, "public_visible_comments": 0, "follows": 0})
    for account in status["accounts"]:
        if account["account_slot"] == 5:
            account.update({"status": "awaiting_user_review", "actual_browse": 12, "actual_deep_reads": 12, "drafts_ready": 6, "public_visible_comments": 0, "verified_follows": 0, "follow_status": "qualified_pending_user_confirmation_without_click", "unsent": 6, "stop_reason": None})
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"drafts": 6, "all_preflight_passed": all_passed, "model_verified": model_verified, "follow_clicked": False, "review_file": str(RUN_DIR / "account_5_human_review_6.json")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
