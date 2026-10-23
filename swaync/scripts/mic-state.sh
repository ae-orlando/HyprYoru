#!/usr/bin/env bash
#     __  ____     ______       __            __
#    /  |/  (_)___/ __/ /____ _/ /____   ___ / /
#   / /|_/ / / __/\ \/ __/ _ `/ __/ -_) (_-</ _ \
#  /_/  /_/_/\__/___/\__/\_,_/\__/\__(_)___/_//_/

#  By ae. Orlando
#  ==========================================================

# Echo true when the default source (mic) is unmuted (active).
# Missing/failed queries are inactive; never report an unavailable mic as live.
set -uo pipefail
if command -v wpctl >/dev/null 2>&1 &&
    volume="$(LC_ALL=C wpctl get-volume @DEFAULT_AUDIO_SOURCE@ 2>/dev/null)" &&
    [[ "$volume" =~ ^Volume:[[:space:]]+[0-9]+([.][0-9]+)?[[:space:]]*$ ]]; then
    echo true
else
    echo false
fi
