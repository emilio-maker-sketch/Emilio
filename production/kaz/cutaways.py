"""Full-screen cutaways that break away from the evidence board:
archival footage, full-screen photographs, museum 'hero' object shots, kinetic type and triptychs.
Shots are keyed to narration sentences; the board engine calls compose() for every frame."""
import os, math, json
import numpy as np, cv2
from PIL import Image, ImageDraw

E = None
FOOT = {'D': ('digging.mp4', 'ARCHIVAL FOOTAGE  ·  THEBES, c. 1920  ·  MET MUSEUM EXPEDITION FILM (PRELINGER ARCHIVES)'),
        'N': ('nile.mp4', 'ARCHIVAL FOOTAGE  ·  EGYPT, 1931  ·  "FATHER NILE" (PRELINGER ARCHIVES)'),
        'X': ('egypt20s.mp4', 'ARCHIVAL FOOTAGE  ·  EGYPT, 1920s  ·  PRELINGER ARCHIVES')}

# sentence index -> list of shots.  part=(a,b) uses a fraction of the sentence.
F = lambda src, a, b, **k: dict(kind='foot', src=src, a=a, b=b, **k)
P = lambda id_, label=None, **k: dict(kind='photo', id=id_, label=label, **k)
O = lambda id_, title, sub, **k: dict(kind='object', id=id_, title=title, sub=sub, **k)
K = lambda text, red=(), **k: dict(kind='type', text=text, red=set(red), **k)
T = lambda ids, label, **k: dict(kind='trip', ids=ids, label=label, **k)
SHOTS = {
    3: [K("THE LAST WARRIOR PHARAOH|WAS MURDERED.", ['MURDERED.'])],
    5: [F('D', 121.5, 139, part=(0, .5)), F('X', 408, 430, part=(.5, 1))],
    6: [K("A QUEEN.|HER SON.|THE THRONE.", ['THRONE.'])],
    7: [K("MESSENGERS.|REBELS.|MAGIC.", ['MAGIC.'])],
    9: [F('N', 296, 309.5)],
    10: [O('met549298', 'Ramesses III', 'FAIENCE INLAY  ·  REIGN OF RAMESSES III, c. 1184–1153 BCE  ·  THE MET', part=(0, .55))],
    11: [P('met705430', 'THE RAMESSEUM, TEMPLE OF RAMESSES II  ·  ÉMILE BÉCHARD, 1870s  ·  THE MET')],
    13: [P('met287142', "MEDINET HABU FROM THE EAST  ·  MAXIME DU CAMP, 1849–50  ·  THE MET")],
    14: [P('met261835', "MEDINET HABU, SECOND COURT  ·  FÉLIX TEYNARD, 1851–52  ·  THE MET")],
    17: [F('X', 408, 430)],
    22: [P('met260975', "THE VALLEY OF THE KINGS  ·  FRANCIS FRITH, c. 1857  ·  THE MET")],
    23: [F('D', 1216, 1240)],
    25: [K("THE FIRST RECORDED|STRIKE IN HISTORY.", ['STRIKE'])],
    26: [F('D', 576, 592)],
    30: [P('met548357', "RAMESSES III AND HIS SON, TOMB IN THE VALLEY OF THE QUEENS  ·  FACSIMILE, NINA DE GARIS DAVIES  ·  THE MET", part=(0, .6))],
    34: [P('met287144', "THE 'HAREM' PAVILION, MEDINET HABU  ·  MAXIME DU CAMP, 1849–50  ·  THE MET", part=(0, .6))],
    36: [K("ESTATES. WORKSHOPS.|SERVANTS. OFFICIALS.", ['ESTATES.'])],
    38: [P('met266121', "MEDINET HABU  ·  JOHN BEASLEY GREEN, 1854  ·  THE MET")],
    46: [O('met548356', 'Ramesses IV', "ARTIST'S SKETCH ON LIMESTONE  ·  c. 1166–1158 BCE  ·  THE MET")],
    51: [K("THE KING|WOULD HAVE TO DIE.", ['DIE.'])],
    54: [P('met260967', "HYPOSTYLE HALL, KARNAK  ·  ADOLPHE BRAUN, c. 1870  ·  THE MET")],
    57: [K("AN ATTACK ON THE|ORDER OF THE WORLD.", ['ORDER'])],
    58: [O('met549250', 'A Hieratic Papyrus', 'PAPYRUS IN HIERATIC SCRIPT  ·  c. 1181 BCE  ·  THE MET', part=(.4, 1))],
    64: [O('met544719', 'Window Grill', 'FROM A PALACE OF RAMESSES III  ·  c. 1184–1153 BCE  ·  THE MET')],
    67: [F('X', 408, 430)],
    68: [K("INCITE THE PEOPLE.|MAKE ENMITY.|MAKE REBELLION.", ['REBELLION.'])],
    76: [K("A DARK IRONY.", ['IRONY.'])],
    78: [O('met556841', 'Execration Figure', 'FIGURE OF A BOUND FOREIGNER  ·  c. 1900 BCE  ·  THE MET', part=(0, .6))],
    89: [P('met263236', "MEDINET HABU, PALACE PERISTYLE  ·  MAXIME DU CAMP, 1850  ·  THE MET", part=(.15, .75))],
    90: [P('met287147', "PILLARS IN THE COURT OF THE TEMPLE OF RAMESSES III  ·  MAXIME DU CAMP, 1850  ·  THE MET")],
    93: [K("RAMESSES III|DIED.", ['DIED.'])],
    96: [O('met549335', 'Ramesses IV', 'HES VASE INSCRIBED WITH HIS NAME  ·  c. 1166–1158 BCE  ·  THE MET')],
    100: [T(['met549229', 'met554341', 'met549250'], "STATUE OF AN OFFICIAL, SCRIBE'S PALETTE, PAPYRUS  ·  THE MET")],
    108: [K("GUILTY.|GUILTY.|GUILTY.", ['GUILTY.'])],
    112: [K("EXECUTED.", ['EXECUTED.'])],
    115: [K("AND TIYE?", ['TIYE?'])],
    124: [K("DID THEY ACTUALLY|KILL THE KING?", ['KILL'])],
    127: [P('met12061', "CLIFFS AT DEIR EL BAHRI  ·  JOHN SINGER SARGENT, 1890–91  ·  THE MET")],
    128: [F('D', 121.5, 139)],
    129: [F('D', 957, 963.5, part=(0, .5)), F('D', 964, 971, part=(.5, 1))],
    131: [F('D', 922.5, 931)],
    132: [F('D', 957, 963.5)],
    136: [K("THE NECK|STAYED WRAPPED.", ['WRAPPED.'])],
    141: [K("THE SCREAMING|MUMMY.", ['SCREAMING'])],
    147: [K("WINDPIPE. ARTERIES.|SEVERED.", ['SEVERED.'])],
    149: [O('met551476', 'The Eye of Horus', 'WEDJAT EYE AMULET  ·  NEW KINGDOM  ·  THE MET', part=(0, .65))],
    154: [K("THE VERDICT|WAS IN.", ['VERDICT'])],
    158: [K("HE WAS|THE KING'S SON.", ['SON.'])],
    165: [F('N', 296, 309.5)],
    166: [P('met557765', "JOURNEY TO ABYDOS, TOMB OF PAIRY  ·  FACSIMILE, CHARLES K. WILKINSON  ·  THE MET")],
    167: [P('met283145', "THE COLOSSI OF RAMESSES II, ABU SIMBEL  ·  FÉLIX TEYNARD, 1851–52  ·  THE MET")],
    168: [K("SIX YEARS.", ['SIX'])],
    170: [O('met544242', 'A Bow Harp', 'BOW HARP  ·  c. 2030–1640 BCE  ·  THE MET', part=(.3, 1))],
    172: [F('D', 973, 1018, part=(.25, .85))],
    173: [P('met261867', "KARNAK, FIRST PYLON IN RUINS  ·  FÉLIX TEYNARD, 1851–52  ·  THE MET")],
    178: [K("A KING MURDERED|BY HIS OWN HOUSEHOLD.", ['MURDERED'])],
    179: [K("A TRIAL CORRUPTED|BY ITS OWN JUDGES.", ['CORRUPTED'])],
    180: [K("A COLD CASE|SOLVED BY A SCANNER.", ['SCANNER.'], part=(0, .8))],
}
CUTS = []
TIN = .28

def init(eng):
    global E
    E = eng
    S = E.TL['sentences']
    busy = [(f['t0'] - .5, f['t1'] + .3) for f in E.FILMS]
    if E.VINTAGE: busy.append((E.VINTAGE[0] - .5, E.VINTAGE[1] + .3))
    for o in E.OVERLAYS:
        busy.append((o['t0'] - .3, o['t0'] + o['dur'] + .3))
    for i, shots in sorted(SHOTS.items()):
        s = S[i]; a, b = s['start'] - .12, s['end'] + .3
        if i + 1 < len(S): b = min(b, S[i + 1]['start'] - .05)
        for sh in shots:
            pa, pb = sh.get('part', (0, 1))
            t0, t1 = a + (b - a) * pa, a + (b - a) * pb
            for x, y in sorted(busy):
                if x < t1 and t0 < y:
                    if y - t0 < t1 - x: t0 = y          # overlap at the head: start after it
                    else: t1 = x                        # overlap at the tail: end before it
            if t1 - t0 < 1.3: print('cutaway skipped (busy):', i, sh['kind']); continue
            CUTS.append(dict(sh, t0=t0, t1=t1, s=i))
    CUTS.sort(key=lambda c: c['t0'])
    for p, n in zip(CUTS, CUTS[1:]):
        if n['t0'] - p['t1'] < .45: p['t1'] = n['t0']; p['hard_out'] = n['hard_in'] = True
    return CUTS

# ------------------------------------------------------------------ helpers
W, H = 1920, 1080
SH = np.array([34, 38, 24], np.float32); HI = np.array([196, 222, 238], np.float32)    # BGR split tone: teal shadows, warm highlights
def grade(img, color_keep=0.0):
    f = img.astype(np.float32)
    l = (f[..., 0]*.11 + f[..., 1]*.59 + f[..., 2]*.30) / 255
    l = np.clip((l - .04) / .92, 0, 1); l = l*l*(3 - 2*l)*.75 + l*.25
    out = SH + (HI - SH) * l[..., None]
    if color_keep: out = out*(1 - color_keep) + f*color_keep
    return out
_GR = None
def finish(f, fi, flicker=0.0):
    global _GR
    if _GR is None: r = np.random.default_rng(5); _GR = [r.normal(0, 6.5, (H, W, 1)).astype(np.float32) for _ in range(5)]
    v = (1 - .55*np.clip(((E.vx - W/2)/(W*.6))**2 + ((E.vy - H/2)/(H*.6))**2, 0, 1))[..., None]
    k = 1.0 + (np.random.default_rng(fi).uniform(-flicker, flicker) if flicker else 0)
    return np.clip(f*v*k + _GR[fi % 5], 0, 255)

def zoom(img, z, cx=.5, cy=.5):
    M = np.float32([[z, 0, W*cx - z*W*cx], [0, z, H*cy - z*H*cy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

def cover(img, w, h, extra=1.0):
    ih, iw = img.shape[:2]; s = max(w/iw, h/ih) * extra
    return cv2.resize(img, (int(iw*s) + 1, int(ih*s) + 1), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)

def label(f, text, t, t0, x=70, y=H - 92):
    n = int(max(0, t - t0 - .35) * 70)
    if n <= 0: return f
    pil = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)[..., ::-1]); d = ImageDraw.Draw(pil)
    s = text[:n]; fn = E.font(E.MONO, 22); w = fn.getlength(s)
    d.rectangle([x - 14, y - 10, x + w + 14, y + 34], fill=(10, 10, 10))
    d.rectangle([x - 14, y - 10, x - 8, y + 34], fill=E.RED)
    d.text((x, y), s, font=fn, fill=(232, 226, 212))
    return np.asarray(pil)[..., ::-1].astype(np.float32)

_IMG = {}
def longest_run(b):
    best, cur, st = (0, 0), 0, 0
    for i, v in enumerate(list(b) + [False]):
        if v:
            if cur == 0: st = i
            cur += 1
        else:
            if cur > best[1] - best[0]: best = (st, st + cur - 1)
            cur = 0
    return best
def museum_img(id_):
    if id_ not in _IMG:
        rec = E.find_image(id_, set())
        im = cv2.imread(os.path.join(E.IMGDIR, rec['file']), cv2.IMREAD_COLOR)
        is_print = 'print' in rec.get('medium', '').lower() or 'photograph' in rec.get('medium', '').lower()
        for _ in range(3 if is_print else 0):  # strip the mount around old photographic prints only; museum object photos keep their full frame
            g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 3)
            e = max(6, int(min(im.shape[:2]) * .025))
            bd = np.median(np.concatenate([g[e:2*e].ravel(), g[-2*e:-e].ravel(), g[:, e:2*e].ravel(), g[:, -2*e:-e].ravel()]))
            m = np.abs(g - bd) > 10
            (y0, y1), (x0, x1) = longest_run(m.mean(1) > .3), longest_run(m.mean(0) > .3)
            if not (y1 - y0 > im.shape[0]*.3 and x1 - x0 > im.shape[1]*.3): break
            if (y1 - y0) > im.shape[0]*.97 and (x1 - x0) > im.shape[1]*.97: break
            if m[y0:y1, x0:x1].mean() < .6: break   # inside is mostly plain backdrop: a studio object photo, not a mounted print
            py, px = int((y1 - y0)*.015), int((x1 - x0)*.015)
            im = im[y0 + py:y1 - py, x0 + px:x1 - px]
        if max(im.shape[:2]) > 2600: s = 2600/max(im.shape[:2]); im = cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        _IMG[id_] = (im, rec)
    return _IMG[id_]

_CUT = {}
def object_rgba(id_):
    if id_ not in _CUT:
        p = os.path.join(E.B, 'cut', id_ + '.png')
        if os.path.exists(p): co = Image.open(p).convert('RGBA')
        else:
            im, rec = museum_img(id_)
            co = E.cutout(Image.fromarray(im[..., ::-1]))
            if co is not None: os.makedirs(os.path.dirname(p), exist_ok=True); co.save(p)
        if co is None or co.width < 2:
            im, _ = museum_img(id_); a = np.dstack([im, np.full(im.shape[:2], 255, np.uint8)])
        else:
            a = np.asarray(co)[..., [2, 1, 0, 3]].copy()
        _CUT[id_] = a
    return _CUT[id_]

class Reader:
    def __init__(self, path):
        self.cap = cv2.VideoCapture(path); self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 24; self.last = -9; self.fr = None
    def get(self, sec):
        i = int(sec * self.fps)
        if i == self.last: return self.fr
        if i != self.last + 1: self.cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, fr = self.cap.read()
        if ok: self.fr, self.last = fr, i
        return self.fr
_RD = {}

# ------------------------------------------------------------------ shot renderers
def r_foot(c, t, fi):
    path, lab = FOOT[c['src']]
    rd = _RD.setdefault(path, Reader(os.path.join(E.B, 'footage', path)))
    dur = c['t1'] - c['t0']; avail = c['b'] - c['a'] - 1.2
    sp = min(1.0, max(.55, avail / dur)); src = c['a'] + .6 + (t - c['t0']) * sp
    fr = rd.get(src)
    if fr is None: return np.zeros((H, W, 3), np.float32)
    h, w = fr.shape[:2]; ch = int(w * 9 / 16); y0 = (h - ch) // 2
    fr = cv2.resize(fr[y0:y0 + ch], (W, H), interpolation=cv2.INTER_CUBIC)
    bl = cv2.GaussianBlur(fr, (0, 0), 2.2); fr = cv2.addWeighted(fr, 1.6, bl, -.6, 0)
    u = (t - c['t0']) / dur; fr = zoom(fr, 1.03 + .07*u, .5 + .03*math.sin(c['s']), .5)
    r = np.random.default_rng(fi); fr = cv2.warpAffine(fr, np.float32([[1, 0, r.normal(0, 1.2)], [0, 1, r.normal(0, 1.6)]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    lum = cv2.cvtColor(fr.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    lo, hi = np.percentile(lum[::4, ::4], (1, 98))
    if hi - lo < 170:                       # flat/dark shot (e.g. the Theban cliffs): stretch it so it reads
        fr = np.clip((fr.astype(np.float32) - lo) * (215.0 / max(30.0, hi - lo)) + 12, 0, 255)
    f = grade(fr)
    for _ in range(r.integers(0, 4)): cv2.circle(f, (int(r.integers(0, W)), int(r.integers(0, H))), int(r.integers(1, 4)), (20, 18, 14), -1)
    if r.random() < .3: x = int(r.integers(0, W)); cv2.line(f, (x, 0), (x + int(r.integers(-15, 15)), H), (210, 220, 228), 1)
    f = finish(f, fi, .05)
    return label(f, lab, t, c['t0'])

def r_photo(c, t, fi):
    im, rec = museum_img(c['id']); dur = c['t1'] - c['t0']; u = E.ease((t - c['t0']) / dur) * .6 + (t - c['t0']) / dur * .4
    big = c.setdefault('_big', cover(im, W, H, 1.22))
    bh, bw = big.shape[:2]; k = c['s'] % 4
    dx = [(0, 1), (1, 0), (.5, .5), (0, .3)][k]; z = 1.0 + .06*u if k != 2 else 1.08 - .06*u
    x = (bw - W) * (dx[0] + (dx[1] - dx[0]) * u); y = (bh - H) * (.35 + .3*u if k % 2 else .6 - .3*u)
    M = np.float32([[z, 0, -x*z + W*(1 - z)/2], [0, z, -y*z + H*(1 - z)/2]])
    fr = cv2.warpAffine(big, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    sat = fr.astype(np.float32).std(axis=2).mean()
    f = grade(fr, .55 if sat > 18 else 0.0)
    sweep = np.clip(1 - np.abs((E.vx - (-400 + 2700*((t - c['t0'])/dur))) + (E.vy - H/2)*.4) / 380, 0, 1)[..., None]
    f = f + sweep * 26
    f = finish(f, fi)
    return label(f, c['label'] or rec['title'].upper(), t, c['t0'])

_BG = None
def dark_bg(t):
    global _BG
    if _BG is None:
        g = np.zeros((H, W, 3), np.float32) + np.array([18, 22, 20], np.float32)
        _BG = g
    lx = W*(.62 + .05*math.sin(t*.4)); ly = H*(.45 + .04*math.cos(t*.3))
    spot = np.exp(-(((E.vx - lx)/(W*.38))**2 + ((E.vy - ly)/(H*.5))**2))[..., None]
    return _BG + spot * np.array([40, 52, 58], np.float32)

def blend_rgba(f, rgba, x, y):
    h, w = rgba.shape[:2]; x0, y0 = max(0, x), max(0, y); x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0: return
    s = rgba[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32); a = s[..., 3:4]/255
    f[y0:y1, x0:x1] = f[y0:y1, x0:x1]*(1 - a) + s[..., :3]*a

def r_object(c, t, fi):
    rgba = object_rgba(c['id']); dur = c['t1'] - c['t0']; u = (t - c['t0']) / dur
    f = dark_bg(t)
    h, w = rgba.shape[:2]; s = min(860/w, 820/h) * (1.0 + .07*E.ease(u)); s *= .94 + .06*E.ss((t - c['t0'])/.5)
    ob = cv2.resize(rgba, (max(2, int(w*s)), max(2, int(h*s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    oh, ow = ob.shape[:2]; cx, cy = 1290 - 30*u, 540
    sh = ob.copy(); sh[..., :3] = 0; sh[..., 3] = (cv2.GaussianBlur(ob[..., 3], (0, 0), 22) * .7).astype(np.uint8)
    blend_rgba(f, sh, int(cx - ow/2 + 26), int(cy - oh/2 + 34))
    obf = ob.astype(np.float32)
    band = np.clip(1 - np.abs(np.arange(ow)[None, :] + np.arange(oh)[:, None]*.5 - (-.3 + 1.6*u)*(ow + oh*.5)) / (ow*.12), 0, 1)
    obf[..., :3] = np.clip(obf[..., :3] + band[..., None]*70, 0, 255)
    blend_rgba(f, obf, int(cx - ow/2), int(cy - oh/2))
    pil = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)[..., ::-1]); d = ImageDraw.Draw(pil)
    lt = t - c['t0']
    d.text((130, 330), 'EXHIBIT', font=E.font(E.MONO, 26), fill=E.RED)
    ft = E.font(E.SERIF, 76); n = int(max(0, lt - .2) * 26); title = c['title']
    d.text((130, 372), title[:n], font=ft, fill=(240, 234, 220))
    if lt > .5: d.line([(132, 478), (132 + min(1, (lt - .5)/.4)*360, 478)], fill=E.RED, width=4)
    sub = c['sub'].split('  ·  '); fs = E.font(E.MONO, 24)
    for i, ln in enumerate(sub):
        k = int(max(0, lt - .7 - .25*i) * 60)
        d.text((132, 506 + 40*i), ln[:k], font=fs, fill=(200, 200, 190))
    f = np.asarray(pil)[..., ::-1].astype(np.float32)
    return finish(f, fi)

_WIMG = {}
def word_img(wd, size, red):
    key = (wd, size, red)
    if key not in _WIMG:
        fn = E.font(E.SERIF, size); bb = fn.getbbox(wd); w, h = bb[2] - bb[0] + 20, bb[3] + 30
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ImageDraw.Draw(im).text((10 - bb[0], 10), wd, font=fn, fill=(E.RED if red else (242, 236, 224)) + (255,))
        _WIMG[key] = np.asarray(im)[..., [2, 1, 0, 3]].copy()
    return _WIMG[key]

def type_layout(c):
    if '_lay' in c: return c['_lay']
    lines = [l.split(' ') for l in c['text'].split('|')]
    size = 150
    while True:
        fn = E.font(E.SERIF, size); sp = fn.getlength(' ')
        widths = [sum(fn.getlength(w) for w in l) + sp*(len(l) - 1) for l in lines]
        if max(widths) < 1500 and size*1.2*len(lines) < 760: break
        size -= 6
    lay, y = [], H/2 - size*1.2*len(lines)/2
    n = sum(len(l) for l in lines); dur = c['t1'] - c['t0']; step = min(.26, (dur*.55) / max(1, n)); k = 0
    for l, wl in zip(lines, widths):
        x = W/2 - wl/2
        for w in l:
            ww = fn.getlength(w); red = w in c['red']
            lay.append(dict(w=w, x=x, cx=x + ww/2, y=y, size=size, red=red, t=c['t0'] + .1 + k*step + (.12 if red else 0)))
            x += ww + sp; k += 1
        y += size*1.2
    c['_lay'] = lay
    return lay

def r_type(c, t, fi):
    f = dark_bg(t) * .8
    shake = 0
    for wd in type_layout(c):
        u = (t - wd['t']) / .16
        if u <= 0: continue
        if wd['red'] and u < 3: shake = max(shake, 9*(1 - u/3))
        img = word_img(wd['w'], wd['size'], wd['red']); s = 1 + (.22 if wd['red'] else .15)*(1 - E.ease(min(1, u)))
        if s != 1: img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR)
        img = img.astype(np.float32); img[..., 3] *= E.ss(u*1.5)
        h, w = img.shape[:2]
        blend_rgba(f, img, int(wd['cx'] - w/2), int(wd['y'] + wd['size']*.55 - h/2))
        if wd['red'] and u > 1.2:
            v = E.ease((u - 1.2)/2.2); fn = E.font(E.SERIF, wd['size']); ww = fn.getlength(wd['w'])
            cv2.line(f, (int(wd['x']), int(wd['y'] + wd['size']*1.12)), (int(wd['x'] + ww*v), int(wd['y'] + wd['size']*1.12)), (45, 49, 208), 7)
    if shake:
        r = np.random.default_rng(fi); f = cv2.warpAffine(f, np.float32([[1, 0, r.uniform(-shake, shake)], [0, 1, r.uniform(-shake, shake)]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    return finish(f, fi)

def content_center(im):
    """Centre (0..1) of the part of a museum photo that differs from its plain backdrop, plus how much of the image it fills."""
    g = cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 4)
    e = max(4, int(min(g.shape) * .03))
    bd = np.median(np.concatenate([g[:e].ravel(), g[-e:].ravel(), g[:, :e].ravel(), g[:, -e:].ravel()]))
    m = np.abs(g - bd) > 14
    if m.mean() < .002: return .5, .5, 0.0
    ys, xs = np.nonzero(m)
    return (np.percentile(xs, 5) + np.percentile(xs, 95)) / 2 / g.shape[1], (np.percentile(ys, 5) + np.percentile(ys, 95)) / 2 / g.shape[0], float(m.mean())

def object_box(im):
    """Bounding box of the object, found from its edges (robust to gradient studio backdrops)."""
    sc = 800 / max(im.shape[:2]); sm = cv2.resize(im, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
    g = cv2.GaussianBlur(cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY), (0, 0), 1.5)
    ed = cv2.dilate(cv2.Canny(g, 40, 110), np.ones((5, 5), np.uint8))
    ys, xs = np.nonzero(ed)
    if len(xs) < 50: return 0, 0, im.shape[1], im.shape[0]
    return tuple(int(v / sc) for v in (np.percentile(xs, .5), np.percentile(ys, .5), np.percentile(xs, 99.5), np.percentile(ys, 99.5)))

def frame_object(im, pw, ph):
    """Crop around the object at the panel's aspect ratio (12% margin), padding with the backdrop colour if needed."""
    x0, y0, x1, y1 = object_box(im); bw, bh = (x1 - x0) * 1.24, (y1 - y0) * 1.24
    ar = pw / ph
    if bw / bh > ar: bh = bw / ar
    else: bw = bh * ar
    bw, bh = bw * 1.07, bh * 1.07                    # room for the slow push-in
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    e = max(4, int(min(im.shape[:2]) * .03)); bg = np.median(np.concatenate([im[:e].reshape(-1, 3), im[-e:].reshape(-1, 3)]), 0)
    pad = int(max(bw, bh)); big = cv2.copyMakeBorder(im, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    X0, Y0 = int(cx - bw/2 + pad), int(cy - bh/2 + pad)
    crop = big[Y0:Y0 + int(bh), X0:X0 + int(bw)]
    return cv2.resize(crop, (int(pw * 1.07) + 2, int(ph * 1.07) + 2), interpolation=cv2.INTER_AREA)

def panel_fill(crop):
    cx, cy, fill = content_center(crop); return fill

def r_trip(c, t, fi):
    f = dark_bg(t) * .7; pw, gap = 610, 22; x0 = (W - 3*pw - 2*gap)//2
    for i, id_ in enumerate(c['ids']):
        u = E.ease((t - c['t0'] - .14*i) / .5)
        if u <= 0: continue
        im, _ = museum_img(id_); key = '_p%d' % i
        if key not in c:
            c[key] = frame_object(im, pw, H - 160)    # whole object in frame, with margin
        p = c[key]; z = (t - c['t0'])/(c['t1'] - c['t0']); k = 1.0 + .06*z
        p2 = cv2.resize(p, None, fx=k, fy=k, interpolation=cv2.INTER_LINEAR); ph, pw2 = p2.shape[:2]
        ox = int((pw2 - pw) * (.5 + .3*math.sin(i + z))); oy = int((ph - (H - 160)) * .5)
        crop = p2[oy:oy + H - 160, ox:ox + pw]
        g = grade(crop, .6) if crop.size else None
        if g is None: continue
        dy = int((1 - u) * (H if i % 2 == 0 else -H))
        y = 80 + dy; x = x0 + i*(pw + gap)
        ys, ye = max(0, y), min(H, y + g.shape[0])
        if ye > ys: f[ys:ye, x:x + g.shape[1]] = g[ys - y:ye - y]
    f = finish(f, fi)
    return label(f, c['label'], t, c['t0'], y=H - 62)

def audit():
    """Flag triptych panels that would be mostly empty backdrop. Run before every full render."""
    bad = []
    for c in CUTS:
        if c['kind'] != 'trip': continue
        pw = 610
        for i, id_ in enumerate(c['ids']):
            im, _ = museum_img(id_); fill = panel_fill(frame_object(im, pw, H - 160))
            if fill < .12: bad.append((round(c['t0'], 1), id_, round(fill, 3)))
    for b in bad: print('WARN trip panel mostly empty at t=%ss: %s (fill %.3f)' % b)
    return bad

R = {'foot': r_foot, 'photo': r_photo, 'object': r_object, 'type': r_type, 'trip': r_trip}

def active(t):
    for c in CUTS:
        if c['t0'] <= t < c['t1']: return c
    return None

def compose(t, fi, board):
    c = active(t)
    if c is None: return board(t, fi)
    fr = R[c['kind']](c, t, fi)
    lt, rt = t - c['t0'], c['t1'] - t
    if lt < TIN and not c.get('hard_in'):
        u = E.ss(lt / TIN); b = board(t, fi).astype(np.float32)
        b = zoom(b, 1 + .7*u); fr = zoom(fr, 1.25 - .25*u)
        k = int(9*math.sin(math.pi*u)) | 1
        mix = b*(1 - u) + fr*u
        fr = cv2.GaussianBlur(mix, (k, k), 0) if k > 1 else mix
    elif lt < 2/30 and c.get('hard_in'):
        fr = fr + 60
    if rt < TIN and not c.get('hard_out'):
        u = E.ss(1 - rt / TIN); b = board(t, fi).astype(np.float32)
        fr = zoom(fr, 1 + .7*u); b = zoom(b, 1.25 - .25*u)
        k = int(9*math.sin(math.pi*u)) | 1
        mix = fr*(1 - u) + b*u
        fr = cv2.GaussianBlur(mix, (k, k), 0) if k > 1 else mix
    return np.clip(fr, 0, 255).astype(np.uint8)
