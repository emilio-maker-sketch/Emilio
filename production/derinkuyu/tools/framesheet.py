"""Mid-shot and end-of-shot frames of a rendered film, on per-chapter sheets (QC_RULES step 7).  python3 tools/framesheet.py build/FILM.mp4 -> build/framecheck/"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw
B = 'build'; F = sys.argv[1]; OUT = os.path.join(B, 'framecheck'); os.makedirs(OUT, exist_ok=True)
tl = json.load(open(os.path.join(B, 'timeline.json'))); sh = [x for x in tl['items'] if x['type'] == 'shot']
jobs = []
for x in sh:
    jobs.append((x['id'] + '_m', x['start'] + x['dur'] / 2, x['chapter']))
    jobs.append((x['id'] + '_e', x['start'] + x['dur'] - 0.15, x['chapter']))
def grab(j):
    n, t, ch = j; p = os.path.join(OUT, n.replace('#', '_') + '.jpg')
    if not os.path.exists(p):
        subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', F, '-frames:v', '1', '-vf', 'scale=640:-1', '-q:v', '4', p])
    return (n, t, ch, p)
with ThreadPoolExecutor(8) as ex: res = list(ex.map(grab, jobs))
by = {}
for r in res: by.setdefault(r[2], []).append(r)
for ch, rs in by.items():
    for k in range(0, len(rs), 24):
        part = rs[k:k + 24]; c = 4; rows = (len(part) + c - 1) // c; W = Image.new('RGB', (c * 640, rows * 360))
        for i, (n, t, _, p) in enumerate(part):
            if not os.path.exists(p): continue
            im = Image.open(p).convert('RGB'); W.paste(im, ((i % c) * 640, (i // c) * 360))
            m, s = divmod(int(t), 60)
            ImageDraw.Draw(W).text(((i % c) * 640 + 6, (i // c) * 360 + 6), f'{n} {m:02d}:{s:02d}', fill=(255, 255, 0))
        W.save(os.path.join(OUT, f'sheet_{ch}_{k // 24}.jpg'), quality=82)
print(len(res), 'frames', len(by), 'chapters')
