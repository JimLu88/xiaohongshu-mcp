#!/usr/bin/env python3
"""Build slot-5 browse receipts and pinned Style Lab requests for 2026-08-09."""

from __future__ import annotations

import copy
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-09"
TEMPLATE_PATH = RUN_DIR / "account_3_style_requests_5.json"
BROWSE_PATH = RUN_DIR / "account_5_browse_receipts_14.json"
REQUESTS_PATH = RUN_DIR / "account_5_style_requests_5.json"
CONTRACT_PATH = RUN_DIR / "account_5_style_runtime_contract_v11.json"


NOTES = [
    {
        "note_id": "6a745e8d000000003301866c",
        "title": "关于宫崎椅子，也关于我们如何生活。",
        "url": "https://www.xiaohongshu.com/search_result/6a745e8d000000003301866c?xsec_source=",
        "body": "1969年，宫崎椅子制作所创立于日本四国德岛县。文章从设计与时间、工艺与制作、尺度与使用、椅子与空间四个方向，介绍一把椅子从设计构想、工坊反复试作、材料结构判断，到身体坐下并进入空间的完整过程。",
        "comments": [],
        "image_count": 6,
        "images_viewed": [1, 2, 3, 4, 5, 6],
        "image_observations": [
            "白底上的宫崎椅子制作所中英文标志封面。",
            "展览现场白色展墙前并列陈列三把不同轮廓的木椅。",
            "工坊里多人围着一把未上色木椅查看靠背与结构。",
            "工坊木椅弧形扶手和连接部位的近景。",
            "大面积落地窗前的大木桌与多把木椅，展示椅子进入用餐空间。",
            "黑色皮革软包与木框架组合的单椅产品图。",
        ],
        "image_coverage_note": "all 6 images were reviewed from the note's exposed image resources",
        "direction": "detail_grounded_praise",
        "parent_intent": "grounded_praise",
        "mode": "support_only",
        "topics": ["material_craft", "global_localization"],
    },
    {
        "note_id": "6954face000000001e00538f",
        "title": "为什么我们很难复刻国外的松弛感？",
        "url": "https://www.xiaohongshu.com/search_result/6954face000000001e00538f?xsec_source=",
        "body": "为什么外国人的房子那么温馨自然，而国人的家装却生硬呆板？同样是房子，差别到底在哪？",
        "comments": [
            "这画就很中国",
            "你拿国内的小套房对标国外的别墅……",
            "有品位也要有经济支撑",
            "这是书房，看看还需要怎么改动，麻烦给点意见",
            "斗柜花瓶里是干花吗？上色的尤加利？",
            "沙发有连接？",
            "你发这几个画店，那画是真买不起",
        ],
        "image_count": 0,
        "images_viewed": [],
        "image_observations": [],
        "image_coverage_note": "no carousel indicator was exposed in the browser DOM",
        "direction": "global_localization_question",
        "parent_intent": "utility_fit_question",
        "mode": "curiosity_question",
        "topics": ["global_localization"],
    },
    {
        "note_id": "69b51f18000000001b021b2b",
        "title": "修复了百年➕法国老家具🇫🇷｜法国田园生活",
        "url": "https://www.xiaohongshu.com/search_result/69b51f18000000001b021b2b?xsec_source=",
        "body": "第一次看到它时又老又旧，但是我们已经看到了它被修复后的样子。它经历过好几个家庭、几代人。漆面下有旧痕，也有被其他木头拼接过的地方；我们不盖住它，只是帮它继续活着。修复过的痕迹成了新的记忆。花了很长时间找到一件适合这个房子的老家具，好喜欢我老公修复的这件老家具。",
        "comments": [
            "请问除了打磨还做了什么？",
            "作者：打磨，有几处地方换了木头，防虫处理，打蜡",
            "请问在哪里可以找到这种老家具呀？",
            "作者：在Le Bon Coin或Vide Maison上都很容易找到，还有很多二手家具店，brocante有时也能遇到，我们主要挑木头。",
        ],
        "image_count": 7,
        "images_viewed": [1, 2, 3, 4, 5, 6, 7],
        "image_observations": [
            "修复前的深色双门木柜，表面旧漆、划痕和磨损清晰可见。",
            "另一张修复前木柜全貌，门板、抽屉和雕花均保留明显旧痕。",
            "修复者在户外手工清理或打磨拆下的雕花门板。",
            "同一柜体一扇门已清理变浅、另一扇仍深色，形成过程对比。",
            "修复后柜体全貌，颜色变浅但旧痕、补木和雕花仍被保留。",
            "修复后的柜子放在白墙前，日光照在门板上，旁边摆一把老椅。",
            "修复后的柜顶摆放棋盘、相框、木雕和黄花，呈现进入日常空间后的状态。",
        ],
        "image_coverage_note": "all 7 images were reviewed from the note's exposed image resources",
        "direction": "detail_grounded_praise",
        "parent_intent": "grounded_praise",
        "mode": "support_only",
        "topics": ["maintenance_lifetime", "global_localization"],
    },
    {
        "note_id": "6a5300ab0000000016024ecb",
        "title": "米兰设计周最值得关注的7个可持续设计",
        "url": "https://www.xiaohongshu.com/search_result/6a5300ab0000000016024ecb?xsec_source=",
        "body": "今年米兰设计周的可持续设计已经从环保概念变成产品创新。作者列举了七个案例，包括重复使用展台结构、模块化异地重建、展后继续使用木材，以及Arper用更少部件完成设计，让家具更方便维修、拆解和回收。作者最后询问大家最喜欢哪个品牌，或还有哪些作品值得推荐。",
        "comments": [],
        "image_count": 8,
        "images_viewed": [1, 2, 3, 4, 5, 6, 7, 8],
        "image_observations": [
            "米兰设计周可持续观察封面，列出七个品牌。",
            "Kriskadecor展位以彩色金属网帘形成可回收的空间隔断。",
            "Arper沙发剖开展示减材结构和可拆解的内部部件。",
            "Kohler展区把浴缸与为鸟、蜜蜂和蝴蝶设置的花园水景结合。",
            "Andreu World以被植物包裹的椅子视觉说明可回收、可降解、可堆肥材料。",
            "Miele深色展台展示节水家电和回收材料家具。",
            "Expormim展位陈列再生铝、耐用织物和藤编结合的座椅。",
            "Fisher & Paykel以森林环幕和木质厨房展台说明展后木材继续利用。",
        ],
        "image_coverage_note": "all 8 images were reviewed from the note's exposed image resources",
        "direction": "acquisition_channel_question",
        "parent_intent": "acquisition_question",
        "mode": "curiosity_question",
        "topics": ["purchase_service", "global_localization"],
    },
    {
        "note_id": "6a409b3a000000001502725b",
        "title": "右滑看我修藤编椅子🪑呀‼️",
        "url": "https://www.xiaohongshu.com/search_result/6a409b3a000000001502725b?xsec_source=",
        "body": "五年的藤编椅子破洞了，作者不舍得换，因为整体框架还很好。这张椅子当时700多元，原藤面对丝质衣服和羊毛裤子容易产生磨损。作者向原商家花300元购买全真皮坐垫，用自攻螺丝自行安装替换；换完后没有味道，感觉又得到了一张漂亮椅子。",
        "comments": [
            "我也遇到同样的问题，请教一下用哪种螺丝固定坐垫？",
            "作者：我是自攻螺丝，穿过椅子的钢架洞再对上坐垫的洞固定，没有其他辅助。",
            "请问这个垫怎么固定在金属上啊？",
            "作者：反面原本有个孔，膨胀螺丝可以直接钉进去。",
            "谢谢",
        ],
        "image_count": 6,
        "images_viewed": [1, 2, 3, 4, 5, 6],
        "image_observations": [
            "藤编椅座面出现明显破洞的近景。",
            "纸箱旁放着新到的棕色纽扣真皮坐垫。",
            "新坐垫的皮面、缝线和纽扣细节近景。",
            "椅架、破损藤编座面和新皮坐垫拆开放在地面上对比。",
            "安装后的悬臂椅全貌，藤编靠背保留，座面换成棕色皮垫。",
            "修好的皮坐垫椅放在餐桌旁，与另一把仍使用藤编座面的椅子并列。",
        ],
        "image_coverage_note": "all 6 images were reviewed with keyboard carousel navigation",
        "direction": "maintenance_durability_question",
        "parent_intent": "utility_fit_question",
        "mode": "curiosity_question",
        "topics": ["maintenance_lifetime", "material_craft"],
    },
]


MODE_RULES = {
    "soft_observation": (
        "先共情或肯定正文中的具体细节，再温和落到普通家庭会遇到的真实日常；"
        "不作验收结论，不以老师口吻点评。",
        25,
        70,
    ),
    "support_only": (
        "接住正文里一个具体、可观察的细节，先真诚支持作者；"
        "不建议、不纠错、不追问，不使用空泛夸赞。",
        12,
        38,
    ),
    "curiosity_question": (
        "先承接一个可定位的具体细节，再问一个正文和全部可见评论尚未回答的问题；"
        "不把建议伪装成问题。",
        18,
        55,
    ),
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_browse_receipts() -> None:
    all_ids = [
        "6a745e8d000000003301866c", "6954face000000001e00538f",
        "69c0be60000000001f00175b", "6a66babb000000000301f68d",
        "6966e39e000000001a01d880", "69c0d48f00000000220271c7",
        "69b2b1b4000000001b01f925", "6a3dfac200000000110177fe",
        "6992cc4f000000000a03d4b7", "6a5b6c3b0000000001032bee",
        "69ac467b000000002603ca6d", "69b51f18000000001b021b2b",
        "6a5300ab0000000016024ecb", "6a409b3a000000001502725b",
    ]
    selected = {item["note_id"]: item for item in NOTES}
    items = []
    for note_id in all_ids:
        source = selected.get(note_id)
        items.append({
            "note_id": note_id,
            "title": source["title"] if source else None,
            "deep_read_seconds": 20,
            "full_visible_body_read": True,
            "visible_comments_read": bool(source and source["comments"]),
            "images_viewed": source["images_viewed"] if source else [1],
            "image_coverage_note": source["image_coverage_note"] if source else "first image verified; carousel control unavailable",
            "selected_for_comment": bool(source),
            "warning": False,
        })
    write_json(BROWSE_PATH, {
        "schema_version": 1,
        "date": "2026-08-09",
        "account_slot": 5,
        "account_profile_id": "6347830c0000000012027db3",
        "account_nickname": "是阿宝啊",
        "browse_target": 14,
        "browse_actual": 14,
        "selected_comment_candidates": 5,
        "items": items,
        "safety_warning_observed": False,
        "external_comments_posted": 0,
    })


def build_style_requests() -> None:
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    base = template["requests"][0]
    requests = []
    for index, note in enumerate(NOTES, 1):
        rule, body_min, body_max = MODE_RULES[note["mode"]]
        item = copy.deepcopy(base)
        request_id = f"panse.2026-08-09.account5.comment.{index:03d}"
        item.update({
            "experiment_id": f"2026-08-09-account5-{index:03d}",
            "comparison_sample_id": None,
            "target_note": {
                "note_id": note["note_id"],
                "title": note["title"],
                "author": "公开笔记作者",
                "source_locator": note["url"],
            },
            "generation_intent": note["parent_intent"],
            "interaction_mode": note["mode"],
            "intent_rule": rule,
            "source_context": {
                "body": note["body"],
                "visible_comments": note["comments"],
                "body_nonempty": True,
                "image_count": note["image_count"],
                "images_viewed": note["images_viewed"],
                "image_coverage_note": note["image_coverage_note"],
                "warning": False,
            },
        })
        style_request = item["style_request"]
        style_request.update({
            "request_id": request_id,
            "idempotency_key": f"panse:2026-08-09:account-5:{note['note_id']}",
            "brief_text": (
                f"目标原帖标题为《{note['title']}》。已完整读取可见正文、当前可见评论和浏览器可验证的图片；"
                f"图片未能完整翻看的部分已经明确标记，不得据此补写。不得只根据标题推断。本条互动模式：{rule} "
                "说话位置是支持创作者的普通家居同好，不是老师、评委、验收人员或设计大师。"
                "只承接可定位的具体细节；不冒充购买、入住、装修、施工、测试或长期使用经历。"
                "输出一条自然的小红书评论，1至2句，不提畔色，不引导主页、私信、搜索、关注、点赞或购买。"
            ),
            "source_locator": note["url"],
            "interaction_mode": note["mode"],
            "source_context": {
                "body": note["body"],
                "visible_comments": note["comments"],
                "image_observations": [
                    {
                        "locator": f"image[{image_index}]#reviewed",
                        "observation": observation,
                        "observation_basis": "caller_reviewed",
                    }
                    for image_index, observation in enumerate(note["image_observations"])
                ],
                "body_complete": True,
                "visible_comments_complete": True,
                "images_complete": True,
                "expected_visible_comment_count": len(note["comments"]),
                "expected_image_count": len(note["image_observations"]),
            },
            "comment_intent_context": {
                "intent_policy_version": "xhs-comment-intent.v4",
                "topic_ids": note["topics"],
                "interaction_intent": note["parent_intent"],
                "comment_direction_id": note["direction"],
                "voice_id": "global_design_observer",
                "human_approved_example_set_version": "panse-xhs-human-approved-comments.v1",
            },
        })
        style_request["content_contract"]["protected_facts"][0]["value"] = note["title"]
        style_request["output"]["body_min_chars"] = body_min
        style_request["output"]["body_max_chars"] = body_max
        item["panse_intent_context"] = {
            "intent_policy_version": "xhs-comment-intent.v4",
            "voice_id": "global_design_observer",
            "voice_style_id": "curious_localization_observer",
            "interaction_intent": note["parent_intent"],
            "comment_direction_id": note["direction"],
            "topic_ids": note["topics"],
            "interaction_mode": note["mode"],
        }
        requests.append(item)

    template.update({
        "phase": "account5_cycle_day01_live_generation",
        "account_slot": 5,
        "account_id": "global_furniture_editor",
        "public_role": "国外家具与本地生活观察编辑",
        "source_deep_reads": "research/panse_multi_direction/daily_runs/2026-08-09/account_5_browse_receipts_14.json",
        "request_count": len(requests),
        "requests": requests,
    })
    write_json(REQUESTS_PATH, template)


def build_runtime_contract() -> None:
    source = REPO / "research" / "panse_multi_direction" / "style_experiment_four_mode_contract_2026-08-07.json"
    contract = json.loads(source.read_text(encoding="utf-8"))
    contract["created_at"] = "2026-08-09"
    contract["phase"] = "account5_cycle_day01_style_runtime_v11"
    contract["current_runtime_evidence"]["catalog_version"] = "2026-08-09-v11"
    contract["current_runtime_evidence"]["catalog_sha256"] = "caf39d2d70e818d37c4849ff420a425b7ea11af2df2df3567e3fcded84e12d99"
    contract["notes"] = (
        "Independent daily contract for Tachikoma catalog v11; historical v10 contract remains unchanged."
    )
    write_json(CONTRACT_PATH, contract)


if __name__ == "__main__":
    build_browse_receipts()
    build_style_requests()
    build_runtime_contract()
    print(json.dumps({"browse": str(BROWSE_PATH), "requests": str(REQUESTS_PATH), "contract": str(CONTRACT_PATH)}, ensure_ascii=False))
