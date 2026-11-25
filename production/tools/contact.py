"""Contact sheets of museum topic pools for visual review: build/review/<topic>_<n>.jpg"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'build', 'images'); OUT = os.path.join(ROOT, 'build', 'review'); os.makedirs(OUT, exist_ok=True)
db = {}
for f in ('museum.json', 'aic.json'):
    p = os.path.join(IMG, f)
    if os.path.exists(p): db.update(json.load(open(p)))
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
TW, TH, COLS, PER = 300, 210, 6, 36
for topic in (sys.argv[1:] or db):
    recs = db[topic]
    for s in range(0, len(recs), PER):
        chunk = recs[s:s + PER]; rows = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new('RGB', (COLS * TW, rows * (TH + 34)), (20, 20, 20)); d = ImageDraw.Draw(sheet)
        for k, r in enumerate(chunk):
            x, y = (k % COLS) * TW, (k // COLS) * (TH + 34)
            try:
                im = Image.open(os.path.join(IMG, r['file'])); im.draft('RGB', (TW * 2, TH * 2)); im = im.convert('RGB'); im.thumbnail((TW - 6, TH - 6))
                sheet.paste(im, (x + (TW - im.width) // 2, y + (TH - im.height) // 2))
                lab = f"{r['id']} {im.width}x{im.height}"
            except Exception as e:
                lab = f"{r['id']} BROKEN"
            d.text((x + 3, y + TH), lab, font=F, fill=(255, 220, 120))
            d.text((x + 3, y + TH + 16), (r['title'] or '')[:40], font=F, fill=(220, 220, 220))
        sheet.save(os.path.join(OUT, f'{topic}_{s // PER}.jpg'), quality=80)
    print(topic, len(recs))
