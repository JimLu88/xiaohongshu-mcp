#!/usr/bin/env python3
"""Static gates for the second offline Xiaohongshu article stockpile."""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research" / "panse_multi_direction"
STOCKPILE = BASE / "article_stockpile_batch02_2026-08-09.md"
MANIFEST = STOCKPILE.with_suffix(".json")
CANDIDATES = BASE / "second_wave_article_candidates_v1.json"
PREFLIGHT = BASE / "second_wave_article_preflight_queue_v1.json"

BODY_LIMITS = {
    1: (600, 950),
    2: (650, 1000),
    3: (600, 950),
    4: (600, 900),
}

BANNED_AI_PHRASES = (
    "综上所述",
    "值得注意的是",
    "在当今社会",
    "不难发现",
    "总而言之",
    "真正的核心是",
)


def compact_length(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def bold_markers(block: str) -> list[re.Match[str]]:
    return list(re.finditer(r"^\*\*[^\n]+\*\*.*$", block, re.MULTILINE))


def main() -> int:
    text = STOCKPILE.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    preflight = json.loads(PREFLIGHT.read_text(encoding="utf-8"))
    blocks = text.split("\n---\n")
    failures: list[str] = []

    if len(blocks) != 4:
        failures.append(f"expected 4 article blocks, got {len(blocks)}")
    if manifest.get("publish_allowed") is not False:
        failures.append("manifest must keep publication disabled")
    if manifest.get("external_posting_performed") is not False:
        failures.append("manifest must record no external posting")
    if manifest.get("required_model_id") != "gpt-5.6-sol":
        failures.append("required model drifted from gpt-5.6-sol")
    if len(manifest.get("articles", [])) != 4:
        failures.append("manifest must contain exactly 4 article drafts")
    if len(candidates.get("candidates", [])) != 4:
        failures.append("source package must contain exactly 4 candidates")
    if '"AUTO"' in CANDIDATES.read_text(encoding="utf-8"):
        failures.append("hydrated candidate package still contains AUTO hashes")
    if preflight.get("summary", {}).get("preconditions_ready") != 4:
        failures.append("all 4 source-ready candidates must pass preflight")
    if preflight.get("summary", {}).get("rejected_by_precondition") != 0:
        failures.append("source-ready preflight queue unexpectedly rejected a candidate")

    for index, block in enumerate(blocks, start=1):
        markers = bold_markers(block)
        if len(markers) < 7:
            failures.append(f"article {index}: incomplete metadata sections")
            continue

        title_section = block[markers[0].end() : markers[1].start()]
        titles = [
            re.sub(r"^\d+\.\s*", "", line)
            for line in title_section.splitlines()
            if re.match(r"^\d+\.\s+", line)
        ]
        body = block[markers[2].end() : markers[3].start()].strip()
        body_length = compact_length(body)
        tags = re.findall(r"#[^\s#]+", markers[3].group(0))

        if len(titles) != 5:
            failures.append(f"article {index}: expected 5 title candidates")
        for title in titles:
            if len(title) > 20:
                failures.append(f"article {index}: title exceeds 20 chars: {title}")
        low, high = BODY_LIMITS[index]
        if not low <= body_length <= high:
            failures.append(
                f"article {index}: body length {body_length} outside {low}-{high}"
            )
        if not 5 <= len(tags) <= 8:
            failures.append(f"article {index}: expected 5-8 tags, got {len(tags)}")
        if "家具品牌项目团队" not in body:
            failures.append(f"article {index}: missing affiliation disclosure")
        if "`publish_allowed=false`" not in block:
            failures.append(f"article {index}: missing fail-closed publish marker")
        if "**配图清单**" not in block or "**事实锚点**" not in block:
            failures.append(f"article {index}: missing visual list or fact anchors")

        manifest_article = manifest["articles"][index - 1]
        if manifest_article.get("body_chars_without_whitespace") != body_length:
            failures.append(f"article {index}: manifest body length is stale")
        if manifest_article.get("title_candidate_count") != len(titles):
            failures.append(f"article {index}: manifest title count is stale")
        if manifest_article.get("publish_allowed") is not False:
            failures.append(f"article {index}: publish gate must fail closed")

        for phrase in BANNED_AI_PHRASES:
            if phrase in body:
                failures.append(f"article {index}: residual AI phrase: {phrase}")

    for candidate in candidates.get("candidates", []):
        evidence_types = {
            item.get("evidence_type") for item in candidate.get("evidence_pack", [])
        }
        if len(evidence_types) < 3:
            failures.append(
                f"{candidate.get('candidate_id')}: fewer than 3 evidence types"
            )
        fact_contract = candidate.get("fact_contract", {})
        if not fact_contract.get("must_cover_fact_ids"):
            failures.append(f"{candidate.get('candidate_id')}: missing must-cover facts")
        if candidate.get("identity", {}).get("fake_consumer_identity") is not False:
            failures.append(f"{candidate.get('candidate_id')}: identity gate failed")

    if failures:
        print("second article stockpile validation failed")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("second article stockpile validation passed")
    for index, block in enumerate(blocks, start=1):
        markers = bold_markers(block)
        body = block[markers[2].end() : markers[3].start()].strip()
        print(f"- article {index}: {compact_length(body)} chars, human review required")
    print("- source briefs: 4 ready, 4 blocked pending project-owned evidence")
    print("- external publication: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
