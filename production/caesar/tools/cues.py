"""Write music.json (music + ambience + effects) for the whole film from build/timeline.json."""
import os, json, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = {
 '00_cold_open': ['Ossuary 1 - A Beginning'], '01_the_republic': ['Echoes of Time v2', 'Unwritten Return'],
 '02_young_caesar': ['Lost Frontier', 'Dreams Become Real'], '03_three_men': ['Long Note One', 'Despair and Triumph'],
 '04_the_rubicon': ['Dark Times', 'Lightless Dawn'], '05_pharsalus': ['Anguish', 'Ossuary 5 - Rest'],
 '06_cleopatra': ['Eternal Hope', 'Lost Frontier'], '07_the_dictator': ['Echoes of Time v2', 'Long Note Two'],
 '08_the_conspirators': ['Long Note Three', 'Ossuary 2 - Turn'], '09_the_deadline': ['Long Note Four', 'Ossuary 6 - Air'],
 '10_the_morning': ['Long Note Two', 'Lightless Dawn'], '11_the_murder': ['Anguish'], '12_liberty': ['Ossuary 5 - Rest', 'Dark Times'],
 '13_the_funeral': ['Bittersweet', 'Despair and Triumph'], '14_the_heir': ['Dreams Become Real', 'Long Note One'],
 '15_philippi': ['Lightless Dawn', 'Ossuary 2 - Turn'], '16_son_of_a_god': ['Eternal Hope', 'Bittersweet']}
AMB = {'night': [('night.wav', 0.30)], 'steel': [('wind.wav', 0.22)], 'dawn': [('wind.wav', 0.24)],
       'ash': [('wind.wav', 0.15)], 'gold': [('wind.wav', 0.06)]}
WORDS = {  # description keyword -> (effect, gain, looped over the shot)
    'boom.wav': (r'\b(charg|clash|storm|combat|battle)', 0.55, False),
    'fire.wav': (r'\b(fire|bonfire|flames|burning|pyre)', 0.35, True),
    'waves.wav': (r'\b(sea|ship|harbour|fleet|boat|beach|swimming)', 0.30, True),
    'march.wav': (r'\b(march|marching|column|wading|legions assembling)', 0.30, True),
    'crowd.wav': (r'\b(crowd|mob|forum|festival|procession|riot)', 0.22, True),
}

def main():
    tl = json.load(open(os.path.join(ROOT, 'build', 'timeline.json'))); D = tl['duration']; items = tl['items']
    chs = sorted({x['chapter'] for x in items if 'chapter' in x})
    span = {c: (min(x['start'] for x in items if x.get('chapter') == c), max(x['start'] + x.get('dur', 0) for x in items if x.get('chapter') == c)) for c in chs}
    cues = []
    for c in chs:
        a, b = span[c]; tr = TRACKS.get(c, ['Long Note One']); n = len(tr); seg = (b - a) / n
        for i, t in enumerate(tr):
            cues.append({'file': t + '.mp3', 'start': round(a + i * seg - (2 if i else 0), 2), 'end': round(a + (i + 1) * seg + 3, 2),
                         'gain': 0.8, 'fade_in': 3, 'fade_out': 4})
    title = [x for x in items if x['type'] == 'title']
    if title: cues.append({'file': 'Despair and Triumph.mp3', 'start': title[0]['start'] - 2, 'end': title[0]['start'] + 15, 'gain': 0.95, 'fade_in': 1.5, 'fade_out': 5})
    sfx, run = [], None
    shots = [x for x in items if x['type'] == 'shot']
    for s in shots + [None]:   # ambience beds that follow the grade
        g = s['grade'] if s else None
        if run and (g != run[0] or s is None):
            for f, gain in AMB.get(run[0], []):
                if run[2] - run[1] > 4: sfx.append({'file': f, 'start': round(run[1], 2), 'end': round(run[2], 2), 'gain': gain})
            run = None
        if s and run is None: run = [g, s['start'], s['start'] + s['dur']]
        elif s: run[2] = s['start'] + s['dur']
    sd = {x['id']: x for x in json.load(open(os.path.join(ROOT, 'shots.json')))}
    for s in shots:
        d = sd.get(s['id'], {}).get('desc', '').lower()
        if s['kind'] == 'quote': sfx.append({'file': 'thud.wav', 'start': round(s['start'] + 0.4, 2), 'gain': 0.35, 'hit': True}); continue
        for f, (rx, gain, loop) in WORDS.items():
            if re.search(rx, d):
                if loop: sfx.append({'file': f, 'start': round(s['start'], 2), 'end': round(s['start'] + s['dur'], 2), 'gain': gain})
                else: sfx.append({'file': f, 'start': round(s['start'] + 0.6, 2), 'gain': gain, 'hit': True})
    for x in items:   # whoosh into every chapter card
        if x['type'] == 'card': sfx.append({'file': 'whoosh.wav', 'start': round(x['start'] - 0.9, 2), 'gain': 0.45, 'hit': True})
    if '11_the_murder' in span:
        m0 = span['11_the_murder'][0]
        sfx.append({'file': 'riser.wav', 'start': round(m0 - 6.0, 2), 'gain': 0.5, 'hit': True})
        sfx.append({'file': 'heartbeat.wav', 'start': round(m0 + 6.0, 2), 'end': round(m0 + 75, 2), 'gain': 0.45})
        sfx.append({'file': 'boom.wav', 'start': round(m0 + 0.2, 2), 'gain': 0.7, 'hit': True})
    for c in ('10_the_morning', '11_the_murder'):
        if c in span: sfx.append({'file': 'drone.wav', 'start': span[c][0], 'end': span[c][1], 'gain': 0.2})
    if title: sfx.append({'file': 'boom.wav', 'start': title[0]['start'], 'gain': 0.9, 'hit': True})
    json.dump({'credit': 'Music by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0',
               'cues': cues, 'sfx': sfx}, open(os.path.join(ROOT, 'music.json'), 'w'), indent=1)
    print(len(cues), 'music cues,', len(sfx), 'sfx cues')

if __name__ == '__main__': main()
