"""One-off: adapt the Harem board engine (copied here) to the Pompeii video."""
import re
P = 'kaz_engine.py'
s = open(P).read()

def rep(old, new, count=1):
    global s
    assert old in s, old[:80]
    s = s.replace(old, new, count)

def rep_block(start, end, new):
    """replace from the line starting with `start` up to (not including) the line starting with `end`"""
    global s
    a = s.index(start); b = s.index(end, a)
    s = s[:a] + new + s[b:]

# ---------------------------------------------------------------- chapters
rep("ZONES = ['open', 'king', 'harem', 'plot', 'night', 'trial', 'case', 'end']",
    "ZONES = ['open', 'city', 'column', 'night', 'surge', 'casts', 'evidence', 'end']")
rep_block("ZONE_TITLES = {", "WW = COLS",
"""ZONE_TITLES = {'open': 'EXHIBIT A', 'city': 'FILE 01  THE CITY', 'column': 'FILE 02  THE COLUMN', 'night': 'FILE 03  THE NIGHT',
               'surge': 'FILE 04  THE SURGE', 'casts': 'FILE 05  THE CASTS', 'evidence': 'FILE 06  THE EVIDENCE', 'end': 'FILE 07  VERDICT'}
""")

# ---------------------------------------------------------------- board background: southern Italy
rep("LON0, LON1, LAT0, LAT1 = 17.0, 47.0, 21.2, 32.6", "LON0, LON1, LAT0, LAT1 = 7.0, 21.0, 36.9, 42.3")
rep_block("    # Nile (schematic)", "    for g in range(0, w, int(250*scale))",
"""    vx_, vy_ = geo(14.426, 40.821)                                                   # Vesuvius: a small dark cone mark
    cv2.circle(bg, (int(vx_*scale), int(vy_*scale)), max(3, int(26*scale)), (40, 40, 60), -1, cv2.LINE_AA)
""")
rep("""    for name, lon, lat in [('THEBES', 32.65, 25.7), ('MEMPHIS', 31.25, 29.85), ('ABYDOS', 31.9, 26.2), ('NUBIA / KUSH', 32.0, 22.2),
                           ('MEDITERRANEAN SEA', 22.0, 32.2), ('RED SEA', 37.0, 23.5), ('SINAI', 33.8, 29.3), ('CANAAN', 35.2, 32.0), ('NILE', 31.5, 27.6)]:""",
"""    for name, lon, lat in [('ROME', 12.5, 41.9), ('POMPEII', 14.6, 40.68), ('VESUVIUS', 14.55, 40.95), ('CAMPANIA', 14.9, 41.25),
                           ('TYRRHENIAN SEA', 11.2, 39.6), ('IONIAN SEA', 18.2, 38.2), ('SICILY', 13.6, 37.6), ('SARDINIA', 8.6, 40.1),
                           ('ADRIATIC SEA', 16.6, 42.15), ('CALABRIA', 16.2, 39.3)]:""")

# ---------------------------------------------------------------- Bay of Naples map card
rep_block("THEBES_PTS = {", "def make_suspect(",
'''BAY_LL = {'misenum': (14.085, 40.782), 'naples': (14.250, 40.845), 'herculaneum': (14.347, 40.806), 'vesuvius': (14.426, 40.821),
          'oplontis': (14.452, 40.757), 'pompeii': (14.485, 40.749), 'stabiae': (14.483, 40.700), 'sorrento': (14.375, 40.626)}
BAY_BOX = (13.98, 14.66, 40.56, 40.95)
def bay_xy(lon, lat, wworld=640, hworld=500):
    lo0, lo1, la0, la1 = BAY_BOX
    return ((lon - lo0) / (lo1 - lo0) * wworld, (la1 - lat) / (la1 - la0) * hworld)
THEBES_PTS = {k: bay_xy(*v) for k, v in BAY_LL.items()}          # name kept: the model looks for map points here
def make_thebes_map():
    wworld, hworld = 640, 500; pw, ph = int(wworld*R), int(hworld*R)
    p = Image.new("RGBA", (pw, ph), (170, 186, 186, 255)); d = ImageDraw.Draw(p, "RGBA")
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from make_maps import LAND
    for poly in LAND:
        for i, ring in enumerate(poly):
            if not any(BAY_BOX[0] - 1 < x < BAY_BOX[1] + 1 and BAY_BOX[2] - 1 < y < BAY_BOX[3] + 1 for x, y in ring[::3] or ring): continue
            pts = [(bay_xy(x, y)[0]*R, bay_xy(x, y)[1]*R) for x, y in ring]
            d.polygon(pts, fill=(170, 186, 186, 255) if i else (231, 220, 194, 255))
            d.line(pts + [pts[0]], fill=(110, 120, 120), width=int(2*R))
    # pumice fall: an ash lobe blown to the south-east of the vent
    vx, vy = THEBES_PTS['vesuvius']
    lobe = Image.new("RGBA", (pw, ph), (0, 0, 0, 0)); ld = ImageDraw.Draw(lobe)
    for k in range(9):
        cx, cy = vx + 24 + 16*k, vy + 22 + 13*k; r = 30 + 7*k
        ld.ellipse([(cx - r*1.3)*R, (cy - r*.8)*R, (cx + r*1.3)*R, (cy + r*.8)*R], fill=(90, 84, 80, 26))
    p.alpha_composite(lobe)
    d.text(((vx + 120)*R, (vy + 150)*R), "PUMICE FALL", font=font(MONO, 13*R), fill=(80, 70, 66))
    d.line([((vx + 40)*R, (vy - 70)*R), ((vx + 100)*R, (vy - 22)*R)], fill=(60, 50, 40), width=int(3*R))       # wind arrow (to SE)
    d.polygon([((vx + 100)*R, (vy - 22)*R), ((vx + 84)*R, (vy - 24)*R), ((vx + 96)*R, (vy - 38)*R)], fill=(60, 50, 40))
    d.text(((vx + 46)*R, (vy - 98)*R), "WIND", font=font(MONO, 13*R), fill=(60, 50, 40))
    # Vesuvius: a hatched cone
    d.polygon([((vx - 34)*R, (vy + 22)*R), (vx*R, (vy - 20)*R), ((vx + 34)*R, (vy + 22)*R)], fill=(120, 100, 80))
    d.polygon([((vx - 8)*R, (vy - 11)*R), (vx*R, (vy - 20)*R), ((vx + 8)*R, (vy - 11)*R)], fill=(178, 40, 32))
    fm = font(MONO, 15*R)
    names = {'misenum': 'MISENUM', 'naples': 'NEAPOLIS', 'herculaneum': 'HERCULANEUM', 'vesuvius': 'VESUVIUS', 'oplontis': 'OPLONTIS',
             'pompeii': 'POMPEII', 'stabiae': 'STABIAE', 'sorrento': 'SURRENTUM'}
    for k, (x, y) in THEBES_PTS.items():
        if k == 'vesuvius':
            d.text(((x - 50)*R, (y + 26)*R), names[k], font=fm, fill=(40, 30, 22)); continue
        d.rectangle([(x - 5)*R, (y - 5)*R, (x + 5)*R, (y + 5)*R], fill=(52, 38, 26))
        left = k in ('herculaneum', 'naples', 'sorrento')
        tx = x - 12 - fm.getbbox(names[k])[2]/R if left else x + 12
        ty = y - 9 + (14 if k == 'oplontis' else 0) - (10 if k == 'pompeii' else 0)
        d.text((tx*R, ty*R), names[k], font=fm, fill=(40, 30, 22))
    d.text((24*R, 14*R), "THE BAY OF NAPLES", font=font(SERIF, 32*R), fill=(40, 30, 22))
    d.text((24*R, 52*R), "A.D. 79", font=font(MONO, 13*R), fill=(80, 66, 52))
    d.text((40*R, 330*R), "BAY OF NAPLES", font=font(MONO, 14*R), fill=(70, 86, 90))
    d.line([(600*R, 30*R), (600*R, 80*R)], fill=(40, 30, 22), width=int(3*R)); d.text((592*R, 84*R), "N", font=font(MONO, 18*R), fill=(40, 30, 22))
    d.line([(470*R, 470*R), (470*R + (10/ ( (BAY_BOX[1]-BAY_BOX[0])*84.6)) * 640*R, 470*R)], fill=(40, 30, 22), width=int(3*R))
    d.text((470*R, 476*R), "10 KM", font=font(MONO, 12*R), fill=(40, 30, 22))
    return shadowed(p), (wworld, hworld)

''')

# ---------------------------------------------------------------- diagrams: strata (pumice / surges) and the plaster-cast mould
rep_block("    if kind == 'neck':", "    paper = Image.new(\"RGBA\", (pw + int(28*R)",
'''    lab = (150, 170, 175); fs = font(MONO, 17*R)
    if kind in ('strata', 'strata2'):
        d.text((24*R, 20*R), "POMPEII - CROSS-SECTION (SCHEMATIC)", font=font(MONO, 18*R), fill=lab)
        g0 = 400                                                                    # Roman ground level
        d.rectangle([40*R, g0*R, 520*R, 430*R], fill=(70, 60, 50)); d.text((50*R, 404*R), "ROMAN STREET, A.D. 79", font=fs, fill=(220, 210, 190))
        d.rectangle([330*R, 150*R, 352*R, g0*R], fill=(120, 110, 100)); d.rectangle([430*R, 150*R, 452*R, g0*R], fill=(120, 110, 100))   # house walls
        top = 250                                                                   # ~2.8 m of pumice
        for yy in range(top, g0, 9):
            for xx in range(44, 520, 11):
                if 330 <= xx <= 352 or 430 <= xx <= 452: continue
                r_ = 2.2 + ((xx*7 + yy*3) % 5)*.5
                c = (214, 210, 200) if yy > 330 else (168, 164, 160)                # white pumice below, grey above
                d.ellipse([(xx - r_)*R, (yy - r_)*R, (xx + r_)*R, (yy + r_)*R], fill=c)
        d.text((60*R, (top + 20)*R), "LAYER 1: PUMICE FALL", font=fs, fill=(255, 255, 255)); d.text((60*R, (top + 44)*R), "~2.8 M, 18 HOURS", font=fs, fill=(230, 230, 230))
        if kind == 'strata2':
            cols = [(150, 92, 60), (130, 80, 52), (160, 100, 66), (120, 74, 48)]
            yy = top
            for i, c in enumerate(cols):
                h_ = 26 + 4*i; d.rectangle([40*R, (yy - h_)*R, 520*R, yy*R], fill=c); yy -= h_
            d.text((60*R, (yy + 6)*R), "SURGES AND FLOWS (DAY 2)", font=fs, fill=(255, 236, 220))
            d.line([(30*R, 70*R), (30*R, g0*R)], fill=RED, width=int(4*R)); d.text((36*R, 76*R), "4-6 M", font=font(MONO, 22*R), fill=RED)
        else:
            d.line([(30*R, top*R), (30*R, g0*R)], fill=RED, width=int(4*R)); d.text((36*R, (top - 30)*R), "~2.8 M", font=font(MONO, 22*R), fill=RED)
    elif kind == 'mold':
        d.text((24*R, 20*R), "FIORELLI'S METHOD (SCHEMATIC)", font=font(MONO, 18*R), fill=lab)
        d.rectangle([40*R, 70*R, 520*R, 400*R], fill=(96, 92, 86))                  # hardened ash
        for k_ in range(140):
            xx, yy = 46 + (k_*37) % 470, 76 + (k_*53) % 318; d.point((xx*R, yy*R), fill=(120, 116, 110))
        body = [(130, 300), (170, 250), (260, 238), (330, 250), (400, 236), (450, 262), (430, 300), (330, 310), (250, 318), (170, 322)]
        d.polygon([(x*R, y*R) for x, y in body], fill=(26, 30, 34), outline=(190, 210, 215))
        d.ellipse([400*R, 228*R, 460*R, 284*R], fill=(26, 30, 34), outline=(190, 210, 215), width=int(2*R))
        d.line([(300*R, 70*R), (300*R, 240*R)], fill=(236, 232, 220), width=int(8*R))     # plaster poured in through a hole
        d.text((310*R, 110*R), "PLASTER IN", font=fs, fill=(236, 232, 220))
        d.text((150*R, 330*R), "HOLLOW LEFT BY THE BODY", font=fs, fill=(190, 210, 215))
        d.text((60*R, 420*R), "ASH HARDENS - BODY DECAYS - VOID REMAINS", font=fs, fill=lab)
''')

# ---------------------------------------------------------------- word pop-ups
rep_block("NAMES = {", "ORD = {",
"""NAMES = {'pompeii': 'POMPEII', 'herculaneum': 'HERCULANEUM', 'vesuvius': 'VESUVIUS', 'pliny': 'PLINY', 'misenum': 'MISENUM',
         'stabiae': 'STABIAE', 'pomponianus': 'POMPONIANUS', 'rectina': 'RECTINA', 'strabo': 'STRABO', 'seneca': 'SENECA',
         'fiorelli': 'GIUSEPPE FIORELLI', 'titus': 'TITUS', 'campania': 'CAMPANIA', 'naples': 'NAPLES', 'florence': 'FLORENCE',
         'harvard': 'HARVARD', 'october': 'OCTOBER', 'august': 'AUGUST'}
KEYWORDS = {'earthquake', 'tremors', 'pumice', 'ash', 'column', 'collapse', 'flow', 'surge', 'heat', 'dna', 'casts', 'plaster',
            'bones', 'teeth', 'skeletons', 'glass', 'brain', 'scrolls', 'charcoal', 'pomegranates', 'wine', 'coin', 'darkness',
            'eyewitness', 'rescue', 'fleet', 'warships', 'pillows', 'sulfur', 'evidence', 'stories', 'escaped', 'roofs', 'mother', 'child',
            'sisters', 'graffito', 'bread', 'buried', 'hollows', 'molds', 'gods', 'scanner'}
""")
rep("ORD = {'third': 'III', 'fourth': 'IV', 'second': 'II', 'ninth': 'IX', 'great': 'THE GREAT'}", "ORD = {}")

# ---------------------------------------------------------------- year card: built-in animated time strip (no Manim)
rep("""            ob = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
            fdir = os.path.join(B, 'tl', str(o.get('tl', -1))); n = len(os.listdir(fdir)) if os.path.isdir(fdir) else 0
            k_ = int((t - t0)*FPS)
            if k_ < n:
                png = cv2.imread(os.path.join(fdir, f'f{k_ + 1:04d}.png'), cv2.IMREAD_UNCHANGED)
                if png is not None:
                    aa = png[..., 3:4].astype(np.float32)/255
                    ob = np.clip(ob*(1 - aa) + png[..., :3]*aa, 0, 255).astype(np.uint8)
            return ob""",
"""            time_strip(d, o, t - t0, al)
            return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)""")
rep("def text_center(d, y, s, f, fill):",
'''CLOCK = [('DAY 1 - 1 PM', 13, '1 PM', 'COLUMN'), ('DAY 1 - 2 PM', 14, '2 PM', 'PUMICE'), ('DAY 2 - 1 AM', 25, '1 AM', 'COLLAPSE'),
         ('DAY 2 - DAWN', 30, 'DAWN', 'DARKNESS'), ('DAY 2 - ABOUT 7 AM', 31, '7 AM', 'SURGE')]
HIST = [('A.D. 62', 62, 'A.D. 62', 'EARTHQUAKE'), ('A.D. 79', 79, 'A.D. 79', 'ERUPTION'), ('AUGUST 24?', 79, 'A.D. 79', 'THE DATE?'),
        ('1748', 1748, '1748', 'DIGGING'), ('1980s', 1982, '1980s', 'SHORELINE'), ('2018', 2018, '2018', 'CHARCOAL'), ('2024', 2024, '2024', 'DNA')]
def time_strip(d, o, lt, al):
    """animated strip under each date card: an eruption clock for the two days, otherwise a broken history axis"""
    y = 820; dim = (150, 160, 150, al); cream = (240, 236, 225, al); fm = font(MONO, 22); fb = font(MONO, 20)
    if o['a'].startswith('DAY'):
        marks = CLOCK; xp = lambda h: 300 + (h - 12) / 20 * 1320
        d.line([(xp(12), y), (xp(32), y)], fill=dim, width=3)
        for h in range(12, 33, 2):
            d.line([(xp(h), y - 8), (xp(h), y + 8)], fill=dim, width=2)
        d.text((xp(12) - 20, y + 60), "DAY 1, NOON", font=fb, fill=dim); d.text((xp(24) - 40, y + 60), "MIDNIGHT", font=fb, fill=dim)
        d.text((xp(32) - 80, y + 60), "DAY 2, 8 AM", font=fb, fill=dim)
        key = o['a']
    else:
        marks = HIST
        def xp(v):
            if v < 200: return 300 + (v - 55) / 30 * 330                          # A.D. 55-85
            if v < 1900: return 790 + (v - 1730) / 140 * 330                      # 1730-1870
            return 1280 + (v - 1975) / 55 * 340                                   # 1975-2030
        for a_, b_ in ((55, 85), (1730, 1870), (1975, 2030)): d.line([(xp(a_), y), (xp(b_), y)], fill=dim, width=3)
        for gx in (720, 1210):
            for k in range(3): d.line([(gx + 14*k, y + 10), (gx + 14*k + 10, y - 10)], fill=dim, width=2)
        key = o['a'] if any(m[0] == o['a'] for m in HIST) else 'A.D. 79'
    idx = [m[0] for m in marks].index(key) if key in [m[0] for m in marks] else 0
    for j, (k_, v, a_, b_) in enumerate(marks):
        if marks is HIST and k_ == 'AUGUST 24?': continue
        x = xp(v); on = j == idx; up = j % 2 == 0
        r_ = 7 if on else 5; d.ellipse([x - r_, y - r_, x + r_, y + r_], fill=cream if on else dim)
        yy = y - 62 if up else y + 18
        d.text((x - fm.getlength(a_)/2, yy), a_, font=fm, fill=cream if on else dim)
        d.text((x - fb.getlength(b_)/2, yy + 26), b_, font=fb, fill=RED + (al,) if on else dim)
    prev = xp(marks[idx - 1][1]) if idx else xp(marks[0][1]) - 120
    u = ease(clamp((lt - .35) / .9)); hx = prev + (xp(marks[idx][1]) - prev) * u
    d.line([(hx, y - 26), (hx, y - 8)], fill=RED + (al,), width=5); d.polygon([(hx - 8, y - 10), (hx + 8, y - 10), (hx, y)], fill=RED + (al,))
    if lt > 1.3:
        rr = 16 * ease(clamp((lt - 1.3) / .3)); x = xp(marks[idx][1]); d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=RED + (al,), width=4)

def text_center(d, y, s, f, fill):''')

# ---------------------------------------------------------------- Roman figures: short hair, knee-length tunic
rep('''    wpoly(d, [(x-34*s, y-230*s), (x+34*s, y-230*s), (x+48*s, y-140*s), (x-40*s, y-140*s)], t, k+1, PAPER, col, int(4*s))   # kilt''',
    '''    wpoly(d, [(x-30*s, y-330*s), (x+30*s, y-330*s), (x+50*s, y-130*s), (x-42*s, y-130*s)], t, k+1, PAPER, col, int(4*s))   # tunic''')
rep('''    wpoly(d, [(x-34*s, y-396*s), (x+16*s, y-398*s), (x+6*s, y-330*s), (x-38*s, y-322*s)], t, k+3, col, col, 2)           # wig''',
    '''    wpoly(d, [(x-30*s, y-396*s), (x+24*s, y-398*s), (x+20*s, y-372*s), (x-32*s, y-364*s)], t, k+3, col, col, 2)           # short hair''')

# ---------------------------------------------------------------- film scenes (silent-film reconstructions)
rep("SCENES = {'strike': sc_strike, 'messengers': sc_messengers, 'trial': sc_trial, 'party': sc_party, 'cache': sc_cache}",
'''def pumice_rain(d, t, k, n=140, CW=2280, top=0, bot=820, speed=520, col=(70, 60, 50)):
    r = np.random.default_rng(k)
    xs, ph, sz = r.uniform(0, CW, n), r.uniform(0, 1, n), r.uniform(3, 8, n)
    for x, p_, z in zip(xs, ph, sz):
        yy = top + ((p_ * (bot - top) + t * speed * (z / 6)) % (bot - top)); xx = x - (yy - top) * .25
        d.ellipse([xx - z, yy - z, xx + z, yy + z], fill=col)

def house(d, x, t, k, w=420, h=360, roof=0.0):
    wpoly(d, [(x, 820), (x, 820 - h), (x + w, 820 - h), (x + w, 820)], t, k, (196, 174, 136), DARK, 5)
    wpoly(d, [(x + w*.38, 820), (x + w*.38, 820 - h*.55), (x + w*.62, 820 - h*.55), (x + w*.62, 820)], t, k + 1, (70, 54, 36), INK, 4)
    sag = 60 * roof
    wpoly(d, [(x - 30, 820 - h), (x + w/2, 820 - h - 90 + sag), (x + w + 30, 820 - h)], t, k + 2, (150, 92, 60), INK, 5)

def sc_flee(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(118, 104, 86))                                     # a dark afternoon sky
    house(d, 120, t, 2000, roof=clamp(lt / 6)); house(d, 1400, t, 2010, 460, 400, roof=clamp((lt - 1) / 5))
    depth = 30 + 40 * clamp(lt / 6)                                                       # pumice piling up in the street
    wpoly(d, [(0, 820), (0, 820 - depth), (CW, 820 - depth * 1.1), (CW, 820)], t, 2020, (184, 178, 168), INK, 3)
    u = ease(lt / 6.5)
    for i in range(3):
        x = 700 + 520 * u + 150 * i
        figure(d, x, 820 - depth + 6, t, 2100 + 50 * i, 1.0 - .08 * i, arm=.9)
        wpoly(d, [(x - 34, 820 - depth - 400), (x + 40, 820 - depth - 404), (x + 44, 820 - depth - 372), (x - 30, 820 - depth - 368)], t, 2130 + i, PAPER, INK, 3)  # cushion held overhead
    pumice_rain(d, t, 2200)
    return ("POMPEII  ·  DAY 1, AFTERNOON", "PUMICE FALLS FOR HOURS; SOME FLEE, SOME SHELTER")

def sc_boathouse(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(120, 106, 90))
    for i in range(5):                                                                    # stone vaults facing the sea
        x = 80 + 300 * i
        wpoly(d, [(x, 820), (x, 360), (x + 260, 360), (x + 260, 820)], t, 2300 + i, (186, 164, 126), DARK, 5)
        d.pieslice([x + 30, 420, x + 230, 620], 180, 360, fill=(60, 46, 32)); d.rectangle([x + 30, 520, x + 230, 820], fill=(60, 46, 32))
        for j in range(2 + i % 2): seated(d, x + 70 + 70 * j, 820, t, 2350 + 10 * i + j, .55, arm=.2, col=(150, 124, 92))
    d.rectangle([1600, 830, CW, 1000], fill=(150, 140, 120)); wline(d, [(1600, 832), (CW, 832)], t, 2390, INK, 4)
    for j in range(3): figure(d, 1640 + 150 * j, 820, t, 2400 + 30 * j, .9, arm=.2)
    g = clamp((lt - 3.2) / 2.5)                                                           # the surge rolls in from the left
    if g > 0:
        wpoly(d, [(-100, 820), (-100, 120), (CW * g * .9, 220), (CW * g, 820)], t, 2450, (200, 196, 186), (120, 110, 100), 4)
    return ("HERCULANEUM  ·  THE SHORE, NIGHT", "THE BOAT SHEDS WHERE MORE THAN 300 PEOPLE SHELTERED")

def sc_darkness(d, t, lt, CW):
    dark = clamp(lt / 4)
    d.rectangle([0, 0, CW, 820], fill=(int(150 - 110 * dark), int(130 - 96 * dark), int(100 - 74 * dark)))
    wpoly(d, [(0, 820), (0, 640), (500, 600), (1200, 650), (CW, 610), (CW, 820)], t, 2500, (150, 130, 100), INK, 4)
    u = ease(lt / 6.5)
    for i, x in enumerate((300, 520, 760, 980)):
        figure(d, x + 700 * u, 820, t, 2510 + 40 * i, .95, arm=.4 + .3 * math.sin(lt * 3 + i))
    woman(d, 1300 + 400 * u, 820, t, 2600, 1.0, arm=.8); figure(d, 1420 + 400 * u, 820, t, 2650, 1.1, arm=.9)     # Pliny leads his mother
    pumice_rain(d, t, 2700, n=220, speed=260, col=(54, 48, 42))
    return ("MISENUM  ·  DAY 2, MORNING", "PLINY AND HIS MOTHER LEAVE THE TOWN IN DARKNESS")

def sc_pliny(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(104, 90, 74))
    d.rectangle([0, 840, CW, 1000], fill=(120, 110, 96))
    for k in range(6):                                                                     # a rough sea
        yy = 860 + 22 * k; wline(d, [(x, yy + 10 * math.sin(x / 60 + lt * 4 + k)) for x in range(0, CW + 60, 60)], t, 2800 + k, DARK, 3)
    for i, x in enumerate((420, 600, 780)):
        figure(d, x + 60 * ease(lt / 4), 820, t, 2900 + 30 * i, 1.0, arm=.95)
        hx = x + 60 * ease(lt / 4)
        wpoly(d, [(hx - 40, 410), (hx + 46, 404), (hx + 48, 440), (hx - 38, 446)], t, 2950 + i, PAPER, INK, 3)        # pillows tied on
    fall = clamp((lt - 3.6) / .8)                                                          # the old admiral collapses
    ax = 1150
    if fall < 1:
        figure(d, ax, 820, t, 3000, 1.12, arm=.3)
    else:
        wpoly(d, [(ax - 220, 790), (ax + 160, 784), (ax + 164, 820), (ax - 218, 822)], t, 3010, PAPER, INK, 4)
        d.ellipse([ax + 150, 770, ax + 210, 826], fill=INK)
    g = clamp((lt - 2.5) / 3)
    if g > 0: d.rectangle([0, 0, CW, int(380 * g)], fill=(176, 120, 70))                    # glow of the flames on the sky
    pumice_rain(d, t, 3050, n=120, speed=400)
    return ("STABIAE  ·  DAY 2, MORNING", "PLINY THE ELDER ON THE SHORE")

def sc_plaster(d, t, lt, CW):
    d.rectangle([0, 0, CW, 820], fill=(176, 160, 130))
    wpoly(d, [(200, 820), (200, 500), (CW - 200, 480), (CW - 200, 820)], t, 3100, (140, 128, 110), INK, 5)   # ash bank
    body = [(700, 760), (760, 700), (900, 690), (1040, 700), (1180, 690), (1260, 720), (1240, 760), (1040, 772), (880, 778), (760, 780)]
    fill_ = clamp((lt - 1.5) / 3)
    col = tuple(int(a + (b - a) * fill_) for a, b in zip((40, 32, 24), (236, 230, 214)))
    wpoly(d, body, t, 3120, col, INK, 4)
    figure(d, 1000, 480, t, 3150, .9, arm=.95)                                             # a workman pours from a bucket
    wpoly(d, [(1080, 230), (1150, 230), (1140, 300), (1090, 300)], t, 3160, MID, INK, 3)
    if 1.0 < lt < 4.8: wline(d, [(1110, 300), (1080, 690)], t, 3170, (240, 236, 220), 10)
    return ("POMPEII  ·  1863", "FIORELLI'S WORKMEN FILL A HOLLOW WITH PLASTER")

SCENES = {'flee': sc_flee, 'boathouse': sc_boathouse, 'darkness': sc_darkness, 'pliny': sc_pliny, 'plaster': sc_plaster}''')

open(P, 'w').write(s)
print('patched')
