#!/usr/bin/env bash
# Repair interrupted theme publications before Waybar and SwayNC read them.
set -euo pipefail

python3 "$HOME/.config/hypr/scripts/palette.py" recover

"$HOME/.config/waybar/scripts/start-waybar.sh" &
"$HOME/.config/swaync/scripts/start-swaync.sh" &

# awww-daemon starts separately; set-wall.sh waits for it to become ready.
exec "$HOME/.config/hypr/scripts/set-wall.sh"
