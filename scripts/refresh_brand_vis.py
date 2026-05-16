#!/usr/bin/env python3
"""
refresh_brand_vis.py

Fetches all prompt histories, recomputes brand_global_vis from ALL brand
mentions across the full time range, and patches it into dashboard.html.

Run this after generate_snapshot.py if you notice the Competitors view is
missing brands that appear in the live aipeekaboo.com/dashboard — it ensures
every brand scored above the threshold is included, not just the top 20.

Required environment variables:
  PEEKABOO_BRAND_ID   — Brand UUID from aipeekaboo.com/settings
  PEEKABOO_API_KEY    — API key from aipeekaboo.com/settings/integrations

Optional environment variables:
  DASHBOARD_PATH      — Path to dashboard.html (default: dashboard.html in cwd)
  TIME_RANGE          — Data window (default: 30d)

Usage:
  PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx python3 refresh_brand_vis.py

Runtime: ~15-25 min for 40 prompts (full history fetch, rate-limited).
"""

import json, re, sys, time, os
import urllib.request, urllib.parse, urllib.error
from collections import defaultdict

BRAND_ID = os.environ.get('PEEKABOO_BRAND_ID', '').strip()
API_KEY  = os.environ.get('PEEKABOO_API_KEY', '').strip()

if not BRAND_ID or not API_KEY:
    print("ERROR: PEEKABOO_BRAND_ID and PEEKABOO_API_KEY env vars are required.")
    sys.exit(1)

BASE_URL   = "https://www.aipeekaboo.com/api/v1"
DASHBOARD  = os.environ.get('DASHBOARD_PATH', os.path.join(os.path.dirname(__file__), '..', 'dashboard.html'))
DASHBOARD  = os.path.normpath(DASHBOARD)
TIME_RANGE = os.environ.get('TIME_RANGE', '30d')

MODEL_KEY = {
    'chatgpt': 'chatgpt', 'gpt-4': 'chatgpt', 'gpt-4o': 'chatgpt', 'gpt-4o-mini': 'chatgpt',
    'gemini': 'gemini', 'gemini-pro': 'gemini', 'gemini-flash': 'gemini',
    'gemini-2.5-flash': 'gemini', 'gemini-2.0-flash': 'gemini',
    'perplexity': 'perplexity', 'sonar': 'perplexity', 'sonar-pro': 'perplexity',
    'google-aio': 'googleaio', 'google-ai-overview': 'googleaio',
    'google-aim': 'googleaimode', 'google-ai-mode': 'googleaimode',
}

_call_times = []

def _throttle():
    now = time.time()
    _call_times[:] = [t for t in _call_times if now - t < 60]
    if len(_call_times) >= 16:
        wait = 62 - (now - _call_times[0])
        if wait > 0:
            print(f"  [throttle] pausing {wait:.1f}s...", flush=True)
            time.sleep(wait)
    _call_times.append(time.time())

def get(path, **params):
    _throttle()
    url = f"{BASE_URL}/{path}"
    if params:
        url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={"X-API-Key": API_KEY, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read())
                return body.get('data', body)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(62)
            elif attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise
    return {}

def normalize_brand(name):
    n = name.strip()
    n = re.sub(r'([a-zA-Z])\.AI$', r'\1 AI', n, flags=re.IGNORECASE)
    n = re.sub(r'([a-z])([A-Z])', r'\1 \2', n)
    n = n.replace('.', ' ').replace('_', ' ').replace('-', ' ')
    n = re.sub(r'\s+', ' ', n)
    return n.lower().strip()

def main():
    print("Fetching prompts list...", flush=True)
    data = get(f"brands/{BRAND_ID}/prompts")
    if isinstance(data, list):
        prompts = data
    else:
        prompts = data.get('prompts') or data.get('data') or []
    if not prompts:
        print(f"ERROR: No prompts found.")
        sys.exit(1)
    print(f"  Found {len(prompts)} prompts")

    brand_scores    = defaultdict(float)
    brand_canonical = {}
    total_entries   = 0

    for i, p in enumerate(prompts):
        pid  = p.get('promptId') or p.get('id', '')
        text = (p.get('promptText') or p.get('text', ''))[:60]
        print(f"  [{i+1:02d}/{len(prompts)}] {text}", flush=True)

        try:
            det = get(f"brands/{BRAND_ID}/prompts/{pid}", include_full_response='true', time_range=TIME_RANGE)
        except Exception as e:
            print(f"    WARN: fetch failed: {e}")
            continue

        hist = det.get('history') or det.get('data') or []
        for entry in hist:
            raw_model = entry.get('aiModel') or entry.get('model', '')
            if not MODEL_KEY.get(raw_model):
                continue
            entry_date = (entry.get('date') or '')[:10]
            if not entry_date:
                continue

            total_entries += 1
            for bm in (entry.get('brandMentions', []) or []):
                bname = (bm.get('entityName') or '').strip()
                if not bname:
                    continue
                bscore = float(bm.get('score', 0) or 0)
                norm = normalize_brand(bname)
                brand_scores[norm] += bscore
                if norm not in brand_canonical:
                    brand_canonical[norm] = bname

    print(f"\nTotal entries processed : {total_entries}")
    print(f"Unique brands (raw)     : {len(brand_scores)}")

    if total_entries == 0:
        print("ERROR: No entries processed. Aborting.")
        sys.exit(1)

    brand_global_vis = {}
    for norm, total_score in sorted(brand_scores.items(), key=lambda x: -x[1]):
        canonical = brand_canonical[norm]
        vis = round(total_score / total_entries, 2)
        brand_global_vis[canonical] = vis

    print("\nBrands >= 1.0% visibility:")
    for name, vis in sorted(brand_global_vis.items(), key=lambda x: -x[1]):
        if vis >= 1.0:
            print(f"  {name:40s} {vis:.2f}%")

    print(f"\nTotal brands : {len(brand_global_vis)}")
    print(f">= 1.0%      : {sum(1 for v in brand_global_vis.values() if v >= 1.0)}")

    print(f"\nPatching {DASHBOARD} ...", flush=True)
    with open(DASHBOARD, 'r', encoding='utf-8') as f:
        html = f.read()

    key_str = '"brand_global_vis":'
    idx = html.find(key_str)
    if idx < 0:
        print("ERROR: brand_global_vis key not found in dashboard.html.")
        sys.exit(1)

    obj_start = html.index('{', idx + len(key_str))
    depth = 0
    obj_end = obj_start
    for i, c in enumerate(html[obj_start:], obj_start):
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                obj_end = i + 1
                break

    old_count = html[obj_start:obj_end].count('":')
    new_obj   = json.dumps(brand_global_vis, ensure_ascii=False, separators=(',', ':'))
    new_count = new_obj.count('":')

    print(f"  Replacing brand_global_vis: {old_count} brands -> {new_count} brands")
    new_html = html[:obj_start] + new_obj + html[obj_end:]

    with open(DASHBOARD, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print("Done.")
    print("\nTop 10 by visibility:")
    for name, vis in sorted(brand_global_vis.items(), key=lambda x: -x[1])[:10]:
        print(f"  {name}: {vis:.2f}%")


if __name__ == '__main__':
    main()
