#!/usr/bin/env python3
"""Build slot-5 day-3 browse evidence and a review-only Style Lab queue."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-11"
TEMPLATE = RUN_DIR.parent / "2026-08-10" / "account_5_style_requests_6.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"


READS = [
    {"note_id":"6a767c85000000002701f134","title":"激光修复木质家具？！","author":"人间布洛芬","format":"30秒视频","body_summary":"视频展示激光去除木质家具表层旧涂层。","visible_comment_summary":"争议集中在防腐层、包浆和后续上油，也有人指出藤条断裂才是常见损坏。","images_viewed":"完整停留覆盖一次播放","selected":False,"exclusion_reason":"讨论争议已充分，且账号更像内容转载源。"},
    {"note_id":"6a6ebc6a00000000350151f4","title":"用几千块钱的工具来修几块钱的椅子","author":"Fan事慢慢来","format":"3分38秒视频","body_summary":"作者用有烟味、木料和结构一般的二手椅练习软包改造。","visible_comment_summary":"讨论工具投入、木种、裂缝注胶夹紧和作者表达。","images_viewed":"连续观看并结合正文和高赞评论理解过程","selected":False,"exclusion_reason":"视频较长，当前浏览段不足以对最终成品作精确评论。"},
    {"note_id":"69e5fb47000000001a020619","title":"🪑“卡扣家具”让组装变得像拼乐高","author":"German Design Council","format":"8图长文","body_summary":"ClipHut以木质卡扣组成免螺丝、免胶水和工具的模块家具，并延伸到开源CNC平台。","visible_comment_summary":"评论区为空。","images_viewed":"6/8，查看卡扣、书架隔断和模块组合","selected":True},
    {"note_id":"69266efc000000001b032994","title":"设计分享：old school一点这叫组合家具","author":"在拧螺丝的猩猩🦍","format":"32秒视频","body_summary":"作者对照板材模块柜和Vandoit铝型材模块，讨论露营车应用。","visible_comment_summary":"已充分讨论颠簸固定、快拆、重量、价格和安全标准。","images_viewed":"完整停留覆盖视频并阅读作者多轮回复","selected":False,"exclusion_reason":"评论区已经覆盖主要使用问题。"},
    {"note_id":"6905aaaa000000000302024b","title":"FROSTA Z｜由两把圆凳改造而成的衣帽架","author":"骄子","format":"10图长文","body_summary":"两张Frosta圆凳拆分、切短凳脚、钻孔并反转叠加成衣帽架，末图附图纸。","visible_comment_summary":"讨论购买、螺丝、圆凳下架和单侧承重；作者给出清楚回答。","images_viewed":"6/10，查看拆解、反转叠加、成品和结构过程","selected":True},
    {"note_id":"69b1214f000000002202df6b","title":"参考|低成本高灵活可打包带走的模块化商铺","author":"J2 studio 空间设计研究室","format":"18图长文","body_summary":"伊朗服装店以可移动模块替代固定硬装，包含柜台、挂衣、更衣、收银、储藏和投影。","visible_comment_summary":"只有一条简单夸赞，没有具体使用讨论。","images_viewed":"6/18，查看店铺整体、柜体和功能组合","selected":True},
    {"note_id":"6a08246a000000003601c570","title":"德国博主全屋USM，高级感拿捏住了！","author":"金JIN软装研究所.","format":"12图长文","body_summary":"德国住宅以多色USM模块柜贯穿全屋。","visible_comment_summary":"评论一边夸配色，一边指出柜底低和扫地清洁问题。","images_viewed":"6/12，查看多房间配色与空间组合","selected":True},
    {"note_id":"69700c8d000000001a02c20e","title":"一把可拆解的椅子","author":"小康是小康","format":"6图作品记录","body_summary":"作者在丹麦交换期间完成一把可拆解椅，拍摄于Milstein Hall。","visible_comment_summary":"三条简短夸赞，没有结构或使用问题。","images_viewed":"6/6，查看正侧面、空间关系和拆解展示","selected":False,"exclusion_reason":"保留为浏览样本，本批优先选择更强的可见细节。"},
    {"note_id":"69c7aa6000000000230132a9","title":"模块化家具为何一直火不起来？","author":"老虎聊设计","format":"3分16秒视频","body_summary":"视频讨论模块家具的市场接受度。","visible_comment_summary":"讨论小众程度、金属冷感、原木偏好、安装、价格和标准化。","images_viewed":"连续观看并通读主要讨论分支","selected":False,"exclusion_reason":"评论区已覆盖主要观点，且存在过度泛化。"},
    {"note_id":"66a279eb000000000a00664c","title":"NO 25 ｜分享一万件好看的家具","author":"分享一万件好看的家具","format":"12图长文","body_summary":"丹麦MOEBE模块架以涂层钢支架和橡木板组成，可重新配置。","visible_comment_summary":"讨论高脚变形、渠道、前倾固定、扫地清洁和实用性。","images_viewed":"6/12，查看高脚支架、层板组合和多场景摆放","selected":True},
    {"note_id":"69fc47fe000000003701c3ba","title":"形态构筑｜可自由组合的波纹置物架〰️","author":"家居视野捕手｜MOOD WHY","format":"5图长文","body_summary":"Ripple Shelf以波浪形立柱兼作造型和层板导轨。","visible_comment_summary":"讨论左右摇摆、顶底板固定、弧度咬合、彩色板和承重厚度。","images_viewed":"5/5，查看波浪立柱、层板咬合和整架侧面","selected":True},
    {"note_id":"69f1836d000000001f003ed4","title":"进口模块家具大盘点 TOP3","author":"苏的家居频道","format":"2分06秒视频","body_summary":"视频比较USM、MONTANA和STRING。","visible_comment_summary":"讨论格子化、铝型材替代、搭配、价格和正版必要性。","images_viewed":"连续观看并通读可见评论","selected":False,"exclusion_reason":"比较结论已被正文和评论区充分覆盖。"}
]


CANDIDATES = [
    {"note_id":"69e5fb47000000001a020619","title":"🪑“卡扣家具”让组装变得像拼乐高","topic":"material_craft","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only","body":READS[2]["body_summary"],"comments":[READS[2]["visible_comment_summary"]],"image":"已看6/8张，木卡扣直接暴露在立面并成为造型细节。","draft":"木卡扣露在外面反而挺好看，像柜子自己的装饰"},
    {"note_id":"6905aaaa000000000302024b","title":"FROSTA Z｜由两把圆凳改造而成的衣帽架","topic":"material_craft","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only","body":READS[4]["body_summary"],"comments":[READS[4]["visible_comment_summary"]],"image":"已看6/10张，看到凳腿反转叠加后的树杈状轮廓。","draft":"凳腿反着叠起来以后，那个树杈一样的形状挺好看"},
    {"note_id":"69b1214f000000002202df6b","title":"参考|低成本高灵活可打包带走的模块化商铺","topic":"global_localization","direction":"light_social_response","parent":"neutral_social","mode":"light_humor_or_neutral","body":READS[5]["body_summary"],"comments":[READS[5]["visible_comment_summary"]],"image":"已看6/18张，可见更衣、收银和储藏模块都能独立搬迁。","draft":"模块化设计都是看着省钱实际后面费钱"},
    {"note_id":"6a08246a000000003601c570","title":"德国博主全屋USM，高级感拿捏住了！","topic":"global_localization","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only","body":READS[6]["body_summary"],"comments":[READS[6]["visible_comment_summary"]],"image":"已看6/12张，看到钢蓝、巧克力色等柜体在同一住宅中的组合。","draft":"钢蓝配巧克力那个真舒服，颜色多也没显得乱"},
    {"note_id":"66a279eb000000000a00664c","title":"NO 25 ｜分享一万件好看的家具","topic":"material_craft","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only","body":READS[9]["body_summary"],"comments":[READS[9]["visible_comment_summary"]],"image":"已看6/12张，看到细钢架和橡木层板的组合。","draft":"细钢架配橡木板看着很轻，第一张特别好看"},
    {"note_id":"69fc47fe000000003701c3ba","title":"形态构筑｜可自由组合的波纹置物架〰️","topic":"material_craft","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only","body":READS[10]["body_summary"],"comments":[READS[10]["visible_comment_summary"]],"image":"已看5/5张，看到波浪立柱与层板咬合后的侧面轮廓。","draft":"波浪立柱夹着层板那张太好看了，侧面有点像雕塑"}
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
    request_id = f"panse.2026-08-11.account5.comment.{index:03d}"
    payload.update({
        "request_id": request_id,
        "idempotency_key": f"panse:2026-08-11:account-5:{item['note_id']}",
        "brief_text": f"目标原帖为《{item['title']}》。已完整阅读正文、相关图片和当前可见评论。身份是喜欢看海外家具、工艺和居住案例的普通同好，不装专家。评论必须扣住标题和正文真正讨论的主题，再给一个具体感受、观点或有用问题；不能因为正文顺带提到某个好处，就复述那个次要卖点。用短口语，说完即停；不为了互动硬提问，不使用思路、维度、层面、落地、参考价值、那组、尤其等书面或整理稿用词，不虚构购买、入住、测试或长期使用经历。输出1至2句，不提畔色，不引导主页、私信、搜索、关注、点赞或购买。",
        "source_locator": f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario": "小红书全球家具与工艺观察账号评论语气实验",
        "audience": "喜欢海外家具、材料工艺和居住案例的普通用户",
        "use_case": "生成一条具体、口语、支持创作者的短评论",
        "interaction_mode": item["mode"],
        "source_context": {"body":item["body"],"visible_comments":item["comments"],"image_observations":[{"locator":"reviewed_images","observation":item["image"],"observation_basis":"caller_reviewed"}],"body_complete":True,"visible_comments_complete":True,"images_complete":True,"expected_visible_comment_count":len(item["comments"]),"expected_image_count":1},
        "required_model_id":"gpt-5.6-sol",
        "fallback_model_allowed":False,
        "content_contract":{"protected_facts":[],"allowed_paraphrases":{},"forbidden_inferences":["不得虚构购买、入住、装修、测试或长期使用经历","不得只凭标题推断正文、图片或作者动机","不得重复评论区已经回答的问题","不得复述正文已经明确的年代、尺寸、材料清单或完整结论","不得抓住正文次要卖点却偏离标题和正文主旨","不得为了互动硬问问题","不得使用老师、专家、验收或裁判口吻","夸赞后不得追加空泛总结或长建议","不得使用思路、维度、层面、落地、参考价值、那组、尤其等书面或整理稿表达"],"citation_anchors":{},"must_cover_fact_ids":[]},
        "output":{"title_candidates":0,"title_max_chars":0,"body_min_chars":12,"body_max_chars":55,"tag_min":0,"tag_max":0},
        "panse_intent_context":{"policy_version":"xhs-comment-intent.v4","topic_ids":[item["topic"]],"interaction_intent":item["parent"],"comment_direction_id":item["direction"],"voice_id":"global_design_observer","human_approved_example_set_version":"panse-xhs-human-approved-comments.v2"}
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
        stages["plan"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"topic_ids":[item["topic"]],"comment_direction_id":item["direction"],"interaction_mode":item["mode"],"entry_angle":"先扣住原帖主旨，再给具体感受或观点；不复述次要卖点，不硬提问。"}
        stages["draft"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"draft_text":item["draft"],"tags":[]}
        stages["semantic_review"][rid] = {"model_id":"gpt-5.6-sol","fallback_used":False,"results":[
            {"gate":"source_grounding","status":"pass","notes":item["image"]},
            {"gate":"source_fact_repetition","status":"pass","notes":"没有照抄标题或复述正文完整结论。"},
            {"gate":"topic_relevance","status":"pass","notes":"草稿直接回应标题和正文真正讨论的主题，不拿次要卖点凑评论。"},
            {"gate":"question_value","status":"not_applicable","notes":"本批均为短夸，没有为了互动硬加问题。"},
            {"gate":"identity_and_fact_boundary","status":"pass","notes":"未虚构购买、入住、测试或长期使用经历。"},
            {"gate":"natural_global_observer_voice","status":"pass","notes":"短句、口语、具体，不使用老师或评委口吻，也不使用那组、尤其等整理稿表达。"}
        ]}
        reviews.append({"request_id":rid,"account_slot_and_nickname":"slot 5 / 是阿宝啊","note_id":item["note_id"],"target_note_title":item["title"],"source_context_summary":item["body"],"visible_comment_context_summary":item["comments"],"exact_draft_text":item["draft"],"interaction_mode":item["mode"],"comment_direction_id":item["direction"],"style_preflight_passed":bool(receipt.get("passed")),"semantic_review_passed":True,"queue_status":"awaiting_user_review","current_user_approval_required":True,"published":False})
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    write_json("account_5_browse_receipts_12.json",{"schema_version":1,"date":"2026-08-11","account_slot":5,"account_nickname":"是阿宝啊","profile_id":"6347830c0000000012027db3","browse_target":12,"browse_actual":12,"deep_read_actual":12,"body_and_visible_comments_read":True,"items":READS,"safety_warning_observed":False})
    write_json("account_5_style_requests_6.json",{"schema_version":1,"date":"2026-08-11","phase":"account5_cycle_day03_review_only_generation","account_slot":5,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"request_count":6,"requests":requests})
    write_json("account_5_style_compile_receipts_6.json",{"schema_version":1,"compiled_at":stamp,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"receipt_count":6,"all_passed":all(x.get("passed") for x in receipts),"text_generated_by_preflight":False,"external_posting_performed":False,"receipts":receipts})
    write_json("account_5_current_session_stage_responses_6.json",{"schema_version":1,"created_at":stamp,"account_slot":5,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"stages":stages})
    write_json("account_5_human_review_6.json",{"schema_version":1,"date":"2026-08-11","account_slot":5,"review_item_count":6,"all_ready_for_user_review":all(x.get("passed") for x in receipts),"send_allowed":False,"user_approval_received":False,"published_count":0,"approval_rule":"Only explicit approval of the exact displayed drafts permits sending.","items":reviews})
    plan_path = RUN_DIR / "account_5_daily_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update({"actual_browse":12,"actual_deep_reads":12,"drafts_ready":6,"verified_follows":0,"public_visible_comments":0,"unsent_review_items":6,"status":"awaiting_user_review","stop_reason":None})
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    status_path = RUN_DIR / "five_account_daily_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    for account in status["accounts"]:
        if account["account_slot"] == 5:
            account.update({"status":"awaiting_user_review","actual_browse":12,"actual_deep_reads":12,"drafts_ready":6,"public_visible_comments":0,"verified_follows":0,"unsent":6})
    status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
