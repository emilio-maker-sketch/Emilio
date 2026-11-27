"""3D frames -> build/sample/tablet3d.mp4 with the on-screen label bar, vignette and grain."""
import os, subprocess, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
W, H = 1920, 1080; FR = 'three/frames'; os.makedirs('build/sample', exist_ok=True)
F = ImageFont.truetype('/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf', 22)
def lab(t):
    if t < 11: return '3D RECONSTRUCTION (ILLUSTRATIVE)  ·  A SCRIBE PRESSES WEDGES INTO CLAY', 0
    if t < 18: return '3D RECONSTRUCTION (ILLUSTRATIVE)  ·  612 B.C.  ·  FIRE AND COLLAPSE', 11
    return '3D RECONSTRUCTION (ILLUSTRATIVE)  ·  TODAY  ·  FRAGMENTS MATCHED AND JOINED; ONE STILL MISSING', 18
yy, xx = np.mgrid[:H, :W]; vig = (1 - .5*np.clip(((xx-W/2)/(W*.6))**2 + ((yy-H/2)/(H*.6))**2, 0, 1))[..., None].astype(np.float32)
rg = np.random.default_rng(3); grains = [rg.normal(0, 5, (H, W, 1)).astype(np.float32) for _ in range(5)]
ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                       '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', 'build/sample/tablet3d.mp4'], stdin=subprocess.PIPE)
for i in range(900):
    t = i / 30; im = np.asarray(Image.open(f'{FR}/f{i:04d}.jpg').convert('RGB')).astype(np.float32)
    im = np.clip(im * vig + grains[i % 5], 0, 255).astype(np.uint8)
    pil = Image.fromarray(im); d = ImageDraw.Draw(pil); text, t0 = lab(t)
    n = int(max(0, t - t0 - .3) * 70); s = text[:n]
    if s:
        x, y = 70, H - 92; w = d.textlength(s, font=F)
        d.rectangle([x - 14, y - 10, x + w + 14, y + 34], fill=(10, 10, 10)); d.rectangle([x - 14, y - 10, x - 8, y + 34], fill=(208, 49, 45))
        d.text((x, y), s, font=F, fill=(232, 226, 212))
    ff.stdin.write(pil.tobytes())
ff.stdin.close(); ff.wait(); print('3D clip done')
