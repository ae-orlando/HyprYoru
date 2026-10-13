#!/usr/bin/env bash
#   _   __     __               _______  __
#  | | / /__  / /_ ____ _  ___ / ___/ /_/ /
#  | |/ / _ \/ / // /  ' \/ -_) /__/ __/ /
#  |___/\___/_/\_,_/_/_/_/\__/\___/\__/_/

# By ae. Orlando

# Echo true when the default sink is unmuted (active), false when muted.
# Used as swaync buttons-grid update-command. Never fails the panel.
set -uo pipefail
if ! command -v wpctl >/dev/null 2>&1; then
    echo true
    exit 0
fi
if wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null | grep -q '\[MUTED\]'; then
    echo false
else
    echo true
fi
