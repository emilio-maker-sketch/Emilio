"""Narration with Kokoro (free, local), voice bm_lewis.

  python3 tools/narrate_local.py [chapter_id ...]
Writes build/narration/<chapter>/<para>.wav and build/narration/<chapter>.json
"""
import os, sys, re, json
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
from script_parse import chapters, ROOT

OUT = os.path.join(ROOT, 'build', 'narration')
VOICE, SPEED, LANG, SR, GAP = 'bm_lewis', 0.92, 'en-gb', 24000, 0.38
SUBS = [('Spurinna', 'Spoo-rinna'), ('Cnidos', 'Nye-doss'), ('Iulus', 'Yoo-lus'), ('Divus Iulius', 'Deevus Yoolius'),
        ('Dyrrhachium', 'Dirra-keeum'), ('Smyrna', 'Smerna'), ('Bibulus', 'Bib-yulus'), ('Nicolaus', 'Nikko-layus'),
        ('Veni, vidi, vici', 'Waynee, weedee, weekee'), ('EID MAR', 'Eed Mar'), ('Pontifex', 'Ponti-fex'),
        ('kai su, teknon', 'kai soo, teknon'), ('Laenas', 'Lye-nas'), ('Formiae', 'For-mee-eye')]
ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'x x twenty thirty forty fifty sixty seventy eighty ninety'.split()
def two(n): return ONES[n] if n < 20 else TENS[n // 10] + ('' if n % 10 == 0 else '-' + ONES[n % 10])
def year(n):
    hi, lo = divmod(n, 100)
    return two(hi) + (' hundred' if lo == 0 else ' ' + (('oh ' + ONES[lo]) if lo < 10 else two(lo)))
def norm(t):
    for a, b in SUBS: t = t.replace(a, b)
    return re.sub(r'\b(1[0-9]{3})\b', lambda m: year(int(m.group(1))), t)
def sentences(p): return [x for x in re.split(r'(?<=[.!?])\s+(?=[A-Z"‘“])', p) if x.strip()]

def main():
    k = Kokoro('/home/user/models/kokoro-v1.0.onnx', '/home/user/models/voices-v1.0.bin')
    only = sys.argv[1:]; total = 0
    for ch in chapters():
        if only and ch['id'] not in only: continue
        done = os.path.join(OUT, ch['id'] + '.json')
        if not only and os.path.exists(done) and len(json.load(open(done))['paras']) == len(ch['paras']):
            total += sum(p['dur'] for p in json.load(open(done))['paras']); continue
        d = os.path.join(OUT, ch['id']); os.makedirs(d, exist_ok=True)
        rec = {'id': ch['id'], 'title': ch['title'], 'paras': []}
        for i, p in enumerate(ch['paras']):
            chunks, sents, t = [], [], 0.0
            for s in sentences(p['text']):
                a, sr = k.create(norm(s), voice=VOICE, speed=SPEED, lang=LANG)
                nz = np.where(np.abs(a) > 0.01)[0]
                if len(nz): a = a[max(0, nz[0] - 600): nz[-1] + 1200]
                sents.append({'text': s, 'start': round(t, 3), 'end': round(t + len(a) / SR, 3)})
                chunks += [a, np.zeros(int(GAP * SR), dtype=a.dtype)]; t += len(a) / SR + GAP
            audio = np.concatenate(chunks[:-1]); wav = os.path.join(d, f'{i:02d}.wav'); sf.write(wav, audio, SR)
            rec['paras'].append({'wav': os.path.relpath(wav, ROOT), 'dur': round(len(audio) / SR, 3), 'sentences': sents})
            total += len(audio) / SR
        json.dump(rec, open(os.path.join(OUT, ch['id'] + '.json'), 'w'), indent=1)
        print(ch['id'], f"{sum(p['dur'] for p in rec['paras'])/60:.1f} min", flush=True)
    print(f'TOTAL {total/60:.1f} min')

if __name__ == '__main__': main()
