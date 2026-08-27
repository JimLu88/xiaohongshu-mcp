#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sqlite3
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("panse_content_registry.py")
SPEC = importlib.util.spec_from_file_location("panse_content_registry", SCRIPT)
assert SPEC and SPEC.loader
registry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(registry)


class ContentRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        registry.initialize(self.connection)

    def test_rights_and_publication_gates(self) -> None:
        content_args = type("Args", (), {
            "content_id": "cnt-1", "title": "数字空间爆改", "direction": "digital_room_makeover",
            "account_slot": 2, "platform": "cross_platform", "hook": "乱屋到可住",
        })()
        registry.create_content(self.connection, content_args)
        asset_args = type("Args", (), {
            "asset_id": "ast-1", "path_or_locator": "scene.blend", "asset_type": "blender_scene",
            "rights_status": "owned", "rights_evidence_ref": "contract-1", "ai_generated": True,
            "sha256": "abc",
        })()
        asset = registry.add_asset(self.connection, asset_args)
        self.assertTrue(asset["production_eligible"])
        self.assertTrue(asset["ai_disclosure_required"])

        move = type("Args", (), {"content_id": "cnt-1", "status": "published", "approval_ref": None, "receipt_ref": "r1"})()
        with self.assertRaises(ValueError):
            registry.transition(self.connection, move)

    def test_owned_asset_requires_rights_evidence(self) -> None:
        args = type("Args", (), {
            "asset_id": "ast-2", "path_or_locator": "photo.jpg", "asset_type": "photo",
            "rights_status": "owned", "rights_evidence_ref": None, "ai_generated": False,
            "sha256": None,
        })()
        with self.assertRaises(ValueError):
            registry.add_asset(self.connection, args)

    def test_researched_status_requires_evidence(self) -> None:
        content_args = type("Args", (), {
            "content_id": "cnt-2", "title": "证据评测", "direction": "evidence_lab",
            "account_slot": 3, "platform": "xiaohongshu", "hook": "先看条件",
        })()
        registry.create_content(self.connection, content_args)
        move = type("Args", (), {"content_id": "cnt-2", "status": "researched", "approval_ref": None, "receipt_ref": None})()
        with self.assertRaises(ValueError):
            registry.transition(self.connection, move)

    def test_asset_ready_requires_production_eligible_link(self) -> None:
        content_args = type("Args", (), {
            "content_id": "cnt-3", "title": "空间爆改", "direction": "digital_room_makeover",
            "account_slot": 2, "platform": "cross_platform", "hook": "前后对比",
        })()
        registry.create_content(self.connection, content_args)
        self.connection.execute(
            "UPDATE content_items SET status='scripted' WHERE content_id='cnt-3'"
        )
        with self.assertRaises(ValueError):
            registry.transition(self.connection, type("Args", (), {
                "content_id": "cnt-3", "status": "asset_ready", "approval_ref": None, "receipt_ref": None,
            })())


if __name__ == "__main__":
    unittest.main()
