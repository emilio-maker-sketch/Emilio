"""Download chosen Commons candidates: python3 tools/photo_get.py  (reads build/picks.json {id: index}); credits -> build/photos/credits.json"""
import os, json, time, sys, requests
sys.path.insert(0, os.path.dirname(__file__))
from commons import UA, ROOT
OUT = os.path.join(ROOT, 'build', 'photos'); os.makedirs(OUT, exist_ok=True)
cand = json.load(open(os.path.join(ROOT, 'build', 'photo_candidates.json'))); picks = json.load(open(os.path.join(ROOT, 'build', 'picks.json')))
cf = os.path.join(OUT, 'credits.json'); cr = json.load(open(cf)) if os.path.exists(cf) else {}
for sid, i in picks.items():
    if i is None or sid in cr and any(os.path.exists(os.path.join(OUT, sid + e)) for e in ('.jpg', '.png')): continue
    c = cand[i[0]]['cands'][i[1]] if isinstance(i, list) else cand[sid]['cands'][i]; ext = '.png' if c['url'].lower().endswith('.png') else '.jpg'
    for k in range(6):
        try:
            r = requests.get(c['url'], headers=UA, timeout=120)
            if r.ok and r.headers.get('content-type', '').startswith('image/'): break
        except Exception: pass
        time.sleep(15 * (k + 1))
    else: print('FAILED', sid, flush=True); continue
    open(os.path.join(OUT, sid + ext), 'wb').write(r.content); cr[sid] = c; json.dump(cr, open(cf, 'w'), indent=1, ensure_ascii=False)
    print('got', sid, c['title'][5:70], flush=True); time.sleep(25)
print('GET_DONE')
