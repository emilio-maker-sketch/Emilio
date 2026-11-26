"""Expand the script's shot lines into a full shot list with composed prompts, timing and cost.

  python3 tools/shotlist.py
Writes shots.json (machine-readable, used by the generator and the editor) and SHOTLIST.md (readable).
Timing uses build/narration/*.json when present (scratch or final narration); otherwise ~2.6 words/s.
"""
import os, json, math
from script_parse import chapters, load_bible, ROOT

SIZES = {'EWS': 'extreme wide establishing shot', 'WS': 'wide shot', 'MS': 'medium shot', 'CU': 'close-up',
         'ECU': 'extreme close-up', 'AERIAL': 'aerial drone shot', 'MAP': 'map', 'CARD': 'title card', '3D': 'diagram'}
MOVES = {'push': 'slow push-in', 'slow push': 'slow push-in', 'pull': 'slow pull-back', 'slow pull': 'slow pull-back',
         'pan': 'slow pan', 'slow pan': 'slow lateral pan', 'track': 'smooth tracking shot', 'orbit': 'slow orbit',
         'slow orbit': 'slow orbit', 'crane-up': 'slow crane up', 'crane-down': 'slow crane down',
         'drift': 'gentle handheld drift', 'static': 'locked-off static camera with subtle natural motion',
         'handheld': 'controlled handheld camera, documentary energy'}
PARA_GAP, WPS = 0.9, 2.6

def narration_durs(cid):
    p = os.path.join(ROOT, 'build', 'narration', cid + '.json')
    return [x['dur'] for x in json.load(open(p))['paras']] if os.path.exists(p) else None

HUMAN = {'constantine', 'mehmed', 'giustiniani', 'orban', 'notaras', 'sphrantzes', 'barbaro', 'halil',
         'janissaries', 'azaps', 'defenders'}
CLIMAX = ('10_', '11_')
def priority(s, cid):
    if s['kind'] != 'vid': return 0
    p = 1
    if s['move'] in ('handheld', 'track', 'orbit', 'slow orbit', 'crane-up', 'crane-down'): p += 2
    if s['size'] in ('AERIAL', 'EWS'): p += 1
    if set(s['refs']) & HUMAN or any(w in s['desc'].lower() for w in ('fire', 'smoke', 'ship', 'riding', 'march', 'crowd', 'wave')): p += 1
    if cid.startswith(CLIMAX) or cid.startswith('00_'): p += 1
    return p

def tier_cost(shots, n, cost):
    vids = sorted((s for s in shots if s['kind'] == 'vid'), key=lambda s: -s['priority'])
    keep = set(id(s) for s in vids[:n]); c = 0.0
    for s in shots:
        if s['kind'] == 'vid' and id(s) in keep: c += s['est_credits']
        elif s['kind'] in ('vid', 'still'): c += cost['still'] * (1 + s['inserts'])
    return c

def main():
    bible = load_bible(); st, refs, grades, cost = bible['style'], bible['refs'], bible['grades'], bible['costs']
    shots, t = [], 0.0
    for ch in chapters():
        durs = narration_durs(ch['id'])
        for pi, p in enumerate(ch['paras']):
            d = (durs[pi] if durs else len(p['text'].split()) / WPS) + PARA_GAP
            n = len(p['shots']) or 1
            for si, s in enumerate(p['shots']):
                for r in s['refs']:
                    if r not in refs: raise SystemExit(f"{ch['id']} line {s['line']}: unknown ref @{r}")
                sd = round(d / n, 2)
                sid = f"{ch['id'][:3].rstrip('_')}-{pi:02d}-{si}"
                look = ', '.join(refs[r] for r in s['refs'])
                image_prompt = '. '.join(x for x in [st['prefix'], f"{SIZES.get(s['size'], s['size'])}: {s['desc']}",
                                                     look, grades.get(s['grade'], ''), st['suffix']] if x)
                motion = f"{MOVES.get(s['move'], s['move'])}. {s['desc']}. Natural, realistic motion; people move subtly and believably; atmosphere: {grades.get(s['grade'], '')}."
                clip = 5 if s['kind'] == 'vid' else None
                # a 5 s clip can be eased to ~6.25 s; longer shots get a cutaway still for the remainder
                inserts = math.ceil((sd - 6.25) / 6) if clip and sd > 8 else 0
                c = {'vid': cost['still'] + cost['video_5s'], 'still': cost['still']}.get(s['kind'], 0.0) + inserts * cost['still']
                shots.append({'id': sid, 'chapter': ch['id'], 'para': pi, 'start': round(t, 2), 'dur': sd,
                              'kind': s['kind'], 'size': s['size'], 'move': s['move'], 'grade': s['grade'],
                              'refs': s['refs'], 'desc': s['desc'], 'image_prompt': image_prompt,
                              'motion_prompt': motion, 'negative': st['negative'], 'clip_seconds': clip,
                              'inserts': inserts, 'priority': priority(s, ch['id']),
                              'est_credits': round(c, 2), 'status': 'planned'})
                t += sd
    json.dump(shots, open(os.path.join(ROOT, 'shots.json'), 'w'), indent=1, ensure_ascii=False)
    by = {}
    for s in shots: by[s['kind']] = by.get(s['kind'], 0) + 1
    gen = sum(s['est_credits'] for s in shots)
    refsheets = len(refs) * 4 * cost['still']
    total = (gen + refsheets) * cost['retake_factor']
    nv = by.get('vid', 0)
    tiers = [('A: every motion shot as AI video', nv), ('B: hero video, rest animated stills', min(nv, 150)),
             ('C: lean, key moments only', min(nv, 80))]
    vids = sorted((s for s in shots if s['kind'] == 'vid'), key=lambda s: -s['priority'])
    for rank, s in enumerate(vids):
        s['tier'] = 'C' if rank < 80 else 'B' if rank < 150 else 'A'
    json.dump(shots, open(os.path.join(ROOT, 'shots.json'), 'w'), indent=1, ensure_ascii=False)
    tier_rows = [f"| {name} | {n} | {(tier_cost(shots, n, cost) + refsheets) * cost['retake_factor']:.0f} |" for name, n in tiers]
    lines = ['# Shot list: The Last Day of Rome', '',
             f"Running time (narration + gaps): **{t/60:.1f} min** ({'timed from narration audio' if narration_durs('00_cold_open') else 'estimated from word count'})", '',
             f"Shots: {len(shots)} ({', '.join(f'{v} {k}' for k, v in sorted(by.items()))})", '',
             '## Tier A breakdown', '', '| Item | Credits |', '|---|---|',
             f'| Reference sheets ({len(refs)} characters/locations x 4 images) | {refsheets:.0f} |',
             f'| Keyframes + video clips + stills | {gen:.0f} |',
             f"| Retake allowance (x{cost['retake_factor']}) | {total - gen - refsheets:.0f} |",
             f'| **Total estimate** | **{total:.0f}** |', '',
             'Map and card shots are rendered locally at no cost.', '',
             '## Budget tiers', '', 'Shots not given AI video become AI stills animated locally (parallax, slow push, drifting smoke). Includes reference sheets and a 25% retake allowance.', '',
             '| Tier | AI video clips | Credits |', '|---|---|---|', *tier_rows, '']
    cur = None
    for s in shots:
        if s['chapter'] != cur:
            cur = s['chapter']; lines += ['', f'## {cur}', '', '| Shot | Time | Dur | Kind | Size / move | Description |', '|---|---|---|---|---|---|']
        m, sec = divmod(int(s['start']), 60)
        lines.append(f"| {s['id']} | {m}:{sec:02d} | {s['dur']:.1f}s | {s['kind']}{' (' + s['tier'] + ')' if s.get('tier') else ''} | {s['size']} / {s['move']} | {s['desc']} |")
    open(os.path.join(ROOT, 'SHOTLIST.md'), 'w').write('\n'.join(lines) + '\n')
    print(f'{len(shots)} shots, {t/60:.1f} min, est {total:.0f} credits', by)

if __name__ == '__main__': main()
