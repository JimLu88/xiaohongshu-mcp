#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).with_name("xhs_warmup_runner.py")
SPEC = importlib.util.spec_from_file_location("xhs_warmup_runner", SCRIPT)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class WarmupRunnerTests(unittest.TestCase):
    def test_day_five_plan_is_idempotent_and_in_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                prior = runner.RUNS / "2026-08-12"
                prior.mkdir()
                for slot in range(1, 6):
                    (prior / f"account_{slot}_daily_plan.json").write_text(
                        json.dumps({"account_slot": slot, "cycle_day": 4}), encoding="utf-8"
                    )
                first = runner.plan_day("2026-08-13")
                second = runner.plan_day("2026-08-13")
                self.assertEqual(first["cycle_days"], {str(slot): 5 for slot in range(1, 6)})
                self.assertFalse(first["deduplicated"])
                self.assertTrue(second["deduplicated"])
                for slot in range(1, 6):
                    plan = runner.load_json(runner.RUNS / "2026-08-13" / f"account_{slot}_daily_plan.json")
                    self.assertGreaterEqual(plan["planned_browse_target"], 5)
                    self.assertLessEqual(plan["planned_browse_target"], 8)
                    self.assertEqual(
                        plan["planned_deep_read_target"],
                        plan["planned_browse_target"],
                    )
                    self.assertEqual(
                        plan["read_target_policy_id"],
                        "panse-xhs-daily-read-volume.v1",
                    )
                    self.assertEqual(
                        plan["read_pacing_contract_id"],
                        "panse-xhs-adjacent-view-pacing.v1",
                    )
                    self.assertEqual(plan["minimum_interval_seconds"], 30)
                    self.assertEqual(plan["maximum_interval_seconds"], 45)
                    self.assertEqual(plan["progress_heartbeat_seconds"], 300)
                    self.assertEqual(plan["permit_idle_timeout_seconds"], 600)
                    self.assertEqual(plan["permit_absolute_timeout_seconds"], 1800)
                    self.assertTrue(plan["same_local_date_required"])
                    self.assertTrue(plan["expired_permit_requires_explicit_resume"])
                    self.assertEqual(plan["planned_comment_draft_cap"], 4)
                    self.assertEqual(plan["planned_follow_target"], 0 if slot == 1 else plan["planned_follow_target"])
                    self.assertFalse(plan["comments_require_current_user_approval"])
                    self.assertTrue(plan["comment_submission_required_after_all_gates"])
                    self.assertFalse(plan["comment_send_allowed"])
            finally:
                runner.RUNS = original

    def test_all_slots_and_cycle_phases_stay_within_five_to_eight_reads(self) -> None:
        policy = runner.load_json(runner.COMMENT_POLICY)
        follow_policy = runner.load_json(runner.FOLLOW_POLICY)
        self.assertTrue(
            all(
                phase["daily_browse_range_possible"] == [5, 8]
                for phase in policy["weekly_phases"]
            )
        )
        for cycle_day in range(1, 29):
            comment_phase = runner.phase_for_day(policy, cycle_day)
            for slot in range(1, 6):
                follow_phase = (
                    runner.phase_for_day(follow_policy, cycle_day)
                    if slot in follow_policy["applies_to_account_slots"]
                    else None
                )
                targets = runner.planned_targets(
                    runner.parse_day("2026-09-01"),
                    slot,
                    cycle_day,
                    comment_phase,
                    follow_phase,
                    policy,
                )
                self.assertGreaterEqual(targets["planned_browse_target"], 5)
                self.assertLessEqual(targets["planned_browse_target"], 8)
                self.assertEqual(
                    targets["planned_deep_read_target"],
                    targets["planned_browse_target"],
                )

    def test_pacing_entry_waits_and_record_read_consumes_each_permit(self) -> None:
        class FakeClock:
            def __init__(self) -> None:
                self.value = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)
                self.sleeps: list[float] = []

            def now(self) -> datetime:
                return self.value

            def sleep(self, seconds: float) -> None:
                self.sleeps.append(seconds)
                self.value += timedelta(seconds=seconds)

        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-31")
                clock = FakeClock()
                pace_args = type("Args", (), {"date": "2026-08-31", "slot": 3})()
                first = runner.issue_read_pacing_permit(
                    pace_args,
                    now_provider=clock.now,
                    sleep_func=clock.sleep,
                )
                self.assertEqual(first["item_index"], 1)
                self.assertEqual(first["required_interval_seconds"], 0)
                self.assertEqual(clock.sleeps, [])
                for stage in runner.READ_PROGRESS_STAGES:
                    runner.touch_read_progress(
                        type(
                            "ProgressArgs",
                            (),
                            {
                                "date": "2026-08-31",
                                "slot": 3,
                                "pacing_permit_id": first["permit_id"],
                                "stage": stage,
                            },
                        )(),
                        now_provider=clock.now,
                    )
                read_args = type(
                    "Args",
                    (),
                    {
                        "date": "2026-08-31",
                        "slot": 3,
                        "note_id": "note-1",
                        "title": "title",
                        "author": "author",
                        "url": "https://www.xiaohongshu.com/explore/note-1",
                        "summary": "summary",
                        "media_reviewed": "one image",
                        "body_read": True,
                        "visible_comments_read": True,
                        "comment_candidate": False,
                        "pacing_permit_id": first["permit_id"],
                    },
                )()
                runner.record_read(read_args, now_provider=clock.now)
                second = runner.issue_read_pacing_permit(
                    pace_args,
                    now_provider=clock.now,
                    sleep_func=clock.sleep,
                )
                self.assertEqual(second["item_index"], 2)
                self.assertGreaterEqual(second["required_interval_seconds"], 30)
                self.assertLessEqual(second["required_interval_seconds"], 45)
                self.assertEqual(clock.sleeps, [second["required_interval_seconds"]])
                state = runner.load_json(
                    runner.RUNS
                    / "2026-08-31"
                    / "account_3_read_pacing_state.json"
                )
                self.assertIsNotNone(state["permits"][0]["consumed_at"])
                self.assertIsNone(state["permits"][1]["consumed_at"])
            finally:
                runner.RUNS = original

    def test_record_read_fails_without_a_pacing_permit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-31")
                args = type(
                    "Args",
                    (),
                    {
                        "date": "2026-08-31",
                        "slot": 3,
                        "note_id": "note-1",
                        "title": "title",
                        "author": "author",
                        "url": "https://www.xiaohongshu.com/explore/note-1",
                        "summary": "summary",
                        "media_reviewed": "one image",
                        "body_read": True,
                        "visible_comments_read": True,
                        "comment_candidate": False,
                        "pacing_permit_id": "",
                    },
                )()
                with self.assertRaisesRegex(runner.RunnerError, "pacing permit"):
                    runner.record_read(args)
            finally:
                runner.RUNS = original

    def test_cli_pacing_entry_is_consumed_by_record_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-31")
                fixed_now = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)
                with mock.patch.object(runner, "current_utc", return_value=fixed_now):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = runner.main(
                            [
                                "pace-next-read",
                                "--date",
                                "2026-08-31",
                                "--slot",
                                "3",
                            ]
                        )
                    self.assertEqual(exit_code, 0)
                    permit = json.loads(output.getvalue())
                    self.assertEqual(permit["item_index"], 1)
                    for stage in runner.READ_PROGRESS_STAGES:
                        output = io.StringIO()
                        with redirect_stdout(output):
                            exit_code = runner.main(
                                [
                                    "touch-read-progress",
                                    "--date",
                                    "2026-08-31",
                                    "--slot",
                                    "3",
                                    "--pacing-permit-id",
                                    permit["permit_id"],
                                    "--stage",
                                    stage,
                                ]
                            )
                        self.assertEqual(exit_code, 0)
                    output = io.StringIO()
                    with redirect_stdout(output):
                        exit_code = runner.main(
                            [
                                "record-read",
                                "--date",
                                "2026-08-31",
                                "--slot",
                                "3",
                                "--note-id",
                                "note-cli-1",
                                "--title",
                                "title",
                                "--author",
                                "author",
                                "--url",
                                "https://www.xiaohongshu.com/explore/note-cli-1",
                                "--summary",
                                "summary",
                                "--media-reviewed",
                                "one image",
                                "--body-read",
                                "--visible-comments-read",
                                "--pacing-permit-id",
                                permit["permit_id"],
                            ]
                        )
                self.assertEqual(exit_code, 0)
                result = json.loads(output.getvalue())
                self.assertEqual(result["count"], 1)
                receipt = runner.load_json(
                    runner.RUNS / "2026-08-31" / "account_3_read_receipts.json"
                )
                self.assertEqual(
                    receipt["items"][0]["pacing_permit_id"], permit["permit_id"]
                )
            finally:
                runner.RUNS = original

    def test_read_contract_rejects_volume_or_interval_drift(self) -> None:
        policy = runner.load_json(runner.COMMENT_POLICY)
        policy["weekly_phases"][2]["daily_browse_range_possible"] = [8, 45]
        with self.assertRaisesRegex(runner.RunnerError, "every cycle phase"):
            runner.active_read_contract(policy)
        policy = runner.load_json(runner.COMMENT_POLICY)
        policy["reading_protocol"]["adjacent_view_pacing"][
            "minimum_interval_seconds"
        ] = 29
        with self.assertRaisesRegex(runner.RunnerError, "30-45"):
            runner.active_read_contract(policy)

    def test_stale_permit_stops_session_and_requires_explicit_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-31")
                issued = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)
                args = type("Args", (), {"date": "2026-08-31", "slot": 3})()
                permit = runner.issue_read_pacing_permit(
                    args, now_provider=lambda: issued, sleep_func=lambda _: None
                )
                stopped = runner.check_read_session(
                    args, now_provider=lambda: issued + timedelta(minutes=11)
                )
                self.assertEqual(stopped["status"], "stopped_no_progress")
                self.assertEqual(stopped["stop_reason"], "no_progress_timeout")
                self.assertTrue(stopped["browser_close_required"])
                state = runner.load_json(
                    runner.RUNS / "2026-08-31" / "account_3_read_pacing_state.json"
                )
                self.assertTrue(state["resume_required"])
                self.assertEqual(state["permits"][0]["permit_id"], permit["permit_id"])
                self.assertEqual(
                    state["permits"][0]["expiration_reason"], "no_progress_timeout"
                )
                with self.assertRaisesRegex(runner.RunnerError, "explicit resume"):
                    runner.issue_read_pacing_permit(
                        args,
                        now_provider=lambda: issued + timedelta(minutes=12),
                        sleep_func=lambda _: None,
                    )
                resume_args = type(
                    "ResumeArgs",
                    (),
                    {
                        "date": "2026-08-31",
                        "slot": 3,
                        "identity_verified": True,
                        "login_verified": True,
                        "risk_clear": True,
                    },
                )()
                resumed = runner.resume_read_session(
                    resume_args, now_provider=lambda: issued + timedelta(minutes=12)
                )
                self.assertFalse(resumed["resume_required"])
                replacement = runner.issue_read_pacing_permit(
                    args,
                    now_provider=lambda: issued + timedelta(minutes=12),
                    sleep_func=lambda _: None,
                )
                self.assertNotEqual(replacement["permit_id"], permit["permit_id"])
            finally:
                runner.RUNS = original

    def test_date_boundary_expires_permit_and_old_date_cannot_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-31")
                issued = datetime(2026, 8, 31, 15, 58, tzinfo=timezone.utc)
                args = type("Args", (), {"date": "2026-08-31", "slot": 3})()
                runner.issue_read_pacing_permit(
                    args, now_provider=lambda: issued, sleep_func=lambda _: None
                )
                stopped = runner.check_read_session(
                    args, now_provider=lambda: issued + timedelta(minutes=3)
                )
                self.assertEqual(stopped["stop_reason"], "date_boundary")
                resume_args = type(
                    "ResumeArgs",
                    (),
                    {
                        "date": "2026-08-31",
                        "slot": 3,
                        "identity_verified": True,
                        "login_verified": True,
                        "risk_clear": True,
                    },
                )()
                with self.assertRaisesRegex(runner.RunnerError, "old-date"):
                    runner.resume_read_session(
                        resume_args, now_provider=lambda: issued + timedelta(minutes=3)
                    )
            finally:
                runner.RUNS = original

    def test_progress_must_be_meaningful_and_ordered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-31")
                now = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)
                pace_args = type("Args", (), {"date": "2026-08-31", "slot": 3})()
                permit = runner.issue_read_pacing_permit(
                    pace_args, now_provider=lambda: now, sleep_func=lambda _: None
                )
                bad = type(
                    "ProgressArgs",
                    (),
                    {
                        "date": "2026-08-31",
                        "slot": 3,
                        "pacing_permit_id": permit["permit_id"],
                        "stage": "body_read",
                    },
                )()
                with self.assertRaisesRegex(runner.RunnerError, "expected opened"):
                    runner.touch_read_progress(bad, now_provider=lambda: now)
            finally:
                runner.RUNS = original

    def test_meaningful_progress_cannot_extend_the_absolute_item_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-31")
                issued = datetime(2026, 8, 31, 8, 0, tzinfo=timezone.utc)
                pace_args = type("Args", (), {"date": "2026-08-31", "slot": 3})()
                permit = runner.issue_read_pacing_permit(
                    pace_args, now_provider=lambda: issued, sleep_func=lambda _: None
                )
                for stage, minutes in zip(
                    ("opened", "body_read", "media_reviewed"), (9, 18, 27)
                ):
                    progress = type(
                        "ProgressArgs",
                        (),
                        {
                            "date": "2026-08-31",
                            "slot": 3,
                            "pacing_permit_id": permit["permit_id"],
                            "stage": stage,
                        },
                    )()
                    runner.touch_read_progress(
                        progress,
                        now_provider=lambda minutes=minutes: issued
                        + timedelta(minutes=minutes),
                    )
                stopped = runner.check_read_session(
                    pace_args, now_provider=lambda: issued + timedelta(minutes=30)
                )
                self.assertEqual(stopped["stop_reason"], "absolute_timeout")
            finally:
                runner.RUNS = original

    def test_same_day_migration_changes_only_unstarted_slot_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-31")
                run_dir = runner.RUNS / "2026-08-31"
                slot_3_path = run_dir / "account_3_daily_plan.json"
                slot_3 = runner.load_json(slot_3_path)
                generated_target = slot_3["planned_browse_target"]
                for key in (
                    "read_target_policy_id",
                    "daily_read_target_range",
                    "read_pacing_contract_id",
                    "minimum_interval_seconds",
                    "maximum_interval_seconds",
                    "interval_basis",
                    "permit_entrypoint",
                    "record_read_requires_matching_unconsumed_permit",
                ):
                    slot_3.pop(key, None)
                slot_3.update(
                    {
                        "schema_version": 2,
                        "browse_multiplier": 3.0,
                        "planned_browse_target": 45,
                        "planned_deep_read_target": 45,
                        "status": "blocked_program_repair",
                        "stop_reason": "waiting for repair",
                    }
                )
                runner.write_json(slot_3_path, slot_3)
                status_path = run_dir / "five_account_daily_status.json"
                status = runner.load_json(status_path)
                status_3 = next(
                    item for item in status["accounts"] if item["account_slot"] == 3
                )
                status_3["planned_browse"] = 45
                status["totals_planned"]["browse"] += 45 - generated_target
                status["totals_planned"]["deep_reads"] += 45 - generated_target
                runner.write_json(status_path, status)
                manifest_path = run_dir / "warmup_run_manifest.json"
                manifest = runner.load_json(manifest_path)
                manifest["active_totals_planned"] = dict(manifest["totals_planned"])
                manifest["active_totals_planned"]["browse"] += 45 - generated_target
                manifest["active_totals_planned"]["deep_reads"] += 45 - generated_target
                runner.write_json(manifest_path, manifest)
                slot_2_path = run_dir / "account_2_daily_plan.json"
                slot_2_before = slot_2_path.read_bytes()
                args = type("Args", (), {"date": "2026-08-31", "slot": 3})()
                first = runner.migrate_unstarted_read_contract(args)
                second = runner.migrate_unstarted_read_contract(args)
                self.assertFalse(first["deduplicated"])
                self.assertTrue(second["deduplicated"])
                self.assertGreaterEqual(first["planned_browse_target"], 5)
                self.assertLessEqual(first["planned_browse_target"], 8)
                self.assertEqual(slot_2_path.read_bytes(), slot_2_before)
                migrated = runner.load_json(slot_3_path)
                self.assertEqual(migrated["status"], "planned_not_started")
                self.assertEqual(
                    migrated["read_contract_migration"]["status"],
                    "completed_verified",
                )
                migrated_status = runner.load_json(status_path)
                migrated_status_3 = next(
                    item
                    for item in migrated_status["accounts"]
                    if item["account_slot"] == 3
                )
                self.assertEqual(
                    migrated_status_3["planned_browse"],
                    first["planned_browse_target"],
                )
                self.assertEqual(
                    migrated_status["totals_verified"], status["totals_verified"]
                )
            finally:
                runner.RUNS = original

    def test_follow_verification_requires_two_notes_and_exact_readback(self) -> None:
        args = type("Args", (), {
            "date": "2026-08-13", "slot": 2, "profile_id": "p1", "nickname": "n",
            "role_fit_reason": "fit", "note_id": ["one"], "state_before": "关注",
            "state_after": "已关注", "profile_consistent": True,
        })()
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-13")
                result = runner.record_follow(args)
                self.assertFalse(result["verified"])
            finally:
                runner.RUNS = original

    def test_stop_receipt_is_idempotent(self) -> None:
        args = type("Args", (), {
            "date": "2026-08-13", "slot": 1, "signal": "captcha",
            "reason": "image challenge displayed", "user_action_required": "complete challenge",
        })()
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-13")
                first = runner.record_stop(args)
                second = runner.record_stop(args)
                self.assertFalse(first["deduplicated"])
                self.assertTrue(second["deduplicated"])
                plan = runner.load_json(runner.RUNS / "2026-08-13" / "account_1_daily_plan.json")
                self.assertEqual(plan["status"], "blocked_waiting_user_security_confirmation")
            finally:
                runner.RUNS = original

    def test_old_plan_field_names_are_reconciled_without_nulls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-13")
                run_dir = runner.RUNS / "2026-08-13"
                old_plan = {
                    "schema_version": 1, "date": "2026-08-13", "account_slot": 2,
                    "cycle_day": 5, "planned_comment_cap": 6, "planned_browse_target": 14,
                    "planned_deep_reads": 14, "planned_follow_target": 1, "status": "queued",
                }
                runner.write_json(run_dir / "account_2_daily_plan.json", old_plan)
                runner.update_status_from_plans(run_dir)
                status = runner.load_json(run_dir / "five_account_daily_status.json")
                slot_2 = next(item for item in status["accounts"] if item["account_slot"] == 2)
                self.assertEqual(slot_2["planned_comment_drafts"], 6)
                self.assertEqual(slot_2["actual_browse"], 0)
                manifest = runner.load_json(run_dir / "warmup_run_manifest.json")
                self.assertTrue(manifest["plan_drift_detected"])
            finally:
                runner.RUNS = original

    def test_user_can_resolve_a_recorded_stop_without_deleting_history(self) -> None:
        stop_args = type("Args", (), {
            "date": "2026-08-13", "slot": 1, "signal": "captcha",
            "reason": "image challenge displayed", "user_action_required": "complete challenge",
        })()
        resume_args = type("Args", (), {
            "date": "2026-08-13", "slot": 1, "resolution": "user completed challenge",
        })()
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-13")
                runner.record_stop(stop_args)
                result = runner.resolve_stop(resume_args)
                self.assertTrue(result["resolved"])
                plan = runner.load_json(runner.RUNS / "2026-08-13" / "account_1_daily_plan.json")
                self.assertEqual(plan["status"], "queued")
                self.assertIsNone(plan["stop_reason"])
            finally:
                runner.RUNS = original

    def test_unverified_model_queue_stays_unsendable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-13")
                queue_path = runner.RUNS / "2026-08-13" / "account_1_candidate_queue.json"
                runner.write_json(queue_path, {
                    "date": "2026-08-13", "account_slot": 1,
                    "required_generation_model_verified": False,
                    "items": [{"exact_draft_text": "候选稿", "published": False, "current_user_approval_required": True}],
                })
                args = type("Args", (), {"date": "2026-08-13", "slot": 1, "file": str(queue_path)})()
                result = runner.record_review_queue(args)
                self.assertFalse(result["send_allowed"])
                plan = runner.load_json(runner.RUNS / "2026-08-13" / "account_1_daily_plan.json")
                self.assertEqual(plan["drafts_ready"], 0)
                self.assertEqual(plan["draft_candidates_ready"], 1)
                self.assertFalse(plan["comment_send_allowed"])
            finally:
                runner.RUNS = original

    def test_verified_model_queue_is_ready_for_platform_submission_without_second_user_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = runner.RUNS
            runner.RUNS = Path(temporary)
            try:
                runner.plan_day("2026-08-13")
                queue_path = runner.RUNS / "2026-08-13" / "account_1_candidate_queue.json"
                runner.write_json(queue_path, {
                    "date": "2026-08-13", "account_slot": 1,
                    "required_generation_model_verified": True,
                    "items": [{"exact_draft_text": "候选稿", "published": False, "current_user_approval_required": True}],
                })
                args = type("Args", (), {"date": "2026-08-13", "slot": 1, "file": str(queue_path)})()
                result = runner.record_review_queue(args)
                self.assertTrue(result["send_allowed"])
                queue = runner.load_json(queue_path)
                self.assertFalse(queue["items"][0]["current_user_approval_required"])
                plan = runner.load_json(runner.RUNS / "2026-08-13" / "account_1_daily_plan.json")
                self.assertEqual(plan["status"], "ready_for_platform_submission")
                self.assertEqual(plan["drafts_ready"], 1)
                self.assertTrue(plan["comment_send_allowed"])
            finally:
                runner.RUNS = original


if __name__ == "__main__":
    unittest.main()
