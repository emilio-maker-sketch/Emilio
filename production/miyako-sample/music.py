"""Slow dramatic score for the Miyako sample, synthesised from scratch (no samples, no licensing).
Layers: string-like pad chords, sub drone, earthquake rumble, riser into the wave, impact boom,
heartbeat pulse during the footage, sparse piano at the end. Long algorithmic reverb.
Usage: python3 music.py <duration> <quake_t> <impact_t> <calm_t>
"""
import os, sys, numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, 'build'); os.makedirs(B, exist_ok=True)
SR = 48000
DUR, T_QUAKE, T_IMPACT, T_CALM = (float(x) for x in sys.argv[1:5])
HITS = [float(x) for x in sys.argv[5].split(',')] if len(sys.argv) > 5 and sys.argv[5] else []
N = int(DUR * SR); t = np.arange(N) / SR
rng = np.random.default_rng(7)

def hz(n): return 440 * 2 ** ((n - 69) / 12)
def env(start, end, att, rel):
    e = np.zeros(N); i0, i1 = int(start * SR), min(int(end * SR), N)
    if i1 <= i0: return e
    seg = np.arange(i1 - i0) / SR; L = (i1 - i0) / SR
    e[i0:i1] = np.minimum(1, seg / att) * np.minimum(1, np.maximum(0, (L - seg) / rel))
    return e
def lowpass(x, fc):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / np.sqrt(1 + (f / fc) ** 4), len(x))
def bandpass(x, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X * (f > lo) * (f < hi), len(x))

def string_voice(freq, e):
    """Ensemble of detuned saw-ish partials with slow vibrato -> warm string pad."""
    out = np.zeros(N)
    for det in (-0.07, 0.0, 0.06):
        f = freq * 2 ** (det / 12) * (1 + 0.003 * np.sin(2 * np.pi * (4.6 + det) * t + rng.uniform(0, 6)))
        ph = 2 * np.pi * np.cumsum(f) / SR
        for h in range(1, 9):
            out += np.sin(h * ph + rng.uniform(0, 6)) / h ** 1.4
    return out * e

# --- chord progression in D minor (MIDI notes), each chord ~ 9 s with long crossfades
CH = [[38, 50, 57, 62, 65], [34, 46, 53, 62, 65], [31, 43, 55, 58, 62], [33, 45, 52, 57, 61],
      [38, 50, 57, 62, 65], [34, 46, 53, 58, 65], [36, 48, 55, 60, 64], [33, 45, 52, 57, 61], [38, 50, 57, 62, 69]]
pad = np.zeros(N); step = 9.0
for k, chord in enumerate(CH):
    s = k * step - 1.5
    if s > DUR: break
    e = env(max(0, s), s + step + 3.0, 3.0, 3.5)
    for n in chord:
        pad += string_voice(hz(n), e) * (1.3 if n < 40 else 0.7)
# intensity curve: soft start, swell into impact, full during footage, fade after calm
inten = np.interp(t, [0, 3, T_QUAKE, T_IMPACT - 0.5, T_IMPACT, T_CALM, T_CALM + 4, DUR - 4, DUR],
                     [0, .35, .45, .75, 1.0, .85, .5, .45, 0])
pad = lowpass(pad, 1400) * inten

# --- sub drone
sub = np.sin(2 * np.pi * hz(26) * t) * 0.9 + np.sin(2 * np.pi * hz(38) * t) * 0.4
sub *= np.interp(t, [0, 4, DUR - 5, DUR], [0, 1, 1, 0]) * 0.5

# --- earthquake rumble (brown noise, trembling)
brown = np.cumsum(rng.normal(0, 1, N)); brown -= lowpass(brown, 8); brown = lowpass(brown, 120)
brown /= np.abs(brown).max() + 1e-9
trem = 0.6 + 0.4 * np.sin(2 * np.pi * 7.3 * t) * np.sin(2 * np.pi * 2.1 * t)
rumble = brown * trem * env(T_QUAKE - 0.2, T_QUAKE + 7, 0.4, 4.5) * 1.6

# --- riser into the wave (filtered noise sweep + rising tone)
ris = np.zeros(N); i0, i1 = int((T_IMPACT - 6) * SR), int(T_IMPACT * SR)
seg = np.arange(i1 - i0) / SR; u = seg / 6
ris[i0:i1] = rng.normal(0, 1, i1 - i0) * u ** 2.2
ris = bandpass(ris, 300, 6000) * 0.25
tone = np.zeros(N); f = 55 * 2 ** (u * 1.5); tone[i0:i1] = np.sin(2 * np.pi * np.cumsum(f) / SR) * u ** 2 * 0.35

# --- impact: deep boom + noise crack
def boom(at, gain=1.0):
    o = np.zeros(N); i = int(at * SR); L = min(int(5 * SR), N - i); s = np.arange(L) / SR
    f = 70 * np.exp(-s * 1.2) + 28
    o[i:i + L] = (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-s * 0.9)
                  + lowpass(rng.normal(0, 1, L), 900) * np.exp(-s * 5) * 0.8) * gain
    return o
impact = boom(T_IMPACT, 1.4)
for h in HITS: impact += boom(h, 0.7)

# --- heartbeat pulse during the footage
hb = np.zeros(N); beat = T_IMPACT + 1.0
while beat < T_CALM:
    for off, g in ((0, 1), (0.24, 0.6)):
        i = int((beat + off) * SR); L = int(0.5 * SR)
        if i + L < N:
            s = np.arange(L) / SR; hb[i:i + L] += np.sin(2 * np.pi * (52 * np.exp(-s * 3) + 40) * s) * np.exp(-s * 9) * g
    beat += 0.82
hb *= 0.9

# --- sparse piano at the end (bell-ish additive tone)
pn = np.zeros(N)
for k, (n, dt) in enumerate([(74, 0), (69, 2.2), (65, 4.4), (62, 7.0), (57, 9.8)]):
    at = T_CALM + 0.5 + dt
    i = int(at * SR); L = min(int(5 * SR), N - i)
    if L <= 0: continue
    s = np.arange(L) / SR; fr = hz(n)
    pn[i:i + L] += sum(np.sin(2 * np.pi * fr * h * s) * np.exp(-s * (1.2 + h)) / h ** 1.2 for h in (1, 2, 3, 4)) * 0.5

dry = pad * 0.16 + sub * 0.18 + rumble * 0.55 + ris + tone + impact * 0.6 + hb * 0.5 + pn * 0.22
# --- reverb: exponentially decaying noise IR (3.5 s)
L = int(3.5 * SR); ir = rng.normal(0, 1, L) * np.exp(-np.arange(L) / SR * 2.0); ir = lowpass(np.pad(ir, (0, 0)), 5000)[:L]
ir /= np.sqrt((ir ** 2).sum())
def conv(x):
    n2 = 1 << int(np.ceil(np.log2(len(x) + L)))
    return np.fft.irfft(np.fft.rfft(x, n2) * np.fft.rfft(ir, n2), n2)[:len(x)]
wetL = conv(dry); ir = np.roll(ir, 211); wetR = conv(dry)
mix = np.stack([dry * 0.75 + wetL * 0.55, dry * 0.75 + wetR * 0.55], 1)
mix /= np.abs(mix).max() + 1e-9; mix *= 0.89
sf.write(os.path.join(B, 'music.wav'), mix.astype(np.float32), SR)
print('music.wav', DUR, 's')
