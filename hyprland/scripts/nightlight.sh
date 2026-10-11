#!/usr/bin/env bash
# by ae. Orlando
# _______________________________________________________________________

# Toggle hyprsunset blue-light filter: 6500K (off/neutral) <-> 4000K (warm).
# Requires: pacman -S hyprsunset (daemon autostarted, see autostart.lua)
set -euo pipefail

DAY_TEMP=6500
NIGHT_TEMP=4000
STATE_FILE="${XDG_CACHE_HOME:-$HOME/.cache}/nightlight-state"

# Make sure the daemon is up (no-op if already running)
if ! pgrep -x hyprsunset >/dev/null 2>&1; then
    hyprsunset >/dev/null 2>&1 & disown
    sleep 0.5
fi

if [ -f "$STATE_FILE" ] && [ "$(cat "$STATE_FILE")" = "on" ]; then
    hyprctl hyprsunset temperature "$DAY_TEMP" >/dev/null
    echo "off" > "$STATE_FILE"
    notify-send "Night light off" "Color temperature back to ${DAY_TEMP}K."
else
    hyprctl hyprsunset temperature "$NIGHT_TEMP" >/dev/null
    echo "on" > "$STATE_FILE"
    notify-send "Night light on" "Warm filter applied (${NIGHT_TEMP}K)."
fi
