#!/usr/bin/env bash
# Set wallpaper + regenerate system-wide matugen palette.
# Usage: set-wall.sh [/path/to/wallpaper] [--pick]
#   No args      -> restore last wallpaper (or default anime3.png)
#   --pick       -> rofi list picker on ~/Pictures/wallpapers
set -euo pipefail

WALL_DIR="$HOME/Pictures/wallpapers"
DEFAULT_WALL="$WALL_DIR/anime3.png"
# Seeds shipped in dotfiles (installer copies them into WALL_DIR).
# ~/.config/hypr resolves through the dotfiles symlink.
SEED_DIR="$HOME/.config/hypr/wallpapers"
SEED_WALL="$SEED_DIR/anime3.png"
CACHE_WALL="$HOME/.cache/matugen/current-wallpaper"
HYPRLOCK_WALL="$HOME/.cache/hyprlock/wallpaper.png"

pick_wallpaper() {
    # Rofi dmenu picker (plain list, no filebrowser/xdg-open side-effects);
    # falls back to default on cancel
    local sel
    sel=$(find "$WALL_DIR" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" -o -iname "*.gif" -o -iname "*.avif" \) -printf "%f\n" | sort | rofi -dmenu -i -p "Wallpaper" \
        -theme "$HOME/.config/rofi/launchers/type-6/style-9.rasi" 2>/dev/null || true)
    if [ -n "${sel:-}" ] && [ -f "$WALL_DIR/$sel" ]; then
        echo "$WALL_DIR/$sel"
    else
        echo "$DEFAULT_WALL"
    fi
}

if [ "${1:-}" = "--pick" ]; then
    WALL="$(pick_wallpaper)"
elif [ -n "${1:-}" ]; then
    WALL="$1"
elif [ -f "$CACHE_WALL" ]; then
    WALL="$(cat "$CACHE_WALL")"
    [ -f "$WALL" ] || WALL="$DEFAULT_WALL"
else
    WALL="$DEFAULT_WALL"
fi

if [ ! -f "$WALL" ]; then
    # Fresh-install fallback: use the dotfiles seed before giving up.
    SEED_CANDIDATE="$SEED_DIR/$(basename "$WALL")"
    if [ -f "$SEED_CANDIDATE" ]; then
        WALL="$SEED_CANDIDATE"
    elif [ -f "$SEED_WALL" ]; then
        WALL="$SEED_WALL"
    fi
fi

if [ ! -f "$WALL" ]; then
    echo "Wallpaper not found: $WALL" >&2
    exit 1
fi

mkdir -p "$(dirname "$CACHE_WALL")"
echo "$WALL" > "$CACHE_WALL"
mkdir -p "$(dirname "$HYPRLOCK_WALL")"
cp -f "$WALL" "$HYPRLOCK_WALL"

# matugen sets wallpaper via [config.wallpaper] (awww) + writes all templates
matugen image "$WALL" --mode dark --type scheme-tonal-spot --prefer closest-to-fallback

# Wait for the awww transition (--transition-duration 2 in matugen config) to
# finish before reloading bars, so the new palette lands together with the
# new wallpaper instead of ahead of it.
sleep 2

# Reload compositor + bars (matugen post_hooks handle kitty/btop).
# Graceful reloads only: SIGUSR2 makes waybar re-read config/CSS in place,
# swaync-client -rs reloads notification CSS. Never killall the bar here:
# killing waybar/swaync drops tray icons and notification state.
hyprctl reload 2>/dev/null || true
pkill -SIGUSR2 waybar 2>/dev/null || true
swaync-client -rs 2>/dev/null || true

echo "Wallpaper + palette applied: $WALL"
