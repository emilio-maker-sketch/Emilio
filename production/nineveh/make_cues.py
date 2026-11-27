"""Build the SFX cue JSON from the board model."""
import json, os, sys
sys.argv = ['kaz_engine.py', 'info']
import kaz_engine as E
c = {'duration': E.DUR, 'whoosh': [], 'type': [], 'thud': [], 'scratch': [], 'tension': [], 'film': [], 'pulse': []}
last = -9
for t, box, mv_ in E.KEYS:
    if t - last > 1.2: c['whoosh'].append(round(t, 2)); last = t
for tg in E.TAGS: c['type'].append([round(tg['t0'], 2), len(tg['text'])])
for o in E.OVERLAYS:
    if o['kind'] in ('year', 'thesis'): c['type'].append([round(o['t0'] + .3, 2), min(len(o['a']), 30)]); c['tension'].append(round(o['t0'] + 1, 2))
    if o['kind'] in ('end_open', 'end'): c['thud'].append(round(o['t0'] + .05, 2))
for st in E.STAMPS: c['thud'].append(round(st['t0'] + .05, 2))
for e in E.ELLS: c['scratch'].append([round(e['t0'], 2), e['du']])
for L in E.LINES: c['scratch'].append([round(L['t0'], 2), .35])
if E.VINTAGE: c['film'].append([round(E.VINTAGE[0], 2), round(E.VINTAGE[1], 2)]); c['thud'].append(round(E.VINTAGE[0] + min(4.2, (E.VINTAGE[1]-E.VINTAGE[0])*.5), 2))
for F in E.FILMS:
    c['film'].append([round(F['t0'], 2), round(F['t1'], 2)]); c['whoosh'] += [round(F['t0'], 2), round(F['t1'] - .3, 2)]
    if F.get('title'): c['thud'].append(round(F['t1'] - 2.0, 2))
import cutaways as CWc
for cu in CWc.CUTS:
    if not cu.get('hard_in'): c['whoosh'].append(round(cu['t0'], 2))
    if cu['kind'] == 'foot': c['film'].append([round(cu['t0'], 2), round(cu['t1'], 2)])
    if cu['kind'] == 'type':
        for wd in CWc.type_layout(cu):
            (c['thud'] if wd['red'] else c.setdefault('tick_extra', [])).append(round(wd['t'], 2))
    if cu['kind'] in ('photo', 'object', 'trip'): c.setdefault('soft_extra2', []).append(round(cu['t0'] + .2, 2))
c['pin'] = [round(i['t0'], 2) for i in E.ITEMS]
c['tick'] = sorted([round(p['t'], 2) for p in E.POPS] + c.pop('tick_extra', []))
for i in E.ITEMS:
    if i.get('kind') == 'quote': c['type'].append([round(i['t0'] + .2, 2), 18])
c['roll'] = [[round(o['t0'], 2), 16] for o in E.OVERLAYS if o['kind'] == 'counter']
c['soft_extra'] = [round(l['t0'], 2) for l in E.LOUPES]
mv = [k[0] for k in E.K]; c['soft'] = [round(t, 2) for t in mv if all(abs(t - w) > 1.0 for w in c['whoosh'])][::2]
zt = {e['d'][1]: e['t'] for e in E.TL['events'] if e['d'][0] == 'zone'}
c['pulse'] = [[zt['fall'], zt['mound']], [zt['war'], zt['verdict']]]
c['soft'] = sorted(c['soft'] + c.pop('soft_extra') + c.pop('soft_extra2', []))
c['whoosh'].sort()
json.dump(c, open(os.path.join(E.B, 'cues.json'), 'w'))
print({k: len(v) if isinstance(v, list) else v for k, v in c.items()})
