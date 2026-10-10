"""One bounded, source-free provider probe. Not a business article run."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import sys

from run_xhs_article_style_lab import DEFAULT_CONTRACT, MODEL, PROVIDER, local_path, read_json
from xhs_style_diagnostics import DiagnosticProvider, failure_diagnostics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-file', required=True)
    args = parser.parse_args()
    output = local_path(args.output_file)
    if output.exists():
        raise ValueError('diagnostic evidence must use a new file')
    contract = read_json(DEFAULT_CONTRACT)
    sys.path.insert(0, contract['style_lab']['runtime_root'])
    os.environ['TK_STYLE_CARD_DB'] = contract['style_lab']['style_card_db']
    os.environ['TK_CODEX_TIMEOUT'] = '60'
    os.environ['TK_CODEX_DLL_INIT_RETRIES'] = '0'
    from base.xiaohongshu_style import CodexSubscriptionStyleProvider
    observer = DiagnosticProvider(CodexSubscriptionStyleProvider(MODEL), model=MODEL, provider=PROVIDER)
    receipt = {'schema_version': 1, 'scope': 'source_free_technical_provider_probe',
               'required_model': MODEL, 'fallback_allowed': False, 'publish_allowed': False,
               'publication_performed': False, 'article_generation_performed': False,
               'started_at': datetime.now(timezone.utc).isoformat(), 'timeout_seconds': 60,
               'max_provider_calls': 1}
    try:
        result = observer.generate(system='Return only the exact JSON object requested. Do not use tools.',
                                   prompt='Return exactly {"diagnostic":"ok"}.',
                                   stage='plan', prompt_version='source-free-provider-diagnostic.v1')
        try:
            matches = json.loads(result.text) == {'diagnostic': 'ok'}
        except (ValueError, TypeError):
            matches = False
        passed = (result.ok is True and result.model_id == MODEL and result.provider == PROVIDER and matches)
        receipt.update(status='passed' if passed else 'blocked_provider_diagnostic',
                       expected_json_verified=matches, provider_diagnostics=observer.calls)
    except Exception as exc:
        receipt.update(status='blocked_provider_diagnostic', **failure_diagnostics(exc, observer))
    receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
