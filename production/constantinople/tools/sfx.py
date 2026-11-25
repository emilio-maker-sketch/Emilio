"""Synthesized ambience and effects (no licences needed). Output build/sfx/*.wav, 48 kHz mono.

  python3 tools/sfx.py
"""
import os, numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'sfx'); SR = 48000
rng = np.random.default_rng(11)

def bp(x, lo, hi, order=2): return sosfilt(butter(order, [lo, hi], 'bandpass', fs=SR, output='sos'), x)
def lp(x, f, order=2): return sosfilt(butter(order, f, 'lowpass', fs=SR, output='sos'), x)
def smooth_noise(n, rate):
    k = max(2, int(n / SR * rate)); pts = rng.normal(0, 1, k)
    return np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)
def norm(x, peak=0.9): return (x / (np.abs(x).max() + 1e-9) * peak).astype(np.float32)
def loopable(x, fade=2.0):
    f = int(fade * SR); y = x[:-f].copy(); y[:f] = y[:f] * np.linspace(0, 1, f) + x[-f:] * np.linspace(1, 0, f); return y

def wind(sec=40):
    n = SR * sec; w = rng.normal(0, 1, n)
    gust = 0.55 + 0.45 * smooth_noise(n, 0.25) ** 2
    a = bp(w, 120, 900) * gust + bp(w, 900, 3000) * 0.25 * smooth_noise(n, 0.6) ** 2
    return loopable(norm(a, 0.6))

def fire(sec=30):
    n = SR * sec; base = lp(rng.normal(0, 1, n), 500) * 0.35
    cr = np.zeros(n)
    for t in rng.integers(0, n - 2000, int(sec * 22)):
        L = int(rng.integers(80, 900)); cr[t:t + L] += rng.normal(0, 1, L) * np.exp(-np.linspace(0, 6, L)) * rng.uniform(0.2, 1.0)
    return loopable(norm(base + bp(cr, 1500, 9000) * 1.4, 0.6))

def night(sec=40):
    n = SR * sec; t = np.arange(n) / SR
    cr = np.zeros(n)
    for c0 in rng.uniform(0, sec - 1, int(sec * 1.6)):   # distant crickets
        i = int(c0 * SR); L = int(0.25 * SR); tt = np.arange(L) / SR
        cr[i:i + L] += np.sin(2 * np.pi * 4300 * tt) * (np.sin(2 * np.pi * 28 * tt) > 0.3) * np.hanning(L) * rng.uniform(0.05, 0.2)
    return loopable(norm(wind(sec + 2)[:n] * 0.5 + cr, 0.5))

def bell(f0=196.0, sec=9):
    n = SR * sec; t = np.arange(n) / SR; out = np.zeros(n)
    for ratio, amp, dec in ((0.5, 0.6, 0.35), (1.0, 1.0, 0.55), (1.19, 0.55, 0.8), (1.5, 0.45, 0.9), (2.0, 0.5, 1.1),
                            (2.52, 0.3, 1.5), (3.0, 0.2, 1.9), (4.07, 0.12, 2.6)):
        out += amp * np.sin(2 * np.pi * f0 * ratio * t + rng.uniform(0, 6)) * np.exp(-dec * t)
    out += rng.normal(0, 1, n) * np.exp(-t * 40) * 0.3   # strike
    return out

def bells(sec=34):
    n = SR * sec; out = np.zeros(n)
    for k, t0 in enumerate(np.arange(0.5, sec - 9, 2.6)):
        f = [196.0, 174.6, 220.0, 146.8][k % 4]; b = bell(f) * (0.8 if k % 4 else 1.0)
        i = int(t0 * SR); out[i:i + len(b)] += b[:n - i]
    far = lp(out, 2500)  # distant, through the city
    return norm(far, 0.7)

def boom(sec=7):
    n = SR * sec; t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (38 + 30 * np.exp(-t * 6)) * t) * np.exp(-t * 1.1)
    crack = lp(rng.normal(0, 1, n), 1800) * np.exp(-t * 9)
    tail = lp(rng.normal(0, 1, n), 300) * np.exp(-t * 0.9) * 0.4
    return norm(body + crack * 0.7 + tail, 0.95)

def drone(sec=40):
    n = SR * sec; t = np.arange(n) / SR
    a = sum(np.sin(2 * np.pi * f * t + p) * w for f, p, w in ((55, 0, 1), (55.3, 1, 0.8), (82.4, 2, 0.4), (110.2, 3, 0.25)))
    return loopable(norm(a * (0.7 + 0.3 * smooth_noise(n, 0.1)), 0.5))

def main():
    os.makedirs(OUT, exist_ok=True)
    for name, fn in (('wind', wind), ('fire', fire), ('night', night), ('bells', bells), ('boom', boom), ('drone', drone)):
        sf.write(os.path.join(OUT, name + '.wav'), fn(), SR); print(name)

if __name__ == '__main__': main()
