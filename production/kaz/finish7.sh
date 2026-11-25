#!/bin/bash
# v7: full QC fix pass. Re-render the board, rebuild cues + real-SFX + ambient beds, splice the 3D CT scenes, mix, deliver.
set -e
cd "$(dirname "$0")"
bash render_kaz.sh
python3 make_cues.py
python3 sample_sound.py full
python3 - <<'EOF'
import json
c = json.load(open('build/cues.json')); keep = {'duration', 'film', 'pulse', 'tension', 'roll'}
json.dump({k: (v if k in keep else []) for k, v in c.items()}, open('build/cues_ambient.json', 'w'))
EOF
python3 sound_bed.py build/cues_ambient.json build/ambient_synth.wav
python3 - <<'EOF'
import soundfile as sf
m, _ = sf.read('build/music_only.wav', dtype='float32'); a, _ = sf.read('build/ambient_synth.wav', dtype='float32'); r, _ = sf.read('build/sfx_real_full.wav', dtype='float32')
L = len(m); out = m.copy(); out[:min(L, len(a))] += a[:L]; out[:min(L, len(r))] += r[:L]
sf.write('build/bed_v7.wav', out, 48000, subtype='FLOAT')
EOF
echo SOUND_DONE
cd build
G=~/.claude/skills/ghost-editor/scripts/transitions.py
python3 $G join board.mp4@0-8.3 sample/ct.mp4@0.3-16.7 board.mp4@24.7-949.4 sample/ct.mp4@6.2-16.7 board.mp4@959.9-1208.7 \
  -t zoom_blur -t whip -t zoom_blur -t whip --audio none --crf 19 -o board_v7.mp4
echo JOIN_DONE
bash /root/.claude/skills/kaz-documentary/scripts/mix_and_mux.sh board_v7.mp4 vo.wav bed_v7.wav final_master_v7.mp4
echo MIX_DONE
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 final_master_v7.mp4)
VB=$(python3 -c "print(int(285*8*1024/$D - 128))")
ffmpeg -v error -y -i final_master_v7.mp4 -c:v libx264 -preset medium -b:v ${VB}k -pass 1 -passlogfile p7 -an -f mp4 /dev/null
ffmpeg -v error -y -i final_master_v7.mp4 -c:v libx264 -preset medium -b:v ${VB}k -maxrate $((VB*2))k -bufsize $((VB*4))k -pass 2 -passlogfile p7 -c:a aac -b:a 128k -movflags +faststart HaremConspiracy_v7.mp4
echo FINISH7_DONE
