"""Search Commons for every photo query (photo shots + split sides); save candidates to build/photo_candidates.json."""
import os, json, time, sys
sys.path.insert(0, os.path.dirname(__file__))
from commons import search, ROOT
shots = json.load(open(os.path.join(ROOT, 'shots.json')))
out_p = os.path.join(ROOT, 'build', 'photo_candidates.json')
out = json.load(open(out_p)) if os.path.exists(out_p) else {}
todo = []
for s in shots:
    if s['kind'] == 'photo': todo.append((s['id'], s['q']))
    for k, side in enumerate(s.get('sides', [])):
        if side.get('q') and not side.get('z'): todo.append((s['id'] + 'ab'[k], side['q']))
for sid, q in todo:
    if sid in out: continue
    try: c = search(q, 10)
    except Exception as e: print('fail', sid, e, flush=True); time.sleep(40); continue
    out[sid] = {'q': q, 'cands': c[:6]}
    json.dump(out, open(out_p, 'w'), indent=1, ensure_ascii=False)
    print(sid, len(c), flush=True); time.sleep(8)
print('SEARCH_DONE', len(todo))
