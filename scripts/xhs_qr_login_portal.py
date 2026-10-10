#!/usr/bin/env python3
"""Dual-surface Xiaohongshu QR login portal backed by playwright_browser MCP."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import Any

from aiohttp import web

from lib.xhs_browser_profiles import (
    build_session_probe_code,
    load_expected_identity,
    normalize_session_probe,
    parse_session_probe_result,
)
from lib.xhs_qr_login import QrStateStore, RefreshGate, load_account_context


OPS_ROOT = Path(r"D:\AI\小红书运营中心")
DEFAULT_RUNTIME_ROOT = OPS_ROOT / ".runtime" / "xhs-qr-login"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_BINDING_PATH = (
    PROJECT_ROOT / "research" / "panse_multi_direction" / "account_role_binding_v1.json"
)
DAILY_RUNS_ROOT = PROJECT_ROOT / "research" / "panse_multi_direction" / "daily_runs"
LAUNCHER = PROJECT_ROOT / "scripts" / "start_xhs_slot_browser_mcp.ps1"
HOME_URL = "https://www.xiaohongshu.com/explore"
QR_PANEL_HEADING = "登录后推荐更懂你的笔记"
QR_PANEL_HELP_TEXT = "小红书如何扫码"
QR_VISIBLE_RASTER_SELECTOR = (
    "img.qrcode-img:visible, img[class*='qrcode']:visible, canvas:visible"
)


def result_text(result: Any) -> str:
    values: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            values.append(text)
    return "\n".join(values)


def resolve_account_context(account_slot: int, plan_date: str) -> dict[str, Any]:
    plan_path = DAILY_RUNS_ROOT / plan_date / f"account_{account_slot}_daily_plan.json"
    if not plan_path.is_file():
        raise ValueError("current-date account plan is missing")
    return load_account_context(
        binding_path=ACCOUNT_BINDING_PATH,
        plan_path=plan_path,
        account_slot=account_slot,
        plan_date=plan_date,
    )


class PlaywrightBrowserProvider:
    def __init__(self, store: QrStateStore, ttl_seconds: int = 75):
        self.store = store
        self.ttl_seconds = ttl_seconds
        self.stack: AsyncExitStack | None = None
        self.session: Any = None
        self.monitor_task: asyncio.Task[None] | None = None
        self.stage = "idle"
        if not self.store.account_context:
            raise ValueError("QR account context is required for the slot browser")
        self.account_slot = int(self.store.account_context["account_slot"])
        self.expected_identity = load_expected_identity(self.account_slot)

    async def _open(self) -> None:
        if not LAUNCHER.is_file():
            self.store.record_status("failed", error_code="browser_missing")
            raise RuntimeError("browser_missing")
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self.stack = AsyncExitStack()
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
                str(self.account_slot),
            ],
        )
        read, write = await self.stack.enter_async_context(stdio_client(params))
        self.session = await self.stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        tools = {tool.name for tool in (await self.session.list_tools()).tools}
        required = {
            "browser_navigate",
            "browser_snapshot",
            "browser_run_code_unsafe",
            "browser_close",
        }
        if not required <= tools:
            raise RuntimeError("browser_missing")

    async def _call(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        result = await self.session.call_tool(
            name,
            arguments or {},
            read_timeout_seconds=timedelta(seconds=75),
        )
        if getattr(result, "isError", False):
            raise RuntimeError("browser_call_failed")
        return result_text(result)

    async def _identity_probe(self) -> dict[str, Any]:
        tools = {tool.name for tool in (await self.session.list_tools()).tools}
        if "browser_run_code_unsafe" not in tools:
            raise RuntimeError("browser_missing")
        expected_profile_id = self.expected_identity["expected_profile_id"]
        text = await self._call(
            "browser_run_code_unsafe",
            {"code": build_session_probe_code(expected_profile_id)},
        )
        return normalize_session_probe(
            parse_session_probe_result(text),
            account_slot=self.account_slot,
            expected_profile_id=expected_profile_id,
        )

    async def _capture_qr_presentation(self, staging: Path) -> None:
        """Capture the unique visible QR panel without persisting DOM or QR payload."""
        code = f"""async (page) => {{
          const heading = page.getByText({json.dumps(QR_PANEL_HEADING, ensure_ascii=False)}, {{exact:true}}).filter({{visible:true}});
          if (await heading.count() !== 1) throw new Error('unique_qr_heading_required');
          const panel = heading.locator('..');
          if (await panel.count() !== 1) throw new Error('unique_qr_panel_required');
          const help = panel.getByText({json.dumps(QR_PANEL_HELP_TEXT, ensure_ascii=False)}, {{exact:true}}).filter({{visible:true}});
          if (await help.count() !== 1) throw new Error('unique_qr_help_required');
          const rasters = panel.locator({json.dumps(QR_VISIBLE_RASTER_SELECTOR)});
          const visibleRasterCount = await rasters.count();
          if (visibleRasterCount !== 1) throw new Error('unique_qr_raster_required');
          const box = await panel.boundingBox();
          if (!box || box.width < 250 || box.width > 520 || box.height < 300 || box.height > 650) throw new Error('qr_panel_bounds_invalid');
          await panel.screenshot({{path:{json.dumps(str(staging))}, scale:'device', type:'png'}});
          return {{qrCaptureWritten:true, visibleRasterCount, panelWidth:Math.round(box.width), panelHeight:Math.round(box.height)}};
        }}"""
        text = await self._call("browser_run_code_unsafe", {"code": code})
        if not re.search(r'"qrCaptureWritten"\s*:\s*true', text):
            raise RuntimeError("qr_not_found")
        if not re.search(r'"visibleRasterCount"\s*:\s*1', text):
            raise RuntimeError("qr_not_found")

    async def acquire(self, *, switch_account: bool = False) -> dict[str, Any]:
        await self.close()
        try:
            self.stage = "initialize"
            await self._open()
            self.stage = "navigate"
            await self._call("browser_navigate", {"url": HOME_URL})
            self.stage = "identity_probe"
            probe = await self._identity_probe()
            if probe["status"] == "risk_blocked":
                raise RuntimeError("browser_risk_signal")
            if probe["status"] == "indeterminate":
                raise RuntimeError("browser_identity_probe_failed")
            if probe["status"] == "identity_mismatch" and not switch_account:
                raise RuntimeError("browser_identity_mismatch")
            if probe["status"] == "valid" and not switch_account:
                state = self.store.record_status("confirmed")
                await self.close()
                return state
            if probe["status"] in {"valid", "identity_mismatch"} and switch_account:
                code = f"""async (page) => {{
                  const more = page.getByText('更多', {{exact:true}}).filter({{visible:true}});
                  if (await more.count() !== 1) throw new Error('unique_more_required');
                  await more.click();
                  const logout = page.getByText('退出登录', {{exact:true}}).filter({{visible:true}});
                  if (await logout.count() !== 1) throw new Error('unique_logout_required');
                  await logout.click();
                  const heading = page.getByText({json.dumps(QR_PANEL_HEADING, ensure_ascii=False)}, {{exact:true}}).filter({{visible:true}});
                  await heading.waitFor({{state:'visible', timeout:15000}});
                  return {{logout_clicked:true, qr_panel_visible:true}};
                }}"""
                await self._call("browser_run_code_unsafe", {"code": code})
            staging = self.store.staging_path
            if staging.exists():
                staging.unlink()
            self.stage = "qr_capture"
            await self._capture_qr_presentation(staging)
            if not staging.is_file():
                raise RuntimeError("qr_not_found")
            state = self.store.publish_image(
                staging,
                ttl_seconds=self.ttl_seconds,
                status="active",
            )
            staging.unlink(missing_ok=True)
            self.monitor_task = asyncio.create_task(self._monitor(state["generation"]))
            self.stage = "active"
            return state
        except Exception as exc:
            stage_codes = {
                "initialize": "browser_initialize_failed",
                "navigate": "browser_navigate_failed",
                "identity_probe": "browser_identity_probe_failed",
                "qr_capture": "browser_qr_capture_failed",
            }
            code = str(exc) if str(exc) in {
                "browser_missing",
                "browser_call_failed",
                "qr_not_found",
                "browser_identity_mismatch",
                "browser_risk_signal",
                "browser_identity_probe_failed",
            } else stage_codes.get(self.stage, "browser_call_failed")
            if code == "browser_call_failed":
                code = stage_codes.get(self.stage, code)
            self.store.staging_path.unlink(missing_ok=True)
            self.store.record_status("failed", error_code=code)
            await self.close()
            raise RuntimeError(code) from None

    async def check(self, *, from_monitor: bool = False) -> dict[str, Any]:
        if self.session is None:
            return self.store.load()
        try:
            snapshot = await self._call("browser_snapshot", {"depth": 5})
            if "二维码已失效" in snapshot or "二维码失效" in snapshot:
                state = self.store.record_status("expired")
                await self.close(from_monitor=from_monitor)
                return state
            if "扫码成功" in snapshot or "已扫码" in snapshot:
                return self.store.record_status("scanned")
            probe = await self._identity_probe()
            if probe["status"] == "valid":
                state = self.store.record_status("confirmed")
                await self.close(from_monitor=from_monitor)
                return state
            if probe["status"] == "risk_blocked":
                state = self.store.record_status(
                    "failed", error_code="browser_risk_signal"
                )
                await self.close(from_monitor=from_monitor)
                return state
            if probe["status"] == "identity_mismatch":
                state = self.store.record_status(
                    "failed", error_code="browser_identity_mismatch"
                )
                await self.close(from_monitor=from_monitor)
                return state
            if probe["status"] == "indeterminate":
                state = self.store.record_status(
                    "failed", error_code="browser_identity_probe_failed"
                )
                await self.close(from_monitor=from_monitor)
                return state
            return self.store.load()
        except Exception:
            state = self.store.record_status("failed", error_code="browser_call_failed")
            await self.close(from_monitor=from_monitor)
            return state

    async def _monitor(self, generation: int) -> None:
        try:
            while True:
                await asyncio.sleep(3)
                state = self.store.load()
                if state["generation"] != generation or state["status"] in {
                    "expired",
                    "confirmed",
                    "failed",
                }:
                    break
                await self.check(from_monitor=True)
        finally:
            if self.store.load()["status"] in {"expired", "confirmed", "failed"}:
                await self.close(from_monitor=True)

    async def close(self, *, from_monitor: bool = False) -> None:
        task = self.monitor_task
        self.monitor_task = None
        if task is not None and not task.done() and not from_monitor:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self.session is not None:
            try:
                await self.session.call_tool(
                    "browser_close", {}, read_timeout_seconds=timedelta(seconds=20)
                )
            except Exception:
                pass
        self.session = None
        if self.stack is not None:
            try:
                await self.stack.aclose()
            except Exception:
                pass
        self.stack = None


class PortalController:
    def __init__(self, store: QrStateStore, provider: Any):
        self.store = store
        self.provider = provider
        self.gate = RefreshGate()

    async def refresh(self, action: str) -> dict[str, Any]:
        state = self.store.load()
        self.gate.begin(state, action)
        try:
            return await self.provider.acquire(switch_account=action == "switch_account")
        finally:
            self.gate.finish()


def render_page() -> str:
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>小红书专用登录二维码</title>
<style>
body{font-family:system-ui,sans-serif;background:#f7f7f8;color:#171717;margin:0}
main{max-width:560px;margin:40px auto;padding:24px;background:white;border-radius:18px;box-shadow:0 8px 30px #0001}
.status{font-weight:700;padding:8px 12px;border-radius:999px;background:#f1f1f3;display:inline-block}
img{display:block;width:min(320px,90%);margin:24px auto;border:1px solid #ddd;border-radius:12px}
button{border:0;border-radius:10px;padding:11px 16px;margin:6px;background:#111;color:white;cursor:pointer}
button.secondary{background:#e9e9ec;color:#111} .note{color:#666;line-height:1.6}
.context{margin:18px 0;padding:14px 16px;background:#f7f7f8;border-radius:12px;line-height:1.8}
.context dt{font-weight:700;float:left;clear:left;width:7.5em}.context dd{margin-left:7.5em}
</style></head><body><main>
<h1>小红书专用登录二维码</h1><div id="status" class="status">读取中</div>
<dl class="context">
<dt>目标账号</dt><dd>slot <span id="account-slot">-</span></dd>
<dt>脱敏手机</dt><dd id="masked-phone">-</dd>
<dt>确认设备</dt><dd id="device">-</dd>
<dt>预期昵称</dt><dd id="expected-nickname">-</dd>
<dt>运营名称</dt><dd id="working-name">-</dd>
<dt>登录目的</dt><dd id="login-purpose">-</dd>
</dl>
<img id="qr" alt="小红书登录二维码" hidden>
<p id="message" class="note"></p>
<button id="refresh">刷新过期二维码</button>
<button id="switch" class="secondary">切换账号并获取二维码</button>
<button id="check" class="secondary">我已扫码，检查状态</button>
<p class="note">二维码和手机确认必须由你完成。本页不保存 Cookie、Token、验证码、完整手机号、二维码内容或 session storage。</p>
</main><script>
const labels={unavailable:'尚未获取',active:'二维码有效',expired:'二维码已过期',scanned:'已扫码，等待手机确认',confirmed:'登录已确认',failed:'获取失败'};
async function load(){const s=await (await fetch('/api/status',{cache:'no-store'})).json();
 document.querySelector('#status').textContent=labels[s.status]||s.status;
 const fields={'account-slot':s.account_slot,'masked-phone':s.masked_phone,'device':s.device,'expected-nickname':s.expected_nickname,'working-name':s.working_name,'login-purpose':s.login_purpose};
 for(const [id,value] of Object.entries(fields)) document.querySelector('#'+id).textContent=value??'-';
 const img=document.querySelector('#qr'); const show=s.image_available&&['active','scanned'].includes(s.status); img.hidden=!show;
 if(show) img.src='/qr.png?g='+s.generation;
 document.querySelector('#message').textContent=s.last_error_code?('状态：'+s.last_error_code):'';}
async function act(action){if(action==='switch_account'&&!confirm('这会退出当前专用网页账号并显示新的登录二维码，是否继续？'))return;
 await fetch('/api/refresh',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action})}); await load();}
document.querySelector('#refresh').onclick=()=>act('refresh');
document.querySelector('#switch').onclick=()=>act('switch_account');
document.querySelector('#check').onclick=async()=>{await fetch('/api/check',{method:'POST'});await load();};
load();setInterval(load,3000);
</script></body></html>"""


def build_app(controller: PortalController) -> web.Application:
    app = web.Application(client_max_size=1024)

    async def index(_request: web.Request) -> web.Response:
        return web.Response(text=render_page(), content_type="text/html")

    async def status(_request: web.Request) -> web.Response:
        return web.json_response(controller.store.public_state())

    async def image(_request: web.Request) -> web.StreamResponse:
        state = controller.store.load()
        public = controller.store.public_state()
        if not public["image_available"]:
            raise web.HTTPNotFound()
        return web.FileResponse(state["image_path"], headers={"Cache-Control": "no-store"})

    async def refresh(request: web.Request) -> web.Response:
        try:
            body = await request.json()
            action = body.get("action")
            result = await controller.refresh(action)
            return web.json_response(controller.store.public_state())
        except (ValueError, RuntimeError) as exc:
            code = str(exc)
            status_code = 409 if code in {
                "refresh_already_used",
                "refresh_in_progress",
                "refresh_requires_expired_or_failed_state",
            } else 503
            return web.json_response({"status": "failed", "error_code": code}, status=status_code)

    async def check(_request: web.Request) -> web.Response:
        await controller.provider.check()
        return web.json_response(controller.store.public_state())

    async def cleanup(_app: web.Application) -> None:
        await controller.provider.close()

    app.router.add_get("/", index)
    app.router.add_get("/api/status", status)
    app.router.add_get("/qr.png", image)
    app.router.add_post("/api/refresh", refresh)
    app.router.add_post("/api/check", check)
    app.on_cleanup.append(cleanup)
    return app


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=DEFAULT_RUNTIME_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    publish = sub.add_parser("publish", help="publish a browser-captured PNG")
    publish.add_argument("image", type=Path)
    publish.add_argument("--ttl", type=int, default=75)
    publish.add_argument("--confirmed", action="store_true")
    status = sub.add_parser("status")
    mark = sub.add_parser("mark")
    mark.add_argument("status", choices=["expired", "scanned", "confirmed", "failed"])
    mark.add_argument("--error-code")
    probe = sub.add_parser("probe-browser")
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18765)
    for command in (publish, status, mark, probe, serve):
        command.add_argument("--account-slot", type=int, required=True)
        command.add_argument("--plan-date", required=True)
    args = parser.parse_args()
    account_context = resolve_account_context(args.account_slot, args.plan_date)
    store = QrStateStore(
        args.runtime_root / f"slot-{args.account_slot}",
        account_context=account_context,
    )
    if args.command == "publish":
        state = store.publish_image(
            args.image,
            ttl_seconds=args.ttl,
            status="confirmed" if args.confirmed else "active",
        )
        print(json.dumps(store.public_state(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        print(json.dumps(store.public_state(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "mark":
        store.record_status(args.status, error_code=args.error_code)
        print(json.dumps(store.public_state(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "probe-browser":
        async def probe() -> dict[str, Any]:
            provider = PlaywrightBrowserProvider(store)
            try:
                await provider.acquire(switch_account=False)
                return store.public_state()
            finally:
                await provider.close()

        print(json.dumps(asyncio.run(probe()), ensure_ascii=False, indent=2))
        return 0
    provider = PlaywrightBrowserProvider(store)
    web.run_app(build_app(PortalController(store, provider)), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
