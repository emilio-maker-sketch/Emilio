#!/bin/bash
cd "$(dirname "$0")"
python3 kaz_engine.py full 0 900 build/prev_board.mp4 && \
ffmpeg -v error -y -t 30 -i build/vo.wav -t 30 -i build/bed.wav -filter_complex "[0:a]aresample=48000,asplit=2[v1][v2];[1:a]aformat=channel_layouts=mono[b];[b][v1]sidechaincompress=threshold=0.05:ratio=6:attack=20:release=300[bd];[bd][v2]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5[a]" -map "[a]" -ar 48000 build/prev_audio.wav && \
ffmpeg -v error -y -i build/prev_board.mp4 -i build/prev_audio.wav -map 0:v -map 1:a -c:v libx264 -preset veryfast -crf 24 -pix_fmt yuv420p -c:a aac -b:a 160k -shortest -movflags +faststart build/preview_first_30s.mp4 && echo PREVIEW_DONE
