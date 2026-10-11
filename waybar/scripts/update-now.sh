#!/usr/bin/env bash
# by ae. Orlando
# _______________________________________________________________________

# Full system update for waybar custom/updates on-click.
# Refreshes the module immediately afterwards instead of waiting for the next poll.
kitty -e yay -Syu
rm -f /tmp/waybar-aur-count
pkill -RTMIN+8 waybar 2>/dev/null
notify-send "System update" "Finished — update count refreshing."
