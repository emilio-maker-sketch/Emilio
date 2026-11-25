"""Per-chapter storyboard of chosen stills: build/review/story_<chapter>.jpg"""
import json, os
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build'); IMG = os.path.join(B, 'images')
tl = json.load(open(os.path.join(B, 'timeline.json')))
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
by = {}
for s in tl['shots']:
    if s['kind'] == 'image': by.setdefault(s['chapter'], []).append(s)
cred = json.load(open(os.path.join(B, 'credits_used.json')))
TW, TH, C = 240, 150, 8
for ch, shots in by.items():
    rows = (len(shots) + C - 1) // C
    sheet = Image.new('RGB', (C * TW, rows * (TH + 30)), (18, 18, 18)); d = ImageDraw.Draw(sheet)
    for k, s in enumerate(shots):
        x, y = (k % C) * TW, (k // C) * (TH + 30)
        im = Image.open(os.path.join(IMG, s['src'])); im.draft('RGB', (TW * 2, TH * 2)); im = im.convert('RGB'); im.thumbnail((TW - 6, TH - 6))
        sheet.paste(im, (x + (TW - im.width) // 2, y + (TH - im.height) // 2))
        m, sec = divmod(int(s['start']), 60)
        c = cred.get(s['src']); idd = os.path.basename(s['src'])[:-4]
        d.text((x + 3, y + TH), f"{m}:{sec:02d} {idd}", font=F, fill=(255, 220, 120))
        d.text((x + 3, y + TH + 14), ((c or {}).get('title') or idd)[:34], font=F, fill=(220, 220, 220))
    sheet.save(os.path.join(B, 'review', f'story_{ch}.jpg'), quality=78)
print('ok', {k: len(v) for k, v in by.items()})
