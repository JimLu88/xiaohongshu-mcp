#!/usr/bin/env python3
"""Generate the offline 100-item four-mode experiment with an exact Codex model.

The provider is invoked in read-only, ephemeral mode through the user's ChatGPT
subscription. Results are replayed through Tachikoma's real plan -> draft ->
deterministic gates -> semantic-review pipeline. Nothing is published.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO = Path(__file__).resolve().parents[1]
RESEARCH = REPO / "research" / "panse_multi_direction"
REQUESTS_PATH = Path(
    os.environ.get(
        "XHS_STYLE_REQUESTS_PATH",
        RESEARCH / "style_experiment_four_mode_generation_requests_100_2026-08-07.json",
    )
)
COMPILE_PATH = Path(
    os.environ.get(
        "XHS_STYLE_COMPILE_PATH",
        RESEARCH / "style_experiment_four_mode_style_compile_receipts_100_2026-08-07.json",
    )
)
OUTPUT_PATH = Path(
    os.environ.get(
        "XHS_STYLE_DRAFT_OUTPUT_PATH",
        RESEARCH / "style_experiment_four_mode_codex_drafts_100_2026-08-07.json",
    )
)
TACHIKOMA_ROOT = Path(r"D:\AI\tachikoma-runtime\writing-style-all-v2")
CACHE_PATH = Path(
    os.environ.get(
        "XHS_STYLE_CACHE_PATH",
        TACHIKOMA_ROOT
        / ".tmp"
        / "xhs-four-mode"
        / "provider-stage-cache-2026-08-07.json",
    )
)
SESSION_RESPONSES_PATH = os.environ.get("XHS_STYLE_SESSION_RESPONSES_PATH", "").strip()
MODEL_ID = "gpt-5.6-sol"
BATCH_SIZE = 4

sys.path.insert(0, str(TACHIKOMA_ROOT))

from base import llm  # noqa: E402
from base.xiaohongshu_style import (  # noqa: E402
    DRAFT_PROMPT_VERSION,
    PLAN_PROMPT_VERSION,
    REVIEW_PROMPT_VERSION,
    ProviderCallResult,
    SemanticReviewResponse,
    StyleWritingRequest,
    XiaohongshuDraft,
    XiaohongshuPlan,
    _draft_prompt,
    _format_checks,
    _plan_prompt,
    _quality_request,
    _review_prompt,
    _validate_plan_constraints,
    _validate_semantic_review_constraints,
    generate_style_content,
    prepare_style_bundle,
)
from chatgpt_mcp.style_cards import AccessContext, StyleCardStore  # noqa: E402
from chatgpt_mcp.style_naturalness import evaluate_naturalness  # noqa: E402
from chatgpt_mcp.style_quality import evaluate_quality  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Path) -> str:
    """Keep metadata readable when an acceptance artifact lives in Tachikoma .tmp."""
    try:
        return str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path)


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def strip_json_fence(value: str) -> str:
    raw = (value or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].strip().casefold() in {"```", "```json"}:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    return raw


def write_stage_schema(stage: str) -> Path:
    stage_key = stage.split(".", 1)[0]
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["request_id", "response_json"],
                    "properties": {
                        "request_id": {"type": "string"},
                        "response_json": {"type": "string"},
                    },
                },
            }
        },
    }
    path = CACHE_PATH.parent / f"{stage_key}.batch-output.schema.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"schema_version": 1, "model_id": MODEL_ID, "stages": {}}
    cache = read_json(CACHE_PATH)
    if cache.get("model_id") != MODEL_ID:
        raise RuntimeError("provider cache model_id drift")
    return cache


def save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_session_responses() -> dict[str, Any] | None:
    """Load stage outputs produced by the exact current Codex session.

    The desktop package executable cannot always be spawned from a child Python
    process on Windows (WinError 5).  This explicit input keeps the same
    production validation/replay pipeline while recording the truthful model
    execution surface instead of pretending the CLI call succeeded.
    """
    if not SESSION_RESPONSES_PATH:
        return None
    payload = read_json(Path(SESSION_RESPONSES_PATH))
    if payload.get("provider") != "codex.current_session":
        raise RuntimeError("session response provider must be codex.current_session")
    if payload.get("model_id") != MODEL_ID:
        raise RuntimeError("session response model_id drift")
    if not payload.get("model_selection_evidence"):
        raise RuntimeError("session response model evidence is required")
    return payload


def inject_session_stage(
    *,
    stage: str,
    jobs: list[dict[str, str]],
    cache: dict[str, Any],
    session_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if session_payload is None:
        return []
    stage_payload = session_payload.get("stages", {}).get(stage)
    if not isinstance(stage_payload, dict):
        raise RuntimeError(f"session responses omitted stage {stage}")
    expected_ids = [job["request_id"] for job in jobs]
    if set(stage_payload) != set(expected_ids):
        raise RuntimeError(f"session responses {stage} request ids drift")
    completed_at = session_payload.get("completed_at") or utc_now()
    entries = cache.setdefault("stages", {}).setdefault(stage, {})
    for job in jobs:
        request_id = job["request_id"]
        input_sha = sha256_text(job["system"] + "\n" + job["prompt"])
        entries[request_id] = {
            "input_sha256": input_sha,
            "response": stage_payload[request_id],
            "receipt": {
                "stage": stage,
                "provider": "codex.current_session",
                "model_id": MODEL_ID,
                "model_selection_evidence": session_payload[
                    "model_selection_evidence"
                ],
                "fallback_model_allowed": False,
                "ephemeral": True,
                "sandbox": "none",
                "api_key_removed": True,
                "started_at": session_payload.get("started_at") or completed_at,
                "completed_at": completed_at,
                "prompt_sha256": input_sha,
            },
        }
    save_cache(cache)
    return [
        {
            "stage": stage,
            "provider": "codex.current_session",
            "model_id": MODEL_ID,
            "model_selection_evidence": session_payload[
                "model_selection_evidence"
            ],
            "fallback_model_allowed": False,
            "completed_at": completed_at,
            "request_count": len(jobs),
        }
    ]


def call_exact_model(
    *,
    stage: str,
    system: str,
    prompt: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started_at = utc_now()
    result = llm.codex_cli_generate(
        prompt,
        system=system,
        model=MODEL_ID,
        output_schema=str(write_stage_schema(stage)),
    )
    if not result.ok or not result.text:
        raise RuntimeError(f"{stage} exact-model call failed: {result.note}")
    if result.model != MODEL_ID:
        raise RuntimeError(
            f"{stage} exact-model receipt mismatch: {result.model!r}"
        )
    try:
        response = json.loads(strip_json_fence(result.text))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{stage} returned invalid JSON: {exc}") from exc
    if not isinstance(response, dict):
        raise RuntimeError(f"{stage} response must be one JSON object")
    receipt = {
        "stage": stage,
        "provider": "tachikoma.codex_subscription",
        "model_id": result.model,
        "model_selection_evidence": "explicit_cli_--model_argument",
        "fallback_model_allowed": False,
        "ephemeral": True,
        "sandbox": "read-only",
        "api_key_removed": True,
        "started_at": started_at,
        "completed_at": utc_now(),
        "prompt_sha256": sha256_text(system + "\n" + prompt),
    }
    return response, receipt


def batch_prompt(stage: str, jobs: list[dict[str, str]]) -> str:
    return (
        "You are executing a controlled offline writing experiment. Do not use "
        "tools, browse, inspect files, or add commentary. For every job below, "
        "follow its complete stage prompt independently. Return exactly one JSON "
        "object shaped as {\"items\":[{\"request_id\":str,\"response_json\":str}]}. "
        "response_json must itself be a complete JSON-encoded string containing "
        "the requested stage response object. "
        "Return every request_id exactly once and keep the same order. The "
        "response must be strict JSON: inside string values use Chinese quotation "
        "marks 「」 instead of unescaped ASCII double quotes. "
        f"current stage is {stage}.\n<jobs>"
        + stable_json(jobs)
        + "</jobs>"
    )


def cache_key(stage: str, request_id: str) -> str:
    return f"{stage}:{request_id}"


def generate_batches(
    *,
    stage: str,
    jobs: list[dict[str, str]],
    cache: dict[str, Any],
) -> list[dict[str, Any]]:
    entries = cache.setdefault("stages", {}).setdefault(stage, {})
    receipts: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    systems: dict[str, str] = {}
    for job in jobs:
        # Two requests can share an interaction mode while carrying different
        # immutable style bundles or selected examples.  They must never be sent
        # under the first request's system contract.
        group_key = f"{job['group']}:{sha256_text(job['system'])}"
        systems.setdefault(group_key, job["system"])
        grouped[group_key].append(job)

    for group_key, same_system_jobs in grouped.items():
        shared_system = systems[group_key]
        for offset in range(0, len(same_system_jobs), BATCH_SIZE):
            chunk = same_system_jobs[offset : offset + BATCH_SIZE]
            missing = []
            for job in chunk:
                input_sha = sha256_text(shared_system + "\n" + job["prompt"])
                cached = entries.get(job["request_id"])
                # Reuse only an exact stage prompt. Request IDs are stable across
                # experiment revisions, so ID-only reuse can silently replay an
                # older source, policy, plan or approved-example selection.
                if not cached or cached.get("input_sha256") != input_sha:
                    missing.append(job)
            if not missing:
                continue
            wire_jobs = [
                {"request_id": job["request_id"], "prompt": job["prompt"]}
                for job in missing
            ]
            response, receipt = call_exact_model(
                stage=stage,
                system=shared_system,
                prompt=batch_prompt(stage, wire_jobs),
            )
            items = response.get("items")
            if not isinstance(items, list):
                raise RuntimeError(f"{stage} batch omitted items[]")
            by_id = {}
            for response_item in items:
                if not isinstance(response_item, dict):
                    continue
                request_id = str(response_item.get("request_id"))
                if "response_json" in response_item:
                    try:
                        stage_response = json.loads(
                            strip_json_fence(str(response_item["response_json"]))
                        )
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            f"{stage} {request_id} response_json is invalid: {exc}"
                        ) from exc
                else:
                    stage_response = response_item.get("response")
                if not isinstance(stage_response, dict):
                    raise RuntimeError(
                        f"{stage} {request_id} response must be one object"
                    )
                by_id[request_id] = stage_response
            expected = [job["request_id"] for job in missing]
            if set(by_id) != set(expected):
                raise RuntimeError(
                    f"{stage} batch IDs mismatch: expected={expected}, "
                    f"observed={sorted(by_id)}"
                )
            receipt["request_ids"] = expected
            receipt["batch_size"] = len(expected)
            receipts.append(receipt)
            for job in missing:
                input_sha = sha256_text(shared_system + "\n" + job["prompt"])
                entries[job["request_id"]] = {
                    "input_sha256": input_sha,
                    "response": by_id[job["request_id"]],
                    "receipt": receipt,
                }
            save_cache(cache)
            print(f"{stage}: generated {len(expected)} ({expected[0]}..{expected[-1]})")
    return receipts


def repair_one(
    *,
    stage: str,
    request_id: str,
    system: str,
    prompt: str,
    error: str,
    cache: dict[str, Any],
) -> dict[str, Any]:
    repair_prompt = (
        prompt
        + "\nThe previous response failed local validation. Return one corrected "
        "stage response JSON object only.\n<local_validation_error>"
        + error[:4_000]
        + "</local_validation_error>"
    )
    response, receipt = call_exact_model(
        stage=f"{stage}.repair",
        system=system,
        prompt=repair_prompt,
    )
    # call_exact_model uses the same constrained batch envelope for both batch
    # and repair calls. A repair prompt asks for one stage object, but the JSON
    # schema can therefore legitimately wrap it as items[0].response_json.
    # Normalize that wire shape before persisting and validating the repair.
    if "items" in response:
        items = response.get("items")
        if not isinstance(items, list) or len(items) != 1:
            raise RuntimeError(
                f"{stage} repair must return exactly one envelope item"
            )
        item = items[0]
        if not isinstance(item, dict) or "response_json" not in item:
            raise RuntimeError(
                f"{stage} repair envelope omitted response_json"
            )
        try:
            response = json.loads(strip_json_fence(str(item["response_json"])))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{stage} repair response_json is invalid: {exc}"
            ) from exc
        if not isinstance(response, dict):
            raise RuntimeError(f"{stage} repair response must be one object")
    input_sha = sha256_text(system + "\n" + prompt)
    cache.setdefault("stages", {}).setdefault(stage, {})[request_id] = {
        "input_sha256": input_sha,
        "response": response,
        "receipt": receipt,
    }
    dependent_stages = {
        "plan": ("draft", "semantic_review"),
        "draft": ("semantic_review",),
    }
    for dependent_stage in dependent_stages.get(stage, ()):
        cache.setdefault("stages", {}).setdefault(dependent_stage, {}).pop(
            request_id,
            None,
        )
    save_cache(cache)
    print(f"{stage}: repaired {request_id}")
    return response


def validate_with_repair(
    *,
    stage: str,
    jobs: list[dict[str, str]],
    cache: dict[str, Any],
    validator: Callable[[str, dict[str, Any]], Any],
) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    entries = cache["stages"][stage]
    for job in jobs:
        request_id = job["request_id"]
        response = entries[request_id]["response"]
        last_error = ""
        for attempt in range(3):
            try:
                parsed[request_id] = validator(request_id, response)
                break
            except Exception as exc:  # local contract determines repair text
                last_error = str(exc)
                if attempt == 2:
                    raise RuntimeError(
                        f"{request_id} {stage} failed after repairs: {last_error}"
                    ) from exc
                response = repair_one(
                    stage=stage,
                    request_id=request_id,
                    system=job["system"],
                    prompt=job["prompt"],
                    error=last_error,
                    cache=cache,
                )
    return parsed


class ReplayProvider:
    def __init__(
        self,
        request_id: str,
        stage_payloads: dict[str, dict[str, Any]],
        stage_entries: dict[str, dict[str, Any]],
    ) -> None:
        self.request_id = request_id
        self.stage_payloads = stage_payloads
        self.stage_entries = stage_entries

    def generate(
        self,
        *,
        system: str,
        prompt: str,
        stage: str,
        prompt_version: str,
    ) -> ProviderCallResult:
        if prompt_version.endswith((".repair1", ".length1")):
            raise RuntimeError(
                f"unexpected replay repair for {self.request_id}: {prompt_version}"
            )
        payload = self.stage_payloads[stage][self.request_id]
        entry = self.stage_entries[stage][self.request_id]
        observed_at = entry["receipt"]["completed_at"].replace("Z", "+00:00")
        return ProviderCallResult(
            text=stable_json(payload),
            provider=str(entry["receipt"]["provider"]),
            model_id=MODEL_ID,
            ok=True,
            observed_at=observed_at,
            note="replayed exact-model batch response through production pipeline",
        )


def main() -> int:
    requests_payload = read_json(REQUESTS_PATH)
    compile_payload = read_json(COMPILE_PATH)
    if compile_payload["required_model_id"] != MODEL_ID:
        raise RuntimeError("compile receipt model mismatch")
    if compile_payload["fallback_model_allowed"]:
        raise RuntimeError("compile receipt unexpectedly allows fallback")

    store = StyleCardStore()
    context = AccessContext.service_admin()
    requests: dict[str, StyleWritingRequest] = {}
    bundles: dict[str, dict[str, Any]] = {}
    instructions: dict[str, str] = {}
    for item in requests_payload["requests"]:
        request = StyleWritingRequest.model_validate(item["style_request"])
        if request.required_model_id != MODEL_ID or request.fallback_model_allowed:
            raise RuntimeError(f"{request.request_id}: provider contract drift")
        bundle, instruction = prepare_style_bundle(
            request,
            store=store,
            context=context,
        )
        requests[request.request_id] = request
        bundles[request.request_id] = bundle
        instructions[request.request_id] = instruction

    cache = load_cache()
    session_payload = load_session_responses()
    plan_jobs = []
    for request_id, request in requests.items():
        system, prompt = _plan_prompt(request, instructions[request_id])
        plan_jobs.append(
            {
                "request_id": request_id,
                "group": str(request.interaction_mode),
                "system": system,
                "prompt": prompt,
            }
        )
    batch_receipts = inject_session_stage(
        stage="plan",
        jobs=plan_jobs,
        cache=cache,
        session_payload=session_payload,
    )
    batch_receipts += generate_batches(
        stage="plan", jobs=plan_jobs, cache=cache
    )

    def validate_plan(request_id: str, value: dict[str, Any]) -> XiaohongshuPlan:
        plan = XiaohongshuPlan.model_validate(value)
        _validate_plan_constraints(requests[request_id], plan)
        return plan

    plans = validate_with_repair(
        stage="plan",
        jobs=plan_jobs,
        cache=cache,
        validator=validate_plan,
    )

    draft_jobs = []
    for request_id, request in requests.items():
        system, prompt = _draft_prompt(
            request,
            instructions[request_id],
            plans[request_id],
        )
        draft_jobs.append(
            {
                "request_id": request_id,
                "group": str(request.interaction_mode),
                "system": system,
                "prompt": prompt,
            }
        )
    batch_receipts += inject_session_stage(
        stage="draft",
        jobs=draft_jobs,
        cache=cache,
        session_payload=session_payload,
    )
    batch_receipts += generate_batches(
        stage="draft", jobs=draft_jobs, cache=cache
    )

    def validate_draft(request_id: str, value: dict[str, Any]) -> XiaohongshuDraft:
        request = requests[request_id]
        draft = XiaohongshuDraft.model_validate(value)
        format_checks = _format_checks(request, draft)
        naturalness = evaluate_naturalness(
            draft.draft_text,
            artifact_type=request.artifact_type,
            register_contract=bundles[request_id]["style_instructions"][
                "register_contract"
            ],
            interaction_mode=request.interaction_mode,
        )
        quality = evaluate_quality(
            _quality_request(request, bundles[request_id], draft, [])
        )
        errors = []
        if not format_checks["all_passed"]:
            errors.append("format=" + stable_json(format_checks))
        if naturalness["repair_required"]:
            errors.append("naturalness=" + stable_json(naturalness))
        if quality["hard_failures"]:
            errors.append("hard_gates=" + stable_json(quality["hard_failures"]))
        if errors:
            raise ValueError("; ".join(errors))
        return draft

    drafts = validate_with_repair(
        stage="draft",
        jobs=draft_jobs,
        cache=cache,
        validator=validate_draft,
    )

    review_jobs = []
    for request_id, request in requests.items():
        system, prompt = _review_prompt(
            request,
            instructions[request_id],
            plans[request_id],
            drafts[request_id],
        )
        review_jobs.append(
            {
                "request_id": request_id,
                "group": str(request.interaction_mode),
                "system": system,
                "prompt": prompt,
            }
        )
    batch_receipts += inject_session_stage(
        stage="semantic_review",
        jobs=review_jobs,
        cache=cache,
        session_payload=session_payload,
    )
    batch_receipts += generate_batches(
        stage="semantic_review", jobs=review_jobs, cache=cache
    )

    def validate_review(
        request_id: str, value: dict[str, Any]
    ) -> SemanticReviewResponse:
        review = SemanticReviewResponse.model_validate(value)
        _validate_semantic_review_constraints(requests[request_id], review)
        return review

    reviews = validate_with_repair(
        stage="semantic_review",
        jobs=review_jobs,
        cache=cache,
        validator=validate_review,
    )

    stage_payloads = {
        "plan": {key: value.model_dump(mode="json") for key, value in plans.items()},
        "draft": {
            key: value.model_dump(mode="json") for key, value in drafts.items()
        },
        "semantic_review": {
            key: value.model_dump(mode="json") for key, value in reviews.items()
        },
    }
    items = []
    item_by_request = {
        item["style_request"]["request_id"]: item
        for item in requests_payload["requests"]
    }
    for request_id, request in requests.items():
        provider = ReplayProvider(
            request_id,
            stage_payloads,
            cache["stages"],
        )
        result = generate_style_content(
            request,
            provider=provider,
            store=store,
            context=context,
        )
        if result["status"] != "review_required":
            raise RuntimeError(
                f"{request_id}: replay pipeline status={result['status']}"
            )
        source_item = item_by_request[request_id]
        items.append(
            {
                "experiment_id": source_item["experiment_id"],
                "request_id": request_id,
                "interaction_mode": request.interaction_mode,
                "draft_text": result["draft"]["draft_text"],
                "plan": result["plan"],
                "semantic_review": stage_payloads["semantic_review"][request_id],
                "pipeline_result": result,
                "publish_allowed": False,
            }
        )

    payload = {
        "schema_version": 2,
        "project": "panse_xiaohongshu",
        "generated_at": utc_now(),
        "scope": "local_research_only",
        "source_requests": display_path(REQUESTS_PATH),
        "source_compile_receipts": display_path(COMPILE_PATH),
        "provider_contract": {
            "provider": (
                "codex.current_session"
                if session_payload is not None
                else "tachikoma.codex_subscription"
            ),
            "required_model_id": MODEL_ID,
            "required_model_match": "exact",
            "model_selection_evidence": (
                session_payload["model_selection_evidence"]
                if session_payload is not None
                else "explicit_cli_--model_argument"
            ),
            "stages": ["plan", "draft", "semantic_review"],
            "fallback_model_allowed": False,
            "ephemeral": True,
            "sandbox": "read-only",
            "api_key_removed": True,
        },
        "request_count": len(items),
        "completed_pipeline_count": len(items),
        "new_batch_receipts": batch_receipts,
        "items": items,
        "human_review_required": True,
        "publish_allowed": False,
        "network_access_performed": True,
        "external_posting_performed": False,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output_path": display_path(OUTPUT_PATH),
                "request_count": len(items),
                "completed_pipeline_count": len(items),
                "required_model_id": MODEL_ID,
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
