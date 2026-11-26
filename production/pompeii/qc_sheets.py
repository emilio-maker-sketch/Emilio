"""Dense QC: one contact sheet per minute, a frame every 2 s, each captioned with the narration spoken at that moment.
Review EVERY sheet before delivery: does each picture match the words under it, and is every image whole and readable?
usage: python3 qc_sheets.py video.mp4 captions.srt outdir [step=2]"""
import sys, os, re, subprocess
from PIL import Image, ImageDraw, ImageFont

video, srt, out = sys.argv[1:4]; step = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
os.makedirs(out, exist_ok=True)
ts = lambda s: sum(float(x) * m for x, m in zip(re.split('[:,]', s), (3600, 60, 1, .001)))
subs = []
for blk in open(srt, encoding='utf-8').read().strip().split('\n\n'):
    ln = blk.strip().split('\n')
    if len(ln) >= 3 and '-->' in ln[1]:
        a, b = [ts(x.strip()) for x in ln[1].split('-->')]; subs.append((a, b, ' '.join(ln[2:])))
said = lambda t: next((s for a, b, s in subs if a <= t < b), '')
dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video]))
fnt = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
TW, TH, COLS = 384, 216, 5
for m in range(int(dur // 60) + 1):
    times = [m * 60 + k * step for k in range(int(60 / step)) if m * 60 + k * step < dur]
    if not times: break
    rows = (len(times) + COLS - 1) // COLS
    sheet = Image.new('RGB', (COLS * TW, rows * (TH + 52)), (20, 20, 20)); d = ImageDraw.Draw(sheet)
    for i, t in enumerate(times):
        fp = os.path.join(out, '_f%d.jpg' % os.getpid())
        if os.path.exists(fp): os.remove(fp)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(t), '-i', video, '-frames:v', '1', '-vf', f'scale={TW}:{TH}', fp])
        x, y = (i % COLS) * TW, (i // COLS) * (TH + 52)
        if os.path.exists(fp) and os.path.getsize(fp): sheet.paste(Image.open(fp), (x, y))
        d.text((x + 4, y + 2), '%d:%04.1f' % (t // 60, t % 60), font=fnt, fill=(255, 230, 0))
        txt = said(t); words, lines, cur = txt.split(), [], ''
        for w in words:
            if d.textlength(cur + ' ' + w, font=fnt) > TW - 8: lines.append(cur); cur = w
            else: cur = (cur + ' ' + w).strip()
        lines.append(cur)
        for j, l in enumerate(lines[:3]): d.text((x + 4, y + TH + 2 + 16 * j), l, font=fnt, fill=(220, 220, 220))
    sheet.save(os.path.join(out, 'min%02d.jpg' % m), quality=85)
    print('min%02d' % m)
