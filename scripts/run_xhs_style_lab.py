#!/usr/bin/env python3
"""Run the real Tachikoma Writing Style Lab for one governed XHS comment.

This is the production drafting entrypoint. It performs no browser or platform
action and always keeps publish_allowed=false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.xhs_comment_production_taxonomy import apply_taxonomy_to_brief
from lib.xhs_comment_length_mix import (
    LENGTH_MIX_MARKER,
    apply_length_assignment_to_request,
    build_length_assignment,
    load_length_mix_policy,
    validate_generated_comment_length,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PREPARE_SCRIPT = REPO_ROOT / "scripts" / "prepare_xhs_style_request.py"
CONTRACT_PATH = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_reply_style_contract_v3.json"
)
REQUIRED_PROVIDER = "tachikoma.codex_subscription"
REQUIRED_MODEL = "gpt-5.6-sol"
REQUIRED_STAGES = ("plan", "draft", "semantic_review")
OFFICIAL_VOICE = "official_explanation"
OFFICIAL_GOVERNANCE_MARKER = "<panse_official_governance>"
PUBLIC_COMMENT_POLICY_MARKER = "<panse_public_comment_text_policy>"
PUBLIC_COMMENT_TEXT_POLICY_ID = "panse-xhs-public-comment-text.v1"
FORBIDDEN_COMMENT_LITERAL_TERMS = ("畔色木作",)
FORBIDDEN_COMMENT_OPENING_RE = re.compile(
    r"^\s*(?:"
    r"官方\s*(?:想追问(?:一下)?|补充(?:一句|一下)|提醒(?:一句|一下))"
    r"|补充(?:一句|一下)"
    r"|提醒(?:一句|一下)"
    r")(?:[，,：:。！？!?、\s]|$)"
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected one JSON object: {path}")
    return value


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def validate_preflight_governance(value: dict[str, Any]) -> str:
    """Require the policy contract that governs the declared account voice."""
    voice_id = str(value.get("voice_id", "")).strip()
    if voice_id == OFFICIAL_VOICE:
        if value.get("production_taxonomy_verified") is not False:
            raise RuntimeError(
                "official brand voice must not use the nonofficial production taxonomy"
            )
        if value.get("production_contract") is not None:
            raise RuntimeError(
                "official brand voice unexpectedly received a nonofficial production contract"
            )
        topic_strategy_id = str(
            value.get("official_topic_strategy_id", "")
        ).strip()
        topic_context = value.get("official_topic_context")
        if (
            not topic_strategy_id
            or not isinstance(topic_context, dict)
            or topic_context.get("strategy_id") != topic_strategy_id
        ):
            raise RuntimeError(
                "official brand voice requires a verified official topic contract"
            )
        professional_contract_id = str(
            value.get("official_professional_value_contract_id", "")
        ).strip()
        professional_context = value.get("official_professional_value_context")
        if (
            not professional_contract_id
            or not isinstance(professional_context, dict)
            or professional_context.get("contract_id")
            != professional_contract_id
        ):
            raise RuntimeError(
                "official brand voice requires a verified professional-value contract"
            )
        return "official"

    if value.get("production_taxonomy_verified") is not True:
        raise RuntimeError(
            "future nonofficial production drafts require a verified production_category_id"
        )
    if not isinstance(value.get("production_contract"), dict):
        raise RuntimeError("verified nonofficial production contract is missing")
    return "nonofficial"


def apply_official_governance_to_brief(
    request_payload: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    """Bind validated official topic and professional value into the transient brief."""
    payload = dict(request_payload)
    brief = str(payload.get("brief_text", ""))
    if OFFICIAL_GOVERNANCE_MARKER in brief:
        raise ValueError("official governance contract was already injected")
    block = {
        "official_topic_strategy_id": preflight["official_topic_strategy_id"],
        "official_topic_context": preflight["official_topic_context"],
        "official_professional_value_contract_id": preflight[
            "official_professional_value_contract_id"
        ],
        "official_professional_value_context": preflight[
            "official_professional_value_context"
        ],
        "generation_instruction": (
            "以品牌官方身份作答；先依据已验证的专业理由，再给判断、条件化建议或短夸；"
            "不得伪装消费者，不得推广或扩写超出当前来源的事实。"
        ),
    }
    payload["brief_text"] = (
        brief.rstrip()
        + "\n\n"
        + OFFICIAL_GOVERNANCE_MARKER
        + json.dumps(block, ensure_ascii=False, sort_keys=True)
        + "</panse_official_governance>"
    )
    return payload


def apply_public_comment_text_policy_to_brief(
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    """Tell every comment route about the deterministic final-text gate."""
    payload = dict(request_payload)
    brief = str(payload.get("brief_text", ""))
    if PUBLIC_COMMENT_POLICY_MARKER in brief:
        raise ValueError("public comment text policy was already injected")
    block = {
        "policy_id": PUBLIC_COMMENT_TEXT_POLICY_ID,
        "forbidden_literal_terms": list(FORBIDDEN_COMMENT_LITERAL_TERMS),
        "forbidden_opening_examples": [
            "官方想追问",
            "官方补充一句",
            "官方提醒一句",
            "补充一句",
            "提醒一句",
        ],
        "generation_instruction": (
            "评论正文不要直接写品牌全名；不要使用身份播报、总结式或助手式模板开场；"
            "表达要口语、直接。最终草稿还会经过程序确定性校验，命中即拒绝进入人工审核。"
        ),
    }
    payload["brief_text"] = (
        brief.rstrip()
        + "\n\n"
        + PUBLIC_COMMENT_POLICY_MARKER
        + json.dumps(block, ensure_ascii=False, sort_keys=True)
        + "</panse_public_comment_text_policy>"
    )
    return payload


def compile_project_preflight(request_path: Path) -> dict[str, Any]:
    process = subprocess.run(
        [sys.executable, str(PREPARE_SCRIPT), str(request_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if process.returncode != 0:
        message = process.stderr.strip() or process.stdout.strip()
        raise RuntimeError(f"Style Lab project preflight failed: {message}")
    value = json.loads(process.stdout)
    if value.get("passed") is not True:
        raise RuntimeError("Style Lab project preflight did not pass")
    if value.get("text_generated") is not False:
        raise RuntimeError("compile receipt unexpectedly claims text generation")
    validate_preflight_governance(value)
    return value


def build_runtime_request_payload(
    raw: dict[str, Any],
    preflight: dict[str, Any],
    length_assignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = dict(raw)
    length_context = payload.pop("panse_comment_length_context", None)
    active_policy = load_length_mix_policy()
    computed_assignment = build_length_assignment(length_context, active_policy)
    if length_assignment is not None and length_assignment != computed_assignment:
        raise RuntimeError("runtime comment length assignment drifted before generation")
    length_assignment = computed_assignment
    if preflight.get("comment_length_mix") != length_assignment:
        raise RuntimeError("Style Lab preflight and runtime length assignments differ")
    intent = payload.pop("panse_intent_context", None)
    if not isinstance(intent, dict):
        raise ValueError("panse_intent_context is required")
    payload.pop("panse_official_topic_context", None)
    payload.pop("panse_official_professional_value_context", None)
    governance_mode = validate_preflight_governance(preflight)
    if governance_mode == "official":
        payload = apply_official_governance_to_brief(payload, preflight)
    else:
        payload = apply_taxonomy_to_brief(payload, preflight["production_contract"])
        payload["comment_intent_context"] = {
            "intent_policy_version": preflight["intent_policy_version"],
            "topic_ids": preflight["topic_ids"],
            "interaction_intent": preflight["interaction_intent"],
            "comment_direction_id": preflight["comment_direction_id"],
            "voice_id": preflight["voice_id"],
            "human_approved_example_set_version": preflight[
                "human_approved_example_set_version"
            ],
            "length_policy_id": length_assignment["policy_id"],
            "length_tier_id": length_assignment["tier_id"],
            "length_override_contract_id": (
                "panse-xhs-role-scoped-comment-length.v1"
                if preflight["direction_contract"].get(
                    "length_tier_override_applied"
                ) is True
                else None
            ),
            "global_case_boundary_verified": preflight.get(
                "global_case_boundary_verified", False
            ),
        }
    payload = apply_public_comment_text_policy_to_brief(payload)
    direction_range = preflight["direction_contract"]["character_range"]
    output = payload.setdefault("output", {})
    output["body_min_chars"] = max(
        int(output.get("body_min_chars", 1)),
        int(direction_range["minimum"]),
    )
    output["body_max_chars"] = min(
        int(output.get("body_max_chars", 20_000)),
        int(direction_range["maximum"]),
    )
    payload = apply_length_assignment_to_request(
        payload,
        length_assignment,
    )
    payload["required_model_id"] = REQUIRED_MODEL
    payload["fallback_model_allowed"] = False
    if payload.get("style_requirement") != "approved_required":
        raise ValueError(
            "production comments require approved Style Cards; taxonomy fallback is forbidden"
        )
    return payload


def verify_public_comment_text(result: dict[str, Any]) -> dict[str, Any]:
    """Fail closed before a generated comment can enter human review."""
    draft = result.get("draft")
    if not isinstance(draft, dict):
        raise ValueError("Style Lab result is missing the generated draft")
    draft_text = draft.get("draft_text")
    if not isinstance(draft_text, str) or not draft_text.strip():
        raise ValueError("Style Lab result has an empty generated draft")
    matched_terms = [
        term for term in FORBIDDEN_COMMENT_LITERAL_TERMS if term in draft_text
    ]
    if matched_terms:
        raise ValueError(
            "public comment text policy rejected a literal brand name: "
            + ", ".join(matched_terms)
        )
    opening_match = FORBIDDEN_COMMENT_OPENING_RE.match(draft_text)
    if opening_match:
        raise ValueError(
            "public comment text policy rejected a template opening: "
            + opening_match.group(0).strip()
        )
    return {
        "policy_id": PUBLIC_COMMENT_TEXT_POLICY_ID,
        "public_comment_text_policy_verified": True,
        "forbidden_literal_terms_absent": True,
        "template_opening_absent": True,
    }


def verify_actual_run(
    result: dict[str, Any],
    length_assignment: dict[str, Any] | None = None,
    effective_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    traces = result.get("provider_runs")
    if not isinstance(traces, list):
        raise ValueError("Style Lab result is missing provider_runs")
    successful = [item for item in traces if item.get("ok") is True]
    seen_stages = [item.get("stage") for item in successful]
    missing = [stage for stage in REQUIRED_STAGES if stage not in seen_stages]
    if missing:
        raise ValueError("Style Lab stages did not complete: " + ", ".join(missing))
    first_positions = [seen_stages.index(stage) for stage in REQUIRED_STAGES]
    if first_positions != sorted(first_positions):
        raise ValueError("Style Lab stages did not run in the required order")
    if any(item.get("provider") != REQUIRED_PROVIDER for item in traces):
        raise ValueError("one or more stages lack the real Codex provider receipt")
    if any(item.get("model_id") != REQUIRED_MODEL for item in traces):
        raise ValueError("one or more stages used the wrong model")
    provider_contract = result.get("provider_contract", {})
    if provider_contract.get("required_model_id") != REQUIRED_MODEL:
        raise ValueError("result provider contract does not pin the required model")
    if provider_contract.get("fallback_model_allowed") is not False:
        raise ValueError("result provider contract does not disable fallback")
    if result.get("delivery_ready_for_human_review") is not True:
        raise ValueError("Style Lab did not clear delivery for human review")
    if result.get("publish_allowed") is not False:
        raise ValueError("Style Lab result must keep publish_allowed=false")
    if any(result.get("side_effects", {}).values()):
        raise ValueError("Style Lab drafting must not perform side effects")
    text_policy = verify_public_comment_text(result)
    length_verification = None
    if length_assignment is not None:
        length_verification = validate_generated_comment_length(
            result["draft"]["draft_text"],
            length_assignment,
            effective_output,
        )
    return {
        "actual_style_lab_run_verified": True,
        "provider": REQUIRED_PROVIDER,
        "model_id": REQUIRED_MODEL,
        "fallback_used": False,
        "completed_stages": list(REQUIRED_STAGES),
        "delivery_ready_for_human_review": True,
        "publish_allowed": False,
        "public_comment_text_policy": text_policy,
        "comment_length_mix": length_verification,
    }


def load_runtime() -> tuple[type[Any], Any, str]:
    contract = load_json(CONTRACT_PATH)
    runtime_root = str(Path(contract["style_lab"]["runtime_root"]).resolve())
    style_card_db = str(Path(contract["style_lab"]["style_card_db"]).resolve())
    if not Path(style_card_db).is_file():
        raise FileNotFoundError(f"Style Card database not found: {style_card_db}")
    os.environ["TK_STYLE_CARD_DB"] = style_card_db
    if runtime_root not in sys.path:
        sys.path.insert(0, runtime_root)
    from base.xiaohongshu_style import (  # pylint: disable=import-outside-toplevel
        StyleWritingRequest,
        generate_style_content,
    )

    return StyleWritingRequest, generate_style_content, runtime_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("request_path", nargs="?", help="one governed request JSON")
    parser.add_argument("--output", help="write the body-free run receipt JSON here")
    parser.add_argument(
        "--check-runtime",
        action="store_true",
        help="verify the real runtime entrypoint without invoking the model",
    )
    args = parser.parse_args()

    request_model, generate_style_content, runtime_root = load_runtime()
    length_mix_policy = load_length_mix_policy()
    if args.check_runtime:
        print(
            json.dumps(
                {
                    "passed": True,
                    "runtime_root": runtime_root,
                    "runtime_function": "base.xiaohongshu_style.generate_style_content",
                    "required_provider": REQUIRED_PROVIDER,
                    "required_model_id": REQUIRED_MODEL,
                    "fallback_model_allowed": False,
                    "public_comment_text_policy_id": PUBLIC_COMMENT_TEXT_POLICY_ID,
                    "deterministic_comment_text_gate_enabled": True,
                    "comment_length_mix_policy_id": length_mix_policy["policy_id"],
                    "comment_length_mix_marker": LENGTH_MIX_MARKER,
                    "comment_length_mix_gate_enabled": True,
                    "model_invoked": False,
                    "external_action_performed": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if not args.request_path:
        parser.error("request_path is required unless --check-runtime is used")

    request_path = Path(args.request_path).resolve()
    raw = load_json(request_path)
    request_input_sha256 = hashlib.sha256(
        json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    preflight = compile_project_preflight(request_path)
    length_assignment = build_length_assignment(
        raw.get("panse_comment_length_context"),
        length_mix_policy,
    )
    runtime_payload = build_runtime_request_payload(
        raw,
        preflight,
        length_assignment,
    )
    request = request_model.model_validate(runtime_payload)
    result = generate_style_content(request)
    verification = verify_actual_run(
        result,
        length_assignment,
        runtime_payload.get("output"),
    )
    receipt = {
        "schema_version": 1,
        "receipt_type": "panse_xhs_actual_style_lab_run",
        "request_id": request.request_id,
        "contract_version": "xhs-reply-style-contract.v3-r10",
        "candidate_input_sha256": request_input_sha256,
        "observed_at": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "production_contract": preflight["production_contract"],
        "compile_receipt": preflight,
        "comment_length_mix": length_assignment,
        "execution_verification": verification,
        "style_lab_result": result,
        "human_review_required": True,
        "external_posting_performed": False,
    }
    if args.output:
        write_json_atomic(Path(args.output).resolve(), receipt)
        print(
            json.dumps(
                {
                    "passed": True,
                    "request_id": request.request_id,
                    "actual_style_lab_run_verified": True,
                    "draft_text": result["draft"]["draft_text"],
                    "output": str(Path(args.output).resolve()),
                    "publish_allowed": False,
                    "comment_length_mix_gate_passed": True,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
