"""Contact sheets of the museum catalog for manual curation: build/img/sheets/<n>.jpg with global indices."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, 'build', 'img')
cat = json.load(open(os.path.join(B, 'museum_catalog.json')))
seen, items = set(), []
for q, ents in cat.items():
    for e in ents:
        if e['file'] in seen: continue
        seen.add(e['file']); items.append((q, e))
json.dump([{'i': i, 'q': q, **e} for i, (q, e) in enumerate(items)], open(os.path.join(B, 'index.json'), 'w'), indent=1, ensure_ascii=False)
os.makedirs(os.path.join(B, 'sheets'), exist_ok=True)
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
C, R, cw, chh = 8, 5, 300, 220
for s in range(0, len(items), C * R):
    sheet = Image.new('RGB', (C * cw, R * chh), (20, 20, 20)); d = ImageDraw.Draw(sheet)
    for k, (q, e) in enumerate(items[s:s + C * R]):
        im = Image.open(os.path.join(B, 'pool', e['file'])); im.thumbnail((cw - 6, chh - 6))
        x, y = (k % C) * cw, (k // C) * chh; sheet.paste(im, (x + 3, y + 3))
        d.rectangle([x + 3, y + 3, x + 62, y + 30], fill=(0, 0, 0)); d.text((x + 6, y + 4), str(s + k), font=f, fill=(255, 230, 0))
    sheet.save(os.path.join(B, 'sheets', f'{s // (C * R):02d}.jpg'), quality=80)
print(len(items), 'items')
