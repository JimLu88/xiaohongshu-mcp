#!/usr/bin/env python3
"""Compile 100 pinned Tachikoma Style Lab requests without generating or posting."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "research" / "panse_multi_direction"
REQUESTS_PATH = Path(
    os.environ.get(
        "XHS_STYLE_REQUESTS_PATH",
        RESEARCH / "style_experiment_four_mode_generation_requests_100_2026-08-07.json",
    )
)
CONTRACT_PATH = RESEARCH / "xhs_reply_style_contract_v2.json"
EXPERIMENT_CONTRACT_PATH = Path(
    os.environ.get(
        "XHS_STYLE_EXPERIMENT_CONTRACT_PATH",
        RESEARCH / "style_experiment_four_mode_contract_2026-08-07.json",
    )
)
OUTPUT_PATH = Path(
    os.environ.get(
        "XHS_STYLE_COMPILE_OUTPUT_PATH",
        RESEARCH / "style_experiment_four_mode_style_compile_receipts_100_2026-08-07.json",
    )
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    requests_payload = read_json(REQUESTS_PATH)
    contract = read_json(CONTRACT_PATH)
    experiment_contract = read_json(EXPERIMENT_CONTRACT_PATH)
    tachikoma_root = Path(contract["style_lab"]["runtime_root"]).resolve()
    sys.path.insert(0, str(tachikoma_root))

    from base.xiaohongshu_style import (  # pylint: disable=import-outside-toplevel
        StyleWritingRequest,
        prepare_style_bundle,
    )
    from chatgpt_mcp.style_cards import (  # pylint: disable=import-outside-toplevel
        AccessContext,
        StyleCardStore,
    )

    required_model_id = experiment_contract["provider_contract"]["required_model_id"]
    expected_catalog = experiment_contract["current_runtime_evidence"][
        "catalog_sha256"
    ]
    expected_catalog_version = experiment_contract["current_runtime_evidence"][
        "catalog_version"
    ]
    expected_cards = {
        (item["card_id"], item["card_version"]): item["content_sha256"]
        for item in experiment_contract["pinned_selection"]["approved_card_refs"]
    }
    store = StyleCardStore()
    context = AccessContext.service_admin()
    receipts = []
    style_instructions_by_mode: dict[str, dict] = {}

    for item in requests_payload["requests"]:
        request = StyleWritingRequest.model_validate(item["style_request"])
        bundle, instruction = prepare_style_bundle(
            request,
            store=store,
            context=context,
        )
        provider = bundle["provider_contract"]
        selection = bundle["selection"]
        taxonomy = selection["taxonomy"]

        if request.required_model_id != required_model_id:
            raise RuntimeError(
                f"{request.request_id}: request model mismatch "
                f"{request.required_model_id!r} != {required_model_id!r}"
            )
        if provider["required_model_id"] != required_model_id:
            raise RuntimeError(f"{request.request_id}: compiled model mismatch")
        if provider["fallback_model_allowed"]:
            raise RuntimeError(f"{request.request_id}: fallback unexpectedly enabled")
        if request.interaction_mode != item["interaction_mode"]:
            raise RuntimeError(f"{request.request_id}: interaction_mode drift")
        if bundle["request"]["interaction_mode"] != request.interaction_mode:
            raise RuntimeError(f"{request.request_id}: compiled interaction_mode drift")
        if taxonomy["catalog_sha256"] != expected_catalog:
            raise RuntimeError(
                f"{request.request_id}: style catalog drift: "
                f"expected={expected_catalog}, observed={taxonomy['catalog_sha256']}, "
                f"catalog_version={taxonomy['catalog_version']}"
            )
        if taxonomy["catalog_version"] != expected_catalog_version:
            raise RuntimeError(f"{request.request_id}: style catalog version drift")
        if not selection["approved_card_refs"]:
            raise RuntimeError(f"{request.request_id}: no approved Style Cards")
        observed_cards = {
            (card["card_id"], card["card_version"]): card["content_sha256"]
            for card in selection["approved_card_refs"]
        }
        if observed_cards != expected_cards:
            raise RuntimeError(f"{request.request_id}: approved Style Card drift")

        style_instructions_by_mode.setdefault(
            request.interaction_mode,
            bundle["style_instructions"],
        )

        receipts.append(
            {
                "experiment_id": item["experiment_id"],
                "request_id": request.request_id,
                "interaction_mode": request.interaction_mode,
                "request_sha256": stable_sha256(item["style_request"]),
                "brief_sha256": hashlib.sha256(
                    request.brief_text.encode("utf-8")
                ).hexdigest(),
                "bundle_id": bundle["bundle_id"],
                "bundle_sha256": bundle["bundle_sha256"],
                "instruction_sha256": hashlib.sha256(
                    instruction.encode("utf-8")
                ).hexdigest(),
                "catalog_version": taxonomy["catalog_version"],
                "catalog_sha256": taxonomy["catalog_sha256"],
                "taxonomy_ids": taxonomy["taxonomy_ids"],
                "approved_card_refs": selection["approved_card_refs"],
                "requested_strength": selection["strength"]["resolved"],
                "register_contract": bundle["style_instructions"][
                    "register_contract"
                ],
                "provider_contract": provider,
                "required_model_id": request.required_model_id,
                "fallback_model_allowed": request.fallback_model_allowed,
                "text_generated": False,
                "network_access_performed": False,
                "external_posting_performed": False,
                "human_review_required": True,
                "publish_allowed": False,
            }
        )

    compiled_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
    payload = {
        "schema_version": 1,
        "project": "panse_xiaohongshu",
        "compiled_at": compiled_at,
        "source_requests": str(REQUESTS_PATH.relative_to(REPO)).replace("\\", "/"),
        "contract": str(CONTRACT_PATH.relative_to(REPO)).replace("\\", "/"),
        "experiment_contract": (
            str(EXPERIMENT_CONTRACT_PATH.relative_to(REPO)).replace("\\", "/")
            if EXPERIMENT_CONTRACT_PATH.is_relative_to(REPO)
            else str(EXPERIMENT_CONTRACT_PATH)
        ),
        "runtime_entrypoint": contract["style_lab"]["runtime_entrypoint"],
        "required_model_id": required_model_id,
        "fallback_model_allowed": False,
        "request_count": len(receipts),
        "compile_pass_count": len(receipts),
        "style_instructions_by_mode": style_instructions_by_mode,
        "mode_specific_style_instructions": True,
        "items": receipts,
        "network_access_performed": False,
        "external_posting_performed": False,
        "human_review_required": True,
        "publish_allowed": False,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output_path": str(OUTPUT_PATH.relative_to(REPO)),
                "request_count": len(receipts),
                "compile_pass_count": len(receipts),
                "model_id": required_model_id,
                "fallback_model_allowed": False,
                "external_posting_performed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
