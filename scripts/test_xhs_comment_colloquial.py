#!/usr/bin/env python3
"""Regression checks for the Xiaohongshu colloquial comment gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).with_name("lint_xhs_comment_colloquial.py")


def run(text: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--account-kind", "ordinary", "--text", text],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def main() -> int:
    assert run("大件最怕退货，运费最好下单前问清楚").returncode == 1
    assert run("大件最怕退货，运费最好买之前问清楚").returncode == 0
    assert run("这个在哪里下单呀？").returncode == 0
    assert run("六把一起开裂真的太坑爹了").returncode == 1
    assert run("6把一起开裂真的太坑爹了").returncode == 0
    assert run("看了两张图还是没看懂").returncode == 1
    assert run("看了2张图还是没看懂").returncode == 0
    print("colloquial regression checks passed: 7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
