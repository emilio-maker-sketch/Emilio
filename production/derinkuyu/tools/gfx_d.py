"""Derinkuyu maps and diagrams (same engine and look as gfx.py).  python3 tools/gfx_d.py [ids...]

Coordinates checked against standard gazetteer positions; distances are great-circle and computed by km() below.
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
import gfx
from gfx import *   # noqa: F401,F403  (Gfx, Proj, map_base, territory, cities, title, legend, text_layer, finish, dbase, nrm, colours, fonts)

PLD = dict(Derinkuyu=(34.735, 38.374), Kaymakli=(34.752, 38.462), Nevsehir=(34.714, 38.625), Goreme=(34.830, 38.643), Ozkonak=(34.850, 38.770),
           Avanos=(34.847, 38.715), Erciyes=(35.447, 38.531), Hasan=(34.164, 38.127), Kayseri=(35.485, 38.722), Nigde=(34.680, 37.970),
           Tyana=(34.610, 37.831), Heraclea=(34.050, 37.512), Tarsus=(34.893, 36.917), Gates=(34.780, 37.280), Constantinople=(28.98, 41.01),
           Gordion=(31.995, 39.651), Midas=(30.555, 39.190), Erzurum=(41.27, 39.90), Trapezus=(39.72, 41.00), Melitene=(38.33, 38.35),
           Ankara=(32.86, 39.93), Antioch=(36.16, 36.20), Amorium=(31.29, 39.02))
BYZ, ARAB, PHR, XEN = (52, 82, 130), (40, 110, 80), (150, 100, 40), (118, 46, 104)

def km(a, b):
    (lo1, la1), (lo2, la2) = PLD[a], PLD[b]; r = math.radians
    return 2 * 6371 * math.asin(math.sqrt(math.sin(r(la2 - la1) / 2) ** 2 + math.cos(r(la1)) * math.cos(r(la2)) * math.sin(r(lo2 - lo1) / 2) ** 2))

def RD(P, *names): return [P.n(*PLD[n]) if isinstance(n, str) else P.n(*n) for n in names]

def peak(P, lon, lat, name, a, G, dx=0, dy=-110):
    gfx.TEXTS.append(name); x, y = P(lon, lat)
    L = G.layer(); d = ImageDraw.Draw(L)
    d.polygon([(x - 60, y + 40), (x, y - 60), (x + 60, y + 40)], fill=(120, 100, 80, 255), outline=INK + (255,), width=5)
    d.text((x + dx, y + dy), name, font=font(ITA, 62), fill=INK + (255,), anchor='mm', stroke_width=3, stroke_fill=(236, 224, 196, 220))
    G.add(L, a)

# ---------------------------------------------------------------- maps
def m_cappadocia(G):
    P = Proj(33.4, 36.2, 37.4, 39.3); base, mask = map_base(P)
    G.add(title('CAPPADOCIA', 'central Anatolia, Turkey'), [0.0, 0.1], fix=True)
    peak(P, *PLD['Erciyes'], 'Mount Erciyes', [0.1, 0.25], G, dx=170, dy=120); peak(P, *PLD['Hasan'], 'Mount Hasan', [0.15, 0.3], G)
    cities(G, P, [(*PLD['Kayseri'], 'Kayseri', 56, 0, -70), (*PLD['Nevsehir'], 'Nevşehir', 56, -230, -10), (*PLD['Goreme'], 'Göreme', 52, 0, -70),
                  (*PLD['Nigde'], 'Niğde', 52, 0, 70)], [0.3, 0.45])
    cities(G, P, [(*PLD['Kaymakli'], 'Kaymaklı', 56, 240, 0), (*PLD['Derinkuyu'], 'Derinkuyu', 66, 0, 85, True)], [0.5, 0.65])
    G.pulse(P.n(*PLD['Derinkuyu']), (200, 60, 40), [0.65, 1.0]); G.focus = P.n(*PLD['Derinkuyu']); G.zoom = 1.18; finish(G, base)

def m_central(G):
    P = Proj(34.2, 35.3, 38.2, 39.05); base, mask = map_base(P)
    d = round(km('Derinkuyu', 'Kaymakli'))
    G.add(title('THE UNDERGROUND CITIES', 'central Cappadocia'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Derinkuyu'], 'Derinkuyu', 66, 0, 85, True), (*PLD['Kaymakli'], 'Kaymaklı', 62, 260, 0, True)], [0.05, 0.25])
    G.route(RD(P, 'Derinkuyu', 'Kaymakli'), INK, [0.25, 0.45], w=6, dash=True)
    G.add(text_layer([((P(*PLD['Derinkuyu'])[0] - 330, (P(*PLD['Derinkuyu'])[1] + P(*PLD['Kaymakli'])[1]) / 2), f'about {d} km', 58, ITA, INK, 'mm')]), [0.4, 0.5])
    cities(G, P, [(*PLD['Ozkonak'], 'Özkonak', 56, 240, 0, True), (*PLD['Nevsehir'], 'Nevşehir', 56, -250, 0), (*PLD['Goreme'], 'Göreme', 52, 220, 20)], [0.55, 0.7])
    G.add(legend([(GOLD, 'underground city open to visitors')], 'positions from map coordinates'), [0.7, 0.85], fix=True)
    G.focus = None; G.zoom = 1.04; finish(G, base)

def m_phrygia(G):
    P = Proj(25.5, 42.5, 35.5, 42.5); base, mask = map_base(P)
    G.add(title('ANATOLIA', 'Phrygia and Cappadocia'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [[(29.5, 40.3), (32.8, 40.3), (33.2, 38.9), (31.5, 38.0), (29.3, 38.6)]], PHR, [0.1, 0.35], alpha=0.4)
    G.add(text_layer([(P(30.9, 38.55), 'Phrygia', 72, CAP, PHR, 'mm'), (P(35.2, 38.95), 'Cappadocia', 72, CAP, BYZ, 'mm')]), [0.25, 0.45])
    cities(G, P, [(*PLD['Gordion'], 'Gordion', 52, 0, -70), (*PLD['Midas'], 'Midas City', 50, 0, -70), (*PLD['Derinkuyu'], 'Derinkuyu', 60, 0, 85, True)], [0.45, 0.6])
    G.add(legend([(PHR, 'Phrygian heartland, 8th–6th centuries BC')]), [0.6, 0.75], fix=True); finish(G, base)

def m_xenophon(G):
    P = Proj(26.0, 45.5, 35.5, 43.0); base, mask = map_base(P)
    d = round(km('Derinkuyu', 'Erzurum'), -1)
    G.add(title('THE MARCH OF THE TEN THOUSAND', '401–400 BC'), [0.0, 0.1], fix=True)
    G.route([P.n(43.4, 37.2), P.n(42.4, 38.4), P.n(41.6, 39.2), P.n(41.27, 39.9), P.n(40.4, 40.6), P.n(*PLD['Trapezus'])], XEN, [0.1, 0.5], w=10)
    G.add(text_layer([(P(42.6, 39.5), 'Armenia', 72, CAP, XEN, 'mm'), (P(41.3, 37.0), 'route approximate', 50, ITA, XEN, 'mm')]), [0.35, 0.5])
    cities(G, P, [(*PLD['Trapezus'], 'Trapezus', 52, 0, -70), (*PLD['Derinkuyu'], 'Derinkuyu', 62, 0, 85, True)], [0.5, 0.62])
    G.route(RD(P, 'Derinkuyu', 'Erzurum'), INK, [0.65, 0.85], w=6, dash=True)
    G.add(text_layer([(P(38.0, 38.65), f'about {d:.0f} km', 60, ITA, INK, 'mm')]), [0.8, 0.9])
    G.add(legend([(XEN, "Xenophon's route through Armenia")], 'positions approximate'), [0.6, 0.75], fix=True); finish(G, base)

FRONT = [(32.6, 36.1), (33.7, 36.9), (34.9, 37.3), (36.0, 37.9), (37.6, 38.6), (38.6, 39.2), (39.5, 39.9), (40.3, 40.4), (41.5, 41.0)]
def m_frontier(G):
    P = Proj(25.5, 44.0, 33.5, 43.0); base, mask = map_base(P)
    G.add(title('THE BYZANTINE–ARAB FRONTIER', 'c. 800 AD'), [0.0, 0.1], fix=True)
    byz = [(25.5, 43.0), (41.5, 43.0)] + FRONT[::-1] + [(25.5, 36.0)]
    arab = FRONT + [(41.5, 41.0), (44.0, 41.0), (44.0, 33.5), (35.8, 33.5), (35.9, 35.6), (35.8, 36.3), (34.5, 36.6), (33.7, 36.4), (32.6, 36.1)]
    territory(G, P, mask, [arab], ARAB, [0.2, 0.45], alpha=0.3)
    gx, gy = P(*PLD['Gates'])
    G.add(text_layer([(P(31.0, 39.8), 'Byzantine Empire', 70, CAP, BYZ, 'mm'), (P(40.0, 35.8), 'Abbasid Caliphate', 70, CAP, ARAB, 'mm'),
                      ((gx - 300, gy + 110), 'Taurus passes', 54, ITA, INK, 'mm')]), [0.35, 0.5])
    cities(G, P, [(*PLD['Constantinople'], 'Constantinople', 54, 0, -70), (*PLD['Derinkuyu'], 'Derinkuyu', 60, 0, -85, True),
                  (*PLD['Tarsus'], 'Tarsus', 52, 150, 30), (*PLD['Melitene'], 'Melitene', 52, 0, 70)], [0.5, 0.65])
    G.pulse(P.n(*PLD['Derinkuyu']), (200, 60, 40), [0.7, 1.0])
    G.add(legend([(LAND, 'Byzantine Empire'), (ARAB, 'Abbasid Caliphate')]), [0.6, 0.75], fix=True); G.focus = P.n(35.0, 38.0); G.zoom = 1.12; finish(G, base)

def m_806(G):
    P = Proj(32.8, 36.6, 36.4, 39.2); base, mask = map_base(P)
    d = round(km('Derinkuyu', 'Tyana'))
    G.add(title('THE INVASION OF 806', 'Harun al-Rashid'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Tarsus'], 'Tarsus', 56, 170, 30), (*PLD['Derinkuyu'], 'Derinkuyu', 62, 0, -85, True)], [0.0, 0.12])
    G.route(RD(P, 'Tarsus', 'Gates', 'Tyana'), ARAB, [0.12, 0.45], w=12)
    G.add(text_layer([((P(*PLD['Gates'])[0] + 60, P(*PLD['Gates'])[1]), 'Cilician Gates', 54, ITA, INK, 'lm')]), [0.25, 0.35])
    cities(G, P, [(*PLD['Tyana'], 'Tyana', 60, 170, 20)], [0.4, 0.5])
    G.route(RD(P, 'Tyana', 'Heraclea'), ARAB, [0.5, 0.65], w=12); cities(G, P, [(*PLD['Heraclea'], 'Heraclea', 56, -200, 20)], [0.6, 0.7])
    G.route(RD(P, 'Tyana', 'Derinkuyu'), INK, [0.7, 0.85], w=6, dash=True)
    G.add(text_layer([((P(*PLD['Tyana'])[0] + 260, (P(*PLD['Tyana'])[1] + P(*PLD['Derinkuyu'])[1]) / 2), f'about {d} km', 58, ITA, INK, 'mm')]), [0.8, 0.9])
    G.add(legend([(ARAB, 'Abbasid army, 806')], 'routes approximate'), [0.6, 0.75], fix=True); G.focus = P.n(34.6, 37.8); G.zoom = 1.1; finish(G, base)

def m_tunnel(G):
    P = Proj(34.45, 35.05, 38.3, 38.55); base, mask = map_base(P)
    d = round(km('Derinkuyu', 'Kaymakli'))
    G.add(title('DERINKUYU AND KAYMAKLI'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Derinkuyu'], 'Derinkuyu', 66, 0, 90, True), (*PLD['Kaymakli'], 'Kaymaklı', 66, 0, -90, True)], [0.05, 0.25])
    G.route(RD(P, 'Derinkuyu', 'Kaymakli'), (150, 60, 50), [0.3, 0.7], w=10, dash=True)
    x0, y0 = P(*PLD['Derinkuyu']); x1, y1 = P(*PLD['Kaymakli'])
    G.add(text_layer([((max(x0, x1) + 420, (y0 + y1) / 2 - 40), f'about {d} km apart', 60, ITA, INK, 'mm'),
                      ((max(x0, x1) + 420, (y0 + y1) / 2 + 60), 'tunnel reported, not confirmed', 56, ITA, (150, 60, 50), 'mm')]), [0.55, 0.7])
    G.focus = None; G.zoom = 1.03; finish(G, base)

def m_nevsehir(G):
    P = Proj(34.35, 35.15, 38.25, 38.75); base, mask = map_base(P)
    d = round(km('Derinkuyu', 'Nevsehir'))
    G.add(title('NEVŞEHIR', '2014'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Derinkuyu'], 'Derinkuyu', 62, 0, 85, True), (*PLD['Kaymakli'], 'Kaymaklı', 54, 230, 0, True)], [0.05, 0.2])
    cities(G, P, [(*PLD['Nevsehir'], 'Nevşehir', 66, 0, -85, True)], [0.3, 0.45]); G.pulse(P.n(*PLD['Nevsehir']), (200, 60, 40), [0.45, 1.0])
    G.route(RD(P, 'Derinkuyu', 'Nevsehir'), INK, [0.5, 0.7], w=6, dash=True)
    G.add(text_layer([((P(*PLD['Nevsehir'])[0] - 330, (P(*PLD['Nevsehir'])[1] + P(*PLD['Derinkuyu'])[1]) / 2), f'about {d} km', 58, ITA, INK, 'mm')]), [0.65, 0.8])
    G.focus = None; G.zoom = 1.03; finish(G, base)

# ---------------------------------------------------------------- diagrams (cross-sections, schematic)
ROCK, ROCK2, AIR, DARK = (206, 186, 146), (190, 168, 128), (90, 130, 170), (70, 56, 44)
GY, BOT = 520, 1960          # ground line and the 85 m line in pixels: 85 m = 1440 px
def mpx(m): return GY + m / 85 * (BOT - GY)
LEVELS = [(4, 700, 1500), (12, 900, 1700), (21, 600, 1300), (30, 1000, 1800), (41, 800, 1500), (53, 1100, 1700), (66, 900, 1400), (80, 1000, 1300)]

def section_base(G, ttl, sub):
    base = dbase(); G.add(title(ttl, sub), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L)
    d.rectangle([0, GY, W, H], fill=ROCK + (255,))
    for k in range(9): d.line([(0, GY + k * 180 + 60), (W, GY + k * 180 + 20)], fill=ROCK2 + (255,), width=4)
    for x in range(260, 3600, 330): d.rectangle([x, GY - 150, x + 220, GY], fill=(232, 222, 196, 255), outline=INK + (255,), width=5)
    d.line([(0, GY), (W, GY)], fill=INK + (255,), width=6)
    G.add(L, [0.0, 0.08])
    G.add(text_layer([((3700, GY - 200), 'the town today', 56, ITA, INK, 'rm')]), [0.05, 0.12])
    return base

def rooms(G, upto, a, col=DARK, start=0):
    L = G.layer(); d = ImageDraw.Draw(L)
    for i, (m, x0, x1) in enumerate(LEVELS[:upto]):
        if i < start: continue
        y = mpx(m); d.rectangle([x0, y - 45, x1, y + 45], fill=col + (255,))
        if i: pm, px0, px1 = LEVELS[i - 1]; sx = max(x0, px0) + 60; d.line([(sx, mpx(pm)), (sx + 120, y)], fill=col + (255,), width=34)
    if not start: d.line([(LEVELS[0][1] + 60, GY), (LEVELS[0][1] + 140, mpx(LEVELS[0][0]))], fill=col + (255,), width=34)
    G.add(L, a)

def scale_bar(G, a):
    L = G.layer(); d = ImageDraw.Draw(L); x = 3350
    x = 2950; d.line([(x, GY), (x, BOT)], fill=INK + (255,), width=6)
    for m in (0, 20, 40, 60, 85): d.line([(x - 30, mpx(m)), (x + 30, mpx(m))], fill=INK + (255,), width=6)
    G.add(L, a); x = 2950; G.add(text_layer([((x + 60, mpx(m)), f'{m} m', 56, CAP, INK, 'lm') for m in (20, 40, 60)] + [((x + 60, mpx(85)), 'about 85 m', 56, CAP, INK, 'lm')]), a)

def d_section(G):
    base = section_base(G, 'DERINKUYU IN SECTION', 'schematic; levels simplified')
    rooms(G, 8, [0.1, 0.6]); scale_bar(G, [0.3, 0.5])
    G.add(text_layer([((LEVELS[0][2] + 60, mpx(LEVELS[0][0])), 'stables, kitchens, presses', 54, ITA, (245, 236, 215), 'lm'),
                      ((LEVELS[7][2] + 60, mpx(LEVELS[7][0])), 'lowest known level', 54, ITA, INK, 'lm'),
                      ((300, H - 110), 'at least eight levels known', 62, ITA, INK, 'lm')]), [0.6, 0.75])
    G.focus = None; G.zoom = 1.03; finish(G, base)

def d_air(G):
    base = section_base(G, 'AIR AND WATER', 'schematic')
    rooms(G, 8, [0.0, 0.1])
    L = G.layer(); d = ImageDraw.Draw(L)
    d.rectangle([1880, GY - 10, 1960, mpx(80) + 40], fill=(236, 226, 200, 255), outline=INK + (255,), width=4)
    d.rectangle([2500, GY - 10, 2560, BOT + 120], fill=(236, 226, 200, 255), outline=INK + (255,), width=4)
    d.rectangle([2505, BOT + 40, 2555, BOT + 120], fill=AIR + (255,))
    G.add(L, [0.1, 0.25])
    G.route([[1920 / W, (GY - 40) / H], [1920 / W, mpx(70) / H]], AIR, [0.25, 0.5], w=12)
    G.route([[1400 / W, mpx(60) / H], [1400 / W, (GY - 40) / H]], (180, 90, 60), [0.45, 0.7], w=12)
    G.add(legend([(AIR, 'fresh air in'), ((180, 90, 60), 'stale air out')], None), [0.5, 0.65], fix=True)
    G.add(text_layer([((2010, mpx(20)), 'air shaft', 56, ITA, INK, 'lm'), ((2610, mpx(45)), 'well shaft', 56, ITA, INK, 'lm'),
                      ((2610, BOT + 80), 'groundwater', 52, ITA, AIR, 'lm')]), [0.5, 0.7])
    G.focus = None; G.zoom = 1.03; finish(G, base)

def d_stand(G):
    base = dbase(); G.add(title('WHY IT STANDS', 'schematic'), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L); d.rectangle([300, 420, 3540, 1900], fill=ROCK + (255,), outline=INK + (255,), width=6); G.add(L, [0.0, 0.1])
    L = G.layer(); d = ImageDraw.Draw(L)
    for i, x in enumerate(range(520, 3300, 560)): d.rectangle([x, 700, x + 380, 950], fill=DARK + (255,))
    for i, x in enumerate(range(800, 3300, 560)): d.rectangle([x, 1300, x + 380, 1550], fill=DARK + (255,))
    G.add(L, [0.1, 0.35])
    G.add(text_layer([((1180, 640), 'small rooms', 56, ITA, INK, 'mm'), ((1000, 1110), 'thick rock left between rooms', 56, ITA, INK, 'mm'),
                      ((2600, 1700), 'lower level offset, standing on solid rock', 56, ITA, INK, 'mm')]), [0.4, 0.65])
    G.focus = None; G.zoom = 1.03; finish(G, base)

def d_door(G):
    base = dbase(); G.add(title('THE ROLLING STONE DOOR', 'schematic'), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L)
    d.rectangle([300, 600, 3540, 1850], fill=ROCK + (255,), outline=INK + (255,), width=6)
    d.rectangle([300, 1050, 3540, 1450], fill=(236, 226, 200, 255))           # passage, seen from above
    d.rectangle([1600, 650, 2100, 1050], fill=(150, 130, 100, 255))            # side slot
    G.add(L, [0.0, 0.12])
    G.add(text_layer([((800, 1250), 'outside', 62, CAP, INK, 'mm'), ((3100, 1250), 'inside the city', 62, CAP, INK, 'mm'),
                      ((1850, 560), 'slot cut into the wall', 54, ITA, INK, 'mm')]), [0.1, 0.25])
    G.unit((120, 100, 80), '', [[0.0, 0.485, 0.39, 0.12, 0.06, 0], [0.45, 0.485, 0.39, 0.12, 0.06, 0], [0.75, 0.485, 0.58, 0.12, 0.06, 0], [1.0, 0.485, 0.58, 0.12, 0.06, 0]])
    G.route([[0.62, 0.36], [0.55, 0.43], [0.53, 0.53]], (160, 60, 40), [0.4, 0.7], w=10)
    G.add(text_layer([((2500, 1620), 'rolled across from inside', 56, ITA, (160, 60, 40), 'mm'), ((W / 2, H - 120), 'view from above; sizes not to scale', 52, ITA, INK, 'mm')]), [0.6, 0.8])
    G.focus = None; G.zoom = 1.03; finish(G, base)

def d_stages(G):
    base = section_base(G, 'A CITY THAT GREW', 'schematic; dates uncertain')
    rooms(G, 3, [0.1, 0.3], col=(120, 90, 60)); G.add(text_layer([((2200, mpx(10)), 'earlier rooms (date unknown)', 54, ITA, INK, 'lm')]), [0.25, 0.4])
    rooms(G, 8, [0.45, 0.7], col=DARK, start=3); G.add(text_layer([((2200, mpx(55)), 'deeper levels added later', 54, ITA, INK, 'lm')]), [0.65, 0.8])
    G.focus = None; G.zoom = 1.03; finish(G, base)

GFXD = {'01-00-0': m_cappadocia, '01-03-0': m_central, '02-02-0': d_section, '03-00-1': d_air, '03-03-0': d_stand, '04-00-2': d_door,
        '05-01-1': m_phrygia, '05-03-0': m_xenophon, '05-04-0': d_stages, '06-00-0': m_frontier, '06-03-0': m_806, '08-02-0': m_tunnel, '08-03-0': m_nevsehir}

if __name__ == '__main__':
    for k in sys.argv[1:] or list(GFXD):
        gfx.TEXTS.clear(); G = Gfx(k); GFXD[k](G); print(k, len(G.layers), 'layers', flush=True)
