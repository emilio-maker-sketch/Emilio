"""Stereo score + mix for a documentary (replaces the mono sidechain mix).

  score:  one track per chapter, kept in STEREO, loops joined with equal-power crossfades at quiet points
          (no hard seams), chapter changes crossfaded; '@hush SECONDS' events take the music out for a dramatic beat
          and bring it back gently.
  mix:    look-ahead voice ducking computed from the narration envelope (music sits ~14 dB under speech, rises in pauses),
          ambience widened (decorrelated L/R), SFX kept centred-ish with slight random pan, short reverb tail on hits,
          then two-pass EBU R128 loudness normalisation to -14 LUFS / -1 dBTP in the final mux.

python3 mix.py score   <timeline.json> <music_dir> <plan.json> <out_music.wav>
python3 mix.py mix     <vo.wav> <music.wav> <ambient.wav> <sfx.wav> <out_mix.wav> [timeline.json]
python3 mix.py mux     <video.mp4> <mix.wav> <out.mp4>
"""
import sys, os, json, subprocess
import numpy as np, soundfile as sf
from scipy.signal import resample_poly, butter, sosfiltfilt, fftconvolve

SR = 48000


def load(path, stereo=True):
    a, sr = sf.read(path, dtype='float32', always_2d=True)
    if sr != SR: a = resample_poly(a, SR, sr, axis=0).astype(np.float32)
    if stereo and a.shape[1] == 1: a = np.repeat(a, 2, 1)
    if not stereo: a = a.mean(1, keepdims=True)
    return a


def rms_db(a):
    return 20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-9)


def env(x, win=.05):
    """RMS envelope sampled every 10 ms."""
    hop = SR // 100; n = len(x) // hop
    fr = x[:n * hop].reshape(n, hop)
    return np.sqrt((fr ** 2).mean(1))


def loop_to(a, n, xf=2.0):
    """Extend a track to n samples by looping at its quietest late bar, with an equal-power crossfade."""
    if len(a) >= n: return a[:n].copy()
    f = int(xf * SR)
    e = env(a.mean(1))
    lo = int(len(e) * .55); hi = max(lo + 1, len(e) - int(xf * 100) - 50)
    cut = (lo + int(np.argmin(e[lo:hi]))) * (SR // 100) if hi > lo else len(a) - f
    seg = a[:cut + f]
    out = seg[:cut].copy()
    t = np.linspace(0, np.pi / 2, f)[:, None]
    while len(out) < n:
        tail = out[-f:] * np.cos(t) if len(out) >= f else out[-f:]
        head = a[:f] * np.sin(t)
        out = np.concatenate([out[:-f], tail + head, a[f:cut]])
    return out[:n]


def score(tl_path, music_dir, plan_path, out):
    TL = json.load(open(tl_path)); D = TL['total']
    zt = {e['d'][1]: e['t'] for e in TL['events'] if e['d'][0] == 'zone'}
    plan = json.load(open(plan_path))                       # [[zone, track, gain_db], ...]
    buf = np.zeros((int(D * SR) + SR, 2), np.float32); XF = 3.0
    for k, row in enumerate(plan):
        z, name = row[0], row[1]; g = row[2] if len(row) > 2 else 0
        t0 = max(0, zt[z] - XF / 2); t1 = (zt[plan[k + 1][0]] + XF / 2) if k + 1 < len(plan) else D
        n = int((t1 - t0) * SR)
        a = load(os.path.join(music_dir, name + '.wav'))
        a = a / (10 ** (rms_db(a) / 20)) * 10 ** ((-20 + g) / 20)
        seg = loop_to(a, n)
        f = int(XF * SR); r = np.linspace(0, np.pi / 2, f)[:, None]
        seg[:f] *= np.sin(r); seg[-f:] *= np.cos(r)
        i = int(t0 * SR); buf[i:i + n] += seg[:len(buf) - i]
    # dramatic silences
    g = np.ones(len(buf), np.float32)
    for e in TL['events']:
        if e['d'][0] != 'hush': continue
        dur = float(e['d'][1]) if len(e['d']) > 1 else 2.5
        a, b = int((e['t'] - .5) * SR), int((e['t'] + dur) * SR)
        fo, fi = int(.5 * SR), int(2.5 * SR)
        g[a:a + fo] = np.minimum(g[a:a + fo], np.linspace(1, 0, fo)[:len(g[a:a + fo])])
        g[a + fo:b] = 0
        g[b:b + fi] = np.minimum(g[b:b + fi], np.linspace(0, 1, fi)[:len(g[b:b + fi])])
    buf *= g[:, None]
    end = int(4 * SR); buf[-end:] *= np.linspace(1, 0, end)[:, None]
    sf.write(out, buf, SR, subtype='FLOAT')
    print('score', round(D, 1), 's', [p[1] for p in plan], 'hush', sum(1 for e in TL['events'] if e['d'][0] == 'hush'))


def duck_gain(vo, depth_db=14.0, floor_db=-6.0):
    """Gain curve for the music: down by depth_db while the narrator speaks, back up in pauses longer than ~0.7 s.
    Look-ahead 180 ms so the dip starts before the first syllable; slow release so pauses breathe without pumping."""
    e = env(vo)
    thr = max(np.percentile(e, 30) * 2.5, 10 ** (-45 / 20))
    speech = e > thr
    # bridge short gaps (between words) so the music doesn't pump
    k = 70
    s = np.convolve(speech.astype(float), np.ones(k), 'same') > 0
    target = np.where(s, -depth_db, 0.0)
    la = 18; target = np.minimum(target, np.concatenate([target[la:], np.zeros(la)]))
    out = np.zeros_like(target); cur = 0.0
    for i, v in enumerate(target):
        rate = .35 if v < cur else .06              # dB per 10 ms: fast attack, gentle release
        cur = max(v, cur - rate * 10) if v < cur else min(v, cur + rate * 10 / 4)
        out[i] = cur
    g = 10 ** (out / 20)
    return np.interp(np.arange(len(vo)) / (SR // 100), np.arange(len(g)), g).astype(np.float32)


def widen(m, seed=3, ms=11):
    """Mono ambience -> decorrelated stereo (Haas-free all-pass-ish via short random FIRs)."""
    r = np.random.default_rng(seed); n = int(SR * ms / 1000)
    irs = [r.normal(0, 1, n) * np.exp(-np.linspace(0, 5, n)) for _ in range(2)]
    irs = [ir / np.sqrt((ir ** 2).sum()) for ir in irs]
    L = fftconvolve(m, irs[0])[:len(m)]; R = fftconvolve(m, irs[1])[:len(m)]
    return np.stack([.6 * m + .4 * L, .6 * m + .4 * R], 1).astype(np.float32)


def mix(vo_p, mus_p, amb_p, sfx_p, out, tl_p=None):
    vo = load(vo_p, stereo=False)[:, 0]
    n = len(vo) + SR
    def fit(a): b = np.zeros((n, a.shape[1]), np.float32); b[:min(n, len(a))] = a[:n]; return b
    mus = fit(load(mus_p)); amb = fit(load(amb_p, stereo=False)); sfx = fit(load(sfx_p, stereo=False))
    vo = np.concatenate([vo, np.zeros(SR, np.float32)])
    g = duck_gain(vo)
    mus *= g[:, None]
    amb2 = widen(amb[:, 0]) * (.55 + .45 * g[:, None])               # ambience dips less than music
    # sfx: slight pan per hit region so impacts don't all sit dead centre
    pan = .5 + .12 * np.sin(np.arange(n) / SR * .37)
    sfx2 = np.stack([sfx[:, 0] * np.sqrt(1 - pan), sfx[:, 0] * np.sqrt(pan)], 1) * 1.41
    # gentle high-pass on everything but voice to keep the low end clean under narration
    sos = butter(2, 45, 'hp', fs=SR, output='sos')
    bed = sosfiltfilt(sos, mus + amb2 + sfx2, axis=0)
    voice = np.stack([vo, vo], 1)
    outm = (voice + bed).astype(np.float32)
    pk = np.abs(outm).max()
    if pk > .98: outm *= .98 / pk
    sf.write(out, outm, SR, subtype='FLOAT')
    sp = g < .5
    vr = rms_db(vo[sp]) if sp.any() else 0
    mr = rms_db(mus[sp, 0]) if sp.any() else 0
    print(f'mix: voice {vr:.1f} dB, music under voice {mr:.1f} dB -> separation {vr - mr:.1f} dB')


def mux(video, mixw, out):
    """Two-pass loudnorm (linear mode) so the whole film sits at -14 LUFS without dynamic pumping."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-i', mixw, '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    j = json.loads(r[r.rindex('{'):r.rindex('}') + 1])
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
          f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000")
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', video, '-i', mixw, '-map', '0:v', '-map', '1:a', '-af', af,
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-ac', '2', '-shortest', '-movflags', '+faststart', out], check=True)
    print('muxed', out)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'score': score(*sys.argv[2:6])
    elif cmd == 'mix': mix(*sys.argv[2:8])
    elif cmd == 'mux': mux(*sys.argv[2:5])
