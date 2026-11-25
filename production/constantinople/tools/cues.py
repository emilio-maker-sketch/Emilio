"""Write music.json (music + ambience + hits) for the whole film from build/timeline.json."""
import os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKS = {
 '00_cold_open': ['Ossuary 1 - A Beginning'], '01_queen_of_cities': ['Echoes of Time v2', 'Unwritten Return'],
 '02_two_rulers': ['Long Note One', 'Ossuary 5 - Rest'], '03_throat_cutter': ['Lost Frontier', 'Dark Times'],
 '04_divided_city': ['Long Note Two', 'Ossuary 6 - Air'], '05_guns_of_april': ['Anguish'],
 '05a_first_weeks': ['Lightless Dawn'], '06_four_ships': ['Despair and Triumph'], '07_ships_over_hill': ['Dreams Become Real'],
 '08_war_underground': ['Long Note Three', 'Ossuary 2 - Turn'], '09_signs_and_omens': ['Long Note Four'],
 '10_last_night': ['Long Note Two'], '11_the_fall': ['Lightless Dawn', 'Anguish'], '12_conquerors_city': ['Bittersweet'],
 '12a_the_witnesses': ['Ossuary 5 - Rest'], '13_last_day_of_rome': ['Eternal Hope', 'Bittersweet']}
AMB = {'night': [('night.wav', 0.32)], 'steel': [('wind.wav', 0.22)], 'dawn': [('wind.wav', 0.28), ('fire.wav', 0.18)],
       'ash': [('wind.wav', 0.15)], 'gold': [('wind.wav', 0.08)]}
HIT = ('fires', 'firing', 'opened fire', 'explod', 'cannonball', 'erupt', 'smashing')

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
    for s in shots + [None]:
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
        if any(h in d for h in HIT): sfx.append({'file': 'boom.wav', 'start': round(s['start'] + 0.8, 2), 'gain': 0.8})
        if 'bell' in d: sfx.append({'file': 'bells.wav', 'start': round(s['start'], 2), 'gain': 0.4})
    for c in ('11_the_fall', '10_last_night'):
        if c in span: sfx.append({'file': 'drone.wav', 'start': span[c][0], 'end': span[c][1], 'gain': 0.22})
    if title: sfx.append({'file': 'boom.wav', 'start': title[0]['start'], 'gain': 0.9})
    json.dump({'credit': 'Music by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0',
               'cues': cues, 'sfx': sfx}, open(os.path.join(ROOT, 'music.json'), 'w'), indent=1)
    print(len(cues), 'music cues,', len(sfx), 'sfx cues')

if __name__ == '__main__': main()
