"""YouTube delivery text: title options, description with chapter timestamps (from rendered chapter lengths), tags, credits."""
import glob, json, os, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, 'build'); D = os.path.join(ROOT, 'delivery')
os.makedirs(D, exist_ok=True)
NAMES = ['Intro', 'The City', 'The Warnings', 'The Seventh Hour', 'The Admiral', 'Night of Fire', 'The Last Morning', 'Buried and Found', 'What the Ash Remembers']

def dur(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True).stdout)

def ts(s):
    s = int(s); return f'{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}' if s >= 3600 else f'{s // 60}:{s % 60:02d}'

chs = sorted(p for p in glob.glob(os.path.join(B, 'chapters', '0[0-8]_*.mp4')) if 'preview' not in p)
t, stamps = 0.0, []
for p, n in zip(chs, NAMES):
    stamps.append(f'{ts(t)} {n}'); t += dur(p)

lib = json.load(open(os.path.join(B, 'img', 'library.json')))
used = {f for fs in lib['themes'].values() for f in fs if not f.startswith('fx:')}
by_src = {}
for f in sorted(used):
    m = lib['meta'].get(f)
    if m: by_src.setdefault(m['source'], []).append(m)

desc = f"""On an ordinary autumn day in AD 79, Mount Vesuvius tore itself open. In less than 24 hours, Pompeii, Herculaneum, Stabiae and Oplontis were buried, and thousands of people were dead. For seventeen centuries, the world forgot they had ever existed.

This is the full story of the last days of Pompeii: the city at its height, the earthquake that warned of what was coming, the admiral Pliny the Elder who sailed into the eruption, the night the burning surges reached Herculaneum, the last morning in Pompeii, and the young Pliny who survived to write the only eyewitness account. Then the rediscovery, the plaster casts, and what DNA and AI are revealing today.

CHAPTERS
""" + '\n'.join(stamps) + """

SOURCES
• Pliny the Younger, Letters 6.16 and 6.20 (quotations from the public-domain translation by William Melmoth, rev. W.M.L. Hutchinson)
• Seneca, Natural Questions, Book 6 (the earthquake of AD 62)
• Strabo, Geography 5.4.8; Suetonius, Life of Titus 8; Cassius Dio 66
• Sigurdsson, Cashdollar & Sparks (1982), The Eruption of Vesuvius in A.D. 79
• Pilli et al. (2024), Current Biology — ancient DNA from the Pompeii casts
• Vesuvius Challenge (2023–24) — reading the Herculaneum scrolls

IMAGE CREDITS
Artworks and photographs courtesy of The Metropolitan Museum of Art (Open Access, CC0), the Art Institute of Chicago (CC0) and Wikimedia Commons. Full list: see credits.txt / pinned comment.
Maps: Natural Earth (public domain). Music: original score. Narration: AI voice.

#Pompeii #Vesuvius #AncientHistory #Documentary #WorldAncientDisasters"""
open(os.path.join(D, 'description.txt'), 'w').write(desc)

cred = ['IMAGE CREDITS — World Ancient Disasters, Episode 1: The Last Days of Pompeii', '']
for src, ms in by_src.items():
    cred.append(f'== {src} ==')
    for m in ms: cred.append(f"{m['title']} — {m['artist']} ({m['license']}) {m['page']}")
    cred.append('')
open(os.path.join(D, 'credits.txt'), 'w').write('\n'.join(cred))

titles = ['The Last Days of Pompeii: The City Erased in One Day (Full Documentary)',
          'Pompeii: The 24 Hours That Buried a Roman City | Full Documentary',
          'How Vesuvius Wiped Out Pompeii — and Preserved It Forever',
          'The Eyewitness: Pliny and the Destruction of Pompeii (AD 79)']
tags = 'Pompeii, Vesuvius, AD 79, Herculaneum, Pliny the Younger, Pliny the Elder, ancient Rome, Roman history, volcano, eruption, ancient disasters, history documentary, plaster casts, Stabiae, Vesuvius Challenge, World Ancient Disasters'
open(os.path.join(D, 'titles_and_tags.txt'), 'w').write('TITLE OPTIONS\n' + '\n'.join('• ' + x for x in titles) + '\n\nTAGS\n' + tags + '\n')
print('\n'.join(stamps)); print('total', ts(t))
