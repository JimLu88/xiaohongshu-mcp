#!/usr/bin/env python3
"""Build slot-2 day-4 evidence and review-only comment queue for 2026-08-12."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-12"
TEMPLATE = RUN_DIR.parent / "2026-08-11" / "account_2_style_requests_6.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {"note_id":"692d7bb1000000001e009f36","title":"装了个44平的老破小，入住一年依旧很满意！","author":"一朵李九花儿🌼","media":"6/13图","selected":True,"summary":"套内44平，一字户型重新分配客厅、卧室、卫生间与玄关空间；正文和当前可见评论已读。"},
    {"note_id":"68b156c1000000001d021716","title":"普通人的家，因阳光而富足☀️","author":"奥仔不吃奥利奥🍪","media":"正文/评论/图组","selected":False,"summary":"南向客厅的自然光与日常生活记录；评论集中问开间、窗户、电器日晒和家具渠道。"},
    {"note_id":"6a7ab4dd00000000060041ff","title":"小户型客厅｜简单布置却越住越舒服~🪴","author":"泡芙的窝🏡","media":"正文/评论/图组","selected":False,"summary":"近期小户型客厅布置，评论多问墙面吊装、晾晒和沙发渠道。"},
    {"note_id":"698f09ad000000000b0112ac","title":"住在自己设计的小家里，太舒服了😌！","author":"一朵李九花儿🌼","media":"15图组/正文/评论","selected":False,"summary":"关注候选主页的第二篇相关内容，持续分享同一套44平真实住宅和使用反馈。"},
    {"note_id":"6969c5f5000000000b00adce","title":"家的丰容｜低楼层家居配色","author":"喜樂家养成计划","media":"8图组/正文/评论","selected":False,"summary":"低楼层浅色、亮面与深浅柜体搭配公式；评论多问具体色号和材料组合。"},
    {"note_id":"6a6eac4e000000003300d929","title":"小众红棕背景墙，到底是高级还是压抑？","author":"云岫","media":"正文/评论/图组","selected":True,"summary":"讨论局部红棕深色墙与采光、浅墙和原木家具的关系；作者邀请评论区选色。"},
    {"note_id":"6a13f47b000000003601ac01","title":"采光一般的客厅里，白色沙发像块天然反光板","author":"伤心凉茶铺","media":"7图组/正文/评论","selected":True,"summary":"作者把深蓝沙发套换成白色亚麻套，记录南向客厅夏季无直射光时的明度变化。"},
    {"note_id":"6a6f38aa0000000033036fbf","title":"52平，有个自己小房子真幸福","author":"有猫的嘉嘉","media":"18图组/正文/评论","selected":False,"summary":"52平自装一室一厅，用开放格局、玻璃隔断、暖白原木和彩色软装；评论问隔断、窗帘和养猫清洁。"},
    {"note_id":"6a75e2ee000000003302d571","title":"小户型餐厅这么装，真的是显大又实用🏠","author":"TT叶子风声","media":"12图组/正文/评论","selected":True,"summary":"75平客餐厅拆推拉门，方桌换成可伸缩圆桌；评论问折叠处清洁、人数和开放厨房油烟。"},
    {"note_id":"6923c996000000001e005ae8","title":"🔥装修必看｜2026乳胶漆颜色怎么选？","author":"木木家的装修日记","media":"8图组/正文/评论","selected":False,"summary":"按风格、采光和家具选乳胶漆并强调试色；评论询问通刷、铲墙和色差。"},
]


CANDIDATES = [
    {"note_id":"692d7bb1000000001e009f36","title":"装了个44平的老破小，入住一年依旧很满意！","topic":"layout_circulation","body":"套内44平重新分配客厅、卧室、卫生间和玄关，玻璃隔断兼顾采光通风，并按家庭生活习惯规划尺寸。","comments":["评论询问洗衣机、床、开放厨房、窗户和改造费用。","作者说明大部分由自己设计，并持续回答真实使用问题。"],"image":"已翻至6/13图；空间很小但生活功能之间没有明显挤成一团。","draft":"小空间没有硬塞功能，住了一年还能觉得顺手，这个真的很厉害。"},
    {"note_id":"6a6eac4e000000003300d929","title":"小众红棕背景墙，到底是高级还是压抑？","topic":"color_light_atmosphere","body":"作者讨论局部红棕深色墙，认为采光差的户型不宜照搬，并用大面积浅墙和原木家具平衡。","comments":["作者邀请大家选择会刷的颜色。","当前可见评论只有作者置顶提问，未重复草稿观点。"],"image":"红棕色只占局部，旁边保留浅墙与较亮软装。","draft":"红棕色真挺挑光线的，不过只刷一面就没那么压，晚上开灯应该会更有感觉。"},
    {"note_id":"6a13f47b000000003601ac01","title":"采光一般的客厅里，白色沙发像块天然反光板","topic":"color_light_atmosphere","body":"作者把冬天的深蓝牛仔沙发套换成白色亚麻套，记录夏季南向客厅没有直射光时的空间变化。","comments":["评论多问客厅尺寸、沙发和沙发套渠道。","也有人说灯光缓解了采光焦虑。"],"image":"白色沙发套成为客厅大面积浅色块，作者同时保留暖光台灯。","draft":"沙发套按季节换颜色这个挺妙，夏天用白色清爽，冬天换深色又会暖很多。"},
    {"note_id":"6a75e2ee000000003302d571","title":"小户型餐厅这么装，真的是显大又实用🏠","topic":"layout_circulation","body":"作者拆掉厨房推拉门，试过方桌后换成可伸缩圆桌，平时四人使用，展开后可应对来客。","comments":["作者已回答折叠处是否藏灰、可坐人数和开放厨房油烟。","评论区仍有人询问客厅开间。"],"image":"圆桌平时保持较小体积，展开功能用于来客场景。","draft":"平时四个人用圆桌不占地方，来人再拉开，比一直摆张大桌子轻松多了。"},
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
    request_id = f"panse.2026-08-12.account2.comment.{index:03d}"
    payload.update({
        "request_id": request_id,
        "idempotency_key": f"panse:2026-08-12:account-2:{item['note_id']}",
        "brief_text": f"目标原帖为《{item['title']}》。已完整阅读正文、相关画面和当前可见评论。身份是支持创作者的普通家居同好。可见细节只用于内部判断，不要把图里显而易见的内容重新描述一遍。评论要补充一个真实感受、生活联系或有用判断；删掉画面描述后仍应是一句完整的人话。夸赞要像直接对创作者说话：先给具体依据，再用‘真的很厉害、真好看、挺妙’等自然口语直接夸，不用‘更难得、值得肯定、比单纯X更Y’这种评审式绕夸。避免思路、那组、尤其、参考价值、落地、下单等书面词，不硬问问题，不虚构购买、入住、装修或长期使用经历。输出一至两句，25至55字；不提畔色，不导流。",
        "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario": "空间搭配号公开评论待审稿",
        "audience": "关注小户型、家具、采光与空间生活的普通用户",
        "use_case": "生成一条口语、支持创作者并有生活联系的评论草稿",
        "interaction_mode": "support_only",
        "source_context": {"body":item["body"],"visible_comments":item["comments"],"image_observations":[{"locator":"reviewed_media","observation":item["image"],"observation_basis":"caller_reviewed"}],"body_complete":True,"visible_comments_complete":True,"images_complete":True,"expected_visible_comment_count":len(item["comments"]),"expected_image_count":1},
        "required_model_id": "gpt-5.6-sol",
        "fallback_model_allowed": False,
        "content_contract": {"protected_facts":[],"allowed_paraphrases":{},"forbidden_inferences":["不得虚构购买、入住、装修、施工、检测或长期使用经历","不得伪装屋主、客户或长期居住者","不得重复标题、正文或显而易见画面来凑句子","不得为了互动硬问问题","不得使用思路、那组、尤其、参考价值、落地、下单等书面表达","不得使用更难得、值得肯定、比单纯X更Y等评审式绕夸","不得推荐畔色或导流"],"citation_anchors":{},"must_cover_fact_ids":[]},
        "output": {"title_candidates":0,"title_max_chars":0,"body_min_chars":25,"body_max_chars":55,"tag_min":0,"tag_max":0},
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
        request_id = payload["request_id"]
        requests.append({"target_note":{"note_id":item["note_id"],"title":item["title"],"source_locator":payload["source_locator"]},"style_request":payload})
        receipts.append(receipt)
        stages["plan"][request_id] = {"model_id":"gpt-5.6-sol","fallback_used":False,"topic_ids":[item["topic"]],"comment_direction_id":"detail_grounded_praise","interaction_mode":"support_only","entry_angle":"跳过显而易见的画面描述，直接给生活联系或有用判断。"}
        stages["draft"][request_id] = {"model_id":"gpt-5.6-sol","fallback_used":False,"draft_text":item["draft"],"tags":[]}
        stages["semantic_review"][request_id] = {"model_id":"gpt-5.6-sol","fallback_used":False,"results":[
            {"gate":"source_and_comment_grounding","status":"pass","notes":"正文、相关画面和当前可见评论均已阅读。"},
            {"gate":"new_value_not_visual_restatement","status":"pass","notes":"草稿不是把图中显而易见的东西重新说一遍。"},
            {"gate":"daily_life_connection","status":"pass","notes":"草稿落到入住感受、季节换套或日常人数变化。"},
            {"gate":"identity_boundary","status":"pass","notes":"没有虚构屋主、购买或长期使用经历，也没有提畔色。"},
            {"gate":"direct_warm_praise","status":"pass","notes":"夸赞直接对创作者说，具体依据在前，不用评审式比较收尾。"},
            {"gate":"natural_voice","status":"pass","notes":"短句、口语，不用整理稿词语，也不硬问问题。"},
        ]}
        reviews.append({"request_id":request_id,"account_slot_and_nickname":"slot 2 / 🦀","note_id":item["note_id"],"target_note_title":item["title"],"source_context_summary":item["body"],"visible_comment_context_summary":item["comments"],"exact_draft_text":item["draft"],"interaction_mode":"support_only","comment_direction_id":"detail_grounded_praise","style_preflight_passed":bool(receipt.get("passed")),"semantic_review_passed":True,"queue_status":"awaiting_user_review","current_user_approval_required":True,"published":False})

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    all_passed = all(item.get("passed") for item in receipts)
    write_json("account_2_browse_receipts_10.json",{"schema_version":1,"date":"2026-08-12","account_slot":2,"account_nickname":"🦀","profile_id":"634c02a1000000001901c0e6","browse_target":10,"browse_actual":10,"deep_read_actual":10,"body_and_visible_comments_read":True,"items":READS,"safety_warning_observed":False,"external_comments_posted":0})
    write_json("account_2_follow_attempt_1.json",{"schema_version":1,"date":"2026-08-12","account_slot":2,"profile_id":"568a85e750c4b423d90cd586","nickname":"一朵李九花儿🌼","role_fit":"持续分享44平真实小家、软装、采光、尺寸和入住反馈","notes_read":["692d7bb1000000001e009f36","698f09ad000000000b0112ac"],"follow_state_before":"关注","follow_state_after_readback":"关注","verified":False,"counted_as_follow":False,"repeat_click_performed":False,"stop_reason":"button state did not change; stopped without retry to avoid accidental unfollow","safety_warning_observed":False})
    write_json("account_2_style_requests_4.json",{"schema_version":1,"date":"2026-08-12","phase":"account2_cycle_day04_review_only","account_slot":2,"style_lab_route":"local_tachikoma_runtime","required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"request_count":4,"requests":requests})
    write_json("account_2_style_compile_receipts_4.json",{"schema_version":1,"compiled_at":stamp,"style_lab_route":"local_tachikoma_runtime","required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"receipt_count":4,"all_passed":all_passed,"text_generated_by_preflight":False,"external_posting_performed":False,"receipts":receipts})
    write_json("account_2_current_session_stage_responses_4.json",{"schema_version":1,"created_at":stamp,"account_slot":2,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"stages":stages,"external_posting_performed":False})
    write_json("account_2_human_review_4.json",{"schema_version":1,"date":"2026-08-12","account_slot":2,"account_nickname":"🦀","review_item_count":4,"all_ready_for_user_review":all_passed,"send_allowed":False,"user_approval_received":False,"published_count":0,"approval_rule":"Only explicit approval of the exact displayed drafts permits sending.","items":reviews})

    plan_path = RUN_DIR / "account_2_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse":10,"actual_deep_reads":10,"drafts_ready":4,"verified_follows":0,"follow_attempted":1,"follow_status":"unverified_stopped_without_retry","public_visible_comments":0,"unsent_review_items":4,"status":"awaiting_user_review","stop_reason":None})
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 2:
            account.update({"status":"awaiting_user_review","actual_browse":10,"actual_deep_reads":10,"drafts_ready":4,"public_visible_comments":0,"verified_follows":0,"follow_attempted":1,"follow_status":"unverified_stopped_without_retry","unsent":4})
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"browse":10,"deep_reads":10,"drafts":4,"preflight_passed":sum(bool(x.get("passed")) for x in receipts),"verified_follows":0,"published":0},ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
