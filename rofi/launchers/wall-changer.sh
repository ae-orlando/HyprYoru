#!/usr/bin/env bash

# --- Configuration ---
# System wallpaper dir (229 wallpapers). Falls back to repo walls.
WALLDIR="$HOME/Pictures/wallpapers"
[ -d "$WALLDIR" ] || WALLDIR="$HOME/Linux/walls"
# Using your specific theme path
ROFI_THEME="$HOME/.config/rofi/styles/wall-picker.rasi"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/wallpaper-thumbs"
THUMB_SIZE="400x400"

# Ensure directories exist
mkdir -p "$CACHE_DIR"

# --- 1. Find Images (sorted for deterministic order) ---
mapfile -t IMG_FILES < <(find "$WALLDIR" -type f \( -iname "*.jpg" -o -iname "*.png" -o -iname "*.jpeg" -o -iname "*.webp" \) | sort)

if [ "${#IMG_FILES[@]}" -eq 0 ]; then
    notify-send "Error" "No images found in $WALLDIR"
    exit 1
fi

# --- Random mode: pick without menu (used by SHIFT+SUPER+W) ---
if [ "${1:-}" = "--random" ]; then
    WALLPAPER_PATH="$(printf '%s\n' "${IMG_FILES[@]}" | shuf -n 1)"
    if [ -z "$WALLPAPER_PATH" ] || [ ! -f "$WALLPAPER_PATH" ]; then
        notify-send "Error" "No images found in $WALLDIR"
        exit 1
    fi
    if "$HOME/.config/hypr/scripts/set-wall.sh" "$WALLPAPER_PATH"; then
        notify-send "Wallpaper Changed" "$(basename "$WALLPAPER_PATH") applied (random)."
    fi
    exit 0
fi

# --- 2. Generate Thumbnails & Rofi Input ---
# Map display name -> full path and select by name (-format s). Selecting by
# rofi index (-format i) is wrong once you type to filter: the index refers to
# the filtered list, so it applies a different wallpaper than shown.
declare -A PATH_BY_NAME
ROFI_INPUT=""
for IMG_FILE in "${IMG_FILES[@]}"; do
    BASENAME=$(basename "$IMG_FILE")
    NAME="$BASENAME"
    if [[ -n "${PATH_BY_NAME[$NAME]:-}" ]]; then
        REL="${IMG_FILE#"$WALLDIR"/}"
        NAME="$BASENAME (${REL%/*})"
    fi
    PATH_BY_NAME["$NAME"]="$IMG_FILE"
    
    # Create thumbnail if it doesn't exist (ImageMagick preferred, ffmpeg fallback)
    THUMB_FILE="$CACHE_DIR/${BASENAME}.png"
    if [ ! -f "$THUMB_FILE" ]; then
        if command -v magick >/dev/null 2>&1; then
            magick "$IMG_FILE" -auto-orient -thumbnail "${THUMB_SIZE}^" -gravity center -extent "$THUMB_SIZE" "$THUMB_FILE" 2>/dev/null
        elif command -v convert >/dev/null 2>&1; then
            convert "$IMG_FILE" -auto-orient -thumbnail "${THUMB_SIZE}^" -gravity center -extent "$THUMB_SIZE" "$THUMB_FILE" 2>/dev/null
        else
            ffmpeg -y -loglevel error -i "$IMG_FILE" -vf "scale=400:400:force_original_aspect_ratio=increase,crop=400:400" "$THUMB_FILE" 2>/dev/null || cp "$IMG_FILE" "$THUMB_FILE"
        fi
    fi
    
    # Build the string for Rofi (display name carries the icon; full path
    # is resolved via PATH_BY_NAME so filtering can't misalign the pick)
    ROFI_INPUT+="${NAME}\0icon\x1f${THUMB_FILE}\n"
done

# --- 3. Show Rofi Menu (select by name: safe under filtering) ---
SELECTED_NAME=$(echo -en "$ROFI_INPUT" | rofi -dmenu \
    -i \
    -show-icons \
    -theme "$ROFI_THEME" \
    -p "Choose wallpaper" \
    -format 's' \
    -selected-row 0
)

# Exit if escaped
[ -z "${SELECTED_NAME:-}" ] && exit 0

# Resolve the display name back to a full path
WALLPAPER_PATH="${PATH_BY_NAME[$SELECTED_NAME]:-}"
if [ -z "$WALLPAPER_PATH" ] || [ ! -f "$WALLPAPER_PATH" ]; then
    notify-send "Error" "Could not resolve wallpaper: $SELECTED_NAME"
    exit 1
fi

# --- 4. Apply via the single canonical path (set-wall.sh -> matugen -> awww) ---
# No direct awww/swww/hyprpaper calls here: matugen already sets the wallpaper
# through [config.wallpaper], so one call = one transition, one palette.
if "$HOME/.config/hypr/scripts/set-wall.sh" "$WALLPAPER_PATH"; then
    notify-send "Wallpaper Changed" "$(basename "$WALLPAPER_PATH") applied."
fi

exit 0
