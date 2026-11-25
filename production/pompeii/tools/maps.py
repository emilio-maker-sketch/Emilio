"""Animated dark cinematic maps for the Pompeii episode (same look as the Miyako sample).
Usage: python3 maps.py <preset> <duration> <out.mp4>
Presets: italy, bay, misenum, plume, voyage, stabiae, herculaneum, today
"""
import json, math, os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, 'build', 'maps'); os.makedirs(B, exist_ok=True)
W, H, FPS = 1920, 1080, 30
SERIF = '/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf'
SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; SANSB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
LAND10 = '/home/user/mapdata/package/land-10m.json'

P = {  # places (lon, lat)
    'VESUVIUS': (14.426, 40.821), 'POMPEII': (14.485, 40.749), 'HERCULANEUM': (14.348, 40.806), 'STABIAE': (14.485, 40.700),
    'OPLONTIS': (14.452, 40.757), 'MISENUM': (14.083, 40.781), 'NEAPOLIS': (14.255, 40.851), 'CAPRI': (14.243, 40.552),
    'NUCERIA': (14.649, 40.745), 'ROME': (12.496, 41.903), 'SURRENTUM': (14.375, 40.627), 'PUTEOLI': (14.121, 40.823),
}
REGIONS = {'italy': (5.0, 21.0, 35.5, 47.5, 260), 'bay': (13.70, 14.95, 40.40, 41.10, 5200)}

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
    out = []
    for g in t['objects'][obj]['geometries']:
        if g['type'] == 'Polygon': out.append([ring(r) for r in g['arcs']])
        elif g['type'] == 'MultiPolygon': out += [[ring(r) for r in p] for p in g['arcs']]
    return out

class Base:
    def __init__(self, name):
        self.lon0, self.lon1, self.lat0, self.lat1, self.ppd = REGIONS[name]
        self.k = math.cos(math.radians((self.lat0 + self.lat1) / 2))
        self.bw = int((self.lon1 - self.lon0) * self.k * self.ppd); self.bh = int((self.lat1 - self.lat0) * self.ppd)
        cache = os.path.join(B, f'base_{name}.png')
        if not os.path.exists(cache): self.render(cache)
        self.img = cv2.imread(cache)
    def xy(self, lon, lat): return ((lon - self.lon0) * self.k * self.ppd, (self.lat1 - lat) * self.ppd)
    def render(self, cache):
        bw, bh = self.bw, self.bh
        yy = np.linspace(0, 1, bh, dtype=np.float32)[:, None]; xx = np.linspace(0, 1, bw, dtype=np.float32)[None, :]
        g = 0.55 + 0.45 * (1 - np.hypot(xx - 0.55, yy - 0.45))
        img = Image.fromarray(np.clip(np.stack([9 * g, 15 * g, 22 * g], -1), 0, 255).astype(np.uint8), 'RGB')
        d = ImageDraw.Draw(img)
        step = 1.0 if self.ppd < 1000 else 0.1
        lon = math.ceil(self.lon0 / step) * step
        while lon < self.lon1:
            x, _ = self.xy(lon, 0); d.line([(x, 0), (x, bh)], fill=(24, 32, 42), width=2); lon += step
        lat = math.ceil(self.lat0 / step) * step
        while lat < self.lat1:
            _, y = self.xy(0, lat); d.line([(0, y), (bw, y)], fill=(24, 32, 42), width=2); lat += step
        land = Image.new('L', (bw, bh), 0); dl = ImageDraw.Draw(land)
        for poly in topo_polys(LAND10, 'land'):
            xs = [p[0] for p in poly[0]]; ys = [p[1] for p in poly[0]]
            if max(xs) < self.lon0 - 1 or min(xs) > self.lon1 + 1 or max(ys) < self.lat0 - 1 or min(ys) > self.lat1 + 1: continue
            dl.polygon([self.xy(*p) for p in poly[0]], fill=255)
            for h in poly[1:]: dl.polygon([self.xy(*p) for p in h], fill=0)
        sm = max(1, int(self.ppd / 900))
        if sm > 1: land = land.filter(ImageFilter.GaussianBlur(sm * 2)).point(lambda v: 255 if v > 127 else 0)
        edge = land.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
        glow = edge.filter(ImageFilter.GaussianBlur(10))
        rng = np.random.default_rng(3)
        n = cv2.resize(cv2.GaussianBlur((rng.normal(0, 1, (bh // 8 + 1, bw // 8 + 1)) * 6).astype(np.float32), (0, 0), 2), (bw, bh))
        landcol = Image.fromarray(np.clip(np.array([44, 41, 38], np.float32) + n[..., None], 0, 255).astype(np.uint8))
        img.paste(landcol, (0, 0), land)
        img.paste(Image.new('RGB', (bw, bh), (170, 150, 120)), (0, 0), glow.point(lambda v: int(v * 0.45)))
        img.paste(Image.new('RGB', (bw, bh), (185, 170, 150)), (0, 0), edge.point(lambda v: int(v * 0.8)))
        cv2.imwrite(cache, cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR))

def ease(x):
    x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)
def font(p, s): return ImageFont.truetype(p, s)
F_LBL = font(SANSB, 30); F_SM = font(SANS, 24); F_SEA = font(SERIF, 46); F_CAP = font(SANS, 30); F_BIG = font(SERIF, 96)

def tracked(d, x, y, s, f, fill, track=6, center=True):
    w = sum(d.textlength(c, font=f) + track for c in s) - track
    if center: x -= w / 2
    for c in s: d.text((x, y), c, font=f, fill=fill); x += d.textlength(c, font=f) + track

PRESETS = {
    'italy':       ('italy', [(0, 14.0, 41.5, 15.0), (0.55, 13.4, 41.3, 6.5), (1, 14.2, 40.9, 3.2)]),
    'bay':         ('bay',   [(0, 14.30, 40.74, 0.95), (1, 14.32, 40.75, 0.78)]),
    'misenum':     ('bay',   [(0, 14.20, 40.78, 0.62), (1, 14.25, 40.77, 0.70)]),
    'plume':       ('bay',   [(0, 14.40, 40.77, 0.70), (1, 14.44, 40.75, 0.52)]),
    'voyage':      ('bay',   [(0, 14.24, 40.76, 0.72), (1, 14.30, 40.74, 0.66)]),
    'stabiae':     ('bay',   [(0, 14.36, 40.74, 0.55), (1, 14.46, 40.71, 0.30)]),
    'herculaneum': ('bay',   [(0, 14.40, 40.80, 0.45), (1, 14.37, 40.81, 0.30)]),
    'today':       ('bay',   [(0, 14.30, 40.78, 0.80), (1, 14.38, 40.775, 0.62)]),
}

def camera(keys, f):
    for (t0, *a), (t1, *b) in zip(keys, keys[1:]):
        if f <= t1:
            e = ease((f - t0) / (t1 - t0 or 1))
            return a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e, a[2] * (b[2] / a[2]) ** e
    return tuple(keys[-1][1:])

def marker(d, x, y, name, sub, a, side='right', col=(245, 240, 230)):
    if a <= 0.01: return
    r = 8; A = int(255 * a)
    d.ellipse([x - r, y - r, x + r, y + r], fill=col + (A,))
    d.ellipse([x - r - 7, y - r - 7, x + r + 7, y + r + 7], outline=col + (int(110 * a),), width=2)
    f = F_LBL; tw = d.textlength(name, font=f)
    if side == 'right': tx = x + 22
    else: tx = x - 22 - tw
    d.text((tx, y - 22), name, font=f, fill=col + (A,))
    if sub: d.text((tx, y + 12), sub, font=F_SM, fill=(195, 190, 180, int(220 * a)))

def volcano(d, x, y, a, glow=0.0):
    if a <= 0.01: return
    s = 22
    if glow > 0:
        g = 40 + 10 * glow
        d.ellipse([x - g, y - g, x + g, y + g], fill=(230, 80, 30, int(70 * glow * a)))
    d.polygon([(x - s, y + s * 0.7), (x + s, y + s * 0.7), (x, y - s * 0.8)], fill=(220, 90, 50, int(255 * a)))
    d.text((x - d.textlength('VESUVIUS', font=F_LBL) / 2, y + 26), 'VESUVIUS', font=F_LBL, fill=(240, 120, 80, int(255 * a)))

def dashed(d, pts, u, col, width=3, dash=14):
    """Draw polyline pts revealed up to fraction u, dashed."""
    segs = list(zip(pts, pts[1:])); L = [math.dist(a, b) for a, b in segs]; tot = sum(L); lim = tot * u; acc = 0
    for (a, b), l in zip(segs, L):
        if acc >= lim: break
        n = max(1, int(l / dash))
        for i in range(n):
            if i % 2: continue
            s0, s1 = i / n, (i + 1) / n
            if acc + s0 * l > lim: break
            s1 = min(s1, (lim - acc) / l)
            d.line([(a[0] + (b[0] - a[0]) * s0, a[1] + (b[1] - a[1]) * s0), (a[0] + (b[0] - a[0]) * s1, a[1] + (b[1] - a[1]) * s1)], fill=col, width=width)
        acc += l

def overlay(preset, d, sxy, t, f, dur, pxdeg):
    A = lambda t0, ln=0.8: ease((t - t0) / ln)
    if preset == 'italy':
        a = 1 - ease((f - 0.35) / 0.2)
        x, y = sxy(12.6, 43.2); tracked(d, x, y - 50, 'ITALIA', F_BIG, (230, 225, 215, int(190 * a)), 26)
        x, y = sxy(11.0, 39.3); tracked(d, x, y, 'MARE NOSTRUM', F_SEA, (160, 150, 130, int(150 * ease(f / 0.15) * (1 - ease((f - 0.5) / 0.15)))), 14)
        x, y = sxy(*P['ROME']); marker(d, x, y, 'ROME', None, A(1.0) * (1 - ease((f - 0.7) / 0.15)), 'left')
        x, y = sxy(*P['POMPEII']); marker(d, x, y, 'POMPEII', 'Campania', ease((f - 0.55) / 0.15), 'right', (250, 215, 160))
    else:
        show = {'bay': ['NEAPOLIS', 'HERCULANEUM', 'OPLONTIS', 'POMPEII', 'STABIAE', 'MISENUM', 'CAPRI', 'PUTEOLI'],
                'misenum': ['MISENUM', 'NEAPOLIS', 'POMPEII', 'HERCULANEUM', 'PUTEOLI'], 'plume': ['POMPEII', 'HERCULANEUM', 'STABIAE', 'OPLONTIS', 'NEAPOLIS'],
                'voyage': ['MISENUM', 'HERCULANEUM', 'POMPEII', 'STABIAE', 'NEAPOLIS'], 'stabiae': ['STABIAE', 'POMPEII', 'OPLONTIS'],
                'herculaneum': ['HERCULANEUM', 'NEAPOLIS', 'POMPEII'], 'today': ['NEAPOLIS', 'POMPEII', 'HERCULANEUM']}[preset]
        sides = {'MISENUM': 'left', 'HERCULANEUM': 'left', 'NEAPOLIS': 'left', 'PUTEOLI': 'left', 'CAPRI': 'right', 'STABIAE': 'left', 'OPLONTIS': 'left'}
        names = {'NEAPOLIS': ('NEAPOLIS', 'Naples'), 'CAPRI': ('CAPREAE', 'Capri'), 'STABIAE': ('STABIAE', None), 'PUTEOLI': ('PUTEOLI', None)}
        if preset == 'today': names = {'NEAPOLIS': ('NAPLES', 'pop. ~3 million metro'), 'POMPEII': ('POMPEII', 'ruins'), 'HERCULANEUM': ('ERCOLANO', 'Herculaneum')}
        for k, nm in enumerate(show):
            x, y = sxy(*P[nm]); lab, sub = names.get(nm, (nm, None))
            hi = (nm == 'POMPEII' and preset in ('plume', 'bay')) or (nm == 'MISENUM' and preset in ('misenum', 'voyage')) or (nm == 'STABIAE' and preset == 'stabiae') or (nm == 'HERCULANEUM' and preset == 'herculaneum')
            marker(d, x, y, lab, sub, A(0.4 + k * (0.5 if preset == 'bay' else 0.25)), sides.get(nm, 'right'), (250, 215, 160) if hi else (235, 232, 225))
        vx, vy = sxy(*P['VESUVIUS'])
        erupt = preset in ('plume', 'herculaneum', 'voyage', 'stabiae', 'misenum')
        volcano(d, vx, vy, A(0.2), (0.6 + 0.4 * math.sin(t * 5)) if erupt else 0)
        if preset == 'bay':
            x, y = sxy(14.22, 40.66); tracked(d, x, y, 'SINUS CUMANUS', F_SEA, (150, 160, 170, int(150 * A(1.5, 1.5))), 12)
        if preset == 'misenum':
            mx, my = sxy(*P['MISENUM']); u = A(1.5, 2.5)
            dashed(d, [(mx, my), (vx, vy)], u, (240, 235, 225, 200))
            if u > 0.9: d.text(((mx + vx) / 2 - 40, (my + vy) / 2 - 48), '≈ 30 km', font=F_SM, fill=(240, 235, 225, int(230 * A(4.0))))
        if preset == 'plume':
            u = A(1.0, max(2.0, dur * 0.7))
            # ash fall: soft grey lobe stretching south-east from the vent
            ov = Image.new('L', (W, H), 0); od = ImageDraw.Draw(ov)
            for i in range(14):
                s = i / 13; px, py = sxy(P['VESUVIUS'][0] + 0.30 * s * u, P['VESUVIUS'][1] - 0.20 * s * u)
                rr = (0.03 + 0.06 * s) * pxdeg * (0.4 + 0.6 * u); od.ellipse([px - rr, py - rr * 0.7, px + rr, py + rr * 0.7], fill=110)
            d._image.paste(Image.new('RGBA', (W, H), (175, 170, 165, 255)), (0, 0), ov.filter(ImageFilter.GaussianBlur(28)))
            ax0, ay0 = sxy(14.33, 40.93); ax1, ay1 = sxy(14.52, 40.82); a2 = A(0.5)
            d.line([(ax0, ay0), (ax1, ay1)], fill=(230, 230, 230, int(220 * a2)), width=4)
            ang = math.atan2(ay1 - ay0, ax1 - ax0)
            d.polygon([(ax1, ay1), (ax1 - 22 * math.cos(ang - 0.45), ay1 - 22 * math.sin(ang - 0.45)), (ax1 - 22 * math.cos(ang + 0.45), ay1 - 22 * math.sin(ang + 0.45))], fill=(230, 230, 230, int(220 * a2)))
            d.text((ax0 - 40, ay0 - 40), 'WIND', font=F_LBL, fill=(230, 230, 230, int(220 * a2)))
        if preset == 'voyage':
            route = [P['MISENUM'], (14.15, 40.74), (14.30, 40.74), (14.36, 40.78), (14.42, 40.72), (14.475, 40.703)]
            dashed(d, [sxy(*p) for p in route], A(0.8, dur * 0.8), (250, 215, 160, 230), 4)
        if preset == 'stabiae':
            route = [(14.30, 40.74), (14.36, 40.78), (14.42, 40.72), (14.475, 40.703)]
            dashed(d, [sxy(*p) for p in route], 1.0, (250, 215, 160, 200), 4)
        if preset == 'herculaneum':
            for k in range(4):
                u = ease((t - 1.0 - k * 1.2) / 3.0)
                if u <= 0: continue
                px, py = sxy(P['VESUVIUS'][0] - 0.085 * u, P['VESUVIUS'][1] - 0.012 * u); rr = (0.01 + 0.05 * u) * pxdeg
                d.ellipse([px - rr, py - rr * 0.6, px + rr, py + rr * 0.6], outline=(235, 80, 40, int(220 * (1 - 0.6 * u))), width=4)
            d.text((60 + 90, 846), 'PYROCLASTIC SURGE  ·  AROUND 1 AM', font=F_CAP, fill=(240, 120, 80, int(235 * A(1.5))))
        if preset == 'today':
            rr = 0.11 * pxdeg; a3 = A(1.0, 1.5)
            d.ellipse([vx - rr, vy - rr * 0.95, vx + rr, vy + rr * 0.95], fill=(220, 50, 40, int(55 * a3)), outline=(230, 60, 45, int(220 * a3)), width=3)
            d.text((vx + rr * 0.75, vy - rr * 0.95), 'RED ZONE', font=F_LBL, fill=(240, 90, 75, int(255 * A(2.0))))
            d.text((vx + rr * 0.75, vy - rr * 0.95 + 36), '~600,000 residents', font=F_SM, fill=(225, 205, 200, int(240 * A(2.4))))

def render(preset, dur, out):
    region, keys = PRESETS[preset]; base = Base(region)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    N = max(2, int(dur * FPS))
    for i in range(N):
        t = i / FPS; f = i / (N - 1)
        lon, lat, span = camera(keys, f)
        cx, cy = base.xy(lon, lat); sw = span * base.k * base.ppd; sh = sw * H / W
        M = np.float32([[W / sw, 0, -(cx - sw / 2) * W / sw], [0, H / sh, -(cy - sh / 2) * H / sh]])
        frame = cv2.warpAffine(base.img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        def sxy(lo, la):
            x, y = base.xy(lo, la); return ((x - (cx - sw / 2)) * W / sw, (y - (cy - sh / 2)) * H / sh)
        im = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert('RGBA')
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        overlay(preset, d, sxy, t, f, dur, W / span)
        im = Image.alpha_composite(im, ov)
        p.stdin.write(cv2.cvtColor(np.asarray(im.convert('RGB')), cv2.COLOR_RGB2BGR).tobytes())
    p.stdin.close(); p.wait()

if __name__ == '__main__':
    render(sys.argv[1], float(sys.argv[2]), sys.argv[3])
