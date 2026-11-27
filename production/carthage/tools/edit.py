"""The editor: narration + shot list + images -> a finished, graded, moving documentary.

  python3 tools/edit.py plan                 # build/timeline.json + captions.srt (cuts synced to the narration's sentences)
  python3 tools/edit.py prep [chapters...]   # crop, grade, depth, focus point and detail framings for every image
  python3 tools/edit.py video [chapters...]  # build/parts/<chapter>.mp4, chapters in parallel
  python3 tools/edit.py audio                # build/audio/mix.wav
  python3 tools/edit.py mux NAME [chapters]  # build/NAME.mp4
  python3 tools/edit.py frames CH t1 t2 ...  # test stills (build/test_<ch>_<t>.jpg)

What it does, in the order the master brief asks for:
  * Picture follows narration: every shot starts and ends on a sentence boundary where possible, so the image
    changes when the subject changes. Long holds are split into "beats": a wide framing, then a detail framing found
    automatically (faces, then visual interest), so no picture sits unchanged for more than ~8 s.
  * Motion is chosen per shot, not one preset: push-in to the face or point of interest, pull-back reveals, pans,
    tilts, tracking with depth parallax, crane moves, aerial pushes, scans across documents, rack focus using the depth
    map, handheld for combat. Consecutive shots never repeat the same move.
  * Transitions are chosen per cut: dissolves (quick or slow), dips to black, soft directional wipes into and out of
    graphics, zoom-throughs into detail and map locations, focus pulls on portraits and quotes, smoke/ink reveals at
    night, film-burn on fire scenes, light flashes on impacts, hard cuts inside fast battle sequences.
  * Motion graphics: animated maps and diagrams (tools/gfx.py), animated timelines, counting statistic cards,
    split-screen comparisons, quote cards, lower thirds, chapter cards.
  * Finish: grade per scene, AI video clips upscaled and slowed with frame blending, film grain, vignette, dust in
    lamplit/sunlit scenes, letterbox for the climax chapters.
"""
import os, sys, re, json, glob, math, zlib, subprocess
from concurrent.futures import ProcessPoolExecutor
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build'); PREP = os.path.join(B, 'prep'); PARTS = os.path.join(B, 'parts'); GFX = os.path.join(B, 'gfx')
FONTS = os.path.join(ROOT, '..', 'assets', 'fonts')
FPS, W, H = 30, 1920, 1080
SW, SH = 2304, 1296
LEAD, GAP = 0.6, 1.4
CH_LEAD, CARD = 4.0, 6.0
MAX_HOLD = 8.2
TITLE = ('CARTHAGE MUST BE DESTROYED', "The Fall of Rome's Greatest Rival")
LETTERBOX = ('08_cannae', '16_the_fall')
GRAPHIC = ('map', 'diagram', 'timeline', 'stat', 'split', 'card', 'quote')
SER, ITA, CAP = 'CormorantGaramond.ttf', 'CormorantGaramond-Italic.ttf', 'Cinzel.ttf'

def load(p): return json.load(open(p))
def font(n, s): return ImageFont.truetype(os.path.join(FONTS, n), s)
def ease(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)
def edits():
    p = os.path.join(ROOT, 'edit.json'); return load(p) if os.path.exists(p) else {}
SMALL = {'a', 'an', 'and', 'of', 'the', 'over', 'in', 'on', 'to', 'at', 'for'}
def nice_title(t):
    w = t.lower().split(); cap = lambda x: '-'.join(p[:1].upper() + p[1:] for p in x.split('-'))
    return ' '.join(x if (i and x in SMALL) else cap(x) for i, x in enumerate(w))

# ------------------------------------------------------------------ sources
def src_of(sid):
    for p in (f'gen/z_{sid}.png', f'photos/{sid}.jpg', f'photos/{sid}.png'):
        f = os.path.join(B, p)
        if os.path.exists(f): return f
    return None

REVIEW = load(os.path.join(ROOT, 'review.json')) if os.path.exists(os.path.join(ROOT, 'review.json')) else {}
SKIPPED = []
def review_of(src):
    """QC rule: only images inspected and marked VERIFIED in review.json may appear. Returns the entry or None."""
    r = REVIEW.get(os.path.splitext(os.path.basename(src))[0])
    return r if r and r.get('status') == 'VERIFIED' else None

def window(crop, focus, frac):
    """A tighter framing (frac of the current crop) centred on the marked subject, in full-image coordinates."""
    c = crop or [0, 0, 1, 1]; w, h = (c[2] - c[0]) * frac, (c[3] - c[1]) * frac
    fx, fy = focus
    x0 = min(max(fx - w / 2, c[0]), c[2] - w); y0 = min(max(fy - h / 2, c[1]), c[3] - h)
    return [x0, y0, x0 + w, y0 + h]

# ------------------------------------------------------------------ plan
def choose_move(s, prev):
    """Script move -> concrete camera move, varied by subject, never the same twice in a row."""
    d = s['desc'].lower(); m = s['move']; k = s['kind']
    if k in ('map', 'diagram'): return 'gfx'
    if k in ('timeline', 'stat', 'quote', 'card'): return 'drift'
    if k == 'split': return 'split'
    table = {'slow push': 'push', 'push': 'push', 'pull': 'pull', 'slow pull': 'pull', 'slow pan': 'pan', 'pan': 'pan', 'track': 'track',
             'crane-up': 'crane-up', 'crane-down': 'crane-down', 'handheld': 'handheld', 'drift': 'drift', 'static': 'breathe', 'focus': 'focus',
             'scan': 'scan', 'reveal': 'pull', 'aerial': 'aerial', 'slow orbit': 'track'}
    mv = table.get(m, 'push')
    if k == 'photo':
        if re.search(r'inscription|manuscript|stele|relief|tablet', d): mv = 'scan' if mv in ('push', 'breathe') else mv
        elif re.search(r'painting|turner|tiepolo|continence|guercino', d): mv = 'pan' if (mv == 'push' and len(d) % 2) else mv
        elif re.search(r'aerial|panorama|today|ruins|ports|hill', d) and mv == 'push': mv = 'aerial' if 'aerial' in d else 'pull'
    if s['size'] == 'EWS' and mv == 'push': mv = 'aerial'
    if s['size'] == 'CU' and mv == 'breathe': mv = 'focus'
    if re.search(r'\b(army|armies|fleet|battlefield|plain)\b', d) and s['size'] in ('WS', 'EWS') and mv in ('push', 'breathe'): mv = 'pull'
    alt = {'push': 'pull', 'pull': 'pan', 'pan': 'tilt', 'tilt': 'push', 'track': 'drift', 'aerial': 'crane-up', 'focus': 'push', 'breathe': 'focus',
           'scan': 'push', 'handheld': 'track', 'crane-up': 'pan', 'crane-down': 'pan', 'drift': 'push'}
    if mv == prev: mv = alt.get(mv, 'drift')
    return mv

def choose_trans(prev, cur, para_start, chapter_start):
    """Incoming transition for `cur` given the previous shot."""
    if prev is None or chapter_start: return ('dip', 1.2)
    pk, ck, g = prev['kind'], cur['kind'], cur['grade']; d = cur.get('desc', '').lower()
    if cur.get('beat'): return ('zoom', 0.8) if cur['beat'] == 1 and cur['move'] == 'push' else ('dissolve', 0.9) if cur['beat'] % 2 else ('focus', 0.9)
    if ck == 'detail': return ('zoom', 0.8)
    if ck in ('map', 'diagram', 'timeline') or pk in ('map', 'diagram', 'timeline'): return ('wipe', 1.0)
    if ck in ('quote', 'card') or pk in ('quote', 'card'): return ('focus', 1.0)
    if ck == 'stat': return ('focus', 0.8)
    if ck == 'split': return ('wipe', 0.9)
    if g == 'fire' and prev['grade'] == 'fire': return ('burn', 1.1)
    if re.search(r'\b(charg|ramm|crash|smash|burst|storm)', d) and cur['move'] == 'handheld': return ('flash', 0.45)
    if g in ('steel',) and cur['move'] == 'handheld' and prev['move'] == 'handheld': return ('cut', 0.0)
    if g in ('night', 'ash', 'fire', 'snow'): return ('smoke', 1.2)
    if para_start: return ('dissolve', 1.0)
    if g in ('dawn', 'candle') and cur['size'] in ('CU', 'ECU'): return ('focus', 0.9)
    return ('dissolve', 0.7)

def plan(_=None):
    shots = load(os.path.join(ROOT, 'shots.json')); ed = edits()
    narr = {os.path.basename(f)[:-5]: load(f) for f in glob.glob(os.path.join(B, 'narration', '*.json'))}
    order = sorted({s['chapter'] for s in shots})
    tl, caps, t = [], [], 0.0; last_src = None; prev = None; prev_move = None; prev_img = None
    for ch in order:
        n = narr[ch]; title = n['title']; ch_start = True
        if not ch.startswith('00'):
            num, name = title.split(':', 1)
            tl.append({'type': 'card', 'start': t, 'dur': CARD, 'line1': num.strip(), 'line2': name.strip(), 'chapter': ch}); t += CARD - 0.4
        for pi, para in enumerate(n['paras']):
            lead = CH_LEAD if pi == 0 and not ch.startswith('00') else LEAD
            seg = lead + para['dur'] + GAP
            ps = [dict(s) for s in shots if s['chapter'] == ch and s['para'] == pi and not ed.get(s['id'], {}).get('skip')]
            keep = []
            for s in ps:
                o = ed.get(s['id'], {})
                if s['kind'] in ('still', 'vid', 'photo'):
                    s['src'] = os.path.join(ROOT, o['src']) if 'src' in o else src_of(s['id'])
                    if not s['src']: SKIPPED.append((s['id'], 'missing image')); continue
                    rv = review_of(s['src'])
                    if not rv: SKIPPED.append((s['id'], 'not verified: ' + REVIEW.get(os.path.splitext(os.path.basename(s['src']))[0], {}).get('note', 'not reviewed'))); continue
                    s['crop'] = rv.get('crop', o.get('crop')); s['focus'] = rv.get('focus', [0.5, 0.45]); s['focus2'] = rv.get('focus2')
                    last_src = (s['src'], s['crop'], s['grade'], s['focus'])
                elif s['kind'] == 'detail':
                    par = next((x for x in keep if x['id'] == s['parent']), None)
                    if not par: continue
                    c0 = par.get('crop') or [0, 0, 1, 1]; c = s['crop']
                    s['src'] = par['src']; s['crop'] = [c0[0] + c[0] * (c0[2] - c0[0]), c0[1] + c[1] * (c0[3] - c0[1]), c0[0] + c[2] * (c0[2] - c0[0]), c0[1] + c[3] * (c0[3] - c0[1])]
                    s['focus'] = [(s['crop'][0] + s['crop'][2]) / 2, (s['crop'][1] + s['crop'][3]) / 2]
                elif s['kind'] in ('quote', 'stat'):
                    if not last_src: continue
                    s['src'], s['crop'], s['bg_grade'], _ = last_src
                elif s['kind'] == 'split':
                    for k, side in enumerate(s['sides']):
                        side['src'] = src_of(side['z']) if side.get('z') else src_of(s['id'] + 'ab'[k])
                        side['focus'] = (review_of(side['src']) or {}).get('focus', [0.5, 0.4]) if side['src'] else None
                    if not all(x['src'] and review_of(x['src']) for x in s['sides']): SKIPPED.append((s['id'], 'split side missing or not verified')); continue
                keep.append(s)
            if not keep:
                if not last_src: raise SystemExit(f'{ch} para {pi}: nothing to show')
                keep = [{'id': f'{ch[:2]}-{pi:02d}-x', 'chapter': ch, 'para': pi, 'kind': 'still', 'size': 'WS', 'move': 'drift', 'grade': last_src[2],
                         'refs': [], 'desc': '', 'src': last_src[0], 'crop': window(last_src[1], last_src[3], 0.8), 'focus': last_src[3]}]
                SKIPPED.append((f'{ch[:2]}-{pi:02d}', 'paragraph had no verified picture: reused the previous one, reframed on its subject'))
            # cut points: proportional, then snapped to sentence boundaries
            wts = [1.35 if s['kind'] in GRAPHIC else 0.8 if s['kind'] == 'detail' else 1.0 for s in keep]
            bounds = [lead + x['end'] + 0.12 for x in para['sentences'][:-1]]
            cuts, acc = [], 0.0
            for w_ in wts[:-1]:
                acc += w_; raw = seg * acc / sum(wts)
                near = min(bounds, key=lambda b: abs(b - raw)) if bounds else raw
                c = near if abs(near - raw) < 2.2 else raw
                lo = (cuts[-1] if cuts else 0) + 2.6
                cuts.append(max(c, lo))
            cuts = [c for c in cuts if c < seg - 2.4] if cuts else []
            if len(cuts) < len(keep) - 1:   # too many shots for a short paragraph: fall back to even spacing
                cuts = [seg * (i + 1) / len(keep) for i in range(len(keep) - 1)]
            edges = [0.0] + cuts + [seg]
            for k, s in enumerate(keep):
                st, du = t + edges[k], edges[k + 1] - edges[k]
                clip = os.path.join(B, 'clips', s['id'] + '.mp4')
                beats = []
                def detail_px(src, crop, frac=0.6):   # source pixels across the tightest detail framing
                    try: w0 = Image.open(src).size[0]
                    except Exception: return 0
                    c = crop or [0, 0, 1, 1]; return w0 * (c[2] - c[0]) * frac
                if s['kind'] in ('still', 'vid', 'photo', 'detail') and du > MAX_HOLD and not (not (s['kind'] == 'vid' and os.path.exists(clip)) and s.get('src') and detail_px(s['src'], s.get('crop')) < 900):
                    if os.path.exists(clip) and s['kind'] == 'vid':
                        first = min(du - 2.6, 5.6); beats = [first] + [(du - first) / max(1, math.ceil((du - first) / MAX_HOLD))] * max(1, math.ceil((du - first) / MAX_HOLD))
                    else:
                        nb = min(4, math.ceil(du / 7.0)); beats = [du / nb] * nb
                elif s['kind'] in GRAPHIC and du > 15.5 and prev_img and detail_px(prev_img[0], prev_img[1], 0.7) >= 900:
                    beats = [12.5, du - 12.5]       # graphic, then a slow detail reprise of the last picture
                else: beats = [du]
                bt = st
                for bi, bd in enumerate(beats):
                    if bi and s['kind'] in GRAPHIC:
                        it = {'type': 'shot', 'id': s['id'] + '#r', 'sid': s['id'], 'chapter': ch, 'para': pi, 'start': round(bt, 3), 'dur': round(bd, 3),
                              'kind': 'still', 'size': 'CU', 'grade': prev_img[2], 'desc': '', 'beat': 1, 'src': prev_img[0], 'crop': window(prev_img[1], prev_img[3], 0.7),
                              'focus': prev_img[3], 'move': 'drift'}
                        it['tr'] = list(choose_trans(prev, it, False, False)); tl.append(it); prev = it; prev_move = 'drift'; bt += bd; continue
                    it = {'type': 'shot', 'id': s['id'] + (f'#{bi}' if bi else ''), 'sid': s['id'], 'chapter': ch, 'para': pi, 'start': round(bt, 3), 'dur': round(bd, 3),
                          'kind': s['kind'], 'size': s['size'], 'grade': s['grade'], 'desc': s['desc'], 'beat': bi}
                    for key in ('src', 'crop', 'quote', 'attrib', 'sides', 'bg_grade', 'focus'):
                        if s.get(key) is not None: it[key] = s[key]
                    if bi and s.get('focus'):
                        f = s['focus2'] if (bi == 2 and s.get('focus2')) else s['focus']
                        it['crop'] = window(s.get('crop'), f, [0.82, 0.66, 0.74, 0.6][bi % 4]); it['focus'] = f
                    if bi == 0 and os.path.exists(clip) and s['kind'] == 'vid': it['clip'] = clip
                    if bi == 0 and s.get('lt'): it['lt'] = s['lt']
                    it['move'] = choose_move(dict(s, move=s['move'] if bi == 0 else ['push', 'drift', 'pull', 'tilt'][(bi - 1 + zlib.crc32(s['id'].encode())) % 4]), prev_move)
                    tr = choose_trans(prev, it, k == 0 and bi == 0, ch_start)
                    if prev is not None and tr[0] == prev['tr'][0] and tr[0] in ('burn', 'smoke', 'focus', 'flash') and it['kind'] not in GRAPHIC:
                        tr = ('dissolve', 0.8)        # never the same effect twice in a row
                    it['tr'] = list(tr); ch_start = False
                    tl.append(it); prev = it; prev_move = it['move']; bt += bd
                    if it['kind'] in ('still', 'vid', 'photo'): prev_img = (it['src'], s.get('crop'), it['grade'], s.get('focus', [0.5, 0.45]))
            tl.append({'type': 'voice', 'start': round(t + lead, 3), 'wav': os.path.join(ROOT, para['wav']), 'chapter': ch})
            for sent in para['sentences']: caps.append((t + lead + sent['start'], t + lead + sent['end'], sent['text']))
            t += seg
        if ch.startswith('00'):
            tl.append({'type': 'title', 'start': t, 'dur': 7.5, 'chapter': ch}); t += 7.5; prev = None
    json.dump({'duration': t, 'items': tl}, open(os.path.join(B, 'timeline.json'), 'w'), indent=1)
    with open(os.path.join(B, 'captions.srt'), 'w') as f:
        def ts(x): h, r = divmod(x, 3600); m, s = divmod(r, 60); return f'{int(h):02d}:{int(m):02d}:{s:06.3f}'.replace('.', ',')
        for i, (a, b_, tx) in enumerate(caps, 1): f.write(f'{i}\n{ts(a)} --> {ts(b_)}\n{tx}\n\n')
    sh = [x for x in tl if x['type'] == 'shot']
    json.dump(SKIPPED, open(os.path.join(B, 'skipped.json'), 'w'), indent=0); json.dump(caps, open(os.path.join(B, 'captions.json'), 'w'))
    print(f'skipped shots: {len(SKIPPED)} (build/skipped.json)')
    print(f'timeline {t/60:.1f} min, {len(sh)} shots, mean {np.mean([x["dur"] for x in sh]):.1f}s, max {max(x["dur"] for x in sh):.1f}s')

# ------------------------------------------------------------------ grading
GRADES = {  # (rgb gain, lift, gamma, saturation, contrast)
    'gold': ((1.035, 1.00, 0.94), 0.008, 1.00, 1.00, 1.04), 'candle': ((1.08, 0.97, 0.82), 0.000, 1.06, 0.95, 1.08),
    'steel': ((0.94, 0.99, 1.06), 0.015, 1.00, 0.70, 1.05), 'night': ((0.92, 0.97, 1.10), 0.000, 1.08, 0.85, 1.06),
    'dawn': ((0.93, 0.98, 1.08), 0.020, 1.00, 0.75, 0.98), 'ash': ((1.02, 0.99, 0.94), 0.030, 1.00, 0.55, 0.94),
    'fire': ((1.10, 0.96, 0.80), 0.000, 1.04, 1.00, 1.08), 'snow': ((0.96, 1.00, 1.05), 0.020, 0.98, 0.80, 1.02),
    'neutral': ((1.02, 1.00, 0.97), 0.012, 1.00, 0.92, 1.03), 'map': ((1, 1, 1), 0, 1, 1, 1)}
def grade(a, key):
    gain, lift, gamma, sat, con = GRADES.get(key, GRADES['gold'])
    a = a * np.array(gain, np.float32); lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    a = lum[..., None] + (a - lum[..., None]) * sat; a = (a - 0.5) * con + 0.5
    a = lift + (1 - lift) * np.clip(a, 0, 1); a = np.power(np.clip(a, 0, 1), gamma)
    return np.where(a > 0.8, 0.8 + (a - 0.8) * 0.75, a)

# ------------------------------------------------------------------ prep
_depth = _face = None
def depth_of(img):
    global _depth
    if _depth is None:
        from transformers import pipeline
        _depth = pipeline('depth-estimation', model='/home/user/models/depth', device='cpu')
    d = np.array(_depth(Image.fromarray(img).resize((768, 432)))['depth'], np.float32)
    d = (d - d.min()) / (d.max() - d.min() + 1e-6)
    return cv2.GaussianBlur(cv2.resize(d, (SW, SH)), (0, 0), 6)

def interest(img, dep):
    """Visual-interest map: faces strongest, then detail (edges) on near objects."""
    global _face
    if _face is None:
        try: _face = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
        except Exception: _face = False
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY); small = cv2.resize(g, (SW // 4, SH // 4))
    e = cv2.GaussianBlur(np.abs(cv2.Laplacian(small.astype(np.float32), cv2.CV_32F)), (0, 0), 9)
    e = e / (e.max() + 1e-6) * (0.5 + cv2.resize(dep, (SW // 4, SH // 4)))
    faces = _face.detectMultiScale(small, 1.1, 5, minSize=(18, 18)) if _face else []
    for (x, y, w, h) in faces: e[y:y + h, x:x + w] += 3.0
    yy, xx = np.mgrid[0:e.shape[0], 0:e.shape[1]]; e *= 1 - 0.35 * np.hypot((xx / e.shape[1] - 0.5) * 2, (yy / e.shape[0] - 0.45) * 2)   # mild centre bias
    return e, len(faces) > 0

def best_window(e, frac, avoid=None):
    """16:9 window covering `frac` of the width with the most interest; returns normalised [x0,y0,x1,y1]."""
    h, w = e.shape; ww, wh = int(w * frac), int(h * frac); ii = cv2.integral(e)
    best, bx = -1, (0, 0)
    for y in range(0, h - wh + 1, 4):
        for x in range(0, w - ww + 1, 4):
            s = ii[y + wh, x + ww] - ii[y, x + ww] - ii[y + wh, x] + ii[y, x]
            if avoid is not None:
                cx, cy = (x + ww / 2) / w, (y + wh / 2) / h
                s *= min(1.0, 0.4 + math.hypot(cx - avoid[0], cy - avoid[1]) * 2)
            if s > best: best, bx = s, (x, y)
    return [bx[0] / w, bx[1] / h, (bx[0] + ww) / w, (bx[1] + wh) / h]

def cover(im, w, h, fx=0.5, fy=0.45):
    """Crop to the output aspect, keeping the marked subject (fx, fy) in frame; returns image and the subject's new position."""
    iw, ih = im.size; tr = w / h
    if iw / ih > tr:
        nw = int(ih * tr); x0 = int(min(max(fx * iw - nw / 2, 0), iw - nw)); im = im.crop((x0, 0, x0 + nw, ih)); fx = (fx * iw - x0) / nw
    else:
        nh = int(iw / tr); y0 = int(min(max(fy * ih - nh / 2, 0), ih - nh)); im = im.crop((0, y0, iw, y0 + nh)); fy = (fy * ih - y0) / nh
    return im.resize((w, h), Image.LANCZOS), (fx, fy)

def prep_image(key, src, crop, gkey, mode='normal', size=(SW, SH), focus=None):
    out = os.path.join(PREP, key.replace('#', '_') + '.npz')
    focus = focus or [0.5, 0.45]
    sig = json.dumps([src, crop, gkey, mode, size, focus])
    if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(src):
        try:
            if str(np.load(out)['sig']) == sig: return out
        except Exception: pass
    im = Image.open(src).convert('RGB'); w, h = im.size; fx, fy = focus
    if crop:
        x0, y0, x1, y1 = crop; im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        fx, fy = (fx - x0) / (x1 - x0), (fy - y0) / (y1 - y0)
    srcw = im.size[0]
    im, (fx, fy) = cover(im, *size, min(max(fx, 0), 1), min(max(fy, 0), 1))
    a = np.asarray(im, np.float32) / 255
    a = (np.clip(grade(a, gkey), 0, 1) * 255).astype(np.uint8)
    if mode == 'plate':      # blurred, darkened backdrop for quote and statistic cards
        a = (cv2.GaussianBlur(a, (0, 0), 16).astype(np.float32) * 0.32).astype(np.uint8); d = np.full(a.shape[:2], 0.5, np.float32)
    else:
        d = depth_of(a) if size == (SW, SH) else cv2.resize(depth_of(cv2.resize(a, (SW, SH))), size)
    np.savez_compressed(out, img=a, depth=d.astype(np.float16), target=np.array([fx, fy], np.float32), srcw=srcw, sig=sig)
    return out

def prep_item(it):
    k = it['kind']
    if k in ('still', 'vid', 'photo', 'detail'): prep_image(it['id'], it['src'], it.get('crop'), it['grade'], focus=it.get('focus'))
    elif k in ('quote', 'stat'): prep_image(it['id'], it['src'], it.get('crop'), it.get('bg_grade', 'gold'), 'plate')
    elif k == 'split':
        for j, side in enumerate(it['sides']): prep_image(it['id'] + 'ab'[j], side['src'], None, 'neutral' if 'photos' in side['src'] else it['grade'], size=(SW // 2, SH), focus=side.get('focus'))

def prep(chs):
    os.makedirs(PREP, exist_ok=True)
    items = [x for x in load(os.path.join(B, 'timeline.json'))['items'] if x['type'] == 'shot' and (not chs or x['chapter'] in chs)]
    for it in items: prep_item(it); print('prep', it['id'], flush=True)

# ------------------------------------------------------------------ camera
_U, _V = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
def camera(move, t, seed, tgt):
    """-> zoom, centre offset (dx, dy) in canvas px, parallax (px, py), focal depth or None."""
    e = ease(t); r = np.random.default_rng(seed); side = 1 if r.random() < 0.5 else -1
    if abs(tgt[0] - 0.5) > 0.06: side = 1 if tgt[0] > 0.5 else -1        # move toward the subject, never away from it
    tx, ty = (tgt[0] - 0.5) * SW, (tgt[1] - 0.5) * SH
    lim = lambda z: ((SW - W / z) / 2, (SH - H / z) / 2)
    def toward(z, f): mx, my = lim(z); return (float(np.clip(tx * f, -mx, mx)), float(np.clip(ty * f, -my, my)))
    if move == 'push': z = 1.0 + 0.14 * e; return z, toward(z, 0.55 * e), (side * 14 * e, -6 * e), None
    if move == 'pull': z = 1.16 - 0.15 * e; return z, toward(z, 0.55 * (1 - e) + 0.25 * e), (side * 14 * (1 - e), 6 * e), None
    if move == 'pan': z = 1.06; b = toward(z, 0.35); return z, (b[0] + side * (150 * e - 75), b[1]), (side * 12 * (e - 0.5), 0), None
    if move == 'tilt': return 1.06, (0, side * (90 * e - 45)), (0, side * 10 * (e - 0.5)), None
    if move == 'track': z = 1.07; b = toward(z, 0.3); return z, (b[0] + side * (160 * e - 80), b[1]), (side * 30 * (e - 0.5), 0), None
    if move == 'crane-up': return 1.07 + 0.03 * e, (0, 100 - 200 * e), (0, -26 * (e - 0.5)), None
    if move == 'crane-down': return 1.07, (0, -100 + 200 * e), (0, 26 * (e - 0.5)), None
    if move == 'aerial': z = 1.02 + 0.12 * e; return z, (toward(z, 0.3 * e)[0], 60 - 120 * e), (0, -20 * e), None
    if move == 'scan': return 1.16, (side * (300 * e - 150), (tgt[1] - 0.5) * SH * 0.3), (0, 0), None
    if move == 'focus': z = 1.03 + 0.05 * e; return z, toward(z, 0.2 * e), (side * 6 * e, 0), (0.15 + 0.7 * e) if side > 0 else (0.85 - 0.7 * e)
    if move == 'handheld':
        f = t * 40; return 1.08 + 0.02 * e, (5 * math.sin(f * 1.3) + 3 * math.sin(f * 2.9), 4 * math.sin(f * 1.7 + 1)), (side * 12 * (e - 0.5), 0), None
    if move == 'drift': return 1.04 + 0.03 * e, (side * 30 * math.sin(e * math.pi - math.pi / 2), 15 * math.sin(e * math.pi * 2)), (side * 12 * (e - 0.5), 3), None
    return 1.0 + 0.035 * e, (0, 0), (side * 8 * (e - 0.5), 0), None

def frame_of(img, dep, move, t, seed, tgt, blur=None):
    z, (dx, dy), (px, py), focal = camera(move, t, seed, tgt)
    sh, sw = img.shape[:2]
    x0 = sw / 2 + dx + (_U - W / 2) / z; y0 = sh / 2 + dy + (_V - H / 2) / z
    if dep is not None and (px or py):
        d = cv2.remap(dep, x0, y0, cv2.INTER_LINEAR) - 0.5; x0 = x0 + px * d; y0 = y0 + py * d
    out = cv2.remap(img, x0, y0, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if focal is not None and blur is not None and dep is not None:
        dd = cv2.remap(dep, x0, y0, cv2.INTER_LINEAR); bl = cv2.remap(blur, x0, y0, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        m = np.clip(np.abs(dd - focal) * 3.2 - 0.25, 0, 1)[..., None]
        out = (out * (1 - m) + bl * m).astype(np.uint8)
    return out

def warp(img, z, cx, cy):
    """Zoom z about canvas point (cx, cy) -> W x H frame (graphics)."""
    sh, sw = img.shape[:2]; s = z * W / sw
    M = np.array([[s, 0, W / 2 - cx * s], [0, s, H / 2 - cy * s]], np.float32)
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

# ------------------------------------------------------------------ clips
def load_clip(path, gkey):
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path], capture_output=True, text=True, check=True)
    w, h = map(int, p.stdout.strip().split(','))
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    out = []
    for f in np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3):
        a = np.asarray(cover(Image.fromarray(f), 1152, 648), np.float32) / 255
        out.append((np.clip(grade(a, gkey), 0, 1) * 255).astype(np.uint8))
    return out

def clip_frame(frames, lt, dur):
    n = len(frames); speed = min(1.0, (n / 24) / max(dur, 0.1)); pos = min(lt * dur * 24 * speed, n - 1.001)
    i = int(pos); f = pos - i
    a = frames[i].astype(np.float32) * (1 - f) + frames[min(i + 1, n - 1)].astype(np.float32) * f
    up = cv2.resize(a, (W, H), interpolation=cv2.INTER_CUBIC); blur = cv2.GaussianBlur(up, (0, 0), 1.4)
    out = np.clip(up * 1.45 - blur * 0.45, 0, 255)
    z = 1.0 + 0.04 * lt                                 # a slow push on top of the clip's own motion
    return warp(out.astype(np.uint8), z, W / 2, H / 2)

# ------------------------------------------------------------------ text layers (output resolution)
def wrap(text, fo, maxw, d):
    words, lines, cur = text.split(), [], ''
    for w_ in words:
        t = (cur + ' ' + w_).strip()
        if d.textlength(t, font=fo) > maxw and cur: lines.append(cur); cur = w_
        else: cur = t
    return lines + [cur]

def rgba(): return Image.new('RGBA', (W, H), (0, 0, 0, 0))
def over(base, layer, alpha):
    a = layer[..., 3:4] / 255 * alpha; return base * (1 - a) + layer[..., :3] * a

def card_img(l1, l2, big=False):
    im = Image.new('RGB', (W, H), (8, 7, 6)); d = ImageDraw.Draw(im)
    if big:
        d.text((W / 2, H / 2 - 30), l1, font=font(CAP, 96), fill=(222, 206, 172), anchor='mm')
        d.line([W / 2 - 300, H / 2 + 60, W / 2 + 300, H / 2 + 60], fill=(150, 116, 60), width=2)
        d.text((W / 2, H / 2 + 115), l2, font=font(ITA, 50), fill=(180, 165, 140), anchor='mm')
    else:
        d.text((W / 2, H / 2 - 70), '   '.join(l1.replace('CHAPTER', 'CHAPTER ').split()), font=font(CAP, 34), fill=(170, 140, 90), anchor='mm')
        d.text((W / 2, H / 2 + 20), nice_title(l2), font=font(SER, 96), fill=(226, 212, 182), anchor='mm')
    a = np.asarray(im, np.float32); yy, xx = np.mgrid[0:H, 0:W]; r = np.hypot((xx - W / 2) / W, (yy - H / 2) / H)
    return (a + (np.exp(-r * r * 9) * 16)[..., None] * np.array([1.0, 0.8, 0.55])).clip(0, 255).astype(np.uint8)

def quote_layer(text, attrib):
    im = rgba(); d = ImageDraw.Draw(im); fo = font(ITA, 74 if len(text) < 90 else 62)
    lines = wrap(text, fo, 1350, d); lh = fo.size * 1.22; y0 = H / 2 - (len(lines) * lh) / 2 - 40
    d.text((W / 2, y0 - 70), '“', font=font(SER, 150), fill=(176, 132, 52, 200), anchor='mm')
    for i, ln in enumerate(lines): d.text((W / 2, y0 + i * lh + lh / 2), ln.replace('"', ''), font=fo, fill=(236, 224, 198, 255), anchor='mm')
    ya = y0 + len(lines) * lh + 60; d.line([W / 2 - 60, ya, W / 2 + 60, ya], fill=(176, 132, 52, 230), width=2)
    at = rgba(); ImageDraw.Draw(at).text((W / 2, ya + 48), attrib.upper(), font=font(CAP, 26), fill=(190, 170, 130, 235), anchor='mm')
    return np.asarray(im, np.float32), np.asarray(at, np.float32)

def lt_layer(name, role):
    im = rgba(); d = ImageDraw.Draw(im); x, y = 130, H - 205
    g = Image.new('L', (W, H), 0); ImageDraw.Draw(g).rectangle([0, y - 40, 1000, H], fill=150); g = g.filter(ImageFilter.GaussianBlur(60))
    d.text((x, y), name.upper(), font=font(CAP, 40), fill=(236, 224, 198, 255), anchor='ls')
    d.line([x, y + 18, x + 90, y + 18], fill=(176, 132, 52, 255), width=3)
    d.text((x, y + 66), role, font=font(ITA, 38), fill=(205, 190, 160, 255), anchor='ls')
    t = np.asarray(im, np.float32); out = np.zeros((H, W, 4), np.float32); out[..., :3] = t[..., :3]
    out[..., 3] = np.maximum(np.asarray(g, np.float32) * 0.55, t[..., 3]); return out

NUM = re.compile(r'\d[\d,]*(?!\d|[\d,]*\s*(?:BC|AD|years|days|metres|m\b))')
def stat_draw(text, label, p):
    """Big statistic: numbers count up, the label rises in."""
    im = rgba(); d = ImageDraw.Draw(im); e = ease(p / 0.55)
    shown = NUM.sub(lambda m: f"{int(round(int(m.group().replace(',', '')) * e)):,}", text)
    size = 120 if len(text) < 14 else 84 if len(text) < 30 else 64
    d.text((W / 2, H / 2 - 40), shown, font=font(CAP, size), fill=(236, 214, 160, int(255 * min(1, p * 4))), anchor='mm')
    la = ease((p - 0.2) / 0.25); yo = 30 * (1 - la)
    d.line([W / 2 - 80, H / 2 + 50, W / 2 + 80, H / 2 + 50], fill=(176, 132, 52, int(230 * la)), width=2)
    lines = wrap(label, font(ITA, 46), 1300, d)
    for i, ln in enumerate(lines): d.text((W / 2, H / 2 + 110 + yo + i * 58), ln, font=font(ITA, 46), fill=(214, 200, 172, int(255 * la)), anchor='mm')
    return np.asarray(im, np.float32)

def text_card(desc, sid):
    """Title-style text cards from the script: 'LINE · line · line'. The end card lists credits."""
    if desc.strip().lower() == 'end card':
        parts = ['CARTHAGE MUST BE DESTROYED', 'Script, narration and edit: Ancient World Files', 'Sources: Polybius, Livy, Appian, Plutarch · modern works in the description',
                 'Reconstructions are artistic interpretations · AI-assisted imagery and voice', 'Music: Kevin MacLeod (incompetech.com), CC BY 4.0']
    else: parts = [x.strip() for x in desc.split('·')]
    lays = []; y = H / 2 - (len(parts) - 1) * 62
    for i, ptxt in enumerate(parts):
        im = rgba(); d = ImageDraw.Draw(im)
        if i == 0: fo, col = font(CAP, 88 if len(ptxt) < 24 else 64), ((196, 70, 56, 255) if ptxt == 'MYTH' else (232, 214, 170, 255))
        else: fo, col = font(ITA if i % 2 else SER, 52), (214, 200, 172, 255)
        for j, ln in enumerate(wrap(ptxt, fo, 1500, d)): d.text((W / 2, y + j * 64), ln, font=fo, fill=col, anchor='mm')
        if i == 0: d.line([W / 2 - 120, y + 62, W / 2 + 120, y + 62], fill=(176, 132, 52, 230), width=2); y += 40
        y += 124 if i == 0 else 112
        lays.append(np.asarray(im, np.float32))
    return lays

def parchment(dark=True):
    rng = np.random.default_rng(11); n = rng.normal(0, 1, (SH // 8, SW // 8)).astype(np.float32)
    n = cv2.GaussianBlur(cv2.resize(n, (SW, SH), interpolation=cv2.INTER_CUBIC), (0, 0), 5)
    base = np.array((26, 22, 18) if dark else (226, 212, 178), np.float32)
    a = np.ones((SH, SW, 3), np.float32) * base + n[..., None] * (6 if dark else 8)
    yy, xx = np.mgrid[0:SH, 0:SW]; r = np.hypot((xx - SW / 2) / SW, (yy - SH / 2) / SH)
    a = a + (np.exp(-r * r * 6) * (22 if dark else 0))[..., None] * np.array([1.0, 0.8, 0.55])
    return a.clip(0, 255).astype(np.uint8)

def timeline_spec(desc):
    """Animated timeline on dark parchment: a line draws itself, dates pop in, the current one glows."""
    ents = [x.strip() for x in desc.split(';') if x.strip()]
    n = len(ents); x0, x1, y = 260, SW - 260, SH * 0.55; xs = [x0 + (x1 - x0) * i / max(1, n - 1) for i in range(n)]
    layers = [{'t': 'route', 'pts': [[x0 / SW, y / SH], [x1 / SW, y / SH]], 'col': [176, 132, 52], 'a': [0.02, 0.3], 'w': 4}]
    star = 0
    for i, e in enumerate(ents):
        cur = e.endswith('*'); e = e.rstrip('*'); star = i if cur else star
        date, _, lab = e.partition(':')
        im = Image.new('RGBA', (SW, SH), (0, 0, 0, 0)); d = ImageDraw.Draw(im); up = i % 2 == 0
        r = 16 if cur else 10; col = (240, 196, 110, 255) if cur else (200, 176, 130, 255)
        d.ellipse([xs[i] - r, y - r, xs[i] + r, y + r], fill=col)
        d.line([xs[i], y + (-22 if up else 22), xs[i], y + (-50 if up else 50)], fill=(176, 132, 52, 200), width=2)
        yd = y - 250 if up else y + 110
        d.text((xs[i], yd), date.strip(), font=font(CAP, 84 if cur else 64), fill=col, anchor='mm')
        for j, ln in enumerate(wrap(lab.strip(), font(ITA, 54 if cur else 48), 440, d)):
            d.text((xs[i], yd + 80 + j * 58 - (0 if up else 0), ), ln, font=font(ITA, 54 if cur else 48), fill=(224, 210, 182, 255) if cur else (190, 176, 150, 255), anchor='mm')
        t0 = 0.12 + 0.55 * i / max(1, n - 1)
        layers.append({'t': 'img', 'arr': np.asarray(im), 'a': [t0, t0 + 0.12]})
    layers.append({'t': 'pulse', 'xy': [xs[star] / SW, y / SH], 'col': [240, 196, 110], 'a': [0.75, 1.0]})
    return {'base': parchment(), 'layers': layers, 'focus': [0.5 + (xs[star] / SW - 0.5) * 0.35, 0.52], 'zoom': 1.05}

# ------------------------------------------------------------------ graphics player (maps, diagrams, timelines)
def load_gfx(sid):
    d = os.path.join(GFX, sid); spec = load(os.path.join(d, 'spec.json'))
    spec['base'] = np.asarray(Image.open(os.path.join(d, 'base.png')).convert('RGB'))
    for L in spec['layers']:
        if L['t'] == 'img': L['arr'] = np.asarray(Image.open(os.path.join(d, L['f'])).convert('RGBA'))
    return spec

def prime_layers(spec):
    for L in spec['layers']:
        if L['t'] == 'img' and L.get('fix') and 'full' not in L:
            L['full'] = cv2.resize(L['arr'], (W, H), interpolation=cv2.INTER_AREA).astype(np.float32); continue
        if L['t'] == 'img' and 'bb' not in L:
            al = L['arr'][..., 3]; ys, xs = np.nonzero(al > 2)
            if len(xs) == 0: L['bb'] = None; continue
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; L['bb'] = (y0, y1, x0, x1)
            L['sub'] = L['arr'][y0:y1, x0:x1].astype(np.float32)
        if L['t'] == 'unit' and L.get('label') and 'spr' not in L:
            im = Image.new('RGBA', (600, 70), (0, 0, 0, 0)); ImageDraw.Draw(im).text((300, 35), L['label'], font=font(ITA, 50), fill=(40, 30, 20, 255), anchor='mm', stroke_width=2, stroke_fill=(236, 224, 196, 220))
            L['spr'] = np.asarray(im, np.float32)
    return spec

def interp(k, p):
    if p <= k[0][0]: return k[0][1:]
    for a, b in zip(k, k[1:]):
        if p <= b[0]: f = ease((p - a[0]) / max(1e-6, b[0] - a[0])); return [x + (y - x) * f for x, y in zip(a[1:], b[1:])]
    return k[-1][1:]

def draw_polyline(out, pts, col, prog, w, dash=False):
    pts = np.array(pts, np.float32) * [SW, SH]
    seg = np.hypot(*np.diff(pts, axis=0).T); L = seg.sum(); want = L * prog; acc = 0; poly = [pts[0]]
    for i, s in enumerate(seg):
        if acc + s >= want: poly.append(pts[i] + (pts[i + 1] - pts[i]) * ((want - acc) / max(s, 1e-6))); break
        acc += s; poly.append(pts[i + 1])
    poly = np.array(poly, np.float32)
    if dash:
        dl = np.hypot(*np.diff(poly, axis=0).T); cum = np.concatenate([[0], np.cumsum(dl)]); step = 34
        for s0 in np.arange(0, cum[-1], step * 2):
            a_ = np.interp(s0, cum, np.arange(len(cum))); b_ = np.interp(min(s0 + step, cum[-1]), cum, np.arange(len(cum)))
            pa = poly[int(a_)] + (poly[min(int(a_) + 1, len(poly) - 1)] - poly[int(a_)]) * (a_ % 1)
            pb = poly[int(b_)] + (poly[min(int(b_) + 1, len(poly) - 1)] - poly[int(b_)]) * (b_ % 1)
            cv2.line(out, tuple(map(int, pa)), tuple(map(int, pb)), tuple(int(c) for c in col), w, cv2.LINE_AA)
    else:
        cv2.polylines(out, [poly.astype(np.int32)], False, (40, 28, 18), w + 5, cv2.LINE_AA)
        cv2.polylines(out, [poly.astype(np.int32)], False, tuple(int(c) for c in col), w, cv2.LINE_AA)
    if len(poly) > 1 and prog > 0.02 and not dash:
        (x1, y1), (x0, y0) = poly[-1], poly[-2]; ang = math.atan2(y1 - y0, x1 - x0); Lh = 4 * w
        tri = np.array([(x1 + w * math.cos(ang), y1 + w * math.sin(ang)), (x1 - Lh * math.cos(ang - 0.5), y1 - Lh * math.sin(ang - 0.5)),
                        (x1 - Lh * math.cos(ang + 0.5), y1 - Lh * math.sin(ang + 0.5))], np.int32)
        cv2.fillPoly(out, [tri], tuple(int(c) for c in col), cv2.LINE_AA)

def gfx_frame(spec, p):
    out = spec['base'].astype(np.float32).copy()
    for L in spec['layers']:
        t = L['t']
        if t == 'img':
            a = ease((p - L['a'][0]) / max(1e-6, L['a'][1] - L['a'][0]))
            if a <= 0 or L.get('fix') or L.get('bb') is None: continue
            y0, y1, x0, x1 = L['bb']; s = L['sub']; al = s[..., 3:4] / 255 * a
            out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - al) + s[..., :3] * al
    o8 = out.clip(0, 255).astype(np.uint8)
    for L in spec['layers']:
        t = L['t']
        if t == 'route':
            pr = ease((p - L['a'][0]) / max(1e-6, L['a'][1] - L['a'][0]))
            if pr > 0: draw_polyline(o8, L['pts'], L['col'], pr, int(L.get('w', 9) * SW / 3840 * 1.6), L.get('dash'))
        elif t == 'pulse' and L['a'][0] <= p:
            x, y = L['xy'][0] * SW, L['xy'][1] * SH; ph = ((p - L['a'][0]) * 3) % 1
            ov = o8.copy(); cv2.circle(ov, (int(x), int(y)), int(10 + 60 * ph), tuple(int(c) for c in L['col']), 5, cv2.LINE_AA)
            o8 = cv2.addWeighted(ov, 1 - ph, o8, ph, 0); cv2.circle(o8, (int(x), int(y)), 11, tuple(int(c) for c in L['col']), -1, cv2.LINE_AA)
        elif t == 'unit':
            x, y, w, h, ang = interp(L['k'], p)
            if p < L['k'][0][0] - 0.02: continue
            box = cv2.boxPoints(((x * SW, y * SH), (w * SW, h * SH), ang)).astype(np.int32)
            cv2.fillPoly(o8, [box], tuple(int(c) for c in L['col']), cv2.LINE_AA); cv2.polylines(o8, [box], True, (40, 28, 18), 3, cv2.LINE_AA)
            if L.get('spr') is not None:
                sp = L['spr']; px, py = int(x * SW - 300), int(y * SH - h * SH / 2 - 60)
                if 0 <= px and px + 600 <= SW and 0 <= py and py + 70 <= SH:
                    reg = o8[py:py + 70, px:px + 600].astype(np.float32); al = sp[..., 3:4] / 255
                    o8[py:py + 70, px:px + 600] = (reg * (1 - al) + sp[..., :3] * al).astype(np.uint8)
    z = 1.0 + (spec.get('zoom', 1.1) - 1.0) * ease(p); f = spec.get('focus') or [0.5, 0.5]
    e = ease(p) * 0.6; cx = SW * (0.5 + (f[0] - 0.5) * e); cy = SH * (0.5 + (f[1] - 0.5) * e)
    hw, hh = SW / (2 * z), SH / (2 * z)               # visible half-size in canvas pixels
    cx = min(max(cx, hw), SW - hw); cy = min(max(cy, hh), SH - hh)
    out = warp(o8, z, cx, cy).astype(np.float32)
    for L in spec['layers']:
        if L['t'] == 'img' and L.get('fix'):
            a = ease((p - L['a'][0]) / max(1e-6, L['a'][1] - L['a'][0]))
            if a > 0: out = over(out, L['full'], a)
    return out

# ------------------------------------------------------------------ transitions
_noise = {}
def noise(seed, scale):
    k = (seed % 7, scale)
    if k not in _noise:
        r = np.random.default_rng(seed % 7); n = r.random((H // scale + 2, W // scale + 2)).astype(np.float32)
        n = cv2.GaussianBlur(cv2.resize(n, (W, H), interpolation=cv2.INTER_CUBIC), (0, 0), scale / 3)
        _noise[k] = (n - n.min()) / (n.max() - n.min())
    return _noise[k]

def transition(A, Bf, p, kind, seed):
    e = ease(p)
    if kind == 'cut': return Bf
    if kind == 'dissolve': return A * (1 - e) + Bf * e
    if kind == 'dip': return A * max(0, 1 - 2 * p) if p < 0.5 else Bf * ease(2 * p - 1)
    if kind == 'flash':
        mix = A * (1 - e) + Bf * e; k = math.sin(math.pi * p) ** 2
        return mix + k * 170 * np.array([1.0, 0.92, 0.78], np.float32)
    if kind == 'wipe':
        side = 1 if seed % 2 else -1; x = (_U / W if side > 0 else 1 - _U / W) + (_V / H - 0.5) * 0.12
        m = np.clip((e * 1.35 - x) / 0.22 + 0.5, 0, 1)[..., None]; return A * (1 - m) + Bf * m
    if kind in ('smoke', 'burn'):
        side = 1 if seed % 2 else -1; gx = (_U / W if side > 0 else 1 - _U / W)
        n = 0.55 * noise(seed, 160 if kind == 'smoke' else 120) + 0.45 * gx; m = np.clip((e * 1.5 - n) / 0.22, 0, 1)
        out = A * (1 - m[..., None]) + Bf * m[..., None]
        if kind == 'burn':
            edge = np.exp(-((e * 1.5 - n - 0.02) / 0.05) ** 2) * math.sin(math.pi * p)
            edge = cv2.GaussianBlur(edge.astype(np.float32), (0, 0), 6)
            out = out + edge[..., None] * np.array([255, 150, 60], np.float32) * 0.55
        return out
    if kind == 'focus':
        s1, s2 = 1 + 22 * e, 1 + 22 * (1 - e)
        a = cv2.GaussianBlur(A, (0, 0), s1) if s1 > 1.5 else A; b = cv2.GaussianBlur(Bf, (0, 0), s2) if s2 > 1.5 else Bf
        return a * (1 - e) + b * e
    if kind == 'zoom':
        za = 1 + 0.35 * e; a = warp(A.clip(0, 255).astype(np.uint8), za, W / 2, H / 2).astype(np.float32)
        if e > 0.05: a = cv2.GaussianBlur(a, (0, 0), 1 + 8 * e)
        zb = 0.88 + 0.12 * e
        b = Bf if zb >= 0.999 else cv2.warpAffine(Bf, np.array([[zb, 0, W / 2 * (1 - zb)], [0, zb, H / 2 * (1 - zb)]], np.float32), (W, H), borderMode=cv2.BORDER_REFLECT)
        return a * (1 - e) + b * e
    return A * (1 - e) + Bf * e

# ------------------------------------------------------------------ atmosphere and finish
class Dust:
    def __init__(self, seed, n=55):
        r = np.random.default_rng(seed); self.p = r.uniform(0, 1, (n, 2)) * [W, H]; self.v = r.normal(0, 1, (n, 2)) * [6, 4] + [3, -2]
        self.s = r.uniform(1.2, 3.5, n); self.b = r.uniform(0.3, 1.0, n); self.ph = r.uniform(0, 6.3, n)
    def draw(self, a, t, strength, col=(255, 236, 200), rise=False):
        for (x, y), (vx, vy), s, b, ph in zip(self.p, self.v, self.s, self.b, self.ph):
            if rise: vy = -abs(vy) * 9 - 25
            cx = (x + vx * t + 14 * math.sin(t * 0.4 + ph)) % W; cy = (y + vy * t + 10 * math.cos(t * 0.33 + ph)) % H
            R = int(s * 3); x0, y0 = int(cx) - R, int(cy) - R
            if x0 < 0 or y0 < 0 or x0 + 2 * R + 1 > W or y0 + 2 * R + 1 > H: continue
            yy, xx = np.mgrid[-R:R + 1, -R:R + 1]
            spr = np.exp(-(xx * xx + yy * yy) / (2 * s * s)) * b * strength * (0.6 + 0.4 * math.sin(t * 1.7 + ph))
            a[y0:y0 + 2 * R + 1, x0:x0 + 2 * R + 1] += spr[..., None] * np.array(col, np.float32)
        return a

def leak(a, p):
    cx = -0.3 * W + 1.6 * W * p; g = np.exp(-((_U - cx) / (W * 0.28)) ** 2 - ((_V - H * 0.35) / (H * 0.9)) ** 2)
    return a + (g * math.sin(math.pi * p) * 150)[..., None] * np.array([1.0, 0.62, 0.30], np.float32)

_grain = None
def finish(f, t, gk, lb=0.0):
    global _grain
    if _grain is None:
        r = np.random.default_rng(3); _grain = [cv2.GaussianBlur(r.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7) for _ in range(6)]
        rr = np.hypot((_U - W / 2) / (W / 2), (_V - H / 2) / (H / 2)); finish.vig = (1 - 0.32 * np.clip(rr - 0.45, 0, 1) ** 1.6)[..., None].astype(np.float32)
    a = f.astype(np.float32)
    if gk in ('candle', 'night', 'fire'): a *= 1 + 0.025 * math.sin(t * 7.1) * math.sin(t * 2.3 + 1)
    a = a * finish.vig + _grain[int(t * FPS) % 6][..., None] * (5.5 if gk != 'map' else 2.5)
    if lb > 0: bar = int(138 * lb); a[:bar] = 0; a[H - bar:] = 0
    return np.clip(a, 0, 255).astype(np.uint8)

# ------------------------------------------------------------------ render
class Shot:
    """Everything needed to draw one timeline item at any moment."""
    def __init__(self, it):
        self.it = it; k = it['kind']; self.seed = zlib.crc32(it['id'].encode())
        self.clip = self.gfx = self.ql = self.lt = self.cards = None
        if k in ('still', 'vid', 'photo', 'detail', 'quote', 'stat'):
            z = np.load(os.path.join(PREP, it['id'].replace('#', '_') + '.npz'))
            self.img = z['img']; self.dep = z['depth'].astype(np.float32) if k not in ('quote', 'stat') else None; self.tgt = list(z['target'])
            self.blur = cv2.GaussianBlur(self.img, (0, 0), 7) if it['move'] == 'focus' else None
        if it.get('clip'): self.clip = load_clip(it['clip'], it['grade'])
        if k in ('map', 'diagram'): self.gfx = prime_layers(load_gfx(it['sid']))
        if k == 'timeline': self.gfx = prime_layers(timeline_spec(it['desc']))
        if k == 'quote': self.ql = quote_layer(it['quote'], it['attrib'])
        if k == 'stat': self.stat = [x.strip() for x in it['desc'].split('::')]
        if k == 'card': self.cards = text_card(it['desc'], it['id'])
        if k == 'split':
            self.sides = []
            for j in range(2):
                z = np.load(os.path.join(PREP, it['id'] + 'ab'[j] + '.npz')); self.sides.append((z['img'], list(z['target'])))
            im = rgba(); d = ImageDraw.Draw(im); g = Image.new('L', (W, H), 0); ImageDraw.Draw(g).rectangle([0, H - 230, W, H], fill=170); g = g.filter(ImageFilter.GaussianBlur(50))
            for j, sd in enumerate(it['sides']):
                for li, ln in enumerate(wrap(sd['label'], font(ITA, 44), 820, d)): d.text((W / 4 + j * W / 2, H - 120 + li * 52), ln, font=font(ITA, 44), fill=(236, 224, 198, 255), anchor='mm')
            t = np.asarray(im, np.float32); self.split_lab = t.copy(); self.split_lab[..., 3] = np.maximum(np.asarray(g, np.float32) * 0.6, t[..., 3])
        if it.get('lt'): self.lt = lt_layer(*it['lt'])

    def frame(self, lt, t_abs):
        it = self.it; k = it['kind']
        if self.clip is not None: fr = clip_frame(self.clip, lt, it['dur']).astype(np.float32)
        elif self.gfx is not None: fr = gfx_frame(self.gfx, lt).astype(np.float32)
        elif k == 'split':
            fr = np.zeros((H, W, 3), np.float32); hw = W // 2
            for j, (img, tgt) in enumerate(self.sides):
                z = 1.0 + 0.06 * ease(lt); sc = z * hw / img.shape[1]; cx, cy = img.shape[1] / 2 + (tgt[0] - 0.5) * img.shape[1] * 0.2 * ease(lt), img.shape[0] / 2
                half = cv2.warpAffine(img, np.array([[sc, 0, hw / 2 - cx * sc], [0, sc, H / 2 - cy * sc]], np.float32), (hw, H), borderMode=cv2.BORDER_REFLECT)
                slide = int((1 - ease(lt / 0.18)) * hw * (1 if j else -1))
                x0 = j * hw + slide; a, b_ = max(0, x0), min(W, x0 + hw)
                if b_ > a: fr[:, a:b_] = half[:, a - x0:b_ - x0]
            fr[:, hw - 2:hw + 2] = (176, 132, 52); fr = over(fr, self.split_lab, ease((lt - 0.2) / 0.15))
        elif k == 'card':
            fr = np.zeros((H, W, 3), np.float32) + 8
            for i, L in enumerate(self.cards): fr = over(fr, L, ease((lt - 0.08 - 0.12 * i) / 0.12))
        else:
            fr = frame_of(self.img, self.dep, it['move'], lt, self.seed, self.tgt, self.blur).astype(np.float32)
        if k == 'quote':
            q, at = self.ql; qa = ease((lt - 0.06) / 0.14); fr = over(fr, q, qa); fr = over(fr, at, ease((lt - 0.3) / 0.12))
        if k == 'stat': fr = over(fr, stat_draw(self.stat[0], self.stat[1] if len(self.stat) > 1 else '', lt), 1.0)
        if self.lt is not None:
            la = min(ease((t_abs - it['start'] - 1.0) / 0.6), ease((it['start'] + 6.5 - t_abs) / 0.6))
            if la > 0: fr = over(fr, self.lt, la)
        return fr

def render_chapter(ch, only=None):
    data = load(os.path.join(B, 'timeline.json'))
    items = [x for x in data['items'] if x.get('chapter') == ch and x['type'] in ('shot', 'card', 'title')]
    t0 = min(x['start'] for x in items)
    nxt = [x['start'] for x in data['items'] if x['type'] in ('shot', 'card') and x['start'] > t0 and x.get('chapter') != ch]
    t_end = min(nxt) if nxt else data['duration']
    for x in items: x['end'] = x['start'] + x['dur']
    shots = [x for x in items if x['type'] == 'shot']
    for a, b_ in zip(shots, shots[1:]): a['end'] = max(a['end'], b_['start'] + b_['tr'][1])   # outgoing shot stays under the incoming transition
    if shots: shots[-1]['end'] = max(shots[-1]['end'], t_end)
    cache = {}; dust = Dust(zlib.crc32(ch.encode())); card_it = next((x for x in items if x['type'] == 'card'), None)
    def get(it):
        key = it['id'] if it['type'] == 'shot' else it['type']
        if key not in cache:
            for old in [k_ for k_ in cache if k_ not in live]: del cache[old]
            cache[key] = Shot(it) if it['type'] == 'shot' else (card_img(*TITLE, True) if it['type'] == 'title' else card_img(it['line1'], it['line2']))
        return cache[key]
    os.makedirs(PARTS, exist_ok=True); out = os.path.join(PARTS, ch + '.mp4'); n = int(round((t_end - t0) * FPS))
    p = None
    if only is None:
        p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                              '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    lb_state = [0.0]
    ks = range(n) if only is None else [int(round((x - t0) * FPS)) for x in only]
    for kf in ks:
        t = t0 + kf / FPS
        act = sorted([x for x in items if x['start'] <= t < x['end']], key=lambda x: x['start'])
        live = {x['id'] if x['type'] == 'shot' else x['type'] for x in act}
        acc, gk = None, 'gold'
        for it in act:
            if it['type'] == 'shot':
                sh = get(it); lt = min(1.0, (t - it['start']) / it['dur']); fr = sh.frame(lt, t)
                kind, L = it['tr']; gk = it['grade'] if it['kind'] not in ('map', 'diagram', 'timeline') else 'map'
                if acc is None or kind == 'cut' or L <= 0: acc = fr
                else:
                    pp = (t - it['start']) / L
                    acc = fr if pp >= 1 else transition(acc, fr, pp, kind, sh.seed)
            else:
                fr = get(it).astype(np.float32); a = min(1.0, (t - it['start']) / 0.9, (it['start'] + it['dur'] - t) / 0.9)
                acc = fr if acc is None else acc * (1 - max(0, a)) + fr * max(0, a); gk = 'map'
        if acc is None: acc = np.zeros((H, W, 3), np.float32)
        if gk in ('candle', 'gold') : acc = dust.draw(acc, t, 0.5 if gk == 'candle' else 0.3)
        if gk == 'fire': acc = dust.draw(acc, t, 0.8, (255, 150, 60), rise=True)
        if gk == 'snow': acc = dust.draw(acc, t, 0.9, (240, 244, 255))
        if card_it and card_it['start'] <= t < card_it['start'] + 1.6: acc = leak(acc, (t - card_it['start']) / 1.6)
        want = 1.0 if ch in LETTERBOX and gk != 'map' and t - t0 > CARD else 0.0   # bars only over pictures, never over graphics
        lb_state[0] = want if only is not None else lb_state[0] + max(-1 / 20, min(1 / 20, want - lb_state[0])); lb = lb_state[0]
        fin = finish(acc, t, gk, lb)
        if p is None: Image.fromarray(fin).save(os.path.join(B, f'test_{ch}_{t:.1f}.jpg'), quality=88); continue
        p.stdin.write(fin.tobytes())
    if p is None: return
    p.stdin.close(); p.wait(); print('rendered', ch, f'{n/FPS:.1f}s', flush=True); return out

def video(chs):
    data = load(os.path.join(B, 'timeline.json'))
    order = sorted({x['chapter'] for x in data['items'] if 'chapter' in x})
    if chs: order = [c for c in order if c in chs]
    with ProcessPoolExecutor(max_workers=min(4, len(order))) as ex: list(ex.map(render_chapter, order))

# ------------------------------------------------------------------ audio
SR = 48000
def read_mono(path):
    import soundfile as sf
    from scipy.signal import resample_poly
    a, sr = sf.read(path, dtype='float32', always_2d=True); a = a.mean(1)
    if sr != SR: a = resample_poly(a, SR, sr).astype(np.float32)
    return a

def audio(_=None):
    import soundfile as sf
    data = load(os.path.join(B, 'timeline.json')); D = data['duration']; n = int(D * SR) + SR
    voice, music, amb, fx = (np.zeros(n, np.float32) for _ in range(4))
    for it in data['items']:
        if it['type'] == 'voice': a = read_mono(it['wav']) * 0.9; i = int(it['start'] * SR); voice[i:i + len(a)] += a[:n - i]
    mp = load(os.path.join(ROOT, 'music.json'))
    for cue in mp['cues']:
        a = read_mono(os.path.join(B, 'music', cue['file'])); s, e = int(cue['start'] * SR), int(min(cue['end'], D) * SR)
        if s >= n or e <= s: continue
        seg = np.tile(a, int((e - s) / len(a)) + 1)[:e - s] * cue.get('gain', 1.0)
        f_in, f_out = min(int(cue.get('fade_in', 2) * SR), len(seg) // 2), min(int(cue.get('fade_out', 3) * SR), len(seg) // 2)
        seg[:f_in] *= np.linspace(0, 1, f_in); seg[len(seg) - f_out:] *= np.linspace(1, 0, f_out); music[s:s + len(seg)] += seg
    for cue in mp.get('sfx', []):
        a = read_mono(os.path.join(B, 'sfx', cue['file'])); s = int(cue['start'] * SR)
        if s >= n or s < 0: continue
        if cue.get('end'):
            e = int(min(cue['end'], D) * SR); a = np.tile(a, int((e - s) / len(a)) + 1)[:e - s]
            f = min(int(1.5 * SR), len(a) // 2); a[:f] *= np.linspace(0, 1, f); a[len(a) - f:] *= np.linspace(1, 0, f)
        (fx if cue.get('hit') else amb)[s:s + len(a)] += a[:n - s] * cue.get('gain', 0.3)
    env = np.convolve(np.abs(voice), np.ones(int(0.3 * SR), np.float32) / int(0.3 * SR), mode='same')
    duck = 1 - 0.72 * np.clip(env / (env.max() * 0.08 + 1e-9), 0, 1); duck = np.convolve(duck, np.ones(SR // 2, np.float32) / (SR // 2), mode='same')
    mix = voice + music * duck * 0.55 + amb * (0.6 + 0.4 * duck) + fx * (0.75 + 0.25 * duck)
    os.makedirs(os.path.join(B, 'audio'), exist_ok=True); raw = os.path.join(B, 'audio', 'raw.wav'); sf.write(raw, np.stack([mix, mix], 1), SR)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', raw, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', str(SR), os.path.join(B, 'audio', 'mix.wav')], check=True)
    print('audio done', f'{D/60:.1f} min')

def mux(name, chs):
    data = load(os.path.join(B, 'timeline.json'))
    order = sorted({x['chapter'] for x in data['items'] if 'chapter' in x})
    if chs: order = [c for c in order if c in chs]
    lst = os.path.join(PARTS, 'list.txt'); open(lst, 'w').write(''.join(f"file '{os.path.join(PARTS, c + '.mp4')}'\n" for c in order))
    audio_in = ['-i', os.path.join(B, 'audio', 'mix.wav')]
    if chs: audio_in = ['-ss', str(min(x['start'] for x in data['items'] if x.get('chapter') in chs))] + audio_in
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, *audio_in, '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k',
                    '-shortest', '-movflags', '+faststart', os.path.join(B, name + '.mp4')], check=True)
    print('wrote', name)

if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'plan': plan()
    elif cmd == 'prep': prep(args)
    elif cmd == 'video': video(args)
    elif cmd == 'audio': audio()
    elif cmd == 'mux': mux(args[0], args[1:])
    elif cmd == 'frames': render_chapter(args[0], [float(x) for x in args[1:]])
