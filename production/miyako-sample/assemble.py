"""Assemble the Miyako style sample.
Style: dark cinematic grade, 2.39:1 letterbox, slow push-ins, slow motion on key moments, dissolves,
small location/time captions, animated map, slow dramatic score, deep narration, footage audio low in the mix.
"""
import json, os, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); B = os.path.join(HERE, 'build')
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'footage')
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(B, 'miyako_sample.mp4')
W, H, FPS, X = 1920, 1080, 30, 0.8           # X = dissolve length
SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
SERIF = '/usr/share/fonts/truetype/crosextra/Caladea-Regular.ttf'
SERIFB = '/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf'

# ---------------- timeline ----------------
# kind, start, src, in, speed, zoom(start,end), caption
SHOTS = [
    ('card_open', 0.0),
    ('map',       4.0),
    ('clip',     24.0, 'yamada.mp4',     6.0, 1.00, (1.06, 1.14), None),
    ('clip',     31.5, 'miyako.mp4',     8.5, 0.80, (1.08, 1.16), '15:26  ·  MIYAKO, IWATE'),
    ('clip',     37.0, 'miyako.mp4',    30.0, 0.85, (1.05, 1.12), None),
    ('clip',     43.0, 'kamaishi.mp4',   7.0, 0.80, (1.04, 1.10), 'KAMAISHI  ·  40 km SOUTH'),
    ('clip',     48.5, 'miyako.mp4',    62.0, 0.85, (1.06, 1.12), None),
    ('clip',     53.0, 'yamada.mp4',    22.0, 0.80, (1.05, 1.13), 'YAMADA TOWN'),
    ('clip',     60.0, 'miyako.mp4',    84.0, 0.70, (1.10, 1.18), None),
    ('card_end', 67.0),
]
END = 76.0
VO_AT = [5.0, 14.9, 20.4, 26.2, 32.2, 37.6, 53.6, 61.6]
T_QUAKE, T_IMPACT, T_CALM = 15.0, 31.5, 60.0
MAP_DUR = 20.0 + X

def ease(x):
    x = min(max(x, 0), 1); return x * x * (3 - 2 * x)

def grade(img):
    """Desaturated, cool-shadow documentary grade + vignette. img: BGR uint8."""
    f = img.astype(np.float32) / 255
    g = f.mean(2, keepdims=True); f = g + (f - g) * 0.72                  # desaturate
    f = np.clip((f - 0.5) * 1.12 + 0.47, 0, 1)                             # contrast, slightly darker
    f = f ** 1.06
    lum = f.mean(2, keepdims=True)
    f[..., 0:1] += 0.035 * (1 - lum)                                       # blue into shadows (BGR)
    f[..., 2:3] += 0.02 * lum                                              # warm highlights
    return np.clip(f * VIG * 255, 0, 255).astype(np.uint8)

yy, xx = np.mgrid[0:H, 0:W]; r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
VIG = (1 - 0.42 * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None].astype(np.float32)

def caption_layer(text, a):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    f = ImageFont.truetype(SANS, 30)
    d.line([(150, 836), (150 + 120 * a, 836)], fill=(230, 60, 45, int(255 * a)), width=3)
    d.text((150, 846), text, font=f, fill=(235, 235, 230, int(235 * a)))
    return ov

def writer(path, dur):
    return subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                             '-t', f'{dur:.3f}', '-c:v', 'libx264', '-crf', '15', '-preset', 'medium', '-pix_fmt', 'yuv420p', path], stdin=subprocess.PIPE)

def render_clip(i, src, tin, speed, zoom, cap, dur):
    path = os.path.join(B, f'shot{i:02d}.mp4')
    srcdur = dur * speed + 0.5
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', str(tin), '-t', f'{srcdur:.3f}', '-i', os.path.join(SRC, src),
                            '-vf', f'fps={FPS * speed:.4f},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}',
                            '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    out = writer(path, dur); n = int(dur * FPS); last = None
    for k in range(n):
        buf = dec.stdout.read(W * H * 3)
        if len(buf) == W * H * 3: last = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        fr = last; u = k / max(1, n - 1)
        z = zoom[0] + (zoom[1] - zoom[0]) * u                       # smooth sub-pixel push-in
        M = cv2.getRotationMatrix2D((W / 2, H / 2 - 20), 0, z)
        fr = grade(cv2.warpAffine(fr, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT))
        if cap:
            t = k / FPS; a = ease((t - 0.6) / 0.7) * (1 - ease((t - (dur - X - 0.9)) / 0.6))
            if a > 0.01:
                im = Image.alpha_composite(Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)).convert('RGBA'), caption_layer(cap, a))
                fr = cv2.cvtColor(np.asarray(im.convert('RGB')), cv2.COLOR_RGB2BGR)
        out.stdin.write(fr.tobytes())
    dec.stdout.close(); dec.wait(); out.stdin.close(); out.wait()
    return path

def render_card(i, kind, dur):
    path = os.path.join(B, f'shot{i:02d}.mp4'); out = writer(path, dur); n = int(dur * FPS)
    for k in range(n):
        t = k / FPS
        im = Image.new('RGB', (W, H), (4, 5, 7)); d = ImageDraw.Draw(im)
        if kind == 'card_open':
            a = ease((t - 0.6) / 1.2) * (1 - ease((t - 3.0) / 1.0))
            f = ImageFont.truetype(SANS, 34); s = '11  ·  03  ·  2011'
            d.text((W / 2 - d.textlength(s, font=f) / 2, H / 2 - 30), s, font=f, fill=tuple(int(c * a) for c in (225, 225, 220)))
            f2 = ImageFont.truetype(SANS, 22); s2 = 'IWATE PREFECTURE, JAPAN'
            d.text((W / 2 - d.textlength(s2, font=f2) / 2, H / 2 + 26), s2, font=f2, fill=tuple(int(c * a) for c in (150, 155, 160)))
        else:
            a = ease((t - 1.0) / 1.8) * (1 - ease((t - (dur - 2.2)) / 1.6))
            f = ImageFont.truetype(SERIF, 92); s = 'THE MIYAKO TRAGEDY'
            track = 10; wdt = sum(d.textlength(c, font=f) + track for c in s) - track; x = W / 2 - wdt / 2
            for c in s:
                d.text((x, H / 2 - 80), c, font=f, fill=tuple(int(v * a) for v in (236, 234, 228))); x += d.textlength(c, font=f) + track
            b = ease((t - 2.4) / 1.4) * (1 - ease((t - (dur - 2.2)) / 1.6))
            d.line([(W / 2 - 60 * b, H / 2 + 34), (W / 2 + 60 * b, H / 2 + 34)], fill=(int(230 * b), int(60 * b), int(45 * b)), width=3)
            f2 = ImageFont.truetype(SERIF, 36); s2 = 'The town erased by the sea in minutes'
            d.text((W / 2 - d.textlength(s2, font=f2) / 2, H / 2 + 58), s2, font=f2, fill=tuple(int(v * b) for v in (170, 172, 175)))
        out.stdin.write(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR).tobytes())
    out.stdin.close(); out.wait(); return path

def render_map(i, dur):
    path = os.path.join(B, f'shot{i:02d}.mp4')
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', os.path.join(B, 'map.mp4'), '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    out = writer(path, dur); last = None
    for k in range(int(dur * FPS)):
        buf = dec.stdout.read(W * H * 3)
        if len(buf) == W * H * 3: last = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        f = last.astype(np.float32) * VIG
        out.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
    dec.stdout.close(); dec.wait(); out.stdin.close(); out.wait(); return path

def main():
    os.makedirs(B, exist_ok=True)
    starts = [s[1] for s in SHOTS] + [END]
    paths = []
    for i, s in enumerate(SHOTS):
        dur = starts[i + 1] - starts[i] + (X if i < len(SHOTS) - 1 else 0)
        print('shot', i, s[0], round(dur, 2), flush=True)
        cached = os.path.join(B, f'shot{i:02d}.mp4')
        if os.path.exists(cached) and os.environ.get('REUSE'): paths.append(cached); continue
        if s[0] == 'clip': paths.append(render_clip(i, *s[2:], dur))
        elif s[0] == 'map': paths.append(render_map(i, dur))
        else: paths.append(render_card(i, s[0], dur))
    # music + narration timings
    subprocess.run([sys.executable, os.path.join(HERE, 'music.py'), str(END), str(T_QUAKE), str(T_IMPACT), str(T_CALM)], check=True)
    lines = json.load(open(os.path.join(B, 'vo', 'lines.json')))
    # ---- ffmpeg: dissolve chain + letterbox + grain, audio mix
    cmd = ['ffmpeg', '-v', 'error', '-y']
    for p in paths: cmd += ['-i', p]
    cmd += ['-i', os.path.join(B, 'music.wav')]; mi = len(paths)
    for l in lines: cmd += ['-i', os.path.join(B, 'vo', f"{l['i']:02d}.wav")]
    vo0 = mi + 1
    clips = [(i, s) for i, s in enumerate(SHOTS) if s[0] == 'clip']
    fa0 = vo0 + len(lines)
    for i, s in clips: cmd += ['-i', os.path.join(SRC, s[2])]
    fg = []; prev = '[0:v]'
    for i in range(1, len(paths)):
        off = starts[i]
        fg.append(f'{prev}[{i}:v]xfade=transition=fade:duration={X}:offset={off:.3f}[v{i}]'); prev = f'[v{i}]'
    fg.append(f'{prev}noise=alls=7:allf=t,drawbox=x=0:y=0:w=iw:h=138:color=black:t=fill,drawbox=x=0:y=ih-138:w=iw:h=138:color=black:t=fill,format=yuv420p[vout]')
    am = [f'[{mi}:a]volume=1.0[mus]']
    for j, l in enumerate(lines):
        d = int(VO_AT[j] * 1000); am.append(f'[{vo0 + j}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,volume=1.9,adelay={d}|{d}[vo{j}]')
    for k, (i, s) in enumerate(clips):
        dur = starts[i + 1] - starts[i] + X; speed = s[4]
        d = int(starts[i] * 1000)
        am.append(f'[{fa0 + k}:a]atrim={s[3]}:{s[3] + dur * speed:.3f},asetpts=PTS-STARTPTS,atempo={speed},aresample=48000,'
                  f'afade=t=in:d=0.6,afade=t=out:st={dur - 0.8:.3f}:d=0.8,volume=0.22,adelay={d}|{d}[fa{k}]')
    # narration ducks the music via sidechain
    vo_all = ''.join(f'[vo{j}]' for j in range(len(lines)))
    am.append(f'{vo_all}amix=inputs={len(lines)}:normalize=0,asplit=2[vomix][vosc]')
    am.append('[mus][vosc]sidechaincompress=threshold=0.05:ratio=4:attack=20:release=600[musd]')
    fa_all = ''.join(f'[fa{k}]' for k in range(len(clips)))
    am.append(f'[musd][vomix]{fa_all}amix=inputs={2 + len(clips)}:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,'
              f'afade=t=out:st={END - 2.5}:d=2.5[aout]')
    cmd += ['-filter_complex', ';'.join(fg + am), '-map', '[vout]', '-map', '[aout]', '-t', str(END),
            '-c:v', 'libx264', '-crf', '23', '-preset', 'slow', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', OUT]
    subprocess.run(cmd, check=True); print('wrote', OUT)

if __name__ == '__main__':
    main()
