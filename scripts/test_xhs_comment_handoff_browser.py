"""Real headless browser; every HTTP request is fulfilled locally or aborted."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import socket
import subprocess
import unittest

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

class BatchBrowserTests(unittest.TestCase):
    def setUp(self):
        self.p=sync_playwright().start()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); self.port=sock.getsockname()[1]
        self.browser=self.p.chromium.launch(headless=True,args=[f'--remote-debugging-port={self.port}'])
        self.context=self.browser.new_context()
        self.fixture=(ROOT/'scripts/tests/comment_batch_fixture.html').read_text(encoding='utf-8')
        self.context.route('**/*',lambda route: route.fulfill(status=200,content_type='text/html',body=self.fixture)
                           if route.request.is_navigation_request() else route.abort())
        self.pages=[]
        self.batch={'contract_id':'panse-xhs-comment-batch-handoff.v1','batch_id':'local-test',
                    'account_slot':3,'expected_profile_id':'1'*24,'human_final_submission_required':True,
                    'date':datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
                    'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat(),'items':[]}
        for index in range(4):
            note=f'{index+2:024x}'
            page=self.context.new_page()
            page.goto(f'https://www.xiaohongshu.com/explore/{note}')
            page.wait_for_load_state('networkidle')
            self.pages.append(page)
            self.batch['items'].append({'note_id':note,'title':'本地模拟帖子','text':f'本地模拟评论{index+1}',
                 'selectors':{'editor':'#editor','title':'#title','comments':'#comments','send':'#send'}})
        self.worker=None

    def tearDown(self):
        if self.worker:
            self.worker.terminate()
            self.worker.communicate(timeout=5)
        self.browser.close(); self.p.stop()

    def run_batch(self):
        self.worker=subprocess.Popen(['node',str(ROOT/'scripts/tests/run_comment_batch_fixture.mjs')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        self.worker.stdin.write(json.dumps({'endpoint':f'http://127.0.0.1:{self.port}','batch':self.batch},ensure_ascii=False)+'\n')
        self.worker.stdin.flush()
        # stdout deadline is enforced by the enclosing test command; browser actions have 5s timeout.
        line=self.worker.stdout.readline()
        if not line: self.fail(self.worker.stderr.read()[:500])
        return json.loads(line)

    def test_four_pages_ready_without_send_then_manual_click(self):
        result=self.run_batch()
        self.assertEqual(result['status'],'ready_for_human_batch',result)
        self.assertEqual(result['ready_count'],4)
        for index,page in enumerate(self.pages):
            self.assertEqual(page.locator('#editor').input_value(),f'本地模拟评论{index+1}')
            self.assertEqual(page.evaluate('window.testSent'),0)
        for page in self.pages:
            page.locator('#send').click()  # Simulated HUMAN action, never in production helper.
            self.assertEqual(page.evaluate('window.testSent'),1)
            page.locator('#send').click()
            self.assertEqual(page.evaluate('window.testSent'),1)  # No double-click resend.
        self.assertTrue(result['browser_window_bounds_verified'])

    def test_existing_draft_blocks_before_any_fill(self):
        self.pages[3].locator('#editor').fill('用户已有草稿')
        result=self.run_batch()
        self.assertEqual(result['status'],'paused')
        self.assertFalse(result['notify_user'])
        self.assertEqual(self.pages[0].locator('#editor').input_value(),'')
        self.assertEqual(self.pages[3].locator('#editor').input_value(),'用户已有草稿')

    def test_wrong_account_blocks_whole_batch(self):
        self.pages[2].locator('a').evaluate('(el)=>el.href="/user/profile/999999999999999999999999"')
        self.assertEqual(self.run_batch()['reason'],'identity_mismatch_or_unknown')

    def test_risk_after_ready_pauses_all_four(self):
        self.assertEqual(self.run_batch()['status'],'ready_for_human_batch')
        self.pages[1].locator('#risk').evaluate('(el)=>el.textContent="操作过于频繁"')
        self.pages[0].wait_for_function('window.__panseBatchGuard.phase === "paused"')
        self.pages[0].locator('#send').click()
        self.assertEqual(self.pages[0].evaluate('window.testSent'),0)

    def test_normal_post_send_disabled_button_does_not_pause_remaining(self):
        self.assertEqual(self.run_batch()['status'],'ready_for_human_batch')
        self.pages[0].locator('#send').click()
        self.pages[0].evaluate('document.querySelector("#send").disabled=true;document.querySelector("#editor").value=""')
        self.pages[1].locator('#send').click()
        self.assertEqual(self.pages[1].evaluate('window.testSent'),1)

    def test_duplicate_existing_comment_blocks(self):
        self.pages[0].locator('#comments p').evaluate('(el)=>el.textContent="本地模拟评论1"')
        self.assertEqual(self.run_batch()['reason'],'duplicate_comment')

    def test_ambiguous_editor_blocks(self):
        self.pages[0].locator('#editor').evaluate('(el)=>el.after(el.cloneNode())')
        self.assertEqual(self.run_batch()['reason'],'ambiguous_or_uneditable_page')

    def test_expired_batch_blocks(self):
        self.batch['expires_at']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
        self.assertEqual(self.run_batch()['status'],'paused')

    def test_expiry_closes_only_four_owned_tabs(self):
        extra=self.context.new_page()
        self.batch['expires_at']=(datetime.now(timezone.utc)+timedelta(seconds=5)).isoformat()
        self.assertEqual(self.run_batch()['status'],'ready_for_human_batch')
        with self.pages[0].expect_event('close',timeout=10000):
            pass
        # Extra tab stays open; complete slot cleanup remains the owning task's job.
        extra.wait_for_function('true')
        self.assertFalse(extra.is_closed())

    def test_disabled_send_never_reports_ready(self):
        self.pages[3].locator('#send').evaluate('(el)=>el.disabled=true')
        self.assertEqual(self.run_batch()['reason'],'send_button_not_ready')

    def test_changed_target_while_waiting_pauses_all(self):
        self.assertEqual(self.run_batch()['status'],'ready_for_human_batch')
        self.pages[2].locator('#title').evaluate('(el)=>el.textContent="页面已经换了"')
        self.pages[0].wait_for_function('window.__panseBatchGuard.phase === "paused"')
        self.assertEqual(self.pages[0].evaluate('window.testSent'),0)

    def test_input_triggered_write_aborted(self):
        self.pages[0].evaluate('document.querySelector("#editor").addEventListener("input",()=>fetch("/fake-comment",{method:"POST"}).catch(()=>{}))')
        result=self.run_batch()
        self.assertEqual(result['status'],'paused',result)
        self.assertFalse(result['notify_user'])
        self.assertEqual(self.pages[0].evaluate('window.testSent'),0)

if __name__=='__main__': unittest.main()
