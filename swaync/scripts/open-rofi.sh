#!/usr/bin/env bash
#   _      ___ ____
#  | | /| / (_) _(_)
#  | |/ |/ / / _/ /
#  |__/|__/_/_//_/

# By ae. Orlando
# =========================================================

# Close the control center, then open a rofi launcher.
# Usage: open-rofi.sh wifi|bluetooth|screenshot|powermenu
set -euo pipefail
swaync-client -cp 2>/dev/null || true
case "${1:-}" in
wifi) exec ~/.config/rofi/launchers/wifi.sh ;;
bluetooth) exec ~/.config/rofi/launchers/rofi-bluetooth ;;
screenshot) exec ~/.config/rofi/launchers/screenshot.sh ;;
powermenu) exec ~/.config/rofi/launchers/powermenu.sh ;;
*)
    echo "usage: $0 wifi|bluetooth|screenshot|powermenu" >&2
    exit 1
    ;;
esac
