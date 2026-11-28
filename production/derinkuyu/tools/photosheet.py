"""Full-size check sheets of downloaded photos with a 10x10 grid for marking the subject point.
python3 tools/photosheet.py [start] [count]  ->  build/photocheck/p_NN.jpg (two per sheet, 1400 px wide each)"""
import os, sys, json
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); P = os.path.join(ROOT, 'build', 'photos'); OUT = os.path.join(ROOT, 'build', 'photocheck')
os.makedirs(OUT, exist_ok=True)
fs = sorted(f for f in os.listdir(P) if f.endswith(('.jpg', '.png')))
s0 = int(sys.argv[1]) if len(sys.argv) > 1 else 0; n = int(sys.argv[2]) if len(sys.argv) > 2 else len(fs)
fs = fs[s0:s0 + n]
for k in range(0, len(fs), 2):
    tiles = []
    for f in fs[k:k + 2]:
        im = Image.open(os.path.join(P, f)).convert('RGB'); w0 = im.size[0]; im.thumbnail((1400, 1000)); d = ImageDraw.Draw(im)
        for i in range(1, 10):
            d.line([(im.width * i / 10, 0), (im.width * i / 10, im.height)], fill=(255, 255, 0), width=1)
            d.line([(0, im.height * i / 10), (im.width, im.height * i / 10)], fill=(255, 255, 0), width=1)
            d.text((im.width * i / 10 + 2, 2), str(i), fill=(255, 255, 0)); d.text((2, im.height * i / 10 + 2), str(i), fill=(255, 255, 0))
        d.rectangle([0, im.height - 22, 700, im.height], fill=(0, 0, 0)); d.text((4, im.height - 18), f'{f}  ({w0} px)', fill=(255, 255, 255))
        tiles.append(im)
    W = Image.new('RGB', (sum(t.width for t in tiles), max(t.height for t in tiles)), (20, 20, 20)); x = 0
    for t in tiles: W.paste(t, (x, 0)); x += t.width
    W.save(os.path.join(OUT, f'p_{(s0 + k) // 2:03d}.jpg'), quality=85)
print(len(fs), 'photos')
