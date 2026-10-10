#!/usr/bin/env python3
"""Contract tests for isolated Xiaohongshu slot browser profiles."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import tomllib

import pytest

from lib.xhs_browser_profiles import (
    SESSION_ENDPOINT,
    build_session_probe_code,
    detect_visible_risk_codes,
    load_expected_identity,
    load_profile_policy,
    normalize_session_probe,
    profile_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
OPS_ROOT = Path(r"D:\AI\小红书运营中心")
PROJECT_CONFIG = OPS_ROOT / ".codex" / "config.toml"
LAUNCHER = REPO_ROOT / "scripts" / "start_xhs_slot_browser_mcp.ps1"
OBSERVED_AT = datetime(2026, 9, 1, tzinfo=timezone.utc)


def raw_probe(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "dom_self_profile_count": 1,
        "dom_profile_match": True,
        "login_prompt_count": 0,
        "risk_codes": [],
        "api_http_status": 200,
        "api_http_ok": True,
        "api_expected_profile_match": True,
        "response_date_present": True,
        "response_date_at": "2026-09-01T00:00:00Z",
        "cache_expires_present": False,
        "exact_ttl_header_present": False,
        "exact_session_expires_at": None,
        "exact_ttl_source": None,
        "api_request_failed": False,
    }
    value.update(overrides)
    return value


def normalize(**overrides: object) -> dict[str, object]:
    return normalize_session_probe(
        raw_probe(**overrides),
        account_slot=3,
        expected_profile_id="5b38445e4eacab65d6c0521c",
        observed_at=OBSERVED_AT,
    )


def test_policy_defines_five_exact_unique_d_drive_profiles() -> None:
    policy = load_profile_policy()
    assert len(policy["slots"]) == 5
    profiles = [Path(item["profile_dir"]).resolve() for item in policy["slots"]]
    outputs = [Path(item["output_dir"]).resolve() for item in policy["slots"]]
    assert len({str(path).lower() for path in profiles}) == 5
    assert len({str(path).lower() for path in outputs}) == 5
    for slot in range(1, 6):
        contract = profile_contract(slot)
        assert Path(contract["profile_dir"]).resolve() == Path(
            rf"D:\AI\tachikoma\.runtime\playwright-browser-profiles\slot-{slot}"
        ).resolve()
        assert Path(contract["output_dir"]).resolve() == Path(
            rf"D:\AI\tachikoma\.tmp\playwright-browser-mcp-slots\slot-{slot}"
        ).resolve()
        assert Path(contract["profile_dir"]).drive.lower() == "d:"
        assert Path(contract["output_dir"]).drive.lower() == "d:"


def test_all_five_expected_public_identities_are_complete() -> None:
    for slot in range(1, 6):
        identity = load_expected_identity(slot)
        assert identity["account_slot"] == slot
        assert identity["expected_profile_id"]
        assert identity["expected_nickname"]


def test_project_config_registers_only_five_slot_login_servers() -> None:
    config = tomllib.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))
    servers = config["mcp_servers"]
    expected = {f"playwright_browser_slot_{slot}" for slot in range(1, 6)}
    assert expected <= set(servers)
    assert "playwright_debug" in servers
    assert "playwright_browser" not in servers
    assert {name for name in servers if name.startswith("playwright_browser_")} == expected
    for slot in range(1, 6):
        args = servers[f"playwright_browser_slot_{slot}"]["args"]
        assert args[-2:] == ["-AccountSlot", str(slot)]


@pytest.mark.parametrize("slot", range(1, 6))
def test_launcher_validate_only_for_each_slot(slot: int) -> None:
    executable = shutil.which("powershell.exe")
    assert executable is not None
    result = subprocess.run(
        [
            executable,
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LAUNCHER),
            "-AccountSlot",
            str(slot),
            "-ValidateOnly",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert f'"account_slot":{slot}'.encode() in result.stdout
    assert b'"browser_started":false' in result.stdout


def test_valid_session_requires_dom_and_api_identity_match() -> None:
    result = normalize()
    assert result["status"] == "valid"
    assert result["session_reusable"] is True
    assert result["qr_human_gate_required"] is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"dom_profile_match": False},
        {"api_expected_profile_match": False},
    ],
)
def test_identity_mismatch_never_becomes_valid(overrides: dict[str, object]) -> None:
    result = normalize(**overrides)
    assert result["status"] == "identity_mismatch"
    assert result["session_reusable"] is False
    assert result["qr_human_gate_required"] is True


def test_login_required_status_is_bounded() -> None:
    result = normalize(
        dom_self_profile_count=0,
        dom_profile_match=False,
        login_prompt_count=1,
        api_http_status=401,
        api_http_ok=False,
        api_expected_profile_match=False,
    )
    assert result["status"] == "login_required"
    assert result["session_reusable"] is False


def test_ordinary_logged_out_login_page_is_not_a_captcha_risk() -> None:
    body_text = (
        "登录后推荐更懂你的笔记\n"
        "可用小红书或微信扫码\n"
        "手机号登录\n"
        "获取验证码"
    )
    assert detect_visible_risk_codes(body_text) == []
    result = normalize(
        dom_self_profile_count=0,
        dom_profile_match=False,
        login_prompt_count=1,
        risk_codes=detect_visible_risk_codes(body_text),
        api_http_status=406,
        api_http_ok=False,
        api_expected_profile_match=False,
    )
    assert result["status"] == "login_required"
    assert result["qr_human_gate_required"] is True


@pytest.mark.parametrize(
    ("body_text", "expected_code"),
    [
        ("请完成图形验证码", "captcha"),
        ("请拖动滑块完成验证", "captcha"),
        ("请完成人机验证后继续", "captcha"),
        ("当前操作需要安全验证", "security_verification"),
        ("请求频繁，请稍后再试", "frequency_limit"),
        ("账号异常，请联系客服", "account_abnormal"),
        ("登录异常，请重新登录", "login_abnormal"),
    ],
)
def test_explicit_challenge_and_risk_pages_remain_blocked(
    body_text: str,
    expected_code: str,
) -> None:
    risk_codes = detect_visible_risk_codes(body_text)
    assert expected_code in risk_codes
    result = normalize(risk_codes=risk_codes)
    assert result["status"] == "risk_blocked"
    assert result["session_reusable"] is False
    assert result["next_action"] == "stop_without_refresh_or_account_switch"


def test_risk_signal_has_priority_and_stops_reuse() -> None:
    result = normalize(risk_codes=["security_verification"])
    assert result["status"] == "risk_blocked"
    assert result["session_reusable"] is False
    assert result["next_action"] == "stop_without_refresh_or_account_switch"


def test_indeterminate_probe_fails_closed() -> None:
    result = normalize(
        api_http_status=None,
        api_http_ok=False,
        api_expected_profile_match=False,
        api_request_failed=True,
    )
    assert result["status"] == "indeterminate"
    assert result["session_reusable"] is False


def test_no_explicit_ttl_never_invents_remaining_lifetime() -> None:
    result = normalize(cache_expires_present=True)
    assert result["cache_expires_header_present"] is True
    assert result["exact_session_ttl_available"] is False
    assert result["session_expires_at"] is None
    assert result["ttl_source"] is None
    assert result["remaining_session_seconds"] is None


def test_only_allowlisted_explicit_session_expiry_header_is_reported() -> None:
    result = normalize(
        exact_ttl_header_present=True,
        exact_session_expires_at="2026-09-02T00:00:00Z",
        exact_ttl_source="x-session-expires-at",
    )
    assert result["exact_session_ttl_available"] is True
    assert result["session_expires_at"] == "2026-09-02T00:00:00Z"
    assert result["remaining_session_seconds"] is None


def test_probe_code_never_reads_or_exports_browser_credentials() -> None:
    assert SESSION_ENDPOINT == "https://edith.xiaohongshu.com/api/sns/web/v2/user/me"
    code = build_session_probe_code("5b38445e4eacab65d6c0521c").lower()
    for forbidden in (
        "document.cookie",
        "sessionstorage",
        "storageState".lower(),
        "set-cookie",
    ):
        assert forbidden not in code
    assert "response.headers.get('date')" in code
    assert "response.headers.get('expires')" in code
    assert "response.headers.get(name)" in code
    assert "['captcha', /验证码/]" not in code
    assert "获取验证码" not in code
    assert "图形验证码" in code
