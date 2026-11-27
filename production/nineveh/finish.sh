#!/bin/bash
# Nineveh with the upgraded pipeline:
#   audit (pre-render accuracy gate) -> board render (content-aware camera, context transitions, adaptive grade, routes)
#   -> SFX + ambience -> stereo score with hushes -> 3D splice -> stereo look-ahead-ducked mix -> two-pass loudnorm
#   -> delivery encode (audio encoded once) -> automated QC + frame-level accuracy audit
set -e
cd "$(dirname "$0")"
D=../docengine
python3 $D/audit.py > build/audit_pre.log 2>&1 || { echo "AUDIT FAILED (MISMATCH) - fix before rendering"; tail -20 build/audit_pre.log; exit 1; }
echo AUDIT_OK
rm -rf build/chunks
python3 make3d.py
[ -f build/words.json ] || python3 words.py
python3 ../docengine/captions.py build/timeline.json build/words.json build/captions_en.srt
bash render_kaz.sh
python3 make_cues.py
python3 sample_sound.py full
python3 - <<'PY'
import json
c = json.load(open('build/cues.json')); keep = {'duration', 'film', 'pulse', 'tension', 'roll'}
json.dump({k: (v if k in keep else []) for k, v in c.items()}, open('build/cues_ambient.json', 'w'))
PY
python3 sound_bed.py build/cues_ambient.json build/ambient_synth.wav
python3 $D/mix.py score build/timeline.json /home/user/Emilio/production/assets/music music_plan.json build/music_v2.wav
echo SOUND_DONE
cd build
T=$(python3 -c "import json;print(json.load(open('timeline.json'))['total'])")
G=~/.claude/skills/ghost-editor/scripts/transitions.py
python3 $G join board.mp4@0-134.9 sample/tablet3d.mp4@1.5-9.2 board.mp4@142.6-326.0 sample/tablet3d.mp4@11.0-17.8 board.mp4@332.8-711.9 sample/tablet3d.mp4@18.0-30.0 board.mp4@723.9-$T \
  -t dissolve -t dissolve -t zoom_blur -t dissolve -t dissolve -t dissolve --audio none --crf 19 -o board_joined.mp4
echo JOIN_DONE
python3 ../$D/mix.py mix vo.wav music_v2.wav ambient_synth.wav sfx_real_full.wav mix_v2.wav
# delivery: video to ~285 MB in two passes, then mux the loudness-normalised audio ONCE (no second AAC generation)
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 board_joined.mp4)
VB=$(python3 -c "print(int(285*8*1024/$DUR - 256))")
ffmpeg -v error -y -i board_joined.mp4 -c:v libx264 -preset medium -b:v ${VB}k -pass 1 -passlogfile pp2 -an -f mp4 /dev/null
ffmpeg -v error -y -i board_joined.mp4 -c:v libx264 -preset medium -b:v ${VB}k -maxrate $((VB*2))k -bufsize $((VB*4))k -pass 2 -passlogfile pp2 -an video_v2.mp4
python3 ../$D/mix.py mux video_v2.mp4 mix_v2.wav Nineveh.mp4
echo MIX_DONE
cd ..
python3 $D/qc_auto.py build/Nineveh.mp4 --srt build/captions_en.srt > build/qc_auto.log 2>&1 || true
python3 $D/audit.py --frames > build/audit_final.log 2>&1 || true
echo FINISH_DONE
