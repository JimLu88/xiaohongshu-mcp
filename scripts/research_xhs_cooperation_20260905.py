"""Bounded, public-document-only research. Never imports or runs remote code."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import urllib.error
import urllib.request
import urllib.parse
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/panse_multi_direction/cooperation_20260905/evidence'
PROJECTS = [
    'white0dew/XiaohongshuSkills', 'jackwener/xiaohongshu-cli',
    'jackwener/xhs-cli', 'Xiangyu-CAS/xiaohongshu-ops-skill',
    '3441293738/creatorhub', 'xpzouying/xiaohongshu-mcp',
    'NanmiCoder/MediaCrawler', 'ReaJason/xhs',
    'HisMax/RedInk', 'comeonzhj/Auto-Redbook-Skills',
    'Jamailar/Beav', 'gitcoffee-os/postbot',
    'dreammis/social-auto-upload', 'iszhouhua/social-media-copilot',
    'devtang/ai-xiaohongshu', 'chenhg5/xiaohongshu-mcp',
    'browser-use/browser-use', 'browserbase/stagehand',
    'microsoft/playwright', 'microsoft/playwright-mcp',
    'ChromeDevTools/chrome-devtools-mcp', 'hangwin/mcp-chrome',
    'jackwener/OpenCLI', 'epiral/bb-browser',
    'Skyvern-AI/skyvern', 'vercel-labs/agent-browser',
    'rrweb-io/rrweb', 'puppeteer/puppeteer',
    'SeleniumHQ/selenium', 'domagent/domagent',
    'langchain-ai/langgraph', 'temporalio/sdk-python',
    'PrefectHQ/prefect', 'dbos-inc/dbos-transact-py',
    'n8n-io/n8n', 'activepieces/activepieces',
    'PostHog/posthog', 'getsentry/sentry',
    'remotion-dev/remotion', 'mermaid-js/mermaid',
    'toeverything/AFFiNE', 'AppFlowy-IO/AppFlowy',
]

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Panse-public-research/1.0'})
    with urllib.request.urlopen(request, timeout=18) as response:
        data = response.read(900_000)
        return data, response.url

def project(repo):
    result = {'repo': repo, 'url': 'https://github.com/' + repo,
              'observed_at': datetime.now(timezone.utc).isoformat(),
              'evidence_level': 'unverified', 'attempts': []}
    for filename in ['README.md', 'readme.md', 'README.zh-CN.md']:
        url = f'https://raw.githubusercontent.com/{repo}/HEAD/{filename}'
        try:
            data, final_url = fetch(url)
            body = data.decode('utf-8', errors='replace')
            path = OUT / (repo.replace('/', '__') + '.md')
            path.write_text(body, encoding='utf-8')
            result.update(source_url=final_url, local_source=str(path.relative_to(ROOT)),
                          sha256=hashlib.sha256(data).hexdigest(), chars=len(body),
                          evidence_level='primary_readme_fetched')
            break
        except Exception as exc:
            result['attempts'].append({'url': url, 'error': type(exc).__name__})
    return result

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if '--frontier' in sys.argv:
        extra = [
            'sunshinehugeboy/xiaohongshu-RAG-agent',
            'tbb390/xiaohongshu-monitor-agent',
            'wang-bool/xiaohongshu-storycraft',
            'soarsky1991/xiaohongshu-creator-skills',
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(project, extra))
        (OUT / 'frontier_manifest.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if '--details' in sys.argv:
        details = []
        for repo in PROJECTS[:6]:
            try:
                data, _ = fetch('https://api.github.com/repos/' + repo)
                meta = json.loads(data)
                item = {key: meta.get(key) for key in ['full_name', 'description', 'created_at', 'pushed_at', 'archived', 'default_branch', 'license']}
                branch = meta.get('default_branch', 'main')
                raw, _ = fetch(f'https://api.github.com/repos/{repo}/commits/{branch}')
                commit = json.loads(raw)
                item['head_commit'] = commit.get('sha')
                item['commit_url'] = commit.get('html_url')
                details.append(item)
                print(json.dumps(item, ensure_ascii=False), flush=True)
            except Exception as exc:
                print(repo, type(exc).__name__, flush=True)
        (OUT / 'priority_metadata.json').write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
        sources = [
            ('white0dew/XiaohongshuSkills', 'scripts/publish_pipeline.py'),
            ('white0dew/XiaohongshuSkills', 'scripts/cdp_publish.py'),
            ('Xiangyu-CAS/xiaohongshu-ops-skill', 'SKILL.md'),
            ('Xiangyu-CAS/xiaohongshu-ops-skill', 'references/xhs-publish-flows.md'),
            ('Xiangyu-CAS/xiaohongshu-ops-skill', 'references/xhs-comment-ops.md'),
            ('jackwener/xiaohongshu-cli', 'xiaohongshu_cli/commands/interactions.py'),
            ('jackwener/xiaohongshu-cli', 'pyproject.toml'),
        ]
        for repo, relative in sources:
            url = f'https://raw.githubusercontent.com/{repo}/HEAD/{relative}'
            try:
                data, _ = fetch(url)
                target = OUT / (repo.replace('/', '__') + '__' + relative.replace('/', '__') + '.txt')
                target.write_bytes(data)
                print(json.dumps({'source_url': url, 'local_file': target.name, 'bytes': len(data)}, ensure_ascii=False), flush=True)
            except Exception as exc:
                print(url, type(exc).__name__, flush=True)
        for query in ['xiaohongshu in:name language:Python', 'xiaohongshu skill in:name']:
            try:
                data, _ = fetch('https://api.github.com/search/repositories?q=' + urllib.parse.quote(query) + '&sort=updated&per_page=8')
                rows = [{key: row.get(key) for key in ['full_name', 'description', 'html_url', 'pushed_at', 'created_at']} for row in json.loads(data).get('items', [])]
                details.append({'search_query': query, 'results': rows})
                print(json.dumps(details[-1], ensure_ascii=False), flush=True)
            except Exception as exc:
                print(query, type(exc).__name__, flush=True)
        (OUT / 'priority_metadata_and_search.json').write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
        return
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(project, repo): repo for repo in PROJECTS}
        for future in as_completed(futures):
            item = future.result()
            results.append(item)
            print(json.dumps({k: item.get(k) for k in ['repo', 'evidence_level', 'chars']}, ensure_ascii=False), flush=True)
    results.sort(key=lambda row: PROJECTS.index(row['repo']))
    (OUT / 'manifest.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
