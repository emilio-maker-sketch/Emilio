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
DOC = r'photograph|albumen|salted paper|gelatin|print|oil on|watercolor|engraving|lithograph|etching|drawing|gouache|daguerreotype|map|plan|paper, board|book|letters on'


def records():
    out = {}
    for f in glob.glob(os.path.join(ROOT, 'build', 'images', 'museum.json')):
        for topic, recs in json.load(open(f)).items():
            for r in recs: out.setdefault(r['id'], dict(r, topic=topic))
    return out


def year_of(rec):
    """Midpoint year of a museum date string; negative = B.C. ('ca. 668-627 BCE', 'late 1st millennium BCE', '8th-7th century BC')."""
    d = ' '.join(str(rec.get(k) or '') for k in ('date', 'period'))
    if not re.search(r'\d', d): return None
    bc = bool(re.search(r'\b(BCE|B\.C\.?|BC)\b', d))
    nums = [int(x) for x in re.findall(r'(\d{1,4})(?:st|nd|rd|th)?', d)[:2]]
    if 'millenni' in d: v = (sum(nums) / len(nums)) * 1000 - 500
    elif 'century' in d: v = (sum(nums) / len(nums)) * 100 - 50
    else: v = sum(nums) / len(nums)
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
