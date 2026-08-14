r"""Build a versioned Xiaohongshu full-context independent-review packet.

Version 2 joins the old top-level ``source_context`` shape with the newer
``style_request.source_context`` shape.  It also excludes notes that have a
separate verified publication receipt.  Complete bodies, comments, image
observations, candidate comments, note IDs, and local provenance remain under
``D:\AI\tachikoma\.tmp``.  The repository manifest contains hashes and
coverage counts only.  The script performs no generation, network, or platform
action.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import tempfile
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO_ROOT / "research" / "panse_multi_direction" / "daily_runs"
PRIVATE_ROOT = Path(r"D:\AI\tachikoma\.tmp")
DEFAULT_PRIVATE_A = PRIVATE_ROOT / "xhs-full-context-blind-reviewer-a-v2.json"
DEFAULT_PRIVATE_B = PRIVATE_ROOT / "xhs-full-context-blind-reviewer-b-v2.json"
DEFAULT_PRIVATE_QUEUE = PRIVATE_ROOT / "xhs-full-context-acquisition-queue-v2.json"
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_full_context_blind_pilot_manifest_v2.json"
)
TARGET_REAL_CONTEXTS = 30


def _sha256(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _items(obj: Any, names: tuple[str, ...] = ("items", "requests", "reviews")) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [item for item in obj if isinstance(item, dict)]
    if isinstance(obj, dict):
        for name in names:
            if isinstance(obj.get(name), list):
                return [item for item in obj[name] if isinstance(item, dict)]
        return [obj]
    return []


def _note_id(item: dict[str, Any]) -> str:
    nested = item.get("item") if isinstance(item.get("item"), dict) else {}
    targets = (
        item.get("target_note"),
        nested.get("target_note"),
    )
    for value in (item.get("note_id"), nested.get("note_id")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    for target in targets:
        if isinstance(target, dict) and str(target.get("note_id") or "").strip():
            return str(target["note_id"]).strip()
    return ""


def _candidate_text(item: dict[str, Any]) -> str:
    nested = item.get("item") if isinstance(item.get("item"), dict) else {}
    for value in (
        item.get("exact_draft_text"),
        item.get("draft"),
        item.get("final_text"),
        nested.get("exact_draft_text"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _as_nonempty_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for item in value if not isinstance(item, str) or item.strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _explicit_false(mapping: dict[str, Any], key: str) -> bool:
    return key in mapping and mapping.get(key) is not True


def _verified_publication(root: dict[str, Any], item: dict[str, Any]) -> bool:
    exact_visible = item.get("exact_text_visible") is True
    account_visible = item.get("current_account_context_visible") is True
    editor_cleared = item.get("editor_cleared") is True
    increment = item.get("comment_count_increment_verified") is True
    before = item.get("comment_count_before")
    after = item.get("comment_count_after")
    numeric_increment = (
        isinstance(before, int) and isinstance(after, int) and after == before + 1
    )
    if root.get("all_publicly_verified") is True:
        root_identity = bool(root.get("profile_id") or root.get("account_id"))
        return exact_visible and root_identity and editor_cleared and numeric_increment
    return exact_visible and account_visible and editor_cleared and (increment or numeric_increment)


def load_verified_publications() -> dict[str, list[dict[str, Any]]]:
    published: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in RUN_ROOT.rglob("*.json"):
        lower_name = path.name.lower()
        if "publish" not in lower_name and "posting" not in lower_name and "human_review" not in lower_name:
            continue
        obj = _load(path)
        if not isinstance(obj, (dict, list)):
            continue
        root = obj if isinstance(obj, dict) else {}
        for item in _items(obj):
            note_id = _note_id(item)
            status_only = "human_review" in lower_name
            observed = item.get("published") is True if status_only else _verified_publication(root, item)
            if note_id and observed:
                text = ""
                for value in (
                    item.get("text"),
                    item.get("exact_text"),
                    item.get("published_text"),
                    item.get("exact_draft_text") if status_only else None,
                ):
                    if isinstance(value, str) and value.strip():
                        text = value.strip()
                        break
                published[note_id].append(
                    {
                        "text": text,
                        "path": str(path.relative_to(REPO_ROOT)),
                        "source_date": path.parent.name,
                        "verification_level": (
                            "status_flag_only"
                            if status_only
                            else "verified_publication_receipt"
                        ),
                    }
                )
    return published


def load_published_note_ids() -> set[str]:
    return set(load_verified_publications())


def load_candidates() -> dict[str, list[dict[str, Any]]]:
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    patterns = ("*human_review*.json", "*comment_candidate_queue*.json")
    paths = sorted({path for pattern in patterns for path in RUN_ROOT.rglob(pattern)})
    for path in paths:
        obj = _load(path)
        for item in _items(obj):
            note_id = _note_id(item)
            candidate = _candidate_text(item)
            if not note_id or not candidate:
                continue
            candidates[note_id].append(
                {
                    "candidate": candidate,
                    "path": str(path.relative_to(REPO_ROOT)),
                    "source_date": path.parent.name,
                }
            )
    return candidates


def _source_context(item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    style_request = item.get("style_request") if isinstance(item.get("style_request"), dict) else {}
    direct = item.get("source_context")
    nested = style_request.get("source_context")
    context = direct if isinstance(direct, dict) else nested if isinstance(nested, dict) else {}
    return context, style_request


def _image_evidence(context: dict[str, Any]) -> tuple[int, int, bool, list[Any]]:
    observations = _as_nonempty_list(context.get("image_observations"))
    if "expected_image_count" in context or "images_complete" in context:
        expected = _as_int(context.get("expected_image_count"))
        viewed = len(observations)
        complete = context.get("images_complete") is True
        if expected > 0:
            complete = complete and viewed >= min(expected, 6)
        return expected, viewed, complete, observations
    expected = _as_int(context.get("image_count"))
    viewed = _as_int(context.get("images_viewed"))
    complete = expected == 0 or viewed >= min(expected, 6)
    return expected, viewed, complete, observations


def _candidate_record(
    path: Path,
    index: int,
    item: dict[str, Any],
    candidates: dict[str, list[dict[str, Any]]],
    publications: dict[str, list[dict[str, Any]]],
    include_verified_published: bool,
) -> dict[str, Any] | None:
    note_id = _note_id(item)
    if not note_id:
        return None
    context, style_request = _source_context(item)
    target = item.get("target_note") if isinstance(item.get("target_note"), dict) else {}
    intent = item.get("panse_intent_context") if isinstance(item.get("panse_intent_context"), dict) else {}
    if not intent and isinstance(style_request.get("panse_intent_context"), dict):
        intent = style_request["panse_intent_context"]
    body = str(context.get("body") or "").strip()
    visible_comments = _as_nonempty_list(context.get("visible_comments"))
    expected_images, viewed_images, image_complete, image_observations = _image_evidence(context)
    candidate_records = sorted(
        candidates.get(note_id, []),
        key=lambda row: (row["source_date"], row["path"]),
        reverse=True,
    )
    publication_records = sorted(
        publications.get(note_id, []),
        key=lambda row: (row["source_date"], row["path"]),
        reverse=True,
    )
    verified_publications = [
        row
        for row in publication_records
        if row["verification_level"] == "verified_publication_receipt"
    ]
    status_only_publications = [
        row for row in publication_records if row["verification_level"] == "status_flag_only"
    ]
    prepublication_candidate = candidate_records[0]["candidate"] if candidate_records else ""
    authoritative_publication = next(
        (row for row in verified_publications if row["text"]),
        None,
    )
    exact_publication = next(
        (
            row
            for row in verified_publications
            if row["text"] and row["text"] == prepublication_candidate
        ),
        None,
    )
    status_only_publication = next(
        (row for row in status_only_publications if row["text"]),
        None,
    )
    if verified_publications and include_verified_published and authoritative_publication:
        review_text = authoritative_publication["text"]
        candidate_origin = (
            "verified_publication_text_exact_prepublish_match"
            if exact_publication
            else "verified_publication_text_authoritative"
        )
    elif status_only_publications and include_verified_published and prepublication_candidate:
        review_text = prepublication_candidate
        candidate_origin = "historical_human_review_candidate"
    else:
        review_text = prepublication_candidate
        candidate_origin = "pending_human_review_packet"
    missing: list[str] = []
    if not body:
        missing.append("body_missing")
    if _explicit_false(context, "body_complete"):
        missing.append("body_not_explicitly_complete")
    if not visible_comments:
        missing.append("visible_comments_missing")
    if _explicit_false(context, "visible_comments_complete"):
        missing.append("visible_comments_not_explicitly_complete")
    if not image_complete:
        missing.append("image_coverage_incomplete")
    if publication_records:
        if not include_verified_published:
            missing.append("already_published")
        elif verified_publications and authoritative_publication is None:
            missing.append("verified_publication_text_missing")
        elif status_only_publications and not prepublication_candidate:
            missing.append("historical_candidate_missing")
    elif not prepublication_candidate:
        missing.append("candidate_missing")
    review_stratum = (
        "retrospective_verified_publication"
        if verified_publications and authoritative_publication is not None
        else (
            "retrospective_candidate_publication_unverified"
            if status_only_publications and prepublication_candidate
            else "prospective_unpublished"
        )
    )
    canonical = json.dumps(
        {
            "title": target.get("title"),
            "body": body,
            "visible_comments": visible_comments,
            "expected_images": expected_images,
            "viewed_images": viewed_images,
            "image_observations": image_observations,
            "candidate": review_text,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "note_id": note_id,
        "note_id_sha256": _sha256(note_id),
        "sample_id": "xhs-blind-v2-" + _sha256(note_id)[:16],
        "context_sha256": _sha256(canonical),
        "title": str(target.get("title") or ""),
        "body": body,
        "visible_comments": visible_comments,
        "image_observation": {
            "expected_image_count": expected_images,
            "images_viewed": viewed_images,
            "images_complete": image_complete,
            "observations": image_observations,
        },
        "candidate": review_text,
        "role": intent.get("voice_id") or "unknown",
        "interaction_mode": item.get("interaction_mode") or style_request.get("interaction_mode") or intent.get("interaction_mode"),
        "interaction_intent": intent.get("interaction_intent"),
        "comment_direction_id": intent.get("comment_direction_id"),
        "topic_ids": intent.get("topic_ids") or [],
        "source_date": path.parent.name,
        "source_path": str(path.relative_to(REPO_ROOT)),
        "source_item_index": index,
        "candidate_source_path": candidate_records[0]["path"] if candidate_records else None,
        "candidate_origin": candidate_origin,
        "review_stratum": review_stratum,
        "publication_receipt_path": authoritative_publication["path"] if authoritative_publication else None,
        "publication_status_path": status_only_publication["path"] if status_only_publication else None,
        "publication_text_exact_match": exact_publication is not None,
        "missing_reasons": sorted(set(missing)),
    }


def audit_local_contexts(
    *, include_verified_published: bool = True
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    candidates = load_candidates()
    publications = load_verified_publications()
    by_note: dict[str, list[dict[str, Any]]] = defaultdict(list)
    patterns = ("*style_requests*.json", "*style_repair_request*.json")
    paths = sorted({path for pattern in patterns for path in RUN_ROOT.rglob(pattern)})
    for path in paths:
        obj = _load(path)
        for index, item in enumerate(_items(obj)):
            record = _candidate_record(
                path,
                index,
                item,
                candidates,
                publications,
                include_verified_published,
            )
            if record:
                by_note[record["note_id"]].append(record)

    eligible: list[dict[str, Any]] = []
    acquisition: list[dict[str, Any]] = []
    for note_id, records in sorted(by_note.items()):
        records.sort(
            key=lambda row: (
                not row["missing_reasons"],
                row["source_date"],
                row["source_path"],
                -row["source_item_index"],
            ),
            reverse=True,
        )
        best = records[0]
        if not best["missing_reasons"]:
            eligible.append(best)
        else:
            acquisition.append(
                {
                    "note_id": note_id,
                    "note_id_sha256": best["note_id_sha256"],
                    "missing_reasons": best["missing_reasons"],
                    "source_date": best["source_date"],
                    "source_path": best["source_path"],
                }
            )
    return eligible, acquisition, set(publications)


def _stratified_select(records: Iterable[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], deque[dict[str, Any]]] = defaultdict(deque)
    for record in sorted(records, key=lambda row: (row["context_sha256"], row["sample_id"])):
        key = (str(record.get("role") or "unknown"), str(record.get("interaction_mode") or "unknown"))
        groups[key].append(record)
    selected: list[dict[str, Any]] = []
    keys = sorted(groups)
    while len(selected) < target and any(groups.values()):
        for key in keys:
            if groups[key] and len(selected) < target:
                selected.append(groups[key].popleft())
    return selected


def _select_with_strata(records: Iterable[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    records = list(records)
    prospective = [row for row in records if row["review_stratum"] == "prospective_unpublished"]
    retrospective = [row for row in records if row["review_stratum"] == "retrospective_verified_publication"]
    status_unverified = [
        row
        for row in records
        if row["review_stratum"] == "retrospective_candidate_publication_unverified"
    ]
    selected = _stratified_select(prospective, min(target, len(prospective)))
    if len(selected) < target:
        selected.extend(_stratified_select(retrospective, target - len(selected)))
    if len(selected) < target:
        selected.extend(_stratified_select(status_unverified, target - len(selected)))
    return selected


def _review_item(item: dict[str, Any], alias: str) -> dict[str, Any]:
    return {
        "blind_id": alias,
        "context_sha256": item["context_sha256"],
        "context": {
            "title": item["title"],
            "body": item["body"],
            "visible_comments": item["visible_comments"],
            "image_observation": item["image_observation"],
        },
        "candidate": item["candidate"],
        "declared_role": item["role"],
        "declared_interaction_mode": item["interaction_mode"],
        "review_dimensions": {
            "source_grounded": None,
            "speaking_position_correct": None,
            "speech_act_fit": None,
            "teacher_or_judge_posture_absent": None,
            "source_restatement_absent": None,
            "fabricated_firsthand_absent": None,
            "question_still_unanswered": None,
            "ordinary_order_and_logic": None,
            "protected_spans_preserved": None,
            "near_copy_safe": None,
        },
        "decision": None,
        "reason_codes": [],
        "reviewer_note": None,
        "reviewed_at": None,
    }


def reversal_cases() -> list[dict[str, Any]]:
    from build_xhs_full_context_blind_pilot import reversal_cases as v1_reversal_cases

    return v1_reversal_cases()


def build(
    target: int = TARGET_REAL_CONTEXTS,
    *,
    include_verified_published: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    eligible, acquisition, published = audit_local_contexts(
        include_verified_published=include_verified_published
    )
    selected = _select_with_strata(eligible, min(target, len(eligible)))
    seed = int(_sha256("\n".join(sorted(item["context_sha256"] for item in selected)))[:16], 16)
    order_a = list(selected)
    order_b = list(selected)
    random.Random(seed).shuffle(order_a)
    random.Random(seed ^ 0x5A5A5A5A).shuffle(order_b)
    created_at = datetime.now(timezone.utc).isoformat()
    packet_base = {
        "schema_version": "xhs-full-context-independent-blind-review/v2",
        "created_at": created_at,
        "review_scope": "real full-context calibration plus separate synthetic reversals",
        "independent_review_required": True,
        "reviewer_identity_in_other_packet_hidden": True,
        "model_or_provider_review_counts_as_human": False,
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
        "publish_allowed": False,
    }
    packet_a = {
        **packet_base,
        "reviewer_slot": "A",
        "items": [_review_item(item, f"A-{index:02d}") for index, item in enumerate(order_a, 1)],
        "reversal_controls": reversal_cases(),
    }
    packet_b = {
        **packet_base,
        "reviewer_slot": "B",
        "items": [_review_item(item, f"B-{index:02d}") for index, item in enumerate(order_b, 1)],
        "reversal_controls": reversal_cases(),
    }
    reason_counts = Counter(
        reason for row in acquisition for reason in row["missing_reasons"]
    )
    queue = {
        "schema_version": "xhs-full-context-acquisition-queue/v2",
        "created_at": created_at,
        "private_local_only": True,
        "records": acquisition,
        "verified_published_note_ids_observed": sorted(published),
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
    }
    provenance = {
        "schema_version": "xhs-full-context-selection-provenance/v2",
        "created_at": created_at,
        "private_local_only": True,
        "records": [
            {
                "context_sha256": row["context_sha256"],
                "note_id": row["note_id"],
                "note_id_sha256": row["note_id_sha256"],
                "review_stratum": row["review_stratum"],
                "source_date": row["source_date"],
                "source_path": row["source_path"],
                "source_item_index": row["source_item_index"],
                "candidate_source_path": row["candidate_source_path"],
                "candidate_origin": row["candidate_origin"],
                "publication_receipt_path": row["publication_receipt_path"],
                "publication_status_path": row["publication_status_path"],
                "publication_text_exact_match": row["publication_text_exact_match"],
            }
            for row in selected
        ],
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
    }
    eligible_strata = Counter(row["review_stratum"] for row in eligible)
    selected_strata = Counter(row["review_stratum"] for row in selected)
    selected_candidate_origins = Counter(row["candidate_origin"] for row in selected)
    manifest = {
        "schema_version": "xhs-full-context-independent-blind-review-manifest/v2",
        "created_at": created_at,
        "eligible_real_contexts": len(eligible),
        "selected_real_contexts": len(selected),
        "minimum_real_context_target": target,
        "remaining_real_context_gap": max(0, target - len(selected)),
        "synthetic_reversal_controls": len(reversal_cases()),
        "context_hashes": sorted(item["context_sha256"] for item in selected),
        "roles": sorted({str(item["role"]) for item in selected}),
        "interaction_modes": sorted({str(item["interaction_mode"]) for item in selected}),
        "eligible_strata": dict(sorted(eligible_strata.items())),
        "selected_strata": dict(sorted(selected_strata.items())),
        "selected_candidate_origins": dict(sorted(selected_candidate_origins.items())),
        "verified_published_note_count_observed": len(published),
        "retrospective_publication_is_style_approval": False,
        "status_flag_only_is_verified_publication": False,
        "historical_candidate_is_style_approval": False,
        "acquisition_queue_count": len(acquisition),
        "acquisition_reason_counts": dict(sorted(reason_counts.items())),
        "private_packet_a": "local-private://tachikoma/.tmp/xhs-full-context-blind-reviewer-a-v2.json",
        "private_packet_b": "local-private://tachikoma/.tmp/xhs-full-context-blind-reviewer-b-v2.json",
        "private_acquisition_queue": "local-private://tachikoma/.tmp/xhs-full-context-acquisition-queue-v2.json",
        "private_selection_provenance": "local-private://tachikoma/.tmp/xhs-full-context-selection-provenance-v2.json",
        "packet_a_sha256": None,
        "packet_b_sha256": None,
        "acquisition_queue_sha256": None,
        "selection_provenance_sha256": None,
        "independent_reviews_completed": 0,
        "r3_status": "awaiting_two_independent_reviewers" if len(selected) >= target else "context_collection_incomplete",
        "stores_note_id_body_comments_images_or_draft": False,
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
        "publish_allowed": False,
    }
    return packet_a, packet_b, queue, provenance, manifest


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=TARGET_REAL_CONTEXTS)
    parser.add_argument("--private-a", type=Path, default=DEFAULT_PRIVATE_A)
    parser.add_argument("--private-b", type=Path, default=DEFAULT_PRIVATE_B)
    parser.add_argument("--private-queue", type=Path, default=DEFAULT_PRIVATE_QUEUE)
    parser.add_argument(
        "--private-provenance",
        type=Path,
        default=PRIVATE_ROOT / "xhs-full-context-selection-provenance-v2.json",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--prospective-only",
        action="store_true",
        help="exclude all records with a verified publication receipt",
    )
    args = parser.parse_args()
    if args.target < 1:
        raise SystemExit("target must be positive")
    packet_a, packet_b, queue, provenance, manifest = build(
        args.target,
        include_verified_published=not args.prospective_only,
    )
    bytes_a = _json_bytes(packet_a)
    bytes_b = _json_bytes(packet_b)
    bytes_queue = _json_bytes(queue)
    bytes_provenance = _json_bytes(provenance)
    manifest["packet_a_sha256"] = _sha256(bytes_a)
    manifest["packet_b_sha256"] = _sha256(bytes_b)
    manifest["acquisition_queue_sha256"] = _sha256(bytes_queue)
    manifest["selection_provenance_sha256"] = _sha256(bytes_provenance)
    _atomic_write(args.private_a, bytes_a)
    _atomic_write(args.private_b, bytes_b)
    _atomic_write(args.private_queue, bytes_queue)
    _atomic_write(args.private_provenance, bytes_provenance)
    _atomic_write(args.manifest, _json_bytes(manifest))
    print(json.dumps({
        "ok": True,
        "eligible_real_contexts": manifest["eligible_real_contexts"],
        "selected_real_contexts": manifest["selected_real_contexts"],
        "remaining_real_context_gap": manifest["remaining_real_context_gap"],
        "selected_strata": manifest["selected_strata"],
        "verified_published_note_count_observed": manifest["verified_published_note_count_observed"],
        "acquisition_reason_counts": manifest["acquisition_reason_counts"],
        "r3_status": manifest["r3_status"],
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
