"""Narration-to-visual accuracy audit for a Kaz-engine project.

For every narration sentence it works out what is actually on screen (board card in camera focus,
full-screen cutaway, film insert, chapter/year card, 3D splice) at several points through the sentence and checks:

  * image visuals  -> CLIP relevance, judged relative to the rest of the script (z-score: is this image a better
                      match for THIS sentence than for the average sentence?), plus rank against the whole image pool;
  * text visuals   -> content-word / number overlap with the sentence (and its neighbours);
  * era            -> ancient objects must come from the project's period and cultures;
  * repetition     -> the same image used in several separate shots;
  * staleness      -> the same focus visual held for too long.

Usage (from a project dir):  python3 ../docengine/audit.py [--frames]   (--frames also scores the rendered video)
Writes build/audit/audit.json and build/audit/audit.md.  Exit code 1 if any MISMATCH is found.
"""
import os, sys, json, re, math, glob
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import semantic as SEM, textmatch as TM, catalog as CAT

PROJ = os.getcwd()
sys.path.insert(0, PROJ)
CFG = json.load(open(os.path.join(PROJ, 'project.json')))
OUT = os.path.join(PROJ, 'build', 'audit'); os.makedirs(OUT, exist_ok=True)
ROOT = os.path.dirname(HERE)
MUSEUM = os.path.join(ROOT, 'build', 'images', 'museum')

import kaz_engine as E
import cutaways as CW

S = E.TL['sentences']; W, H = E.W, E.H

# ---------------------------------------------------------------- item text (notes/quotes keep only pixels)
KMAP = {'card': 'card', 'note': 'note', 'quote': 'quote', 'suspect': 'suspect', 'diagram': 'diagram', 'map': 'map'}
ev_by_kind = {}
for ev in E.TL['events']:
    if ev['d'][0] in KMAP: ev_by_kind.setdefault(ev['d'][0], []).append(ev)
cnt = {}
for it in E.ITEMS:
    k = it['kind']; i = cnt.get(k, 0); cnt[k] = i + 1
    evs = ev_by_kind.get(k, [])
    ev = evs[i] if i < len(evs) else None
    pos, opt = E.kv(ev['d'][1:]) if ev else ([], {})
    it['_text'] = ' '.join(p for p in pos if not re.match(r'^(met|aic|wc_)\w+$', p)) if k != 'card' else ''
    it['_name'] = opt.get('as', '')
    tags = [tg for tg in E.TAGS if tg.get('item') is it] if E.TAGS and isinstance(E.TAGS[0], dict) else []
    it['_tags'] = ' '.join(tg.get('text', '') for tg in tags)


def item_rect(it, C):
    x, y = E.to_screen(it['c'], C); z = C[2]
    w, h = it['size'][0] * z, it['size'][1] * z
    return x - w / 2, y - h / 2, x + w / 2, y + h / 2


def visible(C, t):
    """Board items already on the board and in view, ranked by screen area x centrality (what the eye lands on)."""
    out = []
    for it in E.ITEMS:
        if it['t0'] > t: continue
        x0, y0, x1, y1 = item_rect(it, C)
        ix = max(0, min(x1, W) - max(x0, 0)); iy = max(0, min(y1, H) - max(y0, 0))
        area = ix * iy / (W * H); frac = ix * iy / max(1, (x1 - x0) * (y1 - y0))
        cx, cy = (max(x0, 0) + min(x1, W)) / 2, (max(y0, 0) + min(y1, H)) / 2
        cen = 1 - min(1, math.hypot((cx - W / 2) / W, (cy - H / 2) / H) * 1.6)
        if area > (.03 if it['kind'] in ('note', 'quote') else .06) and frac > .55: out.append((area * (.35 + cen), it))
    out.sort(key=lambda a: -a[0])
    return [it for _, it in out[:2]]


def overlay_at(t):
    for o in E.OVERLAYS:
        if o['t0'] <= t < o['t0'] + o['dur']: return o
    return None


def film_at(t):
    for f in E.FILMS:
        if f['t0'] <= t < f['t1']: return f
    return None


def splice_at(t):
    for s in CFG.get('splices', []):
        if s['t0'] <= t < s['t1']: return s
    return None


def shot_at(t):
    """Describe the dominant visual at time t."""
    sp = splice_at(t)
    if sp: return {'kind': '3d', 'text': sp['desc'], 'key': '3d:%s' % sp['t0']}
    c = CW.active(t)
    if c:
        k = c['kind']
        if k == 'photo': return {'kind': 'photo', 'ids': [c['id']], 'text': c.get('label') or '', 'key': 'photo:' + c['id']}
        if k == 'object': return {'kind': 'object', 'ids': [c['id']], 'text': c['title'] + ' ' + c['sub'], 'key': 'object:' + c['id']}
        if k == 'trip': return {'kind': 'trip', 'ids': list(c['ids']), 'text': c['label'], 'key': 'trip:' + ','.join(c['ids'])}
        if k == 'type': return {'kind': 'type', 'text': c['text'], 'key': 'type:' + c['text']}
        if k == 'foot':
            dur = c['t1'] - c['t0']; avail = c['b'] - c['a'] - 1.2; sp_ = min(1.0, max(.55, avail / dur))
            return {'kind': 'footage', 'src': c['src'], 'ft': c['a'] + .6 + (t - c['t0']) * sp_, 'text': CW.FOOT[c['src']][1], 'key': 'foot:%s:%d' % (c['src'], c['a'])}
    f = film_at(t)
    if f: return {'kind': 'film', 'text': f['scene'] + ' ' + f['title'], 'key': 'film:' + f['scene']}
    o = overlay_at(t)
    if o and o['kind'] not in ('end_open',):
        return {'kind': 'title:' + o['kind'], 'text': '%s %s' % (o.get('a', ''), o.get('b', '')), 'key': 'ov:%s:%s' % (o['kind'], o.get('a'))}
    C0, C1 = E.cam(t - .1), E.cam(t + .1)
    speed = math.hypot(C1[0] - C0[0], C1[1] - C0[1]) * C0[2] / .2          # screen px per second
    if speed > 1500: return {'kind': 'transit', 'text': '', 'key': 'transit'}
    its = visible(E.cam(t), t)
    if not its: return {'kind': 'board-wide', 'text': '', 'key': 'wide'}
    it = its[0]
    if it['kind'] == 'card':
        return {'kind': 'card', 'ids': [it['credit']['id']], 'text': it['_tags'], 'key': 'card:' + it['credit']['id'], 'name': it['_name']}
    return {'kind': it['kind'], 'text': it['_text'], 'key': '%s:%s' % (it['kind'], it['_name'] or it['_text'][:30]), 'born': it['t0']}


# ---------------------------------------------------------------- images
REC = {}
for f in glob.glob(os.path.join(ROOT, 'build', 'images', 'museum.json')):
    for topic, recs in json.load(open(f)).items():
        for r in recs: REC.setdefault(r['id'], dict(r, topic=topic))
cj = os.path.join(PROJ, 'build', 'credits.json')
if os.path.exists(cj): REC.update(json.load(open(cj)))


def img_path(id_):
    r = REC.get(id_)
    if r and r.get('file'):
        for base in (os.path.join(ROOT, 'build', 'images'), PROJ, os.path.join(PROJ, 'build')):
            p = os.path.join(base, r['file'])
            if os.path.exists(p): return p
    g = glob.glob(os.path.join(MUSEUM, '*', id_ + '.jpg')) + glob.glob(os.path.join(ROOT, 'build', 'images', '**', id_ + '.*'), recursive=True)
    return g[0] if g else None


_FOOT = {}
def foot_frame(src, ft):
    path = os.path.join(PROJ, 'build', 'footage', CW.FOOT[src][0])
    cap = _FOOT.setdefault(src, cv2.VideoCapture(path))
    cap.set(cv2.CAP_PROP_POS_MSEC, ft * 1000); ok, fr = cap.read()
    return fr if ok else None


def year_of(rec):
    d = (rec.get('date') or '') + ' ' + (rec.get('period') or '')
    m = re.search(r'(\d{1,4})(?:st|nd|rd|th)?\s*(?:century\s*)?(BCE|B\.C\.|BC|CE|A\.D\.|AD)?', d)
    if not m: return None
    v = int(m.group(1)); bc = bool(m.group(2) and 'B' in m.group(2))
    if 'century' in d and v < 30: v = v * 100 - 50
    return -v if bc else v


def era_check(rec):
    """Ancient objects must sit in the project's window; documents of the place (photos, prints, paintings) are fine."""
    if not rec: return None
    med = (rec.get('medium', '') + ' ' + rec.get('title', '')).lower()
    if re.search(r'photograph|albumen|salted paper|print|oil on|watercolor|engraving|lithograph|etching|drawing|gelatin', med):
        return None
    era = CFG.get('era', {}); y = year_of(rec)
    cult = (rec.get('culture') or '').strip()
    probs = []
    if y is not None and (y < era.get('from', -1e9) - 50 or y > era.get('to', 1e9) + 50): probs.append(f'date {rec.get("date")}')
    if cult and era.get('cultures') and not any(c.lower() in cult.lower() for c in era['cultures']): probs.append(f'culture {cult}')
    return '; '.join(probs) or None


# ---------------------------------------------------------------- main
OK = {}
for ev in E.TL['events']:
    pos_, opt_ = E.kv(ev['d'][1:])
    if 'ok' in opt_:
        for x in re.findall(r'(?:met|aic)\d+|wc_\w+', ' '.join(ev['d'][1:2])): OK[x] = opt_['ok']


def main():
    use_frames = '--frames' in sys.argv
    print('sentences', len(S))
    tv = SEM.embed_text([s['text'] for s in S])                       # raw sentence vectors
    ctx = []
    for i in range(len(S)):                                            # sentence + a little of its neighbours
        v = tv[i] * 1.0
        if i: v = v + .35 * tv[i - 1]
        if i + 1 < len(S): v = v + .35 * tv[i + 1]
        ctx.append(v / np.linalg.norm(v))
    ctx = np.array(ctx)

    # what is on screen, sampled through each sentence
    rows = []
    for i, s in enumerate(S):
        a, b = s['start'], s['end']; d = b - a
        ts = [a + d * f for f in ((.2, .5, .8) if d > 2.5 else (.5,))]
        shots = [dict(shot_at(t), t=round(t, 2)) for t in ts]
        rows.append({'i': i, 'start': a, 'end': b, 'text': s['text'], 'shots': shots})

    # embed every image that appears + the pool
    ids = sorted({x for r in rows for sh in r['shots'] for x in sh.get('ids', [])})
    paths = {i_: img_path(i_) for i_ in ids}
    missing = [i_ for i_, p in paths.items() if not p]
    pool_paths = [p for pre in CFG.get('pool', []) for p in glob.glob(os.path.join(MUSEUM, pre + '*', '*.jpg'))]
    allp = [p for p in paths.values() if p] + pool_paths
    print('embedding', len(allp), 'images (cached after first run)')
    embs = SEM.embed_files(allp, verbose=True)
    EMB = dict(zip(allp, embs))
    pool = np.array([EMB[p] for p in pool_paths]) if pool_paths else np.zeros((0, 512))
    global FILM_IDS
    FILM_IDS = [x for x in ids if paths.get(x)]
    global POOLMEAN, POOLSTD, POOLREC, POOLOK
    RECS = CAT.records()
    POOLREC = [RECS.get(os.path.basename(p)[:-4], {}) for p in pool_paths]
    POOLOK = [CAT.eligible(r, CFG)[0] for r in POOLREC]
    print('pool eligible', sum(POOLOK), 'of', len(POOLOK))
    global POOLOK_ARR
    POOLOK_ARR = np.array(POOLOK, bool)
    if len(pool):
        allsc = pool @ ctx.T * 100                      # (images, sentences): judge pool images relative to the whole script too
        POOLMEAN, POOLSTD = allsc.mean(1), allsc.std(1) + 1e-6
    # footage frames
    for r in rows:
        for sh in r['shots']:
            if sh['kind'] == 'footage':
                fr = foot_frame(sh['src'], sh['ft'])
                if fr is not None: sh['_emb'] = SEM.embed_images([fr])[0]
    if use_frames:
        cap = cv2.VideoCapture(os.path.join(PROJ, CFG['video']))
        for r in rows:
            cap.set(cv2.CAP_PROP_POS_MSEC, (r['start'] + r['end']) / 2 * 1000); ok, fr = cap.read()
            if ok: r['_frame'] = SEM.embed_images([fr])[0]

    def img_eval(v, i):
        sc = ctx @ v * 100                          # this image vs every sentence
        z = (sc[i] - sc.mean()) / (sc.std() + 1e-6)
        pr = float((pool[POOLOK_ARR] @ ctx[i] * 100 < sc[i]).mean()) if len(pool) and POOLOK_ARR.any() else None
        return float(sc[i]), float(z), pr

    flags_all = []
    use_count = {}
    for r in rows:
        i = r['i']; fl = []
        spoken = ' '.join(S[j]['text'] for j in range(max(0, i - 1), min(len(S), i + 2)))
        seen = set()
        for sh in r['shots']:
            if sh['key'] in seen: continue
            seen.add(sh['key'])
            k = sh['kind']
            if k in ('photo', 'card', 'trip', 'object', 'footage'):
                vs = [sh['_emb']] if k == 'footage' and '_emb' in sh else [EMB[paths[x]] for x in sh.get('ids', []) if paths.get(x)]
                if not vs: continue
                evs = [img_eval(v, i) for v in vs]
                sh['clip'] = round(max(e[0] for e in evs), 2); sh['z'] = round(max(e[1] for e in evs), 2)
                sh['pool_rank'] = None if evs[0][2] is None else round(max(e[2] for e in evs), 2)
                lex, words, nums = TM.overlap(sh.get('text', ''), spoken) if sh.get('text') else (0, [], [])
                sh['lex'] = round(lex, 2)
                # judged on PIXELS only: a caption describes the intended picture, not the one on screen
                # pass if specific to this sentence (z) OR among the best eligible images in the pool for it (rank):
                # an image the whole film is about (the casts) scores high everywhere, so z alone under-rates it
                film_sc = sorted((float(EMB[paths[x]] @ ctx[i] * 100) for x in FILM_IDS), reverse=True)
                best_here = max(float(v @ ctx[i] * 100) for v in vs)
                sh['film_rank'] = film_sc.index(min(film_sc, key=lambda q: abs(q - best_here))) + 1 if film_sc else None
                ok = sh['z'] > -1.0 if k == 'footage' else (sh['z'] >= -0.35 or ((sh.get('pool_rank') or 0) >= .85 and (sh['film_rank'] or 99) <= 3))
                if ok and k != 'footage' and sh['z'] < -0.35:
                    # borderline: does the picture show any concrete thing the sentence names?
                    words = [w for w in re.findall(r"[A-Za-z]{4,}", S[i]['text']) if w.lower() not in TM.STOP]
                    if words and len(pool):
                        cv = SEM.embed_text([f'a picture of {w.lower()}' for w in words])
                        pz = pool @ cv.T * 100; mu, sd = pz.mean(0), pz.std(0) + 1e-6
                        nz = max(((v @ cv.T * 100 - mu) / sd).max() for v in vs)
                        sh['concept_z'] = round(float(nz), 2)
                        if nz < 1.0: ok = False
                if not ok:
                    sug = ''
                    if len(pool):
                        sc_all = pool @ ctx[i] * 100
                        zs = (sc_all - POOLMEAN) / POOLSTD + .8 * np.array([CAT.meta_bonus(POOLREC[j], spoken) for j in range(len(pool_paths))])
                        best = [j for j in np.argsort(-zs) if POOLOK[j]][:3]
                        sug = '  -> try: ' + ', '.join(f"{os.path.basename(pool_paths[j])[:-4]} '{POOLREC[j].get('title', '')[:40]}' ({zs[j]:.1f})" for j in best)
                    fl.append(('MISMATCH' if sh['z'] < -0.8 else 'WEAK', f"{k} {sh.get('ids', sh.get('src'))} z={sh['z']} clip={sh['clip']}{sug}"))
                # caption must describe the image actually shown
                if k != 'footage' and sh.get('text') and sh.get('ids'):
                    lab = re.sub(r'\s*·\s*THE MET\s*$', '', sh['text'])
                    lv = SEM.text_vec(lab)
                    for x in dict.fromkeys(sh['ids']):
                        if not paths.get(x): continue
                        rec = REC.get(x, {})
                        meta = TM.overlap(' '.join(str(rec.get(q) or '') for q in ('title', 'artist', 'date', 'culture', 'medium')), lab)[0]
                        lz = (float(EMB[paths[x]] @ lv * 100) - float((pool @ lv * 100).mean())) / (float((pool @ lv * 100).std()) + 1e-6) if len(pool) else 0
                        sh.setdefault('label_z', {})[x] = round(lz, 2)
                        if meta == 0 and lz < .8:
                            fl.append(('LABEL', f"caption '{lab[:50]}' does not describe {x} ('{rec.get('title', '')[:40]}') label_z={lz:.2f}"))
                # a named place must actually be shown
                for name, prompt in CFG.get('entities', {}).items():
                    if not re.search(r'\b' + re.escape(name) + r'(s|es)?\b', S[i]['text'], re.I): continue
                    ev = SEM.text_vec(prompt)
                    for x in sh.get('ids', []):
                        if not paths.get(x): continue
                        if name.lower() in (REC.get(x, {}).get('title', '') or '').lower(): continue
                        ez = (float(EMB[paths[x]] @ ev * 100) - float((pool @ ev * 100).mean())) / (float((pool @ ev * 100).std()) + 1e-6)
                        if ez < 1.0: fl.append(('ENTITY', f"narration names {name} but {x} ('{REC.get(x, {}).get('title', '')[:40]}') does not show it (z={ez:.2f})"))
                for x in sh.get('ids', []):
                    use_count.setdefault(x, set()).add(round(r['start'] / 6))
                    ok_, why = CAT.eligible(REC.get(x), CFG)
                    if not ok_: fl.append(('ERA', f'{x}: {why}'))
            elif k in ('note', 'quote', 'type', 'title:year', 'title:counter', 'title:chapter', 'film', 'suspect'):
                lex, words, nums = TM.overlap(sh['text'], spoken)
                wide = ' '.join(S[j]['text'] for j in range(max(0, i - 3), min(len(S), i + 3)))
                lex2 = TM.overlap(sh['text'], wide)[0]
                sh['lex'] = round(lex, 2); sh['match'] = words + [str(n) for n in nums]
                born = sh.get('born')
                if born is not None and lex2 == 0:
                    bi = max(j for j in range(len(S)) if S[j]['start'] <= born + .05) if born >= S[0]['start'] else 0
                    lex2 = TM.overlap(sh['text'], ' '.join(S[j]['text'] for j in range(max(0, bi - 1), min(len(S), bi + 3))))[0]
                    if lex2 > 0: sh['context'] = True
                if k in ('note', 'quote', 'type', 'title:counter') and lex2 == 0:
                    fl.append(('TEXT-UNRELATED', f"{k} '{sh['text'][:60]}'"))
        if '_frame' in r:
            sc = ctx @ r['_frame'] * 100; r['frame_z'] = round(float((sc[i] - sc.mean()) / (sc.std() + 1e-6)), 2)
        fl = [f for f in fl if not (f[0] in ('ERA', 'ENTITY', 'WEAK') and any(x in f[1] for x in OK))]
        r['flags'] = fl
        for f in fl: flags_all.append((r['start'], f[0], f[1], r['text']))

    # staleness: same focus key across consecutive samples for too long
    seq = [(t, shot_at(t)['key']) for t in np.arange(0, S[-1]['end'], 1.0)]
    run_k, run_t0, stale = None, 0, []
    for t, k in seq + [(S[-1]['end'], None)]:
        if k != run_k:
            if run_k and t - run_t0 > 14 and run_k not in ('wide', 'transit') and not run_k.startswith(('3d', 'ov:end', 'foot:')):
                stale.append((round(run_t0, 1), round(t - run_t0, 1), run_k))
            run_k, run_t0 = k, t
    for s in stale: flags_all.append((s[0], 'STALE', f'{s[2]} held ~{s[1]}s', ''))
    # repetition across separate moments (a card the camera returns to is deliberate; >3 separate uses is not)
    for x, moments in use_count.items():
        if len(moments) > 4: flags_all.append((0, 'REPEAT', f'{x} appears in {len(moments)} separate moments', ''))
    for x in missing: flags_all.append((0, 'MISSING', f'no image file for {x}', ''))

    def clean(o):
        if isinstance(o, dict): return {k: clean(v) for k, v in o.items() if not k.startswith('_')}
        if isinstance(o, list): return [clean(v) for v in o]
        return o
    summary = {
        'sentences': len(rows),
        'image_shots': sum(1 for r in rows for sh in r['shots'] if 'z' in sh),
        'mean_image_z': round(float(np.mean([sh['z'] for r in rows for sh in r['shots'] if 'z' in sh] or [0])), 3),
        'frame_z_mean': round(float(np.mean([r['frame_z'] for r in rows if 'frame_z' in r])), 3) if use_frames else None,
        'frame_z_low': [(round(r['start'], 1), r['frame_z'], r['text'][:60]) for r in rows if r.get('frame_z', 9) < -1.0] if use_frames else None,
        'flags': {k: sum(1 for f in flags_all if f[1] == k) for k in sorted({f[1] for f in flags_all})},
    }
    json.dump({'summary': summary, 'flags': flags_all, 'rows': clean(rows)}, open(os.path.join(OUT, 'audit.json'), 'w'), indent=1)
    with open(os.path.join(OUT, 'audit.md'), 'w') as f:
        f.write(f"# Visual accuracy audit - {CFG['title']}\n\n```\n{json.dumps(summary, indent=1)}\n```\n\n## Flags\n\n")
        for t, k, msg, txt in sorted(flags_all):
            f.write(f"- **{k}** {int(t // 60)}:{t % 60:04.1f}  {msg}  \n  _{txt}_\n")
        f.write('\n## Sentence by sentence\n\n| time | narration | on screen | score |\n|---|---|---|---|\n')
        for r in rows:
            vis = '; '.join(dict.fromkeys(f"{sh['kind']} {','.join(sh.get('ids', [])) or sh.get('text', '')[:40]}" for sh in r['shots']))
            sc = '; '.join(dict.fromkeys((f"z={sh['z']}" if 'z' in sh else f"lex={sh.get('lex', '-')}") for sh in r['shots']))
            f.write(f"| {int(r['start'] // 60)}:{r['start'] % 60:04.1f} | {r['text'][:90]} | {vis} | {sc} |\n")
    print(json.dumps(summary, indent=1))
    for t, k, msg, txt in sorted(flags_all):
        if k in ('MISMATCH', 'WEAK', 'TEXT-UNRELATED', 'ERA', 'STALE', 'LABEL', 'ENTITY'): print(f'{k:15s} {int(t // 60)}:{t % 60:04.1f}  {msg}  | {txt[:70]}')
    return 1 if summary['flags'].get('MISMATCH') else 0


if __name__ == '__main__':
    sys.exit(main())
