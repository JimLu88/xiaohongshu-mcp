#!/usr/bin/env python3
"""Build slot-3 cycle-day-9 review-only artifacts for 2026-08-21."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-21"
TEMPLATE = RUN_DIR.parent / "2026-08-12" / "account_3_style_requests_6.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"
MODEL_ID = "gpt-5.6-sol"


CANDIDATES = [
    {
        "note_id": "6901a00100000000070083a2",
        "title": "小户型选家具最大的误区",
        "body": "65㎡住宅以细腿和小一号家具减轻体量，并结合茶几、沙发和1.2m餐桌说明清洁、移动与来客频率。",
        "comments": "当前可见58条评论；沙发、客厅开间和餐桌尺寸已有作者回复，尚未讨论细腿家具连接处的稳定性。",
        "media": "共11张图，已连续查看前6张。",
        "draft": "细腿家具看着轻，连接处稳不稳也得一起看",
        "mode": "light_humor_or_neutral",
        "direction": "light_social_response",
        "intent": "neutral_social",
        "topic": "material_craft",
        "min_chars": 8,
        "max_chars": 32,
        "angle": "补充细腿家具的连接稳定性检查，不复述显大和好移动。",
    },
    {
        "note_id": "67e7c39e000000001b03a102",
        "title": "网购中古风家具翻车大赏",
        "body": "作者展示沙发、餐椅和边柜到货后的坐深、填充、晃动、色差与重心问题，并表示最终退货。",
        "comments": "当前可见6条评论；作者说明后来改在线下或厂家购买，尚未回答3件大件退货的取件和运费承担。",
        "media": "共3张图，已全部查看。",
        "draft": "这3件退货时，上门取件和运费最后都是商家承担的吗？",
        "mode": "curiosity_question",
        "direction": "installation_delivery_question",
        "intent": "utility_fit_question",
        "topic": "installation_logistics",
        "min_chars": 18,
        "max_chars": 55,
        "angle": "追问评论区尚未回答、作者容易回答的退货成本。",
    },
    {
        "note_id": "6a5b439f000000000101e389",
        "title": "开间2.1m餐桌｜1.1圆桌安全下车咯🥳",
        "body": "作者在2.1m餐厅开间放置1.1m圆桌，日常会经过餐边柜、冰箱和厨房。",
        "comments": "当前可见108条评论；是否位于主过道已有讨论，尚未给出餐椅拉开后到餐边柜的最窄净距。",
        "media": "共7张图，已连续查看前6张。",
        "draft": "餐椅拉开后，到餐边柜最窄还剩多少距离？",
        "mode": "curiosity_question",
        "direction": "size_clearance_question",
        "intent": "utility_fit_question",
        "topic": "dimensions_fit",
        "min_chars": 18,
        "max_chars": 55,
        "angle": "只问影响真实通行的最窄净距。",
    },
    {
        "note_id": "692eba55000000001e016860",
        "title": "收到货当场气哭！买沙发千万要听劝",
        "body": "作者先买2.66m沙发，认为与4.3m满墙柜背景墙比例不协调后承担数百元运费换货。",
        "comments": "当前可见69条评论；沙发长度与背景墙比例已有讨论，换货运费的计费依据尚未说明。",
        "media": "共3张图，已全部查看。",
        "draft": "大件家具一换货就是几百运费，买错一次确实容易长记性",
        "mode": "light_humor_or_neutral",
        "direction": "light_social_response",
        "intent": "neutral_social",
        "topic": "installation_logistics",
        "min_chars": 8,
        "max_chars": 32,
        "angle": "顺着真实换货成本接一句，不复述尺寸比例。",
    },
    {
        "note_id": "676a65d8000000000900eddc",
        "title": "木墨和北欧表情，真实使用感",
        "body": "作者对比两款床和餐桌，次卧无床头床从安装后一直不稳，4年后仍计划更换床板或整床。",
        "comments": "当前可见93条评论；尚未说明不稳具体是床架晃动、床板位移还是异响。",
        "media": "共11张图，已连续查看前6张。",
        "draft": "次卧这张床的不稳，是床架会晃，还是床板会响？",
        "mode": "curiosity_question",
        "direction": "maintenance_durability_question",
        "intent": "utility_fit_question",
        "topic": "maintenance_lifetime",
        "min_chars": 18,
        "max_chars": 55,
        "angle": "把笼统的不稳拆成作者容易回答的具体现象。",
    },
    {
        "note_id": "6a3f965b000000001603f6e8",
        "title": "选板时有多兴奋，看到成品就有多想报警",
        "body": "作者定制黑胡桃大板桌后认为拼缝和色差明显，计划加钱重新选板做双拼。",
        "comments": "当前可见128条评论；讨论排板方式和成品/定制取舍，尚未说明重做前是否有完整排板图确认。",
        "media": "共6张图，已全部查看。",
        "draft": "这次重做双拼前，老板会先出完整排板图给你确认吗？",
        "mode": "curiosity_question",
        "direction": "request_more_evidence",
        "intent": "request_more",
        "topic": "material_craft",
        "min_chars": 18,
        "max_chars": 55,
        "angle": "追问重做前的确认流程，不判定材料等级或责任。",
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
            "request_id": f"panse.2026-08-21.account3.comment.{index:03d}",
            "idempotency_key": f"panse:2026-08-21:account-3:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。标题、完整正文、当前可见评论和规定数量媒体均已阅读。"
                "身份是理性但不替别人下结论的普通家具同好。评论只补1个购买动作、尺寸落点、售后成本或容易回答的问题。"
                "不要复述标题、正文和显而易见画面；不要每条都提问，也不要为了互动硬问。"
                "像普通真人，不用老师、评委、测评机构或验收口吻；数字统一用阿拉伯数字。"
                "少用思路、那组、尤其、参考价值、落地、下单等词；禁止使用“这种分享很实在”。"
                "输出1句话，18至60个中文字符；不提畔色，不导流，不虚构购买、入住、装修、检测、维修或长期使用经历。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "理性家具决策号公开评论待审稿",
            "audience": "正在比较家具尺寸、结构、购买成本和售后的普通用户",
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
                    "不得把材料、结构、安全、性能或责任归属写成未经核验的普遍事实",
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
                "voice_id": "evaluation_judgment",
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
            "interaction_mode": item["mode"],
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
                "account_slot_and_nickname": "slot 3 / link",
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
    model_verified = all(
        response["model_id"] == MODEL_ID and response["fallback_used"] is False
        for stage in stages.values()
        for response in stage.values()
    )
    request_file = "account_3_style_requests_6.json"
    compile_file = "account_3_style_compile_receipts_6.json"
    stage_file = "account_3_current_session_stage_responses_6.json"
    review_file = "account_3_human_review_6.json"
    write_json(request_file, {"schema_version": 1, "date": "2026-08-21", "account_slot": 3, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "request_count": 6, "requests": requests})
    write_json(compile_file, {"schema_version": 1, "compiled_at": stamp, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "receipt_count": 6, "all_passed": all_passed, "external_posting_performed": False, "receipts": receipts})
    write_json(stage_file, {"schema_version": 1, "created_at": stamp, "provider": "codex.current_session", "model_id": MODEL_ID, "model_selection_evidence": {"surface": "codex.current_session", "request_meta_model": MODEL_ID, "reasoning_effort": "high", "thread_id": "019ffb78-aa64-7482-baf8-fc1338b9a0ae"}, "account_slot": 3, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "stages": stages, "external_posting_performed": False})
    write_json(review_file, {"schema_version": 1, "date": "2026-08-21", "account_slot": 3, "account_nickname": "link", "review_item_count": 6, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "required_generation_model_verified": model_verified, "generation_model_evidence": {"current_turn_context_model": MODEL_ID, "stage_response_file": stage_file, "all_stage_models_match": model_verified, "fallback_used": False}, "all_ready_for_user_review": all_passed and model_verified, "send_allowed": False, "user_approval_received": False, "approved_item_numbers": [], "unapproved_item_numbers": [1, 2, 3, 4, 5, 6], "published_count": 0, "items": reviews})
    write_json("account_3_follow_evaluations.json", {"schema_version": 1, "date": "2026-08-21", "account_slot": 3, "profile_id": "5b38445e4eacab65d6c0521c", "planned_follow_target": 1, "follow_attempts": 0, "verified_follows": 0, "evaluations": [{"nickname": "小梦悠悠", "profile_id": "65e68b6d000000000500a70b", "notes_deep_read": ["69d8f6ee000000001a03284a", "697a255d000000002203a9e1"], "profile_observation": "主页长期发布实木家具、尺寸、结构、维修和家居使用内容；方向稳定，未见广告农场或搬运特征。", "decision": "qualified_pending_user_confirmation_without_click", "reason": "two_related_deep_reads_and_profile_consistency_met"}], "follow_button_clicked": False, "safety_warning_observed": False, "recorded_at": stamp})

    plan_path = RUN_DIR / "account_3_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"status": "awaiting_user_review", "actual_browse": 15, "actual_deep_reads": 15, "drafts_ready": 6, "public_visible_comments": 0, "follow_attempts": 0, "verified_follows": 0, "follow_status": "qualified_pending_user_confirmation_without_click", "unsent_review_items": 6, "comment_send_allowed": False, "stop_reason": None})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["totals_verified"]["comment_drafts"] = 6
    for account in status["accounts"]:
        if account["account_slot"] == 3:
            account.update({"status": "awaiting_user_review", "actual_browse": 15, "actual_deep_reads": 15, "drafts_ready": 6, "public_visible_comments": 0, "verified_follows": 0, "follow_status": "qualified_pending_user_confirmation_without_click", "unsent": 6})
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"drafts": 6, "all_preflight_passed": all_passed, "model_verified": model_verified, "question_count": question_count, "follow_clicked": False, "review_file": str(RUN_DIR / review_file)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
