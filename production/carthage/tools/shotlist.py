"""Expand the script into shots.json and the Z Image request list.

  python3 tools/shotlist.py
shots.json: one entry per shot line, with parsed fields:
  q (Commons query), lt (lower third), crop (detail shots), sides (split screens), stat/timeline text.
build/zreq_all.json: [{id, prompt}] for every AI image needed (still, vid, split {z:} sides).
"""
import os, re, json
from script_parse import chapters, load_bible, ROOT

LT_RE = re.compile(r'\{LT:\s*([^|}]+)\|\s*([^}]+)\}')
Q_RE = re.compile(r'\[q:\s*([^\]]+)\]')
Z_RE = re.compile(r'\{z:\s*([^}]+)\}')
SAFE = [(r'\bHannibal\b', 'the Carthaginian commander'), (r'\bScipio\b', 'the Roman general'), (r'\bCato\b', 'the old senator'),
        (r'\bCarthage\b', 'the ancient Punic city'), (r'\bRome\b', 'the ancient Italian city'), (r'\bMasinissa\b', 'the Numidian king'),
        (r'\bHasdrubal\b', 'the Carthaginian general'), (r'\bPolybius\b', 'the Greek historian')]
SIZE = {'EWS': 'Extreme wide establishing shot', 'WS': 'Wide shot', 'MS': 'Medium shot', 'CU': 'Close-up', 'ECU': 'Extreme close-up'}

def zprompt(desc, size, refs, grade, B):
    d = desc
    for a, b in SAFE: d = re.sub(a, b, d)
    look = '; '.join(B['refs'][r] for r in refs)
    p = (f"Photorealistic cinematic historical film still, anamorphic, film grain. "
         f"{SIZE.get(size, 'Shot')}: {d}." + (f" {look}." if look else '') +
         f" {B['grades'].get(grade, '')}. 3rd-2nd century BC, realistic, no text.")
    return re.sub(r'\s+', ' ', p).replace(' .', '.').replace('..', '.')

def main():
    B = load_bible(); shots, zreq = [], []
    for ch in chapters():
        for pi, p in enumerate(ch['paras']):
            last_img = None
            for si, s in enumerate(p['shots']):
                for r in s['refs']:
                    if r not in B['refs']: raise SystemExit(f"{ch['id']}:{s['line']} unknown ref @{r}")
                sid = f"{ch['id'][:2]}-{pi:02d}-{si}"
                d = s['desc']; x = {'id': sid, 'chapter': ch['id'], 'para': pi, 'idx': si, **{k: s[k] for k in ('kind', 'size', 'move', 'grade', 'refs')}}
                m = LT_RE.search(d)
                if m: x['lt'] = [m.group(1).strip(), m.group(2).strip()]; d = LT_RE.sub('', d).strip()
                if s['kind'] == 'photo':
                    x['q'] = Q_RE.search(d).group(1).strip(); d = Q_RE.sub('', d).strip()
                if s['kind'] == 'detail':
                    c, _, txt = d.partition('·'); x['crop'] = [float(v) for v in c.split('=')[1].split(',')]; d = txt.strip()
                    if not last_img: raise SystemExit(f'{sid}: detail without a parent image')
                    x['parent'] = last_img
                if s['kind'] == 'split':
                    sides = []
                    for k, part in enumerate(d.split('||')):
                        part = part.strip(); side = {}
                        if Q_RE.search(part): side['q'] = Q_RE.search(part).group(1).strip()
                        if Z_RE.search(part):
                            side['z'] = f'{sid}{"ab"[k]}'
                            zreq.append({'id': side['z'], 'prompt': zprompt(Z_RE.search(part).group(1), 'MS', [], s['grade'], B)})
                        side['label'] = Z_RE.sub('', Q_RE.sub('', part)).strip()
                        sides.append(side)
                    x['sides'] = sides
                if s['kind'] == 'quote':
                    q, _, a = d.partition('~'); x['quote'] = q.strip().strip('"'); x['attrib'] = a.strip()
                x['desc'] = d
                if s['kind'] in ('still', 'vid'):
                    zreq.append({'id': sid, 'prompt': zprompt(d, s['size'], s['refs'], s['grade'], B)})
                if s['kind'] in ('still', 'vid', 'photo'): last_img = sid
                shots.append(x)
    json.dump(shots, open(os.path.join(ROOT, 'shots.json'), 'w'), indent=1, ensure_ascii=False)
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    json.dump(zreq, open(os.path.join(ROOT, 'build', 'zreq_all.json'), 'w'), indent=1, ensure_ascii=False)
    from collections import Counter
    print(len(shots), 'shots;', len(zreq), 'AI images;', dict(Counter(s['kind'] for s in shots)))

if __name__ == '__main__': main()
