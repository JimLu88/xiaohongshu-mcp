#!/usr/bin/env python3
r"""Build the private 10-context XHS production-gate owner review.

The existing 30 owner-authorized contexts stay immutable.  This tool selects
ten additional complete real contexts from the already-local eligible pool,
adds rule-assisted recommendations, and writes complete context only under
``D:\AI\tachikoma\.tmp``.  The repository manifest is hash/count only.

No model call, network request, platform action, production switch, or
publication is performed by this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = Path(r"D:\AI\tachikoma\.tmp")
RUNTIME_ROOT = Path(r"D:\AI\tachikoma-runtime\writing-style-all-v2")
DEFAULT_COMPLETED_30 = PRIVATE_ROOT / "xhs-full-context-owner-review-v3.completed.json"
DEFAULT_PRIVATE_JSON = PRIVATE_ROOT / "xhs-production-gate-owner-review-v1.json"
DEFAULT_PRIVATE_HTML = PRIVATE_ROOT / "xhs-production-gate-owner-review-v1.html"
DEFAULT_COMPLETED_EXPORT = PRIVATE_ROOT / "xhs-production-gate-owner-review-v1.completed.json"
DEFAULT_MANIFEST = (
    REPO_ROOT
    / "research"
    / "panse_multi_direction"
    / "xhs_production_gate_owner_review_manifest_v1.json"
)
POLICY_PATH = (
    RUNTIME_ROOT
    / "skills"
    / "writing-style-lab"
    / "references"
    / "xhs-comment-intent-policy-v4.json"
)
BASE_BUILDER_PATH = Path(__file__).with_name("build_xhs_full_context_blind_pilot_v2.py")

DIMENSIONS = (
    "source_grounded",
    "speaking_position_correct",
    "speech_act_fit",
    "teacher_or_judge_posture_absent",
    "source_restatement_absent",
    "fabricated_firsthand_absent",
    "question_still_unanswered",
    "ordinary_order_and_logic",
    "protected_spans_preserved",
    "near_copy_safe",
)
DIMENSION_LABELS = {
    "source_grounded": "内容有上下文依据",
    "speaking_position_correct": "说话身份和位置恰当",
    "speech_act_fit": "表达目的符合互动场景",
    "teacher_or_judge_posture_absent": "没有老师、评委或设计顾问口吻",
    "source_restatement_absent": "没有重复原文、标题或图片主题",
    "fabricated_firsthand_absent": "没有虚构亲身经历",
    "question_still_unanswered": "问题确实尚未被回答",
    "ordinary_order_and_logic": "语序和逻辑自然",
    "protected_spans_preserved": "数字、名称等受保护内容准确",
    "near_copy_safe": "没有近似照搬风险",
}
ADVISOR_WORDS = re.compile(r"建议|不妨|最好|一定要|记得|可以试试|先把|优先选")
FIRSTHAND_WORDS = re.compile(r"我家|我买|我用了|我住|我装修|我之前")


def _sha(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _load_base_builder() -> Any:
    spec = importlib.util.spec_from_file_location("xhs_blind_v2", BASE_BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the v2 full-context builder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _completed_hashes(path: Path) -> set[str]:
    packet = json.loads(path.read_text(encoding="utf-8"))
    items = packet.get("items")
    if not isinstance(items, list) or len(items) != 30:
        raise ValueError("the completed owner packet must contain exactly 30 items")
    hashes = {str(item.get("context_sha256") or "") for item in items}
    if "" in hashes or len(hashes) != 30 or packet.get("owner_review_completed") is not True:
        raise ValueError("the existing 30-context owner packet is not complete and unique")
    return hashes


def _policy() -> dict[str, Any]:
    value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if value.get("policy_version") != "xhs-comment-intent.v4":
        raise ValueError("unexpected XHS intent policy")
    return value


def _resolved_mode(record: dict[str, Any], policy: dict[str, Any]) -> str | None:
    if record.get("interaction_mode"):
        return str(record["interaction_mode"])
    direction = policy["directions"].get(str(record.get("comment_direction_id") or ""))
    if not isinstance(direction, dict):
        return None
    return str(direction.get("interaction_mode") or "") or None


def select_additional(
    records: Iterable[dict[str, Any]],
    *,
    existing_hashes: set[str],
    policy: dict[str, Any],
    target: int = 10,
) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for source in records:
        if source.get("context_sha256") in existing_hashes:
            continue
        mode = _resolved_mode(source, policy)
        if not (
            mode
            and source.get("interaction_intent")
            and source.get("comment_direction_id")
            and source.get("topic_ids")
            and source.get("candidate")
        ):
            continue
        eligible.append({**source, "interaction_mode": mode})

    groups: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for item in sorted(eligible, key=lambda row: (str(row["context_sha256"]), str(row["sample_id"]))):
        groups[str(item.get("role") or "unknown")].append(item)

    selected: list[dict[str, Any]] = []
    # Production coverage explicitly needs official explanation.  Prefer four
    # real official contexts, then balance the remaining ordinary roles.
    while groups["official_explanation"] and len(selected) < min(4, target):
        selected.append(groups["official_explanation"].popleft())
    role_order = ["stylist", "evaluation_judgment", "space_advisor", "global_design_observer"]
    while len(selected) < target and any(groups[role] for role in role_order):
        for role in role_order:
            if groups[role] and len(selected) < target:
                selected.append(groups[role].popleft())
    if len(selected) != target:
        raise RuntimeError(f"only {len(selected)} eligible additional contexts were available")
    return selected


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def _source_restatement(candidate: str, context: dict[str, Any]) -> bool:
    candidate_n = _normalize(candidate)
    if len(candidate_n) < 6:
        return False
    source_parts = [str(context.get("title") or ""), str(context.get("body") or "")]
    source_parts.extend(str(item) for item in context.get("visible_comments") or [])
    for source in source_parts:
        source_n = _normalize(source)
        if not source_n:
            continue
        if candidate_n in source_n:
            return True
        if SequenceMatcher(None, candidate_n, source_n[: max(80, len(candidate_n) * 3)]).ratio() >= 0.62:
            return True
    return False


def _naturalness_findings(candidate: str, mode: str) -> list[str]:
    if str(RUNTIME_ROOT) not in sys.path:
        sys.path.insert(0, str(RUNTIME_ROOT))
    from chatgpt_mcp.style_naturalness import evaluate_naturalness
    from chatgpt_mcp.style_register import resolve_register_contract

    register = resolve_register_contract(
        artifact_type="comment",
        taxonomy_ids=[
            "platform.xiaohongshu-comment",
            "persona.lifestyle-curator",
            "role.editor",
            "scene.social-comment",
        ],
        interaction_mode=mode,
    )
    result = evaluate_naturalness(
        candidate,
        artifact_type="comment",
        interaction_mode=mode,
        register_contract=register,
    )
    return [str(item["code"]) for item in result.get("findings") or []]


def recommend(item: dict[str, Any]) -> dict[str, Any]:
    context = {
        "title": item.get("title"),
        "body": item.get("body"),
        "visible_comments": item.get("visible_comments") or [],
    }
    candidate = str(item["candidate"])
    role = str(item.get("role") or "unknown")
    mode = str(item["interaction_mode"])
    findings = _naturalness_findings(candidate, mode)
    dimensions = {name: "pass" for name in DIMENSIONS}
    reasons: list[str] = []

    if findings:
        dimensions["ordinary_order_and_logic"] = "fail"
        reasons.extend(findings)
    if ADVISOR_WORDS.search(candidate) and role not in {"official_explanation", "principal_sincere_signed"}:
        dimensions["speaking_position_correct"] = "fail"
        dimensions["teacher_or_judge_posture_absent"] = "fail"
        reasons.append("advisor_posture")
    if _source_restatement(candidate, context):
        dimensions["source_restatement_absent"] = "fail"
        reasons.append("possible_source_restatement")
    if FIRSTHAND_WORDS.search(candidate) and role not in {"stylist", "space_advisor"}:
        dimensions["fabricated_firsthand_absent"] = "fail"
        reasons.append("firsthand_claim_requires_owner_confirmation")
    if mode == "curiosity_question" and not any(mark in candidate for mark in "?？"):
        dimensions["speech_act_fit"] = "fail"
        reasons.append("question_mode_without_question")
    if mode != "curiosity_question" and any(mark in candidate for mark in "?？"):
        dimensions["speech_act_fit"] = "fail"
        reasons.append("non_question_mode_contains_question")

    decision = "accept" if all(value == "pass" for value in dimensions.values()) else "revise"
    return {
        "decision": decision,
        "review_dimensions": dimensions,
        "reason_codes": sorted(set(reasons)),
        "provenance": "rule_assisted_model_recommendation_not_owner_decision",
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any]]:
    builder = _load_base_builder()
    eligible, _acquisition, _published = builder.audit_local_contexts()
    existing = _completed_hashes(DEFAULT_COMPLETED_30)
    policy = _policy()
    selected = select_additional(eligible, existing_hashes=existing, policy=policy)
    created_at = datetime.now(timezone.utc).isoformat()
    items: list[dict[str, Any]] = []
    for index, source in enumerate(selected, start=31):
        context = {
            "title": source["title"],
            "body": source["body"],
            "visible_comments": source["visible_comments"],
            "image_observation": source["image_observation"],
        }
        items.append(
            {
                "owner_item_id": f"生产补充-{index:02d}",
                "context_sha256": source["context_sha256"],
                "context": context,
                "candidate": source["candidate"],
                "declared_role": source["role"],
                "declared_interaction_mode": source["interaction_mode"],
                "interaction_intent": source["interaction_intent"],
                "comment_direction_id": source["comment_direction_id"],
                "topic_ids": source["topic_ids"],
                "review_stratum": source["review_stratum"],
                "model_recommendation": recommend(source),
                "owner_decision": None,
                "owner_review_dimensions": {name: None for name in DIMENSIONS},
                "owner_note": None,
                "reviewed_at": None,
            }
        )

    packet = {
        "schema_version": "xhs-production-gate-owner-review/v1",
        "created_at": created_at,
        "scope": "additional_10_real_contexts_for_40_case_gate",
        "existing_owner_authorized_context_count": 30,
        "additional_context_count": 10,
        "combined_context_count_after_owner_approval": 40,
        "reviewer_role": "single_owner",
        "items": items,
        "principal_sincere_signed_evidence": {
            "status": "owner_evidence_required",
            "verified_real_participation_fact": None,
            "allowed_public_summary": None,
            "owner_confirms_authentic_participation": None,
            "note": "负责人身份只能绑定真实参与和真实取舍，不得虚构创业故事。",
        },
        "production_switch": {
            "owner_approves_additional_10": None,
            "owner_approves_principal_voice_evidence": None,
            "owner_approves_production_contract_switch": None,
            "publish_allowed": False,
        },
        "owner_review_complete": False,
        "production_ready": False,
        "publish_allowed": False,
    }
    manifest = {
        "schema_version": "xhs-production-gate-owner-review-manifest/v1",
        "created_at": created_at,
        "existing_owner_authorized_context_count": 30,
        "additional_context_count": 10,
        "combined_context_count_after_owner_approval": 40,
        "additional_context_sha256": sorted(item["context_sha256"] for item in items),
        "role_counts": dict(sorted(Counter(item["declared_role"] for item in items).items())),
        "mode_counts": dict(sorted(Counter(item["declared_interaction_mode"] for item in items).items())),
        "recommendation_counts": dict(
            sorted(Counter(item["model_recommendation"]["decision"] for item in items).items())
        ),
        "official_explanation_covered": any(
            item["declared_role"] == "official_explanation" for item in items
        ),
        "principal_sincere_signed_evidence_status": "owner_evidence_required",
        "private_packet_locator": "local-private://tachikoma/.tmp/xhs-production-gate-owner-review-v1.json",
        "private_packet_sha256": None,
        "private_html_locator": "local-private://tachikoma/.tmp/xhs-production-gate-owner-review-v1.html",
        "private_html_sha256": None,
        "stores_source_text_or_candidate": False,
        "model_recommendations_are_owner_decisions": False,
        "owner_review_complete": False,
        "production_contract_updated": False,
        "generation_executed": False,
        "network_executed": False,
        "publication_executed": False,
        "publish_allowed": False,
    }
    return packet, manifest


def render_html(packet: dict[str, Any], export_path: Path) -> str:
    payload = json.dumps(packet, ensure_ascii=False).replace("</", "<\\/")
    labels = json.dumps(DIMENSION_LABELS, ensure_ascii=False)
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>小红书生产门补充审核</title><style>
body{{font:17px/1.6 system-ui;margin:24px auto;max-width:1180px;color:#172033;background:#f5f2ed}}
header,section{{background:#fff;border:1px solid #d9d3cb;border-radius:14px;padding:18px 22px;margin:14px 0}}
h1{{font-size:30px}}h2{{font-size:21px}}.context{{background:#f7f6f4;padding:12px;white-space:pre-wrap}}
.candidate{{border-left:4px solid #8066ff;padding:10px 14px}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}
label{{display:block;font-weight:650}}select,textarea,input{{width:100%;font:inherit;padding:9px;box-sizing:border-box}}
.recommend{{background:#fff6dc;padding:10px;border-radius:8px}}button{{min-height:48px;padding:0 16px;margin:5px}}
@media(max-width:720px){{.grid{{grid-template-columns:1fr}}body{{margin:10px}}}}
</style></head><body><header><h1>小红书 40 条生产门补充审核</h1>
<p>现有 30 条保持不变。下面是额外 10 条真实完整上下文；黄色区域是模型建议，不是你的决定。</p>
<button id='adopt'>全部采用模型建议</button><button id='save'>保存当前进度</button><button id='export'>导出完成结果</button>
<strong id='status'></strong></header><main id='root'></main>
<section><h2>负责人真实参与依据</h2><p>只有确实由负责人参与的节点或取舍才能进入 <code>principal_sincere_signed</code>。</p>
<label>真实参与事实<textarea id='principalFact' rows='3'></textarea></label>
<label>可公开的简短表述<textarea id='principalSummary' rows='3'></textarea></label>
<label>确认事实真实<select id='principalConfirm'><option value=''>请选择</option><option value='true'>确认</option><option value='false'>不确认</option></select></label></section>
<section><h2>生产合同决定</h2><label>批准这 10 条审核<select id='approve10'><option value=''>请选择</option><option value='true'>批准</option><option value='false'>不批准</option></select></label>
<label>批准负责人身份依据<select id='approvePrincipal'><option value=''>请选择</option><option value='true'>批准</option><option value='false'>不批准</option></select></label>
<label>批准切换生产合同<select id='approveSwitch'><option value=''>请选择</option><option value='true'>批准</option><option value='false'>不批准</option></select></label></section>
<script>const packet={payload};const labels={labels};const key='xhs-production-gate-owner-review-v1';
const root=document.getElementById('root');
function esc(value){{return String(value??'').replace(/[&<>"']/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]))}}
function render(){{root.innerHTML='';packet.items.forEach((item,i)=>{{const s=document.createElement('section');s.dataset.i=i;
s.innerHTML=`<h2>${{esc(item.owner_item_id)}} · ${{esc(item.declared_role)}}</h2><p>${{esc(item.declared_interaction_mode)}} · ${{esc(item.comment_direction_id)}}</p><div class='context'><b>标题</b>：${{esc(item.context.title)}}\n<b>正文</b>：${{esc(item.context.body)}}\n<b>可见评论</b>：${{esc(item.context.visible_comments.join(' / '))}}</div><p class='candidate'>${{esc(item.candidate)}}</p><div class='recommend'>模型建议：${{esc(item.model_recommendation.decision)}}；${{esc(item.model_recommendation.reason_codes.join('、')||'未发现规则命中')}}</div><label>负责人决定<select data-decision><option value=''>请选择</option><option value='accept'>接受</option><option value='revise'>修改</option><option value='reject'>拒绝</option></select></label><div class='grid' data-dims></div><label>备注<textarea data-note rows='2'></textarea></label>`;
const dims=s.querySelector('[data-dims]');Object.keys(labels).forEach(name=>{{const l=document.createElement('label');l.textContent=labels[name];l.innerHTML+=`<select data-dim='${{name}}'><option value=''>请选择</option><option value='pass'>通过</option><option value='fail'>不通过</option><option value='not_applicable'>不适用</option></select>`;dims.appendChild(l)}});root.appendChild(s)}});bind();update()}}
function bind(){{document.querySelectorAll('select,textarea,input').forEach(x=>x.addEventListener('change',update));document.querySelectorAll('textarea').forEach(x=>x.addEventListener('input',update))}}
function collect(){{packet.items.forEach((item,i)=>{{const s=document.querySelector(`section[data-i='${{i}}']`);item.owner_decision=s.querySelector('[data-decision]').value||null;Object.keys(labels).forEach(k=>item.owner_review_dimensions[k]=s.querySelector(`[data-dim='${{k}}']`).value||null);item.owner_note=s.querySelector('[data-note]').value||null;item.reviewed_at=item.owner_decision?new Date().toISOString():null}});packet.principal_sincere_signed_evidence.verified_real_participation_fact=principalFact.value||null;packet.principal_sincere_signed_evidence.allowed_public_summary=principalSummary.value||null;packet.principal_sincere_signed_evidence.owner_confirms_authentic_participation=principalConfirm.value===''?null:principalConfirm.value==='true';packet.production_switch.owner_approves_additional_10=approve10.value===''?null:approve10.value==='true';packet.production_switch.owner_approves_principal_voice_evidence=approvePrincipal.value===''?null:approvePrincipal.value==='true';packet.production_switch.owner_approves_production_contract_switch=approveSwitch.value===''?null:approveSwitch.value==='true';return packet}}
function update(){{collect();const done=packet.items.filter(x=>x.owner_decision&&Object.values(x.owner_review_dimensions).every(Boolean)).length;status.textContent=`已完成 ${{done}}/10`;localStorage.setItem(key,JSON.stringify(packet))}}
function download(name,obj){{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(obj,null,2)],{{type:'application/json'}}));a.download=name;a.click();URL.revokeObjectURL(a.href)}}
adopt.onclick=()=>{{packet.items.forEach((item,i)=>{{const s=document.querySelector(`section[data-i='${{i}}']`);s.querySelector('[data-decision]').value=item.model_recommendation.decision;Object.entries(item.model_recommendation.review_dimensions).forEach(([k,v])=>s.querySelector(`[data-dim='${{k}}']`).value=v)}});update()}};
save.onclick=()=>download('xhs-production-gate-owner-review-v1.in-progress.json',collect());export.onclick=()=>{{collect();const missing=packet.items.filter(x=>!x.owner_decision||Object.values(x.owner_review_dimensions).some(v=>!v));if(missing.length||principalConfirm.value===''||approve10.value===''||approvePrincipal.value===''||approveSwitch.value===''){{alert('还有审核项或最终决定未完成');return}}packet.owner_review_complete=true;packet.production_ready=packet.production_switch.owner_approves_additional_10&&packet.production_switch.owner_approves_principal_voice_evidence&&packet.production_switch.owner_approves_production_contract_switch;download('{export_path.name}',packet)}};
render();</script></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-json", type=Path, default=DEFAULT_PRIVATE_JSON)
    parser.add_argument("--private-html", type=Path, default=DEFAULT_PRIVATE_HTML)
    parser.add_argument("--completed-export", type=Path, default=DEFAULT_COMPLETED_EXPORT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    packet, manifest = build_packet()
    private_json = _json_bytes(packet)
    private_html = render_html(packet, args.completed_export).encode("utf-8")
    manifest["private_packet_sha256"] = _sha(private_json)
    manifest["private_html_sha256"] = _sha(private_html)
    _atomic_write(args.private_json, private_json)
    _atomic_write(args.private_html, private_html)
    _atomic_write(args.manifest, _json_bytes(manifest))
    print(json.dumps({
        "ok": True,
        "additional_context_count": manifest["additional_context_count"],
        "combined_context_count_after_owner_approval": manifest["combined_context_count_after_owner_approval"],
        "role_counts": manifest["role_counts"],
        "recommendation_counts": manifest["recommendation_counts"],
        "principal_sincere_signed_evidence_status": manifest["principal_sincere_signed_evidence_status"],
        "owner_review_complete": False,
        "production_contract_updated": False,
        "private_json": str(args.private_json),
        "private_html": str(args.private_html),
        "manifest": str(args.manifest),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
