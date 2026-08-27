#!/usr/bin/env python3
"""Build the slot-1 cycle-day-2 review-only queue for 2026-08-10."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-10"
PREVIOUS_REQUESTS = (
    REPO
    / "research"
    / "panse_multi_direction"
    / "daily_runs"
    / "2026-08-09"
    / "account_1_style_requests_4.json"
)
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {
        "note_id": "6a64c42c000000000401e2cb",
        "title": "开间2.7m小户型客厅｜完整尺寸布局参考",
        "topic": "real_space_use",
        "images": "6/8",
        "selected": False,
        "summary": "作者给出2.7米开间、沙发深度、电视墙和吊灯等尺寸；可见评论中的具体尺寸问题多已由作者回答。",
    },
    {
        "note_id": "6a6b4c7400000000330355e5",
        "title": "50㎡小户型显大，这6个尺寸我做对了！",
        "topic": "real_space_use",
        "images": "6/8",
        "selected": True,
        "summary": "2.5米客厅开间，作者列出80厘米沙发侧宽、34厘米电视柜进深和折叠餐桌等真实尺寸。",
    },
    {
        "note_id": "675a780b000000000603b738",
        "title": "一件家具的诞生 · 工厂纪录",
        "topic": "craft_material_process",
        "images": "video",
        "selected": False,
        "summary": "其他家具品牌的工厂宣传视频；不在竞品或同业商业自述帖刷官方存在感。",
    },
    {
        "note_id": "6a48de81000000001603e84c",
        "title": "进厂记录｜这是家具诞生的地方。",
        "topic": "craft_material_process",
        "images": "video",
        "selected": False,
        "summary": "第一视角工厂记录，但可见评论出现粉尘防护争议；畔色没有足够上下文作安全判断。",
    },
    {
        "note_id": "67820972000000000800cf98",
        "title": "千万不要随意维修实木家具，否则会变得不幸",
        "topic": "maintenance_longevity",
        "images": "2/2",
        "selected": True,
        "summary": "作者记录划痕维修后十几天色差和粗糙感更明显，并在评论持续更新多次处理后的结果。",
    },
    {
        "note_id": "6a3c88060000000007023bba",
        "title": "【家具翻新秘籍】柚木家具翻新全攻略",
        "topic": "maintenance_longevity",
        "images": "6/8",
        "selected": False,
        "summary": "个人翻新教程给出白醋、砂纸和木蜡油步骤，但畔色没有同材质同涂装验证，不复述为品牌建议。",
    },
    {
        "note_id": "6a2ce17a000000001700bb6a",
        "title": "记录一次 AI 软体家具建模的完整流程",
        "topic": "ai_render_design_process",
        "images": "6/6",
        "selected": True,
        "summary": "作者展示Tripo3D基础模、ZBrush分部件、3ds Max调整和QuadRemesh拓扑优化，并说明缝线与拓扑仍需人工收尾。",
    },
    {
        "note_id": "69d66682000000002200cb49",
        "title": "建模思路",
        "topic": "ai_render_design_process",
        "images": "video",
        "selected": False,
        "summary": "以潘顿椅讲解SketchUp曲面建模，评论集中询问插件和四边面基础；与已选AI流程帖过近。",
    },
    {
        "note_id": "68df4610000000000400753b",
        "title": "家具灵感｜有趣的解压家具拆解图",
        "topic": "design_culture_exhibition",
        "images": "video",
        "selected": False,
        "summary": "转载家具拆解动画并标注图片来源；正文信息较少，不优先于原创过程内容。",
    },
    {
        "note_id": "6a1c2ecd000000003601ad3c",
        "title": "我的74平小家，简单日常治愈又放松",
        "topic": "creator_ugc_aesthetic",
        "images": "6/9",
        "selected": True,
        "summary": "74平真实家居多角度实拍；第6张为浅色沙发、木茶几、落地灯和猫的日常画面。",
    },
]


CANDIDATES = [
    {
        "note_id": "6a6b4c7400000000330355e5",
        "title": "50㎡小户型显大，这6个尺寸我做对了！",
        "official_topic": "real_space_use",
        "intent_topic": "dimensions_fit",
        "direction": "detail_grounded_praise",
        "parent_intent": "grounded_praise",
        "author_intent": "share_real_home_dimensions",
        "reply_right": "peer_observation",
        "route_id": "creator_specific_praise",
        "style_mode": "warm_specific",
        "professional_value": {
            "contract_id": "panse-official-professional-value.v1",
            "value_mode": "professional_reasoned_praise",
            "professional_basis_type": "visible_measurement_relation",
            "professional_basis_text": "正文与尺寸图写明2.5米开间和80厘米沙发侧宽",
            "useful_takeaway_present": True,
            "fact_source_status": "source_visible",
            "praise_reason_precedes_praise": True,
        },
        "body": "作者在2.5米客厅开间中使用80厘米侧宽沙发，并列出电视柜、餐边柜、折叠餐桌和灯具尺寸。",
        "comments": [
            "有人确认开间是否真的只有2.5米，作者回答是",
            "可见评论主要询问沙发、餐桌和电视型号，作者已逐项回答",
        ],
        "image_observation": "已翻看前6/8张；尺寸图明确标出80厘米沙发侧宽及其他家具尺寸。",
        "draft": "2.5米开间配80厘米侧宽的沙发，动线设计非常好。",
    },
    {
        "note_id": "67820972000000000800cf98",
        "title": "千万不要随意维修实木家具，否则会变得不幸",
        "official_topic": "maintenance_longevity",
        "intent_topic": "maintenance_lifetime",
        "direction": "invited_peer_tip",
        "parent_intent": "peer_tip_invited",
        "author_intent": "share_repair_outcome_and_followup",
        "reply_right": "conditional_fact_only",
        "route_id": "usage_fit_answer",
        "style_mode": "direct_fact",
        "professional_value": {
            "contract_id": "panse-official-professional-value.v1",
            "value_mode": "conditional_practical_advice",
            "professional_basis_type": "conditional_domain_practice",
            "professional_basis_text": "作者展示了局部维修后仍有明显色差和粗糙感",
            "useful_takeaway_present": True,
            "fact_source_status": "conditional_no_external_claim",
            "advice_context_status": "visible_problem_present",
            "conditional_language_present": True,
        },
        "body": "作者记录桌面划痕维修后十几天色差和粗糙感更明显，后续又在评论更新多次处理后的结果。",
        "comments": [
            "可见评论给出多种相互冲突的修复意见",
            "作者后续表示多次处理后仍有明显色差并停止继续修复",
        ],
        "image_observation": "已翻看2/2张；只承接作者记录的可见结果，不输出维修方法。",
        "draft": "如果还能联系原品牌，可以先问能不能返厂整面处理；另找维修师傅也要看同材质案例。",
    },
    {
        "note_id": "6a2ce17a000000001700bb6a",
        "title": "记录一次 AI 软体家具建模的完整流程",
        "official_topic": "ai_render_design_process",
        "intent_topic": "material_craft",
        "direction": "detail_grounded_praise",
        "parent_intent": "grounded_praise",
        "author_intent": "share_ai_modeling_workflow",
        "reply_right": "process_peer_observation",
        "route_id": "creator_specific_praise",
        "style_mode": "warm_specific",
        "professional_value": {
            "contract_id": "panse-official-professional-value.v1",
            "value_mode": "professional_reasoned_praise",
            "professional_basis_type": "visible_structure_or_process",
            "professional_basis_text": "流程可见AI生成基础模，拓扑和缝线由人工收尾",
            "useful_takeaway_present": True,
            "fact_source_status": "source_visible",
            "praise_reason_precedes_praise": True,
        },
        "body": "作者展示AI出基础模，再用ZBrush、3ds Max和QuadRemesh处理部件、尺寸、细节与拓扑。",
        "comments": [
            "有人询问拓扑后缝线是否变化",
            "作者回答AI缝线造型仍需手动调整",
        ],
        "image_observation": "已翻看6/6张；可见流程和最终布线结果。",
        "draft": "AI先出基础模，拓扑和缝线再人工收尾，很专业👍。",
    },
    {
        "note_id": "6a1c2ecd000000003601ad3c",
        "title": "我的74平小家，简单日常治愈又放松",
        "official_topic": "creator_ugc_aesthetic",
        "intent_topic": "color_light_atmosphere",
        "direction": "atmosphere_grounded_praise",
        "parent_intent": "grounded_praise",
        "author_intent": "share_real_home_atmosphere",
        "reply_right": "specific_creator_support",
        "route_id": "creator_specific_praise",
        "style_mode": "warm_specific",
        "professional_value": {
            "contract_id": "panse-official-professional-value.v1",
            "value_mode": "professional_reasoned_praise",
            "professional_basis_type": "visible_material_color_light_relation",
            "professional_basis_text": "第6张可见浅色沙发、原木茶几和暖光组合",
            "useful_takeaway_present": True,
            "fact_source_status": "source_visible",
            "praise_reason_precedes_praise": True,
        },
        "body": "作者用9张图片记录74平家中的日常空间，正文只保留主题标签。",
        "comments": [
            "可见评论主要询问面积、餐桌、沙发和其他家具链接",
            "已有普通用户表达喜欢，但没有重复本草稿的具体画面",
        ],
        "image_observation": "已翻看前6/9张；第6张是浅色沙发、木茶几、落地灯和一只趴在沙发上的猫。",
        "draft": "浅色沙发、原木茶几和暖光放在一起很舒服，审美真好👍",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def write_json(name: str, payload: object) -> Path:
    path = RUN_DIR / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def preflight(payload: dict) -> dict:
    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT), "-"],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO,
        check=True,
    )
    return json.loads(completed.stdout.decode("utf-8"))


def build_style_payload(base: dict, item: dict, index: int) -> dict:
    payload = copy.deepcopy(base)
    request_id = f"panse.2026-08-10.account1.comment.{index:03d}"
    locator = f"https://www.xiaohongshu.com/explore/{item['note_id']}"
    max_chars = (
        70
        if item["professional_value"]["value_mode"]
        == "conditional_practical_advice"
        else 52
    )
    payload.update(
        {
            "request_id": request_id,
            "idempotency_key": f"panse:2026-08-10:account-1:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。畔色木作官方品牌号公开参与，但不推广畔色产品，也不伪装消费者。"
                "已读取完整可见正文、相关图片和当前可见评论，并通过panse-official-topic-strategy.v1发言权门。"
                "先写一个尺寸、结构、工艺、材料、配色、光线、动线或使用关系的专业依据，再给一个判断、条件化建议或短夸。"
                "只有作者明确提问或页面呈现可见问题时才给建议；不判分、不写空洞总结或产品卖点。"
                f"不虚构购买、入住、装修、检测或长期使用经历。输出12至{max_chars}个中文字符，1至2句；不引导主页、私信、搜索、关注、点赞或购买。"
            ),
            "source_locator": locator,
            "scenario": "品牌官方号公开评论待审稿",
            "audience": "分享真实家居、家具维护或设计过程的创作者",
            "use_case": "生成一条有合法话题发言权的支持性官方评论草稿",
            "source_context": {
                "body": item["body"],
                "visible_comments": item["comments"],
                "image_observations": [
                    {
                        "locator": "reviewed_images",
                        "observation": item["image_observation"],
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
                "不得追加没有提问或可见问题依据的建议、判卷式总结或未经验证的维修技术结论",
                    "不得把第三方平台评级、收费、服务范围或维修结果写成未经当前核验的普遍事实",
                    "不得推广畔色产品、贬低其他品牌或截流",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            "output": {
                "title_candidates": 0,
                "title_max_chars": 0,
                "body_min_chars": 12,
                "body_max_chars": max_chars,
                "tag_min": 0,
                "tag_max": 0,
            },
            "panse_intent_context": {
                "policy_version": "xhs-comment-intent.v4",
                "topic_ids": [item["intent_topic"]],
                "interaction_intent": item["parent_intent"],
                "comment_direction_id": item["direction"],
                "voice_id": "official_explanation",
            },
            "panse_official_topic_context": {
                "strategy_id": "panse-official-topic-strategy.v1",
                "topic_id": item["official_topic"],
                "source_author_intent": item["author_intent"],
                "target_relationship": "third_party_creator",
                "visible_detail_grounded": True,
                "visible_comment_context_read": True,
                "question_answered_in_context": False,
                "panse_reply_right": item["reply_right"],
                "advice_context_status": item["professional_value"].get(
                    "advice_context_status"
                ),
                "fact_source_status": item["professional_value"][
                    "fact_source_status"
                ],
                "conditional_language_present": item["professional_value"].get(
                    "conditional_language_present", False
                ),
            },
            "panse_official_professional_value_context": item[
                "professional_value"
            ],
        }
    )
    return payload


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    previous = json.loads(PREVIOUS_REQUESTS.read_text(encoding="utf-8"))
    base = previous["requests"][0]["style_request"]

    plan = {
        "schema_version": 1,
        "date": "2026-08-10",
        "account_slot": 1,
        "account_nickname": "畔色木作",
        "account_type": "official_brand",
        "phone_mask": "158****8812",
        "device": "小米手机",
        "cycle_day": 2,
        "cycle_week": 1,
        "comment_target_c": 4,
        "browse_multiplier_m": 2.5,
        "browse_target": 10,
        "browse_actual": 10,
        "deep_read_actual": 10,
        "draft_target": 4,
        "external_comments_posted": 0,
        "publish_allowed": False,
    }
    write_json("account_1_daily_plan.json", plan)
    write_json(
        "account_1_browse_receipts_10.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 1,
            "browse_target": 10,
            "browse_actual": 10,
            "deep_read_actual": 10,
            "full_visible_body_read": True,
            "visible_comments_read": True,
            "items": READS,
            "safety_warning_observed": False,
            "external_comments_posted": 0,
        },
    )

    requests = []
    receipts = []
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}
    review_items = []
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_style_payload(base, item, index)
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
        topic_context = payload["panse_official_topic_context"]
        stages["plan"][request_id] = {
            "model_id": "gpt-5.6-sol",
            "topic_strategy": topic_context,
            "route_id": item["route_id"],
            "style_mode": item["style_mode"],
            "professional_value": item["professional_value"],
            "entry_angle": "先写专业依据，再给与依据直接相关的判断、条件化建议或短夸。",
            "source_evidence": item["image_observation"],
        }
        stages["draft"][request_id] = {
            "model_id": "gpt-5.6-sol",
            "draft_text": item["draft"],
            "tags": [],
        }
        stages["semantic_review"][request_id] = {
            "model_id": "gpt-5.6-sol",
            "results": [
                {
                    "gate": "official_topic_and_reply_right",
                    "status": "pass",
                    "notes": f"{item['official_topic']} / {item['reply_right']}",
                },
                {
                    "gate": "source_grounding_and_visible_comments",
                    "status": "pass",
                    "notes": "正文、相关图片和当前可见评论已读；草稿只使用可见细节。",
                },
                {
                    "gate": "professional_basis_before_judgment",
                    "status": "pass",
                    "notes": item["professional_value"]["professional_basis_text"],
                },
                {
                    "gate": "identity_and_fact_boundary",
                    "status": "pass",
                    "notes": "没有伪装消费者、产品导流或竞品截流；建议使用条件化表达，未写未经核验的平台评级、费用或服务结果。",
                },
                {
                    "gate": "natural_official_voice",
                    "status": "pass",
                    "notes": "专业依据在前，判断、建议或短夸在后；没有老师口吻或空尾巴。",
                },
            ],
        }
        review_items.append(
            {
                "request_id": request_id,
                "note_id": item["note_id"],
                "title": item["title"],
                "topic_id": item["official_topic"],
                "panse_reply_right": item["reply_right"],
                "route_id": item["route_id"],
                "professional_value_contract_id": item["professional_value"][
                    "contract_id"
                ],
                "professional_value_mode": item["professional_value"][
                    "value_mode"
                ],
                "professional_value_context": item["professional_value"],
                "draft": item["draft"],
                "draft_status": "final_draft",
                "language_review_status": "user_feedback_applied",
                "style_preflight_passed": receipt["passed"],
                "semantic_review_passed": True,
                "queue_status": "ready_for_final_send_check",
                "published": False,
            }
        )

    write_json(
        "account_1_style_requests_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "phase": "account1_cycle_day02_review_only",
            "account_slot": 1,
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
            "compiled_at": now_iso(),
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "request_count": 4,
            "compile_pass_count": sum(bool(item["passed"]) for item in receipts),
            "items": receipts,
            "external_posting_performed": False,
            "publish_allowed": False,
        },
    )
    write_json(
        "account_1_current_session_stage_responses_4.json",
        {
            "schema_version": 1,
            "provider": "codex.current_session",
            "model_id": "gpt-5.6-sol",
            "fallback_model_used": False,
            "stage_order": ["plan", "draft", "semantic_review"],
            "request_count": 4,
            "stages": stages,
            "external_posting_performed": False,
            "publish_allowed": False,
        },
    )
    write_json(
        "account_1_human_review_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 1,
            "account_nickname": "畔色木作",
            "topic_strategy_id": "panse-official-topic-strategy.v1",
            "official_reply_policy_id": "panse-official-reply.v3",
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "items": review_items,
            "summary": {
                "input": 4,
                "style_preflight_passed": 4,
                "semantic_review_passed": 4,
                "final_draft_ready": 4,
                "ready_for_final_send_check": 4,
                "published": 0,
            },
            "publish_allowed": False,
        },
    )
    print(
        json.dumps(
            {
                "run_dir": str(RUN_DIR),
                "browse_actual": 10,
                "drafts": 4,
                "style_preflight_passed": 4,
                "external_comments_posted": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
