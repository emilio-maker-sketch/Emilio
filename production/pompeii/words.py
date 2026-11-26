"""Word-level timestamps for build/vo.wav -> build/words.json"""
import json, soundfile as sf, numpy as np
from scipy.signal import resample_poly
from faster_whisper import WhisperModel
a, sr = sf.read('build/vo.wav', dtype='float32')
a = resample_poly(a, 2, 3).astype('float32')                # 24k -> 16k
m = WhisperModel('small.en', device='cpu', compute_type='int8', cpu_threads=4)
segs, _ = m.transcribe(a, word_timestamps=True, beam_size=1, vad_filter=False, condition_on_previous_text=False)
words = [{'w': w.word.strip(), 's': round(w.start, 3), 'e': round(w.end, 3)} for s in segs for w in (s.words or [])]
json.dump(words, open('build/words.json', 'w'))
print(len(words), 'words')
