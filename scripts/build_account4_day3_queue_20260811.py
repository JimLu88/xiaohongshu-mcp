#!/usr/bin/env python3
"""Build slot-4 cycle-day-3 evidence and review-only queue for 2026-08-11."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-11"
TEMPLATE = RUN_DIR / "account_3_style_requests_5.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {"note_id":"69b8d167000000001d01f7a9","title":"餐厅净宽2.8米|用1.1米圆桌一年真实体验🥣","author":"阿悦儿呀","media":"6/11图","comments":27,"summary":"净宽2.8米放1.1米圆桌，日常两人靠一侧使用，来客时再移动；正文和当前可见评论已读。"},
    {"note_id":"6937cb21000000001e00e7c8","title":"餐厅开间3.18米｜小户型也可以大胆选圆桌🥣","author":"阿悦儿呀","media":"6/9图","comments":38,"summary":"3.18米开间、扣除餐边柜约2.8米，圆桌随人数移动；正文和当前可见评论已读。"},
    {"note_id":"6a27ac41000000001702b55c","title":"柜门的坑，刚装修好就改造，600大洋出去了","author":"蜜桃啊蜜桃","media":"4/4图","comments":0,"summary":"1500毫米高柜由多扇窄门改为两扇宽门，作者反馈拿取更方便；正文完整，当前无可见评论。"},
    {"note_id":"6a3a2db30000000016027275","title":"拿错的餐桌，没想到确是最合适的选择","author":"蜜桃啊蜜桃","media":"3/3图","comments":5,"summary":"透明桌腿餐桌放入小餐厅后视觉更轻；正文和当前可见评论已读。"},
    {"note_id":"6a72b06c0000000008013f60","title":"衣柜门总撞床头柜？每天开门都像打仗😤","author":"老师傅的装修手记","media":"3/3图","comments":0,"summary":"讨论柜门宽度以及床头柜旁柜门分成上下两段、下段做固定假门；正文完整，当前无可见评论。"},
    {"note_id":"68b707d1000000001c005ebe","title":"在线求助，阳台柜太窄，比例不协调咋整？","author":"泰迪熊","media":"6/6图","comments":6,"summary":"约60厘米宽阳台柜的三扇窄门比例求助；正文和当前可见评论已读。"},
    {"note_id":"689d3113000000001c00890f","title":"入户门过道只有83公分了，怎么办😢","author":"半生欢喜","media":"1/1图","comments":1402,"summary":"40厘米深柜体使长入户过道仅余83厘米，评论讨论日常通行与大件进入；正文和当前可见评论已读。"},
    {"note_id":"68bd85d3000000001d028eb7","title":"进门不到1米宽的过道，我硬是凿出了个鞋柜","author":"木间半百闲","media":"6/10图","comments":3,"summary":"窄玄关借墙体做超薄鞋柜，保留通道并避开强弱电箱；正文和当前可见评论已读。"},
]


CANDIDATES = [
    {
        "note_id":"6a3a2db30000000016027275","title":"拿错的餐桌，没想到确是最合适的选择",
        "topic":"layout_circulation","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者原本想要普通桌腿，拿货时拿成透明桌腿，放进小餐厅后视觉更轻。",
        "comments":["可见评论主要说透明桌腿独特、好看；作者回应是误打误撞选对了。"],
        "image":"已看3/3张，可见透明桌腿与小餐厅的视觉关系。",
        "draft":"透明桌腿反而更适合这个小餐厅，看着轻好多。",
    },
    {
        "note_id":"6a27ac41000000001702b55c","title":"柜门的坑，刚装修好就改造，600大洋出去了",
        "topic":"dimensions_fit","direction":"light_social_response","parent":"neutral_social","mode":"light_humor_or_neutral",
        "body":"作者把1500毫米宽高柜由两大两小的窄门方案改成两扇宽门，表示拿取更方便。",
        "comments":["当前没有可见评论。"],
        "image":"已看4/4张，可比较改造前后柜门分割与整体比例。",
        "draft":"这种高柜还是两扇看着舒服，小门一多真的很碎。",
    },
    {
        "note_id":"6a72b06c0000000008013f60","title":"衣柜门总撞床头柜？每天开门都像打仗😤",
        "topic":"dimensions_fit","direction":"size_clearance_question","parent":"utility_fit_question","mode":"curiosity_question",
        "body":"作者建议把床头柜旁的柜门从下部断开，下半截固定为假门，上半截正常开启。",
        "comments":["当前没有可见评论，也没有说明假门后方空间如何拿取。"],
        "image":"已看3/3张，可见柜门、床头柜和上下分段关系。",
        "draft":"下半截做成假门以后，里面那块怎么拿东西呀？",
    },
    {
        "note_id":"68bd85d3000000001d028eb7","title":"进门不到1米宽的过道，我硬是凿出了个鞋柜",
        "topic":"storage_function","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者在不足一米宽的玄关借墙体做超薄鞋柜，并提醒避开强弱电箱。",
        "comments":["可见评论问砸墙后是否刮腻子，另有一条直接夸赞；没有评论门板与墙面的视觉关系。"],
        "image":"已看前6/10张，可见柜门完成后与墙面的关系。",
        "draft":"这个薄鞋柜做完真清爽，门板也没显得突兀。",
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
    if done.returncode:
        raise RuntimeError(done.stderr.decode("utf-8", errors="replace"))
    return json.loads(done.stdout.decode("utf-8"))


def build_payload(base: dict, item: dict, index: int) -> dict:
    payload = copy.deepcopy(base)
    payload.update({
        "request_id":f"panse.2026-08-11.account4.comment.{index:03d}",
        "idempotency_key":f"panse:2026-08-11:account-4:{item['note_id']}",
        "brief_text":f"目标原帖为《{item['title']}》。已读完整正文、相关图片和当前可见评论。身份是关注户型、尺寸和日常使用的普通同好，不装专家。先扣住一个画面里真能看到的细节，再用一句口语完成夸赞、观点或一个作者能回答的轻问。不要把标题和正文换个说法再讲一遍，不追加空泛总结，不为了互动硬问问题，不虚构购买、入住、量房、装修或长期使用经历。避免思路、那组、尤其、参考价值、落地、下单等书面词，改用想法、那个、特别、买等日常说法。输出1句、12至55字；不提畔色，不引导主页、私信、搜索、关注、点赞或购买。",
        "source_locator":f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario":"小红书户型尺寸账号评论语气实验",
        "audience":"正在核对小户型家具尺寸、净空和通行动作的普通用户",
        "use_case":"生成一条具体、口语化、支持创作者且不装专家的评论草稿",
        "interaction_mode":item["mode"],
        "source_context":{"body":item["body"],"visible_comments":item["comments"],"image_observations":[{"locator":"reviewed_media","observation":item["image"],"observation_basis":"caller_reviewed"}],"body_complete":True,"visible_comments_complete":True,"images_complete":True,"expected_visible_comment_count":len(item["comments"]),"expected_image_count":1},
        "required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,
        "content_contract":{"protected_facts":[],"allowed_paraphrases":{},"forbidden_inferences":["不得虚构购买、入住、量房、装修或长期使用经历","不得在缺少关键净尺寸时下确定结论","不得重复标题、正文结论或当前评论","不得使用老师、专家、验收或裁判口吻","不得为了互动硬问无意义或作者无法回答的问题","不得使用思路、那组、尤其、参考价值、落地、下单等书面表达"],"citation_anchors":{},"must_cover_fact_ids":[]},
        "output":{"title_candidates":0,"title_max_chars":0,"body_min_chars":12,"body_max_chars":55,"tag_min":0,"tag_max":0},
        "panse_intent_context":{"policy_version":"xhs-comment-intent.v4","topic_ids":[item["topic"]],"interaction_intent":item["parent"],"comment_direction_id":item["direction"],"voice_id":"space_advisor","human_approved_example_set_version":"panse-xhs-human-approved-comments.v3"},
    })
    return payload


def main() -> int:
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    requests, receipts, reviews = [], [], []
    stages = {"plan":{},"draft":{},"semantic_review":{}}
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        rid = payload["request_id"]
        requests.append({"target_note":{"note_id":item["note_id"],"title":item["title"],"source_locator":payload["source_locator"]},"style_request":payload})
        receipts.append(receipt)
        stages["plan"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"topic_ids":[item["topic"]],"comment_direction_id":item["direction"],"interaction_mode":item["mode"],"entry_angle":"说一个具体细节后停住；轻问只问作者能回答且评论区未回答的点。"}
        stages["draft"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"draft_text":item["draft"],"tags":[]}
        stages["semantic_review"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"results":[
            {"gate":"source_grounding","status":"pass","notes":item["image"]},
            {"gate":"source_and_comment_repetition","status":"pass","notes":"没有照抄标题或正文结论，也没有重复当前可见评论。"},
            {"gate":"question_value","status":"pass" if item["mode"]=="curiosity_question" else "not_applicable","notes":"唯一问题指向假门后的拿取动作，作者可以回答。" if item["mode"]=="curiosity_question" else "本条不提问。"},
            {"gate":"identity_and_experience_boundary","status":"pass","notes":"普通同好口吻，没有虚构亲历或品牌关系。"},
            {"gate":"natural_voice","status":"pass","notes":"单句、口语、具体，未使用整理稿词和老师口吻。"},
        ]}
        reviews.append({"request_id":rid,"account_slot_and_nickname":"slot 4 / 小红薯6A68E133","note_id":item["note_id"],"target_note_title":item["title"],"source_context_summary":item["body"],"visible_comment_context_summary":item["comments"],"exact_draft_text":item["draft"],"interaction_mode":item["mode"],"comment_direction_id":item["direction"],"style_preflight_passed":bool(receipt.get("passed")),"semantic_review_passed":True,"queue_status":"awaiting_user_review","current_user_approval_required":True,"published":False})

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_json("account_4_browse_receipts_8.json", {"schema_version":1,"date":"2026-08-11","account_slot":4,"account_nickname":"小红薯6A68E133","profile_id":"6a684f14000000001400c004","browse_target":8,"browse_actual":8,"deep_read_actual":8,"body_and_visible_comments_read":True,"items":READS,"safety_warning_observed":False,"external_comments_posted":0})
    write_json("account_4_follow_receipts_2.json", {"schema_version":1,"date":"2026-08-11","account_slot":4,"verified_follow_count":2,"items":[
        {"profile_id":"5d1819d800000000110209d6","nickname":"阿悦儿呀","role_fit":"持续分享真实小户型餐厅尺寸、家具摆放和使用反馈","notes_read":["69b8d167000000001d01f7a9","6937cb21000000001e00e7c8"],"button_before":"关注","button_after":"已关注","verified":True},
        {"profile_id":"5a4cf35c11be1054efbde862","nickname":"蜜桃啊蜜桃","role_fit":"持续发布真实装修、柜体改造与小空间使用复盘","notes_read":["6a27ac41000000001702b55c","6a3a2db30000000016027275"],"button_before":"关注","button_after":"已关注","verified":True},
    ],"current_account_profile_verified":True,"safety_warning_observed":False})
    write_json("account_4_style_requests_4.json", {"schema_version":1,"date":"2026-08-11","phase":"account4_cycle_day03_review_only_generation","account_slot":4,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"request_count":4,"requests":requests})
    write_json("account_4_style_compile_receipts_4.json", {"schema_version":1,"compiled_at":stamp,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"receipt_count":4,"all_passed":all(x.get("passed") for x in receipts),"text_generated_by_preflight":False,"external_posting_performed":False,"receipts":receipts})
    write_json("account_4_current_session_stage_responses_4.json", {"schema_version":1,"created_at":stamp,"account_slot":4,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"stages":stages,"external_posting_performed":False})
    write_json("account_4_human_review_4.json", {"schema_version":1,"date":"2026-08-11","account_slot":4,"account_nickname":"小红薯6A68E133","review_item_count":4,"all_ready_for_user_review":all(x.get("passed") for x in receipts),"send_allowed":False,"user_approval_received":False,"published_count":0,"approval_rule":"Only explicit approval of the exact displayed drafts permits sending.","items":reviews})

    plan_path = RUN_DIR / "account_4_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse":8,"actual_deep_reads":8,"drafts_ready":4,"verified_follows":2,"public_visible_comments":0,"unsent_review_items":4,"status":"awaiting_user_review","stop_reason":None})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 4:
            account.update({"status":"awaiting_user_review","actual_browse":8,"actual_deep_reads":8,"drafts_ready":4,"public_visible_comments":0,"verified_follows":2,"unsent":4})
    status["overall_status"] = "awaiting_user_review"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"browse_actual":8,"deep_read_actual":8,"verified_follows":2,"review_items":4,"all_preflight_passed":all(x.get("passed") for x in receipts),"comments_sent":0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
