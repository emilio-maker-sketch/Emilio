"""Build the upload package in delivery/the_last_day_of_rome/: description (with chapters), credits, titles, tags, captions, thumbnail."""
import os, json, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(ROOT))
OUT = os.path.join(REPO, 'delivery', 'the_ides_of_march')
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
    chapters = [(0, 'Cold open: the morning of the Ides')]
    for x in tl['items']:
        if x['type'] == 'card': chapters.append((x['start'], nice_title(x['line2'])))
    desc = ["On the Ides of March, 44 BC, Julius Caesar was stabbed to death at a meeting of the Senate by men he had pardoned, promoted and trusted. "
            "They believed they were saving the Roman Republic. Within twenty years it was gone.",
            "",
            "This documentary follows the road to the Ides, from the bloody century before Caesar to the Rubicon, the civil war and the dictatorship, "
            "through the conspiracy and the murder itself, to the funeral, the rise of Octavian and the end at Philippi. Along the way it separates "
            "what the ancient sources actually say from the legends: no 'Et tu, Brute?', no murder on the Capitol.",
            "", "CHAPTERS"]
    desc += [f'{ts(t)} {name}' for t, name in chapters]
    desc += ["", "MAIN SOURCES",
             "Ancient: Julius Caesar, Commentaries; Cicero, Letters and Philippics; Nicolaus of Damascus, Life of Augustus; Suetonius, Life of the Deified Julius; "
             "Plutarch, Lives of Caesar, Brutus, Antony and Cicero; Appian, Civil Wars; Cassius Dio, Roman History.",
             "Modern: Adrian Goldsworthy, Caesar: Life of a Colossus (2006); Barry Strauss, The Death of Caesar (2015); Tom Holland, Rubicon (2003); "
             "Mary Beard, SPQR (2015); Greg Woolf, Et Tu, Brute? (2006).",
             "", "ABOUT THE IMAGES",
             "Reconstructions of people and scenes are artistic interpretations made with AI image and video tools. Narration is a synthetic voice (Kokoro). "
             "Real photographs, ancient sculpture, coins and paintings are credited below.",
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
        'The Ides of March: The Assassination of Julius Caesar | Full Documentary\n'
        'Why They Killed Caesar: The Ides of March, 44 BC\n'
        'The Murder That Ended the Roman Republic: Julius Caesar, 44 BC\n')
    open(os.path.join(OUT, 'tags.txt'), 'w').write(', '.join([
        'julius caesar', 'ides of march', 'assassination of julius caesar', '44 bc', 'roman republic', 'brutus', 'cassius',
        'mark antony', 'octavian', 'augustus', 'rubicon', 'cleopatra', 'ancient rome', 'history documentary', 'roman history',
        'et tu brute', 'battle of philippi', 'ancient world files']) + '\n')
    shutil.copy(os.path.join(B, 'captions.srt'), os.path.join(OUT, 'captions_en.srt'))
    W, H = 1280, 720
    th = Image.open(os.path.join(B, 'gen', 'z_11-03-0.png')).convert('RGB').resize((W, H))
    th = ImageEnhance.Contrast(th).enhance(1.12)
    g = Image.new('L', (W, H), 0); dg = ImageDraw.Draw(g)
    for x in range(W): dg.line([x, 0, x, H], fill=int(max(0, (x - 560) / 720) * 215))
    th = Image.composite(Image.new('RGB', (W, H), (8, 6, 5)), th, g)
    d = ImageDraw.Draw(th)
    f1 = ImageFont.truetype(os.path.join(FONTS, 'Cinzel.ttf'), 92); f2 = ImageFont.truetype(os.path.join(FONTS, 'Cinzel.ttf'), 52)
    for dx, dy in ((4, 4), (0, 0)):
        d.text((1000 + dx, 300 + dy), 'THE IDES', font=f1, fill=(0, 0, 0) if dx else (240, 222, 180), anchor='mm')
        d.text((1000 + dx, 400 + dy), 'OF MARCH', font=f1, fill=(0, 0, 0) if dx else (240, 222, 180), anchor='mm')
    d.text((1000, 490), '44 BC', font=f2, fill=(205, 60, 45), anchor='mm')
    th.save(os.path.join(OUT, 'thumbnail.jpg'), quality=92)
    print('package written to', OUT)

if __name__ == '__main__': main()
