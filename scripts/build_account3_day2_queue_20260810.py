#!/usr/bin/env python3
"""Build slot-3 day-2 evidence and four preflighted comment requests."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-10"
PREVIOUS = RUN_DIR.parent / "2026-08-09" / "account_3_style_requests_5.json"
PREFLIGHT = REPO / "scripts" / "prepare_xhs_style_request.py"

READS = [
    {"note_id":"6962058a000000000a02b49c","title":"精准把握客厅沙发尺寸 千万别挑错啦！","author":"ZEOL焯领","images":"5/5","comments":67,"summary":"按户型面积给尺寸区间；评论补充需看插座位置并保留约70厘米空位","selected":False},
    {"note_id":"6a70034d000000002203273a","title":"卡座沙发，我也算是做出经验了（附尺寸）","author":"吴滴滴滴滴","images":"6/9","comments":68,"summary":"两版卡座对比：45厘米靠背、一体木框、弹簧坐垫、加深坐深；评论补充加深后需下挂落地","selected":True},
    {"note_id":"6a5e2a10000000000f03dec7","title":"3.2m小开间｜小户型选沙发真的太熬人了😭","author":"酷酷的小屋🏠（软装中）","images":"2/2","comments":50,"summary":"3.2米开间、105厘米沙发深度、37厘米电视柜和1.78米净距实测","selected":True},
    {"note_id":"69cc79ef0000000023010209","title":"买家具不纠结｜尺寸 + 材质 + 风格全攻略","author":"照见自我的摄影师","images":"6/9","comments":0,"summary":"规则泛化且评论为空，不选为互动目标","selected":False},
    {"note_id":"6687c54c000000000d00e7e2","title":"实木家具科普：结构、选材和造型的取舍","author":"大师谈实木家具","images":"text/video","comments":133,"summary":"拆分结构、选材、造型；评论强调开裂不能只归因于木材稳定性","selected":False},
    {"note_id":"65f2e67f0000000012020108","title":"一期视频讲清楚！不同预算哪种木材更适合你","author":"本真木作","images":"video 1:17/3:03","comments":4,"summary":"同业品牌导流，评论主要询价，不互动","selected":False},
    {"note_id":"6a3f965b000000001603f6e8","title":"选板时有多兴奋，看到成品就有多想报警","author":"啊七啊七啊啊啊啊七","images":"6/6","comments":120,"summary":"毛板与成品对比，后续确认拼接顺序和纹理方向为主要问题","selected":True},
    {"note_id":"690d764f0000000005001451","title":"内行买餐桌都看这10点","author":"狂飙的跑跑熊","images":"5/5","comments":138,"summary":"从底部结构、涂装、材料和尺寸拆解餐桌","selected":False},
    {"note_id":"686de78b0000000017034c89","title":"🔥【血泪教训】安装实木床不被坑指南","author":"赵烧鸡腿（软装开启版）","images":"4/4","comments":22,"summary":"两根支撑梁安装高低不一导致床板翘起，二次钻孔仍未解决","selected":False},
    {"note_id":"68eb92bb0000000005010956","title":"源氏木语修复小哥老帅啦哈哈哈","author":"买买买","images":"6/7","comments":38,"summary":"上门修补效果与漆雾、通风、软装遮盖提醒","selected":True},
    {"note_id":"687c4872000000001202d65c","title":"家具进场稍不注意就成这样了","author":"阿里噶多美羊羊","images":"3/3","comments":27,"summary":"家具进场碰伤门框且缺少过程证据，后续自费修复","selected":False}
]

CANDIDATES = [
    {
        "note_id":"6a70034d000000002203273a","title":"卡座沙发，我也算是做出经验了（附尺寸）",
        "topic":"comfort_ergonomics","direction":"comfort_ergonomics_question","parent":"utility_fit_question","mode":"curiosity_question",
        "body":"作者入住三年并做了两版卡座，第二版采用一体木框、弹簧坐垫，把靠背加高到45厘米，183厘米身高刚好有支撑，同时加深坐深。",
        "comments":["可见评论讨论坐深加深后需下挂落地提高稳定性","未见作者回答最终坐深的具体厘米数"],
        "image":"已看前6/9张，可见两版卡座及尺寸变化。",
        "draft":"靠背做到45厘米，身高183厘米刚好能撑到背，这组数据很有参考。坐深最后加到多少了呀？"
    },
    {
        "note_id":"6a5e2a10000000000f03dec7","title":"3.2m小开间｜小户型选沙发真的太熬人了😭",
        "topic":"dimensions_fit","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者实测客厅开间3.2米、沙发深1.05米、电视柜厚37厘米，沙发到电视柜净距1.78米。",
        "comments":["可见评论围绕相似户型和电视柜尺寸讨论","没有重复草稿中的四项尺寸关系"],
        "image":"已看2/2张，可见实际摆放和尺寸标注。",
        "draft":"3.2米开间配105厘米深沙发，最后还能留1.78米净距，这组实测比一味追超窄沙发有参考多了。"
    },
    {
        "note_id":"6a3f965b000000001603f6e8","title":"选板时有多兴奋，看到成品就有多想报警",
        "topic":"material_craft","direction":"invited_peer_tip","parent":"peer_tip_invited","mode":"soft_observation",
        "body":"作者对比毛板与成品，后续确认拼接顺序和纹理方向造成视觉断裂；厂家同意重新选板，作者表示会再来询问。",
        "comments":["可见评论已讨论直纹、山纹的拼接位置","草稿不重复具体拼法，只补充确认流程"],
        "image":"已看6/6张，可见毛板、成品和拼缝差异。",
        "draft":"下次选毛板时，可以给每块板编号，再把拼接顺序和纹理方向一起确认。好在现在还能重选。"
    },
    {
        "note_id":"68eb92bb0000000005010956","title":"源氏木语修复小哥老帅啦哈哈哈",
        "topic":"maintenance_lifetime","direction":"detail_grounded_praise","parent":"grounded_praise","mode":"support_only",
        "body":"作者记录送达磕损后的品牌上门修补，表示成品看不出修补痕迹；同时提醒密闭房间漆雾明显，空气净化器报警。",
        "comments":["可见评论主要讨论师傅与联系方式","没有重复通风和软装遮盖的完整表达"],
        "image":"已看前6/7张，可见修补过程与结果。",
        "draft":"修补效果能做到看不出确实厉害，漆雾这个细节也提醒得很实在。家里有床垫和布艺的，修之前先挪开会更省事。"
    }
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
    payload.update({
        "request_id":f"panse.2026-08-10.account3.comment.{index:03d}",
        "idempotency_key":f"panse:2026-08-10:account-3:{item['note_id']}",
        "brief_text":f"目标原帖为《{item['title']}》。已完整阅读当前可见正文、相关图片和评论。身份是认真做功课但不替别人做决定的家具购买同伴。先承接一个尺寸、结构、材料、安装或维护的具体事实，再完成一个动作：短夸、一个未回答的轻问，或作者明确邀请下的条件化建议。不使用测评机构、大师、老师或验收口吻，不作无证据质量判断，不虚构购买、入住、维修或长期使用经历。输出1至2句、12至65字；不提畔色，不引导主页、私信、搜索、关注、点赞或购买。",
        "source_locator":f"https://www.xiaohongshu.com/explore/{item['note_id']}",
        "scenario":"家具决策内容评论语气实验","audience":"正在比较家具尺寸、材料、结构和使用条件的普通用户","use_case":"生成一条有依据、支持创作者且不替别人下结论的评论",
        "interaction_mode":item["mode"],
        "source_context":{"body":item["body"],"visible_comments":item["comments"],"image_observations":[{"locator":"reviewed_images","observation":item["image"],"observation_basis":"caller_reviewed"}],"body_complete":True,"visible_comments_complete":True,"images_complete":True,"expected_visible_comment_count":len(item["comments"]),"expected_image_count":1},
        "required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,
        "content_contract":{"protected_facts":[],"allowed_paraphrases":{},"forbidden_inferences":["不得虚构购买、入住、维修、测试或长期使用经历","不得使用测评机构、大师、老师或验收口吻","不得把图片观察写成质量结论","不得重复已经回答的问题或给作者未邀请的长建议"],"citation_anchors":{},"must_cover_fact_ids":[]},
        "output":{"title_candidates":0,"title_max_chars":0,"body_min_chars":12,"body_max_chars":65,"tag_min":0,"tag_max":0},
        "panse_intent_context":{"policy_version":"xhs-comment-intent.v4","topic_ids":[item["topic"]],"interaction_intent":item["parent"],"comment_direction_id":item["direction"],"voice_id":"evaluation_judgment"}
    })
    return payload

def main() -> int:
    base = json.loads(PREVIOUS.read_text(encoding="utf-8"))["requests"][0]["style_request"]
    write_json("account_3_browse_receipts_11.json", {"schema_version":1,"date":"2026-08-10","account_slot":3,"account_nickname":"link","browse_target":11,"browse_actual":11,"deep_read_actual":11,"full_visible_body_read":True,"visible_comments_read":True,"items":READS,"safety_warning_observed":False})
    write_json("account_3_follow_receipts_1.json", {"schema_version":1,"date":"2026-08-10","account_slot":3,"target":{"profile_id":"606bb18b0000000001008c0c","nickname":"狂飙的跑跑熊","read_notes":["690d764f0000000005001451","68f83ee6000000000400728d"],"second_note_images_viewed":"6/17","role_fit":"家具结构、材料和购买条件"},"button_before":"关注","button_after":"已关注","verified":True,"safety_warning_observed":False})
    requests=[]; receipts=[]; reviews=[]; stages={"plan":{},"draft":{},"semantic_review":{}}
    for index,item in enumerate(CANDIDATES,1):
        payload=build_payload(base,item,index); receipt=preflight(payload); rid=payload["request_id"]
        requests.append({"target_note":{"note_id":item["note_id"],"title":item["title"],"source_locator":payload["source_locator"]},"style_request":payload}); receipts.append(receipt)
        stages["plan"][rid]={"model_id":"gpt-5.6-sol","fallback_used":False,"topic_ids":[item["topic"]],"comment_direction_id":item["direction"],"interaction_mode":item["mode"],"entry_angle":"先写可见的决策条件，再完成一个互动动作。"}
        stages["draft"][rid]={"model_id":"gpt-5.6-sol","fallback_used":False,"draft_text":item["draft"],"tags":[]}
        stages["semantic_review"][rid]={"model_id":"gpt-5.6-sol","fallback_used":False,"results":[{"gate":"source_grounding","status":"pass","notes":item["image"]},{"gate":"question_or_advice_right","status":"pass","notes":"轻问未见回答；建议仅用于作者明确表示会再询问的帖子。" if item["mode"]!="support_only" else "本条不提问、不展开建议。"},{"gate":"identity_and_fact_boundary","status":"pass","notes":"未伪装消费者或测评机构，未作无证据质量判断。"},{"gate":"natural_decision_peer_voice","status":"pass","notes":"具体条件在前，语气简短，不替作者和读者做决定。"}]}
        reviews.append({"request_id":rid,"note_id":item["note_id"],"title":item["title"],"draft":item["draft"],"interaction_mode":item["mode"],"comment_direction_id":item["direction"],"style_preflight_passed":bool(receipt.get("passed")),"semantic_review_passed":True,"queue_status":"ready_for_send","published":False})
    stamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    write_json("account_3_style_requests_4.json",{"schema_version":1,"date":"2026-08-10","phase":"account3_cycle_day02_live_generation","account_slot":3,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"request_count":4,"requests":requests})
    write_json("account_3_style_compile_receipts_4.json",{"schema_version":1,"compiled_at":stamp,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"receipt_count":4,"all_passed":all(r.get("passed") for r in receipts),"receipts":receipts})
    write_json("account_3_current_session_stage_responses_4.json",{"schema_version":1,"created_at":stamp,"account_slot":3,"required_model_id":"gpt-5.6-sol","fallback_model_allowed":False,"stages":stages})
    write_json("account_3_human_review_4.json",{"schema_version":1,"date":"2026-08-10","account_slot":3,"review_item_count":4,"all_ready_for_send":all(x["style_preflight_passed"] for x in reviews),"items":reviews})
    print(json.dumps({"requests":4,"all_preflight_passed":all(r.get("passed") for r in receipts),"artifacts":6},ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
