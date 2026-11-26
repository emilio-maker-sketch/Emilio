"""Full-length sound pass (and the 62 s sample) using real recorded CC0 effects from the sound-effects skill library.
Output: build/sample/sfx_real.wav (48 kHz mono float)."""
import json, os, math
import numpy as np, soundfile as sf
from scipy.signal import resample_poly
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, 'build')
LIB = os.path.expanduser('~/.claude/skills/sound-effects/sfx')
import sys
FULL = 'full' in sys.argv
SR = 48000
D = json.load(open(os.path.join(B, 'cues.json')))['duration'] if FULL else 62.0
SCANS = [(215.4, 228.2, 0.0), (423.4, 427.8, 13.1), (574.9, 583.8, 18.0)]   # 3D eruption segments: (abs start, abs end, 3D local time at start)
out = np.zeros(int(SR * D), np.float32)
_c = {}
def snd(rel):
    if rel not in _c:
        a, sr = sf.read(os.path.join(LIB, rel), dtype='float32')
        if a.ndim > 1: a = a.mean(1)
        if sr != SR: a = resample_poly(a, SR, sr).astype(np.float32)
        _c[rel] = a / (np.abs(a).max() + 1e-9)
    return _c[rel]
def place(rel, t, db, dur=None, fade=.03):
    a = snd(rel)
    if dur: a = a[:int(dur * SR)].copy(); n = int(fade * SR); a[-n:] *= np.linspace(1, 0, n)
    i = int(t * SR); j = min(len(out), i + len(a))
    if j > i: out[i:j] += a[:j - i] * 10 ** (db / 20)
def loop(rel, t0, t1, db):
    a = snd(rel); n = int((t1 - t0) * SR); rep = np.tile(a, n // len(a) + 2)[:n].copy()
    f = int(.6 * SR); rep[:f] *= np.linspace(0, 1, f); rep[-f:] *= np.linspace(1, 0, f)
    i = int(t0 * SR); out[i:i + n] += rep * 10 ** (db / 20)

c = json.load(open(os.path.join(B, 'cues.json')))
board = lambda t: t < D and not any(a - .2 <= t <= b + .1 for a, b, _ in SCANS)
W = ['whoosh/fs-169867-swoosh.ogg', 'whoosh/fs-264777-swoosh.ogg', 'whoosh/fs-683101-quick-woosh.ogg', 'kit/whoosh.ogg']
for k, t in enumerate(c['whoosh']):
    if board(t): place(W[k % 4], t - .08, -19)
for t in c['thud']:
    if board(t): place('impact/fs-177242-cinematic-impact.ogg', t, -14)
for t, n in c['type']:
    if board(t): place('typing/fs-447909-keyboard-typing.ogg', t, -24, dur=min(2.2, .055 * n + .15))
for t in c['tick']:
    if board(t): place('kit/tick.ogg', t, -26)
for t in c['pin']:
    if board(t): place('kit/click.ogg', t, -25)
for t, du in c['scratch']:
    if board(t): place('transition/fs-702773-swipe-wav.ogg', t, -27, dur=max(.25, du))
for t in c['soft']:
    if board(t): place('transition/fs-816262-broomstick-whoosh-3-quiet-okm1.ogg', t, -29)
# the opening: case-file typing on black, lamp flicker
place('typing/fs-79388-keyboard-typing-wav.ogg', .3, -20, dur=4.6)
place('glitch/kenney-interface-glitch-002.ogg', 5.4, -24)
# --- synthesized natural sounds (the library has no volcano / sea / pumice): seeded noise, filtered
from scipy.signal import butter, sosfilt
def noise(sec, seed, lo=None, hi=None, order=4):
    r = np.random.default_rng(seed); x = r.normal(0, 1, int(sec * SR)).astype(np.float32)
    if lo and hi: x = sosfilt(butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)
    elif hi: x = sosfilt(butter(order, hi, 'low', fs=SR, output='sos'), x)
    return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)
def put(a, t, db, fin=.4, fout=.6):
    a = a.copy(); n1, n2 = int(fin * SR), int(fout * SR); a[:n1] *= np.linspace(0, 1, n1); a[-n2:] *= np.linspace(1, 0, n2)
    i = int(t * SR); j = min(len(out), i + len(a))
    if j > i: out[i:j] += a[:j - i] * 10 ** (db / 20)
def rumble(t0, t1, db, seed=1, grow=False):
    a = noise(t1 - t0, seed, hi=90, order=4) * .7 + noise(t1 - t0, seed + 1, 40, 260) * .3
    env = 1 + .5 * np.sin(np.linspace(0, (t1 - t0) * 1.7, len(a)))
    if grow: env *= np.linspace(.4, 1.3, len(a))
    put((a * env / env.max()).astype(np.float32), t0, db)
def patter(t0, t1, db, rate=38, seed=4):                 # falling pumice: many small stony clicks
    r = np.random.default_rng(seed); dur = t1 - t0; a = np.zeros(int(dur * SR), np.float32)
    click = noise(.025, seed, 1800, 7000) * np.exp(-np.linspace(0, 9, int(.025 * SR))).astype(np.float32)
    for k in range(int(dur * rate)):
        i = int(r.uniform(0, dur - .03) * SR); a[i:i + len(click)] += click * r.uniform(.2, 1)
    put(a / (np.abs(a).max() + 1e-9), t0, db, .3, .5)
def sea(t0, t1, db, seed=6):
    a = noise(t1 - t0, seed, 120, 1600); n = len(a); x = np.linspace(0, (t1 - t0) / 3.2 * 2 * np.pi, n)
    put((a * (.35 + .65 * np.clip(np.sin(x), 0, 1) ** 2)).astype(np.float32), t0, db)
for a, b, l0 in SCANS:                                     # the 3D eruption segments
    place('riser/fs-685256-riser-sound-effect-short-wav.ogg', a - .8, -20)
    rumble(a, b, -12, seed=int(a), grow=l0 >= 13)
    if l0 == 0: place('impact/kenney-sci-lowfrequency-explosion-000.ogg', a + .7, -12)
    if l0 == 0: patter(a + 6.5, b, -30)
    if l0 >= 13: place('impact/kenney-sci-lowfrequency-explosion-001.ogg', a + .4, -12)
    if l0 >= 18: place('impact/fs-222517-dramatic-hit.ogg', b - 1.2, -15); patter(a, b - 2, -32)
    place('transition/fs-786514-swoosh-v2.ogg', b - .3, -19)
# eruption footage cutaways get a low rumble under them
TL = json.load(open(os.path.join(B, 'timeline.json'))); S_ = TL['sentences']
for ev in TL['events']:
    d = ev['d']
    if d[0] == 'foot' and d[1] == 'V' and 's' in ev:
        s_ = S_[ev['s']]; rumble(s_['start'] - .1, s_['end'] + .3, -18, seed=ev['s'])
    if d[0] == 'film':
        sc = d[1]; dur = next((float(x.split('=')[1]) for x in d[2:] if x.startswith('dur=')), 7.0); t0 = ev['t']; t1 = t0 + dur - 2.0
        if sc == 'flee': patter(t0, t1, -22, rate=55); rumble(t0, t1, -24, seed=21)
        if sc == 'boathouse': rumble(t0, t1, -16, seed=22, grow=True); sea(t0, t1, -26)
        if sc == 'darkness': rumble(t0, t1, -22, seed=23); patter(t0, t1, -28, rate=25)
        if sc == 'pliny': sea(t0, t1, -18); rumble(t0, t1, -22, seed=24); patter(t0, t1, -30)
        if sc == 'plaster': place('ambience/fs-329569-roomtone-bedroom-yew.ogg', t0, -24, dur=t1 - t0)
name = 'sfx_real_full.wav' if FULL else os.path.join('sample', 'sfx_real.wav')
sf.write(os.path.join(B, name), out, SR, subtype='FLOAT')
print('peak', float(np.abs(out).max()))
