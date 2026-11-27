"""Broadcast-style captions from word timestamps.

Cues start exactly on their first spoken word and end shortly after their last; at most 2 lines x 42 characters,
<= 6 s, <= 20 characters/second; breaks prefer sentence ends, then commas, then the most balanced line split.
Words come from words.json (faster-whisper) but their TEXT comes from the script, so names are always spelled correctly.

python3 captions.py <timeline.json> <words.json> <out.srt>
"""
import sys, json, re, difflib

MAXL, MAXC, MAXD, CPS = 42, 84, 6.0, 20.0


def ts(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}'.replace(',1000', ',999')


def wrap(words):
    s = ' '.join(words)
    if len(s) <= MAXL: return s
    best = None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        if len(a) > MAXL or len(b) > MAXL: continue
        score = abs(len(a) - len(b)) - (12 if re.search(r'[,;:]$', words[i - 1]) else 0)
        if best is None or score < best[0]: best = (score, a + '\n' + b)
    return best[1] if best else s


def align(script_words, asr):
    """Give each script word the timing of its matching ASR word (sequence alignment), interpolating gaps."""
    norm = lambda w: re.sub(r'[^a-z0-9]', '', w.lower())
    a = [norm(w) for w in script_words]; b = [norm(w['w']) for w in asr]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    tim = [None] * len(a)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size): tim[blk.a + k] = (asr[blk.b + k]['s'], asr[blk.b + k]['e'])
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'replace' and i2 - i1 > 0 and j2 - j1 > 0:
            s0, e0 = asr[j1]['s'], asr[j2 - 1]['e']
            for k in range(i1, i2):
                f0, f1 = (k - i1) / (i2 - i1), (k - i1 + 1) / (i2 - i1)
                tim[k] = (s0 + (e0 - s0) * f0, s0 + (e0 - s0) * f1)
    return tim


def fits(ws):
    w = wrap(ws); ls = w.split('\n')
    return len(ls) <= 2 and all(len(l) <= MAXL for l in ls)


def build(tl, words):
    cues = []
    for s in tl['sentences']:
        sw = s['text'].split(); n = len(sw)
        inside = [w for w in words if s['start'] - .3 <= w['s'] <= s['end'] + .3]
        tim = align(sw, inside) if inside else [None] * n
        for k in range(n):
            if tim[k] is None:
                tim[k] = (s['start'] + (s['end'] - s['start']) * k / n, s['start'] + (s['end'] - s['start']) * (k + 1) / n)
        groups, cur = [], []
        for k in range(n):
            cand = cur + [k]
            if cur and (not fits([sw[j] for j in cand]) or tim[k][1] - tim[cur[0]][0] > MAXD):
                groups.append(cur); cur = [k]
            else:
                cur = cand
            # natural break at a comma once the cue is reasonably full
            if re.search(r'[,;:]$', sw[k]) and len(' '.join(sw[j] for j in cur)) >= 34 and k < n - 3:
                groups.append(cur); cur = []
        if cur: groups.append(cur)
        # no orphans: move words back from the previous cue while it still fits
        while len(groups) > 1 and len(groups[-1]) < 3:
            prev, last = groups[-2], groups[-1]
            if len(prev) <= 3 or not fits([sw[j] for j in prev[-1:] + last]): break
            groups[-2], groups[-1] = prev[:-1], prev[-1:] + last
        for g in groups:
            cues.append({'t0': tim[g[0]][0], 't1': tim[g[-1]][1], 'text': wrap([sw[j] for j in g])})
    out = []
    for i, c in enumerate(cues):
        t1 = max(c['t1'] + .2, c['t0'] + max(1.0, len(c['text']) / CPS))
        if i + 1 < len(cues): t1 = min(t1, cues[i + 1]['t0'] - .04)
        out.append((c['t0'], t1, c['text']))
    return out


if __name__ == '__main__':
    tl = json.load(open(sys.argv[1])); words = json.load(open(sys.argv[2]))
    words = [{'w': w.get('w', w.get('word', '')), 's': w.get('s', w.get('start')), 'e': w.get('e', w.get('end'))} for w in words]
    cues = build(tl, words)
    with open(sys.argv[3], 'w') as f:
        for i, (a, b, t) in enumerate(cues, 1): f.write(f'{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n')
    L = [len(l) for _, _, t in cues for l in t.split('\n')]
    print(f'{len(cues)} cues, max line {max(L)} chars, lines>42: {sum(1 for x in L if x > 42)}')
