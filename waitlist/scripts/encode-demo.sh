#!/usr/bin/env bash
# Turn a raw screen recording into the hero's demo files:
#   public/media/demo.mp4         H.264, plays everywhere
#   public/media/demo.webm        VP9, smaller where supported
#   public/media/demo-poster.webp the frame shown before (and instead of) playback
# All 1200x900 (4:3, twice the hero's display size), silent, fast-start.
#
# usage: scripts/encode-demo.sh <raw-recording> [--start S] [--end S] [--crop W:H:X:Y] [--poster S]
#   --start/--end  trim, in seconds (default: whole clip)
#   --crop         region of the raw frame to keep, before scaling (e.g. the app
#                  panel without browser chrome); default: centre-cropped to 4:3
#   --poster       second to take the poster from (default: 1)
set -euo pipefail

raw=${1:?usage: scripts/encode-demo.sh <raw-recording> [--start S] [--end S] [--crop W:H:X:Y] [--poster S]}
shift
start="" end="" crop="" poster_at=1
while [ $# -gt 0 ]; do
  case "$1" in
    --start) start=$2; shift 2 ;;
    --end) end=$2; shift 2 ;;
    --crop) crop=$2; shift 2 ;;
    --poster) poster_at=$2; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

out="$(dirname "$0")/../public/media"
mkdir -p "$out"
trim=()
[ -n "$start" ] && trim+=(-ss "$start")
[ -n "$end" ] && trim+=(-to "$end")
filters="${crop:+crop=$crop,}scale=1200:900:force_original_aspect_ratio=increase,crop=1200:900,fps=30"

ffmpeg -y -loglevel error "${trim[@]}" -i "$raw" -an -vf "$filters" \
  -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -movflags +faststart "$out/demo.mp4"
ffmpeg -y -loglevel error -i "$out/demo.mp4" -an \
  -c:v libvpx-vp9 -b:v 0 -crf 38 -row-mt 1 "$out/demo.webm"
ffmpeg -y -loglevel error -ss "$poster_at" -i "$out/demo.mp4" -frames:v 1 -c:v libwebp -quality 82 "$out/demo-poster.webp"

for f in demo.mp4 demo.webm demo-poster.webp; do
  printf '%-18s %6s KB\n' "$f" "$(( $(stat -c %s "$out/$f") / 1024 ))"
done
echo "Duration: $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$out/demo.mp4")s"
echo "Aim for under ~2000 KB per video; if over, trim, or raise -crf by 2-4."
