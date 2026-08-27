#!/usr/bin/env python3
"""Lightweight content, asset-rights, evidence and publication registry."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "panse_multi_direction"
    / "operations"
    / "panse_content_registry.sqlite3"
)
STATUSES = [
    "idea",
    "researched",
    "scripted",
    "asset_ready",
    "rendered",
    "reviewed",
    "approved",
    "published",
    "retired",
]
RIGHTS = {"owned", "licensed", "authorized", "internal_reference", "unknown"}
PRODUCTION_RIGHTS = {"owned", "licensed", "authorized"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS content_items (
          content_id TEXT PRIMARY KEY,
          title TEXT NOT NULL,
          direction TEXT NOT NULL,
          account_slot INTEGER CHECK(account_slot BETWEEN 1 AND 5),
          platform TEXT NOT NULL,
          hook TEXT,
          status TEXT NOT NULL,
          approval_ref TEXT,
          publication_receipt_ref TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS assets (
          asset_id TEXT PRIMARY KEY,
          path_or_locator TEXT NOT NULL,
          asset_type TEXT NOT NULL,
          rights_status TEXT NOT NULL,
          rights_evidence_ref TEXT,
          ai_generated INTEGER NOT NULL DEFAULT 0,
          ai_disclosure_required INTEGER NOT NULL DEFAULT 0,
          sha256 TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS content_assets (
          content_id TEXT NOT NULL REFERENCES content_items(content_id),
          asset_id TEXT NOT NULL REFERENCES assets(asset_id),
          usage_role TEXT NOT NULL,
          PRIMARY KEY(content_id, asset_id, usage_role)
        );
        CREATE TABLE IF NOT EXISTS evidence_sources (
          evidence_id TEXT PRIMARY KEY,
          content_id TEXT NOT NULL REFERENCES content_items(content_id),
          source_locator TEXT NOT NULL,
          source_type TEXT NOT NULL,
          claim_scope TEXT NOT NULL,
          captured_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS experiments (
          experiment_id TEXT PRIMARY KEY,
          content_id TEXT NOT NULL REFERENCES content_items(content_id),
          hypothesis TEXT NOT NULL,
          variant TEXT NOT NULL,
          metric_window TEXT NOT NULL,
          result_json TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS registry_events (
          event_id INTEGER PRIMARY KEY AUTOINCREMENT,
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          action TEXT NOT NULL,
          detail_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )
    connection.commit()


def emit_event(connection: sqlite3.Connection, entity_type: str, entity_id: str, action: str, detail: dict) -> None:
    connection.execute(
        "INSERT INTO registry_events(entity_type,entity_id,action,detail_json,created_at) VALUES(?,?,?,?,?)",
        (entity_type, entity_id, action, json.dumps(detail, ensure_ascii=False), now()),
    )


def create_content(connection: sqlite3.Connection, args: argparse.Namespace) -> dict:
    content_id = args.content_id or f"cnt-{uuid.uuid4().hex[:12]}"
    stamp = now()
    connection.execute(
        "INSERT INTO content_items(content_id,title,direction,account_slot,platform,hook,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (content_id, args.title, args.direction, args.account_slot, args.platform, args.hook, "idea", stamp, stamp),
    )
    emit_event(connection, "content", content_id, "created", {"status": "idea"})
    connection.commit()
    return {"content_id": content_id, "status": "idea"}


def add_asset(connection: sqlite3.Connection, args: argparse.Namespace) -> dict:
    if args.rights_status not in RIGHTS:
        raise ValueError(f"invalid rights status: {args.rights_status}")
    if args.rights_status in PRODUCTION_RIGHTS and not args.rights_evidence_ref:
        raise ValueError("production-eligible rights require --rights-evidence-ref")
    asset_id = args.asset_id or f"ast-{uuid.uuid4().hex[:12]}"
    disclosure_required = bool(args.ai_generated)
    connection.execute(
        "INSERT INTO assets(asset_id,path_or_locator,asset_type,rights_status,rights_evidence_ref,ai_generated,ai_disclosure_required,sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            asset_id,
            args.path_or_locator,
            args.asset_type,
            args.rights_status,
            args.rights_evidence_ref,
            int(args.ai_generated),
            int(disclosure_required),
            args.sha256,
            now(),
        ),
    )
    emit_event(connection, "asset", asset_id, "created", {"rights_status": args.rights_status})
    connection.commit()
    return {"asset_id": asset_id, "production_eligible": args.rights_status in PRODUCTION_RIGHTS, "ai_disclosure_required": disclosure_required}


def link_asset(connection: sqlite3.Connection, args: argparse.Namespace) -> dict:
    connection.execute(
        "INSERT OR IGNORE INTO content_assets(content_id,asset_id,usage_role) VALUES(?,?,?)",
        (args.content_id, args.asset_id, args.usage_role),
    )
    emit_event(connection, "content", args.content_id, "asset_linked", {"asset_id": args.asset_id, "usage_role": args.usage_role})
    connection.commit()
    return {"content_id": args.content_id, "asset_id": args.asset_id, "linked": True}


def add_evidence(connection: sqlite3.Connection, args: argparse.Namespace) -> dict:
    evidence_id = args.evidence_id or f"evd-{uuid.uuid4().hex[:12]}"
    connection.execute(
        "INSERT INTO evidence_sources(evidence_id,content_id,source_locator,source_type,claim_scope,captured_at) VALUES(?,?,?,?,?,?)",
        (evidence_id, args.content_id, args.source_locator, args.source_type, args.claim_scope, now()),
    )
    emit_event(connection, "content", args.content_id, "evidence_added", {"evidence_id": evidence_id})
    connection.commit()
    return {"evidence_id": evidence_id, "content_id": args.content_id}


def transition(connection: sqlite3.Connection, args: argparse.Namespace) -> dict:
    row = connection.execute("SELECT * FROM content_items WHERE content_id=?", (args.content_id,)).fetchone()
    if not row:
        raise ValueError("content item not found")
    current = row["status"]
    target = args.status
    if target not in STATUSES:
        raise ValueError(f"invalid status: {target}")
    allowed = current == target or (STATUSES.index(target) == STATUSES.index(current) + 1)
    if current == "published" and target == "retired":
        allowed = True
    if not allowed:
        raise ValueError(f"invalid transition: {current} -> {target}")
    if target == "researched":
        evidence_count = connection.execute(
            "SELECT COUNT(*) FROM evidence_sources WHERE content_id=?", (args.content_id,)
        ).fetchone()[0]
        if evidence_count < 1:
            raise ValueError("researched status requires at least one evidence source")
    if target == "asset_ready":
        eligible_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM content_assets ca
            JOIN assets a ON a.asset_id=ca.asset_id
            WHERE ca.content_id=?
              AND a.rights_status IN ('owned','licensed','authorized')
              AND a.rights_evidence_ref IS NOT NULL
            """,
            (args.content_id,),
        ).fetchone()[0]
        if eligible_count < 1:
            raise ValueError("asset_ready status requires a linked production-eligible asset")
    approval_ref = row["approval_ref"]
    receipt_ref = row["publication_receipt_ref"]
    if target == "approved":
        if not args.approval_ref:
            raise ValueError("approved status requires --approval-ref")
        approval_ref = args.approval_ref
    if target == "published":
        if current != "approved" or not args.receipt_ref:
            raise ValueError("published status requires prior approval and --receipt-ref")
        receipt_ref = args.receipt_ref
    connection.execute(
        "UPDATE content_items SET status=?,approval_ref=?,publication_receipt_ref=?,updated_at=? WHERE content_id=?",
        (target, approval_ref, receipt_ref, now(), args.content_id),
    )
    emit_event(connection, "content", args.content_id, "status_changed", {"from": current, "to": target})
    connection.commit()
    return {"content_id": args.content_id, "from": current, "to": target}


def list_content(connection: sqlite3.Connection, args: argparse.Namespace) -> list[dict]:
    query = "SELECT * FROM content_items"
    values: list[object] = []
    if args.status:
        query += " WHERE status=?"
        values.append(args.status)
    query += " ORDER BY updated_at DESC, content_id"
    return [dict(row) for row in connection.execute(query, values)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    content = sub.add_parser("create-content")
    content.add_argument("--content-id")
    content.add_argument("--title", required=True)
    content.add_argument("--direction", required=True)
    content.add_argument("--account-slot", type=int, choices=range(1, 6))
    content.add_argument("--platform", choices=["xiaohongshu", "douyin", "kuaishou", "cross_platform"], required=True)
    content.add_argument("--hook")
    asset = sub.add_parser("add-asset")
    asset.add_argument("--asset-id")
    asset.add_argument("--path-or-locator", required=True)
    asset.add_argument("--asset-type", required=True)
    asset.add_argument("--rights-status", required=True)
    asset.add_argument("--rights-evidence-ref")
    asset.add_argument("--ai-generated", action="store_true")
    asset.add_argument("--sha256")
    link = sub.add_parser("link-asset")
    link.add_argument("--content-id", required=True)
    link.add_argument("--asset-id", required=True)
    link.add_argument("--usage-role", required=True)
    evidence = sub.add_parser("add-evidence")
    evidence.add_argument("--evidence-id")
    evidence.add_argument("--content-id", required=True)
    evidence.add_argument("--source-locator", required=True)
    evidence.add_argument("--source-type", required=True)
    evidence.add_argument("--claim-scope", required=True)
    move = sub.add_parser("transition")
    move.add_argument("--content-id", required=True)
    move.add_argument("--status", required=True)
    move.add_argument("--approval-ref")
    move.add_argument("--receipt-ref")
    listing = sub.add_parser("list")
    listing.add_argument("--status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        connection = connect(args.db)
        initialize(connection)
        if args.command == "init":
            result = {"database": str(args.db), "initialized": True}
        elif args.command == "create-content":
            result = create_content(connection, args)
        elif args.command == "add-asset":
            result = add_asset(connection, args)
        elif args.command == "link-asset":
            result = link_asset(connection, args)
        elif args.command == "add-evidence":
            result = add_evidence(connection, args)
        elif args.command == "transition":
            result = transition(connection, args)
        else:
            result = list_content(connection, args)
    except (sqlite3.Error, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"ok": True, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
