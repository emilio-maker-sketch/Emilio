"""Full-size check sheets of every AI image on the timeline: four per sheet, each 1400 x 788 (QC_RULES: post-render AI re-check).

  python3 tools/aisheet.py   ->  build/aicheck/ai_NN.jpg
"""
import json, os
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, 'build'); OUT = os.path.join(B, 'aicheck')
os.makedirs(OUT, exist_ok=True)
tl = json.load(open(os.path.join(B, 'timeline.json'))); srcs = []
for x in tl['items']:
    for s in [x.get('src', '')] * (x.get('type') == 'shot' and not x.get('beat')) + [sd['src'] for sd in x.get('sides', [])]:
        if '/gen/' in s and s not in srcs: srcs.append(s)
for k in range(0, len(srcs), 4):
    W = Image.new('RGB', (2800, 1576))
    for i, s in enumerate(srcs[k:k + 4]):
        W.paste(Image.open(s).convert('RGB').resize((1400, 788)), ((i % 2) * 1400, (i // 2) * 788))
        ImageDraw.Draw(W).text(((i % 2) * 1400 + 8, (i // 2) * 788 + 8), os.path.basename(s), fill=(255, 255, 0))
    W.save(os.path.join(OUT, f'ai_{k // 4:02d}.jpg'), quality=85)
print(len(srcs), 'AI images on', (len(srcs) + 3) // 4, 'sheets in', OUT)
