#!/usr/bin/env python3
"""Verify that the QR portal's persisted/public text contains no login secrets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lib.xhs_qr_login import QrStateStore, assert_no_sensitive_data
from xhs_qr_login_portal import DEFAULT_RUNTIME_ROOT, render_page, resolve_account_context


FORBIDDEN_TEXT = (
    re.compile(r"(?i)data:image/[^;]+;base64,"),
    re.compile(r"(?i)set-cookie\s*:"),
    re.compile(r"(?i)authorization\s*:\s*bearer"),
    re.compile(r"\b1\d{10}\b"),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    parser.add_argument("--account-slot", type=int, required=True)
    parser.add_argument("--plan-date", required=True)
    args = parser.parse_args()
    context = resolve_account_context(args.account_slot, args.plan_date)
    store = QrStateStore(
        args.runtime_root / f"slot-{args.account_slot}",
        account_context=context,
    )
    state = store.load()
    public = store.public_state()
    assert_no_sensitive_data(state)
    assert_no_sensitive_data(public)
    texts = [
        json.dumps(state, ensure_ascii=False),
        json.dumps(public, ensure_ascii=False),
        render_page(),
    ]
    for pattern in FORBIDDEN_TEXT:
        if any(pattern.search(text) for text in texts):
            raise SystemExit(f"security scan failed: {pattern.pattern}")
    print(
        json.dumps(
            {
                "status": "passed",
                "runtime_state_valid": True,
                "public_state_valid": True,
                "qr_payload_absent": True,
                "cookies_tokens_codes_full_phone_absent": True,
                "masked_account_context_verified": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
