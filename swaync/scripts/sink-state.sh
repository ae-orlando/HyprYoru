#!/usr/bin/env bash
#   _   __     __               _______  __
#  | | / /__  / /_ ____ _  ___ / ___/ /_/ /
#  | |/ / _ \/ / // /  ' \/ -_) /__/ __/ /
#  |___/\___/_/\_,_/_/_/_/\__/\___/\__/_/

# By ae. Orlando

# Echo true when the default sink is unmuted (active), false when muted.
# Used as swaync buttons-grid update-command. Missing/failed queries are inactive.
set -uo pipefail
if command -v wpctl >/dev/null 2>&1 &&
    volume="$(LC_ALL=C wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null)" &&
    [[ "$volume" =~ ^Volume:[[:space:]]+[0-9]+([.][0-9]+)?[[:space:]]*$ ]]; then
    echo true
else
    echo false
fi
