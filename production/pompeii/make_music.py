"""Score: one licensed track per chapter (looped/trimmed), crossfaded at chapter changes -> build/music_only.wav (48 kHz mono)."""
import json, os, numpy as np, soundfile as sf
from scipy.signal import resample_poly
SR = 48000; M = '/home/user/Emilio/production/assets/music'
TL = json.load(open('build/timeline.json')); D = TL['total']
zt = {e['d'][1]: e['t'] for e in TL['events'] if e['d'][0] == 'zone'}
PLAN = [('open', 'Ossuary 1 - A Beginning'), ('city', 'Echoes of Time v2'), ('column', 'Long Note Two'), ('night', 'Dark Times'),
        ('surge', 'Lightless Dawn'), ('casts', 'Ossuary 6 - Air'), ('evidence', 'Unwritten Return'), ('end', 'Bittersweet')]
def load(name):
    a, sr = sf.read(os.path.join(M, name + '.wav'), dtype='float32')
    if a.ndim > 1: a = a.mean(1)
    if sr != SR: a = resample_poly(a, SR, sr).astype(np.float32)
    return a / (np.sqrt(np.mean(a ** 2)) + 1e-9) * 10 ** (-20 / 20)       # each track to -20 dB RMS
out = np.zeros(int(D * SR) + SR, np.float32); XF = 3.0
for k, (z, name) in enumerate(PLAN):
    t0 = max(0, zt[z] - XF / 2); t1 = (zt[PLAN[k + 1][0]] + XF / 2) if k + 1 < len(PLAN) else D
    n = int((t1 - t0) * SR); a = load(name)
    seg = np.tile(a, n // len(a) + 1)[:n].copy()
    f = int(XF * SR); seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
    i = int(t0 * SR); out[i:i + n] += seg[:len(out) - i]
out[-int(4 * SR):] *= np.linspace(1, 0, int(4 * SR))
sf.write('build/music_only.wav', out, SR, subtype='FLOAT'); print('music', round(D, 1), 's', [p[1] for p in PLAN])
