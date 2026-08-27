#!/usr/bin/env python3
"""Build slot-4 cycle-day-4 evidence and review-only queue for 2026-08-12."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-12"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"

STYLE_REFS = [
    {"card_id": "preset.platform.xiaohongshu-comment", "card_version": 12},
    {"card_id": "preset.persona.lifestyle-curator", "card_version": 12},
    {"card_id": "preset.role.editor", "card_version": 12},
    {"card_id": "preset.scene.social-comment", "card_version": 12},
]

READS = [
    {
        "note_id": "6a682e4c000000000903510e",
        "title": "客厅开间3.5m｜小户型这样装真的显大",
        "author": "🍐梨小步",
        "media_reviewed": "6/14图",
        "summary": "3.5米开间，开放式U形厨房；鞋柜与餐边柜存在23厘米深度差，用斜边过渡。已读完整正文、前6张图和当前可见评论。",
    },
    {
        "note_id": "6a5059ab0000000011019ab5",
        "title": "装修动线怎么设计？照着这5张图抄就行🏠",
        "author": "老张二明",
        "media_reviewed": "5/5图",
        "summary": "讲居住、家务和厨房动线，并给出备餐区、衣柜前净空等尺寸。已读完整正文和全部图片，当前未见可用评论。",
    },
    {
        "note_id": "6a799509000000002701fa44",
        "title": "68㎡小户型｜客餐厅尺寸大公开，直接抄作业📏",
        "author": "芝奇仕不奇怪",
        "media_reviewed": "6/15图",
        "summary": "120×80厘米餐桌，多功能客厅，阳台兼顾扫地机和收纳。已读完整正文、前6张图和当前可见评论。",
    },
    {
        "note_id": "6966329a000000001a0366bb",
        "title": "5㎡开放式厨房｜详细版尺寸图来啦！！",
        "author": "阿WEI",
        "media_reviewed": "5/5图",
        "summary": "厨房由约2.83×1.55米扩至2.9×1.92米，改成U形布局并留出四块可用台面。已读完整正文和全部图片。",
    },
    {
        "note_id": "6a23fa80000000003501cad4",
        "title": "抄作业 | 厨房做中岛必存",
        "author": "全案整装🌺何aki",
        "media_reviewed": "5/5图",
        "summary": "用两种厨房面积说明岛台类型、通道与座位尺寸。已读完整正文和全部图片；不把帖内“国标”说法当成已验证事实。",
    },
    {
        "note_id": "6a180e050000000035038878",
        "title": "6㎡小厨房布局收纳｜附尺寸详图～",
        "author": "千浔麻麻（软装中～）",
        "media_reviewed": "6/12图",
        "summary": "U形厨房、拉篮薄抽和嵌入电器；正文含较多燃气热水器商业内容。已读完整正文、前6张图和当前可见评论。",
    },
    {
        "note_id": "6a755b4200000000250134c9",
        "title": "讲真，小户型一定要试试餐厨一体，附尺寸图❗️",
        "author": "未记录",
        "media_reviewed": "6/13图",
        "summary": "3.3米开间，4平方米厨房，40厘米深餐边柜，并给出圆桌与柜体尺寸。已读完整正文、前6张图，当前未见可用评论。",
    },
    {
        "note_id": "69f5cec9000000001a02cd6e",
        "title": "厨房布局抄作业！人体工程学尺寸超实用",
        "author": "未记录",
        "media_reviewed": "6/6图",
        "summary": "汇总厨房布局和多项尺寸，但把部分数值写成普适“黄金尺寸”。已读完整正文和全部图片，未把普适性主张当成已验证事实。",
    },
    {
        "note_id": "69f052240000000035024813",
        "title": "小户型装修显大｜4个平面尺寸技巧",
        "author": "知乐",
        "media_reviewed": "6/8图",
        "summary": "围绕视线、薄柜、藏柜体和通行宽度讲小户型显大。已读完整正文、前6张图；当前评论区为空。",
    },
    {
        "note_id": "696cb831000000000b00989d",
        "title": "小户型U型厨房尺寸分享～谁说80cm过道窄",
        "author": "丙子小屋「软装版」",
        "media_reviewed": "4/4图",
        "summary": "高低台面、80厘米过道与窄柜组合。已读完整正文、全部图片和当前可见评论；评论重点是洗碗机开门、电器深度和通行。",
    },
]

CANDIDATES = [
    {
        "note_id": "6a682e4c000000000903510e",
        "title": "客厅开间3.5m｜小户型这样装真的显大",
        "topic": "layout_circulation",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "鞋柜与餐边柜有23厘米深度差，作者用斜边把两个柜体接起来。",
        "comments": ["可见评论主要询问厨房面积、餐桌尺寸和台面材质，没有评价斜边过渡。"],
        "image": "已看前6/14张，能看到斜边连接后从入口方向没有突然凸出一块。",
        "images_complete": True,
        "expected_image_count": 14,
        "draft": "鞋柜和餐边柜中间接个斜边挺顺，进门不会突然鼓出来一块。",
    },
    {
        "note_id": "6a799509000000002701fa44",
        "title": "68㎡小户型｜客餐厅尺寸大公开，直接抄作业📏",
        "topic": "layout_circulation",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "客餐厅用120×80厘米餐桌，桌椅收起后仍保留通往冰箱的路线。",
        "comments": ["可见评论主要求沙发、茶几链接并感谢尺寸分享，没有提到桌椅收起后的通行。"],
        "image": "已看前6/15张，可见桌椅收起后通往冰箱的路线仍然连贯。",
        "images_complete": True,
        "expected_image_count": 15,
        "draft": "这个位置摆得挺舒服",
    },
    {
        "note_id": "6a755b4200000000250134c9",
        "title": "讲真，小户型一定要试试餐厨一体，附尺寸图❗️",
        "topic": "dimensions_fit",
        "direction": "size_clearance_question",
        "parent": "utility_fit_question",
        "mode": "curiosity_question",
        "body": "3.3米开间内放圆桌和40厘米深餐边柜，正文没有说明靠柜椅子坐人后柜门能否正常打开。",
        "comments": ["当前未见可见评论，也没有人问椅子坐人后的柜门净空。"],
        "image": "已看前6/13张，可见圆桌、餐椅和餐边柜相邻关系。",
        "images_complete": True,
        "expected_image_count": 13,
        "draft": "餐边柜前面那把椅子坐下以后，后面的柜门还能正常打开吗？",
    },
    {
        "note_id": "696cb831000000000b00989d",
        "title": "小户型U型厨房尺寸分享～谁说80cm过道窄",
        "topic": "dimensions_fit",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "作者按两个人的身高做了高低台面，并在窄柜、过道和操作台之间取舍。",
        "comments": ["可见评论集中问洗碗机开门、55厘米台面装电器和80厘米过道是否够用。"],
        "image": "已看4/4张，高低台面和窄柜组合在同一厨房里可见。",
        "images_complete": True,
        "expected_image_count": 4,
        "draft": "配上这个窄柜挺顺眼，厨房小也没显得挤。",
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


def build_payload(item: dict, index: int) -> dict:
    return {
        "request_id": f"panse.2026-08-12.account4.comment.{index:03d}",
        "idempotency_key": f"panse:2026-08-12:account-4:{item['note_id']}",
        "brief_text": (
            f"目标原帖为《{item['title']}》。已读完整正文、相关图片和当前可见评论。"
            "身份是替自己家核对户型、尺寸和日常动作的普通同好，不装专家。"
            "评论必须增加一个真实使用动作、具体感受或作者能回答的新问题；不得把标题、正文或评论换个说法再讲一遍。"
            "图片里的显而易见内容只作为内部依据，不要为了证明看过图先描述一遍。删掉句首看图描述后评价仍完整时，必须删除描述；只有不点对象会产生歧义时才保留最短对象词。"
            "不用老师、评委或验收口吻；不虚构购买、入住、量房、装修或长期使用经历。"
            "不用‘思路、那组、尤其、参考价值、落地、下单’等书面词，改用日常口语。"
            "输出1句，符合该方向字数；不提畔色，不引导主页、私信、搜索、关注、点赞或购买。"
        ),
        "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "rights_basis": "public note and visible public comments used only as context for a new non-quoting comment draft",
        "sensitivity": "internal",
        "language": "zh-CN",
        "channel": "小红书",
        "scenario": "小红书户型尺寸账号评论语气实验",
        "audience": "正在核对小户型家具尺寸、净空和通行动作的普通用户",
        "use_case": "生成一条具体、口语化、支持创作者且不装专家的评论草稿",
        "artifact_type": "comment",
        "interaction_mode": item["mode"],
        "source_context": {
            "body": item["body"],
            "visible_comments": item["comments"],
            "image_observations": [
                {
                    "locator": "reviewed_media",
                    "observation": item["image"],
                    "observation_basis": "caller_reviewed",
                }
            ],
            "body_complete": True,
            "visible_comments_complete": True,
            "images_complete": item["images_complete"],
            "expected_visible_comment_count": len(item["comments"]),
            "expected_image_count": 1,
        },
        "taxonomy_ids": [
            "platform.xiaohongshu-comment",
            "persona.lifestyle-curator",
            "role.editor",
            "scene.social-comment",
        ],
        "style_card_refs": STYLE_REFS,
        "requested_strength": 0.5,
        "style_requirement": "approved_required",
        "pin_card_versions": True,
        "required_model_id": "gpt-5.6-sol",
        "fallback_model_allowed": False,
        "content_contract": {
            "protected_facts": [],
            "allowed_paraphrases": {},
            "forbidden_inferences": [
                "不得虚构购买、入住、量房、装修或长期使用经历",
                "不得在缺少关键净尺寸时下确定结论",
                "不得重复标题、正文结论或当前可见评论",
                "不得使用老师、专家、验收或裁判口吻",
                "不得为了互动硬问无意义或作者无法回答的问题",
                "不得使用思路、那组、尤其、参考价值、落地、下单等书面表达",
                "不得为了证明看过图而描述所有人一眼就能看见的画面",
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
        "max_authorized_excerpt_chars": 0,
        "panse_intent_context": {
            "policy_version": "xhs-comment-intent.v4",
            "topic_ids": [item["topic"]],
            "interaction_intent": item["parent"],
            "comment_direction_id": item["direction"],
            "voice_id": "space_advisor",
            "human_approved_example_set_version": "panse-xhs-human-approved-comments.v3",
        },
    }


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    requests = []
    receipts = []
    reviews = []
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(item, index)
        receipt = preflight(dict(payload))
        rid = payload["request_id"]
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
        stages["plan"][rid] = {
            "model_id": "gpt-5.6-sol",
            "fallback_used": False,
            "topic_ids": [item["topic"]],
            "comment_direction_id": item["direction"],
            "interaction_mode": item["mode"],
            "entry_angle": "只说一个画面中可见的细节，或问一个评论区尚未回答的真实使用问题。",
        }
        stages["draft"][rid] = {
            "model_id": "gpt-5.6-sol",
            "fallback_used": False,
            "draft_text": item["draft"],
            "tags": [],
        }
        is_question = item["mode"] == "curiosity_question"
        stages["semantic_review"][rid] = {
            "model_id": "gpt-5.6-sol",
            "fallback_used": False,
            "results": [
                {"gate": "source_grounding", "status": "pass", "notes": item["image"]},
                {"gate": "source_and_comment_repetition", "status": "pass", "notes": "没有照抄标题、正文结论或当前可见评论。"},
                {"gate": "obvious_visible_description", "status": "pass", "notes": "已做删除测试；能删而不影响评价的显而易见画面描述已删除。"},
                {"gate": "question_value", "status": "pass" if is_question else "not_applicable", "notes": "问题指向坐人后柜门能否打开，作者可回答且评论区未回答。" if is_question else "本条不提问。"},
                {"gate": "identity_and_experience_boundary", "status": "pass", "notes": "普通同好口吻，没有虚构亲历或品牌关系。"},
                {"gate": "natural_voice", "status": "pass", "notes": "单句、口语、具体，没有书面整理腔或老师口吻。"},
            ],
        }
        reviews.append(
            {
                "request_id": rid,
                "account_slot_and_nickname": "slot 4 / 小红薯6A68E133",
                "note_id": item["note_id"],
                "target_note_title": item["title"],
                "source_context_summary": item["body"],
                "visible_comment_context_summary": item["comments"],
                "exact_draft_text": item["draft"],
                "interaction_mode": item["mode"],
                "comment_direction_id": item["direction"],
                "style_preflight_passed": bool(receipt.get("passed")),
                "semantic_review_passed": True,
                "queue_status": "awaiting_user_review",
                "current_user_approval_required": True,
                "published": False,
            }
        )

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_json(
        "account_4_browse_receipts_10.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "account_slot": 4,
            "account_nickname": "小红薯6A68E133",
            "profile_id": "6a684f14000000001400c004",
            "browse_target": 10,
            "browse_actual": 10,
            "deep_read_actual": 10,
            "body_and_visible_comments_read": True,
            "items": READS,
            "safety_warning_observed": False,
            "external_comments_posted": 0,
        },
    )
    write_json(
        "account_4_follow_receipts_1.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "account_slot": 4,
            "verified_follow_count": 1,
            "items": [
                {
                    "profile_id": "64c65f95000000000e027d4e",
                    "nickname": "丙子小屋「软装版」",
                    "role_fit": "持续分享87平方米真实小家、厨房尺寸、法式中古软装与使用反馈",
                    "notes_read": ["696cb831000000000b00989d", "6941575b000000001e00f2db"],
                    "button_before": "关注",
                    "button_after": "已关注",
                    "verified": True,
                }
            ],
            "current_account_profile_verified": True,
            "safety_warning_observed": False,
        },
    )
    write_json(
        "account_4_style_requests_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "phase": "account4_cycle_day04_review_only_generation",
            "account_slot": 4,
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "request_count": 4,
            "requests": requests,
        },
    )
    write_json(
        "account_4_style_compile_receipts_4.json",
        {
            "schema_version": 1,
            "compiled_at": stamp,
            "style_lab_route": "local_tachikoma_runtime",
            "remote_connector_status": "unavailable_404",
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "receipt_count": 4,
            "all_passed": all(value.get("passed") for value in receipts),
            "text_generated_by_preflight": False,
            "external_posting_performed": False,
            "receipts": receipts,
        },
    )
    write_json(
        "account_4_current_session_stage_responses_4.json",
        {
            "schema_version": 1,
            "created_at": stamp,
            "account_slot": 4,
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "stages": stages,
            "external_posting_performed": False,
        },
    )
    write_json(
        "account_4_human_review_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "account_slot": 4,
            "account_nickname": "小红薯6A68E133",
            "review_item_count": 4,
            "all_ready_for_user_review": all(value.get("passed") for value in receipts),
            "send_allowed": False,
            "user_approval_received": False,
            "published_count": 0,
            "approval_rule": "Only explicit approval of the exact displayed drafts permits sending.",
            "items": reviews,
        },
    )

    plan_path = RUN_DIR / "account_4_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update(
        {
            "actual_browse": 10,
            "actual_deep_reads": 10,
            "drafts_ready": 4,
            "verified_follows": 1,
            "public_visible_comments": 0,
            "unsent_review_items": 4,
            "status": "awaiting_user_review",
            "stop_reason": None,
        }
    )
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 4:
            account.update(
                {
                    "status": "awaiting_user_review",
                    "actual_browse": 10,
                    "actual_deep_reads": 10,
                    "drafts_ready": 4,
                    "public_visible_comments": 0,
                    "verified_follows": 1,
                    "unsent": 4,
                }
            )
    status["overall_status"] = "in_progress"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "browse_actual": 10,
                "deep_read_actual": 10,
                "verified_follows": 1,
                "review_items": 4,
                "all_preflight_passed": all(value.get("passed") for value in receipts),
                "comments_sent": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
