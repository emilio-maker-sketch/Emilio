"""Build the SFX cue JSON from the board model."""
import json, os, sys
sys.argv = ['kaz_engine.py', 'info']
import kaz_engine as E
c = {'duration': E.DUR, 'whoosh': [], 'type': [], 'thud': [], 'scratch': [], 'tension': [], 'film': [], 'pulse': []}
last = -9
for t, box, mv in E.KEYS:
    if t - last > 1.2: c['whoosh'].append(round(t, 2)); last = t
for tg in E.TAGS: c['type'].append([round(tg['t0'], 2), len(tg['text'])])
for o in E.OVERLAYS:
    if o['kind'] in ('year', 'thesis'): c['type'].append([round(o['t0'] + .3, 2), min(len(o['a']), 30)]); c['tension'].append(round(o['t0'] + 1, 2))
    if o['kind'] in ('end_open', 'end'): c['thud'].append(round(o['t0'] + .05, 2))
for st in E.STAMPS: c['thud'].append(round(st['t0'] + .05, 2))
for e in E.ELLS: c['scratch'].append([round(e['t0'], 2), e['du']])
for L in E.LINES: c['scratch'].append([round(L['t0'], 2), .35])
if E.VINTAGE: c['film'].append([round(E.VINTAGE[0], 2), round(E.VINTAGE[1], 2)]); c['thud'].append(round(E.VINTAGE[0] + min(4.2, (E.VINTAGE[1]-E.VINTAGE[0])*.5), 2))
zt = {e['d'][1]: e['t'] for e in E.TL['events'] if e['d'][0] == 'zone'}
c['pulse'] = [[zt['plot'], zt['night']], [zt['night'], zt['trial']], [zt['case'] + 120, zt['end']]]
json.dump(c, open(os.path.join(E.B, 'cues.json'), 'w'))
print({k: len(v) if isinstance(v, list) else v for k, v in c.items()})
