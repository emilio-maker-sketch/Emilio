"""Contact sheet with a 4x3 grid (columns a-d, rows 1-3) on every image, for marking subjects: python3 tools/gridsheet.py OUT.jpg files..."""
import sys, os
from PIL import Image, ImageDraw
out, fs = sys.argv[1], sys.argv[2:]; c = 4; r = (len(fs) + c - 1) // c; TW, TH = 480, 270
S = Image.new('RGB', (c * TW, r * (TH + 18)), (0, 0, 0)); d = ImageDraw.Draw(S)
for i, f in enumerate(fs):
    im = Image.open(f).convert('RGB'); im = im.resize((TW, TH)); x, y = (i % c) * TW, (i // c) * (TH + 18)
    S.paste(im, (x, y + 18)); d.text((x + 4, y + 3), os.path.basename(f), fill=(255, 255, 0))
    for k in range(1, 4): d.line([x + k * TW // 4, y + 18, x + k * TW // 4, y + 18 + TH], fill=(0, 255, 255), width=1)
    for k in range(1, 3): d.line([x, y + 18 + k * TH // 3, x + TW, y + 18 + k * TH // 3], fill=(0, 255, 255), width=1)
    for a in range(4):
        for b in range(3): d.text((x + a * TW // 4 + 3, y + 20 + b * TH // 3), 'abcd'[a] + str(b + 1), fill=(0, 255, 255))
S.save(out, quality=82)
