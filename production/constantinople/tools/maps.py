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
    city(d, P, 28.97, 41.01, 'Constantinople', 72, dx=-330, dy=10, star=True)
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

def arrow(d, a, b, col=GOLD, w=12):
    (x0, y0), (x1, y1) = a, b; n = 40
    pts = [(x0 + (x1 - x0) * t + math.sin(t * math.pi) * (y1 - y0) * 0.12, y0 + (y1 - y0) * t - math.sin(t * math.pi) * (x1 - x0) * 0.12) for t in [i / n for i in range(n + 1)]]
    for i in range(0, n - 2, 2): d.line([pts[i], pts[i + 1]], fill=col, width=w)
    (ax, ay), (bx, by) = pts[-3], pts[-1]; ang = math.atan2(by - ay, bx - ax); L = 46
    d.polygon([(bx, by), (bx - L * math.cos(ang - 0.45), by - L * math.sin(ang - 0.45)), (bx - L * math.cos(ang + 0.45), by - L * math.sin(ang + 0.45))], fill=col)

def map_forts():
    P = Proj(28.78, 29.32, 40.96, 41.26)
    img = Image.fromarray(paper().clip(0, 255).astype(np.uint8)); draw_land(img, P)
    img, mask = coast_lines(img, P); d = ImageDraw.Draw(img)
    city(d, P, 28.95, 41.01, 'Constantinople', 64, dx=-60, dy=90, star=True)
    city(d, P, 29.056, 41.085, 'Rumeli Hisarı (1452)', 58, dx=-420, dy=-10)
    city(d, P, 29.066, 41.082, 'Anadolu Hisarı', 54, dx=330, dy=40)
    label(d, P(29.2, 41.235), 'to the Black Sea', 56)
    label(d, P(28.92, 40.99), 'Sea of Marmara', 58)
    label(d, P(29.18, 41.04), 'ASIA', 90, f='Cinzel.ttf', fill=(90, 70, 50)); label(d, P(28.88, 41.17), 'EUROPE', 90, f='Cinzel.ttf', fill=(90, 70, 50))
    label(d, (W - 60, H - 60), 'narrowest point: about 700 m', 54, anchor='rd')
    return vignette(img)

def map_help():
    P = Proj(-7.0, 36.0, 34.5, 52.0)
    img = Image.fromarray(paper().clip(0, 255).astype(np.uint8)); draw_land(img, P)
    img, mask = coast_lines(img, P); d = ImageDraw.Draw(img)
    c = P(28.97, 41.01); city(d, P, 28.97, 41.01, 'Constantinople', 60, dx=60, dy=80, star=True)
    for lon, lat, name, dx, dy in ((12.33, 45.44, 'Venice', 0, -60), (8.93, 44.41, 'Genoa', -40, -60), (12.5, 41.9, 'Rome', -110, -10),
                                   (19.04, 47.5, 'Hungary', 0, -60), (14.25, 40.85, 'Aragon (Naples)', 60, 80)):
        city(d, P, lon, lat, name, 54, dx=dx, dy=dy); arrow(d, P(lon, lat), (c[0] - 30, c[1] - 10))
    label(d, (W - 60, H - 60), 'hoped-for help, 1452–53', 54, anchor='rd')
    return vignette(img)

def map_1461():
    P = Proj(17.5, 42.5, 34.5, 46.5)
    img = Image.fromarray(paper().clip(0, 255).astype(np.uint8)); draw_land(img, P)
    img, mask = coast_lines(img, P)
    ott = [(21.0, 42.9), (22.6, 43.9), (25.0, 43.7), (27.6, 44.0), (28.7, 43.7), (29.2, 41.3), (27.9, 40.9), (26.2, 40.6),
           (24.0, 40.6), (22.9, 39.4), (22.6, 38.4), (21.4, 39.0), (20.8, 40.3), (20.6, 41.6)]
    ana = [(26.0, 40.1), (29.4, 41.2), (31.5, 41.3), (33.0, 40.9), (34.6, 40.7), (36.4, 40.6), (36.2, 39.6), (33.6, 39.0),
           (31.6, 38.0), (29.6, 37.0), (27.3, 37.2), (26.1, 38.5)]
    morea = [(21.1, 38.3), (23.2, 38.0), (23.3, 36.3), (21.5, 36.6)]
    treb = [(37.6, 41.2), (41.6, 41.5), (41.4, 40.2), (38.0, 40.4)]
    regs = [region(P, mask, x, OTT) for x in (ott, ana)] + [region(P, mask, x, OTT, 0.6) for x in (morea, treb)]
    img = apply_regions(img, regs); d = ImageDraw.Draw(img)
    city(d, P, 28.97, 41.01, 'Constantinople', 60, dx=230, dy=-55, star=True)
    label(d, P(19.9, 36.6), 'Morea · 1460', 66, fill=(120, 34, 28)); label(d, P(39.6, 41.9), 'Trebizond · 1461', 62, fill=(120, 34, 28))
    label(d, (W - 60, H - 60), 'the last Byzantine lands fall · borders approximate', 54, anchor='rd')
    return vignette(img)

def card(lines, out):
    img = Image.new('RGB', (W, H), (10, 9, 8)); d = ImageDraw.Draw(img); y = H / 2 - (len(lines) - 1) * 130
    for text, size, colr, f in lines:
        d.text((W / 2, y), text, font=font(f, size), fill=colr, anchor='mm'); y += 260 if size > 100 else 200
    img.save(out)

def cards():
    G, Wt, R = (176, 132, 52), (230, 216, 186), (190, 70, 60)
    card([('Contemporary claims: 160,000 – 300,000+', 92, (150, 140, 125), 'CormorantGaramond-Italic.ttf'),
          ('Modern estimates: 50,000 – 80,000 soldiers', 120, Wt, 'CormorantGaramond.ttf'),
          ('Defenders: about 7,000 – 8,000', 120, G, 'CormorantGaramond.ttf')], os.path.join(OUT, '05-01-0.png'))
    card([('MYTH', 110, R, 'Cinzel.ttf'), ('1453 closed the trade routes to Asia', 100, (150, 140, 125), 'CormorantGaramond-Italic.ttf'),
          ('REALITY', 110, G, 'Cinzel.ttf'), ('Trade went on; Portuguese voyages had begun decades earlier', 84, Wt, 'CormorantGaramond.ttf')],
         os.path.join(OUT, '13-02-0.png'))
    card([('THE LAST DAY OF ROME', 150, Wt, 'Cinzel.ttf'), ('Narration, script and edit: Ancient World Files', 64, (160, 150, 130), 'CormorantGaramond-Italic.ttf'),
          ('Reconstructions are artistic interpretations · AI-assisted imagery and voice', 56, (130, 122, 108), 'CormorantGaramond-Italic.ttf')],
         os.path.join(OUT, '13-06-3.png'))

MAPS = {'01-00-0': map_strait, '01-05-0': map_1450, '03-00-2': map_forts, '04-00-0': map_help, '13-00-2': map_1461}

def main():
    os.makedirs(OUT, exist_ok=True)
    for k, fn in MAPS.items():
        fn().save(os.path.join(OUT, k + '.png')); print(k)
    cards(); print('cards')

if __name__ == '__main__': main()
