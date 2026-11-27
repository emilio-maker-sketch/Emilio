#!/bin/bash
# Render the Kaz board video in 4 parallel chunks (resumable), then concat.
cd "$(dirname "$0")"
N=$(python3 -c "import json;print(int(json.load(open('build/timeline.json'))['total']*30))")
mkdir -p build/chunks
P=4; S=$(( (N + P - 1) / P ))
for i in $(seq 0 $((P-1))); do
  a=$((i*S)); b=$(( (i+1)*S < N ? (i+1)*S : N ))
  [ -f build/chunks/c$i.mp4 ] || ( python3 kaz_engine.py full $a $b build/chunks/c$i.tmp.mp4 && mv build/chunks/c$i.tmp.mp4 build/chunks/c$i.mp4 && echo "chunk $i done" ) &
done
wait
ls build/chunks/c*.mp4 | sort -V | sed "s#build/chunks/#file '#; s#\$#'#" > build/chunks/list.txt
ffmpeg -v error -y -f concat -safe 0 -i build/chunks/list.txt -c copy build/board.mp4 && echo BOARD_DONE
