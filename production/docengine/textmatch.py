"""Lexical relevance between narration and on-screen text (notes, quotes, chapter cards, counters).

CLIP is unreliable on typewritten text, so text graphics are checked by content-word overlap,
with numbers normalised ("seventeen" == "17", "nineteen eighties" == "1980s").
"""
import re

STOP = set("""a an the and or but if of to in on at by for with from into onto over under as is was were be been being are am
this that these those it its he his him she her they them their we our you your i me my not no nor so than then there here
what which who whom whose when where why how all any both each few more most other some such only own same too very can will
just do does did done had has have having would could should may might must shall about after again against before below between
during through up down out off once further while also one ones said says say like even still ever new old many much made make
""".split())

NUM = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
       'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
       'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90}
for _k, _v in list(NUM.items()):
    if _k.endswith('ty'): NUM[_k[:-1] + 'ies'] = _v
MULT = {'hundred': 100, 'thousand': 1000, 'million': 10**6}
ORD = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
       'sixteenth': 16, 'seventeenth': 17, 'eighteenth': 18, 'twentieth': 20, 'fourth': 4}


def numbers(text):
    """All numbers mentioned, as ints: digits ('1,150', '79', '1980s') and spelled-out runs ('eleven hundred and fifty')."""
    out = set()
    for m in re.finditer(r'\d[\d,\.]*', text):
        s = m.group().replace(',', '').rstrip('.')
        try: out.add(int(float(s)))
        except ValueError: pass
    words = re.findall(r"[a-z]+", text.lower())
    i = 0
    while i < len(words):
        if words[i] in NUM or words[i] in ORD:
            total, cur, j = 0, 0, i
            while j < len(words) and (words[j] in NUM or words[j] in MULT or words[j] in ORD or (words[j] == 'and' and j + 1 < len(words) and words[j + 1] in NUM)):
                w = words[j]
                if w in NUM: cur += NUM[w]
                elif w in ORD: cur += ORD[w]
                elif w in MULT:
                    if w == 'hundred': cur = max(cur, 1) * 100
                    else: total += max(cur, 1) * MULT[w]; cur = 0
                j += 1
            # "nineteen eighties" / "seventeen sixty three" style years
            seq = [words[k] for k in range(i, j)]
            if len(seq) >= 2 and seq[0] in NUM and 10 <= NUM[seq[0]] <= 20 and seq[1] in NUM and NUM[seq[1]] >= 20:
                rest = sum(NUM.get(w, 0) for w in seq[1:])
                out.add(NUM[seq[0]] * 100 + rest)
            out.add(total + cur)
            for w in seq:
                if w in NUM: out.add(NUM[w])
                if w in ORD: out.add(ORD[w])
            i = j
        else:
            i += 1
    return out


def stem(w):
    w = w.lower()
    for suf in ('ingly', 'edly', 'ings', 'ing', 'ies', 'ied', 'es', 'ed', 'ly', 's'):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[:-len(suf)] + ('y' if suf in ('ies', 'ied') else '')
    return w


def tokens(text):
    return {stem(w) for w in re.findall(r"[A-Za-z][A-Za-z'\-]+", text.replace('|', ' ')) if w.lower().strip("'") not in STOP and len(w) > 2}


def _near(a, b):
    """'suffocation'~'suffocated', 'asleep'~'sleep', 'death'~'dead': shared stem prefix or high similarity."""
    import difflib
    if a == b: return True
    if min(len(a), len(b)) >= 3 and (a.startswith(b) or b.startswith(a)) and abs(len(a) - len(b)) <= 3: return True
    if min(len(a), len(b)) >= 5 and (a[:6] == b[:6] or a in b or b in a): return True
    if min(len(a), len(b)) >= 4 and difflib.SequenceMatcher(None, a, b).ratio() >= .8: return True
    return a[:4] == b[:4] and min(len(a), len(b)) >= 4 and abs(len(a) - len(b)) <= 2


def overlap(screen_text, spoken):
    """Return (score 0..1, shared words, shared numbers). score = share of the card's content words the narration covers."""
    a, b = tokens(screen_text), tokens(spoken)
    na, nb = numbers(screen_text), numbers(spoken)
    shared = {w for w in a if any(_near(w, v) for v in b)}
    nshared = na & nb
    denom = max(1, min(len(a), 6) + len(na))
    return min(1.0, (len(shared) + 1.5 * len(nshared)) / denom), sorted(shared), sorted(nshared)
