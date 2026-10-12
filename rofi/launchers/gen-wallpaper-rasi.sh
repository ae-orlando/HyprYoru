#!/usr/bin/env bash
# by ae. Orlando
# _______________________________________________________________________

# Generate rofi wallpaper-image variables for the yoru-main theme.
# Mirrors ML4W generate_image_variants: downscaled + blurred wallpaper variant,
# referenced with height scaling exactly like the reference implementation.
# Usage: gen-wallpaper-rasi.sh [/path/to/wallpaper]
#   No args -> reads ~/.cache/matugen/current-wallpaper (written by set-wall.sh).
# Writes ~/.cache/rofi/current-wallpaper.rasi defining @current-image.
# Called from hypr/scripts/set-wall.sh on every wallpaper change; safe to re-run.
set -euo pipefail

WALL="${1:-}"
if [ -z "$WALL" ] && [ -f "$HOME/.cache/matugen/current-wallpaper" ]; then
    WALL="$(cat "$HOME/.cache/matugen/current-wallpaper")"
fi
if [ -z "$WALL" ] || [ ! -f "$WALL" ]; then
    exit 0
fi

OUT_DIR="$HOME/.cache/rofi"
BLURRED="$OUT_DIR/blurred_wallpaper.png"
OUT="$OUT_DIR/current-wallpaper.rasi"
mkdir -p "$OUT_DIR"

if command -v magick >/dev/null 2>&1; then
    # Single pass (was resize + blur in two invocations): same rofi backdrop
    # look at a fraction of the cost on 10MB+ PNGs.
    magick "$WALL" -resize 50% -blur 0x8 "$BLURRED"
else
    BLURRED="$WALL"
fi
printf '* {\n    current-image: url("%s", height);\n}\n' "$BLURRED" > "$OUT"
