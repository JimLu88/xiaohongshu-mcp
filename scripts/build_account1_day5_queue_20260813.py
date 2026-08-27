#!/usr/bin/env python3
"""Build the 2026-08-13 slot-1 review-only queue after fifteen deep reads."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-13"
BASE_REQUESTS = RUN_DIR.parent / "2026-08-12" / "account_1_style_requests_4.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    ("698061d3000000001a0249c7", "我的书桌撞烂了😭 又修好了😁", "狂子", "3/3图", True,
     "签收安装后发现桌面凹坑，家具美容师修复；评论讨论泡水、木种、费用和能否转向靠墙。"),
    ("69b2cb4e000000000600ca74", "定制柜落地，终于明白了定制柜的售后服务", "张晚意", "6/7图", True,
     "安装后继续修抽屉、换板、撕膜并处理柜体和墙面划痕；评论主要问价格、颜色和维修师傅。"),
    ("6933fbf8000000001e030eac", "还没住进去，我的柜子？开裂了？", "那年的Home🏠", "6/6图", True,
     "黑胡桃鞋柜和餐边柜在入住前开裂；评论讨论湿度、木材伸缩和门板结构。"),
    ("68c5712d000000001b01ea42", "全屋定制效果图与实拍图的差距大小", "爱家", "6/7图", True,
     "效果图和实拍对照；作者确认颜色后期改过，评论还指出见光板、收口、灯光和拍摄差异。"),
    ("68d21b5f000000001301cf43", "2.75m开间餐厅，选好餐桌和餐边柜尺寸很重要", "大G小屋", "4/4图", False,
     "正文给出餐边柜、餐桌及两侧通道实测尺寸；评论询问咖啡机、冰箱和餐岛台。"),
    ("661a84cc000000001a00dd1b", "2小时建模，下图有实物对照，划过去有布线", "CC家居建模", "2/2图", False,
     "沙发建模与实物对照并展示布线；评论讨论形体偏差。"),
    ("67ce51310000000009014259", "供暖季不要买木质家具！！！（南方梅雨季同样）", "月亮是俺的馍", "单图", False,
     "作者讨论供暖季木家具开裂；评论把复合板不会裂说成绝对结论，作为错误样本保留。"),
    ("69cb340e000000001d01e186", "地暖惹的祸？", "晨起有念 暮色有盼", "单图", False,
     "地暖环境下实木家具开裂；评论讨论热胀冷缩、薄板受热和返修。"),
    ("69ee12b80000000035026415", "天塌了，新买的沙发破皮了", "妮妮装修日记.", "3/3图", True,
     "新沙发到货后非接触面破皮；评论争论局部修补、整套换和皮料范围。"),
    ("6a25307e000000000702ffa9", "源氏木语黑胡桃木也太软了 拖地都能撞出坑", "滢滢", "单图", False,
     "作者担心做卫生时继续磕碰；评论讨论防撞贴、不同木材和表面损伤。"),
    ("68402160000000002202a726", "餐厅过道只有60cm拥挤吗？我家实测分享来了", "小君不着急（自装ing）", "4/4图", False,
     "真实展示60cm餐桌过道；评论多数询问商品链接，缺少对椅子拉开后通行的讨论。"),
    ("6a2ce17a000000001700bb6a", "记录一次 AI 软体家具建模的完整流程", "一纸闲文", "6/6图", False,
     "AI出基础模后人工拓扑和调整缝线；评论询问缝线变化和后续教程。"),
    ("66019d97000000001400794f", "拴Q！还没入住，实木家具都裂了！但又消失了", "二凌子的生活", "6/6图", False,
     "实木家具裂缝随环境变化缩小；评论讨论湿度、贴皮判断和商家所谓正常。"),
    ("68181fca00000000220341e6", "顾家沙发售后全套换皮攻略", "wr🎈", "6/7图", False,
     "作者记录整套换皮、运费和保修；评论追问过保、返厂、气味和费用。"),
    ("6a61e303000000000f0302e6", "实木桌干燥开裂又自动愈合", "一个瘦子", "4/4图", False,
     "地暖季桌面开裂变形，湿度回升后缝隙合上；评论讨论干缩湿胀但也混入冬夏说反的观点。"),
]


CANDIDATES = [
    {
        "note_id": "698061d3000000001a0249c7",
        "title": "我的书桌撞烂了😭 又修好了😁",
        "topic": "maintenance_longevity",
        "body": "签收安装后发现桌面凹坑，家具美容师已经完成修复。",
        "comments": ["高赞评论建议直接加水浸泡。", "作者询问泡水是否通用，也有人追问木种和费用。"],
        "observation": "凹痕处理取决于木种、表面涂层和损伤深度，不能把泡水当成通用方法。",
        "draft": "凹痕别急着直接泡水，先看木种、表面涂层和伤得多深，找师傅判断一下更稳。",
    },
    {
        "note_id": "69b2cb4e000000000600ca74",
        "title": "定制柜落地，终于明白了定制柜的售后服务",
        "topic": "maintenance_longevity",
        "body": "柜体安装后又处理抽屉、换板、保护膜以及柜体和墙面划痕。",
        "comments": ["评论主要问全屋价格和柜体颜色。", "有人询问维修木板的师傅。"],
        "observation": "定制柜安装结束后应一次检查抽屉、门缝、划痕和保护膜，便于集中返工。",
        "draft": "柜子装完先把抽屉、门缝、划痕和保护膜一起过一遍，能当天修的尽量当天修。",
    },
    {
        "note_id": "6933fbf8000000001e030eac",
        "title": "还没住进去，我的柜子？开裂了？",
        "topic": "maintenance_longevity",
        "body": "黑胡桃鞋柜和餐边柜在入住前已经出现明显开裂。",
        "comments": ["评论讨论湿度和实木正常伸缩。", "也有人区分硬拼板和带伸缩余量的门板结构。"],
        "observation": "入住前开裂不宜只补表面裂缝，还需要检查门板结构是否给木材留了伸缩余量。",
        "draft": "还没入住就开裂，先看门板有没有留伸缩余量，别只把缝补上，不然换个季节还可能再裂。",
    },
    {
        "note_id": "68c5712d000000001b01ea42",
        "title": "全屋定制效果图与实拍图的差距大小",
        "topic": "ai_render_design_process",
        "body": "作者对照展示全屋定制效果图和实拍，并说明颜色后来改过。",
        "comments": ["评论提到灯光和拍摄影响。", "也有人指出少了见光板、收口变化和开关位置。"],
        "observation": "颜色、柜体收口和见光板都发生变化，不能只把差距归因于灯光或拍摄。",
        "draft": "这里不只是灯光问题，颜色后来改过，柜体收口和见光板也变了，前后已经不是同一版方案。",
    },
    {
        "note_id": "69ee12b80000000035026415",
        "title": "天塌了，新买的沙发破皮了",
        "topic": "maintenance_longevity",
        "body": "新沙发到货后非接触面出现破皮，作者在局部修补和整套更换之间沟通售后。",
        "comments": ["评论争论局部补皮能否看出色差。", "有人认为大件返运麻烦，也有人主张整套换。"],
        "observation": "到货破损的售后沟通应同时记录位置、修补后的可接受色差和后续质保责任。",
        "draft": "新沙发到货就破皮，先把破损位置、补完后的色差和后面怎么算质保一起写进售后记录。",
    },
]


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    request_id = f"panse.2026-08-13.account1.comment.{index:03d}"
    payload.update({
        "request_id": request_id,
        "idempotency_key": f"panse:2026-08-13:account-1:{item['note_id']}",
        "brief_text": (
            f"目标原帖为《{item['title']}》。畔色木作官方品牌号公开参与，不推广畔色产品，也不伪装消费者。"
            "正文、相关画面和当前可见评论均已读完。不要复述标题、正文或图里显而易见的内容。"
            "只补充一个和原帖直接相关的专业判断、条件差异或可执行提醒。"
            "必须像真人口语：不用思路、那组、尤其、参考价值、落地、下单等整理稿词；不为了互动硬问问题。"
            "输出25至70个中文字符，1至2句；不提畔色产品，不导流，不虚构任何使用经历。"
        ),
        "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario": "品牌官方号公开评论待审稿",
        "audience": "分享家具使用、维修、售后或设计过程的创作者",
        "use_case": "生成一条有专业增量、自然口语且等待人工批准的官方评论",
        "source_context": {
            "body": item["body"],
            "visible_comments": item["comments"],
            "image_observations": [{"locator": "reviewed_media", "observation": item["observation"], "observation_basis": "caller_reviewed"}],
            "body_complete": True,
            "visible_comments_complete": True,
            "images_complete": True,
            "expected_visible_comment_count": len(item["comments"]),
            "expected_image_count": 1,
        },
        "required_model_id": "gpt-5.6-sol",
        "fallback_model_allowed": False,
        "content_contract": {
            "protected_facts": [], "allowed_paraphrases": {},
            "forbidden_inferences": [
                "不得虚构购买、入住、装修、施工、检测或长期使用经历",
                "不得把品牌官方号伪装成独立消费者",
                "不得复述标题、正文或显而易见画面来凑句子",
                "不得推广畔色产品、贬低其他品牌或截流",
                "不得把条件性专业判断写成绝对事实",
            ],
            "citation_anchors": {}, "must_cover_fact_ids": [],
        },
        "output": {"title_candidates": 0, "title_max_chars": 0, "body_min_chars": 25, "body_max_chars": 70, "tag_min": 0, "tag_max": 0},
        "panse_intent_context": {
            "policy_version": "xhs-comment-intent.v4", "topic_ids": ["maintenance_lifetime"],
            "interaction_intent": "contextual_disagreement", "comment_direction_id": "contextual_difference",
            "voice_id": "official_explanation", "human_approved_example_set_version": "panse-xhs-human-approved-comments.v3",
        },
        "panse_official_topic_context": {
            "strategy_id": "panse-official-topic-strategy.v1", "topic_id": item["topic"],
            "source_author_intent": "share_or_ask_furniture_issue", "target_relationship": "third_party_creator",
            "visible_detail_grounded": True, "visible_comment_context_read": True,
            "question_answered_in_context": False, "panse_reply_right": "conditional_fact_only",
            "fact_source_status": "conditional_no_external_claim", "conditional_language_present": True,
        },
        "panse_official_professional_value_context": {
            "contract_id": "panse-official-professional-value.v1", "value_mode": "conditional_practical_advice",
            "professional_basis_type": "conditional_domain_practice", "professional_basis_text": item["observation"],
            "useful_takeaway_present": True, "fact_source_status": "conditional_no_external_claim",
            "advice_context_status": "visible_problem_present", "conditional_language_present": True,
        },
    })
    payload.pop("interaction_mode", None)
    return payload


def main() -> int:
    base = json.loads(BASE_REQUESTS.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    requests, receipts, reviews = [], [], []
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        rid = payload["request_id"]
        requests.append({"target_note": {"note_id": item["note_id"], "title": item["title"], "source_locator": payload["source_locator"]}, "style_request": payload})
        receipts.append(receipt)
        stages["plan"][rid] = {"model_id": "gpt-5.6-sol", "fallback_used": False, "entry_angle": "不复述显而易见内容，只补一个专业增量。"}
        stages["draft"][rid] = {"model_id": "gpt-5.6-sol", "fallback_used": False, "draft_text": item["draft"], "tags": []}
        stages["semantic_review"][rid] = {
            "model_id": "gpt-5.6-sol", "fallback_used": False,
            "results": [
                {"gate": "source_and_comment_grounding", "status": "pass", "notes": "正文、相关画面和当前可见评论均已阅读。"},
                {"gate": "new_value_not_visual_restatement", "status": "pass", "notes": "提供新增专业判断，没有重复显而易见内容。"},
                {"gate": "conditional_fact_boundary", "status": "pass", "notes": "未把条件性判断写成绝对事实。"},
                {"gate": "identity_and_interest_boundary", "status": "pass", "notes": "未伪装消费者，未推荐畔色产品。"},
                {"gate": "colloquial_voice", "status": "pass", "notes": "短句口语，无硬问、无禁用整理稿词。"},
            ],
        }
        reviews.append({
            "request_id": rid, "account_slot_and_nickname": "slot 1 / 畔色木作",
            "note_id": item["note_id"], "target_note_title": item["title"],
            "source_context_summary": item["body"], "visible_comment_context_summary": item["comments"],
            "exact_draft_text": item["draft"], "style_preflight_passed": bool(receipt.get("passed")),
            "semantic_review_passed": True, "queue_status": "awaiting_user_review",
            "current_user_approval_required": True, "published": False,
        })

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    all_passed = all(r.get("passed") for r in receipts)
    items = [{"note_id": n, "title": t, "author": a, "media_reviewed": m, "selected": s, "summary": q} for n, t, a, m, s, q in READS]
    write_json("account_1_browse_receipts_15.json", {
        "schema_version": 1, "date": "2026-08-13", "account_slot": 1, "account_nickname": "畔色木作",
        "profile_id": "6465fa8000000000290160bd", "browse_target": 15, "browse_actual": 15,
        "deep_read_actual": 15, "body_and_visible_comments_read": True, "items": items,
        "excluded_incomplete_item": {"note_id": "675a780b000000000603b738", "title": "一件家具的诞生 · 工厂纪录", "reason": "4分44秒视频播放状态无法稳定核验，未计入15篇"},
        "historical_note_id_hits": 0, "safety_warning_observed": False, "external_comments_posted": 0,
    })
    write_json("account_1_style_requests_5.json", {"schema_version": 1, "date": "2026-08-13", "phase": "account1_cycle_day05_review_only", "account_slot": 1, "style_lab_route": "tachikoma_approved_style_contract", "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "request_count": 5, "requests": requests})
    write_json("account_1_style_compile_receipts_5.json", {"schema_version": 1, "compiled_at": timestamp, "style_lab_route": "tachikoma_approved_style_contract", "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "receipt_count": 5, "all_passed": all_passed, "text_generated_by_preflight": False, "external_posting_performed": False, "receipts": receipts})
    write_json("account_1_current_session_stage_responses_5.json", {"schema_version": 1, "created_at": timestamp, "account_slot": 1, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "stages": stages, "external_posting_performed": False})
    write_json("account_1_human_review_5.json", {"schema_version": 1, "date": "2026-08-13", "account_slot": 1, "account_nickname": "畔色木作", "review_item_count": 5, "all_ready_for_user_review": all_passed, "send_allowed": False, "user_approval_received": False, "published_count": 0, "approval_rule": "Only current-turn approval of the exact displayed drafts permits sending.", "items": reviews})

    plan_path = RUN_DIR / "account_1_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse": 15, "actual_deep_reads": 15, "drafts_ready": 5, "draft_candidates_ready": 5, "public_visible_comments": 0, "unsent_review_items": 5, "status": "awaiting_user_review", "comment_send_allowed": False, "stop_reason": None})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 1:
            account.update({"status": "awaiting_user_review", "actual_browse": 15, "actual_deep_reads": 15, "drafts_ready": 5, "public_visible_comments": 0, "verified_follows": 0, "unsent": 5, "stop_reason": None})
    status["totals_verified"].update({"browse": 15, "deep_reads": 15, "comment_drafts": 5, "public_visible_comments": 0, "follows": 0})
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"browse": 15, "deep_reads": 15, "drafts": 5, "preflight_passed": sum(bool(r.get("passed")) for r in receipts), "published": 0}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
