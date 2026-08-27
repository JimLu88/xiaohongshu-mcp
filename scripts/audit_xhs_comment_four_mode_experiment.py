#!/usr/bin/env python3
"""Audit the offline 100-item Tachikoma four-mode comment experiment."""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "research" / "panse_multi_direction"
REAL_PATH = RESEARCH / "style_experiment_real_comments_100_2026-08-06.json"
REQUESTS_PATH = (
    RESEARCH
    / "style_experiment_four_mode_generation_requests_100_2026-08-07.json"
)
DRAFTS_PATH = (
    RESEARCH / "style_experiment_four_mode_codex_drafts_100_2026-08-07.json"
)
COMPILE_PATH = (
    RESEARCH
    / "style_experiment_four_mode_style_compile_receipts_100_2026-08-07.json"
)
OLD_AUDIT_PATH = RESEARCH / "style_experiment_quality_audit_100_2026-08-06.json"
AUDIT_PATH = (
    RESEARCH / "style_experiment_four_mode_quality_audit_100_2026-08-07.json"
)
REPORT_PATH = (
    RESEARCH / "style_experiment_four_mode_100_vs_100_analysis_2026-08-07.md"
)
HUMAN_PACKET_PATH = (
    RESEARCH / "style_experiment_four_mode_human_review_20_2026-08-07.json"
)
HUMAN_SHEET_PATH = (
    RESEARCH / "style_experiment_four_mode_human_review_20_2026-08-07.md"
)

MODE_ORDER = [
    "support_only",
    "curiosity_question",
    "soft_observation",
    "light_humor_or_neutral",
]
HUMAN_SAMPLE_COUNTS = {
    "support_only": 8,
    "curiosity_question": 7,
    "soft_observation": 3,
    "light_humor_or_neutral": 2,
}
TEACHER = re.compile(
    r"更值得参考的是|真正(?:起作用|重要|要看|值得)|关键(?:在于|不是|是)|"
    r"别硬(?:套|按)|比[^。！？\n]{1,36}更有参考|正确做法|才是"
)
FIRST_HAND = re.compile(
    r"(?:^|[，,；;：:\s])(?:我|我们|我家|我们家)"
    r"[^，,；;。！？!?\n]{0,30}"
    r"(?:住|入住|买|购买|装|装修|用|使用|试|体验|养|打理|踩坑)"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def percentile(values: list[int], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


def length_summary(texts: list[str]) -> dict[str, Any]:
    values = [len(text) for text in texts]
    return {
        "minimum": min(values),
        "p25": percentile(values, 0.25),
        "median": statistics.median(values),
        "mean": round(statistics.fmean(values), 2),
        "p75": percentile(values, 0.75),
        "maximum": max(values),
    }


def review_values(item: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    results = item["semantic_review"]["results"]
    fluency = next(result for result in results if result["gate"] == "fluency/readability")
    value = fluency.get("value") if isinstance(fluency.get("value"), dict) else {}
    return value, all(result["status"] == "pass" for result in results)


def finding_codes(item: dict[str, Any]) -> set[str]:
    return {
        finding["code"]
        for finding in item["pipeline_result"]["naturalness_checks"]["findings"]
    }


def provider_check_pass(
    value: Any,
    *,
    positive_expected: bool,
    not_applicable_is_pass: bool = False,
) -> bool:
    """Normalize bool and explanatory-string provider check values."""
    if isinstance(value, bool):
        return value if positive_expected else not value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized.startswith("pass"):
            return True
        if positive_expected and normalized.startswith(("是", "有")):
            return True
        if not positive_expected and normalized.startswith(
            ("无", "否", "没有", "未出现", "未发现")
        ):
            return True
        if normalized.startswith("not_applicable"):
            return not_applicable_is_pass
        if normalized.startswith(("fail", "review")):
            return False
    return False


def item_observations(
    draft: dict[str, Any],
    request_item: dict[str, Any],
) -> dict[str, Any]:
    result = draft["pipeline_result"]
    fluency, semantic_all_pass = review_values(draft)
    codes = finding_codes(draft)
    mode = draft["interaction_mode"]
    text = draft["draft_text"]
    question_answered = bool(
        mode == "curiosity_question"
        and not provider_check_pass(
            fluency.get("question_unanswered_in_source"),
            positive_expected=True,
        )
    )
    missing_household = bool(
        mode == "soft_observation"
        and (
            not provider_check_pass(
                fluency.get("household_landing_present"),
                positive_expected=True,
            )
            or "missing_household_daily_landing" in codes
        )
    )
    forced_household = bool(
        mode != "soft_observation"
        and (
            not provider_check_pass(
                fluency.get("forced_household_landing_outside_soft_observation"),
                positive_expected=False,
            )
            or "forced_household_landing_in_support_mode" in codes
        )
    )
    teacher = bool(
        not provider_check_pass(
            fluency.get("teacher_or_judge_posture"),
            positive_expected=False,
        )
        or "teacher_or_judge_posture" in codes
        or TEACHER.search(text)
    )
    first_hand = bool(
        not provider_check_pass(
            fluency.get("fake_firsthand_experience"),
            positive_expected=False,
        )
        or "fabricated_home_first_hand_voice" in codes
        or FIRST_HAND.search(text)
    )
    source_grounding_missing = not provider_check_pass(
        fluency.get("source_grounding_present"),
        positive_expected=True,
    )
    advice_first = bool(
        not provider_check_pass(
            fluency.get("advice_first"),
            positive_expected=False,
        )
        or "advice_first" in codes
    )
    mode_match = bool(
        draft["interaction_mode"]
        == request_item["interaction_mode"]
        == result["interaction_mode"]
        == result["plan"]["interaction_mode"]
        == result["draft"]["interaction_mode"]
        == draft["semantic_review"]["interaction_mode"]
    )
    automatic_review_pass = all(
        [
            result["status"] == "review_required",
            semantic_all_pass,
            not result["quality"]["hard_failures"],
            result["format_checks"]["all_passed"],
            not result["naturalness_checks"]["repair_required"],
            mode_match,
            not teacher,
            not first_hand,
            not question_answered,
            not missing_household,
            not forced_household,
            not source_grounding_missing,
            not advice_first,
        ]
    )
    near_copy = next(
        gate for gate in result["quality"]["gate_tuple"] if gate["gate"] == "near_copy"
    )
    return {
        "experiment_id": draft["experiment_id"],
        "request_id": draft["request_id"],
        "interaction_mode": mode,
        "draft_text": text,
        "character_length": len(text),
        "pipeline_status": result["status"],
        "mode_match": mode_match,
        "deterministic_hard_gate_pass": not result["quality"]["hard_failures"],
        "format_pass": result["format_checks"]["all_passed"],
        "naturalness_pass": not result["naturalness_checks"]["repair_required"],
        "semantic_all_pass": semantic_all_pass,
        "automatic_review_pass": automatic_review_pass,
        "teacher_or_judge_posture": teacher,
        "fabricated_firsthand_experience": first_hand,
        "question_already_answered": question_answered,
        "missing_household_landing_in_soft_observation": missing_household,
        "forced_household_landing_outside_soft_observation": forced_household,
        "source_grounding_missing": source_grounding_missing,
        "advice_first": advice_first,
        "near_copy_status": near_copy["status"],
        "near_copy_value": near_copy.get("value"),
        "naturalness_finding_codes": sorted(codes),
        "provider_review": draft["semantic_review"],
        "human_review_required": True,
        "publish_allowed": False,
    }


def mode_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    def count(key: str) -> int:
        return sum(bool(item[key]) for item in items)

    total = len(items)
    passed = count("automatic_review_pass")
    return {
        "count": total,
        "automatic_review_pass_count": passed,
        "automatic_review_pass_rate": round(passed / total, 3),
        "character_length": length_summary([item["draft_text"] for item in items]),
        "teacher_or_judge_posture_count": count("teacher_or_judge_posture"),
        "fabricated_firsthand_experience_count": count(
            "fabricated_firsthand_experience"
        ),
        "question_already_answered_count": count("question_already_answered"),
        "missing_household_landing_in_soft_observation_count": count(
            "missing_household_landing_in_soft_observation"
        ),
        "forced_household_landing_outside_soft_observation_count": count(
            "forced_household_landing_outside_soft_observation"
        ),
        "source_grounding_missing_count": count("source_grounding_missing"),
        "advice_first_count": count("advice_first"),
        "semantic_all_pass_count": count("semantic_all_pass"),
        "naturalness_pass_count": count("naturalness_pass"),
        "format_pass_count": count("format_pass"),
        "hard_gate_pass_count": count("deterministic_hard_gate_pass"),
    }


def select_evenly(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if count >= len(items):
        return items
    positions = [round(index * (len(items) - 1) / (count - 1)) for index in range(count)]
    return [items[position] for position in positions]


def main() -> int:
    real = read_json(REAL_PATH)
    requests_payload = read_json(REQUESTS_PATH)
    drafts_payload = read_json(DRAFTS_PATH)
    compile_payload = read_json(COMPILE_PATH)
    request_by_id = {
        item["experiment_id"]: item for item in requests_payload["requests"]
    }
    if {item["experiment_id"] for item in drafts_payload["items"]} != set(request_by_id):
        raise RuntimeError("request/draft experiment IDs do not align")
    observations = [
        item_observations(item, request_by_id[item["experiment_id"]])
        for item in drafts_payload["items"]
    ]
    by_mode = {
        mode: [item for item in observations if item["interaction_mode"] == mode]
        for mode in MODE_ORDER
    }
    summaries = {mode: mode_summary(items) for mode, items in by_mode.items()}
    overall = mode_summary(observations)
    old_counts: dict[str, Any] = {}
    if OLD_AUDIT_PATH.exists():
        old = read_json(OLD_AUDIT_PATH)
        old_counts = old.get("counts", {})

    audited_at = utc_now()
    audit_payload = {
        "schema_version": 2,
        "project": "panse_xiaohongshu",
        "audited_at": audited_at,
        "scope": "local_research_only",
        "inputs": {
            "real_comments": str(REAL_PATH.relative_to(REPO)).replace("\\", "/"),
            "requests": str(REQUESTS_PATH.relative_to(REPO)).replace("\\", "/"),
            "drafts": str(DRAFTS_PATH.relative_to(REPO)).replace("\\", "/"),
            "compile_receipts": str(COMPILE_PATH.relative_to(REPO)).replace(
                "\\", "/"
            ),
        },
        "provider_contract": drafts_payload["provider_contract"],
        "compile_pass_count": compile_payload["compile_pass_count"],
        "requested_mode_counts": requests_payload["interaction_mode_counts"],
        "overall": overall,
        "by_interaction_mode": summaries,
        "real_comment_length": length_summary(
            [item["comment_text"] for item in real["samples"]]
        ),
        "prior_v9_counts_for_context": old_counts,
        "items": observations,
        "interpretation": {
            "automatic_metrics_are_human_truth": False,
            "semantic_review_is_provider_result": True,
            "human_review_required": True,
            "production_contract_updated": False,
            "external_posting_performed": False,
        },
        "human_review_required": True,
        "publish_allowed": False,
        "external_posting_performed": False,
    }
    AUDIT_PATH.write_text(
        json.dumps(audit_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    selected = []
    for mode in MODE_ORDER:
        selected.extend(select_evenly(by_mode[mode], HUMAN_SAMPLE_COUNTS[mode]))
    packet_items = []
    for item in selected:
        request_item = request_by_id[item["experiment_id"]]
        plan = next(
            draft["plan"]
            for draft in drafts_payload["items"]
            if draft["experiment_id"] == item["experiment_id"]
        )
        packet_items.append(
            {
                **item,
                "target_note": request_item["target_note"],
                "source_context": request_item["source_context"],
                "source_evidence": plan["source_evidence"],
                "question_novelty": plan["question_novelty"],
                "human_labels": {
                    "specific_and_source_grounded": None,
                    "ordinary_user_register": None,
                    "mode_match": None,
                    "question_really_unanswered": None,
                    "household_landing_correctly_scoped": None,
                    "teacher_or_judge_posture": None,
                    "fabricated_firsthand_experience": None,
                    "publishable_after_human_edit": None,
                    "reviewer_notes": "",
                },
            }
        )
    HUMAN_PACKET_PATH.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": audited_at,
                "sample_count": len(packet_items),
                "sample_counts_by_mode": HUMAN_SAMPLE_COUNTS,
                "review_status": "not_started",
                "items": packet_items,
                "publish_allowed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    rows = []
    for index, item in enumerate(packet_items, 1):
        evidence = item["source_evidence"]
        rows.append(
            f"### {index}. {item['experiment_id']} · `{item['interaction_mode']}`\n\n"
            f"- 原帖：{item['target_note'].get('title') or '（无标题）'}\n"
            f"- 草稿：{item['draft_text']}\n"
            f"- 证据：`{evidence['locator']}` — {evidence['evidence_excerpt']}\n"
            "- [ ] 具体且能由来源支持\n"
            "- [ ] 像普通用户，不像老师/评委/设计顾问\n"
            "- [ ] interaction_mode 匹配\n"
            "- [ ] 问题确实未被正文或评论回答（非提问模式勾不适用）\n"
            "- [ ] 家庭日常落点只在 soft_observation 出现且不生硬\n"
            "- [ ] 没有虚构第一手经历\n"
            "- [ ] 人工修改后可用\n"
            "- 备注：\n"
        )
    HUMAN_SHEET_PATH.write_text(
        "# 畔色小红书家居评论四模式人工复核表（20 条）\n\n"
        "状态：**未开始人工复核**。本表只用于本地研究，不代表发布许可。"
        "完整正文和全部可见评论保存在同名 JSON 复核包中。\n\n"
        + "\n".join(rows),
        encoding="utf-8",
    )

    report_lines = [
        "# 畔色小红书家居评论四模式 100 条实验报告",
        "",
        f"审计时间：{audited_at}",
        "",
        "## 结论",
        "",
        f"100 条请求均完成 plan → draft → deterministic gates → semantic review；"
        f"自动复核通过 {overall['automatic_review_pass_count']}/100。"
        "这些结果仍全部需要人工复核，且全部 publish=false。",
        "",
        "## 四模式结果",
        "",
        "| 模式 | 数量 | 自动复核通过 | 长度 min/中位/均值/max | 老师感 | 虚构经历 | 问题已回答 | soft 缺落点 | 非 soft 误加落点 |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for mode in MODE_ORDER:
        summary = summaries[mode]
        lengths = summary["character_length"]
        report_lines.append(
            f"| `{mode}` | {summary['count']} | "
            f"{summary['automatic_review_pass_count']}/{summary['count']} "
            f"({summary['automatic_review_pass_rate']:.1%}) | "
            f"{lengths['minimum']}/{lengths['median']}/{lengths['mean']}/{lengths['maximum']} | "
            f"{summary['teacher_or_judge_posture_count']} | "
            f"{summary['fabricated_firsthand_experience_count']} | "
            f"{summary['question_already_answered_count']} | "
            f"{summary['missing_household_landing_in_soft_observation_count']} | "
            f"{summary['forced_household_landing_outside_soft_observation_count']} |"
        )
    report_lines.extend(
        [
            "",
            "## 口径",
            "",
            "- 自动复核通过不等于可发布：它要求硬门、格式、自然度、模式一致性和三项 provider 软评审均通过。",
            "- 问题是否已回答、source grounding 和语域判断属于 provider result，不是假装成确定性事实。",
            "- 老师感、建议先行、第一手经历、长度和已知模板由本地规则另行检查。",
            "- 完整原帖正文和可见评论只保存在本地研究输入中，没有进入 Style Card 数据库。",
            "",
            "## 人工复核",
            "",
            "已分层抽取 20 条并生成复核表；当前状态是未开始，不能声称人工复核完成。",
            "",
            "## 副作用",
            "",
            "- 生产基础契约：未更新。",
            "- 真实发布、点赞、收藏、关注、回复：均未发生。",
        ]
    )
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "audit_path": str(AUDIT_PATH.relative_to(REPO)),
                "report_path": str(REPORT_PATH.relative_to(REPO)),
                "human_review_sheet": str(HUMAN_SHEET_PATH.relative_to(REPO)),
                "human_review_packet": str(HUMAN_PACKET_PATH.relative_to(REPO)),
                "overall": overall,
                "by_interaction_mode": summaries,
                "human_review_status": "not_started",
                "production_contract_updated": False,
                "external_posting_performed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
