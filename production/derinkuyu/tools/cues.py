"""Music, ambience and effects cues (music.json) from build/timeline.json.

Sound follows picture: ambience beds follow each scene's grade (fire, night wind, snow wind), keyword beds add sea,
marching and crowds, and effects are tied to the edit (impacts on flash cuts, whooshes into graphics, ticks on timeline
dates, paper on documents, a thud under quotes). Hits are thinned so no two land within 3 s.
"""
import os, json, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = {
 '00_cold_open': ['Ossuary 1 - A Beginning'], '01_the_soft_stone': ['Echoes of Time v2', 'Long Note One'], '02_fairy_chimneys': ['Eternal Hope', 'Unwritten Return'],
 '03_how_it_was_built': ['Long Note Three', 'Dreams Become Real'], '04_kanesh': ['Lost Frontier', 'Echoes of Time v2'], '05_katpatuka': ['Eternal Hope', 'Long Note Two'],
 '06_going_down': ['Ossuary 6 - Air', 'Long Note Four'], '07_air_and_water': ['Long Note One', 'Ossuary 2 - Turn'], '08_life_below': ['Lightless Dawn', 'Long Note Three'],
 '09_the_doors': ['Dark Times', 'Ossuary 5 - Rest'], '10_who_dug_it': ['Long Note Two', 'Dreams Become Real'], '11_dating_the_rock': ['Long Note Four', 'Ossuary 6 - Air'],
 '12_the_rock_churches': ['Bittersweet', 'Eternal Hope'], '13_houses_in_the_rock': ['Unwritten Return', 'Echoes of Time v2'], '14_the_raids': ['Anguish', 'Dark Times'],
 '15_turks_and_ottomans': ['Lost Frontier', 'Long Note One'], '16_malakopi': ['Bittersweet', 'Despair and Triumph'], '17_rediscovery': ['Dreams Become Real', 'Long Note Two'],
 '18_kaymakli_and_ozkonak': ['Ossuary 2 - Turn', 'Long Note Three'], '19_cities_underground': ['Lost Frontier', 'Eternal Hope'], '20_what_we_know': ['Despair and Triumph', 'Bittersweet']}
AMB = {'fire': [('fire.wav', 0.30)], 'night': [('night.wav', 0.28)], 'steel': [('wind.wav', 0.20)], 'snow': [('wind.wav', 0.42)],
       'dawn': [('wind.wav', 0.20)], 'ash': [('wind.wav', 0.14)], 'gold': [('wind.wav', 0.06)], 'candle': [('fire.wav', 0.05)]}
BEDS = {'waves.wav': (r'\b(sea|ship|harbour|fleet|galley|galleys|surf|shore|lagoon|strait)', 0.26),
        'march.wav': (r'\b(march|marching|column|wading|army|armies)', 0.24),
        'crowd.wav': (r'\b(crowd|forum|procession|cheering|mob|triumph|assembly|enraged)', 0.2)}

def main():
    tl = json.load(open(os.path.join(ROOT, 'build', 'timeline.json'))); D = tl['duration']; items = tl['items']
    shots = [x for x in items if x['type'] == 'shot']
    chs = sorted({x['chapter'] for x in items if 'chapter' in x})
    span = {c: (min(x['start'] for x in items if x.get('chapter') == c), max(x['start'] + x.get('dur', 0) for x in items if x.get('chapter') == c)) for c in chs}
    cues = []
    for c in chs:
        a, b = span[c]; tr = TRACKS.get(c, ['Long Note One']); seg = (b - a) / len(tr)
        for i, t in enumerate(tr):
            cues.append({'file': t + '.mp3', 'start': round(a + i * seg - (2 if i else 0), 2), 'end': round(a + (i + 1) * seg + 3, 2), 'gain': 0.8, 'fade_in': 3, 'fade_out': 4})
    title = [x for x in items if x['type'] == 'title']
    if title: cues.append({'file': 'Despair and Triumph.mp3', 'start': title[0]['start'] - 2, 'end': title[0]['start'] + 16, 'gain': 0.95, 'fade_in': 1.5, 'fade_out': 5})
    beds, hits = [], []
    run = None
    for s in shots + [None]:   # ambience follows the grade
        g = s['grade'] if s and s['kind'] not in ('map', 'diagram', 'timeline', 'card') else ('_gfx' if s else None)
        if run and (g != run[0] or s is None):
            for f, gain in AMB.get(run[0], []):
                if run[2] - run[1] > 4: beds.append({'file': f, 'start': round(run[1], 2), 'end': round(run[2], 2), 'gain': gain})
            run = None
        if s and run is None: run = [g, s['start'], s['start'] + s['dur']]
        elif s: run[2] = s['start'] + s['dur']
    for s in shots:
        d = s.get('desc', '').lower()
        if s['kind'] in ('still', 'vid', 'photo') and not s.get('beat'):
            for f, (rx, gain) in BEDS.items():
                if re.search(rx, d): beds.append({'file': f, 'start': round(s['start'], 2), 'end': round(s['start'] + s['dur'] + 1, 2), 'gain': gain})
        kind, L = s['tr']
        if kind == 'flash': hits.append((s['start'] + 0.1, 'impact.wav', 0.6))
        if kind == 'wipe' and s['kind'] in ('map', 'diagram', 'timeline', 'split'): hits.append((s['start'] - 0.2, 'whoosh.wav', 0.28))
        if s['kind'] == 'quote': hits.append((s['start'] + 0.5, 'thud.wav', 0.35))
        if s['kind'] == 'stat': hits.append((s['start'] + 0.3, 'thud.wav', 0.3))
        if s['move'] == 'scan': hits.append((s['start'] + 0.4, 'paper.wav', 0.4))
        if s['kind'] == 'timeline':
            n = len([x for x in s['desc'].split(';') if x.strip()])
            for i in range(n): hits.append((s['start'] + s['dur'] * (0.12 + 0.55 * i / max(1, n - 1)), 'tick.wav', 0.35))
        if s['kind'] in ('map', 'diagram') and not s.get('beat'): hits.append((s['start'] + 0.3, 'paper.wav', 0.25))
    for x in items:
        if x['type'] == 'card': hits.append((x['start'] - 0.9, 'whoosh.wav', 0.42))
    for c, (rise_at, hb) in {'08_cannae': ('08-04-0', '08-04'), '16_the_fall': ('16-04-1', '16-04')}.items():
        if c not in span: continue
        tgt = next((s for s in shots if s['sid'] == rise_at), None)
        if tgt: hits.append((tgt['start'] - 5.5, 'riser.wav', 0.5)); hits.append((tgt['start'] + 0.2, 'impact.wav', 0.7))
        hs = [s for s in shots if s['sid'].startswith(hb)]
        if hs: beds.append({'file': 'heartbeat.wav', 'start': round(hs[0]['start'], 2), 'end': round(hs[-1]['start'] + hs[-1]['dur'], 2), 'gain': 0.4})
        beds.append({'file': 'drone.wav', 'start': span[c][0], 'end': span[c][1], 'gain': 0.18})
    if title: hits.append((title[0]['start'], 'boom.wav', 0.9))
    hits.sort(); kept, last = [], -9
    for t, f, g in hits:
        if t - last >= 3.0 or f == 'tick.wav': kept.append({'file': f, 'start': round(t, 2), 'gain': g, 'hit': True}); last = t if f != 'tick.wav' else last
    json.dump({'credit': 'Music by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0', 'cues': cues, 'sfx': beds + kept},
              open(os.path.join(ROOT, 'music.json'), 'w'), indent=1)
    print(len(cues), 'music cues,', len(beds), 'beds,', len(kept), 'hits')

if __name__ == '__main__': main()
