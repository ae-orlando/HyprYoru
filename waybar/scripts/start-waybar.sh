#!/usr/bin/env bash
# Prefer an optional local test build; otherwise use the distro Waybar.
# Author: ae Orland
# GitHub: https://github.com/ae-orlando
set -euo pipefail

local_bar="${XDG_DATA_HOME:-$HOME/.local/share}/yoru/waybar/waybar"
if [[ -x "$local_bar" ]]; then
    exec "$local_bar" "$@"
fi
exec /usr/bin/waybar "$@"
