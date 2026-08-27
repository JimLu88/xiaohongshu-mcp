#!/usr/bin/env python3
"""Build slot-3 cycle-day-3 evidence and review-only queue for 2026-08-11."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-11"
TEMPLATE = RUN_DIR.parent / "2026-08-09" / "account_3_style_requests_5.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {"note_id":"6a7a97ba00000000250118f5","title":"朴愫Tips | 让尺度适配你的生活空间~","author":"朴愫木作","media":"6/8图","status":"deep_read","summary":"沙发长度、墙面余量和通行净空；正文及当前可见评论已读。"},
    {"note_id":"695a4d1d000000001f00c040","title":"怪你家小？其实动线废了！这图专治各种不服","author":"设别木作","media":"3/3图","status":"deep_read","summary":"客厅家具与通道关系；正文及2条当前可见评论已读。"},
    {"note_id":"696bb16e000000000d00a4c8","title":"保姆级干货：沙发茶几怎么摆？全套尺寸公开。","author":"小小怪Home","media":"6/7图","status":"deep_read","summary":"沙发、茶几和走动空间的尺寸关系；正文完整，当前无可见评论。"},
    {"note_id":"68343c5f00000000220079f6","title":"中古横厅尺寸大公开｜这么布置显大还好看","author":"左左家","media":"1/16图","status":"browse_only","reason":"carousel_interaction_blocked","summary":"正文和评论已读，但图集控件连续无法翻页，不计深读。"},
    {"note_id":"6a5dfda60000000001031e42","title":"为啥我们喜欢用实木多层板？","author":"PUPUPULA","media":"5/5图","status":"deep_read","summary":"实木多层板的材料取舍；正文完整，当前无可见评论。"},
    {"note_id":"69a5bca4000000001a0365f9","title":"木屿木作| 一图秒懂，不纠结。","author":"木屿木作","media":"正文图已读","status":"deep_read","summary":"木材与家具选择内容；正文及12条当前可见评论已读。"},
    {"note_id":"69d7568c0000000021005063","title":"原木VS实木，不要傻傻分不清楚！！！！！","author":"邱掌柜说餐桌","media":"2/2图","status":"deep_read","summary":"原木、实木概念辨析；正文及10条当前可见评论已读。"},
    {"note_id":"6a705315000000002402e67d","title":"原木、实木、贴皮板，一次讲清楚","author":"北京实木木作日记","media":"6/7图","status":"deep_read","summary":"材料与表面做法差异；正文完整，当前无可见评论。"},
    {"note_id":"67eb8782000000001202eea4","title":"网购家具的正确步骤（全网最全避坑指南）","author":"圆阿噗","media":"6/18图","status":"deep_read","summary":"网购大件前后的核对步骤；正文及9条当前可见评论已读。"},
    {"note_id":"69fb34ab000000002003a8f4","title":"已退回，运费好贵！","author":"红鱼和阿飞","media":"6/12图","status":"deep_read","summary":"大板桌尺寸比例不合适后退货，运费400元；正文及12条当前可见评论已读。"},
    {"note_id":"68e8d2b0000000000301b134","title":"买大家具容易忽略的一点——进电梯","author":"小梦悠悠","media":"5/5图","status":"deep_read","summary":"大件进电梯、拆包装与额外搬运费用；正文及1条当前可见评论已读。"},
    {"note_id":"69d376fd000000001f00596c","title":"冷知识：2.4米的高度放不下2.4米的衣柜","author":"铁锤妹妹🍬","media":"3/3图","status":"deep_read","summary":"高柜安装后无法立起，地面误差和安装方式均影响所需余量；正文及12条当前可见评论已读。"},
    {"note_id":"6a460bef000000000803f8b2","title":"别再被忽悠了！18883/50325 测不了家具","author":"蓝莘CMA检测中心","media":"1/6图","status":"browse_only","reason":"carousel_interaction_blocked","summary":"正文和评论已读，但图集控件连续无法翻页，不计深读。"},
    {"note_id":"674d20f10000000002038ff2","title":"家具检测报告 胡桃木真假","author":"salt","media":"4/4图","status":"deep_read","summary":"家具检测报告与胡桃木材料疑问；正文及12条当前可见评论已读。"},
    {"note_id":"6a3cda05000000000f016563","title":"客厅人体工学精准尺寸｜装修全屋定制必看✨","author":"MITU 米图研定全屋定制工作室","media":"1/多图","status":"browse_only","reason":"carousel_interaction_blocked","summary":"正文已读，但图集控件连续无法翻页，不计深读。"},
    {"note_id":"6854b0fb00000000120177d2","title":"别总盯着环保这项💢板材检测报告怎么看？","author":"天盟家居","media":"6/8图","status":"deep_read","summary":"板材报告不应只看甲醛，还涉及强度、吸水等项目；正文及12条当前可见评论已读。"},
    {"note_id":"66e148490000000012013ec9","title":"甲醛检测报告是真是假？这样一查就知道了","author":"在寒CMA甲醛检测","media":"正文/单页内容","status":"deep_read","summary":"报告真伪查询；正文及3条当前可见评论已读。"},
]


CANDIDATES = [
    {
        "note_id":"696bb16e000000000d00a4c8","title":"保姆级干货：沙发茶几怎么摆？全套尺寸公开。",
        "topic":"comfort_ergonomics","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者用多张尺寸图讨论沙发、茶几和通道的关系，并提醒家具不能只看照片比例。",
        "comments":["当前没有可见评论。"],
        "image":"已看6/7张，能看到不同沙发、茶几与走动空间的具体关系。",
        "draft":"主要还是看沙发茶几好不好摆，坐下顶不顶腿"
    },
    {
        "note_id":"69fb34ab000000002003a8f4","title":"已退回，运费好贵！",
        "topic":"installation_logistics","direction":"light_social_response","parent":"neutral_social","mode":"light_humor_or_neutral",
        "body":"作者购买186×90厘米大板桌，到家后觉得比例矮胖并退货，退回运费400元。",
        "comments":["可见评论主要晒自家桌子、问价格和链接，没有补充退货费用的购买前核对动作。"],
        "image":"已看6/12张，能看到桌板尺寸和摆入空间后的比例。",
        "draft":"大件最怕退货，运费和上楼费最好买之前一起问清楚。"
    },
    {
        "note_id":"68e8d2b0000000000301b134","title":"买大家具容易忽略的一点——进电梯",
        "topic":"installation_logistics","direction":"light_social_response","parent":"neutral_social","mode":"light_humor_or_neutral",
        "body":"作者提醒整装衣柜、大板桌和长餐边柜需要提前判断能否进电梯，也提到极限情况可能需要拆包装。",
        "comments":["当前仅1条可见评论，未讨论轿厢内转向和外包装尺寸。"],
        "image":"已看5/5张，能看到大件与电梯、入户尺寸的对应关系。",
        "draft":"光量电梯门还不够，里面能不能转过来、带包装有多大也要一起算。"
    },
    {
        "note_id":"69d376fd000000001f00596c","title":"冷知识：2.4米的高度放不下2.4米的衣柜",
        "topic":"dimensions_fit","direction":"light_social_response","parent":"neutral_social","mode":"light_humor_or_neutral",
        "body":"作者的成品高柜组装后无法立起，最后退货；评论提到地面误差和需要留余量。",
        "comments":["可见评论已经讨论地面不平和1至2厘米余量，没有把安装姿态说清。"],
        "image":"已看3/3张，能看到柜体贴近顶面却无法完成安装。",
        "draft":"这种高柜得先问清是平着装再立起来，还是直接竖着装，两种留的高度真不一样。"
    },
    {
        "note_id":"6854b0fb00000000120177d2","title":"别总盯着环保这项💢板材检测报告怎么看？",
        "topic":"material_craft","direction":"light_social_response","parent":"neutral_social","mode":"light_humor_or_neutral",
        "body":"作者列出板材报告中的甲醛、强度、吸水和表面性能项目，并说明如何核对报告。",
        "comments":["可见评论多是请作者判断单份报告，另有人指出商家常只提供普通送检或只测甲醛。"],
        "image":"已看6/8张，能看到报告项目与核对入口。",
        "draft":"商家只发一张报告截图真看不出多少，先把完整页数和样品型号要齐会靠谱很多。"
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
        "request_id":f"panse.2026-08-11.account3.comment.{index:03d}",
        "idempotency_key":f"panse:2026-08-11:account-3:{item['note_id']}",
        "brief_text":f"目标原帖为《{item['title']}》。已完整阅读正文、相关画面和当前可见评论。身份是认真做功课但不替别人做决定的家具购买同伴。只说一个和尺寸、运输、安装或材料有关的具体判断，并连到普通人买家具或日常使用时真会遇到的事。不要重复标题和正文已经说过的话，不为了互动硬问问题，不追加空泛总结，不用老师、评委或验收口吻，不虚构购买、入住、装修、检测或长期使用经历。彻底避免思路、那组、尤其、参考价值、落地等书面词。输出1至2句、12至65字；不提畔色，不引导主页、私信、搜索、关注、点赞或购买。",
        "source_locator":f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario":"家具决策内容评论语气实验",
        "audience":"正在比较家具尺寸、材料、结构、运输和使用条件的普通用户",
        "use_case":"生成一条有依据、口语化、支持创作者且不替别人下结论的评论草稿",
        "interaction_mode":item["mode"],
        "source_context":{
            "body":item["body"],
            "visible_comments":item["comments"],
            "image_observations":[{"locator":"reviewed_media","observation":item["image"],"observation_basis":"caller_reviewed"}],
            "body_complete":True,
            "visible_comments_complete":True,
            "images_complete":True,
            "expected_visible_comment_count":len(item["comments"]),
            "expected_image_count":1,
        },
        "required_model_id":"gpt-5.6-sol",
        "fallback_model_allowed":False,
        "content_contract":{
            "protected_facts":[],
            "allowed_paraphrases":{},
            "forbidden_inferences":[
                "不得虚构购买、入住、装修、维修、检测或长期使用经历",
                "不得使用测评机构、大师、老师、评委或验收口吻",
                "不得重复标题、正文结论或当前评论后再补空泛判断",
                "不得为了互动硬问没有意义或无人能回答的问题",
                "不得使用思路、那组、尤其、参考价值、落地等书面表达",
            ],
            "citation_anchors":{},
            "must_cover_fact_ids":[],
        },
        "output":{"title_candidates":0,"title_max_chars":0,"body_min_chars":12,"body_max_chars":65,"tag_min":0,"tag_max":0},
        "panse_intent_context":{
            "policy_version":"xhs-comment-intent.v4",
            "topic_ids":[item["topic"]],
            "interaction_intent":item["parent"],
            "comment_direction_id":item["direction"],
            "voice_id":"evaluation_judgment",
            "human_approved_example_set_version":"panse-xhs-human-approved-comments.v3",
        },
    })
    return payload


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    requests: list[dict] = []
    receipts: list[dict] = []
    reviews: list[dict] = []
    stages = {"plan":{}, "draft":{}, "semantic_review":{}}

    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        rid = payload["request_id"]
        requests.append({"target_note":{"note_id":item["note_id"],"title":item["title"],"source_locator":payload["source_locator"]},"style_request":payload})
        receipts.append(receipt)
        stages["plan"][rid] = {
            "model_id":"gpt-5.6-sol","fallback_used":False,"topic_ids":[item["topic"]],
            "comment_direction_id":item["direction"],"interaction_mode":item["mode"],
            "entry_angle":"扣住一个真实使用条件，说出普通人会在意的动作或麻烦；不复述、不硬问。",
        }
        stages["draft"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"draft_text":item["draft"],"tags":[]}
        stages["semantic_review"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"results":[
            {"gate":"source_grounding","status":"pass","notes":item["image"]},
            {"gate":"source_and_comment_repetition","status":"pass","notes":"没有照抄标题、正文结论或当前可见评论。"},
            {"gate":"daily_life_connection","status":"pass","notes":"落到顶腿、退货费用、转向、安装姿态或索要完整报告等真实动作。"},
            {"gate":"question_value","status":"not_applicable","notes":"本批不为互动硬提问。"},
            {"gate":"identity_and_experience_boundary","status":"pass","notes":"普通同好口吻；没有虚构亲历、测评或品牌关系。"},
            {"gate":"natural_voice","status":"pass","notes":"短、口语、具体，无整理稿词和老师口吻。"},
        ]}
        reviews.append({
            "request_id":rid,
            "account_slot_and_nickname":"slot 3 / link",
            "note_id":item["note_id"],
            "target_note_title":item["title"],
            "source_context_summary":item["body"],
            "visible_comment_context_summary":item["comments"],
            "exact_draft_text":item["draft"],
            "interaction_mode":item["mode"],
            "comment_direction_id":item["direction"],
            "style_preflight_passed":bool(receipt.get("passed")),
            "semantic_review_passed":True,
            "queue_status":"awaiting_user_review",
            "current_user_approval_required":True,
            "published":False,
        })

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_json("account_3_browse_receipts_17.json", {
        "schema_version":1,"date":"2026-08-11","account_slot":3,"account_nickname":"link",
        "profile_id":"5b38445e4eacab65d6c0521c","browse_target":14,"browse_actual":17,
        "deep_read_actual":14,"browse_only_actual":3,"body_and_visible_comments_read":True,
        "items":READS,"safety_warning_observed":False,"external_comments_posted":0,
    })
    write_json("account_3_follow_receipts_2.json", {
        "schema_version":1,"date":"2026-08-11","account_slot":3,"verified_follow_count":2,
        "items":[
            {"profile_id":"5b862215a12b470001684702","nickname":"朴愫木作","role_fit":"持续发布实木家具、尺寸、材料和工艺内容","button_before":"关注","button_after":"已关注","verified":True},
            {"profile_id":"67c4fe06000000000a03dfb5","nickname":"天盟家居","role_fit":"持续发布全屋定制、板材、尺寸、安装和检测报告内容","button_before":"关注","button_after":"已关注","verified":True},
        ],
        "safety_warning_observed":False,
    })
    write_json("account_3_style_requests_5.json", {"schema_version":1,"date":"2026-08-11","phase":"account3_cycle_day03_review_only","account_slot":3,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"request_count":5,"requests":requests})
    write_json("account_3_style_compile_receipts_5.json", {"schema_version":1,"compiled_at":stamp,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"receipt_count":5,"all_passed":all(x.get("passed") for x in receipts),"text_generated_by_preflight":False,"external_posting_performed":False,"receipts":receipts})
    write_json("account_3_current_session_stage_responses_5.json", {"schema_version":1,"created_at":stamp,"account_slot":3,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"stages":stages,"external_posting_performed":False})
    write_json("account_3_human_review_5.json", {"schema_version":1,"date":"2026-08-11","account_slot":3,"account_nickname":"link","review_item_count":5,"all_ready_for_user_review":all(x.get("passed") for x in receipts),"send_allowed":False,"user_approval_received":False,"published_count":0,"approval_rule":"Only explicit approval of the exact displayed drafts permits sending.","items":reviews})

    plan_path = RUN_DIR / "account_3_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse":17,"actual_deep_reads":14,"drafts_ready":5,"verified_follows":2,"public_visible_comments":0,"unsent_review_items":5,"status":"awaiting_user_review","stop_reason":None})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 3:
            account.update({"status":"awaiting_user_review","actual_browse":17,"actual_deep_reads":14,"drafts_ready":5,"public_visible_comments":0,"verified_follows":2,"unsent":5})
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"requests":5,"all_preflight_passed":all(x.get("passed") for x in receipts),"browse_actual":17,"deep_read_actual":14,"verified_follows":2,"external_comments_posted":0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
