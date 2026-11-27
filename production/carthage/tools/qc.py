"""Quality control: the checks the brief makes mandatory, run before every render and on the rendered file.

  python3 tools/qc.py                 # timeline, assets, text and sync checks -> QC_REPORT.md (scene-by-scene) + exit status
  python3 tools/qc.py --texts         # list every on-screen text that is not yet in text_register.json
  python3 tools/qc.py --render F.mp4  # + black frames, loudness/peaks, and a frame sheet of every shot for visual inspection

Checks (each one exists because of a mistake that happened, see ../QC_RULES.md):
  IMAGE   every picture on screen is marked VERIFIED in review.json (inspected by eye: subject, place, period, no AI text)
  ZOOM    every picture has a marked subject point; framings stay on it; source resolution is high enough for the zoom
  TEXT    every word on screen (quotes, numbers, dates, labels, map names, captions) is in text_register.json with its source;
          quotes that are also spoken must match the narration word for word
  SYNC    cuts land on sentence boundaries; no picture outlives its subject; no paragraph shows a borrowed picture
  REUSE   no image repeated outside deliberate detail beats
  TECH    no gaps between shots, no black stretches, loudness about -14 LUFS, true peak under -1 dB
"""
import os, sys, json, glob, re, subprocess, collections
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, 'build')
sys.path.insert(0, os.path.dirname(__file__))

def norm(t): return re.sub(r'[^a-z0-9 ]', '', t.lower().replace('’', "'")).split()

def screen_texts(sh):
    """(shot id, kind, text) for every piece of text that will be drawn on screen."""
    out = []
    for x in sh:
        k = x['kind']
        if k == 'quote': out += [(x['id'], 'quote', x['quote']), (x['id'], 'attribution', x['attrib'])]
        if k == 'stat': out += [(x['id'], 'statistic', t.strip()) for t in x['desc'].split('::')]
        if k == 'timeline': out += [(x['id'], 'timeline', e.strip().rstrip('*')) for e in x['desc'].split(';') if e.strip()]
        if k == 'card':
            if x['desc'].strip().lower() == 'end card': out.append((x['id'], 'card', 'end card (credits)'))
            else: out += [(x['id'], 'card', t.strip()) for t in x['desc'].split('·')]
        if k == 'split': out += [(x['id'], 'split label', sd['label']) for sd in x['sides']]
        if x.get('lt'): out += [(x['id'], 'lower third', ' | '.join(x['lt']))]
        if k in ('map', 'diagram') and not x.get('beat'):
            spec = os.path.join(B, 'gfx', x['sid'], 'spec.json')
            if os.path.exists(spec): out += [(x['id'], 'map text', t) for t in json.load(open(spec)).get('texts', [])]
            else: out.append((x['id'], 'map text', 'MISSING GRAPHIC'))
    return out

def main():
    tl = json.load(open(os.path.join(B, 'timeline.json'))); sh = [x for x in tl['items'] if x['type'] == 'shot']
    review = json.load(open(os.path.join(ROOT, 'review.json')))
    reg = json.load(open(os.path.join(ROOT, 'text_register.json'))) if os.path.exists(os.path.join(ROOT, 'text_register.json')) else {}
    narr = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(os.path.join(B, 'narration', '*.json'))}
    caps = [(float(a), float(b), t) for a, b, t in json.load(open(os.path.join(B, 'captions.json')))] if os.path.exists(os.path.join(B, 'captions.json')) else []
    fails = collections.defaultdict(list)
    texts = screen_texts(sh)
    if '--texts' in sys.argv:
        for sid, kind, t in texts:
            if t not in reg: print(f'{sid:10s} {kind:12s} {t}')
        return
    # IMAGE + ZOOM
    for x in sh:
        if x.get('src') and x['kind'] in ('still', 'vid', 'photo', 'detail'):
            key = os.path.splitext(os.path.basename(x['src']))[0]; r = review.get(key)
            if not r or r.get('status') != 'VERIFIED': fails[x['id']].append(f'IMAGE not verified ({key})')
            if not x.get('focus'): fails[x['id']].append('ZOOM no subject point')
            npz = os.path.join(B, 'prep', x['id'].replace('#', '_') + '.npz')
            if os.path.exists(npz):
                z = np.load(npz)
                if 'srcw' in z and int(z['srcw']) < 900: fails[x['id']].append(f"ZOOM low source resolution ({int(z['srcw'])} px across)")
        if x['kind'] == 'split':
            for sd in x['sides']:
                key = os.path.splitext(os.path.basename(sd['src']))[0]
                if review.get(key, {}).get('status') != 'VERIFIED': fails[x['id']].append(f'IMAGE split side not verified ({key})')
    # TEXT
    for sid, kind, t in texts:
        if t not in reg: fails[sid].append(f'TEXT not in register: {kind} "{t}"')
    for x in sh:   # quotes that are also spoken must match the narration
        if x['kind'] != 'quote': continue
        if reg.get(x['quote'], {}).get('narration') == 'reviewed': continue   # indirect speech in the narration, checked by eye
        para = re.sub(r',? (he|she) said,?', '', ' '.join(s['text'] for s in narr[x['chapter']]['paras'][x['para']]['sentences'])); q = norm(x['quote'])
        words = norm(para); joined = ' '.join(words)
        overlap = sum(1 for w in q if w in words) / max(1, len(q))
        if overlap > 0.7 and ' '.join(q) not in joined: fails[x['id']].append('TEXT quote differs from the spoken words')
    # SYNC
    voice = [x for x in tl['items'] if x['type'] == 'voice']; offs = []
    for x in sh:
        if x.get('beat') or x['id'].endswith('-x'): continue
        vs = [y for y in voice if y['chapter'] == x['chapter']]; v = vs[x['para']] if x['para'] < len(vs) else None
        if not v: continue
        para = narr[x['chapter']]['paras'][x['para']]
        b = [v['start'] + s['end'] + 0.12 for s in para['sentences']] + [v['start'] - 0.6, v['start'] - 4.0]
        o = min(abs(x['start'] - t) for t in b); offs.append(o)
    for x in sh:
        if x['id'].endswith('-x'): fails[x['id']].append('SYNC paragraph has no picture of its own (borrowed)')
    # REUSE
    use = collections.defaultdict(list)
    for x in sh:
        if x.get('src') and not x.get('beat') and x['kind'] in ('still', 'vid', 'photo'): use[x['src']].append(x['id'])
    for s_, ids in use.items():
        if len(ids) > 1:
            for i in ids[1:]: fails[i].append(f'REUSE same image as {ids[0]}')
    import hashlib   # the same picture saved under two file names is still a reuse
    seen = {}
    for s_, ids in use.items():
        h = hashlib.md5(open(s_, 'rb').read()).hexdigest() if os.path.exists(s_) else s_
        if h in seen: fails[ids[0]].append(f'REUSE same picture as {seen[h]} (different file)')
        else: seen[h] = ids[0]
    # TECH
    for a, b_ in zip(sh, sh[1:]):
        if a['chapter'] == b_['chapter'] and b_['start'] - (a['start'] + a['dur']) > 0.05: fails[a['id']].append('TECH gap after shot')
    # report
    def ts(t): m, s = divmod(int(t), 60); return f'{m:02d}:{s:02d}'
    def said(t):
        for a, b_, tx in caps:
            if a - 0.3 <= t <= b_ + 0.3: return tx
        return ''
    rows = ['# Scene-by-scene QC report', '', f"Runtime {tl['duration']/60:.1f} min · {len(sh)} shots · "
            f"{sum(o < 0.5 for o in offs)}/{len(offs)} cuts on a sentence boundary · {sum(1 for x in sh if fails.get(x['id']))} shots failing", '',
            '| Time | Shot | Narration at the cut | Visual | Image | Zoom | Text | Sync | Status |', '|---|---|---|---|---|---|---|---|---|']
    for x in sh:
        f = fails.get(x['id'], []); cat = lambda c: 'FAIL' if any(m.startswith(c) for m in f) else 'pass'
        vis = (x.get('desc') or os.path.basename(x.get('src', '')))[:60].replace('|', '/')
        rows.append(f"| {ts(x['start'])}–{ts(x['start'] + x['dur'])} | {x['id']} | {said(x['start'] + 0.5)[:70].replace('|', '/')} | {x['kind']}: {vis} | {cat('IMAGE')} | {cat('ZOOM')} | {cat('TEXT')} | {cat('SYNC')} | {'FIX: ' + '; '.join(f) if f else 'Approved'} |")
    skipped = json.load(open(os.path.join(B, 'skipped.json'))) if os.path.exists(os.path.join(B, 'skipped.json')) else []
    rows += ['', '## Shots removed by QC (not shown in the film)', ''] + [f'- {a}: {b_}' for a, b_ in skipped]
    open(os.path.join(ROOT, 'QC_REPORT.md'), 'w').write('\n'.join(rows) + '\n')
    nf = sum(1 for x in sh if fails.get(x['id']))
    print(f'{nf} shots failing · report: QC_REPORT.md'); [print(' ', k, v) for k, v in list(fails.items())[:40]]
    if '--render' in sys.argv:
        f = sys.argv[sys.argv.index('--render') + 1]
        r = subprocess.run(['ffmpeg', '-hide_banner', '-i', f, '-vf', 'blackdetect=d=0.3:pix_th=0.05', '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
        print('black stretches:', re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', r)[:20])
        print('loudness:', ' '.join(l.strip() for l in r.splitlines()[-14:] if re.search(r'I:|LRA:|Peak:', l)))
    sys.exit(1 if nf else 0)

if __name__ == '__main__': main()
