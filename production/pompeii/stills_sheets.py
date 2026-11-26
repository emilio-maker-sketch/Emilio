"""Tile build/stills/*.jpg into captioned review sheets (each frame + the line being spoken)."""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
TL = json.load(open('build/timeline.json')); S = TL['sentences']
fs = sorted(os.listdir('build/stills'), key=lambda f: float(f[:-4]))
out = sys.argv[1] if len(sys.argv) > 1 else 'build/stills_qc'; os.makedirs(out, exist_ok=True)
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15); FB = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', 17)
tw, th, cap = 384, 216, 54; cols, per = 5, 30
def line(t):
    for s in S:
        if s['start'] - .1 <= t <= s['end'] + .5: return s['text']
    return ''
def wrap(d, txt, w):
    words, lines, cur = txt.split(), [], ''
    for x in words:
        if d.textlength((cur + ' ' + x).strip(), font=F) > w: lines.append(cur); cur = x
        else: cur = (cur + ' ' + x).strip()
    return (lines + [cur])[:3]
for k in range(0, len(fs), per):
    sub = fs[k:k + per]; rows = (len(sub) + cols - 1) // cols
    sh = Image.new('RGB', (cols * tw, rows * (th + cap)), (24, 24, 24)); d = ImageDraw.Draw(sh)
    for i, f in enumerate(sub):
        t = float(f[:-4]); x, y = (i % cols) * tw, (i // cols) * (th + cap)
        sh.paste(Image.open(os.path.join('build/stills', f)).resize((tw, th)), (x, y))
        d.text((x + 4, y + 3), f'{int(t // 60)}:{t % 60:04.1f}', font=FB, fill=(255, 220, 0))
        for j, l in enumerate(wrap(d, line(t), tw - 8)): d.text((x + 4, y + th + 2 + 17 * j), l, font=F, fill=(230, 230, 230))
    sh.save(os.path.join(out, f'sheet{k // per:02d}.jpg'), quality=82)
print(len(fs), 'stills ->', out)
