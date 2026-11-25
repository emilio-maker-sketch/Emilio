"""Free voice audition: the opening paragraph in several Kokoro voices (local, no cost)."""
import os, numpy as np, soundfile as sf, subprocess
from kokoro_onnx import Kokoro
from script_parse import chapters, ROOT
from narrate_local import norm, sentences
k = Kokoro('/home/user/models/kokoro-v1.0.onnx', '/home/user/models/voices-v1.0.bin')
text = chapters()[0]['paras'][0]['text']
out = os.path.join(ROOT, 'voice_samples')
for v, lang in [('bm_george', 'en-gb'), ('bm_fable', 'en-gb'), ('bm_lewis', 'en-gb'), ('bm_daniel', 'en-gb'),
                ('am_michael', 'en-us'), ('am_onyx', 'en-us')]:
    parts = []
    for s in sentences(text):
        a, sr = k.create(norm(s), voice=v, speed=0.92, lang=lang)
        parts += [a, np.zeros(int(0.38 * sr), dtype=a.dtype)]
    wav = os.path.join(out, v + '.wav'); sf.write(wav, np.concatenate(parts), sr)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-b:a', '160k', wav[:-4] + '.mp3']); os.remove(wav)
    print(v)
