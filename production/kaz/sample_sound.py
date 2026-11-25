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
SCANS = [(8.0, 25.0, 0.0), (949.2, 959.9, 6.2)] if FULL else [(8.0, 25.0, 0.0)]   # (abs start, abs end, 3D local time at start)
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
# --- 3D CT scan scenes; local 3D time L maps to abs = a + (L - l0)
for a, b, l0 in SCANS:
    at = lambda L: a + (L - l0)
    if l0 == 0: place('riser/fs-464250-echo-chromatic-riser-wav.ogg', a - 1.6, -17)
    else: place('riser/fs-685256-riser-sound-effect-short-wav.ogg', a - .8, -19)
    loop('ambience/fs-426767-apartment-room-tone-wav.ogg', a, b, -26)
    loop('glitch/kenney-sci-computernoise-001.ogg', a + .6, b - .2, -36)
    if l0 < .6: place('ui-blip/kenney-digital-threetone1.ogg', at(.6), -24)
    if l0 < 6.0: place('whoosh/fs810485.ogg', at(6.0), -20)
    if l0 < 6.4: place('ui-blip/kenney-digital-twotone1.ogg', max(a + .2, at(6.4)), -24)
    place('riser/fs-685256-riser-sound-effect-short-wav.ogg', max(a + .3, at(7.7)), -24)
    for k in range(7): place('kit/tick.ogg', at(8.2 + k), -28)
    place('impact/fs-222517-dramatic-hit.ogg', at(14.6), -14)
    place('ding/kenney-interface-glass-001.ogg', at(14.65), -24)
    place('transition/fs-786514-swoosh-v2.ogg', b - .3, -19)
name = 'sfx_real_full.wav' if FULL else os.path.join('sample', 'sfx_real.wav')
sf.write(os.path.join(B, name), out, SR, subtype='FLOAT')
print('peak', float(np.abs(out).max()))
