"""Compile four current verified Style Lab comments into a prepare-only MCP file."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

from lib.xhs_browser_profiles import load_expected_identity
from lib.xhs_comment_length_mix import build_length_assignment, apply_length_assignment_to_request
from run_xhs_style_lab import verify_actual_run, compile_project_preflight

ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))
CONTRACT = 'panse-xhs-comment-batch-handoff.v1'

def local(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT): raise ValueError('file must stay inside authority repository')
    return path

def read(value):
    return json.loads(local(value).read_text(encoding='utf-8'))

def current(value, now, age_seconds=None):
    date = datetime.fromisoformat(value.replace('Z','+00:00'))
    if date.tzinfo is None or date.astimezone(CST).date() != now.astimezone(CST).date() or date > now:
        raise ValueError('evidence is stale, future-dated or timezone-free')
    if age_seconds is not None and (now-date).total_seconds() > age_seconds:
        raise ValueError('evidence requires a fresh observation')

def compile_batch(source, now=None):
    now = now or datetime.now(timezone.utc)
    if not re.fullmatch(r'[a-zA-Z0-9._-]{1,80}', source.get('batch_id','')):
        raise ValueError('invalid batch id')
    if source.get('date') != now.astimezone(CST).date().isoformat():
        raise ValueError('a current-date batch is required')
    identity = load_expected_identity(source['account_slot'])
    session = read(source['session_probe_file'])
    current(session['observed_at'], now, 600)
    if (session.get('contract_id') != 'panse-xhs-session-probe.v1' or session.get('status') != 'valid'
        or session.get('account_slot') != source['account_slot']
        or session.get('expected_profile_id') != identity['expected_profile_id']
        or session.get('risk_signal_observed') is not False):
        raise ValueError('fresh valid exact-slot session evidence is required')
    if len(source.get('items',[])) != 4: raise ValueError('exactly four items required')
    seen_ids, seen_texts, output = set(), set(), []
    for index,item in enumerate(source['items'],1):
        note_id = item['note_id']
        if not re.fullmatch(r'[a-f0-9]{24}',note_id) or note_id in seen_ids:
            raise ValueError('invalid or duplicate note id')
        current(item['selectors_observed_at'],now,600)
        request = read(item['style_request_file'])
        receipt = read(item['style_run_file'])
        current(receipt['observed_at'],now)
        request_hash = hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True,
                                               separators=(',',':')).encode()).hexdigest()
        if (receipt.get('receipt_type') != 'panse_xhs_actual_style_lab_run'
            or receipt.get('candidate_input_sha256') != request_hash
            or receipt.get('request_id') != request.get('request_id')
            or receipt.get('external_posting_performed') is not False
            or request.get('artifact_type') != 'comment'
            or not re.match(r'^https://www\.xiaohongshu\.com/(?:explore|discovery/item)/'+note_id+r'(?:[/?#]|$)', request.get('source_locator',''))):
            raise ValueError('Style Lab request/result/target mismatch')
        context = request.get('panse_comment_length_context',{})
        if (context.get('delivery_mode') != 'human_final_batch' or context.get('batch_id') != source['batch_id']
            or context.get('batch_size') != 4 or context.get('item_index') != index):
            raise ValueError('complete same-id human-final four-item generation batch required')
        assignment = build_length_assignment(context)
        preflight = compile_project_preflight(local(item['style_request_file']))
        if preflight.get('comment_length_mix') != assignment:
            raise ValueError('style preflight length assignment drifted')
        production = preflight.get('production_contract') or {}
        if production.get('account_slot') != source['account_slot']:
            raise ValueError('nonofficial exact-slot voice evidence required for initial batch pilot')
        result = receipt['style_lab_result']
        effective = apply_length_assignment_to_request({'brief_text':'', 'output':request.get('output',{})},assignment)['output']
        verify_actual_run(result,assignment,effective)
        if result.get('quality',{}).get('hard_failures') or result.get('semantic_review_error'):
            raise ValueError('content gates failed')
        text = result['draft']['draft_text']
        normalized = re.sub(r'\s','',text)
        if normalized in seen_texts or '\n' in text or '\r' in text:
            raise ValueError('duplicate or multiline comment')
        readback = read(item['read_receipt_file'])
        if readback.get('date') != source['date'] or readback.get('account_slot') != source['account_slot']:
            raise ValueError('reading evidence does not match current date and account')
        matches = [row for row in readback.get('items',[]) if row.get('note_id') == note_id]
        if len(matches) != 1: raise ValueError('unique reading evidence required')
        evidence = matches[0]
        current(evidence['verified_at'],now)
        if (evidence.get('body_read') is not True or evidence.get('visible_comments_read') is not True
            or not evidence.get('media_reviewed') or evidence.get('comment_candidate') is not True):
            raise ValueError('complete comment-relevant reading evidence required')
        # Readbacks are operational evidence, not a substitute for the existing cross-account history audit.
        if item.get('cross_account_history_checked') is not True or item.get('previously_submitted') is not False:
            raise ValueError('cross-account historical deduplication required')
        output.append({'note_id':note_id,'title':evidence['title'],'text':text,'selectors':item['selectors']})
        seen_ids.add(note_id); seen_texts.add(normalized)
    expiry = min(now + timedelta(minutes=10), now.astimezone(CST).replace(hour=23,minute=59,second=59,microsecond=999000))
    return {'contract_id':CONTRACT,'batch_id':source['batch_id'],'date':source['date'],
            'account_slot':source['account_slot'],'expected_profile_id':identity['expected_profile_id'],
            'mcp_server':f"playwright_browser_slot_{source['account_slot']}",
            'human_final_submission_required':True,'expires_at':expiry.isoformat(),
            'items':output}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('input_file'); parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    output=local(args.output_dir)
    if output.exists(): raise ValueError('use a new output directory')
    batch=compile_batch(read(args.input_file))
    source=(ROOT/'scripts/xhs_comment_batch_handoff.mjs').read_text(encoding='utf-8').replace('export async function','async function',1)
    code='async (page) => {\n'+source+'\nreturn await prepareCommentBatch(page,'+json.dumps(batch,ensure_ascii=False)+');\n}'
    output.mkdir(parents=True,exist_ok=False)
    (output/'prepare_four_pages.js').write_text(code,encoding='utf-8')
    (output/'batch.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'compiled_not_prefilled','items':4,'mcp_server':batch['mcp_server'],
                      'expires_at':batch['expires_at'],'automatic_submission_performed':False},ensure_ascii=False))

if __name__=='__main__': main()
