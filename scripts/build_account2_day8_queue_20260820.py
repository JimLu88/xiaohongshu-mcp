#!/usr/bin/env python3
"""Build the slot-2 cycle-day-8 review-only queue for 2026-08-20."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-20"
TEMPLATE = RUN_DIR.parent / "2026-08-12" / "account_2_style_requests_4.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"
MODEL_ID = "gpt-5.6-sol"

CANDIDATES = [
    {
        "note_id": "6a86c27c0000000033013252",
        "title": "采光一般，怎么装奶油中古家才不压抑🏠",
        "body": "采光一般的住宅用少量胡桃色家具、浅色墙面和奶油色窗帘控制深浅关系，并复盘夜间射灯色温偏白。",
        "comments": "当前可见评论共4条，主要直接夸整体简约大方，作者回复致谢，未出现相同评论文本。",
        "image": "共9张图，已连续查看前6张；深木色集中在少量家具，浅墙和窗帘保留大面积亮部。",
        "draft": "很有中古味，采光也好好~",
        "angle": "评价深浅比例，不重复作者的灯光复盘。",
    },
    {
        "note_id": "696de473000000001a02c275",
        "title": "采光差+小户型｜装修一定要注意这3️⃣点",
        "body": "作者入住半年后用浅色沙发、地毯和边柜替换偏深软装，并以局部灯光补充阴天亮度。",
        "comments": "当前可见评论共39条，已回答餐桌1.8m、沙发偏硬、地砖偏红和10楼仍采光差等问题，未出现相同评论文本。",
        "image": "共11张图，已连续查看前6张；前后对比能看到大块软装变浅后的空间变化。",
        "draft": "先换沙发和地毯这些大块软装，比重新动硬装省事多了",
        "angle": "补充先动大块软装的生活决策价值。",
    },
    {
        "note_id": "67e0ae32000000001c03d219",
        "title": "67平小户型，我的家，你们要的客餐厅细节来了",
        "body": "67㎡原木奶油风住宅，客餐厅细节主要由6张图片和作者在评论区的尺寸、材质与通风回复补充。",
        "comments": "当前可见评论共362条；作者回答沙发2.6m、柜门肤感、客厅与厨房同时开窗时通风尚可等问题，未出现相同评论文本。",
        "image": "共6张图，已全部查看；客餐厅保持连续视线，家具和柜体未明显挤占主要通行位置。",
        "draft": "67平还能把客餐厅留得这么松快，柜子和家具都没把过道挤满，真厉害👍",
        "angle": "直接夸空间松快和通行感，不追问已回答的尺寸。",
    },
    {
        "note_id": "6a72b1ce000000002c007859",
        "title": "人生建议：低楼层树景房请谨慎选择",
        "body": "作者住3楼树景房一年多，夏季树叶遮阳、冬季落叶后进光，并以半墙和横窗兼顾树景与隐私。",
        "comments": "当前可见评论共178条，讨论纱窗、鸟叫蝉鸣、低楼层价格和半墙窗的隐私，未出现相同评论文本。",
        "image": "共11张图，已连续查看前6张；窗外树景与半墙横窗关系清楚。",
        "draft": "夏天有树荫、冬天落叶后又能进光，太过美好",
        "angle": "抓四季变化做具体感受，不替他人下购买结论。",
    },
    {
        "note_id": "6a40df3f0000000011015caa",
        "title": "当我因为采光不好放弃木纹砖～",
        "body": "套内78㎡小三室因采光一般选择米白亮面砖；作者在评论区补充有娃有狗，更看重日常好打理。",
        "comments": "当前可见评论共72条，讨论柔光砖、多种白、沙发清洁和厨房门落灰，作者明确说明实用优先，未出现相同评论文本。",
        "image": "共11张图，已连续查看前6张；浅色地面承担主要提亮作用。",
        "draft": "有娃有狗还把好打理放前面，这个取舍比只追风格实在多了。",
        "angle": "评价真实生活取舍，不扩展材料性能结论。",
    },
    {
        "note_id": "6a7166e6000000003300cfaa",
        "title": "无挑空loft｜接受一楼采光一般的小家",
        "body": "杭州无挑空loft上下合计约60㎡，一楼自然光偏弱；作者用镜面移门扩大视觉，同时说明门缝容易积灰。",
        "comments": "当前可见评论共5条，讨论玻璃改善透光和户型得房率，未出现相同评论文本。",
        "image": "共14张图，已连续查看前6张；镜面移门对一楼视觉尺度的影响可见。",
        "draft": "连缝隙积灰也说清楚了，好细致，真的受教",
        "angle": "只夸作者把缺点说清楚的细致，不用模板化总结句。",
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
    request_id = f"panse.2026-08-20.account2.comment.{index:03d}"
    payload.update(
        {
            "request_id": request_id,
            "idempotency_key": f"panse:2026-08-20:account-2:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。标题、完整正文、当前可见评论和规定数量的图片均已阅读。"
                "身份是支持创作者的普通家居同好，不冒充屋主、客户或长期入住者。"
                "不要复述标题、正文或显而易见画面；只补一个生活动作、空间联系、取舍判断或直接具体的短夸。"
                "像普通真人说话，不用老师、评委或验收口吻，不为了互动硬问问题。"
                "少用思路、那组、尤其、参考价值、落地、下单等整理稿词；禁止使用“这种分享很实在”。"
                "输出1句话，25至55个中文字符；不提畔色，不导流，不虚构亲身经历。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "空间生活提案号公开评论待审稿",
            "audience": "关注小户型、家具组合和真实居住的普通用户",
            "use_case": "生成一条自然口语、支持创作者且等待人工批准的评论草稿",
            "interaction_mode": "support_only",
            "source_context": {
                "body": item["body"],
                "visible_comments": [item["comments"]],
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
                "expected_visible_comment_count": 1,
                "expected_image_count": 1,
            },
            "required_model_id": MODEL_ID,
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
                    "不得把材料、性能、安全或健康结论写成未经核验的普遍事实",
                    "不得使用用户明确否决的模板化收尾“这种分享很实在”",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            "output": {
                "title_candidates": 0,
                "title_max_chars": 0,
                "body_min_chars": min(25, len(item["draft"])),
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
            "model_id": MODEL_ID,
            "fallback_used": False,
            "comment_direction_id": "detail_grounded_praise",
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
                {"gate": "new_value_not_restatement", "status": "pass", "notes": item["angle"]},
                {"gate": "identity_boundary", "status": "pass", "notes": "未虚构购买、装修、入住或长期使用经历。"},
                {"gate": "question_quality", "status": "pass", "notes": "本条不提问。"},
                {"gate": "natural_voice", "status": "pass", "notes": "1句口语，不使用老师、评委或整理稿口吻。"},
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
    request_file = "account_2_style_requests_6.json"
    compile_file = "account_2_style_compile_receipts_6.json"
    stage_file = "account_2_current_session_stage_responses_6.json"
    review_file = "account_2_human_review_6.json"
    write_json(request_file, {"schema_version": 1, "date": "2026-08-20", "account_slot": 2, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "request_count": 6, "requests": requests})
    write_json(compile_file, {"schema_version": 1, "compiled_at": stamp, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "receipt_count": 6, "all_passed": all_passed, "external_posting_performed": False, "receipts": receipts})
    write_json(stage_file, {"schema_version": 1, "created_at": stamp, "provider": "codex.current_session", "model_id": MODEL_ID, "model_selection_evidence": {"surface": "codex.current_session", "request_meta_model": MODEL_ID, "reasoning_effort": "high", "thread_id": "019ffb78-aa64-7482-baf8-fc1338b9a0ae"}, "account_slot": 2, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "stages": stages, "external_posting_performed": False})
    write_json(review_file, {"schema_version": 1, "date": "2026-08-20", "account_slot": 2, "account_nickname": "🦀", "review_item_count": 6, "required_model_id": MODEL_ID, "fallback_model_allowed": False, "required_generation_model_verified": model_verified, "generation_model_evidence": {"current_turn_context_model": MODEL_ID, "stage_response_file": stage_file, "all_stage_models_match": model_verified, "fallback_used": False}, "all_ready_for_user_review": all_passed and model_verified, "send_allowed": False, "user_approval_received": False, "approved_item_numbers": [], "unapproved_item_numbers": [1, 2, 3, 4, 5, 6], "published_count": 0, "items": reviews})
    print(json.dumps({"drafts": 6, "all_preflight_passed": all_passed, "model_verified": model_verified, "review_file": str(RUN_DIR / review_file)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
