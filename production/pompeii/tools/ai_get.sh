#!/bin/bash
# usage: ai_get.sh <index> <url>   — record and download one generated image
cd "$(dirname "$0")/../build/img/ai"
echo "$1 $2" >> urls.txt
curl -s -o "ai_$(printf %02d $1).png" "$2"
