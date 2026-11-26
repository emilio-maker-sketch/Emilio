"""Build the upload package in delivery/the_last_day_of_rome/: description (with chapters), credits, titles, tags, captions, thumbnail."""
import os, json, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(ROOT))
OUT = os.path.join(REPO, 'delivery', 'the_last_day_of_rome')
B = os.path.join(ROOT, 'build')
FONTS = os.path.join(ROOT, '..', 'assets', 'fonts')

SMALL = {'a', 'an', 'and', 'of', 'the', 'over', 'in', 'on', 'to', 'at', 'for'}
def nice_title(t):
    w = t.lower().split()
    cap = lambda x: '-'.join(p[:1].upper() + p[1:] for p in x.split('-'))
    return ' '.join(x if (i and x in SMALL) else cap(x) for i, x in enumerate(w))

def ts(t): m, s = divmod(int(t), 60); h, m = divmod(m, 60); return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'

def main():
    os.makedirs(OUT, exist_ok=True)
    tl = json.load(open(os.path.join(B, 'timeline.json')))
    chapters = [(0, 'Cold open: the last night')]
    for x in tl['items']:
        if x['type'] == 'card': chapters.append((x['start'], nice_title(x['line2'])))
    desc = ["On 29 May 1453, after a siege of fifty-three days, Constantinople fell to the army of the 21-year-old Ottoman sultan Mehmed II. "
            "With it ended the Roman Empire, a state that traced an unbroken history back almost fifteen centuries to Augustus.",
            "",
            "This documentary follows the siege from the building of the fortress that cut the Bosphorus to the final assault, "
            "and tells you where the sources agree, where they disagree, and which famous stories rest on a single chronicler.",
            "", "CHAPTERS"]
    desc += [f'{ts(t)} {name}' for t, name in chapters]
    desc += ["", "MAIN SOURCES",
             "Primary: Nicolò Barbaro, Diary of the Siege; Leonard of Chios, letter to Pope Nicholas V; George Sphrantzes, Chronicle (Minus); "
             "Doukas, Historia; Kritoboulos of Imbros, History of Mehmed the Conqueror; Laonikos Chalkokondyles, Histories; Tursun Beg, Tarih-i Ebu'l-Feth.",
             "Modern: Steven Runciman, The Fall of Constantinople 1453 (1965); Donald M. Nicol, The Immortal Emperor (1992); "
             "Roger Crowley, Constantinople: The Last Great Siege (2005); Marios Philippides & Walter K. Hanak, The Siege and the Fall of Constantinople in 1453 (2011).",
             "", "ABOUT THE IMAGES",
             "Reconstructions of people and scenes are artistic interpretations made with AI image tools; no authentic portrait of Constantine XI survives. "
             "Narration is a synthetic voice (Kokoro). Real photographs, museum objects and period art are credited below.",
             "", "MUSIC", json.load(open(os.path.join(ROOT, 'music.json')))['credit']]
    used = sorted({c['file'].rsplit('.', 1)[0] for c in json.load(open(os.path.join(ROOT, 'music.json')))['cues']})
    desc += ['Tracks: ' + ', '.join(f'"{u}"' for u in used)]
    cr = json.load(open(os.path.join(B, 'photos', 'credits.json')))
    lines = ['IMAGE CREDITS (Wikimedia Commons)']
    for k, c in sorted(cr.items()):
        if not os.path.exists(os.path.join(B, 'photos', k + '.jpg')) and not os.path.exists(os.path.join(B, 'photos', k + '.png')): continue
        art = ' '.join((c['artist'] or 'unknown').split())
        art = {'Unknown authorUnknown author': 'unknown', 'Horses_of_Basilica_San_Marco.jpg: Tteske derivative work: Morn (talk)': 'Tteske, derivative work by Morn'}.get(art, art)
        lines.append(f"- {c['title'][5:].rsplit('.', 1)[0]} · {art} · {c['license']} · {c['page']}")
    lines += ['', 'Maps: made for this video with Natural Earth data (public domain).',
              'Sound effects: synthesized for this video.']
    desc += [''] + lines
    open(os.path.join(OUT, 'description.txt'), 'w').write('\n'.join(desc) + '\n')
    open(os.path.join(OUT, 'credits.txt'), 'w').write('\n'.join(lines) + '\n')
    open(os.path.join(OUT, 'titles.txt'), 'w').write(
        'The Last Day of Rome: The Fall of Constantinople (1453) | Full Documentary\n'
        '53 Days: How Constantinople Fell in 1453\n'
        'The End of the Roman Empire: The Siege of Constantinople, 1453\n')
    open(os.path.join(OUT, 'tags.txt'), 'w').write(', '.join([
        'fall of constantinople', '1453', 'siege of constantinople', 'byzantine empire', 'mehmed ii', 'mehmed the conqueror',
        'constantine xi', 'ottoman empire', 'theodosian walls', 'hagia sophia', 'history documentary', 'medieval history',
        'end of the roman empire', 'giustiniani', 'orban cannon', 'ancient world files']) + '\n')
    shutil.copy(os.path.join(B, 'captions.srt'), os.path.join(OUT, 'captions_en.srt'))
    # thumbnail: emperor vs sultan split with title
    a = Image.open(os.path.join(B, 'gen', 'z_11-07-0.png')).convert('RGB'); b = Image.open(os.path.join(B, 'gen', 'z_00-01-2.png')).convert('RGB')
    W, H = 1280, 720; th = Image.new('RGB', (W, H))
    th.paste(a.resize((1024, 576)).crop((260, 0, 772, 576)).resize((640, 720)), (0, 0))
    th.paste(b.resize((1024, 576)).crop((330, 0, 842, 576)).resize((640, 720)), (640, 0))
    th = ImageEnhance.Contrast(th).enhance(1.15)
    g = Image.new('L', (W, H), 0); dg = ImageDraw.Draw(g)
    for y in range(H): dg.line([0, y, W, y], fill=int(max(0, (y - 380) / 340) * 235))
    th = Image.composite(Image.new('RGB', (W, H), (0, 0, 0)), th, g)
    d = ImageDraw.Draw(th)
    d.line([640, 0, 640, H], fill=(10, 8, 6), width=6)
    f1 = ImageFont.truetype(os.path.join(FONTS, 'Cinzel.ttf'), 96); f2 = ImageFont.truetype(os.path.join(FONTS, 'Cinzel.ttf'), 46)
    for dx, dy in ((4, 4), (0, 0)):
        d.text((W / 2 + dx, 560 + dy), 'THE LAST DAY OF ROME', font=f1, fill=(0, 0, 0) if dx else (240, 222, 180), anchor='mm')
    d.text((W / 2, 650), '1453', font=f2, fill=(205, 70, 50), anchor='mm')
    th.save(os.path.join(OUT, 'thumbnail.jpg'), quality=92)
    print('package written to', OUT)

if __name__ == '__main__': main()
