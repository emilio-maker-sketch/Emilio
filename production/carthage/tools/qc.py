"""Quality control for the edit (master-brief checklist).

  python3 tools/qc.py            # timeline checks
  python3 tools/qc.py FILE.mp4   # + rendered-file checks (black frames, loudness, peaks)
"""
import os, sys, json, glob, subprocess, collections, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); B = os.path.join(ROOT, 'build')

def main():
    tl = json.load(open(os.path.join(B, 'timeline.json'))); sh = [x for x in tl['items'] if x['type'] == 'shot']
    narr = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(os.path.join(B, 'narration', '*.json'))}
    durs = [x['dur'] for x in sh]; pic = [x for x in sh if x['kind'] in ('still', 'vid', 'photo', 'detail')]
    print(f"runtime {tl['duration']/60:.1f} min · {len(sh)} shots · mean {sum(durs)/len(durs):.1f}s")
    long_pic = [(x['id'], round(x['dur'], 1)) for x in pic if x['dur'] > 8.6 and not x.get('clip')]
    long_gfx = [(x['id'], round(x['dur'], 1)) for x in sh if x['kind'] not in ('still', 'vid', 'photo', 'detail') and x['dur'] > 16]
    print(f"picture holds > 8.6 s: {len(long_pic)}  {long_pic[:12]}")
    print(f"graphics > 16 s: {len(long_gfx)}  {long_gfx[:12]}")
    rm = sum(1 for a, b in zip(sh, sh[1:]) if a['move'] == b['move'] and a['move'] not in ('gfx', 'drift'))
    rt = sum(1 for a, b in zip(sh, sh[1:]) if a['tr'][0] == b['tr'][0] and a['tr'][0] not in ('dissolve', 'wipe', 'zoom'))
    print(f"same move twice in a row: {rm} · same special transition twice: {rt}")
    print('moves', dict(collections.Counter(x['move'] for x in sh).most_common()))
    print('transitions', dict(collections.Counter(x['tr'][0] for x in sh).most_common()))
    print('kinds', dict(collections.Counter(x['kind'] for x in sh).most_common()))
    srcs = collections.Counter(x['src'] for x in sh if x.get('src') and x['kind'] in ('still', 'vid', 'photo') and not x.get('beat'))
    print('images used more than once (excluding beats/details):', [os.path.basename(k) for k, v in srcs.items() if v > 1])
    # sync: distance from each cut to the nearest sentence boundary in its paragraph
    voice = [x for x in tl['items'] if x['type'] == 'voice']; offs = []
    for x in sh:
        if x.get('beat'): continue
        v = [y for y in voice if y['chapter'] == x['chapter'] and y['start'] <= x['start'] + 3]
        if not v: continue
        v = v[-1]; para = narr[x['chapter']]['paras'][[y for y in voice if y['chapter'] == x['chapter']].index(v)]
        b = [v['start'] + s['end'] + 0.12 for s in para['sentences']] + [v['start'] - 0.6]
        offs.append(min(abs(x['start'] - t) for t in b))
    if offs: print(f"cuts within 0.5 s of a sentence boundary: {sum(o < 0.5 for o in offs)}/{len(offs)} ({100*sum(o < 0.5 for o in offs)/len(offs):.0f}%)")
    gaps = [(a['id'], round(b['start'] - (a['start'] + a['dur']), 2)) for a, b in zip(sh, sh[1:]) if b['start'] - (a['start'] + a['dur']) > 0.05 and a['chapter'] == b['chapter']]
    print('gaps between shots:', gaps[:10])
    if len(sys.argv) > 1:
        f = sys.argv[1]
        r = subprocess.run(['ffmpeg', '-hide_banner', '-i', f, '-vf', 'blackdetect=d=0.4:pix_th=0.06', '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
        bl = re.findall(r'black_start:([\d.]+) black_end:([\d.]+)', r); print('black stretches (>0.4 s):', bl[:20])
        print('loudness:', ' '.join(l.strip() for l in r.splitlines()[-12:] if re.search(r'I:|LRA:|Peak:', l)))

if __name__ == '__main__': main()
