"""Animated motion graphics: maps (Natural Earth, public domain) and explanatory diagrams.

  python3 tools/gfx.py [ids...]
For every map/diagram shot writes build/gfx/<id>/: base.png (2304x1296), layer PNGs and spec.json.
spec.json layers (times are fractions of the shot's duration, eased in the editor):
  {"t":"img","f":"l3.png","a":[t0,t1]}                      fade a drawn layer in (territory, labels, arrows)
  {"t":"route","pts":[[x,y],..],"col":[r,g,b],"a":[t0,t1]}   a line that draws itself on (campaign routes)
  {"t":"unit","col":..,"label":"..","k":[[t,x,y,w,h,deg],..]}  a moving troop block (battle diagrams)
  {"t":"pulse","xy":[x,y],"col":..,"a":[t0,t1]}             a pulsing location marker
Plus "focus": [x,y] and "zoom": the camera pushes toward the focus (map-to-location move).
All coordinates are fractions of the frame. Borders are simplified and labelled approximate on screen.
"""
import json, os, sys, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'gfx')
FONTS = os.path.join(ROOT, '..', 'assets', 'fonts')
NE = '/home/user/models/ne'
W, H = 3840, 2160; OW, OH = 2304, 1296
INK, SEA, LAND, GOLD = (58, 42, 28), (150, 160, 152), (226, 210, 172), (176, 132, 52)
CAR, ROM, NUM, GRK, MAC, NEU = (118, 46, 104), (160, 44, 36), (150, 120, 40), (52, 82, 130), (70, 96, 120), (110, 100, 86)

TEXTS = []   # every word drawn on a map or diagram, saved into spec.json for the QC text register
def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), int(size * 1.35))
SER, ITA, CAP = 'CormorantGaramond.ttf', 'CormorantGaramond-Italic.ttf', 'Cinzel.ttf'

_land, _riv = None, None
def land():
    global _land
    if _land is None:
        g = json.load(open(os.path.join(NE, 'land10.geojson'))); _land = []
        for f in g['features']:
            geo = f['geometry']; rings = [geo['coordinates']] if geo['type'] == 'Polygon' else geo['coordinates']
            for p in rings: _land.append(p[0])
    return _land

def rivers(names):
    global _riv
    if _riv is None: _riv = json.load(open(os.path.join(NE, 'rivers10.geojson')))['features']
    out = []
    for f in _riv:
        if f['properties'].get('name') in names:
            g = f['geometry']; out += [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
    return out

class Proj:
    def __init__(self, lon0, lon1, lat0, lat1):
        self.lon0, self.lat1 = lon0, lat1; self.cos = math.cos(math.radians((lat0 + lat1) / 2))
        s = min(W / ((lon1 - lon0) * self.cos), H / (lat1 - lat0))
        self.s = s; self.ox = (W - (lon1 - lon0) * self.cos * s) / 2; self.oy = (H - (lat1 - lat0) * s) / 2
    def __call__(self, lon, lat): return (self.ox + (lon - self.lon0) * self.cos * self.s, self.oy + (self.lat1 - lat) * self.s)
    def n(self, lon, lat): x, y = self(lon, lat); return [round(x / W, 4), round(y / H, 4)]

def paper(sea=SEA):
    rng = np.random.default_rng(7)
    n = rng.normal(0, 1, (H // 8, W // 8)).astype(np.float32)
    n = np.array(Image.fromarray(((n * 18) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(6)), np.float32) - 128
    return np.ones((H, W, 3), np.float32) * np.array(sea, np.float32) + n[..., None] * 0.35

def vignette(a):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    return a * (1 - 0.42 * np.clip(r - 0.55, 0, 1) ** 1.4)[..., None]

class Gfx:
    """One graphic: a base image plus animated layers."""
    def __init__(self, sid):
        self.sid, self.layers, self.focus, self.zoom = sid, [], None, 1.10
        self.dir = os.path.join(OUT, sid); os.makedirs(self.dir, exist_ok=True)
    def layer(self):
        return Image.new('RGBA', (W, H), (0, 0, 0, 0))
    def add(self, img, a, fix=False):
        f = f'l{len(self.layers)}.png'; img.resize((OW, OH), Image.LANCZOS).save(os.path.join(self.dir, f))
        self.layers.append({'t': 'img', 'f': f, 'a': a, 'fix': fix})
    def route(self, pts, col, a, w=9, dash=False):
        self.layers.append({'t': 'route', 'pts': pts, 'col': list(col), 'a': a, 'w': w, 'dash': dash})
    def pulse(self, xy, col, a): self.layers.append({'t': 'pulse', 'xy': xy, 'col': list(col), 'a': a})
    def unit(self, col, label, k):
        if label: TEXTS.append(label)
        self.layers.append({'t': 'unit', 'col': list(col), 'label': label, 'k': k})
    def save(self, base):
        Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).resize((OW, OH), Image.LANCZOS).save(os.path.join(self.dir, 'base.png'))
        json.dump({'layers': self.layers, 'focus': self.focus, 'zoom': self.zoom, 'texts': list(dict.fromkeys(TEXTS))}, open(os.path.join(self.dir, 'spec.json'), 'w'))

# ------------------------------------------------------------------ map drawing helpers
def land_mask(P):
    m = Image.new('L', (W, H), 0); d = ImageDraw.Draw(m)
    for ring in land():
        pts = [P(x, y) for x, y in ring]
        if all(p[0] < -300 or p[0] > W + 300 for p in pts) or all(p[1] < -300 or p[1] > H + 300 for p in pts): continue
        d.polygon(pts, fill=255)
    return m

def map_base(P, river_names=(), extra_rivers=()):
    a = paper(); m = land_mask(P); ma = np.array(m, np.float32)[..., None] / 255
    a = a * (1 - ma) + np.array(LAND, np.float32) * ma + (paper(LAND) - np.array(LAND, np.float32)) * ma * 0.6
    halo = np.array(m.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(10)), np.float32)[..., None] / 255 * (1 - ma)
    a = a * (1 - halo * 0.18) + np.array(INK, np.float32) * halo * 0.18
    e = np.array(m.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)), np.float32)[..., None] / 255
    a = a * (1 - e * 0.75) + np.array(INK, np.float32) * e * 0.75
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(img)
    for ln in rivers(river_names) + [list(r) for r in extra_rivers]:
        d.line([P(*q) for q in ln], fill=(110, 128, 140), width=6, joint='curve')
    return np.array(img, np.float32), m

def territory(G, P, mask, polys, col, a, alpha=0.42, hatch=False, blur=10):
    reg = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(reg)
    for q in polys: dr.polygon([P(x, y) for x, y in q], fill=255)
    reg = Image.fromarray(np.minimum(np.array(reg.filter(ImageFilter.GaussianBlur(blur))), np.array(mask)))
    r = np.array(reg, np.float32) / 255
    if hatch:
        yy, xx = np.mgrid[0:H, 0:W]; r = r * (((xx + yy) // 18) % 3 == 0)
    edge = np.array(reg.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)), np.float32) / 255
    L = np.zeros((H, W, 4), np.uint8); L[..., :3] = col
    L[..., 3] = np.clip((r * alpha + edge * 0.55) * 255, 0, 255).astype(np.uint8)
    G.add(Image.fromarray(L), a)

def text_layer(items):
    """items: (xy, text, size, fontname, colour, anchor) drawn with a soft paper halo for legibility."""
    TEXTS.extend(t for _, t, *_ in items)
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    for xy, t, size, fn, col, anc in items:
        d.text(xy, t, font=font(fn, size), fill=tuple(col) + (255,), anchor=anc, stroke_width=max(2, size // 22), stroke_fill=(236, 224, 196, 200))
    return L

def city(P, lon, lat, name, size=70, dx=0, dy=-70, star=False, col=INK):
    TEXTS.append(name)
    x, y = P(lon, lat); r = 22 if star else 14
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.ellipse([x - r, y - r, x + r, y + r], fill=(GOLD if star else col) + (255,), outline=INK + (255,), width=5)
    d.text((x + dx, y + dy), name, font=font(CAP, size), fill=col + (255,), anchor='mm', stroke_width=3, stroke_fill=(236, 224, 196, 220))
    return L

def cities(G, P, rows, a):
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for r in rows: L = Image.alpha_composite(L, city(P, *r))
    G.add(L, a)

def legend(rows, note='borders approximate'):
    TEXTS.extend([t for _, t in rows] + ([note] if note else []))
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L); y = H - 150 - 115 * (len(rows) - 1)
    for col, text in rows:
        d.rectangle([120, y - 26, 184, y + 26], fill=tuple(col) + (230,), outline=INK + (255,), width=3)
        d.text((214, y), text, font=font(ITA, 60), fill=INK + (255,), anchor='lm'); y += 115
    if note: d.text((W - 70, H - 60), note, font=font(ITA, 54), fill=INK + (255,), anchor='rd')
    return L

def title(text, sub=None):
    TEXTS.extend([text] + ([sub] if sub else []))
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L)
    d.text((W / 2, 150), text, font=font(CAP, 80), fill=INK + (255,), anchor='mm', stroke_width=3, stroke_fill=(236, 224, 196, 220))
    if sub: d.text((W / 2, 285), sub, font=font(ITA, 58), fill=INK + (255,), anchor='mm', stroke_width=3, stroke_fill=(236, 224, 196, 230))
    return L

def finish(G, base): G.save(vignette(base))

# frequently used places (lon, lat)
PL = dict(Tyre=(35.2, 33.27), Sidon=(35.37, 33.56), Byblos=(35.65, 34.12), Carthage=(10.33, 36.85), Utica=(10.06, 37.06), Gades=(-6.29, 36.53),
          Kition=(33.63, 34.92), Motya=(12.47, 37.87), Rome=(12.5, 41.9), Syracuse=(15.29, 37.08), Messana=(15.55, 38.19), Panormus=(13.36, 38.12),
          Eryx=(12.59, 38.03), Lilybaeum=(12.44, 37.8), NewCarthage=(-0.99, 37.6), Saguntum=(-0.27, 39.68), Massalia=(5.37, 43.3),
          Placentia=(9.69, 45.05), Cannae=(16.13, 41.3), Capua=(14.25, 41.08), Tarentum=(17.24, 40.47), Zama=(9.43, 36.1), Hadrumetum=(10.64, 35.83),
          Ephesus=(27.34, 37.94), Gortyn=(24.95, 35.06), Libyssa=(29.43, 40.8), Corinth=(22.88, 37.9), Tarraco=(1.25, 41.12), Ilipa=(-5.98, 37.52),
          Baecula=(-3.77, 38.09), Castulo=(-3.63, 38.03), Pella=(22.52, 40.76), Croton=(17.13, 39.08), Canusium=(16.07, 41.22), Tunes=(10.18, 36.8))
ITALY = [(6.6, 45.2), (7.0, 46.0), (10.5, 46.6), (13.8, 46.6), (13.6, 45.6), (12.4, 44.2), (14.2, 42.2), (16.2, 41.5), (18.6, 40.2), (17.0, 39.0),
         (16.5, 38.0), (15.6, 37.9), (15.7, 39.5), (14.5, 40.6), (12.0, 41.5), (10.4, 43.0), (8.0, 43.8)]
ITALY_S = [(9.6, 44.4), (12.6, 44.4), (13.9, 43.7), (14.6, 42.6), (15.2, 42.1), (16.2, 41.5), (18.6, 40.2), (17.0, 39.0), (16.5, 38.0), (15.6, 37.9), (15.7, 39.5), (14.5, 40.6), (12.0, 41.5), (10.4, 43.0)]
SICILY = [(12.2, 38.4), (15.8, 38.4), (15.3, 36.5), (12.2, 37.5)]
SIC_W = [(12.2, 38.4), (13.9, 38.3), (14.0, 37.0), (12.2, 37.5)]
SYRAC = [(14.6, 38.0), (15.8, 38.3), (15.3, 36.5), (14.3, 36.7)]
SARD = [(7.8, 41.4), (10.0, 41.4), (10.0, 38.7), (7.8, 38.7)]
CORS = [(8.3, 43.1), (9.7, 43.1), (9.7, 41.3), (8.3, 41.3)]
BAL = [(1.1, 39.2), (1.75, 39.2), (1.75, 38.6), (1.1, 38.6)]   # Ebusus (Ibiza) and Formentera only
AFR = [(-5.9, 35.9), (-5.3, 36.0), (-2.0, 35.2), (0.0, 36.0), (3.0, 36.9), (6.0, 37.2), (8.6, 37.1), (9.2, 37.4), (10.3, 37.5), (11.2, 37.2),
       (11.2, 36.4), (10.8, 35.5), (11.2, 35.2), (10.5, 34.4), (10.1, 33.8), (10.5, 33.5), (11.5, 33.2), (13.2, 32.9), (15.4, 32.4), (15.3, 31.8), (13.0, 32.4),
       (11.0, 32.9), (9.8, 33.3), (9.0, 34.5), (8.4, 35.8), (8.5, 36.6), (6.0, 36.7), (3.0, 36.4), (0.0, 35.5), (-2.0, 34.8), (-5.3, 35.5), (-5.9, 35.5)]
AFR_CORE = [(8.6, 37.1), (9.2, 37.4), (10.3, 37.5), (11.2, 37.2), (11.2, 36.4), (10.8, 35.5), (11.2, 35.2), (10.5, 34.4), (10.1, 33.8), (10.5, 33.5), (11.5, 33.2),
            (13.2, 32.9), (15.4, 32.4), (15.3, 31.8), (13.0, 32.4), (11.0, 32.9), (9.8, 33.3), (9.0, 34.5), (8.4, 35.8)]
SPAIN_S = [(-6.4, 37.0), (-5.6, 35.95), (-4.0, 36.6), (-2.0, 36.7), (-1.6, 37.3), (-1.9, 37.55), (-3.0, 37.1), (-5.0, 36.9), (-6.2, 37.3)]   # Gades to Baria, before the Barcids
SPAIN_B = [(-7.4, 37.2), (-6.2, 36.6), (-5.6, 35.95), (-2.0, 36.6), (0.2, 38.6), (-0.15, 39.45), (-0.6, 39.6), (-1.6, 40.2), (-3.5, 40.2), (-5.5, 39.5), (-7.2, 38.6)]
NUMIDIA = [(-1.8, 35.9), (2.0, 37.3), (6.0, 37.7), (8.5, 37.4), (8.4, 35.8), (9.0, 34.5), (8.2, 33.9), (4.0, 34.3), (0.0, 34.5), (-1.8, 34.7)]
NUMID_GAIN = [(8.5, 37.0), (9.3, 37.1), (9.6, 36.4), (10.2, 35.8), (10.6, 35.4), (10.4, 34.6), (10.1, 33.8), (10.5, 33.5), (11.5, 33.2), (13.2, 32.9),
              (15.4, 32.4), (15.3, 31.8), (13.0, 32.4), (11.0, 32.9), (9.8, 33.3), (9.0, 34.5), (8.4, 35.8)]
CAR_150 = [(9.3, 37.1), (10.3, 37.5), (11.2, 37.2), (11.2, 36.4), (10.6, 35.4), (10.2, 35.8), (9.6, 36.4)]
MACED = [(20.5, 41.9), (22.0, 42.3), (23.5, 41.6), (24.6, 41.0), (23.8, 40.6), (22.6, 40.3), (22.4, 39.9), (21.2, 39.9), (20.5, 40.6)]
HISP_R = [(-7.4, 37.2), (-5.6, 35.95), (-2.0, 36.6), (0.2, 38.6), (0.6, 40.6), (3.2, 41.9), (3.2, 42.4), (1.5, 42.5), (-1.0, 42.2), (-2.2, 41.4), (-3.5, 40.0), (-5.5, 38.9), (-7.2, 38.3)]
PROV_AFR = [(8.8, 37.0), (9.4, 37.3), (10.3, 37.4), (11.2, 37.1), (11.1, 36.3), (10.7, 35.6), (10.4, 35.2), (9.6, 35.6), (9.1, 36.4)]
CISALP = [(6.6, 45.2), (7.0, 46.0), (10.5, 46.6), (13.8, 46.6), (13.6, 45.6), (12.4, 44.1), (10.0, 44.1), (8.0, 43.8)]
RHONE = [(4.85, 43.35), (4.63, 43.68), (4.8, 44.0), (4.72, 44.5), (4.85, 44.95), (4.8, 45.5), (4.85, 45.76), (5.6, 46.1), (6.15, 46.2)]
PO = [(7.6, 45.0), (8.6, 45.1), (9.7, 45.08), (10.8, 45.0), (11.8, 45.0), (12.4, 44.95)]
ISERE = [(4.88, 45.05), (5.5, 45.2), (6.0, 45.45), (6.6, 45.6)]

def R(P, *names): return [P.n(*PL[n]) if isinstance(n, str) else P.n(*n) for n in names]

# ------------------------------------------------------------------ maps
def m_phoenicia(G):
    P = Proj(27, 40, 29.5, 38.5); base, mask = map_base(P)
    G.add(title('PHOENICIA', 'c. 900 BC'), [0.0, 0.12], fix=True)
    territory(G, P, mask, [[(34.8, 32.9), (35.55, 32.9), (36.05, 34.6), (35.95, 35.25), (35.5, 35.3), (34.8, 34.0)]], CAR, [0.1, 0.35], alpha=0.55)
    cities(G, P, [(*PL['Tyre'], 'Tyre', 74, -190, 40, True), (*PL['Sidon'], 'Sidon', 64, -190, -20), (*PL['Byblos'], 'Byblos', 64, -190, 0)], [0.3, 0.5])
    G.pulse(P.n(*PL['Tyre']), GOLD, [0.5, 1.0]); G.focus = P.n(35.3, 33.6); G.zoom = 1.22; finish(G, base)

def m_trade(G):
    P = Proj(-10, 37, 29, 46); base, mask = map_base(P)
    G.add(title('THE PHOENICIAN WEST', 'trading posts, 9th to 7th centuries BC'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PL['Tyre'], 'Tyre', 64, 0, -70, True)], [0.0, 0.1])
    G.route(R(P, 'Tyre', (33.0, 34.4), 'Kition'), CAR, [0.1, 0.25]); cities(G, P, [(*PL['Kition'], 'Kition', 56, 0, -70)], [0.2, 0.3])
    G.route(R(P, 'Kition', (28, 34.6), (22, 35.6), (16, 36.6), 'Motya'), CAR, [0.25, 0.45]); cities(G, P, [(*PL['Motya'], 'Motya', 56, 0, -70)], [0.42, 0.5])
    G.route(R(P, 'Motya', (11.0, 37.5), 'Carthage'), CAR, [0.45, 0.55]); cities(G, P, [(*PL['Carthage'], 'Carthage', 66, 0, 80, True)], [0.52, 0.6])
    G.route(R(P, 'Motya', (10.5, 38.6), (9.0, 39.0)), CAR, [0.55, 0.65]); cities(G, P, [(8.6, 39.1, 'Sardinia', 52, 0, -70)], [0.62, 0.7])
    G.route(R(P, 'Carthage', (5, 37.6), (-1, 36.6), (-5.6, 36.0), 'Gades'), CAR, [0.6, 0.85]); cities(G, P, [(*PL['Gades'], 'Gades', 60, 0, 80)], [0.82, 0.9])
    G.focus = None; G.zoom = 1.02; finish(G, base)

def m_empire300(G):
    P = Proj(-10, 20, 30.5, 45); base, mask = map_base(P)
    G.add(title('CARTHAGE AND ITS EMPIRE', 'c. 300 BC'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PL['Carthage'], 'Carthage', 72, 0, 85, True)], [0.0, 0.1]); G.pulse(P.n(*PL['Carthage']), GOLD, [0.0, 0.3])
    territory(G, P, mask, [AFR], CAR, [0.1, 0.3]); territory(G, P, mask, [SIC_W], CAR, [0.3, 0.45])
    territory(G, P, mask, [SARD], CAR, [0.42, 0.57]); territory(G, P, mask, [BAL], CAR, [0.55, 0.68]); territory(G, P, mask, [SPAIN_S], CAR, [0.66, 0.8])
    cities(G, P, [(*PL['Gades'], 'Gades', 56, 0, 75), (*PL['Rome'], 'Rome', 56, 0, -70), (*PL['Syracuse'], 'Syracuse', 52, 130, 50)], [0.75, 0.88])
    G.add(legend([(CAR, 'Carthaginian control, c. 300 BC')]), [0.8, 0.95], fix=True); finish(G, base)

def m_sicily264(G):
    P = Proj(8, 19, 35.5, 42.8); base, mask = map_base(P)
    G.add(title('SICILY, 264 BC'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [ITALY_S], ROM, [0.05, 0.3]); territory(G, P, mask, [SIC_W], CAR, [0.2, 0.4]); territory(G, P, mask, [SYRAC], GRK, [0.35, 0.5])
    cities(G, P, [(*PL['Rome'], 'Rome', 64, 0, -70, True), (*PL['Carthage'], 'Carthage', 64, 0, -75, True), (*PL['Syracuse'], 'Syracuse', 56, 160, 40),
                  (*PL['Messana'], 'Messana', 60, 170, -40)], [0.45, 0.6])
    G.pulse(P.n(*PL['Messana']), ROM, [0.6, 1.0]); G.route(R(P, (15.7, 38.6), (15.58, 38.25)), ROM, [0.65, 0.8], w=12)
    G.add(legend([(ROM, 'Rome and its allies'), (CAR, 'Carthage'), (GRK, 'Syracuse')]), [0.55, 0.7], fix=True); G.focus = P.n(*PL['Messana']); G.zoom = 1.16; finish(G, base)

def m_regulus(G):
    P = Proj(8, 17, 34.5, 39.5); base, mask = map_base(P)
    G.add(title('THE INVASION OF AFRICA', '256 BC'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PL['Carthage'], 'Carthage', 64, -40, 80, True), (13.9, 37.1, 'Ecnomus', 52, 0, -60), (11.1, 36.84, 'Aspis', 52, 60, 75), (*PL['Messana'], 'Messana', 52, 0, -60)], [0.05, 0.2])
    G.route(R(P, (15.5, 38.1), (15.3, 37.2), (14.7, 36.7), (13.9, 37.0)), ROM, [0.2, 0.45]); G.add(text_layer([(P(13.6, 36.6), 'naval battle', 50, ITA, INK, 'mm')]), [0.42, 0.5])
    G.route(R(P, (13.9, 37.0), (12.4, 36.9), (11.15, 36.85)), ROM, [0.48, 0.7]); G.route(R(P, (11.1, 36.8), (10.6, 36.7), (10.25, 36.78)), ROM, [0.72, 0.92], w=7, dash=True)
    G.focus = P.n(10.8, 36.8); G.zoom = 1.18; finish(G, base)

def m_aegates(G):
    P = Proj(11.6, 13.3, 37.55, 38.35); base, mask = map_base(P)
    G.add(title('THE AEGATES ISLANDS', '241 BC'), [0.0, 0.1], fix=True)
    isl = [r for r in land() if all(11.9 < x < 12.45 and 37.85 < y < 38.1 for x, y in r)]
    cx = sum(sum(x for x, _ in r) / len(r) for r in isl) / max(1, len(isl)); cy = sum(sum(y for _, y in r) / len(r) for r in isl) / max(1, len(isl))
    G.add(text_layer([(P(cx, cy - 0.11), 'Aegates Islands', 62, ITA, INK, 'mm')]), [0.05, 0.2])
    cities(G, P, [(12.51, 38.02, 'Drepana', 60, 190, -30), (*PL['Lilybaeum'], 'Lilybaeum', 60, 220, 0)], [0.05, 0.2])
    G.route([P.n(11.75, 38.12), P.n(12.0, 38.14), P.n(12.25, 38.1)], CAR, [0.2, 0.5]); G.route([P.n(12.5, 38.03), P.n(12.4, 38.08), P.n(12.3, 38.1)], ROM, [0.3, 0.55])
    G.pulse(P.n(12.27, 38.1), (200, 60, 40), [0.55, 1.0]); G.add(legend([(CAR, 'Carthaginian supply fleet'), (ROM, 'Roman fleet')], 'positions approximate'), [0.5, 0.65], fix=True)
    G.focus = P.n(12.25, 38.03); G.zoom = 1.1; finish(G, base)

def m_241(G):
    P = Proj(-8, 20, 30.5, 46); base, mask = map_base(P)
    G.add(title('AFTER THE FIRST WAR', '241 BC'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [ITALY_S], ROM, [0.0, 0.1]); territory(G, P, mask, [AFR, SARD, SPAIN_S], CAR, [0.0, 0.1])
    territory(G, P, mask, [SICILY], ROM, [0.2, 0.55], alpha=0.5); G.add(text_layer([(P(14.2, 37.2), 'SICILY', 64, CAP, (110, 30, 24), 'mm'), (P(14.2, 36.6), 'first Roman province', 52, ITA, INK, 'mm')]), [0.45, 0.6])
    G.add(legend([(ROM, 'Rome'), (CAR, 'Carthage')]), [0.1, 0.25], fix=True); G.focus = P.n(13.5, 37.6); G.zoom = 1.12; finish(G, base)

def m_sardinia(G):
    P = Proj(2, 20, 34, 46); base, mask = map_base(P)
    G.add(title('ROME SEIZES SARDINIA', '238 BC'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [ITALY_S, SICILY], ROM, [0.0, 0.1]); territory(G, P, mask, [AFR_CORE], CAR, [0.0, 0.1])
    territory(G, P, mask, [SARD], CAR, [0.0, 0.1]); territory(G, P, mask, [SARD], ROM, [0.3, 0.6], alpha=0.75)
    G.route(R(P, (12.0, 41.8), (10.3, 41.0)), ROM, [0.25, 0.5], w=12); G.add(legend([(ROM, 'Rome'), (CAR, 'Carthage')]), [0.1, 0.25], fix=True)
    G.focus = P.n(9.0, 40.5); G.zoom = 1.18; finish(G, base)

def m_spain(G, ebro=False, sag=False):
    P = Proj(-10.5, 4.5, 35.5, 44) if not sag else Proj(-3.5, 2.5, 37.8, 41.7); base, mask = map_base(P, ('Ebro', 'Guadalquivir'))
    if not sag:
        G.add(title('CARTHAGINIAN SPAIN', '237–219 BC' if not ebro else 'the Ebro treaty, 226 BC'), [0.0, 0.1], fix=True)
        territory(G, P, mask, [SPAIN_S], CAR, [0.0, 0.1]); territory(G, P, mask, [SPAIN_B], CAR, [0.1, 0.45], blur=32)
        cities(G, P, [(*PL['Gades'], 'Gades', 60, 0, 75), (*PL['NewCarthage'], 'New Carthage', 64, 0, 80, True)], [0.2, 0.35])
        G.add(text_layer([(P(-4.6, 38.6), 'silver mines', 58, ITA, INK, 'mm'), (P(0.0, 41.45), 'River Ebro', 56, ITA, (60, 80, 100), 'mm')]), [0.35, 0.5])
        if ebro:
            eb = max(rivers(('Ebro',)), key=len); eb = eb[::max(1, len(eb) // 40)]
            G.route([P.n(*q) for q in eb[::-1]], (40, 40, 40), [0.45, 0.7], w=7, dash=True)
            cities(G, P, [(*PL['Saguntum'], 'Saguntum', 60, 270, 0)], [0.65, 0.78]); G.pulse(P.n(*PL['Saguntum']), ROM, [0.75, 1.0]); G.focus = P.n(-0.3, 39.7)
        else: G.focus = P.n(-3, 38.3)
        G.add(legend([(CAR, 'Carthaginian control')]), [0.4, 0.55], fix=True)
    else:
        G.add(title('SAGUNTUM', '219 BC'), [0.0, 0.1], fix=True); territory(G, P, mask, [SPAIN_B], CAR, [0.0, 0.1], alpha=0.3, blur=32)
        cities(G, P, [(*PL['NewCarthage'], 'New Carthage', 60, 0, 80, True), (*PL['Saguntum'], 'Saguntum', 64, 230, 0)], [0.05, 0.2])
        G.add(text_layer([(P(0.3, 40.45), 'Ebro', 60, ITA, (60, 80, 100), 'mm')]), [0.05, 0.2])
        G.route(R(P, 'NewCarthage', (-0.6, 38.6), (-0.4, 39.4), (-0.32, 39.62)), CAR, [0.25, 0.6]); G.pulse(P.n(*PL['Saguntum']), (200, 60, 40), [0.6, 1.0])
        G.focus = P.n(-0.5, 39.0); G.zoom = 1.08
    finish(G, base)

HANNIBAL = [PL['NewCarthage'], (-0.6, 38.7), PL['Saguntum'], (0.3, 40.6), (1.4, 41.4), (2.6, 42.0), (2.9, 42.45), (3.0, 43.2), (4.2, 43.8),
            (4.72, 43.98), (4.85, 44.6), (4.95, 45.0), (5.7, 45.2), (6.4, 45.4), (6.9, 45.25), (7.4, 45.1), (7.68, 45.07), (8.6, 45.1), (9.3, 45.1)]
def m_plan218(G):
    P = Proj(-8, 18, 34, 47.5); base, mask = map_base(P)
    G.add(title('THE PLANS OF 218 BC'), [0.0, 0.08], fix=True)
    territory(G, P, mask, [ITALY_S, SICILY, SARD, CORS], ROM, [0.0, 0.08]); territory(G, P, mask, [AFR_CORE, SPAIN_B], CAR, [0.0, 0.08])
    cities(G, P, [(*PL['Rome'], 'Rome', 60, 0, -70, True), (*PL['Carthage'], 'Carthage', 60, -60, 80, True), (*PL['NewCarthage'], 'New Carthage', 54, 0, 75)], [0.0, 0.1])
    G.route(R(P, 'Rome', (11.2, 42.4), (9.0, 43.2), (6.2, 43.0), 'Massalia', (3.5, 42.6), (2.0, 41.4)), ROM, [0.1, 0.35])
    G.route(R(P, (15.2, 38.0), (13.0, 37.9), 'Lilybaeum', (11.4, 37.4), (10.5, 37.0)), ROM, [0.3, 0.5])
    G.add(text_layer([(P(3.6, 40.8), 'to Spain', 56, ITA, ROM, 'mm'), (P(13.3, 36.9), 'to Africa', 56, ITA, ROM, 'mm')]), [0.45, 0.55])
    G.route([P.n(*q) for q in HANNIBAL], CAR, [0.55, 0.95], w=8, dash=True); G.add(text_layer([(P(1.2, 44.2), "Hannibal's plan", 60, ITA, CAR, 'mm')]), [0.85, 0.95])
    finish(G, base)

def m_march(G, part):
    P = Proj(-3, 11.5, 36.8, 47) if part == 2 else Proj(-3, 6, 36.8, 44.5)
    base, mask = map_base(P, ('Ebro', 'Durance'), [RHONE, PO, ISERE])
    G.add(title("HANNIBAL'S MARCH", '218 BC'), [0.0, 0.08], fix=True); territory(G, P, mask, [SPAIN_B], CAR, [0.0, 0.08], blur=32)
    pts = HANNIBAL if part == 2 else HANNIBAL[:8]
    G.route([P.n(*q) for q in pts], CAR, [0.08, 0.85], w=11)
    rows = [(*PL['NewCarthage'], 'New Carthage', 58, 0, 75, True), (0.87, 40.72, 'Ebro', 52, 120, 0), (2.9, 42.45, 'Pyrenees', 56, 190, -10)]
    if part == 2: rows += [(4.72, 43.98, 'Rhône', 52, -150, 0), (6.9, 45.25, 'Alps', 60, 0, 85), (9.3, 45.1, 'Po valley', 56, 40, -75)]
    cities(G, P, rows, [0.1, 0.25]); end = pts[-1]; G.pulse(P.n(*end), CAR, [0.85, 1.0]); G.focus = P.n(*end) if part == 2 else P.n(2.9, 42.4); G.zoom = 1.12
    G.add(legend([(CAR, "Hannibal's route")], 'route approximate'), [0.2, 0.35], fix=True); finish(G, base)

def m_rhone(G):
    P = Proj(2.6, 7.2, 42.6, 45.4); base, mask = map_base(P, ('Durance',), [RHONE, ISERE])
    G.add(title('THE RHÔNE', 'late summer 218 BC'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PL['Massalia'], 'Massalia', 60, 60, -75)], [0.05, 0.2])
    G.route(R(P, (3.6, 43.5), (4.3, 43.8), (4.72, 43.98), (4.83, 44.5), (4.95, 45.0), (5.7, 45.2)), CAR, [0.15, 0.55], w=11)
    G.route(R(P, (7.0, 42.8), (6.0, 43.0), (5.0, 43.25), (4.6, 43.4)), ROM, [0.45, 0.75]); G.pulse(P.n(4.6, 43.4), ROM, [0.75, 1.0])
    G.add(text_layer([(P(4.62, 44.0), 'Hannibal crosses', 52, ITA, CAR, 'rm'), (P(5.3, 42.95), "Scipio's fleet", 52, ITA, ROM, 'mm'), (P(4.4, 43.2), 'three days too late', 50, ITA, INK, 'rm')]), [0.55, 0.8])
    finish(G, base)

def m_passes(G):
    P = Proj(4.8, 9.2, 43.8, 46.6); base, mask = map_base(P, ('Durance',), [RHONE, PO, ISERE])
    G.add(title('WHICH PASS?', 'main theories'), [0.0, 0.1], fix=True)
    passes = [(6.88, 45.68, 'Little St Bernard'), (6.9, 45.25, 'Mont Cenis'), (6.98, 45.15, 'Col du Clapier'), (7.05, 44.68, 'Col de la Traversette')]
    for k, (lo, la, nm) in enumerate(passes):
        t0 = 0.15 + 0.17 * k; G.route(R(P, (5.9, 45.2 + (la - 45.2) * 0.6), (lo, la), (7.6, 45.05)), CAR, [t0, t0 + 0.15], w=7, dash=True)
        cities(G, P, [(lo, la, nm, 54, *{0: (0, -60), 1: (0, -60), 2: (60, 65), 3: (0, 70)}[k])], [t0 + 0.1, t0 + 0.18])
    cities(G, P, [(7.68, 45.07, 'Taurini (Turin)', 56, 400, 0)], [0.05, 0.15]); finish(G, base)

def m_north_italy(G):
    P = Proj(6.5, 13.5, 43.0, 46.6); base, mask = map_base(P, (), [PO, [(9.45, 44.6), (9.55, 44.85), (9.62, 45.05)], [(8.8, 46.0), (9.0, 45.5), (9.16, 45.15)]])
    G.add(title('NORTHERN ITALY', 'late 218 BC'), [0.0, 0.1], fix=True)
    G.route(R(P, (6.9, 45.25), (7.68, 45.07), (8.6, 45.15), (9.1, 45.2)), CAR, [0.1, 0.4], w=11)
    cities(G, P, [(*PL['Placentia'], 'Placentia', 56, 230, -10), (9.16, 45.19, 'Ticinus', 50, -60, -70), (9.55, 44.85, 'Trebia', 50, -150, 50)], [0.35, 0.55])
    G.pulse(P.n(9.16, 45.19), ROM, [0.5, 0.75]); G.pulse(P.n(9.57, 44.95), (200, 60, 40), [0.75, 1.0]); G.focus = P.n(9.4, 45.0); G.zoom = 1.2; finish(G, base)

def m_to_cannae(G):
    P = Proj(8, 19, 38.5, 45.5); base, mask = map_base(P)
    G.add(title('TO CANNAE', '217–216 BC'), [0.0, 0.1], fix=True)
    G.route(R(P, (12.1, 43.15), (13.0, 43.4), (13.8, 42.8), (14.6, 42.1), (15.0, 41.7), 'Cannae'), CAR, [0.1, 0.65], w=11)
    cities(G, P, [(12.1, 43.15, 'Trasimene', 54, -60, 75), (*PL['Rome'], 'Rome', 58, -40, 70, True), (*PL['Cannae'], 'Cannae', 64, 0, 80)], [0.05, 0.2])
    G.pulse(P.n(*PL['Cannae']), (200, 60, 40), [0.65, 1.0]); G.focus = P.n(*PL['Cannae']); G.zoom = 1.3; finish(G, base)

def m_after_cannae(G):
    P = Proj(8, 19, 38, 45.5); base, mask = map_base(P)
    G.add(title('ITALY AFTER CANNAE', '216–211 BC'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [ITALY_S], ROM, [0.0, 0.1]); territory(G, P, mask, [[(14.0, 41.4), (15.2, 41.6), (16.6, 41.2), (18.6, 40.2), (17.0, 39.0), (16.5, 38.0), (15.6, 37.9), (15.7, 39.5), (14.3, 40.7)]], CAR, [0.4, 0.7], alpha=0.38, hatch=True)
    cities(G, P, [(*PL['Rome'], 'Rome', 60, -110, 10, True), (*PL['Cannae'], 'Cannae', 56, 0, 75), (*PL['Capua'], 'Capua', 56, -110, 30), (*PL['Tarentum'], 'Tarentum', 52, 0, 70)], [0.05, 0.2])
    G.route(R(P, 'Cannae', (14.6, 41.6), 'Rome'), (60, 50, 40), [0.15, 0.35], w=6, dash=True); G.add(text_layer([(P(14.6, 42.35), 'about 310 km in a straight line', 54, ITA, INK, 'mm')]), [0.3, 0.42])
    G.add(legend([(ROM, 'Rome and loyal allies'), (CAR, 'went over to Hannibal (much of the south)')]), [0.6, 0.75], fix=True); finish(G, base)

def m_fronts(G):
    P = Proj(-8, 27, 32, 46.5); base, mask = map_base(P)
    G.add(title('A WAR ON FOUR FRONTS', '215–212 BC'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [ITALY_S, SARD, CORS], ROM, [0.0, 0.1]); territory(G, P, mask, [AFR_CORE, SPAIN_B], CAR, [0.0, 0.1])
    for k, (pt, nm) in enumerate([((14.25, 41.08), 'Capua'), ((15.29, 37.08), 'Syracuse'), ((22.5, 40.8), 'Macedon'), ((-1.5, 39.5), 'Spain')]):
        t0 = 0.2 + 0.17 * k; cities(G, P, [(*pt, nm, 60, 0, -75)], [t0, t0 + 0.08]); G.pulse(P.n(*pt), (200, 60, 40), [t0, t0 + 0.4])
    territory(G, P, mask, [MACED], MAC, [0.65, 0.8]); G.add(legend([(ROM, 'Rome'), (CAR, 'Carthage'), (MAC, 'Macedon, allied to Carthage')]), [0.75, 0.9], fix=True); finish(G, base)

def m_metaurus(G):
    P = Proj(3, 18.5, 39.5, 47); base, mask = map_base(P, (), [PO, RHONE])
    G.add(title('THE METAURUS', '207 BC'), [0.0, 0.1], fix=True)
    G.route(R(P, (3.2, 43.4), (4.7, 44.0), (5.7, 45.2), (6.9, 45.25), (7.68, 45.07), 'Placentia', (11.3, 44.5), (12.6, 44.1), (13.0, 43.83)), CAR, [0.08, 0.5], w=10)
    G.route(R(P, 'Canusium', (15.6, 41.9), (14.6, 42.6), (13.8, 43.3), (13.05, 43.78)), ROM, [0.45, 0.8], w=10)
    cities(G, P, [(13.0, 43.83, 'Metaurus', 56, 250, -30), (*PL['Canusium'], 'Canusium', 50, 90, 60)], [0.1, 0.25]); G.pulse(P.n(13.0, 43.83), (200, 60, 40), [0.8, 1.0])
    G.add(legend([(CAR, 'Hasdrubal'), (ROM, 'Roman consul Nero, secret march north')], 'routes approximate'), [0.45, 0.6], fix=True); G.focus = P.n(13.0, 43.8); G.zoom = 1.15; finish(G, base)

def m_spain_scipio(G):
    P = Proj(-9.5, 4, 35.5, 43.5); base, mask = map_base(P, ('Ebro', 'Guadalquivir'))
    G.add(title("SCIPIO'S CAMPAIGNS IN SPAIN", '209–206 BC'), [0.0, 0.1], fix=True); territory(G, P, mask, [SPAIN_B], CAR, [0.0, 0.1], blur=32)
    G.route(R(P, 'Tarraco', (0.3, 40.2), (-0.4, 38.8), 'NewCarthage'), ROM, [0.1, 0.3]); cities(G, P, [(*PL['NewCarthage'], 'New Carthage 209', 52, 0, 75)], [0.28, 0.36])
    G.route(R(P, 'NewCarthage', (-2.2, 38.0), 'Baecula'), ROM, [0.36, 0.5]); cities(G, P, [(*PL['Baecula'], 'Baecula 208', 52, 0, -70)], [0.48, 0.55])
    G.route(R(P, 'Baecula', (-5.0, 37.7), 'Ilipa'), ROM, [0.55, 0.7]); cities(G, P, [(*PL['Ilipa'], 'Ilipa 206', 52, 0, -70)], [0.68, 0.75])
    G.route(R(P, 'Ilipa', 'Gades'), ROM, [0.75, 0.85]); territory(G, P, mask, [SPAIN_B], ROM, [0.85, 1.0], alpha=0.5, blur=32)
    cities(G, P, [(*PL['Tarraco'], 'Tarraco', 52, 0, -70, True)], [0.05, 0.15]); finish(G, base)

def m_africa202(G):
    P = Proj(7.5, 12.5, 34.5, 37.8); base, mask = map_base(P)
    G.add(title('NORTH AFRICA', '202 BC'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PL['Carthage'], 'Carthage', 64, 140, 60, True), (*PL['Utica'], 'Utica', 56, -140, 0), (*PL['Hadrumetum'], 'Hadrumetum', 54, 170, 0), (*PL['Zama'], 'Zama', 64, -40, 80)], [0.1, 0.35])
    G.add(text_layer([(P(9.2, 36.6), 'Zama: exact site uncertain', 50, ITA, INK, 'mm')]), [0.5, 0.65]); G.pulse(P.n(*PL['Zama']), (200, 60, 40), [0.4, 1.0])
    G.focus = P.n(*PL['Zama']); G.zoom = 1.2; finish(G, base)

def m_exile(G):
    P = Proj(6, 38, 30.5, 43); base, mask = map_base(P)
    G.add(title("HANNIBAL'S EXILE", '195–183 BC'), [0.0, 0.1], fix=True)
    G.route(R(P, 'Carthage', (14, 35.2), (22, 33.6), (30, 33.2), 'Tyre'), CAR, [0.1, 0.35]); G.route(R(P, 'Tyre', (32, 35.5), (29, 36.2), 'Ephesus'), CAR, [0.35, 0.55])
    G.route(R(P, 'Ephesus', (26.5, 36.5), 'Gortyn'), CAR, [0.55, 0.7]); G.route(R(P, 'Gortyn', (26.0, 37.8), (26.5, 40.3), 'Libyssa'), CAR, [0.7, 0.9])
    cities(G, P, [(*PL['Carthage'], 'Carthage', 56, 120, 75, True), (*PL['Tyre'], 'Tyre', 54, -110, 40), (*PL['Ephesus'], 'Ephesus', 52, 170, -60), (*PL['Gortyn'], 'Crete', 52, 0, 70),
                  (*PL['Libyssa'], 'Bithynia', 56, 0, -70)], [0.1, 0.3]); G.pulse(P.n(*PL['Libyssa']), CAR, [0.9, 1.0]); finish(G, base)

def m_numidia(G):
    P = Proj(-2, 14, 31.5, 38.5); base, mask = map_base(P)
    G.add(title('CARTHAGE AND NUMIDIA', 'c. 200 to 150 BC'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [AFR_CORE], CAR, [0.0, 0.1]); territory(G, P, mask, [NUMIDIA], NUM, [0.05, 0.2], blur=40)
    territory(G, P, mask, [NUMID_GAIN], NUM, [0.3, 0.75], alpha=0.75, blur=24)
    cities(G, P, [(*PL['Carthage'], 'Carthage', 60, -60, -70, True)], [0.0, 0.1]); G.add(legend([(CAR, 'Carthage'), (NUM, 'Numidia under Masinissa, growing at Carthage\'s expense')]), [0.15, 0.3], fix=True); finish(G, base)

def m_149(G):
    P = Proj(8.5, 14.5, 35.5, 39.0); base, mask = map_base(P)
    G.add(title('THE THIRD WAR BEGINS', '149 BC'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PL['Lilybaeum'], 'Lilybaeum', 56, 0, -70), (*PL['Utica'], 'Utica', 56, -190, -40), (*PL['Carthage'], 'Carthage', 60, 60, 80, True)], [0.05, 0.2])
    G.route(R(P, 'Lilybaeum', (11.6, 37.5), (10.4, 37.15), (10.1, 37.07)), ROM, [0.2, 0.7], w=12); G.pulse(P.n(*PL['Utica']), ROM, [0.7, 1.0]); G.focus = P.n(10.2, 36.95); G.zoom = 1.25; finish(G, base)

def m_inland(G):
    P = Proj(9.5, 11.2, 36.35, 37.35); base, mask = map_base(P)
    G.add(title('THE ROMAN ULTIMATUM', '149 BC'), [0.0, 0.1], fix=True); cities(G, P, [(*PL['Carthage'], 'Carthage', 62, 120, -30, True)], [0.0, 0.1])
    G.route([P.n(9.75, 37.2), P.n(9.95, 36.9), P.n(10.05, 36.68), P.n(10.25, 36.6), P.n(10.6, 36.55), P.n(10.85, 36.6)], (40, 40, 40), [0.2, 0.55], w=7, dash=True)
    G.add(text_layer([(P(10.05, 36.5), 'at least 80 stades (about 15 km) from the sea', 56, ITA, INK, 'mm')]), [0.5, 0.65]); G.focus = P.n(10.2, 36.75); G.zoom = 1.12; finish(G, base)

def m_146(G):
    P = Proj(-10, 30, 31, 47); base, mask = map_base(P)
    G.add(title('146 BC'), [0.0, 0.1], fix=True); territory(G, P, mask, [ITALY, SICILY, SARD, CORS, HISP_R], ROM, [0.05, 0.25])
    territory(G, P, mask, [MACED], ROM, [0.25, 0.4]); territory(G, P, mask, [PROV_AFR], ROM, [0.4, 0.6], alpha=0.6)
    cities(G, P, [(*PL['Carthage'], 'Carthage', 60, 0, 80), (*PL['Corinth'], 'Corinth', 60, 0, 75), (*PL['Rome'], 'Rome', 60, 0, -70, True)], [0.5, 0.65])
    G.pulse(P.n(*PL['Carthage']), (200, 60, 40), [0.6, 1.0]); G.pulse(P.n(*PL['Corinth']), (200, 60, 40), [0.7, 1.0])
    G.add(text_layer([(P(10.0, 34.8), 'province of Africa', 56, ITA, (110, 30, 24), 'mm')]), [0.55, 0.7]); G.add(legend([(ROM, 'Roman territory, 146 BC')]), [0.3, 0.45], fix=True); finish(G, base)

# ------------------------------------------------------------------ schematic diagrams
def dbase(dark=False):
    a = paper((226, 212, 178)); return a

def nrm(x, y): return [round(x / W, 4), round(y / H, 4)]

def city_plan(G, zoom_harbours=False):
    """Schematic plan of Carthage after the British and German excavations, simplified."""
    a = paper(SEA); img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(img)
    land_pts = [(0, 300), (900, 260), (1500, 120), (2300, 160), (2900, 380), (3300, 700), (3400, 1100), (3200, 1500), (2850, 1750), (2500, 1980), (1800, 2160), (0, 2160)]
    d.polygon(land_pts, fill=LAND); d.line(land_pts + [land_pts[0]], fill=INK, width=6)
    d.polygon([(0, 1150), (900, 1250), (1500, 1650), (1700, 2160), (0, 2160)], fill=(150, 162, 158)); d.line([(0, 1150), (900, 1250), (1500, 1650), (1700, 2160)], fill=INK, width=5)
    TEXTS.extend(['Lake of Tunis', 'Gulf of Tunis']); d.text((850, 1700), 'Lake of Tunis', font=font(ITA, 72), fill=INK, anchor='mm'); d.text((3450, 1650), 'Gulf of Tunis', font=font(ITA, 72), fill=INK, anchor='mm')
    return np.array(img, np.float32)

BYRSA, AGORA, CIRC, RECT = (1900, 1050), (2350, 1450), (2420, 1700), (2300, 1930)
def harbour_layers(G, a0):
    L = G.layer(); d = ImageDraw.Draw(L)
    d.rectangle([2150, 1860, 2520, 2050], fill=(150, 162, 158, 255), outline=INK + (255,), width=6)
    d.ellipse([2250, 1560, 2600, 1840], fill=(150, 162, 158, 255), outline=INK + (255,), width=6); d.line([(2400, 1860), (2420, 1835)], fill=(150, 162, 158, 255), width=40)
    d.ellipse([2370, 1650, 2480, 1750], fill=LAND + (255,), outline=INK + (255,), width=5)
    G.add(L, a0)

def d_harbours(G):
    base = dbase(); G.add(title('THE HARBOURS OF CARTHAGE', 'plan, after the excavations'), [0.0, 0.1], fix=True)
    cx, cy, R1, R2 = 2250, 1150, 650, 160
    L = G.layer(); d = ImageDraw.Draw(L); d.rectangle([600, 1500, 1500, 1950], fill=(150, 162, 158, 255), outline=INK + (255,), width=8); G.add(L, [0.05, 0.2])
    G.add(text_layer([((1050, 1725), 'merchant harbour', 70, ITA, INK, 'mm')]), [0.15, 0.25])
    L = G.layer(); d = ImageDraw.Draw(L); d.line([(1500, 1600), (1700, 1550)], fill=(150, 162, 158, 255), width=110); d.line([(1500, 1600), (1700, 1550)], fill=INK + (255,), width=4)
    d.ellipse([cx - R1, cy - R1, cx + R1, cy + R1], fill=(150, 162, 158, 255), outline=INK + (255,), width=8); G.add(L, [0.22, 0.35])
    G.add(text_layer([((cx, cy + R1 + 90), 'naval harbour', 70, ITA, INK, 'mm')]), [0.3, 0.4])
    L = G.layer(); d = ImageDraw.Draw(L); d.ellipse([cx - R2, cy - R2, cx + R2, cy + R2], fill=LAND + (255,), outline=INK + (255,), width=6)
    d.rectangle([cx - 40, cy - 40, cx + 40, cy + 40], fill=INK + (255,)); G.add(L, [0.38, 0.48])
    G.add(text_layer([((cx + 360, cy - 330), "admiral's island", 64, ITA, INK, 'mm')]), [0.45, 0.55])
    for k in range(4):   # ship sheds appear in sweeps
        L = G.layer(); d = ImageDraw.Draw(L)
        for i in range(k * 30, k * 30 + 30):
            ang = i / 120 * 2 * math.pi
            for r0, r1 in ((R1 - 140, R1 - 10), (R2 + 10, R2 + 70)):
                if r0 < R2 + 20 and i % 4: continue
                d.line([(cx + r0 * math.cos(ang), cy + r0 * math.sin(ang)), (cx + r1 * math.cos(ang), cy + r1 * math.sin(ang))], fill=(90, 70, 50, 255), width=6)
        G.add(L, [0.5 + k * 0.08, 0.6 + k * 0.08])
    G.add(text_layer([((3300, 520), 'covered sheds for', 64, ITA, INK, 'mm'), ((3300, 610), 'about 220 warships', 72, CAP, CAR, 'mm')]), [0.8, 0.9])
    G.zoom = 1.08; G.focus = nrm(cx, cy); finish(G, base)

def ship_side(d, x, y, s, col, flip=False):
    k = -1 if flip else 1
    hull = [(x - 700 * k, y), (x + 700 * k, y), (x + 820 * k, y - 120), (x + 640 * k, y - 160), (x - 640 * k, y - 160), (x - 760 * k, y - 120)]
    d.polygon(hull, fill=col + (255,), outline=INK + (255,)); d.line([(x + 700 * k, y - 20), (x + 900 * k, y + 10)], fill=(150, 110, 50, 255), width=18)
    for i in range(-5, 6): d.line([(x + i * 110, y - 60), (x + i * 110 - 80 * k, y + 120)], fill=(90, 70, 50, 255), width=8)

def d_corvus(G):
    base = dbase(); G.add(title('THE CORVUS', "the 'raven' boarding bridge, simplified"), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L); d.rectangle([0, 1450, W, H], fill=(150, 162, 158, 255)); ship_side(d, 1200, 1450, 1, (160, 120, 80)); ship_side(d, 2700, 1450, 1, (120, 90, 70), True)
    d.line([(1700, 1290), (1700, 700)], fill=(90, 60, 40, 255), width=22); G.add(L, [0.02, 0.15])
    G.add(text_layer([((1200, 1650), 'Roman ship', 64, ITA, INK, 'mm'), ((2700, 1650), 'Carthaginian ship', 64, ITA, INK, 'mm')]), [0.1, 0.2])
    # the bridge: a unit pivoting from upright to down onto the enemy deck
    G.unit((120, 80, 50), '', [[0.25, 0.443, 0.47, 0.03, 0.26, 0], [0.5, 0.443, 0.47, 0.03, 0.26, 0], [0.62, 0.57, 0.585, 0.03, 0.26, -80], [1.0, 0.57, 0.585, 0.03, 0.26, -80]])
    G.add(text_layer([((2200, 700), 'iron spike locks the decks together', 60, ITA, INK, 'mm'), ((1700, 560), 'bridge raised on a pole', 60, ITA, INK, 'mm')]), [0.62, 0.75])
    for i in range(5): G.unit(ROM, '', [[0.7, 0.42, 0.56, 0.012, 0.03, 0], [0.92 + i * 0.015, 0.62 + i * 0.03, 0.58, 0.012, 0.03, 0], [1.0, 0.62 + i * 0.03, 0.58, 0.012, 0.03, 0]])
    finish(G, base)

def u(col, label, frames): return (col, label, frames)

def battle(G, ttl, sub, units, notes, river=None, routes=()):
    base = dbase(); G.add(title(ttl, sub), [0.0, 0.1], fix=True)
    if river:
        L = G.layer(); ImageDraw.Draw(L).line([(x * W, y * H) for x, y in river], fill=(110, 128, 140, 255), width=46, joint='curve'); G.add(L, [0.0, 0.08])
    for col, label, k in units: G.unit(col, label, k)
    for pts, col, a in routes: G.route(pts, col, a, w=12)
    G.add(text_layer([((x * W, y * H), t, 60, ITA, INK, 'mm') for x, y, t in notes[0]]), notes[1])
    G.add(legend([(ROM, 'Romans'), (CAR, 'Carthaginians')], 'positions schematic'), [0.05, 0.15], fix=True); finish(G, base)

def blk(x, y, w=0.05, h=0.035, ang=0): return [x, y, w, h, ang]
def d_trebia(G):
    rom = [u(ROM, '', [[0.0] + blk(0.75 + 0.0 * i, 0.3 + 0.09 * i), [0.15] + blk(0.75, 0.3 + 0.09 * i), [0.45] + blk(0.47, 0.3 + 0.09 * i), [1.0] + blk(0.43, 0.3 + 0.09 * i)]) for i in range(5)]
    car = [u(CAR, '', [[0.0] + blk(0.25, 0.28 + 0.1 * i, 0.04), [1.0] + blk(0.33, 0.28 + 0.1 * i, 0.04)]) for i in range(5)]
    mago = [u(CAR, 'Mago' if i == 0 else '', [[0.0] + blk(0.55 + 0.05 * i, 0.9, 0.035, 0.03), [0.55] + blk(0.55 + 0.05 * i, 0.9, 0.035, 0.03), [0.85] + blk(0.5 + 0.04 * i, 0.72, 0.035, 0.03), [1.0] + blk(0.5 + 0.04 * i, 0.7, 0.035, 0.03)]) for i in range(3)]
    battle(G, 'THE TREBIA', 'December 218 BC', rom + car + mago, ([(0.78, 0.3, 'Romans wade the icy river'), (0.3, 0.82, 'ambush from a hidden streambed')], [0.3, 0.6]),
           river=[(0.6, 0.0), (0.58, 0.5), (0.62, 1.0)])

def cannae_units(phase):
    """phase 1: deployment, 2: centre bends and cavalry rides round, 3: encirclement. Positions (x,y,w,h,ang)."""
    R_, C_ = [], []
    for i in range(7):   # Roman mass
        for j in range(2):
            x0, y0 = 0.32 + 0.055 * i, 0.32 + 0.06 * j
            p1, p2, p3 = [x0, y0], [x0, y0 + 0.12], [0.34 + 0.05 * i, y0 + 0.17]
            k = {1: [[0, *p1, 0.05, 0.05, 0], [1, *p1, 0.05, 0.05, 0]], 2: [[0, *p1, 0.05, 0.05, 0], [0.8, *p2, 0.05, 0.05, 0], [1, *p2, 0.05, 0.05, 0]],
                 3: [[0, *p2, 0.05, 0.05, 0], [0.7, *p3, 0.045, 0.045, 0], [1, *p3, 0.045, 0.045, 0]]}[phase]
            R_.append(u(ROM, 'Roman infantry' if (i, j) == (3, 0) and phase == 1 else '', k))
    for i in range(7):   # crescent of Gauls and Spaniards
        bulge = 0.08 * math.sin(math.pi * i / 6); x = 0.32 + 0.055 * i
        p1, p2, p3 = [x, 0.6 - bulge], [x, 0.6 + bulge * 0.7], [0.34 + 0.05 * i, 0.68]
        k = {1: [[0, *p1, 0.05, 0.03, 0], [1, *p1, 0.05, 0.03, 0]], 2: [[0, *p1, 0.05, 0.03, 0], [0.8, *p2, 0.05, 0.03, 0], [1, *p2, 0.05, 0.03, 0]],
             3: [[0, *p2, 0.05, 0.03, 0], [1, *p3, 0.05, 0.03, 0]]}[phase]
        C_.append(u(CAR, 'Gauls and Spaniards' if i == 3 and phase == 1 else '', k))
    for side, x in ((-1, 0.22), (1, 0.76)):   # African infantry on the flanks
        q1, q3 = [x, 0.5], [x + 0.04 * side * -1, 0.45]
        k = {1: [[0, *q1, 0.04, 0.12, 0], [1, *q1, 0.04, 0.12, 0]], 2: [[0, *q1, 0.04, 0.12, 0], [1, *q1, 0.04, 0.12, 0]], 3: [[0, *q1, 0.04, 0.12, 0], [0.6, *q3, 0.04, 0.16, 0], [1, *q3, 0.04, 0.16, 0]]}[phase]
        C_.append(u((90, 30, 80), 'Africans' if side < 0 and phase == 1 else '', k))
    cav = {1: [[0, 0.12, 0.55, 0.06, 0.03, 0], [1, 0.12, 0.55, 0.06, 0.03, 0]],
           2: [[0, 0.12, 0.55, 0.06, 0.03, 0], [0.3, 0.12, 0.3, 0.06, 0.03, 0], [0.6, 0.5, 0.12, 0.06, 0.03, 0], [1, 0.86, 0.3, 0.06, 0.03, 0]],
           3: [[0, 0.86, 0.3, 0.06, 0.03, 0], [0.6, 0.5, 0.2, 0.3, 0.03, 0], [1, 0.5, 0.21, 0.3, 0.03, 0]]}[phase]
    C_.append(u((150, 100, 40), 'Carthaginian cavalry' if phase == 1 else '', cav))
    if phase == 1:
        R_.append(u((200, 120, 100), 'Roman cavalry', [[0, 0.12, 0.28, 0.06, 0.03, 0], [1, 0.12, 0.28, 0.06, 0.03, 0]]))
        R_.append(u((200, 120, 100), 'allied cavalry', [[0, 0.86, 0.28, 0.06, 0.03, 0], [1, 0.86, 0.28, 0.06, 0.03, 0]]))
    return R_ + C_

def d_cannae(G, phase):
    sub = {1: '2 August 216 BC: deployment', 2: 'the centre gives ground; the cavalry rides round', 3: 'the trap closes'}[phase]
    routes = []
    if phase == 2: routes = [([[0.12, 0.5], [0.12, 0.3], [0.3, 0.14], [0.6, 0.12], [0.84, 0.26]], (150, 100, 40), [0.1, 0.9])]
    if phase == 3: routes = [([[0.2, 0.5], [0.3, 0.48]], (90, 30, 80), [0.2, 0.55]), ([[0.78, 0.5], [0.68, 0.48]], (90, 30, 80), [0.2, 0.55])]
    notes = {1: ([(0.5, 0.92, 'outnumbered almost two to one')], [0.5, 0.65]), 2: ([(0.5, 0.92, 'the crescent bends backward')], [0.5, 0.65]),
             3: ([(0.5, 0.85, 'surrounded on every side')], [0.65, 0.8])}[phase]
    battle(G, 'CANNAE', sub, cannae_units(phase), notes, river=[(0.0, 0.98), (0.4, 0.95), (1.0, 0.99)], routes=routes)

def d_zama(G):
    rom = []
    for i in range(6):
        for j in range(3):
            x = 0.25 + 0.1 * i; rom.append(u(ROM, '', [[0, x, 0.3 + 0.08 * j, 0.06, 0.05, 0], [1, x, 0.3 + 0.08 * j, 0.06, 0.05, 0]]))
    ele = [u((90, 90, 90), 'elephants' if i == 2 else '', [[0, 0.3 + 0.1 * i, 0.75, 0.025, 0.04, 0], [0.2, 0.3 + 0.1 * i, 0.75, 0.025, 0.04, 0], [0.7, 0.3 + 0.1 * i, 0.27, 0.025, 0.04, 0], [1, 0.3 + 0.1 * i, 0.24, 0.025, 0.04, 0]]) for i in range(5)]
    car = [u(CAR, '', [[0, 0.25 + 0.1 * i, 0.84, 0.07, 0.03, 0], [1, 0.25 + 0.1 * i, 0.84, 0.07, 0.03, 0]]) for i in range(6)]
    battle(G, 'ZAMA', '202 BC: the elephant charge', rom + car + ele, ([(0.5, 0.62, 'open lanes between the Roman units')], [0.3, 0.5]))

def d_walls(G):
    base = dbase(); G.add(title('THE LANDWARD WALLS', 'cross-section, after Appian; simplified'), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L); gy = 1800
    d.rectangle([0, gy, W, H], fill=(190, 170, 130, 255)); d.polygon([(500, gy), (620, gy + 160), (900, gy + 160), (1020, gy)], fill=(150, 162, 158, 255), outline=INK + (255,)); G.add(L, [0.05, 0.15])
    G.add(text_layer([((760, gy - 70), 'ditch', 60, ITA, INK, 'mm')]), [0.12, 0.2])
    L = G.layer(); d = ImageDraw.Draw(L); [d.line([(1150 + i * 22, gy), (1150 + i * 22, gy - 220)], fill=(120, 90, 60, 255), width=12) for i in range(10)]; G.add(L, [0.2, 0.3])
    G.add(text_layer([((1250, gy - 300), 'palisade', 60, ITA, INK, 'mm')]), [0.25, 0.35])
    L = G.layer(); d = ImageDraw.Draw(L); x0, x1, top = 1700, 2700, gy - 1200
    d.rectangle([x0, top, x1, gy], fill=(200, 180, 140, 255), outline=INK + (255,), width=8)
    for k in range(9): d.rectangle([x0 - 40 + k * 125, top - 70, x0 + 30 + k * 125, top], fill=(200, 180, 140, 255), outline=INK + (255,), width=5)
    d.line([(x0, gy - 600), (x1, gy - 600)], fill=INK + (255,), width=6); G.add(L, [0.35, 0.5])
    G.add(text_layer([((2200, gy - 300), 'stalls for 300 elephants', 60, ITA, INK, 'mm'), ((2200, gy - 900), 'stables for 4,000 horses,', 60, ITA, INK, 'mm'),
                      ((2200, gy - 820), 'barracks for 20,000 men', 60, ITA, INK, 'mm')]), [0.55, 0.7])
    L = G.layer(); d = ImageDraw.Draw(L); d.line([(2850, top), (2850, gy)], fill=INK + (255,), width=6); d.line([(2810, top), (2890, top)], fill=INK + (255,), width=6); d.line([(2810, gy), (2890, gy)], fill=INK + (255,), width=6)
    TEXTS.extend(['about 13 m', 'a man, for scale']); d.text((2920, (top + gy) / 2), 'about 13 m', font=font(CAP, 70), fill=INK + (255,), anchor='lm')
    hx = 3400; d.ellipse([hx - 25, gy - 175, hx + 25, gy - 125], fill=INK + (255,)); d.line([(hx, gy - 125), (hx, gy - 50)], fill=INK + (255,), width=12)
    d.line([(hx, gy - 50), (hx - 30, gy)], fill=INK + (255,), width=10); d.line([(hx, gy - 50), (hx + 30, gy)], fill=INK + (255,), width=10)
    d.text((hx, gy + 60), 'a man, for scale', font=font(ITA, 50), fill=INK + (255,), anchor='mm'); G.add(L, [0.7, 0.82]); finish(G, base)

def d_siege(G):
    base = city_plan(G); G.add(title('THE SIEGE OF CARTHAGE', '147 BC'), [0.0, 0.1], fix=True); harbour_layers(G, [0.0, 0.1])
    G.add(text_layer([(BYRSA, 'Byrsa', 70, CAP, INK, 'mm')]), [0.0, 0.1])
    L = G.layer(); d = ImageDraw.Draw(L); d.line([(700, 300), (520, 1200)], fill=INK + (255,), width=26); G.add(L, [0.1, 0.25])
    G.add(text_layer([((660, 750), 'city walls', 60, ITA, INK, 'lm')]), [0.15, 0.25])
    L = G.layer(); d = ImageDraw.Draw(L); d.line([(330, 290), (170, 1170)], fill=ROM + (255,), width=26); G.add(L, [0.3, 0.45])
    G.add(text_layer([((120, 200), "Scipio's siege line", 56, ITA, ROM, 'lm')]), [0.4, 0.55])
    G.route([nrm(2900, 2160), nrm(2620, 1990)], ROM, [0.6, 0.85], w=26); G.add(text_layer([((2980, 1960), 'the mole', 60, ITA, ROM, 'lm')]), [0.75, 0.85])
    G.focus = None; G.zoom = 1.02; finish(G, base)

def d_channel(G):
    base = city_plan(G); harbour_layers(G, [0.0, 0.05]); G.add(title('THE NEW CHANNEL', '147 BC'), [0.0, 0.1], fix=True)
    G.route([nrm(2900, 2160), nrm(2620, 1990)], ROM, [0.0, 0.05], w=26)
    G.route([nrm(2560, 1640), nrm(2800, 1520), nrm(3150, 1430)], CAR, [0.15, 0.6], w=18, dash=True)
    G.add(text_layer([((3100, 1300), 'channel dug in secret', 60, ITA, CAR, 'mm')]), [0.4, 0.55])
    for i in range(4): G.unit(CAR, '', [[0.6 + 0.03 * i, 0.64, 0.75, 0.012, 0.025, 30], [0.9 + 0.025 * i, 0.83, 0.65, 0.012, 0.025, 30], [1.0, 0.85 + 0.01 * i, 0.64, 0.012, 0.025, 30]])
    G.focus = nrm(2650, 1650); G.zoom = 1.15; finish(G, base)

def d_assault(G):
    base = city_plan(G); harbour_layers(G, [0.0, 0.05]); G.add(title('THE FINAL ASSAULT', 'spring 146 BC'), [0.0, 0.1], fix=True)
    G.add(text_layer([(BYRSA, 'Byrsa', 70, CAP, INK, 'mm'), ((2500, 1320), 'agora', 60, ITA, INK, 'mm')]), [0.05, 0.15])
    G.route([nrm(2900, 2100), nrm(2470, 1700)], ROM, [0.15, 0.35], w=14); G.route([nrm(2470, 1700), nrm(2380, 1450)], ROM, [0.35, 0.5], w=14)
    for k, off in enumerate((-90, 0, 90)): G.route([nrm(2380 + off, 1430), nrm(2150 + off * 0.6, 1250), nrm(1950 + off * 0.3, 1090)], ROM, [0.55 + 0.05 * k, 0.85 + 0.03 * k], w=9, dash=True)
    G.pulse(nrm(*BYRSA), (200, 60, 40), [0.85, 1.0]); G.focus = nrm(2150, 1300); G.zoom = 1.15; finish(G, base)

def d_byrsa(G):
    base = dbase(); G.add(title('THE THREE STREETS TO THE BYRSA', 'schematic'), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L)
    for r, c in ((900, (214, 196, 156)), (650, (206, 186, 146)), (400, (196, 176, 136))): d.ellipse([1300 - r, 900 - r * 0.7, 1300 + r, 900 + r * 0.7], fill=c + (255,), outline=(150, 130, 100, 255), width=4)
    rng = np.random.default_rng(4)
    for _ in range(260):
        x, y = rng.uniform(300, 3600), rng.uniform(300, 2000)
        if abs(x - 1300) < 160 and abs(y - 900) < 120: continue
        if y < 420 or (abs(x - 2300) < 520 and abs(y - 480) < 90) or (abs(x - 1300) < 380 and abs(y - 680) < 80) or (abs(x - 2750) < 300 and abs(y - 1110) < 80): continue
        d.rectangle([x, y, x + 70, y + 50], fill=(232, 222, 196, 255), outline=(120, 100, 80, 255), width=3)
    G.add(L, [0.05, 0.2])
    for k, (sx, sy) in enumerate(((3000, 1650), (3200, 1300), (2950, 1950))):
        L = G.layer(); ImageDraw.Draw(L).line([(sx, sy), ((sx + 1300) / 2, (sy + 900) / 2 + 60), (1380, 930)], fill=(240, 232, 210, 255), width=70, joint='curve'); G.add(L, [0.2 + 0.06 * k, 0.32 + 0.06 * k])
        G.route([nrm(sx, sy), nrm((sx + 1300) / 2, (sy + 900) / 2 + 60), nrm(1420, 950)], ROM, [0.45 + 0.08 * k, 0.85 + 0.04 * k], w=10)
    G.add(text_layer([((1300, 700), 'temple of Eshmun', 64, ITA, INK, 'mm'), ((2750, 1130), 'from the agora', 60, ITA, INK, 'mm'), ((2300, 500), 'houses six storeys high', 60, ITA, INK, 'mm')]), [0.3, 0.45])
    G.pulse(nrm(1300, 900), (200, 60, 40), [0.85, 1.0]); G.focus = nrm(1600, 1050); G.zoom = 1.2; finish(G, base)

def d_trasimene(G):
    base = dbase(); G.add(title('LAKE TRASIMENE', 'June 217 BC · schematic'), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L); d.ellipse([600, 1250, 3600, 2500], fill=(150, 162, 158, 255), outline=INK + (255,), width=8)
    for x in range(300, 3700, 320): d.arc([x - 260, 560, x + 260, 1100], 200, 340, fill=(120, 100, 70, 255), width=10)
    G.add(L, [0.0, 0.1]); G.add(text_layer([((2100, 1900), 'Lake Trasimene', 80, ITA, INK, 'mm'), ((3150, 500), 'hills', 64, ITA, INK, 'mm')]), [0.05, 0.15])
    for i in range(8): G.unit(CAR, '', [[0, 0.12 + 0.1 * i, 0.38, 0.05, 0.03, 0], [0.55, 0.12 + 0.1 * i, 0.38, 0.05, 0.03, 0], [0.8, 0.12 + 0.1 * i, 0.5, 0.05, 0.03, 0], [1, 0.12 + 0.1 * i, 0.52, 0.05, 0.03, 0]])
    for i in range(10): G.unit(ROM, '', [[0, -0.05 + 0.06 * i, 0.57, 0.04, 0.025, 0], [0.55, 0.15 + 0.06 * i, 0.57, 0.04, 0.025, 0], [1, 0.15 + 0.06 * i, 0.57, 0.04, 0.025, 0]])
    G.add(text_layer([((1900, 920), 'the trap springs', 64, ITA, CAR, 'mm')]), [0.7, 0.8]); G.add(text_layer([((2760, 1231), 'Roman column', 60, ITA, INK, 'lm')]), [0.55, 0.7])
    L = G.layer(); a = np.zeros((H, W, 4), np.uint8); a[..., :3] = 235; yy = np.mgrid[0:H, 0:W][0]; a[..., 3] = (np.clip(1 - np.abs(yy - 1250) / 500, 0, 1) * 120).astype(np.uint8)
    G.add(Image.fromarray(a), [0.0, 0.3]); finish(G, base)

def d_newcarthage(G):
    base = dbase(); G.add(title('NEW CARTHAGE', '209 BC · schematic'), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L); d.rectangle([0, 1500, W, H], fill=(150, 162, 158, 255)); d.ellipse([200, 200, 1500, 1100], fill=(150, 162, 158, 255), outline=INK + (255,), width=6)
    d.ellipse([1300, 700, 2700, 1550], fill=LAND + (255,), outline=INK + (255,), width=8); G.add(L, [0.0, 0.1])
    G.add(text_layer([((2000, 1120), 'New Carthage', 80, CAP, CAR, 'mm'), ((850, 650), 'lagoon', 70, ITA, INK, 'mm'), ((2000, 1850), 'harbour', 70, ITA, INK, 'mm')]), [0.05, 0.2])
    G.unit(ROM, "Scipio's camp", [[0, 0.76, 0.3, 0.08, 0.06, 0], [1, 0.76, 0.3, 0.08, 0.06, 0]])
    G.route([nrm(2850, 760), nrm(2620, 950)], ROM, [0.2, 0.45], w=14); G.add(text_layer([((2950, 1000), 'main attack', 56, ITA, ROM, 'mm')]), [0.35, 0.45])
    G.route([nrm(450, 1000), nrm(900, 900), nrm(1380, 950)], ROM, [0.5, 0.85], w=12, dash=True); G.add(text_layer([((850, 1250), 'wading at low water', 60, ITA, ROM, 'mm')]), [0.65, 0.8])
    G.focus = None; G.zoom = 1.04; finish(G, base)

def m_rome211(G):
    P = Proj(10.5, 17.5, 39.6, 44.2); base, mask = map_base(P)
    G.add(title('HANNIBAL MARCHES ON ROME', '211 BC'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PL['Rome'], 'Rome', 60, -40, -95, True), (*PL['Capua'], 'Capua', 56, 120, 40)], [0.05, 0.2])
    G.route(R(P, 'Capua', (13.9, 41.5), (13.3, 41.75), (12.75, 41.85), 'Rome'), CAR, [0.2, 0.7], w=11)
    G.pulse(P.n(*PL['Rome']), (200, 60, 40), [0.7, 1.0])
    G.add(legend([(CAR, 'Hannibal')], 'route approximate'), [0.5, 0.65], fix=True); G.focus = P.n(13.4, 41.5); G.zoom = 1.15; finish(G, base)


def d_blocks(G):
    """Cold open: block-by-block fighting between the agora and the Byrsa (Appian, Pun. 128-130)."""
    base = city_plan(G); harbour_layers(G, [0.0, 0.05]); G.add(title('CARTHAGE', 'spring 146 BC'), [0.0, 0.1], fix=True)
    G.add(text_layer([(BYRSA, 'Byrsa', 70, CAP, INK, 'mm'), ((2500, 1320), 'agora', 60, ITA, INK, 'mm')]), [0.05, 0.15])
    for k, (x, y) in enumerate(((2330, 1360), (2260, 1300), (2190, 1240), (2120, 1180), (2050, 1120))):
        G.pulse(nrm(x, y), (200, 60, 40), [0.15 + 0.12 * k, 0.3 + 0.12 * k])
    G.add(text_layer([((2700, 1050), 'block by block, then burned', 60, ITA, CAR, 'mm')]), [0.55, 0.7])
    G.focus = nrm(2000, 1150); G.zoom = 1.08; finish(G, base)

def d_envelop(G):
    """The double envelopment, as a general pattern (no positions claimed)."""
    base = dbase(); G.add(title('DOUBLE ENVELOPMENT', 'schematic'), [0.0, 0.1], fix=True)
    G.unit(ROM, '', [[0, 0.5, 0.5, 0.26, 0.16, 0], [1, 0.5, 0.5, 0.24, 0.15, 0]])
    G.unit(CAR, '', [[0, 0.5, 0.72, 0.3, 0.04, 0], [0.5, 0.5, 0.65, 0.3, 0.04, 0], [1, 0.5, 0.63, 0.3, 0.04, 0]])
    G.unit(CAR, '', [[0, 0.22, 0.6, 0.04, 0.1, 0], [0.5, 0.3, 0.5, 0.04, 0.2, 0], [1, 0.33, 0.5, 0.04, 0.2, 0]])
    G.unit(CAR, '', [[0, 0.78, 0.6, 0.04, 0.1, 0], [0.5, 0.7, 0.5, 0.04, 0.2, 0], [1, 0.67, 0.5, 0.04, 0.2, 0]])
    G.unit(CAR, '', [[0, 0.12, 0.25, 0.08, 0.03, 0], [0.4, 0.3, 0.3, 0.1, 0.03, 0], [1, 0.5, 0.37, 0.3, 0.03, 0]])
    G.route([[0.2, 0.6], [0.3, 0.52]], CAR, [0.3, 0.6], w=10); G.route([[0.8, 0.6], [0.7, 0.52]], CAR, [0.3, 0.6], w=10)
    G.add(legend([(ROM, 'larger force'), (CAR, 'smaller force')], 'positions schematic'), [0.05, 0.15], fix=True)
    G.add(text_layer([((W / 2, H * 0.88), 'attacked from every side at once', 60, ITA, INK, 'mm')]), [0.7, 0.85])
    G.focus = None; G.zoom = 1.05; finish(G, base)

def d_arms149(G):
    """149 BC: Carthage decides to fight (Appian, Pun. 92-93)."""
    base = city_plan(G); harbour_layers(G, [0.0, 0.05]); G.add(title('CARTHAGE', '149 BC'), [0.0, 0.1], fix=True)
    G.add(text_layer([(BYRSA, 'Byrsa', 70, CAP, INK, 'mm')]), [0.05, 0.15])
    G.add(text_layer([((2420, 1480), 'naval harbour: no ships', 60, ITA, CAR, 'mm')]), [0.25, 0.4])
    L = G.layer(); d = ImageDraw.Draw(L); d.line([(700, 300), (520, 1200)], fill=INK + (255,), width=26); G.add(L, [0.45, 0.6])
    G.add(text_layer([((660, 750), 'gates closed', 60, ITA, INK, 'lm')]), [0.55, 0.7])
    G.focus = None; G.zoom = 1.04; finish(G, base)

def d_surrender(G):
    """The seventh day on the Byrsa (Appian, Pun. 130)."""
    base = dbase(); G.add(title('THE BYRSA', 'the seventh day, 146 BC'), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L)
    for r, c in ((900, (214, 196, 156)), (650, (206, 186, 146)), (400, (196, 176, 136))): d.ellipse([1300 - r, 900 - r * 0.7, 1300 + r, 900 + r * 0.7], fill=c + (255,), outline=(150, 130, 100, 255), width=4)
    d.rectangle([1220, 850, 1380, 950], fill=(232, 222, 196, 255), outline=INK + (255,), width=5); G.add(L, [0.0, 0.1])
    G.add(text_layer([((1300, 700), 'temple of Eshmun', 64, ITA, INK, 'mm')]), [0.1, 0.2])
    for k, (ex, ey) in enumerate(((3000, 1700), (3300, 1250), (2700, 2000))): G.route([nrm(1450, 960), nrm(ex, ey)], (90, 80, 70), [0.2 + 0.05 * k, 0.55 + 0.05 * k], w=10, dash=True)
    G.add(text_layer([((2850, 1040), '50,000 come out', 66, CAP, INK, 'mm')]), [0.45, 0.6])
    G.pulse(nrm(1300, 900), (200, 60, 40), [0.65, 0.9])
    G.add(text_layer([((1300, 1080), '900 deserters', 60, ITA, CAR, 'mm')]), [0.7, 0.85])
    G.focus = nrm(1900, 1150); G.zoom = 1.1; finish(G, base)

GFX = {'12-03-4': d_harbours, '01-00-0': m_phoenicia, '01-01-1': m_trade, '02-00-0': m_empire300, '02-02-0': d_harbours, '03-00-0': m_sicily264, '03-02-0': d_corvus,
       '03-03-0': m_regulus, '03-06-0': m_aegates, '03-07-0': m_241, '04-02-0': m_sardinia, '04-05-0': lambda G: m_spain(G), '04-06-0': lambda G: m_spain(G, ebro=True),
       '05-03-0': lambda G: m_spain(G, sag=True), '05-05-0': m_plan218, '06-00-0': lambda G: m_march(G, 1), '06-02-0': m_rhone, '06-05-1': m_passes,
       '06-06-2': lambda G: m_march(G, 2), '07-00-2': m_north_italy, '07-02-0': d_trebia, '07-04-0': d_trasimene, '08-01-0': m_to_cannae,
       '08-02-0': lambda G: d_cannae(G, 1), '08-03-0': lambda G: d_cannae(G, 2), '08-04-0': lambda G: d_cannae(G, 3), '09-01-0': m_after_cannae,
       '09-02-0': m_fronts, '09-05-2': m_rome211, '09-06-0': m_metaurus, '10-01-0': d_newcarthage, '10-03-0': m_spain_scipio, '11-00-0': m_africa202, '11-01-0': d_zama,
       '12-01-2': m_exile, '13-00-1': m_numidia, '14-00-0': m_149, '14-03-2': m_inland, '15-00-0': d_walls, '15-04-0': d_siege, '15-05-2': d_channel,
       '16-00-0': d_assault, '16-01-0': d_byrsa, '17-00-1': m_146,
       '00-01-2': d_blocks, '08-06-2': d_envelop, '14-04-3': d_arms149, '16-03-2': d_surrender}

def main():
    ids = sys.argv[1:] or list(GFX)
    for k in ids:
        TEXTS.clear(); G = Gfx(k); GFX[k](G); print(k, len(G.layers), 'layers', flush=True)

if __name__ == '__main__': main()
