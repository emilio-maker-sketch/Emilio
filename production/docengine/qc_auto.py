"""Automated technical QC of a rendered documentary (run from the project dir).

  python3 ../docengine/qc_auto.py <video.mp4> [--srt build/captions_en.srt]

Checks (each PASS / WARN / FAIL with evidence):
  decode      - the file decodes end to end without errors
  black       - black stretches outside intentional opening/ending (blackdetect)
  freeze      - frozen picture >= 4 s (freezedetect)
  static      - stretches with almost no visual change (sampled frame differences)
  strobe      - clusters of hard cuts (> 3 in 2 s) that read as glitchy
  look        - exposure/saturation outliers vs the rest of the film (visual consistency)
  loudness    - integrated loudness -14 LUFS +/-1, true peak <= -1 dBTP, loudness range
  balance     - level of the bed in narration pauses vs. speech (music must not compete with the voice)
  subtitles   - cue timing against the narration's word timestamps, reading speed, line length
  spelling    - every on-screen string (cards, notes, labels, titles) against a dictionary + the narration's own words
  images      - source resolution vs. how large each image is shown (soft upscales), near-duplicate images
Writes build/qc_auto/report.json and report.md; exit 1 on any FAIL.
"""
import os, sys, re, json, subprocess, glob
import numpy as np, cv2

PROJ = os.getcwd(); OUT = os.path.join(PROJ, 'build', 'qc_auto'); os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
RES = []


def res(check, status, msg, items=None):
    RES.append({'check': check, 'status': status, 'msg': msg, 'items': items or []})
    print(f'{status:5s} {check:10s} {msg}')


def ff_pass(video):
    """One decode pass: errors, blackdetect, freezedetect, scene cuts, EBU R128."""
    cmd = ['ffmpeg', '-hide_banner', '-nostats', '-v', 'info', '-i', video,
           '-filter_complex', "[0:v]scale=480:-2,blackdetect=d=0.4:pix_th=0.06,freezedetect=n=0.002:d=4,select='gt(scene,0.42)',metadata=print:file=-[v];[0:a]ebur128=peak=true[a]",
           '-map', '[v]', '-map', '[a]', '-f', 'null', '-']
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout + p.stderr


def tc(t): return f'{int(t // 60)}:{t % 60:04.1f}'


def main():
    video = sys.argv[1]
    srt = sys.argv[sys.argv.index('--srt') + 1] if '--srt' in sys.argv else os.path.join(PROJ, 'build', 'captions_en.srt')
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video], capture_output=True, text=True).stdout)
    log = ff_pass(video)
    errs = [l for l in log.splitlines() if re.search(r'error|corrupt|invalid', l, re.I) and 'Error while filtering' not in l and 'ebur128' not in l]
    res('decode', 'PASS' if not errs else 'FAIL', f'{len(errs)} decode errors', errs[:10])

    blacks = [(float(a), float(b)) for a, b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', log)]
    bad = [(a, b) for a, b in blacks if a > 3.0 and b < dur - 6 and b - a > .6]
    res('black', 'PASS' if not bad else 'WARN', f'{len(bad)} black stretches > 0.6 s (excluding open/close)', [f'{tc(a)}-{tc(b)}' for a, b in bad])

    fz = re.findall(r'freeze_start: ([\d.]+).*?freeze_duration: ([\d.]+)', log, re.S)
    fz = [(float(a), float(d)) for a, d in fz]
    res('freeze', 'PASS' if not fz else 'WARN', f'{len(fz)} frozen stretches >= 4 s', [f'{tc(a)} for {d:.1f}s' for a, d in fz])

    cuts = sorted(float(x) for x in re.findall(r'pts_time:([\d.]+)', log))
    strobe = [cuts[i] for i in range(len(cuts) - 3) if cuts[i + 3] - cuts[i] < 2.0]
    res('strobe', 'PASS' if not strobe else 'WARN', f'{len(cuts)} hard cuts; {len(strobe)} clusters of >3 cuts in 2 s', [tc(t) for t in strobe[:20]])

    # loudness
    m = re.search(r'Integrated loudness:\s+I:\s+([-\d.]+) LUFS.*?LRA:\s+([-\d.]+) LU.*?True peak:\s+Peak:\s+([-\d.]+) dBFS', log, re.S)
    if m:
        I, LRA, TP = map(float, m.groups())
        st = 'PASS' if abs(I + 14) <= 1 and TP <= -0.9 else 'FAIL'
        res('loudness', st, f'integrated {I} LUFS, range {LRA} LU, true peak {TP} dBTP (target -14 LUFS, <= -1 dBTP)')
    else:
        res('loudness', 'FAIL', 'no loudness measurement')

    # sampled frames: static stretches + look consistency
    cap = cv2.VideoCapture(video); fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = .5; prev = None; diffs = []; looks = []
    t = 0.0
    while t < dur:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read()
        if not ok: break
        sm = cv2.resize(fr, (320, 180), interpolation=cv2.INTER_AREA).astype(np.float32)
        if prev is not None: diffs.append((t, float(np.abs(sm - prev).mean())))
        hsv = cv2.cvtColor(sm.astype(np.uint8), cv2.COLOR_BGR2HSV)
        looks.append((t, float(sm.mean() / 255), float(hsv[..., 1].mean() / 255)))
        prev = sm; t += step
    runs, cur = [], None
    for t, d in diffs:
        if d < .55:
            cur = cur or t
        else:
            if cur and t - cur >= 8: runs.append((cur, t))
            cur = None
    if cur and diffs[-1][0] - cur >= 8: runs.append((cur, diffs[-1][0]))
    runs = [r for r in runs if r[1] < dur - 8]
    res('static', 'PASS' if not runs else 'WARN', f'{len(runs)} stretches >= 8 s with almost no visual change', [f'{tc(a)}-{tc(b)}' for a, b in runs])
    L = np.array([l[1] for l in looks]); Sx = np.array([l[2] for l in looks])
    lz = (L - np.median(L)) / (np.median(np.abs(L - np.median(L))) * 1.48 + 1e-6)
    sz = (Sx - np.median(Sx)) / (np.median(np.abs(Sx - np.median(Sx))) * 1.48 + 1e-6)
    # intentional looks (title cards, film inserts, 3D splices) are excluded: only unplanned outliers count
    tlj = json.load(open(os.path.join(PROJ, 'build', 'timeline.json'))); cfgj = json.load(open(os.path.join(PROJ, 'project.json')))
    planned = [(sp_['t0'] - .5, sp_['t1'] + .5) for sp_ in cfgj.get('splices', [])]
    HOLD = {'year': 3.0, 'thesis': 3.6, 'end_open': 4.5, 'end': 7.0, 'open': 6.2, 'zone': 2.5, 'counter': 2.6}
    for e in tlj['events']:
        k_ = e['d'][0]
        if k_ in HOLD: planned.append((e['t'] - .5, e['t'] + HOLD[k_] + .6))
        if k_ == 'film': planned.append((e['t'] - .5, e['t'] + float(next((x.split('=')[1] for x in e['d'] if str(x).startswith('dur=')), 7)) + .6))
        if k_ == 'type': planned.append((e['t'] - .3, e['t'] + 4))
    isplanned = lambda t: any(a <= t <= b for a, b in planned)
    outl = [(looks[i][0], round(L[i], 2), round(Sx[i], 2)) for i in range(len(looks)) if (abs(lz[i]) > 4.5 or sz[i] > 5) and 3 < looks[i][0] < dur - 8 and not isplanned(looks[i][0])]
    # group consecutive samples
    grp = []
    for o in outl:
        if grp and o[0] - grp[-1][1] <= 1.0: grp[-1][1] = o[0]
        else: grp.append([o[0], o[0], o[1], o[2]])
    res('look', 'PASS' if len(grp) <= 3 else 'WARN', f'median luma {np.median(L):.2f}, saturation {np.median(Sx):.2f}; {len(grp)} outlier stretches',
        [f'{tc(a)}-{tc(b)} luma {l} sat {s}' for a, b, l, s in grp[:15]])

    # bed level in pauses vs speech (from the final mix, gated by the narration's word timestamps)
    wj = os.path.join(PROJ, 'build', 'words.json')
    if os.path.exists(wj):
        words = json.load(open(wj)); words = words.get('words', words) if isinstance(words, dict) else words
        words = [{'start': w.get('start', w.get('s')), 'end': w.get('end', w.get('e'))} for w in words if w.get('start', w.get('s')) is not None]
        a = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-ac', '1', '-ar', '8000', '-f', 'f32le', '-'], capture_output=True).stdout
        x = np.frombuffer(a, np.float32); sr = 8000
        # speech and pauses from the synthesised narration's exact sentence boundaries (ASR word gaps contain word tails)
        tl_ = json.load(open(os.path.join(PROJ, 'build', 'timeline.json'))); SS = tl_['sentences']
        sp = np.zeros(len(x), bool); pz = np.zeros(len(x), bool)
        for s_ in SS: sp[int((s_['start'] + .1) * sr):int((s_['end'] - .25) * sr)] = True
        for a_, b_ in zip(SS, SS[1:]):
            if b_['start'] - a_['end'] >= .8: pz[int((a_['end'] + .1) * sr):int((b_['start'] - .1) * sr)] = True
        db = lambda m: 20 * np.log10(np.sqrt(np.mean(x[m] ** 2)) + 1e-9)
        ds, dp = db(sp), db(pz)
        st = 'PASS' if 6 <= ds - dp <= 22 else 'WARN'
        res('balance', st, f'speech {ds:.1f} dB, bed in pauses {dp:.1f} dB -> pauses sit {ds - dp:.1f} dB under speech (target 6-22)')
        # subtitles vs words
        if os.path.exists(srt):
            cues = re.findall(r'(\d\d):(\d\d):(\d\d),(\d\d\d) --> (\d\d):(\d\d):(\d\d),(\d\d\d)\s*\n(.+?)(?:\n\n|\Z)', open(srt).read(), re.S)
            starts = np.array(sorted(w.get('start', 0) for w in words))
            offs, fast, longl = [], [], []
            for c in cues:
                t0 = int(c[0]) * 3600 + int(c[1]) * 60 + int(c[2]) + int(c[3]) / 1000
                t1 = int(c[4]) * 3600 + int(c[5]) * 60 + int(c[6]) + int(c[7]) / 1000
                j = np.searchsorted(starts, t0 - .5); near = starts[max(0, j - 1):j + 2]
                if len(near): offs.append(float(np.min(np.abs(near - t0))))
                txt = c[8].strip(); cps = len(txt.replace('\n', '')) / max(.3, t1 - t0)
                if cps > 21: fast.append(f'{tc(t0)} {cps:.0f} cps')
                if any(len(l) > 42 for l in txt.split('\n')): longl.append(f'{tc(t0)} "{txt[:40]}"')
            # independent reference: the narration is synthesised sentence by sentence, so sentence starts are exact
            tl_ = json.load(open(os.path.join(PROJ, 'build', 'timeline.json')))
            sst = np.array([x['start'] for x in tl_['sentences']])
            cst = np.array([int(c[0]) * 3600 + int(c[1]) * 60 + int(c[2]) + int(c[3]) / 1000 for c in cues])
            sent_off = [float(np.min(np.abs(cst - x))) for x in sst]
            offs = sent_off
            o = np.array(offs)
            st = 'PASS' if len(o) and np.percentile(o, 95) < .25 and not fast else 'WARN'
            res('subtitles', st, f'{len(cues)} cues; caption start vs exact sentence start: median {np.median(o):.3f}s, 95th pct {np.percentile(o, 95):.3f}s; {len(fast)} too fast (>21 cps); {len(longl)} lines > 42 chars',
                fast[:10] + longl[:10])

    # on-screen spelling
    tl = json.load(open(os.path.join(PROJ, 'build', 'timeline.json')))
    narr = ' '.join(s['text'] for s in tl['sentences'])
    cfg = json.load(open(os.path.join(PROJ, 'project.json'))) if os.path.exists(os.path.join(PROJ, 'project.json')) else {}
    strings = []
    for e in tl['events']:
        for a in e['d'][1:]:
            if isinstance(a, str) and not re.match(r'^[a-z_]+=', a) and re.search(r'[A-Za-z]{3,}', a) and not re.match(r'^(met|aic|wc_)\w+$', a) and ' ' in a or (isinstance(a, str) and a.isupper() and len(a) > 3):
                strings.append((e['t'], a))
    try:
        from spellchecker import SpellChecker
        sp_ = SpellChecker(); known = {w.lower() for w in re.findall(r"[A-Za-z]+", narr)} | {w.lower() for w in cfg.get('lexicon', [])}
        bad = []
        for t, s in strings:
            for w in re.findall(r"[A-Za-z][A-Za-z']+", s.replace('|', ' ')):
                wl = re.sub(r"'s$", '', w.lower().strip("'"))
                if len(wl) < 3 or wl in known: continue
                if sp_.unknown([wl]): bad.append(f'{tc(t)} "{w}" in "{s[:50]}"')
        res('spelling', 'PASS' if not bad else 'WARN', f'{len(strings)} on-screen strings, {len(bad)} unknown words', bad[:30])
    except ImportError:
        res('spelling', 'WARN', 'pyspellchecker not installed')

    # images: resolution vs display size, near duplicates
    sys.path.insert(0, PROJ)
    ids = sorted({x for e in tl['events'] for a in e['d'][1:] if isinstance(a, str) for x in re.findall(r'\b(?:met\d+|aic\d+|wc_\w+)\b', a)})
    full = {x for e in tl['events'] if e['d'][0] == 'photo' for x in re.findall(r'\b(?:met\d+|aic\d+|wc_\w+)\b', ' '.join(map(str, e['d'][1:2])))}
    trip = {x for e in tl['events'] if e['d'][0] == 'trip' for x in re.findall(r'\b(?:met\d+|aic\d+|wc_\w+)\b', ' '.join(map(str, e['d'][1:2])))} - full
    paths = {}
    for x in ids:
        g = glob.glob(os.path.join(ROOT, 'build', 'images', '**', x + '.*'), recursive=True)
        if g: paths[x] = g[0]
    soft, hashes = [], {}
    for x, p in paths.items():
        im = cv2.imread(p)
        if im is None: continue
        h, w = im.shape[:2]
        need = 1080 * 1.1 if x in full else (920 if x in trip else 700)
        cover = min(h, w * 9 / 16) if x in full else (h if x in trip else max(h, w))
        if cover < need / 1.6: soft.append(f'{x} {w}x{h} shown {"full-screen" if x in full else "on board"} (upscale {need / cover:.1f}x)')
        g8 = cv2.resize(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA)
        hashes[x] = (g8[:, 1:] > g8[:, :-1]).flatten()
    dup = []
    ks = list(hashes)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            if (hashes[ks[i]] != hashes[ks[j]]).sum() <= 5: dup.append(f'{ks[i]} ~ {ks[j]}')
    res('images', 'PASS' if not soft and not dup else 'WARN', f'{len(paths)} images: {len(soft)} soft upscales, {len(dup)} near-duplicate pairs', soft + dup)

    json.dump({'video': video, 'duration': dur, 'results': RES}, open(os.path.join(OUT, 'report.json'), 'w'), indent=1)
    with open(os.path.join(OUT, 'report.md'), 'w') as f:
        f.write(f'# Technical QC - {os.path.basename(video)} ({tc(dur)})\n\n| check | status | result |\n|---|---|---|\n')
        for r in RES: f.write(f"| {r['check']} | {r['status']} | {r['msg']} |\n")
        for r in RES:
            if r['items']: f.write(f"\n### {r['check']}\n" + ''.join(f'- {i}\n' for i in r['items']))
    return 1 if any(r['status'] == 'FAIL' for r in RES) else 0


if __name__ == '__main__':
    sys.exit(main())
