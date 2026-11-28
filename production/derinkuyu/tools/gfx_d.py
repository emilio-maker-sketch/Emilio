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
           Ankara=(32.86, 39.93), Antioch=(36.16, 36.20), Amorium=(31.29, 39.02), Kultepe=(35.635, 38.850), Assur=(43.262, 35.457),
           Hattusa=(34.615, 40.020), Manzikert=(42.54, 39.14), Konya=(32.49, 37.87), Gelveri=(34.371, 38.277), NeaKarvali=(24.33, 40.96),
           Naours=(2.28, 50.04), Matmata=(10.0, 33.54), Armenia=(42.0, 39.5), Samosata=(38.52, 37.53), Athens=(23.73, 37.98), Comana=(36.150, 38.330))
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


# ---------------------------------------------------------------- graphics added for the one-hour cut
def m_kanesh(G):
    P = Proj(33.4, 36.6, 37.4, 39.5); base, mask = map_base(P); d = round(km('Derinkuyu', 'Kultepe'))
    G.add(title('KANESH', 'Kültepe, near Kayseri'), [0.0, 0.1], fix=True)
    peak(P, *PLD['Erciyes'], 'Mount Erciyes', [0.05, 0.2], G, dx=170, dy=120)
    cities(G, P, [(*PLD['Derinkuyu'], 'Derinkuyu', 60, 0, 85, True), (*PLD['Kayseri'], 'Kayseri', 52, 190, 10)], [0.1, 0.25])
    cities(G, P, [(*PLD['Kultepe'], 'Kanesh (Kültepe)', 62, 0, -80, True)], [0.3, 0.45]); G.pulse(P.n(*PLD['Kultepe']), (200, 60, 40), [0.45, 1.0])
    G.route(RD(P, 'Derinkuyu', 'Kultepe'), INK, [0.5, 0.7], w=6, dash=True)
    x0, y0 = P(*PLD['Derinkuyu']); x1, y1 = P(*PLD['Kultepe'])
    G.add(text_layer([(((x0 + x1) / 2 - 260, (y0 + y1) / 2 - 130), f'about {d} km', 58, ITA, INK, 'mm')]), [0.65, 0.8])
    G.focus = None; G.zoom = 1.04; finish(G, base)

def m_assur(G):
    P = Proj(31.0, 46.0, 33.0, 41.5); base, mask = map_base(P, ('Euphrates', 'Tigris'))
    d = round(km('Assur', 'Kultepe'), -2)
    G.add(title('FROM ASSUR TO KANESH', 'about 1900 BC'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Assur'], 'Assur', 62, 0, 80, True), (*PLD['Kultepe'], 'Kanesh', 62, 0, -80, True)], [0.05, 0.2])
    G.route(RD(P, 'Assur', (41.0, 36.9), (38.3, 37.2), (36.6, 37.9), 'Kultepe'), (150, 100, 40), [0.2, 0.7], w=12)
    G.add(text_layer([(P(40.6, 38.7), 'donkey caravans: tin and cloth west, silver and gold east', 54, ITA, INK, 'mm'), (P(39.2, 36.4), f'about {d:.0f} km in a straight line', 54, ITA, INK, 'mm')]), [0.6, 0.75])
    G.add(legend([((150, 100, 40), 'caravan route')], 'route approximate'), [0.7, 0.85], fix=True); finish(G, base)

def m_hittite(G):
    P = Proj(28.5, 41.5, 35.0, 42.5); base, mask = map_base(P)
    G.add(title('THE HITTITE HEARTLAND', 'about 1600–1200 BC'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [[(32.3, 41.3), (36.3, 41.3), (37.2, 39.4), (36.0, 37.6), (33.5, 37.6), (32.0, 39.0)]], (150, 100, 40), [0.1, 0.35], alpha=0.35)
    cities(G, P, [(*PLD['Hattusa'], 'Hattusa', 64, 0, -80, True), (*PLD['Kultepe'], 'Kanesh', 56, 170, 0), (*PLD['Derinkuyu'], 'Derinkuyu', 56, -200, 40)], [0.35, 0.55])
    G.add(legend([((150, 100, 40), 'Hittite core lands')]), [0.55, 0.7], fix=True); finish(G, base)

def m_kingdom(G):
    P = Proj(31.5, 39.5, 36.0, 41.5); base, mask = map_base(P)
    G.add(title('THE KINGDOM OF CAPPADOCIA', '2nd century BC'), [0.0, 0.1], fix=True)
    territory(G, P, mask, [[(33.0, 40.0), (37.0, 40.2), (38.6, 39.0), (37.6, 37.6), (35.0, 37.3), (33.2, 38.0)]], PHR, [0.1, 0.35], alpha=0.3)
    cities(G, P, [(*PLD['Kayseri'], 'Mazaca', 64, 0, -80, True), (*PLD['Derinkuyu'], 'Derinkuyu', 54, -200, 30)], [0.35, 0.55])
    G.add(legend([(PHR, 'Kingdom of Cappadocia')]), [0.55, 0.7], fix=True); G.focus = P.n(*PLD['Kayseri']); G.zoom = 1.1; finish(G, base)

def m_roman(G):
    P = Proj(29.5, 41.0, 35.0, 42.0); base, mask = map_base(P, ('Euphrates',))
    G.add(title('ROMAN CAPPADOCIA', 'from AD 17'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Kayseri'], 'Caesarea', 62, 200, -85, True), (*PLD['Ankara'], 'Ancyra', 54, 0, -70), (*PLD['Melitene'], 'Melitene', 54, 0, 75),
                  (*PLD['Samosata'], 'Samosata', 52, 0, 75), (*PLD['Derinkuyu'], 'Derinkuyu', 50, -200, 30)], [0.05, 0.25])
    G.route(RD(P, 'Ankara', 'Kayseri', 'Melitene'), ROM, [0.25, 0.55], w=10); G.route(RD(P, 'Kayseri', (37.0, 37.9), 'Samosata'), ROM, [0.4, 0.65], w=10)
    G.add(text_layer([(P(39.6, 39.4), 'the Euphrates frontier', 58, ITA, INK, 'mm')]), [0.6, 0.75])
    G.add(legend([(ROM, 'main roads east')], 'routes approximate'), [0.65, 0.8], fix=True); finish(G, base)

def m_838(G):
    P = Proj(29.5, 37.5, 36.4, 41.4); base, mask = map_base(P)
    G.add(title('THE CAMPAIGN OF 838', "al-Mu'tasim"), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Tarsus'], 'Tarsus', 52, 150, 30), (*PLD['Derinkuyu'], 'Derinkuyu', 54, 250, 0, True)], [0.0, 0.12])
    G.route(RD(P, 'Tarsus', 'Gates', 'Tyana', (34.1, 39.0), 'Ankara'), ARAB, [0.12, 0.5], w=12); cities(G, P, [(*PLD['Ankara'], 'Ancyra', 56, 0, -75)], [0.45, 0.55])
    G.route(RD(P, 'Ankara', 'Amorium'), ARAB, [0.55, 0.75], w=12); cities(G, P, [(*PLD['Amorium'], 'Amorium', 60, 0, 80, True)], [0.7, 0.8])
    G.pulse(P.n(*PLD['Amorium']), (200, 60, 40), [0.8, 1.0])
    G.add(legend([(ARAB, 'one Abbasid army, 838')], 'routes approximate'), [0.6, 0.75], fix=True); finish(G, base)

def m_manzikert(G):
    P = Proj(26.0, 45.0, 35.5, 42.8); base, mask = map_base(P)
    G.add(title('MANZIKERT', '1071'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Constantinople'], 'Constantinople', 52, 0, -70), (*PLD['Derinkuyu'], 'Derinkuyu', 54, 0, 80, True), (*PLD['Konya'], 'Konya', 54, 0, 75)], [0.0, 0.15])
    cities(G, P, [(*PLD['Manzikert'], 'Manzikert', 62, 0, 85)], [0.2, 0.35]); G.pulse(P.n(*PLD['Manzikert']), (200, 60, 40), [0.3, 0.6])
    for k, (lon, lat) in enumerate(((38.2, 39.4), (35.3, 39.0), (32.5, 38.8))): G.route(RD(P, (lon + 2.6, lat + 0.1), (lon, lat)), (40, 110, 80), [0.5 + 0.1 * k, 0.65 + 0.1 * k], w=10)
    G.add(legend([((40, 110, 80), 'Turkish advance after 1071')], 'schematic'), [0.6, 0.75], fix=True); finish(G, base)

def m_exchange(G):
    P = Proj(22.0, 36.5, 35.5, 42.5); base, mask = map_base(P)
    d = round(km('Gelveri', 'Derinkuyu'))
    G.add(title('1923', 'from Gelveri to Nea Karvali'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Gelveri'], 'Gelveri (Güzelyurt)', 56, 0, 85, True), (*PLD['Derinkuyu'], 'Derinkuyu', 50, 240, 0)], [0.05, 0.2])
    G.route(RD(P, 'Gelveri', (31.0, 39.6), (27.5, 40.4), (25.5, 40.7), 'NeaKarvali'), (150, 60, 50), [0.25, 0.7], w=10, dash=True)
    cities(G, P, [(*PLD['NeaKarvali'], 'Nea Karvali', 60, 0, -80, True)], [0.65, 0.8])
    G.add(text_layer([((P(*PLD['Gelveri'])[0], P(*PLD['Gelveri'])[1] + 170), f'about {d} km from Derinkuyu', 50, ITA, INK, 'mm')]), [0.15, 0.25])
    G.add(legend([((150, 60, 50), 'refugees, 1923–24')], 'route schematic'), [0.7, 0.85], fix=True); finish(G, base)

def m_three(G):
    P = Proj(34.2, 35.3, 38.2, 39.05); base, mask = map_base(P)
    G.add(title('THE THREE BEST KNOWN', 'and dozens more across the region'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Derinkuyu'], 'Derinkuyu', 64, 0, 85, True), (*PLD['Kaymakli'], 'Kaymaklı', 60, 250, 0, True), (*PLD['Ozkonak'], 'Özkonak', 60, 240, 0, True)], [0.05, 0.4])
    cities(G, P, [(*PLD['Nevsehir'], 'Nevşehir', 52, -250, 0), (*PLD['Avanos'], 'Avanos', 50, -200, 30)], [0.4, 0.55])
    G.add(legend([(GOLD, 'underground city open to visitors')], 'positions from map coordinates'), [0.55, 0.7], fix=True); finish(G, base)

def m_world(G):
    P = Proj(-8.0, 48.0, 28.0, 54.0); base, mask = map_base(P)
    G.add(title('REFUGES UNDERGROUND'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Derinkuyu'], 'Derinkuyu', 58, 0, 80, True)], [0.05, 0.2]); cities(G, P, [(*PLD['Naours'], 'Naours', 56, 0, -70)], [0.25, 0.4])
    cities(G, P, [(*PLD['Matmata'], 'Matmata', 56, 0, 75)], [0.45, 0.6]); cities(G, P, [(*PLD['Armenia'], "Xenophon's Armenia", 54, 0, -75)], [0.65, 0.8])
    G.focus = None; G.zoom = 1.02; finish(G, base)

def d_chimney(G):
    base = dbase(); G.add(title('HOW A FAIRY CHIMNEY FORMS', 'schematic'), [0.0, 0.1], fix=True)
    gy = 1850
    for k, (x, stage) in enumerate(((800, 0), (1900, 1), (3000, 2))):
        L = G.layer(); d = ImageDraw.Draw(L)
        if stage == 0:
            d.rectangle([x - 450, gy - 900, x + 450, gy], fill=ROCK + (255,), outline=INK + (255,), width=5); d.rectangle([x - 450, gy - 980, x + 450, gy - 900], fill=(110, 100, 90, 255))
        elif stage == 1:
            d.polygon([(x - 300, gy), (x - 90, gy - 900), (x + 90, gy - 900), (x + 300, gy)], fill=ROCK + (255,), outline=INK + (255,)); d.ellipse([x - 170, gy - 990, x + 170, gy - 880], fill=(110, 100, 90, 255))
        else:
            d.polygon([(x - 260, gy), (x, gy - 520), (x + 260, gy)], fill=ROCK + (255,), outline=INK + (255,)); d.ellipse([x + 260, gy - 80, x + 420, gy], fill=(110, 100, 90, 255))
        G.add(L, [0.1 + 0.25 * k, 0.25 + 0.25 * k])
    G.add(text_layer([((800, gy + 90), 'hard layer over soft tuff', 54, ITA, INK, 'mm'), ((1900, gy + 90), 'the cap shields the cone', 54, ITA, INK, 'mm'),
                      ((3000, gy + 90), 'cap falls; the cone wears away', 54, ITA, INK, 'mm')]), [0.75, 0.9])
    L = G.layer(); ImageDraw.Draw(L).line([(0, gy), (W, gy)], fill=INK + (255,), width=6); G.add(L, [0.0, 0.1])
    G.focus = None; G.zoom = 1.03; finish(G, base)

def d_cutting(G):
    base = section_base(G, 'CUTTING A ROOM', 'schematic')
    L = G.layer(); d = ImageDraw.Draw(L); d.rectangle([600, mpx(20) - 120, 1500, mpx(20) + 120], fill=DARK + (255,)); d.line([(700, GY), (800, mpx(20) - 120)], fill=DARK + (255,), width=60); G.add(L, [0.05, 0.2])
    for k in range(4):
        L = G.layer(); ImageDraw.Draw(L).rectangle([1500 + k * 220, mpx(20) - 120, 1720 + k * 220, mpx(20) + 120], fill=DARK + (255,)); G.add(L, [0.2 + 0.12 * k, 0.3 + 0.12 * k])
    G.route([[1300 / W, mpx(20) / H], [900 / W, mpx(12) / H], [760 / W, (GY - 30) / H]], (180, 90, 60), [0.4, 0.75], w=10)
    G.add(text_layer([((2600, mpx(32)), 'working forward into the rock face', 56, ITA, INK, 'mm'), ((1150, mpx(38)), 'loose rock carried up in baskets', 54, ITA, (180, 90, 60), 'mm')]), [0.55, 0.75])
    G.focus = None; G.zoom = 1.03; finish(G, base)

def d_dating(G):
    base = dbase(); G.add(title('WHY CARVED ROOMS ARE HARD TO DATE', 'schematic'), [0.0, 0.1], fix=True)
    L = G.layer(); d = ImageDraw.Draw(L)
    cols = [(160, 130, 90), (180, 150, 105), (196, 168, 120), (210, 186, 140)]
    for i, c in enumerate(cols): d.polygon([(250 + i * 90, 1850 - i * 220), (1650 - i * 90, 1850 - i * 220), (1600 - i * 90, 1630 - i * 220), (300 + i * 90, 1630 - i * 220)], fill=c + (255,), outline=INK + (255,))
    G.add(L, [0.05, 0.3])
    G.add(text_layer([((950, 1950), 'a mound: layers build up, oldest at the bottom', 54, ITA, INK, 'mm')]), [0.25, 0.4])
    L = G.layer(); d = ImageDraw.Draw(L); d.rectangle([2100, 800, 3600, 1850], fill=ROCK + (255,), outline=INK + (255,), width=5); d.rectangle([2500, 1150, 3200, 1500], fill=DARK + (255,)); G.add(L, [0.4, 0.6])
    G.add(text_layer([((2850, 1950), 'a carved room: rock removed, no layers left', 54, ITA, INK, 'mm')]), [0.6, 0.75])
    G.focus = None; G.zoom = 1.03; finish(G, base)


def m_comana(G):
    P = Proj(33.6, 37.4, 37.4, 39.6); base, mask = map_base(P)
    G.add(title('COMANA', 'a temple-state of Cappadocia'), [0.0, 0.1], fix=True)
    cities(G, P, [(*PLD['Kayseri'], 'Caesarea', 58, 0, -80, True), (*PLD['Derinkuyu'], 'Derinkuyu', 50, -200, 30)], [0.05, 0.2])
    cities(G, P, [(*PLD['Comana'], 'Comana (Şar)', 62, 0, 85, True)], [0.3, 0.45]); G.pulse(P.n(*PLD['Comana']), GOLD, [0.45, 1.0])
    G.add(legend([], 'positions from map coordinates'), [0.5, 0.6], fix=True); G.focus = P.n(*PLD['Comana']); G.zoom = 1.12; finish(G, base)

GFX_BY_DESC = {'Map of Cappadocia: Derinkuyu, Kaymaklı, Nevşehir': m_cappadocia, 'Map of central Cappadocia: Derinkuyu and Kaymaklı, about 10 km': m_central,
    'How a fairy chimney forms': d_chimney, 'Map of Cappadocia: Kültepe': m_kanesh, 'Map: the caravan route from Assur': m_assur, 'Map of the Hittite heartland': m_hittite,
    'Map: the Kingdom of Cappadocia': m_kingdom, 'Map: Roman Cappadocia': m_roman, 'Cross-section of Derinkuyu': d_section, 'How a room was cut': d_cutting,
    'Cross-section: vertical shafts': d_air, 'Why it stands': d_stand, 'How a rolling stone door works': d_door, 'Map of Anatolia: Phrygia': m_phrygia,
    "Map: route of Xenophon's": m_xenophon, 'Cross-section: the city growing': d_stages, 'Why rock-cut spaces are hard to date': d_dating,
    'Map of the Byzantine–Arab frontier': m_frontier, 'Map of the Abbasid invasion of 806': m_806, 'Map of the Abbasid campaign of 838': m_838,
    'Map: Manzikert 1071': m_manzikert, 'Map: Gelveri': m_exchange, 'Map: Derinkuyu and Kaymaklı, about 10 km apart, with the reported': m_tunnel,
    'Map: Nevşehir, about 30 km': m_nevsehir, 'Map of central Cappadocia: Derinkuyu, Kaymaklı, Özkonak': m_three, 'World map: Derinkuyu, Naours': m_world, 'Map: Comana': m_comana}

def gfx_map():
    """Shot id -> drawing function, matched on the shot line's description so that renumbering chapters never breaks a graphic."""
    import json
    out = {}
    for x in json.load(open(os.path.join(gfx.ROOT, 'shots.json'))):
        if x['kind'] in ('map', 'diagram'):
            f = next((v for k, v in GFX_BY_DESC.items() if x['desc'].startswith(k)), None)
            if f is None: raise SystemExit(f"no graphic for {x['id']}: {x['desc'][:70]}")
            out[x['id']] = f
    return out
GFXD = gfx_map()

if __name__ == '__main__':
    for k in sys.argv[1:] or list(GFXD):
        gfx.TEXTS.clear(); G = Gfx(k); GFXD[k](G); print(k, len(G.layers), 'layers', flush=True)
