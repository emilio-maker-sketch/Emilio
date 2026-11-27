"""Adapt the board engine (copied from Pompeii) to Nineveh: zones, Near East background with the Tigris and Euphrates,
a Mesopotamia map card, diagrams, silent-film scenes, names/keywords and a B.C.-aware history axis."""
import re
p = 'kaz_engine.py'; s = open(p).read()

def sub(a, b, count=1):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b, count)

def between(start, end, new):
    global s
    i = s.index(start); j = s.index(end, i)
    s = s[:i] + new + s[j:]

# ---------------------------------------------------------------- zones
between("ZONES = [", "WW = COLS", """ZONES = ['open', 'king', 'library', 'fall', 'mound', 'flood', 'war', 'verdict']
ZONE_TITLES = {'open': 'EXHIBIT A', 'king': 'FILE 01  THE KING', 'library': 'FILE 02  THE LIBRARY', 'fall': 'FILE 03  THE FALL',
               'mound': 'FILE 04  THE MOUND', 'flood': 'FILE 05  THE FLOOD TABLET', 'war': 'FILE 06  THE WAR', 'verdict': 'FILE 07  VERDICT'}
""")

# ---------------------------------------------------------------- map card
between("BAY_LL = {", "def make_suspect(", '''BAY_LL = {'nineveh': (43.153, 36.359), 'mosul': (43.153, 36.359), 'nimrud': (43.33, 36.10), 'ashur': (43.26, 35.46),
          'arbela': (44.01, 36.19), 'babylon': (44.42, 32.54), 'borsippa': (44.34, 32.39), 'ecbatana': (48.52, 34.80),
          'zagros_pass': (46.2, 35.3)}
BAY_BOX = (38.6, 49.6, 31.2, 37.9)
def bay_xy(lon, lat, wworld=640, hworld=500):
    lo0, lo1, la0, la1 = BAY_BOX
    return ((lon - lo0) / (lo1 - lo0) * wworld, (la1 - lat) / (la1 - la0) * hworld)
THEBES_PTS = {k: bay_xy(*v) for k, v in BAY_LL.items()}          # name kept: the model looks for map points here
_RIV = None
def rivers():
    """Tigris and Euphrates centrelines (Natural Earth 1:10m). Modern courses: shown as such on the map."""
    global _RIV
    if _RIV is None:
        g = json.load(open('/home/user/mapdata/ne/rivers.geojson')); _RIV = []
        for f in g['features']:
            n = f['properties'].get('name') or ''
            if n in ('Tigris', 'Euphrates', 'Shatt al Arab'):
                geom = f['geometry']; lines = geom['coordinates'] if geom['type'] == 'MultiLineString' else [geom['coordinates']]
                for ln in lines: _RIV.append((n, ln))
    return _RIV
def make_thebes_map():
    wworld, hworld = 640, 500; pw, ph = int(wworld*R), int(hworld*R)
    p = Image.new("RGBA", (pw, ph), (170, 186, 186, 255)); d = ImageDraw.Draw(p, "RGBA")
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from make_maps import LAND
    for poly in LAND:
        for i, ring in enumerate(poly):
            if not any(BAY_BOX[0] - 3 < x < BAY_BOX[1] + 3 and BAY_BOX[2] - 3 < y < BAY_BOX[3] + 3 for x, y in ring[::3] or ring): continue
            pts = [(bay_xy(x, y)[0]*R, bay_xy(x, y)[1]*R) for x, y in ring]
            d.polygon(pts, fill=(170, 186, 186, 255) if i else (231, 220, 194, 255))
            d.line(pts + [pts[0]], fill=(110, 120, 120), width=int(2*R))
    # Zagros foothills: hatching along the north-east
    for k in range(26):
        lo, la = 44.6 + k * .19, 37.4 - k * .16
        x, y = bay_xy(lo, la); d.line([(x*R, y*R), ((x + 9)*R, (y - 12)*R)], fill=(150, 130, 100), width=int(2*R))
    for n, ln in rivers():
        pts = [(bay_xy(x, y)[0]*R, bay_xy(x, y)[1]*R) for x, y in ln]
        d.line(pts, fill=(96, 138, 150), width=int(3*R), joint='curve')
    fm = font(MONO, 15*R); fs = font(MONO, 12*R); ink = (40, 30, 22)
    lab = {'nineveh': ('NINEVEH', 1, -4), 'nimrud': ('NIMRUD', 1, 0), 'ashur': ('ASSUR', 1, 0), 'arbela': ('ARBELA', 1, -2),
           'babylon': ('BABYLON', 1, -6), 'borsippa': ('BORSIPPA', -1, 6), 'ecbatana': ('ECBATANA', -1, 0)}
    for k, (txt, side, dy) in lab.items():
        x, y = THEBES_PTS[k]
        d.rectangle([(x - 5)*R, (y - 5)*R, (x + 5)*R, (y + 5)*R], fill=(52, 38, 26))
        tx = x + 12 if side > 0 else x - 12 - fm.getbbox(txt)[2]/R
        d.text((tx*R, (y - 9 + dy)*R), txt, font=fm, fill=ink)
    x, y = THEBES_PTS['nineveh']; d.text(((x + 12)*R, (y + 9)*R), "(MOSUL)", font=fs, fill=(90, 76, 60))
    for txt, lo, la in (('ASSYRIA', 42.2, 35.9), ('BABYLONIA', 44.9, 31.9), ('MEDIA', 47.6, 35.6), ('ZAGROS', 46.3, 36.6), ('SYRIAN DESERT', 39.2, 34.0)):
        x, y = bay_xy(lo, la); d.text((x*R, y*R), txt, font=font(MONO, 13*R), fill=(110, 92, 70))
    for txt, lo, la in (('TIGRIS', 43.9, 34.6), ('EUPHRATES', 41.3, 34.55)):
        x, y = bay_xy(lo, la); d.text((x*R, y*R), txt, font=font(MONO, 12*R), fill=(70, 108, 120))
    d.text((24*R, 14*R), "ASSYRIA AND BABYLONIA", font=font(SERIF, 30*R), fill=ink)
    d.text((24*R, 50*R), "7TH CENTURY B.C.  -  RIVERS SHOWN IN THEIR MODERN COURSES", font=font(MONO, 11*R), fill=(80, 66, 52))
    d.line([(600*R, 30*R), (600*R, 80*R)], fill=ink, width=int(3*R)); d.text((592*R, 84*R), "N", font=font(MONO, 18*R), fill=ink)
    km = 100 / ((BAY_BOX[1] - BAY_BOX[0]) * 92.0) * 640                         # ~92 km per degree of longitude at 34 N
    d.line([(470*R, 470*R), ((470 + km)*R, 470*R)], fill=ink, width=int(3*R)); d.text((470*R, 476*R), "100 KM", font=font(MONO, 12*R), fill=ink)
    return shadowed(p), (wworld, hworld)

''')

# ---------------------------------------------------------------- diagrams
between("def make_diagram(kind):", "def make_stamp(text):", '''def make_diagram(kind):
    wworld, hworld = 560, 460; pw, ph = int(wworld*R), int(hworld*R)
    p = Image.new("RGBA", (pw, ph), (16, 22, 26, 255)); d = ImageDraw.Draw(p)
    for x in range(0, pw, int(20*R)): d.line([(x, 0), (x, ph)], fill=(24, 34, 40), width=1)
    for y in range(0, ph, int(20*R)): d.line([(0, y), (pw, y)], fill=(24, 34, 40), width=1)
    lab = (150, 170, 175); fs = font(MONO, 20*R); ln = (190, 210, 215)
    def tb(x, y, txt, col=(255, 255, 255), f=None):
        f = f or fs; w_ = f.getbbox(txt)[2]; d.rectangle([x - 6*R, y - 4*R, x + w_ + 6*R, y + f.size + 4], fill=(16, 22, 26)); d.text((x, y), txt, font=f, fill=col)
    if kind == 'tablet':
        d.text((24*R, 20*R), "A CLAY TABLET (SCHEMATIC)", font=font(MONO, 18*R), fill=lab)
        d.rounded_rectangle([70*R, 70*R, 330*R, 400*R], radius=int(26*R), fill=(150, 118, 84), outline=(210, 180, 140), width=int(3*R))
        for row in range(9):                                            # rows of wedges
            yy = 100 + row * 32
            for k in range(7):
                xx = 92 + k * 32 + (row % 2) * 6
                h_ = 10 + ((row * 7 + k * 3) % 3) * 3
                d.polygon([(xx*R, yy*R), ((xx + 14)*R, (yy + 2)*R), ((xx + 2)*R, (yy + h_)*R)], fill=(96, 70, 46))
            d.line([(84*R, (yy + 24)*R), (316*R, (yy + 24)*R)], fill=(130, 100, 70), width=1)
        d.rectangle([84*R, 360*R, 316*R, 388*R], outline=RED, width=int(3*R))
        d.line([(420*R, 120*R), (300*R, 230*R)], fill=(220, 200, 150), width=int(9*R))          # reed stylus
        d.polygon([(300*R, 230*R), (312*R, 214*R), (318*R, 226*R)], fill=(220, 200, 150))
        tb(350*R, 96*R, "REED STYLUS"); tb(350*R, 250*R, "WEDGE-SHAPED"); tb(350*R, 276*R, "MARKS = CUNEIFORM")
        tb(350*R, 360*R, "COLOPHON:", RED); tb(350*R, 386*R, "OWNER'S NOTE")
        tb(70*R, 420*R, "c. 8-15 CM ACROSS  -  WRITTEN ON BOTH SIDES", lab)
    elif kind == 'decipher':
        d.text((24*R, 20*R), "1857: ONE INSCRIPTION, FOUR TRANSLATORS", font=font(MONO, 18*R), fill=lab)
        names = ['RAWLINSON', 'HINCKS', 'TALBOT', 'OPPERT']
        for i, n in enumerate(names):
            x = 40 + i * 128
            d.rectangle([x*R, 110*R, (x + 112)*R, 250*R], outline=ln, width=int(3*R))
            for k in range(5): d.line([((x + 12)*R, (140 + k*20)*R), ((x + 100 - (k % 2)*20)*R, (140 + k*20)*R)], fill=(120, 140, 145), width=int(2*R))
            d.text(((x + 56)*R, 90*R), n, font=font(MONO, 16*R), fill=(230, 230, 230), anchor="mm")
            d.line([((x + 56)*R, 256*R), (280*R, 330*R)], fill=ln, width=int(2*R))
        d.rectangle([150*R, 330*R, 410*R, 390*R], outline=RED, width=int(4*R))
        d.text((280*R, 360*R), "SEALED - COMPARED", font=font(MONO, 20*R), fill=(240, 240, 240), anchor="mm")
        tb(90*R, 410*R, "THE TRANSLATIONS AGREED", (255, 255, 255))
    elif kind == 'joins':
        d.text((24*R, 20*R), "JOINING FRAGMENTS (SCHEMATIC)", font=font(MONO, 18*R), fill=lab)
        pieces = [[(60, 90), (200, 80), (215, 170), (150, 230), (70, 200)], [(215, 170), (200, 80), (330, 95), (320, 200), (250, 240)],
                  [(70, 200), (150, 230), (160, 330), (80, 360)], [(150, 230), (250, 240), (300, 340), (160, 330)]]
        off = [(-20, -10), (24, -14), (-26, 20), (30, 26)]
        for i, (pc, (ox, oy)) in enumerate(zip(pieces, off)):
            pts = [((x + ox)*R, (y + oy)*R) for x, y in pc]
            d.polygon(pts, fill=(150, 118, 84), outline=(210, 180, 140))
            cx = sum(x for x, _ in pc) / len(pc) + ox; cy = sum(y for _, y in pc) / len(pc) + oy
            for k in range(3): d.line([((cx - 30)*R, (cy - 14 + k*12)*R), ((cx + 26)*R, (cy - 14 + k*12)*R)], fill=(96, 70, 46), width=int(3*R))
        for a, b in ((0, 1), (0, 2), (1, 3), (2, 3)):
            ca = [sum(c) / len(pieces[a]) for c in zip(*pieces[a])]; cb = [sum(c) / len(pieces[b]) for c in zip(*pieces[b])]
            d.line([((ca[0] + off[a][0])*R, (ca[1] + off[a][1])*R), ((cb[0] + off[b][0])*R, (cb[1] + off[b][1])*R)], fill=RED, width=int(3*R))
        tb(360*R, 120*R, "PHOTOS + TEXT", (255, 255, 255)); tb(360*R, 150*R, "OF EACH PIECE")
        tb(360*R, 210*R, "ALGORITHM", RED); tb(360*R, 240*R, "SUGGESTS"); tb(360*R, 270*R, "MATCHES")
        tb(360*R, 330*R, "EXPERTS"); tb(360*R, 360*R, "CONFIRM")
    paper = Image.new("RGBA", (pw + int(28*R), ph + int(28*R)), (234, 227, 210, 255)); paper.paste(p, (int(14*R), int(14*R)))
    return shadowed(paper), (wworld + 28, hworld + 28)

''')

# ---------------------------------------------------------------- board background
sub("LON0, LON1, LAT0, LAT1 = 7.0, 21.0, 36.9, 42.3", "LON0, LON1, LAT0, LAT1 = 36.4, 50.4, 31.3, 36.7")
between("    vx_, vy_ = geo(14.426, 40.821)", "    for g in range(0, w, int(250*scale)): bg[:, g:g+2] += 6", '''    for n_, ln_ in rivers():                                                              # the two rivers, faint on the board
        pts = np.array([[geo(x, y)[0]*scale, geo(x, y)[1]*scale] for x, y in ln_], np.int32)
        cv2.polylines(bg, [pts], False, (74, 70, 46), max(2, int(14*scale)), cv2.LINE_AA)
''')
between("    for name, lon, lat in [('ROME', 12.5, 41.9)", "    for i, z in enumerate(ZONES):", '''    for name, lon, lat in [('NINEVEH', 43.25, 36.45), ('BABYLON', 44.5, 32.6), ('ASSUR', 43.35, 35.5), ('NIMRUD', 43.42, 36.15),
                           ('TIGRIS', 44.3, 34.2), ('EUPHRATES', 40.9, 34.9), ('ZAGROS', 46.6, 35.9), ('SYRIAN DESERT', 38.3, 33.4),
                           ('ASSYRIA', 42.1, 36.3), ('BABYLONIA', 45.3, 32.0), ('MEDIA', 48.6, 35.2)]:
        x, y = geo(lon, lat); d.text((x*scale, y*scale), name, font=font(MONO, 60*scale), fill=lab)
''')

# ---------------------------------------------------------------- names / keywords for word pop-ups
between("NAMES = {", "ORD = {}", """NAMES = {'nineveh': 'NINEVEH', 'ashurbanipal': 'ASHURBANIPAL', 'assyria': 'ASSYRIA', 'assyrian': 'ASSYRIA', 'babylon': 'BABYLON',
         'mosul': 'MOSUL', 'tigris': 'TIGRIS', 'nimrud': 'NIMRUD', 'assur': 'ASSUR', 'medes': 'THE MEDES', 'cyaxares': 'CYAXARES',
         'nabopolassar': 'NABOPOLASSAR', 'layard': 'LAYARD', 'rassam': 'RASSAM', 'kuyunjik': 'KUYUNJIK', 'sennacherib': 'SENNACHERIB',
         'smith': 'GEORGE SMITH', 'gilgamesh': 'GILGAMESH', 'utnapishtim': 'UTNAPISHTIM', 'gladstone': 'GLADSTONE', 'aleppo': 'ALEPPO',
         'esarhaddon': 'ESARHADDON', 'munich': 'MUNICH', 'borsippa': 'BORSIPPA'}
KEYWORDS = {'library', 'clay', 'tablets', 'fire', 'omens', 'liver', 'demons', 'curse', 'confiscation', 'siege', 'chronicle', 'skeletons',
            'arrowheads', 'fragments', 'flood', 'boat', 'dove', 'raven', 'clothes', 'expedition', 'video', 'tunnels', 'algorithm',
            'wedge', 'reed', 'scribes', 'wax', 'baked', 'kiln', 'ruins', 'mound', 'night', 'lion', 'engraver', 'evidence'}
""")

# ---------------------------------------------------------------- history axis: 7th century B.C. / 1840-1880 / 2010-2030
between("HIST = [", "def time_strip(", """HIST = [('669 B.C.', -669, '669 B.C.', 'KING'), ('c. 660-631 B.C.', -650, 'c. 650 B.C.', 'LIBRARY'), ('c. 631 B.C.', -631, '631 B.C.', 'DEATH'),
        ('614 B.C.', -614, '614 B.C.', 'ASSUR'), ('612 B.C.', -612, '612 B.C.', 'FALL'), ('1849', 1849, '1849', 'DIGGING'),
        ('1872', 1872, '1872', 'FLOOD TABLET'), ('1876', 1876, '1876', 'SMITH DIES'), ('2015', 2015, '2015', 'DESTRUCTION'), ('2023', 2023, '2023', 'AI JOINS')]
""")
sub("""        def xp(v):
            if v < 200: return 300 + (v - 55) / 30 * 330                          # A.D. 55-85
            if v < 1900: return 790 + (v - 1730) / 140 * 330                      # 1730-1870
            return 1280 + (v - 1975) / 55 * 340                                   # 1975-2030
        for a_, b_ in ((55, 85), (1730, 1870), (1975, 2030)): d.line([(xp(a_), y), (xp(b_), y)], fill=dim, width=3)""",
"""        def xp(v):
            if v < 0: return 300 + (v + 675) / 70 * 430                           # 675-605 B.C.
            if v < 1950: return 860 + (v - 1840) / 45 * 330                       # 1840-1885
            return 1330 + (v - 2008) / 20 * 300                                   # 2008-2028
        for a_, b_ in ((-675, -605), (1840, 1885), (2008, 2028)): d.line([(xp(a_), y), (xp(b_), y)], fill=dim, width=3)""")
sub("        for gx in (720, 1210):", "        for gx in (790, 1260):")
sub("key = o['a'] if any(m[0] == o['a'] for m in HIST) else 'A.D. 79'", "key = o['a'] if any(m[0] == o['a'] for m in HIST) else '612 B.C.'")
sub("        if marks is HIST and k_ == 'AUGUST 24?': continue\n", "")

# ---------------------------------------------------------------- figures: Assyrian men are bearded
sub('''    wline(d, [(x+18*s, y-320*s), (x+18*s + 90*s*arm, y-320*s - 50*s*arm + 90*s*(1-arm))], t, k+5, col, int(12*s))       # arm
''', '''    wline(d, [(x+18*s, y-320*s), (x+18*s + 90*s*arm, y-320*s - 50*s*arm + 90*s*(1-arm))], t, k+5, col, int(12*s))       # arm
    wpoly(d, [(x+8*s, y-350*s), (x+34*s, y-352*s), (x+30*s, y-300*s), (x+12*s, y-306*s)], t, k+11, col, col, 2)            # long Assyrian beard
''')

# ---------------------------------------------------------------- film scenes
between("def sc_flee(d, t, lt, CW):", "def film_frame(t, fi, F):", '''def shelves(d, x, y, t, k, n=5):
    for r in range(n):
        yy = y + r * 90
        wline(d, [(x, yy), (x + 420, yy)], t, k + r, INK, 6)
        for j in range(9):
            d.rectangle([x + 14 + j * 44, yy - 60 + (j % 3) * 6, x + 46 + j * 44, yy - 4], fill=(150, 118, 84), outline=INK)

def sc_scribes(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(150, 128, 98))
    shelves(d, 1500, 300, t, 4000)
    for i, x in enumerate((360, 760, 1160)):
        seated(d, x, 820, t, 4100 + 20 * i, .95, arm=.6 + .25 * math.sin(lt * 5 + i), face=1)
        wpoly(d, [(x + 60, 560), (x + 140, 556), (x + 142, 610), (x + 62, 614)], t, 4150 + i, (150, 118, 84), INK, 3)    # tablet on the knee
        if (int(lt * 6) + i) % 2: d.line([(x + 80, 580), (x + 120, 590)], fill=INK, width=3)
    d.ellipse([1300, 180, 1340, 220], fill=(250, 210, 120)); wline(d, [(1320, 220), (1320, 300)], t, 4190, INK, 4)          # lamp
    return ("NINEVEH  ·  c. 650 B.C.", "SCRIBES COPY TABLETS FOR THE KING'S LIBRARY")

def sc_siege(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(150, 120, 96))
    wpoly(d, [(900, 820), (900, 300), (CW, 300), (CW, 820)], t, 4200, (176, 150, 112), INK, 5)                               # city wall
    for k in range(14): d.rectangle([900 + k * 100, 260, 950 + k * 100, 300], fill=(176, 150, 112), outline=INK, width=4)    # merlons
    u = ease(lt / 6.0)
    for i in range(5):
        x = 120 + 140 * i + 300 * u
        figure(d, x, 820, t, 4300 + 30 * i, .95, arm=.9)
        wline(d, [(x + 60, 520), (x + 60, 380)], t, 4330 + i, INK, 4)                                                         # spear
    wline(d, [(820 + 60 * u, 820), (980, 330)], t, 4360, (90, 70, 50), 8); wline(d, [(860 + 60 * u, 820), (1020, 330)], t, 4361, (90, 70, 50), 8)  # ladder
    for r_ in range(8): wline(d, [(830 + 60 * u + r_ * 19, 800 - r_ * 60), (870 + 60 * u + r_ * 19, 800 - r_ * 60)], t, 4370 + r_, (90, 70, 50), 5)
    g = clamp((lt - 2.5) / 3)
    if g > 0:                                                                                                                # flames over the palace roofs
        for k in range(9):
            fx = 1000 + k * 140; fh = 120 + 80 * math.sin(lt * 7 + k)
            wpoly(d, [(fx - 50, 300), (fx, 300 - fh * g), (fx + 50, 300)], t, 4400 + k, (210, 120, 50), (150, 60, 30), 3)
        d.rectangle([900, 0, CW, int(200 * g)], fill=(120, 80, 60))
    return ("NINEVEH  ·  612 B.C.", "THE MEDES AND BABYLONIANS BREAK INTO THE CITY")

def sc_nightdig(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(46, 52, 70))
    for k in range(40): d.point((int((k * 397) % CW), int((k * 211) % 400)), fill=(220, 220, 200))
    wpoly(d, [(0, 820), (200, 420), (900, 360), (1700, 400), (CW, 560), (CW, 820)], t, 4500, (96, 86, 70), INK, 5)          # the mound
    d.pieslice([760, 520, 1080, 900], 180, 360, fill=(26, 22, 18)); d.rectangle([760, 710, 1080, 820], fill=(26, 22, 18))    # tunnel
    for i, x in enumerate((520, 680, 1180)):
        sw = .2 + .8 * abs(math.sin(lt * 3 + i))
        figure(d, x, 820, t, 4600 + 30 * i, .9, arm=sw)
        wline(d, [(x + 20 + 80 * sw, 520 - 40 * sw), (x + 40 + 110 * sw, 470 - 60 * sw)], t, 4650 + i, (200, 190, 170), 6)    # pick
    for lx in (600, 1100):
        r_ = 120 + 10 * math.sin(lt * 9 + lx)
        d.ellipse([lx - r_, 640 - r_, lx + r_, 640 + r_], outline=(150, 130, 80), width=2); d.ellipse([lx - 14, 626, lx + 14, 654], fill=(250, 210, 120))
    return ("KUYUNJIK, NINEVEH  ·  1853", "RASSAM'S WORKMEN DIG IN SECRET, BY NIGHT")

def sc_reading(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(170, 150, 120))
    shelves(d, 100, 260, t, 4700, 4)
    wpoly(d, [(700, 600), (1500, 600), (1500, 630), (700, 630)], t, 4750, (120, 90, 60), INK, 4)                             # table
    wline(d, [(740, 630), (740, 820)], t, 4751, INK, 8); wline(d, [(1460, 630), (1460, 820)], t, 4752, INK, 8)
    jump = clamp((lt - 2.6) / .3) - clamp((lt - 3.2) / .3)
    x = 1100 + 220 * ease(clamp((lt - 3.2) / 2.5))
    figure(d, x, 820 - 120 * jump, t, 4800, 1.05, arm=.95 if lt > 2.6 else .5)
    d.polygon([(x + 70, 500), (x + 120, 500), (x + 118, 540), (x + 72, 540)], fill=(150, 118, 84))                            # the tablet
    if lt > 3.4:                                                                                                             # the jacket comes off
        u = ease(clamp((lt - 3.4) / 1.4)); jx, jy = x - 120 - 260 * u, 420 + 300 * u * u
        wpoly(d, [(jx, jy), (jx + 90, jy - 10), (jx + 110, jy + 110), (jx - 10, jy + 120)], t, 4850, (70, 64, 60), INK, 3)
    return ("THE BRITISH MUSEUM  ·  1872", "GEORGE SMITH READS THE FLOOD TABLET")

SCENES = {'scribes': sc_scribes, 'siege': sc_siege, 'nightdig': sc_nightdig, 'reading': sc_reading}
''')
open(p, 'w').write(s)
print('patched')
