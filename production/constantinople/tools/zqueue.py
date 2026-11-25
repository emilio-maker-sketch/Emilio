"""Choose which shots get a Z Image render (budget-limited) and write compact, model-safe prompts.

  python3 tools/zqueue.py BUDGET_IMAGES [chapters...]
Writes build/zqueue.json: [{id, prompt}] ordered by chapter.
Rules learned in the preview: never name the city or the great church in a prompt (the model draws modern
Istanbul with minarets), never use negations, keep prompts short and concrete.
"""
import os, sys, json, re
from script_parse import ROOT

SAFE = [(r'\bHagia Sophia\b', 'the great domed Byzantine church'), (r'\bConstantinople\b', 'the medieval city'),
        (r'\bminarets?\b', ''), (r'\bIstanbul\b', 'the city'), (r'\bConstantine\b', 'the emperor'),
        (r'\b(?:the )?(?:young )?Mehmed\b', 'the young sultan'), (r'\bGiustiniani\b', 'the Genoese captain'),
        (r'\bOrban\b', 'the cannon founder'), (r'\bNotaras\b', 'the old grand duke'), (r'\bSphrantzes\b', 'the courtier'),
        (r'\bBarbaro\b', 'the Venetian doctor'), (r'\bHalil(?: Pasha)?\b', 'the old vizier'), (r'\bZaganos Pasha\b', 'an Ottoman commander')]
REFS = {
    'constantine': 'a Byzantine emperor of 48 with a lean weathered face, dark beard flecked with grey and tired dignified eyes, in a deep crimson-purple cloak over steel lamellar armour',
    'mehmed': 'a young Ottoman sultan of 21, slim, sharp aquiline nose, thin dark moustache and short beard, intense eyes, large white wrapped turban, red and gold silk kaftan',
    'giustiniani': 'a Genoese captain in his forties with a short dark beard, in polished 15th-century Italian plate armour with a red-cross sash',
    'orban': 'a burly Hungarian cannon founder in his forties with a heavy moustache, soot-stained face and leather apron',
    'notaras': 'an elderly Byzantine nobleman with a white beard, a tall domed brimmed hat and blue and gold brocade robes',
    'sphrantzes': 'a Byzantine courtier in his fifties with a neat greying beard and plain dark wool robes',
    'barbaro': 'a clean-shaven Venetian doctor in his thirties in a black robe and cap',
    'halil': 'an elderly Ottoman grand vizier with a grey beard, tall white turban and dark green kaftan',
    'janissaries': 'Ottoman janissaries in tall white felt caps with a folded flap at the back, long robes, bows',
    'azaps': 'Ottoman irregular soldiers in simple clothes with wicker shields, spears and ladders',
    'defenders': 'Byzantine and Italian defenders in mixed mail and kettle helmets with crossbows and pavise shields',
    'walls': 'the massive medieval land walls: a dry moat, a lower outer wall and a tall inner wall with square towers of pale limestone banded with red brick',
    'lycus': 'a battered stretch of medieval city wall in a shallow valley, its breaches filled with barricades of earth, timber and barrels',
    'city1453': 'a half-empty medieval walled city of fields, orchards and red-tiled roofs around old domed brick churches',
    'hagia': 'an enormous Byzantine brick church with one vast low dome on heavy sloping buttresses, gold mosaics and marble columns inside',
    'horn': 'a long narrow harbour with a small walled medieval town and a single round stone tower on the hill opposite',
    'chain': 'a massive iron chain floating on wooden logs across a harbour mouth',
    'rumeli': 'a new grey stone fortress with three huge round towers climbing a steep green hillside above a narrow strait',
    'camp': 'a vast 15th-century Ottoman army camp of red and white tents, banners, horses and campfires',
    'bombard': 'a colossal 15th-century bronze bombard, a gigantic thick tube lying on a wooden sledge, huge carved stone balls beside it',
}
LIGHT = {'gold': 'warm golden-hour light, soft haze', 'candle': 'warm candle and oil-lamp light, deep shadows, incense haze',
         'steel': 'overcast cold daylight, steel-grey palette, drifting smoke', 'night': 'night, moonlight blue with orange torchlight and fire, smoke',
         'dawn': 'cold blue pre-dawn light, fires on the horizon, heavy smoke', 'ash': 'muted grey morning light, faded colours, quiet'}
SIZE = {'EWS': 'Extreme wide establishing shot', 'WS': 'Wide shot', 'MS': 'Medium shot', 'CU': 'Close-up', 'ECU': 'Extreme close-up', 'AERIAL': 'Aerial shot'}
HUMAN = {'constantine', 'mehmed', 'giustiniani', 'orban', 'notaras', 'sphrantzes', 'barbaro', 'halil', 'janissaries', 'azaps', 'defenders'}

def prompt(s):
    d = s['desc']
    for a, b in SAFE: d = re.sub(a, b, d)
    refs = '; '.join(REFS[r] for r in s['refs'] if r in REFS)
    p = (f"Photorealistic cinematic film still, historical documentary reconstruction, anamorphic lens, natural film grain. "
         f"{SIZE.get(s['size'], 'Shot')}: {d}." + (f" {refs}." if refs else '') +
         f" {LIGHT.get(s['grade'], '')}. 15th century, realistic textures, no text.")
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
        if s['chapter'][:2] in ('00', '01'): continue
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
