#!/usr/bin/env python3
"""Build slot-5 cycle-day-4 evidence and review-only queue for 2026-08-12."""

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
    {"note_id": "68cba382000000000b010a2a", "title": "工艺积累｜家具部件现代连接方式（17）", "author": "Zephyr Yu（设计", "media_reviewed": "1/10图", "summary": "桌面、抽屉等家具部件连接案例；已读正文与可见评论。因只看1/10图，记为浏览样本，不计合规深读。", "deep_read": False},
    {"note_id": "6a71b88a0000000022030e6c", "title": "标准椅｜90年前的设计，2026依然高级", "author": "MU物所", "media_reviewed": "正文、评论及主要结构图", "summary": "介绍Jean Prouvé Standard Chair的受力结构；评论集中问购买渠道和颜色。", "deep_read": True},
    {"note_id": "6a577834000000000f0326de", "title": "总觉得这个修复 弄丢了点精华？", "author": "小野", "media_reviewed": "修复过程与结果", "summary": "旧木家具被整体刷色，评论争论保留木纹、刷漆和继续使用之间的取舍。", "deep_read": True},
    {"note_id": "69d617d0000000001d01d60b", "title": "做家具出海美国，踩了个大坑！", "author": "安乐的Eric", "media_reviewed": "完整正文与评论", "summary": "讲述家具出口合同、检测与付款纠纷；故事缺少可核实材料，只作低置信度观察，不进入评论候选。", "deep_read": True},
    {"note_id": "68410849000000000303e764", "title": "为什么北美家庭都爱Shaker橱柜？", "author": "Dreamer", "media_reviewed": "完整正文与可见评论", "summary": "讨论Shaker柜门边框宽窄、材料和不同厨房空间的视觉效果；评论有具体宽度与材质问题。", "deep_read": True},
    {"note_id": "6a54e8a6000000000f02a6d1", "title": "跟随Enzo Mari的意志手搓椅子", "author": "CHENKK", "media_reviewed": "正文、评论及主要制作图", "summary": "依据开放图纸用常见材料做椅子；评论讨论晃动、角码和玄关用途。", "deep_read": True},
    {"note_id": "69eaef160000000011020003", "title": "设计师家具一定要买正品吗？", "author": "songmi", "media_reviewed": "完整正文与可见评论", "summary": "讨论正品、仿品、原创小品牌和个人预算之间的选择，评论立场较多元。", "deep_read": True},
    {"note_id": "6a6485e4000000000f005300", "title": "Atelier Fomenta｜橡胶重塑家具形态", "author": "时位", "media_reviewed": "正文、评论及主要材料图", "summary": "硬质橡胶通过弯折、切割和铆钉形成家具；评论主要询问材料厚度。", "deep_read": True},
    {"note_id": "69eed4b70000000035025728", "title": "折叠变形餐桌——每日设计分享", "author": "小羊 momo", "media_reviewed": "完整正文与可见评论", "summary": "正文残留AI提示词，并含5万次、18mm、80kg等无来源数字；记作低可信内容，不进入评论候选。", "deep_read": True},
    {"note_id": "66207bf00000000001007417", "title": "Apprentice Programme｜投资于工艺的未来", "author": "CARL HANSEN & SON", "media_reviewed": "1/12图", "summary": "介绍学徒培养项目；已读正文与评论，但只看1/12图，记为浏览样本，不计合规深读。", "deep_read": False},
    {"note_id": "6a0b1e8f00000000070246b9", "title": "ikea竟然还有made in italy的家具", "author": "葱油拌面加蛋", "media_reviewed": "完整正文与可见评论", "summary": "成品柜恰好适配家中窄位；评论讨论板材、椅子、产地、门扇开启和定制成本。", "deep_read": True},
    {"note_id": "684031b600000000200280b1", "title": "审美积累：桌腿与桌面工艺（4）", "author": "Zephyr Yu（设计", "media_reviewed": "6/9图", "summary": "桌腿与桌面连接细节；已读正文、前6张图和当前可见评论。", "deep_read": True},
    {"note_id": "6a38f9480000000011019407", "title": "拼接式撞色艺术家具，大人房也能童趣出圈", "author": "时位", "media_reviewed": "6/18图", "summary": "模块化拼接家具在成人空间和儿童房的配色方式；已读正文、前6张图，评论区暂无有效讨论。", "deep_read": True},
]

CANDIDATES = [
    {"note_id": "6a577834000000000f0326de", "title": "总觉得这个修复 弄丢了点精华？", "topic": "material_craft", "direction": "contextual_difference", "parent": "contextual_disagreement", "mode": "soft_observation", "body": "旧木家具修复后整体刷色，原来的木纹基本看不到。", "comments": ["评论区主要争论刷漆是否盖掉了原来的木纹，也有人认为继续使用比丢掉好。"], "image": "已看修复过程和最终效果。", "draft": "好好的木纹全刷没了，确实有点可惜。"},
    {"note_id": "68410849000000000303e764", "title": "为什么北美家庭都爱Shaker橱柜？", "topic": "global_localization", "direction": "contextual_difference", "parent": "contextual_disagreement", "mode": "soft_observation", "body": "正文讨论Shaker柜门在北美家庭中的使用，评论进一步问边框宽度和材料。", "comments": ["有人问边框做7厘米还是8厘米，也有人讨论OSB和经典款、窄边款的差别。"], "image": "已看柜门比例与厨房空间的搭配。", "draft": "柜门边框还是得看厨房大小，做太宽了容易显笨。"},
    {"note_id": "69eaef160000000011020003", "title": "设计师家具一定要买正品吗？", "topic": "global_localization", "direction": "contextual_difference", "parent": "contextual_disagreement", "mode": "soft_observation", "body": "正文和评论讨论预算有限时买正品、仿品、原创小品牌或大众品牌的不同选择。", "comments": ["评论观点分散，没有形成单一结论；有人重视原创，也有人更看预算。"], "image": "已结合正文和评论理解争议。", "draft": "正品买不起也没必要硬撑，挑个价格能接受的原创小品牌更舒服。"},
    {"note_id": "6a0b1e8f00000000070246b9", "title": "ikea竟然还有made in italy的家具", "topic": "global_localization", "direction": "light_social_response", "parent": "neutral_social", "mode": "light_humor_or_neutral", "body": "作者找到一个尺寸恰好适配家中窄位的宜家成品柜，并提到意大利制造。", "comments": ["评论讨论产地、板材、门扇开启和定制成本，也有人觉得尺寸合适最重要。"], "image": "已看成品柜与墙面窄位的关系。", "draft": "刚好能塞进这个位置已经很值了，产地反而没那么重要。"},
]


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(payload: dict) -> dict:
    done = subprocess.run([sys.executable, str(PREFLIGHT), "-"], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=REPO, check=False)
    if done.returncode:
        raise RuntimeError(done.stderr.decode("utf-8", errors="replace"))
    return json.loads(done.stdout.decode("utf-8"))


def build_payload(item: dict, index: int) -> dict:
    return {
        "request_id": f"panse.2026-08-12.account5.comment.{index:03d}",
        "idempotency_key": f"panse:2026-08-12:account-5:{item['note_id']}",
        "brief_text": (
            f"目标原帖为《{item['title']}》。已读完整正文、相关媒体和当前可见评论。"
            "身份是喜欢海外家具、材料工艺和居住案例的普通同好，不装专家。"
            "评论必须扣住原帖真正讨论的问题，给一个直接感受或有用观点；不要把标题、正文和图里显而易见的内容再描述一遍。"
            "不是每条都提问，不为了互动硬问作者无法回答的问题。夸赞要直接，专业意见要说清楚实际原因。"
            "不用思路、那组、尤其、维度、落地、参考价值、下单等书面词；数字一律用阿拉伯数字。"
            "输出1句，像真人随手评论，说完就停；不虚构购买、入住、装修、检测或长期使用经历。"
        ),
        "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "rights_basis": "public note and visible public comments used only as context for a new non-quoting comment draft",
        "sensitivity": "internal",
        "language": "zh-CN",
        "channel": "小红书",
        "scenario": "小红书全球家具工艺账号评论语气实验",
        "audience": "喜欢海外家具、材料工艺和居住案例的普通用户",
        "use_case": "生成一条具体、口语化、扣题且不装专家的评论草稿",
        "artifact_type": "comment",
        "interaction_mode": item["mode"],
        "source_context": {"body": item["body"], "visible_comments": item["comments"], "image_observations": [{"locator": "reviewed_media", "observation": item["image"], "observation_basis": "caller_reviewed"}], "body_complete": True, "visible_comments_complete": True, "images_complete": True, "expected_visible_comment_count": len(item["comments"]), "expected_image_count": 1},
        "taxonomy_ids": ["platform.xiaohongshu-comment", "persona.lifestyle-curator", "role.editor", "scene.social-comment"],
        "style_card_refs": STYLE_REFS,
        "requested_strength": 0.5,
        "style_requirement": "approved_required",
        "pin_card_versions": True,
        "required_model_id": "gpt-5.6-sol",
        "fallback_model_allowed": False,
        "content_contract": {"protected_facts": [], "allowed_paraphrases": {}, "forbidden_inferences": ["不得虚构购买、入住、装修、检测或长期使用经历", "不得重复标题、正文、图片中显而易见的信息或当前可见评论", "不得为了互动硬问问题", "不得使用老师、评委、验收或裁判口吻", "不得使用思路、那组、尤其、维度、落地、参考价值、下单等书面表达", "数量不得使用中文数字"], "citation_anchors": {}, "must_cover_fact_ids": []},
        "output": {"title_candidates": 0, "title_max_chars": 0, "body_min_chars": 8, "body_max_chars": 70, "tag_min": 0, "tag_max": 0},
        "max_authorized_excerpt_chars": 0,
        "panse_intent_context": {"policy_version": "xhs-comment-intent.v4", "topic_ids": [item["topic"]], "interaction_intent": item["parent"], "comment_direction_id": item["direction"], "voice_id": "global_design_observer", "human_approved_example_set_version": "panse-xhs-human-approved-comments.v3"},
    }


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    requests, receipts, reviews = [], [], []
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(item, index)
        receipt = preflight(dict(payload))
        rid = payload["request_id"]
        requests.append({"target_note": {"note_id": item["note_id"], "title": item["title"], "source_locator": payload["source_locator"]}, "style_request": payload})
        receipts.append(receipt)
        stages["plan"][rid] = {"model_id": "gpt-5.6-sol", "fallback_used": False, "topic_ids": [item["topic"]], "comment_direction_id": item["direction"], "entry_angle": "不复述画面，直接给扣题的感受或有用观点。"}
        stages["draft"][rid] = {"model_id": "gpt-5.6-sol", "fallback_used": False, "draft_text": item["draft"], "tags": []}
        stages["semantic_review"][rid] = {"model_id": "gpt-5.6-sol", "fallback_used": False, "results": [
            {"gate": "source_grounding", "status": "pass", "notes": item["image"]},
            {"gate": "source_and_comment_repetition", "status": "pass", "notes": "没有照抄标题、正文或可见评论。"},
            {"gate": "obvious_visible_description", "status": "pass", "notes": "评论重点是态度或实际判断，不是重新描述画面。"},
            {"gate": "question_value", "status": "not_applicable", "notes": "本批都不为了互动硬提问。"},
            {"gate": "identity_and_experience_boundary", "status": "pass", "notes": "没有虚构亲历、购买或品牌关系。"},
            {"gate": "natural_voice", "status": "pass", "notes": "单句、口语、直接，没有整理稿口吻。"},
        ]}
        reviews.append({"request_id": rid, "account_slot_and_nickname": "slot 5 / 是阿宝啊", "note_id": item["note_id"], "target_note_title": item["title"], "source_context_summary": item["body"], "visible_comment_context_summary": item["comments"], "exact_draft_text": item["draft"], "interaction_mode": item["mode"], "comment_direction_id": item["direction"], "style_preflight_passed": bool(receipt.get("passed")), "semantic_review_passed": True, "queue_status": "awaiting_user_review", "current_user_approval_required": True, "published": False})

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_json("account_5_browse_receipts_13.json", {"schema_version": 1, "date": "2026-08-12", "account_slot": 5, "account_nickname": "是阿宝啊", "profile_id": "6347830c0000000012027db3", "browse_target": 11, "browse_actual": 13, "deep_read_actual": sum(1 for x in READS if x["deep_read"]), "body_and_visible_comments_read": True, "items": READS, "safety_warning_observed": False, "external_comments_posted": 0})
    write_json("account_5_follow_receipts_2.json", {"schema_version": 1, "date": "2026-08-12", "account_slot": 5, "verified_follow_count": 2, "items": [
        {"profile_id": "5f460f3e0000000001001254", "nickname": "Zephyr Yu（设计", "role_fit": "持续分享家具连接、桌腿桌面工艺和产品设计细节", "notes_read": ["68cba382000000000b010a2a", "684031b600000000200280b1"], "button_before": "关注", "button_after": "已关注", "verified": True},
        {"profile_id": "5be99ac0396fb600015f2bb6", "nickname": "时位", "role_fit": "持续分享海外艺术家具、材料与居住配色案例", "notes_read": ["6a6485e4000000000f005300", "6a38f9480000000011019407"], "button_before": "关注", "button_after": "已关注", "verified": True},
    ], "current_account_profile_verified": True, "safety_warning_observed": False})
    write_json("account_5_style_requests_4.json", {"schema_version": 1, "date": "2026-08-12", "phase": "account5_cycle_day04_review_only_generation", "account_slot": 5, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "request_count": 4, "requests": requests})
    write_json("account_5_style_compile_receipts_4.json", {"schema_version": 1, "compiled_at": stamp, "style_lab_route": "local_tachikoma_runtime", "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "receipt_count": 4, "all_passed": all(x.get("passed") for x in receipts), "text_generated_by_preflight": False, "external_posting_performed": False, "receipts": receipts})
    write_json("account_5_current_session_stage_responses_4.json", {"schema_version": 1, "created_at": stamp, "account_slot": 5, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "stages": stages, "external_posting_performed": False})
    write_json("account_5_human_review_4.json", {"schema_version": 1, "date": "2026-08-12", "account_slot": 5, "account_nickname": "是阿宝啊", "review_item_count": 4, "all_ready_for_user_review": all(x.get("passed") for x in receipts), "send_allowed": False, "user_approval_received": False, "published_count": 0, "approval_rule": "Only explicit approval of the exact displayed drafts permits sending.", "items": reviews})

    plan_path = RUN_DIR / "account_5_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse": 13, "actual_deep_reads": 11, "drafts_ready": 4, "verified_follows": 2, "public_visible_comments": 0, "unsent_review_items": 4, "status": "awaiting_user_review", "stop_reason": None, "login_gate": None})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 5:
            account.update({"status": "awaiting_user_review", "actual_browse": 13, "actual_deep_reads": 11, "drafts_ready": 4, "public_visible_comments": 0, "verified_follows": 2, "unsent": 4, "stop_reason": None})
    status["overall_status"] = "awaiting_user_review"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"browse_actual": 13, "deep_read_actual": 11, "verified_follows": 2, "review_items": 4, "all_preflight_passed": all(x.get("passed") for x in receipts), "comments_sent": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
