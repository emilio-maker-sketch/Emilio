"""Antique-style maps of the Late Bronze Age eastern Mediterranean (4K PNG), from Natural Earth (world-atlas)."""
import json, os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'images', 'maps'); os.makedirs(OUT, exist_ok=True)
FONT = os.path.join(ROOT, 'assets', 'fonts')
W, H = 3840, 2160

def topo_polys(path, obj):
    t = json.load(open(path)); sx, sy = t['transform']['scale']; tx, ty = t['transform']['translate']
    arcs = []
    for a in t['arcs']:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    def ring(idx):
        pts = []
        for i in idx:
            seg = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts += seg[1:] if pts else seg
        return pts
    polys = []
    for g in t['objects'][obj]['geometries']:
        if g['type'] == 'Polygon': polys += [[ring(r) for r in g['arcs']]]
        elif g['type'] == 'MultiPolygon': polys += [[ring(r) for r in p] for p in g['arcs']]
    return polys

LAND = topo_polys('/home/user/mapdata/package/land-10m.json', 'land')

class Proj:
    def __init__(self, lon0, lon1, lat0, lat1):
        self.lon0, self.lat1 = lon0, lat1
        k = math.cos(math.radians((lat0 + lat1) / 2))
        sx = W / ((lon1 - lon0) * k); sy = H / (lat1 - lat0); self.s = min(sx, sy); self.k = k
        self.ox = (W - (lon1 - lon0) * k * self.s) / 2; self.oy = (H - (lat1 - lat0) * self.s) / 2
    def __call__(self, lon, lat):
        return (self.ox + (lon - self.lon0) * self.k * self.s, self.oy + (self.lat1 - lat) * self.s)

SEA = (58, 74, 82); SEA2 = (36, 48, 56); LANDC = (196, 170, 126); COAST = (92, 70, 44); INK = (52, 36, 22)
SITES = {
    'Mycenae': (22.76, 37.73), 'Tiryns': (22.80, 37.60), 'Pylos': (21.70, 37.03), 'Thebes ': (23.32, 38.32),
    'Knossos': (25.16, 35.30), 'Troy': (26.24, 39.96), 'Hattusa': (34.62, 40.02), 'Ugarit': (35.78, 35.60),
    'Enkomi': (33.88, 35.16), 'Kition': (33.63, 34.92), 'Hala Sultan Tekke': (33.61, 34.89), 'Kadesh': (36.51, 34.56), 'Carchemish': (38.01, 36.83),
    'Emar': (38.10, 35.99), 'Byblos': (35.65, 34.12), 'Sidon': (35.37, 33.56), 'Tyre': (35.20, 33.27),
    'Ashkelon': (34.55, 31.66), 'Gaza': (34.45, 31.50), 'Memphis': (31.25, 29.85), 'Amarna': (30.90, 27.65),
    'Thebes (Medinet Habu)': (32.60, 25.72), 'Babylon': (44.42, 32.54), 'Assur': (43.26, 35.46),
    'Uluburun wreck': (29.56, 36.13), 'Gordion': (31.99, 39.65), 'Megiddo': (35.18, 32.58), 'Lachish': (34.85, 31.56),
    'Ashdod': (34.65, 31.80), 'Ekron': (34.85, 31.78), 'Gath': (34.85, 31.70),
}
REGIONS = {
    'HATTI': (34.0, 39.0), 'EGYPT': (30.6, 27.0), 'AHHIYAWA': (21.6, 39.7), 'ALASHIYA': (32.9, 34.35),
    'ASSYRIA': (43.6, 36.5), 'BABYLONIA': (45.0, 31.6), 'MITANNI': (40.2, 37.0), 'CANAAN': (35.4, 32.4),
    'LUKKA': (29.6, 37.0), 'CRETE': (24.8, 34.6), 'ARZAWA': (28.0, 38.6), 'AMURRU': (36.6, 34.1),
}

def font(name, size): return ImageFont.truetype(os.path.join(FONT, name), size)

def base(P, title=None, subtitle=None):
    yy, xx = np.mgrid[0:H, 0:W]
    r = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2)
    sea = np.array(SEA)[None, None, :] * (1 - r[..., None] * 0.8) + np.array(SEA2)[None, None, :] * (r[..., None] * 0.8)
    img = Image.fromarray(np.clip(sea, 0, 255).astype('uint8'))
    land = Image.new('L', (W, H), 0); d = ImageDraw.Draw(land)
    for poly in LAND:
        for i, ring in enumerate(poly):
            pts = [P(x, y) for x, y in ring]
            if len(pts) > 2: d.polygon(pts, fill=0 if i else 255)
    landimg = Image.new('RGB', (W, H), LANDC)
    rng = np.random.default_rng(7)
    noise = Image.fromarray((rng.normal(0, 1, (H // 8, W // 8)) * 6 + 128).clip(0, 255).astype('uint8')).resize((W, H), Image.BICUBIC)
    landimg = Image.composite(Image.merge('RGB', [Image.eval(noise, lambda v, c=c: max(0, min(255, c + v - 128))) for c in LANDC]), landimg, Image.new('L', (W, H), 255))
    img.paste(landimg, (0, 0), land)
    # coast glow + line
    edge = land.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5))
    img.paste(Image.new('RGB', (W, H), COAST), (0, 0), edge.point(lambda v: 200 if v > 40 else 0))
    halo = land.filter(ImageFilter.GaussianBlur(18)); halo = Image.eval(halo, lambda v: int(70 * math.sin(math.pi * v / 255)))
    img.paste(Image.new('RGB', (W, H), (150, 170, 170)), (0, 0), Image.composite(halo, Image.new('L', (W, H), 0), Image.eval(land, lambda v: 255 - v)))
    # paper grain + vignette
    g = (rng.normal(0, 1, (H, W)) * 3).astype('int16')
    a = np.asarray(img).astype('int16') + g[..., None]
    vig = 1 - np.clip(r * 1.15 - 0.25, 0, 1) ** 2 * 0.55
    img = Image.fromarray(np.clip(a * vig[..., None], 0, 255).astype('uint8'))
    if title:
        d = ImageDraw.Draw(img)
        d.text((W / 2, 110), title, font=font('Cinzel.ttf', 96), fill=(236, 220, 190), anchor='mm', stroke_width=3, stroke_fill=(20, 14, 8))
        if subtitle: d.text((W / 2, 205), subtitle, font=font('CormorantGaramond-Italic.ttf', 64), fill=(226, 210, 180), anchor='mm', stroke_width=2, stroke_fill=(20, 14, 8))
    return img

def site(d, P, name, color=(120, 20, 14), r=16, size=50, dx=26, dy=0, anchor='lm'):
    x, y = P(*SITES[name])
    d.ellipse([x - r - 5, y - r - 5, x + r + 5, y + r + 5], fill=(240, 228, 200))
    d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    d.text((x + dx, y + dy), name.strip(), font=font('CormorantGaramond.ttf', size), fill=INK, anchor=anchor,
           stroke_width=4, stroke_fill=(230, 214, 180))

def region(d, P, name, size=64, color=(70, 44, 24)):
    x, y = P(*REGIONS[name])
    d.text((x, y), ' '.join(name), font=font('Cinzel.ttf', size), fill=color, anchor='mm', stroke_width=3, stroke_fill=(214, 192, 150))

def arrow_path(d, P, pts, color=(150, 30, 20), width=13):
    xy = [P(*p) for p in pts]
    for i in range(len(xy) - 1):
        (x0, y0), (x1, y1) = xy[i], xy[i + 1]
        n = int(math.hypot(x1 - x0, y1 - y0) / 34)
        for j in range(0, n, 2):
            a, b = j / n, min(1, (j + 1) / n)
            d.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], fill=color, width=width)
    (x0, y0), (x1, y1) = xy[-2], xy[-1]; ang = math.atan2(y1 - y0, x1 - x0)
    d.polygon([(x1, y1), (x1 - 50 * math.cos(ang - 0.45), y1 - 50 * math.sin(ang - 0.45)), (x1 - 50 * math.cos(ang + 0.45), y1 - 50 * math.sin(ang + 0.45))], fill=color)

LEFT = {'Tiryns', 'Pylos', 'Kition', 'Hala Sultan Tekke', 'Sidon', 'Tyre', 'Ashkelon', 'Gaza', 'Memphis', 'Byblos', 'Lachish', 'Ashdod', 'Gath'}
def sites(d, P, names, **kw):
    for n in names:
        if n in LEFT: site(d, P, n, dx=-26, anchor='rm', **kw)
        else: site(d, P, n, **kw)

def main():
    P = Proj(19.0, 47.5, 24.0, 42.5)
    # 1 overview of the great powers
    img = base(P, 'THE LATE BRONZE AGE WORLD', 'c. 1350 – 1200 B.C.E.'); d = ImageDraw.Draw(img)
    for r in ['HATTI', 'EGYPT', 'AHHIYAWA', 'ALASHIYA', 'ASSYRIA', 'BABYLONIA', 'MITANNI', 'CANAAN', 'CRETE', 'ARZAWA']: region(d, P, r)
    sites(d, P, ['Mycenae', 'Hattusa', 'Ugarit', 'Babylon', 'Assur', 'Memphis', 'Amarna', 'Troy', 'Knossos', 'Enkomi', 'Byblos'])
    img.save(os.path.join(OUT, 'map_overview.png'))
    # 2 trade routes
    img = base(P, 'THE BRONZE AGE NETWORK', 'Copper, tin, glass, ivory and grain'); d = ImageDraw.Draw(img)
    for r in ['HATTI', 'EGYPT', 'AHHIYAWA', 'ALASHIYA', 'BABYLONIA', 'ASSYRIA']: region(d, P, r, size=54)
    arrow_path(d, P, [(47.6, 34.4), (44.6, 32.8), (43.2, 35.4), (38.0, 36.8), (35.9, 35.6)])
    arrow_path(d, P, [(35.6, 35.3), (34.2, 35.0), (32.0, 35.9), (29.6, 36.1), (26.5, 36.7), (23.3, 37.4)], color=(20, 55, 120))
    arrow_path(d, P, [(31.6, 31.4), (33.0, 33.6), (34.6, 35.2)], color=(20, 55, 120))
    arrow_path(d, P, [(32.0, 31.5), (28.5, 33.5), (25.2, 35.6)], color=(20, 55, 120))
    sites(d, P, ['Ugarit', 'Enkomi', 'Uluburun wreck', 'Mycenae', 'Babylon', 'Assur', 'Memphis', 'Byblos'])
    d.text((P(46.3, 34.6)), 'TIN FROM THE EAST', font=font('Cinzel.ttf', 44), fill=(130, 26, 18), anchor='mm', stroke_width=3, stroke_fill=(230, 214, 180))
    img.save(os.path.join(OUT, 'map_trade.png'))
    # 3 Kadesh
    P2 = Proj(28.0, 41.0, 28.5, 41.5)
    img = base(P2, 'EGYPT AND HATTI', 'The Battle of Kadesh, 1274 B.C.E.'); d = ImageDraw.Draw(img)
    for r in ['HATTI', 'CANAAN', 'AMURRU', 'MITANNI']: region(d, P2, r, size=70)
    sites(d, P2, ['Hattusa', 'Kadesh', 'Ugarit', 'Carchemish', 'Megiddo', 'Byblos', 'Memphis'], size=60, r=20)
    arrow_path(d, P2, [(31.3, 30.1), (33.8, 31.4), (35.2, 32.9), (36.3, 34.3)], color=(30, 70, 110), width=14)
    arrow_path(d, P2, [(34.6, 39.7), (35.6, 37.6), (36.6, 35.0)], color=(150, 30, 20), width=14)
    img.save(os.path.join(OUT, 'map_kadesh.png'))
    # 4 Greece
    P3 = Proj(19.5, 29.5, 34.3, 41.0)
    img = base(P3, 'THE MYCENAEAN WORLD', 'Palaces destroyed c. 1225 – 1175 B.C.E.'); d = ImageDraw.Draw(img)
    sites(d, P3, ['Mycenae', 'Tiryns', 'Pylos', 'Thebes ', 'Knossos', 'Troy'], size=70, r=22)
    region(d, P3, 'AHHIYAWA', size=80); region(d, P3, 'CRETE', size=70)
    img.save(os.path.join(OUT, 'map_greece.png'))
    # 5 Cyprus
    P4 = Proj(31.5, 36.5, 33.6, 36.3)
    img = base(P4, 'ALASHIYA', 'Late Bronze Age Cyprus'); d = ImageDraw.Draw(img)
    SITES.update({'Maa-Palaeokastro': (32.37, 34.86), 'Pyla-Kokkinokremos': (33.69, 34.98)})
    sites(d, P4, ['Enkomi', 'Kition', 'Maa-Palaeokastro', 'Ugarit'], size=72, r=22)
    site(d, P4, 'Pyla-Kokkinokremos', size=60, r=18, dx=0, dy=-50, anchor='mb')
    d.text(P4(32.95, 34.95), 'T R O O D O S', font=font('Cinzel.ttf', 70), fill=(70, 44, 24), anchor='mm')
    img.save(os.path.join(OUT, 'map_cyprus.png'))
    # 6 destruction map
    img = base(P, 'A WORLD IN FLAMES', 'Major sites destroyed or abandoned, c. 1225 – 1150 B.C.E.'); d = ImageDraw.Draw(img)
    sites(d, P, ['Mycenae', 'Tiryns', 'Pylos', 'Thebes ', 'Troy', 'Hattusa', 'Ugarit', 'Emar', 'Enkomi', 'Megiddo', 'Lachish', 'Kadesh', 'Carchemish', 'Babylon', 'Gordion'], color=(190, 40, 20))
    site(d, P, 'Thebes (Medinet Habu)', color=(30, 70, 110), dx=-26, anchor='rm')
    img.save(os.path.join(OUT, 'map_destruction.png'))
    # 7 Sea Peoples / Philistines
    P5 = Proj(33.4, 36.8, 30.6, 33.6)
    img = base(P5, 'THE PHILISTINE COAST', 'Early twelfth century B.C.E.'); d = ImageDraw.Draw(img)
    sites(d, P5, ['Ashkelon', 'Ashdod', 'Gaza', 'Ekron', 'Gath', 'Megiddo'], size=72, r=22)
    img.save(os.path.join(OUT, 'map_philistia.png'))
    # 8 Climate evidence
    img = base(P, 'THE CLIMATE EVIDENCE', 'Pollen cores, lake sediments and tree rings'); d = ImageDraw.Draw(img)
    SITES.update({'Sea of Galilee core': (35.59, 32.82), 'Larnaca Salt Lake': (33.62, 34.90)})
    sites(d, P, ['Sea of Galilee core', 'Larnaca Salt Lake', 'Gordion'], color=(30, 70, 110), size=60, r=20)
    img.save(os.path.join(OUT, 'map_climate.png'))
    print('maps done', sorted(os.listdir(OUT)))

if __name__ == '__main__':
    main()
