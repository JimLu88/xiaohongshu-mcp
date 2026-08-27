#!/usr/bin/env python3
"""Build the slot-5 inbound-question reply review packet for 2026-08-21."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-21"
TEMPLATE = RUN_DIR.parent / "2026-08-12" / "account_5_style_requests_4.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"
MODEL_ID = "gpt-5.6-sol"
THREAD_ID = "019ffb78-aa64-7482-baf8-fc1338b9a0ae"
REQUEST_ID = "panse.2026-08-21.account5.inbound-reply.001"
NOTE_ID = "6a59ad51000000000f03094f"
EXACT_DRAFT = (
    "2.7×2.2m先别买1.6m，2—3人选1.2m、4人选1.4m更稳；"
    "桌宽按0.85m算，两侧坐人后基本不能再当过道。"
)


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def compile_style(payload: dict) -> dict:
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


def build_payload() -> dict:
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0][
        "style_request"
    ]
    payload = copy.deepcopy(base)
    payload.update(
        {
            "request_id": REQUEST_ID,
            "idempotency_key": (
                "panse:2026-08-21:account-5:inbound-question:"
                "6a59ad51000000000f03094f:5b68e71db4a9280001512d8c"
            ),
            "brief_text": (
                "回复自己笔记《餐桌1.4还是1.6？做桌子的教你选》下的一条明确尺寸问题。"
                "先根据2.7×2.2m净空间给条件化尺寸建议，再指出2.2m宽的通行限制。"
                "只回答提问，不推销，不导流，不虚构上门测量或真实入住经历。"
                "像普通真人直接回复，使用阿拉伯数字，不使用老师、评委或验收口吻。"
                "输出1至2句，25至70个中文字符；精确信息不足时保留条件，不写成普遍事实。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{NOTE_ID}",
            "scenario": "品牌运营编辑子账号收到的公开尺寸问题回复待审稿",
            "audience": "正在为2.7×2.2m净餐厅选择餐桌尺寸的普通用户",
            "use_case": "生成一条回答明确问题并等待人工批准的公开回复草稿",
            "interaction_mode": "soft_observation",
            "source_context": {
                "body": (
                    "原笔记说明桌宽按850mm计算，椅子拉开坐人约需750mm，走人约需900mm；"
                    "按人数建议1.2m适合2人并偶尔加1位，1.4m适合标准4口，1.6m适合4口且常来客。"
                ),
                "visible_comments": [
                    "宝瓶：除去餐边柜，长2.7，宽2.2，买多大餐桌合适"
                ],
                "image_observations": [
                    {
                        "locator": "image_1_cover",
                        "observation": "封面展示长方形餐桌的多人使用场景。",
                        "observation_basis": "caller_reviewed",
                    },
                    {
                        "locator": "image_2_dimensions",
                        "observation": "尺寸图标注桌宽850mm、桌高750mm，长度含1400、1600和1800mm。",
                        "observation_basis": "caller_reviewed",
                    },
                    {
                        "locator": "image_3_product_info",
                        "observation": "规格图列出1.2m、1.4m、1.6m、1.8m和2m可选长度。",
                        "observation_basis": "caller_reviewed",
                    },
                    {
                        "locator": "image_4_black_table_use",
                        "observation": "黑色桌面实际摆放餐具后的使用场景。",
                        "observation_basis": "caller_reviewed",
                    },
                    {
                        "locator": "image_5_black_table_closeup",
                        "observation": "黑色桌面的近景使用场景。",
                        "observation_basis": "caller_reviewed",
                    },
                    {
                        "locator": "image_6_seated_use",
                        "observation": "一人落座、其余餐椅围桌的实际空间关系。",
                        "observation_basis": "caller_reviewed",
                    },
                ],
                "body_complete": True,
                "visible_comments_complete": True,
                "images_complete": True,
                "expected_visible_comment_count": 1,
                "expected_image_count": 6,
            },
            "required_model_id": MODEL_ID,
            "fallback_model_allowed": False,
            "content_contract": {
                "protected_facts": [
                    {
                        "fact_id": "room.net_dimensions",
                        "kind": "number",
                        "required": True,
                        "value": "2.7×2.2m",
                        "qualifiers": ["提问者说明已除去餐边柜"],
                    },
                    {
                        "fact_id": "table.width",
                        "kind": "number",
                        "required": True,
                        "value": "0.85m",
                        "qualifiers": ["来自原笔记正文与尺寸图"],
                    },
                    {
                        "fact_id": "table.length_by_people",
                        "kind": "qualifier",
                        "required": True,
                        "value": "1.2m对应2人并偶尔加1位；1.4m对应标准4口",
                        "qualifiers": ["来自原笔记正文"],
                    },
                ],
                "allowed_paraphrases": {},
                "forbidden_inferences": [
                    "不得假定提问者的常住人数、门洞位置或实际通道方向",
                    "不得把尺寸建议写成适用于所有户型的普遍结论",
                    "不得推荐具体品牌产品、价格或购买链接",
                    "不得虚构上门测量、购买、入住、装修或长期使用经历",
                    "不得使用老师、评委、测评机构或验收口吻",
                    "不得使用用户明确否决的固定表达“这种分享很实在”",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            "output": {
                "title_candidates": 0,
                "title_max_chars": 0,
                "body_min_chars": 25,
                "body_max_chars": 70,
                "tag_min": 0,
                "tag_max": 0,
            },
            "panse_intent_context": {
                "policy_version": "xhs-comment-intent.v4",
                "topic_ids": ["household_constraints", "dimensions_fit"],
                "interaction_intent": "peer_tip_invited",
                "comment_direction_id": "invited_peer_tip",
                "voice_id": "global_design_observer",
                "human_approved_example_set_version": (
                    "panse-xhs-human-approved-comments.v3"
                ),
            },
        }
    )
    return payload


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    receipt = compile_style(payload)
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    style_passed = bool(receipt.get("passed"))
    stage_file = "account_5_inbound_question_reply_stage_response_1.json"

    write_json(
        "account_5_inbound_question_reply_style_request_1.json",
        {
            "schema_version": 1,
            "date": "2026-08-21",
            "account_slot": 5,
            "required_model_id": MODEL_ID,
            "fallback_model_allowed": False,
            "request_count": 1,
            "requests": [
                {
                    "target_note": {
                        "note_id": NOTE_ID,
                        "title": "餐桌1.4还是1.6？做桌子的教你选",
                        "source_locator": payload["source_locator"],
                    },
                    "incoming_comment": {
                        "author_nickname": "宝瓶",
                        "author_profile_id": "5b68e71db4a9280001512d8c",
                        "exact_text": "除去餐边柜，长2.7，宽2.2，买多大餐桌合适",
                        "classification": "explicit_information_seeking_question",
                    },
                    "style_request": payload,
                }
            ],
        },
    )
    write_json(
        "account_5_inbound_question_reply_compile_receipt_1.json",
        {
            "schema_version": 1,
            "compiled_at": stamp,
            "required_model_id": MODEL_ID,
            "fallback_model_allowed": False,
            "receipt_count": 1,
            "all_passed": style_passed,
            "external_posting_performed": False,
            "receipts": [receipt],
        },
    )
    write_json(
        stage_file,
        {
            "schema_version": 1,
            "created_at": stamp,
            "provider": "codex.current_session",
            "model_id": MODEL_ID,
            "model_selection_evidence": {
                "surface": "codex.current_session",
                "request_meta_model": MODEL_ID,
                "reasoning_effort": "high",
                "thread_id": THREAD_ID,
            },
            "account_slot": 5,
            "required_model_id": MODEL_ID,
            "fallback_model_allowed": False,
            "stages": {
                "plan": {
                    REQUEST_ID: {
                        "model_id": MODEL_ID,
                        "fallback_used": False,
                        "interaction_mode": "soft_observation",
                        "comment_direction_id": "invited_peer_tip",
                        "entry_angle": "按人数给1.2m与1.4m两个条件答案，并明确2.2m宽不能兼顾两侧坐人和主通道。",
                    }
                },
                "draft": {
                    REQUEST_ID: {
                        "model_id": MODEL_ID,
                        "fallback_used": False,
                        "draft_text": EXACT_DRAFT,
                        "tags": [],
                    }
                },
                "semantic_review": {
                    REQUEST_ID: {
                        "model_id": MODEL_ID,
                        "fallback_used": False,
                        "results": [
                            {
                                "gate": "explicit_question_eligibility",
                                "status": "pass",
                                "notes": "来评明确询问餐桌尺寸，符合当前只回复问题的范围。",
                            },
                            {
                                "gate": "source_thread_and_media_grounding",
                                "status": "pass",
                                "notes": "已读取原笔记完整正文、唯一可见评论及6张图。",
                            },
                            {
                                "gate": "conditional_dimension_boundary",
                                "status": "pass",
                                "notes": "人数未知，因此分别给2—3人与4人的条件答案；通道判断仅针对2.2m宽和0.85m桌宽。",
                            },
                            {
                                "gate": "identity_and_promotion_boundary",
                                "status": "pass",
                                "notes": "未虚构测量或使用经历，未推荐品牌、价格或链接。",
                            },
                            {
                                "gate": "natural_direct_reply",
                                "status": "pass",
                                "notes": "60字符，直接回答，不使用老师口吻或模板化收尾。",
                            },
                        ],
                    }
                },
            },
            "external_posting_performed": False,
        },
    )
    write_json(
        "account_5_inbound_question_reply_human_review_1.json",
        {
            "schema_version": 1,
            "date": "2026-08-21",
            "account_slot": 5,
            "account_nickname": "是阿宝啊",
            "account_profile_id": "6347830c0000000012027db3",
            "review_item_count": 1,
            "required_model_id": MODEL_ID,
            "fallback_model_allowed": False,
            "required_generation_model_verified": True,
            "generation_model_evidence": {
                "current_turn_context_model": MODEL_ID,
                "stage_response_file": stage_file,
                "all_stage_models_match": True,
                "fallback_used": False,
            },
            "all_ready_for_user_review": style_passed,
            "send_allowed": False,
            "user_approval_received": False,
            "approved_item_numbers": [],
            "unapproved_item_numbers": [1],
            "published_count": 0,
            "items": [
                {
                    "request_id": REQUEST_ID,
                    "account_slot_and_nickname": "slot 5 / 是阿宝啊",
                    "note_id": NOTE_ID,
                    "target_note_title": "餐桌1.4还是1.6？做桌子的教你选",
                    "source_context_summary": (
                        "原笔记按0.85m桌宽说明餐厅净距，并按人数区分1.2m、1.4m和1.6m桌长。"
                    ),
                    "visible_comment_context_summary": (
                        "当前共1条评论；宝瓶给出除去餐边柜后的净空间2.7×2.2m，询问餐桌尺寸，未说明常住人数和主通道方向。"
                    ),
                    "incoming_question_exact_text": (
                        "除去餐边柜，长2.7，宽2.2，买多大餐桌合适"
                    ),
                    "exact_draft_text": EXACT_DRAFT,
                    "style_preflight_passed": style_passed,
                    "semantic_review_passed": True,
                    "queue_status": "awaiting_user_review",
                    "current_user_approval_required": True,
                    "current_user_approval_received": False,
                    "send_authorized": False,
                    "published": False,
                }
            ],
        },
    )
    print(
        json.dumps(
            {
                "style_preflight_passed": style_passed,
                "model_verified": True,
                "draft_length": len(EXACT_DRAFT),
                "exact_draft": EXACT_DRAFT,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
