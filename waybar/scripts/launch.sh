#!/bin/bash
# Reload waybar + swaync (SUPER+R). Uses in-place reload to keep
# tray and notification state.
pkill -SIGUSR2 waybar || (waybar &)

swaync-client -rs || (swaync &)
