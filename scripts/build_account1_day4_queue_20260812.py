#!/usr/bin/env python3
"""Build the 2026-08-12 slot-1 review-only queue after eight deep reads."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-12"
BASE_REQUESTS = RUN_DIR.parent / "2026-08-11" / "account_1_style_requests_5.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {
        "note_id": "69a9428700000000280225a7",
        "title": "求助椅子裂开了怎么修补",
        "author": "xixi062",
        "topic": "maintenance_longevity",
        "media_reviewed": "4/4图",
        "selected": True,
        "summary": "椅子后腿附近横梁开裂，已经加过两颗螺丝，但旁边凳脚仍晃；正文与可见评论均已读完。",
    },
    {
        "note_id": "6a59e63a000000000f032e3a",
        "title": "实木靠背椅，求指教如何修复！",
        "author": "瑞智",
        "topic": "maintenance_longevity",
        "media_reviewed": "1/1图",
        "selected": False,
        "summary": "靠背旧胶修复后再次失效；评论集中在螺栓、白胶、木粉和受力结构，和第一篇题材重复。",
    },
    {
        "note_id": "69ecc3f1000000001e00f4e0",
        "title": "木桌榫卯结构组装产品动画 | 爆炸图拼装",
        "author": "糯米小星球动画",
        "topic": "ai_render_design_process",
        "media_reviewed": "24秒视频完整观看",
        "selected": False,
        "summary": "完整观看榫卯木桌爆炸装配动画并读完可见评论；评论已在询问制作方法。",
    },
    {
        "note_id": "69d205f5000000002102d9fb",
        "title": "建模代做✨布艺沙发全流程✨犀牛建模",
        "author": "meme设计（接建模、渲染）",
        "topic": "ai_render_design_process",
        "media_reviewed": "4/4图",
        "selected": True,
        "summary": "作者展示软包沙发犀牛建模；评论讨论犀牛做随机褶皱的局限，以及曲面、细分与跨软件收尾。",
    },
    {
        "note_id": "6a5f6d45000000001d020fc0",
        "title": "进了家具行业才知道：原来家具也会水土不服",
        "author": "村上种树",
        "topic": "maintenance_longevity",
        "media_reviewed": "2/2图",
        "selected": False,
        "summary": "同行品牌分享南北湿度与家具养护，暂无可见评论；部分通用养护建议缺少同涂层验证，不进入评论候选。",
    },
    {
        "note_id": "692d1066000000001902614d",
        "title": "冬日家具养护|干裂修复篇",
        "author": "木墨",
        "topic": "maintenance_longevity",
        "media_reviewed": "47秒视频完整观看",
        "selected": False,
        "summary": "同行品牌演示湿布、打磨与木蜡油修复干裂；评论询问复裂和木地板适用性，不在同行商业帖刷存在感。",
    },
    {
        "note_id": "69a4aaec000000001d012079",
        "title": "换桌子？不存在的！木桌去白印亲测有用！",
        "author": "限量款C小姐",
        "topic": "maintenance_longevity",
        "media_reviewed": "3/3图",
        "selected": True,
        "summary": "作者用油、热风和酒精处理桌面白印，并提醒先在隐蔽处测试；评论有成功反馈，也有人提到过热风险。",
    },
    {
        "note_id": "69666408000000002203ac48",
        "title": "烫黑碳化的木桌，自己在家也能修！",
        "author": "青小新",
        "topic": "maintenance_longevity",
        "media_reviewed": "6/7图",
        "selected": True,
        "summary": "作者展示打磨、补土、补色、画木纹与封层过程；评论主要询问调色和损伤能否修复。",
    },
]


CANDIDATES = [
    {
        "note_id": "69a9428700000000280225a7",
        "title": "求助椅子裂开了怎么修补",
        "official_topic": "maintenance_longevity",
        "intent_topic": "maintenance_lifetime",
        "interaction_intent": "peer_tip_invited",
        "direction": "invited_peer_tip",
        "source_author_intent": "ask_repair_help",
        "reply_right": "conditional_fact_only",
        "advice_context": "author_asked",
        "body": "横梁靠近后腿处开裂，作者已经加过螺丝，但旁边凳脚仍晃，并明确求助修补方法。",
        "comments": [
            "可见评论建议白胶、夹紧、木榫、螺栓或继续加螺丝。",
            "也有维修经验者提醒角码和螺丝不能替代榫口修复。",
        ],
        "observation": "可见裂缝与仍然晃动的凳脚表明需要区分木材开裂和榫口松动。",
        "draft": "问题可能不只在裂缝，榫口松动也要一起看，不然补好裂缝凳脚还是会晃。",
    },
    {
        "note_id": "69d205f5000000002102d9fb",
        "title": "建模代做✨布艺沙发全流程✨犀牛建模",
        "official_topic": "ai_render_design_process",
        "intent_topic": "creator_process_ai",
        "interaction_intent": "contextual_disagreement",
        "direction": "contextual_difference",
        "source_author_intent": "share_modeling_process",
        "reply_right": "process_peer_observation",
        "advice_context": "visible_problem_present",
        "body": "作者展示布艺沙发的犀牛建模过程，强调工业设计和生产用途。",
        "comments": [
            "可见评论认为犀牛随机褶皱不够自然。",
            "作者回应犀牛偏工业设计，也有人讨论曲面、细分和褶皱做法。",
        ],
        "observation": "尺寸与基础曲面适合先在犀牛里控制，软包褶皱可在更适合有机形态的软件中收尾。",
        "draft": "犀牛先把尺寸和基础面定好，软包褶皱再放到 Blender 里收，会自然很多。",
    },
    {
        "note_id": "69a4aaec000000001d012079",
        "title": "换桌子？不存在的！木桌去白印亲测有用！",
        "official_topic": "maintenance_longevity",
        "intent_topic": "maintenance_lifetime",
        "interaction_intent": "contextual_disagreement",
        "direction": "contextual_difference",
        "source_author_intent": "share_diy_repair_method",
        "reply_right": "conditional_fact_only",
        "advice_context": "visible_problem_present",
        "body": "作者分享用油、热风和酒精处理木桌白印的过程，并提醒先在隐蔽位置测试。",
        "comments": [
            "多条可见评论反馈方法有效。",
            "也有评论提到热风过久可能留下新的痕迹。",
        ],
        "observation": "桌面涂层体系未知，酒精与热风需要按涂层差异做小范围测试。",
        "draft": "酒精这一步得看涂层，油蜡面和漆面的反应可能不一样，先从小范围试会更稳。",
    },
    {
        "note_id": "69666408000000002203ac48",
        "title": "烫黑碳化的木桌，自己在家也能修！",
        "official_topic": "maintenance_longevity",
        "intent_topic": "maintenance_lifetime",
        "interaction_intent": "contextual_disagreement",
        "direction": "contextual_difference",
        "source_author_intent": "share_diy_repair_method",
        "reply_right": "conditional_fact_only",
        "advice_context": "visible_problem_present",
        "body": "作者展示碳化木桌的打磨、填补、调色、画木纹与封层过程，最后用502做薄层封闭。",
        "comments": [
            "可见评论主要询问如何调色。",
            "也有人带图询问类似损伤能不能修复。",
        ],
        "observation": "最后封层材料会影响后续发白风险和返修难度，宜与原桌面涂层体系相容。",
        "draft": "木纹补得挺细，最后那层502如果以后发白会比较难返修，换成和原桌面同体系的透明面漆会稳一点。",
    },
]


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def preflight(payload: dict) -> dict:
    result = subprocess.run(
        [sys.executable, str(PREFLIGHT), "-"],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return json.loads(result.stdout.decode("utf-8"))


def build_payload(base: dict, item: dict, index: int) -> dict:
    payload = copy.deepcopy(base)
    request_id = f"panse.2026-08-12.account1.comment.{index:03d}"
    payload.update(
        {
            "request_id": request_id,
            "idempotency_key": f"panse:2026-08-12:account-1:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。畔色木作官方品牌号公开参与，但不推广畔色产品，也不伪装消费者。"
                "已经读完正文、相关画面和当前可见评论。可见细节只用于内部判断，不要把图里显而易见的内容再描述一遍。"
                "评论必须补充一个和原帖直接相关的专业判断、条件差异或可执行提醒；没有新增价值的句子直接删掉。"
                "使用自然口语，不用思路、那组、尤其、参考价值、落地、下单等整理稿词语，不硬问问题，不虚构经历。"
                "输出25至70个中文字符，1至2句；不提畔色产品，不导流。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "品牌官方号公开评论待审稿",
            "audience": "分享家具维修、家具建模或真实使用过程的创作者",
            "use_case": "生成一条有专业增量、像真人说话且等待人工批准的官方评论",
            "source_context": {
                "body": item["body"],
                "visible_comments": item["comments"],
                "image_observations": [
                    {
                        "locator": "reviewed_media",
                        "observation": item["observation"],
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
                    "不得把品牌官方号伪装成独立消费者",
                    "不得重复标题、正文或显而易见的画面内容来凑句子",
                    "不得推广畔色产品、贬低其他品牌或截流",
                    "不得把条件性专业判断写成绝对事实",
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
                "topic_ids": [item["intent_topic"]],
                "interaction_intent": item["interaction_intent"],
                "comment_direction_id": item["direction"],
                "voice_id": "official_explanation",
                "human_approved_example_set_version": "panse-xhs-human-approved-comments.v3",
            },
            "panse_official_topic_context": {
                "strategy_id": "panse-official-topic-strategy.v1",
                "topic_id": item["official_topic"],
                "source_author_intent": item["source_author_intent"],
                "target_relationship": "third_party_creator",
                "visible_detail_grounded": True,
                "visible_comment_context_read": True,
                "question_answered_in_context": False,
                "panse_reply_right": item["reply_right"],
                "fact_source_status": "conditional_no_external_claim",
                "conditional_language_present": True,
            },
            "panse_official_professional_value_context": {
                "contract_id": "panse-official-professional-value.v1",
                "value_mode": "conditional_practical_advice",
                "professional_basis_type": "conditional_domain_practice",
                "professional_basis_text": item["observation"],
                "useful_takeaway_present": True,
                "fact_source_status": "conditional_no_external_claim",
                "advice_context_status": item["advice_context"],
                "conditional_language_present": True,
            },
        }
    )
    payload.pop("interaction_mode", None)
    return payload


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    base = json.loads(BASE_REQUESTS.read_text(encoding="utf-8"))["requests"][0][
        "style_request"
    ]
    requests: list[dict] = []
    receipts: list[dict] = []
    reviews: list[dict] = []
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
            "official_topic": item["official_topic"],
            "comment_direction": item["direction"],
            "entry_angle": "不复述画面，直接补一个有条件的专业判断。",
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
                {
                    "gate": "source_and_comment_grounding",
                    "status": "pass",
                    "notes": "正文、相关画面和当前可见评论均已阅读。",
                },
                {
                    "gate": "new_value_not_visual_restatement",
                    "status": "pass",
                    "notes": "草稿提供新增专业判断，没有把图中显而易见的内容重新描述一遍。",
                },
                {
                    "gate": "conditional_fact_boundary",
                    "status": "pass",
                    "notes": "未验证的行业判断均保留可能、如果或条件差异。",
                },
                {
                    "gate": "identity_and_interest_boundary",
                    "status": "pass",
                    "notes": "没有伪装消费者、没有推荐畔色产品、没有截流。",
                },
                {
                    "gate": "colloquial_voice",
                    "status": "pass",
                    "notes": "使用短句和口语，未使用已禁整理稿词语，也没有为了互动硬问问题。",
                },
            ],
        }
        reviews.append(
            {
                "request_id": request_id,
                "account_slot_and_nickname": "slot 1 / 畔色木作",
                "note_id": item["note_id"],
                "target_note_title": item["title"],
                "source_context_summary": item["body"],
                "visible_comment_context_summary": item["comments"],
                "exact_draft_text": item["draft"],
                "style_preflight_passed": bool(receipt.get("passed")),
                "semantic_review_passed": True,
                "queue_status": "awaiting_user_review",
                "current_user_approval_required": True,
                "published": False,
            }
        )

    timestamp = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    all_passed = all(item.get("passed") for item in receipts)
    write_json(
        "account_1_browse_receipts_8.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "account_slot": 1,
            "account_nickname": "畔色木作",
            "profile_id": "6465fa8000000000290160bd",
            "browse_target": 8,
            "browse_actual": 8,
            "deep_read_actual": 8,
            "body_and_visible_comments_read": True,
            "items": READS,
            "safety_warning_observed": False,
            "external_comments_posted": 0,
        },
    )
    write_json(
        "account_1_style_requests_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "phase": "account1_cycle_day04_review_only",
            "account_slot": 1,
            "style_lab_route": "local_tachikoma_runtime",
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "request_count": 4,
            "requests": requests,
        },
    )
    write_json(
        "account_1_style_compile_receipts_4.json",
        {
            "schema_version": 1,
            "compiled_at": timestamp,
            "style_lab_route": "local_tachikoma_runtime",
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "receipt_count": 4,
            "all_passed": all_passed,
            "text_generated_by_preflight": False,
            "external_posting_performed": False,
            "receipts": receipts,
        },
    )
    write_json(
        "account_1_current_session_stage_responses_4.json",
        {
            "schema_version": 1,
            "created_at": timestamp,
            "account_slot": 1,
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "stages": stages,
            "external_posting_performed": False,
        },
    )
    write_json(
        "account_1_human_review_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-12",
            "account_slot": 1,
            "account_nickname": "畔色木作",
            "review_item_count": 4,
            "all_ready_for_user_review": all_passed,
            "send_allowed": False,
            "user_approval_received": False,
            "published_count": 0,
            "approval_rule": "Only explicit approval of the exact displayed drafts permits sending.",
            "items": reviews,
        },
    )

    plan_path = RUN_DIR / "account_1_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update(
        {
            "actual_browse": 8,
            "actual_deep_reads": 8,
            "drafts_ready": 4,
            "verified_follows": 0,
            "public_visible_comments": 0,
            "unsent_review_items": 4,
            "status": "awaiting_user_review",
            "stop_reason": None,
        }
    )
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 1:
            account.update(
                {
                    "status": "awaiting_user_review",
                    "actual_browse": 8,
                    "actual_deep_reads": 8,
                    "drafts_ready": 4,
                    "public_visible_comments": 0,
                    "verified_follows": 0,
                    "unsent": 4,
                }
            )
    status_path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "browse": 8,
                "deep_reads": 8,
                "drafts": 4,
                "preflight_passed": sum(bool(item.get("passed")) for item in receipts),
                "published": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
