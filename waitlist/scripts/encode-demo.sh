#!/usr/bin/env bash
# Turn a raw screen recording into the hero's demo files:
#   public/media/<name>.mp4         H.264, plays everywhere
#   public/media/<name>.webm        VP9, smaller where supported
#   public/media/<name>-poster.webp the frame shown before (and instead of) playback
# Silent and fast-start; 1200x900 (4:3) unless --size says otherwise.
#
# usage: scripts/encode-demo.sh <raw-recording> [--start S] [--end S] [--crop W:H:X:Y] [--poster S]
#                               [--size WxH] [--name NAME]
#   --start/--end  trim, in seconds (default: whole clip)
#   --crop         region of the raw frame to keep, before scaling (e.g. the app
#                  panel without browser chrome); default: centre-cropped to 4:3
#   --poster       second to take the poster from (default: 1)
#   --size         output size (default: 1200x900)
#   --name         output file name, without extension (default: demo)
set -euo pipefail

raw=${1:?usage: scripts/encode-demo.sh <raw-recording> [--start S] [--end S] [--crop W:H:X:Y] [--poster S]}
shift
start="" end="" crop="" poster_at=1 size=1200x900 name=demo
while [ $# -gt 0 ]; do
  case "$1" in
    --start) start=$2; shift 2 ;;
    --end) end=$2; shift 2 ;;
    --crop) crop=$2; shift 2 ;;
    --poster) poster_at=$2; shift 2 ;;
    --size) size=$2; shift 2 ;;
    --name) name=$2; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

out="$(dirname "$0")/../public/media"
mkdir -p "$out"
trim=()
[ -n "$start" ] && trim+=(-ss "$start")
[ -n "$end" ] && trim+=(-to "$end")
w=${size%x*} h=${size#*x}
filters="${crop:+crop=$crop,}scale=$w:$h:force_original_aspect_ratio=increase:flags=lanczos,crop=$w:$h,fps=30"

ffmpeg -y -loglevel error "${trim[@]}" -i "$raw" -an -vf "$filters" \
  -c:v libx264 -preset slow -crf 26 -pix_fmt yuv420p -movflags +faststart "$out/$name.mp4"
# One tile column: some GPU decoders draw a magenta row along the top of each
# tile, which showed as a dashed line over the video.
ffmpeg -y -loglevel error -i "$out/$name.mp4" -an \
  -c:v libvpx-vp9 -b:v 0 -crf 38 -row-mt 1 -tile-columns 0 "$out/$name.webm"
ffmpeg -y -loglevel error -ss "$poster_at" -i "$out/$name.mp4" -frames:v 1 -c:v libwebp -quality 82 "$out/$name-poster.webp"

for f in "$name.mp4" "$name.webm" "$name-poster.webp"; do
  printf '%-18s %6s KB\n' "$f" "$(( $(stat -c %s "$out/$f") / 1024 ))"
done
echo "Duration: $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$out/$name.mp4")s"
echo "Aim for under ~2000 KB per video; if over, trim, or raise -crf by 2-4."
