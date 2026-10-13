#!/usr/bin/env bash
#     ___  __  ______       __            __
#    / _ )/ /_/ __/ /____ _/ /____   ___ / /
#   / _  / __/\ \/ __/ _ `/ __/ -_) (_-</ _ \
#  /____/\__/___/\__/\_,_/\__/\__(_)___/_//_/

# By ae. Orlando
# ==================================================

# Echo true when bluetooth controller is powered.
set -uo pipefail
if ! command -v bluetoothctl >/dev/null 2>&1; then
    echo false
    exit 0
fi
if bluetoothctl show 2>/dev/null | grep -q "Powered: yes"; then
    echo true
else
    echo false
fi
