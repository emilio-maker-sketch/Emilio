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
SUBS = [('Derinkuyu', 'Deh-rin-koo-yoo'), ('Kaymaklı', 'Kai-mak-luh'), ('Özkonak', 'Erz-ko-nak'), ('Nevşehir', 'Nev-sheh-heer'), ('Göreme', 'Gur-reh-meh'),
        ('Erciyes', 'Er-jee-yes'), ('Kültepe', 'Kewl-teh-peh'), ('Kanesh', 'Kah-nesh'), ('Assur', 'Ah-soor'), ('karum', 'kah-room'), ('nesili', 'neh-see-lee'),
        ('Hattusa', 'Hat-too-sha'), ('Katpatuka', 'Kat-pa-too-ka'), ('Mazaca', 'Ma-za-ka'), ('Archelaus', 'Ar-keh-lay-us'), ('Comana', 'Ko-mah-na'),
        ('Ihlara', 'Ih-la-ra'), ('Soğanlı', 'So-ahn-luh'), ('Tokalı', 'To-ka-luh'), ('Açıksaray', 'Ah-chuk-sa-rai'), ('Selime', 'Seh-lee-meh'),
        ('Zelve', 'Zel-veh'), ('Uçhisar', 'Ooch-hee-sar'), ('Çatalhöyük', 'Chah-tal-hur-yook'), ('Tyana', 'Tie-ay-na'), ('Heraclea', 'Heh-ra-klee-a'),
        ('Amorium', 'A-mor-ee-um'), ('Ancyra', 'An-sigh-ra'), ("al-Mu'tasim", 'al Moo-ta-sim'), ('Harun al-Rashid', 'Ha-roon al Ra-sheed'),
        ('Digenis Akritis', 'Dee-yeh-nees A-kree-tees'), ('Manzikert', 'Man-zi-kert'), ('Alp Arslan', 'Alp Ars-lan'), ('Sultanhanı', 'Sool-tan-ha-nuh'),
        ('Aksaray', 'Ak-sa-rai'), ('Karamanlides', 'Ka-ra-man-lee-deez'), ('Sinasos', 'See-na-sos'), ('Mustafapaşa', 'Moos-ta-fa-pa-sha'),
        ('Malakopi', 'Ma-la-ko-pee'), ('Gelveri', 'Gel-veh-ree'), ('Güzelyurt', 'Gew-zel-yurt'), ('Nea Karvali', 'Neh-a Kar-va-lee'),
        ('Naours', 'Na-oor'), ('Matmata', 'Mat-ma-ta'), ('Mazı', 'Ma-zuh'), ('Tatlarin', 'Tat-la-rin'), ('Gaziemir', 'Ga-zee-eh-meer'),
        ('Avanos', 'Ah-va-nos'), ('Anabasis', 'A-na-ba-sis'), ('Xenophon', 'Zen-o-fon'), ('Aydan', 'Ai-dan'), ('Ulusay', 'Oo-loo-sai'),
        ('Kalas', 'Ka-las'), ('Nazianzus', 'Na-zee-an-zus'), ('Nyssa', 'Nis-sa'), ('Dawkins', 'Daw-kins'),
        ('Qart-hadasht', 'Kart-ha-dasht'), ('Karchedon', 'Kar-keh-don'), ('Byrsa', 'Beer-sa'), ('Tanit', 'Tah-neet'),
        ('Baal Hammon', 'Bahl Hammon'), ('suffetes', 'suff-eets'), ('suffete', 'suff-eet'), ('Mylae', 'My-lee'), ('Xanthippus', 'Zan-thippus'),
        ('Aegates', 'Ee-gay-teez'), ('Eryx', 'Eh-rix'), ('Saguntum', 'Sa-gun-tum'), ('Saguntines', 'Sa-gun-tines'), ('Ticinus', 'Tih-kee-nus'),
        ('Trasimene', 'Trazzi-meen'), ('Cunctator', 'Kunk-tah-tor'), ('Aufidus', 'Ow-fid-us'), ('Maharbal', 'Ma-har-bal'),
        ('Metaurus', 'Meh-tow-rus'), ('Bruttium', 'Brut-ee-um'), ('Baecula', 'Bye-kula'), ('Masinissa', 'Massi-nissa'),
        ('Seleucid', 'Seh-loo-sid'), ('Prusias', 'Proo-see-as'), ('Bithynia', 'Bith-inny-a'), ('Nasica', 'Na-see-ka'),
        ('Aemilianus', 'Ay-milly-ah-nus'), ('Censorinus', 'Sen-sor-eye-nus'), ('Laelius', 'Lee-lee-us'), ('Reshef', 'Reh-shef'),
        ('Eshmun', 'Esh-moon'), ('Lancel', 'Lon-sell'), ('Gracchus', 'Grak-us'), ('Carthago delenda est', 'Kar-tah-go deh-len-da est'),
        ('Carthago', 'Kar-tah-go'), ('Hasdrubal', 'Has-droo-bal'), ('Hamilcar', 'Ha-mil-kar'), ('Utica', 'You-tika'),
        ('Pygmalion', 'Pig-may-lee-on'), ('Elissa', 'Eh-lissa'), ('Mago', 'May-go'), ('Panormus', 'Pa-nor-mus'),
        ('Traversette', 'Traver-set'), ('Col de la', 'Coll de la'), ('Atilius', 'A-tilly-us'), ('Ilipa', 'Ill-ipa'),
        ('Hadrumetum', 'Hadroo-meetum'), ('stades', 'stayds'), ('Acherbas', 'A-ker-bas'), ('Nepos', 'Nee-poss'), ('Appian', 'Appy-an'),
        ('Ecnomus', 'Ek-nomus'), ('Messana', 'Mess-ah-na'), ('Sempronius', 'Sem-pro-nee-us'), ('Flaminius', 'Fla-minny-us')]
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
