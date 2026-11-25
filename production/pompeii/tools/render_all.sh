#!/bin/bash
# Render every chapter (2 in parallel), then join them into the finished episode.
set -e
cd "$(dirname "$0")/.."
ls script/*.md | xargs -n1 basename | cut -c1-2 | xargs -P2 -I{} sh -c 'python3 tools/render.py {} > build/render_{}.log 2>&1 && echo "chapter {} done"'
ls build/chapters/0[0-8]_*.mp4 | grep -v preview | sort | sed "s|^build/chapters/|file '|; s|$|'|" > build/chapters/list.txt
ffmpeg -v error -y -f concat -safe 0 -i build/chapters/list.txt -c copy -movflags +faststart build/World_Ancient_Disasters_E01_Pompeii.mp4
echo "episode done"
