"""Render one chapter of the Pompeii episode.
Usage: python3 render.py <chapter_prefix e.g. 03> [--preview SECONDS]
Reads script/<ch>*.md, build/vo/manifest.json, build/img/library.json (curated), renders maps on demand,
writes build/chapters/<ch>.mp4 (1080p, letterboxed, graded, with mixed + loudness-normalised audio).
Style: Miyako sample — dark grade, 2.39:1 bars, slow push-ins, hard cuts inside a paragraph (~2.5-5 s shots),
short dissolves between paragraphs, dips to black around chapter cards, small date captions, quote cards.
"""
import json, math, os, random, re, subprocess, sys, glob, time
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score, maps as mapmod, visuals

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, 'build')
W, H, FPS = 1920, 1080, 30
TOP, BOT = 138, 942                         # letterbox safe area
SERIF = '/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf'; SERIF_I = '/usr/share/fonts/truetype/crosextra/Caladea-Italic.ttf'
SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
GAP, MOOD_GAP, XF = 0.75, 1.5, 0.5          # pause after paragraph, extra on mood change, paragraph dissolve
CARD_DUR, END_CARD_DUR, DIP = 5.0, 9.0, 0.8

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)

# ---------------------------------------------------------------- script parsing
def parse(path):
    blocks, cur = [], {}
    for line in open(path, encoding='utf-8'):
        s = line.strip()
        if not s or s.startswith('# '): continue
        m = re.match(r'^\[(\w+):\s*(.*)\]$', s)
        if m:
            k, v = m.group(1), m.group(2)
            if k == 'card': blocks.append({'card': [x.strip() for x in v.split('|')]})
            else: cur[k] = v
            continue
        cur['text'] = s; blocks.append(cur); cur = {}
    return blocks

# ---------------------------------------------------------------- image library
class Library:
    def __init__(self):
        lib = json.load(open(os.path.join(B, 'img', 'library.json')))
        self.qmap = lib['queries']            # script query -> [themes]
        self.themes = lib['themes']           # theme -> [files]
        self.meta = lib.get('meta', {})
        self.use = {}; self.recent = []; self.cache = {}
        for k, ids in visuals.AIT.items():
            self.themes[k] = [f'../ai/ai_{i:02d}.png' for i in ids if os.path.exists(os.path.join(B, 'img', 'ai', f'ai_{i:02d}.png'))]
    def candidates(self, queries):
        files = []
        for q in queries:
            for th in self.qmap.get(q, ['RUINS']):
                files += [f for f in self.themes.get(th, []) if f not in files]
        return files or self.themes['RUINS']
    def pick_themes(self, themes, rnd):
        c = [f for th in themes for f in self.themes.get(th, [])]
        fresh = [f for f in c if f not in self.recent[-14:]] or c
        if not fresh: return None
        rnd.shuffle(fresh); f = min(fresh, key=lambda f: self.use.get(f, 0))
        self.use[f] = self.use.get(f, 0) + 1; self.recent.append(f); return f
    def pick(self, queries, rnd, primary=False):
        c = self.candidates(queries)
        if primary:
            th = self.qmap.get(queries[0], ['RUINS'])[0]
            first = [f for f in self.themes.get(th, []) if f not in self.recent[-14:]]
            if first: c = first
        fresh = [f for f in c if f not in self.recent[-14:]] or c
        rnd.shuffle(fresh)
        f = min(fresh, key=lambda f: self.use.get(f, 0))
        self.use[f] = self.use.get(f, 0) + 1; self.recent.append(f); return f
    def image(self, f):
        if f in self.cache: return self.cache[f]
        if len(self.cache) > 40: self.cache.pop(next(iter(self.cache)))
        im = cv2.imread(os.path.join(B, 'img', 'pool', f)); im = autocrop(im)
        h, w = im.shape[:2]; s = min(1.0, 3000 / max(w, h))
        if s < 1: im = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        im = grade(im)
        h, w = im.shape[:2]
        if w / h < 1.45 or w < 1500:       # portrait / small: compose onto a blurred 16:9 canvas
            cw, ch = 2400, 1350
            bg = cv2.resize(im, (cw, int(cw * h / w)) if w / h < cw / ch else (int(ch * w / h), ch))
            y0 = (bg.shape[0] - ch) // 2; x0 = (bg.shape[1] - cw) // 2; bg = bg[max(0, y0):max(0, y0) + ch, max(0, x0):max(0, x0) + cw]
            bg = cv2.resize(bg, (cw, ch)); bg = (cv2.GaussianBlur(bg, (0, 0), 30) * 0.35).astype(np.uint8)
            fh = int(ch * 0.86); fw = int(w * fh / h)
            if fw > cw * 0.9: fw = int(cw * 0.9); fh = int(h * fw / w)
            fg = cv2.resize(im, (fw, fh), interpolation=cv2.INTER_AREA)
            y, x = (ch - fh) // 2, (cw - fw) // 2; bg[y:y + fh, x:x + fw] = fg; im = bg; fit = True
        else: fit = False
        self.cache[f] = (im, fit); return im, fit

def autocrop(im):
    """Trim plain paper / mount margins (prints, drawings, photos on card)."""
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32); h, w = g.shape
    def plain(strip): return strip.std() < 14 and strip.mean() > 120
    t = b = l = r = 0; step_h, step_w = max(2, h // 100), max(2, w // 100)
    while t < h * 0.2 and plain(g[t:t + step_h, :]): t += step_h
    while b < h * 0.2 and plain(g[h - b - step_h:h - b, :]): b += step_h
    while l < w * 0.2 and plain(g[:, l:l + step_w]): l += step_w
    while r < w * 0.2 and plain(g[:, w - r - step_w:w - r]): r += step_w
    if t or b or l or r:
        pad_h, pad_w = int(h * 0.01), int(w * 0.01)
        im = im[t + pad_h if t else 0:h - b - pad_h if b else h, l + pad_w if l else 0:w - r - pad_w if r else w]
    return im

yy, xx = np.mgrid[0:H, 0:W]
VIG = (1 - 0.40 * np.clip(np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) - 0.35, 0, 1) ** 1.6).astype(np.float32)[..., None]

def grade(img):
    f = img.astype(np.float32) / 255
    g = f.mean(2, keepdims=True); f = g + (f - g) * 0.78
    f = np.clip((f - 0.5) * 1.10 + 0.47, 0, 1) ** 1.05
    lum = f.mean(2, keepdims=True); f[..., 0:1] += 0.025 * (1 - lum); f[..., 2:3] += 0.025 * lum
    return np.clip(f * 255, 0, 255).astype(np.uint8)

# ---------------------------------------------------------------- shots
class StillShot:
    def __init__(self, lib, f, dur, rnd, shake=False):
        self.im, fit = lib.image(f); self.dur = dur; self.f = f; self.shake = shake
        h, w = self.im.shape[:2]
        # base crop: largest 16:9 window; optionally a closer "detail" window on big images
        bw = min(w, h * 16 / 9); bh = bw * 9 / 16
        detail = (not fit) and w >= 2200 and rnd.random() < 0.45
        sc = rnd.uniform(0.55, 0.75) if detail else rnd.uniform(0.88, 0.97)
        cw, chh = bw * sc, bh * sc
        cx = rnd.uniform(cw / 2, w - cw / 2); cy = rnd.uniform(chh / 2, h - chh / 2)
        if fit: cx, cy = w / 2, h / 2
        z0, z1 = (1.0, rnd.uniform(1.07, 1.13)) if rnd.random() < 0.7 else (rnd.uniform(1.07, 1.12), 1.0)
        pan = rnd.uniform(-0.035, 0.035) * cw if not fit else 0
        self.a = (cx - pan, cy, cw / z0); self.b = (cx + pan, cy, cw / z1)
    def frame(self, t):
        u = t / max(self.dur, 1e-3)
        cx = self.a[0] + (self.b[0] - self.a[0]) * u; cy = self.a[1] + (self.b[1] - self.a[1]) * u
        cw = self.a[2] * (self.b[2] / self.a[2]) ** u; s = W / cw
        if self.shake and t < 2.5:
            amp = 9 * (1 - t / 2.5) / s; cx += amp * math.sin(t * 57); cy += amp * math.cos(t * 43)
        M = np.float32([[s, 0, W / 2 - cx * s], [0, s, H / 2 - cy * s]])
        return cv2.warpAffine(self.im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

class VideoShot:
    def __init__(self, path, dur):
        self.dur = dur
        self.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
        self.last = np.zeros((H, W, 3), np.uint8); self.n = 0
    def frame(self, t):
        want = int(t * FPS + 0.5)
        while self.n <= want:
            buf = self.p.stdout.read(W * H * 3)
            if len(buf) < W * H * 3: break
            self.last = np.frombuffer(buf, np.uint8).reshape(H, W, 3); self.n += 1
        return self.last
    def close(self):
        try: self.p.stdout.close(); self.p.kill()
        except Exception: pass


def _noise(h, w, seed, octaves=((64, 0.55), (24, 0.3), (8, 0.15)), blur=6):
    r = np.random.default_rng(seed); acc = np.zeros((h, w), np.float32)
    for sc, wt in octaves:
        n = r.random((h // sc + 2, w // sc + 2)).astype(np.float32)
        acc += cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC) * wt
    acc = cv2.GaussianBlur(acc, (0, 0), blur); acc -= acc.min(); acc /= acc.max(); return acc
NOISE = None
NOISE_L = None

class FxShot:
    """Procedural ash / pumice / pyroclastic-surge / darkness over a darkened painting or ruin."""
    BG = {'ash': ['ERUPT', 'RUINS', 'VESUV', 'BRULLOV'], 'pumice': ['RUINS'], 'flow': ['ERUPT', 'RUINS', 'BRULLOV'], 'dark': ['CASTS', 'RUINS']}
    def __init__(self, lib, kind, dur, rnd):
        global NOISE, NOISE_L
        if NOISE is None: NOISE = (_noise(H + 400, W * 2, 1), _noise(H + 400, W * 2, 2))
        if kind == 'flow' and NOISE_L is None: NOISE_L = tuple(_noise(H + 400, W * 2, s, ((220, 0.65), (90, 0.35)), 24) for s in (5, 6))
        self.kind, self.dur, self.rnd = kind, dur, rnd
        pool = [f for th in self.BG[kind] for f in lib.themes.get(th, []) if not f.startswith('fx:')]
        self.bg = StillShot(lib, rnd.choice(pool), dur, rnd)
        self.dim = {'ash': 0.5, 'pumice': 0.55, 'flow': 0.42, 'dark': 0.22}[kind]
        n = {'ash': 500, 'pumice': 260, 'flow': 160, 'dark': 120}[kind]
        r = np.random.default_rng(rnd.randrange(1 << 30))
        self.p = np.stack([r.uniform(0, W, n), r.uniform(-H, H, n)], 1).astype(np.float32)
        self.v = {'ash': (r.uniform(10, 45, n), r.uniform(25, 70, n)), 'pumice': (r.uniform(-15, 15, n), r.uniform(260, 520, n)),
                  'flow': (r.uniform(30, 120, n), r.uniform(-70, -20, n)), 'dark': (r.uniform(-8, 8, n), r.uniform(-25, -5, n))}[kind]
        self.sz = r.uniform(1, 3.2, n) if kind != 'pumice' else r.uniform(2, 5.5, n)
        self.ph = r.uniform(0, 6.28, n); self.dir = 1 if rnd.random() < 0.5 else -1
    def frame(self, t):
        fr = self.bg.frame(t).astype(np.float32) * self.dim
        g = fr.mean(2, keepdims=True); fr = g + (fr - g) * 0.6
        n1, n2 = NOISE; h2, w2 = H // 2, W // 2
        if self.kind == 'flow':
            l1, l2 = NOISE_L; ox = int((t * 160) % W); a = l1[100:100 + H:2, ox:ox + W:2]; b = l2[300:300 + H:2, int((t * 70) % W):int((t * 70) % W) + W:2]
            front = ease(t / max(1.5, self.dur * 0.6)) * 1.3                       # the surge rolls in from the left
            xs = np.linspace(0, 1, w2, dtype=np.float32)[None, :]; ys = np.linspace(0, 1, h2, dtype=np.float32)[:, None]
            cover = np.clip((front - xs) * 3, 0, 1)
            smoke = np.clip(a * 1.5 - 0.25, 0, 1) * cover
            glow = np.clip(b * 2.0 - 0.75, 0, 1) * cover * (0.15 + 0.85 * ys ** 1.5)
            smoke = cv2.resize(smoke, (W, H))[..., None]; glow = cv2.resize(glow, (W, H))[..., None]
            fr = fr * (1 - smoke * 0.85) + np.array([28, 30, 34], np.float32) * smoke * 0.85
            fr = fr + np.array([20, 80, 230], np.float32) * glow * 0.75
        else:
            spd = {'ash': 25, 'pumice': 12, 'dark': 10}[self.kind]
            ox = int((t * spd * self.dir) % W); oy = int((200 + t * 18) % 400)
            m = cv2.resize(np.clip(n1[oy:oy + H:2, ox:ox + W:2] * 1.6 - 0.45, 0, 1), (W, H))[..., None]
            col = {'ash': (150, 150, 152), 'pumice': (170, 172, 175), 'dark': (40, 40, 44)}[self.kind]
            fr = fr * (1 - m * 0.45) + np.array(col, np.float32) * m * 0.45
        p = self.p + np.stack([self.v[0] * t * self.dir + 12 * np.sin(self.ph + t * 1.3), self.v[1] * t], 1)
        p[:, 0] %= W; p[:, 1] = (p[:, 1] % (H * 1.3)) - H * 0.15
        out = np.clip(fr, 0, 255).astype(np.uint8)
        if self.kind == 'flow': col, alpha = (90, 170, 255), 0.9
        elif self.kind == 'dark': col, alpha = (80, 140, 230), 0.6
        else: col, alpha = (205, 205, 208), 0.8
        layer = np.zeros_like(out)
        for (x, y), s in zip(p.astype(int), self.sz):
            if self.kind == 'pumice': cv2.line(layer, (x, y - int(s * 3)), (x, y), col, max(1, int(s)), cv2.LINE_AA)
            else: cv2.circle(layer, (x, y), int(s), col, -1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 0.8)
        return cv2.addWeighted(out, 1.0, layer, alpha, 0)

def text_layer(draw_fn):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); draw_fn(ImageDraw.Draw(ov)); a = np.asarray(ov).astype(np.float32)
    return cv2.cvtColor(a[..., :3].astype(np.uint8), cv2.COLOR_RGB2BGR).astype(np.float32), a[..., 3:4] / 255

def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        if d.textlength((cur + ' ' + w).strip(), font=f) > maxw: lines.append(cur); cur = w
        else: cur = (cur + ' ' + w).strip()
    return lines + [cur]

class CardShot:
    def __init__(self, title, sub, dur, big=False):
        self.dur = dur
        def draw(d):
            f = ImageFont.truetype(SERIF, 96 if big else 76); tr = 10
            wdt = sum(d.textlength(c, font=f) + tr for c in title) - tr; x = W / 2 - wdt / 2
            for c in title: d.text((x, H / 2 - 82), c, font=f, fill=(236, 232, 224, 255)); x += d.textlength(c, font=f) + tr
            d.line([(W / 2 - 60, H / 2 + 30), (W / 2 + 60, H / 2 + 30)], fill=(200, 60, 40, 255), width=3)
            f2 = ImageFont.truetype(SERIF_I, 40); d.text((W / 2 - d.textlength(sub, font=f2) / 2, H / 2 + 52), sub, font=f2, fill=(175, 172, 168, 255))
        self.rgb, self.a = text_layer(draw)
    def frame(self, t):
        a = ease((t - 0.5) / 1.3) * (1 - ease((t - (self.dur - 1.4)) / 1.1))
        bg = np.full((H, W, 3), (7, 6, 5), np.float32)
        return np.clip(bg * (1 - self.a * a) + self.rgb * self.a * a, 0, 255).astype(np.uint8)

class QuoteShot:
    def __init__(self, lib, quote, src, bgfile, dur, rnd):
        self.dur = dur
        self.bg = FxShot(lib, bgfile[3:], dur, rnd) if bgfile.startswith('fx:') else StillShot(lib, bgfile, dur, rnd)
        def draw(d):
            f = ImageFont.truetype(SERIF_I, 58); lines = wrap(d, '“' + quote + '”', f, 1300)
            y = H / 2 - len(lines) * 74 / 2 - 30
            for ln in lines: d.text((W / 2 - d.textlength(ln, font=f) / 2, y), ln, font=f, fill=(240, 236, 228, 255)); y += 74
            f2 = ImageFont.truetype(SANS, 26); s = '—  ' + src.upper()
            d.line([(W / 2 - 40, y + 26), (W / 2 + 40, y + 26)], fill=(200, 60, 40, 255), width=3)
            d.text((W / 2 - d.textlength(s, font=f2) / 2, y + 46), s, font=f2, fill=(190, 185, 178, 255))
        self.rgb, self.a = text_layer(draw)
    def frame(self, t):
        bg = self.bg.frame(t).astype(np.float32) * 0.28
        a = ease((t - 0.4) / 1.0) * (1 - ease((t - (self.dur - 0.9)) / 0.7))
        return np.clip(bg * (1 - self.a * a) + self.rgb * self.a * a, 0, 255).astype(np.uint8)

def caption(text):
    def draw(d):
        f = ImageFont.truetype(SANS, 30)
        d.line([(150, 836), (270, 836)], fill=(220, 60, 45, 255), width=3); d.text((150, 846), text, font=f, fill=(238, 236, 230, 255))
    return text_layer(draw)

# ---------------------------------------------------------------- timeline
def build(ch):
    path = sorted(glob.glob(os.path.join(ROOT, 'script', f'{ch}*.md')))[0]; name = os.path.basename(path)[:-3]
    man = json.load(open(os.path.join(B, 'vo', 'manifest.json')))[name]
    blocks = parse(path); rnd = random.Random(int(ch) * 7919 + 1); lib = Library()
    segs, vo, moods, hits, caps = [], [], [], [], []   # segs: (start, dur, kind, payload, transition_in)
    t = 0.0; pi = 0; mood = 'calm'; mood_t = 0.0; last_q = None
    for bi, b in enumerate(blocks):
        if 'card' in b:
            end = bi == len(blocks) - 1 and bi > 0
            d = END_CARD_DUR if end else CARD_DUR
            segs.append((t, d, 'card', (b['card'][0], b['card'][1] if len(b['card']) > 1 else '', bi == 0 or end), 'dip'))
            hits.append(t + 0.6); t += d; continue
        m = man[pi]; pi += 1
        if b.get('mood') and b['mood'] != mood:
            moods.append((mood_t, t, mood)); mood, mood_t = b['mood'], t
        vo.append((t + 0.35, os.path.join(B, 'vo', name, f"{m['i']:02d}.wav")))
        nxt = next((x for x in blocks[bi + 1:] if 'text' in x or 'card' in x), None)
        gap = GAP + (MOOD_GAP if nxt and (nxt.get('mood') and nxt.get('mood') != (b.get('mood') or mood)) else 0)
        dur = m['dur'] + 0.35 + gap
        if b.get('date'): caps.append((t, min(5.0, dur), b['date']))
        trans = 'dip' if segs and segs[-1][2] == 'card' else 'xf'
        if 'map' in b:
            out = os.path.join(B, 'maps', f"{name}_{pi:02d}_{b['map']}.mp4")
            if not os.path.exists(out): mapmod.render(b['map'], dur + XF + 0.1, out)
            segs.append((t, dur, 'video', out, trans))
        else:
            qoff = 0.0
            if 'quote' in b:   # quote card for the opening sentence(s) only (6-10 s), then back to pictures
                q, src = [x.strip() for x in b['quote'].split('|')]
                qs0 = [x.strip() for x in (b.get('v') or last_q or 'Volcanic ash cloud').split(';')]
                bounds = [0.35 + x['start'] for x in m['sentences'][1:]] + [dur]
                qoff = next((x for x in bounds if x >= 6.0), dur)
                if dur - qoff < 2.5: qoff = dur
                segs.append((t, qoff, 'quote', (q, src, lib.pick(qs0, rnd)), trans))
                if qoff >= dur: t += dur; continue
                trans = 'xf'
            qs = [x.strip() for x in (b.get('v') or last_q or 'Pompeii ruins panorama').split(';')]; last_q = b.get('v') or last_q
            # one shot per sentence, picture chosen from what that sentence says
            sents = m['sentences']; starts = [0.0] + [0.35 + x['start'] for x in sents[1:]] + [dur]
            spans = []
            for k, x in enumerate(sents):
                a, b2 = max(starts[k], qoff), starts[k + 1]
                if b2 <= qoff + 0.01: continue
                vis, shake = visuals.for_sentence(x['text'])
                if spans and b2 - a < 1.8 and vis is None:      # short line with no own subject: extend previous shot
                    spans[-1][1] = b2; continue
                spans.append([a, b2, vis, shake, x['text']])
            first = True
            for a, b2, vis, shake, txt in spans:
                pieces = [(a, b2 - a)] if b2 - a <= 5.6 else [(a, (b2 - a) / 2), (a + (b2 - a) / 2, (b2 - a) / 2)]
                for pi_, (pa, pd) in enumerate(pieces):
                    if vis and vis[0] == 'file' and pi_ == 0: f = vis[1]
                    elif vis and vis[0] == 'themes': f = lib.pick_themes(vis[1], rnd) or lib.pick(qs, rnd)
                    else: f = lib.pick(qs, rnd, primary=first)
                    segs.append((t + pa, pd, 'still', (f, shake and pi_ == 0, txt), trans if first else 'cut')); first = False
        t += dur
    moods.append((mood_t, t, mood))
    return name, segs, vo, moods, hits, caps, t, lib, rnd

def make_shot(seg, lib, rnd, extra):
    st, dur, kind, pay, _ = seg
    d = dur + extra
    if kind == 'still':
        f, shake = (pay[0], pay[1]) if isinstance(pay, tuple) else (pay, False)
        if f.startswith('fx:'): return FxShot(lib, f[3:], d, rnd)
        return StillShot(lib, f, d, rnd, shake)
    if kind == 'video': return VideoShot(pay, d)
    if kind == 'card': return CardShot(pay[0], pay[1], d, pay[2])
    if kind == 'quote': return QuoteShot(lib, pay[0], pay[1], pay[2], d, rnd)

def main():
    ch = sys.argv[1]; preview = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[2] == '--preview' else None
    name, segs, vo, moods, hits, caps, total, lib, rnd = build(ch)
    if preview: total = min(total, preview)
    os.makedirs(os.path.join(B, 'chapters'), exist_ok=True)
    out = os.path.join(B, 'chapters', f'{name}{"_preview" if preview else ""}.mp4')
    # ---- audio: score + narration
    mus = os.path.join(B, 'chapters', f'{name}_music.wav'); score.score(total + 1, moods, hits, mus)
    vid = out[:-4] + '_v.mp4'
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-vf', f'noise=alls=4:allf=t,drawbox=x=0:y=0:w=iw:h={TOP}:color=black:t=fill,drawbox=x=0:y={BOT}:w=iw:h={H - BOT}:color=black:t=fill,format=yuv420p',
                            '-c:v', 'libx264', '-crf', '23', '-preset', 'faster', vid], stdin=subprocess.PIPE)
    caps_l = [(a, d, caption(txt)) for a, d, txt in caps]
    N = int(total * FPS); active = {}
    for fi in range(N):
        t = fi / FPS
        # current seg index and whether in an incoming transition
        idx = max(i for i, s in enumerate(segs) if s[0] <= t + 1e-6)
        seg = segs[idx]
        for i in list(active):
            if i < idx - 1: sh = active.pop(i); getattr(sh, 'close', lambda: None)()
        if idx not in active: active[idx] = make_shot(seg, lib, rnd, XF + 0.1)
        fr = active[idx].frame(t - seg[0]).astype(np.float32)
        tin = t - seg[0]
        if seg[4] == 'xf' and tin < XF and idx > 0:
            prev = segs[idx - 1]
            if idx - 1 not in active: active[idx - 1] = make_shot(prev, lib, rnd, XF + 0.1)
            pf = active[idx - 1].frame(t - prev[0]).astype(np.float32); u = ease(tin / XF); fr = pf * (1 - u) + fr * u
        elif seg[4] == 'dip':
            fr *= ease(tin / DIP)
        if idx + 1 < len(segs) and segs[idx + 1][4] == 'dip':
            fr *= ease((segs[idx + 1][0] - t) / DIP)
        if seg[2] != 'card': fr *= VIG
        for a, d, (crgb, ca) in caps_l:
            if a <= t < a + d:
                al = ease((t - a - 0.4) / 0.6) * (1 - ease((t - (a + d - 0.7)) / 0.6)); fr = fr * (1 - ca * al) + crgb * ca * al
        if fi == 0 or fi == N - 1: fr *= 0.0
        enc.stdin.write(np.clip(fr, 0, 255).astype(np.uint8).tobytes())
        if fi % 900 == 0: print(f'{name}: {t / 60:.1f}/{total / 60:.1f} min', flush=True)
    enc.stdin.close(); enc.wait()
    for sh in active.values(): getattr(sh, 'close', lambda: None)()
    # ---- mix
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', vid, '-i', mus]
    vo_use = [(a, p) for a, p in vo if a < total]
    for a, p in vo_use: cmd += ['-i', p]
    fl = ['[1:a]volume=0.9[mus]']
    for j, (a, p) in enumerate(vo_use):
        d = int(a * 1000); fl.append(f'[{j + 2}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,volume=1.8,adelay={d}|{d}[v{j}]')
    fl.append(''.join(f'[v{j}]' for j in range(len(vo_use))) + f'amix=inputs={len(vo_use)}:normalize=0,apad,asplit=2[vm][vs]')
    fl.append('[mus][vs]sidechaincompress=threshold=0.04:ratio=5:attack=30:release=700[md]')
    fl.append(f'[md][vm]amix=inputs=2:normalize=0,atrim=0:{total:.3f},loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]')
    cmd += ['-filter_complex', ';'.join(fl), '-map', '0:v', '-map', '[aout]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', f'{total:.3f}', out]
    subprocess.run(cmd, check=True); os.remove(vid)
    print('wrote', out, f'{total / 60:.2f} min', flush=True)

if __name__ == '__main__':
    main()
