#!/usr/bin/env bash
# Explicit, serialized radio requests from SwayNC's toggle state.
# Author: ae Orland
# GitHub: https://github.com/ae-orlando
set -euo pipefail
case "${1:-}" in
wifi | bluetooth) ;;
*) printf 'usage: %s wifi|bluetooth\n' "$0" >&2; exit 2 ;;
esac
exec python -B "$HOME/.config/rofi/launchers/connectivity/menu.py" "$1" \
    --power "${SWAYNC_TOGGLE_STATE:-toggle}" --from-swaync
