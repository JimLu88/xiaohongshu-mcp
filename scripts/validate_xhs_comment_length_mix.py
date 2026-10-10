#!/usr/bin/env python3
"""Validate a complete comment batch before it may enter a sendable state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.xhs_comment_length_mix import validate_comment_batch


def load_input(path: str) -> object:
    return (
        json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
        if path == "-"
        else json.loads(Path(path).read_text(encoding="utf-8"))
    )


def extract_comments(value: object) -> object:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("comments", "comment_drafts", "items"):
            if isinstance(value.get(key), list):
                return value[key]
    raise ValueError("input must be a comment list or contain comments/comment_drafts/items")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_path", help="JSON file or '-' for stdin")
    args = parser.parse_args()
    result = validate_comment_batch(extract_comments(load_input(args.input_path)))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["length_mix_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
