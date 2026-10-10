#!/usr/bin/env python3
"""Open a public test page through all five slot launchers and verify isolation."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import Any

import psutil

from lib.xhs_browser_profiles import profile_contract


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = PROJECT_ROOT / "scripts" / "start_xhs_slot_browser_mcp.ps1"
PUBLIC_TEST_URL = "https://example.com/"


def _normalized(value: object) -> str:
    return str(value).replace("/", "\\").lower()


def slot_chrome_processes(profile_dir: Path) -> list[int]:
    expected = _normalized(profile_dir.resolve())
    matches: list[int] = []
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if (process.info.get("name") or "").lower() != "chrome.exe":
                continue
            command = _normalized(" ".join(process.info.get("cmdline") or []))
            if expected in command:
                matches.append(int(process.info["pid"]))
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return matches


async def verify_slot(account_slot: int) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    contract = profile_contract(account_slot)
    profile_dir = Path(contract["profile_dir"])
    if slot_chrome_processes(profile_dir):
        raise RuntimeError(f"slot {account_slot} browser was already running")
    stack = AsyncExitStack()
    session: Any = None
    command_line_verified = False
    title_verified = False
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
        navigated = await session.call_tool(
            "browser_navigate",
            {"url": PUBLIC_TEST_URL},
            read_timeout_seconds=timedelta(seconds=75),
        )
        if getattr(navigated, "isError", False):
            raise RuntimeError(f"slot {account_slot} public navigation failed")
        command_line_verified = bool(slot_chrome_processes(profile_dir))
        if not command_line_verified:
            raise RuntimeError(f"slot {account_slot} profile command line was not observed")
        title = await session.call_tool(
            "browser_run_code_unsafe",
            {"code": "async (page) => ({title:await page.title(),url:page.url()})"},
            read_timeout_seconds=timedelta(seconds=30),
        )
        title_text = "\n".join(
            item.text
            for item in (getattr(title, "content", None) or [])
            if isinstance(getattr(item, "text", None), str)
        )
        title_verified = "Example Domain" in title_text and PUBLIC_TEST_URL in title_text
        if not title_verified:
            raise RuntimeError(f"slot {account_slot} public title verification failed")
    finally:
        if session is not None:
            try:
                await session.call_tool(
                    "browser_close", {}, read_timeout_seconds=timedelta(seconds=20)
                )
            except Exception:
                pass
        await stack.aclose()
    deadline = time.monotonic() + 10
    while slot_chrome_processes(profile_dir) and time.monotonic() < deadline:
        await asyncio.sleep(0.2)
    remaining = len(slot_chrome_processes(profile_dir))
    if remaining:
        raise RuntimeError(f"slot {account_slot} browser did not close")
    return {
        "account_slot": account_slot,
        "public_test_page_verified": title_verified,
        "exact_profile_command_line_verified": command_line_verified,
        "browser_close_called": True,
        "remaining_slot_chrome_processes": remaining,
        "xiaohongshu_opened": False,
        "login_state_read": False,
    }


async def main_async() -> dict[str, Any]:
    results = []
    for slot in range(1, 6):
        results.append(await verify_slot(slot))
    final_remaining = sum(
        len(slot_chrome_processes(Path(profile_contract(slot)["profile_dir"])))
        for slot in range(1, 6)
    )
    if final_remaining:
        raise RuntimeError("one or more slot browser processes remain")
    return {
        "status": "passed",
        "slots_verified": 5,
        "target_url": PUBLIC_TEST_URL,
        "xiaohongshu_opened": False,
        "login_state_read": False,
        "final_slot_chrome_processes": final_remaining,
        "results": results,
    }


def main() -> int:
    print(json.dumps(asyncio.run(main_async()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
