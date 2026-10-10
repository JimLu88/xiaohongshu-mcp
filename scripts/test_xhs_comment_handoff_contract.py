from datetime import datetime,timedelta,timezone
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import build_xhs_comment_handoff as builder
from lib.xhs_comment_length_mix import build_length_assignment,validate_generated_comment_length,allocate_length_tiers

class HumanBatchContractTests(unittest.TestCase):
    def context(self,index=1):
        return {'policy_id':'panse-xhs-comment-length-mix.v1','batch_id':'test-batch',
                'batch_size':4,'item_index':index,'delivery_mode':'human_final_batch',
                'human_final_submission_required':True,'assigned_tier':'short','eligible_tiers':['short']}

    def test_four_item_context_keeps_individual_bounds(self):
        for index in range(1,5):
            assignment=build_length_assignment(self.context(index))
            self.assertFalse(assignment['batch_percentage_quota_applied'])
            self.assertTrue(assignment['human_final_submission_required'])
            validate_generated_comment_length('这个细节确实方便',assignment)
            with self.assertRaises(ValueError): validate_generated_comment_length('太长'*30,assignment)

    def test_legacy_percentage_rule_unchanged(self):
        with self.assertRaises(ValueError): allocate_length_tiers(4)
        self.assertEqual(sum(allocate_length_tiers(10).values()),10)

    def test_small_batch_does_not_expand_to_auto_or_unknown(self):
        for key,value in [('human_final_submission_required',False),('batch_size',5),
                          ('assigned_tier','long'),('delivery_mode','auto')]:
            context=self.context(); context[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): build_length_assignment(context)

    def fixture(self):
        now=datetime.now(timezone.utc)
        stamp=(now-timedelta(seconds=1)).isoformat()
        date=now.astimezone(builder.CST).date().isoformat()
        source={'batch_id':'test-batch','date':date,'account_slot':3,'session_probe_file':'session','items':[]}
        docs={'session':{'contract_id':'panse-xhs-session-probe.v1','status':'valid','account_slot':3,
                        'expected_profile_id':'1'*24,'risk_signal_observed':False,'observed_at':stamp}}
        preflights={}
        for index in range(1,5):
            note=f'{index:024x}'
            request={'artifact_type':'comment','request_id':f'test-{index}',
                     'source_locator':'https://www.xiaohongshu.com/explore/'+note,
                     'panse_comment_length_context':self.context(index)}
            assignment=build_length_assignment(self.context(index))
            docs[f'request{index}']=request
            docs[f'run{index}']={'observed_at':stamp,'receipt_type':'panse_xhs_actual_style_lab_run',
                'request_id':request['request_id'],'external_posting_performed':False,
                'candidate_input_sha256':hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                'style_lab_result':{'draft':{'draft_text':f'这个模拟细节{index}'}}}
            docs[f'read{index}']={'date':date,'account_slot':3,'items':[{'note_id':note,'title':'test',
                'body_read':True,'visible_comments_read':True,'media_reviewed':'local mock media',
                'comment_candidate':True,'verified_at':stamp}]}
            preflights[f'request{index}']={'comment_length_mix':assignment,'production_contract':{'account_slot':3}}
            source['items'].append({'note_id':note,'selectors_observed_at':stamp,'style_request_file':f'request{index}',
                'style_run_file':f'run{index}','read_receipt_file':f'read{index}',
                'cross_account_history_checked':True,'previously_submitted':False,
                'selectors':{'editor':'#editor','title':'#title','comments':'#comments','send':'#send'}})
        return now,source,docs,preflights

    def compile(self,now,source,docs,preflights):
        with patch.object(builder,'read',side_effect=lambda path: docs[path]), \
             patch.object(builder,'load_expected_identity',return_value={'expected_profile_id':'1'*24}), \
             patch.object(builder,'compile_project_preflight',side_effect=lambda path:preflights[path.name]), \
             patch.object(builder,'verify_actual_run') as verify:
            result=builder.compile_batch(source,now)
            self.assertEqual(verify.call_count,4)
            return result

    def test_current_four_complete_receipts_compile_only(self):
        args=self.fixture(); result=self.compile(*args)
        self.assertEqual(len(result['items']),4)
        self.assertEqual(result['mcp_server'],'playwright_browser_slot_3')
        self.assertTrue(result['human_final_submission_required'])

    def test_stale_session_rejected(self):
        now,source,docs,preflights=self.fixture()
        docs['session']['observed_at']=(now-timedelta(minutes=11)).isoformat()
        with self.assertRaises(ValueError): self.compile(now,source,docs,preflights)

    def test_edited_source_hash_rejected(self):
        now,source,docs,preflights=self.fixture()
        docs['request1']['brief_text']='changed after generation'
        with self.assertRaises(ValueError): self.compile(now,source,docs,preflights)

    def test_duplicate_or_sent_item_rejected(self):
        for mutation in ['duplicate','sent','wrong_slot','missing_read']:
            now,source,docs,preflights=self.fixture()
            if mutation=='duplicate': source['items'][1]['note_id']=source['items'][0]['note_id']
            if mutation=='sent': source['items'][0]['previously_submitted']=True
            if mutation=='wrong_slot': preflights['request1']['production_contract']['account_slot']=2
            if mutation=='missing_read': docs['read1']['items'][0]['visible_comments_read']=False
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): self.compile(now,source,docs,preflights)

if __name__=='__main__':unittest.main()
