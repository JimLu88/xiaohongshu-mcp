"""Body-free diagnostics. Never serialize arbitrary exceptions or provider text."""
from __future__ import annotations

import re
import time

STAGES = {'plan', 'draft', 'semantic_review'}
ERROR_TYPES = {'XiaohongshuStyleError', 'ValidationError', 'ValueError', 'RuntimeError',
               'TimeoutError', 'TimeoutExpired', 'OSError', 'FileNotFoundError',
               'ConnectionError', 'JSONDecodeError', 'TypeError'}
VALIDATION_TYPES = {'missing', 'extra_forbidden', 'literal_error', 'string_type',
                    'int_type', 'bool_type', 'list_type', 'dict_type', 'model_type',
                    'value_error', 'too_short', 'too_long', 'string_too_short',
                    'string_too_long', 'greater_than', 'less_than'}
FIELDS = {'plan', 'draft', 'semantic_review', 'draft_text', 'title', 'body', 'blocks',
          'covered_fact_ids', 'fact_id', 'content_contract', 'protected_facts',
          'source_fact_ids', 'fact_ids', 'citation_anchor', 'citation_anchors',
          'style_plan', 'title_candidates', 'structure', 'paragraphs', 'hashtags',
          'hook', 'ending', 'rationale', 'quality', 'hard_failures', 'passed'}


def error_type(exc):
    name = type(exc).__name__
    return name if name in ERROR_TYPES else 'OtherError'


def safe_provider_note(value):
    """Retain recognized diagnostics, not stderr tails that may echo input/auth."""
    raw = str(value or '')[:16000].lower()
    if not raw:
        return ''
    markers = []
    patterns = [
        ('provider_reports_rate_limit', r'rate.?limit|usage limit|hit your limit|用量到限'),
        ('provider_reports_auth_error', r'unauthorized|authentication|not logged in|401\b'),
        ('provider_reports_model_unavailable', r'model.{0,80}(not found|not supported|unsupported|unavailable)'),
        ('provider_reports_timeout', r'timed out|timeout|超时'),
        ('provider_reports_network_error', r'connection|network|tls|dns|502\b|503\b'),
        ('provider_reports_invalid_argument', r'unexpected argument|unrecognized argument|invalid argument'),
        ('provider_reports_missing_cli', r'cli 未找到|cli 未启动|no such file'),
    ]
    for label, pattern in patterns:
        if re.search(pattern, raw):
            markers.append(label)
    for code in re.findall(r'\b(?:exit|exit code|returncode)\s*[:=]?\s*(-?\d{1,10})\b', raw)[:2]:
        markers.append('exit_code=' + code)
    return '; '.join(markers)[:400] or 'unrecognized_provider_note_redacted'


def safe_error_message(exc):
    raw = str(exc)[:16000]
    # Only fixed, vetted phrases are retained; their dynamic suffixes are not.
    phrases = (
        'provider output is not valid JSON', 'provider output must be a JSON object',
        'provider output does not match the structured contract', 'provider call failed',
        'model mismatch', 'plan failed the structured and fact-grounding contract after one repair attempt',
        'draft failed the structured contract after one repair attempt',
    )
    matched = [phrase for phrase in phrases if phrase in raw]
    return '; '.join(matched)[:500] or 'runtime failure; unrecognized error text redacted'


class DiagnosticProvider:
    """Transparent delegate: no prompt/result retention, no retry or model change."""
    def __init__(self, delegate, *, model, provider):
        self.delegate = delegate
        self.model = model
        self.provider = provider
        self.calls = []
        self.call_count = 0

    def generate(self, *, system, prompt, stage, prompt_version):
        row = {'stage': stage if stage in STAGES else 'unknown',
               'provider_invocation_attempted': True, 'returned': False}
        self.call_count += 1
        self.calls.append(row)
        self.calls[:] = self.calls[-12:]
        started = time.monotonic()
        try:
            result = self.delegate.generate(system=system, prompt=prompt, stage=stage,
                                            prompt_version=prompt_version)
            row.update(returned=True, ok=result.ok is True, text_present=bool(result.text),
                       exact_model_match=result.model_id == self.model,
                       exact_provider_match=result.provider == self.provider,
                       provider_note=safe_provider_note(result.note))
            return result
        except Exception as exc:
            row.update(ok=False, error_type=error_type(exc), provider_note=safe_provider_note(str(exc)))
            raise
        finally:
            row['elapsed_seconds'] = round(time.monotonic() - started, 3)


def failure_diagnostics(exc, observer):
    stage = observer.calls[-1]['stage'] if observer.calls else 'before_provider'
    message = safe_error_message(exc)
    # A returned provider result followed by an error is different from a failed call.
    failure_kind = ('provider_call' if observer.calls and not observer.calls[-1].get('ok')
                    else 'runtime_validation_or_processing')
    validation = []
    origins = []
    seen = set()
    cause = exc
    while cause is not None and id(cause) not in seen and len(seen) < 6:
        seen.add(id(cause))
        frame = cause.__traceback__
        while frame is not None:
            code = frame.tb_frame.f_code
            if (frame.tb_frame.f_globals.get('__name__') == 'base.xiaohongshu_style'
                    and re.fullmatch(r'_?[a-z_]{1,70}', code.co_name)):
                origins.append({'module': 'base.xiaohongshu_style',
                                'function': code.co_name, 'line': frame.tb_lineno})
            frame = frame.tb_next
        if type(cause).__name__ == 'ValidationError' and type(cause).__module__.startswith('pydantic'):
            for item in cause.errors(include_input=False, include_context=False, include_url=False)[:12]:
                validation.append({
                    'type': item['type'] if item['type'] in VALIDATION_TYPES else 'other_validation_error',
                    'location': [part if isinstance(part, int) and 0 <= part <= 10000
                                 else part if isinstance(part, str) and part in FIELDS
                                 else '[field]' for part in item.get('loc', ())[:8]],
                })
        cause = cause.__cause__ or cause.__context__
    return {'diagnostics_version': 1, 'error_type': error_type(exc),
            'error_message': message, 'error_message_policy': 'allowlisted_summary_dynamic_text_redacted',
            'failed_stage': stage, 'stage_evidence': 'last_provider_call' if observer.calls else 'no_provider_call',
            'failure_kind': failure_kind, 'provider_call_count': observer.call_count,
            'provider_diagnostics': observer.calls,
            'provider_note': observer.calls[-1].get('provider_note', '') if observer.calls else '',
            'validation_errors': validation[:12], 'runtime_error_origins': origins[-12:]}
