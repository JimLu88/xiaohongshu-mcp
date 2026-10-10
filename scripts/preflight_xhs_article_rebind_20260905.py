"""Prepare and validate a candidate catalog rebind, preserving approved voices."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/panse_multi_direction/cooperation_20260905'
SOURCE = ROOT / 'research/panse_multi_direction/xhs_article_style_contract_v2.json'

def main():
    old = json.loads(SOURCE.read_text(encoding='utf-8'))
    reply = json.loads((SOURCE.parent / 'xhs_reply_style_contract_v3.json').read_text(encoding='utf-8'))
    new = copy.deepcopy(old)
    style = new['style_lab']
    style['runtime_root'] = reply['style_lab']['runtime_root']
    style['style_card_db'] = reply['style_lab']['style_card_db']
    os.environ['TK_STYLE_CARD_DB'] = style['style_card_db']
    sys.path.insert(0, style['runtime_root'])
    from chatgpt_mcp import style_taxonomy
    from base.xiaohongshu_style import StyleWritingRequest, prepare_style_bundle
    from validate_xhs_article_style_contract import profile_fingerprint, current_generate_card_count, validate
    catalog = style_taxonomy.load_taxonomy()
    style.update(catalog_version=catalog.catalog_version,
                 catalog_sha256=style_taxonomy.taxonomy_sha256(),
                 declared_taxonomy_count=len(catalog.entries),
                 approved_generate_card_count=current_generate_card_count(Path(style['style_card_db'])))
    for index, profile in enumerate(new['direction_profiles']):
        # Only provenance changes; persona/card versions, strength, output and gates remain intact.
        profile['direction_profile_sha256'] = profile_fingerprint(new, profile)
        request = StyleWritingRequest(
            request_id=f'panse.article-contract.{index}',
            idempotency_key=f"panse:article-contract:{profile['direction']}:v2",
            brief_text=f"这是畔色小红书正文方向 {profile['direction']} 的本地风格契约复验 brief；只验证已批准风格卡、事实合同、体裁和质量流程，不生成或发布正文。",
            source_locator=f"local://panse/article-contract/{profile['direction']}",
            rights_basis='project-owned contract validation fixture', sensitivity='internal',
            audience='正在做家具购买、家居布置或空间决策的小红书读者', use_case='小红书家具家居正文风格预检',
            artifact_type='article', taxonomy_ids=profile['taxonomy_ids'],
            style_card_refs=profile['approved_card_refs'], requested_strength=profile['requested_strength'],
            style_requirement='approved_required', pin_card_versions=True,
            required_model_id='gpt-5.6-sol', fallback_model_allowed=False,
            content_contract={'protected_facts': [], 'allowed_paraphrases': {},
                              'forbidden_inferences': ['不得虚构产品测试、消费者体验或第三方背书', '不得把 AI 合成图描述为真实空间或产品实拍'],
                              'citation_anchors': {}, 'must_cover_fact_ids': []},
            output=profile['output'])
        bundle, _ = prepare_style_bundle(request)
        profile['preflight_bundle_id'] = bundle['bundle_id']
        profile['preflight_bundle_sha256'] = bundle['bundle_sha256']
    new['validated_at'] = '2026-09-05'
    target = OUT / 'article_style_contract_rebound_candidate.json'
    target.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding='utf-8')
    result = validate(target)
    result.update(original_failure='live taxonomy catalog version drifted', candidate_path=str(target),
                  approved_card_versions_changed=False, output_limits_changed=False,
                  model_invoked=False, production_contract_modified=False)
    (OUT / 'article_style_rebind_preflight.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
