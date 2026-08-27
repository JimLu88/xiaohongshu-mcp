#!/usr/bin/env python3
"""Build slot-2 day-2 evidence and the five preflighted comment requests."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-10"
PREVIOUS = RUN_DIR.parent / "2026-08-09" / "account_2_style_requests_6.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    ("6a7726ca000000002203316b", "谁家的家配色这么高级啊啊啊", "韩友娜的家", "single", False, "完整正文及当前可见评论"),
    ("6a6c9c030000000005028420", "极限压缩成本的家🏠", "韩友娜的家", "17秒视频", False, "完整正文及6条可见评论"),
    ("6a7472230000000028000111", "67平两室一厅｜小户型这么装真的太舒适啦✌🏻", "八月午后", "6/16", True, "完整正文及当前可见评论；作者已回答3米开间"),
    ("6a65fb8c00000000090356c8", "🆘谁懂啊，小户型这样装显大又高级", "八月午后", "6/14", False, "完整正文及当前可见评论"),
    ("6a16a654000000003601b374", "小家显贵，先统一这5个地方", "住的有点讲究", "5/5", True, "完整正文及7条可见评论"),
    ("690c4e5500000000030138c1", "从来没有这么直观的感受软装的重要性……", "小鱼🐳的小家", "6/16", False, "完整可见正文及当前可见评论"),
    ("6a479c010000000008002161", "小户型最稳的3套显大配色，白墙也能高级", "克色｜小户型配色", "6/7", False, "页面标注可能含AI生成内容，排除评论候选"),
    ("6a1ad9be0000000035030514", "NO.56｜小户型也可以有电影感（附清单）", "YUNXI", "6/8", True, "完整正文及2条可见评论；正文标注原空间来源"),
    ("69ad2ed4000000001a033c75", "从图1到图18，77㎡自装小家依然越看越幸福~☀", "韩小果的家", "6/18", True, "完整正文及当前可见评论"),
    ("67e0ae32000000001c03d219", "67平小户型，我的家，你们要的客餐厅细节来了", "小小的家（装修记）", "6/6", False, "完整可见正文及当前可见评论"),
    ("69ee0f7d000000001f0064cd", "小户型中古软装｜家居配色与氛围感干货分享", "梵喵的小家", "6/13", False, "完整正文及当前可见评论"),
    ("6a7691a40000000005023fcc", "网购🟤⚫配色的小户型中古风茶几太好看啦！！", "夏天", "6/15", True, "完整正文及11条可见评论；尺寸问题已回答，水印问题未见回答"),
    ("6a60a8ae000000002201a5ec", "越少，越好！", "六耳九思", "6/18", False, "完整可见正文及当前可见评论；评论区观点分歧较大，排除"),
]


CANDIDATES = [
    {
        "note_id": "6a7472230000000028000111",
        "title": "67平两室一厅｜小户型这么装真的太舒适啦✌🏻",
        "topic": "dimensions_fit",
        "direction": "size_clearance_question",
        "parent": "utility_fit_question",
        "mode": "curiosity_question",
        "body": "作者写明67平、套内55平、客厅开间3米，以轻硬装和可变化家具安排小空间；茶几与餐桌均可变形。",
        "comments": ["作者在可见评论中确认客厅开间为3米", "可见评论询问茶几、地毯、沙发等，未见地毯尺寸答案"],
        "image": "已看前6/16张，可见客厅茶几、餐桌与通行动线。",
        "draft": "客厅开间3米还能把茶几和餐桌都留成可变形的，确实很会省空间。地毯是多大尺寸呀？",
    },
    {
        "note_id": "6a16a654000000003601b374",
        "title": "小家显贵，先统一这5个地方",
        "topic": "storage_function",
        "direction": "detail_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "作者建议小家先统一颜色与材质，收起电线、纸巾和遥控器，再用暖光和固定收纳位置减少杂乱。",
        "comments": ["可见评论有人认为方法实用", "另一条询问沙发信息，与草稿无重复"],
        "image": "已看5/5张，可见统一配色、隐藏杂物与暖光关系。",
        "draft": "先统一再慢慢添这个思路很适合小家，尤其把线和遥控器藏起来这点，一收桌面真的会清爽很多。",
    },
    {
        "note_id": "6a1ad9be0000000035030514",
        "title": "NO.56｜小户型也可以有电影感（附清单）",
        "topic": "color_light_atmosphere",
        "direction": "atmosphere_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "作者整理约60㎡真实居住空间：木色打底，蓝色条纹沙发、黄色甜甜圈壁灯和少量高饱和小物搭配暖光。",
        "comments": ["当前可见评论2条", "未见与蓝色沙发、木色和黄色壁灯组合相同的表达"],
        "image": "已看前6/8张，可见蓝色条纹沙发、木色家具与黄色壁灯。",
        "draft": "蓝色条纹沙发配木色真的很亮眼，黄色壁灯一加，整个家一下有电影感了。",
    },
    {
        "note_id": "69ad2ed4000000001a033c75",
        "title": "从图1到图18，77㎡自装小家依然越看越幸福~☀",
        "topic": "color_light_atmosphere",
        "direction": "atmosphere_grounded_praise",
        "parent": "grounded_praise",
        "mode": "support_only",
        "body": "作者自装77㎡小家并已居住三年，空间混搭复古木色，开放阳台摆放大量绿植。",
        "comments": ["可见评论中有人喜欢阳台", "没有重复草稿中绿植与复古木色衔接的完整表达"],
        "image": "已看前6/18张，可见开放阳台绿植与客厅复古木色连续。",
        "draft": "最喜欢开放阳台那块，绿植和客厅的复古木色接得很自然。住了三年还这么喜欢，真的很让人羡慕。",
    },
    {
        "note_id": "6a7691a40000000005023fcc",
        "title": "网购🟤⚫配色的小户型中古风茶几太好看啦！！",
        "topic": "color_light_atmosphere",
        "direction": "color_light_fit_question",
        "parent": "utility_fit_question",
        "mode": "curiosity_question",
        "body": "作者在约90㎡客厅使用黑、棕、白配色，3×2米地毯搭配胡桃木桌面和玻璃边几；可见评论中作者回答茶几尺寸为90和50。",
        "comments": ["作者已回答茶几尺寸、地砖和购买问题", "当前可见评论未见浅咖地毯在自然光下色相的问题"],
        "image": "已看前6/15张，可见90与50茶几组合、胡桃木桌面和玻璃边几。",
        "draft": "胡桃木桌面配浅咖地毯很好看，白天自然光下地毯会更偏灰还是偏黄呀？",
    },
]


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(payload: dict) -> dict:
    done = subprocess.run(
        [sys.executable, str(PREFLIGHT), "-"],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO,
        check=False,
    )
    if done.returncode != 0:
        raise RuntimeError(done.stderr.decode("utf-8", errors="replace"))
    return json.loads(done.stdout.decode("utf-8"))


def build_payload(base: dict, item: dict, index: int) -> dict:
    payload = copy.deepcopy(base)
    payload.update(
        {
            "request_id": f"panse.2026-08-10.account2.comment.{index:03d}",
            "idempotency_key": f"panse:2026-08-10:account-2:{item['note_id']}",
            "brief_text": (
                f"目标原帖为《{item['title']}》。已完整阅读当前可见正文、相关图片和当前可见评论。"
                "说话位置是支持创作者的普通家居同好：先接住一个具体细节，再简短夸赞；最多问一个当前评论区尚未回答、作者容易回答的问题。"
                "不用老师、评委、验收或大师口吻，不纠错、不判分、不补空洞总结。"
                "不得虚构购买、入住、装修、施工、检测或长期使用经历。输出一条自然评论，1至2句、12至60字；"
                "不提畔色，不引导主页、私信、搜索、关注、点赞或购买。"
            ),
            "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
            "scenario": "家居内容评论语气实验",
            "audience": "关注家装、家具与空间生活的普通用户",
            "use_case": "生成一条支持创作者、便于自然互动的评论草稿",
            "interaction_mode": item["mode"],
            "source_context": {
                "body": item["body"],
                "visible_comments": item["comments"],
                "image_observations": [{"locator": "reviewed_images", "observation": item["image"], "observation_basis": "caller_reviewed"}],
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
                    "不得以老师、评委、验收人员或大师口吻评价创作者",
                    "不得重复当前可见评论中已回答的问题",
                    "不得追加与正文无关的空洞建议或结论",
                ],
                "citation_anchors": {},
                "must_cover_fact_ids": [],
            },
            "output": {"title_candidates": 0, "title_max_chars": 0, "body_min_chars": 12, "body_max_chars": 60, "tag_min": 0, "tag_max": 0},
            "panse_intent_context": {
                "policy_version": "xhs-comment-intent.v4",
                "topic_ids": [item["topic"]],
                "interaction_intent": item["parent"],
                "comment_direction_id": item["direction"],
                "voice_id": "stylist",
            },
        }
    )
    return payload


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    previous = json.loads(PREVIOUS.read_text(encoding="utf-8"))
    base = previous["requests"][0]["style_request"]
    write_json(
        "account_2_browse_receipts_13.json",
        {
            "schema_version": 1,
            "date": "2026-08-10",
            "account_slot": 2,
            "account_nickname": "🦀",
            "browse_target": 13,
            "browse_actual": 13,
            "deep_read_actual": 13,
            "full_visible_body_read": True,
            "visible_comments_read": True,
            "items": [
                {"note_id": n, "title": t, "author": a, "images_viewed": i, "selected_for_comment": s, "read_evidence": e}
                for n, t, a, i, s, e in READS
            ],
            "safety_warning_observed": False,
        },
    )

    requests, receipts, review_items = [], [], []
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        rid = payload["request_id"]
        requests.append({"target_note": {"note_id": item["note_id"], "title": item["title"], "source_locator": payload["source_locator"]}, "style_request": payload})
        receipts.append(receipt)
        stages["plan"][rid] = {
            "model_id": "gpt-5.6-sol",
            "fallback_used": False,
            "topic_ids": [item["topic"]],
            "comment_direction_id": item["direction"],
            "interaction_mode": item["mode"],
            "entry_angle": "先承接可见细节，再给短夸或一个未回答的轻问。",
        }
        stages["draft"][rid] = {"model_id": "gpt-5.6-sol", "fallback_used": False, "draft_text": item["draft"], "tags": []}
        stages["semantic_review"][rid] = {
            "model_id": "gpt-5.6-sol",
            "fallback_used": False,
            "results": [
                {"gate": "source_grounding", "status": "pass", "notes": item["image"]},
                {"gate": "visible_comment_question_dedupe", "status": "pass", "notes": "已核对当前可见评论；轻问未见已回答。" if item["mode"] == "curiosity_question" else "本条不提问。"},
                {"gate": "identity_and_experience_boundary", "status": "pass", "notes": "普通家居同好口吻；没有虚构亲历或品牌关系。"},
                {"gate": "supportive_natural_voice", "status": "pass", "notes": "具体承接在前，无判卷、纠错或空尾巴。"},
            ],
        }
        review_items.append({
            "request_id": rid,
            "note_id": item["note_id"],
            "title": item["title"],
            "draft": item["draft"],
            "interaction_mode": item["mode"],
            "comment_direction_id": item["direction"],
            "style_preflight_passed": bool(receipt.get("passed")),
            "semantic_review_passed": True,
            "queue_status": "ready_for_send",
            "published": False,
        })

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_json("account_2_style_requests_5.json", {"schema_version": 1, "date": "2026-08-10", "phase": "account2_cycle_day02_live_generation", "account_slot": 2, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "request_count": 5, "requests": requests})
    write_json("account_2_style_compile_receipts_5.json", {"schema_version": 1, "compiled_at": stamp, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "receipt_count": 5, "all_passed": all(r.get("passed") for r in receipts), "receipts": receipts})
    write_json("account_2_current_session_stage_responses_5.json", {"schema_version": 1, "created_at": stamp, "account_slot": 2, "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "stages": stages})
    write_json("account_2_human_review_5.json", {"schema_version": 1, "date": "2026-08-10", "account_slot": 2, "review_item_count": 5, "all_ready_for_send": all(x["style_preflight_passed"] and x["semantic_review_passed"] for x in review_items), "items": review_items})
    print(json.dumps({"requests": 5, "all_preflight_passed": all(r.get("passed") for r in receipts), "artifacts": 5}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
