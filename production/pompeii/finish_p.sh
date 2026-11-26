#!/bin/bash
# Pompeii: board render -> cues -> real + synthesized SFX -> ambient bed -> music -> 3D splice -> mix -> delivery encode
set -e
cd "$(dirname "$0")"
bash render_kaz.sh
python3 make_cues.py
python3 sample_sound.py full
python3 - <<'PY'
import json
c = json.load(open('build/cues.json')); keep = {'duration', 'film', 'pulse', 'tension', 'roll'}
json.dump({k: (v if k in keep else []) for k, v in c.items()}, open('build/cues_ambient.json', 'w'))
PY
python3 sound_bed.py build/cues_ambient.json build/ambient_synth.wav
python3 make_music.py
python3 - <<'PY'
import soundfile as sf
m, _ = sf.read('build/music_only.wav', dtype='float32'); a, _ = sf.read('build/ambient_synth.wav', dtype='float32'); r, _ = sf.read('build/sfx_real_full.wav', dtype='float32')
L = len(m); out = m.copy(); out[:min(L, len(a))] += a[:L]; out[:min(L, len(r))] += r[:L]
sf.write('build/bed.wav', out, 48000, subtype='FLOAT')
PY
echo SOUND_DONE
cd build
D=$(python3 -c "import json;print(json.load(open('timeline.json'))['total'])")
G=~/.claude/skills/ghost-editor/scripts/transitions.py
python3 $G join board.mp4@0-215.4 sample/eruption3d.mp4@0-12.8 board.mp4@228.2-423.4 sample/eruption3d.mp4@13.1-17.5 board.mp4@427.8-574.9 sample/eruption3d.mp4@18.0-26.9 board.mp4@583.8-$D \
  -t zoom_blur -t whip -t zoom_blur -t whip -t zoom_blur -t whip --audio none --crf 19 -o board_joined.mp4
echo JOIN_DONE
bash /root/.claude/skills/kaz-documentary/scripts/mix_and_mux.sh board_joined.mp4 vo.wav bed.wav final_master.mp4
echo MIX_DONE
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 final_master.mp4)
VB=$(python3 -c "print(int(285*8*1024/$D - 128))")
ffmpeg -v error -y -i final_master.mp4 -c:v libx264 -preset medium -b:v ${VB}k -pass 1 -passlogfile pp -an -f mp4 /dev/null
ffmpeg -v error -y -i final_master.mp4 -c:v libx264 -preset medium -b:v ${VB}k -maxrate $((VB*2))k -bufsize $((VB*4))k -pass 2 -passlogfile pp -c:a aac -b:a 128k -movflags +faststart Pompeii.mp4
echo FINISH_DONE
