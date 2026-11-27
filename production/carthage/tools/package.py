"""Build the upload package in delivery/the_fall_of_carthage/: description (with chapters), credits, titles, tags, captions, thumbnail."""
import os, json, shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(ROOT))
OUT = os.path.join(REPO, 'delivery', 'the_fall_of_carthage')
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
    chapters = [(0, 'Cold open: the last days of Carthage')]
    for x in tl['items']:
        if x['type'] == 'card': chapters.append((x['start'], nice_title(x['line2'])))
    desc = ["In the spring of 146 BC, Roman soldiers fought their way, house by house, up the streets of Carthage. When it was over, the greatest city of the western Mediterranean was a ruin, and its people were sold as slaves.",
            "",
            "This documentary tells the whole story: the Phoenician city founded from Tyre, its harbours and its empire, the wars with Rome over Sicily, "
            "Hannibal's oath, his march over the Alps and his victories at the Trebia, Lake Trasimene and Cannae, Scipio's answer at Zama, "
            "and the half-century of peace that ended with Cato's demand that Carthage must be destroyed. It separates the sources from the legends: "
            "no Romans sowing the ground with salt, and no certain portrait of Hannibal.",
            "", "CHAPTERS"]
    desc += [f'{ts(t)} {name}' for t, name in chapters]
    desc += ["", "MAIN SOURCES",
             "Ancient: Polybius, Histories; Livy, History of Rome 21-30; Appian, Punic Wars; Plutarch, Lives of Cato the Elder and Fabius; Diodorus; Justin; Cornelius Nepos.",
             "Modern: Richard Miles, Carthage Must Be Destroyed (2010); Adrian Goldsworthy, The Fall of Carthage (2000); Dexter Hoyos, Hannibal's Dynasty (2003); "
             "Serge Lancel, Carthage: A History (1995); R. T. Ridley, 'To Be Taken with a Pinch of Salt' (1986).",
             "", "ABOUT THE IMAGES",
             "Reconstructions of people and scenes are artistic interpretations made with AI image and video tools. Narration is a synthetic voice (Kokoro). "
             "Real photographs, ancient sculpture, coins and paintings are credited below.",
             "", "MUSIC", json.load(open(os.path.join(ROOT, 'music.json')))['credit']]
    used = sorted({c['file'].rsplit('.', 1)[0] for c in json.load(open(os.path.join(ROOT, 'music.json')))['cues']})
    desc += ['Tracks: ' + ', '.join(f'"{u}"' for u in used)]
    cr = json.load(open(os.path.join(B, 'photos', 'credits.json')))
    lines = ['IMAGE CREDITS (Wikimedia Commons; full links in the credits file)']; full = ['IMAGE CREDITS (Wikimedia Commons)']
    tl = json.load(open(os.path.join(B, 'timeline.json')))['items']; srcs = {x.get('src', '') for x in tl} | {sd.get('src', '') for x in tl for sd in x.get('sides', [])}
    on_screen = {os.path.splitext(os.path.basename(s_))[0] for s_ in srcs if '/photos/' in s_}   # credit only photos that are actually in the film
    for k, c in sorted(cr.items()):
        if k not in on_screen: continue
        art = ' '.join((c['artist'] or 'unknown').split())
        art = {'Unknown authorUnknown author': 'unknown', 'Horses_of_Basilica_San_Marco.jpg: Tteske derivative work: Morn (talk)': 'Tteske, derivative work by Morn'}.get(art, art)
        full.append(f"- {c['title'][5:].rsplit('.', 1)[0]} · {art} · {c['license']} · {c['page']}")
        lines.append(f"- {c['title'][5:].rsplit('.', 1)[0][:34].rstrip(' ,-(')} · {art[:28].strip()} · {c['license'].replace('Public domain', 'PD')}")
    tail = ['', 'Maps and diagrams: made for this video with Natural Earth data (public domain); borders and positions approximate.', 'Sound effects: synthesized for this video.']
    lines += tail; full += tail
    desc += [''] + lines
    open(os.path.join(OUT, 'description.txt'), 'w').write('\n'.join(desc) + '\n')
    open(os.path.join(OUT, 'credits.txt'), 'w').write('\n'.join(full) + '\n')
    n = len('\n'.join(desc)); print('description', n, 'chars'); assert n < 5000, 'description too long for YouTube'
    open(os.path.join(OUT, 'titles.txt'), 'w').write(
        "Carthage Must Be Destroyed: The Fall of Rome's Greatest Rival | Full Documentary\n"
        "Hannibal, Rome and the Destruction of Carthage (146 BC) | Full Documentary\n"
        "Why Rome Wiped Carthage Off the Map: The Punic Wars\n")
    open(os.path.join(OUT, 'tags.txt'), 'w').write(', '.join([
        'carthage', 'fall of carthage', 'punic wars', 'hannibal', 'hannibal barca', 'scipio africanus', 'battle of cannae', 'battle of zama',
        'carthago delenda est', 'ancient rome', 'roman republic', 'third punic war', '146 bc', 'phoenicians', 'history documentary', 'ancient history',
        'hannibal crossing the alps', 'ancient world files']) + '\n')
    shutil.copy(os.path.join(B, 'captions.srt'), os.path.join(OUT, 'captions_en.srt'))
    W, H = 1280, 720
    th = Image.open(os.path.join(B, 'gen', 'z_00-03-0.png')).convert('RGB').resize((W, H))
    th = ImageEnhance.Contrast(th).enhance(1.12)
    g = Image.new('L', (W, H), 0); dg = ImageDraw.Draw(g)
    for x in range(W): dg.line([x, 0, x, H], fill=int(max(0, (720 - x) / 720) * 225))
    th = Image.composite(Image.new('RGB', (W, H), (8, 6, 5)), th, g)
    d = ImageDraw.Draw(th)
    f1 = ImageFont.truetype(os.path.join(FONTS, 'Cinzel.ttf'), 92); f2 = ImageFont.truetype(os.path.join(FONTS, 'Cinzel.ttf'), 52)
    for dx, dy in ((4, 4), (0, 0)):
        d.text((330 + dx, 270 + dy), 'CARTHAGE', font=f1, fill=(0, 0, 0) if dx else (240, 222, 180), anchor='mm')
        d.text((330 + dx, 370 + dy), 'MUST BE', font=f2, fill=(0, 0, 0) if dx else (240, 222, 180), anchor='mm')
        d.text((330 + dx, 460 + dy), 'DESTROYED', font=f1, fill=(0, 0, 0) if dx else (205, 60, 45), anchor='mm')
    d.text((330, 560), '146 BC', font=f2, fill=(220, 200, 160), anchor='mm')
    th.save(os.path.join(OUT, 'thumbnail.jpg'), quality=92)
    print('package written to', OUT)

if __name__ == '__main__': main()
