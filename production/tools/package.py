"""Write the YouTube upload package: build/youtube/{description.txt, titles.txt, tags.txt, credits.txt}"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build'); OUT = os.path.join(B, 'youtube'); os.makedirs(OUT, exist_ok=True)

chapters = open(os.path.join(B, 'chapters.txt')).read().strip().splitlines()
chapters = [c for c in chapters if not c.endswith(' Title')]
mplan = json.load(open(os.path.join(ROOT, 'assets', 'music_plan.json')))
tracks = []
for v in mplan.values():
    for t in v:
        if t not in tracks: tracks.append(t)
used = json.load(open(os.path.join(B, 'credits_used.json')))
met = sorted({(c['title'], c.get('artist') or '', c.get('date', ''), c['page']) for c in used.values() if c['source'].startswith('The Met')})
aic = sorted({(c['title'], c.get('artist') or '', c.get('date', ''), c['page']) for c in used.values() if c['source'].startswith('Art Institute')})

titles = """What Really Ended the Bronze Age Was Not What You Were Told
1177 B.C.: The Year Civilization Collapsed (Full Documentary)
The Bronze Age Collapse: When Every Empire Fell at Once
"""

desc = f"""Around 1177 B.C., the most connected world before Rome fell apart in a single lifetime. The Hittite Empire vanished. The palaces of Mycenaean Greece burned. The great port of Ugarit was wiped from the map. Egypt survived, but was broken. And in Greece, writing disappeared for almost 400 years.

For a century the blame fell on the mysterious "Sea Peoples." But pollen cores, tree rings, ancient DNA and the desperate letters of the last kings tell a far stranger story. This is an evidence-based, hour-long journey through the end of the Late Bronze Age: what happened, what we know, and what is still debated.

CHAPTERS
{chr(10).join(chapters)}

KEY SOURCES & FURTHER READING
- Eric H. Cline, 1177 B.C.: The Year Civilization Collapsed (Princeton, revised ed. 2021)
- D. Langgut, I. Finkelstein & T. Litt (2013), Climate and the Late Bronze Collapse: New Evidence from the Southern Levant, Tel Aviv 40
- D. Kaniewski et al. (2013), Environmental Roots of the Late Bronze Age Crisis, PLoS ONE 8(8)
- S. W. Manning et al. (2023), Severe multi-year drought coincident with Hittite collapse around 1198-1196 BC, Nature 614
- M. Feldman et al. (2019), Ancient DNA sheds light on the genetic origins of early Iron Age Philistines, Science Advances 5(7)
- A. Nur & E. H. Cline (2000), Poseidon's Horses: Plate Tectonics and Earthquake Storms in the Late Bronze Age Aegean and Eastern Mediterranean, Journal of Archaeological Science 27
- Z. Hawass et al. (2012), Revisiting the harem conspiracy and death of Ramesses III, BMJ 345
- J. Seeher, Hattusha Guide: A Day in the Hittite Capital
- C. Pulak, The Uluburun Shipwreck: An Overview, International Journal of Nautical Archaeology 27 (1998)
- Translations of the Medinet Habu inscription and Ugarit letters follow standard published translations (e.g. J. A. Wilson in ANET; Cline 2021).

CREDITS
Narration: AI-generated voice (Kokoro TTS).
Images: The Metropolitan Museum of Art (Open Access, CC0) and the Art Institute of Chicago (public domain, CC0). Full list below.
Maps: made for this video with Natural Earth data (public domain).
Music by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0 License, http://creativecommons.org/licenses/by/4.0/
{chr(10).join('  "' + t + '" Kevin MacLeod (incompetech.com)' for t in tracks)}

#BronzeAgeCollapse #AncientHistory #Documentary
"""
open(os.path.join(OUT, 'description.txt'), 'w').write(desc)
open(os.path.join(OUT, 'titles.txt'), 'w').write(titles)
open(os.path.join(OUT, 'tags.txt'), 'w').write(', '.join([
    'Bronze Age collapse', '1177 BC', 'Sea Peoples', 'Late Bronze Age', 'Hittites', 'Mycenaeans', 'Ugarit',
    'Ramesses III', 'Medinet Habu', 'ancient history documentary', 'Eric Cline', 'Uluburun shipwreck',
    'Battle of Kadesh', 'Hattusa', 'ancient Egypt', 'ancient Greece', 'history documentary', 'Ancient World Files']))
with open(os.path.join(OUT, 'credits.txt'), 'w') as f:
    f.write('IMAGE CREDITS (all CC0 / public domain)\n\nThe Metropolitan Museum of Art, Open Access:\n')
    for t, a, d, p in met: f.write(f'- {t}' + (f', {a}' if a else '') + (f' ({d})' if d else '') + f'  {p}\n')
    f.write('\nArt Institute of Chicago, public domain:\n')
    for t, a, d, p in aic: f.write(f'- {t}' + (f', {a}' if a else '') + (f' ({d})' if d else '') + f'  {p}\n')
print('description chars:', len(desc), '| images credited:', len(met) + len(aic))
