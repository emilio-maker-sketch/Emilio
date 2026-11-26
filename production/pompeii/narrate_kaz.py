"""Narrate kaz/script.md sentence by sentence; emit vo.wav and timeline.json (sentences + timed directives)."""
import json, os, re, shlex, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))
from narrate import normalize, VOICE, SPEED, LANG
from kokoro_onnx import Kokoro

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'build'); os.makedirs(OUT, exist_ok=True)
SR = 24000
GAP = 0.55                                         # between sentences
HOLD = {'open': 5.5, 'zone': 2.0, 'year': 3.0, 'thesis': 3.6, 'network': 3.0, 'end_open': 4.5, 'end': 7.0, 'vintage': 1.0}
EXTRA = [('Misenum', 'Mih-see-num'), ('Stabiae', 'Stah-bee-eye'), ('Pomponianus', 'Pom-poh-nee-ah-nus'),
         ('Rectina', 'Rek-tee-nah'), ('Fiorelli', 'Fyo-relli'), ('Campania', 'Kam-pahn-ya'), ('Herculaneum', 'Her-kew-lay-nee-um'),
         ('Strabo', 'Stray-bo'), ('Pompeii', 'Pom-pay'), ('Pompeianorum', 'Pom-pay-ah-noh-rum')]

def norm(t):
    for a, b in EXTRA: t = t.replace(a, b)
    return normalize(t)

def parse():
    items = []   # ('d', [args]) or ('s', text)
    for line in open(os.path.join(HERE, 'script.md'), encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('@'): items.append(('d', shlex.split(line[1:])))
        else:
            for s in re.split(r'(?<=[.!?])\s+(?=[A-Z"‘“])', line):
                if s.strip(): items.append(('s', s.strip()))
    return items

def main():
    k = Kokoro('/home/user/models/kokoro-v1.0.onnx', '/home/user/models/voices-v1.0.bin')
    items = parse(); t = 0.8; chunks = [np.zeros(int(0.8 * SR), np.float32)]
    sentences, events, cache = [], [], os.path.join(OUT, 'tts'); os.makedirs(cache, exist_ok=True)
    pend = []
    for kind, v in items:
        if kind == 'd':
            pend.append(v); continue
        # directives fire at this sentence start; add holds first
        hold = sum(HOLD.get(d[0], 0) for d in pend)
        if hold:
            for d in pend:
                if d[0] in HOLD: events.append({'t': round(t, 3), 'd': d})
            chunks.append(np.zeros(int(hold * SR), np.float32)); t += hold
        for d in pend:
            if d[0] not in HOLD: events.append({'t': round(t, 3), 'd': d, 's': len(sentences)})
        pend = []
        key = re.sub(r'\W+', '_', v)[:60] + f'_{abs(hash(v)) % 10**8}'
        p = os.path.join(cache, key + '.wav')
        if os.path.exists(p): a, _ = sf.read(p, dtype='float32')
        else:
            a, sr = k.create(norm(v), voice=VOICE, speed=SPEED, lang=LANG)
            nz = np.where(np.abs(a) > 0.01)[0]
            if len(nz): a = a[max(0, nz[0] - 600): nz[-1] + 1200]
            sf.write(p, a, SR)
        d = len(a) / SR
        sentences.append({'text': v, 'start': round(t, 3), 'end': round(t + d, 3)})
        chunks += [a.astype(np.float32), np.zeros(int(GAP * SR), np.float32)]; t += d + GAP
        print(f'{t/60:5.2f}m {v[:60]}', flush=True)
    for d in pend: events.append({'t': round(t, 3), 'd': d})
    if any(d[0] in HOLD for d in pend):
        h = sum(HOLD.get(d[0], 0) for d in pend); chunks.append(np.zeros(int(h * SR), np.float32)); t += h
    chunks.append(np.zeros(int(1.0 * SR), np.float32)); t += 1.0
    vo = np.concatenate(chunks)
    sf.write(os.path.join(OUT, 'vo.wav'), vo, SR)
    json.dump({'total': round(t, 3), 'sentences': sentences, 'events': events}, open(os.path.join(OUT, 'timeline.json'), 'w'), indent=1)
    print(f'TOTAL {t/60:.2f} min, {len(sentences)} sentences, {len(events)} events')

if __name__ == '__main__':
    main()
