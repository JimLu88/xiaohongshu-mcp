#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


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
                    self.assertGreaterEqual(plan["planned_browse_target"], 8)
                    self.assertLessEqual(plan["planned_browse_target"], 15)
                    self.assertEqual(plan["planned_comment_draft_cap"], 4)
                    self.assertEqual(plan["planned_follow_target"], 0 if slot == 1 else plan["planned_follow_target"])
                    self.assertFalse(plan["comment_send_allowed"])
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
            finally:
                runner.RUNS = original


if __name__ == "__main__":
    unittest.main()
