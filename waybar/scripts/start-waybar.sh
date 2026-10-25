#!/usr/bin/env bash
# Select the tested local compatibility build, or the distro fallback.
# Author: ae Orland
# GitHub: https://github.com/ae-orlando
set -euo pipefail

local_bar="${XDG_DATA_HOME:-$HOME/.local/share}/yoru/waybar/waybar"
if [[ -x "$local_bar" ]]; then
    exec "$local_bar" "$@"
fi
exec /usr/bin/waybar "$@"
