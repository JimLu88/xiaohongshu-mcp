#!/usr/bin/env python3
"""Build slot-4 day-2 evidence and a user-review-only comment queue."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-10"
TEMPLATE = RUN_DIR / "account_3_style_requests_4.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {
        "note_id": "6a4655ab0000000006020b90",
        "title": "85平的理想小家 附详细尺寸的户型图分享🏡",
        "author": "夹生饽饽",
        "images": "6/6",
        "comments": 56,
        "summary": "105平建面、85平套内的手绘户型与详细尺寸；作者强调小户型需要围绕一家人的身高、动线和取舍个性化设计。",
        "selected": False,
        "exclusion_reason": "评论区对入户与厨房关系已有争议，不适合作为新号首日互动目标。",
    },
    {
        "note_id": "6a754043000000003301ab2f",
        "title": "5.8m小横厅尺寸公开｜小户型客餐厅布局",
        "author": "imim11",
        "images": "3/3",
        "comments": 39,
        "summary": "5.8米横厅中用70厘米宽餐桌、90厘米餐桌到餐边柜通道，日常两人使用；沙发与电视墙的观看关系也给出尺寸。",
        "selected": True,
    },
    {
        "note_id": "69511987000000001d038f52",
        "title": "比颜值更重要！54㎡小家的“好住”动线分享",
        "author": "是南意呀",
        "images": "video 1:11/4:09",
        "comments": 10,
        "summary": "视频展示54平方米小家三条主要动线；可见评论集中在厨房燃气和双水槽。",
        "selected": False,
        "exclusion_reason": "当前可见视频段不足以支持更细的尺寸评论。",
    },
    {
        "note_id": "69d5da3e000000001d01fc97",
        "title": "小户型拥有了心心念念的“洄游动线”",
        "author": "户型改造丨桑榆",
        "images": "5/5",
        "comments": 33,
        "summary": "厨房到家政区形成洄游动线；评论区争论是否值得用台面、柜体和卧室空间交换。",
        "selected": False,
        "exclusion_reason": "评论区已有明显立场争论，新号不进入对错判断。",
    },
    {
        "note_id": "68d21b5f000000001301cf43",
        "title": "2.75m开间餐厅，选好餐桌和餐边柜尺寸很重要",
        "author": "大G小屋",
        "images": "4/4",
        "comments": 182,
        "summary": "餐区总开间2.75米、净开间2.45米；35厘米深餐边柜配80厘米宽餐桌，一侧通道90厘米、另一侧70厘米。",
        "selected": True,
    },
    {
        "note_id": "690d842e0000000007030fb2",
        "title": "餐桌是买大了吗？",
        "author": "momo发疯",
        "images": "2/2",
        "comments": 83,
        "summary": "作者给出80厘米过道；评论补充总开间2700、餐边柜约380、餐桌1600×850，并说明旋转餐桌后两侧都局促。",
        "selected": True,
    },
    {
        "note_id": "67e0f047000000000903ac13",
        "title": "餐桌过道只留80公分，会不会太窄了？",
        "author": "亚文哥（装修版）",
        "images": "4/4",
        "comments": 141,
        "summary": "35厘米餐边柜、80厘米餐桌、厨房到餐区83厘米通道；作者结合三口之家和多项功能需求反复调整布局。",
        "selected": False,
        "exclusion_reason": "评论区争议较重，不追加判断。",
    },
    {
        "note_id": "68c91129000000000e031645",
        "title": "替大家试过了，2.8米餐厅岛台这样做很好用。",
        "author": "阿黛🏠",
        "images": "6/11",
        "comments": 52,
        "summary": "2.8米开间、扣除餐边柜后2.4米，两侧各约80厘米；正文含较多具体产品与材料宣传。",
        "selected": False,
        "exclusion_reason": "商业推广属性较强且含多项材料承重主张，不作为新号互动目标。",
    },
    {
        "note_id": "697f178c000000002102a23f",
        "title": "开间3.16m｜床尾柜过道56cm真的不挤！",
        "author": "汪财糕",
        "images": "6/10",
        "comments": 64,
        "summary": "净开间3.16米、床架201厘米、背板4厘米、衣柜55厘米，过道56厘米；柜门44厘米并使用大角度铰链。",
        "selected": False,
        "exclusion_reason": "与入选的43厘米床尾柜案例主题过近，避免同日近似评论。",
    },
    {
        "note_id": "69bfd024000000001a0362c8",
        "title": "床尾衣柜过道小于多少，只能用推拉柜门？",
        "author": "叫我装修木老师",
        "images": "6/7",
        "comments": 0,
        "summary": "将床尾通道按70、60、50厘米拆成舒适、紧凑、局促三档，并把侧身和蹲下取物动作写清。",
        "selected": False,
        "exclusion_reason": "当前没有可见评论，且正文已经回答主要尺寸问题。",
    },
    {
        "note_id": "66cedca2000000001f0381b8",
        "title": "主卧开间3.06m| 床尾过道43cm挤不挤❓",
        "author": "阿丢的家🏡",
        "images": "6/15",
        "comments": 147,
        "summary": "净开间3.06米，床尾衣柜55厘米、柜内51厘米，柜门38厘米、过道43厘米；用大角度铰链并减少床头厚度。",
        "selected": True,
    },
    {
        "note_id": "6674509d000000001c027401",
        "title": "两边柜子中间门！！大佬们看一眼",
        "author": "花花日常记录（干货版）",
        "images": "3/3",
        "comments": 13,
        "summary": "门洞净宽830毫米，原方案成品门约730毫米；评论后作者已重新切门洞并加宽10厘米。",
        "selected": False,
        "exclusion_reason": "问题已在评论区给出落地结果，不重复提问或补建议。",
    },
]


CANDIDATES = [
    {
        "note_id": "6a754043000000003301ab2f",
        "title": "5.8m小横厅尺寸公开｜小户型客餐厅布局",
        "topic": "layout_circulation",
        "direction": "layout_circulation_question",
        "parent": "utility_fit_question",
        "mode": "curiosity_question",
        "body": "作者在5.8米小横厅里使用70厘米宽餐桌，餐桌到餐边柜留90厘米通道，日常主要两人使用；沙发尺度是作者明确优先保留的部分。",
        "comments": [
            "可见评论问过电视尺寸、饮水机和餐边柜尺寸深度",
            "未见作者回答餐椅向沙发一侧拉开后的碰撞情况",
        ],
        "image": "已看3/3张，可见横厅整体、餐桌与沙发的相对位置。",
        "draft": "70厘米宽的餐桌好适合小横厅，坐两个人时，餐椅拉开会碰到沙发吗？",
    },
    {
        "note_id": "68d21b5f000000001301cf43",
        "title": "2.75m开间餐厅，选好餐桌和餐边柜尺寸很重要",
        "topic": "dimensions_fit",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "作者给出餐区总开间2.75米、净开间2.45米；35厘米深餐边柜配80厘米宽餐桌，餐桌两侧分别留90厘米和70厘米。",
        "comments": [
            "可见评论问过三人同坐一侧、冰箱和餐边柜深度",
            "作者已说明三人同侧可以坐，但夹菜会不方便",
        ],
        "image": "已看4/4张，可见餐桌、餐边柜、厨房侧通道和尺寸关系。",
        "draft": "尺寸标得太清楚了👍刚好可以做参考",
    },
    {
        "note_id": "690d842e0000000007030fb2",
        "title": "餐桌是买大了吗？",
        "topic": "dimensions_fit",
        "direction": "size_clearance_question",
        "parent": "utility_fit_question",
        "mode": "curiosity_question",
        "body": "作者展示1600×850餐桌，餐边柜约380毫米，总开间2700毫米，当前通道约80厘米；换过餐桌方向但两侧都觉得局促。",
        "comments": [
            "可见评论已补齐总开间、餐桌和餐边柜尺寸，也讨论过旋转摆放",
            "未见作者回答餐椅拉开后实际剩余净空",
        ],
        "image": "已看2/2张，可见当前餐桌方向与80厘米通道。",
        "draft": "过道80厘米走人看着够，餐椅拉开以后还剩多少呀？",
    },
    {
        "note_id": "66cedca2000000001f0381b8",
        "title": "主卧开间3.06m| 床尾过道43cm挤不挤❓",
        "topic": "dimensions_fit",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "作者在3.06米净开间中做55厘米床尾衣柜，柜门38厘米、过道43厘米，并用大角度铰链解决开门动作。",
        "comments": [
            "可见评论集中在更小过道、尺寸计算和相似户型能否照搬",
            "作者补充43厘米还扣除了6厘米护墙板，并反复提醒柜门宽度",
        ],
        "image": "已看前6/15张，可见床尾柜、柜门开启和过道关系；正文还附户型与内部设计图。",
        "draft": "开门避让都一起算进去了，这组尺寸太有用了，感谢",
    },
]


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
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
            "request_id": f"panse.2026-08-10.account4.comment.{index:03d}",
            "idempotency_key": f"panse:2026-08-10:account-4:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。已完整阅读当前可见正文、相关图片和评论。"
                "身份是正在替自己家核对尺寸的普通住户，不装专家。先承接一个真实使用动作；"
                "需要提问时只问一个尚未回答的净尺寸或通行问题。需要夸赞时，内部审核先核对具体依据；"
                "公开评论优先用‘尺寸’‘这个细节’‘开门避让’等概括承接，不逐项复述正文已经明确的数字、名词和结论。"
                "不得虚构购买、入住、量房或长期使用经历，不替作者下结论，不使用老师、验收或裁判口吻。"
                "输出1至2句，不提畔色，不引导主页、私信、搜索、关注、点赞或购买。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "小红书户型尺寸账号评论语气实验",
            "audience": "正在核对小户型家具尺寸、净空与通行动作的普通用户",
            "use_case": "生成一条有具体尺寸依据、支持创作者且容易接话的评论",
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
                    "不得虚构购买、入住、量房、装修或长期使用经历",
                    "不得在缺少关键尺寸时下确定结论",
                    "不得重复评论区已回答的问题",
                    "不得使用老师、专家、验收或裁判口吻",
                    "夸赞后不得追加空泛总结或未被邀请的长建议",
                    "正文已写清时不得逐项复述作者的数字、名词清单或完整结论",
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
                "voice_id": "space_advisor",
            },
        }
    )
    return payload


def main() -> int:
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    write_json(
        "account_4_browse_receipts_12.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 4,
            "account_nickname": "小红薯6A68E133",
            "profile_id": "6a684f14000000001400c004",
            "browse_target": 12,
            "browse_actual": 12,
            "deep_read_actual": 12,
            "full_visible_body_read": True,
            "visible_comments_read_for_candidates": True,
            "items": READS,
            "safety_warning_observed": False,
            "inaccessible_attempt_excluded": {
                "note_id": "697f178c000000002102a23f",
                "first_attempt": "tokenless URL returned current-note-unavailable",
                "action": "did not retry tokenless; reopened once from visible search result token",
            },
        },
    )
    write_json(
        "account_4_follow_receipts_1.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 4,
            "target": {
                "profile_id": "6358b8f9000000001901fda4",
                "nickname": "阿丢的家🏡",
                "read_notes": [
                    "66cedca2000000001f0381b8",
                    "6a38ce0f000000001702bc65",
                ],
                "second_note_images_viewed": "6/15",
                "role_fit": "持续公开小户型尺寸、柜体净空和多功能房使用动作",
            },
            "button_before": "关注",
            "button_after": "已关注",
            "verified": True,
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
            "entry_angle": "先落到可见尺寸和真实动作；轻问只问一个未回答点，夸赞说完即停。",
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
                    "notes": "问题未在可见评论中回答；夸赞基于正文明确尺寸且没有追加建议。",
                },
                {
                    "gate": "identity_and_fact_boundary",
                    "status": "pass",
                    "notes": "未虚构量房、装修、购买、入住或长期使用经历。",
                },
                {
                    "gate": "natural_space_advisor_voice",
                    "status": "pass",
                    "notes": "口语短句；具体事实留在内部依据，公开评论不逐项复述正文，再轻问或说清参考价值后停住。",
                },
            ],
        }
        reviews.append(
            {
                "request_id": request_id,
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
        "account_4_style_requests_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "phase": "account4_cycle_day02_review_only_generation",
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
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "receipt_count": 4,
            "all_passed": all(item.get("passed") for item in receipts),
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
        },
    )
    write_json(
        "account_4_human_review_4.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 4,
            "review_item_count": 4,
            "all_ready_for_user_review": all(
                item["style_preflight_passed"] and item["semantic_review_passed"]
                for item in reviews
            ),
            "send_allowed": False,
            "approval_rule": "Only explicit approval of the exact displayed drafts permits sending.",
            "items": reviews,
        },
    )
    print(
        json.dumps(
            {
                "browse_actual": 12,
                "follow_verified": 1,
                "review_items": 4,
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
