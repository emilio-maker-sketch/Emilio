"""YouTube thumbnails (1280x720) for the documentary."""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'build', 'images'); OUT = os.path.join(ROOT, 'build', 'thumbs'); os.makedirs(OUT, exist_ok=True)
F = lambda n, s: ImageFont.truetype(os.path.join(ROOT, 'assets', 'fonts', n), s)
W, H = 1280, 720

def cover(im, w, h, fx=0.5, fy=0.5):
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s + 1), int(im.height * s + 1)), Image.LANCZOS)
    x = int((im.width - w) * fx); y = int((im.height - h) * fy); return im.crop((x, y, x + w, y + h))

def grade(im, warm=1.0):
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
    lum = a.mean(axis=2, keepdims=True)
    tint = np.array([1.0, 0.62, 0.30]) * warm + (1 - warm)          # ember orange
    out = (lum ** 1.9) * tint * 1.25
    out = np.clip(out, 0, 1)
    yy, xx = np.mgrid[0:im.height, 0:im.width]
    r = np.sqrt(((xx - im.width * 0.62) / im.width) ** 2 + ((yy - im.height * 0.45) / im.height) ** 2)
    out *= np.clip(1.25 - r * 1.3, 0.15, 1)[..., None]
    return Image.fromarray((out * 255).astype(np.uint8))

def text(d, xy, s, font, fill, stroke=6, anchor='la'):
    d.text(xy, s, font=font, fill=fill, stroke_width=stroke, stroke_fill=(10, 6, 2), anchor=anchor)

def make(name, bg_rel, fx=0.5, fy=0.5, line1='1177 B.C.', line2='THE YEAR', line3='CIVILIZATION FELL'):
    bg = cover(Image.open(os.path.join(IMG, bg_rel)), W, H, fx, fy)
    im = grade(bg)
    # dark band for text on the left
    band = Image.new('L', (W, H), 0); bd = ImageDraw.Draw(band)
    for x in range(W):
        bd.line([(x, 0), (x, H)], fill=int(max(0, min(235, 300 * (1 - x / (W * 0.72))))))
    im = Image.composite(Image.new('RGB', (W, H), (8, 5, 3)), im, band)
    d = ImageDraw.Draw(im)
    text(d, (52, 70), line1, F('Cinzel.ttf', 190), (244, 196, 98), stroke=8)
    text(d, (60, 330), line2, F('Cinzel.ttf', 74), (250, 244, 232))
    text(d, (60, 420), line3, F('Cinzel.ttf', 74), (250, 244, 232))
    d.line([(64, 535), (520, 535)], fill=(244, 196, 98), width=5)
    text(d, (62, 560), 'THE BRONZE AGE COLLAPSE', F('Cinzel.ttf', 40), (230, 200, 150), stroke=4)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    p = os.path.join(OUT, name + '.jpg'); im.save(p, quality=92); print(p)

if __name__ == '__main__':
    make('thumb_a', sys.argv[1] if len(sys.argv) > 1 else 'museum/egypt_photos/met261832.jpg', 0.6, 0.5)
    if len(sys.argv) > 2: make('thumb_b', sys.argv[2], 0.5, 0.5)
