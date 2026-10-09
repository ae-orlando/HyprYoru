#!/usr/bin/env bash
# Cycle waybar pleasure-animation mode: 0 pacman -> 1 wave -> 2 bounce -> 0 ...
MODE_FILE="/tmp/waybar-animation-mode"
mode=0
if [ -f "$MODE_FILE" ]; then
    read -r mode < "$MODE_FILE" 2>/dev/null
fi
case "$mode" in
    0|1|2) ;;
    *) mode=0 ;;
esac
echo $(((mode + 1) % 3)) > "$MODE_FILE"
