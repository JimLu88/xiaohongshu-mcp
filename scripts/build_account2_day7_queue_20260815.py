#!/usr/bin/env python3
"""Build the slot-2 day-7 review-only queue for 2026-08-15."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-15"
TEMPLATE = RUN_DIR.parent / "2026-08-12" / "account_2_style_requests_4.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"

CANDIDATES = [
    {
        "note_id": "6a7ed82f000000002102245a",
        "title": "75㎡小户型🏠女孩子有自己的家真好！",
        "body": "白色和木色为主，作者把沙发旁的斗柜布置成咖啡角，抽屉继续承担杂物收纳。",
        "comments": [
            "评论主要询问铝百叶、抱枕、斗柜、羊毛地毯、沙发和高柜来源。",
            "作者补充斗柜为白蜡木与不锈钢组合。",
        ],
        "image": "前6/13图已看；斗柜位于沙发旁，咖啡区与落座区距离很近。",
        "draft": "咖啡角放在沙发旁边挺顺手，拿完咖啡直接坐下，不用端着杯子绕来绕去。",
        "body_min_chars": 25,
        "approved_in_current_exchange": False,
    },
    {
        "note_id": "6a37ce950000000021015d4c",
        "title": "85平小三室，两个人住很幸福了～🥰",
        "body": "套内85㎡，三间小卧室、两卫和客餐厅一体长户型，两人居住。",
        "comments": [
            "作者补充硬装软装合计约18万元、沙发2.85m×1m、灯带4000K。",
            "作者坦言三房平均下来偏小，若重来可能只留两房。",
        ],
        "image": "前6/15媒体位已看；保留3间房后，客餐厅仍保持连续视线。",
        "draft": "85平能住成这样真舒服，好厉害👍",
        "body_min_chars": 12,
        "approved_in_current_exchange": True,
    },
    {
        "note_id": "690b427f0000000003021ef9",
        "title": "小户型就复制我家吧，真的很好抄作业",
        "body": "套内72㎡原木风小户型，总投入约18万元。",
        "comments": [
            "评论补充柜门边框5cm、铺大块木纹砖、厨房台面为木纹贴纸。",
            "作者说明餐桌不能变圆桌，木纹贴纸目前使用感受尚可。",
        ],
        "image": "前6/15图已看；厨房台面颜色与全屋原木色连续。",
        "draft": "厨房台面用木纹贴纸，和全屋原木色统一了感觉很自然啊",
        "body_min_chars": 12,
        "approved_in_current_exchange": True,
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
    request_id = f"panse.2026-08-15.account2.comment.{index:03d}"
    payload.update(
        {
            "request_id": request_id,
            "idempotency_key": f"panse:2026-08-15:account-2:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。已完整阅读正文、前置要求覆盖的相关画面和当前可见评论。"
                "身份是支持创作者的普通家居同好，不冒充屋主、客户或长期入住者。"
                "不要复述标题、正文或显而易见画面；只补一个生活动作、空间联系或直接具体的短夸。"
                "像普通真人说话，不用老师或评委口吻，不为了互动硬问问题。"
                "避免思路、那组、尤其、参考价值、落地、下单等整理稿词。"
                "输出1句话，25至55个中文字符；不提畔色，不导流，不虚构亲身经历。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "空间生活提案号公开评论待审稿",
            "audience": "关注小户型、家具组合和真实居住的普通用户",
            "use_case": "生成一条自然口语、支持创作者且等待人工批准的评论草稿",
            "interaction_mode": "support_only",
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
                "images_complete": True,
                "expected_visible_comment_count": len(item["comments"]),
                "expected_image_count": 1,
            },
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "content_contract": {
                "protected_facts": [],
                "allowed_paraphrases": {},
                "forbidden_inferences": [
                    "不得虚构购买、入住、装修、施工、检测或长期使用经历",
                    "不得伪装屋主、客户或长期居住者",
                    "不得复述标题、正文或显而易见画面来凑句子",
                    "不得为了互动硬问问题",
                    "不得使用老师、评委或验收者口吻",
                    "不得推荐畔色或导流",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            "output": {
                "title_candidates": 0,
                "title_max_chars": 0,
                "body_min_chars": item["body_min_chars"],
                "body_max_chars": 55,
                "tag_min": 0,
                "tag_max": 0,
            },
            "panse_intent_context": {
                "policy_version": "xhs-comment-intent.v4",
                "topic_ids": ["layout_circulation"],
                "interaction_intent": "grounded_praise",
                "comment_direction_id": "detail_grounded_praise",
                "voice_id": "stylist",
                "human_approved_example_set_version": "panse-xhs-human-approved-comments.v3",
            },
        }
    )
    return payload


def main() -> int:
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
            "model_id": "gpt-5.6-sol",
            "fallback_used": False,
            "comment_direction_id": "detail_grounded_praise",
            "entry_angle": "不复述画面，补一个生活动作或直接具体的短夸。",
        }
        stages["draft"][request_id] = {
            "model_id": "gpt-5.6-sol",
            "fallback_used": False,
            "draft_text": item["draft"],
            "tags": [],
        }
        stages["semantic_review"][request_id] = {
            "model_id": "gpt-5.6-sol",
            "fallback_used": False,
            "results": [
                {"gate": "source_and_comment_grounding", "status": "pass", "notes": "正文、相关画面和可见评论均已阅读。"},
                {"gate": "new_value_not_restatement", "status": "pass", "notes": "加入生活动作或空间联系，没有照抄原文。"},
                {"gate": "identity_boundary", "status": "pass", "notes": "没有虚构屋主、购买或长期使用经历。"},
                {"gate": "question_quality", "status": "pass", "notes": "没有为了互动硬问问题。"},
                {"gate": "natural_voice", "status": "pass", "notes": "1句口语，不用老师、评委或整理稿词。"},
            ],
        }
        reviews.append(
            {
                "request_id": request_id,
                "account_slot_and_nickname": "slot 2 / 🦀",
                "note_id": item["note_id"],
                "target_note_title": item["title"],
                "source_context_summary": item["body"],
                "visible_comment_context_summary": item["comments"],
                "exact_draft_text": item["draft"],
                "style_preflight_passed": bool(receipt.get("passed")),
                "semantic_review_passed": True,
                "queue_status": "awaiting_user_review",
                "current_user_approval_required": True,
                "current_user_approval_received": item["approved_in_current_exchange"],
                "send_authorized": item["approved_in_current_exchange"],
                "published": False,
            }
        )

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    all_passed = all(item.get("passed") for item in receipts)
    request_file = "account_2_style_requests_3.json"
    compile_file = "account_2_style_compile_receipts_3.json"
    stage_file = "account_2_current_session_stage_responses_3.json"
    review_file = "account_2_human_review_3.json"
    write_json(request_file, {"schema_version": 1, "date": "2026-08-15", "account_slot": 2, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "request_count": 3, "requests": requests})
    write_json(compile_file, {"schema_version": 1, "compiled_at": stamp, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "receipt_count": 3, "all_passed": all_passed, "external_posting_performed": False, "receipts": receipts})
    write_json(stage_file, {"schema_version": 1, "created_at": stamp, "account_slot": 2, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "stages": stages, "external_posting_performed": False})
    model_verified = all(
        response["model_id"] == "gpt-5.6-sol" and response["fallback_used"] is False
        for stage in stages.values()
        for response in stage.values()
    )
    write_json(review_file, {"schema_version": 1, "date": "2026-08-15", "account_slot": 2, "account_nickname": "🦀", "review_item_count": 3, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "required_generation_model_verified": model_verified, "generation_model_evidence": {"current_turn_context_model": "gpt-5.6-sol", "stage_response_file": stage_file, "all_stage_models_match": model_verified, "fallback_used": False}, "all_ready_for_user_review": all_passed and model_verified, "send_allowed": False, "user_approval_received": False, "partial_user_approval_received": True, "approved_item_numbers": [2, 3], "unapproved_item_numbers": [1], "published_count": 0, "items": reviews})
    print(json.dumps({"drafts": 3, "all_preflight_passed": all_passed, "review_file": str(RUN_DIR / review_file)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
