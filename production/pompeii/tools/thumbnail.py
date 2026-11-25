"""YouTube thumbnail (1280x720) from Bryullov's The Last Day of Pompeii (public domain)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
W, H = 1280, 720
im = Image.open('build/img/pool/wm_ec39e0c79c85.jpg').convert('RGB')
w, h = im.size; s = max(W / w, H / h) * 1.35
im = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
x0 = im.width - W; y0 = int(im.height * 0.05); im = im.crop((x0, y0, x0 + W, y0 + H))
a = np.asarray(im).astype(np.float32) / 255
g = a.mean(2, keepdims=True); a = g + (a - g) * 0.85
a = np.clip((a - 0.5) * 1.2 + 0.45, 0, 1); a[..., 0] *= 1.08; a[..., 2] *= 0.85
xx = np.mgrid[0:H, 0:W][1]
a = np.clip(a * (1 - 0.6 * np.clip(1 - xx / (W * 0.55), 0, 1))[..., None], 0, 1)
im = Image.fromarray((a * 255).astype(np.uint8)); d = ImageDraw.Draw(im)
f1 = ImageFont.truetype('/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf', 150)
f2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 46)
f3 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
def st(xy, s, f, fill, sh=6):
    d.text((xy[0] + sh, xy[1] + sh), s, font=f, fill=(0, 0, 0)); d.text(xy, s, font=f, fill=fill)
st((54, 200), 'POMPEII', f1, (245, 236, 220)); d.rectangle([60, 372, 330, 380], fill=(220, 60, 40))
st((58, 400), 'ERASED IN', f2, (245, 236, 220), 4); st((58, 456), 'ONE DAY', f2, (255, 120, 60), 4)
st((60, 640), 'WORLD ANCIENT DISASTERS', f3, (220, 210, 195), 3)
im.save('delivery/thumbnail.jpg', quality=92)
