#!/usr/bin/env bash
# by ae. Orlando
# _______________________________________________________________________

# Set wallpaper + regenerate system-wide matugen palette.
# Usage: set-wall.sh [/path/to/wallpaper] [--pick]
#   No args      -> restore last wallpaper (or default anime3.png)
#   --pick       -> rofi list picker on ~/Pictures/wallpapers
set -euo pipefail

# Serialize concurrent runs (waypaper monitors=All can fire post_command
# more than once per pick); second invocation waits instead of double-
# reloading waybar.
exec 9>"$HOME/.cache/matugen/set-wall.lock"
flock 9

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

# Regenerate rofi wallpaper-image variables for the yoru-main theme.
"$HOME/.config/rofi/launchers/gen-wallpaper-rasi.sh" "$WALL" 2>/dev/null || true

# Wallpaper first (own the awww animation here; matugen [config.wallpaper]
# is set=false and only writes templates + fires post_hooks).
# Respect the dark/light toggle (toggle-theme.sh persists current-mode).
MODE="$(cat "$HOME/.cache/matugen/current-mode" 2>/dev/null || echo dark)"
[[ "$MODE" == "light" || "$MODE" == "dark" ]] || MODE="dark"
# Ensure awww-daemon is ready (autostart races set-wall.sh on login,
# like old ml4w-wallpaper wait_for_awww).
for _ in $(seq 1 30); do awww query >/dev/null 2>&1 && break; sleep 0.1; done
awww img --transition-type center --transition-duration 2 "$WALL"

# Wait for the awww transition to finish before generating the palette,
# so the new colors land together with the new wallpaper instead of ahead
# of it.
sleep 2

matugen image "$WALL" --mode "$MODE" --type scheme-tonal-spot --prefer closest-to-fallback

# Reload compositor for hypr colors.lua (matugen post_hooks single-handle
# waybar/swaync/kitty/btop; do not duplicate SIGUSR2/-rs here or the bar
# reloads twice). Graceful reload only: never killall the bar here.
hyprctl reload 2>/dev/null || true

echo "Wallpaper + palette applied: $WALL"
