#!/usr/bin/env python3
"""Tests for the shared Xiaohongshu QR login state and portal."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from aiohttp.test_utils import TestClient, TestServer

from lib.xhs_qr_login import (
    ACCOUNT_CONTEXT_CONTRACT_ID,
    QrStateStore,
    RefreshGate,
    assert_no_sensitive_data,
    load_account_context,
    markdown_image,
)
import xhs_qr_login_portal as portal_module
from xhs_qr_login_portal import (
    PlaywrightBrowserProvider,
    PortalController,
    QR_PANEL_HEADING,
    QR_PANEL_HELP_TEXT,
    QR_VISIBLE_RASTER_SELECTOR,
    build_app,
    render_page,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 512
REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "start_xhs_qr_login_portal.ps1"
BINDING = REPO_ROOT / "research" / "panse_multi_direction" / "account_role_binding_v1.json"
PLAN = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "daily_runs"
    / "2026-08-31"
    / "account_5_daily_plan.json"
)


def account_context(slot: int = 5) -> dict:
    return {
        "account_slot": slot,
        "masked_phone": "153****0935" if slot == 5 else "158****8812",
        "device": "iPhone 13 mini" if slot == 5 else "小米手机",
        "expected_nickname": "是阿宝啊" if slot == 5 else "畔色木作",
        "working_name": "家具在别处" if slot == 5 else "畔色木作",
        "login_purpose": f"继续 2026-08-31 slot {slot} 测试",
    }


def qr_store(tmp_path: Path, context: dict | None = None) -> QrStateStore:
    return QrStateStore(
        tmp_path / "runtime",
        account_context=context or account_context(),
    )


def image(path: Path, suffix: bytes = b"") -> Path:
    path.write_bytes(PNG + suffix)
    return path


def test_launcher_is_ascii_for_windows_powershell_51_compatibility() -> None:
    LAUNCHER.read_bytes().decode("ascii")


@pytest.mark.parametrize("executable", ["powershell.exe", "pwsh.exe"])
def test_launcher_validate_only_runs_on_both_powershell_families(
    executable: str,
) -> None:
    resolved = shutil.which(executable)
    if resolved is None:
        pytest.skip(f"{executable} is not installed")
    result = subprocess.run(
        [
            resolved,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LAUNCHER),
            "-ValidateOnly",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert b"xhs_qr_login_portal_launcher=valid" in result.stdout


def test_authoritative_slot5_context_loads_exact_current_plan() -> None:
    context = load_account_context(
        binding_path=BINDING,
        plan_path=PLAN,
        account_slot=5,
        plan_date="2026-08-31",
        today="2026-08-31",
    )
    assert context == {
        "account_slot": 5,
        "masked_phone": "153****0935",
        "device": "iPhone 13 mini",
        "expected_nickname": "是阿宝啊",
        "working_name": "家具在别处",
        "login_purpose": "继续 2026-08-31 全球家具工艺与居住偏好观察编辑账号日常运营",
    }


def test_authoritative_context_fails_closed_for_stale_date_or_wrong_slot() -> None:
    with pytest.raises(ValueError, match="stale"):
        load_account_context(
            binding_path=BINDING,
            plan_path=PLAN,
            account_slot=5,
            plan_date="2026-08-31",
            today="2026-09-01",
        )
    with pytest.raises(ValueError, match="target slot"):
        load_account_context(
            binding_path=BINDING,
            plan_path=PLAN,
            account_slot=4,
            plan_date="2026-08-31",
            today="2026-08-31",
        )


def test_publish_requires_complete_account_context(tmp_path: Path) -> None:
    store = QrStateStore(tmp_path / "runtime")
    with pytest.raises(ValueError, match="account context is required"):
        store.publish_image(image(tmp_path / "qr.png"), ttl_seconds=60)


def test_active_state_and_markdown_share_one_image(tmp_path: Path) -> None:
    store = qr_store(tmp_path)
    state = store.publish_image(image(tmp_path / "qr.png"), ttl_seconds=60)
    assert state["status"] == "active"
    assert state["generation"] == 1
    assert state["markdown_image"] == markdown_image(store.image_path)
    public = store.public_state()
    assert public["image_available"] is True
    assert public["account_context_contract_id"] == ACCOUNT_CONTEXT_CONTRACT_ID
    for field, value in account_context().items():
        assert public[field] == value


def test_active_generation_fails_closed_for_a_different_target_slot(
    tmp_path: Path,
) -> None:
    store = qr_store(tmp_path)
    store.publish_image(image(tmp_path / "qr.png"), ttl_seconds=60)
    mismatched = qr_store(tmp_path, account_context(1))
    with pytest.raises(ValueError, match="missing or mismatched"):
        mismatched.public_state()


def test_expired_state_is_derived_from_authoritative_expiry(tmp_path: Path) -> None:
    now = datetime(2026, 8, 30, tzinfo=timezone.utc)
    store = qr_store(tmp_path)
    store.publish_image(image(tmp_path / "qr.png"), ttl_seconds=15, now=now)
    assert store.load(now + timedelta(seconds=14))["status"] == "active"
    assert store.load(now + timedelta(seconds=15))["status"] == "expired"
    assert store.public_state()["image_available"] is False
    assert store.public_state()["markdown_image"] is None


def test_one_manual_refresh_per_expired_generation(tmp_path: Path) -> None:
    store = qr_store(tmp_path)
    store.publish_image(image(tmp_path / "qr.png"), ttl_seconds=15)
    state = store.record_status("expired")
    gate = RefreshGate()
    gate.begin(state, "refresh")
    gate.finish()
    with pytest.raises(RuntimeError, match="refresh_already_used"):
        gate.begin(state, "refresh")


def test_refresh_publishes_a_new_generation(tmp_path: Path) -> None:
    store = qr_store(tmp_path)
    first = store.publish_image(image(tmp_path / "one.png"), ttl_seconds=15)
    store.record_status("expired")
    second = store.publish_image(image(tmp_path / "two.png", b"2"), ttl_seconds=60)
    assert second["generation"] == first["generation"] + 1
    assert second["image_sha256"] != first["image_sha256"]


def test_controller_manual_refresh_updates_shared_state_once(tmp_path: Path) -> None:
    store = qr_store(tmp_path)
    store.publish_image(image(tmp_path / "one.png"), ttl_seconds=15)
    store.record_status("expired")

    class FakeProvider:
        async def acquire(self, *, switch_account: bool = False) -> dict:
            assert switch_account is False
            return store.publish_image(image(tmp_path / "two.png", b"2"), ttl_seconds=60)

    controller = PortalController(store, FakeProvider())
    state = asyncio.run(controller.refresh("refresh"))
    assert state["status"] == "active"
    assert state["generation"] == 2


def test_http_fallback_page_refreshes_expired_qr_and_serves_new_image(
    tmp_path: Path,
) -> None:
    store = qr_store(tmp_path)
    store.publish_image(image(tmp_path / "one.png"), ttl_seconds=15)
    store.record_status("expired")

    class FakeProvider:
        async def acquire(self, *, switch_account: bool = False) -> dict:
            return store.publish_image(image(tmp_path / "two.png", b"2"), ttl_seconds=60)

        async def check(self) -> dict:
            return store.load()

        async def close(self) -> None:
            return None

    async def scenario() -> None:
        client = TestClient(TestServer(build_app(PortalController(store, FakeProvider()))))
        await client.start_server()
        try:
            before = await (await client.get("/api/status")).json()
            assert before["status"] == "expired"
            assert before["account_slot"] == 5
            response = await client.post("/api/refresh", json={"action": "refresh"})
            assert response.status == 200
            after = await response.json()
            assert after["status"] == "active"
            assert after["generation"] == 2
            image_response = await client.get("/qr.png")
            assert image_response.status == 200
            assert (await image_response.read()).endswith(b"2")
        finally:
            await client.close()

    asyncio.run(scenario())


def test_missing_browser_is_a_bounded_failed_state(tmp_path: Path) -> None:
    store = qr_store(tmp_path)
    state = store.record_status("failed", error_code="browser_missing")
    assert state["status"] == "failed"
    assert state["last_error_code"] == "browser_missing"


def test_live_provider_missing_launcher_fails_without_starting_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(portal_module, "LAUNCHER", tmp_path / "missing.ps1")
    store = qr_store(tmp_path)
    provider = PlaywrightBrowserProvider(store)
    with pytest.raises(RuntimeError, match="browser_missing"):
        asyncio.run(provider.acquire())
    assert store.public_state()["last_error_code"] == "browser_missing"


@pytest.mark.parametrize(
    ("probe_status", "expected_error"),
    [
        ("identity_mismatch", "browser_identity_mismatch"),
        ("risk_blocked", "browser_risk_signal"),
        ("indeterminate", "browser_identity_probe_failed"),
    ],
)
def test_provider_fails_closed_before_qr_for_unsafe_probe_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    probe_status: str,
    expected_error: str,
) -> None:
    store = qr_store(tmp_path)
    provider = PlaywrightBrowserProvider(store)

    class FakeSession:
        async def call_tool(self, name: str, _arguments: dict, **_kwargs: object):
            assert name == "browser_close"
            return SimpleNamespace(isError=False, content=[])

    async def fake_open() -> None:
        provider.session = FakeSession()

    async def fake_call(name: str, _arguments: dict | None = None) -> str:
        assert name == "browser_navigate"
        return "navigated"

    async def fake_probe() -> dict:
        return {"status": probe_status}

    monkeypatch.setattr(provider, "_open", fake_open)
    monkeypatch.setattr(provider, "_call", fake_call)
    monkeypatch.setattr(provider, "_identity_probe", fake_probe)
    with pytest.raises(RuntimeError, match=expected_error):
        asyncio.run(provider.acquire(switch_account=False))
    assert store.public_state()["last_error_code"] == expected_error
    assert store.public_state()["image_available"] is False


def test_switch_account_captures_current_qr_panel_and_returns_active_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = qr_store(tmp_path)
    provider = PlaywrightBrowserProvider(store)
    calls: list[tuple[str, dict]] = []

    class FakeSession:
        def __init__(self) -> None:
            self.browser_close_calls = 0

        async def list_tools(self):
            return SimpleNamespace(
                tools=[SimpleNamespace(name="browser_run_code_unsafe")]
            )

        async def call_tool(self, name: str, _arguments: dict, **_kwargs: object):
            assert name == "browser_close"
            self.browser_close_calls += 1
            return SimpleNamespace(isError=False, content=[])

    session = FakeSession()

    async def fake_open() -> None:
        provider.session = session

    async def fake_call(name: str, arguments: dict | None = None) -> str:
        values = arguments or {}
        calls.append((name, values))
        code = str(values.get("code", ""))
        if name == "browser_navigate":
            return "navigated"
        if "dom_self_profile_count" in code:
            return (
                '{"dom_self_profile_count":1,"dom_profile_match":true,'
                '"login_prompt_count":0,"risk_codes":[],"api_http_status":200,'
                '"api_http_ok":true,"api_expected_profile_match":true,'
                '"response_date_present":true,"response_date_at":"2026-09-01T00:00:00Z",'
                '"cache_expires_present":false,"exact_ttl_header_present":false,'
                '"exact_session_expires_at":null,"exact_ttl_source":null,'
                '"api_request_failed":false}'
            )
        if "logout_clicked" in code:
            return '{"logout_clicked":true,"qr_panel_visible":true}'
        if "qrCaptureWritten" in code:
            image(store.staging_path)
            return (
                '{"qrCaptureWritten":true,"visibleRasterCount":1,'
                '"panelWidth":400,"panelHeight":480}'
            )
        raise AssertionError(f"unexpected provider call: {name} {values}")

    monkeypatch.setattr(provider, "_open", fake_open)
    monkeypatch.setattr(provider, "_call", fake_call)
    state = asyncio.run(provider.acquire(switch_account=True))
    assert state["status"] == "active"
    assert state["generation"] == 1
    assert state["markdown_image"] == markdown_image(store.image_path)
    assert store.image_path.is_file()

    capture_codes = [
        args["code"]
        for name, args in calls
        if name == "browser_run_code_unsafe" and "qrCaptureWritten" in args.get("code", "")
    ]
    assert len(capture_codes) == 1
    capture_code = capture_codes[0]
    assert QR_PANEL_HEADING in capture_code
    assert QR_PANEL_HELP_TEXT in capture_code
    assert QR_VISIBLE_RASTER_SELECTOR in capture_code
    assert "panel.screenshot" in capture_code
    assert not any(name == "browser_take_screenshot" for name, _args in calls)

    asyncio.run(provider.close())
    assert session.browser_close_calls == 1


def test_qr_capture_fails_closed_without_one_visible_raster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = qr_store(tmp_path)
    provider = PlaywrightBrowserProvider(store)

    async def fake_call(_name: str, _arguments: dict | None = None) -> str:
        return '{"qrCaptureWritten":true,"visibleRasterCount":2}'

    monkeypatch.setattr(provider, "_call", fake_call)
    with pytest.raises(RuntimeError, match="qr_not_found"):
        asyncio.run(provider._capture_qr_presentation(store.staging_path))


@pytest.mark.parametrize(
    "value",
    [
        {"cookie": "secret"},
        {"safe": "access_token=secret"},
        {"safe": "13812345678"},
        {"qr_payload": "hidden"},
    ],
)
def test_sensitive_data_is_rejected(value: object) -> None:
    with pytest.raises(ValueError, match="sensitive"):
        assert_no_sensitive_data(value)


def test_page_contains_statuses_and_user_triggered_controls_only() -> None:
    page = render_page()
    for text in (
        "二维码有效",
        "二维码已过期",
        "已扫码，等待手机确认",
        "登录已确认",
        "获取失败",
        "刷新过期二维码",
        "切换账号并获取二维码",
        "脱敏手机",
        "确认设备",
        "预期昵称",
        "运营名称",
        "登录目的",
    ):
        assert text in page
    for forbidden in ("Cookie=", "access_token", "sessionStorage"):
        assert forbidden not in page


def test_confirmed_state_does_not_offer_stale_markdown_qr(tmp_path: Path) -> None:
    store = qr_store(tmp_path)
    store.publish_image(
        image(tmp_path / "qr.png"), ttl_seconds=60, status="confirmed"
    )
    assert store.public_state()["markdown_image"] is None


def test_png_validation_rejects_non_image(tmp_path: Path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_text("not png", encoding="utf-8")
    with pytest.raises(ValueError, match="bounded PNG"):
        qr_store(tmp_path).publish_image(bad, ttl_seconds=60)
