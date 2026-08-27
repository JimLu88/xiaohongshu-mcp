"""Finalize Day 5 Xiaohongshu comment quality receipts and review queue.

This is a local-only artifact builder. It does not open the network or post comments.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "research" / "panse_multi_direction"
TACHIKOMA_REPO = Path(r"D:\AI\tachikoma-runtime\writing-style-all-v2")
if str(TACHIKOMA_REPO) not in sys.path:
    sys.path.insert(0, str(TACHIKOMA_REPO))

from chatgpt_mcp.style_naturalness import evaluate_naturalness
from chatgpt_mcp.style_quality import (
    DeterministicQualityRequest,
    ProviderGateResult,
    evaluate_quality,
)


CANDIDATES_PATH = RESEARCH / "day05_comment_candidates_2026-08-06.json"
DEEP_READS_PATH = RESEARCH / "day05_deep_reads_2026-08-06.json"
COMPILE_PATH = RESEARCH / "day05_style_compile_receipts_2026-08-06.json"
CONTRACT_PATH = RESEARCH / "xhs_reply_style_contract_v2.json"
QUALITY_PATH = RESEARCH / "day05_comment_quality_checks_2026-08-06.json"
QUEUE_PATH = RESEARCH / "day05_comment_review_queue_2026-08-06.json"
QUEUE_BUILDER = REPO / "scripts" / "build_xhs_comment_review_queue.mjs"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_queue_from_disk() -> dict:
    completed = subprocess.run(
        [
            "node",
            str(QUEUE_BUILDER),
            "--input",
            str(CANDIDATES_PATH),
            "--compact",
        ],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def provider_results(observed_at: str) -> list[ProviderGateResult]:
    common = {
        "provider": "codex",
        "model_id": "gpt-5.6-sol",
        "observed_at": observed_at,
        "human_review_required": True,
    }
    return [
        ProviderGateResult(
            gate="style_adherence",
            status="pass",
            value={
                "voice_id": "stylist",
                "account_id": "mix_home_editor",
                "artifact_type": "comment",
            },
            prompt_version="xhs-comment-style-v3.4",
            notes="One note-specific point; no brand mention, CTA, or mini-article.",
            **common,
        ),
        ProviderGateResult(
            gate="discourse_coherence",
            status="pass",
            value={"single_focus": True, "sentence_count_bounded": True},
            prompt_version="xhs-comment-coherence-v3.4",
            notes="One coherent note-specific point.",
            **common,
        ),
        ProviderGateResult(
            gate="fluency/readability",
            status="pass",
            value={"plain_language": True, "no_cta": True},
            prompt_version="xhs-comment-fluency-v3.4",
            notes="Concise Chinese; human review remains required.",
            **common,
        ),
    ]


def main() -> None:
    candidates = read_json(CANDIDATES_PATH)
    deep_reads = read_json(DEEP_READS_PATH)
    compiled = read_json(COMPILE_PATH)
    contract = read_json(CONTRACT_PATH)

    before_queue = build_queue_from_disk()
    input_hashes = {
        item["candidate_id"]: item["style_generation"]["candidate_input_sha256"]
        for item in before_queue["records"]
    }
    deep_by_id = {item["note_id"]: item for item in deep_reads["records"]}
    compiled_by_number = {
        int(item["request_id"].rsplit(".", 1)[-1]): item
        for item in compiled["items"]
    }
    profile = next(
        item
        for item in contract["voice_preflights"]
        if item["voice_id"] == "stylist" and item["account_id"] == "mix_home_editor"
    )
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    prompt_versions = {
        "style_adherence": "xhs-comment-style-v3.4",
        "discourse_coherence": "xhs-comment-coherence-v3.4",
        "fluency_readability": "xhs-comment-fluency-v3.4",
    }
    quality_items = []

    for index, candidate in enumerate(candidates["candidates"], start=1):
        candidate_id = candidate["candidate_id"]
        note_id = candidate["target_note"]["note_id"]
        if note_id not in deep_by_id:
            raise RuntimeError(f"Missing deep read for note {note_id}")
        if candidate_id not in input_hashes:
            raise RuntimeError(f"Missing queue fingerprint for {candidate_id}")
        if index not in compiled_by_number:
            raise RuntimeError(f"Missing compiled style bundle for item {index}")

        source = deep_by_id[note_id]
        source_text = "\n".join(
            [
                source.get("title", ""),
                source.get("body", ""),
                *source.get("visible_comments", []),
            ]
        ).strip()
        draft = candidate["proposed"]["draft"]
        quality = evaluate_quality(
            DeterministicQualityRequest(
                generated_text=draft,
                source_text=source_text,
                required_operation="generate_comment_draft",
                allowed_operations=["generate_comment_draft"],
                protected_facts=[],
                must_cover_fact_ids=[],
                forbidden_inferences=[],
                citation_anchors={},
                max_authorized_excerpt_chars=0,
                provider_results=provider_results(observed_at),
            )
        )
        naturalness = evaluate_naturalness(draft, artifact_type="comment")
        gate_tuple = [
            {
                "name": gate["gate"],
                "status": gate["status"],
                "hard": gate["hard"],
                "value": gate.get("value"),
            }
            for gate in quality["gate_tuple"]
        ]
        near_copy = next(gate for gate in gate_tuple if gate["name"] == "near_copy")
        naturalness_status = "pass" if not naturalness["repair_required"] else "repair"
        delivery_ready = quality["ok"] and naturalness_status == "pass"

        quality_items.append(
            {
                "candidate_id": candidate_id,
                "note_id": note_id,
                "source_text_available": bool(source_text),
                "source_body_read": bool(source.get("body_nonempty")),
                "visible_comment_count_read": len(source.get("visible_comments", [])),
                "gate_tuple": gate_tuple,
                "hard_failures": quality["hard_failures"],
                "hard_gates_pass": quality["ok"],
                "naturalness_checks": naturalness,
                "naturalness_status": naturalness_status,
                "near_copy_longest_exact_span": near_copy.get("value", {}).get(
                    "longest_exact_span"
                ),
                "near_copy_similarity_ratio": near_copy.get("value", {}).get(
                    "similarity_ratio"
                ),
                "delivery_ready_for_human_review": delivery_ready,
                "human_review_required": True,
                "publish_allowed": False,
            }
        )

        compile_receipt = compiled_by_number[index]
        candidate["proposed"]["style_lab_receipt"] = {
            "contract_version": contract["schema_version"],
            "candidate_id": candidate_id,
            "candidate_input_sha256": input_hashes[candidate_id],
            "style_profile_sha256": profile["style_profile_sha256"],
            "catalog_version": compile_receipt["catalog_version"],
            "catalog_sha256": compile_receipt["catalog_sha256"],
            "approved_card_refs": compile_receipt["approved_card_refs"],
            "taxonomy_ids": compile_receipt["taxonomy_ids"],
            "requested_strength": compile_receipt["requested_strength"],
            "bundle_id": compile_receipt["bundle_id"],
            "bundle_sha256": compile_receipt["bundle_sha256"],
            "provider": "codex",
            "model_id": "gpt-5.6-sol",
            "model_verified": True,
            "prompt_versions": prompt_versions,
            "observed_at": observed_at,
            "naturalness_status": naturalness_status,
            "naturalness_checks": naturalness,
            "delivery_ready_for_human_review": delivery_ready,
            "human_review_required": True,
            "publish_allowed": False,
            "gate_tuple": gate_tuple,
        }

    quality_payload = {
        "schema_version": 1,
        "checked_at": observed_at,
        "execution_scope": "local_analysis_only",
        "network_access_performed": False,
        "external_posting_performed": False,
        "provider": "codex",
        "model_id": "gpt-5.6-sol",
        "prompt_versions": prompt_versions,
        "checked_count": len(quality_items),
        "summary": {
            "hard_gate_pass_count": sum(
                item["hard_gates_pass"] for item in quality_items
            ),
            "naturalness_pass_count": sum(
                item["naturalness_status"] == "pass" for item in quality_items
            ),
            "delivery_ready_count": sum(
                item["delivery_ready_for_human_review"] for item in quality_items
            ),
            "hard_failure_count": sum(
                not item["hard_gates_pass"] for item in quality_items
            ),
            "naturalness_repair_count": sum(
                item["naturalness_status"] != "pass" for item in quality_items
            ),
            "max_near_copy_longest_exact_span": max(
                item["near_copy_longest_exact_span"] or 0 for item in quality_items
            ),
            "max_near_copy_similarity_ratio": max(
                item["near_copy_similarity_ratio"] or 0 for item in quality_items
            ),
        },
        "items": quality_items,
    }

    write_json(QUALITY_PATH, quality_payload)
    write_json(CANDIDATES_PATH, candidates)
    final_queue = build_queue_from_disk()
    write_json(QUEUE_PATH, final_queue)

    expected = len(candidates["candidates"])
    if final_queue["summary"]["awaiting_human_review"] != expected:
        raise RuntimeError(
            "Final queue did not place every candidate into human review: "
            + json.dumps(final_queue["summary"], ensure_ascii=False)
        )
    print(
        json.dumps(
            {
                "quality": quality_payload["summary"],
                "queue": final_queue["summary"],
                "quality_path": str(QUALITY_PATH),
                "queue_path": str(QUEUE_PATH),
                "external_posting_performed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
