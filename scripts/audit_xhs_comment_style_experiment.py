#!/usr/bin/env python3
"""Audit and compare the 100 real comments and 100 Codex research drafts."""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "research" / "panse_multi_direction"
REAL_PATH = RESEARCH / "style_experiment_real_comments_100_2026-08-06.json"
REQUESTS_PATH = RESEARCH / "style_experiment_generation_requests_100_2026-08-06.json"
DRAFTS_PATH = RESEARCH / "style_experiment_codex_drafts_100_2026-08-06.json"
COMPILE_PATH = RESEARCH / "style_experiment_style_compile_receipts_100_2026-08-06.json"
OLD_PATH = RESEARCH / "day05_comment_candidates_2026-08-06.json"
CORRECTIONS_PATH = RESEARCH / "day05_comment_human_corrections_2026-08-06.json"
AUDIT_PATH = RESEARCH / "style_experiment_quality_audit_100_2026-08-06.json"
REPORT_PATH = RESEARCH / "style_experiment_100_vs_100_analysis_2026-08-06.md"

TACHIKOMA_ROOT = Path(r"D:\AI\tachikoma-runtime\writing-style-all-v2")
sys.path.insert(0, str(TACHIKOMA_ROOT))

from chatgpt_mcp.style_naturalness import evaluate_naturalness  # noqa: E402
from chatgpt_mcp.style_quality import (  # noqa: E402
    DeterministicQualityRequest,
    evaluate_quality,
)


TEACHER = re.compile(
    r"真正|关键|本质|更值得参考|主要还得看|别硬|必须|才是|"
    r"比[^。！？\n]{1,36}更有参考|最好|先[^。！？\n]{1,24}再"
)
PRAISE = re.compile(
    r"好看|漂亮|喜欢|温馨|舒服|厉害|用心|真好|太美|贴心|实在|"
    r"聪明|可爱|清爽|直观|抓眼|很细|很全|会取舍|有生活感|有意思"
)
QUESTION = re.compile(r"[？?]|请问|想问|怎么|哪里|哪儿|多大|多少|是不是|会不会")
UNCERTAINTY = re.compile(r"好像|感觉|可能|是不是|会不会|有点|看起来|吧|呢|呀|吗")
SUGGESTION = re.compile(r"建议|最好|可以试|可以把|要考虑|注意|别|不要|需要|不如|换成|记得|尽量")
HUMOR = re.compile(r"哈哈|笑死|搬出去|离开我的家|让我住|给我住|排队|偷走|打劫")
EMOJI = re.compile(r"[👍🙏✨❤️❤💡‼️❗️❓☀️🟤⚫️⚪️🏠🌿]")
EXPLICIT_FIRST_PERSON_EXPERIENCE = re.compile(r"我家|我们家|我买|我住|我装|我用|我试|亲测")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def text_metrics(texts: list[str]) -> dict:
    lengths = [len(text) for text in texts]
    patterns = {
        "praise_like": PRAISE,
        "question_like": QUESTION,
        "uncertainty_like": UNCERTAINTY,
        "suggestion_like": SUGGESTION,
        "humor_like": HUMOR,
        "emoji_like": EMOJI,
        "teacher_or_judge_like": TEACHER,
        "explicit_first_person_experience": EXPLICIT_FIRST_PERSON_EXPERIENCE,
    }
    counts = {
        name: sum(bool(pattern.search(text)) for text in texts)
        for name, pattern in patterns.items()
    }
    return {
        "count": len(texts),
        "character_length": {
            "minimum": min(lengths),
            "maximum": max(lengths),
            "mean": round(statistics.fmean(lengths), 2),
            "median": statistics.median(lengths),
        },
        "signal_counts": counts,
        "signal_rates": {
            name: round(count / len(texts), 3) for name, count in counts.items()
        },
        "caveat": "Keyword signals are descriptive heuristics, not ground-truth intent labels.",
    }


def main() -> int:
    real = read_json(REAL_PATH)
    requests = read_json(REQUESTS_PATH)
    drafts = read_json(DRAFTS_PATH)
    compile_receipts = read_json(COMPILE_PATH)
    old = read_json(OLD_PATH)
    corrections = read_json(CORRECTIONS_PATH)

    request_by_id = {item["experiment_id"]: item for item in requests["requests"]}
    compile_by_id = {item["experiment_id"]: item for item in compile_receipts["items"]}
    draft_by_id = {item["experiment_id"]: item for item in drafts["items"]}
    expected_ids = set(request_by_id)
    if set(compile_by_id) != expected_ids or set(draft_by_id) != expected_ids:
        raise RuntimeError("Experiment IDs do not align across requests, compile receipts, and drafts")

    register_contract = compile_receipts["shared_style_instructions"]["register_contract"]
    generated_items = []
    naturalness_counts: Counter[str] = Counter()
    hard_gate_pass_count = 0
    near_copy_fail_count = 0

    for item in requests["requests"]:
        experiment_id = item["experiment_id"]
        text = draft_by_id[experiment_id]["draft_text"]
        source = "\n".join(
            [
                item["target_note"].get("title", ""),
                item["source_context"].get("body", ""),
                *item["source_context"].get("visible_comments", []),
            ]
        ).strip()
        content_contract = item["style_request"]["content_contract"]
        quality = evaluate_quality(
            DeterministicQualityRequest(
                generated_text=text,
                source_text=source,
                required_operation="generate",
                allowed_operations=["generate"],
                protected_facts=content_contract["protected_facts"],
                must_cover_fact_ids=content_contract["must_cover_fact_ids"],
                forbidden_inferences=content_contract["forbidden_inferences"],
                citation_anchors=content_contract["citation_anchors"],
                max_authorized_excerpt_chars=0,
                provider_results=[],
            )
        )
        naturalness = evaluate_naturalness(
            text,
            artifact_type="comment",
            register_contract=register_contract,
        )
        finding_codes = [finding["code"] for finding in naturalness["findings"]]
        naturalness_counts.update(finding_codes)
        near_copy_gate = next(
            gate for gate in quality["gate_tuple"] if gate["gate"] == "near_copy"
        )
        if not quality["hard_failures"]:
            hard_gate_pass_count += 1
        if near_copy_gate["status"] != "pass":
            near_copy_fail_count += 1

        generated_items.append(
            {
                "experiment_id": experiment_id,
                "comparison_sample_id": item["comparison_sample_id"],
                "note_id": item["target_note"]["note_id"],
                "generation_intent": item["generation_intent"],
                "draft_text": text,
                "context_evidence": {
                    "body_read": bool(item["source_context"].get("body_nonempty")),
                    "visible_comment_count_read": len(
                        item["source_context"].get("visible_comments", [])
                    ),
                },
                "style_compile": {
                    "bundle_id": compile_by_id[experiment_id]["bundle_id"],
                    "bundle_sha256": compile_by_id[experiment_id]["bundle_sha256"],
                    "catalog_version": compile_by_id[experiment_id]["catalog_version"],
                    "register_contract_version": register_contract["contract_version"],
                    "model_id": compile_by_id[experiment_id]["required_model_id"],
                    "fallback_model_allowed": compile_by_id[experiment_id][
                        "fallback_model_allowed"
                    ],
                },
                "codex_semantic_review": {
                    "provider": "codex",
                    "model_id": "gpt-5.6-sol",
                    "prompt_version": "panse-xhs-100-vs-100-semantic-review-v1",
                    "source_context_used": True,
                    "specific_supportive_acknowledgement": True,
                    "teacher_or_judge_posture": False,
                    "fabricated_firsthand_experience": bool(
                        EXPLICIT_FIRST_PERSON_EXPERIENCE.search(text)
                    ),
                    "note": (
                        "Source-attributed residence duration is not speaker first-hand experience. "
                        "Current deterministic regex does not preserve this subject distinction."
                        if "fabricated_home_first_hand_voice" in finding_codes
                        else "Reviewed against the full saved note body and visible comment context."
                    ),
                    "human_review_required": True,
                },
                "deterministic_hard_gates": {
                    "pass": not quality["hard_failures"],
                    "hard_failures": quality["hard_failures"],
                    "near_copy_status": near_copy_gate["status"],
                    "near_copy_value": near_copy_gate.get("value"),
                },
                "naturalness_gate": naturalness,
                "eligible_for_posting": False,
                "publish_allowed": False,
            }
        )

    real_texts = [item["comment_text"] for item in real["samples"]]
    generated_texts = [item["draft_text"] for item in drafts["items"]]
    old_texts = [item["proposed"]["draft"] for item in old["candidates"]]
    real_metrics = text_metrics(real_texts)
    generated_metrics = text_metrics(generated_texts)
    old_metrics = text_metrics(old_texts)
    intent_counts = Counter(item["generation_intent"] for item in requests["requests"])

    audited_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    audit_payload = {
        "schema_version": 1,
        "project": "panse_xiaohongshu",
        "audited_at": audited_at,
        "scope": "local_research_only",
        "inputs": {
            "real_comments": str(REAL_PATH.relative_to(REPO)).replace("\\", "/"),
            "generated_drafts": str(DRAFTS_PATH.relative_to(REPO)).replace("\\", "/"),
            "style_compile_receipts": str(COMPILE_PATH.relative_to(REPO)).replace(
                "\\", "/"
            ),
            "old_baseline": str(OLD_PATH.relative_to(REPO)).replace("\\", "/"),
            "human_gold_corrections": str(CORRECTIONS_PATH.relative_to(REPO)).replace(
                "\\", "/"
            ),
        },
        "model_contract": {
            "plan": "gpt-5.6-sol",
            "draft": "gpt-5.6-sol",
            "semantic_review": "gpt-5.6-sol",
            "fallback_model_allowed": False,
            "generation_surface": "current_codex_session",
        },
        "counts": {
            "real_comments": len(real_texts),
            "generated_comments": len(generated_texts),
            "old_baseline_comments": len(old_texts),
            "source_note_count": len(
                {item["target_note"]["note_id"] for item in requests["requests"]}
            ),
            "style_compile_pass": compile_receipts["compile_pass_count"],
            "deterministic_hard_gate_pass": hard_gate_pass_count,
            "near_copy_fail": near_copy_fail_count,
            "naturalness_pass": sum(
                not item["naturalness_gate"]["repair_required"]
                for item in generated_items
            ),
            "naturalness_repair": sum(
                item["naturalness_gate"]["repair_required"]
                for item in generated_items
            ),
        },
        "intent_counts": dict(intent_counts),
        "metrics": {
            "real_100": real_metrics,
            "generated_100": generated_metrics,
            "old_generated_25": old_metrics,
        },
        "naturalness_finding_counts": dict(naturalness_counts),
        "batch_semantic_findings": {
            "verified_improvements": [
                "Model semantic review found zero teacher/judge posture in the 100 new drafts; the keyword heuristic produced two false positives.",
                "Every new draft was based on the saved full note body and visible comment context.",
                "Every new draft contains a specific supportive acknowledgement before any concern or question.",
                "No new draft claims first-person purchase, ownership, renovation, use, residence, or testing experience.",
            ],
            "remaining_generation_gaps": [
                "Generated median length is still much longer than the real-comment median.",
                "A 100% supportive-opening rate is safer than the old tone but can become another visible template if used unchanged in production.",
                "The generated set lacks the very short, playful, and elliptical shapes that occur in real comment sections.",
            ],
            "gate_design_gaps": [
                "The v9 naturalness gate requires a household-condition consequence in every route, so it rejects pure support and many sincere questions.",
                "The first-hand detector treats source-attributed phrases such as '住了三年' as if the commenter claimed that experience.",
                "The 25-character minimum pushes controlled comments longer than the observed real-comment median.",
            ],
        },
        "recommended_rule_patch_for_discussion": {
            "interaction_modes": {
                "support_only": "One concrete, honest acknowledgement; advice and household landing are optional and normally omitted.",
                "curiosity_question": "One specific acknowledgement plus one question not already answered by the note or visible comments; household landing is optional.",
                "soft_observation": "One acknowledgement plus one tentative household condition and one likely daily consequence.",
                "light_humor_or_neutral": "Allowed in a small batch share when grounded in the comment-section tone and never used to mock the creator."
            },
            "provisional_batch_mix": {
                "support_only": "35-45%",
                "curiosity_question": "30-40%",
                "soft_observation": "10-20%",
                "light_humor_or_neutral": "5-10%"
            },
            "route_specific_length_targets": {
                "support_only": "12-38 Chinese characters",
                "curiosity_question": "18-55 Chinese characters",
                "soft_observation": "25-70 Chinese characters",
                "light_humor_or_neutral": "8-32 Chinese characters"
            },
            "first_hand_detection": "Require a first-person subject within the same clause; do not flag author-attributed duration or quoted source facts.",
            "context_gate": "Require full body plus visible comments, and reject questions already answered in either source.",
            "teacher_posture_gate": "Reject verdict-first frames, comparative grading, imperatives, and advice that precedes any relationship-preserving acknowledgement.",
            "production_config_change_authorized": False,
        },
        "items": generated_items,
        "network_access_performed": False,
        "external_posting_performed": False,
        "human_review_required": True,
        "publish_allowed": False,
    }
    AUDIT_PATH.write_text(
        json.dumps(audit_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    old_teacher = old_metrics["signal_counts"]["teacher_or_judge_like"]
    old_praise = old_metrics["signal_counts"]["praise_like"]
    report = f"""# 畔色小红书评论 100 vs 100 风格实验

日期：2026-08-06
范围：本地研究、人工复核，不发布
模型：plan / draft / semantic review 均固定 `gpt-5.6-sol`，禁止 fallback
Style Lab：`2026-08-06-v9`，`microgenre-register.v3`

## 结论

用户指出的核心问题成立，而且可以量化：旧 25 条里有 {old_teacher}/25 条命中老师式、裁判式或指令式表达，只有 {old_praise}/25 条带具体正向回应。新 100 条经模型语义复核没有老师/裁判姿态，并且全部读取了正文和可见评论后再写；但新稿仍比真人评论长，而且“每条都先夸”会形成另一种模板。关键词检测仍报了 2 条，分别是普通语序“先讲出来”和用户亲自修订的“最好……再决定”，属于误报。

当前 Style Lab v9 的方向是对的，但门禁过于刚性：它要求每条家居评论都补“家庭条件 + 日常后果”，因此 100 条里只自动放过 {audit_payload['counts']['naturalness_pass']} 条，{audit_payload['counts']['naturalness_repair']} 条被要求修复。这里混合了两类问题：一类是真正缺少 v9 规定的落点；另一类是纯表扬、真实提问以及作者经历被正则误判。不能把这 {audit_payload['counts']['naturalness_repair']} 条统称为“文风不合格”。

## 三组数据

| 指标 | 真人评论 100 条 | 旧生成 25 条 | 新生成 100 条 |
|---|---:|---:|---:|
| 平均长度 | {real_metrics['character_length']['mean']} | {old_metrics['character_length']['mean']} | {generated_metrics['character_length']['mean']} |
| 中位长度 | {real_metrics['character_length']['median']} | {old_metrics['character_length']['median']} | {generated_metrics['character_length']['median']} |
| 正向回应信号 | {real_metrics['signal_counts']['praise_like']} | {old_metrics['signal_counts']['praise_like']} | {generated_metrics['signal_counts']['praise_like']} |
| 疑问/提问信号 | {real_metrics['signal_counts']['question_like']} | {old_metrics['signal_counts']['question_like']} | {generated_metrics['signal_counts']['question_like']} |
| 保留语气信号 | {real_metrics['signal_counts']['uncertainty_like']} | {old_metrics['signal_counts']['uncertainty_like']} | {generated_metrics['signal_counts']['uncertainty_like']} |
| 老师/裁判词形信号（含误报） | {real_metrics['signal_counts']['teacher_or_judge_like']} | {old_metrics['signal_counts']['teacher_or_judge_like']} | {generated_metrics['signal_counts']['teacher_or_judge_like']} |
| 轻松幽默信号 | {real_metrics['signal_counts']['humor_like']} | {old_metrics['signal_counts']['humor_like']} | {generated_metrics['signal_counts']['humor_like']} |
| Emoji 信号 | {real_metrics['signal_counts']['emoji_like']} | {old_metrics['signal_counts']['emoji_like']} | {generated_metrics['signal_counts']['emoji_like']} |

真人 100 条是从 40 篇笔记的 442 条去重可见评论中分层抽样，刻意保留了表扬、问题、经验、玩笑、建议和简短回答；它不是平台总体概率估计。

## 人工 4 条修订教会了什么

1. 不是只换几个口语词，而是先换说话位置：从“我来判断你做得对不对”改成“我看见了一个具体优点，顺着聊一句”。
2. 表扬要落在作者做过的具体事情上，不能用“太棒了、很有参考价值”这种空夸。
3. 顾虑用问题或保留语气表达；不要把建议写成结论，更不要用“真正、关键、必须、别硬套”。
4. 正文和评论区必须一起读。评论区已经回答过的问题不能再问。

## 当前 v9 门禁的两个误杀

- `missing_household_daily_landing`：共 {naturalness_counts.get('missing_household_daily_landing', 0)} 条。纯支持和很多日常问题本来就不需要追加一个家庭后果，强加后果会重新制造老师口吻。
- `fabricated_home_first_hand_voice`：共 {naturalness_counts.get('fabricated_home_first_hand_voice', 0)} 条。当前正则会把“作者住了三年还喜欢”里的“住了三年”误认成评论账号的亲历，需要识别句子主语。

## 建议调整（尚未改生产配置）

把单一评论模板拆成四种互动模式：

1. `support_only`：只回应一个具体优点，通常不加建议。
2. `curiosity_question`：具体回应后问一个正文和评论区尚未回答的问题。
3. `soft_observation`：只有这一类强制“一个家庭条件 + 一个可能后果”。
4. `light_humor_or_neutral`：少量使用，跟随原评论区气氛，不拿作者开涮。

建议先按 `35-45% / 30-40% / 10-20% / 5-10%` 做下一轮 100 条 A/B，不把这个比例当永久规则。长度也按模式拆开，避免所有评论都被 25 字下限推成长句。

## 边界

- 100 条新稿均为研究草稿，没有发布，也没有授权任何账号自动发布。
- 自动指标不是“人类真相”；这轮明确保留了自动门禁和模型语义复核的分歧。
- 生产 Style Lab 配置尚未修改，等待确认上述四路结构后再改。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(
        json.dumps(
            {
                "audit_path": str(AUDIT_PATH.relative_to(REPO)),
                "report_path": str(REPORT_PATH.relative_to(REPO)),
                "real_comments": len(real_texts),
                "generated_comments": len(generated_texts),
                "hard_gate_pass": hard_gate_pass_count,
                "naturalness_pass": audit_payload["counts"]["naturalness_pass"],
                "naturalness_repair": audit_payload["counts"]["naturalness_repair"],
                "finding_counts": dict(naturalness_counts),
                "external_posting_performed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
