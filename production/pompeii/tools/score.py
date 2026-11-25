"""Procedural documentary score that follows the script's moods. No samples, no licensing.
score(dur, moods, hits, out_wav): moods = [(t0, t1, 'calm'|'tense'|'rising'|'dark')], hits = [t] (low boom hits)
"""
import numpy as np, soundfile as sf
from scipy import signal

SR = 48000

def hz(n): return 440.0 * 2 ** ((n - 69) / 12)

CHORDS = {  # MIDI voicings (bass + upper)
    'calm':   [[41, 53, 60, 65, 69], [36, 48, 55, 64, 67], [38, 50, 57, 62, 65], [34, 46, 53, 62, 65]],   # F C Dm Bb
    'tense':  [[38, 50, 57, 62, 65], [34, 46, 53, 58, 65], [31, 43, 55, 58, 62], [33, 45, 52, 57, 61]],   # Dm Bb Gm A
    'rising': [[38, 50, 57, 62, 69], [34, 46, 58, 62, 70], [36, 48, 55, 64, 67], [33, 45, 57, 61, 64]],
    'dark':   [[26, 38, 45, 50, 53], [22, 34, 46, 50, 53], [31, 43, 50, 55, 58], [25, 37, 49, 52, 56]],
}
LEVEL = {'calm': 0.38, 'tense': 0.55, 'rising': 0.78, 'dark': 0.5}

def lp(x, fc, order=2):
    sos = signal.butter(order, fc, 'low', fs=SR, output='sos'); return signal.sosfilt(sos, x)
def bp(x, lo, hi):
    sos = signal.butter(2, [lo, hi], 'band', fs=SR, output='sos'); return signal.sosfilt(sos, x)

def pad_voice(freq, L, rng):
    t = np.arange(L) / SR; out = np.zeros(L)
    for det in (-0.07, 0.0, 0.06):
        f = freq * 2 ** (det / 12) * (1 + 0.003 * np.sin(2 * np.pi * (4.6 + det) * t + rng.uniform(0, 6)))
        ph = 2 * np.pi * np.cumsum(f) / SR
        for h in range(1, 8): out += np.sin(h * ph + rng.uniform(0, 6)) / h ** 1.45
    return out

def mood_at(moods, tt):
    for a, b, m in moods:
        if a <= tt < b: return m
    return moods[-1][2] if moods else 'calm'

def score(dur, moods, hits, out):
    rng = np.random.default_rng(11)
    N = int(dur * SR) + SR; t = np.arange(N) / SR
    mix = np.zeros(N)
    # ---- pads: 10 s chords, crossfaded, chord set by mood at chord start
    step = 10.0; k = 0; s = -2.0
    while s < dur:
        m = mood_at(moods, max(0, s + 2)); ch = CHORDS[m][k % 4]
        i0 = max(0, int(s * SR)); i1 = min(N, int((s + step + 4) * SR)); L = i1 - i0
        if L > 0:
            e = np.minimum(1, np.arange(L) / SR / 3.5) * np.minimum(1, (L - np.arange(L)) / SR / 3.5)
            v = sum(pad_voice(hz(n), L, rng) * (1.2 if n < 40 else 0.65) for n in ch)
            mix[i0:i1] += v * e
        s += step; k += 1
    mix = lp(mix, 1300)
    lev = np.array([LEVEL[mood_at(moods, x)] for x in np.arange(0, dur + 1, 0.25)])
    lev = np.convolve(lev, np.ones(16) / 16, mode='same')                  # ~4 s smoothing between moods
    inten = np.interp(t, np.arange(len(lev)) * 0.25, lev)
    inten *= np.interp(t, [0, 3, dur - 4, dur + 1], [0, 1, 1, 0])
    mix *= inten * 0.15
    # ---- sub drone (dark / tense)
    dk = np.array([1.0 if mood_at(moods, x) in ('dark', 'tense') else 0.25 for x in np.arange(0, dur + 1, 0.25)])
    dk = np.interp(t, np.arange(len(dk)) * 0.25, np.convolve(dk, np.ones(24) / 24, mode='same'))
    mix += (np.sin(2 * np.pi * hz(26) * t) * 0.8 + np.sin(2 * np.pi * hz(38) * t) * 0.35) * dk * 0.15 * np.interp(t, [0, 4, dur - 4, dur + 1], [0, 1, 1, 0])
    # ---- heartbeat pulse in tense / rising
    beat = 1.0
    while beat < dur - 1:
        m = mood_at(moods, beat)
        if m in ('tense', 'rising'):
            for off, g in ((0, 1.0), (0.24, 0.6)):
                i = int((beat + off) * SR); L = int(0.5 * SR)
                if i + L < N:
                    ss = np.arange(L) / SR; mix[i:i + L] += np.sin(2 * np.pi * (52 * np.exp(-ss * 3) + 40) * ss) * np.exp(-ss * 9) * g * 0.35
            beat += 0.95 if m == 'rising' else 1.25
        else: beat += 0.5
    # ---- risers into each 'rising' segment, booms at hits
    def boom(at, gain):
        i = int(at * SR); L = min(int(5 * SR), N - i)
        if L <= 0 or i < 0: return
        ss = np.arange(L) / SR; f = 70 * np.exp(-ss * 1.2) + 28
        mix[i:i + L] += (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-ss * 0.9) + lp(rng.normal(0, 1, L), 900) * np.exp(-ss * 5) * 0.6) * gain
    for a, b, m in moods:
        if m == 'rising' and 6 < a < dur - 1:
            i0, i1 = int((a - 5) * SR), int(a * SR); u = np.arange(i1 - i0) / (i1 - i0)
            mix[i0:i1] += bp(rng.normal(0, 1, i1 - i0), 300, 5000) * u ** 2.2 * 0.12
            mix[i0:i1] += np.sin(2 * np.pi * np.cumsum(55 * 2 ** (u * 1.5)) / SR) * u ** 2 * 0.18
            boom(a, 0.55)
    for h in hits: boom(h, 0.45)
    # ---- sparse piano in calm passages
    nt = 3.0; notes = [74, 69, 65, 72, 67, 62, 70, 65]; j = 0
    while nt < dur - 3:
        if mood_at(moods, nt) == 'calm' and rng.random() < 0.6:
            i = int(nt * SR); L = min(int(4.5 * SR), N - i); ss = np.arange(L) / SR; fr = hz(notes[j % len(notes)]); j += 1
            mix[i:i + L] += sum(np.sin(2 * np.pi * fr * h * ss) * np.exp(-ss * (1.3 + h)) / h ** 1.2 for h in (1, 2, 3, 4)) * 0.07
        nt += rng.uniform(2.2, 4.5)
    # ---- reverb
    L = int(3.2 * SR); ir = rng.normal(0, 1, L) * np.exp(-np.arange(L) / SR * 2.1); ir = lp(ir, 5000); ir /= np.sqrt((ir ** 2).sum())
    wl = signal.oaconvolve(mix, ir)[:N]; wr = signal.oaconvolve(mix, np.roll(ir, 211))[:N]
    st = np.stack([mix * 0.75 + wl * 0.55, mix * 0.75 + wr * 0.55], 1)[:int(dur * SR)]
    st /= np.abs(st).max() + 1e-9; st *= 0.85
    sf.write(out, st.astype(np.float32), SR)
