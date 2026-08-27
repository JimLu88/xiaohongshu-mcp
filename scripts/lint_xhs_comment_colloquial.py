#!/usr/bin/env python3
"""Fail closed when a Xiaohongshu comment uses known bookish/editorial wording."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_comment_colloquial_lexicon_v1.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument(
        "--account-kind",
        choices=("ordinary", "official"),
        default="ordinary",
    )
    args = parser.parse_args()

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    hits = []
    for item in contract["hard_fail_terms"]:
        term = item["term"]
        if term == "Chinese_numeral_for_quantity":
            continue
        if term in args.text:
            hits.append(
                {
                    "term": term,
                    "plain_options": item.get("plain_options", []),
                }
            )

    quantity_units = "把张个件套台次只位米厘米毫米平米平方米元块岁年天月小时分钟"
    for match in re.finditer(
        rf"(?<![A-Za-z0-9])[一二两三四五六七八九十百千万]+(?=[{quantity_units}])",
        args.text,
    ):
        hits.append(
            {
                "term": "Chinese_numeral_for_quantity",
                "matched_text": match.group(0),
                "plain_options": ["Arabic_numeral"],
            }
        )

    passed = not hits
    result = {
        "passed": passed,
        "contract_id": contract["contract_id"],
        "account_kind": args.account_kind,
        "text": args.text,
        "hard_fail_hits": hits,
        "required_action": (
            "none"
            if passed
            else "rewrite_before_human_review"
        ),
        "automatic_replacement_allowed": False,
        "human_review_required": True,
        "publish_allowed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
