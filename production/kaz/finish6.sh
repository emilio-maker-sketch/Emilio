#!/bin/bash
# v6: splice the three.js CT-scan scene (twice) into the v5 board with ghost-editor transitions, real-SFX bed, deliver.
cd "$(dirname "$0")/build"
until grep -q FINISH_DONE finish.log 2>/dev/null; do sleep 20; done      # let the v5 encode finish first
G=~/.claude/skills/ghost-editor/scripts/transitions.py
python3 $G join board.mp4@0-8.3 sample/ct.mp4@0.3-16.7 board.mp4@24.7-949.4 sample/ct.mp4@6.2-16.7 board.mp4@959.9-1208.7 \
  -t zoom_blur -t whip -t zoom_blur -t whip --audio none --crf 19 -o board_v6.mp4 && echo JOIN_DONE
bash /root/.claude/skills/kaz-documentary/scripts/mix_and_mux.sh board_v6.mp4 vo.wav bed_v6.wav final_master_v6.mp4 && echo MIX_DONE
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 final_master_v6.mp4)
VB=$(python3 -c "print(int(285*8*1024/$D - 128))")
ffmpeg -v error -y -i final_master_v6.mp4 -c:v libx264 -preset medium -b:v ${VB}k -pass 1 -passlogfile p6 -an -f mp4 /dev/null && \
ffmpeg -v error -y -i final_master_v6.mp4 -c:v libx264 -preset medium -b:v ${VB}k -maxrate $((VB*2))k -bufsize $((VB*4))k -pass 2 -passlogfile p6 -c:a aac -b:a 128k -movflags +faststart HaremConspiracy_v6.mp4 && echo FINISH6_DONE
