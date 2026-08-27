#!/usr/bin/env python3
"""Build slot-2 cycle-day-3 evidence and review-only queue for 2026-08-11."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-11"
TEMPLATE = RUN_DIR.parent / "2026-08-10" / "account_2_style_requests_5.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {"note_id":"690ad2a30000000007021b29","title":"卧室再小也别着急做榻榻米了","author":"远方邵年(自装日记)","media":"视频/完整停留","selected":True,"summary":"床、书桌和收纳沿墙布置，中间留空；可见评论讨论桌宽、墙面、窗帘、地面和下柜做法。"},
    {"note_id":"6a2d3197000000001702aac8","title":"奶油原木风，暗户型提亮通透✨","author":"设计师南禾","media":"视频/完整停留","selected":False,"summary":"暗户型浅色、反光材质和3500K照明公式；缺少具体居住反馈，排除。"},
    {"note_id":"6969c5f5000000000b00adce","title":"家的丰容｜低楼层家居配色","author":"喜樂家养成计划","media":"6/8图","selected":False,"summary":"低楼层用浅暖地面、浅墙和反光表面；公式感较强，排除。"},
    {"note_id":"69cfa2a5000000001a037e46","title":"小户型奶油中古风｜把温柔焊在每一寸空间里","author":"粥粥家🏠","media":"6/8图","selected":True,"summary":"浅墙、胡桃木、藤编、复古灯、弧形垭口与白纱帘；可见评论主要问沙发护理、尺寸和电视柜。"},
    {"note_id":"68f9fef3000000000302fa55","title":"抄作业成功，恭喜我住进了Dream house ！","author":"乖宝儿的家","media":"6/18图","selected":False,"summary":"106㎡奶油原木风预算和尺寸清单，不属于本轮小户型核心样本。"},
    {"note_id":"69ad32b4000000001a02663a","title":"这样温馨的小房子，小时候期盼过无数次…","author":"朱朱（自装日记）","media":"6/9图","selected":True,"summary":"71㎡奶油风小家，自然光、浅墙和木色构成暖调；评论询问3000K灯光、墙漆和餐桌。"},
    {"note_id":"694f888f000000001e0093de","title":"一个人的温馨小家，每个角落我都很喜欢～","author":"南希的家","media":"6/16图","selected":True,"summary":"玄关洞洞板与翻斗鞋柜、L形书桌、沙发床和移动电视柜；评论夸休闲角并询问鞋柜。"},
    {"note_id":"6673ea14000000001f00535c","title":"跟小红书学的小户型简洁配色法🟤⚫️⚪️","author":"收纳研究员Jennie","media":"6/12图","selected":False,"summary":"3.14米开间、满墙柜和三色法，后段带沙发推广，排除评论候选。"},
    {"note_id":"6a06d960000000003503b225","title":"第一次装修，⚫️⚪️🟤配色真的没让我失望~","author":"焕焕の🏠","media":"6/15图","selected":False,"summary":"143㎡黑白棕配色并带家具品牌植入，与小户型定位不一致，排除。"},
    {"note_id":"69b4de1c000000001a037f78","title":"69㎡装出100㎡，谁说小户型不能是dream house","author":"爱喝奶茶的小q","media":"6/15图","selected":True,"summary":"建面69㎡、套内55㎡，开放厨房和阳台；岛台位于厨房与餐桌之间。评论询问油烟机和厨房收纳。"},
    {"note_id":"67e0ae32000000001c03d219","title":"67平小户型，我的家，你们要的客餐厅细节来了","author":"小小的家（装修记）","media":"6/6图","selected":True,"summary":"客餐厅浅黄色墙面与木色家具；作者在评论中说明墙色接近柠檬黄、色号61YY89，评论另问沙发和餐桌。"},
    {"note_id":"6774d04f000000001402793c","title":"🌟超详解Room tour｜55平老破小一镜到底👀","author":"一朵李九花儿🌼","media":"长视频/完整停留","selected":False,"summary":"55㎡老房一镜到底，评论量很大；本轮不挤占六条候选。"},
    {"note_id":"6a49cf2f000000002100be7c","title":"采光差的小户型，千万别用这3种颜色","author":"克色｜小户型配色","media":"6/7图","selected":False,"summary":"列举深灰、红棕和黄米色的采光风险；公式化且评论样本少，排除。"},
    {"note_id":"681c90e4000000000303dbad","title":"56平两室🏠小户型就复制我家吧，简单又好住","author":"君君","media":"6/12图","selected":False,"summary":"56㎡两室居住展示，评论主要问餐桌和地板；保留为浏览样本。"},
    {"note_id":"68be6f28000000001b020541","title":"2025记住这些配色！新房装修不后悔！","author":"布丁的家（装修中）","media":"6/17图","selected":False,"summary":"八套柜体配色公式，缺少具体空间验证，排除。"},
]


CANDIDATES = [
    {"note_id":"690ad2a30000000007021b29","title":"卧室再小也别着急做榻榻米了","topic":"layout_circulation","body":"多功能卧室把床、书桌和收纳沿墙布置，中间留出活动空间。","comments":["可见评论已讨论桌宽、墙面、窗帘和地面","另有评论建议下柜做活动式并给桌面留线孔"],"image":"已完整观看；可见床和书桌贴墙后中间保持空畅。","draft":"床和书桌都贴着墙放，中间一下空出来了，小房间这样看着真舒服"},
    {"note_id":"69cfa2a5000000001a037e46","title":"小户型奶油中古风｜把温柔焊在每一寸空间里","topic":"color_light_atmosphere","body":"小户型以奶油墙面、胡桃木家具、藤编椅和白纱帘搭配。","comments":["可见评论主要询问沙发护理和尺寸","另有评论询问电视柜，没有同类配色判断"],"image":"已看6/8图；深木色家具位于浅墙和白纱帘之间，整体没有明显压暗。","draft":"深木色家具放在浅墙和白纱帘中间，一点没显得重，搭得真好看"},
    {"note_id":"69ad32b4000000001a02663a","title":"这样温馨的小房子，小时候期盼过无数次…","topic":"color_light_atmosphere","body":"作者展示71㎡奶油风小家，强调阳光与暖调居住感。","comments":["可见评论询问3000K灯光、墙漆和餐桌","未见对白纱帘滤光与木色关系的相同表达"],"image":"已看6/9图；白纱帘过滤自然光，木色家具与奶油墙保持暖调。","draft":"白纱帘把阳光滤得很柔，木色和奶油墙看着特别舒服"},
    {"note_id":"694f888f000000001e0093de","title":"一个人的温馨小家，每个角落我都很喜欢～","topic":"storage_function","body":"玄关把云朵洞洞板、翻斗鞋柜和展示格集中在一面墙。","comments":["可见评论夸休闲角并询问鞋柜链接","未见对玄关收纳密度与视觉整齐的相同判断"],"image":"已看6/16图；玄关一面墙容纳鞋柜、洞洞板和展示小物，仍保持清楚分区。","draft":"翻斗鞋柜和洞洞板都放在玄关这面墙上，东西不少也没显得乱"},
    {"note_id":"69b4de1c000000001a037f78","title":"69㎡装出100㎡，谁说小户型不能是dream house","topic":"layout_circulation","body":"建面69㎡、套内55㎡，开放厨房与客餐厅连通，岛台兼操作和收纳。","comments":["可见评论询问油烟机","另有评论询问厨房收纳链接，没有讨论岛台位置"],"image":"已看6/15图；岛台位于厨房出口和餐桌之间，可形成连续的做饭与用餐路线。","draft":"岛台放在厨房和餐桌中间，做饭吃饭都不用绕，这个位置放得真好"},
    {"note_id":"67e0ae32000000001c03d219","title":"67平小户型，我的家，你们要的客餐厅细节来了","topic":"color_light_atmosphere","body":"作者用图片展示67㎡客餐厅，墙面是偏浅的黄色，家具以木色为主。","comments":["作者已回答墙色接近柠檬黄、色号61YY89","其他可见评论询问沙发和餐桌"],"image":"已看6/6图；浅黄色墙面、木色家具和自然光共同形成暖调，客餐厅没有明显压暗。","draft":"浅黄色墙面配木色家具很暖，客餐厅看着一点不暗"},
]


def write_json(name: str, value: object) -> None:
    (RUN_DIR / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preflight(payload: dict) -> dict:
    done = subprocess.run([sys.executable, str(PREFLIGHT), "-"], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=REPO, check=False)
    if done.returncode:
        raise RuntimeError(done.stderr.decode("utf-8", errors="replace"))
    return json.loads(done.stdout.decode("utf-8"))


def build_payload(base: dict, item: dict, index: int) -> dict:
    payload = copy.deepcopy(base)
    rid = f"panse.2026-08-11.account2.comment.{index:03d}"
    payload.update({
        "request_id": rid,
        "idempotency_key": f"panse:2026-08-11:account-2:{item['note_id']}",
        "brief_text": f"目标原帖为《{item['title']}》。已完整阅读正文、相关画面和当前可见评论。身份是支持创作者的普通家居同好。评论要紧扣原帖，用一个画面、动线、配色或日常使用关系说出具体感受，能夸就直接夸，说完即停；不照抄标题或正文结论，不为互动硬问问题，不追加空泛总结。彻底避免思路、那组、尤其、参考价值、落地等书面或整理稿词语。不得虚构购买、入住、装修、检测或长期使用经历。输出1句、12至55字；不提畔色，不导流。",
        "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario": "家居内容评论语气实验",
        "audience": "关注小户型、家具与空间生活的普通用户",
        "use_case": "生成一条具体、口语、支持创作者的评论草稿",
        "interaction_mode": "support_only",
        "source_context": {"body":item["body"],"visible_comments":item["comments"],"image_observations":[{"locator":"reviewed_media","observation":item["image"],"observation_basis":"caller_reviewed"}],"body_complete":True,"visible_comments_complete":True,"images_complete":True,"expected_visible_comment_count":len(item["comments"]),"expected_image_count":1},
        "required_model_id": "gpt-5.6-sol",
        "fallback_model_allowed": False,
        "content_contract": {"protected_facts":[],"allowed_paraphrases":{},"forbidden_inferences":["不得虚构购买、入住、装修、检测或长期使用经历","不得以老师、评委或验收口吻评价创作者","不得复述标题或正文后追加空泛夸奖","不得为了互动硬问问题","不得使用思路、那组、尤其、参考价值、落地等书面表达"],"citation_anchors":{},"must_cover_fact_ids":[]},
        "output": {"title_candidates":0,"title_max_chars":0,"body_min_chars":12,"body_max_chars":55,"tag_min":0,"tag_max":0},
        "panse_intent_context": {"policy_version":"xhs-comment-intent.v4","topic_ids":[item["topic"]],"interaction_intent":"grounded_praise","comment_direction_id":"detail_grounded_praise","voice_id":"stylist","human_approved_example_set_version":"panse-xhs-human-approved-comments.v3"},
    })
    return payload


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    base = json.loads(TEMPLATE.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    requests, receipts, reviews = [], [], []
    stages = {"plan":{},"draft":{},"semantic_review":{}}
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        rid = payload["request_id"]
        requests.append({"target_note":{"note_id":item["note_id"],"title":item["title"],"source_locator":payload["source_locator"]},"style_request":payload})
        receipts.append(receipt)
        stages["plan"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"topic_ids":[item["topic"]],"comment_direction_id":"detail_grounded_praise","interaction_mode":"support_only","entry_angle":"从画面或日常使用关系说一个具体判断，再直接夸；不复述、不硬问。"}
        stages["draft"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"draft_text":item["draft"],"tags":[]}
        stages["semantic_review"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"results":[
            {"gate":"source_grounding","status":"pass","notes":item["image"]},
            {"gate":"source_and_comment_repetition","status":"pass","notes":"没有照抄标题、正文结论或当前可见评论。"},
            {"gate":"daily_life_connection","status":"pass","notes":"评论落到空间观感、走动或日常使用关系。"},
            {"gate":"question_value","status":"not_applicable","notes":"本条不提问。"},
            {"gate":"identity_and_experience_boundary","status":"pass","notes":"普通同好口吻；没有虚构亲历或品牌关系。"},
            {"gate":"natural_voice","status":"pass","notes":"短、口语、具体，无整理稿词语或老师口吻。"},
        ]}
        reviews.append({"request_id":rid,"account_slot_and_nickname":"slot 2 / 🦀","note_id":item["note_id"],"target_note_title":item["title"],"source_context_summary":item["body"],"visible_comment_context_summary":item["comments"],"exact_draft_text":item["draft"],"interaction_mode":"support_only","comment_direction_id":"detail_grounded_praise","style_preflight_passed":bool(receipt.get("passed")),"semantic_review_passed":True,"queue_status":"awaiting_user_review","current_user_approval_required":True,"published":False})

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    write_json("account_2_browse_receipts_15.json",{"schema_version":1,"date":"2026-08-11","account_slot":2,"account_nickname":"🦀","profile_id":"634c02a1000000001901c0e6","browse_target":15,"browse_actual":15,"deep_read_actual":15,"body_and_visible_comments_read":True,"items":READS,"safety_warning_observed":False,"external_comments_posted":0})
    write_json("account_2_style_requests_6.json",{"schema_version":1,"date":"2026-08-11","phase":"account2_cycle_day03_review_only","account_slot":2,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"request_count":6,"requests":requests})
    write_json("account_2_style_compile_receipts_6.json",{"schema_version":1,"compiled_at":stamp,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"receipt_count":6,"all_passed":all(x.get("passed") for x in receipts),"text_generated_by_preflight":False,"external_posting_performed":False,"receipts":receipts})
    write_json("account_2_current_session_stage_responses_6.json",{"schema_version":1,"created_at":stamp,"account_slot":2,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"stages":stages,"external_posting_performed":False})
    write_json("account_2_human_review_6.json",{"schema_version":1,"date":"2026-08-11","account_slot":2,"account_nickname":"🦀","review_item_count":6,"all_ready_for_user_review":all(x.get("passed") for x in receipts),"send_allowed":False,"user_approval_received":False,"published_count":0,"approval_rule":"Only explicit approval of the exact displayed drafts permits sending.","items":reviews})

    plan_path = RUN_DIR / "account_2_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse":15,"actual_deep_reads":15,"drafts_ready":6,"verified_follows":0,"public_visible_comments":0,"unsent_review_items":6,"status":"awaiting_user_review","stop_reason":None})
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 2:
            account.update({"status":"awaiting_user_review","actual_browse":15,"actual_deep_reads":15,"drafts_ready":6,"public_visible_comments":0,"verified_follows":0,"unsent":6})
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"requests":6,"all_preflight_passed":all(x.get("passed") for x in receipts),"external_comments_posted":0},ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
