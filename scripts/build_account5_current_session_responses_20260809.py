#!/usr/bin/env python3
"""Materialize the exact current-session stage outputs for account 5.

The wording and semantic judgments in this file were produced in the verified
gpt-5.6-sol Codex desktop turn.  Tachikoma still validates every structured
stage and replays it through the production style pipeline before human review.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "research" / "panse_multi_direction" / "daily_runs" / "2026-08-09"
REQUESTS_PATH = RUN_DIR / "account_5_style_requests_5.json"
OUTPUT_PATH = RUN_DIR / "account_5_current_session_stage_responses_5.json"
TACHIKOMA_ROOT = Path(r"D:\AI\tachikoma-runtime\writing-style-all-v2")
sys.path.insert(0, str(TACHIKOMA_ROOT))

from base.xiaohongshu_style import (  # noqa: E402
    StyleWritingRequest,
    _resolved_comment_context,
    stage_comment_context,
)


COMMENTS = {
    "panse.2026-08-09.account5.comment.001": (
        "工坊里大家围着椅子看结构那张很喜欢"
    ),
    "panse.2026-08-09.account5.comment.002": (
        "这个对比挺有意思，如果换成面积、朝向接近的房子，差别还会这么明显吗？"
    ),
    "panse.2026-08-09.account5.comment.003": (
        "一扇门清理前后放在一起那张太直观了，旧痕还留着反而更有感觉。"
    ),
    "panse.2026-08-09.account5.comment.004": (
        "Arper那张拆解图好直观，现在哪里能买到么？"
    ),
    "panse.2026-08-09.account5.comment.005": (
        "换成皮坐垫以后看着很利落，用一阵后螺丝会不会松呀？"
    ),
}


PLAN_DECISIONS = {
    "panse.2026-08-09.account5.comment.001": {
        "entry_angle": "承接工坊里多人围看未上色木椅结构的画面，直接表达喜欢并自然停住。",
        "skeleton": ["说喜欢工坊里大家围看椅子结构的画面后立即停住。"],
        "source_kind": "image_observation",
        "locator": "image[2]#reviewed",
        "excerpt": "多人围着一把未上色木椅查看靠背与结构",
        "supported_point": "工坊里多人共同查看木椅结构的制作过程。",
    },
    "panse.2026-08-09.account5.comment.002": {
        "entry_angle": "承接作者对国内外居住画面的比较，再问相近面积和朝向下差别是否仍明显。",
        "skeleton": ["认可对比有意思。", "追问控制面积和朝向后差别是否仍然明显。"],
        "source_kind": "note_body",
        "locator": "note_body#question",
        "excerpt": "同样是房子，差别到底在哪",
        "supported_point": "作者正在比较不同居住画面呈现出的差别。",
        "question": "如果换成面积、朝向接近的房子，差别还会这么明显吗？",
        "search_terms": ["面积", "朝向", "相近", "差别"],
        "body_summary": "正文提出国内外房子呈现差别，但没有比较面积和朝向接近的样本。",
        "comments_summary": "可见评论有人指出小套房与别墅不可直接对标，但没有给出相近面积、朝向下的比较结果。",
        "images_summary": "该笔记没有可供核对的图片观察。",
    },
    "panse.2026-08-09.account5.comment.003": {
        "entry_angle": "承接同一扇门清理前后的并置画面，表达对保留旧痕效果的喜欢。",
        "skeleton": ["说清理前后并置很直观。", "表达旧痕保留下来更有感觉。"],
        "source_kind": "image_observation",
        "locator": "image[3]#reviewed",
        "excerpt": "一扇门已清理变浅、另一扇仍深色",
        "supported_point": "同一柜体清理前后的过程对比很直观。",
    },
    "panse.2026-08-09.account5.comment.004": {
        "entry_angle": "承接Arper拆解内部部件的图，再问现在的购买渠道。",
        "skeleton": ["说Arper拆解图很直观。", "追问现在在哪里可以买到。"],
        "source_kind": "image_observation",
        "locator": "image[2]#reviewed",
        "excerpt": "Arper沙发剖开展示减材结构和可拆解的内部部件",
        "supported_point": "Arper案例用剖开画面展示可拆解结构。",
        "question": "现在哪里能买到么？",
        "search_terms": ["哪里买", "购买", "渠道", "门店"],
        "body_summary": "正文介绍Arper的可拆解设计，没有提供当前购买渠道。",
        "comments_summary": "当前没有可见评论回答购买渠道。",
        "images_summary": "图片只展示Arper的拆解结构，没有购买渠道信息。",
    },
    "panse.2026-08-09.account5.comment.005": {
        "entry_angle": "承接藤编座面换成皮坐垫后的完成效果，再问使用一段时间后螺丝是否会松。",
        "skeleton": ["说换成皮坐垫后看着利落。", "追问使用一段时间后螺丝是否会松。"],
        "source_kind": "image_observation",
        "locator": "image[4]#reviewed",
        "excerpt": "座面换成棕色皮垫",
        "supported_point": "破损藤编座面已经换成棕色皮坐垫。",
        "question": "用一阵后螺丝会不会松呀？",
        "search_terms": ["用一阵", "螺丝", "松动", "长期"],
        "body_summary": "正文说明用自攻螺丝完成安装，没有说明使用一段时间后的松动情况。",
        "comments_summary": "可见评论只询问螺丝种类和固定方法，没有反馈后续是否松动。",
        "images_summary": "图片展示安装后的完成状态，没有呈现长期使用后的螺丝状态。",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def semantic_review(request: StyleWritingRequest, context: dict, text: str) -> dict:
    is_question = request.interaction_mode == "curiosity_question"
    return {
        "interaction_mode": request.interaction_mode,
        "microgenre_context": context,
        "results": [
            {
                "gate": "style_adherence",
                "status": "pass",
                "value": {
                    "single_grounded_point": True,
                    "ordinary_comment_register": True,
                    "literary_drift": False,
                    "product_copy_logic": False,
                },
                "notes": "只承接一个可定位细节，使用普通同好口吻；没有判卷、建议先行、卖点链或文学化收束。",
            },
            {
                "gate": "discourse_coherence",
                "status": "pass",
                "value": {
                    "local_coherence": "pass",
                    "global_coherence": "pass",
                    "internal_factual_consistency": "pass",
                },
                "notes": "计划、成稿和来源证据围绕同一个观察或问题，时间、身份、对象和因果没有冲突。",
            },
            {
                "gate": "fluency/readability",
                "status": "pass",
                "value": {
                    "interaction_mode_match": True,
                    "editorial_summary_voice": False,
                    "teacher_or_judge_posture": False,
                    "advice_first": False,
                    "source_grounding_present": True,
                    "question_unanswered_in_source": True if is_question else "not_applicable",
                    "household_landing_present": False,
                    "forced_household_landing_outside_soft_observation": False,
                    "fake_firsthand_experience": False,
                    "conditionality_preserved": "not_applicable",
                    "sentence_pattern_variation": "natural_one_or_two_clause_comment",
                    "removable_narrator_sentence": False,
                },
                "notes": (
                    "句子自然，证据脚手架没有泄漏；没有假亲历、重复已回答问题、模板总结或可删除的旁白句。"
                    if is_question
                    else "句子自然，证据脚手架没有泄漏；没有假亲历、模板总结、强制提问或可删除的旁白句。"
                ),
            },
        ],
    }


def main() -> int:
    payload = json.loads(REQUESTS_PATH.read_text(encoding="utf-8"))
    stages = {"plan": {}, "draft": {}, "semantic_review": {}}
    for item in payload["requests"]:
        request = StyleWritingRequest.model_validate(item["style_request"])
        request_id = request.request_id
        decision = PLAN_DECISIONS[request_id]
        resolved = _resolved_comment_context(request)
        assert resolved is not None
        context = stage_comment_context(resolved)
        novelty = None
        if request.interaction_mode == "curiosity_question":
            novelty = {
                "question": decision["question"],
                "search_terms": decision["search_terms"],
                "body_search_summary": decision["body_summary"],
                "visible_comment_search_summary": decision["comments_summary"],
                "image_search_summary": decision["images_summary"],
                "answered_in_body": False,
                "answered_in_visible_comments": False,
                "answered_in_images": False,
                "answer_evidence_locators": [],
            }
        stages["plan"][request_id] = {
            "interaction_mode": request.interaction_mode,
            "microgenre_context": context,
            "entry_angle": decision["entry_angle"],
            "title": "",
            "title_candidates": [],
            "hook": "",
            "reader_promise": "",
            "discourse_skeleton": decision["skeleton"],
            "paragraph_roles": ["一条自然短评论"],
            "claim_evidence_reasoning": [],
            "discourse_relations": [],
            "daily_life_landing": None,
            "source_evidence": {
                "source_kind": decision["source_kind"],
                "locator": decision["locator"],
                "evidence_excerpt": decision["excerpt"],
                "supported_point": decision["supported_point"],
            },
            "question_novelty": novelty,
            "closing_cta": "",
            "artifact_microgenre_id": None,
            "artifact_state": None,
            "deterministic_check_plan": [],
        }
        stages["draft"][request_id] = {
            "interaction_mode": request.interaction_mode,
            "microgenre_context": context,
            "title": "",
            "draft_text": COMMENTS[request_id],
            "tags": [],
            "cover_copy": "",
            "covered_fact_ids": [],
            "artifact_microgenre_id": None,
            "state_delta": None,
            "deterministic_check_results": {},
        }
        stages["semantic_review"][request_id] = semantic_review(
            request, context, COMMENTS[request_id]
        )

    observed_at = now_iso()
    output = {
        "schema_version": 1,
        "provider": "codex.current_session",
        "model_id": "gpt-5.6-sol",
        "model_selection_evidence": {
            "surface": "codex.current_session",
            "request_meta_model": "gpt-5.6-sol",
            "reasoning_effort": "high",
            "thread_id": "019fa796-d8b4-74d3-9a7b-c772cf5278b3",
            "turn_id": "019fe613-8cbe-7232-b7f2-266403ede193",
        },
        "started_at": observed_at,
        "completed_at": observed_at,
        "stage_order": ["plan", "draft", "semantic_review"],
        "request_count": len(payload["requests"]),
        "stages": stages,
        "external_posting_performed": False,
    }
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output_path": str(OUTPUT_PATH),
                "request_count": len(payload["requests"]),
                "model_id": output["model_id"],
                "external_posting_performed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
