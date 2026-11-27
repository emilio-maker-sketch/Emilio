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

ROME, POMP = (150, 46, 38), (52, 72, 120)
ROUTES = {}

def route(P, pts, col=ROME):
    return {'pts': [[P(*q)[0] / W, P(*q)[1] / H] for q in pts], 'col': list(col)}

def legend(d, rows):
    y = H - 120 - 90 * (len(rows) - 1)
    for col, text in rows:
        d.rectangle([110, y - 25, 170, y + 25], fill=col); label(d, (200, y), text, 60, anchor='lm'); y += 90

def base(P):
    img = Image.fromarray(paper().clip(0, 255).astype(np.uint8)); draw_land(img, P)
    return coast_lines(img, P)

def map_republic():
    P = Proj(-10, 42, 28, 50); img, mask = base(P)
    polys = [[(7.0, 45.9), (13.8, 46.6), (13.6, 45.6), (12.4, 44.2), (14.2, 42.2), (16.2, 41.5), (18.6, 40.2), (17.0, 39.0), (16.5, 38.0),
              (15.6, 37.9), (15.7, 39.5), (14.5, 40.6), (12.0, 41.5), (10.4, 43.0), (8.0, 43.8), (6.6, 45.2)],
             [(12.3, 38.2), (15.6, 38.3), (15.1, 36.6), (12.4, 37.6)],
             [(-9.5, 37.0), (-6.0, 36.0), (-1.0, 36.7), (0.2, 38.8), (3.2, 41.9), (1.0, 42.6), (-2.0, 41.5), (-6.5, 40.5), (-8.8, 39.0)],
             [(3.0, 42.8), (7.5, 43.8), (7.0, 44.9), (5.0, 45.6), (2.0, 44.5)],
             [(13.6, 45.6), (19.5, 42.5), (19.4, 40.2), (24.0, 40.2), (26.0, 41.2), (23.5, 42.2), (21.0, 42.3), (16.5, 44.5)],
             [(19.5, 40.0), (22.5, 36.4), (24.0, 38.0), (23.0, 40.3)],
             [(26.0, 40.3), (30.0, 41.0), (31.5, 40.5), (30.5, 37.5), (28.0, 36.6), (26.2, 38.2)],
             [(32.0, 36.6), (36.2, 36.6), (36.0, 37.4), (32.6, 37.4)], [(35.8, 36.9), (38.5, 36.4), (37.0, 33.0), (35.0, 33.2)],
             [(8.5, 37.2), (11.2, 37.1), (11.2, 35.0), (10.0, 34.2), (8.4, 35.8)], [(19.8, 32.8), (23.5, 32.9), (23.5, 30.6), (20.0, 30.5)],
             [(8.2, 41.3), (9.8, 41.3), (9.8, 39.0), (8.2, 38.9)], [(8.5, 43.0), (9.7, 43.0), (9.7, 41.4), (8.5, 41.4)]]
    img = apply_regions(img, [region(P, mask, q, ROME, 0.42) for q in polys]); d = ImageDraw.Draw(img)
    city(d, P, 12.5, 41.9, 'Rome', 70, dx=-140, dy=-20, star=True)
    label(d, P(4.0, 47.5), 'GAUL', 90, f='Cinzel.ttf', fill=(90, 70, 50), spacing=1)
    label(d, P(33.5, 33.0), 'PTOLEMAIC EGYPT', 62, f='Cinzel.ttf', fill=(90, 70, 50))
    label(d, P(44.0, 36.0), 'PARTHIA', 80, f='Cinzel.ttf', fill=(90, 70, 50))
    label(d, P(18.0, 34.5), 'MARE NOSTRUM', 70, spacing=1)
    legend(d, [((196, 140, 118), 'Roman territory, c. 60 BC')])
    label(d, (W - 60, H - 60), 'borders approximate', 54, anchor='rd')
    return vignette(img)

def map_gaul():
    P = Proj(-6, 13, 41.5, 52.5); img, mask = base(P)
    prov = [(3.0, 42.8), (7.6, 43.8), (7.0, 45.5), (5.8, 46.3), (4.5, 45.4), (2.0, 44.2), (0.5, 43.3)]
    cis = [(7.0, 45.6), (7.5, 46.5), (13.8, 46.6), (12.4, 44.2), (10.4, 44.0), (8.0, 44.2)]
    img = apply_regions(img, [region(P, mask, prov, ROME, 0.42), region(P, mask, cis, ROME, 0.42)]); d = ImageDraw.Draw(img)
    for lon, lat, n, dx, dy in ((6.14, 46.2, 'Geneva', 120, 40), (4.03, 46.92, 'Bibracte', -170, 0), (4.5, 47.54, 'Alesia', 150, -10),
                                (3.13, 45.72, 'Gergovia', -170, 20), (5.37, 43.3, 'Massilia', 0, 70), (2.35, 48.86, 'Lutetia', -40, -70)):
        city(d, P, lon, lat, n, 56, dx=dx, dy=dy)
    label(d, P(1.5, 47.0), 'FREE GAUL', 96, f='Cinzel.ttf', fill=(90, 70, 50), spacing=1)
    label(d, P(-1.0, 52.0), 'BRITAIN', 72, f='Cinzel.ttf', fill=(90, 70, 50))
    label(d, P(10.5, 50.5), 'GERMANS', 72, f='Cinzel.ttf', fill=(90, 70, 50))
    label(d, P(4.5, 44.4), 'Roman province', 56, fill=(120, 34, 28))
    ROUTES['03-02-1'] = [route(P, [(6.14, 46.2), (4.6, 46.6), (4.03, 46.92)]), route(P, [(4.03, 46.92), (6.0, 47.24), (7.4, 47.9)]),
                         route(P, [(6.0, 47.3), (4.03, 49.25), (4.2, 50.3)]), route(P, [(1.61, 50.73), (1.3, 51.1)]),
                         route(P, [(3.13, 45.72), (4.0, 46.6), (4.5, 47.5)])]
    label(d, (W - 60, H - 60), "Caesar's campaigns, 58–52 BC · simplified", 54, anchor='rd')
    return vignette(img)

def map_rubicon():
    P = Proj(8.5, 19, 39.5, 46.5); img, mask = base(P)
    cis = [(7.0, 45.6), (7.5, 46.5), (13.8, 46.6), (12.6, 45.0), (12.42, 44.1), (11.0, 43.95), (10.2, 44.05), (8.0, 44.2)]
    img = apply_regions(img, [region(P, mask, cis, ROME, 0.42)]); d = ImageDraw.Draw(img)
    rx = [P(12.42, 44.1), P(12.1, 43.95), P(11.8, 43.85)]; d.line(rx, fill=(60, 90, 130), width=12)
    label(d, P(11.6, 44.3), 'Rubicon', 66, fill=(40, 60, 100))
    for lon, lat, n, dx, dy, st in ((12.2, 44.42, 'Ravenna', -160, -40, 0), (12.57, 44.06, 'Ariminum', 210, 0, 0), (13.84, 42.12, 'Corfinium', 270, 50, 0),
                                    (12.5, 41.9, 'Rome', -120, 30, 1), (17.94, 40.63, 'Brundisium', -60, -80, 0)):
        city(d, P, lon, lat, n, 60, dx=dx, dy=dy, star=bool(st))
    label(d, P(10.0, 45.4), "Caesar's province", 64, fill=(120, 34, 28))
    ROUTES['04-02-0'] = [route(P, [(12.2, 44.42), (12.5, 44.1), (12.57, 44.06)]), route(P, [(12.57, 44.06), (13.6, 43.4), (13.84, 42.12)]),
                         route(P, [(13.84, 42.12), (15.6, 41.3), (17.94, 40.63)])]
    label(d, (W - 60, H - 60), 'January – March 49 BC', 54, anchor='rd')
    return vignette(img)

def map_civilwar():
    P = Proj(-10, 30, 33, 48); img, mask = base(P); d = ImageDraw.Draw(img)
    for lon, lat, n, dx, dy, st in ((12.5, 41.9, 'Rome', -120, -30, 1), (17.94, 40.63, 'Brundisium', 40, 70, 0), (19.45, 41.32, 'Dyrrhachium', 60, -70, 0),
                                    (0.62, 41.62, 'Ilerda', 0, -70, 0), (5.37, 43.3, 'Massilia', 0, -70, 0)):
        city(d, P, lon, lat, n, 56, dx=dx, dy=dy, star=bool(st))
    ROUTES['04-05-2'] = [route(P, [(17.94, 40.63), (18.8, 41.0), (19.45, 41.32)], POMP),
                         route(P, [(12.5, 41.9), (8.5, 44.2), (5.4, 43.4), (2.5, 42.3), (0.62, 41.62)])]
    legend(d, [((196, 140, 118), 'Caesar'), ((140, 150, 190), 'Pompey')])
    label(d, (W - 60, H - 60), '49 BC', 54, anchor='rd')
    return vignette(img)

def map_greece():
    P = Proj(17.5, 26, 37.5, 42.8); img, mask = base(P); d = ImageDraw.Draw(img)
    for lon, lat, n, dx, dy, st in ((19.45, 41.32, 'Dyrrhachium', -60, -70, 0), (19.47, 40.72, 'Apollonia', -200, 20, 0),
                                    (22.38, 39.3, 'Pharsalus', 0, 80, 1), (21.6, 39.55, 'Thessaly', 0, -60, 0), (22.95, 40.64, 'Thessalonica', 0, -70, 0)):
        city(d, P, lon, lat, n, 56, dx=dx, dy=dy, star=bool(st))
    ROUTES['05-01-0'] = [route(P, [(19.6, 41.2), (20.6, 40.3), (21.5, 39.6), (22.2, 39.35)]), route(P, [(19.7, 41.35), (21.2, 40.9), (22.2, 39.9), (22.45, 39.45)], POMP)]
    legend(d, [((196, 140, 118), 'Caesar'), ((140, 150, 190), 'Pompey')])
    label(d, (W - 60, H - 60), 'summer 48 BC', 54, anchor='rd')
    return vignette(img)

def map_parthia():
    P = Proj(-2, 52, 27, 50); img, mask = base(P); d = ImageDraw.Draw(img)
    for lon, lat, n, dx, dy, st in ((12.5, 41.9, 'Rome', -110, -30, 1), (17.94, 40.63, 'Brundisium', 0, 70, 0), (19.47, 40.72, 'Apollonia', 60, 60, 0),
                                    (44.58, 33.09, 'Ctesiphon', 0, 70, 0)):
        city(d, P, lon, lat, n, 56, dx=dx, dy=dy, star=bool(st))
    label(d, P(25.0, 46.0), 'DACIA', 80, f='Cinzel.ttf', fill=(90, 70, 50)); label(d, P(47.0, 36.5), 'PARTHIA', 90, f='Cinzel.ttf', fill=(90, 70, 50))
    ROUTES['09-00-0'] = [route(P, [(12.5, 41.9), (15.5, 41.2), (17.94, 40.63), (19.47, 40.72)]), route(P, [(19.47, 40.72), (22.0, 43.0), (24.5, 45.3)]),
                         route(P, [(24.5, 45.3), (30.0, 41.5), (36.5, 38.0), (41.0, 35.5), (44.4, 33.3)])]
    label(d, (W - 60, H - 60), 'the planned campaign, from 18 March 44 BC', 54, anchor='rd')
    return vignette(img)

def map_mutina():
    P = Proj(6.5, 21, 37, 46.8); img, mask = base(P); d = ImageDraw.Draw(img)
    for lon, lat, n, dx, dy, st in ((10.93, 44.65, 'Mutina', -150, -30, 0), (11.34, 44.49, 'Bononia', 150, 40, 0), (12.5, 41.9, 'Rome', -110, 20, 1),
                                    (17.94, 40.63, 'Brundisium', 0, 70, 0), (19.47, 40.72, 'Apollonia', 120, -60, 0)):
        city(d, P, lon, lat, n, 56, dx=dx, dy=dy, star=bool(st))
    ROUTES['14-03-0'] = [route(P, [(19.47, 40.72), (18.6, 40.6), (17.94, 40.63)], (176, 132, 52)), route(P, [(17.94, 40.63), (15.0, 41.4), (12.6, 41.95)], (176, 132, 52)),
                         route(P, [(12.5, 41.9), (11.6, 43.3), (10.95, 44.55)], POMP), route(P, [(12.5, 42.0), (12.4, 43.6), (11.1, 44.5)], (176, 132, 52))]
    legend(d, [((214, 184, 120), 'Octavian'), ((140, 150, 190), 'Antony')])
    label(d, (W - 60, H - 60), '44–43 BC', 54, anchor='rd')
    return vignette(img)

def map_philippi():
    P = Proj(23.85, 24.6, 40.82, 41.17); img, mask = base(P)
    marsh = [(24.05, 40.99), (24.3, 40.985), (24.32, 40.95), (24.05, 40.95)]
    img = apply_regions(img, [region(P, mask, marsh, (110, 130, 100), 0.5)]); d = ImageDraw.Draw(img)
    d.line([P(23.85, 41.02), P(24.28, 41.01), P(24.41, 40.94)], fill=(120, 96, 64), width=10)
    label(d, P(23.98, 41.04), 'Via Egnatia', 56); label(d, P(24.18, 40.965), 'marsh', 60, fill=(60, 80, 50))
    city(d, P, 24.28, 41.01, 'Philippi', 64, dx=0, dy=-75, star=True); city(d, P, 24.41, 40.94, 'Neapolis', 56, dx=0, dy=70)
    for lon, lat, n, col in ((24.22, 41.035, 'Brutus', ROME), (24.235, 41.0, 'Cassius', ROME), (24.10, 41.03, 'Octavian', POMP), (24.10, 40.995, 'Antony', POMP)):
        x, y = P(lon, lat); d.rectangle([x - 60, y - 34, x + 60, y + 34], outline=col, width=8); label(d, (x, y - 75), n, 56, f='Cinzel.ttf', fill=col)
    ROUTES['15-02-0'] = [route(P, [(24.20, 41.035), (24.13, 41.03)]), route(P, [(24.115, 40.995), (24.205, 41.0)], POMP)]
    legend(d, [((196, 140, 118), 'Brutus and Cassius'), ((140, 150, 190), 'Antony and Octavian')])
    label(d, (W - 60, H - 60), 'first battle, 3 October 42 BC · positions approximate', 54, anchor='rd')
    return vignette(img)

def card(lines, out):
    img = Image.new('RGB', (W, H), (10, 9, 8)); d = ImageDraw.Draw(img); y = H / 2 - (len(lines) - 1) * 130
    for text, size, colr, f in lines:
        d.text((W / 2, y), text, font=font(f, size), fill=colr, anchor='mm'); y += 260 if size > 100 else 200
    img.save(out)

def cards():
    G, Wt, R, Gr = (176, 132, 52), (230, 216, 186), (190, 70, 60), (150, 140, 125)
    img = Image.new('RGB', (W, H), (10, 9, 8)); d = ImageDraw.Draw(img)
    d.text((W * 0.27, 330), 'MYTH', font=font('Cinzel.ttf', 90), fill=R, anchor='mm'); d.text((W * 0.68, 330), 'WHAT THE SOURCES SAY', font=font('Cinzel.ttf', 90), fill=G, anchor='mm')
    rows = [('“Et tu, Brute?”', 'A line from the Elizabethan stage. Suetonius: a groan, or “You too, child?”'),
            ('“Beware the Ides of March”', 'Spurinna warned of danger lasting until the Ides'),
            ('Killed on the Capitol', 'Killed in the Curia of Pompey, on the Campus Martius')]
    for i, (m, r) in enumerate(rows):
        y = 700 + i * 470
        d.text((W * 0.27, y), m, font=font('CormorantGaramond-Italic.ttf', 104), fill=Gr, anchor='mm')
        lines = wrap(r, 84, 1900, d)
        for j, ln in enumerate(lines): d.text((W * 0.68, y + (j - (len(lines) - 1) / 2) * 100), ln, font=font('CormorantGaramond.ttf', 84), fill=Wt, anchor='mm')
    img.save(os.path.join(OUT, '16-05-0.png'))
    card([('THE IDES OF MARCH', 150, Wt, 'Cinzel.ttf'), ('Script, narration and edit: Ancient World Files', 64, (160, 150, 130), 'CormorantGaramond-Italic.ttf'),
          ('Reconstructions are artistic interpretations · AI-assisted imagery and voice', 56, (130, 122, 108), 'CormorantGaramond-Italic.ttf')],
         os.path.join(OUT, '16-07-3.png'))

def wrap(text, size, maxw, d):
    fo = font('CormorantGaramond.ttf', size); words, lines, cur = text.split(), [], ''
    for w_ in words:
        t = (cur + ' ' + w_).strip()
        if d.textlength(t, font=fo) > maxw and cur: lines.append(cur); cur = w_
        else: cur = t
    return lines + [cur]

MAPS = {'01-03-0': map_republic, '03-02-1': map_gaul, '04-02-0': map_rubicon, '04-05-2': map_civilwar, '05-01-0': map_greece,
        '09-00-0': map_parthia, '14-03-0': map_mutina, '15-02-0': map_philippi}

def main():
    os.makedirs(OUT, exist_ok=True)
    for k, fn in MAPS.items():
        fn().save(os.path.join(OUT, k + '.png')); print(k)
        if k in ROUTES: json.dump(ROUTES[k], open(os.path.join(OUT, k + '.routes.json'), 'w'))
    cards(); print('cards')

if __name__ == '__main__': main()
