#!/usr/bin/env python3
"""Plan and record evidence for the Panse five-account XHS calibration cycle.

This tool never logs in, follows, comments, or publishes.  It creates an
idempotent daily plan and records evidence produced by an authorized browser
session.  External actions remain subject to the policies referenced by the
plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "research" / "panse_multi_direction"
RUNS = ROOT / "daily_runs"
BINDING = ROOT / "account_role_binding_v1.json"
SCOPE = ROOT / "five_account_daily_scope_v1.json"
COMMENT_POLICY = ROOT / "comment_warmup_policy_v2.json"
FOLLOW_POLICY = ROOT / "follow_warmup_policy_v1.json"
READ_VOLUME_POLICY_ID = "panse-xhs-daily-read-volume.v1"
READ_PACING_CONTRACT_ID = "panse-xhs-adjacent-view-pacing.v1"
READ_PROGRESS_STAGES = ("opened", "body_read", "media_reviewed", "comments_read")
XHS_LOCAL_ZONE = ZoneInfo("Asia/Shanghai")


class RunnerError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RunnerError(f"required file is missing: {path}") from exc


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def current_utc() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise RunnerError("pacing clock must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RunnerError("pacing state contains an invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise RunnerError("pacing state timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise RunnerError("date must use YYYY-MM-DD") from exc


def phase_for_day(policy: dict[str, Any], cycle_day: int) -> dict[str, Any]:
    for phase in policy["weekly_phases"]:
        low, high = phase["cycle_days"]
        if low <= cycle_day <= high:
            return phase
    raise RunnerError(f"cycle day {cycle_day} is outside the configured 28-day cycle")


def latest_cycle_days(before: date) -> dict[int, int]:
    result: dict[int, int] = {}
    if not RUNS.exists():
        return result
    for directory in sorted(RUNS.iterdir(), reverse=True):
        if not directory.is_dir():
            continue
        try:
            directory_day = date.fromisoformat(directory.name)
        except ValueError:
            continue
        if directory_day >= before:
            continue
        for path in directory.glob("account_*_daily_plan.json"):
            try:
                payload = load_json(path)
                slot = int(payload["account_slot"])
                cycle_day = int(payload["cycle_day"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
            result.setdefault(slot, cycle_day)
        if len(result) == 5:
            break
    return result


def observed_name(account: dict[str, Any]) -> str:
    profile = account.get("platform_profile") or {}
    return profile.get("observed_nickname") or account.get("working_name") or "未记录"


def deterministic_rng(day: date, slot: int) -> random.Random:
    seed_text = f"panse-xhs-warmup-v1:{day.isoformat()}:slot-{slot}"
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(seed)


def active_read_contract(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = policy or load_json(COMMENT_POLICY)
    selection = policy.get("daily_target_selection") or {}
    pacing = (policy.get("reading_protocol") or {}).get("adjacent_view_pacing") or {}
    target_range = selection.get("daily_read_target_range")
    phase_ranges = [
        phase.get("daily_browse_range_possible")
        for phase in policy.get("weekly_phases", [])
    ]
    if (
        selection.get("read_target_policy_id") != READ_VOLUME_POLICY_ID
        or target_range != [5, 8]
        or len(phase_ranges) != 4
        or any(value != [5, 8] for value in phase_ranges)
    ):
        raise RunnerError(
            "daily read volume contract must remain exactly 5-8 in every cycle phase"
        )
    minimum = pacing.get("minimum_interval_seconds")
    maximum = pacing.get("maximum_interval_seconds")
    progress_stages = pacing.get("progress_stages")
    if (
        pacing.get("contract_id") != READ_PACING_CONTRACT_ID
        or not isinstance(minimum, int)
        or not isinstance(maximum, int)
        or minimum < 30
        or maximum > 45
        or minimum > maximum
        or pacing.get("record_read_requires_matching_unconsumed_permit") is not True
        or pacing.get("first_view_wait_required") is not False
        or progress_stages != list(READ_PROGRESS_STAGES)
        or pacing.get("progress_heartbeat_seconds") != 300
        or pacing.get("permit_idle_timeout_seconds") != 600
        or pacing.get("permit_absolute_timeout_seconds") != 1800
        or pacing.get("same_local_date_required") is not True
        or pacing.get("expired_permit_requires_explicit_resume") is not True
    ):
        raise RunnerError(
            "adjacent view pacing contract must keep 30-45 second spacing, "
            "5-minute progress checkpoints, 10-minute idle timeout, and 30-minute absolute timeout"
        )
    return {
        "read_target_policy_id": READ_VOLUME_POLICY_ID,
        "daily_read_target_range": [5, 8],
        "read_pacing_contract_id": READ_PACING_CONTRACT_ID,
        "minimum_interval_seconds": minimum,
        "maximum_interval_seconds": maximum,
        "interval_basis": pacing.get("interval_basis"),
        "permit_entrypoint": pacing.get("permit_entrypoint"),
        "progress_entrypoint": pacing.get("progress_entrypoint"),
        "progress_stages": list(READ_PROGRESS_STAGES),
        "progress_heartbeat_seconds": 300,
        "permit_idle_timeout_seconds": 600,
        "permit_absolute_timeout_seconds": 1800,
        "same_local_date_required": True,
        "expired_permit_requires_explicit_resume": True,
        "record_read_requires_matching_unconsumed_permit": True,
    }


def deterministic_read_target(day: date, slot: int, policy: dict[str, Any]) -> int:
    contract = active_read_contract(policy)
    low, high = contract["daily_read_target_range"]
    seed_text = f"{READ_VOLUME_POLICY_ID}:{day.isoformat()}:slot-{slot}"
    value = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
    return low + value % (high - low + 1)


def planned_targets(
    day: date,
    slot: int,
    cycle_day: int,
    comment_phase: dict[str, Any],
    follow_phase: dict[str, Any] | None,
    comment_policy: dict[str, Any],
) -> dict[str, Any]:
    rng = deterministic_rng(day, slot)
    comment_low, comment_high = comment_phase["daily_comment_range"]

    # The 15-day role-calibration plan treats policy numbers as candidate caps,
    # not a mandatory send quota.  Days 5-6 deliberately stay at four drafts.
    if cycle_day in (5, 6):
        comment_cap = min(4, comment_high)
    elif 8 <= cycle_day <= 15:
        comment_cap = min(6 if cycle_day < 14 else comment_high, comment_high)
    else:
        comment_cap = rng.randint(comment_low, comment_high)

    browse_target = deterministic_read_target(day, slot, comment_policy)
    read_contract = active_read_contract(comment_policy)

    follow_target = 0
    if follow_phase is not None:
        follow_low, follow_high = follow_phase["daily_range"]
        if 5 <= cycle_day <= 15:
            follow_high = min(1, follow_high)
        follow_target = rng.randint(follow_low, follow_high)

    return {
        "planned_comment_draft_cap": comment_cap,
        "browse_multiplier": None,
        "planned_browse_target": browse_target,
        "planned_deep_read_target": browse_target,
        **read_contract,
        "planned_follow_target": follow_target,
    }


def plan_day(day_text: str) -> dict[str, Any]:
    target_day = parse_day(day_text)
    run_dir = RUNS / day_text
    existing_manifest = run_dir / "warmup_run_manifest.json"
    if existing_manifest.exists():
        manifest = load_json(existing_manifest)
        manifest["deduplicated"] = True
        manifest["message"] = "same-day plan already exists; no files were overwritten"
        return manifest

    binding = load_json(BINDING)
    scope = load_json(SCOPE)
    comment_policy = load_json(COMMENT_POLICY)
    follow_policy = load_json(FOLLOW_POLICY)
    required_slots = [int(value) for value in scope["daily_required_slots"]]
    accounts = {int(item["slot"]): item for item in binding["accounts"]}
    prior_days = latest_cycle_days(target_day)
    plans: list[dict[str, Any]] = []

    for slot in required_slots:
        account = accounts.get(slot)
        if not account:
            raise RunnerError(f"slot {slot} is authorized but has no role binding")
        cycle_day = prior_days.get(slot, 0) + 1
        comment_phase = phase_for_day(comment_policy, cycle_day)
        follow_phase = None
        if slot in follow_policy["applies_to_account_slots"]:
            follow_phase = phase_for_day(follow_policy, cycle_day)
        targets = planned_targets(
            target_day,
            slot,
            cycle_day,
            comment_phase,
            follow_phase,
            comment_policy,
        )
        plan = {
            "schema_version": 3,
            "date": day_text,
            "account_slot": slot,
            "account_id": account["account_id"],
            "masked_phone": account["phone_mask"],
            "device": account["device"],
            "observed_nickname": observed_name(account),
            "working_name": account.get("working_name"),
            "role": account["public_role"],
            "cycle_day": cycle_day,
            "week": comment_phase["week"],
            "phase": comment_phase["phase"],
            **targets,
            "topic_pool": account["warmup_topic_pool"],
            "status": "planned_not_started",
            "deduplicated": False,
            "browser": "codex_in_app_browser_only",
            "external_actions_performed": False,
            "actual_browse": 0,
            "actual_deep_reads": 0,
            "drafts_ready": 0,
            "public_visible_comments": 0,
            "follow_attempts": 0,
            "verified_follows": 0,
            "comments_require_current_user_approval": False,
            "comment_submission_required_after_all_gates": True,
            "comment_send_allowed": False,
            "likes_favorites_private_messages_enabled": False,
            "stop_reason": None,
            "idempotency_key": f"panse:xhs:warmup:{day_text}:slot-{slot}",
        }
        write_json(run_dir / f"account_{slot}_daily_plan.json", plan)
        plans.append(plan)

    totals = {
        "browse": sum(item["planned_browse_target"] for item in plans),
        "deep_reads": sum(item["planned_deep_read_target"] for item in plans),
        "comment_draft_cap": sum(item["planned_comment_draft_cap"] for item in plans),
        "follows": sum(item["planned_follow_target"] for item in plans),
    }
    manifest = {
        "schema_version": 1,
        "project": binding["project"],
        "date": day_text,
        "created_at": utc_now(),
        "scope": required_slots,
        "cycle_days": {str(item["account_slot"]): item["cycle_day"] for item in plans},
        "totals_planned": totals,
        "status": "planned_not_started",
        "deduplicated": False,
        "external_actions_performed": False,
        "comment_gate": "generate_review_submit_and_verify",
        "source_files": [
            str(BINDING.relative_to(REPO)),
            str(SCOPE.relative_to(REPO)),
            str(COMMENT_POLICY.relative_to(REPO)),
            str(FOLLOW_POLICY.relative_to(REPO)),
        ],
    }
    status = {
        "schema_version": 2,
        "date": day_text,
        "timezone": "Asia/Shanghai",
        "scope": required_slots,
        "overall_status": "planned_not_started",
        "comment_gate": "generate_review_submit_and_verify",
        "totals_planned": totals,
        "totals_verified": {
            "browse": 0,
            "deep_reads": 0,
            "comment_drafts": 0,
            "public_visible_comments": 0,
            "follows": 0,
        },
        "accounts": [
            {
                "account_slot": item["account_slot"],
                "cycle_day": item["cycle_day"],
                "status": item["status"],
                "planned_browse": item["planned_browse_target"],
                "planned_comment_drafts": item["planned_comment_draft_cap"],
                "planned_follows": item["planned_follow_target"],
                "actual_browse": 0,
                "actual_deep_reads": 0,
                "drafts_ready": 0,
                "public_visible_comments": 0,
                "verified_follows": 0,
                "stop_reason": None,
            }
            for item in plans
        ],
    }
    write_json(run_dir / "five_account_daily_status.json", status)
    write_json(existing_manifest, manifest)
    return manifest


def all_same_day_note_ids(run_dir: Path, exclude_slot: int | None = None) -> set[str]:
    seen: set[str] = set()
    for path in run_dir.glob("account_*_read_receipts.json"):
        if exclude_slot is not None and path.name.startswith(f"account_{exclude_slot}_"):
            continue
        payload = load_json(path)
        for item in payload.get("items", []):
            if item.get("note_id"):
                seen.add(str(item["note_id"]))
    return seen


def pacing_state_path(run_dir: Path, slot: int) -> Path:
    return run_dir / f"account_{slot}_read_pacing_state.json"


def read_session_stop_path(run_dir: Path, slot: int) -> Path:
    return run_dir / f"account_{slot}_read_session_stop_receipts.json"


def active_read_day_matches(day_text: str, now: datetime) -> bool:
    if now.tzinfo is None:
        raise RunnerError("read-session clock must be timezone-aware")
    return now.astimezone(XHS_LOCAL_ZONE).date() == parse_day(day_text)


def permit_deadlines(permit: dict[str, Any], contract: dict[str, Any]) -> tuple[datetime, datetime]:
    issued_at = parse_utc(str(permit.get("issued_at") or ""))
    last_progress_at = parse_utc(str(permit.get("last_progress_at") or permit.get("issued_at") or ""))
    return (
        last_progress_at + timedelta(seconds=contract["permit_idle_timeout_seconds"]),
        issued_at + timedelta(seconds=contract["permit_absolute_timeout_seconds"]),
    )


def permit_expiration_reason(
    permit: dict[str, Any],
    *,
    day_text: str,
    now: datetime,
    contract: dict[str, Any],
) -> str | None:
    if permit.get("consumed_at") or permit.get("expired_at"):
        return None
    if not active_read_day_matches(day_text, now):
        return "date_boundary"
    idle_deadline, absolute_deadline = permit_deadlines(permit, contract)
    now_utc = now.astimezone(timezone.utc)
    if now_utc >= absolute_deadline:
        return "absolute_timeout"
    if now_utc >= idle_deadline:
        return "no_progress_timeout"
    return None


def mark_read_session_stopped(
    *,
    run_dir: Path,
    slot: int,
    state: dict[str, Any],
    permit: dict[str, Any],
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    stopped_at = utc_iso(now)
    permit["expired_at"] = permit.get("expired_at") or stopped_at
    permit["expiration_reason"] = permit.get("expiration_reason") or reason
    state["resume_required"] = True
    state["stopped_at"] = stopped_at
    state["stop_reason"] = reason
    write_json(pacing_state_path(run_dir, slot), state)

    stop_path = read_session_stop_path(run_dir, slot)
    stops = load_json(stop_path) if stop_path.exists() else {
        "schema_version": 1,
        "date": state.get("date"),
        "account_slot": slot,
        "items": [],
    }
    stop_key = f"{permit.get('permit_id')}:{reason}"
    if not any(item.get("stop_key") == stop_key for item in stops.get("items", [])):
        stops.setdefault("items", []).append(
            {
                "stop_key": stop_key,
                "permit_id": permit.get("permit_id"),
                "item_index": permit.get("item_index"),
                "reason": reason,
                "stopped_at": stopped_at,
                "resume_requires_identity_login_and_risk_reverification": True,
                "browser_close_required": True,
                "old_permit_reuse_forbidden": True,
            }
        )
        write_json(stop_path, stops)

    plan_path = run_dir / f"account_{slot}_daily_plan.json"
    plan = load_json(plan_path)
    plan["status"] = "stopped_date_boundary" if reason == "date_boundary" else "stopped_no_progress"
    plan["stop_reason"] = reason
    write_json(plan_path, plan)

    status_path = run_dir / "five_account_daily_status.json"
    if status_path.exists():
        status = load_json(status_path)
        matches = [
            item
            for item in status.get("accounts", [])
            if int(item.get("account_slot", 0)) == slot
        ]
        if len(matches) == 1:
            matches[0]["status"] = plan["status"]
            matches[0]["stop_reason"] = reason
            write_json(status_path, status)
    return {
        "status": plan["status"],
        "stop_reason": reason,
        "permit_id": permit.get("permit_id"),
        "stop_receipt": str(stop_path),
        "browser_close_required": True,
        "resume_required": True,
    }


def require_live_permit(
    *,
    run_dir: Path,
    slot: int,
    permit_id: str,
    item_index: int,
    now: datetime,
    contract: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    state_path = pacing_state_path(run_dir, slot)
    state = load_json(state_path)
    if (
        state.get("contract_id") != READ_PACING_CONTRACT_ID
        or int(state.get("account_slot", 0)) != slot
        or state.get("date") != run_dir.name
    ):
        raise RunnerError("read pacing state identity does not match the requested session")
    matches = [
        item
        for item in state.get("permits", [])
        if item.get("permit_id") == permit_id
        and int(item.get("item_index", 0)) == item_index
    ]
    if len(matches) != 1 or matches[0].get("consumed_at"):
        raise RunnerError("record-read requires one matching unconsumed pacing permit")
    permit = matches[0]
    reason = permit_expiration_reason(
        permit,
        day_text=str(state.get("date")),
        now=now,
        contract=contract,
    )
    if reason:
        mark_read_session_stopped(
            run_dir=run_dir,
            slot=slot,
            state=state,
            permit=permit,
            reason=reason,
            now=now,
        )
        raise RunnerError(
            f"read pacing permit expired: {reason}; close the dedicated browser and explicitly resume after identity, login, and risk reverification"
        )
    return state, permit


def deterministic_pacing_interval(day_text: str, slot: int, item_index: int) -> int:
    contract = active_read_contract()
    low = contract["minimum_interval_seconds"]
    high = contract["maximum_interval_seconds"]
    seed_text = f"{READ_PACING_CONTRACT_ID}:{day_text}:slot-{slot}:item-{item_index}"
    value = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
    return low + value % (high - low + 1)


def issue_read_pacing_permit(
    args: argparse.Namespace,
    *,
    now_provider: Callable[[], datetime] | None = None,
    sleep_func: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Wait for the governed gap, then issue one auditable next-view permit."""
    now_provider = now_provider or current_utc
    sleep_func = sleep_func or time.sleep
    run_dir = RUNS / args.date
    plan = load_json(run_dir / f"account_{args.slot}_daily_plan.json")
    contract = active_read_contract()
    if (
        plan.get("read_target_policy_id") != READ_VOLUME_POLICY_ID
        or plan.get("read_pacing_contract_id") != READ_PACING_CONTRACT_ID
        or plan.get("minimum_interval_seconds") != contract["minimum_interval_seconds"]
        or any(plan.get(key) != contract[key] for key in contract)
    ):
        raise RunnerError("daily plan is missing the active read pacing contract")
    now = now_provider()
    if not active_read_day_matches(args.date, now):
        raise RunnerError("pace-next-read refuses a plan outside the current Asia/Shanghai date")
    target = int(plan.get("planned_deep_read_target", 0) or 0)
    low, high = contract["daily_read_target_range"]
    if not low <= target <= high:
        raise RunnerError("daily deep-read target is outside the active 5-8 contract")
    receipt_path = run_dir / f"account_{args.slot}_read_receipts.json"
    receipt = load_json(receipt_path) if receipt_path.exists() else {"items": []}
    items = receipt.get("items")
    if not isinstance(items, list):
        raise RunnerError("read receipt items must be a list")
    if len(items) >= target:
        raise RunnerError("daily read target has already been reached")
    item_index = len(items) + 1
    state_path = pacing_state_path(run_dir, args.slot)
    state = load_json(state_path) if state_path.exists() else {
        "schema_version": 2,
        "contract_id": READ_PACING_CONTRACT_ID,
        "date": args.date,
        "account_slot": args.slot,
        "minimum_interval_seconds": contract["minimum_interval_seconds"],
        "maximum_interval_seconds": contract["maximum_interval_seconds"],
        "progress_heartbeat_seconds": contract["progress_heartbeat_seconds"],
        "permit_idle_timeout_seconds": contract["permit_idle_timeout_seconds"],
        "permit_absolute_timeout_seconds": contract["permit_absolute_timeout_seconds"],
        "resume_required": False,
        "permits": [],
    }
    if (
        state.get("contract_id") != READ_PACING_CONTRACT_ID
        or state.get("date") != args.date
        or int(state.get("account_slot", 0)) != args.slot
        or state.get("minimum_interval_seconds") != contract["minimum_interval_seconds"]
        or state.get("maximum_interval_seconds") != contract["maximum_interval_seconds"]
        or not isinstance(state.get("permits"), list)
    ):
        raise RunnerError("read pacing state does not match the active plan")
    outstanding = [
        item
        for item in state["permits"]
        if not item.get("consumed_at") and not item.get("expired_at")
    ]
    if outstanding:
        if len(outstanding) != 1 or int(outstanding[0].get("item_index", 0)) != item_index:
            raise RunnerError("read pacing state has an ambiguous outstanding permit")
        reason = permit_expiration_reason(
            outstanding[0], day_text=args.date, now=now, contract=contract
        )
        if reason:
            mark_read_session_stopped(
                run_dir=run_dir,
                slot=args.slot,
                state=state,
                permit=outstanding[0],
                reason=reason,
                now=now,
            )
            raise RunnerError(
                f"read pacing permit expired: {reason}; close the dedicated browser and explicitly resume after reverification"
            )
        return {"deduplicated": True, **outstanding[0]}
    if state.get("resume_required"):
        raise RunnerError(
            "read session is stopped; explicit resume requires identity, login, and risk reverification"
        )

    required_interval = 0
    waited_seconds = 0.0
    previous_consumed_at = None
    if item_index > 1:
        previous = next(
            (
                item
                for item in state["permits"]
                if int(item.get("item_index", 0)) == item_index - 1
            ),
            None,
        )
        if not previous or not previous.get("consumed_at"):
            raise RunnerError("previous deep read has no consumed pacing permit")
        previous_consumed_at = str(previous["consumed_at"])
        required_interval = deterministic_pacing_interval(
            args.date, args.slot, item_index
        )
        next_allowed = parse_utc(previous_consumed_at) + timedelta(
            seconds=required_interval
        )
        now = now_provider().astimezone(timezone.utc)
        waited_seconds = max(0.0, (next_allowed - now).total_seconds())
        if waited_seconds > contract["maximum_interval_seconds"]:
            raise RunnerError("pacing clock moved backwards beyond the bounded interval")
        if waited_seconds:
            sleep_func(waited_seconds)
    issued_now = now_provider()
    if not active_read_day_matches(args.date, issued_now):
        raise RunnerError("date changed while pacing; do not open another item from the old plan")
    issued_at = utc_iso(issued_now)
    if previous_consumed_at and parse_utc(issued_at) < (
        parse_utc(previous_consumed_at) + timedelta(seconds=required_interval)
    ):
        raise RunnerError("next view permit was requested before the pacing wait completed")
    permit_seed = (
        f"{READ_PACING_CONTRACT_ID}:{args.date}:{args.slot}:{item_index}:"
        f"{previous_consumed_at or 'first'}:attempt-"
        f"{1 + sum(int(item.get('item_index', 0)) == item_index for item in state['permits'])}"
    )
    permit = {
        "permit_id": "readpermit_" + hashlib.sha256(
            permit_seed.encode("utf-8")
        ).hexdigest()[:24],
        "item_index": item_index,
        "required_interval_seconds": required_interval,
        "waited_seconds": round(waited_seconds, 3),
        "previous_read_recorded_at": previous_consumed_at,
        "issued_at": issued_at,
        "last_progress_at": issued_at,
        "progress_events": [],
        "next_progress_required_by": utc_iso(
            parse_utc(issued_at)
            + timedelta(seconds=contract["permit_idle_timeout_seconds"])
        ),
        "absolute_expires_at": utc_iso(
            parse_utc(issued_at)
            + timedelta(seconds=contract["permit_absolute_timeout_seconds"])
        ),
        "consumed_at": None,
        "expired_at": None,
        "expiration_reason": None,
    }
    state["permits"].append(permit)
    write_json(state_path, state)
    return {"deduplicated": False, **permit}


def touch_read_progress(
    args: argparse.Namespace,
    *,
    now_provider: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    now_provider = now_provider or current_utc
    now = now_provider()
    run_dir = RUNS / args.date
    receipt_path = run_dir / f"account_{args.slot}_read_receipts.json"
    receipt = load_json(receipt_path) if receipt_path.exists() else {"items": []}
    item_index = len(receipt.get("items", [])) + 1
    contract = active_read_contract()
    state, permit = require_live_permit(
        run_dir=run_dir,
        slot=args.slot,
        permit_id=args.pacing_permit_id,
        item_index=item_index,
        now=now,
        contract=contract,
    )
    stage = str(args.stage)
    events = permit.setdefault("progress_events", [])
    completed = [str(item.get("stage")) for item in events]
    expected_index = len(completed)
    if stage in completed:
        existing = next(item for item in events if item.get("stage") == stage)
        return {
            "deduplicated": True,
            "permit_id": permit["permit_id"],
            "stage": stage,
            "recorded_at": existing["recorded_at"],
            "next_progress_required_by": permit.get("next_progress_required_by"),
            "absolute_expires_at": permit.get("absolute_expires_at"),
        }
    if expected_index >= len(READ_PROGRESS_STAGES) or stage != READ_PROGRESS_STAGES[expected_index]:
        expected = READ_PROGRESS_STAGES[expected_index] if expected_index < len(READ_PROGRESS_STAGES) else "record-read"
        raise RunnerError(f"read progress is out of order; expected {expected}")
    recorded_at = utc_iso(now)
    events.append({"stage": stage, "recorded_at": recorded_at})
    permit["last_progress_at"] = recorded_at
    idle_deadline, absolute_deadline = permit_deadlines(permit, contract)
    permit["next_progress_required_by"] = utc_iso(idle_deadline)
    permit["absolute_expires_at"] = utc_iso(absolute_deadline)
    write_json(pacing_state_path(run_dir, args.slot), state)
    return {
        "deduplicated": False,
        "permit_id": permit["permit_id"],
        "stage": stage,
        "recorded_at": recorded_at,
        "next_progress_required_by": permit["next_progress_required_by"],
        "absolute_expires_at": permit["absolute_expires_at"],
    }


def check_read_session(
    args: argparse.Namespace,
    *,
    now_provider: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    now_provider = now_provider or current_utc
    now = now_provider()
    run_dir = RUNS / args.date
    state_path = pacing_state_path(run_dir, args.slot)
    if not state_path.exists():
        return {"status": "no_read_session", "browser_close_required": False}
    state = load_json(state_path)
    if (
        state.get("contract_id") != READ_PACING_CONTRACT_ID
        or int(state.get("account_slot", 0)) != args.slot
        or state.get("date") != args.date
    ):
        raise RunnerError("read pacing state identity does not match the requested session")
    outstanding = [
        item
        for item in state.get("permits", [])
        if not item.get("consumed_at") and not item.get("expired_at")
    ]
    if not outstanding:
        return {
            "status": "stopped" if state.get("resume_required") else "no_outstanding_permit",
            "browser_close_required": bool(state.get("resume_required")),
            "stop_reason": state.get("stop_reason"),
        }
    if len(outstanding) != 1:
        raise RunnerError("read pacing state has ambiguous outstanding permits")
    contract = active_read_contract()
    permit = outstanding[0]
    reason = permit_expiration_reason(
        permit, day_text=args.date, now=now, contract=contract
    )
    if reason:
        return mark_read_session_stopped(
            run_dir=run_dir,
            slot=args.slot,
            state=state,
            permit=permit,
            reason=reason,
            now=now,
        )
    idle_deadline, absolute_deadline = permit_deadlines(permit, contract)
    return {
        "status": "active",
        "permit_id": permit.get("permit_id"),
        "item_index": permit.get("item_index"),
        "next_progress_required_by": utc_iso(idle_deadline),
        "absolute_expires_at": utc_iso(absolute_deadline),
        "browser_close_required": False,
    }


def resume_read_session(
    args: argparse.Namespace,
    *,
    now_provider: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    now_provider = now_provider or current_utc
    now = now_provider()
    if not active_read_day_matches(args.date, now):
        raise RunnerError("an old-date read session cannot be resumed")
    if not (args.identity_verified and args.login_verified and args.risk_clear):
        raise RunnerError("resume requires identity, login, and risk reverification")
    run_dir = RUNS / args.date
    state_path = pacing_state_path(run_dir, args.slot)
    state = load_json(state_path)
    if not state.get("resume_required"):
        return {"deduplicated": True, "status": "active", "resume_required": False}
    resumed_at = utc_iso(now)
    state["resume_required"] = False
    state["stopped_at"] = None
    state["stop_reason"] = None
    state.setdefault("resume_events", []).append(
        {
            "resumed_at": resumed_at,
            "identity_verified": True,
            "login_verified": True,
            "risk_clear": True,
        }
    )
    write_json(state_path, state)
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    plan = load_json(plan_path)
    plan["status"] = "reading_in_progress" if int(plan.get("actual_deep_reads", 0) or 0) else "planned_not_started"
    plan["stop_reason"] = None
    write_json(plan_path, plan)
    status_path = run_dir / "five_account_daily_status.json"
    if status_path.exists():
        status = load_json(status_path)
        matches = [
            item
            for item in status.get("accounts", [])
            if int(item.get("account_slot", 0)) == args.slot
        ]
        if len(matches) == 1:
            matches[0]["status"] = plan["status"]
            matches[0]["stop_reason"] = None
            write_json(status_path, status)
    return {
        "deduplicated": False,
        "status": plan["status"],
        "resume_required": False,
        "resumed_at": resumed_at,
    }


def consume_read_pacing_permit(
    *,
    run_dir: Path,
    slot: int,
    permit_id: str,
    item_index: int,
    consumed_at: str,
) -> dict[str, Any]:
    state_path = pacing_state_path(run_dir, slot)
    state = load_json(state_path)
    matches = [
        item for item in state.get("permits", []) if item.get("permit_id") == permit_id
    ]
    if len(matches) != 1 or int(matches[0].get("item_index", 0)) != item_index:
        raise RunnerError("record-read requires the matching next-view pacing permit")
    permit = matches[0]
    if permit.get("consumed_at") and permit["consumed_at"] != consumed_at:
        raise RunnerError("read pacing permit was already consumed by another record")
    permit["consumed_at"] = consumed_at
    write_json(state_path, state)
    return permit


def update_status_from_plans(run_dir: Path) -> None:
    status_path = run_dir / "five_account_daily_status.json"
    status = load_json(status_path)
    planned = {"browse": 0, "deep_reads": 0, "comment_drafts_cap": 0, "follows": 0}
    verified = {
        "browse": 0,
        "deep_reads": 0,
        "comment_drafts": 0,
        "public_visible_comments": 0,
        "follows": 0,
    }
    states = []
    for account_status in status["accounts"]:
        slot = int(account_status["account_slot"])
        plan = load_json(run_dir / f"account_{slot}_daily_plan.json")
        planned_browse = int(plan.get("planned_browse_target", plan.get("planned_browse", 0)) or 0)
        planned_deep_reads = int(
            plan.get("planned_deep_read_target", plan.get("planned_deep_reads", planned_browse)) or 0
        )
        planned_comment_drafts = int(
            plan.get("planned_comment_draft_cap", plan.get("planned_comment_cap", 0)) or 0
        )
        planned_follows = int(plan.get("planned_follow_target", plan.get("planned_follows", 0)) or 0)
        account_status.update(
            {
                "cycle_day": int(plan.get("cycle_day", account_status.get("cycle_day", 0)) or 0),
                "planned_browse": planned_browse,
                "planned_comment_drafts": planned_comment_drafts,
                "planned_follows": planned_follows,
            }
        )
        planned["browse"] += planned_browse
        planned["deep_reads"] += planned_deep_reads
        planned["comment_drafts_cap"] += planned_comment_drafts
        planned["follows"] += planned_follows
        for key in (
            "status",
            "actual_browse",
            "actual_deep_reads",
            "drafts_ready",
            "public_visible_comments",
            "verified_follows",
            "stop_reason",
        ):
            account_status[key] = plan.get(key, account_status.get(key))
        for numeric_key in (
            "actual_browse",
            "actual_deep_reads",
            "drafts_ready",
            "public_visible_comments",
            "verified_follows",
        ):
            account_status[numeric_key] = int(account_status.get(numeric_key) or 0)
        verified["browse"] += int(plan.get("actual_browse", 0) or 0)
        verified["deep_reads"] += int(plan.get("actual_deep_reads", 0) or 0)
        verified["comment_drafts"] += int(plan.get("drafts_ready", 0) or 0)
        verified["public_visible_comments"] += int(plan.get("public_visible_comments", 0) or 0)
        verified["follows"] += int(plan.get("verified_follows", 0) or 0)
        states.append(plan["status"])
    status["totals_planned"] = planned
    status["totals_verified"] = verified
    if all(value.startswith("completed") for value in states):
        status["overall_status"] = "completed"
    elif any(value != "planned_not_started" for value in states):
        status["overall_status"] = "in_progress"
    write_json(status_path, status)
    manifest_path = run_dir / "warmup_run_manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        if manifest.get("totals_planned") != planned:
            manifest["plan_drift_detected"] = True
            manifest["original_totals_planned"] = manifest.get("totals_planned")
            manifest["active_totals_planned"] = planned
            manifest["status"] = "reconciled_with_existing_plan_files"
            manifest["reconciled_at"] = utc_now()
            write_json(manifest_path, manifest)


def migrate_unstarted_read_contract(args: argparse.Namespace) -> dict[str, Any]:
    """Incrementally migrate one same-day, never-started account plan only."""
    target_day = parse_day(args.date)
    run_dir = RUNS / args.date
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    plan = load_json(plan_path)
    contract = active_read_contract()
    new_target = deterministic_read_target(target_day, args.slot, load_json(COMMENT_POLICY))
    migration_id = f"{READ_VOLUME_POLICY_ID}:{args.date}:slot-{args.slot}"
    prior_migration = plan.get("read_contract_migration") or {}
    status_path = run_dir / "five_account_daily_status.json"
    manifest_path = run_dir / "warmup_run_manifest.json"
    status = load_json(status_path)
    manifest = load_json(manifest_path)
    status_migration = status.get("read_contract_migration") or {}
    manifest_migrations = manifest.get("read_contract_migrations") or []
    migration_everywhere = (
        prior_migration.get("migration_id") == migration_id
        and status_migration.get("migration_id") == migration_id
        and sum(
            item.get("migration_id") == migration_id for item in manifest_migrations
        ) == 1
    )
    if (
        plan.get("read_target_policy_id") == READ_VOLUME_POLICY_ID
        and plan.get("read_pacing_contract_id") == READ_PACING_CONTRACT_ID
        and int(plan.get("planned_browse_target", 0)) == new_target
        and int(plan.get("planned_deep_read_target", 0)) == new_target
        and migration_everywhere
    ):
        return {
            "deduplicated": True,
            "account_slot": args.slot,
            "planned_browse_target": new_target,
            "planned_deep_read_target": new_target,
        }
    if any(
        (
            prior_migration.get("migration_id") == migration_id,
            status_migration.get("migration_id") == migration_id,
            any(item.get("migration_id") == migration_id for item in manifest_migrations),
        )
    ):
        raise RunnerError("read-contract migration is partially applied and needs repair")
    zero_fields = (
        "actual_browse",
        "actual_deep_reads",
        "drafts_ready",
        "public_visible_comments",
        "follow_attempts",
        "verified_follows",
    )
    if any(int(plan.get(field, 0) or 0) != 0 for field in zero_fields):
        raise RunnerError("same-day read-contract migration requires a never-started plan")
    if plan.get("external_actions_performed") is not False:
        raise RunnerError("same-day read-contract migration refuses a plan with external actions")
    receipt_path = run_dir / f"account_{args.slot}_read_receipts.json"
    if receipt_path.exists() and load_json(receipt_path).get("items"):
        raise RunnerError("same-day read-contract migration refuses existing read evidence")
    old_browse = int(plan.get("planned_browse_target", 0) or 0)
    old_deep = int(plan.get("planned_deep_read_target", old_browse) or 0)
    migrated_at = utc_now()
    plan.update(
        {
            "schema_version": max(3, int(plan.get("schema_version", 0) or 0)),
            "browse_multiplier": None,
            "planned_browse_target": new_target,
            "planned_deep_read_target": new_target,
            **contract,
            "status": "planned_not_started",
            "stop_reason": None,
            "read_contract_migration": {
                "migration_id": migration_id,
                "status": "completed_verified",
                "migrated_at": migrated_at,
                "previous_planned_browse_target": old_browse,
                "previous_planned_deep_read_target": old_deep,
                "new_planned_browse_target": new_target,
                "new_planned_deep_read_target": new_target,
                "other_account_plans_modified": False,
            },
        }
    )

    matches = [
        item for item in status.get("accounts", []) if int(item.get("account_slot", 0)) == args.slot
    ]
    if len(matches) != 1:
        raise RunnerError("daily status does not contain one exact target account")
    account_status = matches[0]
    if any(
        int(account_status.get(field, 0) or 0) != 0
        for field in (
            "actual_browse",
            "actual_deep_reads",
            "drafts_ready",
            "public_visible_comments",
            "verified_follows",
        )
    ):
        raise RunnerError("daily status target account is no longer unstarted")
    if int(account_status.get("planned_browse", 0) or 0) != old_browse:
        raise RunnerError("daily status target plan does not match the migration source")
    totals = status.get("totals_planned") or {}
    if not isinstance(totals.get("browse"), int) or not isinstance(
        totals.get("deep_reads"), int
    ):
        raise RunnerError("daily status planned totals are missing")
    account_status.update(
        {
            "planned_browse": new_target,
            "planned_deep_reads": new_target,
            "read_target_policy_id": READ_VOLUME_POLICY_ID,
            "read_pacing_contract_id": READ_PACING_CONTRACT_ID,
            "status": "planned_not_started",
            "stop_reason": None,
        }
    )
    totals["browse"] += new_target - old_browse
    totals["deep_reads"] += new_target - old_deep
    status["read_contract_migration"] = {
        "migration_id": migration_id,
        "account_slot": args.slot,
        "status": "completed_verified",
        "planned_browse_delta": new_target - old_browse,
        "planned_deep_read_delta": new_target - old_deep,
        "other_account_entries_modified": False,
        "migrated_at": migrated_at,
    }

    active_totals = manifest.get("active_totals_planned")
    if not isinstance(active_totals, dict):
        active_totals = dict(manifest.get("totals_planned") or {})
    if not isinstance(active_totals.get("browse"), int) or not isinstance(
        active_totals.get("deep_reads"), int
    ):
        raise RunnerError("warmup manifest active totals are missing")
    active_totals["browse"] += new_target - old_browse
    active_totals["deep_reads"] += new_target - old_deep
    manifest["active_totals_planned"] = active_totals
    migrations = manifest.setdefault("read_contract_migrations", [])
    if any(item.get("migration_id") == migration_id for item in migrations):
        raise RunnerError("warmup manifest already contains a conflicting migration")
    migrations.append(
        {
            "migration_id": migration_id,
            "account_slot": args.slot,
            "status": "completed_verified",
            "previous_targets": {"browse": old_browse, "deep_reads": old_deep},
            "new_targets": {"browse": new_target, "deep_reads": new_target},
            "migrated_at": migrated_at,
        }
    )
    write_json(plan_path, plan)
    write_json(status_path, status)
    write_json(manifest_path, manifest)
    return {
        "deduplicated": False,
        "account_slot": args.slot,
        "previous_planned_browse_target": old_browse,
        "previous_planned_deep_read_target": old_deep,
        "planned_browse_target": new_target,
        "planned_deep_read_target": new_target,
        "other_account_plans_modified": False,
    }


def record_read(
    args: argparse.Namespace,
    *,
    now_provider: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    now_provider = now_provider or current_utc
    now = now_provider()
    run_dir = RUNS / args.date
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    plan = load_json(plan_path)
    contract = active_read_contract()
    if (
        plan.get("read_pacing_contract_id") != READ_PACING_CONTRACT_ID
        or plan.get("read_target_policy_id") != READ_VOLUME_POLICY_ID
        or any(plan.get(key) != contract[key] for key in contract)
    ):
        raise RunnerError("record-read requires the active read volume and pacing contract")
    if not args.body_read or not args.visible_comments_read:
        raise RunnerError("a deep read requires both --body-read and --visible-comments-read")
    other_seen = all_same_day_note_ids(run_dir, exclude_slot=args.slot)
    if args.note_id in other_seen:
        raise RunnerError("this note is already assigned to another controlled account today")
    receipt_path = run_dir / f"account_{args.slot}_read_receipts.json"
    receipt = load_json(receipt_path) if receipt_path.exists() else {
        "schema_version": 1,
        "date": args.date,
        "account_slot": args.slot,
        "items": [],
    }
    permit_id = str(getattr(args, "pacing_permit_id", "") or "")
    if not permit_id:
        raise RunnerError("record-read requires a next-view pacing permit")
    existing = next(
        (item for item in receipt["items"] if str(item.get("note_id")) == args.note_id),
        None,
    )
    if existing is not None:
        if existing.get("pacing_permit_id") != permit_id:
            raise RunnerError("deduplicated record-read must reuse its original pacing permit")
        consume_read_pacing_permit(
            run_dir=run_dir,
            slot=args.slot,
            permit_id=permit_id,
            item_index=int(existing["item_index"]),
            consumed_at=str(existing["verified_at"]),
        )
        return {"deduplicated": True, "note_id": args.note_id, "count": len(receipt["items"])}
    target = int(plan.get("planned_deep_read_target", 0) or 0)
    low, high = contract["daily_read_target_range"]
    if not low <= target <= high:
        raise RunnerError("daily deep-read target is outside the active 5-8 contract")
    if len(receipt["items"]) >= target:
        raise RunnerError("daily read target has already been reached")
    item_index = len(receipt["items"]) + 1
    _, permit = require_live_permit(
        run_dir=run_dir,
        slot=args.slot,
        permit_id=permit_id,
        item_index=item_index,
        now=now,
        contract=contract,
    )
    completed_stages = [
        str(item.get("stage")) for item in permit.get("progress_events", [])
    ]
    if completed_stages != list(READ_PROGRESS_STAGES):
        raise RunnerError(
            "record-read requires ordered opened, body_read, media_reviewed, and comments_read progress checkpoints"
        )
    verified_at = utc_iso(now)
    receipt["items"].append(
        {
            "item_index": item_index,
            "note_id": args.note_id,
            "title": args.title,
            "author": args.author,
            "source_locator": args.url,
            "summary": args.summary,
            "body_read": True,
            "visible_comments_read": True,
            "media_reviewed": args.media_reviewed,
            "comment_candidate": bool(args.comment_candidate),
            "read_pacing_contract_id": READ_PACING_CONTRACT_ID,
            "pacing_permit_id": permit_id,
            "verified_at": verified_at,
        }
    )
    receipt["browse_actual"] = len(receipt["items"])
    receipt["deep_read_actual"] = len(receipt["items"])
    write_json(receipt_path, receipt)
    consume_read_pacing_permit(
        run_dir=run_dir,
        slot=args.slot,
        permit_id=permit_id,
        item_index=item_index,
        consumed_at=verified_at,
    )
    plan["actual_browse"] = len(receipt["items"])
    plan["actual_deep_reads"] = len(receipt["items"])
    plan["external_actions_performed"] = True
    plan["status"] = "reading_in_progress"
    write_json(plan_path, plan)
    update_status_from_plans(run_dir)
    return {"deduplicated": False, "note_id": args.note_id, "count": len(receipt["items"])}


def record_follow(args: argparse.Namespace) -> dict[str, Any]:
    if args.slot == 1:
        raise RunnerError("slot 1 follows are disabled by policy")
    run_dir = RUNS / args.date
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    plan = load_json(plan_path)
    notes = list(dict.fromkeys(args.note_id))
    verified = (
        len(notes) >= 2
        and args.state_before == "关注"
        and args.state_after == "已关注"
        and args.profile_consistent
    )
    receipt_path = run_dir / f"account_{args.slot}_follow_receipts.json"
    receipt = load_json(receipt_path) if receipt_path.exists() else {
        "schema_version": 1,
        "date": args.date,
        "account_slot": args.slot,
        "items": [],
    }
    if any(str(item.get("profile_id")) == args.profile_id for item in receipt["items"]):
        return {"deduplicated": True, "profile_id": args.profile_id, "verified": False}
    item = {
        "profile_id": args.profile_id,
        "nickname": args.nickname,
        "role_fit_reason": args.role_fit_reason,
        "notes_read": notes,
        "follow_state_before": args.state_before,
        "follow_state_after": args.state_after,
        "profile_and_content_consistent": bool(args.profile_consistent),
        "verified": verified,
        "verified_at": utc_now(),
    }
    if not verified:
        item["stop_reason"] = "follow requirements or exact button-state readback were not satisfied"
    receipt["items"].append(item)
    receipt["follow_attempts"] = len(receipt["items"])
    receipt["verified_follow_count"] = sum(bool(value.get("verified")) for value in receipt["items"])
    write_json(receipt_path, receipt)
    plan["follow_attempts"] = receipt["follow_attempts"]
    plan["verified_follows"] = receipt["verified_follow_count"]
    plan["external_actions_performed"] = True
    if not verified:
        plan["stop_reason"] = item["stop_reason"]
    write_json(plan_path, plan)
    update_status_from_plans(run_dir)
    return {"deduplicated": False, "profile_id": args.profile_id, "verified": verified}


def record_stop(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = RUNS / args.date
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    plan = load_json(plan_path)
    stop_path = run_dir / f"account_{args.slot}_stop_receipt.json"
    if stop_path.exists():
        receipt = load_json(stop_path)
        update_status_from_plans(run_dir)
        return {"deduplicated": True, **receipt}
    receipt = {
        "schema_version": 1,
        "date": args.date,
        "account_slot": args.slot,
        "signal": args.signal,
        "reason": args.reason,
        "external_interaction_after_signal": False,
        "other_account_bypass_performed": False,
        "user_action_required": args.user_action_required,
        "stopped_at": utc_now(),
    }
    write_json(stop_path, receipt)
    plan["status"] = "blocked_waiting_user_security_confirmation"
    plan["stop_reason"] = f"{args.signal}: {args.reason}"
    write_json(plan_path, plan)
    update_status_from_plans(run_dir)
    return {"deduplicated": False, **receipt}


def resolve_stop(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = RUNS / args.date
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    stop_path = run_dir / f"account_{args.slot}_stop_receipt.json"
    if not stop_path.exists():
        raise RunnerError("no recorded stop exists for this account and date")
    receipt = load_json(stop_path)
    if receipt.get("resolved_at"):
        update_status_from_plans(run_dir)
        return {"deduplicated": True, **receipt}
    receipt.update(
        {
            "resolved": True,
            "resolved_by": "user",
            "resolution": args.resolution,
            "resolved_at": utc_now(),
        }
    )
    write_json(stop_path, receipt)
    plan = load_json(plan_path)
    plan["status"] = "queued"
    plan["stop_reason"] = None
    if isinstance(plan.get("login_gate"), dict):
        plan["login_gate"]["resolved"] = True
        plan["login_gate"]["resolved_at"] = receipt["resolved_at"]
    write_json(plan_path, plan)
    update_status_from_plans(run_dir)
    return {"deduplicated": False, **receipt}


def record_review_queue(args: argparse.Namespace) -> dict[str, Any]:
    queue_path = Path(args.file).resolve()
    queue = load_json(queue_path)
    if queue.get("date") != args.date or int(queue.get("account_slot", 0)) != args.slot:
        raise RunnerError("review queue date or account slot does not match the command")
    items = queue.get("items")
    if not isinstance(items, list) or not items:
        raise RunnerError("review queue must contain at least one item")
    for item in items:
        if item.get("published") is not False:
            raise RunnerError("every review item must be explicitly unpublished")
        if not item.get("exact_draft_text"):
            raise RunnerError("every review item must contain exact_draft_text")
        item["current_user_approval_required"] = False
    run_dir = RUNS / args.date
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    plan = load_json(plan_path)
    cap = int(plan.get("planned_comment_draft_cap", plan.get("planned_comment_cap", 0)) or 0)
    if len(items) > cap:
        raise RunnerError(f"review queue has {len(items)} items but the daily cap is {cap}")
    model_verified = bool(queue.get("required_generation_model_verified"))
    queue["registered_at"] = utc_now()
    queue["send_allowed"] = model_verified
    queue["published_count"] = 0
    write_json(queue_path, queue)
    plan["drafts_ready"] = len(items) if model_verified else 0
    plan["draft_candidates_ready"] = len(items)
    plan["public_visible_comments"] = int(plan.get("public_visible_comments", 0) or 0)
    plan["comments_require_current_user_approval"] = False
    plan["comment_send_allowed"] = model_verified
    plan["status"] = (
        "ready_for_platform_submission"
        if model_verified
        else "reading_completed_awaiting_required_model_generation"
    )
    write_json(plan_path, plan)
    update_status_from_plans(run_dir)
    return {
        "queue": str(queue_path),
        "items": len(items),
        "required_generation_model_verified": model_verified,
        "send_allowed": model_verified,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="create an idempotent five-account daily plan")
    plan.add_argument("--date", required=True)

    migrate = sub.add_parser(
        "migrate-read-contract",
        help="migrate one never-started same-day plan to the active read contract",
    )
    migrate.add_argument("--date", required=True)
    migrate.add_argument("--slot", type=int, choices=range(1, 6), required=True)

    pace = sub.add_parser(
        "pace-next-read",
        help="wait for the governed adjacent-view interval and issue one permit",
    )
    pace.add_argument("--date", required=True)
    pace.add_argument("--slot", type=int, choices=range(1, 6), required=True)

    progress = sub.add_parser(
        "touch-read-progress",
        help="record one ordered meaningful progress checkpoint for a live permit",
    )
    progress.add_argument("--date", required=True)
    progress.add_argument("--slot", type=int, choices=range(1, 6), required=True)
    progress.add_argument("--pacing-permit-id", required=True)
    progress.add_argument("--stage", choices=READ_PROGRESS_STAGES, required=True)

    check = sub.add_parser(
        "check-read-session",
        help="expire a stale or cross-date permit and emit a stop receipt",
    )
    check.add_argument("--date", required=True)
    check.add_argument("--slot", type=int, choices=range(1, 6), required=True)

    resume = sub.add_parser(
        "resume-read-session",
        help="resume a same-day stopped read session after full reverification",
    )
    resume.add_argument("--date", required=True)
    resume.add_argument("--slot", type=int, choices=range(1, 6), required=True)
    resume.add_argument("--identity-verified", action="store_true")
    resume.add_argument("--login-verified", action="store_true")
    resume.add_argument("--risk-clear", action="store_true")

    read = sub.add_parser("record-read", help="record one verified deep read")
    read.add_argument("--date", required=True)
    read.add_argument("--slot", type=int, choices=range(1, 6), required=True)
    read.add_argument("--note-id", required=True)
    read.add_argument("--title", required=True)
    read.add_argument("--author", required=True)
    read.add_argument("--url", required=True)
    read.add_argument("--summary", required=True)
    read.add_argument("--media-reviewed", required=True)
    read.add_argument("--body-read", action="store_true")
    read.add_argument("--visible-comments-read", action="store_true")
    read.add_argument("--comment-candidate", action="store_true")
    read.add_argument("--pacing-permit-id", required=True)

    follow = sub.add_parser("record-follow", help="record one follow attempt and readback")
    follow.add_argument("--date", required=True)
    follow.add_argument("--slot", type=int, choices=range(1, 6), required=True)
    follow.add_argument("--profile-id", required=True)
    follow.add_argument("--nickname", required=True)
    follow.add_argument("--role-fit-reason", required=True)
    follow.add_argument("--note-id", action="append", required=True)
    follow.add_argument("--state-before", required=True)
    follow.add_argument("--state-after", required=True)
    follow.add_argument("--profile-consistent", action="store_true")
    stop = sub.add_parser("record-stop", help="record a safety stop without bypassing it")
    stop.add_argument("--date", required=True)
    stop.add_argument("--slot", type=int, choices=range(1, 6), required=True)
    stop.add_argument(
        "--signal",
        choices=["captcha", "security", "frequency", "account_risk", "identity_mismatch", "login_required"],
        required=True,
    )
    stop.add_argument("--reason", required=True)
    stop.add_argument("--user-action-required", required=True)
    resume = sub.add_parser("resolve-stop", help="mark a previously recorded safety stop as user-resolved")
    resume.add_argument("--date", required=True)
    resume.add_argument("--slot", type=int, choices=range(1, 6), required=True)
    resume.add_argument("--resolution", required=True)
    review = sub.add_parser("record-review-queue", help="register an unpublished review queue")
    review.add_argument("--date", required=True)
    review.add_argument("--slot", type=int, choices=range(1, 6), required=True)
    review.add_argument("--file", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = plan_day(args.date)
        elif args.command == "migrate-read-contract":
            result = migrate_unstarted_read_contract(args)
        elif args.command == "pace-next-read":
            result = issue_read_pacing_permit(args)
        elif args.command == "touch-read-progress":
            result = touch_read_progress(args)
        elif args.command == "check-read-session":
            result = check_read_session(args)
        elif args.command == "resume-read-session":
            result = resume_read_session(args)
        elif args.command == "record-read":
            result = record_read(args)
        elif args.command == "record-follow":
            result = record_follow(args)
        elif args.command == "record-stop":
            result = record_stop(args)
        elif args.command == "resolve-stop":
            result = resolve_stop(args)
        else:
            result = record_review_queue(args)
    except RunnerError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
