"""Assemble the documentary: plan -> prep -> video -> audio -> mux.

  python3 tools/build_video.py plan      # timeline.json, captions.srt, chapters.txt
  python3 tools/build_video.py prep      # pre-graded 2304x1296 stills
  python3 tools/build_video.py video [--preview]   # per-chapter H.264 parts (parallel)
  python3 tools/build_video.py audio     # narration + ducked music, loudness-normalized
  python3 tools/build_video.py mux       # final.mp4
"""
import json, os, sys, glob, math, random, subprocess, hashlib, unicodedata
from concurrent.futures import ProcessPoolExecutor
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build')
IMG = os.path.join(B, 'images')
PREP = os.path.join(IMG, 'prepped')
PARTS = os.path.join(B, 'parts')
FONTS = os.path.join(ROOT, 'assets', 'fonts')
FPS, W, H = 30, 1920, 1080
SW, SH = 2304, 1296            # prepped still size (1.2x)
XF = 1.2                       # crossfade seconds
PARA_GAP, CARD, TITLE_CARD, OUTRO = 0.9, 6.0, 9.0, 14.0
SHOT_TARGET = 8.5              # seconds per still

CHAPTER_SUBTITLES = {
    '01_a_world_connected': 'A World of Brothers', '02_uluburun': 'The Ship at Uluburun',
    '03_kadesh': 'Kadesh and the First Peace', '04_cracks': 'The First Cracks',
    '05_ugarit': 'The Last Days of Ugarit', '06_hattusa': 'The Empty Capital',
    '07_greece': 'The Fall of the Palaces', '08_cyprus': 'The Island of Copper',
    '09_egypt': "Egypt's Last Stand", '10_who_were_sea_peoples': 'Who Were the Sea Peoples?',
    '11_perfect_storm': 'The Perfect Storm', '12_aftermath': 'Out of the Ruins',
}
ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']

# ----------------------------------------------------------------------------- plan
def load_chapters():
    out = []
    for f in sorted(glob.glob(os.path.join(B, 'narration', '*.json'))):
        out.append(json.load(open(f)))
    return out

def pick_images(chapters):
    """Per paragraph: fill ~dur/SHOT_TARGET stills from assets/visual_plan.json sources, never reusing an image."""
    db = {}
    for f in ('museum.json', 'aic.json'):
        p = os.path.join(IMG, f)
        if os.path.exists(p): db.update(json.load(open(p)))
    rej = set()
    rp = os.path.join(ROOT, 'assets', 'reject.txt')
    if os.path.exists(rp): rej = {l.split()[0] for l in open(rp) if l.strip() and not l.startswith('#')}
    vplan = json.load(open(os.path.join(ROOT, 'assets', 'visual_plan.json')))
    allow = json.load(open(os.path.join(ROOT, 'assets', 'aic_allow.json')))
    allow_ids = {i for v in allow.values() for i in v}
    used, map_uses = set(), {}
    def cands(spec):
        if spec.startswith('map:'): return [{'file': 'maps/' + spec[4:] + '.png', 'id': spec, 'map': True}]
        topic, _, kw = spec[2:].partition('~')
        kws = [k.lower() for k in kw.split('|')] if kw else None
        out = []
        for r in db.get(topic, []):
            if r['id'] in rej or not os.path.exists(os.path.join(IMG, r['file'])): continue
            if r['id'].startswith('aic') and r['id'] not in allow_ids: continue
            if r['id'].startswith('met') and not r.get('artist') and 'BCE' not in r.get('date', '') and 'B.C.' not in r.get('date', ''):
                continue   # unattributed artifact not dated BCE: wrong era
            hay = unicodedata.normalize('NFKD', r.get('title', '') + ' ' + r.get('term', '')).encode('ascii', 'ignore').decode().lower()
            if kws and not any(k in hay for k in kws): continue
            out.append(r)
        return out
    plan = []
    for ch in chapters:
        specs = vplan[ch['id']]
        assert len(specs) == len(ch['paras']), (ch['id'], len(specs), len(ch['paras']))
        for i, p in enumerate(ch['paras']):
            n = max(1, round((p['dur'] + PARA_GAP) / SHOT_TARGET))
            chosen = []
            pools = [cands(sp) for sp in specs[i]]
            # round-robin across the listed sources so a paragraph mixes them
            for rnd in range(40):
                for pool in pools:
                    if len(chosen) >= n: break
                    for r in pool:
                        if r.get('map'):
                            if map_uses.get((r['id'], ch['id'], i)): continue
                            map_uses[(r['id'], ch['id'], i)] = 1
                            chosen.append({'file': r['file'], 'credit': None}); break
                        if r['id'] in used: continue
                        used.add(r['id']); chosen.append({'file': r['file'], 'credit': r}); break
                if len(chosen) >= n or rnd > 3 and not any(pools): break
            if len(chosen) < n:   # top up from the same chapter's other sources
                for sp in [x for row in specs for x in row]:
                    for r in cands(sp):
                        if len(chosen) >= n: break
                        if r.get('map') or r['id'] in used: continue
                        used.add(r['id']); chosen.append({'file': r['file'], 'credit': r})
            if not chosen: chosen = [{'file': 'maps/map_overview.png', 'credit': None}]
            plan.append((ch['id'], i, chosen))
    return plan

def fmt_ts(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f'{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}'.replace(',1000', ',999')

def split_caption(text, start, end):
    words, chunks, cur = text.split(), [], []
    for w in words:
        if len(' '.join(cur + [w])) > 84 and cur: chunks.append(' '.join(cur)); cur = [w]
        else: cur.append(w)
    if cur: chunks.append(' '.join(cur))
    tot = sum(len(c) for c in chunks); t = start; out = []
    for c in chunks:
        d = (end - start) * len(c) / tot
        lines = c
        if len(c) > 42:
            ws = c.split(); best = None
            for k in range(1, len(ws)):
                a, b = ' '.join(ws[:k]), ' '.join(ws[k:])
                score = max(len(a), len(b))
                if best is None or score < best[0]: best = (score, a + '\n' + b)
            lines = best[1]
        out.append((t, t + d, lines)); t += d
    return out

def plan():
    chapters = load_chapters()
    picks = {(c, i): ch for c, i, ch in pick_images(chapters)}
    shots, audio, chapter_marks = [], [], []
    t = 1.0
    def add_paragraphs(ch):
        nonlocal t, captions
        for i, p in enumerate(ch['paras']):
            audio.append({'wav': p['wav'], 'start': round(t, 3)})
            for s in p['sentences']:
                captions += split_caption(s['text'], t + s['start'], t + s['end'])
            seg = p['dur'] + PARA_GAP
            imgs = picks[(ch['id'], i)]
            d = seg / len(imgs)
            for k, im in enumerate(imgs):
                shots.append({'kind': 'image', 'src': im['file'], 'start': round(t + k * d, 3), 'dur': round(d, 3), 'chapter': ch['id']})
            t += seg
    captions = []
    segs = []
    for ch in chapters:
        segs.append([ch['id'], round(t, 3)])
        if ch['id'] == '00_cold_open':
            chapter_marks.append((0.0, 'Cold Open: The Last Letter of Ugarit'))
            add_paragraphs(ch)
            t += 0.6
            chapter_marks.append((t, 'Title'))
            segs.append(['title', round(t, 3)])
            shots.append({'kind': 'title', 'start': round(t, 3), 'dur': TITLE_CARD, 'chapter': 'title'}); t += TITLE_CARD
            continue
        num = int(ch['id'][:2])
        chapter_marks.append((t, f"Chapter {num}: {CHAPTER_SUBTITLES[ch['id']]}"))
        shots.append({'kind': 'card', 'num': num, 'title': CHAPTER_SUBTITLES[ch['id']], 'start': round(t, 3), 'dur': CARD, 'chapter': ch['id']})
        t += CARD
        add_paragraphs(ch)
        t += 0.6
    segs.append(['outro', round(t, 3)])
    shots.append({'kind': 'outro', 'start': round(t, 3), 'dur': OUTRO, 'chapter': 'outro'}); t += OUTRO
    total = round(t, 3)
    segs = [[a, st, (segs[i + 1][1] if i + 1 < len(segs) else total)] for i, (a, st) in enumerate(segs)]
    json.dump({'total': total, 'music_segments': segs, 'shots': shots, 'audio': audio, 'chapters': chapter_marks}, open(os.path.join(B, 'timeline.json'), 'w'), indent=1)
    with open(os.path.join(B, 'captions.srt'), 'w') as f:
        for k, (a, b, txt) in enumerate(captions, 1):
            f.write(f'{k}\n{fmt_ts(a)} --> {fmt_ts(b)}\n{txt}\n\n')
    with open(os.path.join(B, 'chapters.txt'), 'w') as f:
        for a, name in chapter_marks:
            m, s = divmod(int(a), 60); h, m = divmod(m, 60)
            f.write((f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}') + f' {name}\n')
    credits = {}
    for c, i, ims in pick_images(chapters):
        for im in ims:
            if im['credit']: credits[im['file']] = im['credit']
    json.dump(credits, open(os.path.join(B, 'credits_used.json'), 'w'), indent=1)
    print(f'total {total/60:.1f} min, {len(shots)} shots, {len(captions)} captions, {len(credits)} credited images')

# ----------------------------------------------------------------------------- prep
def prep_one(rel):
    import cv2
    src = os.path.join(IMG, rel)
    os.makedirs(PREP, exist_ok=True)
    dst = os.path.join(PREP, hashlib.md5(rel.encode()).hexdigest()[:14] + '.jpg')
    if os.path.exists(dst): return dst
    im = cv2.imread(src, cv2.IMREAD_COLOR)
    if im is None:
        from PIL import Image
        im = cv2.cvtColor(np.asarray(Image.open(src).convert('RGB')), cv2.COLOR_RGB2BGR)
    h, w = im.shape[:2]; ar = w / h
    def cover(img, W2, H2):
        h, w = img.shape[:2]; s = max(W2 / w, H2 / h)
        r = cv2.resize(img, (max(W2, int(w * s + 0.5)), max(H2, int(h * s + 0.5))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        y0 = (r.shape[0] - H2) // 2; x0 = (r.shape[1] - W2) // 2
        return r[y0:y0 + H2, x0:x0 + W2]
    if rel.startswith('maps/') or 1.55 <= ar <= 2.1:
        out = cover(im, SW, SH)
    else:
        bg = cover(im, SW // 4, SH // 4); bg = cv2.GaussianBlur(bg, (0, 0), 9); bg = cv2.resize(bg, (SW, SH), interpolation=cv2.INTER_CUBIC)
        out = (bg.astype(np.float32) * 0.38).astype(np.uint8)
        s = min(SW * 0.86 / w, SH * 0.88 / h)
        fw, fh = int(w * s), int(h * s)
        fg = cv2.resize(im, (fw, fh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        x0, y0 = (SW - fw) // 2, (SH - fh) // 2
        sh = np.zeros((SH, SW), np.float32); sh[y0 + 18:y0 + fh + 18, x0 + 12:x0 + fw + 12] = 1
        sh = cv2.GaussianBlur(sh, (0, 0), 22)[..., None]
        out = (out.astype(np.float32) * (1 - 0.65 * sh)).astype(np.uint8)
        out[y0:y0 + fh, x0:x0 + fw] = fg
    if not rel.startswith('maps/'):
        f = out.astype(np.float32)
        f = (f - 128) * 1.04 + 128 - 3                   # gentle contrast
        f *= np.array([0.95, 1.0, 1.04], np.float32)      # BGR warm
        out = np.clip(f, 0, 255).astype(np.uint8)
    cv2.imwrite(dst, out, [cv2.IMWRITE_JPEG_QUALITY, 93])
    return dst

def prep():
    os.makedirs(PREP, exist_ok=True)
    tl = json.load(open(os.path.join(B, 'timeline.json')))
    rels = sorted({s['src'] for s in tl['shots'] if s['kind'] == 'image'})
    with ProcessPoolExecutor(4) as ex: list(ex.map(prep_one, rels))
    print('prepped', len(rels))

# ----------------------------------------------------------------------------- cards
def font(n, s):
    from PIL import ImageFont; return ImageFont.truetype(os.path.join(FONTS, n), s)

def card_frame(kind, shot, bg=None):
    from PIL import Image, ImageDraw, ImageFilter
    import cv2
    if bg is not None:
        base = Image.fromarray(cv2.cvtColor(cv2.resize(bg, (W, H)), cv2.COLOR_BGR2RGB)).filter(ImageFilter.GaussianBlur(14))
        base = Image.eval(base, lambda v: int(v * 0.30))
    else:
        base = Image.new('RGB', (W, H), (10, 9, 8))
    d = ImageDraw.Draw(base); gold = (214, 184, 130); cream = (238, 228, 208)
    if kind == 'card':
        d.text((W / 2, H / 2 - 120), f'CHAPTER {ROMAN[shot["num"]]}', font=font('Cinzel.ttf', 46), fill=gold, anchor='mm')
        d.line([(W / 2 - 170, H / 2 - 70), (W / 2 + 170, H / 2 - 70)], fill=gold, width=2)
        d.text((W / 2, H / 2 + 10), shot['title'].upper(), font=font('Cinzel.ttf', 92), fill=cream, anchor='mm')
    elif kind == 'title':
        d.text((W / 2, H / 2 - 150), 'ANCIENT WORLD FILES', font=font('Cinzel.ttf', 40), fill=gold, anchor='mm')
        d.text((W / 2, H / 2 - 20), 'THE BRONZE AGE COLLAPSE', font=font('Cinzel.ttf', 116), fill=cream, anchor='mm')
        d.line([(W / 2 - 260, H / 2 + 62), (W / 2 + 260, H / 2 + 62)], fill=gold, width=2)
        d.text((W / 2, H / 2 + 125), 'The Year Civilization Fell  ·  1177 B.C.E.', font=font('CormorantGaramond-Italic.ttf', 64), fill=cream, anchor='mm')
    elif kind == 'outro':
        d.text((W / 2, H / 2 - 150), 'ANCIENT WORLD FILES', font=font('Cinzel.ttf', 84), fill=cream, anchor='mm')
        d.text((W / 2, H / 2 - 50), 'Evidence-based deep dives into the lost civilizations of the ancient world', font=font('CormorantGaramond-Italic.ttf', 52), fill=gold, anchor='mm')
        d.text((W / 2, H / 2 + 90), 'Narration: AI voice (Kokoro TTS)  ·  Images: Wikimedia Commons, The Met (CC0)', font=font('CormorantGaramond.ttf', 38), fill=cream, anchor='mm')
        d.text((W / 2, H / 2 + 145), 'Full image credits and sources in the description', font=font('CormorantGaramond.ttf', 38), fill=cream, anchor='mm')
    return cv2.cvtColor(np.asarray(base), cv2.COLOR_RGB2BGR)

# ----------------------------------------------------------------------------- video
def _vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    v = 1 - 0.42 * np.clip((r - 0.45) / 0.55, 0, 1) ** 1.6
    return np.repeat(v[..., None], 3, axis=2)

class ShotRenderer:
    def __init__(self, shot, idx):
        import cv2
        self.s = shot; self.kind = shot['kind']
        rnd = random.Random(idx * 7919 + 13)
        if self.kind == 'image':
            p = prep_one(shot['src']); self.img = cv2.imread(p)
            composite = not (shot['src'].startswith('maps/'))
            mapshot = shot['src'].startswith('maps/')
            amt = 0.06 if mapshot else 0.10 + rnd.random() * 0.06
            zin = rnd.random() < 0.6
            self.z0, self.z1 = (1.0, 1.0 + amt) if zin else (1.0 + amt, 1.0)
            ang = rnd.random() * 2 * math.pi; pan = 0.0 if mapshot else 0.35 + 0.4 * rnd.random()
            self.c0 = (math.cos(ang) * -pan, math.sin(ang) * -pan); self.c1 = (math.cos(ang) * pan, math.sin(ang) * pan)
        else:
            bg = None
            self.frame = card_frame(self.kind, shot, bg)
    def render(self, u):
        import cv2
        L = self.s['dur'] + XF
        p = min(max(u / L, 0), 1)
        if self.kind != 'image':
            z = 1.0 + 0.03 * p
            M = np.float32([[z, 0, W / 2 * (1 - z)], [0, z, H / 2 * (1 - z)]])
            return cv2.warpAffine(self.frame, M, (W, H), flags=cv2.INTER_LINEAR)
        z = self.z0 + (self.z1 - self.z0) * p
        vw = (SW / 1.2) * 1.2 / z; vh = vw * 9 / 16   # z=1 -> full prepped frame
        mx, my = (SW - vw) / 2, (SH - vh) / 2
        cx = SW / 2 + mx * (self.c0[0] + (self.c1[0] - self.c0[0]) * p)
        cy = SH / 2 + my * (self.c0[1] + (self.c1[1] - self.c0[1]) * p)
        s = vw / W
        M = np.float32([[s, 0, cx - vw / 2], [0, s, cy - vh / 2]])
        return cv2.warpAffine(self.img, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT)

def render_part(args):
    import cv2
    pid, shots, t0, t1, preview = args
    out = os.path.join(PARTS, f'part_{pid:03d}.mp4')
    if os.path.exists(out) and not preview: return out
    vig = _vignette()
    w, h = (W, H)
    enc = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'veryfast' if preview else 'medium', '-crf', '28' if preview else '19', '-tune', 'film',
           '-pix_fmt', 'yuv420p', '-g', str(FPS * 2), '-threads', '2']
    if preview: enc += ['-vf', 'scale=960:540']
    tmp = out + '.tmp.mp4'
    pr = subprocess.Popen(enc + [tmp], stdin=subprocess.PIPE)
    rs = {}
    nfr = int(round((t1 - t0) * FPS))
    for fi in range(nfr):
        t = t0 + fi / FPS
        acc = None; wsum = 0
        layers = []
        for k, s in shots:
            a, b = s['start'], s['start'] + s['dur']
            if t < a - XF / 2 or t >= b + XF / 2: continue
            # opacity: fade in over XF centred at a, out over XF centred at b
            op = min(1, (t - (a - XF / 2)) / XF, ((b + XF / 2) - t) / XF)
            if s['kind'] in ('card', 'title', 'outro'):
                op = min(1, (t - a) / 0.9, (b - t) / 0.9)
            elif s.get('fade_in_black') and t < a + XF / 2: op = min(op, (t - a) / 0.9) if t > a else 0
            if op <= 0: continue
            if k not in rs: rs[k] = ShotRenderer(s, k)
            layers.append((op, rs[k].render(t - (a - XF / 2))))
        for k in [k for k in rs if not any(k == kk and (t < s['start'] + s['dur'] + XF) for kk, s in shots)]:
            del rs[k]
        frame = np.zeros((H, W, 3), np.float32)
        if layers:
            layers.sort(key=lambda x: -x[0])
            frame = layers[0][1].astype(np.float32) * layers[0][0]
            for op, img in layers[1:]:
                # cross-dissolve on top of dominant layer
                frame = frame * (1 - op) + img.astype(np.float32) * op if op < 1 else img.astype(np.float32)
        frame *= vig
        pr.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    pr.stdin.close(); pr.wait()
    os.replace(tmp, out)
    return out

def video(preview=False, only=None):
    os.makedirs(PARTS, exist_ok=True)
    tl = json.load(open(os.path.join(B, 'timeline.json')))
    shots = list(enumerate(tl['shots']))
    # split into parts at card boundaries (cards start from black, so parts are independent)
    bounds = [0.0] + [s['start'] for _, s in shots if s['kind'] in ('card', 'title', 'outro')] + [tl['total']]
    # mark first image shot after a card / at start as fading from black
    jobs = []
    for pid in range(len(bounds) - 1):
        t0, t1 = bounds[pid], bounds[pid + 1]
        sub = [(k, s) for k, s in shots if s['start'] < t1 and s['start'] + s['dur'] + XF > t0]
        jobs.append((pid, sub, t0, t1, preview))
    if only is not None: jobs = [j for j in jobs if j[0] in only]
    with ProcessPoolExecutor(3) as ex:
        for r in ex.map(render_part, jobs): print('done', os.path.basename(r), flush=True)
    with open(os.path.join(PARTS, 'list.txt'), 'w') as f:
        for pid in range(len(bounds) - 1): f.write(f"file 'part_{pid:03d}.mp4'\n")

# ----------------------------------------------------------------------------- audio
def audio():
    import soundfile as sf
    from scipy.signal import resample_poly
    tl = json.load(open(os.path.join(B, 'timeline.json')))
    SR = 48000; N = int(tl['total'] * SR) + SR
    voice = np.zeros(N, np.float32)
    for a in tl['audio']:
        x, sr = sf.read(os.path.join(ROOT, a['wav']), dtype='float32')
        x = resample_poly(x, 2, 1).astype(np.float32)
        i = int(a['start'] * SR)
        voice[i:i + len(x)] += x[:N - i]
    # voice activity envelope (10 ms frames), smoothed
    hop = SR // 100
    act = np.array([np.abs(voice[i:i + hop]).max() > 0.02 for i in range(0, N, hop)], np.float32)
    k = int(0.9 * 100); act = np.convolve(act, np.ones(k) / k, mode='same') > 0.02
    env = np.where(act, 0.20, 0.55).astype(np.float32)
    # smooth ramps (0.6s)
    k = 60; env = np.convolve(np.pad(env, (k, k), mode='edge'), np.ones(k) / k, mode='same')[k:-k]
    gain = np.repeat(env, hop)[:N]
    # music bed, aligned to chapters (assets/music_plan.json)
    mplan = json.load(open(os.path.join(ROOT, 'assets', 'music_plan.json')))
    cache = {}
    def track(name):
        if name not in cache:
            x, sr = sf.read(os.path.join(ROOT, 'assets', 'music', name + '.wav'), dtype='float32', always_2d=True)
            x = x.mean(axis=1)
            if sr != SR: x = resample_poly(x, SR, sr).astype(np.float32)
            cache[name] = x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * 0.1   # -20 dBFS RMS
        return cache[name]
    bed = np.zeros(N, np.float32); fade = 3 * SR
    for seg_id, st, en in tl['music_segments']:
        a = max(0, int(st * SR) - fade // 2); b = min(N, int(en * SR) + fade // 2)
        names = mplan.get(seg_id, []); pos = a; k = 0
        while pos < b and names:
            x = track(names[k % len(names)]).copy(); k += 1
            take = min(len(x), b - pos)
            x = x[:take]
            r = np.ones(take, np.float32); f = min(fade, take // 2)
            r[:f] = np.linspace(0, 1, f); r[take - f:] = np.linspace(1, 0, f); x *= r
            bed[pos:pos + take] += x
            pos = pos + take - f
    # fade music in at start, out at end
    bed[:3 * SR] *= np.linspace(0, 1, 3 * SR); bed[-6 * SR:] *= np.linspace(1, 0, 6 * SR)
    mix = voice + bed * gain
    sf.write(os.path.join(B, 'mix_raw.wav'), mix, SR, subtype='FLOAT')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(B, 'mix_raw.wav'), '-af',
                    'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'pcm_s16le', os.path.join(B, 'mix.wav')], check=True)
    print('audio done', round(len(mix) / SR / 60, 1), 'min')

def mux():
    out = os.path.join(B, 'final.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(PARTS, 'list.txt'),
                    '-i', os.path.join(B, 'mix.wav'), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-shortest', '-movflags', '+faststart', out], check=True)
    print('wrote', out)

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'plan': plan()
    elif cmd == 'prep': prep()
    elif cmd == 'video':
        only = [int(x) for x in sys.argv[2].split(',')] if len(sys.argv) > 2 and sys.argv[2] != '--preview' else None
        video('--preview' in sys.argv, only)
    elif cmd == 'audio': audio()
    elif cmd == 'mux': mux()
