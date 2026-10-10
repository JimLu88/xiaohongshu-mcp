"""Shared, privacy-bounded state for Xiaohongshu QR login surfaces."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCHEMA_VERSION = 2
ACCOUNT_CONTEXT_CONTRACT_ID = "panse-xhs-qr-account-context.v1"
ACCOUNT_CONTEXT_FIELDS = (
    "account_slot",
    "masked_phone",
    "device",
    "expected_nickname",
    "working_name",
    "login_purpose",
)
STATUSES = {"unavailable", "active", "expired", "scanned", "confirmed", "failed"}
ERROR_CODES = {
    None,
    "browser_missing",
    "browser_call_failed",
    "browser_initialize_failed",
    "browser_navigate_failed",
    "browser_identity_probe_failed",
    "browser_identity_mismatch",
    "browser_risk_signal",
    "browser_qr_capture_failed",
    "qr_not_found",
    "refresh_already_used",
    "refresh_in_progress",
    "invalid_artifact",
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SENSITIVE_KEY = re.compile(
    r"(?i)(cookie|token|password|verification.?code|session.?storage|qr.?payload|phone)"
)
SENSITIVE_VALUE = re.compile(
    r"(?i)(bearer\s+[a-z0-9._-]+|(?:access|refresh)[_-]?token\s*[:=]|\b1\d{10}\b)"
)
MASKED_PHONE = re.compile(r"^1\d{2}\*{4}\d{4}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def markdown_image(path: Path) -> str:
    normalized = path.resolve().as_posix()
    if re.match(r"^[A-Za-z]:/", normalized):
        normalized = "/" + normalized
    return f"![小红书登录二维码]({normalized})"


def assert_no_sensitive_data(value: object, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if SENSITIVE_KEY.search(str(key)) and str(key) != "masked_phone":
                raise ValueError(f"sensitive state key rejected at {path}.{key}")
            assert_no_sensitive_data(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            assert_no_sensitive_data(item, f"{path}[{index}]")
    elif isinstance(value, str) and SENSITIVE_VALUE.search(value):
        raise ValueError(f"sensitive state value rejected at {path}")


def validate_account_context(context: object) -> dict[str, Any]:
    if not isinstance(context, dict):
        raise ValueError("QR account context is required")
    if set(context) != set(ACCOUNT_CONTEXT_FIELDS):
        raise ValueError("QR account context fields are incomplete or ambiguous")
    normalized = {
        "account_slot": context.get("account_slot"),
        **{
            field: str(context.get(field, "")).strip()
            for field in ACCOUNT_CONTEXT_FIELDS
            if field != "account_slot"
        },
    }
    if not isinstance(normalized["account_slot"], int) or not 1 <= normalized["account_slot"] <= 5:
        raise ValueError("QR account slot must be an integer from 1 to 5")
    if not MASKED_PHONE.fullmatch(normalized["masked_phone"]):
        raise ValueError("QR account context requires one masked phone number")
    if any(not normalized[field] for field in ACCOUNT_CONTEXT_FIELDS):
        raise ValueError("QR account context fields must not be blank")
    assert_no_sensitive_data(normalized)
    return normalized


def account_context_sha256(context: dict[str, Any]) -> str:
    canonical = json.dumps(
        validate_account_context(context),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_account_context(
    *,
    binding_path: Path,
    plan_path: Path,
    account_slot: int,
    plan_date: str,
    today: str | None = None,
) -> dict[str, Any]:
    """Load one exact sanitized context from the binding and current-date plan."""
    today = today or datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    if plan_date != today:
        raise ValueError("QR login plan date is stale")
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    accounts = binding.get("accounts")
    if not isinstance(accounts, list):
        raise ValueError("authoritative account binding is missing accounts")
    matches = [item for item in accounts if item.get("slot") == account_slot]
    if len(matches) != 1:
        raise ValueError("target account slot is missing or ambiguous")
    account = matches[0]
    if plan.get("date") != plan_date or plan.get("account_slot") != account_slot:
        raise ValueError("daily plan date or target slot does not match")
    if plan.get("account_id") != account.get("account_id"):
        raise ValueError("daily plan account does not match authoritative binding")
    profile = account.get("platform_profile")
    if not isinstance(profile, dict):
        raise ValueError("authoritative account nickname is missing")
    comparisons = {
        "masked_phone": (plan.get("masked_phone"), account.get("phone_mask")),
        "device": (plan.get("device"), account.get("device")),
        "expected_nickname": (
            plan.get("observed_nickname"),
            profile.get("observed_nickname"),
        ),
        "working_name": (plan.get("working_name"), account.get("working_name")),
        "role": (plan.get("role"), account.get("public_role")),
    }
    for field, (plan_value, binding_value) in comparisons.items():
        if not isinstance(plan_value, str) or not plan_value.strip():
            raise ValueError(f"daily plan {field} is missing")
        if plan_value != binding_value:
            raise ValueError(f"daily plan {field} does not match authoritative binding")
    return validate_account_context(
        {
            "account_slot": account_slot,
            "masked_phone": comparisons["masked_phone"][0],
            "device": comparisons["device"][0],
            "expected_nickname": comparisons["expected_nickname"][0],
            "working_name": comparisons["working_name"][0],
            "login_purpose": (
                f"继续 {plan_date} {comparisons['role'][0]}账号日常运营"
            ),
        }
    )


class QrStateStore:
    """Atomic state and image store shared by chat and local-page surfaces."""

    def __init__(self, root: Path, account_context: dict[str, Any] | None = None):
        self.root = root.resolve()
        self.state_path = self.root / "state.json"
        self.image_path = self.root / "current-qr.png"
        self.staging_path = self.root / ".staging-qr.png"
        self.account_context = (
            validate_account_context(account_context)
            if account_context is not None
            else None
        )
        self.root.mkdir(parents=True, exist_ok=True)

    def _default(self) -> dict[str, Any]:
        context = dict(self.account_context) if self.account_context is not None else None
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "unavailable",
            "generation": 0,
            "source": "playwright_browser",
            "created_at": None,
            "expires_at": None,
            "image_path": None,
            "markdown_image": None,
            "image_sha256": None,
            "account_context_contract_id": ACCOUNT_CONTEXT_CONTRACT_ID,
            "account_context": context,
            "account_context_sha256": (
                account_context_sha256(context) if context is not None else None
            ),
            "last_error_code": None,
        }

    def _migrate(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("schema_version") == SCHEMA_VERSION:
            return state
        if state.get("schema_version") != 1:
            raise ValueError("unexpected QR state schema")
        migrated = self._default()
        migrated["generation"] = int(state.get("generation", 0))
        return migrated

    def _context_matches(self, state: dict[str, Any]) -> bool:
        context = state.get("account_context")
        if not isinstance(context, dict):
            return False
        try:
            validated = validate_account_context(context)
        except ValueError:
            return False
        if state.get("account_context_contract_id") != ACCOUNT_CONTEXT_CONTRACT_ID:
            return False
        if state.get("account_context_sha256") != account_context_sha256(validated):
            return False
        return self.account_context is not None and validated == self.account_context

    def _write(self, state: dict[str, Any]) -> dict[str, Any]:
        self.validate(state)
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, self.state_path)
        return state

    def validate(self, state: dict[str, Any]) -> None:
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unexpected QR state schema")
        if state.get("status") not in STATUSES:
            raise ValueError("unexpected QR status")
        if state.get("source") != "playwright_browser":
            raise ValueError("QR source must remain playwright_browser")
        if state.get("last_error_code") not in ERROR_CODES:
            raise ValueError("unbounded QR error code rejected")
        if state.get("account_context_contract_id") != ACCOUNT_CONTEXT_CONTRACT_ID:
            raise ValueError("unexpected QR account context contract")
        if state.get("status") in {"active", "scanned"} and not self._context_matches(state):
            raise ValueError("active QR state account context is missing or mismatched")
        assert_no_sensitive_data(state)

    def load(self, now: datetime | None = None) -> dict[str, Any]:
        state = self._default()
        if self.state_path.is_file():
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            migrated = self._migrate(state)
            if migrated is not state:
                state = self._write(migrated)
            else:
                state = migrated
            self.validate(state)
            if (
                state["status"] == "unavailable"
                and self.account_context is not None
                and not self._context_matches(state)
            ):
                state["account_context"] = dict(self.account_context)
                state["account_context_sha256"] = account_context_sha256(
                    self.account_context
                )
                state = self._write(state)
        now = now or utc_now()
        if state["status"] in {"active", "scanned"} and state.get("expires_at"):
            if now >= parse_time(state["expires_at"]):
                state["status"] = "expired"
                state["last_error_code"] = None
                self._write(state)
        return state

    def publish_image(
        self,
        source: Path,
        *,
        ttl_seconds: int,
        status: str = "active",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if status not in {"active", "confirmed"}:
            raise ValueError("new QR image may only be active or confirmed")
        raw = source.read_bytes()
        if not raw.startswith(PNG_SIGNATURE) or not 256 <= len(raw) <= 5_000_000:
            raise ValueError("QR artifact must be a bounded PNG")
        if not 15 <= ttl_seconds <= 300:
            raise ValueError("QR ttl must remain between 15 and 300 seconds")
        now = now or utc_now()
        if self.account_context is None:
            raise ValueError("QR account context is required before publishing")
        previous = self.load(now)
        temporary = self.image_path.with_suffix(".png.tmp")
        temporary.write_bytes(raw)
        os.replace(temporary, self.image_path)
        state = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "generation": int(previous.get("generation", 0)) + 1,
            "source": "playwright_browser",
            "created_at": isoformat(now),
            "expires_at": isoformat(now + timedelta(seconds=ttl_seconds)),
            "image_path": str(self.image_path),
            "markdown_image": markdown_image(self.image_path),
            "image_sha256": hashlib.sha256(raw).hexdigest(),
            "account_context_contract_id": ACCOUNT_CONTEXT_CONTRACT_ID,
            "account_context": dict(self.account_context),
            "account_context_sha256": account_context_sha256(self.account_context),
            "last_error_code": None,
        }
        return self._write(state)

    def record_status(
        self,
        status: str,
        *,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        if status not in STATUSES:
            raise ValueError("unexpected QR status")
        if error_code not in ERROR_CODES:
            raise ValueError("unbounded QR error code rejected")
        state = self.load()
        if state.get("account_context") is None and self.account_context is not None:
            state["account_context"] = dict(self.account_context)
            state["account_context_sha256"] = account_context_sha256(
                self.account_context
            )
        state["status"] = status
        state["last_error_code"] = error_code
        return self._write(state)

    def public_state(self) -> dict[str, Any]:
        state = self.load()
        context_valid = self._context_matches(state)
        live_status = state["status"] in {"active", "scanned"}
        image_available = bool(
            context_valid
            and live_status
            and state.get("image_path")
            and Path(state["image_path"]).is_file()
        )
        markdown = (
            state.get("markdown_image")
            if image_available
            else None
        )
        public = {
            "schema_version": state["schema_version"],
            "account_context_contract_id": state["account_context_contract_id"],
            "status": state["status"],
            "generation": state["generation"],
            "source": state["source"],
            "created_at": state["created_at"],
            "expires_at": state["expires_at"],
            "image_available": image_available,
            "markdown_image": markdown,
            "last_error_code": state.get("last_error_code"),
        }
        for field in ACCOUNT_CONTEXT_FIELDS:
            public[field] = (
                state["account_context"].get(field)
                if context_valid
                else None
            )
        return public


class RefreshGate:
    """Allow one user-triggered refresh for each expired/failed generation."""

    def __init__(self) -> None:
        self._used: set[tuple[int, str]] = set()
        self.in_progress = False

    def begin(self, state: dict[str, Any], action: str) -> None:
        if self.in_progress:
            raise RuntimeError("refresh_in_progress")
        if action not in {"refresh", "switch_account"}:
            raise ValueError("unknown refresh action")
        if action == "refresh" and state["status"] not in {
            "expired",
            "failed",
            "unavailable",
        }:
            raise RuntimeError("refresh_requires_expired_or_failed_state")
        key = (int(state["generation"]), action)
        if key in self._used:
            raise RuntimeError("refresh_already_used")
        self._used.add(key)
        self.in_progress = True

    def finish(self) -> None:
        self.in_progress = False


def copy_confirmed_artifact(source: Path, store: QrStateStore) -> dict[str, Any]:
    """Import a real previously displayed QR as confirmed evidence, never active."""
    return store.publish_image(source, ttl_seconds=15, status="confirmed")
