"""Parchment-style maps for the film (Natural Earth, public domain). Output 3840x2160 PNG in build/maps/<shot>.png.

  python3 tools/maps.py            # all maps
Territories are deliberately simplified and labelled "approximate" on screen.
"""
import json, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'maps')
FONTS = os.path.join(ROOT, '..', 'assets', 'fonts')
NE = '/home/user/models/ne'
W, H = 3840, 2160
INK, SEA, LAND = (58, 42, 28), (148, 158, 150), (224, 208, 170)
OTT, BYZ, GOLD = (150, 46, 38), (92, 40, 110), (176, 132, 52)

def font(name, size): return ImageFont.truetype(os.path.join(FONTS, name), size)

_land = None
def land():
    global _land
    if _land is None:
        g = json.load(open(os.path.join(NE, 'land10.geojson')))
        polys = []
        for f in g['features']:
            geo = f['geometry']
            rings = [geo['coordinates']] if geo['type'] == 'Polygon' else geo['coordinates']
            for p in rings: polys.append(p[0])
        _land = polys
    return _land

class Proj:
    def __init__(self, lon0, lon1, lat0, lat1):
        self.lon0, self.lat1 = lon0, lat1
        self.kx = W / (lon1 - lon0); self.ky = H / (lat1 - lat0)
        self.cos = math.cos(math.radians((lat0 + lat1) / 2))
        # keep aspect: equirectangular scaled by cos(lat)
        s = min(W / ((lon1 - lon0) * self.cos), H / (lat1 - lat0))
        self.s = s; self.ox = (W - (lon1 - lon0) * self.cos * s) / 2; self.oy = (H - (lat1 - lat0) * s) / 2
    def __call__(self, lon, lat):
        return (self.ox + (lon - self.lon0) * self.cos * self.s, self.oy + (self.lat1 - lat) * self.s)

def paper():
    rng = np.random.default_rng(7)
    n = rng.normal(0, 1, (H // 8, W // 8)).astype(np.float32)
    n = np.array(Image.fromarray(((n * 18) + 128).clip(0, 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
                 .filter(ImageFilter.GaussianBlur(6)), np.float32) - 128
    base = np.ones((H, W, 3), np.float32) * np.array(SEA, np.float32)
    return base + n[..., None] * 0.35

def draw_land(img, P, fill=LAND):
    d = ImageDraw.Draw(img)
    for ring in land():
        pts = [P(x, y) for x, y in ring]
        if all(p[0] < -200 or p[0] > W + 200 for p in pts) or all(p[1] < -200 or p[1] > H + 200 for p in pts): continue
        d.polygon(pts, fill=fill)
    return img

def coast_lines(img, P):
    mask = Image.new('L', (W, H), 0); draw_land(mask, P, 255)
    edge = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5))
    halo = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(31)).filter(ImageFilter.GaussianBlur(10))
    a = np.array(img, np.float32)
    h = np.array(halo, np.float32)[..., None] / 255 * (1 - np.array(mask, np.float32)[..., None] / 255)
    a = a * (1 - h * 0.18) + np.array(INK, np.float32) * h * 0.18
    e = np.array(edge, np.float32)[..., None] / 255
    a = a * (1 - e * 0.75) + np.array(INK, np.float32) * e * 0.75
    return Image.fromarray(a.clip(0, 255).astype(np.uint8)), mask

def region(P, mask, poly_lonlat, colour, alpha=0.38):
    reg = Image.new('L', (W, H), 0); ImageDraw.Draw(reg).polygon([P(x, y) for x, y in poly_lonlat], fill=255)
    reg = reg.filter(ImageFilter.GaussianBlur(28)); reg = Image.fromarray(np.minimum(np.array(reg), np.array(mask)))
    return reg, colour, alpha

def apply_regions(img, regs):
    a = np.array(img, np.float32)
    for reg, col, al in regs:
        r = np.array(reg, np.float32)[..., None] / 255 * al
        a = a * (1 - r) + np.array(col, np.float32) * r
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))

def label(d, xy, text, size, fill=INK, f='CormorantGaramond-Italic.ttf', anchor='mm', spacing=0):
    fo = font(f, size)
    if spacing: text = (' ' * spacing).join(text)
    d.text(xy, text, font=fo, fill=fill, anchor=anchor)

def vignette(img):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    v = (1 - 0.45 * np.clip(r - 0.55, 0, 1) ** 1.4)[..., None]
    a = np.array(img, np.float32) * v
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))

def city(d, P, lon, lat, name, size=64, dx=0, dy=-70, star=False):
    x, y = P(lon, lat); r = 22 if star else 14
    d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD if star else INK, outline=INK, width=5)
    label(d, (x + dx, y + dy), name, size, f='Cinzel.ttf')

def map_strait():
    P = Proj(25.6, 31.4, 39.9, 42.4)
    img = Image.fromarray(paper().clip(0, 255).astype(np.uint8)); draw_land(img, P)
    img, mask = coast_lines(img, P); d = ImageDraw.Draw(img)
    label(d, P(29.2, 41.95), 'BLACK SEA', 92, spacing=1)
    label(d, P(28.0, 40.72), 'SEA OF MARMARA', 80, spacing=1)
    label(d, P(29.12, 41.33), 'Bosphorus', 58)
    label(d, P(27.0, 41.6), 'EUROPE', 110, f='Cinzel.ttf', fill=(90, 70, 50))
    label(d, P(30.3, 40.35), 'ASIA', 110, f='Cinzel.ttf', fill=(90, 70, 50))
    city(d, P, 28.97, 41.01, 'Constantinople', 72, dx=-40, dy=-80, star=True)
    # sea lanes
    for pts in ([(29.12, 41.6), (29.06, 41.2), (28.98, 41.0)], [(28.98, 41.0), (28.4, 40.75), (27.3, 40.5), (26.6, 40.2)]):
        q = [P(*p) for p in pts]
        for i in range(len(q) - 1):
            x0, y0 = q[i]; x1, y1 = q[i + 1]; n = 24
            for k in range(0, n, 2):
                a, b = k / n, (k + 1) / n
                d.line([x0 + (x1 - x0) * a, y0 + (y1 - y0) * a, x0 + (x1 - x0) * b, y0 + (y1 - y0) * b], fill=GOLD, width=9)
    return vignette(img)

def map_1450():
    P = Proj(17.5, 42.5, 34.5, 46.5)
    img = Image.fromarray(paper().clip(0, 255).astype(np.uint8)); draw_land(img, P)
    img, mask = coast_lines(img, P)
    # Simplified Ottoman lands c. 1450 (Balkans south of the Danube to the Morea border, and western/central Anatolia)
    ott = [(21.0, 42.9), (22.6, 43.9), (25.0, 43.7), (27.6, 44.0), (28.7, 43.7), (29.2, 41.3), (27.9, 40.9),
           (26.2, 40.6), (24.0, 40.6), (22.9, 39.4), (22.6, 38.4), (21.4, 39.0), (20.8, 40.3), (20.6, 41.6)]
    ana = [(26.0, 40.1), (29.4, 41.2), (31.5, 41.3), (33.0, 40.9), (34.6, 40.7), (36.4, 40.6), (36.2, 39.6),
           (33.6, 39.0), (31.6, 38.0), (29.6, 37.0), (27.3, 37.2), (26.1, 38.5)]
    byz_city = [(28.4, 41.25), (29.2, 41.25), (29.2, 40.85), (28.4, 40.85)]
    morea = [(21.1, 38.3), (23.2, 38.0), (23.3, 36.3), (21.5, 36.6)]
    treb = [(37.6, 41.2), (41.6, 41.5), (41.4, 40.2), (38.0, 40.4)]
    regs = [region(P, mask, ott, OTT), region(P, mask, ana, OTT), region(P, mask, byz_city, BYZ, 0.6),
            region(P, mask, morea, BYZ, 0.5), region(P, mask, treb, BYZ, 0.35)]
    img = apply_regions(img, regs); d = ImageDraw.Draw(img)
    label(d, P(24.3, 42.25), 'OTTOMANS', 84, f='Cinzel.ttf', fill=(120, 34, 28), spacing=1)
    label(d, P(31.6, 39.6), 'OTTOMANS', 84, f='Cinzel.ttf', fill=(120, 34, 28), spacing=1)
    city(d, P, 28.97, 41.01, 'Constantinople', 60, dx=230, dy=-55, star=True)
    label(d, P(22.2, 37.0), 'Morea', 64, fill=(70, 28, 86))
    label(d, P(39.6, 41.9), 'Trebizond', 60, fill=(70, 28, 86))
    city(d, P, 26.56, 41.68, 'Edirne', 56, dx=-150, dy=0)
    label(d, (W - 60, H - 60), 'c. 1450 · borders approximate', 54, anchor='rd')
    # legend
    d.rectangle([110, H - 300, 170, H - 250], fill=(196, 140, 118)); label(d, (200, H - 275), 'Ottoman', 60, anchor='lm')
    d.rectangle([110, H - 210, 170, H - 160], fill=(170, 130, 160)); label(d, (200, H - 185), 'Byzantine (Roman) Empire', 60, anchor='lm')
    return vignette(img)

MAPS = {'01-00-0': map_strait, '01-05-0': map_1450}

def main():
    os.makedirs(OUT, exist_ok=True)
    for k, fn in MAPS.items():
        fn().save(os.path.join(OUT, k + '.png')); print(k)

if __name__ == '__main__': main()
