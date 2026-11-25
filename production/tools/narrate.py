"""Generate narration audio per paragraph (sentence-level timing) from the script markdown files.

Output: production/build/narration/<chapter>/<para>.wav and build/narration/manifest.json
"""
import json, re, sys, glob, os
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'narration')
VOICE, SPEED, LANG = 'bm_george', 0.92, 'en-gb'
SENT_GAP, SR = 0.38, 24000

ONES = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'x x twenty thirty forty fifty sixty seventy eighty ninety'.split()
def two(n):
    if n < 20: return ONES[n]
    return TENS[n // 10] + ('' if n % 10 == 0 else '-' + ONES[n % 10])
def year(n):
    if n == 2000: return 'two thousand'
    hi, lo = divmod(n, 100)
    if lo == 0: return two(hi) + ' hundred'
    if 2000 < n < 2010: return 'two thousand ' + ONES[lo]
    return two(hi) + ' ' + (('oh ' + ONES[lo]) if lo < 10 else two(lo))

SUBS = [
    (r'\bB\.C\.E\.', 'B.C.E.'),
    ('Kaş', 'Kahsh'), ('Mehmet Çakır', 'Mehmet Chakeur'), ('Bedřich Hrozný', 'Bedrzhikh Hrozny'),
    ('Jürgen Seeher', 'Yurgen Zayer'), ('Meryey', 'Mery-yay'), ('Maathorneferure', 'Maat-hor-neferu-ray'),
    ('Puduhepa', 'Pudu-hepa'), ('Ekwesh', 'Ek-wesh'), ('Shekelesh', 'Shek-elesh'), ('Weshesh', 'Wesh-esh'),
    ('Tjeker', 'Cheker'), ('Peleset', 'Pele-set'), ('Kode,', 'Ko-deh,'), ('Uluburun', 'Oolooboorun'),
    ('Muwatalli', 'Moowa-talli'), ('Hattusili', 'Hattu-sili'), ('Suppiluliuma', 'Suppi-luli-uma'),
    ('Tudhaliya', 'Tood-haliya'), ('Tukulti-Ninurta', 'Tukulti-Ninoorta'), ('Burna-Buriash', 'Burna-Booriash'),
    ('Pentawere', 'Penta-weray'), ('Kokkinokremos', 'Kokkino-kremos'), ('Palaeokastro', 'Paleo-kastro'),
    ('Büyükkaya', 'Buyuk-kaya'), ('Ras Shamra', 'Rass Shamra'), ('Minet el-Beida', 'Meenet el Bayda'),
    ('Deir el-Medina', 'Dair el Medeena'), ('Medinet Habu', 'Medeenet Haboo'), ('Hala Sultan Tekke', 'Hala Sultan Tekkeh'),
    ('Kaniewski', 'Kan-yev-ski'), ('Langgut', 'Lang-goot'), ('Troy Seven A', 'Troy Seven-A'),
]

def normalize(t):
    for a, b in SUBS: t = re.sub(a, b, t)
    t = re.sub(r'\b(1[0-9]{3}|20[0-2][0-9])\b', lambda m: year(int(m.group(1))), t)
    return t

def parse(path):
    title, paras, vis = None, [], None
    for block in open(path, encoding='utf-8').read().split('\n\n'):
        for line in block.strip().split('\n'):
            line = line.strip()
            if not line: continue
            if line.startswith('# '): title = line[2:].strip()
            elif line.startswith('[v:'): vis = line[3:-1].strip()
            else: paras.append({'text': line, 'visual': vis})
    return title, paras

def sentences(p):
    s = re.split(r'(?<=[.!?])\s+(?=[A-Z"‘“])', p)
    return [x for x in s if x.strip()]

def main():
    k = Kokoro('/home/user/models/kokoro-v1.0.onnx', '/home/user/models/voices-v1.0.bin')
    manifest = []
    files = sorted(glob.glob(os.path.join(ROOT, 'script', '*.md')))
    only = sys.argv[1:]  # optional chapter filter
    for f in files:
        cid = os.path.basename(f)[:-3]
        if only and cid not in only: continue
        done = os.path.join(OUT, cid + '.json')
        if os.path.exists(done) and not only:
            manifest.append(json.load(open(done))); continue
        title, paras = parse(f)
        os.makedirs(os.path.join(OUT, cid), exist_ok=True)
        ch = {'id': cid, 'title': title, 'paras': []}
        for i, p in enumerate(paras):
            wav = os.path.join(OUT, cid, f'{i:02d}.wav')
            chunks, sents, t = [], [], 0.0
            for s in sentences(p['text']):
                a, sr = k.create(normalize(s), voice=VOICE, speed=SPEED, lang=LANG)
                assert sr == SR
                # trim leading/trailing near-silence
                nz = np.where(np.abs(a) > 0.01)[0]
                if len(nz): a = a[max(0, nz[0] - 600): nz[-1] + 1200]
                d = len(a) / SR
                sents.append({'text': s, 'start': round(t, 3), 'end': round(t + d, 3)})
                chunks += [a, np.zeros(int(SENT_GAP * SR), dtype=a.dtype)]
                t += d + SENT_GAP
            audio = np.concatenate(chunks[:-1])
            sf.write(wav, audio, SR)
            ch['paras'].append({'wav': os.path.relpath(wav, ROOT), 'dur': round(len(audio) / SR, 3),
                                'visual': p['visual'], 'text': p['text'], 'sentences': sents})
            print(cid, i, f'{len(audio)/SR:.1f}s', flush=True)
        manifest.append(ch)
        json.dump(ch, open(os.path.join(OUT, cid + '.json'), 'w'), indent=1)
    tot = sum(p['dur'] for c in manifest for p in c['paras'])
    print(f'TOTAL narration {tot/60:.1f} min')

if __name__ == '__main__':
    main()
