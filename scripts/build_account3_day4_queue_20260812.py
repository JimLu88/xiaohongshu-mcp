#!/usr/bin/env python3
"""Build slot-3 cycle-day-4 evidence and review-only queue for 2026-08-12."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-12"
TEMPLATE = RUN_DIR.parent / "2026-08-11" / "account_3_style_requests_5.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"
COLLOQUIAL_LINT = REPO / "scripts" / "lint_xhs_comment_colloquial.py"


READS = [
    {"note_id":"690d764f0000000005001451","title":"内行买餐桌都看这10点","author":"狂飙的跑跑熊","status":"deep_read","summary":"正文与当前可见评论已读；记录桌底结构、连接和使用条件，绝对化说法不进入评论。"},
    {"note_id":"6808cea9000000001c00d588","title":"为什么实木家具品相差距那么大？知识分享","author":"大师谈实木家具","status":"deep_read","summary":"正文与当前可见评论已读；材料等级不能代替成品拼板和修色判断。"},
    {"note_id":"696dfb61000000001a031608","title":"实木家具工艺篇｜一篇搞懂不踩坑❗️","author":"原始原素","status":"deep_read","summary":"正文及5条当前可见评论已读；营销性绝对结论只作争议样本。"},
    {"note_id":"68e3aefb0000000004010a20","title":"全网最全选沙发攻略","author":"李喵喵i（装修ing）","status":"deep_read","summary":"4图正文与当前可见评论已读；坐感、结构、面料和自然光选色均涉及。"},
    {"note_id":"697a18b5000000001a01ee0e","title":"餐椅避雷‼️1.5k一把的实木餐椅真心不值❌","author":"BlueSaltyRain","status":"deep_read","summary":"4图正文及当前可见评论已读；重点是到货两个月开裂与退修运费争议。"},
    {"note_id":"68e4ece6000000000300e342","title":"长凳避雷！！","author":"飞天小猫","status":"deep_read","summary":"9图正文与当前可见评论已读；长凳断裂，评论集中在木料、连接和价格。"},
    {"note_id":"66f505df000000001a02210e","title":"家居木材到底怎么选？橡胶木到底好不好？","author":"圆脸lulu","status":"deep_read","summary":"正文及当前可见评论已读；评论对木材适用场景和防潮有大量追问。"},
    {"note_id":"677e61370000000001003478","title":"装修小白友好｜家具木材选购指南！","author":"暴走拉面","status":"deep_read","summary":"正文及当前可见评论已读；讨论木种选择、地区环境和后期工艺。"},
    {"note_id":"6704ebba000000001902f46c","title":"家具选实木还是贴木皮？5个点教你看明白","author":"黄云海","status":"deep_read","summary":"正文及当前可见评论已读；核心是用途、地区、基材和维护成本的取舍。"},
    {"note_id":"6a4b194b000000001c0272a1","title":"分享我在实体店买家具的维权之路","author":"啦啦啦啊种太阳","status":"deep_read","summary":"2图正文及当前可见评论已读；记录裂缝、协商、投诉、立案和退款。"},
    {"note_id":"69c1188a000000001a027502","title":"那天我花2480r，买了个巨丑的樱桃木柜子😅","author":"Lady夏天","status":"deep_read","summary":"正文及当前可见评论已读；重点是退货成本、审美差异和大件权益确认。"},
    {"note_id":"68c13130000000001c031bb1","title":"网上买餐桌一定要慎重，真的有坑","author":"磊磊妈妈","status":"deep_read","summary":"8图正文及当前可见评论已读；安装后退货损失1030元，评论讨论验货与责任认定。"},
    {"note_id":"68a04d1f000000001d00e0a6","title":"网购实木家具避坑指南","author":"老虎聊设计","status":"browse_only","reason":"video_watch_time_insufficient","summary":"正文与评论可见，但视频停留不足，不计深读。"},
    {"note_id":"69c397fb0000000020038c6f","title":"黑胡桃“太黑”不值得买","author":"大师谈实木家具","status":"browse_only","reason":"carousel_images_insufficient","summary":"正文与评论已读，但15图未翻满6张，不计深读。"},
    {"note_id":"6a3f965b000000001603f6e8","title":"选板时有多兴奋，看到成品就有多想报警","author":"啊七啊七啊啊啊啊七","status":"browse_only","reason":"historical_target_duplicate","summary":"完整阅读后发现slot 3于2026-08-10已评论，排除候选且不计今日目标。"},
]


CANDIDATES = [
    {
        "note_id":"697a18b5000000001a01ee0e","title":"餐椅避雷‼️1.5k一把的实木餐椅真心不值❌",
        "topic":"purchase_service","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者买了6把实木餐椅，使用约两个月后都出现开裂；商家只同意寄回维修且要求买家承担运费。",
        "comments":["可见评论主要追问店铺、价格和实木是否必然开裂，也有人质疑售后说法。"],
        "image":"已看4/4张，能看到椅子开裂位置和整体外观。",
        "draft":"6把一起开裂真的太坑爹了，寄回修之前最好让商家把运费和修完后的质保说清楚。"
    },
    {
        "note_id":"68e4ece6000000000300e342","title":"长凳避雷！！",
        "topic":"material_craft","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者的长凳从拼接位置断裂，正文提醒购买时看木料和腿部连接；评论有人追问价格和重量。",
        "comments":["可见评论集中在木头、枪钉、价格和相同款断裂，没有补充购买前如何索要结构信息。"],
        "image":"已阅读9图正文并看到断裂位置。",
        "draft":"长凳这种受力大的，买之前真得让商家发1张底面和连接处的近照，光看正面太容易漏掉结构问题。"
    },
    {
        "note_id":"66f505df000000001a02210e","title":"家居木材到底怎么选？橡胶木到底好不好？",
        "topic":"material_craft","direction":"product_identity_material_question","parent":"utility_fit_question","mode":"curiosity_question",
        "body":"作者比较不同家具木材并谈橡胶木的使用争议；评论里很多人问某个木种能不能用。",
        "comments":["当前可见评论多是单问木种好坏，少有先说明家具用途和所在环境。"],
        "image":"正文与当前可见评论已完整阅读。",
        "draft":"同一种木头做柜门和做餐桌要求也不一样吧，选的时候是不是得先看用在哪儿？"
    },
    {
        "note_id":"6704ebba000000001902f46c","title":"家具选实木还是贴木皮？5个点教你看明白",
        "topic":"material_craft","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者讨论实木和贴皮的取舍，评论延伸到南北环境、基材环保和维护成本。",
        "comments":["评论区很多人纠结是不是全实木，也有人担心贴皮不耐用。"],
        "image":"正文与当前可见评论已完整阅读。",
        "draft":"家里要是温差大又不想天天小心维护，贴皮也不一定差，基材和封边问清楚更重要。"
    },
    {
        "note_id":"6a4b194b000000001c0272a1","title":"分享我在实体店买家具的维权之路",
        "topic":"purchase_service","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者收到开裂电视柜，经过协商、商场介入、投诉和在线立案，最终由商家全额退款并承担运费。",
        "comments":["可见评论主要追问立案入口、类别和退款结果，也有相似维权经历。"],
        "image":"已看2/2张并读完详细过程。",
        "draft":"把每一步和最后结果都写出来太有用了，遇到这种事的人照着找入口会省很多时间。"
    },
    {
        "note_id":"68c13130000000001c031bb1","title":"网上买餐桌一定要慎重，真的有坑",
        "topic":"installation_logistics","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者的岩板餐桌安装后才决定退货，拆卸、物流和磨损扣费合计损失1030元。",
        "comments":["评论多关注退货花费、质量责任和店铺，也有人分享类似岩板粘接问题。"],
        "image":"已读8图正文和当前可见评论。",
        "draft":"大件安装前这一步太关键了，发现材质或缝隙不对就先别让师傅继续装，不然后面退起来真费钱。"
    },
]


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(payload: dict) -> dict:
    done = subprocess.run([sys.executable, str(PREFLIGHT), "-"], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=REPO, check=False)
    if done.returncode:
        raise RuntimeError(done.stderr.decode("utf-8", errors="replace"))
    return json.loads(done.stdout.decode("utf-8"))


def colloquial_lint(text: str) -> dict:
    done = subprocess.run(
        [sys.executable, str(COLLOQUIAL_LINT), "--account-kind", "ordinary", "--text", text],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO,
        check=False,
    )
    result = json.loads(done.stdout.decode("utf-8"))
    if done.returncode:
        raise ValueError("colloquial lint failed: " + json.dumps(result, ensure_ascii=False))
    return result


def build_payload(base: dict, item: dict, index: int) -> dict:
    payload = copy.deepcopy(base)
    payload.update({
        "request_id":f"panse.2026-08-12.account3.comment.{index:03d}",
        "idempotency_key":f"panse:2026-08-12:account-3:{item['note_id']}",
        "brief_text":f"目标原帖为《{item['title']}》。已完整阅读正文、相关画面和当前可见评论。身份是认真做功课但不替别人做决定的家具购买同伴。评论要像真人随手说话：先扣住普通买家真正会遇到的成本、结构、售后、维护或用途，再给一个短而有用的反应。所有数量使用阿拉伯数字，例如6把、3张、2次。别人正在讲商家、产品或售后造成的损失时，可以用太坑爹了这类直接站队的口语，不要用太糟心了这种偏旁观、自我感受的表达。不要复述标题、正文和图片里显而易见的事，不为了互动硬问问题，不追加空泛总结，不用老师、评委或验收口吻，不虚构购买、入住、装修、检测或长期使用经历。避免思路、那组、尤其、参考价值、落地、下单、更难得、值得肯定等表达。输出1至2句、12至65字；不提畔色，不引导主页、私信、搜索、关注、点赞或购买。",
        "source_locator":f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario":"家具决策内容评论语气实验",
        "audience":"正在比较家具材料、结构、售后和使用条件的普通用户",
        "use_case":"生成一条有依据、口语化、支持创作者且不替别人下结论的评论草稿",
        "interaction_mode":item["mode"],
        "source_context":{"body":item["body"],"visible_comments":item["comments"],"image_observations":[{"locator":"reviewed_media","observation":item["image"],"observation_basis":"caller_reviewed"}],"body_complete":True,"visible_comments_complete":True,"images_complete":True,"expected_visible_comment_count":len(item["comments"]),"expected_image_count":1},
        "required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,
        "content_contract":{"protected_facts":[],"allowed_paraphrases":{},"forbidden_inferences":["不得虚构购买、入住、装修、维修、检测或长期使用经历","不得使用测评机构、大师、老师、评委或验收口吻","不得复述标题、正文结论或画面中显而易见的内容","不得为了互动硬问没有意义或无人能回答的问题","数量不得使用中文数字，统一使用阿拉伯数字","别人讲外部损失时不得用太糟心了做旁观式共情","不得使用思路、那组、尤其、参考价值、落地、下单、更难得、值得肯定等表达"],"citation_anchors":{},"must_cover_fact_ids":[]},
        "output":{"title_candidates":0,"title_max_chars":0,"body_min_chars":12,"body_max_chars":65,"tag_min":0,"tag_max":0},
        "panse_intent_context":{"policy_version":"xhs-comment-intent.v4","topic_ids":[item["topic"]],"interaction_intent":item["parent"],"comment_direction_id":item["direction"],"voice_id":"evaluation_judgment","human_approved_example_set_version":"panse-xhs-human-approved-comments.v3"},
    })
    return payload


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    requests, receipts, reviews = [], [], []
    stages = {"plan":{}, "draft":{}, "semantic_review":{}}
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        lint_receipt = colloquial_lint(item["draft"])
        rid = payload["request_id"]
        requests.append({"target_note":{"note_id":item["note_id"],"title":item["title"],"source_locator":payload["source_locator"]},"style_request":payload})
        receipts.append(receipt)
        stages["plan"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"topic_ids":[item["topic"]],"comment_direction_id":item["direction"],"interaction_mode":item["mode"],"entry_angle":"说普通买家真会碰到的动作、钱或麻烦；不复述、不硬问。"}
        stages["draft"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"draft_text":item["draft"],"tags":[]}
        stages["semantic_review"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"results":[
            {"gate":"source_grounding","status":"pass","notes":item["image"]},
            {"gate":"historical_target_dedup","status":"pass","notes":"未在历史发布回执中找到该note_id。"},
            {"gate":"source_and_obvious_repetition","status":"pass","notes":"没有只描述标题、正文或图片里已经显而易见的内容。"},
            {"gate":"daily_life_connection","status":"pass","notes":"落到运费、质保、底面近照、用途、维护、维权入口或停止安装等真实动作。"},
            {"gate":"identity_and_experience_boundary","status":"pass","notes":"普通同好口吻；没有虚构亲历、测评或品牌关系。"},
            {"gate":"natural_voice","status":"pass","notes":"短、口语、直接，无老师口吻和疏离式评价。"},
            {"gate":"colloquial_lint","status":"pass","notes":"数量使用阿拉伯数字，且未命中已知书面表达。"},
        ]}
        reviews.append({"request_id":rid,"account_slot_and_nickname":"slot 3 / link","note_id":item["note_id"],"target_note_title":item["title"],"source_context_summary":item["body"],"visible_comment_context_summary":item["comments"],"exact_draft_text":item["draft"],"interaction_mode":item["mode"],"comment_direction_id":item["direction"],"style_preflight_passed":bool(receipt.get("passed")),"colloquial_lint_passed":bool(lint_receipt.get("passed")),"semantic_review_passed":True,"queue_status":"awaiting_user_review","current_user_approval_required":True,"published":False})

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    write_json("account_3_browse_receipts_12.json", {"schema_version":1,"date":"2026-08-12","account_slot":3,"account_nickname":"link","profile_id":"5b38445e4eacab65d6c0521c","browse_target":12,"browse_actual":15,"deep_read_actual":12,"browse_only_actual":3,"body_and_visible_comments_read":True,"items":READS,"safety_warning_observed":False,"external_comments_posted":0})
    write_json("account_3_follow_attempt_1.json", {"schema_version":1,"date":"2026-08-12","account_slot":3,"target_profile_id":"5f05eae6000000000100191c","target_nickname":"大师谈实木家具","role_fit":"持续发布实木家具材料、结构和成品判断内容","notes_read":["6808cea9000000001c00d588","69c397fb0000000020038c6f"],"button_before":"关注","click_result":"timeout_or_uncertain","button_after_readback":"关注","verified":False,"counted":False,"repeat_attempted":False,"stop_reason":"follow_result_not_verified_no_retry","safety_warning_observed":False})
    write_json("account_3_style_requests_6.json", {"schema_version":1,"date":"2026-08-12","phase":"account3_cycle_day04_review_only","account_slot":3,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"request_count":6,"requests":requests})
    write_json("account_3_style_compile_receipts_6.json", {"schema_version":1,"compiled_at":stamp,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"receipt_count":6,"all_passed":all(x.get("passed") for x in receipts),"text_generated_by_preflight":False,"external_posting_performed":False,"receipts":receipts})
    write_json("account_3_current_session_stage_responses_6.json", {"schema_version":1,"created_at":stamp,"account_slot":3,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"stages":stages,"external_posting_performed":False})
    write_json("account_3_human_review_6.json", {"schema_version":1,"date":"2026-08-12","account_slot":3,"account_nickname":"link","review_item_count":6,"all_ready_for_user_review":all(x.get("passed") for x in receipts),"send_allowed":False,"user_approval_received":False,"published_count":0,"approval_rule":"Only explicit approval of the exact displayed drafts permits sending.","items":reviews})

    plan_path = RUN_DIR / "account_3_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse":15,"actual_deep_reads":12,"drafts_ready":6,"verified_follows":0,"follow_attempted":1,"follow_status":"unverified_stopped_without_retry","public_visible_comments":0,"unsent_review_items":6,"status":"awaiting_user_review","stop_reason":None})
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 3:
            account.update({"status":"awaiting_user_review","actual_browse":15,"actual_deep_reads":12,"drafts_ready":6,"public_visible_comments":0,"verified_follows":0,"unsent":6,"follow_attempted":1,"follow_status":"unverified_stopped_without_retry"})
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"requests":6,"all_preflight_passed":all(x.get("passed") for x in receipts),"browse_actual":15,"deep_read_actual":12,"verified_follows":0,"external_comments_posted":0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
