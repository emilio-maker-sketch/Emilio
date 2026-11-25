"""Dark cinematic animated map for the Miyako sample.
Renders one big base map once, then per frame: eased camera crop + live overlays (markers, rings, labels).
Output: build/map.mp4 (1920x1080, 30fps, raw, graded later in assemble.py)
"""
import json, math, os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, 'build'); os.makedirs(B, exist_ok=True)
W, H, FPS = 1920, 1080, 30
DUR = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
LON0, LON1, LAT0, LAT1, PPD = 124.0, 152.0, 26.0, 48.0, 360
K = math.cos(math.radians(37))
BW, BH = int((LON1 - LON0) * K * PPD), int((LAT1 - LAT0) * PPD)
SERIF = '/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf'
SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
SANSB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

MIYAKO = (141.957, 39.641); EPI = (142.373, 38.297); TOKYO = (139.69, 35.68); SENDAI = (140.87, 38.27)

def bxy(lon, lat):  # base-image pixel
    return ((lon - LON0) * K * PPD, (LAT1 - lat) * PPD)

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

def base_map():
    cache = os.path.join(B, 'map_base.png')
    if os.path.exists(cache): return cv2.imread(cache)
    # ocean: deep gradient
    yy = np.linspace(0, 1, BH)[:, None]; xx = np.linspace(0, 1, BW)[None, :]
    g = (0.55 + 0.45 * (1 - np.hypot(xx - 0.62, yy - 0.42)))
    ocean = np.stack([22 * g, 15 * g, 9 * g], -1)  # BGR-ish navy (B,G,R) -> stored as RGB below
    img = Image.fromarray(np.clip(ocean[..., ::-1], 0, 255).astype(np.uint8), 'RGB')
    d = ImageDraw.Draw(img)
    # faint graticule
    for lon in range(124, 153, 2):
        x, _ = bxy(lon, 0); d.line([(x, 0), (x, BH)], fill=(24, 32, 42), width=2)
    for lat in range(26, 49, 2):
        _, y = bxy(0, lat); d.line([(0, y), (BW, y)], fill=(24, 32, 42), width=2)
    land = Image.new('L', (BW, BH), 0); dl = ImageDraw.Draw(land)
    for poly in topo_polys('/home/user/mapdata/package/land-10m.json', 'land'):
        rings = [[bxy(x, y) for x, y in r] for r in poly]
        if not any(LON0 - 2 < x < LON1 + 2 and LAT0 - 2 < y < LAT1 + 2 for x, y in poly[0][::5] + poly[0][:1]): continue
        dl.polygon(rings[0], fill=255)
        for h in rings[1:]: dl.polygon(h, fill=0)
    edge = land.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    glow = edge.filter(ImageFilter.GaussianBlur(10))
    landcol = Image.new('RGB', (BW, BH), (38, 41, 44))
    # subtle relief noise on land
    n = (np.random.default_rng(3).normal(0, 1, (BH // 8, BW // 8)) * 6).astype(np.float32)
    n = cv2.resize(cv2.GaussianBlur(n, (0, 0), 2), (BW, BH))
    la = np.asarray(landcol).astype(np.float32) + n[..., None]
    landcol = Image.fromarray(np.clip(la, 0, 255).astype(np.uint8))
    img.paste(landcol, (0, 0), land)
    img.paste(Image.new('RGB', (BW, BH), (120, 150, 170)), (0, 0), glow.point(lambda v: int(v * 0.55)))
    img.paste(Image.new('RGB', (BW, BH), (150, 165, 175)), (0, 0), edge.point(lambda v: int(v * 0.8)))
    img.save(cache)
    return cv2.imread(cache)

def ease(x):
    x = min(max(x, 0), 1); return x * x * (3 - 2 * x)

# camera keyframes: (time_frac, lon, lat, span_lon)
KEYS = [(0.00, 138.2, 37.6, 21.0), (0.40, 141.6, 39.45, 5.2), (0.52, 142.4, 39.0, 6.4), (1.00, 142.5, 38.95, 6.0)]
def camera(f):
    for (t0, *a), (t1, *b) in zip(KEYS, KEYS[1:]):
        if f <= t1:
            e = ease((f - t0) / (t1 - t0))
            # interpolate span geometrically for a natural zoom
            lon = a[0] + (b[0] - a[0]) * e; lat = a[1] + (b[1] - a[1]) * e
            span = a[2] * (b[2] / a[2]) ** e
            return lon, lat, span
    return KEYS[-1][1:]

def font(p, s): return ImageFont.truetype(p, s)
F_BIG = font(SERIF, 120); F_LBL = font(SANSB, 30); F_SM = font(SANS, 24); F_SEA = font(SERIF, 44); F_CAP = font(SANS, 30)

def text_tracked(d, xy, s, f, fill, track=6, anchor_center=False):
    w = sum(d.textlength(c, font=f) + track for c in s) - track
    x, y = xy
    if anchor_center: x -= w / 2
    for c in s:
        d.text((x, y), c, font=f, fill=fill); x += d.textlength(c, font=f) + track

def main():
    base = base_map()
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-crf', '14', '-preset', 'medium', '-pix_fmt', 'yuv420p', os.path.join(B, 'map.mp4')], stdin=subprocess.PIPE)
    N = int(DUR * FPS)
    T_EQ = (float(sys.argv[2]) if len(sys.argv) > 2 else 0.55) * DUR  # earthquake moment (sec into the map)
    for i in range(N):
        t = i / FPS; f = i / (N - 1)
        lon, lat, span = camera(f)
        cx, cy = bxy(lon, lat); sw = span * K * PPD; sh = sw * H / W
        # shake during earthquake
        if T_EQ < t < T_EQ + 3.0:
            amp = 6 * (1 - (t - T_EQ) / 3.0) * sw / W
            cx += amp * math.sin(t * 61); cy += amp * math.cos(t * 47)
        M = np.float32([[W / sw, 0, -(cx - sw / 2) * W / sw], [0, H / sh, -(cy - sh / 2) * H / sh]])
        frame = cv2.warpAffine(base, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        def sxy(ll):
            x, y = bxy(*ll); return ((x - (cx - sw / 2)) * W / sw, (y - (cy - sh / 2)) * H / sh)
        pxdeg = W / span  # screen px per degree lon (approx, *K handled in bxy)
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        # --- labels for the wide shot
        a_wide = 1 - ease((f - 0.05) / 0.2)
        if a_wide > 0.01:
            x, y = sxy((138.3, 36.6)); text_tracked(d, (x, y - 70), 'JAPAN', F_BIG, (230, 230, 225, int(200 * a_wide)), 28, True)
        a_sea = ease(f / 0.15) * (1 - ease((f - 0.35) / 0.15))
        if a_sea > 0.01:
            x, y = sxy((146.5, 35.0)); text_tracked(d, (x, y), 'PACIFIC OCEAN', F_SEA, (120, 145, 165, int(170 * a_sea)), 14, True)
        a_t = ease(f / 0.1) * (1 - ease((f - 0.3) / 0.1))
        if a_t > 0.01:
            x, y = sxy(TOKYO); d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(220, 220, 215, int(220 * a_t)))
            d.text((x + 16, y - 16), 'TOKYO', font=F_LBL, fill=(220, 220, 215, int(220 * a_t)))
        # --- Miyako marker
        a_m = ease((f - 0.28) / 0.1)
        if a_m > 0.01:
            x, y = sxy(MIYAKO); r = 9
            pulse = (t * 0.8) % 1
            d.ellipse([x - r - 30 * pulse, y - r - 30 * pulse, x + r + 30 * pulse, y + r + 30 * pulse], outline=(240, 240, 235, int(160 * a_m * (1 - pulse))), width=2)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(245, 245, 240, int(255 * a_m)))
            d.line([(x - 18, y), (x - 160, y)], fill=(245, 245, 240, int(200 * a_m)), width=2)
            d.text((x - 380, y - 44), 'MIYAKO', font=font(SANSB, 40), fill=(245, 245, 240, int(255 * a_m)))
            d.text((x - 380, y + 6), 'Iwate Prefecture', font=F_SM, fill=(190, 195, 200, int(230 * a_m)))
        # --- epicentre
        if t > T_EQ - 0.3:
            te = t - T_EQ; a_e = ease((te + 0.3) / 0.3)
            x, y = sxy(EPI)
            for k in range(6):  # expanding seismic rings
                age = te - k * 0.7
                if age > 0:
                    rr = age * pxdeg * 0.9; al = max(0, 1 - age / 4.0)
                    d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(230, 60, 45, int(200 * al)), width=3)
            glow = 22 + 6 * math.sin(t * 6)
            d.ellipse([x - glow, y - glow, x + glow, y + glow], fill=(220, 40, 30, int(70 * a_e)))
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=(240, 70, 55, int(255 * a_e)))
            a_lbl = ease((te - 0.6) / 0.5)
            d.text((x + 34, y - 38), 'EPICENTRE', font=F_LBL, fill=(240, 90, 75, int(255 * a_lbl)))
            d.text((x + 34, y + 2), 'Magnitude 9.0', font=F_SM, fill=(225, 205, 200, int(240 * a_lbl)))
            # distance line to Miyako
            a_l = ease((te - 2.5) / 1.0)
            if a_l > 0.01:
                mx, my = sxy(MIYAKO); n = 24
                for s in range(n):
                    if s % 2: continue
                    u0, u1 = s / n, (s + 1) / n
                    d.line([(x + (mx - x) * u0, y + (my - y) * u0), (x + (mx - x) * u1, y + (my - y) * u1)], fill=(230, 230, 225, int(170 * a_l)), width=2)
                d.text(((x + mx) / 2 + 18, (y + my) / 2 - 14), '≈ 150 km', font=F_SM, fill=(230, 230, 225, int(220 * a_l)))
        # --- time stamp lower-left (inside letterbox safe area)
        a_c = ease((t - T_EQ - 0.2) / 0.6)
        if a_c > 0.01:
            d.text((150, 846), '11 MARCH 2011  ·  14:46 JST', font=F_CAP, fill=(235, 235, 230, int(235 * a_c)))
            d.line([(150, 836), (150 + 120 * a_c, 836)], fill=(230, 60, 45, int(255 * a_c)), width=3)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        im = Image.alpha_composite(Image.fromarray(rgb).convert('RGBA'), ov).convert('RGB')
        p.stdin.write(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR).tobytes())
        if i % 60 == 0: print(f'map frame {i}/{N}', flush=True)
    p.stdin.close(); p.wait()

if __name__ == '__main__':
    main()
