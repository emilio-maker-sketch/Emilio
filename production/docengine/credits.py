"""Credits list generated from what the film actually uses (run from the project dir).

python3 ../docengine/credits.py <out.txt> [title]
Images: every museum id referenced by the timeline, with title, artist, date and source page.
Music: the project's music_plan.json (Kevin MacLeod, CC BY 4.0). Plus fixed notes for 3D, maps, film scenes, SFX, narration.
"""
import os, sys, json, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import catalog as CAT


def main():
    out = sys.argv[1]; title = sys.argv[2] if len(sys.argv) > 2 else json.load(open('project.json')).get('title', '')
    tl = json.load(open('build/timeline.json')); R = CAT.records()
    ids = []
    for e in tl['events']:
        for a in e['d'][1:]:
            if isinstance(a, str):
                for x in re.findall(r'\b(?:met\d+|aic\d+|wc_\w+)\b', a):
                    if x not in ids: ids.append(x)
    L = [f'CREDITS - {title}', '', 'IMAGES - The Metropolitan Museum of Art, Open Access (CC0)']
    other = []
    for x in ids:
        r = R.get(x)
        if not r: other.append(x); continue
        bits = [r.get('title', '')]
        if r.get('artist'): bits.append(r['artist'])
        if r.get('date'): bits.append(r['date'])
        L.append('- ' + ', '.join(b for b in bits if b) + f" - {r.get('page', '')}")
    if other: L += ['', 'OTHER IMAGES'] + [f'- {x}' for x in other]
    if os.path.exists('music_plan.json'):
        L += ['', 'MUSIC - Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0',
              '- ' + ' · '.join(dict.fromkeys(p[1] for p in json.load(open('music_plan.json'))))]
    L += ['', '3D RECONSTRUCTIONS - illustrative scenes built for this video with three.js (MIT License)',
          'MAPS, DIAGRAMS, SILENT-FILM SCENES - drawn for this video (schematic)',
          'SOUND EFFECTS - CC0 recordings + effects synthesized for this video',
          'NARRATION - Kokoro TTS (Apache 2.0), voice bm_george']
    open(out, 'w').write('\n'.join(L) + '\n'); print(len(ids), 'images credited ->', out)


if __name__ == '__main__':
    main()
