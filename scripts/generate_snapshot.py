#!/usr/bin/env python3
"""
generate_snapshot.py

Fetches live data from the AI Peekaboo REST API and injects it into
dashboard.html as window._AIM_SNAPSHOT.

Required environment variables:
  PEEKABOO_BRAND_ID   — Brand UUID from aipeekaboo.com/settings
  PEEKABOO_API_KEY    — API key from aipeekaboo.com/settings/integrations

Optional environment variables:
  DASHBOARD_PATH      — Path to dashboard.html (default: dashboard.html in cwd)
  TIME_RANGE          — Data window, e.g. "7d", "30d", "90d" (default: 30d)
  MAX_HIST_DATES      — Max response-history dates per prompt (default: 7)

Usage:
  PEEKABOO_BRAND_ID=xxx PEEKABOO_API_KEY=xxx python3 generate_snapshot.py
  python3 generate_snapshot.py --dry-run      # print summary, don't write
  python3 generate_snapshot.py --save out.json  # save raw JSON

Runtime: ~10-20 min for 40 prompts (API rate-limited to 18 req/min).
"""

import json, time, datetime, re, os, sys
import urllib.request, urllib.parse, urllib.error
from collections import defaultdict

# ── Config (read from env, fail fast if missing) ──────────────────────────
BRAND_ID = os.environ.get('PEEKABOO_BRAND_ID', '').strip()
API_KEY  = os.environ.get('PEEKABOO_API_KEY', '').strip()

if not BRAND_ID or not API_KEY:
    print("ERROR: PEEKABOO_BRAND_ID and PEEKABOO_API_KEY env vars are required.")
    print("  Get them from aipeekaboo.com/settings/integrations")
    sys.exit(1)

BASE_URL   = "https://www.aipeekaboo.com/api/v1"
DASHBOARD  = os.environ.get('DASHBOARD_PATH', os.path.join(os.path.dirname(__file__), '..', 'dashboard.html'))
DASHBOARD  = os.path.normpath(DASHBOARD)
TIME_RANGE = os.environ.get('TIME_RANGE', '30d')
MAX_HIST_DATES = int(os.environ.get('MAX_HIST_DATES', '7'))
MAX_TEXT_LEN   = 4000

INJECT_START = "<!-- AIM_SNAPSHOT_INJECT_START -->"
INJECT_END   = "<!-- AIM_SNAPSHOT_INJECT_END -->"

# ── Model key mapping ─────────────────────────────────────────────────────
MODEL_KEY = {
    'gpt-4o-mini':        'chatgpt',
    'gpt-4o':             'chatgpt',
    'chatgpt':            'chatgpt',
    'gemini-2.5-flash':   'gemini',
    'gemini-2.0-flash':   'gemini',
    'gemini':             'gemini',
    'sonar':              'perplexity',
    'sonar-pro':          'perplexity',
    'perplexity':         'perplexity',
    'google-aio':         'googleaio',
    'google-ai-overview': 'googleaio',
    'google-ai-mode':     'googleaimode',
}
MODEL_DISPLAY = {
    'chatgpt':      'ChatGPT',
    'gemini':       'Gemini',
    'perplexity':   'Perplexity',
    'googleaio':    'Google AIO',
    'googleaimode': 'Google AI Mode',
}
ALL_PROVIDERS = ['chatgpt', 'gemini', 'perplexity', 'googleaio', 'googleaimode']
SENT_SCORE    = {'positive': 75, 'neutral': 50, 'negative': 25}

# ── Rate limiter (stay under 18 req/min) ─────────────────────────────────
_call_times = []

def _throttle():
    now = time.time()
    _call_times[:] = [t for t in _call_times if now - t < 60]
    if len(_call_times) >= 18:
        wait = 61 - (now - _call_times[0])
        if wait > 0:
            print(f"  [throttle] pausing {wait:.1f}s (rate limit)...", flush=True)
            time.sleep(wait)
    _call_times.append(time.time())

def api_get(path, **params):
    _throttle()
    url = f"{BASE_URL}/{path}"
    if params:
        url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers={
        "X-API-Key": API_KEY,
        "Accept": "application/json",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read())
                remaining = r.headers.get('X-RateLimit-Remaining', '?')
                if remaining != '?' and int(remaining) < 3:
                    reset_ts = int(r.headers.get('X-RateLimit-Reset', time.time() + 60))
                    wait = max(1, reset_ts - time.time()) + 0.5
                    print(f"  [low RL {remaining}] pausing {wait:.1f}s...", flush=True)
                    time.sleep(wait)
                return body.get('data', body)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                reset_ts = int(e.headers.get('X-RateLimit-Reset', time.time() + 60))
                wait = max(2, reset_ts - time.time()) + 1
                print(f"  [429] retry in {wait:.1f}s...", flush=True)
                time.sleep(wait)
            elif attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise
    return {}

# ── Helpers ───────────────────────────────────────────────────────────────
def sent_label(raw):
    if raw is None:
        return 'neutral'
    s = str(raw).lower().strip()
    return s if s in ('positive', 'negative', 'neutral') else 'neutral'

def fmt_date(iso):
    try:
        d = datetime.date.fromisoformat(iso[:10])
        return d.strftime('%b %-d')
    except Exception:
        return iso[:10]

def _entity_domain(name):
    slug = re.sub(r'[^a-z0-9]', '', name.lower())
    return f"{slug}.com"

def build_se(all_responses_flat, prompt_metrics, brand_name):
    """Build SE (Sentiment Entries) from all response history where brand is mentioned.
    Called at snapshot generation time so the result is injected as aim_se,
    eliminating the need for any browser-to-API calls in the dashboard."""
    import re as _re
    brand_low = (brand_name or '').lower()
    pid_topic, pid_text = {}, {}
    for pm in prompt_metrics:
        pid = pm.get('prompt_id', '')
        if pid:
            pid_topic[pid] = pm.get('topic', 'General') or 'General'
            pid_text[pid]  = pm.get('prompt_text', '') or ''
    _mkey = {
        'ChatGPT': 'chatgpt', 'Gemini': 'gemini', 'Perplexity': 'perplexity',
        'Google AIO': 'googleaio', 'Google AI Mode': 'googleaimode',
    }
    def _reason(text):
        if not text: return ''
        for s in _re.split(r'(?<=[.!?])\s+|\n+', text):
            if brand_low and brand_low in s.lower():
                s = s.strip()
                return (s[:240] + '...') if len(s) > 240 else s
        return text[:180].strip()
    SE = {'positive': [], 'negative': [], 'neutral': [], 'uncertain': []}
    seen = set()
    for r in all_responses_flat:
        if not r.get('is_mentioned'):
            continue
        pid     = r.get('prompt_id', '')
        mk      = _mkey.get(r.get('model', ''), (r.get('model') or '').lower().replace(' ', ''))
        dk      = r.get('date', '')
        key     = f"{pid}|{mk}|{dk}"
        if key in seen: continue
        seen.add(key)
        label = (r.get('sentiment_label') or 'neutral').lower()
        stype = 'positive' if label == 'positive' else ('negative' if label == 'negative' else 'neutral')
        SE[stype].append({
            'runId':    key,
            'prompt':   r.get('prompt_text') or pid_text.get(pid, ''),
            'promptId': pid,
            'model':    mk,
            'category': pid_topic.get(pid, 'General'),
            'sentiment': stype,
            'reason':   _reason(r.get('text', '') or ''),
            'date':     dk,
        })
    return SE


# ── Main ──────────────────────────────────────────────────────────────────
def main():
    dry_run  = '--dry-run' in sys.argv
    save_arg = next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == '--save' and i+1 < len(sys.argv)), None)

    # 0. All brands (for the brand selector dropdown)
    print("Fetching /brands...", flush=True)
    all_brands_resp = api_get("brands")
    raw_brands = all_brands_resp if isinstance(all_brands_resp, list) else all_brands_resp.get('brands', all_brands_resp.get('data', []))
    sorted_brands = sorted(raw_brands, key=lambda x: x.get('lastAnalysisAt') or '', reverse=True)
    print(f"  {len(sorted_brands)} brands found — fetching per-brand details...", flush=True)
    all_brands = []
    for i, b in enumerate(sorted_brands):
        url = b.get('url', '') or ''
        domain = re.sub(r'^https?://(www\.)?', '', url).rstrip('/').split('/')[0]
        last_at = b.get('lastAnalysisAt', '')
        entry = {
            'id':               b['id'],
            'name':             b['name'],
            'domain':           domain,
            'industry':         b.get('industry'),
            'lastAnalysisAt':   last_at if last_at else None,
            'analysisFrequency': b.get('analysisFrequency'),
            'location':         None,
            'promptCount':      None,
            'analysisEnabled':  True,
        }
        try:
            detail = api_get(f"brands/{b['id']}")
            if isinstance(detail, dict):
                d = detail.get('data', detail)
                entry['location']        = d.get('location')
                entry['promptCount']     = d.get('promptCount')
                entry['analysisEnabled'] = d.get('analysisEnabled', True)
                if d.get('lastAnalysisAt'):
                    entry['lastAnalysisAt'] = d['lastAnalysisAt']
            print(f"  [{i+1}/{len(sorted_brands)}] {b['name'][:30]}", flush=True)
        except Exception as e:
            print(f"  [{i+1}/{len(sorted_brands)}] {b['name'][:30]} — detail fetch failed: {e}", flush=True)
        all_brands.append(entry)
    print(f"  Done enriching {len(all_brands)} brands", flush=True)

    # 1. Snapshot for overall metrics + competitors
    print("Fetching /snapshot...", flush=True)
    snap = api_get(f"brands/{BRAND_ID}/snapshot")
    overall_visibility = float(snap.get('visibility', {}).get('score', 0) or 0)
    total_runs         = int(snap.get('visibility', {}).get('totalChatsAnalyzed', 0) or 0)
    snap_competitors   = snap.get('competitors', [])
    ai_suggestions     = snap.get('aiSuggestions', []) or []

    # 2. All prompts
    print("Fetching /prompts...", flush=True)
    pdata = api_get(f"brands/{BRAND_ID}/prompts", limit=200, time_range=TIME_RANGE)
    if isinstance(pdata, dict):
        prompts_list = pdata.get('prompts', pdata.get('data', []))
    else:
        prompts_list = pdata or []
    print(f"  {len(prompts_list)} prompts found", flush=True)

    # 3. Prompt details (one API call per prompt)
    details = {}
    for idx, p in enumerate(prompts_list):
        pid = p.get('promptId') or p.get('id', '')
        print(f"  prompt {idx+1}/{len(prompts_list)} {pid[:8]}...", flush=True)
        d = api_get(f"brands/{BRAND_ID}/prompts/{pid}",
                    include_full_response='true',
                    time_range=TIME_RANGE)
        details[pid] = d

    # 4. Competitors
    print("Fetching /competitors...", flush=True)
    cdata = api_get(f"brands/{BRAND_ID}/competitors")
    if isinstance(cdata, dict):
        comp_list = cdata.get('competitors', cdata.get('data', []))
    else:
        comp_list = cdata or []
    if len(snap_competitors) > len(comp_list):
        comp_list = snap_competitors

    # ── Assign ap-ids ─────────────────────────────────────────────────────
    ap_ids = {}
    for i, p in enumerate(prompts_list):
        pid = p.get('promptId') or p.get('id', '')
        ap_ids[pid] = f"ap{i+1}"

    # ── Per-prompt aggregation ────────────────────────────────────────────
    prompt_response_history = {}
    prompt_responses        = {}
    prompt_analysis         = {}
    prompt_metrics          = []
    all_responses_flat      = []

    daily_prov_scores          = defaultdict(lambda: defaultdict(list))
    latest_prov_data           = defaultdict(list)
    source_count               = defaultdict(int)
    source_runs_map            = defaultdict(set)
    source_url_runs_map        = defaultdict(set)
    source_url_count           = defaultdict(int)
    source_url_meta            = {}
    brand_timeline_raw         = defaultdict(lambda: defaultdict(list))
    bt_by_prov_raw             = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    src_by_date_raw            = defaultdict(lambda: defaultdict(int))
    src_by_prov_raw            = defaultdict(lambda: defaultdict(int))
    global_entity_model_scores = defaultdict(lambda: defaultdict(list))
    comp_sentiment_raw         = defaultdict(lambda: {'sum': 0.0, 'count': 0})
    comp_position_raw          = defaultdict(lambda: {'sum': 0.0, 'count': 0})
    source_url_prov_raw        = defaultdict(lambda: defaultdict(int))
    brand_global_vis_raw       = defaultdict(float)
    prompt_matrix_data         = {}
    total_processed_entry_count = 0

    for p in prompts_list:
        pid   = p.get('promptId') or p.get('id', '')
        ap_id = ap_ids[pid]
        det   = details.get(pid, {})
        hist  = det.get('history', []) or []

        by_date_prov = defaultdict(dict)
        vis_by_prov  = defaultdict(list)
        sent_by_prov = defaultdict(list)
        pos_by_prov  = defaultdict(list)
        brand_counts = defaultdict(int)
        domain_counts = defaultdict(int)

        for entry in hist:
            raw_model  = entry.get('aiModel') or entry.get('model', '')
            prov_key   = MODEL_KEY.get(raw_model)
            if not prov_key:
                continue
            entry_date = (entry.get('date') or '')[:10]
            if not entry_date:
                continue

            total_processed_entry_count += 1
            score        = float(entry.get('score', 0) or 0)
            rank         = entry.get('rank')
            is_mentioned = bool(entry.get('mentioned', False) or score > 0)
            run_id       = entry.get('runId', f"{ap_id}_{entry_date}_{prov_key}")

            bm_list = entry.get('brandMentions', []) or []
            pb_entry = next(
                (bm for bm in bm_list
                 if bm.get('type') not in ('competitor', 'untracked')
                 or 'peekaboo' in bm.get('entityName', '').lower()),
                None
            )
            raw_sent     = pb_entry.get('sentiment') if pb_entry else None
            e_sent_label = sent_label(raw_sent)
            e_sent_score = SENT_SCORE.get(e_sent_label, 50)

            raw_sources = entry.get('sources', []) or []
            src_objs = []
            for s in raw_sources:
                dom = s.get('domain', '')
                url = s.get('url', '')
                lbl = s.get('title', '') or dom
                src_objs.append({'domain': dom, 'url': url, 'label': lbl})
                if dom:
                    domain_counts[dom] += 1
                    source_count[dom] += 1
                    source_runs_map[dom].add(run_id)
                    src_by_date_raw[entry_date][dom] += 1
                    src_by_prov_raw[prov_key][dom] += 1
                if url and dom:
                    source_url_count[url] += 1
                    source_url_runs_map[url].add(run_id)
                    if url not in source_url_meta:
                        source_url_meta[url] = {'domain': dom, 'label': lbl, 'last_seen': entry_date}
                    elif entry_date > source_url_meta[url]['last_seen']:
                        source_url_meta[url]['last_seen'] = entry_date
                    source_url_prov_raw[url][prov_key] += 1

            brands_in = [bm.get('entityName', '') for bm in bm_list if bm.get('entityName')]
            for b in brands_in:
                brand_counts[b] += 1

            _total_in_run = len(bm_list)
            for bm in bm_list:
                bname  = bm.get('entityName', '')
                bscore = float(bm.get('score', 0) or 0)
                if bname:
                    brand_timeline_raw[bname][entry_date].append(bscore)
                    bt_by_prov_raw[bname][prov_key][entry_date].append(bscore)
                    brand_global_vis_raw[bname] += bscore
                    _bm_sent = bm.get('sentimentScore') or bm.get('sentiment')
                    if _bm_sent is None:
                        _bm_sent = e_sent_score
                    elif isinstance(_bm_sent, str):
                        _bm_sent = SENT_SCORE.get(sent_label(_bm_sent), 50)
                    comp_sentiment_raw[bname]['sum'] += float(_bm_sent)
                    comp_sentiment_raw[bname]['count'] += 1
                    if _total_in_run > 0:
                        _derived_rank = _total_in_run * (1.0 - bscore / 100.0) + 1.0
                        comp_position_raw[bname]['sum'] += _derived_rank
                        comp_position_raw[bname]['count'] += 1

            for bm in bm_list:
                bm_entity = bm.get('entityName', '').strip()
                bm_score  = float(bm.get('score', 0) or 0)
                if bm_entity and prov_key:
                    global_entity_model_scores[bm_entity][prov_key].append(bm_score)

            full_text = entry.get('fullResponse', '') or entry.get('responseSnippet', '') or ''
            resp_obj = {
                'model':            MODEL_DISPLAY[prov_key],
                'date':             entry_date,
                'text':             full_text[:MAX_TEXT_LEN],
                'brands':           brands_in,
                'sources':          [s.get('domain', '') for s in raw_sources],
                'source_objects':   src_objs,
                'sentiment_label':  e_sent_label,
                'sentiment_score':  e_sent_score,
                'visibility_score': score,
                'is_mentioned':     1 if is_mentioned else 0,
                'prompt_id':        ap_id,
                'prompt_text':      det.get('promptText', p.get('promptText', '')),
            }
            by_date_prov[entry_date][prov_key] = resp_obj
            vis_by_prov[prov_key].append(score)
            sent_by_prov[prov_key].append(e_sent_score)
            if rank is not None:
                pos_by_prov[prov_key].append(float(rank))
            daily_prov_scores[entry_date][prov_key].append(score)
            latest_prov_data[prov_key].append((entry_date, score, e_sent_score, rank))
            all_responses_flat.append(resp_obj)

        sorted_dates = sorted(by_date_prov.keys(), reverse=True)
        history_dates = sorted_dates[:MAX_HIST_DATES]
        prompt_response_history[ap_id] = {d: by_date_prov[d] for d in history_dates}

        latest_per_prov = {}
        for d in sorted_dates:
            for prov, resp in by_date_prov[d].items():
                if prov not in latest_per_prov:
                    latest_per_prov[prov] = resp
        prompt_responses[ap_id] = latest_per_prov

        top_brands = sorted(brand_counts.items(), key=lambda x: -x[1])
        top_doms   = sorted(domain_counts.items(), key=lambda x: -x[1])
        prompt_analysis[ap_id] = {
            'top_brand':    top_brands[0][0] if top_brands else '',
            'top_citation': top_doms[0][0]   if top_doms  else '',
            'brands':       [b for b, _ in top_brands[:8]],
            'citations':    [d for d, _ in top_doms[:8]],
        }

        matrix_entry = sorted(
            [{'n': name, 'count': cnt} for name, cnt in brand_counts.items()],
            key=lambda x: -x['count']
        )[:10]
        comp_name_map = {c.get('name','').lower(): c.get('url','') for c in comp_list}
        for item in matrix_entry:
            url = comp_name_map.get(item['n'].lower(), '')
            if url:
                try:
                    item['d'] = urllib.parse.urlparse(url).netloc.replace('www.', '')
                except Exception:
                    item['d'] = ''
            else:
                item['d'] = ''
        prompt_matrix_data[ap_id] = matrix_entry

        all_vis  = [s for ss in vis_by_prov.values()  for s in ss]
        all_sent = [s for ss in sent_by_prov.values() for s in ss]
        all_pos  = [v for vv in pos_by_prov.values()  for v in vv]
        vis_all  = round(sum(all_vis)  / len(all_vis),  2) if all_vis  else 0.0
        sent_all = round(sum(all_sent) / len(all_sent), 2) if all_sent else 50.0
        pos_all  = round(sum(all_pos)  / len(all_pos),  2) if all_pos  else None
        by_prov_m = {}
        for prov in ALL_PROVIDERS:
            v  = vis_by_prov.get(prov, [])
            s  = sent_by_prov.get(prov, [])
            pp = pos_by_prov.get(prov, [])
            by_prov_m[prov] = {
                'visibility': round(sum(v)/len(v),   2) if v  else 0.0,
                'sentiment':  round(sum(s)/len(s),   2) if s  else 50.0,
                'position':   round(sum(pp)/len(pp), 2) if pp else None,
            }

        prompt_text   = det.get('promptText', p.get('promptText', ''))
        category      = det.get('category', p.get('category', 'General')) or 'General'
        search_intent = det.get('searchIntent', p.get('searchIntent')) or 'Informational'
        last_run      = sorted_dates[0] if sorted_dates else ''

        prompt_metrics.append({
            'prompt_id':      ap_id,
            'prompt_text':    prompt_text,
            'topic':          category,
            'intent':         str(search_intent).capitalize() if search_intent else 'Informational',
            'visibility_all': vis_all,
            'sentiment_all':  sent_all,
            'position_all':   pos_all,
            'by_provider':    by_prov_m,
            'last_run':       last_run,
        })

    # ── Daily trend ───────────────────────────────────────────────────────
    daily_trend = []
    for d in sorted(daily_prov_scores.keys()):
        pv = daily_prov_scores[d]
        all_today = [s for scores in pv.values() for s in scores]
        row = {
            'date':       fmt_date(d),
            'iso_date':   d,
            'visibility': round(sum(all_today) / len(all_today), 2) if all_today else 0,
        }
        for prov in ALL_PROVIDERS:
            scores = pv.get(prov, [])
            row[prov] = round(sum(scores) / len(scores), 2) if scores else 0
        daily_trend.append(row)

    # ── Latest by provider ────────────────────────────────────────────────
    latest_by_provider = {}
    for prov in ALL_PROVIDERS:
        entries = sorted(latest_prov_data.get(prov, []), key=lambda x: x[0], reverse=True)
        if not entries:
            latest_by_provider[prov] = {'visibility': 0, 'sentiment': 50, 'sentiment_label': 'neutral', 'position': None}
            continue
        latest_d = entries[0][0]
        recent   = [e for e in entries if e[0] == latest_d]
        vis_avg  = round(sum(e[1] for e in recent) / len(recent), 2)
        sent_avg = round(sum(e[2] for e in recent) / len(recent), 2)
        pos_vals = [e[3] for e in recent if e[3] is not None]
        pos_avg  = round(sum(pos_vals) / len(pos_vals), 2) if pos_vals else None
        s_lbl    = 'positive' if sent_avg >= 65 else ('negative' if sent_avg <= 35 else 'neutral')
        latest_by_provider[prov] = {
            'visibility':      vis_avg,
            'sentiment':       sent_avg,
            'sentiment_label': s_lbl,
            'position':        pos_avg,
        }

    all_positions = [
        v for pm in prompt_metrics
        for prov_d in pm['by_provider'].values()
        for v in ([prov_d['position']] if prov_d['position'] is not None else [])
    ]
    overall_avg_pos = round(sum(all_positions) / len(all_positions), 2) if all_positions else None

    # ── Per-model heatmap data ────────────────────────────────────────────
    HM_PROV_KEY = {
        'chatgpt': 'chatgpt', 'gemini': 'gemini', 'perplexity': 'perplexity',
        'googleaio': 'google-aio', 'googleaimode': 'google-aim',
    }
    aim_real_hm_data = {}
    for entity, prov_scores in global_entity_model_scores.items():
        aim_real_hm_data[entity] = {}
        for int_key, hm_key in HM_PROV_KEY.items():
            vals = prov_scores.get(int_key, [])
            aim_real_hm_data[entity][hm_key] = round(sum(vals) / len(vals), 1) if vals else 0

    # ── Global brand mention counts ───────────────────────────────────────
    global_brand_counts = defaultdict(int)
    for pm_detail in details.values():
        for entry in pm_detail.get('history', []) or []:
            for bm in entry.get('brandMentions', []) or []:
                bname = bm.get('entityName', '')
                if bname:
                    global_brand_counts[bname] += 1

    # ── Competitor entities ───────────────────────────────────────────────
    def _comp_lookup(raw_map, name):
        key = name.lower().strip()
        if key in raw_map:
            return raw_map[key]
        bare = re.sub(r'\s*(ai|io)$', '', key, flags=re.IGNORECASE).strip()
        for k, v in raw_map.items():
            k2 = k.lower().strip()
            if k2 == bare or re.sub(r'\s*(ai|io)$', '', k2, flags=re.IGNORECASE).strip() == bare:
                return v
        return None

    competitor_entities = []
    for c in comp_list:
        name = c.get('name', '')
        vis  = float(c.get('score', 0) or 0)
        _sd  = _comp_lookup(comp_sentiment_raw, name)
        _ce_sent = round(_sd['sum'] / _sd['count']) if _sd and _sd['count'] > 0 else 50
        _pd  = _comp_lookup(comp_position_raw, name)
        _ce_pos = round(_pd['sum'] / _pd['count'], 1) if _pd and _pd['count'] > 0 else None
        _mc_raw = {k.lower().strip(): v for k, v in global_brand_counts.items()}
        _mc = _mc_raw.get(name.lower().strip(), 0)
        competitor_entities.append({
            'name':          name,
            'visibility':    round(vis, 2),
            'rank':          c.get('rank'),
            'sentiment':     _ce_sent,
            'avg_position':  _ce_pos,
            'mention_count': _mc,
            'run_count':     total_runs,
        })

    # ── Top sources ───────────────────────────────────────────────────────
    top_sources = sorted(
        [{'domain': d, 'citation_count': count,
          'run_count': len(source_runs_map.get(d, set()))}
         for d, count in source_count.items()],
        key=lambda x: -x['citation_count']
    )[:20]

    total_url = sum(source_url_count.values()) or 1
    top_source_urls = sorted(
        [{'url':            url,
          'domain':         source_url_meta[url]['domain'],
          'label':          source_url_meta[url]['label'],
          'citation_count': count,
          'mentions':       count,
          'run_count':      len(source_url_runs_map.get(url, set())),
          'last_seen':      source_url_meta[url]['last_seen'],
          'share':          round(count / total_url * 100, 1),
          'by_provider':    dict(source_url_prov_raw.get(url, {}))}
         for url, count in source_url_count.items()],
        key=lambda x: -x['citation_count']
    )[:300]

    # ── Recent responses ──────────────────────────────────────────────────
    recent_sorted       = sorted(all_responses_flat, key=lambda r: r.get('date', ''), reverse=True)
    recent_responses    = recent_sorted[:20]
    mentioned_responses = [r for r in recent_sorted if r.get('is_mentioned', 0) > 0][:10]

    # ── Brand timeline ────────────────────────────────────────────────────
    tracked_names = {c.get('name', '').lower().strip() for c in comp_list if c.get('name')}
    top_global    = sorted(global_brand_counts.items(), key=lambda x: -x[1])[:50]
    keep_names    = tracked_names | {n.lower().strip() for n, _ in top_global}

    brand_timeline = {}
    for name, by_date in brand_timeline_raw.items():
        if name.lower().strip() in keep_names:
            brand_timeline[name] = [
                {'date': d, 'visibility': round(sum(ss)/len(ss), 2)}
                for d, ss in sorted(by_date.items())
            ]

    def _norm_key(n):
        n = n.strip()
        n = re.sub(r'\s+(ai|io|radar)$', '', n, flags=re.IGNORECASE)
        n = re.sub(r'\.(ai|io|com|dev|net|org)$', '', n, flags=re.IGNORECASE)
        n = re.sub(r'\s+', ' ', n).strip()
        return re.sub(r'[^a-z0-9]', '', n.lower())

    norm_to_canonical = {}
    for name in list(brand_timeline.keys()):
        nk = _norm_key(name)
        if nk not in norm_to_canonical:
            norm_to_canonical[nk] = name
        else:
            existing = norm_to_canonical[nk]
            is_tracked = name.lower().strip() in tracked_names
            existing_tracked = existing.lower().strip() in tracked_names
            if is_tracked and not existing_tracked:
                norm_to_canonical[nk] = name
            elif not is_tracked and not existing_tracked and len(name) < len(existing):
                norm_to_canonical[nk] = name

    deduped_bt = {}
    for name, entries in brand_timeline.items():
        canonical = norm_to_canonical[_norm_key(name)]
        if canonical not in deduped_bt:
            deduped_bt[canonical] = {}
        for e in entries:
            d = e['date']
            if d not in deduped_bt[canonical]:
                deduped_bt[canonical][d] = []
            deduped_bt[canonical][d].append(e['visibility'])
    brand_timeline = {
        name: [{'date': d, 'visibility': round(sum(vs)/len(vs), 2)} for d, vs in sorted(by_date.items())]
        for name, by_date in deduped_bt.items()
    }

    brand_timeline_by_provider_raw_filtered = {}
    for name, by_prov in bt_by_prov_raw.items():
        if name.lower().strip() not in keep_names:
            continue
        canonical = norm_to_canonical.get(_norm_key(name), name)
        if canonical not in brand_timeline_by_provider_raw_filtered:
            brand_timeline_by_provider_raw_filtered[canonical] = {}
        for prov in ALL_PROVIDERS:
            if prov not in brand_timeline_by_provider_raw_filtered[canonical]:
                brand_timeline_by_provider_raw_filtered[canonical][prov] = {}
            for d, ss in by_prov.get(prov, {}).items():
                if d not in brand_timeline_by_provider_raw_filtered[canonical][prov]:
                    brand_timeline_by_provider_raw_filtered[canonical][prov][d] = []
                brand_timeline_by_provider_raw_filtered[canonical][prov][d].extend(ss)
    brand_timeline_by_provider = {
        name: {
            prov: [{'date': d, 'visibility': round(sum(vs)/len(vs), 2)} for d, vs in sorted(by_date.items())]
            for prov, by_date in by_prov.items()
        }
        for name, by_prov in brand_timeline_by_provider_raw_filtered.items()
    }

    sources_by_date = {
        d: [{'domain': dom, 'citation_count': count}
            for dom, count in sorted(counts.items(), key=lambda x: -x[1])[:50]]
        for d, counts in src_by_date_raw.items()
    }
    sources_by_provider = {
        prov: [{'domain': dom, 'citation_count': count}
               for dom, count in sorted(counts.items(), key=lambda x: -x[1])[:50]]
        for prov, counts in src_by_prov_raw.items()
    }

    # ── Final snapshot ────────────────────────────────────────────────────
    snapshot = {
        'generated_at':               datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'brand':                      next((b.get('name', '') for b in all_brands if b.get('id') == BRAND_ID), ''),
        'brand_id':                   BRAND_ID,
        'all_brands':                 all_brands,
        'total_runs':                 total_runs,
        'overall_visibility':         round(overall_visibility, 2),
        'overall_avg_position':       overall_avg_pos,
        'daily_trend':                daily_trend,
        'latest_by_provider':         latest_by_provider,
        'top_sources':                top_sources,
        'competitor_entities':        competitor_entities,
        'prompt_metrics':             prompt_metrics,
        'prompt_responses':           prompt_responses,
        'prompt_response_history':    prompt_response_history,
        'recent_responses':           recent_responses,
        'mentioned_responses':        mentioned_responses,
        'prompt_analysis':            prompt_analysis,
        'brand_timeline':             brand_timeline,
        'brand_timeline_by_provider': brand_timeline_by_provider,
        'sources_by_date':            sources_by_date,
        'sources_by_provider':        sources_by_provider,
        'top_source_urls':            top_source_urls,
        'brand_global_vis': {
            name: round(total / max(total_processed_entry_count, 1), 2)
            for name, total in brand_global_vis_raw.items()
        },
        'ai_suggestions':      ai_suggestions,
        'aim_real_hm_data':    aim_real_hm_data,
        'aim_real_matrix_data': prompt_matrix_data,
        'aim_se':            build_se(all_responses_flat, prompt_metrics,
                                   next((b['name'] for b in all_brands if b['id'] == BRAND_ID), '')),
    }

    # ── Output ────────────────────────────────────────────────────────────
    if dry_run:
        print("\n=== Snapshot summary ===")
        print(f"  Generated:           {snapshot['generated_at']}")
        print(f"  Overall visibility:  {snapshot['overall_visibility']}%")
        print(f"  Total runs:          {snapshot['total_runs']}")
        print(f"  Prompts:             {len(prompt_metrics)}")
        print(f"  Daily trend points:  {len(daily_trend)}")
        print(f"  Competitors:         {len(competitor_entities)}")
        print(f"  Top sources:         {len(top_sources)}")
        print(f"  Brand timeline:      {len(brand_timeline)} brands")
        _se = build_se(all_responses_flat, prompt_metrics, next((b['name'] for b in all_brands if b['id'] == BRAND_ID), ''))
        print(f"  SE entries:          pos={len(_se['positive'])} neg={len(_se['negative'])} neu={len(_se['neutral'])}")
        if daily_trend:
            print(f"  Date range:          {daily_trend[0]['iso_date']} – {daily_trend[-1]['iso_date']}")
        return

    if save_arg:
        with open(save_arg, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        print(f"\nSaved JSON to {save_arg}")

    with open(DASHBOARD, 'r', encoding='utf-8') as f:
        html = f.read()

    start_pos = html.find(INJECT_START)
    end_pos   = html.find(INJECT_END)
    if start_pos == -1 or end_pos == -1:
        print("ERROR: Injection markers not found in dashboard.html")
        sys.exit(1)

    json_str  = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'))
    new_block = f'{INJECT_START}<script>window._AIM_SNAPSHOT={json_str}</script>{INJECT_END}'
    new_html  = html[:start_pos] + new_block + html[end_pos + len(INJECT_END):]

    with open(DASHBOARD, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print(f"\nSnapshot injected into {DASHBOARD}")
    print(f"  Prompts: {len(prompt_metrics)} | Visibility: {overall_visibility:.1f}% | "
          f"Competitors: {len(competitor_entities)} | Sources: {len(top_sources)}")
    if daily_trend:
        print(f"  Date range: {daily_trend[0]['iso_date']} – {daily_trend[-1]['iso_date']}")


if __name__ == '__main__':
    main()
