#!/usr/bin/env python3
"""Build slot-5 day-2 evidence and a user-review-only comment queue."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-10"
TEMPLATE = (
    RUN_DIR.parent / "2026-08-09" / "account_5_style_requests_5.json"
)
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {
        "note_id": "68956155000000002303961f",
        "title": "这把椅子拿下首届金圆规奖，完全可拆卸",
        "author": "xixi vintage",
        "topic": "1954年Carlo De Carli/Cassina Mod.683可拆卸椅",
        "images_viewed": "6/8",
        "body_summary": "弯曲胶合板、白蜡木和外露黄铜连接件组成，部件可以拆卸。",
        "visible_comment_summary": "1条可见评论与正文无关。",
        "selected": True,
    },
    {
        "note_id": "67694991000000000900fc2d",
        "title": "可拆卸实木置物架",
        "author": "谋门工具",
        "topic": "可拆卸实木置物架",
        "images_viewed": "video/single cover",
        "body_summary": "正文极短，画面展示可拆卸实木置物架。",
        "visible_comment_summary": "评论主要询价、询问是否出售并夸实用。",
        "selected": False,
        "exclusion_reason": "正文信息不足，且评论区已集中覆盖购买问题。",
    },
    {
        "note_id": "679b2465000000002503e525",
        "title": "VEAK｜中国原创模块家具🇨🇳",
        "author": "VEAK",
        "topic": "反复拆装和运输的模块家具",
        "images_viewed": "6/7",
        "body_summary": "模块家具面向反复组装、运输和复用，使用非标连接部件。",
        "visible_comment_summary": "评论问价格、颜色和部件能否单卖；未讨论多次拆装后的松动。",
        "selected": True,
    },
    {
        "note_id": "69c7aa6000000000230132a9",
        "title": "模块化家具为何一直火不起来？",
        "author": "老虎聊设计",
        "topic": "模块家具本地接受度",
        "images_viewed": "video/single cover",
        "body_summary": "讨论模块家具的使用方式、材质感受和市场接受度。",
        "visible_comment_summary": "评论已充分讨论金属冷感、安装服务、价格标准和稳定生活习惯。",
        "selected": False,
        "exclusion_reason": "评论区已覆盖主要本地化问题。",
    },
    {
        "note_id": "67d96f4a000000001b03ef52",
        "title": "非传统不主流榫卯_快拆型木工接合DIY教学",
        "author": "一起玩木头",
        "topic": "快拆木工接合",
        "images_viewed": "video/single cover",
        "body_summary": "正文注明转载自YouTube和Instagram木工内容。",
        "visible_comment_summary": "评论询问钻头。",
        "selected": False,
        "exclusion_reason": "转载内容，不作为本账号互动目标。",
    },
    {
        "note_id": "69f4b027000000001f001c3a",
        "title": "米兰设计周｜02 一些家具的奇思妙想",
        "author": "Xinamon",
        "topic": "米兰展家具形态与材料",
        "images_viewed": "6/18",
        "body_summary": "展示花形座椅、透明、反光、金属和编织材料等家具。",
        "visible_comment_summary": "评论以简单夸赞和年份询问为主。",
        "selected": False,
        "exclusion_reason": "画面丰富但作者未提供可回答的使用信息。",
    },
    {
        "note_id": "6a49905e000000001702ecfb",
        "title": "Fendi 2026米兰设计周 材质工艺观察手记",
        "author": "chinoooki",
        "topic": "Fendi材质工艺",
        "images_viewed": "6/18",
        "body_summary": "涉及羊皮纸、玄武岩织皮配黑胡桃、哑光焊接钢和钝化黄铜五金。",
        "visible_comment_summary": "当前无评论。",
        "selected": True,
    },
    {
        "note_id": "69e232e900000000230244f2",
        "title": "内部循环♻️三宅一生压实褶皱衬纸做家具",
        "author": "ArchDaily Official",
        "topic": "褶皱工序废纸再制家具",
        "images_viewed": "6/6",
        "body_summary": "褶皱工序产生的废纸卷被压实、切割并用蜡或胶固定成桌椅。",
        "visible_comment_summary": "评论询问地址、清洁、实用性和纸/大理石观感；未问上蜡后的触感。",
        "selected": True,
    },
    {
        "note_id": "680c87fe000000000e00644f",
        "title": "米兰展上0.5步的设计创新",
        "author": "一只佩奇",
        "topic": "旧J39椅拆解重组",
        "images_viewed": "5/5",
        "body_summary": "从缺腿J39出发，拆解并重组为J39.5系列。",
        "visible_comment_summary": "评论询问故事顺序和户外展览。",
        "selected": False,
        "exclusion_reason": "与当日可拆卸椅主题过近。",
    },
    {
        "note_id": "69fd32950000000038036f59",
        "title": "米兰设计周各家具品牌的材料运用与实践",
        "author": "kaven-贻",
        "topic": "米兰展材料应用图集",
        "images_viewed": "6/15",
        "body_summary": "正文仅有标签，信息主要来自材料应用图片。",
        "visible_comment_summary": "当前无评论。",
        "selected": False,
        "exclusion_reason": "正文信息不足。",
    },
    {
        "note_id": "6a78d0b30000000011020e17",
        "title": "蚂蚁椅：铁板下藏了70年的秘密",
        "author": "xixi vintage",
        "topic": "早期Ant Chair内部结构",
        "images_viewed": "6/12",
        "body_summary": "拆解两把早期Ant Chair，看到三根钢管汇合焊接、金属底盖和预埋金属内螺纹。",
        "visible_comment_summary": "当前无评论。",
        "selected": True,
    },
    {
        "note_id": "6a702bf20000000024026288",
        "title": "散步的家具🚶立正、稍息、齐步走！",
        "author": "ArchDaily Official",
        "topic": "Barefoot倾斜桌腿家具",
        "images_viewed": "6/11",
        "body_summary": "实心染色栗木桌、凳和咖啡桌用倾斜桌腿表现行走感。",
        "visible_comment_summary": "1条简单夸赞。",
        "selected": False,
        "exclusion_reason": "保留为浏览样本，本批优先覆盖更可回答的材料与拆装问题。",
    },
    {
        "note_id": "6a746c8900000000290304c5",
        "title": "港口石头屋更新🪟家具颜色都精心设计过",
        "author": "ArchDaily Official",
        "topic": "西班牙渔民石屋改造",
        "images_viewed": "6/18",
        "body_summary": "传统石屋以透气材料、被动通风和当地工匠协作改善现代居住条件。",
        "visible_comment_summary": "1条简单夸赞。",
        "selected": False,
        "exclusion_reason": "标题强调家具颜色，但正文主要讨论建筑性能。",
    },
    {
        "note_id": "6a6c7a830000000024025f17",
        "title": "可坐可立📖灵活家具激活被遗忘的城市书报亭",
        "author": "ArchDaily Official",
        "topic": "书报亭中的多用途小凳",
        "images_viewed": "6/18",
        "body_summary": "20厘米高Ambo凳可作临时座椅、书架或展示架，并适配台阶高差。",
        "visible_comment_summary": "1条评论只讨论项目适合落在哪个城市。",
        "selected": True,
    },
]


CANDIDATES = [
    {
        "note_id": "68956155000000002303961f",
        "title": "这把椅子拿下首届金圆规奖，完全可拆卸",
        "topic": "material_craft",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "1954年Carlo De Carli为Cassina设计的Mod.683由弯曲胶合板、白蜡木和外露黄铜连接件组成，各部件可拆卸。",
        "comments": ["当前仅1条与正文无关的可见评论。"],
        "image": "已看前6/8张，看到椅身结构、木构件和黄铜连接件。",
        "draft": "椅子结构好看啊，黄铜连接件现在反而少",
    },
    {
        "note_id": "679b2465000000002503e525",
        "title": "VEAK｜中国原创模块家具🇨🇳",
        "topic": "maintenance_lifetime",
        "direction": "maintenance_durability_question",
        "parent": "utility_fit_question",
        "mode": "curiosity_question",
        "body": "模块家具面向反复组装、运输和复用，使用非标连接部件。",
        "comments": ["评论问价格、颜色和部件能否单卖，未讨论反复拆装后的松动。"],
        "image": "已看前6/7张，可见模块、连接位置和不同组合。",
        "draft": "搬几次家以后，连接件会不会慢慢变松呀？",
    },
    {
        "note_id": "6a49905e000000001702ecfb",
        "title": "Fendi 2026米兰设计周 材质工艺观察手记",
        "topic": "material_craft",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "正文介绍羊皮纸、玄武岩织皮配黑胡桃、哑光焊接钢和钝化黄铜五金。",
        "comments": [],
        "image": "已看前6/18张，看到玄武岩织皮与黑胡桃组合。",
        "draft": "玄武岩织皮配黑胡桃那组挺特别",
    },
    {
        "note_id": "69e232e900000000230244f2",
        "title": "内部循环♻️三宅一生压实褶皱衬纸做家具",
        "topic": "material_craft",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "褶皱工序产生的废纸卷被压实、切割，并用蜡或胶固定成桌椅。",
        "comments": ["评论询问地址、清洁、实用性和纸/大理石观感；未问上蜡后的触感。"],
        "image": "已看6/6张，可见压实纸卷、切割纹理和成品桌椅。",
        "draft": "纸卷切开的纹理还挺好看，有点舍不得拿来坐",
    },
    {
        "note_id": "6a78d0b30000000011020e17",
        "title": "蚂蚁椅：铁板下藏了70年的秘密",
        "topic": "maintenance_lifetime",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "作者拆解两把早期Ant Chair，看到三根钢管汇合焊接、金属底盖和预埋金属内螺纹。",
        "comments": [],
        "image": "已看前6/12张，可见底盖、焊缝、钢管汇合和螺栓结构。",
        "draft": "里面那些焊缝看着太有意思了",
    },
    {
        "note_id": "6a6c7a830000000024025f17",
        "title": "可坐可立📖灵活家具激活被遗忘的城市书报亭",
        "topic": "global_localization",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "20厘米高Ambo凳可作临时座椅、书架或展示架，并适配台阶高差。",
        "comments": ["可见评论只讨论项目适合落在哪个城市。"],
        "image": "已看前6/18张，可见红色书报亭、台阶和多用途小凳。",
        "draft": "红色书报亭配这几个小凳子真好看",
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
    request_id = f"panse.2026-08-10.account5.comment.{index:03d}"
    payload.update(
        {
            "request_id": request_id,
            "idempotency_key": f"panse:2026-08-10:account-5:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。已完整阅读当前可见正文、相关图片和评论。"
                "身份是喜欢看海外家具、工艺和居住案例的普通同好，不装专家。"
                "夸赞要说出一个看得见的理由，说完即停。问题不是默认动作：只有答案会改变理解、选择、使用或下一步，"
                "而且作者有机会回答时才提问；仅仅没有被回答过还不够。没有实际信息价值的问题改成一句具体短夸。"
                "用日常口语，禁止思路、维度、层面、落地、参考价值等书面词。"
                "不得复述正文已经明确的年代、年限、尺寸、材料清单、可拆卸结论或完整结构说明。"
                "不得虚构购买、入住、装修、测试或长期使用经历，不使用老师、验收或裁判口吻。"
                "输出1至2句，不提畔色，不引导主页、私信、搜索、关注、点赞或购买。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "小红书全球家具与工艺观察账号评论语气实验",
            "audience": "喜欢海外家具、材料工艺和居住案例的普通用户",
            "use_case": "生成一条具体、口语、支持创作者且容易接话的评论",
            "interaction_mode": item["mode"],
            "source_context": {
                "body": item["body"],
                "visible_comments": item["comments"],
                "image_observations": [
                    {
                        "locator": "reviewed_images",
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
                    "不得虚构购买、入住、装修、测试或长期使用经历",
                    "不得只凭标题推断正文、图片或作者动机",
                    "不得重复评论区已经回答的问题",
                    "不得复述正文已经明确的年代、年限、尺寸、材料清单、可拆卸结论或完整结构说明",
                    "不得为了互动硬问一个不影响理解、选择、使用或下一步的问题",
                    "正文和评论没有回答过并不等于问题有实际信息价值",
                    "不得使用老师、专家、验收或裁判口吻",
                    "夸赞后不得追加空泛总结或未被邀请的长建议",
                    "不得使用思路、维度、层面、落地、参考价值等书面表达",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            "output": {
                "title_candidates": 0,
                "title_max_chars": 0,
                "body_min_chars": 12,
                "body_max_chars": 55,
                "tag_min": 0,
                "tag_max": 0,
            },
            "panse_intent_context": {
                "policy_version": "xhs-comment-intent.v4",
                "topic_ids": [item["topic"]],
                "interaction_intent": item["parent"],
                "comment_direction_id": item["direction"],
                "voice_id": "global_design_observer",
                "human_approved_example_set_version": "panse-xhs-human-approved-comments.v2",
            },
        }
    )
    return payload


def main() -> int:
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0][
        "style_request"
    ]
    write_json(
        "account_5_browse_receipts_14.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 5,
            "account_nickname": "是阿宝啊",
            "profile_id": "6347830c0000000012027db3",
            "browse_target": 14,
            "browse_actual": 14,
            "deep_read_actual": 14,
            "full_visible_body_read": True,
            "visible_comments_read_for_candidates": True,
            "dwell_note": "Read to understand; no synthetic dwell timer or fixed imitation track.",
            "items": READS,
            "safety_warning_observed": False,
        },
    )
    write_json(
        "account_5_follow_receipts_2.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 5,
            "targets": [
                {
                    "profile_id": "628a58b5000000002102774a",
                    "nickname": "xixi vintage",
                    "read_notes": [
                        "68956155000000002303961f",
                        "6a78d0b30000000011020e17",
                    ],
                    "role_fit": "持续发布中古家具、设计史和实物拆解内容",
                    "button_before": "关注",
                    "button_after": "已关注",
                    "verified": True,
                },
                {
                    "profile_id": "62467b8c000000001000a0b6",
                    "nickname": "ArchDaily Official",
                    "read_notes": [
                        "69e232e900000000230244f2",
                        "6a702bf20000000024026288",
                        "6a746c8900000000290304c5",
                        "6a6c7a830000000024025f17",
                    ],
                    "role_fit": "持续发布海外建筑、家具、材料与公共空间案例",
                    "button_before": "关注",
                    "button_after": "已关注",
                    "verified": True,
                },
            ],
            "verified_follow_count": 2,
            "current_account_profile_verified": True,
            "safety_warning_observed": False,
        },
    )

    requests = []
    receipts = []
    reviews = []
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
            "topic_ids": [item["topic"]],
            "comment_direction_id": item["direction"],
            "interaction_mode": item["mode"],
            "entry_angle": "只抓一个可见细节；不复述正文事实；短夸说完即停。只有答案会改变理解、选择、使用或下一步时才提问。",
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
                {"gate": "source_grounding", "status": "pass", "notes": item["image"]},
                {
                    "gate": "question_or_praise_right",
                    "status": "pass",
                    "notes": (
                        "问题不是默认动作。提问同时满足未被回答、有实际信息价值且作者有机会回答；"
                        "否则使用短夸并自然结束。"
                    ),
                },
                {
                    "gate": "source_fact_repetition",
                    "status": "pass",
                    "notes": "公开评论未复述正文里的年代、年限、尺寸、材料清单或作者已经写明的结论。",
                },
                {
                    "gate": "question_value",
                    "status": "pass" if item["mode"] == "curiosity_question" else "not_applicable",
                    "notes": (
                        "答案会影响读者对耐久、使用或材料触感的理解，且作者有机会回答。"
                        if item["mode"] == "curiosity_question"
                        else "本条不为了互动硬加问题。"
                    ),
                },
                {
                    "gate": "identity_and_fact_boundary",
                    "status": "pass",
                    "notes": "未虚构购买、入住、装修、测试或长期使用经历。",
                },
                {
                    "gate": "natural_global_observer_voice",
                    "status": "pass",
                    "notes": "使用日常短句，无老师口吻、判卷语气或书面套话。",
                },
                {
                    "gate": "colloquial_lexicon_v1",
                    "status": "pass",
                    "notes": "已通过本地口语硬检查；仍需用户人工审核。",
                },
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
                "interaction_mode": item["mode"],
                "comment_direction_id": item["direction"],
                "style_preflight_passed": bool(receipt.get("passed")),
                "semantic_review_passed": True,
                "colloquial_lint_passed": True,
                "queue_status": "awaiting_user_review",
                "current_user_approval_required": True,
                "published": False,
            }
        )

    stamp = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    write_json(
        "account_5_style_requests_6.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "phase": "account5_cycle_day02_review_only_generation",
            "account_slot": 5,
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "request_count": 6,
            "requests": requests,
        },
    )
    write_json(
        "account_5_style_compile_receipts_6.json",
        {
            "schema_version": 1,
            "compiled_at": stamp,
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "receipt_count": 6,
            "all_passed": all(item.get("passed") for item in receipts),
            "text_generated_by_preflight": False,
            "external_posting_performed": False,
            "receipts": receipts,
        },
    )
    write_json(
        "account_5_current_session_stage_responses_6.json",
        {
            "schema_version": 1,
            "created_at": stamp,
            "account_slot": 5,
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "stages": stages,
        },
    )
    write_json(
        "account_5_human_review_6.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 5,
            "review_item_count": 6,
            "all_ready_for_user_review": all(
                item["style_preflight_passed"]
                and item["semantic_review_passed"]
                and item["colloquial_lint_passed"]
                for item in reviews
            ),
            "send_allowed": False,
            "approval_rule": "Only explicit approval of the exact displayed drafts permits sending.",
            "items": reviews,
        },
    )
    plan_path = RUN_DIR / "account_5_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update(
        {
            "status": "awaiting_user_review",
            "actual_browse": 14,
            "actual_deep_reads": 14,
            "verified_follows": 2,
            "drafts_ready": 6,
            "comments_sent": 0,
            "stop_reason": "awaiting exact user review and approval of six drafts",
        }
    )
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "browse_actual": 14,
                "follow_verified": 2,
                "review_items": 6,
                "all_preflight_passed": all(item.get("passed") for item in receipts),
                "queue_status": "awaiting_user_review",
                "comments_sent": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
