#!/bin/bash
# After render_kaz.sh: mix voice + bed (ducked, -14 LUFS), master MP4, and a <300 MB delivery copy.
cd "$(dirname "$0")"
until grep -q BOARD_DONE build/render.log 2>/dev/null; do sleep 20; done
bash /root/.claude/skills/kaz-documentary/scripts/mix_and_mux.sh build/board.mp4 build/vo.wav build/bed.wav build/final_master.mp4 && echo MIX_DONE
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 build/final_master.mp4)
VB=$(python3 -c "print(int(285*8*1024/$D - 128))")
ffmpeg -v error -y -i build/final_master.mp4 -c:v libx264 -preset medium -b:v ${VB}k -pass 1 -passlogfile build/p2 -an -f mp4 /dev/null && \
ffmpeg -v error -y -i build/final_master.mp4 -c:v libx264 -preset medium -b:v ${VB}k -maxrate $((VB*2))k -bufsize $((VB*4))k -pass 2 -passlogfile build/p2 -c:a aac -b:a 128k -movflags +faststart build/HaremConspiracy.mp4 && echo FINISH_DONE
