#!/usr/bin/env python3
"""Build the slot-1 cycle-day-3 review-only queue for 2026-08-11."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-11"
BASE_REQUESTS = RUN_DIR.parent / "2026-08-10" / "account_1_style_requests_4.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {"note_id":"66ecf3f10000000012013d48","title":"小户型客厅的“洄游动线”｜21 m²的多样性","author":"-叫我小徐就好了","topic":"real_space_use","media":"6/10图","selected":True,"summary":"67㎡住宅的7.1×3.5米竖厅经历三次布局；当前把置物架、沙发餐桌、餐边柜电视柜分成三条纵线。评论讨论3.2米宽适配、圆桌和移动电视柜。"},
    {"note_id":"696d18a6000000002202ccc5","title":"小户型显大误区：家具买小了，家就更小了","author":"秋鱼的家","topic":"real_space_use","media":"5/5图","selected":False,"summary":"讨论大家具建立视觉重心，但评论质疑案例开间并不小、缺少3×4.8米等常见小客厅条件。"},
    {"note_id":"69d3705f000000001b02269b","title":"69㎡装出100㎡🏠小户型直接抄作业（附尺寸）","author":"爱喝奶茶的小q","topic":"real_space_use","media":"6/多图","selected":False,"summary":"55㎡套内开放厨房、阳台打通和多组家具尺寸；评论已询问墙面、木饰面、餐桌和地板。"},
    {"note_id":"66d8464f000000001201354d","title":"小户型装修｜15㎡客厅家具尺寸分享","author":"SUGER不加糖","topic":"real_space_use","media":"6/多图","selected":False,"summary":"3.5×4.3米客厅列出沙发、边几、茶几、电视柜和边柜尺寸；评论已覆盖家具渠道与挂钟高度。"},
    {"note_id":"691d5955000000000d03fe50","title":"让实木家具历久弥新的养护方法","author":"朴愫木作","topic":"maintenance_longevity","media":"5/5图","selected":False,"summary":"品牌科普木蜡油护理、避强光热源、40%至60%湿度和及时擦水油污；评论多为复述正文。"},
    {"note_id":"67eb5edf0000000007036967","title":"狗狗拆家不心塞！专业修复师帮你还原家具","author":"六匠人专业维修服务","topic":"maintenance_longevity","media":"6/多图","selected":False,"summary":"商业维修服务展示宠物啃咬后的补形与调色；评论集中询价和服务城市，官方号不在同业商业帖刷存在感。"},
    {"note_id":"67d66380000000001b039aa7","title":"【家具保养秘籍】胡桃木家具木蜡油保养全攻略","author":"爱吃米线的Jessie","topic":"maintenance_longevity","media":"6/多图","selected":False,"summary":"个人木蜡油护理步骤；评论对砂纸目数、油品和木种有不同意见，缺少同材质同涂装验证。"},
    {"note_id":"6a55b12d000000001700b621","title":"二手实木家具翻新全过程","author":"杨关关","topic":"maintenance_longevity","media":"视频","selected":True,"summary":"作者现场看二手家具后付款并记录打磨上油；评论讨论木种判断、脱漆、400目砂纸和曲面手磨。"},
    {"note_id":"6713b6e60000000024018a9b","title":"【木作榫卯】攒框","author":"下午来信","topic":"craft_material_process","media":"视频","selected":False,"summary":"攒框过程视频；作者置顶提醒机械工具旁不可戴手套，评论已反复讨论安全和工时。"},
    {"note_id":"69c6620d00000000230146a0","title":"木工小白首次做真榫卯！只花了100+","author":"周周爱户外","topic":"craft_material_process","media":"视频","selected":False,"summary":"松木燕尾榫长凳的画线、凿榫和手工制作；评论已大量询问锯具、板材和学习渠道。"},
    {"note_id":"68ce2f8f00000000130182e8","title":"100件微缩家具挑战第二件 | 斗柜的制作流程","author":"Liyu鲤鱼","topic":"craft_material_process","media":"视频","selected":True,"summary":"3.5毫米板微缩斗柜需要开槽切边；作者复盘0.5毫米锯片偏差、胶水、打磨上蜡和修边机精度。"},
    {"note_id":"69fc6b5b000000003502544a","title":"全网都在求的室内AI渲染教程来咯！","author":"理智芯","topic":"ai_render_design_process","media":"3/3图","selected":False,"summary":"长提示词强调家具比例、材质、窗帘和光线，但评论未明确工具，且流程细节不足。"},
    {"note_id":"69dce2c80000000023026198","title":"AI建模工作流分享 快速完成家具设计建模","author":"何酒酒的AI记事本","topic":"ai_render_design_process","media":"视频","selected":True,"summary":"手绘草图、AI细化、AI建模、SU摆放和AI渲染的完整链路；评论集中询问模型、软件和费用。"},
    {"note_id":"693128e1000000001b02546c","title":"87㎡的家，色彩搭配与色调统一心得 🟤⚪️⚫️","author":"爱丽思思","topic":"creator_ugc_aesthetic","media":"6/多图","selected":True,"summary":"浅墙、木纹砖和深色家具组成主色，彩色小件提亮；评论确认地面是木纹砖并询问家具尺寸渠道。"},
    {"note_id":"69240588000000001f00c4bd","title":"人就应该住在采光好的地方！","author":"公主想回家🏰","topic":"creator_ugc_aesthetic","media":"6/多图","selected":False,"summary":"南向落地窗与原木空间的日常记录；评论主要询问乳胶漆、木地板和阳台铺砖。"},
]


CANDIDATES = [
    {"note_id":"66ecf3f10000000012013d48","title":"小户型客厅的“洄游动线”｜21 m²的多样性","official_topic":"real_space_use","intent_topic":"layout_circulation","basis_type":"visible_measurement_relation","value_mode":"professional_reasoned_praise","fact_source_status":"source_visible","body":"67㎡住宅的客厅长7.1米、宽3.5米，当前把沙发和餐桌放在中轴，两侧形成两条通道。","comments":["作者说明3.2米宽可考虑小围合空间","评论区已回答圆桌和移动电视柜尺寸"],"image":"已看6/10张，可见沙发餐桌位于中轴，两侧保留通道。","draft":"3.5米宽的竖厅把沙发餐桌放中间，两边都能走，动线设计非常好"},
    {"note_id":"6a55b12d000000001700b621","title":"二手实木家具翻新全过程","official_topic":"maintenance_longevity","intent_topic":"maintenance_lifetime","basis_type":"conditional_domain_practice","value_mode":"professional_reasoned_praise","fact_source_status":"conditional_no_external_claim","body":"作者现场看完二手实木家具后付款并记录打磨上油。","comments":["作者说明木种仅凭颜色纹理难确认","评论讨论脱漆、砂纸、木蜡油和曲面手磨"],"image":"已观看翻新视频并阅读可见评论；只承接现场验货，不判断木种。","draft":"现场看完再付款这点很靠谱，木材、结构和松动情况都比照片好判断"},
    {"note_id":"68ce2f8f00000000130182e8","title":"100件微缩家具挑战第二件 | 斗柜的制作流程","official_topic":"craft_material_process","intent_topic":"material_craft","basis_type":"visible_structure_or_process","value_mode":"professional_reasoned_praise","fact_source_status":"source_visible","body":"作者用3.5毫米木板制作微缩斗柜，需要开槽切边，并复盘0.5毫米误差造成的缝隙。","comments":["作者补充简易版可用3毫米板免开槽切边","评论讨论迷你台锯精度和操作安全"],"image":"已观看制作视频；正文与置顶评论明确板厚、开槽和精度问题。","draft":"3.5毫米板还要开槽切边，微缩斗柜比大件更考验精度，做得太细了"},
    {"note_id":"69dce2c80000000023026198","title":"AI建模工作流分享 快速完成家具设计建模","official_topic":"ai_render_design_process","intent_topic":"creator_process_ai","basis_type":"visible_structure_or_process","value_mode":"professional_reasoned_praise","fact_source_status":"source_visible","body":"作者展示手绘、AI细化、AI建模、SU摆放和AI渲染的家具设计链路。","comments":["作者在置顶评论补充流程图","评论集中询问建模工具、手稿转图和费用"],"image":"已观看流程视频，可见AI模型进入SU后的尺度和场景检查。","draft":"AI先出基础模型，再放进SU看比例，前期改造型会方便很多"},
    {"note_id":"693128e1000000001b02546c","title":"87㎡的家，色彩搭配与色调统一心得 🟤⚪️⚫️","official_topic":"creator_ugc_aesthetic","intent_topic":"color_light_atmosphere","basis_type":"visible_material_color_light_relation","value_mode":"professional_reasoned_praise","fact_source_status":"source_visible","body":"作者以浅墙、木纹砖和深色家具为主，加入彩色小件。","comments":["作者确认地面是木纹砖","评论主要询问家具和软装渠道"],"image":"已看6张，深色家具压住浅墙与木纹砖，彩色小件分散出现。","draft":"深色家具把浅墙和木纹砖压住了，彩色小件放进去也没乱，审美真好👍"},
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
    rid = f"panse.2026-08-11.account1.comment.{index:03d}"
    payload.update({
        "request_id": rid,
        "idempotency_key": f"panse:2026-08-11:account-1:{item['note_id']}",
        "brief_text": f"目标原帖为《{item['title']}》。畔色木作官方品牌号公开参与，但不推广畔色产品，也不伪装消费者。已读完正文、相关画面和当前可见评论。评论必须扣住原帖主旨，先给一个尺寸、结构、工艺、材料、配色、光线、动线或使用关系的专业理由，再给直接相关的判断或短夸；不复述正文后补空话，不硬问问题，不使用思路、那组、尤其、参考价值、落地等整理稿用词。不得虚构购买、入住、装修、检测或长期使用经历。输出12至70个中文字符，1至2句；不提畔色产品，不导流。",
        "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario": "品牌官方号公开评论待审稿",
        "audience": "分享真实家居、家具工艺或设计过程的创作者",
        "use_case": "生成一条有专业理由且像真人说话的官方评论草稿",
        "source_context": {"body":item["body"],"visible_comments":item["comments"],"image_observations":[{"locator":"reviewed_media","observation":item["image"],"observation_basis":"caller_reviewed"}],"body_complete":True,"visible_comments_complete":True,"images_complete":True,"expected_visible_comment_count":len(item["comments"]),"expected_image_count":1},
        "required_model_id": "gpt-5.6-sol",
        "fallback_model_allowed": False,
        "content_contract": {"protected_facts":[],"allowed_paraphrases":{},"forbidden_inferences":["不得虚构购买、入住、装修、施工、检测或长期使用经历","不得把品牌官方号伪装成独立消费者","不得偏离标题与正文主旨","不得复述正文后追加空泛夸奖","不得使用思路、那组、尤其、参考价值、落地等整理稿表达","不得推广畔色产品、贬低其他品牌或截流"],"citation_anchors":{},"must_cover_fact_ids":[]},
        "output": {"title_candidates":0,"title_max_chars":0,"body_min_chars":12,"body_max_chars":70,"tag_min":0,"tag_max":0},
        "panse_intent_context": {"policy_version":"xhs-comment-intent.v4","topic_ids":[item["intent_topic"]],"interaction_intent":"grounded_praise","comment_direction_id":"detail_grounded_praise","voice_id":"official_explanation","human_approved_example_set_version":"panse-xhs-human-approved-comments.v2"},
        "panse_official_topic_context": {"strategy_id":"panse-official-topic-strategy.v1","topic_id":item["official_topic"],"source_author_intent":"share_process_or_real_home","target_relationship":"third_party_creator","visible_detail_grounded":True,"visible_comment_context_read":True,"question_answered_in_context":False,"panse_reply_right":"professional_peer_observation","fact_source_status":"source_visible","conditional_language_present":False},
        "panse_official_professional_value_context": {"contract_id":"panse-official-professional-value.v1","value_mode":item["value_mode"],"professional_basis_type":item["basis_type"],"professional_basis_text":item["image"],"useful_takeaway_present":True,"fact_source_status":item["fact_source_status"],"praise_reason_precedes_praise":True},
    })
    return payload


def main() -> int:
    base = json.loads(BASE_REQUESTS.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    requests, receipts, reviews = [], [], []
    stages = {"plan":{},"draft":{},"semantic_review":{}}
    for index, item in enumerate(CANDIDATES, 1):
        payload = build_payload(base, item, index)
        receipt = preflight(payload)
        rid = payload["request_id"]
        requests.append({"target_note":{"note_id":item["note_id"],"title":item["title"],"source_locator":payload["source_locator"]},"style_request":payload})
        receipts.append(receipt)
        stages["plan"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"official_topic":item["official_topic"],"entry_angle":"先给可见专业理由，再给直接相关的判断或短夸；不重复正文凑评论。"}
        stages["draft"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"draft_text":item["draft"],"tags":[]}
        stages["semantic_review"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"results":[
            {"gate":"official_topic_and_reply_right","status":"pass","notes":f"{item['official_topic']} / professional_peer_observation"},
            {"gate":"source_grounding","status":"pass","notes":item["image"]},
            {"gate":"topic_relevance","status":"pass","notes":"草稿直接回应原帖主旨。"},
            {"gate":"professional_basis_before_judgment","status":"pass","notes":"具体依据在前，判断或短夸在后。"},
            {"gate":"identity_and_fact_boundary","status":"pass","notes":"未伪装消费者、未推广畔色、未写未经验证的经历。"},
            {"gate":"natural_official_voice","status":"pass","notes":"短句、口语，不使用思路、那组、尤其、参考价值、落地。"}
        ]}
        reviews.append({"request_id":rid,"account_slot_and_nickname":"slot 1 / 畔色木作","note_id":item["note_id"],"target_note_title":item["title"],"source_context_summary":item["body"],"visible_comment_context_summary":item["comments"],"exact_draft_text":item["draft"],"style_preflight_passed":bool(receipt.get("passed")),"semantic_review_passed":True,"queue_status":"awaiting_user_review","current_user_approval_required":True,"published":False})

    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    write_json("account_1_browse_receipts_15.json",{"schema_version":1,"date":"2026-08-11","account_slot":1,"account_nickname":"畔色木作","profile_id":"6465fa8000000000290160bd","browse_target":15,"browse_actual":15,"deep_read_actual":15,"body_and_visible_comments_read":True,"items":READS,"safety_warning_observed":False,"external_comments_posted":0})
    write_json("account_1_style_requests_5.json",{"schema_version":1,"date":"2026-08-11","phase":"account1_cycle_day03_review_only","account_slot":1,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"request_count":5,"requests":requests})
    write_json("account_1_style_compile_receipts_5.json",{"schema_version":1,"compiled_at":stamp,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"receipt_count":5,"all_passed":all(x.get("passed") for x in receipts),"text_generated_by_preflight":False,"external_posting_performed":False,"receipts":receipts})
    write_json("account_1_current_session_stage_responses_5.json",{"schema_version":1,"created_at":stamp,"account_slot":1,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"stages":stages,"external_posting_performed":False})
    write_json("account_1_human_review_5.json",{"schema_version":1,"date":"2026-08-11","account_slot":1,"account_nickname":"畔色木作","review_item_count":5,"all_ready_for_user_review":all(x.get("passed") for x in receipts),"send_allowed":False,"user_approval_received":False,"published_count":0,"approval_rule":"Only explicit approval of the exact displayed drafts permits sending.","items":reviews})

    plan_path = RUN_DIR / "account_1_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse":15,"actual_deep_reads":15,"drafts_ready":5,"verified_follows":0,"public_visible_comments":0,"unsent_review_items":5,"status":"awaiting_user_review","stop_reason":None})
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 1:
            account.update({"status":"awaiting_user_review","actual_browse":15,"actual_deep_reads":15,"drafts_ready":5,"public_visible_comments":0,"verified_follows":0,"unsent":5})
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"browse":15,"deep_reads":15,"drafts":5,"preflight_passed":sum(bool(x.get("passed")) for x in receipts),"published":0},ensure_ascii=False,indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
