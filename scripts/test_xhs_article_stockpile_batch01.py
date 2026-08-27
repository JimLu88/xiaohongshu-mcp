#!/usr/bin/env python3
"""Static gates for the first offline Xiaohongshu article stockpile."""

from __future__ import annotations

import re
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCKPILE = (
    ROOT
    / "research"
    / "panse_multi_direction"
    / "article_stockpile_batch01_2026-08-09.md"
)
MANIFEST = STOCKPILE.with_suffix(".json")

BODY_LIMITS = {
    1: (550, 900),
    2: (450, 750),
    3: (650, 1000),
    4: (500, 850),
}

BANNED_AI_PHRASES = (
    "综上所述",
    "值得注意的是",
    "在当今社会",
    "不难发现",
    "总而言之",
)


def compact_length(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


def bold_markers(block: str) -> list[re.Match[str]]:
    return list(re.finditer(r"^\*\*[^\n]+\*\*.*$", block, re.MULTILINE))


def numbered_lines(value: str) -> list[str]:
    return [
        re.sub(r"^\d+\.\s*", "", line)
        for line in value.splitlines()
        if re.match(r"^\d+\.\s+", line)
    ]


def main() -> int:
    text = STOCKPILE.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    blocks = text.split("\n---\n")
    failures: list[str] = []

    if len(blocks) != 5:
        failures.append(f"expected 5 article/material blocks, got {len(blocks)}")

    if "外部发布：禁止" not in text:
        failures.append("missing document-level external publication prohibition")
    if manifest.get("publish_allowed") is not False:
        failures.append("manifest must keep publication disabled")
    if manifest.get("external_posting_performed") is not False:
        failures.append("manifest must record that no external posting occurred")
    if manifest.get("required_model_id") != "gpt-5.6-sol":
        failures.append("manifest required model drifted from gpt-5.6-sol")
    if len(manifest.get("articles", [])) != 4:
        failures.append("manifest must contain exactly 4 article drafts")

    for index, block in enumerate(blocks[:4], start=1):
        markers = bold_markers(block)
        if len(markers) < 7:
            failures.append(f"article {index}: incomplete metadata sections")
            continue

        title_section = block[markers[0].end() : markers[1].start()]
        titles = numbered_lines(title_section)
        body = block[markers[2].end() : markers[3].start()].strip()
        tags_line = markers[3].group(0)

        if len(titles) != 5:
            failures.append(f"article {index}: expected 5 title candidates, got {len(titles)}")
        for title in titles:
            if len(title) > 20:
                failures.append(f"article {index}: title exceeds 20 chars: {title}")

        body_length = compact_length(body)
        low, high = BODY_LIMITS[index]
        if not low <= body_length <= high:
            failures.append(
                f"article {index}: body length {body_length} outside {low}-{high}"
            )

        tags = re.findall(r"#[^\s#]+", tags_line)
        if not 5 <= len(tags) <= 8:
            failures.append(f"article {index}: expected 5-8 tags, got {len(tags)}")

        if "家具品牌项目团队" not in body:
            failures.append(f"article {index}: missing brand-team affiliation disclosure")
        if "`publish_allowed=false`" not in block:
            failures.append(f"article {index}: missing fail-closed publish marker")
        if "**配图清单**" not in block or "**事实锚点**" not in block:
            failures.append(f"article {index}: missing visual list or fact anchors")

        manifest_article = manifest.get("articles", [{}] * 4)[index - 1]
        if manifest_article.get("body_chars_without_whitespace") != body_length:
            failures.append(f"article {index}: manifest body length is stale")
        if manifest_article.get("title_candidate_count") != len(titles):
            failures.append(f"article {index}: manifest title count is stale")
        if manifest_article.get("publish_allowed") is not False:
            failures.append(f"article {index}: manifest publish gate must fail closed")

        for phrase in BANNED_AI_PHRASES:
            if phrase in body:
                failures.append(f"article {index}: residual AI phrase: {phrase}")

    blocked = blocks[4] if len(blocks) >= 5 else ""
    if "rejected_by_precondition" not in blocked:
        failures.append("blocked image-mix candidate lost its precondition status")
    if "**正文候选**" in blocked:
        failures.append("blocked image-mix candidate must not contain publishable body")
    if "空间提案" not in blocked or "场景合成" not in blocked:
        failures.append("blocked image-mix candidate lacks required disclosure labels")
    blocked_records = manifest.get("blocked_candidates", [])
    if len(blocked_records) != 1 or blocked_records[0].get("status") != "rejected_by_precondition":
        failures.append("manifest must retain exactly one blocked image-mix candidate")

    if failures:
        print("article stockpile validation failed")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("article stockpile validation passed")
    for index, block in enumerate(blocks[:4], start=1):
        markers = bold_markers(block)
        body = block[markers[2].end() : markers[3].start()].strip()
        print(f"- article {index}: {compact_length(body)} chars, human review required")
    print("- image-mix article: blocked pending product-fidelity evidence")
    print("- external publication: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
