#!/usr/bin/env bash
# by ae. Orlando
# _______________________________________________________________________

# Full system update for waybar custom/updates on-click.
# Refresh + notification fire the moment the update finishes; the window
# closes itself right after.

kitty -e bash -c '
    yay -Syu
    rc=$?
    pkill -RTMIN+8 waybar
    if [ $rc -eq 0 ]; then
        notify-send "System update" "Finished — update count refreshed."
    else
        notify-send -u critical "System update" "Failed (exit $rc)"
    fi
'
