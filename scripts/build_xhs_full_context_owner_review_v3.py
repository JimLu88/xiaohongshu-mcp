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
DEFAULT_PROVENANCE = PRIVATE_ROOT / "xhs-full-context-selection-provenance-v3.json"
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_full_context_owner_review_manifest_v3.json"
)


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
        owner_item["owner_item_id"] = f"OWNER-{index:02d}"
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


def _render_html(packet: dict[str, Any], export_path: Path) -> bytes:
    payload = json.dumps(packet, ensure_ascii=False).replace("</", "<\\/")
    export_name = html.escape(export_path.name, quote=True)
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>小红书 30 条完整上下文 Owner 审核</title>
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
<h1>小红书 30 条完整上下文 Owner 审核</h1>
<p class="muted">单一审核人：项目 Owner。逐维度判断，不使用总分补偿失败项。</p>
<div class="notice">历史发布不等于风格批准；标记 published=true 也不等于已验证发布。本页不会联网、不会发送、不会发布。</div>
<div id="items"></div>
<div class="toolbar"><span class="status" id="status">0 / 30 已决定</span><button id="export">校验并导出 {export_name}</button></div>
</main>
<script type="application/json" id="packet">{payload}</script>
<script>
const packet = JSON.parse(document.getElementById('packet').textContent);
const root = document.getElementById('items');
const dimensions = Object.keys(packet.items[0].review_dimensions);
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
    const label = document.createElement('label'); label.textContent = name;
    const select = document.createElement('select'); select.dataset.dimension = name;
    select.innerHTML = '<option value="">请选择</option><option value="pass">通过</option><option value="fail">失败</option><option value="not_applicable">不适用</option>';
    label.appendChild(select); grid.appendChild(label);
  }}
  card.appendChild(grid);
  const decisionLabel = document.createElement('label'); decisionLabel.textContent = 'Owner 决定';
  const decision = document.createElement('select'); decision.dataset.decision = '1';
  decision.innerHTML = '<option value="">请选择</option><option value="accept">接受</option><option value="revise">修改</option><option value="reject">拒绝</option>';
  decisionLabel.appendChild(decision); card.appendChild(decisionLabel);
  const noteLabel = document.createElement('label'); noteLabel.textContent = '审核备注';
  const note = document.createElement('textarea'); note.dataset.note = '1'; noteLabel.appendChild(note); card.appendChild(noteLabel);
  decision.addEventListener('change', updateStatus); root.appendChild(card);
}}
function updateStatus() {{ const done = [...document.querySelectorAll('[data-decision]')].filter(x => x.value).length; document.getElementById('status').textContent = `${{done}} / ${{packet.items.length}} 已决定`; }}
document.getElementById('export').addEventListener('click', () => {{
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
  if (missing.length) {{ alert(`还有 ${{missing.length}} 条未完整判断：${{missing.join(', ')}}`); return; }}
  packet.owner_review_completed = true; packet.r3_status = 'owner_review_completed_pending_acceptance_analysis';
  packet.completed_at = new Date().toISOString();
  const blob = new Blob([JSON.stringify(packet, null, 2) + '\\n'], {{type:'application/json'}});
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = '{export_name}'; link.click(); URL.revokeObjectURL(link.href);
}});
</script></body></html>"""
    return page.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-json", type=Path, default=DEFAULT_OWNER_JSON)
    parser.add_argument("--owner-html", type=Path, default=DEFAULT_OWNER_HTML)
    parser.add_argument("--completed-export", type=Path, default=DEFAULT_OWNER_EXPORT)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    packet, provenance, manifest = build_owner()
    owner_json = _json_bytes(packet)
    owner_html = _render_html(packet, args.completed_export)
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
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
