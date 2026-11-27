"""Data-driven Kaz evidence-board engine (adapted from the kaz-documentary board_engine.py).

Reads build/timeline.json (sentences + timed @directives from script.md) and renders the board video.
  python3 kaz_engine.py stills 12,40,95        -> build/stills/*.jpg
  python3 kaz_engine.py full START END out.mp4 (frame range)
"""
import json, math, os, re, subprocess, sys, unicodedata
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
B = os.path.join(HERE, 'build')
IMGDIR = os.path.join(ROOT, 'build', 'images')
W, H, FPS = 1920, 1080, 30
MONO = "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf"
SERIF = "/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf"
RED = (208, 49, 45)                       # RGB for PIL
R = 2.0                                   # card pixels per world unit
ZW, ZH, MARG, COLS = 4300, 3100, 420, 4
ZONES = ['open', 'king', 'library', 'fall', 'mound', 'flood', 'war', 'verdict']
ZONE_TITLES = {'open': 'EXHIBIT A', 'king': 'FILE 01  THE KING', 'library': 'FILE 02  THE LIBRARY', 'fall': 'FILE 03  THE FALL',
               'mound': 'FILE 04  THE MOUND', 'flood': 'FILE 05  THE FLOOD TABLET', 'war': 'FILE 06  THE WAR', 'verdict': 'FILE 07  VERDICT'}
WW = COLS * ZW + 2 * MARG
WH = 2 * ZH + 2 * MARG

def font(p, s): return ImageFont.truetype(p, max(1, int(s)))
def clamp(x, a=0, b=1): return max(a, min(b, x))
def ss(x): x = clamp(x); return x * x * (3 - 2 * x)
def ease(x): x = clamp(x); return 4*x*x*x if x < .5 else 1 - (-2*x+2)**3/2
def backout(x, s=1.7): x = clamp(x) - 1; return 1 + (s+1)*x**3 + s*x**2
rng = np.random.default_rng(1)

# ------------------------------------------------------------------ assets
DB = {}
for f in ('museum.json', 'aic.json', 'commons.json'):
    p = os.path.join(IMGDIR, f)
    if os.path.exists(p):
        for t, recs in json.load(open(p)).items():
            for r in recs: r['topic'] = t; DB.setdefault(r['id'], r)

def find_image(spec, used):
    if re.match(r'^(met|aic)\d+$', spec) or spec.startswith('wc_'): return DB[spec]
    topic, _, kw = spec.partition(':')
    kws = [k.lower() for k in kw.split('|')] if kw else None
    for r in DB.values():
        if r['topic'] != topic or r['id'] in used: continue
        hay = unicodedata.normalize('NFKD', r['title'] + ' ' + r.get('term', '')).encode('ascii', 'ignore').decode().lower()
        if kws and not any(k in hay for k in kws): continue
        if os.path.exists(os.path.join(IMGDIR, r['file'])): return r
    raise SystemExit(f'no image for {spec}')

def shadowed(paper_rgba, pad_world=50):
    pad = int(pad_world * R); pw, ph = paper_rgba.size
    c = Image.new("RGBA", (pw + 2*pad, ph + 2*pad), (0, 0, 0, 0))
    sh = Image.new("L", c.size, 0); ImageDraw.Draw(sh).rectangle([pad, pad + 16*R, pad+pw, pad+ph+16*R], fill=130)
    c.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(14*R)))
    c.alpha_composite(paper_rgba, (pad, pad))
    return cv2.cvtColor(np.array(c), cv2.COLOR_RGBA2BGRA)

def trim(im):
    """crop museum studio backgrounds / photo mounts using the production trimmer"""
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from build_video import trim_mount
    a = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    return Image.fromarray(cv2.cvtColor(trim_mount(a), cv2.COLOR_BGR2RGB))

_RB = None
def cutout(im):
    """Lift a museum object off a plain studio background. rembg (IS-Net) first; GrabCut as a fallback."""
    global _RB
    try:
        from rembg import remove, new_session
        if _RB is None: _RB = new_session('isnet-general-use')
        sm = im.copy(); sm.thumbnail((1600, 1600))
        co = remove(sm, session=_RB, post_process_mask=True)
        al = np.array(co)[..., 3]; frac = (al > 128).mean()
        if .04 < frac < .92:
            ys, xs = np.nonzero(al > 20)
            return co.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    except ImportError:
        pass
    return cutout_grabcut(im)

def cutout_grabcut(im):
    a = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR); h, w = a.shape[:2]
    k = 640 / max(h, w); sm = cv2.resize(a, (int(w*k), int(h*k)), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY).astype(np.float32); hh, ww = g.shape; c = max(4, int(min(hh, ww)*.04))
    corners = [g[:c, :c], g[:c, -c:], g[-c:, :c], g[-c:, -c:]]
    if max(p.std() for p in corners) > 12 or max(p.mean() for p in corners) - min(p.mean() for p in corners) > 40: return None
    mask = np.zeros((hh, ww), np.uint8); r = (int(ww*.03), int(hh*.03), int(ww*.94), int(hh*.94))
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    try: cv2.grabCut(sm, mask, r, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    except cv2.error: return None
    m = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2: return None
    i = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])); m = np.where(lab == i, 255, 0).astype(np.uint8)
    frac = m.mean() / 255
    if not (.06 < frac < .88): return None
    m = cv2.GaussianBlur(cv2.resize(m, (w, h), interpolation=cv2.INTER_LINEAR), (0, 0), 1.6)
    ys, xs = np.where(m > 20); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([np.array(im), m]); return Image.fromarray(rgba[y0:y1, x0:x1], 'RGBA')

def make_cutout(rgba, wworld, max_h=520):
    ar = rgba.height / rgba.width
    if wworld * ar > max_h: wworld = max_h / ar
    pw = int(wworld * R); ph = int(pw * ar); im = rgba.resize((pw, ph), Image.LANCZOS)
    pad = int(50 * R); c = Image.new("RGBA", (pw + 2*pad, ph + 2*pad), (0, 0, 0, 0))
    sh = Image.new("L", c.size, 0); sh.paste(im.split()[3].point(lambda v: int(v * .62)), (pad + int(10*R), pad + int(20*R)))
    c.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(12*R)))
    c.alpha_composite(im, (pad, pad))
    return cv2.cvtColor(np.array(c), cv2.COLOR_RGBA2BGRA), (wworld, wworld*ar)

def make_card(path, wworld, max_h=560, border=14, rec=None, nocut=False):
    raw = Image.open(path).convert("RGB")
    objlike = rec is not None and not nocut and not re.search(r'paint|fresco|photograph|print|albumen|watercolor|oil on|ink|cubiculum|paper|board|cloth|book|letters', (rec.get('medium', '') + ' ' + rec.get('title', '')).lower())
    if rec is not None and not rec.get('artist') and objlike:
        cache = os.path.join(B, 'cut', rec['id'] + '.png')
        if os.path.exists(cache): co = Image.open(cache)
        else:
            co = cutout(raw); os.makedirs(os.path.dirname(cache), exist_ok=True)
            (co or Image.new('RGBA', (1, 1))).save(cache)
        if co is not None and co.width > 1: return make_cutout(co, wworld * 1.05)
    im = trim(raw)
    ar = im.height / im.width
    if wworld * ar > max_h: wworld = max_h / ar
    pw = int(wworld * R); ph = int(pw * ar)
    im = im.resize((pw, ph), Image.LANCZOS)
    b = int(border * R)
    paper = Image.new("RGBA", (pw + 2*b, ph + 2*b), (234, 227, 210, 255)); paper.paste(im, (b, b))
    return shadowed(paper), (wworld + 2*border, wworld*ar + 2*border)

def make_paper(lines, wworld=None):
    f = font(MONO, 30*R)
    tw = max(f.getbbox(l)[2] for l in lines) / R + 80
    wworld = max(wworld or 0, tw, 300); hworld = 60 + 52 * len(lines) + 30
    pw, ph = int(wworld*R), int(hworld*R)
    p = Image.new("RGBA", (pw, ph), (228, 218, 196, 255)); d = ImageDraw.Draw(p)
    for i in range(0, ph, int(26*R)): d.line([(0, i), (pw, i)], fill=(205, 196, 176), width=2)
    y = 40*R
    for txt in lines:
        d.text((36*R, y), txt, font=f, fill=(40, 36, 32)); y += 52*R
    # masking tape
    d.rectangle([pw/2 - 60*R, -10, pw/2 + 60*R, 22*R], fill=(214, 204, 170, 230))
    return shadowed(p), (wworld, hworld)

def silhouette(d, x, y, s, fill):
    """head-and-shoulders with a striped Egyptian tripartite wig (centre x, head centre y)"""
    d.pieslice([x - 175*s, y + 105*s, x + 175*s, y + 420*s], 180, 360, fill=fill)                  # shoulders
    d.rectangle([x - 24*s, y + 40*s, x + 24*s, y + 130*s], fill=fill)                               # neck
    d.polygon([(x - 70*s, y - 60*s), (x + 70*s, y - 60*s), (x + 92*s, y + 118*s), (x - 92*s, y + 118*s)], fill=fill)  # wig
    d.ellipse([x - 72*s, y - 98*s, x + 72*s, y + 20*s], fill=fill)                                  # wig crown
    face = tuple(min(255, c + 22) for c in fill[:3]) + (255,)
    d.ellipse([x - 44*s, y - 62*s, x + 44*s, y + 58*s], fill=face)                                  # face
    for k in range(-3, 4):                                                                          # wig stripes
        d.line([(x + k*24*s, y + 24*s), (x + k*28*s, y + 116*s)], fill=tuple(max(0, c - 18) for c in fill[:3]) + (255,), width=max(1, int(4*s)))

def make_quote(text, hl):
    fs = 34
    while font(MONO, fs*R).getbbox(text)[2] / R > 620 and fs > 20: fs -= 1
    f = font(MONO, fs*R); tw = f.getbbox(text)[2]; pw, ph = int(tw + 90*R), int(110*R)
    def strip(highlight):
        p = Image.new("RGBA", (pw, ph), (0, 0, 0, 0)); d = ImageDraw.Draw(p)
        r = np.random.default_rng(len(text))
        top = [(x, int(r.uniform(0, 7*R))) for x in range(0, pw + 1, int(14*R))]; bot = [(x, ph - int(r.uniform(0, 7*R))) for x in range(pw, -1, -int(14*R))]
        d.polygon(top + bot, fill=(236, 229, 212, 255))
        if highlight and hl and hl in text:
            x0 = 45*R + f.getbbox(text[:text.index(hl)])[2]; x1 = 45*R + f.getbbox(text[:text.index(hl) + len(hl)])[2]
            d.rectangle([x0 - 6*R, 30*R, x1 + 6*R, 82*R], fill=(226, 74, 60, 92))
        d.text((45*R, 33*R), text, font=f, fill=(34, 30, 28))
        return p
    hx = (45*R + f.getbbox(text[:text.index(hl)])[2] - 6*R, 45*R + f.getbbox(text[:text.index(hl) + len(hl)])[2] + 6*R) if hl and hl in text else None
    return shadowed(strip(False)), (pw / R, ph / R), shadowed(strip(True)), hx

BAY_LL = {'nineveh': (43.153, 36.359), 'mosul': (43.153, 36.359), 'nimrud': (43.33, 36.10), 'ashur': (43.26, 35.46),
          'arbela': (44.01, 36.19), 'babylon': (44.42, 32.54), 'borsippa': (44.34, 32.39), 'ecbatana': (48.52, 34.80),
          'zagros_pass': (46.2, 35.3)}
BAY_BOX = (38.6, 49.6, 31.2, 37.9)
def bay_xy(lon, lat, wworld=640, hworld=500):
    lo0, lo1, la0, la1 = BAY_BOX
    return ((lon - lo0) / (lo1 - lo0) * wworld, (la1 - lat) / (la1 - la0) * hworld)
THEBES_PTS = {k: bay_xy(*v) for k, v in BAY_LL.items()}          # name kept: the model looks for map points here
_RIV = None
def rivers():
    """Tigris and Euphrates centrelines (Natural Earth 1:10m). Modern courses: shown as such on the map."""
    global _RIV
    if _RIV is None:
        g = json.load(open('/home/user/mapdata/ne/rivers.geojson')); _RIV = []
        for f in g['features']:
            n = f['properties'].get('name') or ''
            if n in ('Tigris', 'Euphrates', 'Shatt al Arab'):
                geom = f['geometry']; lines = geom['coordinates'] if geom['type'] == 'MultiLineString' else [geom['coordinates']]
                for ln in lines: _RIV.append((n, ln))
    return _RIV
def make_thebes_map():
    wworld, hworld = 640, 500; pw, ph = int(wworld*R), int(hworld*R)
    p = Image.new("RGBA", (pw, ph), (170, 186, 186, 255)); d = ImageDraw.Draw(p, "RGBA")
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from make_maps import LAND
    for poly in LAND:
        for i, ring in enumerate(poly):
            if not any(BAY_BOX[0] - 3 < x < BAY_BOX[1] + 3 and BAY_BOX[2] - 3 < y < BAY_BOX[3] + 3 for x, y in ring[::3] or ring): continue
            pts = [(bay_xy(x, y)[0]*R, bay_xy(x, y)[1]*R) for x, y in ring]
            d.polygon(pts, fill=(170, 186, 186, 255) if i else (231, 220, 194, 255))
            d.line(pts + [pts[0]], fill=(110, 120, 120), width=int(2*R))
    # Zagros foothills: hatching along the north-east
    for k in range(26):
        lo, la = 44.6 + k * .19, 37.4 - k * .16
        x, y = bay_xy(lo, la); d.line([(x*R, y*R), ((x + 9)*R, (y - 12)*R)], fill=(150, 130, 100), width=int(2*R))
    for n, ln in rivers():
        pts = [(bay_xy(x, y)[0]*R, bay_xy(x, y)[1]*R) for x, y in ln]
        d.line(pts, fill=(96, 138, 150), width=int(3*R), joint='curve')
    fm = font(MONO, 15*R); fs = font(MONO, 12*R); ink = (40, 30, 22)
    lab = {'nineveh': ('NINEVEH', 1, -4), 'nimrud': ('NIMRUD', 1, 0), 'ashur': ('ASSUR', 1, 0), 'arbela': ('ARBELA', 1, -2),
           'babylon': ('BABYLON', 1, -6), 'borsippa': ('BORSIPPA', -1, 6), 'ecbatana': ('ECBATANA', -1, 0)}
    for k, (txt, side, dy) in lab.items():
        x, y = THEBES_PTS[k]
        d.rectangle([(x - 5)*R, (y - 5)*R, (x + 5)*R, (y + 5)*R], fill=(52, 38, 26))
        tx = x + 12 if side > 0 else x - 12 - fm.getbbox(txt)[2]/R
        d.text((tx*R, (y - 9 + dy)*R), txt, font=fm, fill=ink)
    x, y = THEBES_PTS['nineveh']; d.text(((x + 12)*R, (y + 9)*R), "(MOSUL)", font=fs, fill=(90, 76, 60))
    for txt, lo, la in (('ASSYRIA', 42.2, 35.9), ('BABYLONIA', 44.9, 31.9), ('LAND OF THE MEDES', 46.9, 35.6), ('ZAGROS', 46.3, 36.6), ('SYRIAN DESERT', 39.2, 34.0)):
        x, y = bay_xy(lo, la); d.text((x*R, y*R), txt, font=font(MONO, 13*R), fill=(110, 92, 70))
    for txt, lo, la in (('TIGRIS', 43.9, 34.6), ('EUPHRATES', 41.3, 34.55)):
        x, y = bay_xy(lo, la); d.text((x*R, y*R), txt, font=font(MONO, 12*R), fill=(70, 108, 120))
    d.text((24*R, 14*R), "ASSYRIA AND BABYLONIA", font=font(SERIF, 30*R), fill=ink)
    d.text((24*R, 50*R), "7TH CENTURY B.C.  -  RIVERS SHOWN IN THEIR MODERN COURSES", font=font(MONO, 11*R), fill=(80, 66, 52))
    d.line([(600*R, 30*R), (600*R, 80*R)], fill=ink, width=int(3*R)); d.text((592*R, 84*R), "N", font=font(MONO, 18*R), fill=ink)
    km = 100 / ((BAY_BOX[1] - BAY_BOX[0]) * 92.0) * 640                         # ~92 km per degree of longitude at 34 N
    d.line([(470*R, 470*R), ((470 + km)*R, 470*R)], fill=ink, width=int(3*R)); d.text((470*R, 476*R), "100 KM", font=font(MONO, 12*R), fill=ink)
    return shadowed(p), (wworld, hworld)

def make_suspect(name, role):
    wworld, hworld = 360, 470; pw, ph = int(wworld*R), int(hworld*R)
    p = Image.new("RGBA", (pw, ph), (232, 224, 204, 255)); d = ImageDraw.Draw(p)
    d.rectangle([20*R, 20*R, pw - 20*R, 290*R], fill=(58, 54, 48))
    sil = Image.new("RGBA", (pw, int(270*R)), (0, 0, 0, 0)); silhouette(ImageDraw.Draw(sil), pw/2, 110*R, R*0.62, (112, 106, 96, 255))
    p.alpha_composite(sil.crop((int(20*R), 0, pw - int(20*R), int(270*R))), (int(20*R), int(20*R)))
    d.text((pw/2, 125*R), "?", font=font(SERIF, 90*R), fill=(58, 54, 48), anchor="mm")
    d.text((26*R, 300*R), "NAME:", font=font(MONO, 18*R), fill=(90, 80, 70))
    f = font(SERIF, 44*R)
    while f.getbbox(name)[2] > pw - 52*R: f = font(SERIF, f.size * 0.92)
    d.text((26*R, 322*R), name, font=f, fill=(30, 26, 22))
    fr = font(MONO, 19*R); words, lines, cur = role.split(), [], ''
    for w_ in words:
        if fr.getbbox((cur + ' ' + w_).strip())[2] > pw - 52*R: lines.append(cur); cur = w_
        else: cur = (cur + ' ' + w_).strip()
    lines.append(cur)
    for i, l in enumerate(lines[:3]): d.text((26*R, (390 + 24*i)*R), l, font=fr, fill=(60, 54, 48))
    d.rounded_rectangle([pw - 70*R, -6, pw - 40*R, 60*R], radius=8, outline=(150, 150, 150), width=int(4*R))   # paperclip
    return shadowed(p), (wworld, hworld)

def make_diagram(kind):
    wworld, hworld = 560, 460; pw, ph = int(wworld*R), int(hworld*R)
    p = Image.new("RGBA", (pw, ph), (16, 22, 26, 255)); d = ImageDraw.Draw(p)
    for x in range(0, pw, int(20*R)): d.line([(x, 0), (x, ph)], fill=(24, 34, 40), width=1)
    for y in range(0, ph, int(20*R)): d.line([(0, y), (pw, y)], fill=(24, 34, 40), width=1)
    lab = (150, 170, 175); fs = font(MONO, 20*R); ln = (190, 210, 215)
    def tb(x, y, txt, col=(255, 255, 255), f=None):
        f = f or fs; w_ = f.getbbox(txt)[2]; d.rectangle([x - 6*R, y - 4*R, x + w_ + 6*R, y + f.size + 4], fill=(16, 22, 26)); d.text((x, y), txt, font=f, fill=col)
    if kind == 'tablet':
        d.text((24*R, 20*R), "A CLAY TABLET (SCHEMATIC)", font=font(MONO, 18*R), fill=lab)
        d.rounded_rectangle([70*R, 70*R, 330*R, 400*R], radius=int(26*R), fill=(150, 118, 84), outline=(210, 180, 140), width=int(3*R))
        for row in range(9):                                            # rows of wedges
            yy = 100 + row * 32
            for k in range(7):
                xx = 92 + k * 32 + (row % 2) * 6
                h_ = 10 + ((row * 7 + k * 3) % 3) * 3
                d.polygon([(xx*R, yy*R), ((xx + 14)*R, (yy + 2)*R), ((xx + 2)*R, (yy + h_)*R)], fill=(96, 70, 46))
            d.line([(84*R, (yy + 24)*R), (316*R, (yy + 24)*R)], fill=(130, 100, 70), width=1)
        d.rectangle([84*R, 360*R, 316*R, 388*R], outline=RED, width=int(3*R))
        d.line([(420*R, 120*R), (300*R, 230*R)], fill=(220, 200, 150), width=int(9*R))          # reed stylus
        d.polygon([(300*R, 230*R), (312*R, 214*R), (318*R, 226*R)], fill=(220, 200, 150))
        tb(350*R, 96*R, "REED STYLUS"); tb(350*R, 250*R, "WEDGE-SHAPED"); tb(350*R, 276*R, "MARKS = CUNEIFORM")
        tb(350*R, 360*R, "COLOPHON:", RED); tb(350*R, 386*R, "OWNER'S NOTE")
        tb(70*R, 420*R, "c. 8-15 CM ACROSS  -  WRITTEN ON BOTH SIDES", lab)
    elif kind == 'decipher':
        d.text((24*R, 20*R), "1857: ONE INSCRIPTION, FOUR TRANSLATORS", font=font(MONO, 18*R), fill=lab)
        names = ['RAWLINSON', 'HINCKS', 'TALBOT', 'OPPERT']
        for i, n in enumerate(names):
            x = 40 + i * 128
            d.rectangle([x*R, 110*R, (x + 112)*R, 250*R], outline=ln, width=int(3*R))
            for k in range(5): d.line([((x + 12)*R, (140 + k*20)*R), ((x + 100 - (k % 2)*20)*R, (140 + k*20)*R)], fill=(120, 140, 145), width=int(2*R))
            d.text(((x + 56)*R, 90*R), n, font=font(MONO, 16*R), fill=(230, 230, 230), anchor="mm")
            d.line([((x + 56)*R, 256*R), (280*R, 330*R)], fill=ln, width=int(2*R))
        d.rectangle([150*R, 330*R, 410*R, 390*R], outline=RED, width=int(4*R))
        d.text((280*R, 360*R), "SEALED - COMPARED", font=font(MONO, 20*R), fill=(240, 240, 240), anchor="mm")
        tb(90*R, 410*R, "THE TRANSLATIONS AGREED", (255, 255, 255))
    elif kind == 'joins':
        d.text((24*R, 20*R), "JOINING FRAGMENTS (SCHEMATIC)", font=font(MONO, 18*R), fill=lab)
        pieces = [[(60, 90), (200, 80), (215, 170), (150, 230), (70, 200)], [(215, 170), (200, 80), (330, 95), (320, 200), (250, 240)],
                  [(70, 200), (150, 230), (160, 330), (80, 360)], [(150, 230), (250, 240), (300, 340), (160, 330)]]
        off = [(-20, -10), (24, -14), (-26, 20), (30, 26)]
        for i, (pc, (ox, oy)) in enumerate(zip(pieces, off)):
            pts = [((x + ox)*R, (y + oy)*R) for x, y in pc]
            d.polygon(pts, fill=(150, 118, 84), outline=(210, 180, 140))
            cx = sum(x for x, _ in pc) / len(pc) + ox; cy = sum(y for _, y in pc) / len(pc) + oy
            for k in range(3): d.line([((cx - 30)*R, (cy - 14 + k*12)*R), ((cx + 26)*R, (cy - 14 + k*12)*R)], fill=(96, 70, 46), width=int(3*R))
        for a, b in ((0, 1), (0, 2), (1, 3), (2, 3)):
            ca = [sum(c) / len(pieces[a]) for c in zip(*pieces[a])]; cb = [sum(c) / len(pieces[b]) for c in zip(*pieces[b])]
            d.line([((ca[0] + off[a][0])*R, (ca[1] + off[a][1])*R), ((cb[0] + off[b][0])*R, (cb[1] + off[b][1])*R)], fill=RED, width=int(3*R))
        tb(360*R, 120*R, "PHOTOS + TEXT", (255, 255, 255)); tb(360*R, 150*R, "OF EACH PIECE")
        tb(360*R, 210*R, "ALGORITHM", RED); tb(360*R, 240*R, "SUGGESTS"); tb(360*R, 270*R, "MATCHES")
        tb(360*R, 330*R, "EXPERTS"); tb(360*R, 360*R, "CONFIRM")
    paper = Image.new("RGBA", (pw + int(28*R), ph + int(28*R)), (234, 227, 210, 255)); paper.paste(p, (int(14*R), int(14*R)))
    return shadowed(paper), (wworld + 28, hworld + 28)

def make_stamp(text):
    f = font(SERIF, 110*R); tw = f.getbbox(text)[2] + 60*R; th = 160*R
    c = Image.new("RGBA", (int(tw), int(th)), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
    d.rectangle([6*R, 6*R, tw-6*R, th-6*R], outline=RED+(235,), width=int(9*R))
    d.text((30*R, 10*R), text, font=f, fill=RED+(235,))
    a = np.array(c); noise = rng.random(a.shape[:2]) > .22; a[..., 3] = a[..., 3] * noise
    return cv2.cvtColor(a, cv2.COLOR_RGBA2BGRA)

# ------------------------------------------------------------------ board background (map of Egypt)
def zone_rect(i):
    c, r = i % COLS, i // COLS
    x0, y0 = MARG + c * ZW, MARG + r * ZH
    return (x0, y0, x0 + ZW, y0 + ZH)

LON0, LON1, LAT0, LAT1 = 36.4, 50.4, 31.3, 36.7
def geo(lon, lat):
    return ((lon - LON0) / (LON1 - LON0) * WW, (LAT1 - lat) / (LAT1 - LAT0) * WH)

def build_bg(scale=1.0):
    cache = os.path.join(B, f'bg_{scale}.png')
    if os.path.exists(cache): return cv2.imread(cache)
    w, h = int(WW*scale), int(WH*scale)
    bg = np.zeros((h, w, 3), np.float32) + np.array([42, 40, 22], np.float32)
    n = cv2.resize(rng.random((max(2, h//40), max(2, w//40))).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    bg += (n[..., None] - .5) * 14
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from make_maps import LAND
    q = 4; mask = Image.new('L', (w // q, h // q), 0); md = ImageDraw.Draw(mask)
    for poly in LAND:
        for i, ring in enumerate(poly):
            pts = [(geo(x, y)[0]*scale/q, geo(x, y)[1]*scale/q) for x, y in ring]
            if len(pts) > 2 and any(-200 < p[0] < w/q + 200 and -200 < p[1] < h/q + 200 for p in pts[::5] or pts):
                md.polygon(pts, fill=0 if i else 255)
    m = cv2.resize(np.array(mask, np.float32) / 255, (w, h), interpolation=cv2.INTER_CUBIC)
    m = cv2.GaussianBlur(m, (0, 0), 3 * scale + 1)
    land, sea = np.array([66, 66, 44], np.float32), np.array([42, 40, 22], np.float32)
    bg = bg + (land - sea) * m[..., None]
    edge = np.abs(cv2.Laplacian(m, cv2.CV_32F)); edge = np.clip(edge * 40, 0, 1)
    bg += edge[..., None] * np.array([40, 44, 30], np.float32)
    for n_, ln_ in rivers():                                                              # the two rivers, faint on the board
        pts = np.array([[geo(x, y)[0]*scale, geo(x, y)[1]*scale] for x, y in ln_], np.int32)
        cv2.polylines(bg, [pts], False, (74, 70, 46), max(2, int(14*scale)), cv2.LINE_AA)
    for g in range(0, w, int(250*scale)): bg[:, g:g+2] += 6
    for g in range(0, h, int(250*scale)): bg[g:g+2, :] += 6
    img = Image.fromarray(cv2.cvtColor(np.clip(bg, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(img)
    lab = (150, 160, 130)
    for name, lon, lat in [('NINEVEH', 43.25, 36.45), ('BABYLON', 44.5, 32.6), ('ASSUR', 43.35, 35.5), ('NIMRUD', 43.42, 36.15),
                           ('TIGRIS', 44.3, 34.2), ('EUPHRATES', 40.9, 34.9), ('ZAGROS', 46.6, 35.9), ('SYRIAN DESERT', 38.3, 33.4),
                           ('ASSYRIA', 42.1, 36.3), ('BABYLONIA', 45.3, 32.0), ('LAND OF THE MEDES', 47.6, 35.2)]:
        x, y = geo(lon, lat); d.text((x*scale, y*scale), name, font=font(MONO, 60*scale), fill=lab)
    for i, z in enumerate(ZONES):
        x0, y0, x1, y1 = zone_rect(i)
        d.text(((x0 + 60)*scale, (y0 + 40)*scale), ZONE_TITLES[z], font=font(MONO, 90*scale), fill=(160, 168, 140))
        d.line([((x0 + 60)*scale, (y0 + 150)*scale), ((x0 + 900)*scale, (y0 + 150)*scale)], fill=(150, 160, 130), width=max(1, int(3*scale)))
    out = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    cv2.imwrite(cache, out)
    return out

# ------------------------------------------------------------------ timeline -> board model
TL = json.load(open(os.path.join(B, 'timeline.json')))
DUR = TL['total']

def kv(args):
    pos, opt = [], {}
    for a in args:
        if re.match(r'^[a-z]+=', a): k, v = a.split('=', 1); opt[k] = v
        else: pos.append(a)
    return pos, opt

ITEMS, BYNAME, TAGS, LINES, ELLS, STAMPS, OVERLAYS, KEYS, NETWORKS = [], {}, [], [], [], [], [], [], []
ROUTES = []
VINTAGE = None
FILMS, LOUPES = [], []

def layout_slots(zi):
    x0, y0, x1, y1 = zone_rect(zi)
    cols, rows = 6, 4
    sw, sh = ZW / cols, (ZH - 260) / rows
    order = [(1, 1), (2, 1), (1, 2), (2, 2), (3, 1), (3, 2), (4, 1), (4, 2), (0, 1), (0, 2), (5, 1), (5, 2),
             (1, 0), (2, 0), (3, 0), (4, 0), (1, 3), (2, 3), (3, 3), (4, 3), (0, 0), (5, 0), (0, 3), (5, 3)]
    r = np.random.default_rng(zi * 31 + 5)
    return [(x0 + sw*(c + .5) + r.uniform(-60, 60), y0 + 260 + sh*(rr + .5) + r.uniform(-50, 50), r.uniform(-6, 6)) for c, rr in order]

WORDS = json.load(open(os.path.join(B, 'words.json'))) if os.path.exists(os.path.join(B, 'words.json')) else []
def _clean(w): return re.sub(r'[^a-z0-9]', '', w.lower())

def trig(ev, opt, default):
    if 'on' in opt and 's' in ev and ev['s'] < len(TL['sentences']) and WORDS:
        snt = TL['sentences'][ev['s']]; key = _clean(opt['on'])
        for w in WORDS:
            if snt['start'] - .4 <= w['s'] <= snt['end'] + .4 and _clean(w['w']).startswith(key[:max(3, len(key) - 1)]):
                return w['s'] + .05
    return _trig_chars(ev, opt, default)

def _trig_chars(ev, opt, default):
    """time of the event: on=word places it on that word of the sentence"""
    if 'on' in opt and 's' in ev and ev['s'] < len(TL['sentences']):
        snt = TL['sentences'][ev['s']]; txt = snt['text'].lower(); i = txt.find(opt['on'].lower())
        if i >= 0: return snt['start'] + (snt['end'] - snt['start']) * i / max(1, len(txt)) + .1
    return ev['t'] + default

def loc(it, key):
    if key and it.get('pts') and key in it['pts']:
        x, y = it['pts'][key]; return (it['c'][0] - it['size'][0]/2 + x, it['c'][1] - it['size'][1]/2 + y)
    return None

NAMES = {'nineveh': 'NINEVEH', 'ashurbanipal': 'ASHURBANIPAL', 'assyria': 'ASSYRIA', 'assyrian': 'ASSYRIA', 'babylon': 'BABYLON',
         'mosul': 'MOSUL', 'tigris': 'TIGRIS', 'nimrud': 'NIMRUD', 'assur': 'ASSUR', 'medes': 'THE MEDES', 'cyaxares': 'CYAXARES',
         'nabopolassar': 'NABOPOLASSAR', 'layard': 'LAYARD', 'rassam': 'RASSAM', 'kuyunjik': 'KUYUNJIK', 'sennacherib': 'SENNACHERIB',
         'smith': 'GEORGE SMITH', 'gilgamesh': 'GILGAMESH', 'utnapishtim': 'UTNAPISHTIM', 'gladstone': 'GLADSTONE', 'aleppo': 'ALEPPO',
         'esarhaddon': 'ESARHADDON', 'munich': 'MUNICH', 'borsippa': 'BORSIPPA'}
KEYWORDS = {'library', 'clay', 'tablets', 'fire', 'omens', 'liver', 'demons', 'curse', 'confiscation', 'siege', 'chronicle', 'skeletons',
            'arrowheads', 'fragments', 'flood', 'boat', 'dove', 'raven', 'clothes', 'expedition', 'video', 'tunnels', 'algorithm',
            'wedge', 'reed', 'scribes', 'wax', 'baked', 'kiln', 'ruins', 'mound', 'night', 'lion', 'engraver', 'evidence'}
ORD = {}
POPS = []
def build_pops():
    blocked = [(o['t0'], o['t0'] + o['dur'] + .3) for o in OVERLAYS if o['kind'] in ('year', 'thesis', 'end_open', 'end', 'open', 'counter', 'chapter')]
    if VINTAGE: blocked.append((VINTAGE[0] - .3, VINTAGE[1] + .3))
    for F in FILMS: blocked.append((F['t0'] - .3, F['t1'] + .3))
    import cutaways as CW_
    for c_ in CW_.CUTS: blocked.append((c_['t0'] - .3, c_['t1'] + .3))
    last_t, recent = -9, {}
    for i, w in enumerate(WORDS):
        c = _clean(w['w']); t = w['s']
        if any(a <= t <= b for a, b in blocked) or t - last_t < 1.05: continue
        txt, kind = None, 'mono'
        if c not in NAMES:
            for k in NAMES:
                if len(k) >= 6 and len(c) >= 5 and c[:5] == k[:5]: c = k; break
            if c in ('ramses', 'rameses', 'ramesis'): c = 'ramesses'
        if c in NAMES:
            if c == 'ramesses':
                n1 = _clean(WORDS[i + 1]['w']) if i + 1 < len(WORDS) else ''
                nx = _clean(WORDS[i + 2]['w']) if i + 2 < len(WORDS) and n1 == 'the' else ''
                if n1 in ('ii', 'iii', 'iv', 'ix'): txt = 'RAMESSES ' + n1.upper()
                else: txt = 'RAMESSES ' + ORD[nx] if nx in ORD else 'RAMESSES'
            else: txt = NAMES[c]
            kind = 'serif'
        elif (re.fullmatch(r'\d{2,5}', c) and not c.startswith('0')) or re.fullmatch(r'[1-9]\d*(st|nd|rd|th)', c):
            txt, kind = c.upper(), 'serif'
        elif c in KEYWORDS:
            txt = c.upper()
        if not txt or t - recent.get(txt, -99) < 25: continue
        POPS.append(dict(t=t, text=txt, kind=kind, n=len(POPS))); last_t = t; recent[txt] = t

def build_model():
    global VINTAGE
    zi, slots, used = 0, layout_slots(0), set()
    last_item = None
    for ev in TL['events']:
        t, d = ev['t'], ev['d']; cmd, args = d[0], d[1:]
        pos, opt = kv(args)
        if cmd == 'zone':
            zi = ZONES.index(pos[0]); slots = layout_slots(zi)
            sx, sy, _ = slots[0]; KEYS.append((t, (sx, sy, 1000, 760), 1.7))      # travel straight to where the first card lands
            if pos[0] != 'open':
                num, _, name = ZONE_TITLES[pos[0]].partition('  ')
                OVERLAYS.append(dict(kind='chapter', t0=t, a=name, b=num))
            continue
        if cmd == 'open':
            OVERLAYS.append(dict(kind='open', t0=0.0, a=pos[0], b='')); continue
        if cmd == 'push':
            it = BYNAME[pos[0]]; KEYS.append((t, (it['c'][0], it['c'][1], it['size'][0]*.78, it['size'][1]*.78), 1.0)); continue
        if cmd == 'counter':
            OVERLAYS.append(dict(kind='counter', t0=trig(ev, opt, .2), a=pos[0], b=pos[1] if len(pos) > 1 else '')); continue
        if cmd in ('card', 'note', 'suspect', 'diagram', 'quote', 'map'):
            if cmd == 'card':
                rec = find_image(pos[0], used); used.add(rec['id'])
                img, size = make_card(os.path.join(IMGDIR, rec['file']), min(float(opt.get('w', 520)), 600), rec=rec, nocut=opt.get('cut') == '0')
                credit = rec
            elif cmd == 'note':
                img, size = make_paper(pos[0].split('|')); credit = None
            elif cmd == 'suspect':
                img, size = make_suspect(pos[1], pos[2]); opt['as'] = pos[0]; credit = None
            elif cmd == 'quote':
                img, size, hlimg, hx = make_quote(pos[0], opt.get('hl')); credit = None
            elif cmd == 'map':
                img, size = make_thebes_map(); credit = None
            else:
                img, size = make_diagram(pos[0]); credit = None
            cx, cy, rot = slots.pop(0)
            if cmd == 'quote': rot = rot * .4
            it = dict(img=img, c=(cx, cy), rot=rot, t0=t + .25, size=size, zone=zi, credit=credit, kind=cmd)
            if cmd == 'quote' and hx:
                it.update(hlimg=hlimg, hx=hx, ht=max(t + .9, trig(ev, opt, .9)))
            if cmd == 'map': it['pts'] = THEBES_PTS
            ITEMS.append(it); last_item = it
            if 'as' in opt: BYNAME[opt['as']] = it
            KEYS.append((t, (cx, cy, size[0], size[1]), .9))
        elif cmd == 'tag':
            it = BYNAME[pos[0]]; TAGS.append(dict(item=it, text=pos[1], t0=trig(ev, opt, .5), zone=it['zone'], at=loc(it, opt.get('at'))))
            if it['zone'] != zi or opt.get('at'): KEYS.append((t, (it['c'][0], it['c'][1], it['size'][0]*1.2, it['size'][1]*1.2), .9))
        elif cmd == 'string':
            a, b = BYNAME[pos[0]], BYNAME[pos[1]]; LINES.append(dict(a=a, b=b, t0=t + .3, du=.8))
            xs = [a['c'][0], b['c'][0]]; ys = [a['c'][1], b['c'][1]]
            KEYS.append((t, ((min(xs) + max(xs))/2, (min(ys) + max(ys))/2, abs(xs[1]-xs[0]) + 600, abs(ys[1]-ys[0]) + 520), .9))
        elif cmd == 'circle':
            it = BYNAME[pos[0]]; at = loc(it, opt.get('at'))
            ELLS.append(dict(item=it, t0=trig(ev, opt, .35), du=.55, at=at))
            KEYS.append((t, (it['c'][0], it['c'][1], it['size'][0]*1.3, it['size'][1]*1.3), .7))
        elif cmd == 'route':
            # animated route on a map: @route <map> a,b,c "LABEL" [dur=3]  (points are named map locations)
            it = BYNAME[pos[0]]; pts = [loc(it, k) for k in pos[1].split(',')]
            ROUTES.append(dict(item=it, pts=pts, t0=trig(ev, opt, .4), du=float(opt.get('dur', 3.0)), label=pos[2] if len(pos) > 2 else ''))
            KEYS.append((t, (it['c'][0], it['c'][1], it['size'][0]*1.12, it['size'][1]*1.12), .8))
        elif cmd == 'stamp':
            it = BYNAME[pos[0]]; STAMPS.append(dict(item=it, img=make_stamp(pos[1]), t0=trig(ev, opt, .45) + .05))
            KEYS.append((t, (it['c'][0], it['c'][1], it['size'][0]*1.25, it['size'][1]*1.25), .6))
        elif cmd == 'network':
            zs = [i for i in ITEMS if i['zone'] == zi]
            if zs:
                xs = [i['c'][0] for i in zs]; ys = [i['c'][1] for i in zs]
                KEYS.append((t, ((min(xs) + max(xs))/2, (min(ys) + max(ys))/2, max(xs) - min(xs) + 900, max(ys) - min(ys) + 800), 1.2))
                NETWORKS.append((t, zi))
        elif cmd in ('year', 'thesis', 'end_open', 'end'):
            OVERLAYS.append(dict(kind=cmd, t0=t, a=pos[0], b=pos[1] if len(pos) > 1 else ''))
        elif cmd == 'vintage':
            VINTAGE = [t, None]
        elif cmd == 'film':
            FILMS.append(dict(t0=t, t1=t + float(opt.get('dur', 7)), scene=pos[0], title=opt.get('title')))
    # vintage ends at the next card event after it starts
    if VINTAGE:
        nxt = [e['t'] for e in TL['events'] if e['t'] > VINTAGE[0] + 1 and e['d'][0] == 'card']
        VINTAGE[1] = min(nxt) if nxt else VINTAGE[0] + 10
    for o in OVERLAYS:
        o['dur'] = {'year': 3.0, 'thesis': 5.0, 'end_open': 4.6, 'end': 7.0, 'open': 6.2, 'counter': 2.8, 'chapter': 2.2}[o['kind']]
        if o['kind'] == 'end': o['dur'] = max(7.0, DUR - o['t0'] + .5)      # hold the end card through the sign-off
    # play overlapping overlays one after another (chapter card, then year card, ...)
    seq = sorted([o for o in OVERLAYS if o['kind'] in ('chapter', 'year', 'thesis', 'counter', 'end_open')], key=lambda o: o['t0'])
    for a_, b_ in zip(seq, seq[1:]):
        if b_['t0'] < a_['t0'] + a_['dur']: b_['t0'] = a_['t0'] + a_['dur'] + .05
    # the first exhibit drops in as the desk lamp comes on; in later chapters, as the chapter card fades
    for it in ITEMS:
        if it['zone'] == 0: it['t0'] = min(it['t0'], 6.1); break
    for o in OVERLAYS:
        if o['kind'] != 'chapter': continue
        zi_ = ZONES.index([z for z in ZONES if ZONE_TITLES[z].endswith(o['a'])][0])
        first = [it for it in ITEMS if it['zone'] == zi_]
        if first: first[0]['t0'] = min(first[0]['t0'], o['t0'] + o['dur'] - .4)
    yi = 0
    for o in sorted(OVERLAYS, key=lambda o: o['t0']):
        if o['kind'] == 'year': o['tl'] = yi; yi += 1
    lastl = -99
    for it in ITEMS:
        if it['kind'] != 'card': continue
        nk = [k[0] for k in KEYS if k[0] > it['t0'] + .2]; gap = (min(nk) if nk else DUR) - it['t0']
        if gap > 3.6 and it['t0'] - lastl > 16 and not any(F['t0'] - 1 < it['t0'] < F['t1'] for F in FILMS):
            LOUPES.append(dict(item=it, t0=it['t0'] + 1.0, du=min(gap - 1.3, 3.4))); lastl = it['t0']
    import cutaways as CW_; CW_.init(sys.modules[__name__])
    build_pops()
    # mip levels
    for it in ITEMS:
        if 'hlimg' in it: it['hlmips'] = [it['hlimg'], cv2.resize(it['hlimg'], None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA), cv2.resize(it['hlimg'], None, fx=.25, fy=.25, interpolation=cv2.INTER_AREA)]
        it['mips'] = [it['img'], cv2.resize(it['img'], None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA),
                      cv2.resize(it['img'], None, fx=.25, fy=.25, interpolation=cv2.INTER_AREA)]

# ------------------------------------------------------------------ camera
def frame_box(box):
    cx, cy, bw, bh = box
    z = min(W * .64 / max(bw, 1), H * .64 / max(bh, 1))
    return (cx, cy, clamp(z, .30, 1.45))

def build_cam():
    keys = [(0.0, *frame_box(KEYS[0][1]), 0.0)]
    rr = np.random.default_rng(3)
    for i, (t, box, mv) in enumerate(KEYS):
        tgt = frame_box(box)
        prev = keys[-1]
        if t <= prev[0] + .05: continue
        # drift: slow push-in from the previous target until this move starts
        keys.append((t, prev[1], prev[2], prev[3] * 1.05, prev[4]))
        rot = (1 if i % 2 else -1) * rr.uniform(1.2, 3.2)
        nxt = [k[0] for k in KEYS[i + 1:] if k[0] > t + .3]
        keys.append((max(t + .35, min(t + mv, nxt[0] - .05)) if nxt else t + mv, tgt[0], tgt[1], tgt[2], rot))
    last = keys[-1]; keys.append((DUR, last[1], last[2], last[3] * 1.05, last[4]))
    # fill every hold longer than ~3.2s with deliberate reframes (push / slide / pull) every ~2.2s
    PAT = [(1.16, .10, -.06), (1.0, -.12, .05), (1.24, .0, .08), (.94, .08, -.08), (1.12, -.08, -.04)]
    out, pi = [keys[0]], 0
    for a, b in zip(keys, keys[1:]):
        if b[0] - a[0] > 3.4 and a[3] > .34:
            tt, base = a[0] + 1.3, a
            while b[0] - tt > 2.0:
                zf, ox, oy = PAT[pi % len(PAT)]; pi += 1
                span = W / base[3]
                out.append((tt, *cam_at(out, tt)))
                out.append((tt + .9, base[1] + ox*span*.35, base[2] + oy*span*.25, base[3]*zf, base[4] + (pi % 3 - 1)*.6))
                tt += 2.2
        out.append(b)
    out.sort(key=lambda k: k[0])
    return out

def cam_at(keys, t):
    a = keys[-1]
    return (a[1], a[2], a[3], a[4])
K = []
def cam(t):
    for i in range(len(K) - 1):
        a, b = K[i], K[i + 1]
        if a[0] <= t <= b[0]:
            u = ease((t - a[0]) / max(1e-6, b[0] - a[0]))
            lz = math.log(a[3]) + (math.log(b[3]) - math.log(a[3])) * u
            dist = math.hypot(b[1] - a[1], b[2] - a[2])
            if dist > 900:                                   # flight arc: pull back wide on long travel, push in on arrival
                zmid = clamp(W * 1.1 / dist, .28, 1.0)
                lmid = math.log(a[3]) + (math.log(b[3]) - math.log(a[3])) * .5
                if math.log(zmid) < lmid: lz += (math.log(zmid) - lmid) * math.sin(math.pi * u)
            return [a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, math.exp(lz), a[4] + (b[4] - a[4]) * u]
    return list(K[-1][1:])

def to_screen(p, C):
    cx, cy, z, r = C; a = math.radians(-r)
    x, y = (p[0]-cx)*z, (p[1]-cy)*z
    return (x*math.cos(a) - y*math.sin(a) + W/2, x*math.sin(a) + y*math.cos(a) + H/2)

def world_M(C, scale=1.0):
    cx, cy, z, r = C; a = math.radians(-r); c, s = math.cos(a)*z/scale, math.sin(a)*z/scale
    cxs, cys = cx*scale, cy*scale
    return np.array([[c, -s, W/2 - c*cxs + s*cys], [s, c, H/2 - s*cxs - c*cys]], np.float32)

def blend_roi(frame, bgra, M):
    h, w = bgra.shape[:2]
    pts = M @ np.array([[0, w, 0, w], [0, 0, h, h], [1, 1, 1, 1]], np.float32)
    x0, y0 = max(0, int(pts[0].min()) - 2), max(0, int(pts[1].min()) - 2)
    x1, y1 = min(W, int(pts[0].max()) + 3), min(H, int(pts[1].max()) + 3)
    if x1 <= x0 or y1 <= y0: return
    M2 = M.copy(); M2[0, 2] -= x0; M2[1, 2] -= y0
    wpd = cv2.warpAffine(bgra, M2, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    a = wpd[..., 3:4].astype(np.float32) / 255
    roi = frame[y0:y1, x0:x1]
    roi[:] = roi * (1 - a) + wpd[..., :3] * a

def item_M(it, C, img, extra=1.0, dy=0.0, rot=None, sx=1.0, sy=1.0, dx=0.0):
    h, w = img.shape[:2]; scale_px = it['img'].shape[1] / w
    rr = math.radians(it['rot'] if rot is None else rot); k = extra * scale_px / R
    c, s = math.cos(rr)*k, math.sin(rr)*k
    L = np.array([[c*sx, -s*sy, it['c'][0] + dx - (c*sx*w/2 - s*sy*h/2)], [s*sx, c*sy, it['c'][1] + dy - (s*sx*w/2 + c*sy*h/2)], [0, 0, 1]])
    return (np.vstack([world_M(C), [0, 0, 1]]) @ L)[:2].astype(np.float32)

# ------------------------------------------------------------------ overlays
def wobble_ellipse(c, rx, ry, frac, C, seed=0):
    n = int(90*frac)+2; pts = []
    for i in range(n):
        th = -2.3 + 2*math.pi*1.08*(i/89)
        jit = 1 + .04*math.sin(i*.7+seed)
        pts.append(to_screen((c[0]+rx*jit*math.cos(th), c[1]+ry*jit*math.sin(th)), C))
    return pts

def zone_now(t):
    zs = [(e['t'], ZONES.index(e['d'][1])) for e in TL['events'] if e['d'][0] == 'zone' and e['t'] <= t]
    return zs[-1][1] if zs else 0

def draw_overlays(img, t, C):
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil, "RGBA"); z = C[2]
    for e in ELLS:
        if t < e['t0']: continue
        it = e['item']; rx, ry = it['size'][0]*.62, it['size'][1]*.62; cc = it['c']
        if e.get('at'): cc, rx, ry = e['at'], 62, 42
        pts = wobble_ellipse(cc, rx, ry, clamp((t - e['t0'])/e['du']), C, seed=e['t0'])
        if len(pts) > 1: d.line(pts, fill=RED+(240,), width=max(3, int(7*z)), joint="curve")
    for L in LINES:
        if t < L['t0']: continue
        u = ease((t - L['t0'])/L['du'])
        a = to_screen((L['a']['c'][0], L['a']['c'][1] - L['a']['size'][1]*.35), C)
        b0 = to_screen((L['b']['c'][0], L['b']['c'][1] - L['b']['size'][1]*.35), C)
        b = (a[0]+(b0[0]-a[0])*u, a[1]+(b0[1]-a[1])*u + math.sin(u*math.pi)*25*z)
        d.line([a, b], fill=RED+(230,), width=max(2, int(5*z)))
        for p in (a, b): d.ellipse([p[0]-8, p[1]-8, p[0]+8, p[1]+8], fill=RED+(255,))
    for R_ in ROUTES:
        if t < R_['t0'] or t > R_['t0'] + R_['du'] + 14: continue     # a route belongs to its moment; it fades after ~14 s
        u = ease((t - R_['t0']) / R_['du'])
        P = [to_screen(p, C) for p in R_['pts']]
        # smooth the route (Catmull-Rom through the waypoints) and draw the travelled part as a dashed line
        S_ = []
        for i in range(len(P) - 1):
            p0, p1, p2, p3 = P[max(0, i - 1)], P[i], P[i + 1], P[min(len(P) - 1, i + 2)]
            for k in range(24):
                q = k / 24
                S_.append(tuple(.5 * ((2*p1[j]) + (-p0[j] + p2[j])*q + (2*p0[j] - 5*p1[j] + 4*p2[j] - p3[j])*q*q + (-p0[j] + 3*p1[j] - 3*p2[j] + p3[j])*q**3) for j in (0, 1)))
        S_.append(P[-1]); n = max(2, int(len(S_) * u))
        seg = S_[:n]; lw = max(3, int(6 * z))
        for i in range(0, len(seg) - 1, 2): d.line([seg[i], seg[i + 1]], fill=RED + (235,), width=lw)
        d.ellipse([P[0][0] - 9, P[0][1] - 9, P[0][0] + 9, P[0][1] + 9], fill=RED + (255,))
        if len(seg) >= 2:
            (x0, y0), (x1, y1) = seg[-2], seg[-1]; ang = math.atan2(y1 - y0, x1 - x0); L_ = 20 * max(.8, z)
            tip = [(x1 + math.cos(ang) * 4, y1 + math.sin(ang) * 4), (x1 - math.cos(ang - .45) * L_, y1 - math.sin(ang - .45) * L_), (x1 - math.cos(ang + .45) * L_, y1 - math.sin(ang + .45) * L_)]
            d.polygon(tip, fill=RED + (255,))
        if R_['label'] and u > .35:
            la = int(230 * min(1, (u - .35) / .3)); m = S_[len(S_) // 3]; fl = font(MONO, 26); tw = fl.getbbox(R_['label'])[2]
            y = m[1] + 26                                  # label below the route (map names sit above their points)
            d.rectangle([m[0] - tw / 2 - 10, y, m[0] + tw / 2 + 10, y + 38], fill=(14, 14, 14, la)); d.text((m[0] - tw / 2, y + 3), R_['label'], font=fl, fill=(235, 235, 228, la))
    fm = font(MONO, 30); zn = zone_now(t)
    net = [n for n in NETWORKS if n[0] <= t and n[1] == zn]
    for tg in TAGS:
        t0 = tg['t0']
        if t < t0: continue
        life = 1 - ss((t - t0 - 7)/.5)
        if net and tg['zone'] == zn and t0 < net[-1][0]: life = max(life, ss((t - net[-1][0])/.6))
        if tg['zone'] != zn and t - t0 > 7: life = 0
        if life <= 0: continue
        LA = int(235*life); txt = tg['text']
        n = min(len(txt), int((t - t0)*22)); s = txt[:n]
        if n < len(txt) or (int(t*2.5) % 2 == 0 and t - t0 < 3): s += "_"
        it = tg['item']; p = to_screen(tg['at'] if tg.get('at') else (it['c'][0] - it['size'][0]*.42, it['c'][1] - it['size'][1]*.42), C)
        q = (p[0] - 40, p[1] - 90)
        tw = fm.getbbox(txt + "_")[2]
        if q[0] + tw > W - 20: q = (W - 30 - tw, q[1])
        q = (max(20, q[0]), max(20, q[1]))
        if not (-400 < p[0] < W + 100 and -100 < p[1] < H + 100): continue
        d.line([p, (q[0] + 20, q[1] + 44)], fill=RED+(LA,), width=2)
        d.ellipse([p[0]-6, p[1]-6, p[0]+6, p[1]+6], fill=RED+(LA,))
        d.rectangle([q[0]-10, q[1]-4, q[0]+tw+10, q[1]+44], fill=(14, 14, 14, LA))
        d.text((q[0], q[1]+2), s, font=fm, fill=(235, 235, 228, LA))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

POP_SPOTS = [(150, 860), (1180, 170), (170, 190), (1150, 860)]
def draw_pops(img, t):
    act = [p for p in POPS if p['t'] - .05 <= t < p['t'] + 1.35]
    if not act: return img
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil, "RGBA")
    for p in act:
        u = (t - p['t']); a = ss(u/.12) * (1 - ss((u - 1.05)/.3)); al = int(255*a)
        x, y = POP_SPOTS[p['n'] % 4]; dx = int(28*(1 - ease(u/.25)))
        if p['kind'] == 'serif':
            f = font(SERIF, 100); tw = f.getbbox(p['text'])[2]
            if x + tw > W - 60: x = W - 60 - tw
            d.text((x + dx + 3, y + 4), p['text'], font=f, fill=(0, 0, 0, int(al*.6)))
            d.text((x + dx, y), p['text'], font=f, fill=(244, 238, 226, al))
            uu = ease((u - .12)/.3); d.line([(x + dx, y + 118), (x + dx + tw*uu, y + 118)], fill=RED + (al,), width=8)
        else:
            f = font(MONO, 62); s_ = p['text'][:max(1, int(u*30))]; tw = f.getbbox(p['text'])[2]
            if x + tw > W - 60: x = W - 60 - tw
            d.rectangle([x + dx - 18, y - 10, x + dx + tw + 18, y + 80], fill=(12, 12, 12, int(al*.92)))
            d.rectangle([x + dx - 18, y - 10, x + dx - 9, y + 80], fill=RED + (al,))
            d.text((x + dx, y + 4), s_, font=f, fill=(240, 238, 230, al))
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

CLOCK = [('DAY 1 - 1 PM', 13, '1 PM', 'COLUMN'), ('DAY 1 - 2 PM', 14, '2 PM', 'PUMICE'), ('DAY 2 - 1 AM', 25, '1 AM', 'COLLAPSE'),
         ('DAY 2 - DAWN', 30, 'DAWN', 'DARKNESS'), ('DAY 2 - 7 AM', 31, '7 AM', 'SURGE')]
HIST = [('669 B.C.', -669, '669 B.C.', 'KING'), ('c. 660-631 B.C.', -650, 'c. 650 B.C.', 'LIBRARY'), ('c. 631 B.C.', -631, '631 B.C.', 'DEATH'),
        ('614 B.C.', -614, '614 B.C.', 'ASSUR'), ('612 B.C.', -612, '612 B.C.', 'FALL'), ('1849', 1849, '1849', 'DIGGING'),
        ('1872', 1872, '1872', 'FLOOD TABLET'), ('1876', 1876, '1876', 'SMITH DIES'), ('2015', 2015, '2015', 'DESTRUCTION'), ('2023', 2023, '2023', 'AI JOINS')]
def time_strip(d, o, lt, al):
    """animated strip under each date card: an eruption clock for the two days, otherwise a broken history axis"""
    y = 820; dim = (150, 160, 150, al); cream = (240, 236, 225, al); fm = font(MONO, 22); fb = font(MONO, 20)
    if o['a'].startswith('DAY'):
        marks = CLOCK; xp = lambda h: 300 + (h - 12) / 20 * 1320
        d.line([(xp(12), y), (xp(32), y)], fill=dim, width=3)
        for h in range(12, 33, 2):
            d.line([(xp(h), y - 8), (xp(h), y + 8)], fill=dim, width=2)
        d.text((xp(12) - 20, y + 60), "DAY 1, NOON", font=fb, fill=dim); d.text((xp(24) - 40, y + 60), "MIDNIGHT", font=fb, fill=dim)
        d.text((xp(32) - 80, y + 60), "DAY 2, 8 AM", font=fb, fill=dim)
        key = o['a']
    else:
        marks = HIST
        def xp(v):
            if v < 0: return 300 + (v + 675) / 70 * 430                           # 675-605 B.C.
            if v < 1950: return 860 + (v - 1840) / 45 * 330                       # 1840-1885
            return 1330 + (v - 2008) / 20 * 300                                   # 2008-2028
        for a_, b_ in ((-675, -605), (1840, 1885), (2008, 2028)): d.line([(xp(a_), y), (xp(b_), y)], fill=dim, width=3)
        for gx in (790, 1260):
            for k in range(3): d.line([(gx + 14*k, y + 10), (gx + 14*k + 10, y - 10)], fill=dim, width=2)
        key = o['a'] if any(m[0] == o['a'] for m in HIST) else '612 B.C.'
    idx = [m[0] for m in marks].index(key) if key in [m[0] for m in marks] else 0
    for j, (k_, v, a_, b_) in enumerate(marks):
        x = xp(v); on = j == idx; up = j % 2 == 0
        r_ = 7 if on else 5; d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=cream if on else dim)
        yy = y - 62 if up else y + 18
        d.text((x - fm.getlength(a_)/2, yy), a_, font=fm, fill=cream if on else dim)
        d.text((x - fb.getlength(b_)/2, yy + 26), b_, font=fb, fill=RED + (al,) if on else dim)
    prev = xp(marks[idx - 1][1]) if idx else xp(marks[0][1]) - 120
    u = ease(clamp((lt - .35) / .9)); hx = prev + (xp(marks[idx][1]) - prev) * u
    d.line([(hx, y - 26), (hx, y - 8)], fill=RED + (al,), width=5); d.polygon([(hx - 8, y - 10), (hx + 8, y - 10), (hx, y)], fill=RED + (al,))
    if lt > 1.3:
        rr = 16 * ease(clamp((lt - 1.3) / .3)); x = xp(marks[idx][1]); d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=RED + (al,), width=4)

def text_center(d, y, s, f, fill):
    w = f.getbbox(s)[2]; d.text(((W-w)/2, y), s, font=f, fill=fill)

def screen_overlays(img, t):
    out = img.astype(np.float32)
    for o in OVERLAYS:
        t0, du = o['t0'], o['dur']
        if not (t0 <= t < t0 + du + .4): continue
        if o['kind'] in ('counter', 'year', 'thesis', 'chapter'):          # defocus the board behind the card
            a0 = ss((t - t0)/.3) * (1 - ss((t - (t0 + du - .3))/.4))
            if a0 > .02:
                small = cv2.resize(out, (W//6, H//6), interpolation=cv2.INTER_AREA)
                bl = cv2.resize(cv2.GaussianBlur(small, (0, 0), 3), (W, H), interpolation=cv2.INTER_LINEAR)
                out = out*(1 - a0) + bl*a0
        if o['kind'] == 'open':
            # typed case file on black, then the desk lamp flickers on
            lines = o['a'].split('|'); pil = Image.new('RGB', (W, H), (6, 6, 6)); d = ImageDraw.Draw(pil)
            y = 330; tt = t - .3
            for i, ln in enumerate(lines):
                n = int(clamp(tt / 1.0) * len(ln)) if tt > 0 else 0
                f = font(MONO, 46 if i < 2 else 58); col = (222, 218, 206) if i != 2 else RED
                if i >= 2: f = font(SERIF, 64)
                d.text((260, y), ln[:n] + ('_' if 0 < n < len(ln) and int(t*6) % 2 == 0 else ''), font=f, fill=col)
                tt -= max(.7, len(ln) / 34.0) + .25; y += 70 if i < 2 else 92
                if i == 1: y += 40
            blk = np.array(pil)[..., ::-1].astype(np.float32)
            on = 0.0 if t < 5.4 else (1.0 if t > 6.1 else (1.0 if int((t - 5.4) * 14) % 3 == 1 else .25))
            return np.clip(blk * (1 - on) + out * on, 0, 255).astype(np.uint8)
        if o['kind'] == 'chapter':
            a = ss((t - t0)/.3) * (1 - ss((t - (t0 + du - .35))/.35)); out *= 1 - .5*a
            pil = Image.fromarray(cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil, "RGBA"); al = int(255*a)
            text_center(d, 380, o['b'], font(MONO, 44), (225, 222, 212, al))
            f = font(SERIF, 150); n = min(len(o['a']), int(max(0, t - t0 - .15)*24))
            text_center(d, 450, o['a'][:n], f, (244, 240, 230, al))
            tw = f.getbbox(o['a'])[2]; u = ease((t - t0 - .3)/.5)
            d.line([((W - tw)/2, 640), ((W - tw)/2 + tw*u, 640)], fill=RED + (al,), width=8)
            return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if o['kind'] == 'counter':
            a = ss((t - t0)/.25) * (1 - ss((t - (t0 + du - .3))/.35))
            out *= 1 - .62*a
            out[300:700] *= 1 - .45*a
            pil = Image.fromarray(cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil, "RGBA"); al = int(255*a)
            val = o['a']; m = re.match(r'^(\D*)(\d[\d,]*)(.*)$', val)
            if m:
                num = int(m.group(2).replace(',', '')); u = ease((t - t0)/1.1); cur = int(round(num * u))
                val = m.group(1) + (f'{cur:,}' if ',' in m.group(2) else str(cur)) + m.group(3)
            fb = font(SERIF, 190); wv = fb.getbbox(o['a'])[2]
            d.rectangle([(W - wv)/2 - 50, 560, (W + wv)/2 + 50, 568], fill=RED + (al,))
            d.text(((W - wv)/2, 330), val, font=fb, fill=(244, 240, 230, al))
            text_center(d, 600, o['b'], font(MONO, 46), (225, 222, 212, al))
            return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if o['kind'] == 'year':
            a = ss((t - t0)/.3) * (1 - ss((t - (t0 + du - .3))/.4)); out *= 1 - .5*a
            fl = math.exp(-(t - t0)*5) * a
            yy, xx = np.ogrid[:H, :W]; g = np.exp(-(((xx-W/2)/700)**2 + ((yy-H/2)/400)**2))
            out += (g*fl*120)[..., None] * np.array([40, 120, 230]) / 230
            pil = Image.fromarray(cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil, "RGBA")
            al = int(255*a); f = font(SERIF, 170 if len(o['a']) < 10 else 130)
            n = min(len(o['a']), int(max(0, t - t0 - .15)*18))
            text_center(d, 330, o['b'], font(MONO, 44), (220, 220, 210, al))
            text_center(d, 410, o['a'][:n], f, (240, 236, 225, al))
            d.line([(560, 620), (860, 620)], fill=(200, 200, 190, al), width=2); d.line([(1060, 620), (1360, 620)], fill=(200, 200, 190, al), width=2)
            time_strip(d, o, t - t0, al)
            return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if o['kind'] == 'thesis':
            a = ss((t - t0)/.5) * (1 - ss((t - (t0 + du - .4))/.5)); out *= 1 - .78*a
            pil = Image.fromarray(cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil, "RGBA")
            al = int(255*a); f1 = font(MONO, 50); s1 = o['a']
            n = min(len(s1), int(max(0, t - t0 - .3)*30)); w1 = f1.getbbox(s1)[2]; x1 = (W - w1)/2
            d.text((x1, 380), s1[:n], font=f1, fill=(220, 220, 212, al))
            if t > t0 + 1.0:
                u = ease((t - t0 - 1.0)/.35); d.line([(x1-10, 412), (x1-10+(w1+20)*u, 412)], fill=RED+(al,), width=6)
            if t > t0 + 1.45:
                s2 = o['b']; f2 = font(SERIF, 120 if len(s2) < 14 else (96 if len(s2) < 22 else 76))
                n2 = min(len(s2), int((t - t0 - 1.45)*30)); w2 = f2.getbbox(s2 + ".")[2]
                d.text(((W - w2)/2, 480), s2[:n2], font=f2, fill=(242, 238, 228, al))
                if n2 == len(s2): d.text(((W - w2)/2 + f2.getbbox(s2)[2], 480), ".", font=f2, fill=RED+(al,))
            return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if o['kind'] in ('end_open', 'end'):
            a = ss((t - t0)/.6); fade = 1 - ss((t - (t0 + du - .6))/.6)
            out *= (1 - .88*a)
            pil = Image.fromarray(cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil, "RGBA")
            text_center(d, 400, o['a'], font(SERIF, 120), RED+(int(255*a),))
            text_center(d, 560, o['b'], font(MONO, 40), (220, 220, 212, int(255*a)))
            ob = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
            if t0 < t < t0 + .5:
                r2 = np.random.default_rng(int(t*FPS))
                for k in range(6):
                    y = int(r2.integers(380, 620)); hh = int(r2.integers(8, 30)); sh = int(r2.integers(-60, 60))
                    ob[y:y+hh] = np.roll(ob[y:y+hh], sh, axis=1)
            if o['kind'] == 'end' or fade < 1:
                base = img.astype(np.float32) if o['kind'] == 'end_open' else 0
                return np.clip(ob*fade + (base*(1 - fade) if o['kind'] == 'end_open' else 0), 0, 255).astype(np.uint8)
            return ob
    return np.clip(out, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ vintage insert (night of the conspiracy)
INK = (52, 38, 26); PAPER = (226, 208, 172); MID = (150, 124, 92); DARK = (88, 66, 46); VRED = (178, 40, 32)
vy, vx = np.ogrid[:H, :W]
VIG = (1 - .62*np.clip(((vx-W/2)/(W*.58))**2 + ((vy-H/2)/(H*.58))**2, 0, 1))[..., None].astype(np.float32)
def J(t, k, a=2.0): q = int(t*12); r = np.random.default_rng(q*97 + k); return r.uniform(-a, a)
def wline(d, pts, t, k, fill=INK, w=5):
    d.line([(x+J(t, k+i), y+J(t, k+i+50)) for i, (x, y) in enumerate(pts)], fill=fill, width=w, joint="curve")
def wpoly(d, pts, t, k, fill, outline=INK, w=4):
    pts = [(x+J(t, k+i, 1.5), y+J(t, k+i+50, 1.5)) for i, (x, y) in enumerate(pts)]
    d.polygon(pts, fill=fill); d.line(pts+[pts[0]], fill=outline, width=w)
def figure(d, x, y, t, k, s=1.0, arm=0.0, col=INK):
    """flat side-view Egyptian figure: wig, torso, kilt, legs mid-stride"""
    st = math.sin(t*6 + k) * 18 * s
    wline(d, [(x, y-150*s), (x-10*s + st, y)], t, k+7, col, int(14*s)); wline(d, [(x, y-150*s), (x+10*s - st, y)], t, k+9, col, int(14*s))
    wpoly(d, [(x-30*s, y-330*s), (x+30*s, y-330*s), (x+50*s, y-130*s), (x-42*s, y-130*s)], t, k+1, PAPER, col, int(4*s))   # tunic
    wpoly(d, [(x-26*s, y-330*s), (x+26*s, y-330*s), (x+30*s, y-230*s), (x-30*s, y-230*s)], t, k+2, col, col, 2)          # torso
    d.ellipse([x-26*s+J(t, k), y-392*s+J(t, k+1), x+30*s+J(t, k), y-332*s+J(t, k+1)], fill=col)                        # head
    wpoly(d, [(x-30*s, y-396*s), (x+24*s, y-398*s), (x+20*s, y-372*s), (x-32*s, y-364*s)], t, k+3, col, col, 2)           # short hair
    wline(d, [(x+18*s, y-320*s), (x+18*s + 90*s*arm, y-320*s - 50*s*arm + 90*s*(1-arm))], t, k+5, col, int(12*s))       # arm
    wpoly(d, [(x+8*s, y-350*s), (x+34*s, y-352*s), (x+30*s, y-300*s), (x+12*s, y-306*s)], t, k+11, col, col, 2)            # long Assyrian beard

def night_scene(t, T0):
    lt = t - T0
    im = Image.new("RGB", (W, H), PAPER); d = ImageDraw.Draw(im)
    d.rectangle([0, 820, W, H], fill=(205, 184, 146)); wline(d, [(0, 820), (W, 820)], t, 1, INK, 5)
    for i, x in enumerate(range(150, W, 330)):                                                 # columns
        wpoly(d, [(x, 210), (x+90, 210), (x+90, 820), (x, 820)], t, 10+i, (196, 174, 136), DARK, 4)
        wpoly(d, [(x-30, 170), (x+120, 170), (x+120, 215), (x-30, 215)], t, 30+i, (186, 164, 126), DARK, 4)
    # oil lamp on a stand, flame flickers
    wline(d, [(1500, 820), (1500, 560)], t, 60, INK, 8); wpoly(d, [(1460, 560), (1540, 560), (1520, 530), (1480, 530)], t, 61, DARK)
    fl = 26 + 6*math.sin(t*23)
    d.polygon([(1500, 530-fl-J(t, 62, 4)), (1488, 530), (1512, 530)], fill=(240, 220, 160))
    # doorway on the right (royal chamber)
    wpoly(d, [(1650, 300), (1880, 300), (1880, 820), (1650, 820)], t, 70, (60, 46, 32), INK, 5)
    # two figures cross toward the door
    u = ease((lt - .4)/3.2)
    figure(d, 380 + 1150*u, 820, t, 100, 1.25, arm=ease((lt-2.8)/.5))
    figure(d, 200 + 1150*u, 820, t, 200, 1.15)
    d.text((60, 40), "THEBES  ·  YEAR 32 OF RAMESSES III", font=font(SERIF, 50), fill=INK)
    d.text((60, 100), "(A RECONSTRUCTION - DETAILS UNKNOWN)", font=font(MONO, 26), fill=DARK)
    return im
def intertitle(lines):
    im = Image.new("RGB", (W, H), (18, 14, 10)); d = ImageDraw.Draw(im)
    d.rectangle([180, 140, W-180, H-140], outline=(200, 180, 140), width=4); d.rectangle([200, 160, W-200, H-160], outline=(200, 180, 140), width=1)
    for (x, y) in ((200, 160), (W-200, 160), (200, H-160), (W-200, H-160)): d.ellipse([x-12, y-12, x+12, y+12], fill=VRED)
    y = 380
    for i, s in enumerate(lines):
        f = font(SERIF, 96 if i == 0 else 72); w = f.getbbox(s)[2]; d.text(((W-w)/2, y), s, font=f, fill=(232, 218, 190)); y += 150 if i == 0 else 100
        if i == 0: d.line([(W/2-160, y - 30), (W/2+160, y - 30)], fill=VRED, width=4)
    return im
def film(img, fi):
    a = np.asarray(img).astype(np.float32)
    g = a.mean(axis=2, keepdims=True); sep = np.concatenate([g*1.07, g*.95, g*.78], 2)
    redmask = ((a[..., 0] > a[..., 1]*1.6) & (a[..., 0] > 120))[..., None]
    a = np.where(redmask, a, sep*.85 + a*.15)
    r = np.random.default_rng(fi); a *= 0.93 + 0.07*r.random(); a = a*VIG + r.normal(0, 13, (H, W, 1))
    out = np.clip(a, 0, 255).astype(np.uint8)
    for _ in range(r.integers(0, 3)):
        x = int(r.integers(0, W)); cv2.line(out, (x, 0), (x+int(r.integers(-20, 20)), H), (235, 225, 200) if r.random() < .6 else (40, 30, 20), 1)
    for _ in range(r.integers(2, 8)): cv2.circle(out, (int(r.integers(0, W)), int(r.integers(0, H))), int(r.integers(1, 4)), (25, 18, 12), -1)
    M = np.float32([[1, 0, r.normal(0, 1.5)], [0, 1, r.normal(0, 2.0)]])
    return cv2.warpAffine(out, M, (W, H), borderMode=cv2.BORDER_REFLECT)
def iris(o, r):
    m = (((vx-W/2)**2 + (vy-H/2)**2) <= r*r).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 6)[..., None]
    return (o*m).astype(np.uint8)
def vintage_frame(t, fi):
    T0, T1 = VINTAGE; dur = T1 - T0; flash = T0 + min(4.2, dur*.5)
    tq = math.floor(t*12)/12 if abs(t - flash) > .3 else t
    if t < flash + .6: img = night_scene(tq, T0)
    else: img = intertitle(["Year 32.", "The conspirators strike.", "The king is dead."])
    out = film(img, fi)
    st = t - flash
    if 0 <= st < .3:
        k = 1 - st/.3; out = np.clip(out.astype(np.float32) + 230*k, 0, 255).astype(np.uint8); out = np.roll(out, int(16*k), axis=0)
    if .3 <= st < .6:   # smoke
        k = 1 - (st - .3)/.3; out = np.clip(out.astype(np.float32)*(1 - .6*k) + 120*k, 0, 255).astype(np.uint8)
    full = math.hypot(W/2, H/2)
    if t < T0 + .6: out = iris(out, full*ss((t - T0)/.6))
    if t > T1 - .5: out = iris(out, full*(1 - ss((t - (T1 - .5))/.5)))
    return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

# ------------------------------------------------------------------ v4: magnifying loupe, lamp dust, extra silent-film scenes
def draw_loupe(frame, lp, t, C):
    it = lp['item']; u = (t - lp['t0']) / lp['du']
    a = ss(u / .15) * (1 - ss((u - .85) / .15))
    if a < .02: return
    w, h = it['size']; cx, cy = it['c']; v = ease(clamp((u - .1) / .8))
    wp = (cx + w * (-.2 + .4 * v), cy + h * (-.14 + .26 * v + .06 * math.sin(v * math.pi)))
    p = to_screen(wp, C); m = 2.4; r = int(175 * (.6 + .4 * a))
    x0, y0 = int(p[0]) - r, int(p[1]) - r
    if x0 < 0 or y0 < 0 or x0 + 2*r > W or y0 + 2*r > H: return
    Mi = np.vstack([item_M(it, C, it['img']), [0, 0, 1]])
    S = np.array([[m, 0, p[0] - m*p[0] - x0], [0, m, p[1] - m*p[1] - y0], [0, 0, 1]])
    mag = cv2.warpAffine(it['img'], (S @ Mi)[:2].astype(np.float32), (2*r, 2*r), flags=cv2.INTER_CUBIC, borderValue=(0, 0, 0, 0))
    roi = frame[y0:y0 + 2*r, x0:x0 + 2*r]
    yy, xx = np.ogrid[:2*r, :2*r]; d = np.sqrt((xx - r)**2 + (yy - r)**2) / r
    lens = np.clip((1 - d) * r / 3, 0, 1)[..., None] * a
    al = mag[..., 3:4].astype(np.float32) / 255
    inside = roi * (1 - al) + mag[..., :3] * al
    inside = inside * (1.06 - .25 * np.clip(d, 0, 1)**3)[..., None] + 18 * np.clip(1 - np.hypot(xx - r*.62, yy - r*.55)/(r*.5), 0, 1)[..., None]
    shadow = np.clip(1 - np.abs(d - 1.06) / .09, 0, 1)[..., None] * a * .55
    roi[:] = roi * (1 - shadow) * (1 - lens) + inside * lens
    rim = np.clip(1 - np.abs(d - .97) / .045, 0, 1)[..., None] * a
    roi[:] = roi * (1 - rim) + np.array([38, 58, 74], np.float32) * rim
    hx, hy = p[0] + r * .72, p[1] + r * .72
    cv2.line(frame, (int(hx), int(hy)), (int(hx + 120*a), int(hy + 120*a)), (30, 40, 52), 22, cv2.LINE_AA)

DUST = np.random.default_rng(9).random((80, 5))
SPR = {}
def add_dust(f, t, C):
    for x0, y0, sz, sp, ph in DUST:
        rr = int(2 + sz * 5)
        if rr not in SPR:
            g = np.exp(-((np.arange(-3*rr, 3*rr + 1)[None] / rr)**2 + (np.arange(-3*rr, 3*rr + 1)[:, None] / rr)**2))
            SPR[rr] = g[..., None].astype(np.float32)
        x = (x0 * W * 1.2 + t * (8 + 18 * sp) - C[0] * C[2] * (.05 + .12 * sz)) % (W * 1.2) - W * .1
        y = (y0 * H * 1.2 + t * (4 + 10 * sp) + 30 * math.sin(t * .4 + ph * 6) - C[1] * C[2] * (.05 + .12 * sz)) % (H * 1.2) - H * .1
        g = SPR[rr]; k = g.shape[0] // 2; xi, yi = int(x), int(y)
        if k <= xi < W - k - 1 and k <= yi < H - k - 1:
            tw = .5 + .5 * math.sin(t * (1.5 + 2 * sp) + ph * 9)
            f[yi - k:yi + k + 1, xi - k:xi + k + 1] += g * (10 + 26 * sz) * tw
    return f

def seated(d, x, y, t, k, s=1.0, arm=0.0, col=INK, face=1):
    """flat side-view figure sitting on the ground / a stool, knees raised"""
    f = face
    wline(d, [(x, y - 40*s), (x + f*95*s, y - 105*s), (x + f*120*s, y)], t, k + 7, col, int(14*s))
    wpoly(d, [(x - 34*s, y - 60*s), (x + 30*s, y - 60*s), (x + 30*s, y), (x - 34*s, y)], t, k + 1, PAPER, col, int(4*s))
    wpoly(d, [(x - 26*s, y - 170*s), (x + 26*s, y - 170*s), (x + 30*s, y - 60*s), (x - 30*s, y - 60*s)], t, k + 2, col, col, 2)
    d.ellipse([x - 28*s + J(t, k), y - 232*s + J(t, k + 1), x + 28*s + J(t, k), y - 172*s + J(t, k + 1)], fill=col)
    wpoly(d, [(x - f*36*s, y - 236*s), (x + f*16*s, y - 238*s), (x + f*6*s, y - 170*s), (x - f*40*s, y - 162*s)], t, k + 3, col, col, 2)
    wline(d, [(x + f*14*s, y - 150*s), (x + f*(14 + 80*arm)*s, y - (150 - 10*arm)*s + 70*(1 - arm)*s)], t, k + 5, col, int(12*s))

def woman(d, x, y, t, k, s=1.0, sway=0.0, arm=0.0, col=INK):
    figure(d, x, y, t, k, s, arm, col)
    o = sway * 14 * s
    wpoly(d, [(x - 30*s, y - 330*s), (x + 30*s, y - 330*s), (x + 52*s + o, y - 20*s), (x - 48*s + o, y - 20*s)], t, k + 11, (214, 196, 160), col, int(4*s))

def coffin(d, x, y, t, k, L=260, col=(120, 92, 58)):
    wpoly(d, [(x, y - 24), (x + 40, y - 46), (x + L - 30, y - 40), (x + L, y - 20), (x + L - 30, y), (x + 40, y), (x, y - 10)], t, k, col, INK, 4)
    d.ellipse([x + L - 70 + J(t, k), y - 40, x + L - 20 + J(t, k), y - 6], fill=(196, 160, 96), outline=INK, width=3)

def sc_strike(d, t, lt, CW):
    wpoly(d, [(0, 820), (0, 430), (260, 360), (620, 420), (900, 330), (1300, 400), (1500, 380), (1500, 820)], t, 300, (205, 182, 140), DARK, 4)
    wpoly(d, [(1580, 820), (1640, 300), (1980, 300), (2040, 820)], t, 310, (196, 174, 136), DARK, 5)
    for i in range(3): wline(d, [(1660 + 110*i, 360), (1680 + 110*i, 780)], t, 320 + i, MID, 3)
    for i, x in enumerate((240, 470, 700, 930, 1160)):
        seated(d, x, 820, t, 400 + 40*i, 1.15, arm=.15 + .1*(i % 2))
    for i, x in enumerate((1290, 1360, 1430)): wline(d, [(x, 812), (x + 70, 790)], t, 500 + i, DARK, 9)
    d.ellipse([1300, 770, 1380, 818], outline=INK, width=5)
    wpoly(d, [(1440, 820), (1430, 700), (1460, 650), (1540, 650), (1570, 700), (1560, 820)], t, 520, (190, 150, 100), INK, 5)
    if lt > 2.2:
        u = ease((lt - 2.2) / .3); c = (1500, 735); e = 46 * u
        d.line([(c[0] - e, c[1] - e), (c[0] + e, c[1] + e)], fill=VRED, width=12); d.line([(c[0] - e, c[1] + e), (c[0] + e, c[1] - e)], fill=VRED, width=12)
    return ("DEIR EL-MEDINA  ·  YEAR 29", "THE TOMB-BUILDERS PUT DOWN THEIR TOOLS")

def sc_messengers(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(150, 130, 100)); d.ellipse([1720, 90, 1820, 190], fill=PAPER)
    wpoly(d, [(0, 260), (900, 260), (900, 820), (0, 820)], t, 600, (186, 164, 126), INK, 5)
    wpoly(d, [(1240, 260), (CW, 260), (CW, 820), (1240, 820)], t, 610, (186, 164, 126), INK, 5)
    wpoly(d, [(860, 200), (1280, 200), (1280, 270), (860, 270)], t, 620, (176, 152, 116), INK, 5)
    woman(d, 760, 820, t, 640, 1.1, sway=math.sin(lt*2), arm=clamp(lt / 1.2))
    u = ease((lt - 1.4) / 3.6)
    mx = 1000 + 900*u; figure(d, mx, 820, t, 700, 1.15, arm=.55)
    sx_, sy_ = (850, 520) if lt < 1.4 else (mx + 70, 540)
    wpoly(d, [(sx_, sy_), (sx_ + 60, sy_ - 8), (sx_ + 62, sy_ + 26), (sx_ + 2, sy_ + 32)], t, 720, PAPER, INK, 3)
    d.ellipse([sx_ + 22, sy_ + 4, sx_ + 42, sy_ + 24], fill=VRED)
    return ("THE HAREM GATE  ·  NIGHT", "MESSAGES CARRIED OUT OF THE PALACE")

def sc_trial(d, t, lt, CW):
    for i, x in enumerate(range(120, CW, 420)):
        wpoly(d, [(x, 190), (x + 80, 190), (x + 80, 820), (x, 820)], t, 800 + i, (196, 174, 136), DARK, 4)
    wpoly(d, [(120, 760), (1080, 760), (1080, 820), (120, 820)], t, 830, (150, 120, 84), INK, 4)
    for i, x in enumerate((200, 380, 560, 740, 920)): seated(d, x, 760, t, 850 + 30*i, 1.0, arm=.3 if i != 2 else .2 + .7*clamp((lt - 3)/.6))
    seated(d, 1180, 820, t, 1000, .8, arm=.6)
    wpoly(d, [(1250, 700), (1330, 690), (1335, 712), (1255, 722)], t, 1010, PAPER, INK, 3)
    if lt > 3.4: d.ellipse([1282, 696, 1302, 716], fill=VRED)
    figure(d, 1560, 820, t, 1100, 1.15, arm=0.0); figure(d, 1720, 820, t, 1150, 1.2, arm=.3); figure(d, 1420, 820, t, 1200, 1.2, arm=.3)
    return ("THE COURT OF INQUIRY  ·  THEBES", "OFFICIALS EXAMINE THE ACCUSED")

def sc_party(d, t, lt, CW):
    for i, x in enumerate(range(160, CW, 460)):
        wpoly(d, [(x, 190), (x + 80, 190), (x + 80, 820), (x, 820)], t, 1300 + i, (196, 174, 136), DARK, 4)
    for i, x in enumerate((260, 460, 660)):
        seated(d, x, 820, t, 1350 + 30*i, 1.05, arm=.4 + .4*math.sin(lt*3 + i)**2)
        cx_ = x + 14 + 80*(.4 + .4*math.sin(lt*3 + i)**2); d.rectangle([cx_ - 10, 660 - 60*(.4 + .4*math.sin(lt*3+i)**2), cx_ + 10, 690 - 60*(.4 + .4*math.sin(lt*3+i)**2)], fill=DARK)
    for i, x in enumerate((1020, 1240)): woman(d, x + 40*math.sin(lt*2.2 + i*2), 820, t, 1450 + 50*i, 1.1, sway=math.sin(lt*4 + i), arm=.5 + .5*math.sin(lt*3 + i))
    seated(d, 1580, 820, t, 1550, 1.05, arm=.8)
    wpoly(d, [(1700, 820), (1720, 480), (1760, 470), (1790, 820)], t, 1560, (170, 130, 80), INK, 4)
    for i in range(5): wline(d, [(1722 + 6*i, 500 + 10*i), (1700 + 18*i, 800)], t, 1570 + i, DARK, 2)
    return ("THE JUDGES' MISCONDUCT", "CAROUSING WITH THE ACCUSED WOMEN")

def sc_cache(d, t, lt, CW):
    wpoly(d, [(0, 820), (0, 140), (380, 120), (640, 200), (820, 180), (980, 300), (1060, 820)], t, 1700, (198, 172, 128), INK, 5)
    wpoly(d, [(430, 200), (520, 200), (520, 820), (430, 820)], t, 1710, (70, 54, 36), INK, 4)
    wline(d, [(475, 150), (475, 200 + 300*clamp(lt / 2))], t, 1720, INK, 5)
    for i in range(3): coffin(d, 560 + 30*i, 820 - 52*i, t, 1730 + 20*i, 300)
    u = ease((lt - .8) / 5); bx = 1080 + 520*u
    figure(d, bx, 820, t, 1800, 1.0, arm=.9); figure(d, bx + 250, 820, t, 1850, 1.0, arm=.9)
    coffin(d, bx - 30, 560, t, 1880, 330)
    d.rectangle([1500, 840, CW, 1000], fill=(150, 140, 120)); wline(d, [(1500, 842), (CW, 842)], t, 1890, INK, 4)
    hx = 1900 + 60*math.sin(lt*.6)
    wpoly(d, [(hx, 860), (hx + 340, 860), (hx + 280, 920), (hx + 60, 920)], t, 1900, (120, 92, 58), INK, 4)
    wline(d, [(hx + 170, 860), (hx + 170, 640)], t, 1910, INK, 6); wpoly(d, [(hx + 175, 650), (hx + 300, 760), (hx + 175, 840)], t, 1920, PAPER, INK, 3)
    return ("DEIR EL-BAHARI  ·  JULY 1881", "THE MUMMIES ARE CARRIED OUT, THEN SHIPPED TO CAIRO")

def pumice_rain(d, t, k, n=140, CW=2280, top=0, bot=820, speed=520, col=(70, 60, 50)):
    r = np.random.default_rng(k)
    xs, ph, sz = r.uniform(0, CW, n), r.uniform(0, 1, n), r.uniform(3, 8, n)
    for x, p_, z in zip(xs, ph, sz):
        yy = top + ((p_ * (bot - top) + t * speed * (z / 6)) % (bot - top)); xx = x - (yy - top) * .25
        d.ellipse([xx - z, yy - z, xx + z, yy + z], fill=col)

def house(d, x, t, k, w=420, h=360, roof=0.0):
    wpoly(d, [(x, 820), (x, 820 - h), (x + w, 820 - h), (x + w, 820)], t, k, (196, 174, 136), DARK, 5)
    wpoly(d, [(x + w*.38, 820), (x + w*.38, 820 - h*.55), (x + w*.62, 820 - h*.55), (x + w*.62, 820)], t, k + 1, (70, 54, 36), INK, 4)
    sag = 60 * roof
    wpoly(d, [(x - 30, 820 - h), (x + w/2, 820 - h - 90 + sag), (x + w + 30, 820 - h)], t, k + 2, (150, 92, 60), INK, 5)

def shelves(d, x, y, t, k, n=5):
    for r in range(n):
        yy = y + r * 90
        wline(d, [(x, yy), (x + 420, yy)], t, k + r, INK, 6)
        for j in range(9):
            d.rectangle([x + 14 + j * 44, yy - 60 + (j % 3) * 6, x + 46 + j * 44, yy - 4], fill=(150, 118, 84), outline=INK)

def sc_scribes(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(150, 128, 98))
    shelves(d, 1500, 300, t, 4000)
    for i, x in enumerate((360, 760, 1160)):
        seated(d, x, 820, t, 4100 + 20 * i, .95, arm=.6 + .25 * math.sin(lt * 5 + i), face=1)
        wpoly(d, [(x + 60, 560), (x + 140, 556), (x + 142, 610), (x + 62, 614)], t, 4150 + i, (150, 118, 84), INK, 3)    # tablet on the knee
        if (int(lt * 6) + i) % 2: d.line([(x + 80, 580), (x + 120, 590)], fill=INK, width=3)
    d.ellipse([1300, 180, 1340, 220], fill=(250, 210, 120)); wline(d, [(1320, 220), (1320, 300)], t, 4190, INK, 4)          # lamp
    return ("NINEVEH  ·  c. 650 B.C.", "SCRIBES COPY TABLETS FOR THE KING'S LIBRARY")

def sc_siege(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(150, 120, 96))
    wpoly(d, [(900, 820), (900, 300), (CW, 300), (CW, 820)], t, 4200, (176, 150, 112), INK, 5)                               # city wall
    for k in range(14): d.rectangle([900 + k * 100, 260, 950 + k * 100, 300], fill=(176, 150, 112), outline=INK, width=4)    # merlons
    u = ease(lt / 6.0)
    for i in range(5):
        x = 120 + 140 * i + 300 * u
        figure(d, x, 820, t, 4300 + 30 * i, .95, arm=.9)
        wline(d, [(x + 60, 520), (x + 60, 380)], t, 4330 + i, INK, 4)                                                         # spear
    wline(d, [(820 + 60 * u, 820), (980, 330)], t, 4360, (90, 70, 50), 8); wline(d, [(860 + 60 * u, 820), (1020, 330)], t, 4361, (90, 70, 50), 8)  # ladder
    for r_ in range(8): wline(d, [(830 + 60 * u + r_ * 19, 800 - r_ * 60), (870 + 60 * u + r_ * 19, 800 - r_ * 60)], t, 4370 + r_, (90, 70, 50), 5)
    g = clamp((lt - 2.5) / 3)
    if g > 0:                                                                                                                # flames over the palace roofs
        for k in range(9):
            fx = 1000 + k * 140; fh = 120 + 80 * math.sin(lt * 7 + k)
            wpoly(d, [(fx - 50, 300), (fx, 300 - fh * g), (fx + 50, 300)], t, 4400 + k, (210, 120, 50), (150, 60, 30), 3)
        d.rectangle([900, 0, CW, int(200 * g)], fill=(120, 80, 60))
    return ("NINEVEH  ·  612 B.C.", "THE MEDES AND BABYLONIANS BREAK INTO THE CITY")

def sc_nightdig(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(46, 52, 70))
    for k in range(40): d.point((int((k * 397) % CW), int((k * 211) % 400)), fill=(220, 220, 200))
    wpoly(d, [(0, 820), (200, 420), (900, 360), (1700, 400), (CW, 560), (CW, 820)], t, 4500, (96, 86, 70), INK, 5)          # the mound
    d.pieslice([760, 520, 1080, 900], 180, 360, fill=(26, 22, 18)); d.rectangle([760, 710, 1080, 820], fill=(26, 22, 18))    # tunnel
    for i, x in enumerate((520, 680, 1180)):
        sw = .2 + .8 * abs(math.sin(lt * 3 + i))
        figure(d, x, 820, t, 4600 + 30 * i, .9, arm=sw)
        wline(d, [(x + 20 + 80 * sw, 520 - 40 * sw), (x + 40 + 110 * sw, 470 - 60 * sw)], t, 4650 + i, (200, 190, 170), 6)    # pick
    for lx in (600, 1100):
        r_ = 120 + 10 * math.sin(lt * 9 + lx)
        d.ellipse([lx - r_, 640 - r_, lx + r_, 640 + r_], outline=(150, 130, 80), width=2); d.ellipse([lx - 14, 626, lx + 14, 654], fill=(250, 210, 120))
    return ("KUYUNJIK, NINEVEH  ·  1853", "RASSAM'S WORKMEN DIG IN SECRET, BY NIGHT")

def sc_reading(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(170, 150, 120))
    shelves(d, 100, 260, t, 4700, 4)
    wpoly(d, [(700, 600), (1500, 600), (1500, 630), (700, 630)], t, 4750, (120, 90, 60), INK, 4)                             # table
    wline(d, [(740, 630), (740, 820)], t, 4751, INK, 8); wline(d, [(1460, 630), (1460, 820)], t, 4752, INK, 8)
    jump = clamp((lt - 2.6) / .3) - clamp((lt - 3.2) / .3)
    x = 1100 + 220 * ease(clamp((lt - 3.2) / 2.5))
    figure(d, x, 820 - 120 * jump, t, 4800, 1.05, arm=.95 if lt > 2.6 else .5)
    d.polygon([(x + 70, 500), (x + 120, 500), (x + 118, 540), (x + 72, 540)], fill=(150, 118, 84))                            # the tablet
    if lt > 3.4:                                                                                                             # the jacket comes off
        u = ease(clamp((lt - 3.4) / 1.4)); jx, jy = x - 120 - 260 * u, 420 + 300 * u * u
        wpoly(d, [(jx, jy), (jx + 90, jy - 10), (jx + 110, jy + 110), (jx - 10, jy + 120)], t, 4850, (70, 64, 60), INK, 3)
    return ("THE BRITISH MUSEUM  ·  1872", "GEORGE SMITH READS THE FLOOD TABLET")

SCENES = {'scribes': sc_scribes, 'siege': sc_siege, 'nightdig': sc_nightdig, 'reading': sc_reading}
def film_frame(t, fi, F):
    T0, T1 = F['t0'], F['t1']; lt = t - T0; tq = math.floor(t*12)/12; lq = tq - T0
    CW = W + 360; im = Image.new("RGB", (CW, H), PAPER); d = ImageDraw.Draw(im)
    d.rectangle([0, 820, CW, H], fill=(205, 184, 146)); wline(d, [(0, 820), (CW, 820)], tq, 1, INK, 5)
    cap = SCENES[F['scene']](d, tq, lq, CW)
    pan = int(360 * ease(lt / (T1 - T0))); img = im.crop((pan, 0, pan + W, H)); d = ImageDraw.Draw(img)
    d.text((60, 40), cap[0], font=font(SERIF, 50), fill=INK); d.text((60, 100), cap[1] + "   (RECONSTRUCTION)", font=font(MONO, 26), fill=DARK)
    if F.get('title') and t > T1 - 2.0: img = intertitle(F['title'].split('|'))
    out = film(img, fi); full = math.hypot(W/2, H/2)
    if t < T0 + .5: out = iris(out, full*ss((t - T0)/.5))
    if t > T1 - .45: out = iris(out, full*(1 - ss((t - (T1 - .45))/.45)))
    return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

# ------------------------------------------------------------------ render
def render(frames, out, stills_dir=None):
    bg_full, bg_half = build_bg(1.0), None
    bg_half = cv2.resize(bg_full, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
    vig = (1 - .45*np.clip(((vx-W/2)/(W*.62))**2 + ((vy-H/2)/(H*.62))**2, 0, 1))[..., None].astype(np.float32)
    grains = [rng.normal(0, 3.2, (H, W, 1)).astype(np.float32) for _ in range(6)]
    global LAMP
    d2 = ((vx - W*.5)/(W*.62))**2 + ((vy - H*.46)/(H*.66))**2
    light = (1.20 - .60*np.clip(d2, 0, 1.3)**1.1)[..., None]
    LAMP = (light * np.array([0.96, 1.0, 1.05], np.float32)).astype(np.float32)     # warm centre (BGR), dark edges
    ff = None
    if not stills_dir:
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    def board_frame(t, fi):
        C = cam(t)
        for st in STAMPS:
            if st['t0'] < t < st['t0'] + .35:
                k = (1 - (t - st['t0'])/.35)*14; C[0] += k*math.sin(t*90)/C[2]; C[1] += k*math.cos(t*77)/C[2]
        if C[2] < .62: frame = cv2.warpAffine(bg_half, world_M(C, .5), (W, H), flags=cv2.INTER_LINEAR, borderValue=(38, 38, 24)).astype(np.float32)
        else: frame = cv2.warpAffine(bg_full, world_M(C), (W, H), flags=cv2.INTER_LINEAR, borderValue=(38, 38, 24)).astype(np.float32)
        for it in ITEMS:
            if t < it['t0']: continue
            p = to_screen(it['c'], C); r = max(it['size'])*C[2]
            if p[0]+r < 0 or p[0]-r > W or p[1]+r < 0 or p[1]-r > H: continue
            u = (t - it['t0'])/.45; sc = 1.12 - .12*backout(u); dy = -60*(1 - ease(u)); sx = sy = 1.0; dx = 0.0; rx = None
            kd = it['kind']
            if kd in ('quote', 'note'): dy = 0; sc = 1.0; dx = -240*(1 - ease(u)); rx = it['rot'] - 9*(1 - backout(u))
            elif kd == 'suspect': dy = 0; sx = max(.03, backout(clamp((t - it['t0'])/.55), 1.2))
            elif kd in ('map', 'diagram'): dy = 0; sc = 1.0; sy = max(.03, ease((t - it['t0'])/.6))
            lvl = 0 if C[2]/R*2 > .55 else (1 if C[2]/R*2 > .28 else 2)
            im = it['mips'][lvl]
            if 'hlimg' in it and t >= it['ht']:
                hu = ease((t - it['ht'])/.45); hm = it['hlmips'][lvl]
                if hu >= 1: im = hm
                else:
                    sc_ = im.shape[1] / it['img'].shape[1]; pad_ = int(50*R*sc_); x0 = pad_ + int(it['hx'][0]*sc_); x1 = pad_ + int(it['hx'][1]*sc_)
                    xm = int(x0 + (x1 - x0)*hu); im = im.copy(); im[:, x0:xm] = hm[:, x0:xm]
            if u < 1: im = im.copy(); im[..., 3] = (im[..., 3]*ss(u*1.6)).astype(np.uint8)
            blend_roi(frame, im, item_M(it, C, im, sc, dy, rx, sx, sy, dx))
        for st in STAMPS:
            if t < st['t0']: continue
            it = st['item']; u = (t - st['t0'])/.2; sc = (1.6 - .6*backout(u, 2.2)) * min(1.0, it['size'][0]*R*.9/st['img'].shape[1])
            blend_roi(frame, st['img'], item_M(dict(it, img=st['img']), C, st['img'], sc, 0, rot=it['rot'] - 12))
        for lp in LOUPES:
            if lp['t0'] <= t < lp['t0'] + lp['du']: draw_loupe(frame, lp, t, C)
        # motion blur on fast camera travel
        Cn = cam(t + 1/FPS); v = math.hypot((Cn[0] - C[0])*C[2], (Cn[1] - C[1])*C[2]) + abs(math.log(Cn[2]/C[2]))*900
        if v > 14:
            L = int(min(41, v * .9)) | 1; ang = math.atan2((Cn[1] - C[1]), (Cn[0] - C[0])); k = np.zeros((L, L), np.float32)
            cv2.line(k, (int(L/2 - math.cos(ang)*L/2), int(L/2 - math.sin(ang)*L/2)), (int(L/2 + math.cos(ang)*L/2), int(L/2 + math.sin(ang)*L/2)), 1, 1)
            k /= max(k.sum(), 1); frame = cv2.filter2D(frame, -1, k)
        fr = np.clip(frame, 0, 255).astype(np.uint8)
        fr = draw_overlays(fr, t, C)
        fr = draw_pops(fr, t)
        fr = screen_overlays(fr, t)
        f = fr.astype(np.float32)
        for st in STAMPS:
            if st['t0'] < t < st['t0'] + .2:
                f[..., 2] = np.roll(f[..., 2], 10, axis=1); f[..., 0] = np.roll(f[..., 0], -10, axis=1)
        f = add_dust(f, t, C)
        f = f*LAMP + grains[fi % 6]
        if t < .6: f *= t/.6
        if t > DUR - 1.0: f *= max(0, (DUR - t))/1.0
        fr = np.clip(f, 0, 255).astype(np.uint8)
        return fr
    import cutaways as CW
    for fi in frames:
        t = fi / FPS
        FL = [F for F in FILMS if F['t0'] <= t < F['t1']]
        if VINTAGE and VINTAGE[0] <= t < VINTAGE[1]:
            fr = vintage_frame(t, fi)
        elif FL:
            fr = film_frame(t, fi, FL[0])
        else:
            fr = CW.compose(t, fi, board_frame)
        if stills_dir: cv2.imwrite(os.path.join(stills_dir, f'{t:07.2f}.jpg'), fr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        else: ff.stdin.write(fr.tobytes())
    if ff: ff.stdin.close(); ff.wait()

build_model()
K = build_cam()

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == 'stills':
        sd = os.path.join(B, 'stills'); os.makedirs(sd, exist_ok=True)
        ts = [float(x) for x in sys.argv[2].split(',')]
        render([int(t*FPS) for t in ts], None, sd)
    elif mode == 'info':
        print('DUR', DUR, 'items', len(ITEMS), 'tags', len(TAGS), 'lines', len(LINES), 'stamps', len(STAMPS), 'keys', len(K), 'vintage', VINTAGE)
        json.dump({it['credit']['id']: it['credit'] for it in ITEMS if it['credit']}, open(os.path.join(B, 'credits.json'), 'w'), indent=1)
    else:
        render(range(int(sys.argv[2]), int(sys.argv[3])), sys.argv[4])
