"""Asset catalogue with historical eligibility rules.

A visual may only be suggested or used if it is historically appropriate for the film:
  * an ancient object must fall inside the project's era window AND belong to one of its cultures;
  * a document of the place (photograph, print, painting, map) must name one of the project's places in its title;
  * anything else (a 19th-century American portrait that happened to match a search word) is rejected.
Relevance for a sentence = CLIP specificity (z) + a metadata bonus when the record's title/culture shares words with the
narration (names of people, places, objects).
"""
import os, re, json, glob
import textmatch as TM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = r'photograph|albumen|salted paper|gelatin|print|oil on|watercolor|engraving|lithograph|etching|drawing|gouache|daguerreotype|map|plan'


def records():
    out = {}
    for f in glob.glob(os.path.join(ROOT, 'build', 'images', 'museum.json')):
        for topic, recs in json.load(open(f)).items():
            for r in recs: out.setdefault(r['id'], dict(r, topic=topic))
    return out


def year_of(rec):
    d = ' '.join(str(rec.get(k) or '') for k in ('date', 'period'))
    m = re.search(r'(\d{1,4})(?:st|nd|rd|th)?\s*(century)?\s*(BCE|B\.C\.|BC|CE|A\.D\.|AD)?', d)
    if not m: return None
    v = int(m.group(1)); bc = bool(m.group(3) and 'B' in m.group(3))
    if m.group(2): v = v * 100 - 50
    return -v if bc else v


def is_document(rec):
    return bool(re.search(DOC, (rec.get('medium', '') + ' ' + rec.get('title', '')).lower()))


def eligible(rec, cfg):
    """(ok, reason)."""
    if not rec: return False, 'no record'
    era = cfg.get('era', {}); places = [p.lower() for p in cfg.get('places', [])]
    title = (rec.get('title') or '').lower(); cult = (rec.get('culture') or '').lower()
    if any(b.lower() in title for b in cfg.get('banned_words', [])): return False, 'banned word in title'
    if is_document(rec):
        if any(p in title for p in places): return True, 'document of the place'
        return False, 'document not of the subject'
    y = year_of(rec)
    if y is None: return False, 'undated object'
    if y < era.get('from', -1e9) - 50 or y > era.get('to', 1e9) + 50: return False, f'off-era ({rec.get("date")})'
    cults = [c.lower() for c in era.get('cultures', [])]
    if cults and cult and not any(c in cult for c in cults): return False, f'wrong culture ({rec.get("culture")})'
    if cults and not cult and not any(c in title for c in cults + places): return False, 'culture unknown'
    if 'reproduction' in title or 'reproduction' in cult or 'modern' in cult: return False, 'reproduction'
    return True, 'period object'


def meta_bonus(rec, spoken):
    txt = ' '.join(str(rec.get(k) or '') for k in ('title', 'culture', 'period'))
    return TM.overlap(txt, spoken)[0]
