"""Narration for the Pompeii episode: one WAV per paragraph, sentence timings in a manifest.
Output: build/vo/<chapter>/<NN>.wav, build/vo/manifest.json
"""
import json, re, glob, os, sys
import numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'vo')
VOICE, SPEED, LANG, SR, GAP = 'bm_george', 0.88, 'en-gb', 24000, 0.42
SUBS = [('Pompeianorum', 'Pompay-ahnorum'), ('Pompeians', 'Pompayans'), ('Pompeian', 'Pompayan'), ('Pompeii', 'Pompay'),
        ('Misenum', 'Miseenum'), ('Iucundus', 'Yookundus'), ('Pomponianus', 'Pomponee-ahnus'), ('Philodemus', 'Fillo-deemus'),
        ('la Civita', 'la Cheevita'), ('Civita Giuliana', 'Cheevita Julee-ahna'), ('quadriremes', 'kwod-ri-reems'),
        ('porphyras', 'por-fur-ahs'), ('Resina', 'Rezeena'), ('Puteoli', 'Pyoo-tee-oh-lee'), ('Capri', 'Cah-pree'),
        ('Liburnian', 'Libernian'), ('Oplontis', 'Oplontiss')]
def norm(t):
    for a, b in SUBS: t = t.replace(a, b)
    return t
def parse(path):
    paras = []
    for line in open(path, encoding='utf-8'):
        s = line.strip()
        if s and not s.startswith(('#', '[')): paras.append(s)
    return paras
def sentences(p): return [x for x in re.split(r'(?<=[.!?:])\s+(?=[A-Z"])', p) if x.strip()]
def main():
    k = Kokoro('/home/user/models/kokoro-v1.0.onnx', '/home/user/models/voices-v1.0.bin')
    mpath = os.path.join(OUT, 'manifest.json'); man = json.load(open(mpath)) if os.path.exists(mpath) else {}
    only = sys.argv[1:]
    for f in sorted(glob.glob(os.path.join(ROOT, 'script', '*.md'))):
        ch = os.path.basename(f)[:-3]
        if only and ch[:2] not in only: continue
        os.makedirs(os.path.join(OUT, ch), exist_ok=True); man[ch] = []
        for i, p in enumerate(parse(f)):
            chunks, sents, t = [], [], 0.0
            for s in sentences(p):
                a, _ = k.create(norm(s), voice=VOICE, speed=SPEED, lang=LANG)
                sents.append({'text': s, 'start': round(t, 3), 'dur': round(len(a) / SR, 3)})
                chunks += [a, np.zeros(int(GAP * SR), np.float32)]; t += len(a) / SR + GAP
            audio = np.concatenate(chunks[:-1])
            sf.write(os.path.join(OUT, ch, f'{i:02d}.wav'), audio, SR)
            man[ch].append({'i': i, 'dur': round(len(audio) / SR, 3), 'sentences': sents})
            print(ch, i, round(len(audio) / SR, 1), flush=True)
        json.dump(man, open(mpath, 'w'), indent=1)
if __name__ == '__main__':
    main()
