#!/usr/bin/env python3
"""Run a bounded, read-only Xiaohongshu session probe for one isolated slot."""

from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import Any

from lib.xhs_browser_profiles import (
    SESSION_ENDPOINT,
    build_session_probe_code,
    load_expected_identity,
    normalize_session_probe,
    parse_session_probe_result,
    profile_contract,
)
from lib.xhs_qr_login import load_account_context


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_ROOT / "scripts" / "start_xhs_slot_browser_mcp.ps1"
ACCOUNT_BINDING_PATH = (
    PROJECT_ROOT / "research" / "panse_multi_direction" / "account_role_binding_v1.json"
)
DAILY_RUNS_ROOT = PROJECT_ROOT / "research" / "panse_multi_direction" / "daily_runs"
HOME_URL = "https://www.xiaohongshu.com/explore"


def result_text(result: Any) -> str:
    return "\n".join(
        item.text
        for item in (getattr(result, "content", None) or [])
        if isinstance(getattr(item, "text", None), str)
    )


def resolve_context(account_slot: int, plan_date: str) -> dict[str, Any]:
    plan_path = DAILY_RUNS_ROOT / plan_date / f"account_{account_slot}_daily_plan.json"
    return load_account_context(
        binding_path=ACCOUNT_BINDING_PATH,
        plan_path=plan_path,
        account_slot=account_slot,
        plan_date=plan_date,
    )


async def probe(account_slot: int, expected_profile_id: str) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    stack = AsyncExitStack()
    session: Any = None
    try:
        params = StdioServerParameters(
            command="powershell.exe",
            args=[
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(LAUNCHER),
                "-AccountSlot",
                str(account_slot),
            ],
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        tools = {tool.name for tool in (await session.list_tools()).tools}
        required = {"browser_navigate", "browser_run_code_unsafe", "browser_close"}
        if not required <= tools:
            raise RuntimeError("slot browser MCP is missing required tools")
        navigated = await session.call_tool(
            "browser_navigate",
            {"url": HOME_URL},
            read_timeout_seconds=timedelta(seconds=75),
        )
        if getattr(navigated, "isError", False):
            raise RuntimeError("slot browser navigation failed")
        result = await session.call_tool(
            "browser_run_code_unsafe",
            {"code": build_session_probe_code(expected_profile_id)},
            read_timeout_seconds=timedelta(seconds=75),
        )
        if getattr(result, "isError", False):
            raise RuntimeError("slot browser session probe failed")
        return normalize_session_probe(
            parse_session_probe_result(result_text(result)),
            account_slot=account_slot,
            expected_profile_id=expected_profile_id,
        )
    finally:
        if session is not None:
            try:
                await session.call_tool(
                    "browser_close", {}, read_timeout_seconds=timedelta(seconds=20)
                )
            except Exception:
                pass
        await stack.aclose()


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    contract = sub.add_parser("contract")
    live = sub.add_parser("probe")
    for command in (contract, live):
        command.add_argument("--account-slot", type=int, required=True)
    live.add_argument("--plan-date", required=True)
    args = parser.parse_args()
    slot = profile_contract(args.account_slot)
    identity = load_expected_identity(args.account_slot)
    if args.command == "contract":
        print(
            json.dumps(
                {
                    **slot,
                    **identity,
                    "session_endpoint": SESSION_ENDPOINT,
                    "browser_started": False,
                    "credentials_read_or_exported": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    resolve_context(args.account_slot, args.plan_date)
    result = asyncio.run(probe(args.account_slot, identity["expected_profile_id"]))
    print(json.dumps({**slot, **result}, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"valid", "login_required", "identity_mismatch"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
