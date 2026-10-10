"""Five-slot browser profile and privacy-bounded session probe contracts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.xhs_qr_login import assert_no_sensitive_data


REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_POLICY_PATH = (
    REPO_ROOT / "configs" / "panse" / "xhs_browser_profile_slots_v1.json"
)
ACCOUNT_BINDING_PATH = (
    REPO_ROOT / "research" / "panse_multi_direction" / "account_role_binding_v1.json"
)
SESSION_PROBE_CONTRACT_ID = "panse-xhs-session-probe.v1"
SESSION_ENDPOINT = "https://edith.xiaohongshu.com/api/sns/web/v2/user/me"
ALLOWED_RISK_CODES = {
    "captcha",
    "security_verification",
    "frequency_limit",
    "account_abnormal",
    "login_abnormal",
}
VISIBLE_RISK_PATTERN_SOURCES = (
    (
        "captcha",
        r"图形验证码|图片验证码|滑块验证|拖动滑块|人机验证|请完成验证(?:挑战|后继续)?",
    ),
    ("security_verification", r"安全验证|安全校验|身份验证异常"),
    ("frequency_limit", r"访问过于频繁|请求频繁"),
    ("account_abnormal", r"账号异常"),
    ("login_abnormal", r"登录异常"),
)
ALLOWED_EXACT_TTL_SOURCES = {
    "x-session-expires-at",
    "x-auth-expires-at",
}


def _resolved(path: object) -> Path:
    return Path(str(path)).resolve()


def _is_direct_child(path: Path, root: Path, expected_name: str) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return relative.parts == (expected_name,)


def load_profile_policy(path: Path = PROFILE_POLICY_PATH) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("contract_id") != "panse-xhs-slot-browser-profiles.v1":
        raise ValueError("unexpected slot browser profile contract")
    profile_root = _resolved(value.get("profile_root"))
    output_root = _resolved(value.get("output_root"))
    slots = value.get("slots")
    if not isinstance(slots, list) or len(slots) != 5:
        raise ValueError("slot browser profile contract must define exactly five slots")
    observed_slots: set[int] = set()
    profiles: set[str] = set()
    outputs: set[str] = set()
    servers: set[str] = set()
    for item in slots:
        slot = item.get("account_slot")
        if not isinstance(slot, int) or isinstance(slot, bool) or not 1 <= slot <= 5:
            raise ValueError("slot browser profile id must be an integer from 1 to 5")
        profile = _resolved(item.get("profile_dir"))
        output = _resolved(item.get("output_dir"))
        server = str(item.get("mcp_server", "")).strip()
        if server != f"playwright_browser_slot_{slot}":
            raise ValueError("slot browser MCP server name drifted")
        if not _is_direct_child(profile, profile_root, f"slot-{slot}"):
            raise ValueError("slot browser profile path escapes its exact slot")
        if not _is_direct_child(output, output_root, f"slot-{slot}"):
            raise ValueError("slot browser output path escapes its exact slot")
        observed_slots.add(slot)
        profiles.add(str(profile).lower())
        outputs.add(str(output).lower())
        servers.add(server)
    if observed_slots != set(range(1, 6)):
        raise ValueError("slot browser profile contract is incomplete")
    if len(profiles) != 5 or len(outputs) != 5 or len(servers) != 5:
        raise ValueError("slot browser profiles, outputs and servers must be unique")
    safety = value.get("safety") or {}
    if not all(
        safety.get(field) is True
        for field in (
            "persistent_per_slot",
            "on_demand_only",
            "browser_close_required",
            "everyday_chrome_profile_forbidden",
            "credential_export_forbidden",
            "exact_ttl_must_not_be_inferred",
        )
    ):
        raise ValueError("slot browser safety contract drifted")
    return value


def profile_contract(account_slot: int) -> dict[str, Any]:
    if not isinstance(account_slot, int) or isinstance(account_slot, bool):
        raise ValueError("account slot must be an integer")
    policy = load_profile_policy()
    matches = [
        item for item in policy["slots"] if item.get("account_slot") == account_slot
    ]
    if len(matches) != 1:
        raise ValueError("account slot is missing or ambiguous")
    item = dict(matches[0])
    item["contract_id"] = policy["contract_id"]
    return item


def load_expected_identity(
    account_slot: int,
    binding_path: Path = ACCOUNT_BINDING_PATH,
) -> dict[str, Any]:
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    matches = [
        item for item in binding.get("accounts", [])
        if item.get("slot") == account_slot
    ]
    if len(matches) != 1:
        raise ValueError("target account binding is missing or ambiguous")
    account = matches[0]
    profile = account.get("platform_profile")
    if not isinstance(profile, dict):
        raise ValueError("target account has no verified platform profile")
    profile_id = str(profile.get("xiaohongshu_user_id", "")).strip()
    nickname = str(profile.get("observed_nickname", "")).strip()
    if not profile_id or not nickname:
        raise ValueError("target account verified profile is incomplete")
    return {
        "account_slot": account_slot,
        "account_id": account.get("account_id"),
        "expected_profile_id": profile_id,
        "expected_nickname": nickname,
    }


def detect_visible_risk_codes(body_text: object) -> list[str]:
    """Classify explicit challenge/risk copy without flagging ordinary SMS login UI."""
    text = body_text if isinstance(body_text, str) else ""
    return [
        code
        for code, pattern in VISIBLE_RISK_PATTERN_SOURCES
        if re.search(pattern, text)
    ]


def build_session_probe_code(expected_profile_id: str) -> str:
    profile_id = str(expected_profile_id).strip()
    if not profile_id or any(char not in "0123456789abcdefABCDEF" for char in profile_id):
        raise ValueError("expected profile id must be one public hexadecimal id")
    expected = json.dumps(profile_id)
    endpoint = json.dumps(SESSION_ENDPOINT)
    risk_pattern_sources = json.dumps(
        VISIBLE_RISK_PATTERN_SOURCES,
        ensure_ascii=False,
    )
    return f"""async (page) => {{
      const expectedProfileId = {expected};
      const selfLink = page.getByRole('link', {{name:'我', exact:true}}).filter({{visible:true}});
      const selfCount = await selfLink.count();
      const selfHref = selfCount === 1 ? await selfLink.getAttribute('href') : null;
      let domProfileMatch = false;
      if (selfHref) {{
        try {{ domProfileMatch = new URL(selfHref, page.url()).pathname === `/user/profile/${{expectedProfileId}}`; }}
        catch {{ domProfileMatch = false; }}
      }}
      const bodyText = await page.locator('body').innerText().catch(() => '');
      const riskPatternSources = {risk_pattern_sources};
      const riskCodes = riskPatternSources
        .filter(([, source]) => new RegExp(source, 'u').test(bodyText))
        .map(([code]) => code);
      const loginPromptCount = await page.getByText('登录后查看', {{exact:false}}).filter({{visible:true}}).count();
      const api = await page.evaluate(async (args) => {{
        const parseTime = (value) => {{
          if (!value) return null;
          const numeric = /^\\d{{10,13}}$/.test(value) ? Number(value) : null;
          const millis = numeric === null ? Date.parse(value) : (value.length === 10 ? numeric * 1000 : numeric);
          return Number.isFinite(millis) ? new Date(millis).toISOString() : null;
        }};
        const containsExact = (value, expected, depth = 0) => {{
          if (depth > 8) return false;
          if (typeof value === 'string') return value === expected;
          if (Array.isArray(value)) return value.slice(0, 100).some((item) => containsExact(item, expected, depth + 1));
          if (value && typeof value === 'object') return Object.values(value).slice(0, 100).some((item) => containsExact(item, expected, depth + 1));
          return false;
        }};
        try {{
          const response = await fetch(args.endpoint, {{credentials:'include', cache:'no-store'}});
          let profileMatch = false;
          try {{ profileMatch = containsExact(await response.json(), args.expectedProfileId); }} catch {{}}
          const responseDate = parseTime(response.headers.get('date'));
          const cacheExpiresPresent = Boolean(response.headers.get('expires'));
          const ttlCandidates = ['x-session-expires-at', 'x-auth-expires-at'];
          let exactTtlSource = null;
          let exactSessionExpiresAt = null;
          for (const name of ttlCandidates) {{
            const parsed = parseTime(response.headers.get(name));
            if (parsed) {{ exactTtlSource = name; exactSessionExpiresAt = parsed; break; }}
          }}
          return {{
            api_http_status: response.status,
            api_http_ok: response.ok,
            api_expected_profile_match: profileMatch,
            response_date_present: responseDate !== null,
            response_date_at: responseDate,
            cache_expires_present: cacheExpiresPresent,
            exact_ttl_header_present: exactSessionExpiresAt !== null,
            exact_session_expires_at: exactSessionExpiresAt,
            exact_ttl_source: exactTtlSource,
            api_request_failed: false,
          }};
        }} catch {{
          return {{
            api_http_status: null,
            api_http_ok: false,
            api_expected_profile_match: false,
            response_date_present: false,
            response_date_at: null,
            cache_expires_present: false,
            exact_ttl_header_present: false,
            exact_session_expires_at: null,
            exact_ttl_source: null,
            api_request_failed: true,
          }};
        }}
      }}, {{endpoint:{endpoint}, expectedProfileId}});
      return {{
        dom_self_profile_count: selfCount,
        dom_profile_match: domProfileMatch,
        login_prompt_count: loginPromptCount,
        risk_codes: riskCodes,
        ...api,
      }};
    }}"""


def parse_session_probe_result(text: str) -> dict[str, Any]:
    """Extract only the bounded probe object from an MCP text response."""
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "dom_self_profile_count" in value:
            return value
    raise ValueError("browser session probe returned no bounded JSON object")


def _parse_iso(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_session_probe(
    raw: object,
    *,
    account_slot: int,
    expected_profile_id: str,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("session probe must return one bounded object")
    risk_codes = raw.get("risk_codes")
    if not isinstance(risk_codes, list) or any(
        value not in ALLOWED_RISK_CODES for value in risk_codes
    ):
        raise ValueError("session probe returned an unknown risk code")
    self_count = raw.get("dom_self_profile_count")
    login_count = raw.get("login_prompt_count")
    api_status = raw.get("api_http_status")
    if not isinstance(self_count, int) or isinstance(self_count, bool) or self_count < 0:
        raise ValueError("session probe returned an invalid self-profile count")
    if not isinstance(login_count, int) or isinstance(login_count, bool) or login_count < 0:
        raise ValueError("session probe returned an invalid login-prompt count")
    if api_status is not None and (
        not isinstance(api_status, int) or isinstance(api_status, bool)
    ):
        raise ValueError("session probe returned an invalid API status")
    dom_match = raw.get("dom_profile_match") is True
    api_ok = raw.get("api_http_ok") is True and api_status == 200
    api_match = raw.get("api_expected_profile_match") is True
    risk_observed = bool(risk_codes)
    if risk_observed:
        status = "risk_blocked"
    elif self_count == 1 and (not dom_match or (api_ok and not api_match)):
        status = "identity_mismatch"
    elif self_count == 1 and dom_match and login_count == 0 and api_ok and api_match:
        status = "valid"
    elif login_count > 0 or self_count == 0 or api_status in {401, 403}:
        status = "login_required"
    else:
        status = "indeterminate"
    ttl_source = raw.get("exact_ttl_source")
    expires_at = _parse_iso(raw.get("exact_session_expires_at"))
    exact_ttl_available = bool(
        raw.get("exact_ttl_header_present") is True
        and ttl_source in ALLOWED_EXACT_TTL_SOURCES
        and expires_at is not None
    )
    if not exact_ttl_available:
        ttl_source = None
        expires_at = None
    result = {
        "schema_version": 1,
        "contract_id": SESSION_PROBE_CONTRACT_ID,
        "status": status,
        "account_slot": account_slot,
        "expected_profile_id": expected_profile_id,
        "observed_at": (observed_at or datetime.now(timezone.utc))
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "session_reusable": status == "valid",
        "qr_human_gate_required": status in {"login_required", "identity_mismatch"},
        "risk_signal_observed": risk_observed,
        "risk_codes": list(risk_codes),
        "dom_profile_match": dom_match,
        "login_prompt_observed": login_count > 0,
        "api_http_200": api_ok,
        "api_expected_profile_match": api_match,
        "response_date_present": raw.get("response_date_present") is True,
        "response_date_at": _parse_iso(raw.get("response_date_at")),
        "cache_expires_header_present": raw.get("cache_expires_present") is True,
        "exact_session_ttl_available": exact_ttl_available,
        "session_expires_at": expires_at,
        "ttl_source": ttl_source,
        "remaining_session_seconds": None,
        "next_action": {
            "valid": "reuse_slot_profile_without_logout_or_qr_refresh",
            "login_required": "enter_existing_qr_human_gate_for_this_slot",
            "identity_mismatch": "enter_confirmed_account_switch_qr_human_gate_for_this_slot",
            "risk_blocked": "stop_without_refresh_or_account_switch",
            "indeterminate": "stop_and_save_bounded_probe_evidence",
        }[status],
    }
    assert_no_sensitive_data(result)
    return result
