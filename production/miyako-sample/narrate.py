"""Narration lines for the Miyako style sample -> build/vo/NN.wav + build/vo/lines.json"""
import json, os, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
B = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build', 'vo'); os.makedirs(B, exist_ok=True)
LINES = [
 "On the afternoon of March eleventh, twenty eleven, Miyako was an ordinary fishing town on the northeast coast of Japan.",
 "At two forty-six, beneath the Pacific seafloor, the earth tore open.",
 "A magnitude nine earthquake. The most powerful ever recorded in Japan.",
 "The shaking lasted almost six minutes. Then, the warnings began.",
 "Forty minutes later, the sea came over the wall.",
 "In moments, the water rose above the rooftops. Boats were carried through the streets. Cars, houses, entire lives, swept inland.",
 "Along this coast, the waves would reach nearly forty metres.",
 "By nightfall, much of Miyako lay in ruins.",
]
k = Kokoro('/home/user/models/kokoro-v1.0.onnx', '/home/user/models/voices-v1.0.bin')
out = []
for i, t in enumerate(LINES):
    a, sr = k.create(t, voice='bm_george', speed=0.86, lang='en-gb')
    p = os.path.join(B, f'{i:02d}.wav'); sf.write(p, a, sr)
    out.append({'i': i, 'text': t, 'dur': round(len(a) / sr, 2)}); print(i, out[-1]['dur'])
json.dump(out, open(os.path.join(B, 'lines.json'), 'w'), indent=1)
