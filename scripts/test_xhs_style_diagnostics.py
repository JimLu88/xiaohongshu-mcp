import contextlib
import io
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

import run_xhs_article_style_lab as runner
from xhs_style_diagnostics import DiagnosticProvider, failure_diagnostics, safe_provider_note


class DiagnosticsTests(unittest.TestCase):
    def observer(self, **overrides):
        result = SimpleNamespace(ok=True, text='secret generated text', note='',
                                 model_id=runner.MODEL, provider=runner.PROVIDER)
        for key, value in overrides.items():
            setattr(result, key, value)
        delegate = SimpleNamespace(generate=Mock(return_value=result))
        return DiagnosticProvider(delegate, model=runner.MODEL, provider=runner.PROVIDER), result

    def call(self, observer, stage='plan'):
        return observer.generate(system='PRIVATE_SYSTEM', prompt='PRIVATE_SOURCE',
                                 stage=stage, prompt_version='PRIVATE_VERSION')

    def test_transparent_delegate_and_no_body(self):
        observer, result = self.observer()
        self.assertIs(self.call(observer), result)
        observer.delegate.generate.assert_called_once_with(system='PRIVATE_SYSTEM',
            prompt='PRIVATE_SOURCE', stage='plan', prompt_version='PRIVATE_VERSION')
        serialized = json.dumps(observer.calls)
        for secret in ['PRIVATE_SYSTEM', 'PRIVATE_SOURCE', 'PRIVATE_VERSION', result.text]:
            self.assertNotIn(secret, serialized)
        self.assertTrue(observer.calls[0]['exact_model_match'])

    def test_failure_note_and_stage(self):
        observer, _ = self.observer(ok=False, text='', note='Rate limit reached; Bearer sk-PRIVATE_TOKEN')
        self.call(observer, 'draft')
        record = failure_diagnostics(RuntimeError('draft provider call failed: PRIVATE_SOURCE'), observer)
        self.assertEqual(record['failed_stage'], 'draft')
        self.assertEqual(record['failure_kind'], 'provider_call')
        self.assertEqual(record['provider_note'], 'provider_reports_rate_limit')
        self.assertNotIn('PRIVATE', json.dumps(record))

    def test_provider_exception_is_not_swallowed_or_retried(self):
        observer, _ = self.observer()
        exc = TimeoutError('timed out; prompt=PRIVATE_SOURCE')
        observer.delegate.generate.side_effect = exc
        with self.assertRaises(TimeoutError) as caught:
            self.call(observer)
        self.assertIs(caught.exception, exc)
        self.assertEqual(observer.call_count, 1)
        self.assertIn('timeout', observer.calls[-1]['provider_note'])

    def test_empty_trace_does_not_claim_model_invocation(self):
        observer, _ = self.observer()
        record = failure_diagnostics(ValueError('PRIVATE_SOURCE'), observer)
        self.assertEqual(record['failed_stage'], 'before_provider')
        self.assertEqual(record['provider_call_count'], 0)
        self.assertNotIn('PRIVATE_SOURCE', json.dumps(record))

    def test_validation_omits_input_custom_message_and_dynamic_keys(self):
        from pydantic import BaseModel, ConfigDict, ValidationError
        class Payload(BaseModel):
            model_config = ConfigDict(extra='forbid')
            title: str
        observer, _ = self.observer()
        self.call(observer)
        try:
            try:
                Payload.model_validate({'title': ['PRIVATE_SOURCE'], 'PRIVATE_FIELD': 'sk-PRIVATE'})
            except ValidationError as cause:
                raise RuntimeError('plan provider output does not match the structured contract: ' + str(cause)) from cause
        except RuntimeError as exc:
            record = failure_diagnostics(exc, observer)
        self.assertEqual(record['validation_errors'][0]['location'], ['title'])
        self.assertTrue(record['validation_errors'])
        self.assertNotIn('PRIVATE', json.dumps(record))
        self.assertNotIn('input', json.dumps(record))

    def test_notes_never_preserve_arbitrary_text(self):
        for raw in ['Cookie: SECRET', 'https://host/?token=SECRET', 'full prompt SECRET',
                    'Bearer SECRET', 'unknown error\n' + 'SECRET' * 10000]:
            self.assertEqual(safe_provider_note(raw), 'unrecognized_provider_note_redacted')

    def test_failed_result_model_metadata_is_not_echoed(self):
        observer, _ = self.observer(model_id='PRIVATE_MODEL', provider='PRIVATE_PROVIDER')
        self.call(observer)
        self.assertFalse(observer.calls[0]['exact_model_match'])
        self.assertFalse(observer.calls[0]['exact_provider_match'])
        self.assertNotIn('PRIVATE', json.dumps(observer.calls))

    def test_bounded_calls_unknown_stage(self):
        observer, _ = self.observer()
        for _ in range(20):
            self.call(observer, 'PRIVATE_STAGE')
        self.assertEqual(len(observer.calls), 12)
        self.assertEqual(observer.call_count, 20)
        self.assertNotIn('PRIVATE', json.dumps(observer.calls))

    def test_main_writes_safe_failure_receipt_and_preserves_preparation(self):
        observer, _ = self.observer(ok=False, text='', note='exit code 1; token=PRIVATE_TOKEN')
        module = ModuleType('base.xiaohongshu_style')
        module.CodexSubscriptionStyleProvider = Mock(return_value=observer.delegate)
        def fail(request, *, provider):
            self.call(provider, 'draft')
            raise RuntimeError('draft provider call failed: PRIVATE_SOURCE')
        module.generate_style_content = fail
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'new-run'
            prepared = {'publish_allowed': False, 'model_invoked': False, 'text_generated': False}
            with patch.object(runner, 'ROOT', Path(directory)), \
                    patch.object(runner, 'prepare', return_value=(object(), prepared)), \
                    patch('sys.argv', ['runner', 'fixture.json', '--output-dir', str(output), '--generate']), \
                    patch.dict('sys.modules', {'base.xiaohongshu_style': module}), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 1)
            saved = json.loads((output / 'generation_receipt.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['failed_stage'], 'draft')
            self.assertFalse(saved['publish_allowed'])
            self.assertFalse(saved['publication_performed'])
            self.assertEqual(saved['provider_note'], 'exit_code=1')
            self.assertNotIn('PRIVATE', json.dumps(saved))
            self.assertFalse((output / 'style_lab_result.json').exists())
            self.assertFalse(json.loads((output / 'preparation.json').read_text())['model_invoked'])

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runner, 'ROOT', Path(directory)), patch.object(runner, 'prepare') as prepare, \
                    patch('sys.argv', ['runner', 'fixture', '--output-dir', directory, '--generate']):
                with self.assertRaisesRegex(ValueError, 'never overwritten'):
                    runner.main()
                prepare.assert_not_called()


if __name__ == '__main__':
    unittest.main()
