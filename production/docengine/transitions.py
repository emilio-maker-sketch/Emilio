"""Context-aware transitions between the evidence board and full-screen shots.

choose() picks a transition for each cut from what is being cut to and the mood of the chapter, and avoids using the
same transition twice running:
  cut       - hard cut (kinetic type punches in; the start of a sentence that changes subject abruptly)
  dissolve  - soft cross-dissolve (calm/somber chapters, paintings, archival photographs)
  zoomblur  - push-through with radial blur (energetic chapters, entering footage)
  whip      - fast lateral whip pan with motion blur (tense chapters, between related shots)
  dip       - dip through near-black (heavy, emotional beats; leaving a 3D/footage sequence in a somber chapter)
apply(kind, a, b, u) blends frame a (outgoing) into frame b (incoming) at progress u in [0, 1].
"""
import math
import numpy as np, cv2

W, H = 1920, 1080
DUR = {'cut': 0.0, 'dissolve': .55, 'zoomblur': .30, 'whip': .26, 'dip': .7}


def ss(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)


def choose(kind, mood, prev=None, entering=True):
    if kind == 'type': return 'cut'
    pref = {
        'calm':   ['dissolve', 'zoomblur', 'dissolve', 'whip'],
        'reveal': ['dissolve', 'zoomblur', 'dip'],
        'somber': ['dissolve', 'dip', 'dissolve'],
        'tense':  ['whip', 'zoomblur', 'cut', 'whip'],
    }.get(mood, ['dissolve', 'zoomblur'])
    if kind == 'foot': pref = (['zoomblur', 'cut'] if mood == 'tense' else ['dissolve', 'dip']) + pref
    if kind == 'trip': pref = ['dissolve', 'whip'] + pref
    if not entering and mood in ('somber',): pref = ['dip'] + pref
    for p in pref:
        if p != prev: return p
    return pref[0]


def _zoom(img, z):
    M = np.float32([[z, 0, W / 2 - z * W / 2], [0, z, H / 2 - z * H / 2]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def _hblur(img, k):
    k = int(k) | 1
    if k < 3: return img
    ker = np.zeros((1, k), np.float32); ker[0] = 1.0 / k
    return cv2.filter2D(img, -1, ker, borderType=cv2.BORDER_REFLECT)


def apply(kind, a, b, u, direction=1):
    a = a.astype(np.float32); b = b.astype(np.float32)
    if kind == 'cut': return b
    if kind == 'dissolve':
        e = ss(u); return a * (1 - e) + b * e
    if kind == 'dip':
        if u < .5: return a * (1 - .88 * ss(u * 2))
        return b * (.12 + .88 * ss(u * 2 - 1))
    if kind == 'zoomblur':
        e = ss(u)
        A = _zoom(a, 1 + .7 * e); B = _zoom(b, 1.25 - .25 * e)
        k = int(9 * math.sin(math.pi * e)) | 1
        m = A * (1 - e) + B * e
        return cv2.GaussianBlur(m, (k, k), 0) if k > 1 else m
    if kind == 'whip':
        e = ss(u); off = int(direction * W * e)
        A = np.roll(a, -off, axis=1); B = np.roll(b, W * direction - off, axis=1) if e > 0 else b
        m = A * (1 - e) + B * e if .35 < e < .65 else (A if e <= .35 else B)
        return _hblur(m, 160 * math.sin(math.pi * e))
    return b
