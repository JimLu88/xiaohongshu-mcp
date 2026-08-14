r"""Build one private owner-review packet for the 30-context XHS pilot.

The user explicitly replaced the A/B independent-review workflow for this
pilot with a single owner review.  Complete context and review UI remain under
``D:\AI\tachikoma\.tmp``.  The repository manifest is hash-only.  This script
does not generate comments, access the network, publish, or approve anything.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_xhs_full_context_blind_pilot_v2 import (
    DEFAULT_PRIVATE_QUEUE,
    PRIVATE_ROOT,
    TARGET_REAL_CONTEXTS,
    _atomic_write,
    _json_bytes,
    _sha256,
    build as build_v2,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OWNER_JSON = PRIVATE_ROOT / "xhs-full-context-owner-review-v3.json"
DEFAULT_OWNER_HTML = PRIVATE_ROOT / "xhs-full-context-owner-review-v3.html"
DEFAULT_OWNER_EXPORT = PRIVATE_ROOT / "xhs-full-context-owner-review-v3.completed.json"
DEFAULT_IN_PROGRESS_EXPORT = (
    PRIVATE_ROOT / "xhs-full-context-owner-review-v3.in-progress.json"
)
DEFAULT_RECOVERED_NOTES = (
    PRIVATE_ROOT / "xhs-owner-review-notes-recovered-2026-08-14.json"
)
DEFAULT_OWNER_ADJUDICATION = (
    PRIVATE_ROOT / "xhs-owner-review-adjudication-2026-08-14.json"
)
DEFAULT_PROVENANCE = PRIVATE_ROOT / "xhs-full-context-selection-provenance-v3.json"
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_full_context_owner_review_manifest_v3.json"
)

DIMENSION_LABELS = {
    "source_grounded": "内容有上下文依据",
    "speaking_position_correct": "说话身份和位置恰当",
    "speech_act_fit": "表达目的符合互动场景",
    "teacher_or_judge_posture_absent": "没有老师或评委口吻",
    "source_restatement_absent": "没有复述原文或图片",
    "fabricated_firsthand_absent": "没有虚构亲身经历",
    "question_still_unanswered": "如有提问，问题尚未被回答",
    "ordinary_order_and_logic": "语序和逻辑自然",
    "protected_spans_preserved": "数字、名称等受保护内容准确",
    "near_copy_safe": "没有近似照搬风险",
}

HARD_FAILURE_DIMENSIONS = {
    "source_grounded",
    "fabricated_firsthand_absent",
    "protected_spans_preserved",
    "near_copy_safe",
}


def build_owner() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    packet_a, _, queue, provenance_v2, source_manifest = build_v2(
        TARGET_REAL_CONTEXTS,
        include_verified_published=True,
    )
    created_at = datetime.now(timezone.utc).isoformat()
    items: list[dict[str, Any]] = []
    for index, item in enumerate(packet_a["items"], start=1):
        owner_item = dict(item)
        owner_item.pop("blind_id", None)
        owner_item["owner_item_id"] = f"审核项-{index:02d}"
        items.append(owner_item)
    owner_packet = {
        "schema_version": "xhs-full-context-owner-review/v3",
        "created_at": created_at,
        "review_policy": {
            "reviewer_role": "owner",
            "required_reviewer_count": 1,
            "independent_review_required": False,
            "override_scope": "xhs-30-context-pilot-2026-08-14-only",
            "override_source": "current_user_instruction",
            "does_not_modify_other_contract_approval_rules": True,
        },
        "instructions": {
            "review_each_dimension_separately": True,
            "aggregate_score_forbidden": True,
            "publication_status_hidden_from_review_items": True,
            "prior_publication_is_not_style_approval": True,
            "status_flag_only_is_not_verified_publication": True,
            "owner_decision_values": ["accept", "revise", "reject"],
            "dimension_values": ["pass", "fail", "not_applicable"],
        },
        "items": items,
        "reversal_controls": packet_a["reversal_controls"],
        "owner_review_completed": False,
        "r3_status": "awaiting_owner_review",
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
        "publish_allowed": False,
    }
    provenance = dict(provenance_v2)
    provenance["schema_version"] = "xhs-full-context-selection-provenance/v3"
    provenance["created_at"] = created_at
    provenance["review_policy"] = owner_packet["review_policy"]
    manifest = {
        "schema_version": "xhs-full-context-owner-review-manifest/v3",
        "created_at": created_at,
        "selected_real_contexts": len(items),
        "selected_strata": source_manifest["selected_strata"],
        "selected_candidate_origins": source_manifest["selected_candidate_origins"],
        "synthetic_reversal_controls": len(owner_packet["reversal_controls"]),
        "reviewer_role": "owner",
        "required_reviewer_count": 1,
        "independent_review_required": False,
        "override_scope": "xhs-30-context-pilot-2026-08-14-only",
        "owner_packet_json": "local-private://tachikoma/.tmp/xhs-full-context-owner-review-v3.json",
        "owner_packet_html": "local-private://tachikoma/.tmp/xhs-full-context-owner-review-v3.html",
        "owner_completed_export": "local-private://tachikoma/.tmp/xhs-full-context-owner-review-v3.completed.json",
        "private_selection_provenance": "local-private://tachikoma/.tmp/xhs-full-context-selection-provenance-v3.json",
        "private_acquisition_queue": "local-private://tachikoma/.tmp/xhs-full-context-acquisition-queue-v2.json",
        "owner_json_sha256": None,
        "owner_html_sha256": None,
        "provenance_sha256": None,
        "acquisition_queue_sha256": source_manifest["acquisition_queue_sha256"],
        "owner_review_completed": False,
        "r3_status": "awaiting_owner_review",
        "stores_note_id_body_comments_images_or_draft": False,
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
        "publish_allowed": False,
    }
    return owner_packet, provenance, manifest


def _apply_recovered_notes(
    packet: dict[str, Any],
    recovery: dict[str, Any],
) -> int:
    if recovery.get("schema_version") != "xhs-owner-review-note-recovery/v1":
        raise ValueError("unsupported recovered-notes schema")
    rows = recovery.get("items")
    if not isinstance(rows, list) or recovery.get("note_count") != len(rows):
        raise ValueError("recovered-notes count mismatch")
    items_by_id = {item["owner_item_id"]: item for item in packet["items"]}
    seen: set[str] = set()
    for row in rows:
        owner_item_id = row.get("owner_item_id")
        if owner_item_id in seen:
            raise ValueError(f"duplicate recovered note: {owner_item_id}")
        seen.add(owner_item_id)
        item = items_by_id.get(owner_item_id)
        if item is None:
            raise ValueError(f"unknown recovered-note item: {owner_item_id}")
        if row.get("candidate") != item["candidate"]:
            raise ValueError(f"candidate mismatch for {owner_item_id}")
        reviewer_note = row.get("reviewer_note")
        if not isinstance(reviewer_note, str) or not reviewer_note.strip():
            raise ValueError(f"empty recovered note for {owner_item_id}")
        item["reviewer_note"] = reviewer_note.strip()
        item["review_note_source"] = recovery["source"]
        item["review_note_recovered_at"] = recovery["recovered_at"]
    packet["recovery_summary"] = {
        "source": recovery["source"],
        "recovered_at": recovery["recovered_at"],
        "recovered_note_count": len(rows),
        "dimensions_or_decisions_inferred": False,
    }
    return len(rows)


def _apply_owner_adjudication(
    packet: dict[str, Any],
    adjudication: dict[str, Any],
) -> dict[str, int]:
    if adjudication.get("schema_version") != "xhs-owner-review-adjudication/v1":
        raise ValueError("unsupported owner-adjudication schema")
    rows = adjudication.get("items")
    if not isinstance(rows, list) or adjudication.get("item_count") != len(rows):
        raise ValueError("owner-adjudication count mismatch")
    items_by_id = {item["owner_item_id"]: item for item in packet["items"]}
    row_ids = [row.get("owner_item_id") for row in rows]
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("duplicate owner-adjudication item")
    if set(row_ids) != set(items_by_id):
        raise ValueError("owner-adjudication item set mismatch")
    valid_dimensions = set(DIMENSION_LABELS)
    decision_counts = {"accept": 0, "revise": 0, "reject": 0}
    for row in rows:
        owner_item_id = row["owner_item_id"]
        decision = row.get("decision")
        if decision not in decision_counts:
            raise ValueError(f"invalid owner decision for {owner_item_id}")
        fail_dimensions = set(row.get("fail_dimensions") or [])
        if not fail_dimensions <= valid_dimensions:
            raise ValueError(f"invalid failure dimension for {owner_item_id}")
        if decision == "accept" and fail_dimensions:
            raise ValueError(f"accepted item has failures: {owner_item_id}")
        if decision in {"revise", "reject"} and not fail_dimensions:
            raise ValueError(f"non-accepted item has no failure: {owner_item_id}")
        if decision == "reject" and not (
            fail_dimensions & HARD_FAILURE_DIMENSIONS
        ):
            raise ValueError(f"rejected item has no hard failure: {owner_item_id}")
        dimensions = dict.fromkeys(valid_dimensions, "pass")
        if not row.get("question_applicable"):
            dimensions["question_still_unanswered"] = "not_applicable"
        if not row.get("protected_spans_applicable"):
            dimensions["protected_spans_preserved"] = "not_applicable"
        for dimension in fail_dimensions:
            dimensions[dimension] = "fail"
        item = items_by_id[owner_item_id]
        item["review_dimensions"] = dimensions
        item["decision"] = decision
        item["reason_codes"] = list(row.get("reason_codes") or [])
        item["reviewed_at"] = adjudication["authorized_at"]
        item["adjudication_source"] = adjudication["completion_mode"]
        decision_counts[decision] += 1
    packet["owner_review_completed"] = True
    packet["r3_status"] = "owner_review_completed_pending_acceptance_analysis"
    packet["completed_at"] = adjudication["authorized_at"]
    packet["review_completion_provenance"] = {
        "authorization_source": adjudication["authorization_source"],
        "inference_basis": adjudication["inference_basis"],
        "human_note_count": adjudication["human_note_count"],
        "completion_mode": adjudication["completion_mode"],
        "requires_owner_readback_before_r4_approval": adjudication[
            "requires_owner_readback_before_r4_approval"
        ],
    }
    return decision_counts


def _render_html(
    packet: dict[str, Any],
    export_path: Path,
    in_progress_path: Path | None = None,
) -> bytes:
    if in_progress_path is None:
        in_progress_path = export_path.with_name(
            "xhs-full-context-owner-review-v3.in-progress.json"
        )
    payload = json.dumps(packet, ensure_ascii=False).replace("</", "<\\/")
    export_name = html.escape(export_path.name, quote=True)
    in_progress_name = html.escape(in_progress_path.name, quote=True)
    dimension_labels = json.dumps(DIMENSION_LABELS, ensure_ascii=False)
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>小红书 30 条完整上下文负责人审核</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, "Microsoft YaHei", sans-serif; }}
body {{ margin: 0; background: #f5f3ef; color: #282522; }}
main {{ max-width: 1080px; margin: 0 auto; padding: 28px 18px 80px; }}
h1 {{ margin: 0 0 8px; }} .muted {{ color: #6b655f; }}
.notice {{ background: #fff4d6; border: 1px solid #e7ca74; padding: 14px; border-radius: 10px; margin: 18px 0; }}
.item {{ background: white; border: 1px solid #ddd7cf; border-radius: 12px; padding: 18px; margin: 16px 0; box-shadow: 0 2px 8px #0000000a; }}
.context {{ white-space: pre-wrap; background: #f8f7f4; padding: 12px; border-radius: 8px; margin: 8px 0; }}
.comments {{ padding-left: 22px; }} .candidate {{ border-left: 4px solid #7c5cff; padding-left: 12px; font-size: 1.05rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; margin: 14px 0; }}
label {{ display: grid; gap: 5px; font-weight: 600; }} select, textarea {{ font: inherit; padding: 8px; border: 1px solid #bbb3aa; border-radius: 7px; background: white; }}
textarea {{ min-height: 78px; resize: vertical; }}
.toolbar {{ position: sticky; bottom: 0; background: #282522; color: white; padding: 12px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-radius: 10px; }}
button {{ font: inherit; font-weight: 700; padding: 10px 16px; border: 0; border-radius: 8px; cursor: pointer; }}
.status {{ font-variant-numeric: tabular-nums; }}
</style>
</head>
<body><main>
<h1>小红书 30 条完整上下文负责人审核</h1>
<p class="muted">单一审核人：项目负责人。逐项判断，不使用总分掩盖失败项。</p>
<div class="notice">历史发布不等于风格批准；发布状态标记为真，也不等于已经验证发布。本页不会联网、不会发送、不会发布。未选完下拉框也可以保存当前进度。</div>
<div id="items"></div>
<div class="toolbar"><span class="status" id="status">0 / 30 已决定</span><div><button id="save">保存当前进度</button> <button id="export">校验并导出审核结果</button></div></div>
</main>
<script type="application/json" id="packet">{payload}</script>
<script>
const packet = JSON.parse(document.getElementById('packet').textContent);
const root = document.getElementById('items');
const dimensions = Object.keys(packet.items[0].review_dimensions);
const dimensionLabels = {dimension_labels};
const esc = value => String(value ?? '');
for (const [index, item] of packet.items.entries()) {{
  const card = document.createElement('section'); card.className = 'item'; card.dataset.index = index;
  const title = document.createElement('h2'); title.textContent = `${{item.owner_item_id}} · ${{item.context.title}}`; card.appendChild(title);
  const body = document.createElement('div'); body.className = 'context'; body.textContent = item.context.body; card.appendChild(body);
  const commentsTitle = document.createElement('h3'); commentsTitle.textContent = '当前可见评论'; card.appendChild(commentsTitle);
  const comments = document.createElement('ul'); comments.className = 'comments';
  for (const value of item.context.visible_comments) {{ const li = document.createElement('li'); li.textContent = typeof value === 'string' ? value : JSON.stringify(value); comments.appendChild(li); }}
  card.appendChild(comments);
  const candidateTitle = document.createElement('h3'); candidateTitle.textContent = '待审文本'; card.appendChild(candidateTitle);
  const candidate = document.createElement('p'); candidate.className = 'candidate'; candidate.textContent = item.candidate; card.appendChild(candidate);
  const grid = document.createElement('div'); grid.className = 'grid';
  for (const name of dimensions) {{
    const label = document.createElement('label'); label.textContent = dimensionLabels[name] || '未定义审核维度';
    const select = document.createElement('select'); select.dataset.dimension = name;
    select.innerHTML = '<option value="">请选择</option><option value="pass">通过</option><option value="fail">失败</option><option value="not_applicable">不适用</option>';
    select.value = item.review_dimensions[name] || '';
    label.appendChild(select); grid.appendChild(label);
  }}
  card.appendChild(grid);
  const decisionLabel = document.createElement('label'); decisionLabel.textContent = '负责人决定';
  const decision = document.createElement('select'); decision.dataset.decision = '1';
  decision.innerHTML = '<option value="">请选择</option><option value="accept">接受</option><option value="revise">修改</option><option value="reject">拒绝</option>';
  decision.value = item.decision || '';
  decisionLabel.appendChild(decision); card.appendChild(decisionLabel);
  const noteLabel = document.createElement('label'); noteLabel.textContent = '审核备注';
  const note = document.createElement('textarea'); note.dataset.note = '1'; note.value = esc(item.reviewer_note); noteLabel.appendChild(note); card.appendChild(noteLabel);
  decision.addEventListener('change', updateStatus); note.addEventListener('input', updateStatus); root.appendChild(card);
}}
function updateStatus() {{
  const done = [...document.querySelectorAll('[data-decision]')].filter(x => x.value).length;
  const notes = [...document.querySelectorAll('[data-note]')].filter(x => x.value.trim()).length;
  document.getElementById('status').textContent = `${{done}} / ${{packet.items.length}} 已决定 · ${{notes}} 条有备注`;
}}
function syncPacket() {{
  const cards = [...document.querySelectorAll('.item')]; const missing = [];
  for (const card of cards) {{
    const item = packet.items[Number(card.dataset.index)];
    const decision = card.querySelector('[data-decision]').value;
    const selects = [...card.querySelectorAll('[data-dimension]')];
    if (!decision || selects.some(x => !x.value)) missing.push(item.owner_item_id);
    item.decision = decision || null;
    for (const select of selects) item.review_dimensions[select.dataset.dimension] = select.value || null;
    item.reviewer_note = card.querySelector('[data-note]').value.trim() || null;
    item.reviewed_at = decision ? new Date().toISOString() : null;
  }}
  return missing;
}}
function downloadPacket(filename) {{
  const blob = new Blob([JSON.stringify(packet, null, 2) + '\\n'], {{type:'application/json'}});
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = filename; link.click(); URL.revokeObjectURL(link.href);
}}
document.getElementById('save').addEventListener('click', () => {{
  const missing = syncPacket();
  packet.owner_review_completed = missing.length === 0;
  packet.r3_status = missing.length ? 'awaiting_owner_review' : 'owner_review_completed_pending_acceptance_analysis';
  packet.in_progress_saved_at = new Date().toISOString();
  downloadPacket('{in_progress_name}');
}});
document.getElementById('export').addEventListener('click', () => {{
  const missing = syncPacket();
  if (missing.length) {{ alert(`还有 ${{missing.length}} 条未完整判断：${{missing.join(', ')}}`); return; }}
  packet.owner_review_completed = true; packet.r3_status = 'owner_review_completed_pending_acceptance_analysis';
  packet.completed_at = new Date().toISOString();
  downloadPacket('{export_name}');
}});
updateStatus();
</script></body></html>"""
    return page.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-json", type=Path, default=DEFAULT_OWNER_JSON)
    parser.add_argument("--owner-html", type=Path, default=DEFAULT_OWNER_HTML)
    parser.add_argument("--completed-export", type=Path, default=DEFAULT_OWNER_EXPORT)
    parser.add_argument(
        "--in-progress-export", type=Path, default=DEFAULT_IN_PROGRESS_EXPORT
    )
    parser.add_argument("--recovered-notes", type=Path, default=DEFAULT_RECOVERED_NOTES)
    parser.add_argument(
        "--owner-adjudication", type=Path, default=DEFAULT_OWNER_ADJUDICATION
    )
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    packet, provenance, manifest = build_owner()
    recovered_notes_bytes = None
    if args.recovered_notes.exists():
        recovered_notes_bytes = args.recovered_notes.read_bytes()
        recovered_notes = json.loads(recovered_notes_bytes.decode("utf-8"))
        manifest["recovered_notes_count"] = _apply_recovered_notes(
            packet, recovered_notes
        )
        manifest["recovered_notes_sha256"] = _sha256(recovered_notes_bytes)
    else:
        manifest["recovered_notes_count"] = 0
        manifest["recovered_notes_sha256"] = None
    adjudication_bytes = None
    if args.owner_adjudication.exists():
        adjudication_bytes = args.owner_adjudication.read_bytes()
        adjudication = json.loads(adjudication_bytes.decode("utf-8"))
        decision_counts = _apply_owner_adjudication(packet, adjudication)
        manifest["adjudication_sha256"] = _sha256(adjudication_bytes)
        manifest["decision_counts"] = decision_counts
        manifest["owner_review_completed"] = True
        manifest["r3_status"] = packet["r3_status"]
        manifest["completion_mode"] = adjudication["completion_mode"]
        manifest["requires_owner_readback_before_r4_approval"] = adjudication[
            "requires_owner_readback_before_r4_approval"
        ]
    else:
        manifest["adjudication_sha256"] = None
        manifest["decision_counts"] = {"accept": 0, "revise": 0, "reject": 0}
    owner_json = _json_bytes(packet)
    owner_html = _render_html(packet, args.completed_export, args.in_progress_export)
    provenance_bytes = _json_bytes(provenance)
    manifest["owner_json_sha256"] = _sha256(owner_json)
    manifest["owner_html_sha256"] = _sha256(owner_html)
    manifest["provenance_sha256"] = _sha256(provenance_bytes)
    _atomic_write(args.owner_json, owner_json)
    _atomic_write(args.owner_html, owner_html)
    _atomic_write(args.provenance, provenance_bytes)
    _atomic_write(args.manifest, _json_bytes(manifest))
    print(json.dumps({
        "ok": True,
        "selected_real_contexts": manifest["selected_real_contexts"],
        "reviewer_role": manifest["reviewer_role"],
        "required_reviewer_count": manifest["required_reviewer_count"],
        "r3_status": manifest["r3_status"],
        "decision_counts": manifest["decision_counts"],
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
