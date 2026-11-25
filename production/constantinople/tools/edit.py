"""The editor: turns narration + shot images into a finished, graded, moving picture.

  python3 tools/edit.py plan [chapters...]      # timeline.json + captions.srt
  python3 tools/edit.py prep [chapters...]      # crop, grade, depth map for every shot image
  python3 tools/edit.py video [chapters...]     # build/parts/<chapter>.mp4 (silent), chapters rendered in parallel
  python3 tools/edit.py audio [chapters...]     # build/audio/mix.wav (narration + music + ambience, -14 LUFS)
  python3 tools/edit.py mux NAME                # build/NAME.mp4

Shot images are looked up in order: edit.json override -> build/gen/z_<id>.png -> build/photos/<id>.jpg
-> build/maps/<id>.png -> a reframed copy of another image in the same paragraph.
Every still gets a slow camera move plus depth parallax (Depth Anything V2) so nothing sits frozen.
"""
import os, sys, json, glob, math, zlib, subprocess
from concurrent.futures import ProcessPoolExecutor
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build'); PREP = os.path.join(B, 'prep'); PARTS = os.path.join(B, 'parts')
FONTS = os.path.join(ROOT, '..', 'assets', 'fonts')
FPS, W, H = 30, 1920, 1080
SW, SH = 2304, 1296                    # working canvas (1.2x) so moves never reveal edges
LEAD, GAP, XF, PXF = 0.7, 1.1, 0.6, 1.2  # narration lead-in, gap after paragraph, shot dissolve, paragraph dissolve
CARD = 5.5
WORDS = 'ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE THIRTEEN FOURTEEN FIFTEEN'.split()

def load(p): return json.load(open(p))
def edits():
    p = os.path.join(ROOT, 'edit.json')
    return load(p) if os.path.exists(p) else {}

# ------------------------------------------------------------------ plan
def resolve(shot, para_shots, ed):
    o = ed.get(shot['id'], {})
    if o.get('skip'): return None
    if 'src' in o: return dict(o, src=os.path.join(ROOT, o['src']))
    for p in (f"gen/z_{shot['id']}.png", f"photos/{shot['id']}.jpg", f"photos/{shot['id']}.png", f"maps/{shot['id']}.png"):
        f = os.path.join(B, p)
        if os.path.exists(f):
            try: Image.open(f).verify(); return dict(o, src=f)
            except Exception: print('  bad image, ignored:', p)
    return 'fallback'

def plan(chs):
    shots = load(os.path.join(ROOT, 'shots.json')); ed = edits()
    narr = {os.path.basename(f)[:-5]: load(f) for f in glob.glob(os.path.join(B, 'narration', '*.json'))}
    order = sorted({s['chapter'] for s in shots})
    if chs: order = [c for c in order if c in chs]
    tl, caps, t = [], [], 0.0
    for ci, ch in enumerate(order):
        n = narr[ch]; title = n['title']
        if ch.startswith('00'):
            pass
        else:
            num, name = title.split(':', 1)
            tl.append({'type': 'card', 'start': t, 'dur': CARD, 'line1': num.strip(), 'line2': name.strip(), 'chapter': ch})
            t += CARD - 0.3
        for pi, para in enumerate(n['paras']):
            ps = [s for s in shots if s['chapter'] == ch and s['para'] == pi]
            seg = LEAD + para['dur'] + GAP
            items = []
            for s in ps:
                r = resolve(s, ps, ed)
                if r is None: continue
                items.append((s, r))
            if not items: raise SystemExit(f'{ch} para {pi}: no usable shots')
            real = [x for x in items if x[1] != 'fallback']
            if not real: raise SystemExit(f'{ch} para {pi}: no images yet')
            fixed = []
            for k, (s, r) in enumerate(items):
                if r == 'fallback':
                    base = real[k % len(real)][1]
                    r = dict(base, crop=base.get('alt_crop', [0.18, 0.12, 0.82, 0.48 + 0.12 * (k % 2)]), fallback=True)
                fixed.append((s, r))
            weights = [s['dur'] if s['kind'] not in ('map', 'card') else s['dur'] * 1.2 for s, _ in fixed]
            tot = sum(weights); cur = t
            for (s, r), w in zip(fixed, weights):
                d = seg * w / tot
                tl.append({'type': 'shot', 'id': s['id'], 'chapter': ch, 'start': round(cur, 3), 'dur': round(d + XF, 3),
                           'src': r['src'], 'crop': r.get('crop'), 'move': r.get('move', s['move']),
                           'grade': r.get('grade', s['grade']), 'kind': s['kind'], 'title': r.get('title')})
                cur += d
            tl.append({'type': 'voice', 'start': round(t + LEAD, 3), 'wav': os.path.join(ROOT, para['wav']), 'chapter': ch})
            for sent in para['sentences']:
                caps.append((t + LEAD + sent['start'], t + LEAD + sent['end'], sent['text']))
            t += seg
        if ch.startswith('00'):
            tl.append({'type': 'title', 'start': t, 'dur': 7.0, 'chapter': ch}); t += 7.0
    json.dump({'duration': t, 'items': tl}, open(os.path.join(B, 'timeline.json'), 'w'), indent=1)
    with open(os.path.join(B, 'captions.srt'), 'w') as f:
        def ts(x): h, r = divmod(x, 3600); m, s = divmod(r, 60); return f'{int(h):02d}:{int(m):02d}:{s:06.3f}'.replace('.', ',')
        for i, (a, b, tx) in enumerate(caps, 1): f.write(f'{i}\n{ts(a)} --> {ts(b)}\n{tx}\n\n')
    print(f'timeline {t/60:.1f} min, {sum(1 for x in tl if x["type"]=="shot")} shots')

# ------------------------------------------------------------------ grading
GRADES = {  # (rgb gain, lift, gamma, saturation, contrast, strength)
    'gold':   ((1.06, 1.00, 0.88), 0.010, 1.00, 0.95, 1.04),
    'candle': ((1.08, 0.97, 0.82), 0.000, 1.06, 0.95, 1.08),
    'steel':  ((0.94, 0.99, 1.06), 0.015, 1.00, 0.68, 1.05),
    'night':  ((0.92, 0.97, 1.10), 0.000, 1.08, 0.85, 1.06),
    'dawn':   ((0.93, 0.98, 1.08), 0.020, 1.00, 0.75, 0.98),
    'ash':    ((1.02, 0.99, 0.94), 0.030, 1.00, 0.55, 0.94),
    'map':    ((1.00, 1.00, 1.00), 0.000, 1.00, 1.00, 1.00),
}
def grade(a, key):
    gain, lift, gamma, sat, con = GRADES.get(key, GRADES['gold'])
    a = a * np.array(gain, np.float32)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    a = lum[..., None] + (a - lum[..., None]) * sat
    a = (a - 0.5) * con + 0.5
    a = lift + (1 - lift) * np.clip(a, 0, 1)
    a = np.power(np.clip(a, 0, 1), gamma)
    # soft highlight roll-off
    return np.where(a > 0.8, 0.8 + (a - 0.8) * 0.75, a)

# ------------------------------------------------------------------ prep
_depth = None
def depth_of(img):
    global _depth
    if _depth is None:
        from transformers import pipeline
        _depth = pipeline('depth-estimation', model='/home/user/models/depth', device='cpu')
    d = np.array(_depth(Image.fromarray(img).resize((768, 432)))['depth'], np.float32)
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)
    return cv2.GaussianBlur(cv2.resize(d, (SW, SH)), (0, 0), 6)

def prep_one(it):
    key = it['id']; out = os.path.join(PREP, key + '.npz')
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(it['src']) and not it.get('force'): return
    im = Image.open(it['src']).convert('RGB'); w, h = im.size
    if it.get('crop'):
        x0, y0, x1, y1 = it['crop']; im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))); w, h = im.size
    # cover-fit to 16:9
    tr = 16 / 9
    if w / h > tr: nw = int(h * tr); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else: nh = int(w / tr); im = im.crop((0, (h - nh) // 3, w, (h - nh) // 3 + nh))
    im = im.resize((SW, SH), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255
    if it['kind'] != 'map': a = grade(a, it['grade'])
    a = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    d = depth_of(a) if it['kind'] not in ('map',) else np.full((SH, SW), 0.5, np.float32)
    np.savez_compressed(out, img=a, depth=d.astype(np.float16))

def prep(chs):
    os.makedirs(PREP, exist_ok=True)
    tl = load(os.path.join(B, 'timeline.json'))['items']
    seen = set()
    for it in tl:
        if it['type'] != 'shot' or it['id'] in seen: continue
        seen.add(it['id']); prep_one(it); print('prep', it['id'], flush=True)

# ------------------------------------------------------------------ motion
def ease(x): return x * x * (3 - 2 * x)

def camera(move, t, seed):
    """Returns zoom, centre offset (dx, dy) in canvas px, parallax (px, py)."""
    e = ease(t); r = np.random.default_rng(seed); side = 1 if r.random() < 0.5 else -1
    if move in ('push', 'slow push'): return 1.0 + 0.11 * e, (0, 0), (side * 14 * e, -6 * e)
    if move in ('pull', 'slow pull'): return 1.11 - 0.11 * e, (0, 0), (side * 14 * (1 - e), 6 * e)
    if move in ('pan', 'slow pan'): return 1.04, (side * (150 * e - 75), 0), (side * 10 * (e - 0.5), 0)
    if move == 'track': return 1.06, (side * (180 * e - 90), 0), (side * 26 * (e - 0.5), 0)
    if move in ('orbit', 'slow orbit'): return 1.05 + 0.03 * e, (side * (60 * e - 30), 0), (side * 44 * (e - 0.5), 4 * math.sin(e * math.pi))
    if move == 'crane-up': return 1.06, (0, 100 - 200 * e), (0, -24 * (e - 0.5))
    if move == 'crane-down': return 1.06, (0, -100 + 200 * e), (0, 24 * (e - 0.5))
    if move == 'handheld':
        f = t * 40
        return 1.07 + 0.02 * e, (5 * math.sin(f * 1.3) + 3 * math.sin(f * 2.9), 4 * math.sin(f * 1.7 + 1)), (side * 12 * (e - 0.5), 0)
    if move == 'drift': return 1.04 + 0.03 * e, (side * 30 * math.sin(e * math.pi - math.pi / 2), 15 * math.sin(e * math.pi * 2)), (side * 12 * (e - 0.5), 3)
    return 1.0 + 0.035 * e, (0, 0), (side * 8 * (e - 0.5), 0)   # static: barely breathing

_U, _V = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
def frame_of(img, dep, move, t, seed):
    z, (dx, dy), (px, py) = camera(move, t, seed)
    x0 = SW / 2 + dx + (_U - W / 2) / z
    y0 = SH / 2 + dy + (_V - H / 2) / z
    if px or py:
        d = cv2.remap(dep, x0, y0, cv2.INTER_LINEAR) - 0.5
        x0 = x0 + px * d; y0 = y0 + py * d
    return cv2.remap(img, x0, y0, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

# ------------------------------------------------------------------ cards
def font(n, s): return ImageFont.truetype(os.path.join(FONTS, n), s)
def card_img(l1, l2, big=False):
    im = Image.new('RGB', (W, H), (8, 7, 6)); d = ImageDraw.Draw(im)
    if big:
        d.text((W / 2, H / 2 - 20), l1, font=font('Cinzel.ttf', 118), fill=(222, 206, 172), anchor='mm')
        d.line([W / 2 - 260, H / 2 + 70, W / 2 + 260, H / 2 + 70], fill=(150, 116, 60), width=2)
        d.text((W / 2, H / 2 + 120), l2, font=font('CormorantGaramond-Italic.ttf', 46), fill=(180, 165, 140), anchor='mm')
    else:
        d.text((W / 2, H / 2 - 70), '   '.join(l1.replace('CHAPTER', 'CHAPTER ').split()), font=font('Cinzel.ttf', 34), fill=(170, 140, 90), anchor='mm')
        d.text((W / 2, H / 2 + 20), l2.title() if l2.isupper() else l2, font=font('CormorantGaramond.ttf', 96), fill=(226, 212, 182), anchor='mm')
    a = np.asarray(im, np.float32)
    yy, xx = np.mgrid[0:H, 0:W]; r = np.hypot((xx - W / 2) / W, (yy - H / 2) / H)
    a = a + (np.exp(-r * r * 9) * 16)[..., None] * np.array([1.0, 0.8, 0.55])
    return a.clip(0, 255).astype(np.uint8)

# ------------------------------------------------------------------ video
_grain = None
def finish(f, t, grade_key):
    global _grain
    if _grain is None:
        r = np.random.default_rng(3)
        _grain = [cv2.GaussianBlur(r.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7) for _ in range(6)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        rr = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
        finish.vig = (1 - 0.32 * np.clip(rr - 0.45, 0, 1) ** 1.6)[..., None].astype(np.float32)
    a = f.astype(np.float32)
    if grade_key in ('candle', 'night'):
        a *= 1 + 0.025 * math.sin(t * 7.1) * math.sin(t * 2.3 + 1)
    a = a * finish.vig
    g = _grain[int(t * FPS) % 6]
    a = a + g[..., None] * (5.5 if grade_key != 'map' else 2.5)
    return np.clip(a, 0, 255).astype(np.uint8)

def render_chapter(ch):
    data = load(os.path.join(B, 'timeline.json'))
    items = [x for x in data['items'] if x.get('chapter') == ch and x['type'] in ('shot', 'card', 'title')]
    t0 = min(x['start'] for x in items); t1 = max(x['start'] + x['dur'] for x in items)
    nxt = [x['start'] for x in data['items'] if x['type'] in ('shot', 'card') and x['start'] > t0 and x.get('chapter') != ch]
    t_end = min(nxt) if nxt else data['duration']
    cache = {}
    def get(it):
        if it['type'] in ('card', 'title'):
            k = 'card_' + ch + it['type']
            if k not in cache:
                cache[k] = card_img('THE LAST DAY OF ROME', 'The Fall of Constantinople, 1453', True) if it['type'] == 'title' else card_img(it['line1'], it['line2'])
            return cache[k]
        if it['id'] not in cache:
            z = np.load(os.path.join(PREP, it['id'] + '.npz'))
            cache[it['id']] = (z['img'], z['depth'].astype(np.float32))
        return cache[it['id']]
    os.makedirs(PARTS, exist_ok=True)
    out = os.path.join(PARTS, ch + '.mp4')
    n = int(round((t_end - t0) * FPS))
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
                          '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for k in range(n):
        t = t0 + k / FPS
        act = [x for x in items if x['start'] <= t < x['start'] + x['dur']]
        acc, gk = np.zeros((H, W, 3), np.float32), 'gold'
        for it in sorted(act, key=lambda x: x['start']):
            lt = (t - it['start']) / it['dur']
            if it['type'] == 'shot':
                a = min(1.0, (t - it['start']) / XF)
                if it['start'] + it['dur'] >= t_end - 0.05: a = min(a, (t_end - t) / 1.0)
                img, dep = get(it); fr = frame_of(img, dep, it['move'], lt, zlib.crc32(it['id'].encode())); gk = it['grade']
            else:
                a = min(1.0, (t - it['start']) / 0.9, (it['start'] + it['dur'] - t) / 0.9); fr = get(it); gk = 'map'
            a = max(0.0, a)
            acc = acc * (1 - a) + fr.astype(np.float32) * a
        p.stdin.write(finish(acc, t, gk).tobytes())
    p.stdin.close(); p.wait(); print('rendered', ch, f'{n/FPS:.1f}s', flush=True)
    return out

def video(chs):
    data = load(os.path.join(B, 'timeline.json'))
    order = sorted({x['chapter'] for x in data['items'] if 'chapter' in x})
    if chs: order = [c for c in order if c in chs]
    with ProcessPoolExecutor(max_workers=min(4, len(order))) as ex: list(ex.map(render_chapter, order))

# ------------------------------------------------------------------ audio
SR = 48000
def read_mono(path):
    import soundfile as sf
    from scipy.signal import resample_poly
    a, sr = sf.read(path, dtype='float32', always_2d=True); a = a.mean(1)
    if sr != SR: a = resample_poly(a, SR, sr).astype(np.float32)
    return a

def audio(chs):
    import soundfile as sf
    data = load(os.path.join(B, 'timeline.json')); D = data['duration']; n = int(D * SR) + SR
    voice = np.zeros(n, np.float32); music = np.zeros(n, np.float32); amb = np.zeros(n, np.float32)
    for it in data['items']:
        if it['type'] == 'voice':
            a = read_mono(it['wav']) * 0.9; i = int(it['start'] * SR); voice[i:i + len(a)] += a[:n - i]
    mp = load(os.path.join(ROOT, 'music.json'))
    for cue in mp['cues']:
        a = read_mono(os.path.join(B, 'music', cue['file']))
        s, e = int(cue['start'] * SR), int(min(cue['end'], D) * SR)
        if s >= n: continue
        seg = np.tile(a, int((e - s) / len(a)) + 1)[:e - s] * cue.get('gain', 1.0)
        f_in, f_out = int(cue.get('fade_in', 2) * SR), int(cue.get('fade_out', 3) * SR)
        seg[:f_in] *= np.linspace(0, 1, f_in); seg[-f_out:] *= np.linspace(1, 0, f_out)
        music[s:s + len(seg)] += seg
    for cue in mp.get('sfx', []):
        a = read_mono(os.path.join(B, 'sfx', cue['file'])); s = int(cue['start'] * SR)
        if cue.get('end'):
            e = int(min(cue['end'], D) * SR); a = np.tile(a, int((e - s) / len(a)) + 1)[:e - s]
            f = int(1.5 * SR); a[:f] *= np.linspace(0, 1, f); a[-f:] *= np.linspace(1, 0, f)
        amb[s:s + len(a)] += a[:n - s] * cue.get('gain', 0.3)
    # duck music under the voice (smoothed envelope)
    env = np.abs(voice); k = int(0.3 * SR)
    env = np.convolve(env, np.ones(k, np.float32) / k, mode='same')
    duck = 1 - 0.72 * np.clip(env / (env.max() * 0.08 + 1e-9), 0, 1)
    duck = np.convolve(duck, np.ones(SR // 2, np.float32) / (SR // 2), mode='same')
    mix = voice + music * duck * 0.55 + amb * (0.6 + 0.4 * duck)
    os.makedirs(os.path.join(B, 'audio'), exist_ok=True)
    raw = os.path.join(B, 'audio', 'raw.wav'); sf.write(raw, np.stack([mix, mix], 1), SR)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11',
                    '-ar', str(SR), os.path.join(B, 'audio', 'mix.wav')], check=True)
    print('audio done', f'{D/60:.1f} min')

def mux(name, chs):
    data = load(os.path.join(B, 'timeline.json'))
    order = sorted({x['chapter'] for x in data['items'] if 'chapter' in x})
    if chs: order = [c for c in order if c in chs]
    lst = os.path.join(B, 'parts', 'list.txt')
    open(lst, 'w').write(''.join(f"file '{os.path.join(PARTS, c + '.mp4')}'\n" for c in order))
    out = os.path.join(B, name + '.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-i', os.path.join(B, 'audio', 'mix.wav'),
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', out], check=True)
    print('wrote', out)

if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'plan': plan(args)
    elif cmd == 'prep': prep(args)
    elif cmd == 'video': video(args)
    elif cmd == 'audio': audio(args)
    elif cmd == 'mux': mux(args[0], args[1:])
