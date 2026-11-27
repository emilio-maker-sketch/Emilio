"""Choose which shots get a Z Image render (budget-limited) and write compact, model-safe prompts.

  python3 tools/zqueue.py BUDGET_IMAGES [chapters...]
Writes build/zqueue.json: [{id, prompt}] ordered by chapter.
Rules learned in the preview: never name the city or the great church in a prompt (the model draws modern
Istanbul with minarets), never use negations, keep prompts short and concrete.
"""
import os, sys, json, re
from script_parse import ROOT

SAFE = [(r'\bJulius Caesar\b', 'the dictator'), (r"\bCaesar's\b", "the dictator's"), (r'\bCaesar\b', 'the dictator'),
        (r'\bBrutus\b', 'the senator'), (r'\bCassius\b', 'the lean senator'), (r'\bPompey\b', 'the general'),
        (r'\bCleopatra\b', 'the queen'), (r'\bAntony\b', 'the consul'), (r'\bCicero\b', 'the orator'),
        (r'\bOctavian\b', 'the young man'), (r'\{LT:[^}]*\}', '')]
B_ = json.load(open(os.path.join(ROOT, 'bible.json')))
REFS = B_['refs']
LIGHT = B_['grades']
SIZE = {'EWS': 'Extreme wide establishing shot', 'WS': 'Wide shot', 'MS': 'Medium shot', 'CU': 'Close-up', 'ECU': 'Extreme close-up', 'AERIAL': 'Aerial shot'}
HUMAN = {'caesar', 'young_caesar', 'brutus', 'cassius', 'decimus', 'antony', 'pompey', 'calpurnia', 'porcia', 'cleopatra', 'cicero', 'octavian', 'spurinna', 'artemidorus', 'cimber', 'casca', 'senators', 'legion', 'gauls'}

def prompt(s):
    d = s['desc']
    for a, b in SAFE: d = re.sub(a, b, d)
    refs = '; '.join(REFS[r] for r in s['refs'] if r in REFS)
    if s['chapter'][:2] in ('02', '03', '04', '05', '06'):
        refs = refs.replace('statesman of 55', 'man in his forties').replace('thinning dark-grey hair', 'thinning dark hair')
    p = (f"Photorealistic cinematic film still, historical documentary reconstruction, anamorphic lens, natural film grain. "
         f"{SIZE.get(s['size'], 'Shot')}: {d}." + (f" {refs}." if refs else '') +
         f" {LIGHT.get(s['grade'], '')}. Late Roman Republic, 1st century BC, realistic textures, no text.")
    return re.sub(r'\s+', ' ', p).replace(' .', '.')

def score(s):
    v = 0
    if set(s['refs']) & HUMAN: v += 3
    if s['size'] in ('WS', 'MS', 'EWS', 'AERIAL'): v += 1
    if s['move'] in ('handheld', 'track', 'orbit', 'crane-up'): v += 1
    if s['kind'] == 'still': v -= 2
    return v

def main():
    budget = int(sys.argv[1]); chs = sys.argv[2:]
    shots = json.load(open(os.path.join(ROOT, 'shots.json')))
    narr = {}
    for s in shots:
        if chs and s['chapter'] not in chs: continue
        if s['kind'] not in ('vid', 'still'): continue
        narr.setdefault((s['chapter'], s['para']), []).append(s)
    have = {f[2:-4] for f in os.listdir(os.path.join(ROOT, 'build', 'gen')) if f.startswith('z_')}
    first, second = [], []
    for k, ps in sorted(narr.items()):
        ps = [p for p in ps if p['id'] not in have]
        if any(p['id'] in have for p in narr[k]): ps_have = True
        else: ps_have = False
        r = sorted(ps, key=lambda s: -score(s))
        if not r: continue
        if not ps_have: first.append(r[0]); rest = r[1:]
        else: rest = r
        dur = sum(p['dur'] for p in narr[k])
        if rest and dur > 20: second.append((dur, rest[0]))
    pick = first[:budget]
    second.sort(key=lambda x: -x[0])
    pick += [s for _, s in second[:max(0, budget - len(pick))]]
    pick.sort(key=lambda s: s['id'])
    out = [{'id': s['id'], 'prompt': prompt(s)} for s in pick]
    json.dump(out, open(os.path.join(ROOT, 'build', 'zqueue.json'), 'w'), indent=1, ensure_ascii=False)
    print(len(first), 'paragraph leads,', len(second), 'second candidates ->', len(out), 'queued')

if __name__ == '__main__': main()
