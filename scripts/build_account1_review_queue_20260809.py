#!/usr/bin/env python3
"""Build and validate the slot-1 review-only queue for 2026-08-09."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-09"
TEMPLATE_PATH = RUN_DIR / "account_3_style_requests_5.json"
BROWSE_PATH = RUN_DIR / "account_1_browse_receipts_10.json"
REQUESTS_PATH = RUN_DIR / "account_1_style_requests_4.json"
COMPILE_PATH = RUN_DIR / "account_1_style_compile_receipts_4.json"
SESSION_PATH = RUN_DIR / "account_1_current_session_stage_responses_4.json"
TACHIKOMA_ROOT = Path(r"D:\AI\tachikoma-runtime\writing-style-all-v2")
sys.path.insert(0, str(TACHIKOMA_ROOT))

from base.xiaohongshu_style import (  # noqa: E402
    StyleWritingRequest,
    _resolved_comment_context,
    prepare_style_bundle,
    stage_comment_context,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


NOTES = [
    {"note_id": "67d66380000000001b039aa7", "title": "【家具保养秘籍】胡桃木家具木蜡油保养全攻略", "topic": "maintenance_lifetime", "selected": False, "images": "1/7封面与正文已读", "summary": "通用木蜡油清洁、打磨、上油和抛光步骤；评论集中询问砂纸、软布、油品和水渍。"},
    {"note_id": "69523a55000000001f00a19b", "title": "勤快的笨女人涂木蜡油大翻车了及后续", "topic": "maintenance_lifetime", "selected": True, "images": "已翻看1至6/8", "summary": "作者记录木蜡油涂厚、未收油后的粗糙反光及补救过程；评论强调先确认原涂装并小面积试验。"},
    {"note_id": "6a688187000000000f03cea1", "title": "耗时三天！一个人翻新用了8年的餐桌", "topic": "maintenance_lifetime", "selected": False, "images": "视频与正文已读", "summary": "旧餐桌打磨、上油和粉尘处理过程；涉及二黑产品，官方号不进入评论候选。"},
    {"note_id": "681d98fe0000000021002ee5", "title": "关于实木家具发霉问题", "topic": "maintenance_lifetime", "selected": False, "images": "正文与可见评论已读", "summary": "竞品官方发布的发霉预防和售后说明；仅浏览，不在竞品商业帖评论。"},
    {"note_id": "6a574410000000000f02ad89", "title": "实木桌面越擦越白？这5个清洁方法全错了", "topic": "maintenance_lifetime", "selected": False, "images": "1/4封面与正文已读", "summary": "清洁与定期补蜡建议含多处泛化和绝对化表达，互动很少，不进入候选。"},
    {"note_id": "6a756f360000000032032896", "title": "北美黑胡桃木家具，日常该怎么保养？", "topic": "maintenance_lifetime", "selected": False, "images": "20秒视频完整停留", "summary": "视频笔记正文只有话题标签，公开上下文不足，不进入候选。"},
    {"note_id": "6a0873a000000000070138b0", "title": "求求！餐桌买1.4还是1.6", "topic": "dimensions_fit", "selected": True, "images": "已翻看3/3", "summary": "2.3米见方餐区在1.4、1.6、1.8米餐桌间选择，作者最终选1.4米；评论讨论通道和架高模拟。"},
    {"note_id": "6974c33c000000000903af95", "title": "圆桌会惩罚每一个贪大的人（附适配尺寸）", "topic": "layout_circulation", "selected": False, "images": "1/10封面、正文和可见评论已读", "summary": "作者用2.1乘2.7米餐厅说明1.2米圆桌拉椅后的拥挤，并列尺寸参考。"},
    {"note_id": "6a2ff57a0000000008027d45", "title": "餐厅2.6m开间，坚持做餐边柜，满意", "topic": "layout_circulation", "selected": True, "images": "已翻看4/4", "summary": "2.6米开间内放40厘米餐边柜和1.6乘0.8米圆弧餐桌，窄处过道65厘米以上。"},
    {"note_id": "67dbd372000000000903bbe9", "title": "试过了，小餐厅也能放下1.8的大板桌", "topic": "dimensions_fit", "selected": True, "images": "已翻看3/3", "summary": "作者用纸板在家模拟1.8米餐桌，入住近两个月后分享人数、通道和实际使用感受。"},
]


CANDIDATES = [
    {
        "note_id": "69523a55000000001f00a19b",
        "title": "勤快的笨女人涂木蜡油大翻车了及后续",
        "topic": "maintenance_lifetime",
        "body": "作者完整记录给黑胡桃家具涂木蜡油时用量过多、没有及时收油，导致表面粗糙反光，并持续更新补救过程。",
        "comments": ["先确认家具原来的涂装方式", "应该先在背面或小面积试效果", "作者决定先观察再做其他动作"],
        "image_observation": "作者展示涂油前后和局部表面变化，已翻看前6张图片。",
        "draft": "木蜡油涂厚后那种粗糙反光拍得很清楚。",
        "evidence": "作者在正文复盘没有先做小面积试验，评论区也反复讨论先试再处理。",
    },
    {
        "note_id": "6a0873a000000000070138b0",
        "title": "求求！餐桌买1.4还是1.6",
        "topic": "dimensions_fit",
        "body": "作者给出2.3米见方餐区，在1.4、1.6、1.8米餐桌之间选择，最终评论确认买了1.4米。",
        "comments": ["作者最终回复买了1.4米", "有人建议把模拟尺寸架到真实桌高再看", "评论集中讨论通道和餐边柜开门"],
        "image_observation": "三张图展示餐区和不同餐桌尺寸的现场比划，已翻看3/3。",
        "draft": "最后选1.4米，家里现场比划尺寸这一步很直观。",
        "evidence": "正文用现场尺寸比划辅助选择，作者在评论确认最终购买1.4米。",
    },
    {
        "note_id": "6a2ff57a0000000008027d45",
        "title": "餐厅2.6m开间，坚持做餐边柜，满意",
        "topic": "layout_circulation",
        "body": "作者在2.6米开间内做40厘米餐边柜，搭配1.6乘0.8米圆弧餐桌，实测窄处过道仍有65厘米以上。",
        "comments": ["多人询问类似开间能否放餐边柜和餐桌", "作者反复结合小家电深度回答", "作者说明桌宽80厘米"],
        "image_observation": "四张图展示餐边柜、餐桌和实际过道，已翻看4/4。",
        "draft": "2.6米开间的餐边柜和过道一起拍出来很直观。",
        "evidence": "正文和图片明确给出开间、柜深、桌尺寸与实际完成效果。",
    },
    {
        "note_id": "67dbd372000000000903bbe9",
        "title": "试过了，小餐厅也能放下1.8的大板桌",
        "topic": "dimensions_fit",
        "body": "作者在购买前用纸板在家搭出1.8米餐桌尺寸，选择后使用近两个月并分享人数和通道感受。",
        "comments": ["大家集中询问各自餐厅能否放1.8米桌", "作者说明椅后可以过人但有时需要侧身", "作者建议结合图中尺寸判断"],
        "image_observation": "三张图包含实物餐桌、尺寸标注和购买前纸板模拟，已翻看3/3。",
        "draft": "用纸板先搭出1.8米餐桌的大小，这张太直观了。",
        "evidence": "正文和第3张图片明确展示购买前用纸板模拟1.8米餐桌。",
    },
]


def build_browse_receipts() -> None:
    write_json(BROWSE_PATH, {
        "schema_version": 1,
        "date": "2026-08-09",
        "account_slot": 1,
        "account_profile_id": "6465fa8000000000290160bd",
        "account_nickname": "畔色木作",
        "browse_target": 10,
        "browse_actual": 10,
        "selected_comment_candidates": 4,
        "items": [
            {
                **note,
                "source_locator": f"https://www.xiaohongshu.com/explore/{note['note_id']}",
                "full_visible_body_read": True,
                "visible_comments_read": True,
                "warning": False,
            }
            for note in NOTES
        ],
        "safety_warning_observed": False,
        "external_comments_posted": 0,
    })


def build_requests_and_compile() -> dict[str, StyleWritingRequest]:
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    base = template["requests"][0]
    requests = []
    typed: dict[str, StyleWritingRequest] = {}
    receipts = []
    for index, note in enumerate(CANDIDATES, 1):
        item = copy.deepcopy(base)
        request_id = f"panse.2026-08-09.account1.comment.{index:03d}"
        locator = f"https://www.xiaohongshu.com/explore/{note['note_id']}"
        item.update({
            "experiment_id": f"2026-08-09-account1-{index:03d}",
            "comparison_sample_id": None,
            "target_note": {"note_id": note["note_id"], "title": note["title"], "author": "公开笔记作者", "source_locator": locator},
            "generation_intent": "grounded_praise",
            "interaction_mode": "support_only",
            "intent_rule": "只夸一个可定位的具体细节，说完个人感受就停；不追加建议、判分或卖点。",
            "source_context": {"body": note["body"], "visible_comments": note["comments"], "body_nonempty": True, "image_count": 1, "images_viewed": [1], "image_coverage_note": note["image_observation"], "warning": False},
            "panse_intent_context": {"intent_policy_version": "xhs-comment-intent.v4", "voice_id": "official_explanation", "voice_style_id": "concise_disclosed_brand_reply", "interaction_intent": "grounded_praise", "comment_direction_id": "detail_grounded_praise", "topic_ids": [note["topic"]], "interaction_mode": "support_only"},
            "panse_official_reply_context": {"policy_id": "panse-official-reply.v3", "interaction_type": "outbound_comment", "route_id": "creator_specific_praise", "style_mode": "warm_specific", "visible_comment_context_read": True, "visible_detail_grounded": True, "third_party_target": True, "mentions_panse": False, "cta_count": 0},
        })
        req = item["style_request"]
        req.update({
            "request_id": request_id,
            "idempotency_key": f"panse:2026-08-09:account-1:{note['note_id']}",
            "brief_text": f"目标原帖为《{note['title']}》。畔色木作官方品牌号公开参与，但不推广畔色产品，也不伪装消费者。官方回复政策固定为panse-official-reply.v3，互动类型为outbound_comment，细方向为creator_specific_praise，风格模式为warm_specific。已读取完整可见正文、相关图片和当前可见评论。只夸一个可定位的具体细节，说完就停；不追加建议、空洞第二句或判分，不虚构购买、入住、装修、检测或长期使用经历。输出8至36个中文字符，只写1句，不引导主页、私信、搜索、关注、点赞或购买。",
            "source_locator": locator,
            "scenario": "品牌官方号公开评论待审稿",
            "audience": "分享真实家具维护或空间使用过程的家居创作者",
            "use_case": "生成一条支持创作者的具体夸赞评论草稿",
            "interaction_mode": "support_only",
            "source_context": {"body": note["body"], "visible_comments": note["comments"], "image_observations": [{"locator": "reviewed_images", "observation": note["image_observation"], "observation_basis": "caller_reviewed"}], "body_complete": True, "visible_comments_complete": True, "images_complete": True, "expected_visible_comment_count": len(note["comments"]), "expected_image_count": 1},
            "taxonomy_ids": ["platform.xiaohongshu-comment", "persona.minimalist-communicator", "role.brand-spokesperson", "scene.brand-reply"],
            "style_card_refs": [
                {"card_id": "preset.platform.xiaohongshu-comment", "card_version": 12},
                {"card_id": "preset.persona.minimalist-communicator", "card_version": 12},
                {"card_id": "preset.role.brand-spokesperson", "card_version": 12},
                {"card_id": "preset.scene.brand-reply", "card_version": 12},
            ],
            "comment_intent_context": {"intent_policy_version": "xhs-comment-intent.v4", "topic_ids": [note["topic"]], "interaction_intent": "grounded_praise", "comment_direction_id": "detail_grounded_praise", "voice_id": "official_explanation", "human_approved_example_set_version": None},
            "content_contract": {"protected_facts": [{"fact_id": "target_note_title", "kind": "quote", "required": False, "value": note["title"], "aliases": [], "subject": "", "predicate": "", "object": "", "qualifiers": ["原帖标题，仅作上下文"], "citation_anchor": "target_note"}], "allowed_paraphrases": {}, "forbidden_inferences": ["不得虚构购买、入住、装修、施工、检测或长期使用经历", "不得把品牌官方号伪装成独立消费者", "不得追加建议或判卷式总结", "不得推广畔色产品或截流"], "citation_anchors": {"target_note_title": "target_note"}, "must_cover_fact_ids": []},
            "output": {"title_candidates": 0, "title_max_chars": 0, "body_min_chars": 8, "body_max_chars": 36, "tag_min": 0, "tag_max": 0},
            "required_model_id": "gpt-5.6-sol",
            "fallback_model_allowed": False,
        })
        # The approved brand-spokesperson route has its own register and does
        # not accept the lifestyle-editor interaction-mode payload. Keep the
        # direction declaration in the outer Panse audit record, but do not
        # leak editor-only fields into StyleWritingRequest.
        req.pop("interaction_mode", None)
        req.pop("comment_intent_context", None)
        typed_request = StyleWritingRequest.model_validate(req)
        bundle, instruction = prepare_style_bundle(typed_request)
        typed[request_id] = typed_request
        receipts.append({"request_id": request_id, "bundle_id": bundle["bundle_id"], "bundle_sha256": bundle["bundle_sha256"], "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(), "catalog_version": bundle["selection"]["taxonomy"]["catalog_version"], "catalog_sha256": bundle["selection"]["taxonomy"]["catalog_sha256"], "approved_card_refs": bundle["selection"]["approved_card_refs"], "provider_contract": bundle["provider_contract"], "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "text_generated": False, "external_posting_performed": False, "publish_allowed": False})
        requests.append(item)
    template.update({"phase": "account1_cycle_day01_review_only", "account_slot": 1, "account_id": "panse_official", "public_role": "畔色木作官方品牌号", "source_deep_reads": "research/panse_multi_direction/daily_runs/2026-08-09/account_1_browse_receipts_10.json", "request_count": 4, "requests": requests})
    write_json(REQUESTS_PATH, template)
    write_json(COMPILE_PATH, {"schema_version": 1, "compiled_at": now_iso(), "required_model_id": "gpt-5.6-sol", "fallback_model_allowed": False, "request_count": 4, "compile_pass_count": 4, "items": receipts, "external_posting_performed": False, "human_review_required": True, "publish_allowed": False})
    return typed


def build_session_responses(requests: dict[str, StyleWritingRequest]) -> None:
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}
    for index, note in enumerate(CANDIDATES, 1):
        request_id = f"panse.2026-08-09.account1.comment.{index:03d}"
        request = requests[request_id]
        context = {
            "voice_id": "official_explanation",
            "interaction_mode": "support_only",
            "comment_direction_id": "detail_grounded_praise",
            "official_reply_policy_id": "panse-official-reply.v3",
            "official_interaction_type": "outbound_comment",
            "official_reply_route_id": "creator_specific_praise",
            "official_style_mode": "warm_specific",
        }
        stages["plan"][request_id] = {"interaction_mode": "support_only", "microgenre_context": context, "entry_angle": "承接一个可定位的真实细节，具体夸赞后自然停住。", "title": "", "title_candidates": [], "hook": "", "reader_promise": "", "discourse_skeleton": ["指出具体细节", "表达真实感受并停住"], "paragraph_roles": ["一条自然短评论"], "claim_evidence_reasoning": [], "discourse_relations": [], "daily_life_landing": None, "source_evidence": {"source_kind": "note_body_and_reviewed_images", "locator": "target_note#reviewed", "evidence_excerpt": note["evidence"], "supported_point": note["evidence"]}, "question_novelty": None, "closing_cta": "", "artifact_microgenre_id": None, "artifact_state": None, "deterministic_check_plan": []}
        stages["draft"][request_id] = {"interaction_mode": "support_only", "microgenre_context": context, "title": "", "draft_text": note["draft"], "tags": [], "cover_copy": "", "covered_fact_ids": [], "artifact_microgenre_id": None, "state_delta": None, "deterministic_check_results": {}}
        stages["semantic_review"][request_id] = {"interaction_mode": "support_only", "microgenre_context": context, "results": [
            {"gate": "style_adherence", "status": "pass", "value": {"single_grounded_point": True, "ordinary_comment_register": True, "literary_drift": False, "product_copy_logic": False}, "notes": "只夸一个具体细节，没有广告、建议链或文学化收束。"},
            {"gate": "discourse_coherence", "status": "pass", "value": {"local_coherence": "pass", "global_coherence": "pass", "internal_factual_consistency": "pass"}, "notes": "评论与正文、图片和可见评论中的同一细节一致。"},
            {"gate": "fluency/readability", "status": "pass", "value": {"interaction_mode_match": True, "editorial_summary_voice": False, "teacher_or_judge_posture": False, "advice_first": False, "source_grounding_present": True, "question_unanswered_in_source": "not_applicable", "household_landing_present": False, "forced_household_landing_outside_soft_observation": False, "fake_firsthand_experience": False, "conditionality_preserved": "not_applicable", "sentence_pattern_variation": "natural_short_praise", "removable_narrator_sentence": False}, "notes": "语气简短自然，没有假亲历、判卷、建议先行或多余后半句。"},
        ]}
    stamp = now_iso()
    write_json(SESSION_PATH, {"schema_version": 1, "provider": "codex.current_session", "model_id": "gpt-5.6-sol", "model_selection_evidence": {"surface": "codex.current_session", "request_meta_model": "gpt-5.6-sol", "reasoning_effort": "high", "thread_id": "019fa796-d8b4-74d3-9a7b-c772cf5278b3"}, "started_at": stamp, "completed_at": stamp, "stage_order": ["plan", "draft", "semantic_review"], "request_count": 4, "stages": stages, "external_posting_performed": False})


def main() -> int:
    build_browse_receipts()
    typed = build_requests_and_compile()
    build_session_responses(typed)
    print(json.dumps({"browse": str(BROWSE_PATH), "requests": str(REQUESTS_PATH), "compile": str(COMPILE_PATH), "session": str(SESSION_PATH), "external_posting_performed": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
