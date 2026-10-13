#!/usr/bin/env bash
#   ________               ______               __
#  /_  __/ /  ___ __ _  __/_  __/__  ___ ____ _/ /__
#   / / / _ \/ -_)  ' \/ -_) / / _ \/ _ `/ _ `/ / -_)
#  /_/ /_//_/\__/_/_/_/\__/_/  \___/\_, /\_, /_/\__/
#                                  /___//___/
# by ae. Orlando
# _______________________________________________________________________

# Toggle system palette between dark and light mode.
# Adapted from ML4W ml4w-toggle-theme + gtk-theme-switcher flow:
# flips gtk-application-prefer-dark-theme, re-runs matugen on the
# current wallpaper with --mode light|dark, then graceful-reloads
# swaync / waybar / hyprland. Persists mode to
# ~/.cache/matugen/current-mode so set-wall.sh keeps it.
set -euo pipefail

MODE_FILE="$HOME/.cache/matugen/current-mode"
WALL_FILE="$HOME/.cache/matugen/current-wallpaper"
GTK3="$HOME/.config/gtk-3.0/settings.ini"
GTK4="$HOME/.config/gtk-4.0/settings.ini"
KEY="gtk-application-prefer-dark-theme"

current="dark"
if [ -f "$MODE_FILE" ]; then
    cached="$(cat "$MODE_FILE" 2>/dev/null || echo dark)"
    case "$cached" in
    light | dark) current="$cached" ;;
    esac
elif [ -f "$GTK3" ]; then
    pref="$(grep -E "^$KEY=" "$GTK3" | awk -F'=' '{print $2}' || true)"
    case "$pref" in
    0 | false) current="light" ;;
    *) current="dark" ;;
    esac
fi

if [ "$current" = "dark" ]; then
    NEW="light"
    gtk3_value=0
    gtk4_value=false
    gsettings_value="prefer-light"
else
    NEW="dark"
    gtk3_value=1
    gtk4_value=true
    gsettings_value="prefer-dark"
fi

mkdir -p "$(dirname "$MODE_FILE")"
echo "$NEW" >"$MODE_FILE"

set_gtk_pref() {
    local file="$1" value="$2"
    [ -f "$file" ] || return 0
    if grep -qE "^$KEY=" "$file"; then
        sed -i "s/^$KEY=.*/$KEY=$value/" "$file"
    else
        printf '%s=%s\n' "$KEY" "$value" >>"$file"
    fi
}

set_gtk_pref "$GTK3" "$gtk3_value"
set_gtk_pref "$GTK4" "$gtk4_value"

if command -v gsettings >/dev/null 2>&1; then
    gsettings set org.gnome.desktop.interface color-scheme "$gsettings_value" 2>/dev/null || true
fi

WALL=""
if [ -f "$WALL_FILE" ]; then
    WALL="$(cat "$WALL_FILE" 2>/dev/null || true)"
fi
if [ -n "${WALL:-}" ] && [ -f "$WALL" ] && command -v matugen >/dev/null 2>&1; then
    # Palette-only (matugen [config.wallpaper] set=false, so no wallpaper
    # re-animation flash on theme toggle).
    matugen image "$WALL" --mode "$NEW" --type scheme-tonal-spot --prefer closest-to-fallback
else
    echo "No wallpaper found ($WALL_FILE); palette unchanged, GTK + mode only." >&2
fi

# Graceful reload only (never killall): matugen post_hooks single-handle
# waybar/swaync/kitty/btop; hyprctl covers hypr colors.lua. Do not duplicate
# SIGUSR2/-rs here or the bar reloads twice.
hyprctl reload 2>/dev/null || true

echo "Switched to $NEW theme."
