#!/usr/bin/env bash
#     ____                 __  ___
#    / __/    _____ ___ __/  |/  /__ ___  __ _____
#   _\ \| |/|/ / _ `/ // / /|_/ / -_) _ \/ // (_-<
#  /___/|__,__/\_,_/\_, /_/  /_/\__/_//_/\_,_/___/
#                  /___/

# Author: ae. Orland
# GitHub: https://github.com/ae-orlando
# =========================================================

# Close the control center before opening a drawer or desktop tool.
set -euo pipefail
swaync-client -cp 2>/dev/null || true
case "${1:-}" in
wifi) exec ~/.config/rofi/launchers/wifi.sh --from-swaync ;;
bluetooth) exec ~/.config/rofi/launchers/rofi-bluetooth --from-swaync ;;
screenshot) exec ~/.config/rofi/launchers/screenshot.sh ;;
powermenu) exec ~/.config/rofi/launchers/powermenu.sh ;;
wallpaper) exec ~/.config/rofi/launchers/wall-changer.sh ;;
audio) exec pavucontrol ;;
annotate) exec "$(dirname -- "${BASH_SOURCE[0]}")/annotate.py" ;;
clipboard) exec "$(dirname -- "${BASH_SOURCE[0]}")/clipboard.py" picker ;;
*)
    echo "usage: $0 wifi|bluetooth|screenshot|powermenu|wallpaper|audio|annotate|clipboard" >&2
    exit 1
    ;;
esac
