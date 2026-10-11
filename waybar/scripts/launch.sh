#!/bin/bash
# by ae. Orlando
# _______________________________________________________________________

# Hard restart waybar + swaync (SUPER+R). Drops tray and notification
# state; prefer SIGUSR2 / swaync-client -rs for theme-only reloads.
killall -9 waybar
waybar &

killall -9 swaync
swaync &
