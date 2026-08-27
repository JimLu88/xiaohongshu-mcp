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
import math
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / "research" / "panse_multi_direction"
RUNS = ROOT / "daily_runs"
BINDING = ROOT / "account_role_binding_v1.json"
SCOPE = ROOT / "five_account_daily_scope_v1.json"
COMMENT_POLICY = ROOT / "comment_warmup_policy_v2.json"
FOLLOW_POLICY = ROOT / "follow_warmup_policy_v1.json"


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


def day_five_to_fifteen_browse_bounds(cycle_day: int) -> tuple[int, int] | None:
    if cycle_day in (5, 6):
        return 8, 15
    if cycle_day == 7:
        return 8, 18
    if cycle_day in (8, 9):
        return 12, 20
    if cycle_day in (10, 11, 12, 13):
        return 12, 24
    if cycle_day == 14:
        return 16, 30
    if cycle_day == 15:
        return 12, 20
    return None


def planned_targets(
    day: date,
    slot: int,
    cycle_day: int,
    comment_phase: dict[str, Any],
    follow_phase: dict[str, Any] | None,
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

    multipliers = [float(value) for value in load_json(COMMENT_POLICY)["daily_target_selection"]["browse_multiplier_values"]]
    multiplier = rng.choice(multipliers)
    formula_target = math.ceil(comment_cap * multiplier)
    bounds = day_five_to_fifteen_browse_bounds(cycle_day)
    if bounds:
        browse_target = max(bounds[0], min(bounds[1], formula_target))
    else:
        allowed_low, allowed_high = comment_phase["daily_browse_range_possible"]
        browse_target = max(allowed_low, min(allowed_high, formula_target))

    follow_target = 0
    if follow_phase is not None:
        follow_low, follow_high = follow_phase["daily_range"]
        if 5 <= cycle_day <= 15:
            follow_high = min(1, follow_high)
        follow_target = rng.randint(follow_low, follow_high)

    return {
        "planned_comment_draft_cap": comment_cap,
        "browse_multiplier": multiplier,
        "planned_browse_target": browse_target,
        "planned_deep_read_target": browse_target,
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
        targets = planned_targets(target_day, slot, cycle_day, comment_phase, follow_phase)
        plan = {
            "schema_version": 2,
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
            "comments_require_current_user_approval": True,
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
        "comment_gate": "draft_and_wait_for_current_user_review",
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
        "comment_gate": "draft_and_wait_for_current_user_review",
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


def record_read(args: argparse.Namespace) -> dict[str, Any]:
    run_dir = RUNS / args.date
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    plan = load_json(plan_path)
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
    if any(str(item.get("note_id")) == args.note_id for item in receipt["items"]):
        return {"deduplicated": True, "note_id": args.note_id, "count": len(receipt["items"])}
    receipt["items"].append(
        {
            "note_id": args.note_id,
            "title": args.title,
            "author": args.author,
            "source_locator": args.url,
            "summary": args.summary,
            "body_read": True,
            "visible_comments_read": True,
            "media_reviewed": args.media_reviewed,
            "comment_candidate": bool(args.comment_candidate),
            "verified_at": utc_now(),
        }
    )
    receipt["browse_actual"] = len(receipt["items"])
    receipt["deep_read_actual"] = len(receipt["items"])
    write_json(receipt_path, receipt)
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
        if item.get("current_user_approval_required") is not True:
            raise RunnerError("every review item must require current user approval")
        if not item.get("exact_draft_text"):
            raise RunnerError("every review item must contain exact_draft_text")
    run_dir = RUNS / args.date
    plan_path = run_dir / f"account_{args.slot}_daily_plan.json"
    plan = load_json(plan_path)
    cap = int(plan.get("planned_comment_draft_cap", plan.get("planned_comment_cap", 0)) or 0)
    if len(items) > cap:
        raise RunnerError(f"review queue has {len(items)} items but the daily cap is {cap}")
    model_verified = bool(queue.get("required_generation_model_verified"))
    queue["registered_at"] = utc_now()
    queue["send_allowed"] = False
    queue["published_count"] = 0
    write_json(queue_path, queue)
    plan["drafts_ready"] = len(items) if model_verified else 0
    plan["draft_candidates_ready"] = len(items)
    plan["public_visible_comments"] = int(plan.get("public_visible_comments", 0) or 0)
    plan["comment_send_allowed"] = False
    plan["status"] = (
        "awaiting_current_user_review"
        if model_verified
        else "reading_completed_awaiting_required_model_generation"
    )
    write_json(plan_path, plan)
    update_status_from_plans(run_dir)
    return {
        "queue": str(queue_path),
        "items": len(items),
        "required_generation_model_verified": model_verified,
        "send_allowed": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="create an idempotent five-account daily plan")
    plan.add_argument("--date", required=True)

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
