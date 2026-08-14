r"""Build a five-item private full-context blind-review pilot.

The script only reads previously authorized local run artifacts.  Private note
bodies, visible comments, image observations, and candidate comments are written
under ``D:\AI\tachikoma\.tmp``.  The repository manifest contains hashes and
coverage counts only.  Nothing is generated, networked, or posted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = REPO_ROOT / "research" / "panse_multi_direction" / "daily_runs"
DEFAULT_PRIVATE_A = Path(r"D:\AI\tachikoma\.tmp\xhs-full-context-blind-pilot-reviewer-a-v1.json")
DEFAULT_PRIVATE_B = Path(r"D:\AI\tachikoma\.tmp\xhs-full-context-blind-pilot-reviewer-b-v1.json")
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_full_context_blind_pilot_manifest_v1.json"
)


def _sha256(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _items(obj: Any, names: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [item for item in obj if isinstance(item, dict)]
    if isinstance(obj, dict):
        for name in names:
            if isinstance(obj.get(name), list):
                return [item for item in obj[name] if isinstance(item, dict)]
        return [obj]
    return []


def _count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _candidate_text(review: dict[str, Any]) -> str:
    nested = review.get("item") if isinstance(review.get("item"), dict) else {}
    for value in (
        review.get("exact_draft_text"),
        review.get("draft"),
        review.get("final_text"),
        nested.get("exact_draft_text"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def load_eligible() -> list[dict[str, Any]]:
    reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in RUN_ROOT.rglob("*human_review*.json"):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in _items(obj, ("items", "reviews")):
            nested = item.get("item") if isinstance(item.get("item"), dict) else {}
            note_id = (
                item.get("note_id")
                or (item.get("target_note") or {}).get("note_id")
                or (nested.get("target_note") or {}).get("note_id")
            )
            if note_id:
                reviews[str(note_id)].append(item)

    eligible: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(RUN_ROOT.rglob("*style_requests*.json")):
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in _items(obj, ("items", "requests")):
            context = item.get("source_context")
            target = item.get("target_note")
            if not isinstance(context, dict) or not isinstance(target, dict):
                continue
            note_id = str(target.get("note_id") or "")
            if not note_id or note_id in seen:
                continue
            body = str(context.get("body") or "").strip()
            visible_comments = context.get("visible_comments")
            if not isinstance(visible_comments, list):
                visible_comments = [visible_comments] if str(visible_comments or "").strip() else []
            image_count = _count(context.get("image_count"))
            images_viewed = _count(context.get("images_viewed"))
            image_complete = image_count == 0 or images_viewed >= min(image_count, 6)
            candidate = next(
                (_candidate_text(review) for review in reviews.get(note_id, []) if _candidate_text(review)),
                "",
            )
            published = any(
                bool(review.get("published") or review.get("public_visible") or review.get("posting_verification"))
                for review in reviews.get(note_id, [])
            )
            if not (body and visible_comments and image_complete and candidate and not published):
                continue
            style_request = item.get("style_request") if isinstance(item.get("style_request"), dict) else {}
            intent = item.get("panse_intent_context") if isinstance(item.get("panse_intent_context"), dict) else {}
            if not intent:
                intent = style_request.get("panse_intent_context") if isinstance(style_request.get("panse_intent_context"), dict) else {}
            canonical = json.dumps(
                {
                    "title": target.get("title"),
                    "body": body,
                    "visible_comments": visible_comments,
                    "image_count": image_count,
                    "images_viewed": images_viewed,
                    "image_coverage_note": context.get("image_coverage_note"),
                    "candidate": candidate,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            eligible.append(
                {
                    "sample_id": "xhs-blind-" + _sha256(note_id)[:16],
                    "context_sha256": _sha256(canonical),
                    "title": str(target.get("title") or ""),
                    "body": body,
                    "visible_comments": visible_comments,
                    "image_observation": {
                        "image_count": image_count,
                        "images_viewed": images_viewed,
                        "coverage_note": context.get("image_coverage_note"),
                    },
                    "candidate": candidate,
                    "role": intent.get("voice_id") or "unknown",
                    "interaction_mode": item.get("interaction_mode") or intent.get("interaction_mode"),
                    "interaction_intent": intent.get("interaction_intent"),
                    "comment_direction_id": intent.get("comment_direction_id"),
                    "topic_ids": intent.get("topic_ids") or [],
                    "source_date": path.parent.name,
                    "protected_spans": {
                        "numbers": [],
                        "titles": [str(target.get("title") or "")],
                        "identity": intent.get("voice_id") or "unknown",
                    },
                }
            )
            seen.add(note_id)
    return eligible


def reversal_cases() -> list[dict[str, Any]]:
    """Synthetic structure controls; never treated as source facts or comments."""
    cases = [
        ("teacher_posture", "这个思路值得肯定，建议大家都学习这种布局方式。", "把评课和号召删掉，只承接一个具体细节。"),
        ("judge_posture", "整体完成度很高，动线、配色和收纳都处理得很成熟。", "不要像评委验收整套作品，只说当前评论者真正要回应的一点。"),
        ("advice_first", "建议把旁边那张椅子换小一点，这样空间会更通透。", "没有被邀请做方案时，不先给改造建议。"),
        ("source_restatement", "你把客厅做成无茶几布局，还加了小推车来补收纳。", "不要把正文和图片重新讲一遍。"),
        ("fabricated_firsthand", "我家也这么装了，用了一年真的很方便。", "没有真实经历就不能借第一人称提高可信度。"),
        ("answered_question", "想问这个柜子具体多深呀？", "正文或评论区已经回答的问题不能再问。"),
        ("narrator_inflation", "这说明真正好的设计不是堆功能，而是回到生活本身。", "删旁白和价值拔高，回到可见细节或直接回应。"),
        ("fake_colloquial", "谁懂啊，这个收纳思路真的绝绝子，直接抄作业！", "口语词不等于普通人位置；不硬凹网感。"),
        ("complete_editor_logic", "上面的开放格很方便，常用东西伸手就能拿，日常使用效率更高。", "即使词很口语，完整特征名词到好处解释仍像产品编辑。"),
        ("mandatory_life_landing", "颜色挺好看，放在普通家庭里每天看着心情都会更好。", "非 soft_observation 不强塞家庭日常落点。"),
        ("unearned_authority", "从专业角度看，这个结构的稳定性完全没问题。", "没有结构证据或身份授权，不下专业结论和绝对判断。"),
        ("uniform_polish", "这个细节很实用。这个配色很舒服。这个布局很合理。", "三句等长、同抬手、同落点像批量抛光；保留一条真正有信息的回应。"),
    ]
    return [
        {
            "case_id": f"xhs-reversal-{index:02d}",
            "problem_family": family,
            "candidate": candidate,
            "expected_decision": "reject",
            "expected_reason": reason,
            "synthetic_control": True,
            "publish_allowed": False,
        }
        for index, (family, candidate, reason) in enumerate(cases, start=1)
    ]


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


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    eligible = load_eligible()
    if len(eligible) != 5:
        raise RuntimeError(f"expected exact five eligible full-context items, found {len(eligible)}")
    seed = int(_sha256("\n".join(sorted(item["context_sha256"] for item in eligible)))[:16], 16)
    order_a = list(eligible)
    order_b = list(eligible)
    random.Random(seed).shuffle(order_a)
    random.Random(seed ^ 0x5A5A5A5A).shuffle(order_b)
    packet_base = {
        "schema_version": "xhs-full-context-independent-blind-review/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "review_scope": "five-item real full-context pilot plus separate synthetic reversals",
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
    manifest = {
        "schema_version": "xhs-full-context-independent-blind-review-manifest/v1",
        "created_at": packet_base["created_at"],
        "eligible_real_contexts": 5,
        "synthetic_reversal_controls": len(reversal_cases()),
        "context_hashes": sorted(item["context_sha256"] for item in eligible),
        "roles": sorted({item["role"] for item in eligible}),
        "private_packet_a": "local-private://tachikoma/.tmp/xhs-full-context-blind-pilot-reviewer-a-v1.json",
        "private_packet_b": "local-private://tachikoma/.tmp/xhs-full-context-blind-pilot-reviewer-b-v1.json",
        "packet_a_sha256": None,
        "packet_b_sha256": None,
        "independent_reviews_completed": 0,
        "minimum_real_context_target": 30,
        "remaining_real_context_gap": 25,
        "r3_status": "pilot_ready_awaiting_two_independent_reviewers",
        "stores_note_body_comments_images_or_draft": False,
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
        "publish_allowed": False,
    }
    return packet_a, packet_b, manifest


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
    parser.add_argument("--private-a", type=Path, default=DEFAULT_PRIVATE_A)
    parser.add_argument("--private-b", type=Path, default=DEFAULT_PRIVATE_B)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    packet_a, packet_b, manifest = build()
    bytes_a = (json.dumps(packet_a, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    bytes_b = (json.dumps(packet_b, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    manifest["packet_a_sha256"] = _sha256(bytes_a)
    manifest["packet_b_sha256"] = _sha256(bytes_b)
    bytes_manifest = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _atomic_write(args.private_a, bytes_a)
    _atomic_write(args.private_b, bytes_b)
    _atomic_write(args.manifest, bytes_manifest)
    print(json.dumps({
        "ok": True,
        "eligible_real_contexts": manifest["eligible_real_contexts"],
        "synthetic_reversal_controls": manifest["synthetic_reversal_controls"],
        "remaining_real_context_gap": manifest["remaining_real_context_gap"],
        "r3_status": manifest["r3_status"],
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
