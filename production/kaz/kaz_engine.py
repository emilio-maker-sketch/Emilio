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
ZW, ZH, MARG, COLS = 3600, 2700, 420, 4
ZONES = ['open', 'king', 'harem', 'plot', 'night', 'trial', 'case', 'end']
ZONE_TITLES = {'open': 'EXHIBIT A', 'king': 'FILE 01  THE KING', 'harem': 'FILE 02  THE HAREM', 'plot': 'FILE 03  THE PLOT',
               'night': 'FILE 04  THE NIGHT', 'trial': 'FILE 05  THE TRIAL', 'case': 'FILE 06  THE EVIDENCE', 'end': 'FILE 07  VERDICT'}
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
for f in ('museum.json', 'aic.json'):
    p = os.path.join(IMGDIR, f)
    if os.path.exists(p):
        for t, recs in json.load(open(p)).items():
            for r in recs: r['topic'] = t; DB.setdefault(r['id'], r)

def find_image(spec, used):
    if re.match(r'^(met|aic)\d+$', spec): return DB[spec]
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

def make_card(path, wworld, max_h=560, border=14):
    im = trim(Image.open(path).convert("RGB"))
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
    """generic head-and-shoulders with an Egyptian wig (centre x, head centre y)"""
    d.ellipse([x - 150*s, y + 95*s, x + 150*s, y + 330*s], fill=fill)              # shoulders
    d.rounded_rectangle([x - 78*s, y - 92*s, x + 78*s, y + 120*s], radius=int(40*s), fill=fill)   # wig
    d.rectangle([x - 26*s, y + 40*s, x + 26*s, y + 120*s], fill=fill)             # neck
    d.ellipse([x - 56*s, y - 70*s, x + 56*s, y + 64*s], fill=fill)                 # face

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
    ln = (190, 210, 215); w = int(3*R)
    if kind == 'neck':
        d.ellipse([170*R, 40*R, 360*R, 230*R], outline=ln, width=w)                              # skull
        d.line([(250*R, 230*R), (240*R, 420*R)], fill=ln, width=w); d.line([(320*R, 220*R), (330*R, 420*R)], fill=ln, width=w)
        for i in range(6): d.rounded_rectangle([262*R, (238 + 30*i)*R, 300*R, (262 + 30*i)*R], radius=6, outline=ln, width=int(2*R))  # vertebrae
        d.line([(232*R, 300*R), (318*R, 300*R)], fill=RED, width=int(6*R))                       # wound line
        d.text((340*R, 284*R), "~7 CM", font=font(MONO, 26*R), fill=RED)
        d.text((24*R, 20*R), "CT RECONSTRUCTION (SCHEMATIC)", font=font(MONO, 18*R), fill=(150, 170, 175))
        d.text((24*R, 420*R), "NECK - FRONT CUT TO THE VERTEBRAE", font=font(MONO, 18*R), fill=(150, 170, 175))
    else:
        pts = [(120, 360), (150, 200), (220, 120), (320, 100), (420, 110), (470, 160), (470, 220), (430, 300), (330, 380), (200, 400)]
        d.line([(x*R, y*R) for x, y in pts] + [(pts[0][0]*R, pts[0][1]*R)], fill=ln, width=w, joint="curve")
        for i, (x, y) in enumerate([(440, 130), (400, 112), (360, 104), (320, 104), (290, 112)]):
            d.ellipse([(x - 18)*R, (y - 22)*R, (x + 18)*R, (y + 14)*R], outline=ln if i else RED, width=w)
        for k in range(0, 9, 2): d.line([((410 + k*6)*R, 160*R), ((410 + (k + 1)*6)*R, 160*R)], fill=RED, width=int(5*R))
        d.text((24*R, 20*R), "CT RECONSTRUCTION (SCHEMATIC)", font=font(MONO, 18*R), fill=(150, 170, 175))
        d.text((24*R, 420*R), "LEFT FOOT - BIG TOE SEVERED", font=font(MONO, 18*R), fill=(150, 170, 175))
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

LON0, LON1, LAT0, LAT1 = 17.0, 47.0, 21.2, 32.6
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
    # Nile (schematic): Mediterranean delta -> Aswan
    nile = [(31.0, 31.5), (31.25, 30.1), (31.2, 29.0), (30.9, 28.0), (31.2, 27.2), (31.9, 26.4), (32.5, 26.0), (32.65, 25.7), (32.6, 25.0), (32.9, 24.1)]
    pts = np.array([[geo(*p)[0]*scale, geo(*p)[1]*scale] for p in nile], np.int32)
    cv2.polylines(bg, [pts], False, (110, 104, 62), max(2, int(10*scale)), cv2.LINE_AA)
    for g in range(0, w, int(250*scale)): bg[:, g:g+2] += 6
    for g in range(0, h, int(250*scale)): bg[g:g+2, :] += 6
    img = Image.fromarray(cv2.cvtColor(np.clip(bg, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(img)
    lab = (150, 160, 130)
    for name, lon, lat in [('THEBES', 32.65, 25.7), ('MEMPHIS', 31.25, 29.85), ('ABYDOS', 31.9, 26.2), ('NUBIA / KUSH', 32.0, 22.2),
                           ('MEDITERRANEAN SEA', 22.0, 32.2), ('RED SEA', 37.0, 23.5), ('SINAI', 33.8, 29.3), ('CANAAN', 35.2, 32.0), ('NILE', 31.5, 27.6)]:
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
VINTAGE = None

def layout_slots(zi):
    x0, y0, x1, y1 = zone_rect(zi)
    cols, rows = 5, 4
    sw, sh = ZW / cols, (ZH - 260) / rows
    order = [(1, 1), (2, 1), (1, 2), (2, 2), (3, 1), (3, 2), (0, 1), (0, 2), (4, 1), (4, 2), (1, 0), (2, 0), (3, 0), (1, 3), (2, 3), (3, 3), (0, 0), (4, 0), (0, 3), (4, 3)]
    r = np.random.default_rng(zi * 31 + 5)
    return [(x0 + sw*(c + .5) + r.uniform(-60, 60), y0 + 260 + sh*(rr + .5) + r.uniform(-50, 50), r.uniform(-6, 6)) for c, rr in order]

def build_model():
    global VINTAGE
    zi, slots, used = 0, layout_slots(0), set()
    last_item = None
    for ev in TL['events']:
        t, d = ev['t'], ev['d']; cmd, args = d[0], d[1:]
        pos, opt = kv(args)
        if cmd == 'zone':
            zi = ZONES.index(pos[0]); slots = layout_slots(zi)
            x0, y0, x1, y1 = zone_rect(zi); KEYS.append((t, ((x0 + x1)/2, (y0 + y1)/2, ZW*.62, ZH*.62), 1.6))
            continue
        if cmd in ('card', 'note', 'suspect', 'diagram'):
            if cmd == 'card':
                rec = find_image(pos[0], used); used.add(rec['id'])
                img, size = make_card(os.path.join(IMGDIR, rec['file']), min(float(opt.get('w', 520)), 640))
                credit = rec
            elif cmd == 'note':
                img, size = make_paper(pos[0].split('|')); credit = None
            elif cmd == 'suspect':
                img, size = make_suspect(pos[1], pos[2]); opt['as'] = pos[0]; credit = None
            else:
                img, size = make_diagram(pos[0]); credit = None
            cx, cy, rot = slots.pop(0)
            it = dict(img=img, c=(cx, cy), rot=rot, t0=t + .25, size=size, zone=zi, credit=credit)
            ITEMS.append(it); last_item = it
            if 'as' in opt: BYNAME[opt['as']] = it
            KEYS.append((t, (cx, cy, size[0], size[1]), .9))
        elif cmd == 'tag':
            it = BYNAME[pos[0]]; TAGS.append(dict(item=it, text=pos[1], t0=t + .5, zone=it['zone']))
        elif cmd == 'string':
            a, b = BYNAME[pos[0]], BYNAME[pos[1]]; LINES.append(dict(a=a, b=b, t0=t + .3, du=.8))
            xs = [a['c'][0], b['c'][0]]; ys = [a['c'][1], b['c'][1]]
            KEYS.append((t, ((min(xs) + max(xs))/2, (min(ys) + max(ys))/2, abs(xs[1]-xs[0]) + 600, abs(ys[1]-ys[0]) + 520), .9))
        elif cmd == 'circle':
            it = BYNAME[pos[0]]; ELLS.append(dict(item=it, t0=t + .35, du=.55))
            KEYS.append((t, (it['c'][0], it['c'][1], it['size'][0]*1.3, it['size'][1]*1.3), .7))
        elif cmd == 'stamp':
            it = BYNAME[pos[0]]; STAMPS.append(dict(item=it, img=make_stamp(pos[1]), t0=t + .45))
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
    # vintage ends at the next card event after it starts
    if VINTAGE:
        nxt = [e['t'] for e in TL['events'] if e['t'] > VINTAGE[0] + 1 and e['d'][0] == 'card']
        VINTAGE[1] = min(nxt) if nxt else VINTAGE[0] + 10
    for o in OVERLAYS:
        o['dur'] = {'year': 3.0, 'thesis': 3.8, 'end_open': 4.6, 'end': 7.0}[o['kind']] + (0 if o['kind'] != 'thesis' else 0)
    # mip levels
    for it in ITEMS:
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
        rot = rr.uniform(-2, 2)
        keys.append((min(t + mv, (KEYS[i + 1][0] - .05) if i + 1 < len(KEYS) else t + mv), tgt[0], tgt[1], tgt[2], rot))
    last = keys[-1]; keys.append((DUR, last[1], last[2], last[3] * 1.05, last[4]))
    return keys
K = []
def cam(t):
    for i in range(len(K) - 1):
        a, b = K[i], K[i + 1]
        if a[0] <= t <= b[0]:
            u = ease((t - a[0]) / max(1e-6, b[0] - a[0]))
            z = math.exp(math.log(a[3]) + (math.log(b[3]) - math.log(a[3])) * u)
            return [a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, z, a[4] + (b[4] - a[4]) * u]
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

def item_M(it, C, img, extra=1.0, dy=0.0, rot=None):
    h, w = img.shape[:2]; scale_px = it['img'].shape[1] / w
    rr = math.radians(it['rot'] if rot is None else rot); k = extra * scale_px / R
    c, s = math.cos(rr)*k, math.sin(rr)*k
    L = np.array([[c, -s, it['c'][0] - (c*w/2 - s*h/2)], [s, c, it['c'][1] + dy - (s*w/2 + c*h/2)], [0, 0, 1]])
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
        it = e['item']; rx, ry = it['size'][0]*.62, it['size'][1]*.62
        pts = wobble_ellipse(it['c'], rx, ry, clamp((t - e['t0'])/e['du']), C, seed=e['t0'])
        if len(pts) > 1: d.line(pts, fill=RED+(240,), width=max(3, int(7*z)), joint="curve")
    for L in LINES:
        if t < L['t0']: continue
        u = ease((t - L['t0'])/L['du'])
        a = to_screen((L['a']['c'][0], L['a']['c'][1] - L['a']['size'][1]*.35), C)
        b0 = to_screen((L['b']['c'][0], L['b']['c'][1] - L['b']['size'][1]*.35), C)
        b = (a[0]+(b0[0]-a[0])*u, a[1]+(b0[1]-a[1])*u + math.sin(u*math.pi)*25*z)
        d.line([a, b], fill=RED+(230,), width=max(2, int(5*z)))
        for p in (a, b): d.ellipse([p[0]-8, p[1]-8, p[0]+8, p[1]+8], fill=RED+(255,))
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
        it = tg['item']; p = to_screen((it['c'][0] - it['size'][0]*.42, it['c'][1] - it['size'][1]*.42), C)
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

def text_center(d, y, s, f, fill):
    w = f.getbbox(s)[2]; d.text(((W-w)/2, y), s, font=f, fill=fill)

def screen_overlays(img, t):
    out = img.astype(np.float32)
    for o in OVERLAYS:
        t0, du = o['t0'], o['dur']
        if not (t0 < t < t0 + du + .4): continue
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
            return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        if o['kind'] == 'thesis':
            a = ss((t - t0)/.5) * (1 - ss((t - (t0 + du - .4))/.5)); out *= 1 - .6*a
            pil = Image.fromarray(cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB)); d = ImageDraw.Draw(pil, "RGBA")
            al = int(255*a); f1 = font(MONO, 50); s1 = o['a']
            n = min(len(s1), int(max(0, t - t0 - .3)*20)); w1 = f1.getbbox(s1)[2]; x1 = (W - w1)/2
            d.text((x1, 380), s1[:n], font=f1, fill=(220, 220, 212, al))
            if t > t0 + 1.3:
                u = ease((t - t0 - 1.3)/.4); d.line([(x1-10, 412), (x1-10+(w1+20)*u, 412)], fill=RED+(al,), width=6)
            if t > t0 + 1.8:
                s2 = o['b']; f2 = font(SERIF, 120 if len(s2) < 14 else (96 if len(s2) < 22 else 76))
                n2 = min(len(s2), int((t - t0 - 1.8)*16)); w2 = f2.getbbox(s2 + ".")[2]
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
    wpoly(d, [(x-34*s, y-230*s), (x+34*s, y-230*s), (x+48*s, y-140*s), (x-40*s, y-140*s)], t, k+1, PAPER, col, int(4*s))   # kilt
    wpoly(d, [(x-26*s, y-330*s), (x+26*s, y-330*s), (x+30*s, y-230*s), (x-30*s, y-230*s)], t, k+2, col, col, 2)          # torso
    d.ellipse([x-26*s+J(t, k), y-392*s+J(t, k+1), x+30*s+J(t, k), y-332*s+J(t, k+1)], fill=col)                        # head
    wpoly(d, [(x-34*s, y-396*s), (x+16*s, y-398*s), (x+6*s, y-330*s), (x-38*s, y-322*s)], t, k+3, col, col, 2)           # wig
    wline(d, [(x+18*s, y-320*s), (x+18*s + 90*s*arm, y-320*s - 50*s*arm + 90*s*(1-arm))], t, k+5, col, int(12*s))       # arm

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

# ------------------------------------------------------------------ render
def render(frames, out, stills_dir=None):
    bg_full, bg_half = build_bg(1.0), None
    bg_half = cv2.resize(bg_full, None, fx=.5, fy=.5, interpolation=cv2.INTER_AREA)
    vig = (1 - .45*np.clip(((vx-W/2)/(W*.62))**2 + ((vy-H/2)/(H*.62))**2, 0, 1))[..., None].astype(np.float32)
    grains = [rng.normal(0, 4.5, (H, W, 1)).astype(np.float32) for _ in range(6)]
    ff = None
    if not stills_dir:
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for fi in frames:
        t = fi / FPS
        if VINTAGE and VINTAGE[0] <= t < VINTAGE[1]:
            fr = vintage_frame(t, fi)
        else:
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
                u = (t - it['t0'])/.45; sc = 1.12 - .12*backout(u); dy = -60*(1 - ease(u))
                lvl = 0 if C[2]/R*2 > .55 else (1 if C[2]/R*2 > .28 else 2)
                im = it['mips'][lvl]
                if u < 1: im = im.copy(); im[..., 3] = (im[..., 3]*ss(u*1.6)).astype(np.uint8)
                blend_roi(frame, im, item_M(it, C, im, sc, dy))
            for st in STAMPS:
                if t < st['t0']: continue
                it = st['item']; u = (t - st['t0'])/.2; sc = (1.6 - .6*backout(u, 2.2)) * min(1.0, it['size'][0]*R*.9/st['img'].shape[1])
                blend_roi(frame, st['img'], item_M(dict(it, img=st['img']), C, st['img'], sc, 0, rot=it['rot'] - 12))
            fr = np.clip(frame, 0, 255).astype(np.uint8)
            fr = draw_overlays(fr, t, C)
            fr = screen_overlays(fr, t)
            f = fr.astype(np.float32)
            for st in STAMPS:
                if st['t0'] < t < st['t0'] + .2:
                    f[..., 2] = np.roll(f[..., 2], 10, axis=1); f[..., 0] = np.roll(f[..., 0], -10, axis=1)
            f = f*vig + grains[fi % 6]
            if t < .6: f *= t/.6
            if t > DUR - 1.0: f *= max(0, (DUR - t))/1.0
            fr = np.clip(f, 0, 255).astype(np.uint8)
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
