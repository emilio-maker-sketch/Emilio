"""The editor: turns narration + shot images into a finished, graded, moving picture.

  python3 tools/edit.py plan [chapters...]      # timeline.json + captions.srt
  python3 tools/edit.py prep [chapters...]      # crop, grade, depth map for every shot image
  python3 tools/edit.py video [chapters...]     # build/parts/<chapter>.mp4 (silent), chapters rendered in parallel
  python3 tools/edit.py audio [chapters...]     # build/audio/mix.wav (narration + music + ambience + effects, -14 LUFS)
  python3 tools/edit.py mux NAME                # build/NAME.mp4

Shot images are looked up in order: edit.json override -> build/gen/z_<id>.png -> build/photos/<id>.jpg
-> build/maps/<id>.png -> a reframed copy of another image in the same paragraph.
If build/clips/<id>.mp4 exists (AI video), it plays instead of the still.

Editing features:
  - depth-parallax camera moves on every still (Depth Anything V2)
  - AI video clips, slowed with frame blending to fit the shot
  - quote cards: text over a blurred, darkened plate of the scene, with source line
  - lower-third name titles from {LT: name | role} in the shot description
  - animated maps: campaign routes draw themselves on (build/maps/<id>.routes.json)
  - light-leak transitions into chapter cards, letterbox bars for the climax chapters
  - floating dust in lamplit and sunlit scenes, film grain, vignette, candle flicker
"""
import os, sys, re, json, glob, math, zlib, subprocess
from concurrent.futures import ProcessPoolExecutor
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build'); PREP = os.path.join(B, 'prep'); PARTS = os.path.join(B, 'parts')
FONTS = os.path.join(ROOT, '..', 'assets', 'fonts')
FPS, W, H = 30, 1920, 1080
SW, SH = 2304, 1296                    # working canvas (1.2x) so moves never reveal edges
LEAD, GAP, XF = 0.7, 1.6, 0.6          # narration lead-in, gap after paragraph, shot dissolve
CH_LEAD = 4.5                          # music-only opening at the start of each chapter
CARD = 6.5
TITLE = ('THE IDES OF MARCH', 'The Assassination of Julius Caesar, 44 BC')
LETTERBOX = ('10_the_morning', '11_the_murder')
WORDS = 'ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE THIRTEEN FOURTEEN FIFTEEN SIXTEEN'.split()

SMALL = {'a', 'an', 'and', 'of', 'the', 'over', 'in', 'on', 'to', 'at', 'for'}
def nice_title(t):
    w = t.lower().split()
    cap = lambda x: '-'.join(p[:1].upper() + p[1:] for p in x.split('-'))
    return ' '.join(x if (i and x in SMALL) else cap(x) for i, x in enumerate(w))

def load(p): return json.load(open(p))
def edits():
    p = os.path.join(ROOT, 'edit.json')
    return load(p) if os.path.exists(p) else {}

LT_RE = re.compile(r'\{LT:\s*([^|}]+)\|\s*([^}]+)\}')
QREF = re.compile(r'\s*\[q:[^\]]*\]')

# ------------------------------------------------------------------ plan
def resolve(shot, ed):
    o = ed.get(shot['id'], {})
    if o.get('skip'): return None
    if shot['kind'] == 'quote': return 'quote'
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
    tl, caps, t, last_real = [], [], 0.0, None
    for ch in order:
        n = narr[ch]; title = n['title']
        if not ch.startswith('00'):
            num, name = title.split(':', 1)
            tl.append({'type': 'card', 'start': t, 'dur': CARD, 'line1': num.strip(), 'line2': name.strip(), 'chapter': ch})
            t += CARD - 0.3
        for pi, para in enumerate(n['paras']):
            ps = [s for s in shots if s['chapter'] == ch and s['para'] == pi]
            lead = CH_LEAD if pi == 0 and not ch.startswith('00') else LEAD
            seg = lead + para['dur'] + GAP
            items = [(s, r) for s in ps for r in [resolve(s, ed)] if r is not None]
            real = [x for x in items if isinstance(x[1], dict)]
            if not real and last_real: real = [last_real]; print(f'  {ch} para {pi}: borrowing previous image')
            if not real: raise SystemExit(f'{ch} para {pi}: no images yet')
            last_real = real[-1]
            fixed = []
            for k, (s, r) in enumerate(items):
                if r == 'fallback':
                    base = real[k % len(real)][1]
                    r = dict(base, crop=base.get('alt_crop', [[0.18, 0.1, 0.84, 0.52], [0.1, 0.38, 0.62, 0.95], [0.4, 0.3, 0.95, 0.85]][k % 3]),
                             fallback=True, move=['slow push', 'pan', 'drift'][k % 3])
                elif r == 'quote':
                    m = re.match(r'\s*(.*?)\s*~\s*(.*)$', s['desc'])
                    base = real[0][1]
                    r = dict(src=base['src'], crop=base.get('crop'), quote=m.group(1), attrib=m.group(2))
                fixed.append((s, r))
            weights = [s['dur'] * (1.25 if s['kind'] in ('map', 'card', 'quote') else 1.0) for s, _ in fixed]
            tot = sum(weights); cur = t
            for (s, r), w in zip(fixed, weights):
                d = seg * w / tot
                it = {'type': 'shot', 'id': s['id'], 'chapter': ch, 'start': round(cur, 3), 'dur': round(d + XF, 3),
                      'src': r['src'], 'crop': r.get('crop'), 'move': r.get('move', s['move']),
                      'grade': r.get('grade', s['grade']), 'kind': s['kind'], 'title': r.get('title')}
                if r.get('quote'): it.update(quote=r['quote'], attrib=r['attrib'], move='static')
                clip = os.path.join(B, 'clips', s['id'] + '.mp4')
                if os.path.exists(clip) and not r.get('fallback'): it['clip'] = clip
                lt = LT_RE.search(s['desc'])
                if lt and not r.get('fallback'): it['lt'] = [lt.group(1).strip(), lt.group(2).strip()]
                tl.append(it); cur += d
            tl.append({'type': 'voice', 'start': round(t + lead, 3), 'wav': os.path.join(ROOT, para['wav']), 'chapter': ch})
            for sent in para['sentences']:
                caps.append((t + lead + sent['start'], t + lead + sent['end'], sent['text']))
            t += seg
        if ch.startswith('00'):
            tl.append({'type': 'title', 'start': t, 'dur': 7.0, 'chapter': ch}); t += 7.0
    json.dump({'duration': t, 'items': tl}, open(os.path.join(B, 'timeline.json'), 'w'), indent=1)
    with open(os.path.join(B, 'captions.srt'), 'w') as f:
        def ts(x): h, r = divmod(x, 3600); m, s = divmod(r, 60); return f'{int(h):02d}:{int(m):02d}:{s:06.3f}'.replace('.', ',')
        for i, (a, b, tx) in enumerate(caps, 1): f.write(f'{i}\n{ts(a)} --> {ts(b)}\n{tx}\n\n')
    print(f'timeline {t/60:.1f} min, {sum(1 for x in tl if x["type"]=="shot")} shots')

# ------------------------------------------------------------------ grading
GRADES = {  # (rgb gain, lift, gamma, saturation, contrast)
    'gold':    ((1.035, 1.00, 0.94), 0.008, 1.00, 1.00, 1.04),
    'candle':  ((1.08, 0.97, 0.82), 0.000, 1.06, 0.95, 1.08),
    'steel':   ((0.94, 0.99, 1.06), 0.015, 1.00, 0.68, 1.05),
    'night':   ((0.92, 0.97, 1.10), 0.000, 1.08, 0.85, 1.06),
    'dawn':    ((0.93, 0.98, 1.08), 0.020, 1.00, 0.75, 0.98),
    'ash':     ((1.02, 0.99, 0.94), 0.030, 1.00, 0.55, 0.94),
    'neutral': ((1.02, 1.00, 0.97), 0.012, 1.00, 0.92, 1.03),
    'map':     ((1.00, 1.00, 1.00), 0.000, 1.00, 1.00, 1.00),
}
def grade(a, key):
    gain, lift, gamma, sat, con = GRADES.get(key, GRADES['gold'])
    a = a * np.array(gain, np.float32)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    a = lum[..., None] + (a - lum[..., None]) * sat
    a = (a - 0.5) * con + 0.5
    a = lift + (1 - lift) * np.clip(a, 0, 1)
    a = np.power(np.clip(a, 0, 1), gamma)
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

def cover(im, w, h):
    iw, ih = im.size; tr = w / h
    if iw / ih > tr: nw = int(ih * tr); im = im.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
    else: nh = int(iw / tr); im = im.crop((0, (ih - nh) // 3, iw, (ih - nh) // 3 + nh))
    return im.resize((w, h), Image.LANCZOS)

def prep_one(it):
    key = it['id']; out = os.path.join(PREP, key + '.npz')
    sig = json.dumps([it['src'], it.get('crop'), it['grade'], bool(it.get('quote'))])
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(it['src']):
        try:
            if str(np.load(out)['sig']) == sig: return
        except Exception: pass
    im = Image.open(it['src']).convert('RGB'); w, h = im.size
    if it.get('crop'):
        x0, y0, x1, y1 = it['crop']; im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    im = cover(im, SW, SH)
    a = np.asarray(im, np.float32) / 255
    if it['kind'] != 'map': a = grade(a, it['grade'])
    a = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    if it.get('quote'):
        a = (cv2.GaussianBlur(a, (0, 0), 18).astype(np.float32) * 0.30).astype(np.uint8); d = np.full((SH, SW), 0.5, np.float32)
    elif it['kind'] == 'map': d = np.full((SH, SW), 0.5, np.float32)
    else: d = depth_of(a)
    np.savez_compressed(out, img=a, depth=d.astype(np.float16), sig=sig)

def prep(chs):
    os.makedirs(PREP, exist_ok=True)
    tl = load(os.path.join(B, 'timeline.json'))['items']
    seen = set()
    for it in tl:
        if it['type'] != 'shot' or it['id'] in seen: continue
        if chs and it['chapter'] not in chs: continue
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
    if dep is not None and (px or py):
        d = cv2.remap(dep, x0, y0, cv2.INTER_LINEAR) - 0.5
        x0 = x0 + px * d; y0 = y0 + py * d
    return cv2.remap(img, x0, y0, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

# ------------------------------------------------------------------ clips (AI video)
def load_clip(path, grade_key):
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height',
                        '-of', 'csv=p=0', path], capture_output=True, text=True, check=True)
    w, h = map(int, p.stdout.strip().split(','))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    out = []
    for f in fr:
        a = np.asarray(cover(Image.fromarray(f), 1152, 648), np.float32) / 255
        out.append((np.clip(grade(a, grade_key), 0, 1) * 255).astype(np.uint8))
    return out

def clip_frame(frames, lt, dur):
    """Play the clip slowed to fill the shot (never faster than real time), blending neighbouring frames."""
    n = len(frames); speed = min(1.0, (n / 24) / max(dur, 0.1))
    pos = min(lt * dur * 24 * speed, n - 1.001)
    i = int(pos); f = pos - i
    a = frames[i].astype(np.float32) * (1 - f) + frames[min(i + 1, n - 1)].astype(np.float32) * f
    up = cv2.resize(a, (SW, SH), interpolation=cv2.INTER_CUBIC)
    blur = cv2.GaussianBlur(up, (0, 0), 1.4)
    return np.clip(up * 1.45 - blur * 0.45, 0, 255).astype(np.uint8)   # unsharp mask after upscaling

# ------------------------------------------------------------------ type
def font(n, s): return ImageFont.truetype(os.path.join(FONTS, n), s)
def card_img(l1, l2, big=False):
    im = Image.new('RGB', (W, H), (8, 7, 6)); d = ImageDraw.Draw(im)
    if big:
        d.text((W / 2, H / 2 - 20), l1, font=font('Cinzel.ttf', 118), fill=(222, 206, 172), anchor='mm')
        d.line([W / 2 - 260, H / 2 + 70, W / 2 + 260, H / 2 + 70], fill=(150, 116, 60), width=2)
        d.text((W / 2, H / 2 + 120), l2, font=font('CormorantGaramond-Italic.ttf', 46), fill=(180, 165, 140), anchor='mm')
    else:
        d.text((W / 2, H / 2 - 70), '   '.join(l1.replace('CHAPTER', 'CHAPTER ').split()), font=font('Cinzel.ttf', 34), fill=(170, 140, 90), anchor='mm')
        d.text((W / 2, H / 2 + 20), nice_title(l2), font=font('CormorantGaramond.ttf', 96), fill=(226, 212, 182), anchor='mm')
    a = np.asarray(im, np.float32)
    yy, xx = np.mgrid[0:H, 0:W]; r = np.hypot((xx - W / 2) / W, (yy - H / 2) / H)
    a = a + (np.exp(-r * r * 9) * 16)[..., None] * np.array([1.0, 0.8, 0.55])
    return a.clip(0, 255).astype(np.uint8)

def wrap(text, fo, maxw, d):
    words, lines, cur = text.split(), [], ''
    for w_ in words:
        t = (cur + ' ' + w_).strip()
        if d.textlength(t, font=fo) > maxw and cur: lines.append(cur); cur = w_
        else: cur = t
    return lines + [cur]

def quote_layer(text, attrib):
    """RGBA text layer for a quote card."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    fo = font('CormorantGaramond-Italic.ttf', 74 if len(text) < 90 else 62)
    lines = wrap(text, fo, 1350, d); lh = fo.size * 1.22
    y0 = H / 2 - (len(lines) * lh) / 2 - 40
    d.text((W / 2, y0 - 70), '“', font=font('CormorantGaramond.ttf', 150), fill=(176, 132, 52, 200), anchor='mm')
    for i, ln in enumerate(lines):
        d.text((W / 2, y0 + i * lh + lh / 2), ln.replace('"', ''), font=fo, fill=(236, 224, 198, 255), anchor='mm')
    ya = y0 + len(lines) * lh + 60
    d.line([W / 2 - 60, ya, W / 2 + 60, ya], fill=(176, 132, 52, 230), width=2)
    d.text((W / 2, ya + 48), attrib.upper(), font=font('Cinzel.ttf', 26), fill=(190, 170, 130, 235), anchor='mm')
    return np.asarray(im, np.float32)

def lt_layer(name, role):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x, y = 130, H - 205
    g = Image.new('L', (W, H), 0); ImageDraw.Draw(g).rectangle([0, y - 40, 1000, H], fill=150)
    g = g.filter(ImageFilter.GaussianBlur(60))
    shade = np.zeros((H, W, 4), np.float32); shade[..., 3] = np.asarray(g, np.float32)
    d.text((x, y), name.upper(), font=font('Cinzel.ttf', 40), fill=(236, 224, 198, 255), anchor='ls')
    d.line([x, y + 18, x + 90, y + 18], fill=(176, 132, 52, 255), width=3)
    d.text((x, y + 66), role, font=font('CormorantGaramond-Italic.ttf', 38), fill=(205, 190, 160, 255), anchor='ls')
    t = np.asarray(im, np.float32)
    a = t[..., 3:4] / 255; out = shade.copy()
    out[..., :3] = t[..., :3]; out[..., 3] = np.maximum(shade[..., 3] * 0.55, t[..., 3])
    return out

def over(base, layer, alpha):
    a = layer[..., 3:4] / 255 * alpha
    return base * (1 - a) + layer[..., :3] * a

# ------------------------------------------------------------------ atmosphere
class Dust:
    def __init__(self, seed, n=55):
        r = np.random.default_rng(seed)
        self.p = r.uniform(0, 1, (n, 2)) * [W, H]; self.v = r.normal(0, 1, (n, 2)) * [6, 4] + [3, -2]
        self.s = r.uniform(1.2, 3.5, n); self.b = r.uniform(0.3, 1.0, n); self.ph = r.uniform(0, 6.3, n)
    def draw(self, a, t, strength):
        for (x, y), (vx, vy), s, b, ph in zip(self.p, self.v, self.s, self.b, self.ph):
            cx = (x + vx * t + 14 * math.sin(t * 0.4 + ph)) % W; cy = (y + vy * t + 10 * math.cos(t * 0.33 + ph)) % H
            R = int(s * 3); x0, y0 = int(cx) - R, int(cy) - R
            if x0 < 0 or y0 < 0 or x0 + 2 * R + 1 > W or y0 + 2 * R + 1 > H: continue
            yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
            spr = np.exp(-(xx * xx + yy * yy) / (2 * s * s)) * b * strength * (0.6 + 0.4 * math.sin(t * 1.7 + ph))
            a[y0:y0 + 2 * R + 1, x0:x0 + 2 * R + 1] += spr[..., None] * np.array([255, 236, 200], np.float32)
        return a

def leak(a, p):
    """Warm light leak sweeping across the frame, p in [0, 1]."""
    cx = -0.3 * W + 1.6 * W * p; g = np.exp(-((_U - cx) / (W * 0.28)) ** 2 - ((_V - H * 0.35) / (H * 0.9)) ** 2)
    k = math.sin(math.pi * p) * 150
    return a + (g * k)[..., None] * np.array([1.0, 0.62, 0.30], np.float32)

_grain = None
def finish(f, t, grade_key, lb=0.0):
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
    if lb > 0:
        bar = int(138 * lb); a[:bar] = 0; a[H - bar:] = 0
    return np.clip(a, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ video
def map_routes(it):
    p = os.path.join(B, 'maps', it['id'] + '.routes.json')
    return load(p) if os.path.exists(p) else None

def draw_routes(img, routes, prog):
    """Draw campaign routes (normalised polylines) up to prog in [0,1], one route after another."""
    out = img.copy(); n = len(routes)
    for k, r in enumerate(routes):
        p = min(1.0, max(0.0, prog * n - k))
        if p <= 0: break
        pts = np.array(r['pts'], np.float32) * [SW, SH]
        seg = np.hypot(*np.diff(pts, axis=0).T); L = seg.sum(); want = L * p; acc = 0; poly = [pts[0]]
        for i, s in enumerate(seg):
            if acc + s >= want: poly.append(pts[i] + (pts[i + 1] - pts[i]) * ((want - acc) / max(s, 1e-6))); break
            acc += s; poly.append(pts[i + 1])
        poly = np.array(poly, np.int32); col = tuple(int(c) for c in r.get('col', (150, 46, 38)))
        cv2.polylines(out, [poly], False, (40, 28, 18), 13, cv2.LINE_AA)
        cv2.polylines(out, [poly], False, col, 8, cv2.LINE_AA)
        (x1, y1) = poly[-1]; (x0, y0) = poly[-2] if len(poly) > 1 else poly[-1]
        ang = math.atan2(y1 - y0, x1 - x0); Lh = 34
        tri = np.array([(x1 + 10 * math.cos(ang), y1 + 10 * math.sin(ang)), (x1 - Lh * math.cos(ang - 0.5), y1 - Lh * math.sin(ang - 0.5)),
                        (x1 - Lh * math.cos(ang + 0.5), y1 - Lh * math.sin(ang + 0.5))], np.int32)
        cv2.fillPoly(out, [tri], col, cv2.LINE_AA)
    return out

def render_chapter(ch, only=None):
    data = load(os.path.join(B, 'timeline.json'))
    items = [x for x in data['items'] if x.get('chapter') == ch and x['type'] in ('shot', 'card', 'title')]
    t0 = min(x['start'] for x in items); t1 = max(x['start'] + x['dur'] for x in items)
    nxt = [x['start'] for x in data['items'] if x['type'] in ('shot', 'card') and x['start'] > t0 and x.get('chapter') != ch]
    t_end = min(nxt) if nxt else data['duration']
    cache = {}; dust = Dust(zlib.crc32(ch.encode()))
    card_it = next((x for x in items if x['type'] == 'card'), None)
    def get(it):
        if it['type'] in ('card', 'title'):
            k = 'card_' + it['type']
            if k not in cache: cache[k] = card_img(*TITLE, True) if it['type'] == 'title' else card_img(it['line1'], it['line2'])
            return cache[k]
        if it['id'] not in cache:
            z = np.load(os.path.join(PREP, it['id'] + '.npz'))
            dep = z['depth'].astype(np.float32) if it['kind'] not in ('map',) and not it.get('quote') else None
            clip = load_clip(it['clip'], it['grade']) if it.get('clip') else None
            cache[it['id']] = (z['img'], dep, clip, map_routes(it) if it['kind'] == 'map' else None,
                               quote_layer(it['quote'], it['attrib']) if it.get('quote') else None,
                               lt_layer(*it['lt']) if it.get('lt') else None)
        return cache[it['id']]
    os.makedirs(PARTS, exist_ok=True)
    out = os.path.join(PARTS, ch + '.mp4')
    n = int(round((t_end - t0) * FPS))
    p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                          '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17',
                          '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    ks = range(n) if only is None else [int(round((x - t0) * FPS)) for x in only]
    if only is not None: p.stdin.close(); p.wait(); p = None
    for k in ks:
        t = t0 + k / FPS
        act = [x for x in items if x['start'] <= t < x['start'] + x['dur']]
        acc, gk = np.zeros((H, W, 3), np.float32), 'gold'
        for it in sorted(act, key=lambda x: x['start']):
            lt = (t - it['start']) / it['dur']
            if it['type'] == 'shot':
                a = min(1.0, (t - it['start']) / XF)
                if it['start'] + it['dur'] >= t_end - 0.05: a = min(a, (t_end - t) / 1.0)
                img, dep, clip, routes, ql, ltl = get(it); seed = zlib.crc32(it['id'].encode())
                if clip is not None: src, dep = clip_frame(clip, lt, it['dur']), None
                elif routes: src = draw_routes(img, routes, min(1.0, max(0.0, (lt - 0.12) / 0.62)))
                else: src = img
                fr = frame_of(src, dep, it['move'], lt, seed).astype(np.float32); gk = it['grade']
                if ql is not None:
                    qa = min(1.0, max(0.0, (t - it['start'] - 0.5) / 1.1)) * min(1.0, max(0.0, (it['start'] + it['dur'] - XF - t) / 0.6))
                    fr = over(fr, ql, qa)
                if ltl is not None:
                    la = min(1.0, max(0.0, (t - it['start'] - 1.0) / 0.6)) * min(1.0, max(0.0, (it['start'] + 6.5 - t) / 0.6))
                    if la > 0: fr = over(fr, ltl, la)
            else:
                a = min(1.0, (t - it['start']) / 0.9, (it['start'] + it['dur'] - t) / 0.9); fr = get(it).astype(np.float32); gk = 'map'
            a = max(0.0, a)
            acc = acc * (1 - a) + fr * a
        if gk in ('candle', 'gold') and not any(x.get('quote') for x in act): acc = dust.draw(acc, t, 0.55 if gk == 'candle' else 0.35)
        if card_it and card_it['start'] <= t < card_it['start'] + 1.6: acc = leak(acc, (t - card_it['start']) / 1.6)
        lb = min(1.0, max(0.0, (t - t0 - CARD + 1.0) / 2.0)) if ch in LETTERBOX else 0.0
        fin = finish(acc, t, gk, lb)
        if p is None: Image.fromarray(fin).save(os.path.join(B, f'test_{ch}_{t:.1f}.jpg'), quality=88); continue
        p.stdin.write(fin.tobytes())
    if p is None: return
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
    voice = np.zeros(n, np.float32); music = np.zeros(n, np.float32); amb = np.zeros(n, np.float32); fx = np.zeros(n, np.float32)
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
        if s >= n: continue
        if cue.get('end'):
            e = int(min(cue['end'], D) * SR); a = np.tile(a, int((e - s) / len(a)) + 1)[:e - s]
            f = min(int(1.5 * SR), len(a) // 2); a[:f] *= np.linspace(0, 1, f); a[-f:] *= np.linspace(1, 0, f)
        (fx if cue.get('hit') else amb)[s:s + len(a)] += a[:n - s] * cue.get('gain', 0.3)
    env = np.abs(voice); k = int(0.3 * SR)
    env = np.convolve(env, np.ones(k, np.float32) / k, mode='same')
    duck = 1 - 0.72 * np.clip(env / (env.max() * 0.08 + 1e-9), 0, 1)
    duck = np.convolve(duck, np.ones(SR // 2, np.float32) / (SR // 2), mode='same')
    mix = voice + music * duck * 0.55 + amb * (0.6 + 0.4 * duck) + fx * (0.75 + 0.25 * duck)
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
    audio_in = ['-i', os.path.join(B, 'audio', 'mix.wav')]
    if chs:  # preview: cut the matching stretch of the full mix
        t0 = min(x['start'] for x in data['items'] if x.get('chapter') in chs)
        audio_in = ['-ss', str(t0), '-i', os.path.join(B, 'audio', 'mix.wav')]
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, *audio_in,
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', out], check=True)
    print('wrote', out)

if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'plan': plan(args)
    elif cmd == 'prep': prep(args)
    elif cmd == 'video': video(args)
    elif cmd == 'audio': audio(args)
    elif cmd == 'mux': mux(args[0], args[1:])
    elif cmd == 'frames': render_chapter(args[0], [float(x) for x in args[1:]])
