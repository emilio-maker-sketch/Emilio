"""Search Commons for every photo shot ([q: ...] in the description); save top candidates to build/photo_candidates.json."""
import os, re, json, time, sys
sys.path.insert(0, os.path.dirname(__file__))
from commons import search, ROOT
shots = json.load(open(os.path.join(ROOT, 'shots.json')))
out_p = os.path.join(ROOT, 'build', 'photo_candidates.json')
out = json.load(open(out_p)) if os.path.exists(out_p) else {}
for s in shots:
    if s['kind'] != 'photo' or s['id'] in out: continue
    m = re.search(r'\[q: ([^\]]+)\]', s['desc']); q = m.group(1)
    try: c = search(q, 10)
    except Exception as e: print('fail', s['id'], e, flush=True); time.sleep(30); continue
    out[s['id']] = {'q': q, 'cands': [{k: x[k] for k in ('title', 'w', 'h', 'license')} for x in c[:6]]}
    json.dump(out, open(out_p, 'w'), indent=1, ensure_ascii=False)
    print(s['id'], len(c), flush=True); time.sleep(12)
print('SEARCH_DONE')
